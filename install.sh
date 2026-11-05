#!/usr/bin/env bash
# macOS / Linux / WSL: startet das Installationsprogramm (install.py). Optionen: --skip-hq, --yes
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3 || command -v python)" || { echo "Python 3.10+ fehlt (macOS: brew install python, Ubuntu: sudo apt install python3 python3-venv)"; exit 1; }
exec "$PY" install.py "$@"
