#!/usr/bin/env python3
"""Liest Reportings eines oder mehrerer Monate aus HQ (rein lesend) nach data/hq_<JJJJ-MM>.json.

  ./run.sh hq_import.py 2026-10 2026-11
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from hq_client import hq_session, read_month
from hq_login_test import OUT

DATA = Path(os.environ.get("HQ_DATA_DIR") or OUT.parent / "data")


def main(months):
    DATA.mkdir(exist_ok=True)
    with hq_session() as page:
        for ym in months:
            y, m = map(int, ym.split("-"))
            res = read_month(page, y, m)
            res["fetched"] = datetime.now().isoformat(timespec="seconds")
            (DATA / f"hq_{ym}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            n = len(res["entries"])
            print(f"{ym}: {n} Einträge (Zeitraum angezeigt: {res['range_shown']}, vorher: {res['range_before']})")
            for e in res["entries"][:3]:
                print(f"   {e['date']} {e['start']//60}:{e['start']%60:02d}-{e['end']//60}:{e['end']%60:02d} "
                      f"{e['task'][:34]:34} arbeit={e['arbeit_min']} dauer={e['dauer_min']} pause={e['pause_min']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [datetime.now().strftime("%Y-%m")]))
