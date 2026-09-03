@echo off
cd /d "%~dp0"
python "%~dp0sgRNA_Analyzer.pyw" 2>nul
if %errorlevel% neq 0 (
    python3 "%~dp0sgRNA_Analyzer.pyw" 2>nul
)
if %errorlevel% neq 0 (
    echo Python not found.
    echo Install from https://www.python.org/downloads/
    echo Make sure to check [Add Python to PATH] during install.
    pause
)
