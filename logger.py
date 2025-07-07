import logging
import os
from datetime import datetime
import pytz
import sys
import logging
import sys, contextvars, logging
from pathlib import Path
from typing import Optional, List

from src.utils.context import get_ctxt_id

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

# --------------------------------------------------------------------------- #
#  formatter that injects the context-local ID
# --------------------------------------------------------------------------- #
class ContextVarFormatter(logging.Formatter):
    """
    Prepends the current value of `_context_id_var` to every record.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Expose the context value as an attribute the format string can use
        record.context_id = get_ctxt_id()
        return super().format(record)

# --------------------------------------------------------------------------- #
#  format strings
# --------------------------------------------------------------------------- #
_LOG_FORMAT = "[%(context_id)s] %(asctime)s:[%(funcName)s:%(lineno)s] - %(message)s"
_CONSOLE_FORMAT = "[%(context_id)s] %(message)s"

# The rest of your config stays the same, just swap in the new formatter class
formatter = ContextVarFormatter(_LOG_FORMAT, datefmt="%H:%M:%S")
formatter.converter = converter                    # keep your custom time zone
console_formatter = ContextVarFormatter(_CONSOLE_FORMAT)

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
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(ExcludeStringsFilter(exclude_strs))
    return console_handler