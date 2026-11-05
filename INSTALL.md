# Installation auf einem neuen Computer

Läuft unter **Windows, macOS und Linux** (auch WSL). Auf iPhone/iPad läuft die Anwendung nicht selbst (siehe unten).

## 1. Voraussetzung: Python 3.10 oder neuer
| System | Installieren |
|---|---|
| Windows | https://www.python.org/downloads/ (Haken bei „Add python.exe to PATH“ setzen) |
| macOS | `brew install python` oder von python.org |
| Linux | `sudo apt install python3 python3-venv` |

## 2. Projektordner kopieren
Den Ordner `hellohq-reporting` per Git oder ZIP auf den neuen Computer legen. **Nicht mitkopieren** (entstehen neu): `.venv/`, `.browsers/`, `.libs/`, `data/`, `out/`.

## 3. Installieren
| System | Befehl |
|---|---|
| Windows | Doppelklick auf `install.bat` |
| macOS / Linux | `./install.sh` |
| überall | `python install.py` (Optionen: `--skip-hq` ohne HQ-Verbindung, `--yes` Vorgabewerte ohne Rückfragen) |

Das Programm erledigt in 7 Schritten:
1. prüft Python und `venv`
2. legt `.venv` an und installiert die Pakete (`requirements.txt`)
3. lädt den Browser (Chromium, rund 150 MB) in `.browsers/` und prüft, dass er startet. Der Browser gilt nur für das Betriebssystem, auf dem installiert wurde: Wird der Ordner unter Windows und WSL/Linux gemeinsam genutzt, liegen beide Fassungen nebeneinander. Fehlt eine beim Start, lädt die Anwendung sie einmal automatisch nach.
4. Linux: ergänzt fehlende Systembibliotheken (mit `sudo` oder ohne Root nach `.libs/`); Windows und macOS brauchen das nicht
5. **fragt die Standardwerte ab**: Sollzeit, Rundung, typische Pause (Beginn und Länge), freie Tage (Wochentage oder Daten), HQ-Adresse
6. **legt die Zugangsdatei an und wartet, bis du sie gespeichert hast**: `~/.config/hellohq/credentials.env` (Windows: `C:\Users\<Name>\.config\hellohq\credentials.env`). Dort trägst du `HQ_USER=` und `HQ_PASSWORD=` ein. Das Passwort erscheint nie im Terminal. Die Datei ist nur für dich lesbar.
7. testet Rechenkern, Anmeldung bei HQ und liest Projekte und Aufgaben aus HQ ein

Die Installation ist mehrfach ausführbar. Vorhandenes wird erkannt, deine Monatsdaten bleiben erhalten.

## 4. Starten
| System | Befehl |
|---|---|
| Windows | Doppelklick auf `start.bat` |
| macOS / Linux | `./start.sh` |
| überall | `python start.py` |

Der Browser öffnet `http://127.0.0.1:8765`. Beenden mit Strg+C im Terminalfenster.

## Hinweise
- **Nur lokal:** Der Server hört nur auf `127.0.0.1`. Er braucht keine Anmeldung, weil niemand sonst herankommt, und kann in HQ buchen. Deshalb wird er bewusst nicht im Netzwerk freigegeben.
- **iPhone/iPad (iOS):** Dort lassen sich weder Python noch der Browser für die HQ-Anbindung betreiben. Zugriff vom iPhone wäre nur möglich, wenn die Anwendung auf einem Mac, PC oder Server im Heimnetz läuft und dort zusätzlich per Anmeldung geschützt ist. Das ist nicht eingebaut.
- **Firmenrechner:** Der HQ-Zugriff braucht Zugang zu `<firma>.hellohq.io` und seinen Hilfsdiensten (`hq-signalr-production.service.signalr.net`, `cdn.syncfusion.com`, `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `fonts.googleapis.com`). Der Browser nutzt den Proxy aus `HTTPS_PROXY`, wenn er gesetzt ist.
- **Zugangsdaten ändern:** Datei `credentials.env` bearbeiten und speichern. Eine neue HQ-Adresse steht dort in der Zeile `HQ_URL=`.
