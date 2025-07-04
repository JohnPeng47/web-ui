#!/usr/bin/env python
"""
serial_tp_sigint_demo.py – reproduce Ctrl-C behaviour with:
  • PythonInterpreter wrapper
  • ThreadPoolExecutor present
  • Jobs executed strictly one-by-one (serial)
"""

from __future__ import annotations

import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Dict, Optional

# ────────────────────────────────────────────────────────────────
# 1. Mini PythonInterpreter (fatal exceptions bubble out)
# ────────────────────────────────────────────────────────────────
class PythonInterpreter:
    def __init__(self, shared_globals: Optional[Dict[str, object]] = None) -> None:
        self._globals: Dict[str, object] = shared_globals or {}

    def run(self, code: str) -> str:
        out_buf, err_buf = StringIO(), StringIO()
        try:
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                exec(code, self._globals, {})
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            import traceback
            traceback.print_exc(file=err_buf)
        except BaseException:
            import traceback
            traceback.print_exc(file=err_buf)
            raise
        return out_buf.getvalue() + err_buf.getvalue()

# ────────────────────────────────────────────────────────────────
# 2. Job executed by the pool
# ────────────────────────────────────────────────────────────────
def sandbox_job(job_id: int) -> str:
    interp = PythonInterpreter()
    code = (
        "import time\n"
        f"print('job {job_id} START', flush=True)\n"
        "time.sleep(2)\n"
        f"print('job {job_id} END', flush=True)\n"
    )
    return interp.run(code)

# ────────────────────────────────────────────────────────────────
# 3. SIGINT handler – kill pool fast, exit(1)
# ────────────────────────────────────────────────────────────────
executor: ThreadPoolExecutor | None = None  # set in main()

def _sigint(signum, frame):  # noqa: D401
    print("\n[!] SIGINT caught – shutting down pool", file=sys.stderr)
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)
    sys.exit(1)

signal.signal(signal.SIGINT, _sigint)

# ────────────────────────────────────────────────────────────────
# 4. Main loop – submit jobs *serially*
# ────────────────────────────────────────────────────────────────
def main() -> None:
    global executor
    executor = ThreadPoolExecutor(max_workers=2)  # pool exists, but we go serial

    try:
        for i in range(5):
            print(f"\n=== launching job {i} ===")
            fut = executor.submit(sandbox_job, i)
            # SERIAL: wait for this job before queuing the next
            result = fut.result()
            print("--- captured output ---")
            print(result, end="")
    finally:
        executor.shutdown(wait=False)

    print("\n[driver] all jobs done (normal shutdown)")
    sys.exit(0)

if __name__ == "__main__":
    main()
