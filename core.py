"""Rechenkern der Monatsübersicht: Zeiteingaben, Pause nach ArbZG §4, Rundung, Verteilung, HQ-Zerlegung.

Alle Zeiten intern in Minuten (Uhrzeiten: Minuten seit 00:00). Keine Abhängigkeiten.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

DEFAULT_CONFIG = {
    "soll_min": 480,        # Sollzeit pro Arbeitstag (Mo-Fr)
    "round_min": 15,        # Rundung der Arbeitszeit
    "pause_start": None,    # z. B. "12:00"; None = kein Wunsch, Pause nach Gesetz
    "pause_len_min": None,  # z. B. 60
    "free_days": [],        # Feiertage/Urlaub als "JJJJ-MM-TT": ohne Soll
}


# ---------- Eingaben lesen / formatieren ----------

def parse_clock(text):
    """'8:30', '08:30', '830', '8.30', '8' -> Minuten seit 00:00; leer -> None; sonst ValueError."""
    t = (text or "").strip().lower().replace("uhr", "").strip()
    if not t:
        return None
    m = re.fullmatch(r"(\d{1,2})[:.,](\d{2})", t) or re.fullmatch(r"(\d{1,2})(\d{2})", t) or re.fullmatch(r"(\d{1,2})()", t)
    if not m:
        raise ValueError(f"Keine Uhrzeit: {text!r}")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 24 or mi > 59 or (h == 24 and mi):
        raise ValueError(f"Keine Uhrzeit: {text!r}")
    return h * 60 + mi


def parse_duration(text):
    """'1,75', '1.75', '1:45', '1h 45m', '45m', '0,5h' -> Minuten; leer -> None; sonst ValueError.
    Reine Ziffernfolgen sind Stunden mit der ersten Ziffer als ganzen Stunden: '175' = 1,75 h, '05' = 0,5 h, '8' = 8 h."""
    t = (text or "").strip().lower().replace(",", ".")
    if not t:
        return None
    if re.fullmatch(r"\d{2,}", t):
        t = t[0] + "." + t[1:]
    m = re.fullmatch(r"(\d+):(\d{2})", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?", t)
    if m and (m.group(1) or m.group(2)):
        return round(float(m.group(1) or 0) * 60) + int(m.group(2) or 0)
    m = re.fullmatch(r"\d+(?:\.\d+)?", t)
    if m:
        return round(float(t) * 60)
    raise ValueError(f"Keine Dauer: {text!r}")


def parse_pause(text):
    """Wie parse_duration, aber eine reine Zahl sind Minuten ('30' = 30 min, '45' = 45 min)."""
    t = (text or "").strip()
    if re.fullmatch(r"\d+", t):
        return int(t)
    return parse_duration(t)


def split_note(text):
    """Zelleneingabe '1,75 Sprint-Review' -> ('1,75', 'Sprint-Review'). Die Dauer steht immer zuerst."""
    t = (text or "").strip()
    m = re.match(r"^(\d+(?:[.,]\d+)?(?::\d{2})?(?:\s*h(?:\s*\d+\s*m(?:in)?)?|\s*m(?:in)?)?)(?:\s+(.*))?$", t, re.I)
    if not m:
        return t, ""
    return m.group(1).strip(), (m.group(2) or "").strip()


def fmt_clock(minutes):
    return "" if minutes is None else f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_hm(minutes):
    """Dauer als H:MM (negativ mit Vorzeichen); 0/None -> ''."""
    if not minutes:
        return ""
    sign = "-" if minutes < 0 else ""
    m = abs(minutes)
    return f"{sign}{m // 60}:{m % 60:02d}"


# ---------- Pause nach ArbZG §4 ----------

def legal_pause(span_min):
    """Mindestpause für eine Anwesenheitsspanne (Beginn bis Ende, inkl. Pause).
    ArbZG §4: Arbeitszeit mehr als 6 h -> 30 min, mehr als 9 h -> 45 min (Arbeitszeit = Spanne minus Pause)."""
    pause = 0
    if span_min > 6 * 60:
        pause = 30
    if span_min - pause > 9 * 60:
        pause = 45
    return pause


def round_to(minutes, step):
    return minutes if step <= 1 else int(round(minutes / step)) * step


WEEKDAY_NAMES = {
    "montag": 0, "mo": 0, "dienstag": 1, "di": 1, "mittwoch": 2, "mi": 2, "donnerstag": 3, "do": 3,
    "freitag": 4, "fr": 4, "samstag": 5, "sa": 5, "sonntag": 6, "so": 6,
}


def free_day_rules(entries):
    """Zerlegt die Liste der freien Tage in (Datumsmenge als ISO, Wochentagsmenge 0=Mo).
    Einträge: 'JJJJ-MM-TT', 'TT.MM.JJJJ' oder ein Wochentag ('Freitag', 'Fr'): dann ist jeder dieser Wochentage frei."""
    dates, weekdays = set(), set()
    for raw in entries or []:
        t = str(raw).strip().lower().rstrip(".")
        if t in WEEKDAY_NAMES:
            weekdays.add(WEEKDAY_NAMES[t])
            continue
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t) or re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
        if m:
            a, b, c = m.groups()
            y, mo, dd = (int(a), int(b), int(c)) if len(a) == 4 else (int(c), int(b), int(a))
            try:
                dates.add(date(y, mo, dd).isoformat())
            except ValueError:
                pass
    return dates, weekdays


def is_workday(d: date, config):
    dates, weekdays = free_day_rules(config.get("free_days"))
    return d.weekday() < 5 and d.weekday() not in weekdays and d.isoformat() not in dates


def effective_pause(beginn, ende, config, manual=None):
    """(pause_dauer, pause_start) für einen Tag. manual = vom Nutzer eingetragene Pause (Minuten) gewinnt,
    darf aber das gesetzliche Minimum nicht unterschreiten (Warnung statt Zwang, siehe day_calc)."""
    if beginn is None or ende is None or ende <= beginn:
        return 0, None
    span = ende - beginn
    legal = legal_pause(span)
    if manual is not None:
        return manual, None
    ps, pl = parse_clock(config.get("pause_start") or ""), config.get("pause_len_min")
    if ps is not None and pl and beginn < ps and ps + pl <= ende:
        return max(pl, legal), ps
    return legal, None


# ---------- Tagesrechnung ----------

def day_calc(day, tasks_min, d: date, config):
    """Berechnet die Zeilen der oberen Hälfte für einen Tag.

    day: {"beginn": min|None, "ende": min|None, "pause_min": int|None (manuell)}
    tasks_min: Liste der verteilten Minuten je Aufgabe (nur >0).
    """
    cfg = {**DEFAULT_CONFIG, **config}
    beginn, ende = day.get("beginn"), day.get("ende")
    verteilt = sum(tasks_min)
    warnings = []

    # Ende fehlt: aus Beginn + verteilter Zeit + Pause ableiten (Pause iterativ, weil sie von der Spanne abhängt)
    ende_derived = False
    if beginn is not None and ende is None and verteilt:
        span = verteilt
        for _ in range(3):
            pause, _ps = effective_pause(beginn, beginn + span, cfg, day.get("pause_min"))
            span = verteilt + pause
        ende, ende_derived = beginn + span, True

    pause, pause_start = effective_pause(beginn, ende, cfg, day.get("pause_min"))
    if beginn is not None and ende is not None:
        if ende <= beginn:
            warnings.append("Ende liegt nicht nach dem Beginn")
        if day.get("pause_min") is not None and pause < legal_pause(ende - beginn):
            warnings.append(f"Pause kürzer als gesetzlich ({legal_pause(ende - beginn)} min, ArbZG §4)")
        if ende - beginn - pause > 10 * 60:
            warnings.append("Mehr als 10 Stunden Arbeitszeit (ArbZG §3)")

    brutto = (ende - beginn - pause) if beginn is not None and ende is not None and ende > beginn else 0
    gerundet = round_to(max(brutto, 0), cfg["round_min"])
    soll = cfg["soll_min"] if is_workday(d, cfg) else 0
    ueber = (gerundet - soll) if (gerundet or soll) else 0
    rest = gerundet - verteilt
    if verteilt and abs(rest) >= cfg["round_min"] > 0 and rest < 0:
        warnings.append("Mehr verteilt als Arbeitszeit")
    return {
        "soll": soll, "beginn": beginn, "ende": ende, "ende_derived": ende_derived,
        "pause": pause, "pause_start": pause_start,
        "arbeit": gerundet, "ueber": ueber if (gerundet or day.get("beginn") is not None) else 0,
        "verteilt": verteilt, "rest": rest if gerundet or verteilt else 0, "warnings": warnings,
    }


# ---------- Zerlegung in HQ-Reportings ----------

def schedule_day(day_res, entries, config):
    """Zerlegt einen Tag in HQ-Reportings, nacheinander ab Beginn.

    entries: [{"project","task","min","note"}] in Anzeigereihenfolge.
    Gibt [{"project","task","note","start","end","dauer","pause"}] zurück (Zeiten in Minuten).
    Die Pause wandert in den Eintrag, der über den Pausenbeginn läuft; HQ-Annahme: Dauer = Ende - Start
    (inkl. Pause), Arbeitszeit = Dauer - Pause. Ohne Pausenwunsch wird die Pause nach 4 h Arbeit gelegt.
    """
    beginn = day_res["beginn"]
    pause = day_res["pause"]
    if beginn is None or not entries:
        return []
    pause_start = day_res["pause_start"]
    if pause and pause_start is None:
        pause_start = beginn + 4 * 60
    out, cursor, pause_done = [], beginn, not pause
    for e in entries:
        if e["min"] <= 0:
            continue
        start, net = cursor, e["min"]
        p = 0
        if not pause_done:
            if start >= pause_start:           # Eintrag beginnt erst nach dem Pausenbeginn: Pause davor
                start += pause
                pause_done = True
            elif start + net > pause_start:    # Pause fällt in diesen Eintrag
                p, pause_done = pause, True
        end = start + net + p
        out.append({**{k: e[k] for k in ("project", "task", "note")}, "start": start, "end": end,
                    "dauer": end - start, "pause": p})
        cursor = end
    return out


# ---------- Monat ----------

def month_days(year, month):
    return [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]
