import asyncio
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

import aiohttp
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from johnllm import LLMModel
from logging import getLogger

from src.agent.harness import AgentHarness
from src.agent.controllers.observation_contoller import ObservationController, ObservationModel

from scripts.portswigger.data import PORT_SWIGGER_LABS
from scripts.portswigger.agent.agent import CustomAgent as BrowserAgent
from scripts.portswigger.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt

# ────────────────────────────────────────────
# Configuration constants
# ────────────────────────────────────────────
PORTSWIGGER_JSON = "scripts/portswigger/port_swigger_labs.json"
PORTSWIGGER_CREDS = {
    "email": "johnpeng47@gmail.com",
    "password": "i;CZTW8x6p4CTWqL!N8}x~J@9iMbTxyZ",
}
PORTSWIGGER_URL = "https://portswigger.net"
DATA_DIR_PATH = Path("tmp/profiles").resolve()

logger = getLogger(__name__)


# ────────────────────────────────────────────
# Helper dataclass for ObservationController
# ────────────────────────────────────────────
class LabURLObservation(ObservationModel):
    lab_url: str

    def to_msg(self) -> str:
        return self.lab_url


# ────────────────────────────────────────────
# Main runner class
# ────────────────────────────────────────────
class PortSwiggerLabRunner:
    """
    Start PortSwigger Web-Security-Academy labs and continuously
    poll the live-instance URLs to make sure they respond with 200.
    """

    def __init__(
        self,
        labs_to_start: List[Dict[str, List[int]]],
        poll_interval: int = 15,
        headless: bool = False,
        max_agent_steps: int = 15,
    ):
        """
        Parameters
        ----------
        labs_to_start
            Example:
            [
                {"vuln_name": "sql_injection", "labs": [1, 2, 5]},
                {"vuln_name": "xss", "labs": [0]}
            ]
        poll_interval
            Seconds between successive health checks for every live lab.
        headless
            Whether to launch the Playwright browser headless.
        max_agent_steps
            Upper-bound on LLM agent steps when starting a lab.
        """
        self._labs_to_start = labs_to_start
        self._poll_interval = poll_interval
        self._headless = headless
        self._max_steps = max_agent_steps

        # (vuln_name, lab_index) -> live-lab URL
        self._active_labs: Dict[Tuple[str, int], str] = {}
        self._poll_tasks: List[asyncio.Task] = []

    # ────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────
    def run(self) -> None:
        """
        Launch all requested labs sequentially and keep polling them.
        This call blocks (foreground thread) until cancelled (Ctrl-C or
        `asyncio.CancelledError`).
        """
        try:
            asyncio.run(self._async_run())
        except KeyboardInterrupt:
            logger.info("Interrupted by user, shutting down …")

    # ────────────────────────────────────────
    # Private methods
    # ────────────────────────────────────────
    async def _async_run(self) -> None:
        async with aiohttp.ClientSession() as session:
            for spec in self._labs_to_start:
                vuln = spec["vuln_name"]
                for lab_idx in spec["labs"]:
                    url = await self._start_single_lab(vuln, lab_idx)
                    if not url:
                        continue  # Failed to start this lab, skip polling.

                    key = (vuln, lab_idx)
                    self._active_labs[key] = url

                    # Start a long-running polling task.
                    task = asyncio.create_task(
                        self._poll_lab(session, key, url)
                    )
                    self._poll_tasks.append(task)

            # All labs requested; keep polling forever (or until cancelled).
            if self._poll_tasks:
                await asyncio.gather(*self._poll_tasks)

    async def _start_single_lab(self, vuln_category: str, lab_idx: int) -> str | None:
        """
        Return the live-lab URL (e.g. https://<uuid>.web-security-academy.net/)
        or None on error.
        """
        labs = PORT_SWIGGER_LABS[vuln_category]
        if not labs or lab_idx >= len(labs):
            logger.error("Invalid category (%s) or lab index (%s)", vuln_category, lab_idx)
            return None

        lab_href = labs[lab_idx]["link"]
        logger.info("Launching lab %s / #%s …", vuln_category, lab_idx)

        try:
            url = await self._portswigger_labstart_agent(lab_href)
            if url:
                logger.info("✅  %s/#%s → %s", vuln_category, lab_idx, url)
            else:
                logger.error("Failed to capture lab URL for %s/#%s", vuln_category, lab_idx)
            return url
        except Exception:
            logger.exception("Error starting %s/#%s", vuln_category, lab_idx)
            return None

    async def _poll_lab(
        self,
        session: aiohttp.ClientSession,
        key: Tuple[str, int],
        url: str,
    ) -> None:
        """Continuously poll the live-lab URL."""
        vuln, idx = key
        while True:
            try:
                async with session.get(url, timeout=10) as resp:
                    status = resp.status
            except Exception as exc:
                status = f"ERROR – {exc!s}"

            print(f"[{vuln},{idx}] {url} → {status}")
            await asyncio.sleep(self._poll_interval)

    # ────────────────────────────────────────
    # Core logic for starting a single lab
    # ────────────────────────────────────────
    async def _portswigger_labstart_agent(self, lab_href: str) -> str | None:
        """
        Launches a PortSwigger browser/LLM agent that:
        1. Navigates to the lab listing.
        2. Clicks “Access the lab”.
        3. Logs in if redirected.
        4. Captures the redirected, unique lab URL.
        """
        class _LabURLObservation(LabURLObservation):
            """Local subclass to avoid mypy/name-conflict warnings."""

        # Browser config.
        llm = LLMModel()
        window_w, window_h = 1920, 1080
        browser = Browser(
            config=BrowserConfig(
                headless=self._headless,
                disable_security=True,
                # user_data_dir=str(DATA_DIR_PATH / "browser"),
                extra_chromium_args=[f"--window-size={window_w},{window_h}", "--incognito"],
                # chrome_instance_path=(
                #     r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
                # ),
            )
        )

        shared_cfg = {
            "llm": llm,
            "use_vision": False,
            "tool_calling_method": "function_calling",
            "system_prompt_class": CustomSystemPrompt,
            "agent_prompt_class": CustomAgentMessagePrompt,
            "controller": ObservationController(_LabURLObservation),
            "app_id": None,
            "context_cfg": BrowserContextConfig(no_viewport=False),
            "close_browser": True
        }

        agent_prompt = """
Navigate to the following URL:
{url}

Click on "Access THE LAB" to start the lab
If redirected to a login page, use the following creds to login;
{creds}

After logging in successfully, confirm that you have been redirected to the lab page
<important>
After being redirected, make a note of the redirected to URL in memory
</important>
Once this is done, you can exit 
""".format(url=PORTSWIGGER_URL + lab_href, creds=str(PORTSWIGGER_CREDS))
        # agent_prompt = (
        #     "Navigate to the following URL:\n"
        #     f"{PORTSWIGGER_URL}{lab_href}\n\n"
        #     "Click on “Access THE LAB”. If redirected to login, use these creds:\n"
        #     f"{PORTSWIGGER_CREDS}\n\n"
        #     "After successful login, capture the redirected lab URL with "
        #     "`record_observation` and exit."
        # )

        harness = AgentHarness(
            agent_cls=BrowserAgent,
            browser=browser,
            agents_config=[{"task": agent_prompt, "agent_client": None}],
            common_kwargs=shared_cfg,
        )

        try:
            await harness.start_all(max_steps=self._max_steps)
            await harness.wait()

            history_str = str(harness.get_history())
            match = re.search(
                r"https://[0-9a-f]{32}\.web-security-academy\.net/",
                history_str,
            )
            return match.group(0) if match else None
    
        except Exception:
            logger.error(">>>> Error during runnning the agent: ")
            traceback.print_exc(file=sys.stderr)
            return None
        finally:
            logger.error(">>>> Forcibly shutting down the agent: ")
            await harness.kill_all(reason="Done")
            await browser.close()

if __name__ == "__main__":
    from .labs import GENERIC_SUBSET
    from .labs import SQLI_SUBSET_NO_STATE
    from .labs import SQLI_TEST
    from .labs import SSRF_TEST_SINGLE
    from .labs import XSS_TEST_SINGLE

    from scripts.portswigger.data import XSS_APPRENTICE_LABS as TEST_LABS

    # lab test sets
    convert_xss_apprentice_labs = lambda labs: [{"vuln_name": "cross_site_scripting", "labs": labs[0]["labs"][-4:]}]
    apprentice_labs = convert_xss_apprentice_labs(TEST_LABS)

    PortSwiggerLabRunner(apprentice_labs, poll_interval=15, headless=False).run()
