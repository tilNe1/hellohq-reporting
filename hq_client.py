"""Zugriff auf helloHQ per Browser-Automatisierung: Monat einlesen (lesend).

Der Zeitraum-Filter in HQ wird im Benutzerprofil gemerkt. read_month() merkt sich den vorherigen Zeitraum
und stellt ihn am Ende wieder her.
"""
import re
from contextlib import contextmanager

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from hq_explore_new import login
from hq_login_test import load_credentials, proxy_from_env

MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
RANGE_INPUT = 'input[placeholder="Zeitraum auswählen"]'


@contextmanager
def hq_session(headless=True):
    """Meldet sich an und liefert die Seite 'Reportings'."""
    user, password = load_credentials()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(proxy=proxy_from_env(), headless=headless)
        page = browser.new_context(locale="de-DE", viewport={"width": 1600, "height": 1100}).new_page()
        login(page, user, password)
        page.wait_for_timeout(1500)
        try:
            yield page
        finally:
            browser.close()


def current_range(page):
    return page.locator(RANGE_INPUT).first.input_value()


def _open_picker(page):
    page.locator(f"span.e-input-group:has({RANGE_INPUT}) .e-input-group-icon").first.click()
    page.locator(".e-daterangepicker.e-popup-open").first.wait_for(timeout=10_000)
    page.wait_for_timeout(400)


def _title(page):
    return " ".join(page.locator(".e-left-calendar .e-title").first.inner_text().split())


def _goto_month(page, year, month):
    """Linken Kalender auf den Monat bringen (Titel z. B. 'November 2026')."""
    want = f"{MONTHS[month - 1]} {year}"
    for _ in range(60):
        title = _title(page)
        if title == want:
            return
        m = re.match(r"(\D+)\s+(\d{4})", title)
        cur = (int(m.group(2)), MONTHS.index(m.group(1).strip()) + 1) if m and m.group(1).strip() in MONTHS else None
        if cur is None:
            raise RuntimeError(f"Kalendertitel nicht lesbar: {title!r}")
        page.locator(".e-left-calendar .e-prev" if cur > (year, month) else ".e-left-calendar .e-next").first.click()
        page.wait_for_timeout(200)
    raise RuntimeError(f"Monat {want} nicht erreicht")


def _click_day(page, day):
    cells = page.locator(".e-left-calendar td.e-cell:not(.e-other-month):not(.e-disabled)")
    cells.filter(has_text=re.compile(rf"^\s*{day}\s*$")).first.click()
    page.wait_for_timeout(250)


def set_range(page, y1, m1, d1, y2, m2, d2):
    """Setzt den Zeitraum im Kalender-Popup (Start und Ende im selben Monat)."""
    assert (y1, m1) == (y2, m2), "set_range: Start und Ende müssen im selben Monat liegen"
    _open_picker(page)
    _goto_month(page, y1, m1)
    _click_day(page, d1)
    _click_day(page, d2)
    page.get_by_role("button", name="Anwenden").first.click()
    page.wait_for_timeout(2500)


def _parse_dt(text):
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})\s+(\d{1,2}):(\d{2})", text.strip())
    if not m:
        return None
    d, mo, y, h, mi = map(int, m.groups())
    return {"date": f"20{y:02d}-{mo:02d}-{d:02d}", "time": h * 60 + mi}


def _dec(text):
    try:
        return round(float(text.replace(",", ".")) * 60)
    except ValueError:
        return None


def read_table(page):
    """Alle Zeilen der Reporting-Tabelle (alle Seiten) als Liste von Einträgen."""
    out = []
    for _page in range(40):
        page.wait_for_timeout(800)
        for row in page.locator(".e-grid tr.e-row:visible").all():
            c = [" ".join(t.split()) for t in row.locator("td").all_inner_texts()]
            if len(c) < 15:
                continue
            s, e = _parse_dt(c[7]), _parse_dt(c[9])
            if not s or not e:
                continue
            out.append({
                "project": c[3], "task": c[4], "description": c[5],
                "date": s["date"], "start": s["time"], "end_date": e["date"], "end": e["time"],
                "arbeit_min": _dec(c[12]), "dauer_min": _dec(c[13]), "pause_min": _dec(c[14]), "arbeit_text": c[11],
            })
        nxt = page.locator(".e-pager .e-nextpage:not(.e-disable)")
        if nxt.count() == 0 or not nxt.first.is_visible():
            break
        nxt.first.click()
    return out


def read_month(page, year, month):
    """Liest alle Reportings eines Monats. Stellt danach den vorherigen Zeitraum wieder her."""
    import calendar
    before = current_range(page)
    try:
        set_range(page, year, month, 1, year, month, calendar.monthrange(year, month)[1])
        shown = current_range(page)
        entries = read_table(page)
    finally:
        _restore_range(page, before)
    return {"range_shown": shown, "range_before": before, "entries": entries}


def _restore_range(page, text):
    """Stellt den Zeitraum 'TT.MM.JJ - TT.MM.JJ' wieder her (nur im selben Monat möglich, sonst Hinweis)."""
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2}) - (\d{2})\.(\d{2})\.(\d{2})", text.strip())
    if not m:
        return
    d1, mo1, y1, d2, mo2, y2 = map(int, m.groups())
    if (y1, mo1) != (y2, mo2):
        print(f"Hinweis: vorheriger Zeitraum {text} liegt über zwei Monate, nicht wiederhergestellt.")
        return
    try:
        set_range(page, 2000 + y1, mo1, d1, 2000 + y2, mo2, d2)
    except (PWTimeout, RuntimeError) as err:
        print(f"Hinweis: Zeitraum {text} konnte nicht wiederhergestellt werden: {err}")


# ---------- Schreiben: Reporting-Dialog (anlegen / bearbeiten) ----------

def fmt_dur(minutes):
    """Minuten -> '1h 45m', '4h', '45m' (so versteht HQ das Dauer- und Pausenfeld)."""
    h, m = divmod(int(minutes), 60)
    return " ".join(x for x in (f"{h}h" if h else "", f"{m}m" if m else "") if x) or "0m"


def _norm(s):
    return " ".join(s.lower().replace(" - ", " ").split())


def _set_text(box, value):
    box.click()
    box.press("Control+A")
    box.type(value, delay=30)
    box.press("Tab")


def _choose(page, placeholder, wanted, label):
    """Dropdown im Dialog öffnen und den Eintrag wählen, der `wanted` enthält (Projekt: Syncfusion-Popup,
    Aufgabe: eigene Liste, Einträge enden auf '(Ist/Soll h)')."""
    field = page.locator(f"span[role=combobox]:has(input[placeholder='{placeholder}'])")
    if field.count() == 0:
        field = page.get_by_placeholder(placeholder, exact=True)
    field.first.click()
    page.wait_for_timeout(2000)
    items = page.locator(".e-popup-open:visible").last.locator("li:visible")
    texts = [" ".join(t.split()) for t in items.all_inner_texts()]
    if texts:
        hits = [i for i, t in enumerate(texts) if _norm(wanted) in _norm(t)]
        if len(hits) != 1:
            raise RuntimeError(f"{label}: '{wanted}' nicht eindeutig ({len(hits)} Treffer unter {len(texts)})")
        items.nth(hits[0]).click()
    else:
        loc = page.get_by_text(re.compile(re.escape(wanted) + r"\s*\(\d"))
        if loc.count() != 1:
            raise RuntimeError(f"{label}: '{wanted}' nicht eindeutig ({loc.count()} Treffer)")
        loc.first.click()
    page.wait_for_timeout(600)


def open_new_dialog(page):
    page.locator('div.primary-icon-add[title="Neu"]:visible').first.click()
    page.get_by_text("Neues Reporting").first.wait_for(timeout=15_000)
    page.wait_for_timeout(1000)


def fill_dialog(page, e):
    """Füllt Zeitfelder und Beschreibung. e: date 'JJJJ-MM-TT', start (Min), dauer (Min, inkl. Pause), pause (Min), note."""
    y, mo, d = e["date"].split("-")
    page.get_by_text("Start + Dauer", exact=True).first.click()
    page.wait_for_timeout(500)
    _set_text(page.locator("input[aria-label=datetimepicker]:visible").nth(0), f"{d}.{mo}.{y} {e['start'] // 60:02d}:{e['start'] % 60:02d}")
    boxes = page.locator("input[aria-label=textbox]:visible")
    _set_text(boxes.nth(boxes.count() - 2), fmt_dur(e["dauer"]))
    _set_text(boxes.nth(boxes.count() - 1), fmt_dur(e["pause"]) if e["pause"] else "0m")
    if e.get("note") is not None:
        area = page.locator("textarea:visible").first
        area.fill(e["note"])
    page.wait_for_timeout(600)


def read_dialog(page):
    """Liest die Zeitfelder des offenen Dialogs zurück (zur Kontrolle)."""
    boxes = page.locator("input[aria-label=textbox]:visible")
    dt = page.locator("input[aria-label=datetimepicker]:visible")
    return {"start": dt.nth(0).input_value(), "ende": dt.nth(1).input_value(),
            "dauer": boxes.nth(boxes.count() - 2).input_value(), "pause": boxes.nth(boxes.count() - 1).input_value()}


def _finish_dialog(page, save):
    if save:
        page.get_by_role("button", name="Speichern").first.click()
        page.wait_for_timeout(3000)
    else:
        page.get_by_role("button", name="Abbrechen").first.click()
        page.wait_for_timeout(800)


def create_entry(page, e, save=False):
    open_new_dialog(page)
    _choose(page, "Projekt auswählen", e["project"], "Projekt")
    page.wait_for_timeout(1200)
    _choose(page, "Aufgabe auswählen", e["task"], "Aufgabe")
    fill_dialog(page, e)
    shown = read_dialog(page)
    _finish_dialog(page, save)
    return shown


def edit_entry(page, old, e, save=False):
    """Öffnet den bestehenden Eintrag (Zeile mit Datum, Start und Aufgabe von `old`) über ⋮ > Bearbeiten."""
    y, mo, d = old["date"].split("-")
    stamp = f"{d}.{mo}.{y[2:]} {old['start'] // 60:02d}:{old['start'] % 60:02d}"
    rows = page.locator(".e-grid tr.e-row:visible")
    for i in range(rows.count()):
        cells = [" ".join(t.split()) for t in rows.nth(i).locator("td").all_inner_texts()]
        if len(cells) > 9 and cells[7].startswith(stamp[:8]) and cells[7].endswith(stamp[9:]) and cells[4] == old["task"]:
            rows.nth(i).locator("td >> text=more_vert").first.click()
            page.wait_for_timeout(700)
            page.get_by_text("Bearbeiten", exact=True).first.click()
            page.get_by_role("button", name="Speichern").first.wait_for(timeout=15_000)
            page.wait_for_timeout(1000)
            fill_dialog(page, e)
            shown = read_dialog(page)
            _finish_dialog(page, save)
            return shown
    raise RuntimeError(f"Zeile nicht gefunden: {stamp} {old['task']}")
