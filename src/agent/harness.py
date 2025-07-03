from __future__ import annotations

"""
Agent harness that supervises multiple ``CustomAgent`` instances and abstracts
browser lifecycle management – including connecting to an *already running*
Chrome/Edge instance over the Chrome DevTools Protocol (CDP).

Usage example
-------------
>>> harness = AgentHarness(
        agents_config=[{"start_url": "http://localhost:3000"}],
        cdp_url="http://localhost:9222",  # Connect to remote Chromium
        common_kwargs={"max_steps": 50},
    )
>>> await harness.start_all()
>>> await harness.wait()

New in this revision
--------------------
* **CDP support** – pass a ``cdp_url`` to connect to a remote browser without
  spawning a local Playwright instance.
* **Automatic browser bootstrap** – if neither a ``Browser`` instance nor a
  ``BrowserConfig`` is supplied, the harness will attempt to build one from the
  provided CDP URL or fall back to sensible defaults.
* Cleaner structure – smaller helpers, private state encapsulation, and
  stricter typing.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence, Type

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from pydantic import BaseModel

from src.agent.custom_agent import CustomAgent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentHarness:
	"""Supervisor for multiple :class:`~src.agent.custom_agent.CustomAgent`\ s.

	Each agent gets its *own* :class:`BrowserContext`.  Those contexts are closed
	when the harness is torn down.
	"""

	def __init__(
		self,
		agents_config: Sequence[Dict[str, Any]],
		agent_cls: Type[CustomAgent] = CustomAgent,
		browser: Browser | None = None,
		browser_config: BrowserConfig | None = None,
		*,
		cdp_url: str | None = None,
		common_kwargs: Optional[Dict[str, Any]] = None,
	):
		# --- resolve browser --------------------------------------------------
		if browser and browser_config:
			raise ValueError("Pass either 'browser' **or** 'browser_config', not both")

		self._owns_browser = False  # Track whether *we* created the browser

		if browser is None:
			if browser_config is None and cdp_url is None:
				raise ValueError(
					"AgentHarness requires at least 'browser', 'browser_config' or 'cdp_url'"
				)

            # NOTE: does not currently work!
			# Build config from CDP URL if provided
			if browser_config is None:
				browser_config = BrowserConfig(cdp_url=cdp_url or "")

			browser = Browser(config=browser_config)
			self._owns_browser = True

		self.browser: Browser = browser  # type: ignore[assignment]
		self.agent_cls = agent_cls
		self.agents_cfg = list(agents_config)
		self.common_kwargs = common_kwargs or {}

		# runtime state
		self._agents: List[CustomAgent] = []
		self._tasks: List[asyncio.Task] = []
		self._contexts: List[BrowserContext] = []  # contexts created by us
		self._history: List[Dict[str, Any]] = []

	# ---------------------------------------------------------------------
	# public API
	# ---------------------------------------------------------------------

	async def start_all(self, *, max_steps: int = 100, page_max_steps: int = 10) -> List[asyncio.Task]:
		"""Instantiate & launch every agent.  Returns the list of *running* tasks."""

		logger.info("Spawning %d agents …", len(self.agents_cfg))

		for raw_cfg in self.agents_cfg:
			cfg = {**self.common_kwargs, **raw_cfg}

			# 1️⃣ Ensure a BrowserContext is present (create one if needed)
			if "browser_context" not in cfg:
				ctx_cfg: BrowserContextConfig = cfg.pop(
					"context_cfg", BrowserContextConfig()
				)
				browser_context = await self.browser.new_context(config=ctx_cfg)
				self._contexts.append(browser_context)
				cfg["browser_context"] = browser_context

			# 2️⃣ Provide browser reference so agents can issue *global* shutdown
			cfg.setdefault("browser", self.browser)

			# 3️⃣ Instantiate and schedule the agent
			agent = self.agent_cls(**cfg)
			self._agents.append(agent)
			task = asyncio.create_task(self._run_agent(agent, max_steps, page_max_steps))
			self._tasks.append(task)

		return self._tasks

	async def wait(self) -> None:
		"""Wait until **all** agent tasks complete (or raise)."""

		done, _ = await asyncio.wait(self._tasks, return_when=asyncio.ALL_COMPLETED)
		for t in done:
			if exc := t.exception():
				logger.error("Agent task raised: %s", exc)

	async def kill_all(self, *, reason: str = "kill") -> None:
		"""Gracefully stop every agent & clean up resources."""

		logger.warning("Kill‑switch activated: %s", reason)

		# Shutdown agents first (they might persist local state)
		await asyncio.gather(
			*(agent.shutdown(reason) for agent in self._agents),
			return_exceptions=True,
		)

		# Cancel any tasks that are still running
		for task in self._tasks:
			if not task.done():
				task.cancel()

		# Close contexts we own
		await asyncio.gather(*(ctx.close() for ctx in self._contexts), return_exceptions=True)

		# Close browser if we started it
		if self._owns_browser:
			try:
				await self.browser.close()
			except Exception as e:  # pragma: no cover – defensive
				logger.debug("Browser close failed: %s", e)

	# ---------------------------------------------------------------------
	# helpers
	# ---------------------------------------------------------------------

	async def _run_agent(self, agent: CustomAgent, max_steps: int, page_max_steps: int) -> None:
		"""Run a *single* agent and collect its history."""

		try:
			result = await agent.run(max_steps=max_steps, page_max_steps=page_max_steps)
			self._history.append(result.model_dump())
		except asyncio.CancelledError:
			logger.info("Agent cancelled")
		except Exception as e:
			logger.exception("Agent crashed: %s", e)

	def get_history(self) -> List[Dict[str, Any]]:
		"""Return agents' run histories **without** embedded screenshots."""

		def _strip(d: Any):
			if isinstance(d, dict):
				return {k: _strip(v) for k, v in d.items() if k != "screenshot"}
			if isinstance(d, list):
				return [_strip(x) for x in d]
			return d

		return _strip(self._history)
