@echo off
rem Windows: startet die Monatsuebersicht und oeffnet den Browser.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" start.py) else (echo Bitte zuerst install.bat ausfuehren. & pause)
