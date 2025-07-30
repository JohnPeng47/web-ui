#!/usr/bin/env python3
"""
osv_scanner.py

Read projects from a CSV and write structured JSON results for each:
- Query OSV by package/ecosystem[/version]
- Optionally fetch Docker Hub tags and record match status for 'introduced' events

CSV columns (by header):
  - Project Name
  - OSV Search Term   (formats: "package", "package:ecosystem", "package:ecosystem:version", "package::version")
  - Docker Repository (e.g., "library/ghost" or "grafana/grafana")

Output:
  - JSON files under ./test_osv/

Usage:
    python osv_scanner.py projects.csv
"""

from __future__ import annotations
import sys
sys.path.append("..")

import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import requests

from src.llm_models import openai_o4_mini as lazy_openai_o4_mini
from classify_vuln import ClassifyVuln

openai_o4_mini = lazy_openai_o4_mini()

# ──────────────────────────────────────────────────────────────────────────────
# Docker Hub helper (requires docker.py from previous step)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from docker import repository_exists, iter_all_tags
except Exception:
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
    POST /v1/query with a package and an optional version or commit.
    Returns a list of vulnerability objects (may be empty).
    """
    url = f"{OSV_API_BASE}/v1/query"
    if not package_name or not ecosystem:
        return []

    body: Dict = {"package": {"name": package_name, "ecosystem": ecosystem}}
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


def _format_best_severity(v: Dict) -> Optional[str]:
    sev = v.get("severity") or []
    if not sev:
        return None
    by_pref = {"CVSS_V4": 1, "CVSS_V3": 2, "CVSS_V2": 3, "UNSPECIFIED": 4}
    sev_sorted = sorted(sev, key=lambda s: by_pref.get((s.get("type") or "UNSPECIFIED"), 99))
    best = sev_sorted[0]
    t = best.get("type") or "UNSPECIFIED"
    s = best.get("score") or ""
    return f"{t} {s}".strip()


def _normalize_tag_candidates(introduced: str) -> str:
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
    return no_v

def _github_link_exists(
    references: List[Dict]
) -> Dict[str, bool]:
    result = {
        "gh_commit": False,
        "gh_pr": False
    }
    
    for ref in references:
        url = ref.get("url")
        if ref.get("type") == "WEB" and url and url.startswith("https://github.com/"):
            if "/commit/" in url:
                result["gh_commit"] = True
            elif "/pull/" in url:
                result["gh_pr"] = True
    
    return result


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


def _vulns_to_json(
    subject: str,
    vulns: List[Dict],
    docker_repo: Optional[str],
    docker_tags: Optional[Set[str]],
) -> Dict:
    """
    Convert raw OSV vulns + docker context into a structured JSON-serializable dict.
    """
    out: Dict = {
        "subject": subject,
        "docker_repo": docker_repo,
        "docker_tag_count": len(docker_tags) if docker_tags is not None else None,
        "vulnerability_count": len(vulns),
        "vulnerabilities": [],
    }

    # newest first
    vulns_sorted = sorted(vulns, key=lambda x: (x.get("modified") or x.get("published") or ""), reverse=True)

    for v in vulns_sorted:
        v_entry: Dict = {
            "id": v.get("id"),
            "published": v.get("published"),
            "modified": v.get("modified"),
            "withdrawn": v.get("withdrawn"),
            "summary": v.get("summary"),
            "details": v.get("details"),
            "aliases": v.get("aliases") or [],
            "related": v.get("related") or [],
            "severity_raw": v.get("severity") or [],
            "best_severity": _format_best_severity(v),
            "references": [{"type": r.get("type"), "url": r.get("url")} for r in (v.get("references") or [])],
            "affected": [],
            "vuln_categories": []
        }

        vuln_description = v.get("summary") or ""
        vuln_description += "\n" + v.get("details") or ""
        vuln_categories = ClassifyVuln().invoke(openai_o4_mini, prompt_args={"vuln_description": vuln_description})
        v_entry["vuln_categories"] = vuln_categories.vuln_category

        for a in v.get("affected") or []:
            pkg = a.get("package") or {}
            affected_entry: Dict = {
                "package": {
                    "ecosystem": pkg.get("ecosystem"),
                    "name": pkg.get("name"),
                    "purl": pkg.get("purl"),
                },
                "docker_matched": [],
                "github_matched": _github_link_exists(v.get("references") or [])
            }
            for version in a.get("versions") or []:
                if _normalize_tag_candidates(version):
                    affected_entry["docker_matched"].append(version)
                    
            v_entry["affected"].append(affected_entry)

        out["vulnerabilities"].append(v_entry)

    return out


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Search OSV for vulnerabilities by repo or package name and emit JSON.")
    parser.add_argument("filename", nargs="?", help="Read package rows from CSV and write JSON files into ./test_osv")
    parser.add_argument("--ecosystem", help="Default OSV ecosystem if not in CSV (Go, npm, PyPI, Maven, RubyGems, crates.io, Packagist, NuGet).")
    parser.add_argument("--version", help="Default package version if not in CSV.")
    parser.add_argument("--commit", help="Optional commit hash (rarely used when package+version suffice).")
    parser.add_argument("--max-candidates", type=int, default=10, help="Maximum candidate mappings to try when ecosystem is not specified.")
    parser.add_argument("--docker-max-tags", type=int, default=1000, help="Max number of Docker tags to fetch for matching.")
    args = parser.parse_args(argv)

    if not args.filename or not args.filename.endswith(".csv"):
        print("Please provide a CSV file as the first argument.")
        return 2

    output_dir = "osv"
    os.makedirs(output_dir, exist_ok=True)

    with open(args.filename, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            project_name = row.get("Project Name", "") or ""
            osv_search_term = row.get("OSV Search Term", "") or ""
            docker_repo = row.get("Docker Repository", "") or ""

            if not osv_search_term:
                # Skip rows without an OSV target
                continue

            # Load docker tags if a repo is given
            docker_tags: Optional[Set[str]] = None
            if docker_repo:
                docker_tags = _load_docker_tags(docker_repo, max_tags=args.docker_max_tags)

            # Parse OSV search term → package, ecosystem, version
            # Formats: "package", "package:ecosystem", "package:ecosystem:version", "package::version"
            parts = osv_search_term.split(":")
            package_name = parts[0]
            line_ecosystem = parts[1] if len(parts) > 1 and parts[1] else args.ecosystem
            line_version = parts[2] if len(parts) > 2 and parts[2] else args.version

            # Query OSV
            vulns = search_vulns_by_name(
                package_name,
                ecosystem=line_ecosystem,
                version=line_version,
                commit=args.commit,
                max_candidates=args.max_candidates,
            )

            # Subject metadata
            subject = package_name if not line_ecosystem else f"{line_ecosystem}:{package_name}"
            if project_name:
                subject = f"{project_name} ({subject})"

            # Convert to JSON structure
            json_doc = _vulns_to_json(
                subject=subject,
                vulns=vulns,
                docker_repo=docker_repo or None,
                docker_tags=docker_tags,
            )

            # Build safe file name and write JSON
            if project_name:
                safe_filename = project_name
            else:
                safe_filename = package_name
            safe_filename = (
                safe_filename.replace("/", "_")
                .replace("@", "_")
                .replace(":", "_")
                .replace(" ", "_")
            )
            if line_ecosystem:
                safe_filename += f"_{line_ecosystem}"
            if line_version:
                safe_filename += f"_{line_version}"
            output_path = os.path.join(output_dir, f"{safe_filename}.json")

            with open(output_path, "w", encoding="utf-8") as out_f:
                json.dump(json_doc, out_f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
