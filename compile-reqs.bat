@echo off
::
:: compile-reqs.bat - Compiles requirements.in to requirements.txt using pip-tools.
::
setlocal
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set VENV_DIR=%SCRIPT_DIR%\.venv
set SERVER_DIR=%SCRIPT_DIR%\server

echo --- Compiling Python Requirements ---

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Error: Virtual environment not found at "%VENV_DIR%".
    echo Please run the install.bat script first.
    goto :eof
)

:: Activate venv and run pip-compile
call "%VENV_DIR%\Scripts\activate.bat"
echo Compiling "%SERVER_DIR%\requirements.in" -> "%SERVER_DIR%\requirements.txt"...
pip-compile "%SERVER_DIR%\requirements.in" --output-file="%SERVER_DIR%\requirements.txt"

echo ✅ Compilation complete.
endlocal
