import contextvars
from contextlib import contextmanager
from typing import Iterator
import difflib

# The one and only ContextVar you export  –  anything else stays private
_log_context_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "log_context_id",
    default="-",
)

# Public helpers -------------------------------------------------------------
def get_ctxt_id() -> str:              # for the formatter
    return _log_context_id.get()

def set_ctxt_id(value: str) -> None:   # for your app code
    _log_context_id.set(value)

@contextmanager
def push_ctxt_id(value: str) -> Iterator[None]:
    """
    Temporary override of the current context ID.

    >>> with push("http-42"):
    ...     ...
    """
    token = _log_context_id.set(value)
    try:
        yield
    finally:
        _log_context_id.reset(token)


def extract_state_from_history(history):
    """
    Extract all current_state keys from the history dictionary and return as a list.
    
    Args:
        history (dict): A dictionary containing history data with model_output entries
        
    Returns:
        list: A list of all current_state dictionaries found in the history
    """
    states = []
    
    if not history or "history" not in history:
        return states
    
    for entry in history["history"]:
        if "model_output" in entry and "current_state" in entry["model_output"]:
            states.append(entry["model_output"]["current_state"])
    
    return states

def diff_dom(a: str, b: str) -> str:
    diff = difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="a.txt",
        tofile="b.txt",
        lineterm=""
    )
    return "".join(diff)
