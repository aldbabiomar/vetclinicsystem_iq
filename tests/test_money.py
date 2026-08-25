"""
Money-path tests — VetClinicSystem IQ (IQD).

Why this file exists: the money math is the longest-lived, least-visible
code in the app. A wrong colour is obvious the moment someone looks at
it; a wrong total is a bill a client actually paid. Until this file, all
of it was verified by hand.

IQ's money model, which every assertion below depends on:
  - Amounts are `float`, columns are DOUBLE PRECISION.
  - The IQD's smallest circulating note is 250, so every *payable* figure
    (total, balance, change) is rounded to a multiple of it.
  - Rounding is half-up, NOT Python's default banker's rounding.
  - A non-zero bill must never round down to "free".

JO is deliberately different (exact 3-decimal Decimal, no note rounding,
no anti-free floor). Its equivalent file makes the opposite assertions on
purpose — see COMPARISON.md §1.1 before copying anything between them.
"""
import math

import pytest

import app
import logic
import money


# ---------------------------------------------------------------------------
# parse_money — the front door. Everything downstream trusts its output.
# ---------------------------------------------------------------------------

def test_parse_money_blank_is_none():
    assert app.parse_money("") is None
    assert app.parse_money("   ") is None
    assert app.parse_money(None) is None


def test_parse_money_blank_but_required_raises():
    with pytest.raises(app.BadNumber):
        app.parse_money("", required=True)


def test_parse_money_accepts_ordinary_amounts():
    assert app.parse_money("10000") == 10000
    assert app.parse_money("0") == 0
    assert app.parse_money(" 250 ") == 250


@pytest.mark.parametrize("hostile", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_parse_money_rejects_nan_and_infinity(hostile):
    """The trap parse_money's own comment documents: float() parses these
    happily, and every bound check downstream (`x > cap`, `x < 0`) is False
    against NaN — so an unchecked NaN doesn't merely slip past validation,
    it appears to *pass* every check. Must be rejected at the door."""
    with pytest.raises(app.BadNumber):
        app.parse_money(hostile)


@pytest.mark.parametrize("garbage", ["abc", "1,000", "10.0.0", "$50", "12 34"])
def test_parse_money_rejects_non_numeric(garbage):
    with pytest.raises(app.BadNumber):
        app.parse_money(garbage)


@pytest.mark.parametrize("arabic,expected", [("١٠٠", 100), ("٢٥٠", 250), ("1٠0", 100)])
def test_parse_money_accepts_arabic_indic_digits(arabic, expected):
    """Not an accident worth "fixing": Python's float()/Decimal() both parse
    Arabic-Indic digits, so a clinic in Iraq or Jordan can type ٢٥٠ into a
    price field and get 250. JO behaves identically. Locked in so that
    restricting input to ASCII digits later is a deliberate decision with a
    failing test to justify it, rather than a silent regression for the
    people this app was actually built for."""
    assert app.parse_money(arabic) == expected


def test_parse_money_allows_negative_by_design():
    """Negative is not rejected here — has_negative() is the separate guard
    for the fields where negative is never valid. Locking this in so nobody
    "helpfully" adds a sign check here and silently breaks refunds."""
    assert app.parse_money("-500") == -500


def test_parse_money_has_no_upper_bound_in_iq():
    """Documents a real divergence rather than asserting a bound that does
    not exist: JO caps money input at MAX_MONEY and raises BadNumber; IQ has
    no such ceiling and relies on the reactive NumericValueOutOfRange
    handler once the value reaches the database. If IQ ever gains a cap,
    this test should be replaced by the JO-style bound test, not deleted."""
    assert app.parse_money("1000000000000000000") == 1e18


# ---------------------------------------------------------------------------
# parse_int / has_negative — the other input guards on money-adjacent fields
# ---------------------------------------------------------------------------

def test_parse_int_blank_and_required():
    assert app.parse_int("") is None
    with pytest.raises(app.BadNumber):
        app.parse_int("", required=True)


def test_parse_int_rejects_above_max_int():
    """MAX_INT is the widest an INTEGER column here can hold. Proactive
    rejection gives a real message instead of a Postgres cast error."""
    assert app.parse_int(str(app.MAX_INT)) == app.MAX_INT
    with pytest.raises(app.BadNumber):
        app.parse_int(str(app.MAX_INT + 1))


def test_has_negative():
    assert app.has_negative(-1) is True
    assert app.has_negative(0, 5, 100) is False
    assert app.has_negative(None, 5) is False   # absent is not negative
    assert app.has_negative(5, None, -0.01) is True


# ---------------------------------------------------------------------------
# round_to_denomination — the core of IQ's money model
# ---------------------------------------------------------------------------

def test_round_to_denomination_passes_none_through():
    assert money.round_to_denomination(None) is None


def test_round_to_denomination_leaves_exact_multiples_alone():
    for v in (0, 250, 500, 1000, 12_750):
        assert money.round_to_denomination(v) == v


def test_round_to_denomination_is_half_up_not_bankers():
    """The single most important line in money.py. Python's round() breaks
    an exact .5 tie toward the nearest EVEN multiple, so 125 would round to
    0 ("free") while 375 rounds to 500 — the direction decided by parity,
    not by intent. math.floor(x/denom + 0.5) always breaks upward."""
    assert money.round_to_denomination(125) == 250
    assert money.round_to_denomination(375) == 500
    assert money.round_to_denomination(625) == 750


def test_round_to_denomination_nearest_rounds_both_ways():
    assert money.round_to_denomination(124) == 0
    assert money.round_to_denomination(126) == 250
    assert money.round_to_denomination(374) == 250
    assert money.round_to_denomination(376) == 500


def test_round_to_denomination_up_never_returns_less():
    for v in (1, 124, 125, 126, 249, 250, 251, 9999):
        assert money.round_to_denomination(v, mode="up") >= v


def test_round_to_denomination_down_never_returns_more():
    """Used for CHANGE DUE. Rounding change *up* would have the clinic hand
    back more cash than it owes, every single time, forever."""
    for v in (1, 124, 125, 249, 250, 251, 9999):
        assert money.round_to_denomination(v, mode="down") <= v


def test_round_to_denomination_respects_a_custom_denomination():
    assert money.round_to_denomination(1120, denom=1000) == 1000
    assert money.round_to_denomination(1500, denom=1000) == 2000


def test_is_denomination_valid():
    assert money.is_denomination_valid(250) is True
    assert money.is_denomination_valid(0) is True
    assert money.is_denomination_valid(251) is False
    assert money.is_denomination_valid(None) is True  # absent is not invalid


def test_fmt_money_uses_thousands_separator_and_no_decimals():
    assert money.fmt_money(1_234_567) == "1,234,567"
    assert money.fmt_money(0) == "0"
    assert money.fmt_money(None) == "—"


# ---------------------------------------------------------------------------
# compute_bill_totals — the single shared entry point for every bill in
# the app (visits, inpatient, boarding). Returns (total, paid, balance, status).
# ---------------------------------------------------------------------------

def test_bill_unpaid():
    total, paid, balance, status = logic.compute_bill_totals(10_000, 0, 0)
    assert (total, paid, balance, status) == (10_000, 0, 10_000, "Unpaid")


def test_bill_applies_percentage_discount():
    total, _, balance, _ = logic.compute_bill_totals(10_000, 10, 0)
    assert total == 9_000
    assert balance == 9_000


def test_bill_full_waiver_is_free_and_not_floored():
    """A 100% discount is an intentional waiver, not a rounding accident, so
    it is explicitly exempt from the anti-"looks free" floor below."""
    total, _, _, status = logic.compute_bill_totals(10_000, 100, 0)
    assert total == 0
    assert status == "N/A"


@pytest.mark.parametrize("subtotal", [1, 50, 100, 124, 125])
def test_bill_never_presents_a_real_charge_as_free(subtotal):
    """Anything owed but under half a note would otherwise round to 0 and
    print as a free bill. The floor lifts it to one note instead."""
    total, _, _, status = logic.compute_bill_totals(subtotal, 0, 0)
    assert total == money.SMALLEST_NOTE
    assert status == "Unpaid"


def test_bill_fully_paid():
    _, _, balance, status = logic.compute_bill_totals(10_000, 0, 10_000)
    assert balance == 0
    assert status == "Fully Paid"


def test_bill_partially_paid():
    _, _, balance, status = logic.compute_bill_totals(10_000, 0, 5_000)
    assert balance == 5_000
    assert status == "Partially Paid"


def test_bill_overpayment_reads_as_paid_with_negative_balance():
    """A negative balance is money owed back to the client, not a bug — the
    Refunds module is what settles it. Status must not read "Partially Paid"."""
    _, _, balance, status = logic.compute_bill_totals(10_000, 0, 10_250)
    assert balance == -250
    assert status == "Fully Paid"


def test_cleanup_writes_off_after_rounding():
    total, _, _, _ = logic.compute_bill_totals(10_000, 0, 0, cleanup_amount=1_000)
    assert total == 9_000


def test_cleanup_cannot_drive_a_bill_negative():
    """A write-off larger than the bill clamps at zero — it must never turn
    into the clinic owing the client money."""
    total, _, _, status = logic.compute_bill_totals(500, 0, 0, cleanup_amount=1_000)
    assert total == 0
    assert status == "N/A"


def test_discount_and_cleanup_apply_in_that_order():
    """Discount is a percentage of the subtotal; Clean Up is a flat amount
    off what remains. Reversing them would make the write-off itself
    discountable and quietly change what the client pays."""
    total, _, _, _ = logic.compute_bill_totals(10_000, 10, 0, cleanup_amount=1_000)
    assert total == 8_000          # 10000 -10% = 9000, then -1000
    assert total != (10_000 - 1_000) * 0.9


def test_cleanup_cap_is_a_flat_global_constant():
    """Not per-role, by design (see money.py). Locked in so a future
    per-role discount change doesn't silently absorb it."""
    assert money.CLEANUP_CAP == 1_000


# ---------------------------------------------------------------------------
# Invariants — these are the ones that catch a bug nobody thought to write
# a specific case for.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("subtotal", [0, 1, 137, 999, 10_000, 33_333, 1_000_000])
@pytest.mark.parametrize("discount", [0, 7, 33, 50, 99, 100])
def test_every_payable_figure_lands_on_a_real_note(subtotal, discount):
    """The whole point of the IQD model: a cashier must be able to physically
    hand over the total and the balance. Both must be multiples of 250."""
    total, _, balance, _ = logic.compute_bill_totals(subtotal, discount, 0)
    assert total % money.SMALLEST_NOTE == 0
    assert balance % money.SMALLEST_NOTE == 0


@pytest.mark.parametrize("subtotal", [0, 250, 10_000])
@pytest.mark.parametrize("cleanup", [0, 250, 1_000, 99_999])
def test_total_is_never_negative(subtotal, cleanup):
    total, _, _, _ = logic.compute_bill_totals(subtotal, 0, 0, cleanup_amount=cleanup)
    assert total >= 0


@pytest.mark.parametrize("subtotal", [250, 1_000, 10_000, 77_777])
def test_paying_the_stated_total_always_settles_the_bill(subtotal):
    """Round-trip: whatever total the app shows, paying exactly that must
    read as Fully Paid. Catches any rounding step applied to the total but
    not to the balance (or vice versa)."""
    total, _, _, _ = logic.compute_bill_totals(subtotal, 0, 0)
    _, _, balance, status = logic.compute_bill_totals(subtotal, 0, total)
    assert status == "Fully Paid"
    assert balance <= 0.5


def test_no_float_dust_survives_into_a_total():
    """0.1 + 0.2 != 0.3 in binary floating point. IQ tolerates float only
    because the 250-rounding step scrubs the dust before anything is stored
    or shown — this proves the scrubbing actually happens."""
    total, _, _, _ = logic.compute_bill_totals(0.1 + 0.2, 0, 0)
    assert total == money.SMALLEST_NOTE
    assert float(total).is_integer()


def test_status_is_always_one_of_the_four_known_values():
    seen = set()
    for subtotal in (0, 125, 10_000):
        for paid in (0, 100, 10_000, 99_999):
            seen.add(logic.compute_bill_totals(subtotal, 0, paid)[3])
    assert seen <= {"N/A", "Unpaid", "Partially Paid", "Fully Paid"}


# ---------------------------------------------------------------------------
# Regression guards — each of these is a bug that actually happened.
# ---------------------------------------------------------------------------

def test_regression_exactly_half_a_note_rounds_up_not_to_free():
    """COMPARISON.md §1.1. Banker's rounding turned a real 125 IQD charge
    into a 0 IQD "free" bill, because 0 is the even multiple."""
    assert money.round_to_denomination(125) != 0
    assert logic.compute_bill_totals(125, 0, 0)[0] == 250


def test_regression_parse_date_validates_the_whole_value_not_a_prefix():
    """v1.10.1. parse_date truncated to 10 characters *before* validating,
    so "2026-08-25garbage" parsed clean and the untruncated string reached a
    DATE column — a reproducible 500 on /visits and /refunds."""
    with pytest.raises(ValueError):
        logic.parse_date("2026-08-25garbage")
    assert logic.parse_date("2026-08-25").isoformat() == "2026-08-25"
    # ...while the ISO timestamps that TEXT columns really store still parse.
    assert logic.parse_date("2026-08-25T02:00:00").isoformat() == "2026-08-25"
