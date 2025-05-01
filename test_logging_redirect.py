import sys, contextvars, logging
_current_err = contextvars.ContextVar("task_stderr", default=sys.__stderr__)

class StderrProxy:
    def write(self, m): _current_err.get().write(m)
    def flush(self):   _current_err.get().flush()

sys.stderr = StderrProxy()           # global install once

from contextlib import contextmanager
@contextmanager
def stderr_to_logger(logger: logging.Logger):
    class _W:                         # task-local writer
        def write(self, m): logger.error(m.rstrip())
        def flush(self): pass
    tok = _current_err.set(_W())
    try:  yield
    finally: _current_err.reset(tok)


import asyncio
from logger import init_file_logger

async def task_with_errors():
    """A test task that generates some errors to stderr."""
    logger = init_file_logger("test_task")
    
    # Normal logging
    logger.info("Starting test task")
    logger.debug("This is a debug message")
    
    # Use stderr redirection
    with stderr_to_logger(logger):
        # This will be captured by the logger
        print("This goes to stdout, not stderr", file=sys.stdout)
        print("This error will be captured by the logger", file=sys.stderr)
        
        # Simulate an exception
        try:
            result = 1 / 0
        except Exception as e:
            print(f"Exception occurred: {e}", file=sys.stderr)
    
    # Outside the context manager, stderr is back to normal
    print("This error goes to normal stderr", file=sys.stderr)
    logger.info("Task completed")

async def main():
    """Run the test tasks."""
    logger = init_file_logger("test_main")
    logger.info("Starting test of stderr redirection")
    
    await task_with_errors()
    
    # Run multiple tasks concurrently to test context isolation
    logger.info("Testing multiple concurrent tasks")
    await asyncio.gather(
        task_with_errors(),
        task_with_errors(),
        task_with_errors()
    )
    
    logger.info("All tests completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Test interrupted by user")
    except Exception as e:
        print(f"Test error: {e}")

