#!/usr/bin/env python3
"""Schreibt die Standardwerte (Sollzeit, Rundung, Pause, freie Tage) in data/state.json, ohne vorhandene Monate anzufassen.

  ./run.sh setup_config.py --soll 8:00 --rundung 15 --pause-start 12:00 --pause-laenge 1:00 --frei "Freitag, 24.12.2026"
Leere Werte bei --pause-start/--pause-laenge bedeuten: nur gesetzliche Pause (ArbZG §4).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import core

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("HQ_DATA_DIR") or ROOT / "data")


def duration(text, label):
    try:
        v = core.parse_pause(text) if text.strip().isdigit() else core.parse_duration(text)
    except ValueError:
        sys.exit(f"{label}: '{text}' ist keine gültige Dauer (z. B. 8:00 oder 7,5)")
    if v is None:
        sys.exit(f"{label}: Wert fehlt")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soll", default="8:00")
    ap.add_argument("--rundung", type=int, default=15)
    ap.add_argument("--pause-start", default="")
    ap.add_argument("--pause-laenge", default="")
    ap.add_argument("--frei", default="", help="Komma- oder zeilengetrennt: Datum (JJJJ-MM-TT, TT.MM.JJJJ) oder Wochentag")
    a = ap.parse_args()

    if not 1 <= a.rundung <= 60:
        sys.exit("Rundung: 1 bis 60 Minuten")
    pause_start = None
    if a.pause_start.strip():
        try:
            core.parse_clock(a.pause_start)
        except ValueError:
            sys.exit(f"Pausenbeginn: '{a.pause_start}' ist keine Uhrzeit (z. B. 12:00)")
        minutes = core.parse_clock(a.pause_start)
        pause_start = f"{minutes // 60}:{minutes % 60:02d}"
    pause_len = duration(a.pause_laenge, "Pausenlänge") if a.pause_laenge.strip() else None
    if bool(pause_start) != bool(pause_len):
        sys.exit("Pausenbeginn und Pausenlänge gehören zusammen: beide angeben oder beide leer lassen")
    free = [x.strip() for x in a.frei.replace("\n", ",").split(",") if x.strip()]
    unknown = [x for x in free if core.free_day_rules([x]) == (set(), set())]
    if unknown:
        sys.exit("Freie Tage nicht erkannt: " + ", ".join(unknown) + " (erlaubt: Wochentag oder Datum JJJJ-MM-TT / TT.MM.JJJJ)")

    DATA.mkdir(exist_ok=True)
    path = DATA / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state["config"] = {"soll_min": duration(a.soll, "Sollzeit"), "round_min": a.rundung, "pause_start": pause_start,
                       "pause_len_min": pause_len, "free_days": free}
    state.setdefault("months", {})
    state.setdefault("synced", {})
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    c = state["config"]
    print(f"Gespeichert in {path}: Soll {core.fmt_hm(c['soll_min'])}, Rundung {c['round_min']} min, "
          f"Pause {'nach Gesetz (ArbZG §4)' if not pause_start else pause_start + ' für ' + core.fmt_hm(pause_len)}, "
          f"freie Tage: {', '.join(free) or 'keine'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
