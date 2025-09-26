#!/usr/bin/env python3
import re
import sys
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pvariance

OUTPUT_RE = re.compile(r'^(\d{2}:\d{2}:\d{2}):\[_llm_next_actions:\d+\] - AGENT OUTPUT')
ACTION_RE = re.compile(r'^(\d{2}:\d{2}:\d{2}):\[_execute_actions:\d+\] - \[Action\][: ]')

def parse_time(ts: str) -> datetime:
    # Use a dummy base date; we will handle day rollovers.
    return datetime.strptime("1970-01-01 " + ts, "%Y-%m-%d %H:%M:%S")

def extract_durations_for_file(path: Path) -> list[float]:
    """
    Scan one logfile and compute durations (seconds) from AGENT OUTPUT
    to the next [Action] line. Returns a list of float seconds.
    """
    durations: list[float] = []
    pending: deque[datetime] = deque()

    current_day_offset = 0
    last_seen: datetime | None = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m_out = OUTPUT_RE.match(line)
                m_act = ACTION_RE.match(line)

                ts_str = None
                if m_out:
                    ts_str = m_out.group(1)
                elif m_act:
                    ts_str = m_act.group(1)

                if ts_str is None:
                    continue

                t = parse_time(ts_str) + timedelta(days=current_day_offset)

                # Handle potential day rollover in logs
                if last_seen is not None and t < last_seen:
                    current_day_offset += 1
                    t = t + timedelta(days=1)

                last_seen = t

                if m_out:
                    pending.append(t)
                elif m_act:
                    if pending:
                        t0 = pending.popleft()
                        delta = (t - t0).total_seconds()
                        if delta >= 0:
                            durations.append(delta)
                        # If delta < 0 due to weird ordering, drop it silently.
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)

    return durations

def scan_directory(root: Path) -> list[tuple[str, float, float, int]]:
    """
    Find files matching '<int>.log' recursively under root, compute
    mean, variance, and n for each file. Returns list of tuples:
    (relative_path, mean_seconds, variance_seconds2, n)
    """
    results: list[tuple[str, float, float, int]] = []
    pattern = re.compile(r"^\d+\.log$")

    for p in root.rglob("*.log"):
        if not pattern.match(p.name):
            continue

        durations = extract_durations_for_file(p)
        n = len(durations)
        if n == 0:
            mu = 0.0
            var = 0.0
        elif n == 1:
            mu = durations[0]
            var = 0.0
        else:
            mu = mean(durations)
            var = pvariance(durations)

        rel = str(p.relative_to(root))
        if n != 0:
            results.append((rel, mu, var, n))

    # Sort by path for stable output
    results.sort(key=lambda x: x[0])
    return results

def main() -> None:
    root = Path(".server_logs").resolve()
    if not root.exists() or not root.is_dir():
        print("Given directory does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    results = scan_directory(root)

    if not results:
        print("No matching log files found.")
        return

    # Print header
    print(f"{'file':<50} {'mean_s':>12} {'variance_s2':>14} {'n':>6}")
    print("-" * 86)
    for rel, mu, var, n in results:
        print(f"{rel:<50} {mu:12.3f} {var:14.3f} {n:6d}")

if __name__ == "__main__":
    main()
