import pytest

from app import db
from app.balances import compute_balances
from app.splits import split_equal


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def trip(conn):
    """A group with three members: returns (group_id, [a, b, c])."""
    group = db.create_group(conn, "Trip")
    ids = [db.add_member(conn, group["id"], n)["id"] for n in ("Ali", "Sara", "Omar")]
    return group["id"], ids


# ---------------------------------------------------------------- groups
def test_create_and_get_group(conn):  # AC1.1
    group = db.create_group(conn, "  Flat 4B ")
    assert group == {"id": 1, "name": "Flat 4B"}
    assert db.get_group(conn, 1) == {"id": 1, "name": "Flat 4B", "members": []}
    assert db.list_groups(conn) == [{"id": 1, "name": "Flat 4B"}]


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, None, 5])
def test_invalid_group_names(conn, name):  # AC1.2, AC1.3
    with pytest.raises(db.ValidationError):
        db.create_group(conn, name)


def test_group_name_at_limit_ok(conn):
    assert db.create_group(conn, "x" * 60)["name"] == "x" * 60


def test_get_missing_group(conn):
    with pytest.raises(db.NotFoundError):
        db.get_group(conn, 99)


def test_delete_group_removes_everything(conn, trip):  # AC1.4
    group_id, (a, b, c) = trip
    db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b, c]))
    db.add_settlement(conn, group_id, b, a, 1000)
    db.delete_group(conn, group_id)
    with pytest.raises(db.NotFoundError):
        db.get_group(conn, group_id)
    for table in ("members", "expenses", "expense_shares", "settlements"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


# --------------------------------------------------------------- members
def test_add_member_trims_name(conn):  # AC2.1
    group = db.create_group(conn, "G")
    assert db.add_member(conn, group["id"], "  Ali ")["name"] == "Ali"


def test_duplicate_member_case_insensitive(conn):  # AC2.2
    group = db.create_group(conn, "G")
    db.add_member(conn, group["id"], "Ali")
    with pytest.raises(db.ConflictError):
        db.add_member(conn, group["id"], "ALI")


def test_same_name_allowed_in_other_group(conn):
    g1, g2 = db.create_group(conn, "G1"), db.create_group(conn, "G2")
    db.add_member(conn, g1["id"], "Ali")
    db.add_member(conn, g2["id"], "Ali")


def test_add_member_unknown_group(conn):  # AC2.3
    with pytest.raises(db.NotFoundError):
        db.add_member(conn, 42, "Ali")


@pytest.mark.parametrize("name", ["", "  ", "x" * 51, None])
def test_invalid_member_names(conn, name):
    group = db.create_group(conn, "G")
    with pytest.raises(db.ValidationError):
        db.add_member(conn, group["id"], name)


def test_remove_member_without_activity(conn, trip):  # AC2.4
    group_id, (a, b, c) = trip
    db.remove_member(conn, group_id, c)
    assert [m["id"] for m in db.list_members(conn, group_id)] == [a, b]


def test_remove_member_with_expense_blocked(conn, trip):  # AC2.5
    group_id, (a, b, c) = trip
    db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b]))
    with pytest.raises(db.ConflictError):
        db.remove_member(conn, group_id, b)
    with pytest.raises(db.ConflictError):
        db.remove_member(conn, group_id, a)
    db.remove_member(conn, group_id, c)  # c took no part


def test_remove_missing_member(conn, trip):
    with pytest.raises(db.NotFoundError):
        db.remove_member(conn, trip[0], 999)


# -------------------------------------------------------------- expenses
def test_add_and_get_expense(conn, trip):
    group_id, (a, b, c) = trip
    shares = split_equal(10000, [a, b, c])
    expense = db.add_expense(conn, group_id, "Taxi", 10000, b, "EQUAL", shares)
    assert expense["amount"] == 10000
    assert expense["payer_id"] == b
    assert expense["shares"] == {a: 3334, b: 3333, c: 3333}
    assert db.list_expenses(conn, group_id) == [expense]


def test_payer_outside_group_rejected(conn, trip):  # AC3.7
    group_id, (a, b, c) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, 999, "EQUAL", {a: 100})


def test_participant_outside_group_rejected(conn, trip):  # AC3.7
    group_id, (a, b, c) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "EQUAL", {a: 50, 999: 50})


def test_member_of_other_group_rejected(conn, trip):
    group_id, (a, b, c) = trip
    other = db.create_group(conn, "Other")
    stranger = db.add_member(conn, other["id"], "Zed")["id"]
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "EQUAL", {a: 50, stranger: 50})


def test_no_participants_rejected(conn, trip):  # AC3.8
    group_id, (a, *_rest) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "EQUAL", {})


def test_shares_must_sum_to_amount(conn, trip):
    group_id, (a, b, c) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "EXACT", {a: 50, b: 49})


def test_invalid_split_type_and_description(conn, trip):
    group_id, (a, b, c) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "HALF", {a: 100})
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "  ", 100, a, "EQUAL", {a: 100})


def test_failed_expense_leaves_nothing_behind(conn, trip):
    group_id, (a, b, c) = trip
    with pytest.raises(db.ValidationError):
        db.add_expense(conn, group_id, "X", 100, a, "EQUAL", {a: 50, 999: 50})
    assert db.list_expenses(conn, group_id) == []


def test_update_expense_recalculates(conn, trip):  # AC8.1
    group_id, (a, b, c) = trip
    original = db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b, c]))
    db.update_expense(
        conn, group_id, original["id"], "Dinner (fixed)", 6000, b, "EQUAL", split_equal(6000, [a, c])
    )
    ledger = db.load_ledger(conn, group_id)
    assert compute_balances(*ledger) == {a: -3000, b: 6000, c: -3000}
    assert db.get_expense(conn, group_id, original["id"])["description"] == "Dinner (fixed)"


def test_delete_expense_restores_balances(conn, trip):  # AC8.2
    group_id, (a, b, c) = trip
    before = compute_balances(*db.load_ledger(conn, group_id))
    expense = db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b, c]))
    db.delete_expense(conn, group_id, expense["id"])
    assert compute_balances(*db.load_ledger(conn, group_id)) == before


def test_missing_expense(conn, trip):  # AC8.3
    group_id, (a, *_rest) = trip
    with pytest.raises(db.NotFoundError):
        db.delete_expense(conn, group_id, 999)
    with pytest.raises(db.NotFoundError):
        db.update_expense(conn, group_id, 999, "X", 100, a, "EQUAL", {a: 100})


# ----------------------------------------------------------- settlements
def test_settlement_round_trip(conn, trip):
    group_id, (a, b, c) = trip
    db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b, c]))
    db.add_settlement(conn, group_id, b, a, 3000)
    assert len(db.list_settlements(conn, group_id)) == 1
    balances = compute_balances(*db.load_ledger(conn, group_id))
    assert balances == {a: 3000, b: 0, c: -3000}


def test_settlement_unknown_member(conn, trip):
    with pytest.raises(db.ValidationError):
        db.add_settlement(conn, trip[0], 999, trip[1][0], 100)


def test_ledger_matches_spec_example(conn, trip):  # AC5.1
    group_id, (a, b, c) = trip
    db.add_expense(conn, group_id, "Dinner", 9000, a, "EQUAL", split_equal(9000, [a, b, c]))
    assert compute_balances(*db.load_ledger(conn, group_id)) == {a: 6000, b: -3000, c: -3000}
