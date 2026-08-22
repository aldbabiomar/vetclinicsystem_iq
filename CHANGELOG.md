# Changelog

All notable changes to Vetzone IQ are documented in this file, in
[Keep a Changelog](https://keepachangelog.com) style.

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
