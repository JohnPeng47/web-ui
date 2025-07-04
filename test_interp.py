import os
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Dict, Optional


class PythonInterpreter:
    """Minimal, state‑preserving Python execution sandbox."""

    def __init__(self, shared_globals: Optional[Dict[str, object]] = None) -> None:
        self._globals: Dict[str, object] = shared_globals or {}

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def run(self, code: str) -> str:
        """Execute *code* and return ``stdout`` + ``stderr`` as a single string."""

        stdout_buf = StringIO()
        stderr_buf = StringIO()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, self._globals, {})
        except Exception:  # pylint: disable=broad-except
            traceback.print_exc(file=stderr_buf)

        stdout_text = stdout_buf.getvalue()
        stderr_text = stderr_buf.getvalue()
        return f"{stdout_text}{os.linesep if stderr_text else ''}{stderr_text}"


def test_python_interpreter():
    """Test case for PythonInterpreter with a global function."""
    
    # Define a simple global function
    def hello_world(name="World"):
        return f"Hello, {name}!"
    
    # Create interpreter with the global function
    shared_globals = {"hello_world": hello_world}
    interp = PythonInterpreter(shared_globals)
    
    # Test script that calls the function
    test_code = """
print("Testing global function:")
result = hello_world("Python")
print(result)
print("Direct call:", hello_world())
"""
    
    # Run the test
    output = interp.run(test_code)
    print("Test Output:")
    print(output)


if __name__ == "__main__":
    test_python_interpreter()
