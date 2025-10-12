import re
import sys
import traceback

from old_browser_use.browser.browser import Browser, BrowserConfig
from old_browser_use.browser.context import BrowserContextConfig

from src.llm_models import LLMHub
from common.constants import DISCOVERY_MODEL_CONFIG

from src.agent.old_agent.agent.controllers.observation_contoller import ObservationController
from src.agent.old_agent.agent.custom_agent import CustomAgent as BrowserAgent
from src.agent.old_agent.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt

# ────────────────────────────────────────────
# Extracted function for running a single task agent
# ────────────────────────────────────────────
async def start_single_task_agent(task_prompt: str, headless: bool = False, max_steps: int = 15) -> str | None:
    """
    Launches a PortSwigger browser/LLM agent with a custom task prompt.
    
    Parameters
    ----------
    task_prompt
        The task prompt to give to the agent
    headless
        Whether to launch the Playwright browser headless
    max_steps
        Upper-bound on LLM agent steps
        
    Returns
    -------
    str | None
        The extracted lab URL if found, None otherwise
    """
    # Browser config.
    llm = LLMHub(function_map=DISCOVERY_MODEL_CONFIG["model_config"])
    window_w, window_h = 1920, 1080
    browser = Browser(
        config=BrowserConfig(
            headless=headless,
            disable_security=True,
            # user_data_dir=str(DATA_DIR_PATH / "browser"),
            extra_chromium_args=[f"--window-size={window_w},{window_h}", "--incognito"],
            # chrome_instance_path=(
            #     r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
            # ),
        )
    )

    browser_context = None
    agent = None
    
    try:
        # Create browser context
        context_cfg = BrowserContextConfig(no_viewport=False)
        browser_context = await browser.new_context(config=context_cfg)
        
        # Create agent directly
        agent = BrowserAgent(
            start_urls=[],
            llm=llm,
            start_task=task_prompt,
            browser=browser,
            browser_context=browser_context,
            use_vision=False,
            tool_calling_method="function_calling",
            system_prompt_class=CustomSystemPrompt,
            agent_prompt_class=CustomAgentMessagePrompt,
            app_id=None,
            close_browser=True,
            agent_client=None,
        )
        
        # Run the agent
        result = await agent.run(max_steps=max_steps, page_max_steps=10)
        
        # Extract lab URL from history
        history_str = str(result.model_dump())
        match = re.search(
            r"https://[0-9a-f]{32}\.web-security-academy\.net/",
            history_str,
        )
        return match.group(0) if match else None

    except Exception:
        print(">>>> Error during running the agent: ")
        traceback.print_exc(file=sys.stderr)
        return None
    finally:
        print(">>>> Shutting down the agent")
        # Clean up resources
        if agent:
            try:
                await agent.shutdown("Done")
            except Exception as e:
                print(f"Agent shutdown failed: {e}")
        
        if browser_context:
            try:
                await browser_context.close()
            except Exception as e:
                print(f"Browser context close failed: {e}")
        
        try:
            await browser.close()
        except Exception as e:
            print(f"Browser close failed: {e}")

