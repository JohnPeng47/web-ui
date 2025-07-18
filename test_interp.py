import os
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Dict, Optional
import re
import sys

if __name__ == "__main__":
    from pentest_bot.web_exploit.tools.interpreter import PythonInterpreter
    import requests

    interpreter = PythonInterpreter()
    res = interpreter.run(r"""
import re, textwrap, html, requests, urllib.parse as up
from bs4 import BeautifulSoup

base = 'https://0a42001c03933a6998c6f7640091005a.web-security-academy.net'
marker = 'XSS_9c2b1'
visited = set()

session = requests.Session()

print('[*] Fetching home page')
resp = session.get(base, timeout=15)
resp.raise_for_status()
print(f'Home page: ({resp.status_code}, {len(resp.text)})')

soup = BeautifulSoup(resp.text, 'html.parser')

candidates = set()
# Links
for a in soup.find_all('a', href=True):
    href = a['href']
    if href.startswith('http') and not href.startswith(base):
        continue  # external link
    full = up.urljoin(base, href)
    parsed = up.urlparse(full)
    if parsed.query:
        candidates.add(full)
# Forms with GET
for form in soup.find_all('form', action=True):
    method = form.get('method', 'get').lower()
    if method != 'get':
        continue
    action = form['action']
    full = up.urljoin(base, action)
    inputs = [i.get('name') for i in form.find_all('input') if i.get('name')]
    if not inputs:
        continue
    q = {name: marker for name in inputs}
    full = full + ('&' if '?' in full else '?') + up.urlencode(q)
    candidates.add(full)

print(f'[*] Found {len(candidates)} candidate URLs to test')

for url in sorted(candidates):
    if url in visited:
        continue
    visited.add(url)
    # Replace or append a single parameter with the marker if not via form logic above
    parsed = up.urlparse(url)
    qs = up.parse_qs(parsed.query)
    if not qs:
        continue
    # Replace first parameter value to marker (unless already added)
    if marker not in parsed.query:
        first_key = next(iter(qs))
        qs[first_key] = [marker]
        new_q = up.urlencode({k: v[0] for k, v in qs.items()})
        url = up.urlunparse(parsed._replace(query=new_q))
    try:
        r = session.get(url, timeout=15)
    except Exception as e:
        print(f'[!] Error fetching {url}: {e}')
        continue
    body = r.text
    if marker in body:
        # Show a small context around first occurrence
        m = body.index(marker)
        start = max(0, m-60)
        end = min(len(body), m+60)
        snippet = body[start:end]
        snippet = snippet.replace('\n', ' ')
        print('\n[+] Reflection found!')
        print('URL:', url)
        print('Context:', snippet)
    else:
        print(f'[-] No reflection: {url} -> ({r.status_code}, {len(body)})')
""")
    print(res)

    # real = requests.get("https://example.com")
    # print(res)
    # print("-"*100)
    # print(real.text[:200])

