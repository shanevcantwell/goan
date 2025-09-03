@echo off
::
:: sync-reqs.bat - Syncs the virtual environment with requirements.txt using pip-tools.
::
setlocal
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set VENV_DIR=%SCRIPT_DIR%\.venv
set SERVER_DIR=%SCRIPT_DIR%\server
set REQUIREMENTS_FILE=%SERVER_DIR%\requirements.txt

echo --- Syncing Python Environment ---

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Error: Virtual environment not found at "%VENV_DIR%".
    echo Please run the install.bat script first.
    goto :eof
)

if not exist "%REQUIREMENTS_FILE%" (
    echo Error: "%REQUIREMENTS_FILE%" not found.
    echo Please run the compile-reqs.bat script first.
    goto :eof
)

:: Activate venv and run pip-sync
call "%VENV_DIR%\Scripts\activate.bat"
echo Syncing environment with "%REQUIREMENTS_FILE%"...
pip-sync "%REQUIREMENTS_FILE%"

echo ✅ Environment is up to date.
endlocal
