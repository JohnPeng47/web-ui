import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Sequence, Set
from logger import (
    LOG_DIR, 
    get_incremental_logdir, 
    get_console_handler, 
    get_file_handler
)

class _StreamFilter(logging.Filter):
    """
    Accept the record only if its `record.stream` attribute is in `allowed_streams`.
    """
    def __init__(self, allowed_streams: Sequence[str]) -> None:
        super().__init__()
        self.allowed: Set[str] = set(allowed_streams)

    def filter(self, record: logging.LogRecord) -> bool:         # noqa: D401
        return getattr(record, "stream", None) in self.allowed


class _MultiStreamAdapter:
    """
    Thin proxy so `adapter.info("msg")` duplicates the call once for each stream
    in `self._streams`, injecting `extra={'stream': s}` each time.
    """
    def __init__(self, base: logging.Logger, streams: Sequence[str]) -> None:
        self._base = base
        self._streams = list(streams)

    # Dynamically proxy any logging method (debug, info, warning, …)
    def __getattr__(self, name):
        attr = getattr(self._base, name, None)
        if callable(attr):
            def _wrapper(msg, *args, **kwargs):
                orig_extra = kwargs.pop("extra", {})
                for s in self._streams:
                    extra = {**orig_extra, "stream": s}
                    attr(msg, *args, extra=extra, **kwargs)
            return _wrapper
        return attr


class AgentLogger:
    """
    Usage
    -----
        log = AgentLogger()

        log.action.info("User clicked X")
        log.context.debug("some json blob")
        log.both.warning("Something went wrong")

    Configuration
    -------------
    Public attribute names  ->  list of *stream* tags the call should fan‑out to.
    A stream tag is just an arbitrary string; one file handler is created per tag.
    """
    action:  logging.Logger   # declared to appease linters ...
    context: logging.Logger


    LOG_STREAMS: Dict[str, List[str]] = {
        "action":  ["agent_actions", "agent_context"],
        "context": ["agent_context"],
    }

    def __init__(self, name: str = "agentlog") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        log_dir = os.path.join(LOG_DIR, name, timestamp)
        os.makedirs(log_dir, exist_ok=True)        

        self._base = logging.getLogger(name)
        self._base.setLevel(logging.INFO)
        self._base.addHandler(get_console_handler())
        
        # Unique set of stream tags across every mapping value
        all_streams = {stream for streams in self.LOG_STREAMS.values()
                                 for stream in streams}

        # one file per *stream* tag
        for stream in all_streams:
            fh = self._get_incremental_fhandler(log_dir, stream)
            fh.addFilter(_StreamFilter([stream]))  # single‑stream filter
            self._base.addHandler(fh)

        # Build adapters and expose them as attributes, e.g. self.action
        for public, streams in self.LOG_STREAMS.items():
            adapter = _MultiStreamAdapter(self._base, streams)
            setattr(self, public, adapter)

    def _get_incremental_fhandler(self, log_dir: str, file_prefix: str) -> logging.FileHandler:
        """
        Returns a file handler for logging with incremental file naming.
        Creates files like 0.log, 1.log, 2.log in the specified directory.
        """
        # Create directory if it doesn't exist
        log_subdir = os.path.join(log_dir, file_prefix)
        os.makedirs(log_subdir, exist_ok=True)
        
        # Get list of existing log files and determine next number
        existing_logs = [f for f in os.listdir(log_subdir) if f.endswith(".log")]
        next_number = 0
        
        if existing_logs:
            # Extract numbers from filenames and find the highest
            log_numbers = [int(f.split(".")[0]) for f in existing_logs if f.split(".")[0].isdigit()]
            if log_numbers:
                next_number = max(log_numbers) + 1
        
        # Create new log file with incremental number
        file_name = f"{next_number}.log"
        log_file = os.path.join(log_subdir, file_name)
        return get_file_handler(log_file)
        
    # Optional: pretty repr() for debugging
    def __repr__(self) -> str:
        return f"<AgentLogger streams={list(self.LOG_STREAMS.keys())}>"
