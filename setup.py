"""
VetClinicSystem IQ — one-command setup.
Works the same way on macOS and Windows.

    python3 setup.py

What it does, in order:
  1. Checks Docker is installed and running (prints install instructions if not).
  2. Creates .env from .env.example if you don't have one yet (with a fresh
     random SECRET_KEY).
  3. Starts the PostgreSQL container (docker compose up -d) and waits for it
     to be ready.
  4. Creates the database schema if it isn't there yet, AND applies any
     columns/tables added since your database was first set up — this runs
     every time, so a schema update never requires remembering to run a
     separate migration script by hand.
  5. If the database is empty, seeds it from seed_data.json.
  6. Prints next steps.

Safe to re-run any time — every step skips itself if already done.
"""
import os
import secrets
import shutil
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def step(msg):
    print(f"\n== {msg}")


def run(cmd, **kwargs):
    print("  $ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=BASE_DIR, **kwargs)


def check_docker():
    step("Checking Docker")
    if not shutil.which("docker"):
        print(
            "Docker was not found on this computer.\n\n"
            "Install Docker Desktop (free) from:\n"
            "  https://www.docker.com/products/docker-desktop/\n"
            "then run this script again. Docker Desktop works the same way "
            "on macOS and Windows."
        )
        sys.exit(1)
    result = run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        print(
            "Docker is installed but doesn't seem to be running.\n"
            "Start Docker Desktop, wait for it to finish launching, then "
            "run this script again."
        )
        sys.exit(1)
    print("  Docker is installed and running.")


def ensure_env_file():
    step("Checking configuration (.env)")
    env_path = os.path.join(BASE_DIR, ".env")
    example_path = os.path.join(BASE_DIR, ".env.example")
    if os.path.exists(env_path):
        print("  .env already exists — leaving it as-is.")
        return
    with open(example_path) as f:
        content = f.read()
    content = content.replace("change-me", secrets.token_hex(32))
    with open(env_path, "w") as f:
        f.write(content)
    print("  Created .env with a fresh secret key.")


def start_postgres():
    step("Starting PostgreSQL (Docker)")
    compose = ["docker", "compose"]
    result = run(compose + ["version"], capture_output=True, text=True)
    if result.returncode != 0:
        compose = ["docker-compose"]  # older standalone binary
    run(compose + ["up", "-d"], check=True)

    print("  Waiting for the database to be ready...")
    for _ in range(60):
        r = run(
            compose + ["exec", "-T", "db", "pg_isready", "-U", "vetclinicsystemiq", "-d", "vetclinicsystemiq"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            print("  PostgreSQL is ready.")
            return
        time.sleep(2)
    print("  PostgreSQL didn't become ready in time — check `docker compose logs db`.")
    sys.exit(1)


def load_dotenv_now():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))


def apply_schema():
    step("Setting up the database schema")
    import db as dbmod
    con = dbmod.connect()
    schema_path = os.path.join(BASE_DIR, "schema_postgres.sql")
    with open(schema_path) as f:
        sql_text = f.read()
    dbmod.run_script(con, sql_text)
    con.commit()

    import auth
    auth.seed_default_roles_and_permissions(con)
    con.close()
    print("  Schema is up to date.")



# Additive-only schema changes shipped in a release AFTER the one that
# first introduced schema_postgres.sql's CREATE TABLE for that column/
# table. schema_postgres.sql's CREATE TABLE IF NOT EXISTS statements are
# no-ops against a table that already exists, so a column added to an
# existing table needs its own idempotent statement here too, or a
# database set up before that release would silently never get it.
#
# Add one entry per change, in the same commit as the CHANGELOG entry
# that introduces it (CLAUDE_CODE_RELEASE_WORKFLOW.md §6 step 2) — never
# edit or remove an entry once it's shipped in a release, since a live
# database may already depend on it having run. Every statement must be
# safe to run against a live database with real data: ADD COLUMN IF NOT
# EXISTS with a DEFAULT, or CREATE TABLE IF NOT EXISTS — never a
# DROP/RENAME/type-narrowing in place.
#
# Example:
#     "ALTER TABLE sales ADD COLUMN IF NOT EXISTS notes TEXT",
INCREMENTAL_SCHEMA_STATEMENTS = [
    "ALTER TABLE inventory_list ADD COLUMN IF NOT EXISTS consignment_since TEXT",
    "ALTER TABLE refunds ADD COLUMN IF NOT EXISTS refund_method TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TEXT",

    # --- One-time data normalization, not schema — same idempotent-list
    # mechanism, safe to run on every launch since each statement only
    # touches rows that still need it. Unifies "Bank Transfer" (an old,
    # inconsistent label used in a few free-text fields and, briefly, the
    # POS payment method) down to the one label the rest of the app has
    # always used: "Transfer".
    "UPDATE sales SET payment_method='Transfer' WHERE payment_method ILIKE 'bank transfer'",
    "UPDATE payments SET method='Transfer' WHERE method ILIKE 'bank transfer'",
    "UPDATE distributor_bill_payments SET method='Transfer' WHERE method ILIKE 'bank transfer'",
    "UPDATE consignment_settlements SET payment_method='Transfer' WHERE payment_method ILIKE 'bank transfer'",

    # --- Retroactive permission grant, not schema. A brand-new permission
    # added to auth.PERMISSIONS only reaches a role at the moment that
    # role is first created (seed_default_roles_and_permissions never
    # re-grants into an existing role) — so an install whose Admin role
    # already existed before manage_cash_register was introduced needs it
    # granted explicitly here, once, or nobody could ever reach the page.
    "INSERT INTO role_permissions (role_id, permission_id) "
    "SELECT id, 'manage_cash_register' FROM roles WHERE is_system=true "
    "ON CONFLICT DO NOTHING",
    # Mirrors auth.bump_permissions_version() — forces any already-logged-in
    # session (e.g. an Admin mid-shift when this update lands) to pick up
    # the newly-granted permission above on its next request, no re-login
    # required, same as every other in-app permission change.
    "INSERT INTO settings (key, value) VALUES ('permissions_version', '1') "
    "ON CONFLICT (key) DO UPDATE SET value = (COALESCE(settings.value, '0')::int + 1)::text",
]


def apply_incremental_migrations():
    step("Applying incremental schema updates")
    import db as dbmod
    con = dbmod.connect()
    for stmt in INCREMENTAL_SCHEMA_STATEMENTS:
        con.execute(stmt)
    con.commit()
    con.close()
    if INCREMENTAL_SCHEMA_STATEMENTS:
        print(f"  Applied {len(INCREMENTAL_SCHEMA_STATEMENTS)} incremental statement(s).")
    else:
        print("  Nothing to apply.")


def migrate_or_seed():
    step("Loading data")
    import db as dbmod
    con = dbmod.connect()
    existing = con.execute("SELECT COUNT(*) AS n FROM owners").fetchone()["n"]
    con.close()

    if existing:
        print("  Database already has data in it — skipping seed.")
        return

    print("  No existing data found — building a fresh database from seed_data.json...")
    run([sys.executable, "import_seed.py"], check=True)


def ensure_dependencies():
    step("Checking Python dependencies")
    req = os.path.join(BASE_DIR, "requirements.txt")
    # Plain install first; if the system Python refuses (macOS's
    # "externally-managed-environment" restriction on Homebrew/python.org
    # installs is the common case), retry with --user before giving up.
    attempts = [
        [sys.executable, "-m", "pip", "install", "-q", "-r", req],
        [sys.executable, "-m", "pip", "install", "-q", "--user", "-r", req],
    ]
    for cmd in attempts:
        if subprocess.run(cmd).returncode == 0:
            print("  Dependencies are installed.")
            return
    print(
        "\nCouldn't install the required Python packages automatically.\n"
        "Try running this by hand and then re-run setup.py:\n\n"
        f"  {sys.executable} -m pip install -r requirements.txt\n\n"
        "If that reports an 'externally-managed-environment' error, add\n"
        "--break-system-packages to the command above, or use a virtual\n"
        "environment (python3 -m venv .venv && source .venv/bin/activate).\n"
    )
    sys.exit(1)


def main():
    ensure_dependencies()
    check_docker()
    ensure_env_file()
    start_postgres()
    load_dotenv_now()
    apply_schema()
    apply_incremental_migrations()
    migrate_or_seed()

    # In-app updates (Settings -> Updates) are on by default for every new
    # install — this switches onto the versioned-release layout
    # automatically, the same as running setup.py --enable-updates by hand
    # used to require. Skipped when already running from inside a managed
    # release, or when --no-enable-updates is passed (e.g. a plain local
    # dev checkout that deliberately wants to keep running in place).
    # "Already inside a managed release" is checked two ways: VETCLINICSYSTEMIQ_DATA_DIR
    # is set when launched through the real launcher, but someone can also
    # cd into a release folder and run setup.py by hand with no env vars
    # set at all — the structural check (this folder is literally named
    # app_v* directly under a vetclinicsystemiq-releases/ folder) catches that case
    # too, since re-running enable_updates() from in there would resolve
    # data_dir/releases_dir relative to the WRONG parent and nest a second,
    # broken layout inside the first.
    in_release_folder = (
        os.path.basename(BASE_DIR).startswith("app_v")
        and os.path.basename(os.path.dirname(BASE_DIR)) == "vetclinicsystemiq-releases"
    )
    already_managed = bool(os.environ.get("VETCLINICSYSTEMIQ_DATA_DIR")) or in_release_folder
    if already_managed or "--no-enable-updates" in sys.argv:
        print(
            "\nAll set. Start the app with:\n"
            "  python3 app.py\n"
            "\n(macOS: double-click 'Start VetClinicSystem.command'."
            "  Windows: double-click 'Start VetClinicSystem.bat'.)\n"
        )
        return

    enable_updates()


# ---------------------------------------------------------------------------
# One-time opt-in: switch this install onto the versioned-release layout
# the in-app updater (Settings -> Updates, updater.py) needs. Not run by
# default main() — an admin runs `python3 setup.py --enable-updates`
# deliberately, since it moves .env/logs/attachments out of this folder.
# See UPDATE_MECHANISM_PLAN.md §3 for the target layout.
# ---------------------------------------------------------------------------
_MACOS_LAUNCHER = """#!/bin/bash
# VetClinicSystem IQ — supervisor launcher (macOS). Lives in vetclinicsystemiq-data/,
# OUTSIDE any versioned release folder, so it survives every update.
# Reads active_release.txt fresh on every loop iteration to know which
# vetclinicsystemiq-releases/app_vX.Y.Z/ to run, and restarts automatically if the
# app process exits for any reason — a crash, or the deliberate exit
# updater.py triggers after promoting a new release (see
# updater.py's _request_restart()). updater.py has already proven the new
# release boots and passes /health, on a throwaway port, before ever
# flipping the pointer that controls what this loop runs next — this
# script's only job is to keep something running and pick up that change.
set -u
DATA_DIR="$(cd "$(dirname "$0")" && pwd)"
RELEASES_DIR="$(cd "$DATA_DIR/../vetclinicsystemiq-releases" && pwd)"
POINTER="$DATA_DIR/active_release.txt"
PORT="${VETCLINICSYSTEMIQ_PORT:-5050}"
opened_browser=false

echo "VetClinicSystem IQ is running at http://127.0.0.1:$PORT"
echo "Leave this window open while you use the app."
echo "Close this window (or press Control-C) to stop it."
echo ""

while true; do
  ACTIVE=$(cat "$POINTER" 2>/dev/null || true)
  if [ -z "$ACTIVE" ] || [ ! -d "$RELEASES_DIR/$ACTIVE" ]; then
    echo "No valid release at $POINTER — can't start. Run setup.py --enable-updates again?"
    read -p "Press Return to close this window..."
    exit 1
  fi
  RELEASE_DIR="$RELEASES_DIR/$ACTIVE"
  echo "Starting $ACTIVE..."
  VETCLINICSYSTEMIQ_DATA_DIR="$DATA_DIR" VETCLINICSYSTEMIQ_RELEASES_DIR="$RELEASES_DIR" VETCLINICSYSTEMIQ_PORT="$PORT" \\
    "$RELEASE_DIR/venv/bin/python3" "$RELEASE_DIR/app.py" &
  APP_PID=$!

  if [ "$opened_browser" = false ]; then
    ( sleep 1.5 && open "http://127.0.0.1:$PORT" ) &
    opened_browser=true
  fi

  wait "$APP_PID"
  echo "VetClinicSystem IQ exited (code $?) — restarting in 2 seconds..."
  sleep 2
done
"""

_WINDOWS_LAUNCHER = """@echo off
REM VetClinicSystem IQ — supervisor launcher (Windows). Lives in vetclinicsystemiq-data\\,
REM OUTSIDE any versioned release folder, so it survives every update.
REM Reads active_release.txt fresh on every loop iteration — see the
REM matching comment in the macOS launcher (Start VetClinicSystem.command) for
REM why this loop doesn't need its own health-check/rollback logic.
setlocal
set "DATA_DIR=%~dp0"
set "RELEASES_DIR=%DATA_DIR%..\\vetclinicsystemiq-releases"
set "POINTER=%DATA_DIR%active_release.txt"
if not defined VETCLINICSYSTEMIQ_PORT set "VETCLINICSYSTEMIQ_PORT=5050"
set "OPENED_BROWSER=0"

:loop
set /p ACTIVE=<"%POINTER%"
if not exist "%RELEASES_DIR%\\%ACTIVE%" (
  echo No valid release at %POINTER% — can't start. Run setup.py --enable-updates again?
  pause
  exit /b 1
)
set "RELEASE_DIR=%RELEASES_DIR%\\%ACTIVE%"
echo Starting %ACTIVE%...
set "VETCLINICSYSTEMIQ_DATA_DIR=%DATA_DIR%"
set "VETCLINICSYSTEMIQ_RELEASES_DIR=%RELEASES_DIR%"
if "%OPENED_BROWSER%"=="0" (
  start "" http://127.0.0.1:%VETCLINICSYSTEMIQ_PORT%
  set "OPENED_BROWSER=1"
)
"%RELEASE_DIR%\\venv\\Scripts\\python.exe" "%RELEASE_DIR%\\app.py"
echo VetClinicSystem IQ exited — restarting in 2 seconds...
timeout /t 2 /nobreak >nul
goto loop
"""


def _copy_release_snapshot(dest):
    """Copies the current codebase into dest, excluding everything that
    belongs to a specific machine/install rather than the versioned app
    itself (venv, .git, __pycache__, and anything already destined for
    vetclinicsystemiq-data/)."""
    exclude = {"venv", ".git", "__pycache__", "logs", ".env", "vetclinicsystemiq-data", "vetclinicsystemiq-releases"}
    shutil.copytree(
        BASE_DIR, dest,
        ignore=lambda src, names: [n for n in names if n in exclude or n.startswith(".env")],
    )


def enable_updates(data_dir=None, releases_dir=None):
    step("Switching to the versioned-release layout")
    parent = os.path.dirname(BASE_DIR)
    data_dir = os.path.abspath(data_dir or os.path.join(parent, "vetclinicsystemiq-data"))
    releases_dir = os.path.abspath(releases_dir or os.path.join(parent, "vetclinicsystemiq-releases"))
    pointer = os.path.join(data_dir, "active_release.txt")

    if os.path.isfile(pointer):
        print(f"  Already enabled — {pointer} exists.")
        print(f"  VETCLINICSYSTEMIQ_DATA_DIR={data_dir}\n  VETCLINICSYSTEMIQ_RELEASES_DIR={releases_dir}")
        return

    version_path = os.path.join(BASE_DIR, "VERSION")
    if not os.path.isfile(version_path):
        print("  No VERSION file in this codebase — can't determine the release name. Aborting.")
        sys.exit(1)
    version = open(version_path).read().strip()
    release_name = f"app_v{version}"
    release_path = os.path.join(releases_dir, release_name)

    print(f"  This will:\n"
          f"    - create {data_dir}/ (persistent: .env, logs, attachments, backups)\n"
          f"    - create {releases_dir}/{release_name}/ (a copy of this codebase)\n"
          f"    - move .env, logs/, attachments/uploads/ into {data_dir}/\n"
          f"    - write new launcher scripts into {data_dir}/\n"
          f"  This folder ({BASE_DIR}) is left as-is otherwise — nothing here is deleted.\n")

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(releases_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "backups"), exist_ok=True)

    print(f"  Copying codebase into {release_path} ...")
    if os.path.isdir(release_path):
        shutil.rmtree(release_path)
    _copy_release_snapshot(release_path)

    print("  Creating this release's own virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", os.path.join(release_path, "venv")], check=True)
    venv_py = os.path.join(release_path, "venv", "Scripts" if sys.platform == "win32" else "bin",
                            "python.exe" if sys.platform == "win32" else "python3")
    subprocess.run([venv_py, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
                    check=True, cwd=release_path)

    env_src = os.path.join(BASE_DIR, ".env")
    env_dst = os.path.join(data_dir, ".env")
    if os.path.isfile(env_src) and not os.path.isfile(env_dst):
        shutil.move(env_src, env_dst)
        print(f"  Moved .env -> {env_dst}")

    logs_src = os.path.join(BASE_DIR, "logs")
    logs_dst = os.path.join(data_dir, "logs")
    os.makedirs(logs_dst, exist_ok=True)
    if os.path.isdir(logs_src):
        for name in os.listdir(logs_src):
            shutil.move(os.path.join(logs_src, name), os.path.join(logs_dst, name))

    uploads_src = os.path.join(BASE_DIR, "uploads")
    uploads_dst = os.path.join(data_dir, "attachments", "uploads")
    if os.path.isdir(uploads_src):
        os.makedirs(os.path.dirname(uploads_dst), exist_ok=True)
        shutil.move(uploads_src, uploads_dst)
        print(f"  Moved uploads/ -> {uploads_dst}")

    with open(pointer, "w") as f:
        f.write(release_name)

    mac_launcher = os.path.join(data_dir, "Start VetClinicSystem.command")
    win_launcher = os.path.join(data_dir, "Start VetClinicSystem.bat")
    with open(mac_launcher, "w", newline="\n") as f:
        f.write(_MACOS_LAUNCHER)
    os.chmod(mac_launcher, 0o755)
    with open(win_launcher, "w", newline="\r\n") as f:
        f.write(_WINDOWS_LAUNCHER)

    print(
        f"\nDone. Add these two lines to {env_dst}:\n\n"
        f"  VETCLINICSYSTEMIQ_DATA_DIR={data_dir}\n"
        f"  VETCLINICSYSTEMIQ_RELEASES_DIR={releases_dir}\n\n"
        f"Then start the app from now on with:\n"
        f"  {mac_launcher}   (macOS)\n"
        f"  {win_launcher}   (Windows)\n\n"
        f"Not from {os.path.join(BASE_DIR, 'Start VetClinicSystem.command')} anymore — that copy has no "
        f"way to pick up future updates. This original folder is untouched and safe to keep "
        f"around, but the copy under {releases_dir}/ is what actually runs from now on.\n"
    )


if __name__ == "__main__":
    if "--enable-updates" in sys.argv:
        enable_updates()
    else:
        main()
