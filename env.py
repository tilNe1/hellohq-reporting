"""Gemeinsame Umgebung für alle HQ-Skripte (Windows, macOS, Linux). Wird vor playwright importiert.

- Browser liegen im Projektordner (.browsers), unabhängig vom Benutzerverzeichnis.
- Linux ohne Root: fehlende Systembibliotheken liegen in .libs/root (siehe install.py).
- Ausgabe immer UTF-8 (Windows-Konsolen nutzen sonst cp1252 und stürzen bei Umlauten ab).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".browsers"))
os.environ.setdefault("PYTHONUTF8", "1")  # gilt für gestartete Kindprozesse

if sys.platform.startswith("linux"):
    _libs = ROOT / ".libs" / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    if _libs.is_dir() and str(_libs) not in os.environ.get("LD_LIBRARY_PATH", ""):
        os.environ["LD_LIBRARY_PATH"] = str(_libs) + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
