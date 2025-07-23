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
import requests, re, textwrap, bs4, html, sys, json, os, urllib.parse, pprint, itertools

base = 'https://0ad2009f0372bbba801612ed00a0008b.web-security-academy.net'

r = requests.get(base)
print('Status:', r.status_code, 'length:', len(r.text))

# show first 800 chars for context
print('\n--- HEAD ---')
print(r.text[:800])

# parse forms
soup = bs4.BeautifulSoup(r.text, 'html.parser')
print('\n--- Forms ---')
for i, form in enumerate(soup.find_all('form'), 1):
    action = form.get('action')
    method = form.get('method','GET').upper()
    inputs = [(inp.get('name'), inp.get('type')) for inp in form.find_all('input')]
    print(i, method, action, inputs)

# grab all links containing query parameters
print('\n--- Links with ? ---')
for a in soup.find_all('a', href=True):
    href = a['href']
    if '?' in href:
        print(href)

""")
    print(res)

    # real = requests.get("https://example.com")
    # print(res)
    # print("-"*100)
    # print(real.text[:200])

