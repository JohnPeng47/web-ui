# docker.py
"""
Minimal Docker Hub v2 API helper.

Supports:
- Checking if a repository exists (public)
- Listing tags for a repository (paged)

Notes:
- For official images, Docker Hub uses the "library" namespace. Example:
  repo "ghost"  →  namespace="library", name="ghost" for API calls.
- This uses the "registry.hub.docker.com" host to match your example URL.
"""

from __future__ import annotations

from typing import Generator, List, Optional, Tuple

import requests

_HUB_BASE = "https://registry.hub.docker.com"


def split_repo(repo: str) -> Tuple[str, str]:
    """
    Accepts "grafana/grafana" or "ghost" and returns (namespace, name).
    If no namespace is present, defaults to "library".
    """
    repo = repo.strip().strip("/")
    if not repo:
        raise ValueError("Empty repository name.")
    if "/" in repo:
        ns, name = repo.split("/", 1)
        return ns, name
    return "library", repo


def repository_exists(repo: str, timeout: int = 20) -> bool:
    """
    Returns True if the Docker Hub repository exists (public).
    This checks the first page of tags:
      GET /v2/repositories/{namespace}/{name}/tags
    """
    namespace, name = split_repo(repo)
    url = f"{_HUB_BASE}/v2/repositories/{namespace}/{name}/tags?page_size=1"
    r = requests.get(url, timeout=timeout)
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    # Treat other codes as transient/unexpected; caller may handle separately.
    r.raise_for_status()
    return False


def list_tags(repo: str, page_size: int = 100, timeout: int = 20) -> List[str]:
    """
    Return up to `page_size` tag names (first page only) for the repository.
    """
    namespace, name = split_repo(repo)
    url = f"{_HUB_BASE}/v2/repositories/{namespace}/{name}/tags?page_size={page_size}"
    r = requests.get(url, timeout=timeout)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    data = r.json() or {}
    results = data.get("results") or []
    return [t.get("name") for t in results if t.get("name")]


def iter_all_tags(repo: str, page_size: int = 100, timeout: int = 20) -> Generator[str, None, None]:
    """
    Iterate all tags for the repository (auto-paged).
    """
    namespace, name = split_repo(repo)
    url = f"{_HUB_BASE}/v2/repositories/{namespace}/{name}/tags?page_size={page_size}"
    while url:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 404:
            return
        r.raise_for_status()
        data = r.json() or {}
        for t in data.get("results") or []:
            tag = t.get("name")
            if tag:
                yield tag
        url = data.get("next")
