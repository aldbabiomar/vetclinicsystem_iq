# Reconciling Orphaned Attachments After a Restore

## Problem

`uploads/` (attached files for visits and inpatient cases) is **not** included in
backup/restore — only the Postgres database is (`backup.py`, `pg_dump`/`pg_restore`).
After a restore, any `attachments` rows created after the backup are gone, but the
files they pointed to are still sitting on disk under
`uploads/<patient_id>/<key>/<filename>`. The app only serves/lists attachments via
the `attachments` table (`relative_path` column), so these files become invisible
("orphaned") even though nothing was deleted.

Separately: because restore also rewinds ID-generation state (`id_counters` for
visit IDs, the `inpatient_cases` identity sequence) back to its backup-time value,
a **new** record created after the restore can be handed the exact same ID as a
record that existed only in the post-backup gap — meaning a leftover folder could
get silently misattributed to the wrong patient/visit if we're not careful.

## Key facts (already confirmed by code inspection)

- Upload path: `uploads/<patient_id>/<record_key>/<YYYYmmddHHMMSS>_<uuid6>_<original_name>`
  - `attachments.py:74-78` (`save_attachment`)
  - `record_key()` = `"V" + visit_id` or `"IC" + case_id` (`attachments.py:26-28`)
  - **Quirk:** for visits, `visit_id` passed in is already prefixed (e.g. `"V007"`),
    so the folder actually ends up double-prefixed: `VV007`, not `V007`. Inpatient
    case folders are clean (`IC7`). Any script must special-case this.
- Filename encodes original name + upload timestamp to the second — no separate
  manifest file exists, but this is enough to reconstruct `original_name` and
  `uploaded_at`.
- `attachments` table schema (`schema_postgres.sql:528-541`): `patient_id`,
  `visit_id`, `inpatient_case_id`, `relative_path`, `original_name`, `uploaded_at`,
  `uploaded_by`. The app resolves files strictly through this table
  (`app.py:1963-1977` `serve_attachment`), never by scanning disk — so a rebuild
  must **insert rows**, not just leave files in place.
- IDs survive a restore verbatim: `pg_restore` replays row data + `setval()`
  exactly as dumped. So a folder's embedded `patient_id`/`record_key` can still be
  matched against *current* `patients`/`visits`/`inpatient_cases` rows after a
  restore — **if** that row still legitimately corresponds to the same real-world
  record (see collision risk below).
- `backup_log` / `restore_log` (`schema_postgres.sql:19-40`) record exact
  `started_at`/`finished_at` for every backup/restore — used to detect the
  collision window.

## Collision risk to guard against

If a folder's embedded upload timestamp is **after** the `started_at` of the
backup that was restored, the matching `visit_id`/`case_id`/`patient_id` in the
*current* database may belong to a different record created after the restore
(because ID counters/sequences got rewound). In that case the folder must **not**
be auto-readopted — flag it for manual review instead.

## Proposed script: `reconcile_attachments.py`

### Inputs
- DB connection (reuse `db.py` connection helper).
- `UPLOAD_ROOT` (`attachments.py:15`).
- Latest relevant `restore_log` row (to get the restore cutoff timestamp), if one
  exists.

### Algorithm
1. Walk `uploads/<patient_id>/<key>/*` on disk.
2. For each file, parse `<patient_id>`, `<key>`, and from the filename extract
   `uploaded_at` and `original_name`.
3. Normalize `key`:
   - If it starts with `IC`, strip prefix → `inpatient_case_id` (int).
   - If it starts with `VV`, strip the doubled prefix → `visit_id` (e.g. `V007`).
   - Anything else → log as unrecognized, skip.
4. Look up the resolved `patient_id` + `visit_id`/`inpatient_case_id` in the
   current DB:
   - No matching record → still orphaned (patient/visit truly gone), leave alone,
     report in a "no home found" list for manual triage (don't delete anything).
   - Matching record found → check if a corresponding `attachments` row
     (matching `relative_path`) already exists. If yes, skip (already fine).
5. If matching record found and no `attachments` row exists yet:
   - If there is no relevant restore event, **or** the file's `uploaded_at` is
     **before** the restore's `started_at` → safe to readopt. Insert the missing
     `attachments` row.
   - If the file's `uploaded_at` is **after** the restore's `started_at` → do
     **not** auto-readopt (possible ID-reuse collision). Report separately as
     "needs manual review."
6. Produce a report (counts + full lists) for all four buckets: readopted,
   no-home-found, needs-manual-review, already-fine. Nothing is deleted or moved
   in any case.

### Safety requirements
- **Dry-run by default.** Require an explicit `--apply` flag to actually insert
  rows; otherwise only print the report.
- **Idempotent.** Re-running after `--apply` should find nothing left to do.
- **Never delete or move files.** This script only adds missing DB rows.
- **Log every insert** (patient_id, record id, relative_path, timestamp) to a
  file for audit purposes, separate from the app's normal logs.
- Run against a DB backup/staging copy first if possible before running
  `--apply` against production.

### Open questions to confirm before building
- Should `uploaded_by` be set to some sentinel value (e.g. `"reconciled"`) for
  readopted rows, so they're distinguishable from normal uploads later?
- Do we want a companion script/report to run automatically right after every
  restore (via `backup.py`'s restore flow), or is this strictly a manual,
  on-demand tool for now?

## Status

This is a design document only — no code has been written yet. Next step is to
implement `reconcile_attachments.py` per the algorithm above, once the open
questions are answered.
