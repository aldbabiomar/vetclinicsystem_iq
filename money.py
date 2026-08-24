"""
Central IQD money helpers. All "payable" figures (totals, balances,
change, refunds, settlement payouts) must go through round_to_denomination()
before being stored/displayed/charged. Do not round subtotals, unit
prices, or cost snapshots this way — see IQD CURRENCY ROUNDING PLAN.md §1.
"""
import math

SMALLEST_NOTE = 250

# Flat ceiling on the cumulative "Clean Up" write-off allowed per bill —
# see CLEANUP_FEATURE_PLAN.md §3.3. Not per-role; a global constant.
CLEANUP_CAP = 1000


def round_to_denomination(amount, denom=SMALLEST_NOTE, mode="nearest"):
    """
    Round `amount` to the nearest multiple of `denom` (default 250 IQD).

    mode:
      "nearest" - standard rounding, half rounds up (use for totals where
                  the discount already benefits the customer)
      "up"      - always round up (use when rounding UP is a courtesy to
                  the *clinic*, e.g. never let a rounding step reduce
                  revenue below what's owed — rare, prefer "nearest")
      "down"    - always round down (use for CHANGE DUE — never make the
                  clinic hand back more cash than it owes; the shortfall,
                  if any, becomes clinic-absorbed rounding)
    """
    if amount is None:
        return None
    if mode == "up":
        return -(-round(amount) // denom) * denom
    if mode == "down":
        return (round(amount) // denom) * denom
    # nearest, half-up — Python's built-in round() breaks an exact .5 tie
    # toward the nearest EVEN multiple (banker's rounding), not always up,
    # so a bill of exactly half a denomination could round either way
    # depending on which side happened to be even (125 IQD -> 0, "free";
    # 375 IQD -> 500 by coincidence of parity, not because it's meant to
    # round up). math.floor(x + 0.5) always breaks the tie up instead.
    return math.floor(amount / denom + 0.5) * denom


def fmt_money(amount):
    """Display formatting — whole-number + thousands separator. Does NOT
    imply 250-rounding; callers must round first if the figure is a
    payable amount."""
    if amount is None:
        return "—"
    return f"{round(amount):,}"


def is_denomination_valid(amount, denom=SMALLEST_NOTE):
    """True if amount is exactly payable with current notes (multiple of
    250). Used for validation/warnings, e.g. on manual billing amounts
    or price list entries."""
    if amount is None:
        return True
    return round(amount) % denom == 0
