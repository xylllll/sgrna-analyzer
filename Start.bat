@echo off
cd /d "%~dp0"
title sgRNA Analyzer v2.0

echo ========================================
echo   sgRNA Analyzer v2.0 (Windows Native)
echo ========================================
echo.

rem ---------- Check Python ----------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo.
    echo Please install Python 3.9+:
    echo   1. Open https://www.python.org/downloads/
    echo   2. Download Windows 64-bit installer
    echo   3. CHECK "Add Python to PATH" during install
    echo.
    pause
    exit /b 1
)

rem ---------- Check dependencies ----------
python -c "import numpy, matplotlib, jinja2" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run - installing dependencies...
    echo        (using Tsinghua mirror, may take a few minutes)
    echo.
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple matplotlib numpy jinja2
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Dependency install failed! Check network and retry.
        pause
        exit /b 1
    )
    echo.
    echo [DONE] Dependencies installed successfully!
    echo.
)

rem ---------- Launch GUI ----------
echo Starting sgRNA Analyzer v2.0...
echo (This window closes when the app exits)
echo.

python "%~dp0sgRNA_Analyzer.pyw"
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   Program exited with error code: %errorlevel%
    echo ========================================
    echo.
    echo Possible causes:
    echo   - Missing FLASH/BLAST tools (needed for analysis)
    echo   - Other runtime error
    echo.
    pause
)
