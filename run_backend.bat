@echo off
title RootSearch Backend Launcher
cd /d "c:\Best Projects\FuckenSearch"

echo ===================================================
echo   RootSearch Backend & Cloudflare Tunnel Launcher
echo ===================================================
echo.
echo Starting orchestrator...
"C:\Program Files\Python314\python.exe" launch_backend.py
pause
