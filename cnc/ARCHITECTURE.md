AI Cybersecurity Agent — Architecture and Scaling Plan

Overview
- API layer: FastAPI app in `main.py` exposes engagement + agent routes under `routers/`.
- Workers: Long‑running discovery and exploit agent pools under `pools/`, launched via `workers_launcher.start_workers()`.
- Messaging: In‑memory `BroadcastChannel` pub/sub in `services/queue.py` wires API to worker pools.
- Persistence: SQLite via SQLModel models in `database/` with Alembic migrations present.
- Services: Orchestration logic and LLM‑driven scheduling in `services/` (detection, enrichment, engagement merge).

Key Abstractions
- LiveQueuePool: Generic pool handling item consumption and agent execution, used by discovery/exploit pools.
- BroadcastChannel: Minimal pub/sub used for decoupling API producers and worker consumers.
- CRUD layer: `database/crud.py` and `database/agent/crud.py` encapsulate DB operations.

Recent Hardening
- Cooperative shutdown: Pools now accept `stop_event` and honor it for graceful exit. The supervisor wires a single shutdown event through launcher → pools.

Path to Scale (Option B: easy to modify to scale)
1) Pluggable Messaging
   - Introduce an `AbstractChannel` interface (Protocol) and implement `RedisChannel` later. Keep `BroadcastChannel` as the default in‑memory backend for dev/tests.
   - Benefit: swap to Redis/RabbitMQ without touching business logic.

2) Process Separation
   - Run API and worker pools as separate processes (or containers). Communicate via the message broker and HTTP callbacks.
   - Benefit: independent scaling and clearer failure domains.

3) Dependency Injection & Settings
   - Centralize configuration with Pydantic Settings (ports, model configs, Chrome path, proxy, feature flags). Inject into routers and worker launcher.
   - Benefit: remove hardcoded paths and improve environment portability.

4) Observability
   - Replace prints with structured logging throughout and propagate correlation IDs (engagement_id, agent_id) across logs.
   - Optional: OpenTelemetry traces around queue publish/consume and LLM calls.

5) Backpressure & Lifecycle
   - Add bounded queues or per‑subscriber backpressure and an unsubscribe API to avoid unbounded growth.

6) DB Migrations
   - Prefer Alembic migrations over ad‑hoc `ALTER TABLE` in `create_db_and_tables`. Keep `create_all` only for ephemeral dev environments.

Target Operating Modes
- Dev: In‑memory queues + single process (API + workers), SQLite.
- Staging/Prod: Redis queues + separate API/worker services, Postgres, horizontal scale by increasing worker pool size.

