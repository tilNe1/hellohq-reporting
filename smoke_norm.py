#!/usr/bin/env python3
"""Rauchtest: Eingaben werden beim Verlassen des Feldes vereinheitlicht (gegen Server mit Test-Datenverzeichnis)."""
import sys
from playwright.sync_api import sync_playwright

CASES_CLOCK = [("830", "8:30"), ("17", "17:00"), ("1630", "16:30"), ("08:30", "8:30"), ("9.15", "9:15"), ("abc", "abc")]
CASES_DUR = [("175", "1,75"), ("05", "0,5"), ("8", "8"), ("1.75", "1,75"), ("150", "1,5"), ("10", "1"), ("1:45", "1:45"),
             ("175 Review", "1,75 Review"), ("2h 30m", "2h 30m")]
CASES_PAUSE = [("30", "0:30"), ("45", "0:45"), ("90", "1:30"), ("1:00", "1:00")]


def main():
    ok = True
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_context(viewport={"width": 1600, "height": 900}).new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://127.0.0.1:8765/", wait_until="networkidle"); pg.wait_for_selector("#grid input")
        pg.click("#addRow"); pg.wait_for_selector("tr.task")

        def run(label, selector, cases):
            nonlocal ok
            for raw, want in cases:
                pg.fill(selector, raw); pg.keyboard.press("Tab"); pg.wait_for_timeout(120)
                got = pg.locator(selector).input_value()
                good = got == want; ok = ok and good
                print(("OK   " if good else "FEHL ") + f"{label}: {raw!r} -> {got!r}" + ("" if good else f" (erwartet {want!r})"))

        run("Beginn", 'input[data-day="2026-11-05"][data-field="beginn"]', CASES_CLOCK)
        run("Ende", 'input[data-day="2026-11-05"][data-field="ende"]', CASES_CLOCK[:3])
        run("Aufgabe", 'input[data-row][data-iso="2026-11-05"]', CASES_DUR)
        run("Pause", 'input[data-day="2026-11-05"][data-field="pause"]', CASES_PAUSE)

        # Rechenergebnis aus normalisierten Eingaben: 8:30-17:00, 175 -> 1:45 verteilt
        pg.fill('input[data-day="2026-11-06"][data-field="beginn"]', "830"); pg.keyboard.press("Tab")
        pg.fill('input[data-day="2026-11-06"][data-field="ende"]', "17"); pg.keyboard.press("Tab")
        pg.fill('input[data-row][data-iso="2026-11-06"]', "175"); pg.keyboard.press("Tab"); pg.wait_for_timeout(900)
        v = pg.locator('td[data-f="verteilt"][data-iso="2026-11-06"]').inner_text()
        good = v == "1:45"; ok = ok and good
        print(("OK   " if good else "FEHL ") + f"175 wird als 1:45 verteilt (ist {v!r})")
        print("JS-Fehler:", errs or "keine"); ok = ok and not errs
        b.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
