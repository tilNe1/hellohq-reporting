"""Gemeinsame Umgebung für alle HQ-Skripte (Windows, macOS, Linux). Wird vor playwright importiert.

- Browser liegen im Projektordner, je Betriebssystem getrennt (.browsers/windows, .browsers/linux, .browsers/macos). Playwright legt
  sonst nur einen Marker pro Version an und hielte einen Linux-Browser fälschlich für den Windows-Browser (Ordner wird dann gemeinsam genutzt, z. B. Windows + WSL).
- Linux ohne Root: fehlende Systembibliotheken liegen in .libs/root (siehe install.py).
- Ausgabe immer UTF-8 (Windows-Konsolen nutzen sonst cp1252 und stürzen bei Umlauten ab).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OS_NAME = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".browsers" / OS_NAME))
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


def launch_chromium(pw, **kw):
    """Startet Chromium. Fehlt der Browser für dieses Betriebssystem (z. B. Browser fehlt nach dem Kopieren des Projekts,
    gestartet wird unter Windows), wird er einmal automatisch nachinstalliert und der Start wiederholt."""
    try:
        return pw.chromium.launch(**kw)
    except Exception as e:  # playwright._impl._errors.Error
        if "Executable doesn't exist" not in str(e):
            raise
        import subprocess
        print("Browser für dieses System fehlt, installiere Chromium (einmalig, rund 150 MB) …", flush=True)
        r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=os.environ)
        if r.returncode:
            raise RuntimeError("Chromium konnte nicht installiert werden. Von Hand: "
                               f'"{sys.executable}" -m playwright install chromium') from e
        return pw.chromium.launch(**kw)
