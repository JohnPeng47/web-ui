==================== TODOS =====================
Bugs:
- should do periodic performance testing to ensure that slowdown issue from e6f36ec doesnt show up
- check if ainvoke is blocking in exploitAgent

Internal:
- construct dataset for web agents
- consolidate cost logging for LLMs
- HTTPRequest parsing different payload data
> how to handle error?
> handling more exotic datatypes?
- set up monoRepo for integrated FE/BE agent dev

Features:
- Integrating Authz/AuthN attacker:
> also integrate user_id into
- Resetable agents via snapshots
> pausing/editing/rerunning agent
- Improving Discovery agent
> dynamic max_page_steps for each page implemented in CreatePlan
>> Planning: "@agent.py Currently max_page_steps is set statically for each new page. I want add new logic that piggies back off of _create_new_plan to estimate the number of steps required "

Refactor:
- Only single init of MITMProxy should happen per server instance, but it is currently initialized per Discovery Agent in the Discovery Agent Pool. Should just attach single instance to app.state
- Unify proxy.log with agent_log -> tricky thing is we cant correlate by context_var since MITMProxy http handler forks new thread to handle each req/res flow

Design:
- Workflow for saving/running deterministic test cases
- Plugin system?
> where to expose the APIs

==================== DEV NOTES ====================
2025/10/11:
- added tests that confirmed MITMProxy handles edge cases without crashing
> probably will still need more robust HTTP handling a la httptoolkit