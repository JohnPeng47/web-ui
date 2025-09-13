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
1. encodes the subclass info in JSON format
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
- Modify start_agent server to work without the routes, so we can avoid triggering side effects -> create and label these fixtures
- [BUG] auto-incremented, table specific ID for both discovery/exploit agents, need to consilidate into single ID
- add the fastapi specific instructions
2025/09/12:
- [DESIGN] change page_data API to accept engagementID instead
- [FEATURE]
> need to have resettable state for agent runs so we can restart failed runs 
> API change:
>> create agent and start agent separate APIs
>> start agent can take be used to restart agent
- [FEATURE]
> 
=========================
===== HIGH THOUGHTS =====
- brainstorm how to construct an a/b test
> commits!
> if we can isolate fully remote commits, and context, then we can do a/b testing to determine the effectiveness of different context patterns
> part of what we need to monitor on
Deployment Notes:
- do a grep for http:// to make sure we have all the schemas configured properly for HTTPS
- yo
- what we build our inline-tree editing thing to do in-line code-gen project management 
=========================

# spend last 2 hours on front end UI

Goals next week:
- get code ready so that it can be refactored on and worked on by CC and systems
- continue 
=================
Claude Code Comments
=================
# TODO:
- should create mapping of doc to live references that change
> parse @location and check on every commit, if the mapping has changed
> essentially parse every entity relationship in doc and iterate if changes are required in the docs
- identify parts of the code that have strong logical components
- refactoring check over the import boundaries to assure that these relationships hold
- generate grep patterns for each of the lines above
- extract from description to add a git commit hook to look at the message
- derive a set of rules from above to apply to each commit to check if any of these are broken

Positives:
1. if we define doc, we can then actually abstract out implementation and make it easy to port code over to Golang eventually
2. we can use the same abstractions to generate our vulnerable web apps