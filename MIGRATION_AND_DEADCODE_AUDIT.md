# VetClinicSystem IQ — Migration Script & Dead Code Audit

**Scope:** Full repository sweep ahead of a fresh deployment.
**Database:** PostgreSQL only (this codebase has no SQLite path).
**Method:** Manual review of `setup.py`/`db.py`/`schema_postgres.sql` for Task 1; automated static analysis (`vulture` + `pyflakes`) across all 16 first‑party Python modules for Task 2, with every hit manually verified against the actual call graph (including Flask's decorator-based dispatch, which static analysis cannot see) before being reported. Nothing below is a raw tool dump — every finding was checked with `grep`/`git log`/source reading before being listed.

---

## Architecture note (read this first)

This codebase does **not** use a `migrations/0001_xxx.sql`, `0002_yyy.sql`-style folder. There is exactly **one** SQL file, plus **one** in-code list that acts as the migration history:

| File | Role |
|---|---|
| [schema_postgres.sql](schema_postgres.sql) | Full, current schema — every `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` needed to build the database from nothing. This is what a fresh install actually runs first. |
| [setup.py](setup.py) `INCREMENTAL_SCHEMA_STATEMENTS` (lines 139–169) | An append-only list of idempotent `ALTER TABLE`/`UPDATE`/`INSERT` statements, one per schema change shipped **after** `schema_postgres.sql` last had that change baked in natively. This is the closest thing this codebase has to individual "migration scripts" — each list entry is effectively one migration, just stored as a list item instead of a file. |

Critically, per the [README](README.md): *"The same codebase deploys independently per clinic (each with its own database)"*, and `updater.py` re-runs `setup.apply_incremental_migrations()` on **every** in-app update (Settings → Updates) against a clinic's live, already-populated database (see `updater.py:216`, `backup.py:393`). So `INCREMENTAL_SCHEMA_STATEMENTS` isn't scoped to *this* fresh deployment — it's shared code that every other clinic instance in the field (or every future clinic instance that installs an older release and updates forward) depends on to catch its database up.

This matters for how "removable" is judged below.

---

## Task 1 — Migration Script Audit

### Essential (required for a fresh deployment)

| Item | Why essential |
|---|---|
| [schema_postgres.sql](schema_postgres.sql) | The base schema. `setup.apply_schema()` runs this file verbatim on every install. Non-negotiable. |
| [setup.py](setup.py) — `apply_schema()`, `apply_incremental_migrations()`, `migrate_or_seed()`, `main()` | The install/bootstrap driver. Runs schema creation, then incremental statements, then seeds if empty. |
| [auth.py](auth.py) `seed_default_roles_and_permissions()` | Called from `apply_schema()` — creates the Admin/Vet/Reception roles and grants permissions. Without it a fresh DB has tables but no usable login. |
| [import_seed.py](import_seed.py) | Populates a genuinely empty database (owners, patients, price list, etc. from `seed_data.json`) on first run — invoked automatically by `migrate_or_seed()` when the `owners` table is empty. |
| [db.py](db.py) `run_script()`, `next_id()`, `seed_counter()` | Support code the schema/seed step depends on (statement-splitting for the schema file, atomic ID counters). |

### `INCREMENTAL_SCHEMA_STATEMENTS` (setup.py:139–169) — keep the mechanism, but it's functionally inert on a true fresh install

I checked each of the 7 statements currently in the list against `schema_postgres.sql` and the current `auth.PERMISSIONS`:

| Statement | Already covered natively by a fresh `schema_postgres.sql`? |
|---|---|
| `ALTER TABLE inventory_list ADD COLUMN IF NOT EXISTS consignment_since TEXT` | Yes — column exists in the `CREATE TABLE` at [schema_postgres.sql:218](schema_postgres.sql). No-op on fresh install. |
| `ALTER TABLE refunds ADD COLUMN IF NOT EXISTS refund_method TEXT` | Yes — [schema_postgres.sql:618](schema_postgres.sql). No-op on fresh install. |
| 4× "Bank Transfer" → "Transfer" `UPDATE` normalization statements | No rows exist yet on a fresh DB, so these touch 0 rows. No-op. |
| `manage_cash_register` retroactive grant `INSERT` + `permissions_version` bump | `manage_cash_register` is already in `auth.PERMISSIONS` (auth.py:40) and gets granted to Admin at role-creation time by `seed_default_roles_and_permissions()`. No-op on fresh install (`ON CONFLICT DO NOTHING`). |

**Recommendation: do not delete this list or any entry in it**, despite every current entry being a harmless no-op for *this specific* fresh deployment. Reasons:
1. The comment block directly above the list (setup.py:122–135) explicitly documents this as append-only and warns against editing/removing shipped entries because "a live database may already depend on it having run" — i.e. other clinic installs in the field.
2. `git log` confirms entries were added across multiple shipped releases (v1.0.0 → v1.1.0 → Cash Register feature → consignment fix → rebrand), each tied to a real customer-facing update.
3. The mechanism itself (the `INCREMENTAL_SCHEMA_STATEMENTS` list, `apply_incremental_migrations()`, the wiring in `updater.py`) is essential infrastructure — it's only the **specific line items** that are stale for a fresh install, and they cost nothing to leave (each runs in under a millisecond against an empty table).

If you want a leaner fresh-install path specifically, the only genuinely safe trim is optional and cosmetic: nothing here should actually be removed. This section is "essential" as a mechanism; the current entries are naturally self-obsoleting no-ops rather than something requiring deletion.

### Removable / not part of the deployed application

| Item | Why removable from a deployment package |
|---|---|
| [dev_seed/](dev_seed/) (`generate_seed.py`, `apply_seed.sh`, `vetclinicsystemiq_test_data.dump` — 26 MB, `README.md`) | A local-only 25-year synthetic test dataset generator for development. Already excluded from git via [.gitignore:29](.gitignore). Not referenced anywhere in `app.py`, `setup.py`, or `updater.py` — confirmed via repo-wide grep. Not part of what ships to a clinic; if this folder exists in your deployment working copy, exclude it (it already won't be pulled by the updater's git-based release mechanism since it's untracked). |

No other files matched "migration script" in this codebase — there is no legacy `schema.sql` (SQLite), no old `migrations/` directory, and no orphaned one-off migration scripts sitting around. The codebase is already lean on this front.

---

## Task 2 — Dead Code Analysis

### Methodology

Ran `vulture` (confidence ≥60%) and `pyflakes` against all first-party modules: `app.py, attachments.py, auth.py, autostart.py, backup.py, barcode.py, db.py, import_seed.py, jobs.py, logic.py, money.py, pdf_export.py, reconcile_attachments.py, scheduler.py, setup.py, updater.py`.

- **`pyflakes`: zero findings.** No unused imports, no undefined names, anywhere in the 16 core modules.
- **`vulture`: 169 raw hits**, of which **156 were confirmed false positives** — Flask view functions (`@app.route`), lifecycle hooks (`@app.before_request`, `@app.after_request`), error handlers (`@app.errorhandler`), a template filter (`@app.template_filter`), and a context processor (`@app.context_processor`). These are invoked by Flask's dispatcher/Jinja at runtime, which static analysis can't trace — I verified this by counting: `app.py` has 157 such decorators and vulture flagged 156 of the decorated functions "unused," a 1:1 match confirming the pattern rather than 156 individual bugs. Also excluded: `csrf = CSRFProtect(app)` (registers CSRF protection via side effect on construction — not dead), `session.permanent = True` (real Flask session API), and the `signum`/`frame` parameters of a `signal.signal()` callback (required by that interface's signature, unused by design).

What's left after removing all false positives is genuinely dead:

### Confirmed dead code (safe to delete)

| # | Location | What it is | Evidence |
|---|---|---|---|
| 1 | [logic.py:164–169](logic.py) `_txn_qty_since(db, item_id, since_date)` | Single-item inventory-transaction-quantity lookup. | Zero call sites anywhere in the repo. Superseded by `_txn_qty_since_batch()` (logic.py:172), which does the same thing for all items in one query and *is* used (called from `inventory_status()` at logic.py:221). This looks like dead code left behind after the batch version replaced it. |
| 2 | [logic.py:352–353](logic.py) `price_lookup(db)` | Returns `{price_list.id: row}` for every price list row. | Zero call sites anywhere in the repo (checked `app.py`, all templates, all other modules). |
| 3 | [auth.py:74](auth.py) `ROLES = ["Admin", "Vet", "Reception"]` | Hardcoded legacy role-name list. | Zero references anywhere else in the codebase. The comment directly above it (auth.py:71–73) already says it's kept "only for places... that still refer to a role by its seeded name" — but no such place exists in the current code; the live source of truth is the `roles` table, as the same comment states. Even the author's own comment flags this as legacy. |
| 4 | [import_seed.py:45](import_seed.py) `INPATIENT_CASE_STATUSES_CLOSED = {"Resolved", "Deceased/Euthanized", "Lost to Follow Up", "Referred"}` | A set of "closed" inpatient case statuses. | Zero references anywhere in `import_seed.py` or elsewhere. Its sibling `CASE_STATUS_MAP` (line 40, three lines above) *is* used (import_seed.py:174) — this one was apparently never wired up. |

**Action:** delete all four (10 lines total). None are imported or referenced elsewhere, so removal is a pure subtraction with no follow-up changes needed.

### Out of scope, noted only for completeness

[dev_seed/generate_seed.py](dev_seed/generate_seed.py) (a git-ignored, dev-only data generator — see Task 1) has a handful of unused locals (`owner_rows_buffer` L580, `join_date` L589, `PATIENT_SEX` L635, `BOARDING_SEED` L793, `all_staff_today` L804, `user_by_id` L1354). Since this file never ships and isn't tracked in git, cleaning it up has no effect on the deployed app or code integrity — flagged here only so it's not mistaken for something the sweep missed.

---

## Summary / Action Checklist

- [ ] Delete `logic.py:164–169` (`_txn_qty_since`)
- [ ] Delete `logic.py:352–353` (`price_lookup`)
- [ ] Delete `auth.py:74` (`ROLES`)
- [ ] Delete `import_seed.py:45` (`INPATIENT_CASE_STATUSES_CLOSED`)
- [ ] Leave `setup.py`'s `INCREMENTAL_SCHEMA_STATEMENTS` list and mechanism untouched — it's live infrastructure for every other/future clinic install's auto-update path, not dead weight
- [ ] Optional: exclude `dev_seed/` from anything you package for a clinic deployment (already git-ignored, so this is likely already a non-issue)
- [ ] No unused imports found anywhere — no action needed there
