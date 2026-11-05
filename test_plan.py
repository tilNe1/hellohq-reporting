import unittest
from datetime import date

import core
import server

CFG = {**core.DEFAULT_CONFIG}
P = "100001 ACME - Projektmanagement 2026 (Beispiel GmbH)"   # Dropdown-Schreibweise
PH = "100001 - ACME - Projektmanagement 2026"                          # Tabellen-Schreibweise


def hq(date, task, start, end, pause=0, desc="", project=PH):
    return {"project": project, "task": task, "description": desc, "date": date, "start": start, "end_date": date, "end": end,
            "arbeit_min": end - start - pause, "dauer_min": end - start, "pause_min": pause}


def data(cells, beginn="8:30"):
    return {"days": {"2026-11-05": {"beginn": beginn}}, "rows": [{"project": P, "task": "T100 Entwicklung", "defnote": ""},
                                                                  {"project": P, "task": "T200 Support", "defnote": ""}],
            "cells": {f"{P}|{t}|2026-11-05": {"v": v} for t, v in cells.items()}}


A, B = "T100 Entwicklung", "T200 Support"


class Abgleich(unittest.TestCase):
    def status(self, d, entries):
        plan = server.plan_month("2026-11", d, CFG, {"fetched": "x", "entries": entries})
        return {(p.get("task"), p["status"]) for p in plan}

    def test_neu(self):
        self.assertEqual(self.status(data({A: "2", B: "1"}), []), {(A, "neu"), (B, "neu")})

    def test_unveraendert_trotz_anderer_projektschreibweise(self):
        e = [hq("2026-11-05", A, 510, 630), hq("2026-11-05", B, 630, 690)]
        self.assertEqual(self.status(data({A: "2", B: "1"}), e), {(A, "unverändert"), (B, "unverändert")})

    def test_geaendert_bei_anderer_dauer(self):
        e = [hq("2026-11-05", A, 510, 600), hq("2026-11-05", B, 600, 660)]
        s = self.status(data({A: "2", B: "1"}), e)
        self.assertIn((A, "geändert"), s)

    def test_notiz_nur_wenn_lokal_gesetzt(self):
        e = [hq("2026-11-05", A, 510, 630, desc="Alte HQ-Notiz")]
        self.assertEqual(self.status(data({A: "2"}), e), {(A, "unverändert")})          # lokal keine Notiz: HQ-Text nicht überschreiben
        self.assertEqual(self.status(data({A: "2 Neue Notiz"}), e), {(A, "geändert")})   # lokal andere Notiz: ändern

    def test_mehrdeutig_und_nur_in_hq(self):
        e = [hq("2026-11-05", A, 510, 570), hq("2026-11-05", A, 600, 660), hq("2026-11-05", "T300 Betrieb", 700, 760)]
        s = self.status(data({A: "2"}), e)
        self.assertIn((A, "mehrdeutig"), s)
        self.assertIn(("T300 Betrieb", "nur in HQ"), s)

    def test_pause_wird_verglichen(self):
        # 8:30 + 6,5 h Arbeit: über 6 h -> 30 min Pause (ArbZG), nach 4 h Arbeit im Eintrag -> 8:30-15:30, Pause 30
        e = [hq("2026-11-05", A, 510, 930, pause=30)]
        self.assertEqual(self.status(data({A: "6,5"}), e), {(A, "unverändert")})
        # ohne die Pause in HQ wäre derselbe Eintrag geändert
        self.assertEqual(self.status(data({A: "6,5"}), [hq("2026-11-05", A, 510, 930, pause=0)]), {(A, "geändert")})
        # unter 6 h keine Pause
        self.assertEqual(self.status(data({A: "5"}), [hq("2026-11-05", A, 510, 810, pause=0)]), {(A, "unverändert")})

    def test_ohne_baseline_unbekannt(self):
        plan = server.plan_month("2026-11", data({A: "2"}), CFG, None)
        self.assertEqual({p["status"] for p in plan}, {"unbekannt"})


if __name__ == "__main__":
    unittest.main()


class Import(unittest.TestCase):
    PROJ = [{"project": P, "tasks": []}]

    def base(self):
        return {"fetched": "x", "entries": [
            hq("2026-11-04", A, 510, 690),                       # 8:30-11:30, 3 h
            hq("2026-11-04", B, 750, 930, desc="Review"),        # 12:30-15:30, 3 h -> Lücke 1 h = Pause
            hq("2026-11-03", A, 480, 585),                       # 1:45
        ]}

    def merged(self, st, overwrite=False):
        return server.merge_import("2026-11", st, self.base(), self.PROJ, overwrite)

    def test_tageswerte(self):
        st = {"months": {}}
        r = self.merged(st)
        d = st["months"]["2026-11"]
        self.assertEqual(sorted(r["imported_days"]), ["2026-11-03", "2026-11-04"])
        self.assertEqual(d["days"]["2026-11-04"]["beginn"], "8:30")
        self.assertEqual(d["days"]["2026-11-04"]["ende"], "15:30")
        self.assertEqual(d["days"]["2026-11-04"]["pause"], "1:00")   # 7 h Spanne - 6 h Arbeit
        self.assertEqual(d["days"]["2026-11-03"]["pause"], "0:00")   # keine Pause in HQ: ausdrücklich 0, nicht die gesetzliche
        r3 = core.day_calc({"beginn": 480, "ende": 585, "pause_min": 0}, [105], date(2026, 11, 3), CFG)
        self.assertEqual((r3["pause"], r3["arbeit"]), (0, 105))
        self.assertEqual(d["cells"][f"{P}|{A}|2026-11-04"]["v"], "3")
        self.assertEqual(d["cells"][f"{P}|{B}|2026-11-04"]["note"], "Review")
        self.assertEqual(d["cells"][f"{P}|{A}|2026-11-03"]["v"], "1,75")
        self.assertEqual(r["rows_added"], 2)
        self.assertEqual({(x["project"], x["task"]) for x in d["rows"]}, {(P, A), (P, B)})   # Dropdown-Schreibweise

    def test_eigene_eingaben_bleiben_ohne_overwrite(self):
        st = {"months": {"2026-11": {"days": {"2026-11-04": {"beginn": "9:00"}}, "rows": [], "cells": {}}}}
        r = self.merged(st)
        self.assertEqual(r["skipped_days"], ["2026-11-04"])
        self.assertEqual(st["months"]["2026-11"]["days"]["2026-11-04"]["beginn"], "9:00")
        self.merged(st, overwrite=True)
        self.assertEqual(st["months"]["2026-11"]["days"]["2026-11-04"]["beginn"], "8:30")

    def test_uebernommener_tag_wird_nicht_neu_geschrieben(self):
        st = {"months": {}}
        self.merged(st)
        d = st["months"]["2026-11"]
        plan = server.plan_month("2026-11", d, CFG, self.base())
        self.assertTrue(plan and all(p["status"] == "unverändert" for p in plan if p["date"] == "2026-11-04"))
        # ein Eingriff hebt die Sperre auf
        d["cells"][f"{P}|{A}|2026-11-04"]["v"] = "2"
        plan = server.plan_month("2026-11", d, CFG, self.base())
        self.assertTrue(any(p["status"] != "unverändert" for p in plan if p["date"] == "2026-11-04"))

    def test_erneuter_import_ersetzt_unberuehrte_tage_ohne_nachfrage(self):
        st = {"months": {}}
        self.merged(st)
        r = self.merged(st)
        self.assertEqual(r["skipped_days"], [])

    def test_viertelstunden_schreibweise(self):
        self.assertEqual([server.fmt_dec(m) for m in (105, 30, 480, 45, 20, 90)], ["1,75", "0,5", "8", "0,75", "0:20", "1,5"])
