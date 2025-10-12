# log_context.py
import contextvars
from contextlib import contextmanager
from typing import Iterator

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
