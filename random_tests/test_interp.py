import os
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Dict, Optional
import re
import sys

from pentest_bot.web_exploit.tools.browser_check import create_browser_check_xss

if __name__ == "__main__":
    from pentest_bot.web_exploit.tools.interpreter import PythonInterpreter

    browser_check_template, check_cb, target_url = create_browser_check_xss()

    script = r"""
import urllib.parse as up

html_variants = [
    f"<script>fetch('{target_url}')</script>",
    f"<img src='{target_url}'>",
    f"<!DOCTYPE html><html><body onload=\"(new Image()).src='{target_url}'\"></body></html>"
]
for i, html in enumerate(html_variants, 1):
    data_url = "data:text/html," + up.quote(html, safe='')
    print(f"\n[Variant]…")
    browser_check_xss(url=data_url)
""".format(target_url=target_url)

    interpreter = PythonInterpreter(shared_globals=browser_check_template)
    res = interpreter.run(script)
    print(res)
