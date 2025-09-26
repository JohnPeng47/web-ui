import logging
import pytz
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Any, cast, Tuple, Dict

from src.utils import get_ctxt_id, LoggerProxy

# Logger names as top-level constants
AGENT_LOGGER_NAME = "agentlog"
FULL_REQUESTS_LOGGER_NAME = "full_requests"

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
        create_run_subdir: bool = True,
        add_thread_filter: bool = True,
    ):
        self.thread_id = thread_id or threading.get_ident()

        if create_run_subdir:
            try:
                self.base_logdir = run_id_dir(base_dir)
                self.base_logdir.mkdir()
            except FileExistsError: 
                # race condition with other loggers creating files in same dir, random backoff to avoid 
                # re-conflicts
                time.sleep(0.1 + 0.3 * random.random())
                self.base_logdir = run_id_dir(base_dir)
                self.base_logdir.mkdir()
        else:
            # Write directly under the provided base_dir
            self.base_logdir = base_dir

        # Final log file path
        self.log_filepath = self.base_logdir / f"{eval_name}.log"

        # ── initialise parent FileHandler ───────────────────────────────── #
        super().__init__(self.log_filepath, encoding="utf-8")
        self.setLevel(level)
        self.setFormatter(formatter)

        # Per-thread isolation (optional)
        self._thread_id = self.thread_id
        if add_thread_filter:
            self.addFilter(_ThreadFilter(self.thread_id))

    def get_log_dirs(self):
        return self.base_logdir, self.log_filepath

# --------------------------------------------------------------------------- #
#  updated helpers
# --------------------------------------------------------------------------- #
# TODO: swap the order of eval_name and subfolder
def _setup_agent_logger(
    log_dir: str,
    *,
    parent_dir: Optional[Path] = None, # empty path
    name: str = AGENT_LOGGER_NAME,
    level: int = logging.INFO,
    create_run_subdir: bool = True,
    add_thread_filter: bool = True,
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
    existing_fh = next((
        h for h in logger.handlers
        if isinstance(h, AgentFileHandler) and getattr(h, "_thread_id", None) == thread_id
    ), None)
    if existing_fh is not None:
        fh = existing_fh
        cast(Any, logger)._run_dir = fh.base_logdir          # keep this public attr
    else:
        fh = AgentFileHandler(
            name,
            base_dir,
            level=level,
            thread_id=thread_id,
            create_run_subdir=create_run_subdir,
            add_thread_filter=add_thread_filter,
        )
        logger.addHandler(fh)
        cast(Any, logger)._run_dir = fh.base_logdir          # keep this public attr

    # ─────────── Secondary logger ("full_requests") ────────────────────── #
    fr_logger = logging.getLogger(FULL_REQUESTS_LOGGER_NAME)
    fr_logger.setLevel(level)
    fr_logger.propagate = False

    if not any(isinstance(h, AgentFileHandler) and h._thread_id == thread_id for h in fr_logger.handlers):
        # create a sibling dir <run>/full_requests/
        run_dir = cast(Path, getattr(logger, "_run_dir"))
        fr_dir = run_dir / "full_requests"
        fr_dir.mkdir(exist_ok=True)

        fr_fh = AgentFileHandler(
            f"{name}_requests",
            fr_dir,
            level=level,
            thread_id=thread_id,
            create_run_subdir=create_run_subdir,
            add_thread_filter=add_thread_filter,
        )
        fr_logger.addHandler(fr_fh)

    # return logger, fr_logger, fh.get_log_dirs
    return fh.get_log_dirs()

def setup_server_logger(log_dir: str):
    """Initialize a server logger with file handler using run-id directory structure"""
    base_dir = create_log_dir_or_noop(log_dir)
    run_dir = run_id_dir(base_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(SERVER_LOGGER_NAME)
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
    logger.addHandler(get_console_handler())

    for h in logger.handlers:
        print(f"SERVER LOGGER HANDLER: ", h)

def get_server_logger():
    return logging.getLogger(SERVER_LOGGER_NAME)

def unified_log():
    agent_log, full_log = get_agent_loggers()
    return LoggerProxy([agent_log, full_log])

def get_agent_loggers():
    return logging.getLogger(AGENT_LOGGER_NAME), logging.getLogger(FULL_REQUESTS_LOGGER_NAME)

# --------------------------------------------------------------------------- #
#  ServerLogFactory: per-engagement loggers and directory layout
# --------------------------------------------------------------------------- #

# static logger names
SERVER_LOGGER_NAME = "serverlog"
PROXY_LOGGER_NAME = "proxylog"
UVICORN_LOG = "uvicorn"
UVICORN_ACCESSS_LOG = "uvicorn.access"
UVICORN_ERROR_LOG = "uvicorn.error"
AGENT_POOL_LOGGER_NAME = "agentpool"

class _ServerLogFactory:
    """
    Singleton application-wide logger factory.
    3-tier file-level logging:

    1. base_dir (server / single-run agents)
        2. timestamp (represents a run instance)
            3. agents (discovery/exploit)

    - tier 1 represents a logical application container for the logs ie. single run of server
    - tier 2 [static] represents log processes where only a single log file is created ie. server logs
    - tier 3 [dynamic] represents log processes where multiple log files may be created ie. mutliple agents running in pool 
    """
    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._server_logger: Optional[logging.Logger] = None
        self._engagement_dir: Optional[Path] = None

        self.setup_static_loggers()

    def _get_engagement_dir(self) -> Path:
        # Return cached directory if already created
        if self._engagement_dir is not None:
            return self._engagement_dir
        
        # Create timestamp directory
        timestamp = datetime.now().strftime("%Y-%m-%d")
        timestamp_dir = self._base_dir / timestamp
        timestamp_dir.mkdir(parents=True, exist_ok=True)
        
        # Find next incremental ID in timestamp directory
        max_incr = 0
        for p in timestamp_dir.iterdir():
            if p.is_dir() and p.name.isdigit():
                max_incr = max(max_incr, int(p.name))
        
        incr_id = max_incr + 1
        engagement_dir = timestamp_dir / str(incr_id)
        engagement_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure subfolders exist
        (engagement_dir / "discovery_agents").mkdir(exist_ok=True)
        (engagement_dir / "exploit_agents").mkdir(exist_ok=True)
        
        # Cache the directory
        self._engagement_dir = engagement_dir
        
        return engagement_dir

    def _next_numeric_name(self, root: Path) -> str:
        """
        Determine the next numeric filename stem by scanning existing *.log files
        recursively and returning max(N)+1.
        """
        max_num = 0
        for p in root.rglob("*.log"):
            try:
                num = int(p.stem)
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
        return str(max_num + 1)

    # static loggers
    def _create_static_logger(self, logger_name: str, log_filepath: Path) -> logging.Logger:
        """Create a static logger with console and file handlers."""
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Avoid duplicate handlers if called multiple times
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            logger.addHandler(get_console_handler())

        if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_filepath) for h in logger.handlers):
            fh = logging.FileHandler(log_filepath, encoding="utf-8")
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    def setup_server_logger(self, logger_name: str):
        """Create or return the server logger (with console + file)."""
        e_dir = self._get_engagement_dir()
        server_log_path = e_dir / "server.log"
        self._create_static_logger(logger_name, server_log_path)

    def setup_proxy_logger(self, logger_name: str):
        """Create or return the proxy logger (with console + file)."""
        e_dir = self._get_engagement_dir()
        proxy_log_path = e_dir / "proxy.log"
        self._create_static_logger(logger_name, proxy_log_path)

    def setup_uvicorn_logger(self, logger_name: str):
        e_dir = self._get_engagement_dir()
        uvicorn_log_path = e_dir / "server.log"
        self._create_static_logger(logger_name, uvicorn_log_path)
    
    def setup_agent_pool_logger(self, logger_name: str):
        e_dir = self._get_engagement_dir()
        agent_pool_log_path = e_dir / "agent_pool.log"
        self._create_static_logger(logger_name, agent_pool_log_path)

    def setup_static_loggers(self) -> None:
        """Setup the static loggers."""
        self.setup_server_logger(SERVER_LOGGER_NAME)
        self.setup_proxy_logger(PROXY_LOGGER_NAME)
        self.setup_uvicorn_logger(UVICORN_LOG)
        self.setup_uvicorn_logger(UVICORN_ACCESSS_LOG)
        self.setup_uvicorn_logger(UVICORN_ERROR_LOG)
        self.setup_agent_pool_logger(AGENT_POOL_LOGGER_NAME)

        # should include?
        # self.get_discovery_agent_loggers()
        # self.get_exploit_agent_loggers()

    # dynamic loggers
    def get_discovery_agent_loggers(self) -> Tuple[logging.Logger, logging.Logger]:
        """
        Return loggers for a new discovery agent.
        Does not attach handlers; the worker thread should call setup_agent_logger
        with these values.
        """
        e_dir = self._get_engagement_dir()
        discovery_dir = e_dir / "discovery_agents"
        
        name = self._next_numeric_name(discovery_dir)

        _setup_agent_logger(log_dir="", parent_dir=discovery_dir, name=name, create_run_subdir=False, add_thread_filter=False)
        return logging.getLogger(name), logging.getLogger(FULL_REQUESTS_LOGGER_NAME)
    
    def get_exploit_agent_loggers(self) -> Tuple[logging.Logger, logging.Logger]:
        """
        Return loggers for a new exploit agent.
        Does not attach handlers; the worker thread should call setup_agent_logger.
        """
        e_dir = self._get_engagement_dir()
        exploit_dir = e_dir / "exploit_agents"

        name = self._next_numeric_name(exploit_dir)

        _setup_agent_logger(log_dir="", parent_dir=exploit_dir, name=name, create_run_subdir=False, add_thread_filter=False)
        return logging.getLogger(name), logging.getLogger(FULL_REQUESTS_LOGGER_NAME)

_SERVER_LOG_FACTORY_SINGLETON: Optional[_ServerLogFactory] = None

def get_or_init_log_factory(base_dir: Optional[str] = None) -> _ServerLogFactory:
    """
    Return a singleton ServerLogFactory. If base_dir is provided on first call,
    it sets the base directory; otherwise defaults to ".server_logs/engagements".
    Subsequent calls ignore base_dir.
    """
    global _SERVER_LOG_FACTORY_SINGLETON
    if _SERVER_LOG_FACTORY_SINGLETON is None:
        root = base_dir or ".server_logs/engagements"
        Path(root).mkdir(parents=True, exist_ok=True)
        _SERVER_LOG_FACTORY_SINGLETON = _ServerLogFactory(root)
    return _SERVER_LOG_FACTORY_SINGLETON