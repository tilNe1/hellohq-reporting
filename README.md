# hellohq-reporting

Lokale **Monatsübersicht für die Zeiterfassung** mit Übertragung nach [helloHQ](https://www.hellohq.io): Arbeitszeiten für den ganzen Monat im Raster erfassen, auf Aufgaben verteilen, Pausen automatisch nach ArbZG berechnen und die Reportings per Knopfdruck in HQ eintragen.

Die Oberfläche folgt dem Aufbau klassischer Monatsraster (Tage als Spalten, oben Beginn/Ende/Pause und Summen, unten die Aufgaben) und läuft als kleine lokale Web-Anwendung.

> **Hinweis:** Inoffizielles Hobby-/Werkzeugprojekt, nicht mit helloHQ verbunden. Die Anbindung steuert die Weboberfläche von HQ per Browser-Automatisierung, weil dafür kein API-Token zur Verfügung stand. Prüfe vor dem Einsatz, ob automatisiertes Anmelden in deinem Unternehmen erlaubt ist. Nutzung auf eigene Verantwortung.

## Funktionen

- **Monatsraster** mit Monatswechsel und allen Tagen, Wochenenden und freien Tagen farblich abgesetzt
- **Schnelle Eingabe:** `830` wird `8:30`, `17` wird `17:00`, `175` wird `1,75`, `05` wird `0,5`; Enter springt eine Zeile tiefer
- **Automatische Pause nach ArbZG §4** (über 6 h: 30 min, über 9 h: 45 min) oder nach eigener Vorgabe (z. B. 1 h um 12:00); manuelle Pause überschreibt, Unterschreiten des Gesetzes wird gewarnt
- **Verteilung** der Tagesarbeitszeit auf Aufgaben mit Anzeige „Noch zu verteilende Zeit“
- **Gerundete Arbeitszeit, Soll und Überstunden** (Sollzeit pro Arbeitstag, Rundung und freie Tage/Wochentage einstellbar)
- **Notizen ohne Umweg:** Text hinter die Zeit tippen (`1,75 Sprint-Review`), `Alt`+`N` oder Doppelklick für ein Notizfeld, Standardnotiz pro Aufgabe, Tagesnotiz
- **Projekt- und Aufgabenauswahl** aus den Daten deiner HQ-Instanz
- **Import:** „Diesen Monat aus HQ importieren“ zeigt bestehende Reportings im Raster
- **Übertragung:** „Übertrage in HQ“ liest den Monat frisch ein, gleicht ab und überträgt nur **neue oder geänderte** Einträge; Probelauf und Bestätigung vor dem Speichern, **gelöscht wird nie etwas**
- **Läuft unter Windows, macOS und Linux**; geführte Installation mit Abfrage der Standardwerte

## Schnellstart

Voraussetzung: **Python 3.10 oder neuer**.

| System | Installieren | Starten |
|---|---|---|
| Windows | Doppelklick `install.bat` | Doppelklick `start.bat` |
| macOS / Linux | `./install.sh` | `./start.sh` |
| überall | `python install.py` | `python start.py` |

Das Installationsprogramm richtet eine virtuelle Umgebung und den Browser ein, fragt die Standardwerte ab (Sollzeit, Rundung, typische Pause, freie Tage, HQ-Adresse), wartet auf das Speichern der Zugangsdaten und prüft die Anmeldung. Details und Hinweise: [INSTALL.md](INSTALL.md).

Danach öffnet sich `http://127.0.0.1:8765` im Browser.

## Bedienung

| Eingabe | Beispiele | Ergebnis |
|---|---|---|
| Uhrzeit (Beginn, Ende) | `830`, `17`, `1630`, `9.15` | `8:30`, `17:00`, `16:30`, `9:15` |
| Stunden bei Aufgaben | `175`, `05`, `1.75`, `1:45`, `2h 30m` | `1,75`, `0,5`, `1,75`, `1:45`, `2h 30m` |
| Stunden mit Notiz | `1,75 Sprint-Review` | Zeit `1,75`, Notiz „Sprint-Review“ |
| Pause | `30`, `45`, `1:00`, `1,5` | reine Zahl = Minuten, sonst Stunden |

Ziffernfolgen bei Aufgaben lesen sich so: erste Ziffer = ganze Stunden, Rest = Nachkommastellen (`10` ist 1 Stunde, für zehn Stunden `10:00` schreiben). Fehlt „Ende“, wird es aus Beginn, verteilter Zeit und Pause berechnet.

**Freie Tage** (Einstellungen): je Zeile ein Datum (`JJJJ-MM-TT` oder `TT.MM.JJJJ`) oder ein Wochentag (`Freitag`: jeder Freitag ist frei).

### Rechnung

```
Arbeitszeit (gerundet) = Ende − Beginn − Pause, auf die eingestellte Rundung (Standard 15 min)
Überstunden            = Arbeitszeit − Sollzeit   (Mo–Fr; Wochenende und freie Tage ohne Soll)
Noch zu verteilen      = Arbeitszeit − Summe der Aufgaben
```

### Übertragung nach HQ

1. **Übertrage in HQ** liest den Monat aus HQ ein (etwa 30 Sekunden) und zeigt eine Vorschau.
2. Status je Eintrag: `neu` (wird angelegt), `geändert` (wird in HQ bearbeitet, die Vorschau zeigt den Stand in HQ), `unverändert`, `nur in HQ` (bleibt unberührt), `mehrdeutig` (wird übersprungen).
3. Auswahl treffen, **Probelauf** (füllt nur die Dialoge, speichert nichts) oder **In HQ übertragen** (mit Bestätigung).

Ein Tag wird in Reportings zerlegt: pro Projekt/Aufgabe und Tag ein Eintrag, nacheinander ab „Beginn“; die Pause liegt in dem Eintrag, der über den Pausenbeginn läuft. In HQ gilt: Dauer = Zeitspanne inklusive Pause, Arbeitszeit = Dauer − Pause. Aus HQ importierte Tage gelten als „unverändert“, solange du sie nicht änderst. Eine Notiz überschreibt die Beschreibung in HQ nur, wenn sie hier gesetzt ist und abweicht.

## Konfiguration

Zugangsdaten liegen **außerhalb des Projekts** in `~/.config/hellohq/credentials.env` (Windows: `C:\Users\<Name>\.config\hellohq\credentials.env`), nur für den Benutzer lesbar:

```
HQ_URL=https://<deine-firma>.hellohq.io
HQ_USER=...
HQ_PASSWORD=...
```

Einstellungen und Eingaben speichert die Anwendung in `data/state.json` (von Git ausgeschlossen). Das Verzeichnis lässt sich mit der Umgebungsvariable `HQ_DATA_DIR` verlegen.

## Projektstruktur

| Datei | Zweck |
|---|---|
| `core.py` | Rechenkern: Zeiteingaben, Pause nach ArbZG §4, Rundung, Soll/Überstunden, Zerlegung in Reportings (ohne Abhängigkeiten) |
| `server.py`, `static/index.html` | lokaler Server (nur `127.0.0.1`) und Oberfläche (Vanilla-JS) |
| `hq_client.py` | HQ-Zugriff per [Playwright](https://playwright.dev/python/): Monat lesen, Reporting anlegen/bearbeiten |
| `hq_import.py`, `hq_sync.py`, `hq_projects.py` | Monat einlesen, Plan übertragen (Probelauf als Standard), Projekte/Aufgaben lesen |
| `hq_create_reporting.py`, `hq_login_test.py`, `hq_explore_new.py` | einzelnes Reporting, Anmelde-Test, Erkundung |
| `install.py` / `.sh` / `.bat`, `start.py` / `.sh` / `.bat`, `setup_config.py`, `env.py` | Installation und Start auf allen Systemen |
| `test_core.py`, `test_plan.py`, `smoke_ui.py`, `smoke_norm.py` | Tests |

## Tests

```
python -m unittest test_core test_plan      # Rechenkern und Abgleich mit HQ-Daten
```

Die Rauchtests der Oberfläche (`smoke_ui.py`, `smoke_norm.py`) laufen gegen einen laufenden Server mit Testdaten:

```
HQ_DATA_DIR=/tmp/hqtest python server.py &   # in einem leeren Datenverzeichnis starten
python smoke_ui.py && python smoke_norm.py
```

## Sicherheit und Datenschutz

- Der Server hört **nur auf `127.0.0.1`**, prüft den Host-Header und verlangt JSON bei Schreibzugriffen. Er hat keine Anmeldung, weil niemand sonst herankommt, und kann in HQ buchen. Gib ihn deshalb nicht im Netzwerk frei.
- Das Passwort steht nur in der lokalen Zugangsdatei, wird nie ausgegeben oder geloggt und nicht ins Projekt geschrieben.
- Es gibt keine Telemetrie. `data/`, `out/` (Screenshots der Browser-Automatisierung) und `*.env` sind in `.gitignore`.
- Schreibende Zugriffe auf HQ passieren nur nach ausdrücklicher Bestätigung; die Anwendung löscht nie Einträge.

## Bekannte Grenzen

- **Browser-Automatisierung:** Ändert HQ seine Oberfläche, können Auswahlfelder, Dialoge oder die Tabellenerkennung brechen.
- **Pausenrecht:** umgesetzt ist das deutsche Arbeitszeitgesetz (§ 4 ArbZG); Feiertage sind manuell einzutragen.
- **Plattformen:** Linux/WSL ist getestet; Windows und macOS sind vorgesehen, aber nicht ausführlich geprüft.
- **iOS/iPadOS:** nicht unterstützt (kein Python und Browser für die Anbindung).
- Sprache der Oberfläche: Deutsch.

## Lizenz

Noch nicht festgelegt. Vor einer Veröffentlichung eine `LICENSE`-Datei ergänzen (z. B. MIT).
