2025/09/02:
- Start deprecating pentest_bot and moving agent logic into src/exploit and moving eval harnesses into eval/harness/exploit
--> AMF, should move start_*agent into eval/harness/discovery
2025/09/03:
- Inventory all hardcoded variaables, remote services (ie. Opik). Especially important are filepaths and env variables that need to be taken into account during deployment to another environment ( linux environment)
- DEBT: currently only PageItem is HTTPMessage. Should be genericized to include more things. Affects: 
Detect -> Queue (item) -> Convert to Exploit Prompt
Files:
> src/detection/prompts.py
> src/agent/pages.py
> eval/harness/exploit/eval_agent_pool.py
- DEBT: HTTPMessage.req/res.body no longer has to be async I think since we are not getting them from PW anymore
- Logging is fucked for AgentPool
2025/09/04:
- MITM local proxy will not work for remote browsers
> should be deprecating in favor of CDP anyways
- Initialize LLM configs at one of the parent layers instead of inside PentestSession
2025/09/04:
TODO:
> make get_browser_session do more retries ..
> we should make use of HTTP endpoints to accept queue updates from the clients because this gives us:
1. access to db
2. flexibility to trigger other logic -> such as queueing up another agent request 
- Relationship kinda weird between:
1. DB models
2. FastAPI schemas
3. DB accessors
> DB models <- FastAPI schemas
> DB accessors are implemented in database folder
- move all common type definitions of agents into src/detection, src/discovery, src/exploit
> src.agent -> src.exploit
- add a dynamic adapter class for handling serializing/deserializing data for UserRole and AgentSteps that:
1. encodes the subclass     info in JSON format
2. can read 1. and dynamically choose the appropriate serialization routine
- currently not supporting UserRole based testing
- add agent service to configure things like configuring LLMs before calling 
DB crud API
- should implement a GET agent request in AgentClient to confirm agent_id
2025/09/05:
- CDP traffic interception bonked, using MITMProxy for now
- [BUG] Proxy handler not catching any response data
> Seems to catch for some request on homepage
- [FIX] BrowserUse browser session connection script
- [REFACTOR] Convert _invoke in PentestSession to async
- [BUG] Error here:
> await self.server_client.update_page_data(self.pages)
> httpx timeout error (Big request ??)
> or possibly thread is blocked
- Split off features that can be completed with CC vs. those that need manual attention
Error Handling:
- Better error handling at run_mitm (currently mitm loop crashes on http error from agent error)
> [DESIGN] need better error isolation between workers
- Finish writing CLAUDE_CODE.md
- [FIX] generating ALTER syntax for alembic

Deployment Notes:
- do a grep for http:// to make sure we have all the schemas configured properly for HTTPS

# spend last 2 hours on front end UI

Goals next week:
- refactor code to a point where we can start running CC and CodexCLI on it
- continue 
