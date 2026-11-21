"""Debt simplification for SplitEase (feature F6).

Input: balances {member_id: cents}; positive = is owed, negative = owes.
Output: list of payments [{"from": id, "to": id, "amount": cents}].
Greedy: repeatedly match the largest debtor with the largest creditor.
Result has at most (members with non-zero balance - 1) payments.
"""


def simplify(balances):
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to 0")

    creditors = {m: b for m, b in balances.items() if b > 0}
    debtors = {m: -b for m, b in balances.items() if b < 0}
    payments = []

    while creditors and debtors:
        # largest first; ties broken by lowest id so output is deterministic
        c = min(creditors, key=lambda m: (-creditors[m], m))
        d = min(debtors, key=lambda m: (-debtors[m], m))
        amount = min(creditors[c], debtors[d])
        payments.append({"from": d, "to": c, "amount": amount})
        creditors[c] -= amount
        debtors[d] -= amount
        if creditors[c] == 0:
            del creditors[c]
        if debtors[d] == 0:
            del debtors[d]
    return payments
