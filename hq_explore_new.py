#!/usr/bin/env python3
"""Erkundung: Anmelden, 'Reportings' öffnen, grünes '+' anklicken, Formular beschreiben.
Speichert NICHTS: schließt den Dialog danach mit Escape. Zugangsdaten werden nie ausgegeben."""
import sys

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from hq_login_test import OUT, URL, load_credentials, proxy_from_env, wait_rendered


def login(page, user, password):
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    wait_rendered(page)
    if page.locator("input[type=password]:visible").count():
        page.locator("input[name=username]:visible").first.fill(user)
        page.locator("input[type=password]:visible").first.fill(password)
        page.locator("input[type=password]:visible").first.press("Enter")
        page.wait_for_selector("input[type=password]", state="detached", timeout=30_000)
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    wait_rendered(page)


def add_candidates(page):
    """Alle sichtbaren Elemente mit Icon-Text 'add', mit Position und Farbe."""
    return page.evaluate(
        """() => [...document.querySelectorAll('button, a, span, i, div')]
          .filter(e => e.children.length === 0 && e.innerText && e.innerText.trim() === 'add')
          .map((e, i) => {
            const b = e.closest('button, a, [role=button]') || e;
            const r = b.getBoundingClientRect();
            const cs = getComputedStyle(e), bs = getComputedStyle(b);
            return {i, tag: b.tagName, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
                    color: cs.color, bg: bs.backgroundColor, cls: (b.className || '').toString().slice(0, 80),
                    visible: r.width > 0 && r.height > 0};
          })"""
    )


def is_green(rgb):
    try:
        r, g, b = [int(float(x)) for x in rgb[rgb.index("(") + 1 : rgb.index(")")].split(",")[:3]]
    except ValueError:
        return False
    return g > r + 20 and g > b + 20


def main():
    OUT.mkdir(exist_ok=True)
    user, password = load_credentials()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(proxy=proxy_from_env())
        page = browser.new_context(locale="de-DE", viewport={"width": 1400, "height": 900}).new_page()
        login(page, user, password)

        plus = page.locator('div.primary-icon-add[title="Neu"]:visible')
        print(f"Grünes '+' (div.primary-icon-add, Titel 'Neu') gefunden: {plus.count()}")
        if plus.count() == 0:
            browser.close()
            sys.exit(1)
        plus.first.click()
        page.wait_for_timeout(2500)
        wait_rendered(page)

        print(f"\nURL danach: {page.url}")
        dialogs = page.locator("[role=dialog]:visible, .e-dialog:visible, .modal:visible, .e-popup-open:visible")
        scope = dialogs.first if dialogs.count() else page
        print("Formularbereich:", "Dialog" if dialogs.count() else "ganze Seite")
        print("\nFelder:")
        for el in scope.locator("input:visible, textarea:visible, select:visible").all():
            attrs = {a: el.get_attribute(a) for a in ("type", "name", "id", "placeholder", "aria-label", "value")}
            print("  -", {k: v for k, v in attrs.items() if v})
        print("Beschriftungen/Buttons:")
        text = " | ".join(" ".join(t.split()) for t in scope.locator("label:visible, button:visible, h1:visible, h2:visible, h3:visible").all_inner_texts() if t.strip())
        print("  ", text[:900])
        page.screenshot(path=str(OUT / "03_plus_geklickt.png"), timeout=15_000)
        print(f"\nScreenshot: {OUT / '03_plus_geklickt.png'}")
        page.keyboard.press("Escape")
        browser.close()


if __name__ == "__main__":
    main()
