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
import socket, sys, time

HOST, PORT = "localhost", 5000
payload = "1+1\n$$END$$\n"  # minimal test: should return 2

s = socket.socket()
s.settimeout(5)
try:
    s.connect((HOST, PORT))
    # wait a tiny bit for the server to emit its prompt (if any)
    time.sleep(0.3)
    try:
        banner = s.recv(4096)
        sys.stderr.write(banner.decode(errors="ignore"))
    except socket.timeout:
        pass  # maybe the service doesn’t send a banner

    s.sendall(payload.encode())
    data = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        except socket.timeout:
            break
    print(data.decode(errors="ignore"))
finally:
    s.close()
""")
    print(res)

    # real = requests.get("https://example.com")
    # print(res)
    # print("-"*100)
    # print(real.text[:200])

