#!/usr/bin/env python3
"""Überträgt geplante Reportings nach HQ: neue anlegen, bestehende bearbeiten. Löscht nie etwas.

  ./run.sh hq_sync.py PLAN.json              # Probelauf: Dialog ausfüllen und zurücklesen, NICHT speichern
  ./run.sh hq_sync.py PLAN.json --speichern  # wirklich speichern

PLAN.json: {"month": "JJJJ-MM", "entries": [{"action": "create"|"edit", "date", "project", "task", "start", "dauer",
            "pause", "note", "old": {"date", "start", "task"}}]}   (Zeiten in Minuten)
Die letzte Zeile der Ausgabe ist 'RESULT:' + JSON.
"""
import json
import os
import sys
from pathlib import Path
import traceback
from datetime import datetime

import calendar

from hq_client import create_entry, edit_entry, hq_session, read_month, set_range, current_range, _restore_range
from hq_login_test import OUT

DATA = Path(os.environ.get("HQ_DATA_DIR") or OUT.parent / "data")


def main(plan_path, save):
    plan = json.loads(open(plan_path, encoding="utf-8").read())
    y, m = map(int, plan["month"].split("-"))
    results = []
    with hq_session() as page:
        before = current_range(page)
        try:
            set_range(page, y, m, 1, y, m, calendar.monthrange(y, m)[1])
            for e in plan["entries"]:
                label = f'{e["date"]} {e["task"]}'
                try:
                    shown = (create_entry(page, e, save) if e["action"] == "create" else edit_entry(page, e["old"], e, save))
                    results.append({"entry": label, "ok": True, "dialog": shown, "saved": save})
                    print(f"{'GESPEICHERT' if save else 'PROBE'} {e['action']:6} {label}: {shown}")
                except Exception as err:  # weitermachen, am Ende melden
                    results.append({"entry": label, "ok": False, "error": str(err)[:300]})
                    print(f"FEHLER {label}: {str(err)[:200]}")
                    traceback.print_exc(limit=1)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
        finally:
            _restore_range(page, before)
        if save:
            res = read_month(page, y, m)
            res["fetched"] = datetime.now().isoformat(timespec="seconds")
            (DATA / f"hq_{plan['month']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("RESULT:" + json.dumps({"saved": save, "results": results}, ensure_ascii=False))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(args[0], "--speichern" in sys.argv))
