"""
Boarding stays are refundable.

`payments` has anchored on exactly one of visit_id / inpatient_case_id /
boarding_id since it existed. `refunds` only ever had the first two, and its
CHECK constraint actively required one of them — so a clinic could take money
for a boarding stay and had no way to give it back through the Refunds page.
Boarding was the only such gap: the four billable surfaces are visits,
inpatient cases, boarding stays and POS sales, and the other three were
covered. Grooming and wellness bill through a visit, so they are covered by
the visit anchor.

Amounts here are IQD and deliberately multiples of 250: a service refund is
passed through money.round_to_denomination(), so a test using 5001 would
assert against a stored 5000 and read as a bug in the cap instead of a
rounding step. JO's copy of this file uses JOD amounts for the same reason,
re-derived rather than copied.
"""
import uuid
from datetime import date

import pytest

import logic
from conftest import needs_db

pytestmark = needs_db


def _uid(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def paid_stay(db):
    """A boarding stay with 20,000 IQD actually paid against it."""
    o_id, p_id = _uid("O"), _uid("P")
    db.execute("INSERT INTO owners (id, name) VALUES (?,?)", (o_id, f"Refund Owner {o_id}"))
    db.execute("INSERT INTO patients (id, owner_id, animal_name) VALUES (?,?,?)",
               (p_id, o_id, f"Refund Pet {p_id}"))
    cur = db.execute(
        "INSERT INTO boarding_sessions (patient_id, entry_date, special_needs, total_is_auto, "
        "cleanup_amount, discount_percent, dismissed, total, price_per_day) "
        "VALUES (?,?,?,?,?,?,?,?,?) RETURNING id",
        (p_id, date.today().isoformat(), False, False, 0.0, 0.0, True, 20000.0, 5000.0))
    bid = cur.fetchone()["id"]
    db.execute("INSERT INTO payments (boarding_id, amount, method, date, user_id) VALUES (?,?,?,?,?)",
               (bid, 20000.0, "Cash", date.today().isoformat(), "U001"))
    db.commit()
    yield {"id": bid, "patient_id": p_id, "owner_id": o_id, "paid": 20000.0}
    db.execute("DELETE FROM refunds WHERE boarding_id=?", (bid,))
    db.execute("DELETE FROM payments WHERE boarding_id=?", (bid,))
    db.execute("DELETE FROM boarding_sessions WHERE id=?", (bid,))
    db.execute("DELETE FROM patients WHERE id=?", (p_id,))
    db.execute("DELETE FROM owners WHERE id=?", (o_id,))
    db.commit()


def _refund(client, **data):
    payload = {"amount": "5000", "refund_date": date.today().isoformat(),
               "refund_method": "Cash", "reason": "test",
               "visit_id": "", "inpatient_case_id": "", "boarding_id": ""}
    payload.update(data)
    return client.post("/refunds/service", data=payload, follow_redirects=True)


# ---------------------------------------------------------------------------
# The feature
# ---------------------------------------------------------------------------

def test_a_boarding_stay_can_be_refunded(client, db, paid_stay):
    """GUARD. Before this change the route rejected every boarding refund and
    the CHECK constraint would have refused the row even if it had not."""
    resp = _refund(client, boarding_id=str(paid_stay["id"]), amount="5000")
    assert b"Service refund of" in resp.data, resp.data[-600:]
    row = db.execute("SELECT * FROM refunds WHERE boarding_id=?", (paid_stay["id"],)).fetchone()
    assert row is not None, "no refund row was written"
    assert row["refund_type"] == "service"
    assert float(row["amount"]) == 5000.0
    assert row["visit_id"] is None and row["inpatient_case_id"] is None


def test_the_refund_shows_up_on_the_refunds_page(client, paid_stay):
    """The history list has to name the stay, or the refund is invisible."""
    _refund(client, boarding_id=str(paid_stay["id"]), amount="5000")
    page = client.get("/refunds").data.decode()
    assert f"Boarding {paid_stay['id']}" in page


# ---------------------------------------------------------------------------
# It is capped at what was actually paid
# ---------------------------------------------------------------------------

def test_a_boarding_refund_cannot_exceed_what_was_paid(client, db, paid_stay):
    """GUARD. The cap is the whole reason this anchors on a record at all."""
    resp = _refund(client, boarding_id=str(paid_stay["id"]), amount="25000")
    assert b"still refundable" in resp.data
    assert db.execute("SELECT COUNT(*) c FROM refunds WHERE boarding_id=?",
                      (paid_stay["id"],)).fetchone()["c"] == 0


def test_a_second_refund_cannot_exceed_the_remainder(client, db, paid_stay):
    """GUARD. Two refunds of 15,000 against a 20,000 stay must not both land."""
    first = _refund(client, boarding_id=str(paid_stay["id"]), amount="15000")
    assert b"Service refund of" in first.data
    second = _refund(client, boarding_id=str(paid_stay["id"]), amount="15000")
    assert b"still refundable" in second.data
    total = db.execute("SELECT COALESCE(SUM(amount),0) s FROM refunds WHERE boarding_id=?",
                       (paid_stay["id"],)).fetchone()["s"]
    assert float(total) == 15000.0


def test_the_remainder_is_still_refundable(client, db, paid_stay):
    """CONTROL. The cap must not have become 'only ever one refund'."""
    _refund(client, boarding_id=str(paid_stay["id"]), amount="15000")
    resp = _refund(client, boarding_id=str(paid_stay["id"]), amount="5000")
    assert b"Service refund of" in resp.data
    total = db.execute("SELECT COALESCE(SUM(amount),0) s FROM refunds WHERE boarding_id=?",
                       (paid_stay["id"],)).fetchone()["s"]
    assert float(total) == 20000.0


def test_an_unpaid_stay_cannot_be_refunded(client, db, paid_stay):
    """GUARD. Nothing paid means nothing to give back."""
    db.execute("DELETE FROM payments WHERE boarding_id=?", (paid_stay["id"],))
    db.commit()
    resp = _refund(client, boarding_id=str(paid_stay["id"]), amount="5000")
    assert b"still refundable" in resp.data


# ---------------------------------------------------------------------------
# Exactly one anchor — the rule the form text used to contradict
# ---------------------------------------------------------------------------

def test_no_anchor_at_all_is_refused(client):
    """GUARD. A goodwill refund belongs in Cash Register, not here."""
    resp = _refund(client, amount="5000")
    assert b"exactly one visit, inpatient case, or boarding stay" in resp.data


def test_two_anchors_are_refused(client, db, paid_stay):
    """GUARD. A refund reverses one record; two would double-count the cap."""
    resp = _refund(client, boarding_id=str(paid_stay["id"]), visit_id="V001", amount="5000")
    assert b"exactly one visit, inpatient case, or boarding stay" in resp.data
    assert db.execute("SELECT COUNT(*) c FROM refunds WHERE boarding_id=?",
                      (paid_stay["id"],)).fetchone()["c"] == 0


def test_an_unknown_boarding_id_is_refused(client):
    resp = _refund(client, boarding_id="99999999", amount="5000")
    assert b"Boarding stay 99999999 not found" in resp.data


def test_a_non_numeric_boarding_id_is_refused(client):
    resp = _refund(client, boarding_id="abc", amount="5000")
    assert b"not found" in resp.data


def test_the_database_itself_refuses_a_two_anchor_service_refund(db, paid_stay):
    """Defence in depth: the route check above is the friendly message, the
    CHECK constraint is what makes the rule true regardless of the route.
    Both matter — see CLAUDE.md §7.4 on disabling one layer at a time."""
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO refunds (refund_type, refund_date, amount, visit_id, boarding_id, "
            "processed_by, created_at) VALUES ('service',?,?,?,?,?,?)",
            (date.today().isoformat(), 1000.0, "V001", paid_stay["id"], "U001", "2026-01-01T00:00:00"))
    db.rollback()


def test_the_database_refuses_a_service_refund_with_no_anchor(db):
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO refunds (refund_type, refund_date, amount, processed_by, created_at) "
            "VALUES ('service',?,?,?,?)",
            (date.today().isoformat(), 1000.0, "U001", "2026-01-01T00:00:00"))
    db.rollback()


# ---------------------------------------------------------------------------
# It nets against the right P&L column
# ---------------------------------------------------------------------------

def test_a_boarding_refund_reduces_the_boarding_category(client, db, paid_stay):
    """GUARD. revenue_by_category's refund arm mapped everything non-retail to
    'Service'. Boarding revenue has its own column, so a boarding refund landing
    in Service would push the two columns apart and make neither correct."""
    month = date.today().strftime("%Y-%m")
    before = logic.revenue_by_category(db)["grid"].get(month, {})
    b_before = before.get("Boarding", 0)
    s_before = before.get("Service", 0)

    _refund(client, boarding_id=str(paid_stay["id"]), amount="5000")

    after = logic.revenue_by_category(db)["grid"].get(month, {})
    assert round(after.get("Boarding", 0) - b_before, 2) == -5000.0, (
        "the boarding refund did not reduce the Boarding column")
    assert round(after.get("Service", 0) - s_before, 2) == 0.0, (
        "the boarding refund was charged against Service")


# ---------------------------------------------------------------------------
# CONTROLS — the two anchors that already worked must be untouched
# ---------------------------------------------------------------------------

@pytest.fixture
def paid_visit(db):
    o_id, p_id, v_id = _uid("O"), _uid("P"), _uid("V")
    db.execute("INSERT INTO owners (id, name) VALUES (?,?)", (o_id, f"V Owner {o_id}"))
    db.execute("INSERT INTO patients (id, owner_id, animal_name) VALUES (?,?,?)",
               (p_id, o_id, f"V Pet {p_id}"))
    db.execute("INSERT INTO visits (id, patient_id, date, visit_type) VALUES (?,?,?,?)",
               (v_id, p_id, date.today().isoformat(), "Consultation"))
    db.execute("INSERT INTO payments (visit_id, amount, method, date, user_id) VALUES (?,?,?,?,?)",
               (v_id, 10000.0, "Cash", date.today().isoformat(), "U001"))
    db.commit()
    yield {"id": v_id}
    db.execute("DELETE FROM refunds WHERE visit_id=?", (v_id,))
    db.execute("DELETE FROM payments WHERE visit_id=?", (v_id,))
    db.execute("DELETE FROM visits WHERE id=?", (v_id,))
    db.execute("DELETE FROM patients WHERE id=?", (p_id,))
    db.execute("DELETE FROM owners WHERE id=?", (o_id,))
    db.commit()


def test_a_visit_refund_still_works(client, db, paid_visit):
    """CONTROL. Widening the anchor rule must not have broken the two that
    already worked — the most likely way this change goes wrong."""
    resp = _refund(client, visit_id=paid_visit["id"], amount="5000")
    assert b"Service refund of" in resp.data, resp.data[-600:]
    row = db.execute("SELECT * FROM refunds WHERE visit_id=?", (paid_visit["id"],)).fetchone()
    assert row is not None and row["boarding_id"] is None


def test_a_visit_refund_is_still_capped(client, paid_visit):
    """CONTROL."""
    resp = _refund(client, visit_id=paid_visit["id"], amount="50000")
    assert b"still refundable" in resp.data


def test_a_visit_refund_still_nets_against_service(client, db, paid_visit):
    """CONTROL for the category change: non-boarding service refunds must
    still land in Service."""
    month = date.today().strftime("%Y-%m")
    before = logic.revenue_by_category(db)["grid"].get(month, {}).get("Service", 0)
    _refund(client, visit_id=paid_visit["id"], amount="5000")
    after = logic.revenue_by_category(db)["grid"].get(month, {}).get("Service", 0)
    assert round(after - before, 2) == -5000.0
