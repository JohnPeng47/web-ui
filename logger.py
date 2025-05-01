import logging
import os
from datetime import datetime
import pytz
import sys
import logging
import sys, contextvars, logging
from contextlib import contextmanager

_current_err = contextvars.ContextVar("task_stderr", default=sys.__stderr__)


LOG_DIR = "logs"

def converter(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz=pytz.utc)
    return dt.astimezone(pytz.timezone("US/Eastern")).timetuple()

formatter = logging.Formatter(
    "%(asctime)s - %(name)s:%(levelname)s: %(filename)s:%(lineno)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
formatter.converter = converter
console_formatter = logging.Formatter("%(message)s")

def get_file_handler(log_dir=LOG_DIR, file_prefix: str = ""):
    """
    Returns a file handler for logging.
    """
    log_subdir = os.path.join(log_dir, file_prefix)
    os.makedirs(log_subdir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    file_name = f"{file_prefix}_{timestamp}.log"
    file_handler = logging.FileHandler(os.path.join(log_subdir, file_name), encoding="utf-8")
    file_handler.setFormatter(formatter)
    return file_handler

def get_console_handler():
    """
    Returns a console handler for logging.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    return console_handler

def get_logfile_id(log_dir=LOG_DIR, file_prefix: str = "") -> tuple[str, int]:
    """
    Returns a tuple of (timestamp, next_id) for `file_prefix` log files.
    Also checks for empty log files and removes them, renaming subsequent files 
    to maintain sequential numbering. For example, if 0.log is empty and 1.log exists,
    1.log will be renamed to 0.log before returning the next available ID.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_subdir = os.path.join(log_dir, file_prefix, timestamp)
    os.makedirs(log_subdir, exist_ok=True)
    
    existing_logs = [f for f in os.listdir(log_subdir) if f.endswith(".log")]
    existing_logs.sort(key=lambda x: int(x.split(".")[0]))
    
    # Check for and remove empty files, shifting other files down
    current_index = 0
    for log_file in existing_logs:
        file_path = os.path.join(log_subdir, log_file)
        if os.path.getsize(file_path) == 0:
            os.remove(file_path)
            continue
            
        # Rename file if its index doesn't match current_index
        expected_name = f"{current_index}.log"
        if log_file != expected_name:
            os.rename(
                file_path,
                os.path.join(log_subdir, expected_name)
            )
        current_index += 1
    
    return timestamp, current_index

def get_incremental_file_handler(log_dir=LOG_DIR, file_prefix: str = ""):
    """
    Returns a file handler that creates logs in timestamped directories with incremental filenames.
    Directory structure: log_dir/file_prefix/YYYY-MM-DD/0.log, 1.log, etc.
    """
    timestamp, next_number = get_logfile_id(log_dir, file_prefix)
    log_subdir = os.path.join(log_dir, file_prefix, timestamp)
    
    # Create new log file with incremental number
    file_name = f"{next_number}.log"
    file_handler = logging.FileHandler(os.path.join(log_subdir, file_name), encoding="utf-8")
    file_handler.setFormatter(formatter)
    return file_handler

def init_root_logger():
    print("Initializing root logger")
    
    root_logger = logging.getLogger()  # Get root logger by passing no name
    # TODO: should set all logging to DEBUG instead of INFO so we cant stop fucking logging LITELLM
    # or altneratively export logger instead of configuring global logger
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(get_incremental_file_handler(file_prefix="main"))
    root_logger.addHandler(get_console_handler())

def init_file_logger(name):    
    logger = logging.getLogger(name)  # Get root logger by passing no name
    # TODO: should set all logging to DEBUG instead of INFO so we cant stop fucking logging LITELLM
    # or altneratively export logger instead of configuring global logger
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_incremental_file_handler(file_prefix=name))
    logger.addHandler(get_console_handler())

    return logger

# TODO: definitely get rid of this once we move to remote queue/workers implementation
class StderrProxy:
    def write(self, m): _current_err.get().write(m)
    def flush(self):   _current_err.get().flush()

sys.stderr = StderrProxy()           # global install once

@contextmanager
def stderr_to_logger(logger: logging.Logger):
    class _W:                         # task-local writer
        def write(self, m): logger.error(m.rstrip())
        def flush(self): pass
    tok = _current_err.set(_W())
    try:  yield
    finally: _current_err.reset(tok)