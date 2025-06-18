import logging
import os
from datetime import datetime
import pytz
import sys
import logging
import re
import sys, contextvars, logging
from pathlib import Path
from typing import Optional, List

LOG_DIR = "logs"

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

def converter(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz=pytz.utc)
    return dt.astimezone(pytz.timezone("US/Eastern")).timetuple()

formatter = logging.Formatter(
    "%(asctime)s:[%(filename)s:%(lineno)s] - %(message)s",
    datefmt="%H:%M:%S",
)
formatter.converter = converter
console_formatter = logging.Formatter("%(message)s")

def get_file_handler(log_file: str | Path):
    """
    Returns a file handler for logging.
    """
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    return file_handler

def get_console_handler(exclude_strs: List[str] = []):
    """
    Returns a console handler for logging.
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(ExcludeStringsFilter(exclude_strs))
    return console_handler

def get_logfile_id(log_dir=LOG_DIR, file_prefix: str = "", log_name: str = "") -> tuple[str, int]:
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
    existing_logs.sort(key=lambda x: int(re.search(r"(\d+)", x.split(".")[0]).group(1)))
    
    # Check for and remove empty files, shifting other files down
    current_index = 0
    for log_file in existing_logs:
        file_path = os.path.join(log_subdir, log_file)
        if os.path.getsize(file_path) == 0:
            os.remove(file_path)
            continue
            
        # Rename file if its index doesn't match current_index
        expected_name = f"{current_index}.log" if not log_name else f"{log_name}_{current_index}.log"
        if log_file != expected_name:
            os.rename(
                file_path,
                os.path.join(log_subdir, expected_name)
            )
        current_index += 1
    
    return timestamp, current_index

def get_incremental_logdir(log_dir=LOG_DIR, file_prefix: str = "", log_name: str = "") -> tuple[str, int]:
    """
    Returns a file handler that creates logs in timestamped directories with incremental filenames.
    Directory structure: log_dir/file_prefix/YYYY-MM-DD/0.log, 1.log, etc.
    """
    timestamp, next_number = get_logfile_id(log_dir, file_prefix, log_name=log_name)
    return os.path.join(log_dir, file_prefix, timestamp), next_number
    
def get_incremental_file_handler(log_dir=LOG_DIR, file_prefix: str = "", log_name: str = "", exclude_strs: List[str] = []):
    """
    Returns a file handler that creates logs in timestamped directories with incremental filenames.
    Directory structure: log_dir/file_prefix/YYYY-MM-DD/0.log, 1.log, etc.
    """
    log_subdir, next_number = get_incremental_logdir(log_dir, file_prefix, log_name=log_name)
    
    # Create new log file with incremental number
    file_name = f"{next_number}.log" if not log_name else f"{log_name}_{next_number}.log"
    file_handler = logging.FileHandler(os.path.join(log_subdir, file_name), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(ExcludeStringsFilter(exclude_strs))
    return file_handler

# TODO: DEEMO change back
def init_file_logger(name, log_name: str = ""):  
    root_logger = logging.getLogger("pentestbot")  # Get root logger by passing no name
    # TODO: should set all logging to DEBUG instead of INFO so we cant stop fucking logging LITELLM
    # or altneratively export logger instead of configuring global logger
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(get_incremental_file_handler(file_prefix=name, log_name=log_name))
    root_logger.addHandler(get_console_handler())

    return root_logger

def init_root_logger(name):
    print("Initializing root logger")
    
    root_logger = logging.getLogger()  # Get root logger by passing no name
    # TODO: should set all logging to DEBUG instead of INFO so we cant stop fucking logging LITELLM
    # or altneratively export logger instead of configuring global logger
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(get_incremental_file_handler(file_prefix=name))
    root_logger.addHandler(get_console_handler())