@echo off
rem Windows: startet das Installationsprogramm (install.py). Optionen: --skip-hq, --yes
cd /d "%~dp0"
where py >nul 2>nul && (py -3 install.py %* & goto :end)
where python >nul 2>nul && (python install.py %* & goto :end)
echo Python 3.10 oder neuer fehlt. Bitte von https://www.python.org/downloads/ installieren (Option "Add python.exe to PATH" aktivieren).
:end
pause
