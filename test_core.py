import unittest
from datetime import date

from core import (day_calc, effective_pause, is_workday, legal_pause, parse_clock, parse_duration, parse_pause, round_to,
                  schedule_day, split_note)

CFG = {"soll_min": 480, "round_min": 15, "pause_start": None, "pause_len_min": None, "free_days": []}


class Eingaben(unittest.TestCase):
    def test_uhrzeit(self):
        self.assertEqual(parse_clock("8:30"), 510)
        self.assertEqual(parse_clock("08.30"), 510)
        self.assertEqual(parse_clock("830"), 510)
        self.assertEqual(parse_clock("9"), 540)
        self.assertIsNone(parse_clock(""))
        with self.assertRaises(ValueError):
            parse_clock("25:00")

    def test_dauer(self):
        self.assertEqual(parse_duration("1,75"), 105)
        self.assertEqual(parse_duration("1.75"), 105)
        self.assertEqual(parse_duration("1:45"), 105)
        self.assertEqual(parse_duration("1h 45m"), 105)
        self.assertEqual(parse_duration("45m"), 45)
        self.assertEqual(parse_duration("0,5h"), 30)
        with self.assertRaises(ValueError):
            parse_duration("abc")

    def test_ziffernfolgen(self):
        self.assertEqual(parse_clock("830"), 510)
        self.assertEqual(parse_clock("17"), 1020)
        self.assertEqual(parse_clock("1630"), 990)
        self.assertEqual(parse_clock("8,30"), 510)
        self.assertEqual(parse_duration("175"), 105)     # 1,75 h
        self.assertEqual(parse_duration("05"), 30)       # 0,5 h
        self.assertEqual(parse_duration("8"), 480)       # 8 h
        self.assertEqual(parse_duration("150"), 90)      # 1,5 h
        self.assertEqual(parse_pause("30"), 30)          # Pause: reine Zahl = Minuten
        self.assertEqual(parse_pause("45"), 45)
        self.assertEqual(parse_pause("1:00"), 60)
        self.assertEqual(parse_pause("1,5"), 90)

    def test_notiz_hinter_zahl(self):
        self.assertEqual(split_note("1,75 Sprint-Review"), ("1,75", "Sprint-Review"))
        self.assertEqual(split_note("1:45 Planung mit Team"), ("1:45", "Planung mit Team"))
        self.assertEqual(split_note("2h Workshop"), ("2h", "Workshop"))
        self.assertEqual(split_note("2"), ("2", ""))


class Pause(unittest.TestCase):
    def test_arbzg(self):
        self.assertEqual(legal_pause(6 * 60), 0)            # genau 6 h: keine Pflichtpause
        self.assertEqual(legal_pause(6 * 60 + 1), 30)
        self.assertEqual(legal_pause(9 * 60 + 30), 30)      # netto 9:00: noch 30 min
        self.assertEqual(legal_pause(9 * 60 + 31), 45)      # netto 9:01 mit 30 min -> 45 min
        self.assertEqual(legal_pause(10 * 60), 45)

    def test_nutzerpause(self):
        cfg = {**CFG, "pause_start": "12:00", "pause_len_min": 60}
        self.assertEqual(effective_pause(510, 1050, cfg), (60, 720))   # 8:30-17:30, Mittag 1 h
        self.assertEqual(effective_pause(510, 600, cfg), (0, None))    # kurzer Vormittag, Pause nicht im Fenster
        # Nutzerpause kürzer als Gesetz wird auf das Gesetz angehoben
        cfg2 = {**CFG, "pause_start": "12:00", "pause_len_min": 15}
        self.assertEqual(effective_pause(480, 1080, cfg2)[0], 45)      # 10 h Spanne -> 45 min

    def test_manuelle_pause_gewinnt(self):
        self.assertEqual(effective_pause(510, 1050, CFG, manual=45), (45, None))


class Tag(unittest.TestCase):
    def test_normaler_tag(self):
        # Do 05.11.2026, 8:30-17:00, ohne Wunsch -> 30 min gesetzlich, netto 8:00, keine Überstunden
        r = day_calc({"beginn": 510, "ende": 1020}, [480], date(2026, 11, 5), CFG)
        self.assertEqual((r["pause"], r["arbeit"], r["ueber"], r["rest"]), (30, 480, 0, 0))

    def test_rundung_und_ueberstunden(self):
        # 8:00-16:48: Spanne 528 min, 30 min Pause -> netto 498 min -> auf 15 min gerundet 495 (8:15), 15 min Überstunden
        r = day_calc({"beginn": 480, "ende": 1008}, [], date(2026, 11, 5), CFG)
        self.assertEqual((r["arbeit"], r["ueber"]), (495, 15))

    def test_ende_wird_abgeleitet(self):
        r = day_calc({"beginn": 510}, [105 + 60], date(2026, 11, 5), CFG)  # nur Beginn, 2:45 verteilt
        self.assertTrue(r["ende_derived"])
        self.assertEqual(r["ende"], 510 + 165)   # unter 6 h: keine Pause

    def test_wochenende_hat_kein_soll(self):
        r = day_calc({"beginn": 600, "ende": 720}, [120], date(2026, 11, 7), CFG)  # Samstag
        self.assertEqual(r["soll"], 0)
        self.assertEqual(r["ueber"], 120)

    def test_warnung_pause_zu_kurz(self):
        r = day_calc({"beginn": 480, "ende": 1020, "pause_min": 15}, [], date(2026, 11, 5), CFG)
        self.assertTrue(any("gesetzlich" in w for w in r["warnings"]))


class FreieTage(unittest.TestCase):
    def test_wochentag_und_datum(self):
        cfg = {**CFG, "free_days": ["Freitag", "24.12.2026", "2026-12-31", "unsinn"]}
        self.assertFalse(is_workday(date(2026, 11, 6), cfg))    # Freitag
        self.assertFalse(is_workday(date(2026, 11, 13), cfg))   # jeder Freitag
        self.assertTrue(is_workday(date(2026, 11, 5), cfg))     # Donnerstag
        self.assertFalse(is_workday(date(2026, 12, 24), cfg))   # deutsches Datum
        self.assertFalse(is_workday(date(2026, 12, 31), cfg))   # ISO-Datum

    def test_kurzform_und_gross_klein(self):
        self.assertFalse(is_workday(date(2026, 11, 2), {**CFG, "free_days": ["MONTAG"]}))
        self.assertFalse(is_workday(date(2026, 11, 4), {**CFG, "free_days": ["mi"]}))

    def test_freier_wochentag_ohne_soll(self):
        cfg = {**CFG, "free_days": ["Freitag"]}
        r = day_calc({"beginn": 480, "ende": 780}, [270], date(2026, 11, 6), cfg)   # Freitag 8:00-13:00 gearbeitet
        self.assertEqual((r["soll"], r["ueber"]), (0, r["arbeit"]))


class Zerlegung(unittest.TestCase):
    def test_pause_im_eintrag(self):
        cfg = {**CFG, "pause_start": "12:00", "pause_len_min": 60}
        res = day_calc({"beginn": 510, "ende": 1050}, [210, 270, 0], date(2026, 11, 5), cfg)
        plan = schedule_day(res, [
            {"project": "P", "task": "A", "min": 210, "note": ""},
            {"project": "P", "task": "B", "min": 270, "note": ""},
        ], cfg)
        # A: 8:30-12:00 (3:30), B: 12:00-17:30 -> Pause 60 vor B, B 13:00-17:30
        self.assertEqual((plan[0]["start"], plan[0]["end"], plan[0]["pause"]), (510, 720, 0))
        self.assertEqual((plan[1]["start"], plan[1]["end"], plan[1]["pause"]), (780, 1050, 0))

    def test_pause_laeuft_ueber_eintrag(self):
        cfg = {**CFG, "pause_start": "12:00", "pause_len_min": 60}
        res = day_calc({"beginn": 510, "ende": 1050}, [300, 180], date(2026, 11, 5), cfg)
        plan = schedule_day(res, [
            {"project": "P", "task": "A", "min": 300, "note": ""},   # 8:30 + 5 h Arbeit = Pause fällt hinein
            {"project": "P", "task": "B", "min": 180, "note": ""},
        ], cfg)
        self.assertEqual((plan[0]["start"], plan[0]["end"], plan[0]["dauer"], plan[0]["pause"]), (510, 870, 360, 60))
        self.assertEqual((plan[1]["start"], plan[1]["end"], plan[1]["pause"]), (870, 1050, 0))


if __name__ == "__main__":
    unittest.main()
