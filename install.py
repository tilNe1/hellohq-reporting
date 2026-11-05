#!/usr/bin/env python3
"""Installation der HQ-Monatsübersicht auf einem neuen Computer: Windows, macOS und Linux (inkl. WSL).

  python install.py              interaktiv: richtet alles ein, fragt Standardwerte ab, wartet auf die Zugangsdaten
  python install.py --skip-hq    ohne Verbindungstest und ohne Projektabruf aus HQ (z. B. offline)
  python install.py --yes        alle Fragen mit dem Vorgabewert beantworten (Zugangsdaten werden trotzdem abgewartet)

Nur Standardbibliothek, mehrfach ausführbar: Vorhandenes wird erkannt und übersprungen.
Zugangsdaten werden nie angezeigt oder geloggt.
"""
import argparse
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
CRED_DIR = Path(os.environ.get("HQ_CRED_DIR") or Path.home() / ".config" / "hellohq")
CRED = CRED_DIR / "credentials.env"
LIBS = ROOT / ".libs"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def say(text=""):
    print(text, flush=True)


def head(text):
    say(f"\n== {text}")


def ok(text):
    say(f"  [ok] {text}")


def warn(text):
    say(f"  [!]  {text}")


def die(text):
    say(f"  [FEHLER] {text}")
    sys.exit(1)


def run(cmd, **kw):
    """Führt einen Befehl im Projektordner aus; Rückgabe: CompletedProcess (Ausgabe als Text)."""
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".browsers"), "PYTHONUTF8": "1", **kw.pop("env", {})}
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, env=env, capture_output=kw.pop("capture", True), text=True,
                          encoding="utf-8", errors="replace", **kw)


class Ask:
    def __init__(self, yes):
        self.yes = yes

    def text(self, question, default=""):
        if self.yes:
            return default
        shown = default if default else "leer"
        try:
            answer = input(f"  {question} [{shown}]: ").strip()
        except EOFError:
            answer = ""
        if answer == "-":
            return ""
        return answer or default

    def yesno(self, question, default=True):
        if self.yes:
            return default
        try:
            answer = input(f"  {question} [{'J/n' if default else 'j/N'}]: ").strip().lower()
        except EOFError:
            answer = ""
        return default if not answer else answer in ("j", "ja", "y", "yes")


# ---------------------------------------------------------------- 1. Voraussetzungen
def step_prereq():
    head("1/7 Voraussetzungen")
    if sys.version_info < (3, 10):
        die(f"Python 3.10 oder neuer nötig (gefunden: {platform.python_version()}). Download: https://www.python.org/downloads/")
    ok(f"Python {platform.python_version()} ({platform.system()}{' / WSL' if 'microsoft' in platform.release().lower() else ''})")
    try:
        import ensurepip, venv  # noqa: F401
    except ImportError:
        hint = "sudo apt install python3-venv" if IS_LINUX else "Python neu von python.org installieren (Option 'pip' aktivieren)"
        die(f"Das Modul 'venv' fehlt. {hint}")
    ok("venv verfügbar")


# ---------------------------------------------------------------- 2. Python-Umgebung
def step_venv():
    head("2/7 Python-Umgebung (.venv) und Pakete")
    if not VENV_PY.exists():
        r = run([sys.executable, "-m", "venv", ROOT / ".venv"])
        if r.returncode:
            die("venv konnte nicht erstellt werden:\n" + r.stderr[-400:])
        ok(".venv erstellt")
    else:
        ok(".venv vorhanden")
    r = run([VENV_PY, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", ROOT / "requirements.txt"])
    if r.returncode:
        die("Paketinstallation fehlgeschlagen (Netzwerk? pypi.org erreichbar?):\n" + r.stderr[-400:])
    ver = re.search(r"^playwright\s+(\S+)", run([VENV_PY, "-m", "pip", "list"]).stdout, re.M | re.I)
    ok(f"Pakete installiert (playwright {ver.group(1) if ver else '?'})")


# ---------------------------------------------------------------- 3. Browser
def step_browser():
    head("3/7 Browser für die HQ-Anbindung (Chromium, rund 150 MB, bei Wiederholung schnell)")
    r = run([VENV_PY, "-m", "playwright", "install", "chromium"], capture=False)
    if r.returncode:
        die("Chromium konnte nicht geladen werden (Netzwerk?)")
    ok("Chromium installiert")


# ---------------------------------------------------------------- 4. Systembibliotheken (nur Linux)
def chrome_binary():
    hits = sorted((ROOT / ".browsers").glob("chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
    return hits[0] if hits else None


def missing_libs(chrome):
    libdir = LIBS / "root" / "usr" / "lib" / "x86_64-linux-gnu"
    env = {**os.environ, "LD_LIBRARY_PATH": f"{libdir}{os.pathsep}{os.environ.get('LD_LIBRARY_PATH', '')}"}
    out = subprocess.run(["ldd", str(chrome)], capture_output=True, text=True, env=env).stdout
    return [line.split()[0] for line in out.splitlines() if "not found" in line]


def step_libs(ask):
    head("4/7 Systembibliotheken für Chromium")
    if not IS_LINUX:
        ok("auf Windows und macOS nicht nötig")
        return
    chrome = chrome_binary()
    if not chrome:
        die("Chromium wurde nicht gefunden")
    miss = missing_libs(chrome)
    if not miss:
        ok("alle Bibliotheken vorhanden")
        return
    warn("Es fehlen: " + " ".join(miss))
    if not ask.yes and ask.yesno("Mit sudo installieren (empfohlen, fragt ggf. nach deinem Passwort)?", True):
        r = subprocess.run(["sudo", str(VENV_PY), "-m", "playwright", "install-deps", "chromium"], cwd=ROOT)
        if r.returncode:
            warn("sudo-Installation fehlgeschlagen, versuche es ohne Root")
        miss = missing_libs(chrome)
    if miss and shutil.which("apt-get"):
        warn("Entpacke die fehlenden Pakete ohne Root in .libs/ (Debian/Ubuntu: apt-get download)")
        pkgs = set()
        for lib in miss:
            if lib.startswith("libnspr4"):
                pkgs.add("libnspr4")
            elif re.match(r"lib(nss3|nssutil3|smime3|ssl3)\.so", lib):
                pkgs.add("libnss3")
            elif lib.startswith("libasound.so"):
                pol = subprocess.run(["apt-cache", "policy", "libasound2t64"], capture_output=True, text=True).stdout
                pkgs.add("libasound2t64" if re.search(r"Candidate: \d", pol) else "libasound2")
            else:
                warn(f"Keine automatische Zuordnung für {lib}")
        debs = LIBS / "debs"
        debs.mkdir(parents=True, exist_ok=True)
        subprocess.run(["apt-get", "download", *sorted(pkgs)], cwd=debs, capture_output=True)
        for deb in debs.glob("*.deb"):
            subprocess.run(["dpkg", "-x", str(deb), str(LIBS / "root")], capture_output=True)
        miss = missing_libs(chrome)
    if miss:
        die("Weiterhin fehlend: " + " ".join(miss) + f"\n  Installiere sie von Hand, z. B.: sudo {VENV_PY} -m playwright install-deps chromium")
    ok("Bibliotheken ergänzt")


# ---------------------------------------------------------------- 5. Standardwerte
def step_defaults(ask):
    head("5/7 Standardwerte (jederzeit in der Oberfläche unter 'Einstellungen' änderbar; '-' leert einen Vorgabewert)")
    soll = ask.text("Sollzeit pro Arbeitstag (Mo-Fr), z. B. 8:00 oder 7,5", "8:00")
    rnd = ask.text("Rundung der Arbeitszeit in Minuten", "15")
    say("  Typische Pause, z. B. 12:00 für 1:00. Leer lassen = nur die gesetzliche Pause (ArbZG §4: über 6 h 30 min, über 9 h 45 min).")
    ps = ask.text("Typische Pause: Beginn", "12:00")
    pl = ask.text("Typische Pause: Länge", "1:00") if ps else ""
    say("  Freie Tage: Wochentage (z. B. Freitag) und/oder Daten (JJJJ-MM-TT oder TT.MM.JJJJ), durch Komma getrennt.")
    free = ask.text("Freie Tage", "")
    url = ask.text("HQ-Adresse Ihrer helloHQ-Instanz, z. B. https://firma.hellohq.io", os.environ.get("HQ_URL", "")).rstrip("/")
    if not url.startswith("https://"):
        die("Die HQ-Adresse fehlt oder beginnt nicht mit https:// (bei --yes: Umgebungsvariable HQ_URL setzen)")
    r = run([VENV_PY, "setup_config.py", "--soll", soll, "--rundung", rnd, "--pause-start", ps, "--pause-laenge", pl, "--frei", free])
    say("  " + (r.stdout.strip() or r.stderr.strip()))
    if r.returncode:
        die("Die Standardwerte sind ungültig, bitte die Installation erneut starten")
    return url


# ---------------------------------------------------------------- 6. Zugangsdaten
def read_creds():
    values = {}
    try:
        for line in CRED.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def lock_down(path):
    """Datei bzw. Ordner nur für den aktuellen Benutzer lesbar machen."""
    if IS_WIN:
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(OI)(CI)F" if path.is_dir() else f"{getpass.getuser()}:F"],
                       capture_output=True)
    else:
        os.chmod(path, 0o700 if path.is_dir() else 0o600)


def write_creds(url, user="", password=""):
    CRED_DIR.mkdir(parents=True, exist_ok=True)
    lock_down(CRED_DIR)
    CRED.write_text("# Zugangsdaten für HQ (nur lokal, nicht teilen, nicht in Git)\n"
                    f"HQ_URL={url}\nHQ_USER={user}\nHQ_PASSWORD={password}\n", encoding="utf-8")
    lock_down(CRED)


def open_in_editor(path):
    try:
        if IS_WIN:
            os.startfile(str(path))  # noqa: S606  (Standardprogramm für .env, sonst Notepad)
        elif IS_MAC:
            subprocess.Popen(["open", "-t", str(path)])
        else:
            editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi")
            subprocess.run([editor, str(path)])
    except Exception as err:  # noqa: BLE001
        warn(f"Editor konnte nicht geöffnet werden ({err}). Bitte die Datei von Hand öffnen.")


def step_credentials(ask, url):
    head("6/7 Zugangsdaten für HQ")
    old = read_creds()
    if old.get("HQ_USER") and old.get("HQ_PASSWORD") and ask.yesno("Es gibt schon gespeicherte Zugangsdaten. Behalten?", True):
        write_creds(url, old["HQ_USER"], old["HQ_PASSWORD"])  # aktualisiert nur HQ_URL
        ok(f"Zugangsdaten behalten ({CRED})")
        return
    write_creds(url)
    say()
    say("  Bitte trage Benutzername und Passwort in diese Datei ein und SPEICHERE sie:")
    say(f"    {CRED}")
    say("  Zeilen: HQ_USER=...  und  HQ_PASSWORD=...  (ohne Anführungszeichen, ohne Leerzeichen um das =).")
    say("  Das Passwort erscheint nicht hier im Terminal. Ich warte, bis beide Werte gespeichert sind (Abbrechen mit Strg+C).")
    if not ask.yes and ask.yesno("Datei jetzt im Editor öffnen?", True):
        open_in_editor(CRED)
    waited = 0
    try:
        while True:
            c = read_creds()
            if c.get("HQ_USER") and c.get("HQ_PASSWORD"):
                break
            time.sleep(2)
            waited += 2
            if waited % 30 == 0:
                say(f"  … warte weiter auf die gespeicherten Zugangsdaten ({CRED.name})")
    except KeyboardInterrupt:
        die("Abgebrochen. Mit 'python install.py' später fortsetzen (alles Bisherige bleibt erhalten).")
    lock_down(CRED)
    ok("Zugangsdaten gespeichert (nur für dich lesbar)")


# ---------------------------------------------------------------- 7. Prüfung
def step_check(skip_hq):
    head("7/7 Prüfung")
    r = run([VENV_PY, "-m", "unittest", "test_core", "test_plan"])
    ok("Rechenkern und Abgleich: Tests bestanden") if r.returncode == 0 else warn("Tests fehlgeschlagen: python -m unittest test_core test_plan")
    if skip_hq:
        warn("HQ-Verbindung übersprungen (--skip-hq). Später: hq_login_test.py und hq_projects.py")
        return
    say("  Teste die Anmeldung bei HQ (etwa 20 Sekunden) ...")
    r = run([VENV_PY, "hq_login_test.py"])
    if "[Reportings] Titel: 'Reportings'" not in r.stdout:
        warn(f"Anmeldung bei HQ fehlgeschlagen. Prüfe Benutzername, Passwort und HQ-Adresse in {CRED}, dann: hq_login_test.py")
        return
    ok("Anmeldung bei HQ funktioniert")
    say("  Lese Projekte und Aufgaben aus HQ (etwa 1 Minute) ...")
    r = run([VENV_PY, "hq_projects.py"])
    pj = ROOT / "data" / "projects.json"
    if r.returncode == 0 and pj.exists() and pj.stat().st_size:
        d = json.loads(pj.read_text(encoding="utf-8"))
        ok(f"Projekte und Aufgaben gespeichert ({len(d['projects'])} Projekte, {sum(len(p['tasks']) for p in d['projects'])} Aufgaben)")
    else:
        warn("Projekte konnten nicht gelesen werden. Später: hq_projects.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-hq", action="store_true")
    ap.add_argument("--yes", "-y", action="store_true")
    a = ap.parse_args()
    ask = Ask(a.yes)
    say("HQ-Monatsübersicht: Installation")
    say(f"Ordner: {ROOT}")
    step_prereq()
    step_venv()
    step_browser()
    step_libs(ask)
    url = step_defaults(ask)
    step_credentials(ask, url)
    step_check(a.skip_hq)
    say()
    say("Fertig. Starten:")
    say("  Windows:        start.bat (Doppelklick)")
    say("  macOS / Linux:  ./start.sh")
    say("  überall:        python start.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
