import logging
import pytz
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.utils import get_ctxt_id, LoggerProxy

_LOG_FORMAT = "%(asctime)s:[%(funcName)s:%(lineno)s] - %(message)s"

def converter(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz=pytz.utc)
    return dt.astimezone(pytz.timezone("US/Eastern")).timetuple()

formatter = logging.Formatter(_LOG_FORMAT, datefmt="%H:%M:%S")
formatter.converter = converter

# note: literally exists to filter out Litellm ...
class ExcludeStringsFilter(logging.Filter):
    """
    A logging filter that excludes log records containing any of the specified strings.
    """
    DEFAULT_EXCLUDE_STRS = [
        "LiteLLM",
        "completion()",
        "selected model name",
        "Wrapper: Completed Call"
    ]

    def __init__(self, exclude_strs: List[str] = []):
        super().__init__()
        self.exclude_strs = exclude_strs + self.DEFAULT_EXCLUDE_STRS
    
    def filter(self, record):
        """
        Return False if the log record should be excluded, True otherwise.
        """
        if not self.exclude_strs:
            return True
        
        # Check if any exclude string is in the log message
        log_message = record.getMessage()
        for exclude_str in self.exclude_strs:
            if exclude_str in log_message:
                return False
        return True

# --------------------------------------------------------------------------- #
#  existing helpers (unchanged except for the new formatter objects)
# --------------------------------------------------------------------------- #
def get_file_handler(log_file: str | Path) -> logging.FileHandler:
    """
    Returns a file handler for logging.
    """
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    return file_handler

def get_console_handler(exclude_strs: List[str] = []) -> logging.StreamHandler:
    """
    Returns a console handler for logging.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ExcludeStringsFilter(exclude_strs))
    return console_handler

def create_log_dir_or_noop(log_dir: str):
    date_dir = datetime.now().strftime("%Y-%m-%d")
    base_dir = Path(log_dir) / date_dir

    print(f"Creating log dir: {base_dir}")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def run_id_dir(base_dir: Path):
    """Returns the next run-id directory"""
    run_id = max((int(p.name) for p in base_dir.iterdir() if p.name.isdigit()), default=-1) + 1
    return base_dir / str(run_id)

class _ThreadFilter(logging.Filter):
    """Accept records only from the thread that created this handler."""
    def __init__(self, thread_id: int):
        super().__init__()
        self._thread_id = thread_id

    def filter(self, record: logging.LogRecord) -> bool:    # noqa: D401
        return record.thread == self._thread_id             # ❶ key line

class AgentFileHandler(logging.FileHandler):
    """
    A self-contained FileHandler that

    • creates the per-run directory tree (<LOG_DIR>/…/<run_id>/)
    • stores   .base_logdir   (Path to that run directory)
    • stores   .log_filepath  (Path to the specific *.log file)
    • auto-adds a _ThreadFilter so each thread gets its own file
    """
    def __init__(
        self,
        eval_name: str,
        base_dir: Path,
        *,
        level: int = logging.INFO,
        thread_id: Optional[int] = None,
    ):        
        self.thread_id = thread_id or threading.get_ident()

        try:
            self.base_logdir = run_id_dir(base_dir)
            self.base_logdir.mkdir()
        except FileExistsError: 
            # race condition with other loggers creating files in same dir, random backoff to avoid 
            # re-conflicts
            time.sleep(0.1 + 0.3 * random.random())
            self.base_logdir = run_id_dir(base_dir)
            self.base_logdir.mkdir()

        # Final log file path
        self.log_filepath = self.base_logdir / f"{eval_name}.log"

        # ── initialise parent FileHandler ───────────────────────────────── #
        super().__init__(self.log_filepath, encoding="utf-8")
        self.setLevel(level)
        self.setFormatter(formatter)

        # Per-thread isolation
        self._thread_id = self.thread_id
        self.addFilter(_ThreadFilter(self.thread_id))

    def get_log_dirs(self):
        return self.base_logdir, self.log_filepath

# --------------------------------------------------------------------------- #
#  updated helpers
# --------------------------------------------------------------------------- #
# TODO: swap the order of eval_name and subfolder
def setup_agent_logger(
    log_dir: str,
    *,
    parent_dir: Optional[Path] = None, # empty path
    name: str = "agentlog",
    level: int = logging.INFO,
):
    """
    Updated log-directory layout:

        <LOG_DIR>/pentest_bot/<YYYY-MM-DD>/<N>/…

    The optional *subfolder* argument is still supported and, if supplied,
    is placed **inside** the date directory:

        <LOG_DIR>/pentest_bot/<YYYY-MM-DD>/<subfolder>/<N>/…
    """
    base_dir = parent_dir if parent_dir else create_log_dir_or_noop(log_dir)
    thread_id = threading.get_ident()
    
    # Clear all handlers from root logger
    logging.getLogger().handlers.clear()

    # ─────────── Primary logger ────────────────────────────────────────── #
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(get_console_handler())
    if not any(isinstance(h, AgentFileHandler) and h._thread_id == thread_id for h in logger.handlers):
        fh = AgentFileHandler(
            name,
            base_dir,
            level=level,
            thread_id=thread_id,
        )
        logger.addHandler(fh)
        logger._run_dir = fh.base_logdir          # keep this public attr

    # ─────────── Secondary logger ("full_requests") ────────────────────── #
    fr_logger = logging.getLogger("full_requests")
    fr_logger.setLevel(level)
    fr_logger.propagate = False

    if not any(isinstance(h, AgentFileHandler) and h._thread_id == thread_id for h in fr_logger.handlers):
        # create a sibling dir <run>/full_requests/
        fr_dir = logger._run_dir / "full_requests"
        fr_dir.mkdir(exist_ok=True)

        fr_fh = AgentFileHandler(
            f"{name}_requests",
            fr_dir,
            level=level,
            thread_id=thread_id,
        )
        fr_logger.addHandler(fr_fh)

    # return logger, fr_logger, fh.get_log_dirs
    return fh.get_log_dirs()

def setup_server_logger(log_dir: str):
    """Initialize a server logger with file handler using run-id directory structure"""
    base_dir = create_log_dir_or_noop(log_dir)
    run_dir = run_id_dir(base_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("serverlog")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create file handler for run_id.log
    log_file = run_dir / f"{run_dir.name}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s:[%(funcName)s:%(lineno)s] - %(message)s",
        datefmt="%H:%M:%S"
    ))
    
    logger.addHandler(file_handler)

def get_server_logger():
    return logging.getLogger("serverlog")

def unified_log():
    agent_log, full_log = get_agent_loggers()
    return LoggerProxy([agent_log, full_log])

def get_agent_loggers():
    return logging.getLogger("agentlog"), logging.getLogger("full_requests")