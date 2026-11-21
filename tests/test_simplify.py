import pytest
from app.simplify import simplify


def apply(balances, payments):
    result = dict(balances)
    for p in payments:
        result[p["from"]] += p["amount"]
        result[p["to"]] -= p["amount"]
    return result


def test_two_debtors_one_creditor():  # AC6.1
    payments = simplify({"A": 6000, "B": -3000, "C": -3000})
    assert sorted((p["from"], p["to"], p["amount"]) for p in payments) == [
        ("B", "A", 3000),
        ("C", "A", 3000),
    ]


def test_chain_collapses_to_one_payment():  # AC6.2
    # A owes B 10, B owes C 10  ->  net A -10, B 0, C +10
    assert simplify({"A": -1000, "B": 0, "C": 1000}) == [
        {"from": "A", "to": "C", "amount": 1000}
    ]


def test_all_zero_gives_empty_list():  # AC6.4
    assert simplify({"A": 0, "B": 0}) == []


def test_empty_group():
    assert simplify({}) == []


def test_unbalanced_input_rejected():
    with pytest.raises(ValueError):
        simplify({"A": 100, "B": -50})


@pytest.mark.parametrize(
    "balances",
    [
        {"A": 6000, "B": -3000, "C": -3000},
        {"A": 5000, "B": 3000, "C": -4000, "D": -4000},
        {"A": 1, "B": -1},
        {"A": 700, "B": 200, "C": -300, "D": -250, "E": -350},
    ],
)
def test_payments_settle_everyone_and_are_minimal(balances):  # AC6.3, AC6.5
    payments = simplify(balances)
    assert all(v == 0 for v in apply(balances, payments).values())
    non_zero = sum(1 for v in balances.values() if v != 0)
    assert len(payments) <= max(non_zero - 1, 0)
    assert all(p["amount"] > 0 for p in payments)
