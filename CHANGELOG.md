# Changelog

All notable changes to Vetzone IQ are documented in this file, in
[Keep a Changelog](https://keepachangelog.com) style.

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
