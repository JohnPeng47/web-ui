#!/usr/bin/env python3
"""
osv_scanner.py

Query OSV for vulnerabilities by repo or package name and optionally
check whether each affected-range 'introduced' version appears as a
Docker Hub tag in a provided repository.

Usage examples:
    python osv_scanner.py mattermost --ecosystem Go --docker-repo mattermost/mattermost-team-edition
    python osv_scanner.py ghost --ecosystem npm --docker-repo library/ghost
    python osv_scanner.py grafana --ecosystem Go --docker-repo grafana/grafana --docker-max-tags 500
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from sqlalchemy.sql.expression import True_

# ──────────────────────────────────────────────────────────────────────────────
# Docker Hub helper (requires docker.py from previous step)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from docker import repository_exists, iter_all_tags
except Exception:
    # Allow running without docker.py; Docker checks will just be disabled
    repository_exists = None  # type: ignore
    iter_all_tags = None  # type: ignore

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
            break
        data = resp.json() or {}
        vulns.extend(data.get("vulns", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.05)

    return vulns


def _best_effort_candidates(repo_or_pkg: str) -> List[Tuple[str, str]]:
    token = repo_or_pkg.strip()
    candidates: List[Tuple[str, str]] = []
    if token.startswith("github.com/"):
        candidates.append(("Go", token))

    lowered = token.lower()
    candidates.extend(
        [
            ("Go", f"github.com/{lowered}/{lowered}"),
            ("Go", f"github.com/{lowered}/{lowered}-server"),
            ("Go", f"github.com/{lowered}/server"),
            ("PyPI", lowered),
            ("npm", lowered),
            ("Maven", lowered),
            ("RubyGems", lowered),
            ("crates.io", lowered),
            ("Packagist", lowered),
            ("NuGet", token),
        ]
    )

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
    by_pref = {"CVSS_V4": 1, "CVSS_V3": 2, "CVSS_V2": 3, "UNSPECIFIED": 4}
    sev_sorted = sorted(sev, key=lambda s: by_pref.get((s.get("type") or "UNSPECIFIED"), 99))
    best = sev_sorted[0]
    return f"{best.get('type', 'n/a')} {best.get('score', 'n/a')}"


def _normalize_tag_candidates(introduced: str) -> List[str]:
    """
    Produce plausible docker tag candidates from an introduced version:
    - exact
    - strip leading 'v'
    - add leading 'v' (common tagging style)
    """
    intro = introduced.strip()
    if not intro:
        return []
    no_v = intro[1:] if intro.startswith("v") else intro
    return [intro, no_v, f"v{no_v}"]


def _print_intro_match_status(
    intro: Optional[str],
    range_type: Optional[str],
    docker_tags: Optional[Set[str]],
    indent: str = "    ",
) -> None:
    """
    Implements the requested prints:
      - if introduced tag is not "0" → print "ORIGINAL"
      - if it matches a Docker tag → print f"MATCHED {intro}"
      - otherwise                → print f"NO MATCH {intro}"
    Notes:
      * We only attempt matching for SEMVER/ECOSYSTEM ranges; GIT introduced
        values are commits, not version tags.
    """
    if not intro:
        return

    # Always print ORIGINAL if introduced != "0"
    if intro != "0":
        print(f"{indent}ORIGINAL")

    # Attempt match only when we have docker tags and a version-based range
    if not docker_tags:
        return
    if (range_type or "").upper() not in {"SEMVER", "ECOSYSTEM"}:
        return

    for cand in _normalize_tag_candidates(intro):
        if cand in docker_tags:
            print(f"{indent}MATCHED {intro}")
            return
    print(f"{indent}NO MATCH {intro}")


def print_vulnerabilities(subject: str, vulns: List[Dict], docker_tags: Optional[Set[str]] = None) -> bool:
    if not vulns:
        print(f"No vulnerabilities found for '{subject}'.")
        return False

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
            snippet = details.replace("\n", " ")
            if len(snippet) > 500:
                snippet = snippet[:500] + " …"
            print(f"Details:   {snippet}")

        if affected:
            print("Affected:")
            for a in affected:
                pkg = a.get("package") or {}
                eco = pkg.get("ecosystem", "n/a")
                name = pkg.get("name", "n/a")
                print(f"- {eco} :: {name}")

                versions = a.get("versions") or []
                if versions:
                    joined = ", ".join(versions[:10])
                    suffix = " …" if len(versions) > 10 else ""
                    print(f"    versions: {joined}{suffix}")

                ranges = a.get("ranges") or []
                for r in ranges:
                    rtype = r.get("type", "n/a")
                    print(f"    range[{rtype}]:")
                    events = r.get("events") or []
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
                            print(f"      " + "{" + ", ".join(parts) + "}")

                        # New: print ORIGINAL / MATCHED / NO MATCH status per 'introduced'
                        if intro:
                            _print_intro_match_status(intro, rtype, docker_tags, indent="      ")

        if refs:
            print("References:")
            for url in refs[:15]:
                print(f"  - {url}")
        print()

    print("=" * 80)
    return True


def _load_docker_tags(repo: str, max_tags: int) -> Optional[Set[str]]:
    """
    Load up to `max_tags` tags from Docker Hub for the given repo.
    Returns a set of tag names, or None if docker.py is unavailable or the repo
    does not exist.
    """
    if repository_exists is None or iter_all_tags is None:
        return None
    try:
        if not repository_exists(repo):
            return None
        tags: Set[str] = set()
        for i, tag in enumerate(iter_all_tags(repo, page_size=100)):
            tags.add(tag)
            if i + 1 >= max_tags:
                break
        return tags
    except Exception:
        return None


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Search OSV for vulnerabilities by repo or package name.")
    parser.add_argument("filename", nargs="?", help="Read package names from file (txt or csv) and write results to osv folder")
    parser.add_argument("--ecosystem", help="Optional OSV ecosystem, e.g., Go, npm, PyPI, Maven, RubyGems, crates.io, Packagist, NuGet.")
    parser.add_argument("--version", help="Optional package version string for a precise query.")
    parser.add_argument("--commit", help="Optional commit hash for a precise query.")
    parser.add_argument("--max-candidates", type=int, default=10, help="Maximum candidate mappings to try when ecosystem is not specified.")
    args = parser.parse_args(argv)

    # Process packages from file
    import os
    import csv
    output_dir = "osv"
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine file type and process accordingly
    if args.filename.endswith(".csv"):
        # Process CSV file
        with open(args.filename, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:

                project_name = row.get("Project Name", "")
                osv_search_term = row.get("OSV Search Term", "")
                docker_repo = row.get("Docker Repository", "")
                
                if not osv_search_term:
                    continue
                
                docker_tags: Optional[Set[str]] = None
                docker_tags = _load_docker_tags(docker_repo, max_tags=200)
                if docker_tags is None:
                    print(f"[WARN] Could not load Docker tags for '{docker_repo}'. Continuing without tag matching.")

                # Parse OSV search term for ecosystem and version info
                # Format: package:ecosystem:version or package:ecosystem or package::version
                parts = osv_search_term.split(":")
                package_name = parts[0]
                line_ecosystem = parts[1] if len(parts) > 1 and parts[1] else args.ecosystem
                line_version = parts[2] if len(parts) > 2 and parts[2] else args.version
                
                # Create safe filename using project name if available
                if project_name:
                    safe_filename = project_name.replace("/", "_").replace("@", "_").replace(":", "_").replace(" ", "_")
                else:
                    safe_filename = package_name.replace("/", "_").replace("@", "_").replace(":", "_")
                
                if line_ecosystem:
                    safe_filename += f"_{line_ecosystem}"
                if line_version:
                    safe_filename += f"_{line_version}"
                output_file = os.path.join(output_dir, f"{safe_filename}.txt")
                
                # Search for vulnerabilities
                vulns = search_vulns_by_name(
                    package_name,
                    ecosystem=line_ecosystem,
                    version=line_version,
                    commit=args.commit,
                    max_candidates=args.max_candidates,
                )

                import sys
                from io import StringIO
                old_stdout = sys.stdout
                sys.stdout = mystdout = StringIO()
                
                subject = package_name if not line_ecosystem else f"{line_ecosystem}:{package_name}"
                if project_name:
                    subject = f"{project_name} ({subject})"
                vulns_found = print_vulnerabilities(subject, vulns, docker_tags)

                # Write results to file
                if vulns_found:
                    with open(output_file, "w") as out_f:
                        sys.stdout = old_stdout
                        out_f.write(mystdout.getvalue())

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
