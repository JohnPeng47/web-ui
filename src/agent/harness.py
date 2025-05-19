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
    
import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence, Type, Literal

from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from pydantic import BaseModel

from src.agent.custom_agent import CustomAgent  # adjust import to your tree


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentHarness:
    """
    Spawns and supervises multiple CustomAgent instances.

    • If `browser` is supplied, a **new BrowserContext** is created for each agent
      unless the agent’s config already specifies `browser_context`.
    • Contexts created by the harness are tracked and closed by `kill_all()`.
    """

    def __init__(
        self,
        agents_config: Sequence[Dict[str, Any]],
        agent_cls: Type[CustomAgent] = CustomAgent,
        browser: Browser | None = None,
        common_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.agent_cls = agent_cls
        self.agents_cfg = list(agents_config or [])
        self.browser = browser
        self.common_kwargs = common_kwargs or {}

        self._agents: List[CustomAgent] = []
        self._tasks: List[asyncio.Task] = []
        self._contexts: List[BrowserContext] = []   # contexts we own
        self._history: List[Dict] = []

    # ---------- public API -------------------------------------------------

    async def start_all(self, max_steps: int = 100):
        """
        Build and launch every agent.  Returns the list of asyncio.Tasks.
        """
        logger.info("Spawning %d agents …", len(self.agents_cfg))

        for raw_cfg in self.agents_cfg:
            cfg = {**self.common_kwargs, **raw_cfg}

            # 1. Ensure a BrowserContext is present
            if "browser_context" not in cfg:
                if not self.browser:
                    raise RuntimeError(
                        "AgentHarness needs either an explicit "
                        "`browser_context` in each agent config or a global "
                        "`browser` to create contexts from."
                    )

                # Per‑agent context config can be passed via `context_cfg`
                ctx_cfg: BrowserContextConfig = cfg.pop(
                    "context_cfg", BrowserContextConfig()
                )
                browser_context = await self.browser.new_context(config=ctx_cfg)

                self._contexts.append(browser_context)   # keep track
                cfg["browser_context"] = browser_context
                
                if cfg.get("agent_client"):
                    cfg["agent_client"].set_shutdown(self.kill_all)

            # so agent can kill browser
            if self.browser:
                cfg["browser"] = self.browser

            # 2. Instantiate and launch the agent
            agent = self.agent_cls(**cfg)
            self._agents.append(agent)

            task = asyncio.create_task(self._run_agent(agent, max_steps))
            self._tasks.append(task)

        return self._tasks

    async def wait(self):
        done, _ = await asyncio.wait(self._tasks, return_when=asyncio.ALL_COMPLETED)
        for t in done:
            if exc := t.exception():
                logger.error("Agent task raised: %s", exc)

    async def kill_all(self, reason: str = "kill"):
        """
        Stops every agent, cancels outstanding tasks, and closes all contexts
        created by the harness.
        """
        logger.warning("Kill‑switch activated: %s", reason)

        # Ask agents to shut down gracefully
        await asyncio.gather(
            *(agent.shutdown(reason) for agent in self._agents),
            return_exceptions=True,
        )

        # Cancel any lingering tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Close contexts that *we* created
        for ctx in self._contexts:
            try:
                await ctx.close()
            except Exception as e:
                logger.debug("Context close failed: %s", e)

    # ---------- helpers ----------------------------------------------------

    async def _run_agent(self, agent: CustomAgent, max_steps: int):
        try:
            history = await agent.run(max_steps=max_steps)
            self._history.append(history.model_dump())
        except asyncio.CancelledError:
            logger.info("Agent cancelled")
        except Exception as e:
            logger.exception("Agent crashed: %s", e)

    def get_history(self):
        """
        Returns the history of all agents.
        """
        def remove_screenshots(d):
            if isinstance(d, dict):
                return {k: remove_screenshots(v) for k, v in d.items() if k != "screenshot"}
            elif isinstance(d, list):
                return [remove_screenshots(x) for x in d]
            return d
            
        return remove_screenshots(self._history)
