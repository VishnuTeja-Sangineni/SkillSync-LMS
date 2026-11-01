@echo off
title SkillSync LMS Launcher
cd /d "%~dp0"

echo =======================================================
echo          Starting SkillSync LMS...
echo =======================================================
echo.
echo Opening your browser to http://localhost:8000 ...
echo (Leave this black window open while using the platform)
echo.

start "" http://localhost:8000

.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
