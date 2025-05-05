import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence, Type, Literal
from pydantic import BaseModel
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig

from src.agent.custom_agent import CustomAgent   # or wherever your agent lives

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AgentLogin(BaseModel):
    username: str | None = None
    email: str | None = None
    role: str
    password: str
    
    @classmethod
    def model_validator(cls, values):
        if not values.get("username") and not values.get("email"):
            raise ValueError("At least one of username or email must be provided")
        return values
    
class AgentHarness:
    def __init__(
        self,
        agents_config: Sequence[Dict[str, Any]],
        agent_cls: Type[CustomAgent] = CustomAgent,
        browser: Browser | None = None,
        context_strategy: Literal["shared", "per_agent"] = "shared",
        common_kwargs: Dict[str, Any] | None = None,
    ):
        self.agent_cls = agent_cls
        self.agents_cfg = list(agents_config or [])
        self.browser = browser
        self.context_strategy = context_strategy
        self.common_kwargs = common_kwargs or {}
        self._agents: List[CustomAgent] = []
        self._tasks: List[asyncio.Task] = []
        self._contexts: list[BrowserContext] = []

    async def _build_context(self, cfg: Dict[str, Any]) -> BrowserContext | None:
        """Create context if harness is supposed to own it."""
        if not self.browser:
            return None
        ctx_cfg: BrowserContextConfig = cfg.pop("context_cfg", BrowserContextConfig())
        ctx = await self.browser.new_context(config=ctx_cfg)
        self._contexts.append(ctx)
        return ctx

    async def start_all(self, max_steps: int = 100):
        logger.info("Spawning %d agents …", len(self.agents_cfg))

        for raw_cfg in self.agents_cfg:
            # Merge: per‑agent keys override common defaults
            cfg = {**self.common_kwargs, **raw_cfg}

            if "browser_context" not in cfg:
                match self.context_strategy:
                    case "shared":
                        if not self._contexts:
                            ctx = await self._build_context(cfg)
                        else:
                            ctx = self._contexts[0]
                        cfg["browser_context"] = ctx
                    case "per_agent":
                        cfg["browser_context"] = await self._build_context(cfg)

            agent = self.agent_cls(**cfg)
            self._agents.append(agent)

            task = asyncio.create_task(self._run_agent(agent, max_steps))
            self._tasks.append(task)

        return self._tasks

    async def kill_all(self, reason: str = "kill"):
        logger.warning("Kill‑switch activated: %s", reason)
        await asyncio.gather(
            *(agent.shutdown(reason) for agent in self._agents),
            return_exceptions=True,
        )
        for task in self._tasks:
            if not task.done():
                task.cancel()

        for ctx in self._contexts:
            try:
                await ctx.close()
            except Exception as e:
                logger.debug("Context close failed: %s", e)

    async def wait(self):
        done, _ = await asyncio.wait(self._tasks, return_when=asyncio.ALL_COMPLETED)
        for t in done:
            if exc := t.exception():
                logger.error("Agent task raised: %s", exc)

    async def _run_agent(self, agent: CustomAgent, max_steps: int):
        try:
            await agent.run(max_steps=max_steps)
        except asyncio.CancelledError:
            logger.info("Agent cancelled")
        except Exception as e:
            logger.exception("Agent crashed: %s", e)

# ---------- quick demo ---------- #
if __name__ == "__main__":
    import sys
    import traceback
    from datetime import datetime
    import httpx
    from src.agent.client import AgentClient
    from browser_use.browser.browser import Browser, BrowserConfig
    from browser_use.browser.context import (
        BrowserContextConfig,
        BrowserContextWindowSize,
    )
    from johnllm import LLMModel
    from src.agent.custom_prompts import CustomAgentMessagePrompt, CustomSystemPrompt

    async def main():
        try:
            # Create the client
            main_client = AgentClient(
                username="admin",
                role="scanner",
                client=httpx.AsyncClient(base_url="http://localhost:8001"),
            )
            
            # Create a new application
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            app_name = f"AgentIntruderTest_{timestamp}"
            app_description = f"Automated test application created at {timestamp}"
            
            print(f"Creating application: {app_name}")
            app_id = await main_client.create_application(app_name, app_description)
            print(f"Application created successfully:")
            print(f"  ID: {app_id}")

            # Agent client with credentials
            agent_client = AgentClient(
                username="tenant1",
                role="scanner",
                client=httpx.AsyncClient(base_url="http://localhost:8001"),
            )
            
            creds = {
                "credentials": {
                    "username": "evil_corp-store_admin1",
                    "password": "password123"
                }
            }
            
            AGENT_PROMPT = """
Navigate to the following URL:
http://localhost:8000/products/

Find an existing product and edit its descriptions
If you are faced with a login screen, use these credentials:
{creds}

Exit after you have successfully edited the product and redirected
""".format(creds=str(creds))
            
            # Setup browser
            llm = LLMModel()
            window_w, window_h = 1920, 1080
            use_vision = False
            browser = Browser(
                config=BrowserConfig(
                    headless=False,
                    disable_security=True,
                    extra_chromium_args=[f"--window-size={window_w},{window_h} --incognito"],
                    chrome_instance_path=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe"
                )
            )
            
            # Configure agent
            agents_cfg = [{
                "task": AGENT_PROMPT,
                "llm": llm,
                "use_vision": use_vision,
                "tool_calling_method": "function_calling",
                "system_prompt_class": CustomSystemPrompt,
                "agent_prompt_class": CustomAgentMessagePrompt,
                "agent_client": agent_client,
                "app_id": app_id,
                "context_cfg": BrowserContextConfig(
                    no_viewport=False,
                    browser_window_size=BrowserContextWindowSize(
                        width=window_w, height=window_h
                    ),
                )
            }]
            
            # Create and run harness
            harness = AgentHarness(
                agents_config=agents_cfg,
                browser=browser,
                context_strategy="per_agent"
            )

            # Start agent
            print(f"\nLaunching agent for application ID: {app_id}")
            await harness.start_all(max_steps=15)
            await harness.wait()
            print("Agent completed successfully")
                
            await browser.close()
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            print("\nTraceback (most recent call last):", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return 1
        
        return 0

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main()))
