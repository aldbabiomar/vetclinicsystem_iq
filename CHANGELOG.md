# Changelog

All notable changes to VetClinicSystem IQ are documented in this file, in
[Keep a Changelog](https://keepachangelog.com) style.

## [1.7.5] - 2026-08-24

### Fixed
- On a phone, a table's sticky column headings sat hidden behind the top
  bar while scrolling a long list. They now sit just below it.

## [1.7.4] - 2026-08-24

### Fixed
- Hardened how the database password is handed to the backup tools on
  Docker-based installs, so it is passed privately rather than in a way
  other users of the same computer could read.

## [1.7.3] - 2026-08-24

### Fixed
- **Backups could appear to hang forever.** The backup was actually
  waiting for a database password to be typed into the black Terminal
  window behind the app — easy to miss entirely, and the password it
  wanted was the database's, not your login. Backups and restores now
  use the password the app already has, and if a password is ever wrong
  they stop straight away with a clear message instead of waiting.
  This affected the nightly automatic backup and the backup taken
  before an update too, not just the Back Up Now button.
- **Back Up Now no longer pretends to start when no backup folder is
  set.** The button stays disabled until you've chosen and saved a
  folder, and tells you so, instead of running a progress bar and then
  reporting a failure. That case also no longer clutters Recent Backups
  with failed entries.

## [1.7.2] - 2026-08-24

### Fixed
- The Browse-for-a-folder window's buttons were scattered across two
  uneven rows. The folder-name box and all the buttons now sit neatly on
  one line, lined up with the folder list above them — and on a phone or
  narrow window they stack, with Cancel and Select centred underneath.
- Pop-up windows could be wider than the screen on a phone, pushing their
  buttons out of reach. They now always fit.

## [1.7.1] - 2026-08-24

### Fixed
- Buttons that warn before something destructive (Restore Now, and others
  like it) turned a slightly-off colour when hovered — one that didn't
  belong to VetClinicSystem IQ's own palette. They now darken correctly. The same
  fix cleans up a handful of other places where a stray colour had been
  hardcoded instead of following the app's palette, including a grooming label on the Appointments grid that showed the wrong text colour under the ChamPet theme.

## [1.7.0] - 2026-08-24

### Added
- **A VetClinicSystem IQ icon on the Desktop.** Double-click it to start
  the app — and if the app is already running, it just brings it up in
  your browser instead of starting a second copy. It keeps working after
  updates, shutdowns and restarts, so it's there as a reliable way in if
  "start automatically when this computer starts" ever doesn't fire. It's
  created for you during setup; if it ever gets deleted, running setup
  again puts it back.

## [1.6.1] - 2026-08-24

### Fixed
- "Start automatically when this computer starts" could point at the
  wrong copy of the app on installs with automatic updates enabled — it
  would keep launching whatever version was installed at the time you
  turned the toggle on, ignoring later updates until the app was started
  by hand at least once. It now always finds and uses the correct,
  currently-active version on every restart.

## [1.6.0] - 2026-08-24

### Added
- **Clean Up** — a small, capped amount you can apply to a visit,
  inpatient, or boarding bill (or a POS sale) to round off or write down
  the total, instead of forcing every bill to land on an exact figure.
  Shows on the bill, the printed receipt/PDF, and is accounted for
  correctly if the sale is later refunded.

### Fixed
- Several forms could still be submitted with a required field left
  blank (owner/patient name, price list/inventory item name, appointment
  details) without a clear error — now rejected with a specific message
  instead of a confusing failure later on.
- A visit's Body Condition Score, and quantities/amounts on Point of
  Sale, refunds, and inpatient billing, are now checked against sane
  bounds before saving, instead of accepting anything typed in.
- Marking a visit "Admitted to Inpatient" now reliably creates the
  matching inpatient case (and the reverse — you can't move a visit off
  that status while its inpatient case is still open).
- A handful of pages could occasionally crash with a server error
  instead of showing a normal message — creating/editing price list or
  inventory items with a distributor or linked item that no longer
  exists, deleting a role or disabling a user whose upcoming appointments
  would be left stranded, and a few others. These now either fail
  cleanly with an explanation or, where it makes sense, warn you and let
  you continue.
- Deactivated inventory items no longer disappear from an audit session
  that already referenced them.
- A discount can no longer be applied to a visit before its bill has
  been saved.
- Deleting an inpatient billing line, or applying a discount, can no
  longer push a bill below what's already been paid on it.
- A refund is now required to reference exactly one visit or one
  inpatient case — never both, never neither.
- New Draft audit sessions can be discarded, and can no longer be
  confirmed with nothing actually counted.
- Attached files, payments, and refunds are now guaranteed at the
  database level to reference exactly one thing, closing a class of
  bug where a bad or incomplete request could leave one referencing
  nothing (or everything at once).
- If the app is closed or crashes mid-restore, Settings now shows a
  clear warning instead of silently leaving the database in an unknown
  state.
- Backup/restore/update no longer silently overlap with each other if
  triggered close together; a stale "running" backup left over from a
  crash is now automatically cleared on the next startup instead of
  blocking new ones forever.
- A single bad row created by very old data no longer prevents *every*
  routine database update from applying on startup — only that one
  update is skipped (and flagged on the Dashboard for an admin to look
  at), the rest still apply normally.

## [1.5.2] - 2026-08-24

### Fixed
- **A mistake in a form (an invalid phone number, a bad date) used to
  wipe out everything else you'd typed and bounce you back to a blank
  page.** Forms now show exactly what you entered, with the problem
  field flagged, so you only need to fix the one thing — across Log
  Visit, Owners, Distributors, Boarding, Appointments, Inpatient Cases,
  billing/discount/payment, Price List, Inventory Catalog, Audit
  History, and Reports.
- Phone numbers are now checked as you type, before you submit, instead
  of only after a failed save.
- Fixed a bug where logging a new visit for a brand-new owner could
  leave a duplicate patient behind if the visit's own date/weight/BCS
  failed validation after the owner and pet had already been saved.

## [1.5.1] - 2026-08-23

### Fixed
- **Auto-generated inventory barcodes were 12 digits, not real EAN-13's
  13** — one digit short in the random body, so every generated barcode
  failed strict EAN-13 validation. Now generates the correct length;
  already-generated barcodes are unaffected and keep printing normally.
- **A visit's attachment folder was named with a doubled prefix**
  (`VV0042` instead of `V0042`), contradicting this app's own documented
  folder-naming convention. New attachments now use the correct single
  prefix; `reconcile_attachments.py` updated to match.

## [1.5.0] - 2026-08-23

### Fixed
- **POS checkout could oversell stock under genuine concurrent load** — the row lock that serializes concurrent checkouts was sound, but the stock-since-last-audit calculation compared whole-second-precision timestamps with a strict `>`; a sale landing in the same wall-clock second as the audit it was being checked against got silently excluded from the running total, letting stock go negative while the Inventory Status page itself still reported a plausible (wrong) number. Every timestamp feeding that comparison now carries microsecond precision.
- **Re-entering an existing owner's name and phone while adding a pet created a duplicate owner record** instead of linking to the existing one, both from the "new patient" visit form and from double-submitting the New Owner form. Owner phone numbers are now enforced unique at the database level; a submission that collides with an existing owner links to them instead of erroring or duplicating.
- **Double-clicking "Complete Sale" on an unchanged cart created two separate, fully valid sales** — double-charging the customer and double-deducting stock, with no confirmation prompt either side. Checkout now carries a one-time token per POS page load; a repeat submission is recognized and sent to the original sale instead of creating another one.
- **A `%00`-encoded null byte in a GET query parameter bypassed the null-byte input guard** (it checked raw query bytes and POST form fields, but not decoded query parameters), reaching the database and surfacing as a raw error page instead of a clean rejection.
- **A database outage could occasionally show a raw, unbranded error page** instead of the app's own error page, in the narrow window right as the connection dropped — traced to the per-request cleanup step trying to commit/roll back an already-dead connection outside the app's normal error handling. Now guarded, and each request also fails faster during an outage instead of hanging for the full connection-pool timeout.

## [1.4.7] - 2026-08-23

### Fixed
- **POS checkout accepted cash below the sale total and marked it fully paid regardless** — a cashier could complete a sale having collected far less than owed, with no error and no record of the shortfall. Now rejected until the full amount is collected.
- **Service refunds had no cap against what was actually paid** — any amount could be refunded against any visit or inpatient case, including one with zero payments on it (retail/POS refunds were already correctly capped; this closes the same gap on the service side), with a row lock closing the same race between two concurrent refunds.
- **Bill rounding used banker's rounding, not half-up** — a bill of exactly 125 IQD rounded to 0 ("free"); other exact-half amounts rounded inconsistently depending on which side happened to be an even multiple. Fixed to always round up on a tie, and closed a boundary gap that let a 125 IQD bill slip past the "never present a real charge as free" floor. Retail refunds now round down instead of nearest, so a refund can never exceed what the returned items add up to.
- **Visit/inpatient payments, consignment settlements, and cash-register payouts all allowed unlimited overpayment** — only checked the amount was positive, unlike boarding payments (and distributor bill payments, fixed earlier this cycle), which already capped correctly. All four now capped against their live balance, with a row lock closing the same race.
- **Inpatient billing never re-checked a standing discount against non-discountable items** — unlike visit billing, which already re-validates on every save, a discount could be applied to an inpatient case and then a non-discountable procedure added afterward with zero resistance. Now matches visit billing's protection.
- **Account lockout was sliding, not fixed-length** — a single new failed login every few minutes kept re-arming the same 15-minute lock indefinitely, letting an attacker permanently lock out any known username (including `admin`, documented in the README) at negligible cost. Now escalates per fresh lockout episode (15/30/60/120 minutes, capped at 4 hours) and resets on a real successful login.
- **A password change or admin reset didn't invalidate that account's other active sessions** — a stolen session cookie kept working for up to 12 hours after the password changed, including right after an admin reset a suspected-compromised account. Now stamped and checked on every request.
- Login didn't clear pre-authentication session state before establishing the authenticated session (minor hardening; Flask's signed-cookie sessions make this hard to actually exploit).
- A user forced to change their password who clicked **Logout** was redirected back to Change Password instead of actually logging out.
- The in-app updater's release-tarball extraction had no member filtering; added Python's built-in `filter="data"` safety net (falls back cleanly on Python <3.12).
- Backup `.dump` files (which contain full patient/owner records) were written at the process's default umask, potentially group/world-readable — now locked to owner-only immediately after each backup.
- **A real self-update would have silently orphaned every existing patient attachment** (X-rays, bloodwork, test results) and reset the error log — both were anchored to the current release folder instead of the persistent data directory, so the very first update after enabling the versioned-release layout would have left uploads unreachable and logging discontinuous. Found via a cross-check against the sibling deployment's port of this same update mechanism.
- The Settings folder browser inserted server folder/file names into the page without full escaping — rebuilt to use safe DOM construction instead of string-built HTML.
- Flask's debug server (opt-in via an env var, not used in normal operation) bound to every device on the network instead of just this machine.
- Added a baseline Content-Security-Policy header.
- An oversized `?page=` value on any list page, or a null byte anywhere in a request, surfaced as a raw, unhandled error page instead of a clean response.
- Sales History's date filter was the one place that skipped validation before filtering — brought in line with Visits and Refunds, which already validated correctly.
- Removed several confirmed-dead functions and a stale legacy constant (zero call sites each, verified via repo-wide search) and corrected two misleading code comments.

## [1.4.6] - 2026-08-22

### Fixed
- The Dashboard's "Missed Items" review panel and its operating-costs/backup-alert
  banners were still gated on the role literally being named "Admin," even though the
  page had already been switched to checking real permissions instead. A custom role
  granted the right permissions (e.g. a "Practice Manager" role with `manage_settings`)
  never saw these panels at all, including backup-failure alerts.
- A patient's "Full History" page silently omitted boarding stays — it only pulled
  from visits and inpatient cases, even though boarding is tracked as its own record
  type with its own dates and billing.
- Booking a grooming appointment didn't force its resource ID to blank, so a crafted
  request could silently double- (or many-times-) book a grooming slot in a way that
  never appeared on the schedule grid and wasn't caught by the "needs attention"
  fallback list either. Vet appointments now also validate the vet and time slot are
  real before booking, instead of trusting whatever the form submitted.
- Boarding admission/edit accepted a negative price-per-day or total with no guard,
  which could silently reduce or negate a month's reported revenue.
- Boarding payments had no cap against the outstanding balance and no lock — unlike
  every other payment-entry point in the app, there's also no way to delete or correct
  a boarding payment once recorded, so an overpayment here was permanent.
- Two inventory barcode routes (manual set, generate) didn't handle the same
  duplicate-barcode race window already guarded against elsewhere in the app —
  a concurrent collision surfaced a generic error page instead of the intended
  friendly "already in use" message.
- Login now takes the same amount of time whether or not the submitted username
  exists, closing a timing side-channel that could be used to enumerate valid
  usernames.

## [1.4.5] - 2026-08-22

### Fixed
- **Refunding a discounted POS sale refunded the pre-discount price, not what the
  customer actually paid.** Checkout only ever applied the sale's discount to the
  overall total, never to each item's stored unit price — so refunding any item from a
  discounted sale handed back more money than the sale collected, every time, silently.
- A discount applied to a visit's bill wasn't re-checked against items added to that
  bill afterward — so an item explicitly marked "not discountable" could still end up
  discounted, just by adding it after the discount instead of before.
- Saving a visit's billing or discount for the first time had a narrow race: two
  near-simultaneous saves (double-click, a retried request) could both try to create
  the bill row and one would crash instead of saving.
- Three internal lookup endpoints (patient search, inventory lookup, price list
  lookup) had no permission check of their own — reachable by any logged-in user
  regardless of their role's actual permissions, even a role deliberately restricted
  from seeing owner contact info or pricing.
- Backup, restore, and in-app update/rollback could all run concurrently with each
  other — a manual restore triggered at the same moment as the nightly scheduled
  backup (or another admin action) had no guard stopping two database-level
  operations from touching the same tables at once. Now mutually exclusive.
- A handful of routes (follow-up/wellness/grooming status updates, an inpatient
  attachment upload, an admin password reset) crashed instead of showing a clean
  error when given a nonexistent record ID.
- The Operating Costs form on Reports didn't validate the month value server-side.

## [1.4.4] - 2026-08-22

### Fixed
- **Inventory Status was double-counting same-day sales against the count that already
  included them.** It compared transactions to the *date* of the last audit, not the
  *moment* it was confirmed — so a completely normal same-day workflow (sell all
  morning, do the physical shelf count in the afternoon) would subtract the morning's
  sales a second time on top of a stock_counted figure that already reflected them.
  This had been silently wrong since the audit feature shipped, cascading into false
  LOW STOCK flags, wrong Ordering Sheet priorities, wrongly-blocked consignment
  shrinkage/return entries, and false shortfall warnings on the next audit's confirm.
  Now compares against the audit's actual confirmation timestamp.
- Picking up a boarding stay (dismiss) locked in the real final total but never told
  the monthly P&L cache about it — that month's revenue stayed stuck at whatever
  placeholder total existed when the stay began, permanently understating it until
  something unrelated happened to touch the same month.
- Confirming an audit session with consignment items re-ran the full inventory status
  computation once per counted item instead of once total — a Confirm click on a
  large audit could mean the catalog-wide status query running dozens of times over.
- A distributor bill payment could be entered for more than the bill's remaining
  balance, and two near-simultaneous submissions (double-click, a retried request)
  could both record a payment before either was accounted for by the other.
- Two near-simultaneous consignment settlement submissions could both compute a
  balance against the same "last settlement so far" and both post — settling
  (and appearing to pay out) the same batch of sales twice.
- A Price List row could be linked to an inventory item that was already linked from
  another active row, silently making pricing nondeterministic for that item
  depending on which row happened to be read. Blocked on create, edit, and bulk edit
  (bulk edit also checks for two rows in the same batch claiming the same item).
  Editing a Price List row that no longer existed also crashed instead of showing
  a clean error.
- Phone number entry accepted implausibly short input and silently mis-normalized a
  foreign number typed without its country code into a fabricated local number,
  instead of rejecting either as invalid.

## [1.4.3] - 2026-08-22

### Added
- Appointments now has a "need attention" list for bookings that stopped
  matching anything on the day grid — a vet was deactivated, or the
  scheduling hours/slot length changed since the appointment was booked.
  These were still valid rows in the database but had no UI path to find
  or cancel them; this list is the guaranteed fallback regardless of
  what caused the mismatch, with a Cancel action right on it. Deactivating
  a vet or changing the scheduling settings now also warns immediately if
  it just orphaned any upcoming bookings.
- Inpatient Cases has a new "Balance Due" filter: discharged cases that
  still owe money (e.g. a procedure billed after the patient already went
  home). Previously nothing ever resurfaced a case like this for
  collection once it dropped off the default admitted-only view.

## [1.4.2] - 2026-08-22

### Fixed
- Visits, Refunds, and Cash Register all crashed (500 error) if their
  date filter was ever malformed — now shows a clean "that date wasn't
  valid" message instead. Same fix applied to the two new Cash Register
  write actions (Pay From Register, Perform Audit).
- Six PDF export routes (patient file, patient billing, sale receipt,
  visit, inpatient, boarding) crashed instead of a clean "not found" if
  the record no longer existed by the time the export ran. The Patient
  Billing History PDF also showed money as "150000.00" instead of
  "150,000" like every other export and the app itself — now consistent.
- Editing a boarding stay after it was already picked up could silently
  recalculate and overwrite the final billed total — the record was
  never actually locked despite the code's own stated intent. Dates,
  price, and total now stay locked once picked up; room, admitted items,
  and special needs stay editable for ordinary corrections.
- Restoring a database backup never reconciled the restored database
  against the schema this app version actually expects — a backup taken
  before a schema change (or a permission grant) landed would leave
  things broken until the next unrelated update happened to fix it.
  Restore now re-applies the same schema sync every update already runs.
- The in-app updater's release pointer file was written directly rather
  than atomically — a process killed at the exact wrong moment could
  leave it corrupted. Now written to a temp file and swapped in atomically.
- Follow-Ups and Wellness Reminders (including the "Missed Items" list on
  the Dashboard) were sorted oldest-first; swept the rest of the app for
  the same pattern and found no other instances. All three now show the
  most recent item first, matching every other list in the app.
- Newly-enabled grooming requests (toggling "Grooming?" to Yes while
  editing an existing visit) were saved with no status at all, unlike a
  brand-new visit's grooming request, which always starts at "Waiting".
- The Follow-Ups status dropdown was missing "N/A" as an option, so a
  visit in that state displayed as "Pending" in the dropdown even though
  that wasn't what was actually stored.
- Dashboard's "Missed Items" header had no gap above it, unlike every
  other section on the page.
- Boarding's list page recomputed each row's billing status with 2-3
  extra queries per row (up to ~150 extra queries for a full page) — one
  of them re-fetching data the page already had in hand. Now batched
  into 2 queries total for the whole page.

## [1.4.1] - 2026-08-22

### Added
- Sticky table headers on every paginated list in the app (and the
  Retention cohort grid) — the header row now stays pinned in view while
  you scroll through a long page of results, instead of scrolling away
  with the rest of the table.
- Distributor bill payments and consignment settlement payments now use
  the same Cash/Card/Transfer dropdown as every other payment method
  field in the app, instead of free text. Visit, Boarding, and Inpatient
  payments already used this dropdown and were left as-is.

### Fixed
- The "Grooming" badge on Visits wrapped mid-word ("Groomin"/"g") in a
  column that was simply too narrow for it and the visit type text
  together; rebalanced that table's column widths and gave the badge its
  own line instead of letting it break apart. Swept every other table in
  the app against the 25-year test dataset for the same pattern — this
  was the only one affected.
- Cash Register's "Last audited…" note was rendering with a negative top
  margin left over from a copy-pasted style, sitting behind the totals
  table instead of clearly below it.

## [1.4.0] - 2026-08-22

### Added
- Cash Register: a new page unifying every place money actually changes
  hands on a given day — POS sales, Visit/Inpatient/Boarding payments,
  and refunds (netted as negative) — for end-of-day cash-up against
  what's physically in the till. Shows Cash/Card/Transfer/All totals for
  the day, plus:
  - **Pay From Cash Register** — logs manual cash leaving the till for a
    reason that isn't a refund (petty cash, paying a supplier directly
    out of the drawer).
  - **Perform Audit** — compares the system's Cash total against what
    staff actually counted, and permanently records the result
    (Deficit/Surplus/Perfect) as an immutable historical entry; a later
    re-audit of the same day adds a new record rather than overwriting
    the old one.
  - Integrated into Insights as a new "Cash Register Health" section —
    the last 30 days' status at a glance, including days nobody ever
    audited, so poor documentation (or worse) doesn't hide in a gap.
  - Refunds now record how the money was actually handed back (Cash /
    Card / Transfer) — needed to net refunds against the right bucket in
    the day's totals; shown as a new Method column on the Refunds page.
  - New "Manage Cash Register" permission, off by default for existing
    installs' Admin role until this update grants it once.

### Changed
- Unified "Bank Transfer" and "Transfer" — an old, inconsistent label
  that had crept into a few free-text payment-method fields (and,
  briefly, POS sales) — down to the one label the app has always
  actually used: "Transfer". Existing data is normalized automatically
  on update.

### Fixed
- 4 more delete routes (distributor, distributor bill, distributor bill
  payment, inpatient billing line) could log a "delete" audit entry even
  when nothing was actually deleted (an already-gone or invalid id) —
  found during a sweep prompted by the same issue fixed in three other
  routes last release. All now confirm the record exists first.

### Removed
- The Sales History end-of-day totals row added in 1.3.0 — superseded by
  Cash Register, which does the same job correctly across every type of
  sale, not just POS.

## [1.3.0] - 2026-08-21

### Added
- Bulk Barcode Print (Inventory Catalog): prints every Vetzone-created
  barcode at once instead of one at a time. Only shows up when at least
  one item has a created (not scanned/manual) barcode; lets you set how
  many copies each item needs and drop any you don't want before
  printing a single sheet.
- Sales History now shows a Cash / Card / Bank Transfer / All-Methods
  end-of-day tally whenever a date filter is applied — meant for closing
  out the register and reconciling against what's actually on hand.
- Pagination (50/page, matching the rest of the app) added to
  Consignment Items and Consignment Sales by Distributor — audited every
  other page in the app for the same need; everything else already
  paginates or is naturally small (catalog/staff/distributor-count-sized,
  not transaction-log-sized).

### Fixed
- The barcode label box had a fixed pixel width narrower than what
  JsBarcode actually renders, so the barcode overflowed past its own
  dashed border. The box now sizes to its content instead.
- Two refund routes recorded the 250-IQD-rounded amount in the database
  but showed the customer/staff the un-rounded figure in the success
  message — up to 125 IQD apart from what was actually saved.
- Three payment-recording routes (visit, boarding, inpatient) logged the
  audit entry against the parent record's id instead of the payment's
  own id, making individual payments indistinguishable from each other
  in Admin > Logins and Changes.
- Closed 7 gaps found in an audit-logging sweep of every state-changing
  route in the app: attachment uploads (visit + inpatient), a second
  unlogged field-update during inpatient admission, self-service
  password changes, starting an inventory audit session, boarding
  incident reports, and appointment booking/cancellation. All now write
  to the audit trail like every other action in the app.

## [1.2.1] - 2026-08-21

### Fixed
- A distributor's owed balance could include sales that happened before
  an item was ever flagged Consignment. This was most severe for a
  brand-new distributor relationship (no receiving logged yet): flagging
  an item that used to be Retail with years of sales history would
  immediately show the distributor owed for every sale that item had
  ever had, none of which were actually theirs. Inventory items now
  record when they most recently became Consignment
  (`inventory_list.consignment_since`), and balance calculations floor
  their sales/refund scan at that date per item, on top of the existing
  distributor-level floor. Verified against the 25-year synthetic
  dataset: a newly-flagged item with 3,572 historical sales (267M IQD)
  now correctly shows 0 owed until it actually sells again as
  Consignment; an existing distributor's other legitimate Consignment
  items are unaffected.

## [1.2.0] - 2026-08-21

### Added
- Consignment Items now uses the same bulk-edit-and-save pattern as
  Inventory Catalog's Track Expiry column: check "Consignment?" and pick a
  distributor for as many items as needed, then save them all at once,
  instead of flagging one item at a time through a separate button. Comes
  with the same unsaved-changes safeguards (dirty-row highlighting, a
  save/discard/keep-editing prompt on navigating away).
- Consignment Overview now shows the same step-by-step loading screen as
  Insights while it computes distributor balances, instead of leaving the
  page blank.

### Fixed
- An item that had ever appeared in a sale was permanently blocked from
  being flagged as Consignment, even if it was never actually Consignment
  at the time of those sales. On real data this affected effectively every
  actively-sold item, silently breaking the flagging feature. The lock now
  only applies to items that are currently Consignment and have sold while
  Consignment.
- Consignment Overview recomputed full inventory status once per
  distributor instead of once total, making it far slower than it needed
  to be as the catalog and distributor list grew.
- "Track Expiry" header on Inventory Catalog wrapped awkwardly (the "y"
  landing on its own line); the ID column could wrap mid-value too.

## [1.1.2] - 2026-08-21

### Fixed
- The "Update Now" / "Rollback to Previous Version" confirmations on
  Settings used the browser's plain native confirm dialog instead of the
  app's own styled one. Audited every other popup in the app — everything
  else already used the styled dialog or modal system consistently; these
  were the only ones left over from when Updates was first built.

## [1.1.1] - 2026-08-21

### Fixed
- The "Updates" section header on Settings sat flush against the "Save
  Settings" button above it, with none of the spacing every other
  section header on that page has.

## [1.1.0] - 2026-08-21

### Changed
- In-app updates (Settings → Updates) are now on by default. Running
  `Start Vetzone.command` / `Start Vetzone.bat` (or `python3 setup.py`)
  for the first time now automatically switches the install onto the
  versioned-release layout the updater needs — what used to require a
  separate manual `setup.py --enable-updates` step. The launcher scripts
  hand off to the real one under `vetzone-data/` from then on. A plain
  local checkout that wants to keep running in place (e.g. for
  development) can pass `--no-enable-updates` to opt out.

## [1.0.1] - 2026-08-21

### Fixed
- Insights crashed on open (`only '%s', '%b', '%t' are allowed as
  placeholders, got '%)'`) — a stray `%` inside a SQL comment tripped up
  the database driver's placeholder parser even though it was never part
  of an actual query.

## [1.0.0] - 2026-08-21

### Added
- In-app update checker (Settings → Updates) that pulls tagged GitHub
  Releases, backs up the database first, and rolls back automatically if
  a new version fails its health check.
- Cash Received / Change Due fields on the POS checkout screen.
- A heads-up when a Price List entry isn't a multiple of 250 IQD.

### Changed
- Bill totals, balances, refunds, boarding/inpatient totals, and
  consignment settlement payouts now round to the nearest 250 IQD note —
  the smallest banknote in circulation — instead of showing unpayable
  fractional amounts.
- Revenue reports now read the same rounded, final total shown on the
  receipt instead of recomputing it, so reports and receipts always
  agree to the dinar.
- `is_system`, `is_vet_role`, `active`, `must_change_password`,
  `can_discount`, `track_expiry`, `special_needs`, `dismissed`,
  `restocked`, and `liability_overridden` are now native boolean columns
  instead of 0/1 integers.
- Retail refunds are now linked to the original sale: the amount refunded
  matches what was actually charged, refunding more than was sold (or
  already refunded) is blocked, and refunding an item never sold is no
  longer possible.
- Boarding totals for a stay still in progress are now computed live from
  price-per-day × nights so far, instead of staying frozen at the
  1-night estimate made at check-in.
- Editing a visit, boarding session, or inpatient case now warns if
  someone else saved changes to it first, instead of silently
  overwriting their edit.
- Minimum password length raised from 6 to 8 characters.
- The "not a multiple of 250" price warning, negative-value checks on
  prices/weights/unit costs, and rejecting a fractional Body Condition
  Score are all new; `distributor_delete()` now explains what's still
  linked instead of crashing.

### Fixed
- `schema_postgres.sql` could not be applied to a genuinely empty
  database (`price_list`/`payments` referenced tables not yet created).
- `parse_money()` accepted `NaN`/`Infinity`, which silently defeated
  every downstream bound check that compares against it.
