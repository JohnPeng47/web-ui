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

Design:
- Workflow for saving/running deterministic test cases
- Plugin system?
> where to expose the APIs

==================== DEV NOTES ====================
2025/10/11:
- added tests that confirmed MITMProxy handles edge cases without crashing
> probably will still need more robust HTTP handling a la httptoolkit