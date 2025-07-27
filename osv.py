#!/usr/bin/env python3
"""
OSV search by repo/package name using only endpoints in the provided API spec.

Usage:
    python osv_search.py mattermost
    python osv_search.py mattermost --ecosystem Go
    python osv_search.py mattermost --version 9.11.0
    python osv_search.py github.com/mattermost/mattermost-server --ecosystem Go
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, Iterable, List, Optional, Tuple

import requests


OSV_API_BASE = "https://api.osv.dev"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "Content-Type": "application/json"})


def _query_osv(
    package_name: str,
    ecosystem: str,
    version: Optional[str] = None,
    commit: Optional[str] = None,
) -> List[Dict]:
    """
    Call POST /v1/query with a package and an optional version or commit.
    Returns a list of vulnerability objects (may be empty).
    """
    url = f"{OSV_API_BASE}/v1/query"

    if not package_name or not ecosystem:
        return []

    body: Dict = {
        "package": {
            "name": package_name,
            "ecosystem": ecosystem,
        }
    }
    if version:
        body["version"] = version
    if commit:
        body["commit"] = commit

    vulns: List[Dict] = []
    page_token: Optional[str] = None

    while True:
        if page_token:
            body["pageToken"] = page_token
        resp = SESSION.post(url, json=body, timeout=30)
        if resp.status_code != 200:
            # Stop on first error for this candidate
            break
        data = resp.json() or {}
        vulns.extend(data.get("vulns", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        # Gentle pacing for paged results
        time.sleep(0.05)

    return vulns


def _best_effort_candidates(repo_or_pkg: str) -> List[Tuple[str, str]]:
    """
    Generate (ecosystem, package_name) candidates from a simple repo or package token.
    The OSV /v1/query endpoint is version/commit centric, but many databases
    will still return matches for a package identifier without a version.
    """
    token = repo_or_pkg.strip()

    # If the user passed a full Go module path or similar, try it directly in Go.
    candidates: List[Tuple[str, str]] = []
    if token.startswith("github.com/"):
        candidates.append(("Go", token))

    # Common ecosystems and straightforward name mappings.
    # You can extend this as needed for your environment.
    lowered = token.lower()
    candidates.extend(
        [
            ("Go", f"github.com/{lowered}/{lowered}"),
            ("Go", f"github.com/{lowered}/{lowered}-server"),
            ("Go", f"github.com/{lowered}/{lowered}-app"),
            ("Go", f"github.com/{lowered}/server"),
            ("PyPI", lowered),
            ("npm", lowered),
            ("Maven", lowered),         # For Maven, group:artifact is ideal; this is a best-effort fallback
            ("RubyGems", lowered),
            ("crates.io", lowered),
            ("Packagist", lowered),
            ("NuGet", token),           # NuGet names are often PascalCase
        ]
    )

    # De-duplicate while preserving order
    seen: set = set()
    uniq: List[Tuple[str, str]] = []
    for eco, name in candidates:
        key = (eco, name)
        if key not in seen:
            uniq.append(key)
            seen.add(key)
    return uniq


def search_vulns_by_name(
    name: str,
    ecosystem: Optional[str] = None,
    version: Optional[str] = None,
    commit: Optional[str] = None,
    max_candidates: int = 10,
) -> List[Dict]:
    """
    Try a set of ecosystem/name candidates derived from the input name, unless an ecosystem
    is explicitly provided. Aggregate and de-duplicate vulnerabilities across candidates.
    """
    results: List[Dict] = []
    seen_ids: set = set()

    if ecosystem:
        candidates = [(ecosystem, name)]
    else:
        candidates = _best_effort_candidates(name)

    for eco, pkg in candidates[:max_candidates]:
        vulns = _query_osv(pkg, eco, version=version, commit=commit)
        for v in vulns:
            vid = v.get("id")
            if vid and vid not in seen_ids:
                results.append(v)
                seen_ids.add(vid)

    return results


def _format_severity(v: Dict) -> str:
    sev = v.get("severity") or []
    if not sev:
        return "n/a"
    # Prefer CVSS v3 or v4 if present; otherwise just join all entries.
    by_pref = {"CVSS_V4": 1, "CVSS_V3": 2, "CVSS_V2": 3, "UNSPECIFIED": 4}
    sev_sorted = sorted(sev, key=lambda s: by_pref.get((s.get("type") or "UNSPECIFIED"), 99))
    best = sev_sorted[0]
    return f"{best.get('type', 'n/a')} {best.get('score', 'n/a')}"


def _format_affected_one(a: Dict) -> str:
    pkg = a.get("package") or {}
    eco = pkg.get("ecosystem", "n/a")
    name = pkg.get("name", "n/a")

    out: List[str] = [f"- {eco} :: {name}"]
    versions = a.get("versions") or []
    if versions:
        out.append(f"  versions: {', '.join(versions[:10])}{' …' if len(versions) > 10 else ''}")

    ranges = a.get("ranges") or []
    for r in ranges:
        rtype = r.get("type", "n/a")
        events = r.get("events") or []
        formatted_events: List[str] = []
        for e in events:
            intro = e.get("introduced")
            fixed = e.get("fixed")
            last = e.get("lastAffected")
            limit = e.get("limit")
            parts: List[str] = []
            if intro:
                parts.append(f"introduced={intro}")
            if fixed:
                parts.append(f"fixed={fixed}")
            if last:
                parts.append(f"lastAffected={last}")
            if limit:
                parts.append(f"limit={limit}")
            if parts:
                formatted_events.append("{" + ", ".join(parts) + "}")
        if formatted_events:
            out.append(f"  range[{rtype}]: " + " ".join(formatted_events))
    return "\n".join(out)


def print_vulnerabilities(subject: str, vulns: List[Dict]) -> None:
    if not vulns:
        print(f"No vulnerabilities found for '{subject}'.")
        return

    print(f"Found {len(vulns)} vulnerabilities for '{subject}':\n")
    for v in sorted(vulns, key=lambda x: (x.get("modified") or x.get("published") or ""), reverse=True):
        vid = v.get("id", "n/a")
        published = v.get("published", "n/a")
        modified = v.get("modified", "n/a")
        summary = (v.get("summary") or "").strip()
        details = (v.get("details") or "").strip()
        severity = _format_severity(v)
        aliases = ", ".join(v.get("aliases") or []) or "n/a"
        refs = [r.get("url") for r in (v.get("references") or []) if r.get("url")]
        affected = v.get("affected") or []

        print("=" * 80)
        print(f"ID: {vid}")
        print(f"Severity: {severity}")
        print(f"Published: {published}")
        print(f"Modified:  {modified}")
        print(f"Aliases:   {aliases}")
        if summary:
            print(f"Summary:   {summary}")
        if details:
            # Keep details concise in console output
            snippet = details.replace("\n", " ")
            if len(snippet) > 500:
                snippet = snippet[:500] + " …"
            print(f"Details:   {snippet}")
        if affected:
            print("Affected:")
            for a in affected:
                print(_format_affected_one(a))
        if refs:
            print("References:")
            for url in refs[:15]:
                print(f"  - {url}")
        print()

    print("=" * 80)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Search OSV for vulnerabilities by repo or package name.")
    parser.add_argument("name", help="Repository or package name, e.g., 'mattermost' or 'github.com/mattermost/mattermost-server'.")
    parser.add_argument("--ecosystem", help="Optional OSV ecosystem, e.g., Go, npm, PyPI, Maven, RubyGems, crates.io, Packagist, NuGet.")
    parser.add_argument("--version", help="Optional package version string for a precise query.")
    parser.add_argument("--commit", help="Optional commit hash for a precise query.")
    parser.add_argument("--max-candidates", type=int, default=10, help="Maximum candidate mappings to try when ecosystem is not specified.")
    args = parser.parse_args(argv)

    vulns = search_vulns_by_name(
        args.name,
        ecosystem=args.ecosystem,
        version=args.version,
        commit=args.commit,
        max_candidates=args.max_candidates,
    )
    print_vulnerabilities(args.name if not args.ecosystem else f"{args.ecosystem}:{args.name}", vulns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
