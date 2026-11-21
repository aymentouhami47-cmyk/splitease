import random

import pytest

from app.balances import (
    SettlementError,
    compute_balances,
    max_settlement,
    validate_settlement,
)
from app.simplify import simplify
from app.splits import split_equal, split_percent


def expense(payer, amount, participants):
    return {"payer": payer, "amount": amount, "shares": split_equal(amount, participants)}


def test_equal_split_90_among_3():  # AC5.1
    balances = compute_balances([1, 2, 3], [expense(1, 9000, [1, 2, 3])], [])
    assert balances == {1: 6000, 2: -3000, 3: -3000}


def test_payer_not_among_participants():  # AC3.9
    balances = compute_balances([1, 2, 3], [expense(1, 6000, [2, 3])], [])
    assert balances == {1: 6000, 2: -3000, 3: -3000}


def test_no_expenses_all_zero():  # AC5.3
    assert compute_balances([1, 2, 3], [], []) == {1: 0, 2: 0, 3: 0}


def test_settlement_reduces_debt_and_credit():  # AC7.1
    balances = compute_balances(
        [1, 2, 3],
        [expense(1, 9000, [1, 2, 3])],
        [{"from": 2, "to": 1, "amount": 3000}],
    )
    assert balances == {1: 3000, 2: 0, 3: -3000}


def test_unknown_member_rejected():
    with pytest.raises(ValueError):
        compute_balances([1, 2], [expense(1, 100, [1, 3])], [])


def test_max_settlement():
    balances = {1: 6000, 2: -3000, 3: -3000}
    assert max_settlement(balances, 2, 1) == 3000
    assert max_settlement(balances, 1, 2) == 0  # wrong direction
    assert max_settlement(balances, 2, 3) == 0  # both owe money


def test_settlement_valid():
    validate_settlement({1: 6000, 2: -3000, 3: -3000}, 2, 1, 3000)


def test_settlement_above_debt_rejected():  # AC7.2
    with pytest.raises(SettlementError):
        validate_settlement({1: 6000, 2: -3000, 3: -3000}, 2, 1, 3001)


@pytest.mark.parametrize("amount", [0, -5, 10.5, "100", None, True])
def test_settlement_bad_amount_rejected(amount):  # AC7.3
    with pytest.raises(SettlementError):
        validate_settlement({1: 6000, 2: -3000, 3: -3000}, 2, 1, amount)


def test_settlement_to_self_rejected():  # AC7.4
    with pytest.raises(SettlementError):
        validate_settlement({1: 6000, 2: -3000, 3: -3000}, 2, 2, 100)


def test_settlement_unknown_member_rejected():
    with pytest.raises(SettlementError):
        validate_settlement({1: 6000, 2: -6000}, 2, 9, 100)


def _random_expense(rng, member_ids):
    participants = rng.sample(member_ids, rng.randint(1, len(member_ids)))
    amount = rng.randint(1, 1_000_000)
    if rng.random() < 0.5 or len(participants) == 1:
        shares = split_equal(amount, participants)
    else:
        cuts = sorted(rng.sample(range(1, 10_000), len(participants) - 1))
        points = [0, *cuts, 10_000]
        percents = {
            p: f"{(points[i + 1] - points[i]) / 100:.2f}" for i, p in enumerate(participants)
        }
        shares = split_percent(amount, percents)
    return {"payer": rng.choice(member_ids), "amount": amount, "shares": shares}


def test_balances_always_sum_to_zero():  # AC5.2 / BR9
    rng = random.Random(2026)
    for _ in range(200):
        members = list(range(1, rng.randint(2, 7)))  # at least 2 members
        members = members or [1, 2]
        expenses = [_random_expense(rng, members) for _ in range(rng.randint(0, 8))]
        assert sum(compute_balances(members, expenses, []).values()) == 0


def test_every_suggested_payment_can_be_recorded_and_settles_group():
    rng = random.Random(7)
    for _ in range(100):
        members = list(range(1, rng.randint(3, 7)))
        expenses = [_random_expense(rng, members) for _ in range(rng.randint(1, 8))]
        settlements = []
        for payment in simplify(compute_balances(members, expenses, settlements)):
            current = compute_balances(members, expenses, settlements)
            validate_settlement(current, payment["from"], payment["to"], payment["amount"])
            settlements.append(
                {"from": payment["from"], "to": payment["to"], "amount": payment["amount"]}
            )
        final = compute_balances(members, expenses, settlements)
        assert all(v == 0 for v in final.values())
