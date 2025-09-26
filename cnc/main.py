import asyncio
import contextlib
import logging
import socket
import uvicorn
from contextlib import asynccontextmanager
from typing import Callable, Any, Type, Union, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from logger import get_or_init_log_factory, SERVER_LOGGER_NAME
from cnc.workers_launcher import start_workers

from cnc.schemas.http import EnrichedRequest, EnrichAuthNZMessage
from cnc.services.queue import BroadcastChannel

from cnc.database.session import create_db_and_tables
from cnc.routers.engagement import make_engagement_router
from cnc.routers.agent import make_agent_router

from cnc.pools.discovery_agent_pool import start_discovery_agent as start_discovery_pool
from cnc.pools.exploit_agent_pool import start_exploit_agent as start_exploit_pool
from cnc.pools.pool import StartDiscoveryRequest, StartExploitRequest

from src.agent.discovery.agent import DiscoveryAgent
from src.agent.discovery.min_agent_single_page import MinimalAgentSinglePage

from src.llm_models import LLMHub

from common.constants import API_SERVER_PORT, SERVER_MODEL_CONFIG

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pentest Hub",
        description="A hub-and-spoke service for pentest traffic collection and analysis",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware with most permissive settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    raw_channel = BroadcastChannel[EnrichAuthNZMessage]()
    enriched_channel = BroadcastChannel[EnrichedRequest]()
    discovery_agent_queue = BroadcastChannel[StartDiscoveryRequest]()
    exploit_agent_queue = BroadcastChannel[StartExploitRequest]()

    app.state.raw_channel = raw_channel
    app.state.enriched_channel = enriched_channel
    app.state.discovery_agent_queue = discovery_agent_queue
    app.state.exploit_agent_queue = exploit_agent_queue

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print("Validation error: %s", exc.errors())

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    llm_hub = LLMHub(function_map=SERVER_MODEL_CONFIG["model_config"])
    engagement_router = make_engagement_router()
    agent_router = make_agent_router(discovery_agent_queue, exploit_agent_queue, llm_hub)
    app.include_router(engagement_router)
    app.include_router(agent_router)
    return app

def preflight_bind(host: str, port: int) -> None:
    """
    Try to bind the socket first to catch Windows WSAEACCES/port reservations early,
    before uvicorn spins up and calls sys.exit(1) on failure.
    """
    af = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(af, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # If you want dual-stack IPv6 + IPv4 on Windows, you'd handle IPV6_V6ONLY here.
        try:
            s.bind((host, port))
        except OSError as e:
            if getattr(e, "errno", None) in (13, 10013):
                raise PermissionError(
                    f"Bind refused on {host}:{port} (permission/access). "
                    f"Another process, reserved range, HTTP.SYS, or policy may own it: {e!r}"
                ) from e
            raise
        # Close immediately; this is only a check.


async def serve_uvicorn(app: FastAPI, host: str, port: int, shutdown_event: asyncio.Event) -> None:
    preflight_bind(host, port)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        # Avoid uvicorn installing signal handlers on Windows runner
        # (it is mostly a no-op on Windows, but be explicit)
        loop="asyncio",
        lifespan="on",
    )
    server = uvicorn.Server(config=config)

    async def _run() -> None:
        try:
            await server.serve()
        except SystemExit as se:
            # Uvicorn calls sys.exit(1) on startup failure; translate to normal exception
            raise RuntimeError(f"bind_failed: {host}:{port} (uvicorn SystemExit {se.code})") from se
        except OSError as e:
            if getattr(e, "errno", None) in (13, 10013):
                raise RuntimeError(
                    f"bind_failed: {host}:{port} (permission/access): {e!r}"
                ) from e
            raise

    task = asyncio.create_task(_run(), name="uvicorn-serve")

    done, pending = await asyncio.wait(
        {task, asyncio.create_task(shutdown_event.wait(), name="shutdown-wait")},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if shutdown_event.is_set() and not task.done():
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            print("Uvicorn did not stop within timeout; forcing exit")
            server.force_exit = True
            with contextlib.suppress(Exception):
                await task

    for d in done:
        if d is task:
            exc = d.exception()
            if exc:
                raise exc


async def workers_supervisor(
    app: FastAPI,
    shutdown_event: asyncio.Event,
    start_discovery_pool_fn: Callable[[BroadcastChannel], Any],
    start_exploit_pool_fn: Callable[[BroadcastChannel], Any],
    discovery_agent_cls: Type[Union[DiscoveryAgent, MinimalAgentSinglePage]],
    override_max_steps: Optional[int],
) -> None:
    try:
        await start_workers(
            start_discovery_pool=start_discovery_pool_fn,
            start_exploit_pool=start_exploit_pool_fn,
            app=app,
            discovery_agent_cls=discovery_agent_cls,
            override_max_steps=override_max_steps,
        )
    except Exception as e:
        print("Worker subsystem failed: %r", e)
        shutdown_event.set()
        raise
    finally:
        shutdown_event.set()


async def start_all(
    start_discovery_pool: Callable[[BroadcastChannel], Any],
    discovery_agent_cls: Type[Union[DiscoveryAgent, MinimalAgentSinglePage]] = DiscoveryAgent,
    override_max_steps: Optional[int] = 12,
) -> None:
    print(f"Starting api server on {'0.0.0.0'}:{API_SERVER_PORT}")

    get_or_init_log_factory(base_dir=".server_logs")
    
    app_instance = create_app()
    shutdown_event = asyncio.Event()
    workers_task = asyncio.create_task(
        workers_supervisor(
            app=app_instance,
            shutdown_event=shutdown_event,
            start_discovery_pool_fn=start_discovery_pool,
            start_exploit_pool_fn=start_exploit_pool,
            discovery_agent_cls=discovery_agent_cls,
            override_max_steps=override_max_steps,
        ),
        name="workers",
    )
    api_task = asyncio.create_task(
        serve_uvicorn(app_instance, host="0.0.0.0", port=API_SERVER_PORT, shutdown_event=shutdown_event),
        name="api",
    )

    try:
        done, pending = await asyncio.wait({workers_task, api_task}, return_when=asyncio.FIRST_EXCEPTION)
        for d in done:
            exc = d.exception()
            if exc:
                shutdown_event.set()
                raise exc
    finally:
        shutdown_event.set()
        for t in (workers_task, api_task):
            if not t.done():
                t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(workers_task, api_task, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(start_all(start_discovery_pool))
    except PermissionError as e:
        # Clean, explicit message for the Windows bind case
        print("%s", e)
        raise
    except RuntimeError as e:
        # Includes "bind_failed" from uvicorn/SystemExit translation
        if "bind_failed" in str(e):
            print("%s", e)
        raise
