"""Balance calculation for SplitEase (features F5 and F7).

Balances are {member_id: cents}. Positive = the member is owed money,
negative = the member owes money. The sum of all balances is always 0 (BR9).
"""


class SettlementError(ValueError):
    """Raised when a settlement breaks a rule (maps to HTTP 400)."""


def _add(balances, member, delta):
    if member not in balances:
        raise ValueError(f"unknown member {member}")
    balances[member] += delta


def compute_balances(member_ids, expenses, settlements):
    """expenses:    [{"payer": id, "amount": cents, "shares": {id: cents}}]
    settlements: [{"from": id, "to": id, "amount": cents}]

    The payer is credited the full amount, every participant is debited
    their share. A settlement moves the payer's balance up and the
    receiver's balance down by the same amount."""
    balances = {m: 0 for m in member_ids}
    for e in expenses:
        _add(balances, e["payer"], e["amount"])
        for member, share in e["shares"].items():
            _add(balances, member, -share)
    for s in settlements:
        _add(balances, s["from"], s["amount"])
        _add(balances, s["to"], -s["amount"])
    return balances


def max_settlement(balances, from_id, to_id):
    """The most that from_id can currently pay to_id: it is limited by how
    much from_id owes overall and by how much to_id is owed overall."""
    return max(0, min(-balances[from_id], balances[to_id]))


def validate_settlement(balances, from_id, to_id, amount):
    """BR8 (balance-based): amount must be positive and cannot exceed
    max_settlement(). This is what makes every payment suggested by
    simplify() recordable."""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise SettlementError("amount must be a positive integer number of cents")
    if from_id == to_id:
        raise SettlementError("a member cannot settle with themselves")
    for member in (from_id, to_id):
        if member not in balances:
            raise SettlementError(f"unknown member {member}")
    allowed = max_settlement(balances, from_id, to_id)
    if amount > allowed:
        raise SettlementError(
            f"amount exceeds what can be settled between these members ({allowed} cents)"
        )
