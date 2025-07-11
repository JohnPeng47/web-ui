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
    res = interpreter.run("""
import requests
res = requests.get("https://example.com")
print(res.text[:200])
    """)
    
    real = requests.get("https://example.com")
    print(res)
    print("-"*100)
    print(real.text[:200])

