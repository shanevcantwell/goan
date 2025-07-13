@echo off
:: Script to run the goan installation from the repo root.
:: This will create a .venv_goan in the 'install' subdirectory.

:: Determine the directory of the current script (repo root)
set SCRIPT_DIR=%~dp0
set INSTALL_DIR=%SCRIPT_DIR%install
set INSTALL_SCRIPT=%INSTALL_DIR%\install.py

:: Check for Python, preferring python3 if available to align with the Linux script.
set PYTHON_CMD=
where python3 >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python
    )
)

if not defined PYTHON_CMD (
    echo Error: Python is not found. Please install Python 3 and ensure 'python' or 'python3' is in your PATH.
    goto :eof
)

:: Check if install directory and script exist
if not exist "%INSTALL_DIR%\" (
    echo Error: The 'install' directory not found at "%INSTALL_DIR%".
    goto :eof
)
if not exist "%INSTALL_SCRIPT%" (
    echo Error: 'install.py' not found at "%INSTALL_SCRIPT%".
    goto :eof
)

:: Pass arguments to the Python script
%PYTHON_CMD% "%INSTALL_SCRIPT%" %*
