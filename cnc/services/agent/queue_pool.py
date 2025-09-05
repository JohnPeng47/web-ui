import asyncio
import threading
from typing import Optional, TypeVar, Type

from pydantic import BaseModel

from common.agent import AgentPool
from logger import get_agent_loggers
from cnc.services.queue import BroadcastChannel

agent_log, full_log = get_agent_loggers()

T = TypeVar("T", bound=BaseModel)

class LiveQueuePool(AgentPool[T]):
    def __init__(
        self,
        *,
        channel: BroadcastChannel[T],
        item_cls: Optional[Type[T]] = None,
        queue_fp: Optional[str] = None,
        llm_config: dict,
        max_workers: Optional[int] = None,
        log_subfolder: str = "pentest_bot",
        label_steps: bool = False,
    ):
        super().__init__(
            llm_config=llm_config,
            max_workers=max_workers,
            log_subfolder=log_subfolder,
            label_steps=label_steps,
        )
        self._channel = channel
        self._item_cls = item_cls
        self._queue_fp = queue_fp
        # Each pool instance keeps its own subscription queue
        self._sub_queue: asyncio.Queue[T] = self._channel.subscribe()

        # Bookkeeping for the consumer task
        self._consumer_task: Optional[asyncio.Task] = None
        self._consumer_lock = threading.Lock()
        self._stop_event: asyncio.Event = asyncio.Event()
        self._install_sigint_handler()

    async def start_channel_consumer(self) -> asyncio.Task:
        """
        Start an async consumer that continuously pulls from a live
        BroadcastChannel subscription and enqueues agent runs.

        Runs indefinitely until `stop_channel_consumer` is called, using
        an internal asyncio.gather to keep the loop alive alongside a
        stop-event waiter.

        You must call this from within a running event loop.
        """
        with self._consumer_lock:
            if self._consumer_task is not None and not self._consumer_task.done():
                raise RuntimeError("Channel consumer already running.")
            loop = asyncio.get_running_loop()

            async def _run():
                try:
                    await asyncio.gather(
                        self._consume_queue(),
                        self._stop_event.wait(),
                    )
                except asyncio.CancelledError:
                    pass
                finally:
                    try:
                        await self.on_exit()
                    except NotImplementedError:
                        pass
                    except Exception:
                        agent_log.exception("on_exit handler failed.")

            self._consumer_task = loop.create_task(_run())
            return self._consumer_task

    def stop_channel_consumer(self) -> None:
        """
        Cancel the consumer task if it is running. This is a best-effort stop.
        """
        with self._consumer_lock:
            self._stop_event.set()
            if self._consumer_task is not None and not self._consumer_task.done():
                self._consumer_task.cancel()

    async def _consume_queue(self) -> None:
        """
        Core loop: await queue items from a live BroadcastChannel subscription,
        convert, and enqueue agent runs. Relies on AgentPool.start_agent for
        execution and tracking.
        """
        print("Consuming live queue, initial qsize: ", self._sub_queue.qsize())

        while not self._stop_event.is_set():
            # Wait for either a new item or a stop signal, whichever comes first
            get_task = asyncio.create_task(self._sub_queue.get())
            stop_task = asyncio.create_task(self._stop_event.wait())
            done, pending = await asyncio.wait(
                {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )

            if stop_task in done and self._stop_event.is_set():
                # Stop requested; cancel any pending get and exit
                if not get_task.done():
                    get_task.cancel()
                break

            # Otherwise, we have an item from the queue
            item = get_task.result()
            try:
                run_id = await asyncio.to_thread(self.start_agent, item)
                agent_log.info(f"Enqueued run_id {run_id} from broadcast item.")
            except Exception:
                agent_log.exception("start_agent failed for broadcast item.")
            finally:
                self._sub_queue.task_done()

    async def on_exit(self) -> None:
        """Hook for graceful shutdown. Override in subclasses."""
        raise NotImplementedError