import asyncio
import logging

from typing import List, Optional
from pathlib import Path

from browser_use.browser import BrowserSession
from browser_use.controller.service import Controller
from browser_use.agent.views import ActionResult

from src.agent.discovery.agent import DiscoveryAgent
from src.llm_models import LLMHub
from cnc.workers.agent.cdp_handler import CDPHTTPHandler
from src.agent.discovery.proxy import MitmProxyHTTPHandler
from src.agent.discovery.pages import Page

# clients
from src.agent.agent_client import AgentClient
from eval.client import PagedDiscoveryEvalClient

INCLUDE_ATTRIBUTES: List[str] = (
    ["title", "type", "name", "role", "aria-label", "placeholder", "value", "alt"]
)

class MinimalAgentSinglePage(DiscoveryAgent):
    """
    A subclass of MinimalAgent that visits a single page without executing LLM actions.
    Simply visits the page and triggers necessary state updates.
    """

    def __init__(
        self,
        llm: LLMHub,
        agent_sys_prompt: str,
        browser_session: BrowserSession,
        controller: Controller,
        start_urls: List[str],
        max_steps: int = 50,
        max_page_steps: int = 10,
        *,
        challenge_client: Optional[PagedDiscoveryEvalClient] = None,
        server_client: Optional[AgentClient] = None,
        cdp_handler: MitmProxyHTTPHandler | None = None,
        agent_dir: Path,
        init_task: Optional[str] = None,
        screenshots: bool = False,
        agent_log: Optional[logging.Logger] = None,
        full_log: Optional[logging.Logger] = None,
    ):
        super().__init__(
            llm=llm,
            agent_sys_prompt=agent_sys_prompt,
            browser_session=browser_session,
            controller=controller,
            start_urls=start_urls,
            max_steps=max_steps,
            max_page_steps=max_page_steps,
            challenge_client=challenge_client,
            server_client=server_client,
            cdp_handler=cdp_handler,
            agent_dir=agent_dir,
            init_task=init_task,
            screenshots=screenshots,
            agent_log=agent_log,
            full_log=full_log,
        )

    async def step(self):
        """
        Overridden step function that:
        1. Dequeues a single page from start_urls
        2. Visits the page
        3. Does not execute any LLM actions
        4. Triggers all necessary updates
        """
        # Only process if we have URLs to visit and haven't started this page yet
        if self.page_step == 0 and self.urls:
            self._log(f"[PAGE_TRANSITION]: Processing single page")

            # Dequeue a single URL
            self.curr_url = self.urls.pop(0)
            await self._goto_page(self.curr_url)
            self.pages.add_page(Page(url=self.curr_url))

            # Get browser state and update DOM
            browser_state = await self._get_browser_state()
            self.curr_dom_str = browser_state.dom_state.llm_representation(include_attributes=INCLUDE_ATTRIBUTES)
            self.curr_dom_tree = browser_state.dom_tree

            # Create plan if not in init_task mode
            if not self._init_task:
                self._create_new_plan()
            else:
                self.task = self._init_task

            # Create empty results list (no LLM actions executed)
            results: List[ActionResult] = []

            # Update state with empty model output and results
            # from browser_use.agent.views import AgentBrain
            # empty_brain = AgentBrain(
            #     evaluation_previous_goal="No previous goal - single page visit",
            #     next_goal="Page visited successfully", 
            #     current_state="Page loaded and processed"
            # )
            
            # # Update agent context and state
            # await self._update_state(browser_state, None, results)
            # self.agent_state.is_done = True  # Mark as done after visiting the page

            # Update page state with proxy handler messages if available
            if self.cdp_handler:
                msgs = await self.cdp_handler.flush()
                for msg in msgs:
                    self.pages.curr_page().add_http_msg(msg)
                    print(f"[{msg.method}] {msg.url}")
                if self.challenge_client:
                    await self.challenge_client.update_status(
                        msgs, 
                        self.curr_url, 
                        self.agent_state.step, 
                        self.page_step,
                    )
                if self.server_client:
                    self.page_skip = await self.server_client.update_page_data(
                        self.agent_state.step,
                        self.agent_state.max_steps,
                        self.page_step, 
                        self.max_page_steps,
                        self.pages
                    )
                    
            self._log(f"Single page visit completed for: {self.curr_url}")
        else:
            # No more URLs to process or already processed
            self.agent_state.is_done = True
            self._log("No more pages to visit - agent done")

    async def run(self):
        await self.step()
        print("Single page agent run completed!")