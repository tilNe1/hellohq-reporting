#!/usr/bin/env python3
"""Lokaler Server für die Monatsübersicht (nur 127.0.0.1).

  ./run.sh server.py            -> http://127.0.0.1:8765

Daten: data/state.json (Eingaben, Einstellungen), data/projects.json (Projekte/Aufgaben aus HQ).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import env  # noqa: F401  (UTF-8-Ausgabe, Browser-Pfad für die HQ-Skripte)
import core

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("HQ_DATA_DIR") or ROOT / "data")
STATIC = ROOT / "static"
PORT = 8765
LOCK = threading.Lock()
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, obj):
    DATA.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_state():
    st = read_json(DATA / "state.json", {})
    st.setdefault("config", {})
    st.setdefault("months", {})
    st.setdefault("synced", {})
    return st


def full_config(state):
    return {**core.DEFAULT_CONFIG, **state["config"]}


def row_key(row):
    return f'{row["project"]}|{row["task"]}'


def compute_month(month, data, config):
    """Berechnet alle Felder eines Monats aus den Roheingaben. Fehler werden je Feld gemeldet."""
    year, mon = map(int, month.split("-"))
    errors = {}
    days_out = {}
    rows = data.get("rows", [])
    cells = data.get("cells", {})
    sums_row = {row_key(r): 0 for r in rows}
    for d in core.month_days(year, mon):
        iso = d.isoformat()
        raw = data.get("days", {}).get(iso, {})
        day = {}
        for field, parser, key in (("beginn", core.parse_clock, "beginn"), ("ende", core.parse_clock, "ende"),
                                   ("pause", core.parse_pause, "pause_min")):
            try:
                day[key] = parser(raw.get(field, ""))
            except ValueError as e:
                errors[f"day|{iso}|{field}"] = str(e)
                day[key] = None
        task_min, cell_out = [], {}
        for r in rows:
            c = cells.get(f"{row_key(r)}|{iso}", {})
            minutes = None
            try:
                minutes = core.parse_duration(core.split_note(c.get("v", ""))[0]) if c.get("v") else None
            except ValueError as e:
                errors[f"cell|{row_key(r)}|{iso}"] = str(e)
            note = c.get("note") or core.split_note(c.get("v", ""))[1] or ""
            if minutes:
                task_min.append(minutes)
                sums_row[row_key(r)] += minutes
            cell_out[row_key(r)] = {"min": minutes or 0, "text": core.fmt_hm(minutes), "note": note,
                                    "has_note": bool(note or r.get("defnote"))}
        res = core.day_calc(day, task_min, d, config)
        days_out[iso] = {
            "weekday": WEEKDAYS[d.weekday()], "day": d.day, "workday": core.is_workday(d, config),
            "soll": core.fmt_hm(res["soll"]), "arbeit": core.fmt_hm(res["arbeit"]), "ueber": core.fmt_hm(res["ueber"]),
            "verteilt": core.fmt_hm(res["verteilt"]), "rest": core.fmt_hm(res["rest"]),
            "pause_auto": core.fmt_hm(res["pause"]) if res["pause"] else "",
            "ende_auto": core.fmt_clock(res["ende"]) if res["ende_derived"] else "",
            "warnings": res["warnings"], "cells": cell_out,
            "_m": {k: res[k] for k in ("soll", "arbeit", "ueber", "verteilt", "rest", "pause")},
        }
    totals = {k: sum(v["_m"][k] for v in days_out.values()) for k in ("soll", "arbeit", "ueber", "verteilt", "rest")}
    for v in days_out.values():
        del v["_m"]
    return {"days": days_out, "totals": {k: core.fmt_hm(v) for k, v in totals.items()},
            "row_sums": {k: core.fmt_hm(v) for k, v in sums_row.items()}, "errors": errors}


def fmt_dec(minutes):
    """Minuten als Stunden in der Eingabeschreibweise: Viertelstunden dezimal ('1,75', '0,5', '8'), sonst H:MM."""
    if minutes % 15:
        return f"{minutes // 60}:{minutes % 60:02d}"
    t = f"{minutes / 60:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return t or "0"


def day_sig(data, iso):
    """Fingerabdruck der Eingaben eines Tages (ohne Tagesnotiz): erkennt, ob ein aus HQ übernommener Tag verändert wurde."""
    d = data.get("days", {}).get(iso, {})
    cells = sorted((k, (v.get("v") or "").strip(), (v.get("note") or "").strip())
                   for k, v in data.get("cells", {}).items() if k.endswith("|" + iso) and ((v.get("v") or "").strip() or v.get("note")))
    return json.dumps([(d.get("beginn") or "").strip(), (d.get("ende") or "").strip(), (d.get("pause") or "").strip(), cells], ensure_ascii=False)


def project_label(project_text, projects):
    c = code(project_text)
    for p in projects:
        if code(p["project"]) == c:
            return p["project"]
    return project_text


def build_import(month, baseline, projects):
    """Aus den in HQ eingelesenen Reportings eines Monats: Tageswerte, Zellen und Aufgabenzeilen.
    Beginn = frühester Start, Ende = spätestes Ende, Pause = Zeitspanne minus Arbeitszeit (Lücken zählen als Pause)."""
    by_day = {}
    for e in baseline.get("entries", []):
        if e["date"].startswith(month):
            by_day.setdefault(e["date"], []).append(e)
    days, cells, pairs = {}, {}, []
    for iso, es in sorted(by_day.items()):
        start, end = min(e["start"] for e in es), max(e["end"] for e in es)
        work = sum(e["arbeit_min"] or 0 for e in es)
        pause = max(0, (end - start) - work)
        days[iso] = {"beginn": core.fmt_clock(start).lstrip("0") if core.fmt_clock(start)[0] == "0" else core.fmt_clock(start),
                     "ende": core.fmt_clock(end), "pause": core.fmt_hm(pause) if pause else "0:00"}   # Pause immer eintragen: so zeigt die Ansicht den HQ-Stand, nicht die gesetzliche Pause
        per = {}
        for e in es:
            label = project_label(e["project"], projects)
            slot = per.setdefault((label, e["task"]), {"min": 0, "notes": []})
            slot["min"] += e["arbeit_min"] or 0
            if e["description"] and e["description"] not in slot["notes"]:
                slot["notes"].append(e["description"])
        for (label, task), v in per.items():
            if (label, task) not in pairs:
                pairs.append((label, task))
            if v["min"]:
                cells[f"{label}|{task}|{iso}"] = {"v": fmt_dec(v["min"]), "note": "; ".join(v["notes"])}
    return days, cells, pairs


def merge_import(month, st, baseline, projects, overwrite):
    """Schreibt den HQ-Stand in die Monatsdaten. Tage mit eigenen Eingaben werden nur mit overwrite ersetzt."""
    data = st["months"].setdefault(month, {"days": {}, "rows": [], "cells": {}})
    data.setdefault("days", {}); data.setdefault("rows", []); data.setdefault("cells", {})
    days, cells, pairs = build_import(month, baseline, projects)
    imported, skipped = [], []
    for iso, vals in days.items():
        own = data["days"].get(iso, {})
        has_local = any((own.get(f) or "").strip() for f in ("beginn", "ende", "pause")) or \
            any(k.endswith("|" + iso) and (v.get("v") or "").strip() for k, v in data["cells"].items())
        locked = own.get("hq_sig") == day_sig(data, iso)
        if has_local and not locked and not overwrite:
            skipped.append(iso)
            continue
        for k in [k for k in data["cells"] if k.endswith("|" + iso)]:
            del data["cells"][k]
        note = own.get("note")
        data["days"][iso] = {**vals, **({"note": note} if note else {})}
        for k, v in cells.items():
            if k.endswith("|" + iso):
                data["cells"][k] = v
        data["days"][iso]["hq_sig"] = None   # unten gesetzt, sobald alle Zellen des Tages stehen
        imported.append(iso)
    added = 0
    for label, task in pairs:
        if not any(r["project"] == label and r["task"] == task for r in data["rows"]):
            data["rows"].append({"project": label, "task": task, "defnote": ""})
            added += 1
    order = {p["project"]: i for i, p in enumerate(projects)}
    data["rows"].sort(key=lambda r: order.get(r["project"], 99))
    data["rows_init"] = True
    for iso in imported:
        data["days"][iso]["hq_sig"] = day_sig(data, iso)
    return {"imported_days": imported, "skipped_days": skipped, "rows_added": added,
            "entries": sum(1 for e in baseline.get("entries", []) if e["date"].startswith(month))}


def code(project):
    return (project or "").split()[0] if project else ""


def load_baseline(month):
    """Zuletzt aus HQ eingelesener Monat (hq_import.py); None, wenn noch nie eingelesen."""
    return read_json(DATA / f"hq_{month}.json", None)


def plan_month(month, data, config, baseline):
    """Zerlegt den Monat in HQ-Reportings und gleicht ihn mit dem aus HQ eingelesenen Stand ab.
    Status: neu | geändert | unverändert | mehrdeutig | fehler | nur in HQ (wird nie angefasst)."""
    year, mon = map(int, month.split("-"))
    hq = (baseline or {}).get("entries", [])
    plan = []
    for d in core.month_days(year, mon):
        iso = d.isoformat()
        raw = data.get("days", {}).get(iso, {})
        try:
            day = {"beginn": core.parse_clock(raw.get("beginn", "")), "ende": core.parse_clock(raw.get("ende", "")),
                   "pause_min": core.parse_pause(raw.get("pause", ""))}
        except ValueError:
            continue
        locked = bool(raw.get("hq_sig")) and raw.get("hq_sig") == day_sig(data, iso)
        entries = []
        for r in data.get("rows", []):
            c = data.get("cells", {}).get(f"{row_key(r)}|{iso}", {})
            try:
                m = core.parse_duration(core.split_note(c.get("v", ""))[0]) if c.get("v") else None
            except ValueError:
                continue
            if m:
                note = c.get("note") or core.split_note(c.get("v", ""))[1] or r.get("defnote") or ""
                entries.append({"project": r["project"], "task": r["task"], "min": m, "note": note})
        if not entries:
            continue
        res = core.day_calc(day, [e["min"] for e in entries], d, config)
        if res["beginn"] is None:
            plan.append({"date": iso, "status": "fehler", "reason": "Beginn fehlt"})
            continue
        for s in core.schedule_day(res, entries, config):
            key = f'{iso}|{s["project"]}|{s["task"]}'
            if locked:   # aus HQ übernommen und seither nicht angefasst: nicht neu schreiben
                plan.append({"date": iso, "project": s["project"], "task": s["task"], "start": core.fmt_clock(s["start"]),
                             "end": core.fmt_clock(s["end"]), "dauer": core.fmt_hm(s["dauer"]), "pause": core.fmt_hm(s["pause"]),
                             "note": s["note"], "status": "unverändert", "key": key, "hq": "aus HQ übernommen"})
                continue
            same = [h for h in hq if h["date"] == iso and code(h["project"]) == code(s["project"]) and h["task"] == s["task"]]
            old = None
            if baseline is None:
                status = "unbekannt"
            elif not same:
                status = "neu"
            elif len(same) > 1:
                status = "mehrdeutig"
            else:
                old = same[0]
                equal = (old["start"], old["end"], old["pause_min"] or 0) == (s["start"], s["end"], s["pause"])
                note_ok = (not s["note"]) or s["note"] == old["description"]
                status = "unverändert" if equal and note_ok else "geändert"
            row = {"date": iso, "project": s["project"], "task": s["task"], "start": core.fmt_clock(s["start"]),
                   "end": core.fmt_clock(s["end"]), "dauer": core.fmt_hm(s["dauer"]), "pause": core.fmt_hm(s["pause"]),
                   "note": s["note"], "status": status, "key": key,
                   "_e": {"date": iso, "project": s["project"], "task": s["task"], "start": s["start"], "dauer": s["dauer"],
                          "pause": s["pause"], "note": s["note"]}}
            if old and status == "geändert":
                row["hq"] = f'{core.fmt_clock(old["start"])}-{core.fmt_clock(old["end"])} Pause {core.fmt_hm(old["pause_min"]) or "0:00"}'
                row["_e"]["old"] = {"date": old["date"], "start": old["start"], "task": old["task"]}
            plan.append(row)
        if baseline is not None:   # Einträge dieses Tages, die nur in HQ stehen: anzeigen, nie ändern
            touched = {(e["project"] and code(e["project"]), e["task"]) for e in entries}
            for h in hq:
                if h["date"] == iso and (code(h["project"]), h["task"]) not in touched:
                    plan.append({"date": iso, "project": h["project"], "task": h["task"], "start": core.fmt_clock(h["start"]),
                                 "end": core.fmt_clock(h["end"]), "dauer": core.fmt_hm(h["dauer_min"]),
                                 "pause": core.fmt_hm(h["pause_min"]), "note": h["description"], "status": "nur in HQ", "key": ""})
    return plan


def last_note(st, project, task, before):
    """Beschreibung der letzten Buchung (Datum < before) zu dieser Aufgabe: zuerst lokale Einträge
    (alle Monate), sonst aus HQ eingelesene Reportings (Projektcode + Aufgabe). Liefert (Text, Datum, Quelle)."""
    best = None   # (datum, text, quelle)
    key = f"{project}|{task}|"
    for m in st.get("months", {}).values():
        for k, c in m.get("cells", {}).items():
            if not k.startswith(key):
                continue
            iso = k[len(key):]
            if iso >= before:
                continue
            text = c.get("note") or core.split_note(c.get("v", ""))[1]
            if text and (best is None or iso > best[0]):
                best = (iso, text, "lokal")
    for f in DATA.glob("hq_*.json"):
        for h in (read_json(f, {}) or {}).get("entries", []):
            if h["date"] < before and code(h["project"]) == code(project) and h["task"] == task and h.get("description"):
                if best is None or h["date"] > best[0]:
                    best = (h["date"], h["description"], "HQ")
    return best


class Handler(BaseHTTPRequestHandler):
    server_version = "Monatsuebersicht/1.0"

    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "Host nicht erlaubt"})
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/bootstrap":
            with LOCK:
                st = load_state()
            return self._send(200, {"projects": read_json(DATA / "projects.json", {"projects": []})["projects"],
                                    "config": full_config(st), "today": date.today().isoformat()})
        if path.startswith("/api/month/"):
            month = path.rsplit("/", 1)[1]
            with LOCK:
                st = load_state()
            data = st["months"].get(month, {"days": {}, "rows": [], "cells": {}})
            return self._send(200, {"data": data, "computed": compute_month(month, data, full_config(st))})
        self._send(404, {"error": "nicht gefunden"})

    def do_POST(self):
        if not self._host_ok() or "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._send(403, {"error": "nicht erlaubt"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "kein JSON"})
        path = self.path.split("?")[0]
        with LOCK:
            st = load_state()
            if path == "/api/month":
                month, data = body["month"], body["data"]
                st["months"][month] = data
                write_json(DATA / "state.json", st)
                return self._send(200, {"computed": compute_month(month, data, full_config(st))})
            if path == "/api/config":
                st["config"] = {k: v for k, v in body.items() if k in core.DEFAULT_CONFIG}
                write_json(DATA / "state.json", st)
                return self._send(200, {"config": full_config(st)})
            if path == "/api/lastnote":
                r = last_note(st, body["project"], body["task"], body.get("before") or "9999-12-31")
                return self._send(200, {"found": bool(r), "date": r and r[0], "note": r and r[1], "source": r and r[2]})
            if path == "/api/plan":
                month = body["month"]
                data = st["months"].get(month, {"days": {}, "rows": [], "cells": {}})
                base = load_baseline(month)
                plan = plan_month(month, data, full_config(st), base)
                for p in plan:
                    p.pop("_e", None)
                return self._send(200, {"plan": plan, "baseline": (base or {}).get("fetched")})
            if path == "/api/hq/import":
                return self._send(200, run_script(["hq_import.py", body["month"]]))
            if path == "/api/hq/import-month":
                month = body["month"]
                if not body.get("reuse"):
                    r = run_script(["hq_import.py", month])
                    if not r["ok"]:
                        return self._send(200, r)
                base = load_baseline(month)
                if base is None:
                    return self._send(200, {"ok": False, "message": "Kein HQ-Stand vorhanden"})
                projects = read_json(DATA / "projects.json", {"projects": []})["projects"]
                res = merge_import(month, st, base, projects, bool(body.get("overwrite")))
                write_json(DATA / "state.json", st)
                return self._send(200, {"ok": True, **res})
            if path == "/api/hq/sync":
                month = body["month"]
                data = st["months"].get(month, {"days": {}, "rows": [], "cells": {}})
                plan = plan_month(month, data, full_config(st), load_baseline(month))
                keys = set(body.get("keys") or [])
                todo = [p for p in plan if p["key"] in keys and p["status"] in ("neu", "geändert")]
                entries = [{**p["_e"], "action": "create" if p["status"] == "neu" else "edit"} for p in todo]
                if not entries:
                    return self._send(200, {"ok": True, "message": "Nichts zu übertragen", "results": []})
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
                    json.dump({"month": month, "entries": entries}, f, ensure_ascii=False)
                args = ["hq_sync.py", f.name] + (["--speichern"] if body.get("save") else [])
                try:
                    return self._send(200, run_script(args, result_key="RESULT:"))
                finally:
                    Path(f.name).unlink(missing_ok=True)
        self._send(404, {"error": "nicht gefunden"})


def run_script(args, result_key=None, timeout=900):
    """Startet ein HQ-Skript im Projektordner (Browser-Automatisierung, dauert Sekunden bis Minuten)."""
    try:
        p = subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env={**os.environ, "PYTHONUTF8": "1"})
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "Zeitüberschreitung beim HQ-Zugriff"}
    out = (p.stdout or "") + (p.stderr or "")
    res = {"ok": p.returncode == 0, "log": out[-1500:]}
    if result_key:
        line = next((l for l in reversed(out.splitlines()) if l.startswith(result_key)), None)
        if line:
            res.update(json.loads(line[len(result_key):]))
    return res


def main():
    DATA.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Monatsübersicht läuft auf http://127.0.0.1:{PORT} (Strg+C beendet)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
