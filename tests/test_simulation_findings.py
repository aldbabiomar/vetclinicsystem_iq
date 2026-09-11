"""
Regression tests for the six findings in SIMULATION_AUDIT_2026-09-11.md.

These came out of driving the app as a real user rather than reading it, and
four of the six were invisible to the existing suite because they live at the
seam between two code paths that should share a rule and did not:

  F1  pos_checkout rounded to the note without the anti-"looks free" floor
      that compute_bill_totals has always applied. A cart under half a note
      recorded total 0 -- free goods, and every dinar tendered handed back.
  F2  _save_audit_lines parsed counts with float(), which accepts "nan".
      `qty > nan` is False, so the POS oversell guard passed an empty shelf.
  F3  a retail refund rounded DOWN to zero: goods returned, nothing paid.
  F4  "?day=" (present but empty) reached Postgres as a date and 500'd.
  F5  counts accepted negatives.
  F6  an inpatient case accepted a discharge dated before its admission.

Every guard below is paired with a control asserting the valid case still
works -- without one, "refused for the right reason" and "refused for any
reason" are indistinguishable (CLAUDE.md §7.3). Each was also verified by
reverting the fix and watching the test fail; see scripts/simulation/.

JO's equivalent file asserts deliberately DIFFERENT things for F1/F3 --
it has no note rounding, so there is nothing to floor. COMPARISON.md §1.1.
"""
import uuid
from datetime import date, datetime, timedelta

import pytest

import logic
import money

from conftest import needs_db


def _uid(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def sellable(db):
    """An inventory item with a price, a confirmed audit, and stock.

    Deliberately a local copy rather than an import from test_money_routes:
    a fixture defined in a test module is not visible outside it, and moving
    it to conftest would make two files share arrangement that they each
    tune (this one rewrites sale_price per test). The confirmed audit is not
    set-dressing -- pos_checkout fails closed on an item whose current_stock
    is None, so a fixture without one makes every checkout test fail for the
    wrong reason.
    """
    inv_id, pl_id = _uid("INV"), _uid("PL")
    db.execute("INSERT INTO inventory_list (id, name, category, unit, track_expiry, cost_price, "
               "ownership_type, active) VALUES (?,?,?,?,?,?,?,?)",
               (inv_id, f"Sim Test Item {inv_id}", "Retail", "unit", False, 1000.0, "Owned", True))
    db.execute("INSERT INTO price_list (id, name, category, cost_price, sale_price, active, "
               "linked_item_id, can_discount) VALUES (?,?,?,?,?,?,?,?)",
               (pl_id, f"Sim Test Item {inv_id}", "Retail", 1000.0, 5000.0, True, inv_id, True))
    cur = db.execute("INSERT INTO audit_sessions (audit_date, performed_by, status, created_at, "
                     "confirmed_at) VALUES (?,?,?,?,?) RETURNING id",
                     (date.today().isoformat(), "U001", "Confirmed",
                      datetime.now().isoformat(timespec="seconds"),
                      datetime.now().isoformat(timespec="microseconds")))
    session_id = cur.fetchone()["id"]
    db.execute("INSERT INTO audit_session_lines (session_id, item_id, stock_counted, "
               "received_since_prior) VALUES (?,?,?,?)", (session_id, inv_id, 1000.0, 0.0))
    db.commit()
    yield {"inv_id": inv_id, "pl_id": pl_id, "price": 5000.0, "stock": 1000.0,
           "session_id": session_id}
    for sql, args in (
        ("DELETE FROM refund_items WHERE sale_item_id IN "
         "(SELECT id FROM sale_items WHERE item_id=?)", (inv_id,)),
        ("DELETE FROM refunds WHERE sale_id IN "
         "(SELECT sale_id FROM sale_items WHERE item_id=?)", (inv_id,)),
        ("DELETE FROM inventory_transactions WHERE item_id=?", (inv_id,)),
        ("DELETE FROM sale_items WHERE item_id=?", (inv_id,)),
        ("DELETE FROM audit_session_lines WHERE item_id=?", (inv_id,)),
        ("DELETE FROM audit_sessions WHERE id=?", (session_id,)),
        ("DELETE FROM price_list WHERE id=?", (pl_id,)),
        ("DELETE FROM inventory_list WHERE id=?", (inv_id,)),
    ):
        try:
            db.execute(sql, args)
        except Exception:
            db.rollback()
    db.commit()


# ===========================================================================
# F1 — the anti-"looks free" floor, and the fact that ONE function owns it
# ===========================================================================

def test_payable_total_floors_a_non_zero_charge():
    """Below half a note, a real charge becomes the smallest note, not free."""
    assert money.payable_total(10) == 250
    assert money.payable_total(100) == 250
    assert money.payable_total(124) == 250
    assert money.payable_total(125) == 250


def test_payable_total_leaves_ordinary_amounts_to_plain_rounding():
    """CONTROL — the floor must not distort anything above the boundary."""
    assert money.payable_total(250) == 250
    assert money.payable_total(374) == 250
    assert money.payable_total(376) == 500
    assert money.payable_total(10000) == 10000


def test_payable_total_keeps_a_full_waiver_free():
    """A 100% discount is an intentional waiver, not a rounding accident."""
    assert money.payable_total(0, discount_percent=100) == 0
    assert money.payable_total(100, discount_percent=100) == 0
    # ...but 99% is still a charge, and must not be presented as free.
    assert money.payable_total(100, discount_percent=99) == 250


def test_payable_total_treats_zero_as_zero():
    assert money.payable_total(0) == 0


def test_both_money_paths_agree_at_every_boundary():
    """The regression that started F1: pos_checkout and compute_bill_totals
    must produce the same payable figure for the same subtotal. They diverged
    because the floor was written inline in one of them."""
    for subtotal in (1, 10, 50, 100, 124, 125, 126, 200, 250, 375, 500, 10000):
        bill_total, _, _, _ = logic.compute_bill_totals(subtotal, 0, 0)
        pos_total = money.payable_total(subtotal * (1 - 0 / 100), 0)
        assert bill_total == pos_total, (
            f"subtotal {subtotal}: bill path says {bill_total}, POS says {pos_total}")


@needs_db
def test_a_small_pos_sale_is_not_free(client, db, sellable):
    """The headline case: a sale worth less than half a note must not record
    total 0 and hand back the entire amount tendered."""
    db.execute("UPDATE price_list SET sale_price=? WHERE id=?", (100.0, sellable["pl_id"]))
    db.commit()
    resp = client.post("/pos/checkout", data={
        "item_id": sellable["inv_id"], "quantity": "1", "payment_method": "Cash",
        "discount_percent": "0", "cash_received": "250000",
        "idempotency_key": uuid.uuid4().hex}, follow_redirects=True)
    assert resp.status_code == 200
    row = db.execute("SELECT subtotal, total, cash_received, change_given FROM sales "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    assert row["subtotal"] == 100.0
    assert row["total"] == 250.0, "a 100 IQD cart must floor to one note, not 0"
    assert row["change_given"] == 250000 - 250, "change must not return the full tender"


@needs_db
def test_an_ordinary_pos_sale_is_unaffected(client, db, sellable):
    """CONTROL — the floor changes nothing for a normal-priced sale."""
    resp = client.post("/pos/checkout", data={
        "item_id": sellable["inv_id"], "quantity": "1", "payment_method": "Cash",
        "discount_percent": "0", "cash_received": "250000",
        "idempotency_key": uuid.uuid4().hex}, follow_redirects=True)
    assert resp.status_code == 200
    row = db.execute("SELECT subtotal, total FROM sales ORDER BY id DESC LIMIT 1").fetchone()
    assert row["total"] == sellable["price"]


# ===========================================================================
# F2 / F5 — counts are physical quantities: finite and non-negative
# ===========================================================================

@needs_db
@pytest.mark.parametrize("bad", ["nan", "NaN", "inf", "-inf", "Infinity", "-5", "1e400"])
def test_audit_counts_reject_non_finite_and_negative(client, db, sellable, bad):
    """Saved into a DRAFT session, so a refusal means the VALUE was refused --
    a confirmed session refuses every save regardless, which would make this
    pass whether or not the guard exists."""
    cur = db.execute("INSERT INTO audit_sessions (audit_date, performed_by, status, created_at) "
                     "VALUES (?,?,?,?) RETURNING id",
                     (date.today().isoformat(), "U001", "Draft",
                      datetime.now().isoformat(timespec="seconds")))
    sid = cur.fetchone()["id"]
    db.commit()
    try:
        # a good value first, so "unchanged" is what proves the reject
        client.post(f"/audit-history/session/{sid}/save",
                    data={f"stock_{sellable['inv_id']}": "5",
                          f"received_{sellable['inv_id']}": "0"}, follow_redirects=True)
        seeded = db.execute("SELECT stock_counted FROM audit_session_lines "
                            "WHERE session_id=? AND item_id=?",
                            (sid, sellable["inv_id"])).fetchone()
        assert seeded and seeded["stock_counted"] == 5.0, "control value did not save"

        client.post(f"/audit-history/session/{sid}/save",
                    data={f"stock_{sellable['inv_id']}": bad,
                          f"received_{sellable['inv_id']}": "0"}, follow_redirects=True)
        after = db.execute("SELECT stock_counted FROM audit_session_lines "
                           "WHERE session_id=? AND item_id=?",
                           (sid, sellable["inv_id"])).fetchone()
        assert after["stock_counted"] == 5.0, f"{bad!r} was accepted into the count"
    finally:
        db.execute("DELETE FROM audit_session_lines WHERE session_id=?", (sid,))
        db.execute("DELETE FROM audit_sessions WHERE id=?", (sid,))
        db.commit()


@needs_db
def test_a_valid_audit_count_still_saves(client, db, sellable):
    """CONTROL — the draft is not simply locked; good values go in."""
    cur = db.execute("INSERT INTO audit_sessions (audit_date, performed_by, status, created_at) "
                     "VALUES (?,?,?,?) RETURNING id",
                     (date.today().isoformat(), "U001", "Draft",
                      datetime.now().isoformat(timespec="seconds")))
    sid = cur.fetchone()["id"]
    db.commit()
    try:
        client.post(f"/audit-history/session/{sid}/save",
                    data={f"stock_{sellable['inv_id']}": "42.5",
                          f"received_{sellable['inv_id']}": "3"}, follow_redirects=True)
        row = db.execute("SELECT stock_counted, received_since_prior FROM audit_session_lines "
                         "WHERE session_id=? AND item_id=?", (sid, sellable["inv_id"])).fetchone()
        assert row["stock_counted"] == 42.5
        assert row["received_since_prior"] == 3.0
    finally:
        db.execute("DELETE FROM audit_session_lines WHERE session_id=?", (sid,))
        db.execute("DELETE FROM audit_sessions WHERE id=?", (sid,))
        db.commit()


@needs_db
def test_the_database_itself_refuses_a_nan_count(db, sellable):
    """Defence in depth. Note a plain `>= 0` CHECK would NOT catch this:
    in Postgres NaN sorts above every value, so 'NaN' >= 0 is true."""
    import db as dbmod
    cur = db.execute("INSERT INTO audit_sessions (audit_date, performed_by, status, created_at) "
                     "VALUES (?,?,?,?) RETURNING id",
                     (date.today().isoformat(), "U001", "Draft",
                      datetime.now().isoformat(timespec="seconds")))
    sid = cur.fetchone()["id"]
    db.commit()
    try:
        for bad in ("NaN", "Infinity", "-1"):
            with pytest.raises(Exception):
                db.execute("INSERT INTO audit_session_lines (session_id, item_id, stock_counted, "
                           "received_since_prior) VALUES (?,?,?::float8,?)",
                           (sid, sellable["inv_id"], bad, 0.0))
                db.commit()
            db.rollback()
        # CONTROL — a sane count is accepted by the same constraint
        db.execute("INSERT INTO audit_session_lines (session_id, item_id, stock_counted, "
                   "received_since_prior) VALUES (?,?,?,?)", (sid, sellable["inv_id"], 9.0, 0.0))
        db.commit()
        row = db.execute("SELECT stock_counted FROM audit_session_lines WHERE session_id=?",
                         (sid,)).fetchone()
        assert row["stock_counted"] == 9.0
    finally:
        db.rollback()
        db.execute("DELETE FROM audit_session_lines WHERE session_id=?", (sid,))
        db.execute("DELETE FROM audit_sessions WHERE id=?", (sid,))
        db.commit()


@needs_db
def test_a_nan_count_already_stored_fails_closed_in_pos(client, db, sellable):
    """The second layer: even if a NaN reaches the table by some other path,
    POS must refuse rather than let `qty > nan` silently pass. The CHECK
    constraint is dropped for this test so it actually reaches the app-level
    guard it names -- see CLAUDE.md §7.4 on defence in depth."""
    db.execute("ALTER TABLE audit_session_lines "
               "DROP CONSTRAINT IF EXISTS audit_session_lines_stock_counted_check")
    db.commit()
    try:
        db.execute("UPDATE audit_session_lines SET stock_counted='NaN'::float8 WHERE item_id=?",
                   (sellable["inv_id"],))
        db.commit()
        planted = db.execute("SELECT stock_counted FROM audit_session_lines WHERE item_id=?",
                             (sellable["inv_id"],)).fetchone()
        assert str(planted["stock_counted"]).lower() == "nan", "could not plant the bad row"

        before = db.execute("SELECT COUNT(*) c FROM sales").fetchone()["c"]
        resp = client.post("/pos/checkout", data={
            "item_id": sellable["inv_id"], "quantity": "500", "payment_method": "Cash",
            "discount_percent": "0", "cash_received": "250000",
            "idempotency_key": uuid.uuid4().hex}, follow_redirects=True)
        assert resp.status_code == 200, "must refuse cleanly, not 500"
        after = db.execute("SELECT COUNT(*) c FROM sales").fetchone()["c"]
        assert after == before, "500 units were sold against a NaN stock count"
        assert b"audit" in resp.data.lower()
    finally:
        db.execute("UPDATE audit_session_lines SET stock_counted=? WHERE item_id=?",
                   (sellable["stock"], sellable["inv_id"]))
        db.execute("ALTER TABLE audit_session_lines ADD CONSTRAINT "
                   "audit_session_lines_stock_counted_check CHECK (stock_counted IS NULL "
                   "OR (stock_counted >= 0 AND stock_counted < 'Infinity'::float8))")
        db.commit()


# ===========================================================================
# F3 — a refund is never settled at zero
# ===========================================================================

@needs_db
def test_a_small_retail_refund_pays_at_least_one_note(client, db, sellable):
    """Rounding a refund DOWN is deliberate (never pay out more than the lines
    add up to) but must not reach zero: the customer hands the goods back, the
    item is restocked, and nothing is paid."""
    db.execute("UPDATE price_list SET sale_price=? WHERE id=?", (240.0, sellable["pl_id"]))
    db.commit()
    client.post("/pos/checkout", data={
        "item_id": sellable["inv_id"], "quantity": "1", "payment_method": "Cash",
        "discount_percent": "0", "cash_received": "250000",
        "idempotency_key": uuid.uuid4().hex}, follow_redirects=True)
    sale = db.execute("SELECT id, total FROM sales ORDER BY id DESC LIMIT 1").fetchone()
    assert sale["total"] == 250.0
    line = db.execute("SELECT id FROM sale_items WHERE sale_id=? LIMIT 1", (sale["id"],)).fetchone()
    resp = client.post("/refunds/retail", data={
        "sale_id": str(sale["id"]), "sale_item_id": str(line["id"]), "quantity": "1",
        "reason": "Returned unopened", "refund_date": date.today().isoformat(),
        "refund_method": "Cash", "restock": "on"}, follow_redirects=True)
    assert resp.status_code == 200
    ref = db.execute("SELECT amount FROM refunds WHERE sale_id=? ORDER BY id DESC LIMIT 1",
                     (sale["id"],)).fetchone()
    assert ref is not None, "no refund was recorded at all"
    assert ref["amount"] > 0, "the refund was recorded as zero"
    assert ref["amount"] <= sale["total"], "refunded more than the sale collected"


@needs_db
def test_an_ordinary_refund_is_unaffected(client, db, sellable):
    """CONTROL — a normal refund still pays exactly the line value."""
    client.post("/pos/checkout", data={
        "item_id": sellable["inv_id"], "quantity": "1", "payment_method": "Cash",
        "discount_percent": "0", "cash_received": "250000",
        "idempotency_key": uuid.uuid4().hex}, follow_redirects=True)
    sale = db.execute("SELECT id, total FROM sales ORDER BY id DESC LIMIT 1").fetchone()
    line = db.execute("SELECT id FROM sale_items WHERE sale_id=? LIMIT 1", (sale["id"],)).fetchone()
    client.post("/refunds/retail", data={
        "sale_id": str(sale["id"]), "sale_item_id": str(line["id"]), "quantity": "1",
        "reason": "Returned", "refund_date": date.today().isoformat(),
        "refund_method": "Cash", "restock": "on"}, follow_redirects=True)
    ref = db.execute("SELECT amount FROM refunds WHERE sale_id=? ORDER BY id DESC LIMIT 1",
                     (sale["id"],)).fetchone()
    assert ref["amount"] == sellable["price"]


# ===========================================================================
# F4 — an empty date filter is not a server error
# ===========================================================================

@needs_db
@pytest.mark.parametrize("query", [
    "?day=", "?week=", "?day=&week=", "?day=%20", "?day=&show_past=1",
])
def test_appointments_survives_an_empty_date_filter(client, query):
    """parse_date("") RETURNS None rather than raising, so the route's
    except-ValueError guard never fired and "" reached Postgres as a date."""
    resp = client.get("/appointments" + query)
    assert resp.status_code < 500, f"/appointments{query} returned {resp.status_code}"


@needs_db
@pytest.mark.parametrize("query", ["", "?day=abc", "?day=2026-13-45", "?week=nonsense"])
def test_appointments_still_handles_absent_and_invalid_dates(client, query):
    """CONTROL — the previously-working cases must keep working."""
    resp = client.get("/appointments" + query)
    assert resp.status_code < 500


# ===========================================================================
# F6 — a stay cannot end before it began
# ===========================================================================

@needs_db
def test_an_inpatient_case_cannot_be_discharged_before_admission(client, db):
    """boarding_edit() has always enforced this; inpatient_edit() did not."""
    o_id, p_id = _uid("O"), _uid("P")
    db.execute("INSERT INTO owners (id, name) VALUES (?,?)", (o_id, f"Date Owner {o_id}"))
    db.execute("INSERT INTO patients (id, owner_id, animal_name) VALUES (?,?,?)",
               (p_id, o_id, f"Date Pet {p_id}"))
    admitted = date.today().isoformat()
    cur = db.execute("INSERT INTO inpatient_cases (patient_id, admission_date, complaint, "
                     "dismissed, updated_at) VALUES (?,?,?,?,?) RETURNING id",
                     (p_id, admitted, "obs", False,
                      datetime.now().isoformat(timespec="seconds")))
    case_id = cur.fetchone()["id"]
    db.commit()
    try:
        def edit(dismissal_date):
            stamp = db.execute("SELECT updated_at FROM inpatient_cases WHERE id=?",
                               (case_id,)).fetchone()["updated_at"]
            return client.post(f"/inpatient/{case_id}/edit", data={
                "complaint": "obs", "exam_findings": "stable", "weight_kg": "10", "bcs": "5",
                "dismissed": "on", "dismissal_date": dismissal_date,
                "expected_updated_at": stamp}, follow_redirects=True)

        edit((date.today() - timedelta(days=400)).isoformat())
        row = db.execute("SELECT admission_date, dismissal_date FROM inpatient_cases WHERE id=?",
                         (case_id,)).fetchone()
        assert (row["dismissal_date"] is None
                or str(row["dismissal_date"]) >= str(row["admission_date"])), (
            f"stored a negative-length stay: admitted {row['admission_date']}, "
            f"discharged {row['dismissal_date']}")

        # CONTROL — a same-day discharge is legitimate and must still save
        edit(admitted)
        row = db.execute("SELECT dismissal_date, dismissed FROM inpatient_cases WHERE id=?",
                         (case_id,)).fetchone()
        assert str(row["dismissal_date"]) == admitted, "a valid discharge was blocked too"
    finally:
        db.execute("DELETE FROM inpatient_cases WHERE id=?", (case_id,))
        db.execute("DELETE FROM patients WHERE id=?", (p_id,))
        db.execute("DELETE FROM owners WHERE id=?", (o_id,))
        db.commit()


# ===========================================================================
# Observation 2 — a saved cash count with a discrepancy is not an "error"
# ===========================================================================

@needs_db
def test_a_cash_discrepancy_is_flashed_as_a_warning_not_an_error(client, db):
    """The audit saved. Flashing it in the same red as a failure reads as
    "that did not work" and invites staff to run the count again."""
    day = date.today().isoformat()
    resp = client.post("/cash-register/audit",
                       data={"day": day, "counted_cash": "777777", "notes": "regression"},
                       follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'class="flash warning"' in body, "a discrepancy should use the warning style"
    row = db.execute("SELECT status FROM cash_register_audits ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] in ("Surplus", "Deficit"), "the audit was not actually recorded"


@needs_db
def test_a_perfect_cash_count_is_still_a_success(client, db):
    """CONTROL — the success path must not have been turned into a warning."""
    day = date.today().isoformat()
    totals = logic.cash_register_totals(db, day)
    resp = client.post("/cash-register/audit",
                       data={"day": day, "counted_cash": str(totals["Cash"]), "notes": "control"},
                       follow_redirects=True)
    body = resp.data.decode()
    assert 'class="flash success"' in body
    row = db.execute("SELECT status FROM cash_register_audits ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "Perfect"
