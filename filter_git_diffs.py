#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def run_git(repo: Path, args: list[str]) -> str:
    try:
        out = subprocess.check_output(["git"] + args, cwd=str(repo), stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="replace").replace("\r", "")
    except subprocess.CalledProcessError as e:
        msg = e.output.decode("utf-8", errors="replace")
        raise RuntimeError(f"git {' '.join(args)} failed:\n{msg}") from e


def list_commits(repo: Path, since: str, until: str, include_merges: bool) -> list[tuple[str, str, str]]:
    """
    Returns a list of (commit_hash, iso_date, subject) in chronological order.
    """
    fmt = "%H%x09%ad%x09%s"
    args = [
        "log",
        f"--since={since}",
        f"--until={until}",
        "--date=iso-strict",
        f"--pretty=format:{fmt}",
        "--reverse",
    ]
    if not include_merges:
        args.append("--no-merges")

    output = run_git(repo, args)
    commits = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            # Fallback if subject contains tabs (rare with our delimiter, but guard anyway)
            raw = line.split("\t")
            chash = raw[0]
            cdate = raw[1] if len(raw) > 1 else ""
            subj = "\t".join(raw[2:]) if len(raw) > 2 else ""
        else:
            chash, cdate, subj = parts
        commits.append((chash.strip(), cdate.strip(), subj.strip()))
    return commits


def first_parent(repo: Path, commit: str) -> str | None:
    """
    Returns the first parent hash or None if there is no parent.
    """
    line = run_git(repo, ["rev-list", "--parents", "-n", "1", commit]).strip()
    toks = line.split()
    if len(toks) >= 2:
        return toks[1]
    return None


def commit_diff(repo: Path, parent: str | None, commit: str) -> str:
    """
    Returns unified diff from parent -> commit.
    Uses --no-ext-diff, avoids external tools. Skips binary blobs in patch text.
    """
    if parent is None:
        parent = EMPTY_TREE
    args = [
        "diff",
        "--no-ext-diff",
        "--find-renames",
        "--find-copies",
        "--unified=3",
        "--binary",  # keep headers for renames; patch body may include binary markers
        parent,
        commit,
    ]
    return run_git(repo, args)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Concatenate diffs for all commits in a date range, each labeled with hash/date/subject."
    )
    parser.add_argument("repo", nargs="?", default=".", help="Path to git repo (default: current directory)")
    parser.add_argument(
        "--since",
        default="2025-09-19 00:00:00",
        help='Start datetime inclusive (git syntax), e.g. "2025-09-19 00:00:00"',
    )
    parser.add_argument(
        "--until",
        default="2025-09-23 23:59:59",
        help='End datetime inclusive (git syntax), e.g. "2025-09-23 23:59:59"',
    )
    parser.add_argument(
        "--output",
        "-o",
        default="commit_range_diffs.txt",
        help="Output text file (default: commit_range_diffs.txt)",
    )
    parser.add_argument(
        "--include-merges",
        action="store_true",
        help="Include merge commits (diffs are against first parent). Default is to exclude merges.",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"Not a git repository: {repo}", file=sys.stderr)
        sys.exit(1)

    try:
        commits = list_commits(repo, args.since, args.until, args.include_merges)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if not commits:
        print("No commits in the specified range.")
        return

    out_path = Path(args.output).resolve()
    with out_path.open("w", encoding="utf-8") as outf:
        for idx, (chash, cdate, subj) in enumerate(commits, start=1):
            try:
                parent = first_parent(repo, chash)
                diff_txt = commit_diff(repo, parent, chash)
            except Exception as e:
                diff_txt = f"<<ERROR retrieving diff for {chash}: {e}>>\n"

            header = (
                "======================================================================\n"
                f"COMMIT {chash}\n"
                f"DATE   {cdate}\n"
                f"SUBJ   {subj}\n"
                "----------------------------------------------------------------------\n"
            )
            outf.write(header)
            outf.write(diff_txt)
            if not diff_txt.endswith("\n"):
                outf.write("\n")
            outf.write("\n")  # blank line between commits

    print(f"Wrote {len(commits)} commit diffs to {out_path}")


if __name__ == "__main__":
    main()
