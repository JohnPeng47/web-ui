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
- turn on "MSG NOT IN SCOPE" log line

CC:
- [6] deploy to prod -> use test_discovery_agent, modify and test as successful script
- [10] HTTPMessage.req/res.body no longer has to be async I think since we are not getting them from PW anymore
> hard refactor task
- [2] logging not working for exploit agent
[STRATEGIC]
- browser pool using MITM
> investigate browser hosting frameworks


Business:
- Setup meetings with dynamic scanning companies to see prices
- Probably need to find cheap offering