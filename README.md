2025/09/02:
[TODO]
Human
- Exploit Agent:
> Get logging working
> Change ainvoke
> Need to test if ainvoke is blocking -> (important write tests)
- Start deprecating pentest_bot and moving agent logic into src/exploit and moving eval harnesses into eval/harness/exploit
- Consolidate cost logging feature:
> Centralize llm_config initialization and move outside of agents
- Integrating Authz/AuthN attacker:
> also integrate user_id into "Agent Activity" component
>> this in itself might become a sub-workflow for 
- Support Dynamic Agent Interaction:
> add support for agent snapshots
> pause/modify agent responses
- Try BrowserUse Session rewrite
- Need to introduce pages

2025/09/23
- Test
- New Detection Module
> 3 diff modes for page/req/global scoped action scheduling
- Http Proxy
> parse non-JSON responses
>> script
>> html
>> binary
- test_http_proxy:
> future: put
- Deployment
> Current setup with start proxy/browser combo is not ideal 

2025/09/24
> Confirm that ainvoke with detection is working
> Explore:
>> do the scheduled actions match vulns to be found on these pages
>> add request level and page level detection triggered by API
>> test prompt with different levels of automaticity
>> hierarchal pageData breakdown by pages (maybe not rn since this requires persisted state in DetectScheduler) 
>> tagging an agent with search tags so that we can better look for the results later
> Agent:
>> * add agent results to model -> no matter this should update 
> Deployment to hostinger server

Think:
> When should we start building custom web-apps for testing vulns?

TODOs:
- Discovery
--> [OPTIMIZATION] save completed tasks in discovery agents so we dont end up completing the same tasks again

CC:
- [6] deploy to prod -> use test_discovery_agent, modify and test as successful script
- [10] HTTPMessage.req/res.body no longer has to be async I think since we are not getting them from PW anymore
> hard refactor task
- [2] logging not working for exploit agent
> Refactors
1. Refactor agents CreateExploit/Discovery agent in [](cnc/schemas/agent.py) to remove model_name, model_cost, and log_filepath
> these should not be apart of the create 

[STRATEGIC]
- browser pool using MITM
> investigate browser hosting frameworks


Business:
- Setup meetings with dynamic scanning companies to see prices
- Probably need to find cheap offering