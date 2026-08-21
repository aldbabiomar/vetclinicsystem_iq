#!/bin/bash
# Vetzone IQ — double-click launcher (macOS)
# First run: creates a virtual environment, installs dependencies, sets up
# PostgreSQL in Docker, loads your data, and switches this install onto
# the versioned-release layout the in-app updater needs (Settings ->
# Updates) — automatically, no separate step required. From then on, the
# app actually runs out of vetzone-data/ (a sibling of this folder, not
# inside it) — every run after the first just hands off to the launcher
# that lives there.

cd "$(dirname "$0")" || exit 1

DATA_DIR="$(cd .. 2>/dev/null && pwd)/vetzone-data"
if [ -f "$DATA_DIR/active_release.txt" ]; then
  exec "$DATA_DIR/Start Vetzone.command"
fi

echo "Vetzone IQ — first-time setup..."
echo ""

# 1. Create the virtual environment if it doesn't exist yet
if [ ! -d "venv" ]; then
  echo "Creating a Python environment for setup..."
  python3 -m venv venv
  if [ $? -ne 0 ]; then
    echo ""
    echo "Could not create the environment. Make sure Python 3 is installed"
    echo "(python3 --version in Terminal should show a version number)."
    read -p "Press Return to close this window..."
    exit 1
  fi
fi

# 2. Activate it
source venv/bin/activate

# 3. Install dependencies if they're not already there
python3 -c "import flask, reportlab, PIL, psycopg, waitress, apscheduler, dotenv, requests" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "Installing dependencies..."
  python3 -m pip install --quiet -r requirements.txt
fi

# 4. Set up PostgreSQL (Docker), schema, and data, then switch onto the
#    versioned-release layout — all one step, safe to re-run.
python3 setup.py
if [ $? -ne 0 ]; then
  echo ""
  read -p "Setup did not finish — press Return to close this window..."
  exit 1
fi

if [ ! -f "$DATA_DIR/active_release.txt" ]; then
  echo ""
  echo "Setup finished, but the versioned-release layout wasn't created —"
  echo "check the output above for what went wrong."
  read -p "Press Return to close this window..."
  exit 1
fi

echo ""
echo "First-time setup complete — handing off to the real launcher."
echo ""
exec "$DATA_DIR/Start Vetzone.command"
