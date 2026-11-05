#!/usr/bin/env python3
"""Rauchtest der Oberfläche gegen einen laufenden Server (am besten mit HQ_DATA_DIR auf ein Testverzeichnis)."""
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/"


def main():
    errors, ok = [], True
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_context(viewport={"width": 1600, "height": 900}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_selector("#grid input")

        def check(name, cond):
            nonlocal ok
            print(("OK   " if cond else "FEHL ") + name)
            ok = ok and bool(cond)

        month = pg.locator("#monthLabel").inner_text()
        check(f"Monat angezeigt ({month})", "2026" in month)
        check("30 Tage im November", pg.locator("th.dayn").count() == 30)

        # Zeile hinzufügen: erstes Projekt, erste Aufgabe
        pg.click("#addRow")
        pg.wait_for_selector("tr.task")
        check("Aufgabenzeile erscheint", pg.locator("tr.task").count() == 1)

        # Do 05.11. -> Spalte 5; Beginn 8:30, Ende 17:00, Aufgabe 7,5 mit Notiz
        pg.fill('input[data-day="2026-11-05"][data-field="beginn"]', "8:30"); pg.keyboard.press("Tab")
        pg.fill('input[data-day="2026-11-05"][data-field="ende"]', "17:00"); pg.keyboard.press("Tab")
        pg.fill('input[data-row][data-iso="2026-11-05"]', "7,5 Sprint-Review"); pg.keyboard.press("Tab")
        pg.wait_for_timeout(900)
        get = lambda f: pg.locator(f'td[data-f="{f}"][data-iso="2026-11-05"]').inner_text()
        check(f"Arbeitszeit 8:00 (ist {get('arbeit')!r})", get("arbeit") == "8:00")
        check(f"Verteilt 7:30 (ist {get('verteilt')!r})", get("verteilt") == "7:30")
        check(f"Rest 0:30 (ist {get('rest')!r})", get("rest") == "0:30")
        check("Pause automatisch 0:30 als Platzhalter", pg.locator('input[data-day="2026-11-05"][data-field="pause"]').get_attribute("placeholder") == "0:30")
        check("Notiz-Markierung an der Zelle", pg.locator('td.hasnote[data-iso="2026-11-05"]').count() == 1)
        check("Monatssumme Verteilt 7:30", pg.locator('td[data-sum="verteilt"]').inner_text() == "7:30")

        # Notiz per Alt+N
        pg.focus('input[data-row][data-iso="2026-11-05"]')
        pg.keyboard.press("Alt+n")
        check("Notiz-Popover öffnet", pg.locator(".pop textarea").count() == 1)
        pg.fill(".pop textarea", "Neue Notiz"); pg.keyboard.press("Enter"); pg.wait_for_timeout(700)
        check("Popover schließt nach Enter", pg.locator(".pop").count() == 0)
        title = pg.locator('input[data-row][data-iso="2026-11-05"]').get_attribute("title") or ""
        check(f"Notiz im Tooltip ({title!r})", "Neue Notiz" in title)

        # Fehleingabe
        pg.fill('input[data-day="2026-11-06"][data-field="beginn"]', "abc"); pg.keyboard.press("Tab"); pg.wait_for_timeout(700)
        check("Fehleingabe wird markiert", pg.locator('input.bad[data-day="2026-11-06"]').count() == 1)

        # Monatswechsel behält Eingaben
        pg.click("#next"); pg.wait_for_timeout(900)
        check("Dezember geladen", "Dezember" in pg.locator("#monthLabel").inner_text())
        check("Aufgabenzeile wird übernommen", pg.locator("tr.task").count() == 1)
        pg.click("#prev"); pg.wait_for_timeout(900)
        check("Eingabe nach Rückkehr vorhanden", pg.locator('input[data-row][data-iso="2026-11-05"]').input_value().startswith("7"))

        # Vorschau
        pg.click("#syncBtn"); pg.wait_for_selector("#planDlg[open]")
        check("Vorschau listet 1 Eintrag", pg.locator("#planTbl tr").count() == 2)
        pg.screenshot(path="out/08_ui_smoke.png", timeout=15000)
        b.close()
    print("\nJS-Fehler:", errors or "keine")
    return 0 if ok and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
