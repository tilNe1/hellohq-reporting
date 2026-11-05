#!/usr/bin/env python3
"""Login-Test für helloHQ per Playwright.

  hq_login_test.py --recon   Seite öffnen, Formularfelder auflisten, Screenshot (ohne Zugangsdaten)
  hq_login_test.py           Anmelden, "My Reportings" öffnen, Screenshot (erstellt nichts)

Zugangsdaten stehen in ~/.config/hellohq/credentials.env (HQ_USER, HQ_PASSWORD).
Sie werden nie ausgegeben oder geloggt.
"""
import argparse
import os
import sys

import env  # noqa: F401  (Browser-Pfad, UTF-8; muss vor playwright kommen)
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

CRED_FILE = Path.home() / ".config" / "hellohq" / "credentials.env"


def _hq_base():
    """HQ-Adresse: Umgebungsvariable HQ_URL, sonst Zeile HQ_URL in credentials.env (z. B. https://firma.hellohq.io)."""
    base = os.environ.get("HQ_URL", "")
    if not base:
        try:
            for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("HQ_URL="):
                    base = line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    if not base:
        sys.exit(f"HQ-Adresse fehlt: HQ_URL=https://<firma>.hellohq.io in {CRED_FILE} eintragen (oder install.py ausführen).")
    return base.rstrip("/")


URL = _hq_base() + "/my/myreportings"
OUT = Path(__file__).resolve().parent / "out"


def load_credentials():
    user = password = ""
    for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if key.strip() == "HQ_USER":
            user = value
        elif key.strip() == "HQ_PASSWORD":
            password = value
    if not user or not password:
        sys.exit(f"HQ_USER und HQ_PASSWORD fehlen in {CRED_FILE}")
    return user, password


def proxy_from_env():
    """Chromium liest Proxy-Zugangsdaten nicht aus HTTPS_PROXY; Playwright braucht sie getrennt.
    Ohne Proxy in der Umgebung wird direkt verbunden. Die Werte werden nie ausgegeben."""
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not raw:
        return None
    u = urlsplit(raw)
    proxy = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        proxy["username"] = unquote(u.username)
        proxy["password"] = unquote(u.password or "")
    return proxy


def describe_fields(page):
    print("\nFormularfelder (sichtbar):")
    for el in page.locator("input:visible, textarea:visible, select:visible").all():
        attrs = {a: el.get_attribute(a) for a in ("type", "name", "id", "placeholder", "aria-label", "autocomplete")}
        print("  -", {k: v for k, v in attrs.items() if v})
    print("Buttons (sichtbar):")
    for el in page.locator("button:visible, [role=button]:visible").all()[:15]:
        text = " ".join(el.inner_text().split())
        if text:
            print("  -", text[:60])


def wait_rendered(page, seconds=25):
    """Blazor Server baut die Oberfläche erst nach der SignalR-Verbindung auf: auf Text im Body warten."""
    try:
        page.wait_for_function("document.body && document.body.innerText.trim().length > 20", timeout=seconds * 1000)
    except PWTimeout:
        print("  (Seite blieb leer: SignalR-Verbindung oder Rendering fehlt)")
    page.wait_for_timeout(1500)


def summary(page, label):
    wait_rendered(page)
    print(f"\n[{label}] URL: {page.url}")
    body = " ".join(page.inner_text("body").split()) if page.locator("body").count() else ""
    print(f"[{label}] Text ({len(body)} Zeichen): {body[:400]!r}")
    print(f"[{label}] Titel: {page.title()!r}")
    for sel in ("h1", "h2"):
        texts = [" ".join(t.split()) for t in page.locator(f"{sel}:visible").all_inner_texts() if t.strip()]
        if texts:
            print(f"[{label}] {sel}: {texts[:5]}")
    alerts = [" ".join(t.split()) for t in page.locator("[role=alert]:visible").all_inner_texts() if t.strip()]
    if alerts:
        print(f"[{label}] Hinweise: {alerts[:3]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recon", action="store_true", help="nur Login-Seite ansehen, ohne Zugangsdaten")
    parser.add_argument("--headed", action="store_true", help="Browser sichtbar starten")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    creds = None if args.recon else load_credentials()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, proxy=proxy_from_env())
        page = browser.new_context(locale="de-DE", viewport={"width": 1280, "height": 900}).new_page()
        failed_hosts = {}

        def on_failed(request):
            host = request.url.split("/")[2] if "//" in request.url else request.url
            failed_hosts[host] = failed_hosts.get(host, 0) + 1
            print(f"  [fehlgeschlagen] {request.method} {request.url[:120]} -> {request.failure}")

        page.on("requestfailed", on_failed)
        page.on("console", lambda m: m.type in ("error", "warning") and print(f"  [console {m.type}] {m.text[:160]}"))
        page.on("pageerror", lambda e: print(f"  [seitenfehler] {str(e)[:160]}"))
        page.goto(URL, wait_until="networkidle", timeout=60_000)
        summary(page, "Start")
        if failed_hosts:
            print("\nFehlgeschlagene Anfragen nach Host (blockiert oder nicht erreichbar):")
            for host, n in sorted(failed_hosts.items(), key=lambda kv: -kv[1]):
                print(f"  - {host}: {n}")
        body = " ".join(page.inner_text("body").split()) if page.locator("body").count() else ""
        print(f"\nSeitentext ({len(body)} Zeichen): {body[:300]!r}")
        try:
            page.screenshot(path=str(OUT / "01_start.png"), timeout=15_000)
        except PWTimeout:
            print("Screenshot nicht möglich (Timeout), weiter ohne.")

        if args.recon:
            describe_fields(page)
            print(f"\nScreenshot: {OUT / '01_start.png'}")
            browser.close()
            return

        user, password = creds
        pw_field = page.locator("input[type=password]:visible").first
        if pw_field.count() == 0:
            print("\nKein Passwortfeld sichtbar: vermutlich schon angemeldet oder mehrstufiges Login.")
        else:
            user_field = page.locator(
                "input[type=email]:visible, input[name*=user i]:visible, input[name*=mail i]:visible, "
                "input[id*=user i]:visible, input[id*=mail i]:visible, input[type=text]:visible"
            ).first
            user_field.fill(user)
            pw_field.fill(password)
            pw_field.press("Enter")
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
                page.wait_for_selector("input[type=password]", state="detached", timeout=20_000)
            except PWTimeout:
                print("\nPasswortfeld ist nach dem Absenden noch da: Login vermutlich nicht erfolgreich.")

        page.goto(URL, wait_until="networkidle", timeout=60_000)
        summary(page, "Reportings")
        page.screenshot(path=str(OUT / "02_reportings.png"), full_page=True)
        print(f"\nScreenshots: {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
