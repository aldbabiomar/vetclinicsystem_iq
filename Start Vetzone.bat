@echo off
REM Vetzone IQ — double-click launcher (Windows)
REM First run: creates a virtual environment, installs dependencies, sets up
REM PostgreSQL in Docker, loads your data, and switches this install onto
REM the versioned-release layout the in-app updater needs (Settings ->
REM Updates) — automatically, no separate step required. From then on, the
REM app actually runs out of vetzone-data\ (a sibling of this folder, not
REM inside it) — every run after the first just hands off to the launcher
REM that lives there.

cd /d "%~dp0"

set "DATA_DIR=%~dp0..\vetzone-data"
if exist "%DATA_DIR%\active_release.txt" (
    call "%DATA_DIR%\Start Vetzone.bat"
    exit /b %errorlevel%
)

echo Vetzone IQ - first-time setup...
echo.

REM 1. Create the virtual environment if it doesn't exist yet
if not exist "venv\" (
    echo Creating a Python environment for setup...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo Could not create the environment. Make sure Python 3 is installed
        echo and added to PATH ^(python --version in Command Prompt should show
        echo a version number^).
        pause
        exit /b 1
    )
)

REM 2. Activate it
call venv\Scripts\activate.bat

REM 3. Install dependencies if they're not already there
python -c "import flask, reportlab, PIL, psycopg, waitress, apscheduler, dotenv, requests" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --quiet -r requirements.txt
)

REM 4. Set up PostgreSQL (Docker), schema, and data, then switch onto the
REM    versioned-release layout — all one step, safe to re-run.
python setup.py
if errorlevel 1 (
    echo.
    echo Setup did not finish.
    pause
    exit /b 1
)

if not exist "%DATA_DIR%\active_release.txt" (
    echo.
    echo Setup finished, but the versioned-release layout wasn't created —
    echo check the output above for what went wrong.
    pause
    exit /b 1
)

echo.
echo First-time setup complete — handing off to the real launcher.
echo.
call "%DATA_DIR%\Start Vetzone.bat"
