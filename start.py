#!/usr/bin/env python3
"""Startet die Monatsübersicht und öffnet den Browser (Windows, macOS, Linux). Beenden mit Strg+C."""
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def open_browser_when_ready():
    for _ in range(40):
        try:
            urllib.request.urlopen(URL + "/api/bootstrap", timeout=1).read()
            break
        except OSError:
            time.sleep(0.25)
    if not webbrowser.open(URL):
        print(f"Bitte im Browser öffnen: {URL}")


def main():
    py = VENV_PY if VENV_PY.exists() else Path(sys.executable)
    if py == Path(sys.executable) and not VENV_PY.exists():
        print("Hinweis: .venv fehlt, bitte zuerst 'python install.py' ausführen.")
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    try:
        return subprocess.call([str(py), str(ROOT / "server.py")], cwd=ROOT)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
