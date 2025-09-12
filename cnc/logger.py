import threading
import logging

from typing import Optional, cast, Any
from pathlib import Path
from logger import (
    AgentFileHandler,
    AGENT_LOGGER_NAME, 
    FULL_REQUESTS_LOGGER_NAME
)

def setup_agent_logger(
    log_dir: str,
    *,
    name: str = AGENT_LOGGER_NAME,
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
        )
        fr_logger.addHandler(fr_fh)

    # return logger, fr_logger, fh.get_log_dirs
    return fh.get_log_dirs()
