"""Starts the local app and a once-daily sync without terminal windows."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT/'data'
FLAGS = getattr(subprocess,'CREATE_NO_WINDOW',0)

def alive():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/bootstrap',timeout=2) as response:
            return 'token' in json.load(response)
    except Exception:
        return False

def main():
    DATA.mkdir(exist_ok=True)
    mode = sys.argv[1] if len(sys.argv)>1 else '--daily'
    # pythonw.exe can run the backend; logs are local and contain no cookie values.
    if not alive():
        with (DATA/'app.log').open('a',encoding='utf8') as log:
            subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=ROOT,stdout=log,stderr=log,creationflags=FLAGS)
        for _ in range(30):
            if alive(): break
            time.sleep(1)
    if not alive(): return
    if mode == '--open':
        webbrowser.open('http://127.0.0.1:8765')
        mode = '--daily'
    # The Chromium extension now owns daily collection in the user's normal profile.
    # Startup only starts the local worker and API; no separate browser is launched.
    return

if __name__ == '__main__': main()
