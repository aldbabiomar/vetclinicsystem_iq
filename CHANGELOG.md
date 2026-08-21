# Changelog

All notable changes to Vetzone IQ are documented in this file, in
[Keep a Changelog](https://keepachangelog.com) style.

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
