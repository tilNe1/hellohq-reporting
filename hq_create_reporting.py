#!/usr/bin/env python3
"""Legt ein einzelnes Reporting (Zeitbuchung) in helloHQ an.

Standard ist ein PROBELAUF: Dialog ausfüllen, Werte zurücklesen, NICHT speichern. Gebucht wird nur mit --speichern.

  ./run.sh hq_create_reporting.py --datum 05.11.2026 --projekt "100001 ACME" --aufgabe "T100 Entwicklung" \\
      --start 8:30 --dauer "2h 15m" --pause 30m
(--dauer ist die Zeitspanne inklusive Pause; HQ rechnet Arbeitszeit = Dauer - Pause.)
"""
import argparse
import sys

import core
from hq_client import create_entry, hq_session


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datum", required=True, help="TT.MM.JJJJ")
    ap.add_argument("--projekt", required=True)
    ap.add_argument("--aufgabe", required=True)
    ap.add_argument("--beschreibung", default="")
    ap.add_argument("--start", required=True)
    ap.add_argument("--dauer", required=True)
    ap.add_argument("--pause", default="0m")
    ap.add_argument("--speichern", action="store_true", help="wirklich buchen (sonst Probelauf)")
    a = ap.parse_args()
    d, m, y = a.datum.split(".")
    entry = {"date": f"{y}-{m}-{d}", "project": a.projekt, "task": a.aufgabe, "note": a.beschreibung,
             "start": core.parse_clock(a.start), "dauer": core.parse_pause(a.dauer) if a.dauer.isdigit() else core.parse_duration(a.dauer),
             "pause": core.parse_pause(a.pause)}
    with hq_session() as page:
        print("Dialog:", create_entry(page, entry, save=a.speichern))
    print("Gebucht." if a.speichern else "PROBELAUF: nicht gespeichert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
