# Vetzone IQ — Security/Integrity Fix Changelog

Applied against the uploaded `Vetzone_IQ.zip`. Every item below was verified
by reading the actual current code (line numbers in the original audit
reports had drifted slightly from a prior edit; this changelog uses what's
actually in this codebase).

No live PostgreSQL instance was available in this environment (no network
access), so every fix below was verified by manual trace-through of every
call site, not by running the app. **A manual QA pass in staging is required
before production deploy** — see QA_CHECKLIST.md.

---

## High #17 — Audit log is now atomic with the change it describes
**Files:** `auth.py`, `app.py`

`auth.log_change()` used to call `db.commit()` itself. Every route did
`mutate → db.commit() → auth.log_change()`, so if the process died or the
audit insert failed between those two calls, the mutation was permanently
saved with no audit trail.

Fix: `log_change()` no longer commits. Every one of the 56 call sites in
`app.py` was reordered so `log_change()` runs *before* the route's
`db.commit()` (a few — role edits, attachment delete, bulk inpatient
billing — needed a slightly bigger reorder because of an
`auth.bump_permissions_version()` call or a loop in between; those were
each checked and fixed by hand, not just mechanically). Now mutation +
audit row commit together, or roll back together via the existing
`teardown_appcontext` handler if an exception happens first.

Verified: every `auth.log_change(` call site in `app.py` was individually
grep'd and inspected; all 56 now precede a `db.commit()` in the same
function, in the same transaction.

## Critical #1 — POS checkout oversell race
**File:** `app.py` (`pos_checkout`)

Added `SELECT id FROM inventory_list WHERE id=? FOR UPDATE` for every
distinct item in the cart, in sorted-by-id order, *before* any stock is
computed or checked. This makes two concurrent checkouts touching the
same item serialize on the row lock instead of both reading the same
"before" stock number; the second checkout's stock computation runs only
after the first has committed, so it correctly sees the first sale's
movement. Sorting the lock order (not cart order) prevents a deadlock
between two carts that share two items in opposite order.

Scope note: this only covers the POS checkout path (what F-001/Critical#1
specifically named). Other places that write `inventory_transactions`
(audit-session confirmation, manual stock adjustment) were not touched —
they weren't part of what was asked, and a race there is lower-frequency
and lower-severity than concurrent point-of-sale checkouts. Flagging this
as a known residual gap, not a silent one.

## Critical #3 — Restore endpoint accepted an arbitrary file path
**Files:** `backup.py` (new `resolve_restorable_backup()`), `app.py`

Added a check, run before any restore work starts, requiring the
submitted path to (1) resolve — symlinks included — to somewhere inside
the currently-configured backup folder, and (2) exactly match a
`backup_log` row with `status='success'`, i.e. a file this app's own
Backup Now / nightly job actually produced. Anything else is rejected
with a clear message before `pg_restore` is ever invoked. Deliberately
does **not** add a second-admin approval step, per your instruction —
this closes the arbitrary-path hole while leaving restore a single-admin
action.

Also fixed a pooling correctness bug this surfaced: `settings_restore_now`
used to call `conn.close()` directly on the request's connection before
restoring; now that `get_db()` hands out pooled connections, that would
have silently leaked a pool slot every time someone restored. Now uses
`dbmod.putconn()`, and closes the whole pool before the restore runs (it's
about to DROP/recreate every table `pg_restore --clean` touches) — the
pool transparently reopens on the next request afterward.

## High #6 — No connection pool
**Files:** `db.py`, `app.py`, `requirements.txt`

Added `psycopg_pool.ConnectionPool` (bounded size; `DB_POOL_MIN_SIZE` /
`DB_POOL_MAX_SIZE` / `DB_POOL_TIMEOUT_SECONDS` / `DB_POOL_MAX_LIFETIME_SECONDS`
env vars, sensible defaults for a single-clinic LAN deployment).
`get_db()`/`close_db()` now borrow/return pooled connections. Pool
exhaustion raises `db.PoolTimeout` (a plain `Exception`), which the
existing catch-all error handler already logs and shows as a clear,
redacted error page — no raw hang, no crash.

`dbmod.connect()` (standalone, unpooled) is kept as-is for code that
legitimately runs outside a request lifecycle: `setup.py`, `import_seed.py`,
the nightly backup job, the shutdown backup, and restore's post-restore
logging. Each of those call sites was individually checked before being
left alone.

## Medium — Insights dashboard's 6 parallel connections
**File:** `app.py` (`insights`)

The 6 parallel report queries now borrow/return pooled connections
(`dbmod.getconn()`/`dbmod.putconn()`) instead of opening 6 brand-new raw
connections per page view — bounded by the same pool now, instead of
being unbounded. Each borrowed connection is explicitly rolled back
before being returned (these are read-only queries, so a rollback is
correct and doesn't rely on the pool's own defensive reset-on-return).

## High #9 — Attachment upload/delete file↔DB ordering
**File:** `attachments.py`, `app.py`

**Upload:** the DB row is now inserted first (uncommitted), then the file
is written to disk, and only then committed. A disk-write failure now
just rolls back the still-open insert — nothing was ever on disk to
clean up. If the *commit* itself fails after a successful disk write (a
narrower window), the just-written file is now explicitly removed rather
than left as an orphan.

**Delete:** reversed to file-first, DB-row-second, and the DB row is now
only removed if the file delete actually succeeded (or the file was
already gone). A filesystem failure no longer silently destroys the
app's only pointer to a real file while leaving that file sitting on
disk unreferenced — it now leaves the attachment row (and thus the
file) fully intact and shows staff a clear error. This changed
`delete_attachment()`'s return shape from `row|None` to `(row, error)`;
the one caller (`attachment_delete` in `app.py`) was updated to match —
grepped for other callers, there are none.

## High #16 + Medium (2 items) — Missing foreign keys, duplicate audit lines
**Files:** `schema_postgres.sql`, `setup.py`, `app.py`

Added FKs: `payments.visit_id/inpatient_case_id/boarding_id/user_id`,
`attachments.visit_id/inpatient_case_id/uploaded_by`,
`inpatient_cases.visit_id`, `price_list.linked_item_id`. All reference
nullable columns, so NULL still means "not linked to that kind of
record" exactly as before — the constraint only ever fires on a
non-NULL value that doesn't point at a real row.

**Important implementation note:** this codebase's own `db.run_script()`
(which executes `schema_postgres.sql`) splits the file on bare `;` after
stripping `--` comments — it does not understand PL/pgSQL's dollar-quoted
`DO $$ ... $$` blocks, which is the normal way to make
`ADD CONSTRAINT` idempotent in plain SQL (Postgres has no
`ADD CONSTRAINT IF NOT EXISTS`). I initially wrote the FK additions as
`DO $$` blocks directly in `schema_postgres.sql` and caught this before
finishing — those would have shattered into invalid fragments on next
startup. Fixed by: (1) keeping the defensive orphan-cleanup `UPDATE`
statements (single-statement, splitter-safe) in `schema_postgres.sql`,
and (2) adding the actual `ADD CONSTRAINT` calls from Python in
`setup.py`'s new `add_missing_foreign_keys()`, checking
`information_schema.table_constraints` first — the exact same pattern
this codebase already uses for `users_role_id_fkey` in
`migrate_users_role_to_role_id()`.

Checked every `INSERT INTO payments` / attachment-creation / inpatient
-case-creation call site in `app.py` by hand to confirm the app never
writes a value that would violate these constraints under normal use —
`user_id`/`uploaded_by` always come from the logged-in session, parent
IDs always come from routes/helpers that already looked up or just
inserted the parent row. No `ON DELETE CASCADE` — nothing in the app
hard-deletes a visit/inpatient case/boarding session/user/price_list/
inventory_list row (grepped every `DELETE FROM` against these tables),
so the default `RESTRICT` is correct and inert today.

Also added `uq_auditlines_session_item` — a unique index on
`audit_session_lines (session_id, item_id)` — with a defensive
dedup `DELETE` first (keeps the highest `id`, i.e. most recently saved
values, for any pre-existing duplicate). `app.py`'s `_save_audit_lines()`
now does `INSERT ... ON CONFLICT (session_id, item_id) DO UPDATE`
instead of a check-then-insert, closing the race where two concurrent
saves for the same item could both insert.

## Medium — Report/list pages paginating in Python instead of SQL
**Files:** `logic.py`, `app.py`

Converted 4 of the 6 flagged routes to real `ORDER BY ... LIMIT ? OFFSET ?`
pagination: Follow-ups, Wellness, Grooming, Audit History. (Price List
was already SQL-paginated when I checked — nothing to do there.)

For Follow-ups/Wellness/Grooming specifically, `logic.followups()` /
`wellness_reminders()` / `grooming_queue()` are each called from *two*
places: the list page (wants one page) and the dashboard's missed-items
summary / daily counts (`logic.missed_items()`, `logic.dashboard_counts()`
— wants every matching row, to correctly count "missed" items across the
whole clinic, not just page 1). So rather than add limit/offset to those
shared functions, I added a parallel `..._page()` function for each
that does the real SQL pagination, and left the original functions
completely untouched for the dashboard's unpaginated use. The per-row
"missed"/"due" calculation (`_annotate_followup`/`_annotate_wellness`)
is factored into a shared helper so both the paginated and unpaginated
code paths compute it identically from one place — not two copies that
could quietly drift apart. Verified this is safe because "missed"/"due"
are pure display flags on this list page (not something rows are
filtered or sorted by), so paginating first and annotating only the
resulting page produces the exact same rows the old fetch-everything-
then-slice code showed.

`only_pending` (followups) moves fully into SQL now (verified equivalent
to the old Python filter, NULL-handling included). `only_due` (wellness)
deliberately stays a Python-side filter — it depends on today's date at
request time, not a stored column, and its one caller
(`dashboard_counts()`) wants the full unpaginated set anyway.

**Retention report was deliberately left alone.** Its "rows" are
cohort-months (bounded by how long the clinic has been open — typically
a few dozen at most), not per-visit/per-record rows that grow with
clinic history — `cohort_retention_grid()`'s own docstring already says
pagination there is "the caller's job," by original design. The actual
cost on that page is the one full-history aggregate query needed to
build the grid at all (already isolated into a background job with a
progress bar and an explicit "this runs one query across your full
visit history" note), not the small in-memory slice afterward.
Restructuring the cohort-retention math into SQL-paginated form would
carry real correctness risk (cohort/retention math is easy to get
subtly wrong) for no real scalability benefit, since the row count
doesn't scale with the thing that was actually causing concern
(number of visits/audits/follow-ups).

## High #7 — 0.0.0.0 bind with no compensating controls
## Medium — Session cookie policy not explicitly configured
**Files:** `app.py`, `.env.example`

Everything here is opt-in via environment variable — an operator who
configures nothing gets identical behavior to before (same 0.0.0.0:5050
bind, same cookie behavior modulo the explicit flags below).

- **`BEHIND_TLS_PROXY=1`** — for an operator who puts a reverse proxy in
  front for TLS (Waitress itself never terminates TLS — that's not a
  gap I could "fix" by passing it a certificate, it's a deliberate
  design choice of Waitress's; a proxy in front is the standard way to
  add HTTPS to a Waitress app). When set: enables Werkzeug's `ProxyFix`
  (trusts `X-Forwarded-For`/`-Proto`/`-Host` from exactly one proxy hop)
  and marks the session cookie `Secure`. Left off, `Secure` stays off —
  setting it without TLS would silently break every login, since
  browsers refuse to send `Secure` cookies over plain HTTP.
- **`VETZONE_ALLOWED_NETWORKS`** — optional comma-separated CIDR
  allowlist, enforced in a `before_request` hook, returning a plain 403
  for anything outside it. No-op unless set.
- **`VETZONE_HOST` / `VETZONE_PORT`** — bind address/port now
  configurable instead of hardcoded; default unchanged (`0.0.0.0:5050`).
- **Per-IP login rate limit** — a small in-memory sliding window (20
  attempts / 5 minutes per source IP), independent of and in addition to
  the existing per-username lockout in `auth.py` (which I did not touch —
  that's specifically the Low-severity "spraying across usernames" item,
  which wasn't in your list). No new dependency.
- **Session cookie config**: `HTTPONLY=True`, `SAMESITE=Lax` set
  explicitly (Flask defaults to these already, but the finding was about
  the absence of an *explicit* policy, so now it's visible/intentional
  rather than implicit). `SECURE` tied to `BEHIND_TLS_PROXY` as above.
  **`PERMANENT_SESSION_LIFETIME`** (default 12h, `SESSION_LIFETIME_HOURS`)
  is a real behavior change worth flagging: previously a login session had
  *no* server-enforced expiry at all — only "until the browser drops the
  cookie", which mostly doesn't happen on a front-desk machine left open
  for a shift. `session.permanent = True` is now set at successful login
  so this actually takes effect. Staff will be prompted to log in again
  after 12 hours of a session existing, even mid-shift with the browser
  never closed — configurable, but flagging it since it's the one item
  here that changes day-to-day behavior rather than just adding a option.

Also (small, related, caught while I was in this part of the file):
`_graceful_shutdown()` now calls `dbmod.close_pool()` so pooled
connections close cleanly on shutdown instead of being dropped by
process exit.

New env vars documented in `.env.example`, all commented out (inert
until an operator uncomments and sets them) except the ones with sane
defaults noted inline.

## High #12 + #13 — Billing snapshotting + invalid code rejection
**Files:** `schema_postgres.sql`, `setup.py`, `logic.py`, `app.py`

**The core problem:** revenue/COGS reports re-read *current* Price List /
Inventory Catalog values for every past transaction, so editing today's
prices could retroactively change last month's (or last year's) revenue
report. Separately, a typo'd billing code was silently dropped from an
Automatic bill instead of being rejected, quietly undercharging with no
warning.

**New table `visit_billing_lines`** — Automatic visit billing had no
line-item table at all before this; just a comma-separated `codes`
string on `billing`, re-priced live on every read. `billing.codes` is
kept as-is (still what prefills the edit form), but the actual priced
lines now live in this new table, snapshotted at Save time.

**`logic.price_codes_or_none()`** — validates every code against the
Price List and returns either a fully-priced line list or a rejection
message naming exactly which codes didn't match. `visit_billing_save()`
now calls this *first*, before touching the database at all, and
rejects the whole save on any mismatch — the exact "typo silently
undercharges" behavior this closes. Uses the same matching rule
`billing_lines()` always used (code exists + has a sale_price set — not
filtered by active/inactive, so a since-deactivated code someone still
references doesn't newly break) — only what happens on a miss changed.

**Inpatient billing** — `inpatient_billing` already had a real
line-items table with a price_id FK; it just re-joined `price_list`
live for price/cost on every read. Added `unit_price`/`unit_cost`
columns, populated at `inpatient_billing_add()` time; `inpatient_billing_add`
also now looks the price row up itself (rather than trusting the FK to
catch a bad price_id) so a stale reference gets a clear flash instead of
a raw database error.

**POS/retail** — `sale_items.unit_price` was already snapshotted at sale
time; only `unit_cost` (for COGS) was still live. Added the column,
populated inside the same `SELECT ... FOR UPDATE`-protected block the
Critical #1 fix already added (same point in time everything else about
this sale gets decided).

**`_revenue_and_cogs_by_month()`** rewritten to read the snapshots above
instead of live-joining current catalog values, for all three sources
(visit billing, inpatient billing, retail sales). Each has a fallback to
the old live-lookup behavior *only* for rows that predate this change
(NULL snapshot) — a one-time `backfill_visit_billing_lines()` migration
in `setup.py` (same idempotent style as the FK migration) populates
`visit_billing_lines` for every existing Automatic bill using current
Price List values, so the fallback path is expected to see real use only
once, at upgrade time, not on an ongoing basis.

**Known, deliberate limitation:** refund COGS reversal
(`refund_items` doesn't link back to the specific `sale_items` row it
came from) still values the reversal at *current* inventory cost — this
is a pre-existing approximation, unrelated to the retroactive-price-edit
problem this fix closes, and fixing it properly would mean adding a
`sale_item_id` link to `refund_items`, a bigger schema change than what
was in scope here. Documented in the code, not silently left unexplained.

**Historical data honesty:** the backfill can only snapshot using
*today's* Price List values for old bills — the true historical price at
the original billing time isn't recoverable from what the app stored.
Every bill saved from now on gets a real point-in-time snapshot; old
bills get the best available approximation, which is what the old live
-lookup was already showing anyway (a lateral move for old data, a real
fix for everything going forward).

---

## High #8 — Deliberately NOT done: floating point → Decimal/NUMERIC
**Not implemented this session — flagging why rather than rushing it.**

This is the largest and riskiest item on the original list — bigger than
everything else combined. It touches money/quantity arithmetic scattered
across most of `logic.py` (~1650 lines) and large parts of `app.py`, and
the failure mode isn't a clean error: mixing `Decimal` and `float` in the
same expression raises `TypeError` at the exact line it happens, and
`Decimal` isn't JSON-serializable by Flask's default JSON provider,
so every `jsonify()` call touching a converted field needs checking too.
Doing this properly means:
- Converting `parse_money()` and every other numeric-input parser to
  return `Decimal` instead of `float`.
- Converting the relevant schema columns from `DOUBLE PRECISION` to
  `NUMERIC(p,s)` (psycopg auto-converts `NUMERIC` ↔ `Decimal` on read,
  which is *why* this needs to happen together with the Python-side
  change, not before or after it — a half-converted state is worse than
  the current fully-consistent-float state).
- Auditing every arithmetic expression that touches a converted value,
  including ones several function calls away from where the value was
  read (e.g. `compute_bill_totals()`, `boarding_suggested_total()`,
  the entire `_revenue_and_cogs_by_month()` I just rewrote above).
- Checking every `jsonify()` response and every Jinja money-formatting
  filter for the new type.

Given your explicit instruction to go slow and verify rather than risk a
production bug, I'd rather flag this honestly as unstarted than do a
shallow, partially-verified pass across that much surface area in
whatever budget remains. This deserves its own fully-focused pass,
ideally starting from a fresh read of every money/quantity field in
`schema_postgres.sql` and tracing each one through to every place it's
read, written, and computed with — the same rigor as everything else in
this changelog, just at 5-10x the scope.

## Cleanup — migration scaffolding removed (no production data to migrate)

Per instruction: this deployment has no existing data, so the defensive
"handle pre-existing bad data" machinery added for the FK/snapshot fixes
above was unnecessary complexity. Simplified:

- **`schema_postgres.sql`**: the 4 new foreign keys (payments ×4,
  attachments ×3, `inpatient_cases.visit_id`, `price_list.linked_item_id`),
  the `audit_session_lines` unique constraint, and the `unit_price`/
  `unit_cost` snapshot columns on `inpatient_billing`/`sale_items` are now
  declared directly inline in their original `CREATE TABLE IF NOT EXISTS`
  statements — not bolted on afterward via `ALTER TABLE`. Removed: the
  orphan-cleanup `UPDATE ... SET x = NULL` statements (nothing to clean
  up with no data) and the `audit_session_lines` dedup `DELETE` (nothing
  to dedupe). `visit_billing_lines` (a genuinely new table) is unchanged.
- **`setup.py`**: removed `add_missing_foreign_keys()` /
  `FK_CONSTRAINTS_TO_ADD` and `backfill_visit_billing_lines()` entirely,
  along with their calls in `apply_incremental_migrations()`. The FKs are
  now just part of the base schema; there's nothing to backfill.
- **`logic.py`**: updated a handful of comments that referenced "rows
  predating this column" / "the one-time backfill" to describe what the
  fallback-to-live-lookup paths actually protect against now (a
  snapshot value that's legitimately NULL — e.g. a price_list item with
  no cost_price set — not stale pre-migration data). Also corrected
  `recompute_full_summary()`'s docstring, which had gone stale: it still
  claimed revenue/COGS are "not a value frozen at transaction time",
  which was true before the billing-snapshot fix and isn't anymore.

**Left untouched, deliberately:** `INCREMENTAL_SCHEMA_STATEMENTS` and
`migrate_users_role_to_role_id()` in `setup.py` — these are pre-existing
app conventions (predating this audit entirely, e.g. the `users.role` →
`users.role_id` migration), not something added as part of these fixes,
so they're out of scope for this cleanup.

Note: the fallback-to-live-lookup *logic* in `visit_billing_summary()`,
`inpatient_billing_summary()`, and `_revenue_and_cogs_by_month()` (used
when a snapshot value is NULL) was kept — that's defensive read-time
code protecting against a legitimately-missing snapshot (e.g. an item
with no cost_price set), not a data migration, so it doesn't fall under
"migration script."

## New feature — Consignment
Built per `Consignment_Feature_Framework.md`, incorporating the review
notes from before this build started: `sale_items.unit_cost` (the real
column name, not the speculative `consignment_unit_cost`) used directly
with no live-join TODO; no dependency on a Decimal/NUMERIC migration
(closed as not applicable, see High #8 above) — settlement math uses
plain float + `round(x, 2)`, consistent with the rest of the app; every
new table/column declared inline with `IF NOT EXISTS`, no migration
scaffolding, per the "no data" instruction.

**Schema:** `inventory_list.ownership_type` ('Owned'/'Consignment'),
four new tables (`consignment_receipts`, `consignment_shrinkage`,
`consignment_returns`, `consignment_settlements`), all inline with FKs
— no separate ALTER-table migration.

**Permissions:** `view_consignment`, `manage_consignment_items`,
`manage_consignment_stock` (open to Vet/Reception like everything else
non-admin), `manage_consignment_settlements` (admin-only — a
cash-handling action against a distributor relationship, per the
framework's own recommendation). Settlement viewing is gated behind the
same admin-only permission as recording one, not the broader
`view_consignment` — consistent with how this app already treats
`view_financial_reports` as admin-only.

**Business logic (`logic.py`):** `record_consignment_receipt/shrinkage/return()`
— the latter two use the same `SELECT ... FOR UPDATE` row-locking
pattern as the Critical #1 POS fix, since write-offs and returns have
the identical "can't take stock below zero under concurrent requests"
race a sale does. `consignment_balance()` implements the §7 settlement
formula (residual + units sold − restocked refunds + Clinic-liable
shrinkage, all priced at snapshot-time cost, not a live catalog join).
`consignment_sales_by_distributor()`, `consignment_distributors_overview()`,
`consignment_item_locked()` (an item's distributor becomes fixed once
it has any receipt/sale/shrinkage/return against it — a supply-source
change means a new inventory_list row, not re-pointing this one).

**§10 audit integration:** `audit_session_confirm()` now checks, right
before the confirming UPDATE (so "expected" still reflects the prior
baseline, not this confirm's own numbers), whether any Consignment
item's counted stock came in under expected — surfaced as a flash
message pointing to Shrinkage, kept within this app's existing
flash-only conventions rather than inventing new session state.
Non-blocking: a shortfall never prevents confirming, only nudges.

**Routes/templates:** 16 new routes in `app.py`, 7 new templates, plus
a Consignment nav group in `base.html` and small "consignment" badges
on Inventory Status and the Audit session view (both read `inventory_list
.ownership_type`, which `inventory_status()` now also returns).
Settlement amount is recomputed server-side at submit time — never
trusted from a hidden form field, since the balance can move between
when the settlement page was opened and when it's submitted.

**Caught and fixed while building, before it shipped:** the PDF export
route/function initially didn't match this codebase's actual
conventions — used `Response` (not imported) instead of `send_file`
with an in-memory buffer, and took a pre-fetched dict instead of
`(db, id)` like every other `export_*` function in `pdf_export.py`.
Also referenced a `distributors.contact_info` column that doesn't
exist (real columns are `contact_person`/`phone`). Also caught that
`data-confirm` only works on `<form>` elements (this app's JS handler
specifically listens for it there), not on a `<button>` — one template
had it in the wrong place initially.

**Verification performed:** full `py_compile` across every Python file
touched or added; full Jinja `env.parse()` across every template in the
project (not just the new ones — a regression check); cross-referenced
every `url_for()` call in the new/edited templates against every
`def` in `app.py` to confirm no broken endpoint references; confirmed
every route's `render_template()` call passes exactly the variables its
template consumes. As with the security-fix work earlier, this was all
static/structural verification — no live Postgres available in this
environment, so **the QA checklist should be extended to cover this
feature before it reaches staging** (not yet done in this session).

## Executed: Billing Redesign (Option C — search + editable cart)
Per `Billing_Redesign_Framework.md`, executed in full:
- Schema: `visit_billing_lines.quantity` added, `billing.codes` dropped.
- `logic.py`: `billing_lines()`/`price_codes_or_none()` deleted;
  `save_visit_billing_lines()` extended with quantity;
  `visit_billing_summary()` rewritten (no codes fallback, no
  `code_check`, lines now carry `quantity`/`line_total`);
  `_revenue_and_cogs_by_month()`'s legacy fallback removed.
- **Fixed while executing** (not in the doc's own scope, but the same
  class of gap): `revenue_by_category()` and `vet_performance()` were
  still reading `billing.codes` live via `string_to_array` — rewired
  both to `visit_billing_lines` per the doc's §4. While in
  `revenue_by_category()`, also fixed its `inpatient_lines` CTE, which
  was still live-joining `price_list.sale_price` instead of the
  `unit_price`/`unit_cost` snapshot added earlier — same underlying bug,
  same function, not previously caught.
- `app.py`: new `/api/price-list/lookup`; `visit_billing_save` rewritten
  to match `inpatient_billing_add`'s validate-per-item pattern (kept an
  "at least one item" rejection to preserve the old empty-bill-reject
  behavior); `proc_items` query removed from `inpatient_detail`.
- Templates: `visit_detail.html` and `inpatient_detail.html` both got
  search+cart UIs reusing `pos.html`'s fetch/debounce/cart pattern.
  Caught and fixed: the visit-billing cart prefill (from
  `summary.lines`) needed to be guarded to Automatic-only — unguarded,
  it would have injected a bogus `id: null` line into the cart on a
  Manual bill's page load.
- Verified: full `py_compile`, full Jinja parse (project-wide), grepped
  for every dead reference the doc's own checklist calls for (all
  clean), traced `pdf_export.py`'s actual field usage to confirm the
  doc's "no changes needed" claim was correct.

## Executed: Distributor Ledger
Per `Distributor_Ledger_Framework.md`, executed in full, applying the
three fixes identified in the earlier review before writing anything:
- **`| fmt_money` → `| money`** throughout (the doc's filter name
  doesn't exist in this app — would have crashed on first render).
- **`badge success` → `badge ok`** (matches this app's actual status
  badge convention everywhere else).
- **Added `abort` to the Flask import** in `app.py` — it was used
  (pre-existing, in `_role_or_404()`) but never imported; this doc's new
  `distributor_detail()` route would have inherited the same latent
  `NameError` otherwise.
- Also substituted the doc's proposed new `parse_amount()` helper for
  the existing `parse_money(raw, required=True)` — already the
  established pattern used everywhere else in this app (including every
  route I've added), so no duplicate helper was created.
- Also used `datetime.now().isoformat(timespec="seconds")` in place of
  the doc's `datetime.utcnow().isoformat()`, matching this codebase's
  one consistent timestamp convention.
- Schema: `distributor_bills` / `distributor_bill_payments`, inline in
  the Distributors section of `schema_postgres.sql`, as specified.
- `logic.py`: `distributor_bill_balance`, `distributor_ledger`,
  `distributor_outstanding_totals`, `distributor_payables_summary`.
- `app.py`: 6 new routes (detail, bill create/delete, payment
  create/delete, PDF export), all gated on `manage_distributors` per
  spec (no new permission row). `distributors_list()` now passes
  `outstanding` + `payables`.
- `pdf_export.py`: `export_distributor_ledger()`.
- Templates: new `distributor_detail.html`; `distributors.html` gained
  an Outstanding column, a Ledger link per row, and the payables summary
  block (stat-grid + "Who You Owe Most" table) above the search form.
- Verified: full `py_compile`, full Jinja parse (project-wide),
  confirmed zero remaining `fmt_money`/`badge success` occurrences
  anywhere in the templates directory, cross-referenced every
  `url_for()` in the two touched/new templates against `app.py`,
  checked for duplicate route function names (none). Schema
  re-verified against the statement-splitter (80 clean statements).

Both features are additive per their own specs — neither touches POS,
Sales, Refunds, or any existing financial report beyond what each
document explicitly called out (the Billing Redesign's two report
rewires).
