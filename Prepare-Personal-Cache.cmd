@echo off
setlocal
title MARS CACHE - Personal Offline Preparation
echo MARS CACHE - prepare your personal offline library
echo Keep your internet connected until preparation finishes.
echo.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0tools\prepare_personal.py"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Install Python 3 from https://www.python.org/downloads/ and run this again.
        pause
        exit /b 1
    )
    python "%~dp0tools\prepare_personal.py"
)
echo.
pause
