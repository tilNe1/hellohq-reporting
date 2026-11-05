#!/usr/bin/env bash
# macOS / Linux / WSL: startet die Monatsübersicht und öffnet den Browser.
cd "$(dirname "$0")" || exit 1
PY=".venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
exec "$PY" start.py
