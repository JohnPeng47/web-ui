#!/usr/bin/env python3
"""
Scrape PortSwigger’s *All labs* page and output a JSON object that
maps each vulnerability class (H2 heading) to a list of its labs.

Result format (example):

{
  "SQL injection": [
    {
      "link": "/web-security/sql-injection/lab-retrieve-hidden-data",
      "name": "SQL injection vulnerability in WHERE clause allowing retrieval of hidden data"
    },
    …
  ],
  …
}
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

###############################################################################
# Configuration – change START_URL if you prefer to fetch live.
###############################################################################
START_URL = "https://portswigger.net/web-security/all-labs"

###############################################################################
# Helper functions
###############################################################################
def fetch_html() -> str:
    """Return the raw HTML of the All-labs page (from stdin, file, or web)."""
    # 1️⃣ If HTML piped on stdin ⇒ use that.
    if not sys.stdin.isatty():
        return sys.stdin.read()

    # 2️⃣ If a local file path supplied as first CLI arg ⇒ read it.
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).read_text(encoding="utf-8")

    # 3️⃣ Otherwise download the live page.
    resp = requests.get(START_URL, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_labs(html: str, base_url: str = START_URL) -> dict[str, list[dict[str, str]]]:
    """
    Walk the DOM:

    * every <h2> gives the vulnerability type
    * every sibling <div class="widgetcontainer-lab-link"> until the next <h2>
      holds one lab (anchor has href + title)

    Return {category: [{link, name}, ...], …}
    """
    soup = BeautifulSoup(html, "html.parser")
    data = defaultdict(list)

    for h2 in soup.find_all("h2"):
        category = h2.get_text(strip=True)
        # Iterate until next heading
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            if "widgetcontainer-lab-link" in sib.get("class", []):
                a = sib.find("a", href=True)
                if not a:
                    continue
                data[category].append(
                    {
                        "link": a["href"],                 # keep relative path
                        "name": a.get_text(" ", strip=True)
                    }
                )
    return dict(data)


###############################################################################
# Main
###############################################################################
def main() -> None:
    html = fetch_html()
    labs_json = parse_labs(html)
    print(json.dumps(labs_json, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
