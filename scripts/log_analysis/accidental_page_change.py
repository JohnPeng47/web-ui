#!/usr/bin/env python3
import re
import sys
from pathlib import Path

PAGE_CHANGE_RE = re.compile(r"Page changed from")
LOGFILE_NAME_RE = re.compile(r"^\d+\.log$")

def count_quick_successions(path: Path, max_gap_lines: int = 20) -> int:
    """
    Count how many times the line containing 'Page changed from'
    is followed by the next 'Page changed from' within max_gap_lines lines.
    Overlapping pairs are counted.
    """
    count = 0
    last_hit_line = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, start=1):
                if PAGE_CHANGE_RE.search(line):
                    if last_hit_line is not None and (lineno - last_hit_line) <= max_gap_lines:
                        count += 1
                    last_hit_line = lineno
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)

    return count

def scan_directory(root: Path) -> list[tuple[str, int]]:
    """
    Find files matching '<int>.log' recursively under root.
    For each, compute the succession count as defined above.
    Returns list of tuples: (relative_path, count)
    """
    results: list[tuple[str, int]] = []

    for p in root.rglob("*.log"):
        if not LOGFILE_NAME_RE.match(p.name):
            continue

        c = count_quick_successions(p, max_gap_lines=30)
        # Only show files with at least one quick succession.
        if c > 0:
            rel = str(p.relative_to(root))
            results.append((rel, c))

    results.sort(key=lambda x: x[0])
    return results

def main() -> None:
    root = Path(".server_logs").resolve()
    if not root.exists() or not root.is_dir():
        print("Given directory does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    results = scan_directory(root)

    if not results:
        print("No matching quick successions found.")
        return

    print(f"{'file':<50} {'quick_successions':>18}")
    print("-" * 70)
    for rel, c in results:
        print(f"{rel:<50} {c:18d}")

if __name__ == "__main__":
    main()
