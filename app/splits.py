"""Split logic for SplitEase.

All money is integer cents. Every function returns a dict {member_id: cents}
whose values sum EXACTLY to the expense total (business rules BR2-BR4).
"""
from decimal import Decimal, InvalidOperation

MAX_AMOUNT_CENTS = 100_000_000  # BR1: 1,000,000.00


class SplitError(ValueError):
    """Raised when split input breaks a business rule (maps to HTTP 400)."""


def validate_amount(amount):
    """BR1: amount must be a positive integer number of cents, within the maximum."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise SplitError("amount must be an integer number of cents")
    if amount <= 0:
        raise SplitError("amount must be greater than 0")
    if amount > MAX_AMOUNT_CENTS:
        raise SplitError("amount exceeds the maximum of 100000000 cents")


def _check_participants(participants):
    if not participants:
        raise SplitError("at least one participant is required")
    if len(set(participants)) != len(participants):
        raise SplitError("participants must be unique")


def split_equal(amount, participants):
    """BR2: floor(amount / N) each; leftover cents go one each to the first
    participants in member-ID order."""
    validate_amount(amount)
    _check_participants(participants)
    ordered = sorted(participants)
    base, remainder = divmod(amount, len(ordered))
    return {m: base + (1 if i < remainder else 0) for i, m in enumerate(ordered)}


def split_exact(amount, shares):
    """BR3: exact amounts per member; they must sum to the total.
    shares: {member_id: cents}"""
    validate_amount(amount)
    _check_participants(list(shares))
    for cents in shares.values():
        if isinstance(cents, bool) or not isinstance(cents, int) or cents < 0:
            raise SplitError("exact amounts must be non-negative integers")
    if sum(shares.values()) != amount:
        raise SplitError("exact amounts must sum to the expense total")
    return dict(shares)


def split_percent(amount, percents):
    """BR4: percentages (up to 2 decimals) must sum to exactly 100.
    Uses the largest-remainder method so shares sum exactly to the total.
    percents: {member_id: number or numeric string}"""
    validate_amount(amount)
    _check_participants(list(percents))

    # Work in basis points (1% = 100 bp) with Decimal to avoid float error.
    basis = {}
    for member, pct in percents.items():
        try:
            d = Decimal(str(pct))
        except InvalidOperation:
            raise SplitError("percentages must be numbers")
        if not d.is_finite() or d < 0:
            raise SplitError("percentages must be non-negative numbers")
        bp = d * 100
        if bp != bp.to_integral_value():
            raise SplitError("percentages may have at most 2 decimals")
        basis[member] = int(bp)
    if sum(basis.values()) != 10_000:
        raise SplitError("percentages must sum to 100")

    # share = amount * bp / 10000 ; floor first, then hand out leftover cents
    # to the largest fractional remainders (ties: lowest member id).
    floors, remainders = {}, {}
    for member, bp in basis.items():
        q, r = divmod(amount * bp, 10_000)
        floors[member] = q
        remainders[member] = r
    leftover = amount - sum(floors.values())
    order = sorted(basis, key=lambda m: (-remainders[m], m))
    for member in order[:leftover]:
        floors[member] += 1
    return floors
