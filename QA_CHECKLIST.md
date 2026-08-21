# Manual QA Checklist — run in staging before production

I don't have network access or a live PostgreSQL instance in the
environment I worked in, so everything below was verified by reading the
actual code and tracing every affected call site by hand — not by
running the app end-to-end. Please run this checklist against a staging
copy (ideally seeded from a recent prod backup) before deploying.

## 1. Startup / migration
- [ ] Fresh install: `python setup.py` (or however you normally bootstrap)
      completes without error against an empty database.
- [ ] Upgrade path: run against a copy of your **actual current production
      database** (this is the important one — fresh-install always works,
      upgrade-in-place is where migrations bite). Confirm:
  - [ ] No errors from the new `ADD CONSTRAINT` / FK additions
        (`setup.py: add_missing_foreign_keys`). If this *does* error, it
        means there's real orphaned data the defensive `UPDATE ... SET
        x = NULL` cleanup in `schema_postgres.sql` didn't catch — check
        the error for which constraint failed.
  - [ ] `visit_billing_lines` gets backfilled for existing Automatic
        bills (watch the startup log for "Backfilled visit_billing_lines
        for N existing...").

## 2. POS oversell fix (Critical #1)
- [ ] Normal single-user checkout still works, stock decrements correctly.
- [ ] Try to sell more than current stock — still blocked with the same
      message as before.
- [ ] **The actual race**: from two browser sessions (or two terminals
      hitting `/pos/checkout` with curl), submit two simultaneous
      checkouts for the same low-stock item where each individually
      would be fine but together would oversell. Confirm one succeeds and
      the other is correctly blocked (or both succeed only if combined
      quantity is actually in stock).

## 3. Restore path confinement (Critical #3)
- [ ] A real backup created via "Backup Now" still restores successfully
      end to end.
- [ ] Attempting to restore a `.dump` file that exists on disk but is
      **not** in `backup_log` (e.g. copy a valid backup file to a new
      name) is rejected with the "not in this app's own backup history"
      message.
- [ ] Attempting a path outside the configured backup folder (if your
      browser widget lets you type/paste one) is rejected.

## 4. Attachments (High #9)
- [ ] Normal upload/download/delete still works for both visit and
      inpatient attachments.
- [ ] Simulate a disk-full or permission-denied condition during upload
      (e.g. temporarily `chmod 000` the uploads folder) — confirm no
      orphan DB row is created, and the user gets a clear error.

## 5. Audit log atomicity (High #17)
- [ ] Spot check a handful of routes (visit edit, role edit, price list
      edit, attachment delete) — confirm the Admin Log still shows an
      entry for each action, with correct before/after values.

## 6. Billing snapshot + code validation (High #12/#13)
- [ ] Save an Automatic bill with a valid code — confirm it saves and the
      visit detail page shows the right line items/total.
- [ ] Save an Automatic bill with a **typo'd/nonexistent code** — confirm
      the whole save is rejected with a clear message (not silently
      partially saved).
- [ ] Open an **old** visit that was billed before this update — confirm
      it still displays its bill correctly (this exercises the
      live-lookup fallback path for pre-existing, non-backfilled data —
      should be rare after the startup backfill runs, but worth checking
      once).
- [ ] Edit a Price List item's sale price, then check a bill from a
      **previous month** — confirm that old bill's total did *not*
      change. This is the actual bug the fix closes; it's the most
      important thing to verify here.
- [ ] Add an inpatient billing line, then edit that Price List item's
      price — confirm the inpatient case's existing line still shows the
      original price.
- [ ] Run a POS sale, then check Reports for that month's COGS figure —
      confirm it's using the cost at time of sale (change the item's
      inventory cost afterward and confirm the historical figure doesn't
      move).

## 7. Connection pool (High #6) / insights (Medium)
- [ ] Normal usage for an extended period doesn't exhaust connections
      (watch `SELECT count(*) FROM pg_stat_activity` on Postgres while
      using the app normally).
- [ ] Insights dashboard still loads and shows correct numbers.
- [ ] After a restore, the app continues working normally afterward (pool
      should transparently reopen).

## 8. Network/session hardening (High #7 / Medium session cookies)
- [ ] With no new env vars set, app behaves identically to before
      (binds 0.0.0.0:5050, no allowlist, sessions behave as before except
      the new 12-hour expiry — see below).
- [ ] **Flag for staff**: sessions now expire after 12 hours
      (`SESSION_LIFETIME_HOURS`) even if the browser is never closed —
      confirm this is the behavior you want before rolling out; adjust
      the env var if a different duration fits your clinic's shifts
      better.
- [ ] If you use `BEHIND_TLS_PROXY=1`: confirm login still works through
      the proxy, and that the session cookie is marked `Secure` (check
      browser devtools).
- [ ] Rapid repeated login attempts from one IP get rate-limited after 20
      attempts in 5 minutes (429/error page, not silently ignored).

## 9. Pagination (Medium)
- [ ] Follow-ups, Wellness, Grooming, Audit History list pages: confirm
      page counts/totals look right, and that page 2+ shows different
      records than page 1 (not a repeat of page 1's data — the classic
      off-by-one bug in a pagination rewrite).
- [ ] Dashboard's "missed items" badge/count still reflects the *entire*
      dataset, not just one page (this is the thing I was most careful
      to preserve — worth a specific check).

## 10. Foreign keys (High #16 / Medium)
- [ ] Normal payment/attachment creation across visits, inpatient cases,
      and boarding still works without new errors.

## Note: High #8 (float precision) — closed, not implemented
Deliberately not fixed — closed as not applicable given this deployment
bills in whole-number IQD and never bills fractional quantities. See
`CHANGELOG_SECURITY_FIXES.md`'s "Update — closed as not applicable"
section for the full reasoning. Nothing to test here *unless* either of
those two premises changes in the future (fractional currency use, or
fractional-quantity billing) — if so, this should be revisited before
assuming it's still safe.


## 11. Consignment (new feature)
- [ ] Fresh install picks up the 4 new permissions correctly: Admin gets
      all 4, Vet/Reception get the 3 non-settlement ones, and
      `manage_consignment_settlements` is Admin-only by default.
- [ ] Flag a Retail item as Consignment (Consignment > Items) — requires
      picking a distributor and cost price.
- [ ] Sell that item through normal POS checkout — confirm it behaves
      identically to an owned item (price lookup, stock deduction, the
      row-lock oversell protection).
- [ ] Try to unflag/change-distributor on an item that's already had a
      sale against it — confirm it's refused with a clear message
      ("locked — has activity").
- [ ] Log a Receiving entry — confirm stock goes up on Inventory Status
      immediately, with the "consignment" badge showing.
- [ ] Log a Shrinkage entry for more than what's on the shelf — confirm
      it's rejected (this exercises the same row-lock/cap logic as the
      POS fix). Log a valid one — confirm stock goes down and it shows
      up in the distributor's settlement balance if Clinic-liable, and
      does NOT if Distributor-liable.
- [ ] Log a Return for more than what's on the shelf — same rejection
      check. Log a valid one — confirm it does NOT affect the
      settlement balance (§7: returns are money-neutral).
- [ ] Confirm an audit where a Consignment item's physical count comes
      in under the expected shelf number — confirm the flash message
      appears listing the shortfall and pointing to Shrinkage, and that
      the audit still confirms normally (this is a nudge, not a block).
- [ ] Open Consignment > Settlements for a distributor with some sales
      logged — confirm the balance breakdown (residual + new activity =
      owed) matches manual math against what you logged.
- [ ] Record a partial settlement (pay less than owed) — confirm the
      residual carries forward correctly into the next balance
      calculation.
- [ ] Export a settlement PDF — confirm it opens and shows the right
      figures.
- [ ] Check Reports > Monthly P&L / Consignment > Sales by Distributor
      after a consignment sale — confirm the numbers agree with each
      other (both should be reading the same `sale_items.unit_cost`
      snapshot).

## 12. Billing Redesign (visit + inpatient billing UI)
- [ ] New visit, Automatic billing: search adds a line, quantity is
      editable, remove works, subtotal updates live, Save persists and
      reloads with the same cart shown.
- [ ] Search for a known Retail item's name in the visit billing search
      — confirm it returns no results (Retail is excluded).
- [ ] Existing (pre-redesign-era, if any test data has it) Automatic
      bill still displays and re-opens with its cart correctly prefilled.
- [ ] Switch a bill to Manual and back to Automatic — confirm the cart
      doesn't show a bogus empty/null line (this was a bug I caught and
      fixed before it shipped — worth specifically re-checking).
- [ ] Manual Entry mode still works exactly as before.
- [ ] Discount % and payment recording on a visit still compute the
      same total/balance/status as before.
- [ ] Inpatient billing tab: search adds a procedure with quantity,
      submit adds it to "Bill so Far", per-line delete still works.
- [ ] Patient/visit PDF export still shows correct billing lines/totals.
- [ ] Insights dashboard: Revenue by Category and Vet Performance
      numbers look sane, and — most importantly — editing a Price List
      item's price today does NOT change last month's numbers on either
      report (this is the actual gap that was found and fixed).

## 13. Distributor Ledger
- [ ] From the Distributors list, click into a distributor's Ledger —
      page loads, shows zero totals for a distributor with no bills yet.
- [ ] Log a bill, record a partial payment — status shows "Partial",
      balance is correct.
- [ ] Record a payment that completes the balance — status flips to
      "Paid".
- [ ] Try to delete a bill that has payments — confirm it's blocked with
      a clear message; delete the payments first, then the bill deletes.
- [ ] Export PDF — confirm it opens and totals match the on-screen ledger.
- [ ] Back on the Distributors list: Outstanding column shows the right
      number for a distributor with a balance, "—" for one without.
- [ ] Payables summary block at the top: Total Outstanding, Distributors
      With a Balance, and Fully Unpaid Bills counts all match manual
      arithmetic against what you logged; "Who You Owe Most" is sorted
      correctly and links through to the right distributor.
- [ ] Confirm this feature has zero effect on POS, Sales, Refunds, or
      any report page — spot check one of each before/after.
