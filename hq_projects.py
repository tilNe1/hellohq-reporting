#!/usr/bin/env python3
"""Liest Projekte und Aufgaben aus dem Dialog 'Neues Reporting' (rein lesend, speichert nichts)
und schreibt sie nach data/projects.json."""
import json
import re
from datetime import datetime

from playwright.sync_api import sync_playwright

from hq_explore_new import login
from hq_login_test import OUT, load_credentials, proxy_from_env

DATA = OUT.parent / "data"
TASK_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<ist>[\d.,]+)/(?P<soll>[\d.,]+)h\)\s*$")


def open_dropdown(page, placeholder):
    field = page.locator(f"span[role=combobox]:has(input[placeholder='{placeholder}'])")
    if field.count() == 0:  # die Aufgaben-Auswahl ist kein Syncfusion-Combobox-Wrapper
        field = page.get_by_placeholder(placeholder, exact=True)
    field.first.click()
    page.wait_for_timeout(1500)


def main():
    DATA.mkdir(exist_ok=True)
    user, password = load_credentials()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(proxy=proxy_from_env())
        page = browser.new_context(locale="de-DE", viewport={"width": 1400, "height": 1000}).new_page()
        login(page, user, password)
        def open_dialog():
            page.locator('div.primary-icon-add[title="Neu"]:visible').first.click()
            page.get_by_text("Neues Reporting").first.wait_for(timeout=15_000)
            page.wait_for_timeout(1000)

        open_dialog()
        open_dropdown(page, "Projekt auswählen")
        popup = page.locator(".e-popup-open:visible").last
        projects = [" ".join(t.split()) for t in popup.locator("li:visible").all_inner_texts()]
        print(f"{len(projects)} Projekte:")
        page.get_by_role("button", name="Abbrechen").first.click()
        page.wait_for_timeout(800)

        result = []
        for i, name in enumerate(projects):
            print(f"  - {name}")
            open_dialog()  # pro Projekt ein frischer Dialog
            open_dropdown(page, "Projekt auswählen")
            page.locator(".e-popup-open:visible").last.locator("li:visible").nth(i).click()
            page.wait_for_timeout(1500)
            open_dropdown(page, "Aufgabe auswählen")
            tasks = []
            for el in page.get_by_text(re.compile(r"\([\d.,]+/[\d.,]+h\)\s*$")).all():
                if not el.is_visible():
                    continue
                txt = " ".join(el.inner_text().split())
                m = TASK_RE.match(txt)
                if m and m["name"] not in [t["name"] for t in tasks]:
                    tasks.append({"name": m["name"], "ist": m["ist"], "soll": m["soll"]})
            print(f"      {len(tasks)} Aufgaben: " + "; ".join(t["name"] for t in tasks))
            result.append({"project": name, "tasks": tasks})
            page.keyboard.press("Escape")
            page.wait_for_timeout(700)
            if page.get_by_text("Neues Reporting").count() and page.get_by_text("Neues Reporting").first.is_visible():
                page.get_by_role("button", name="Abbrechen").first.click()  # Escape schließt meist schon den ganzen Dialog
                page.wait_for_timeout(800)

        (DATA / "projects.json").write_text(
            json.dumps({"fetched": datetime.now().isoformat(timespec="seconds"), "projects": result}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nGespeichert: {DATA / 'projects.json'}")
        browser.close()


if __name__ == "__main__":
    main()
