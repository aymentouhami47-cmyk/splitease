import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app(":memory:").test_client()


def make_group(client, names=("Ali", "Sara", "Omar")):
    gid = client.post("/api/groups", json={"name": "Trip"}).get_json()["id"]
    ids = [
        client.post(f"/api/groups/{gid}/members", json={"name": n}).get_json()["id"]
        for n in names
    ]
    return gid, ids


def equal_expense(client, gid, payer, participants, amount=9000, description="Dinner"):
    return client.post(
        f"/api/groups/{gid}/expenses",
        json={
            "description": description,
            "amount": amount,
            "payer_id": payer,
            "split_type": "EQUAL",
            "participants": participants,
        },
    )


def balances(client, gid):
    return client.get(f"/api/groups/{gid}/balances").get_json()["balances"]


# ---------------------------------------------------------------- groups
def test_create_group(client):  # AC1.1
    response = client.post("/api/groups", json={"name": "Flat"})
    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "name": "Flat"}


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, None, 7])
def test_create_group_invalid_name(client, name):  # AC1.2, AC1.3
    assert client.post("/api/groups", json={"name": name}).status_code == 400


def test_group_name_60_chars_ok(client):
    assert client.post("/api/groups", json={"name": "x" * 60}).status_code == 201


def test_list_and_get_group(client):
    gid, ids = make_group(client)
    assert client.get("/api/groups").get_json() == [{"id": gid, "name": "Trip"}]
    group = client.get(f"/api/groups/{gid}").get_json()
    assert [m["name"] for m in group["members"]] == ["Ali", "Sara", "Omar"]


def test_get_missing_group(client):
    assert client.get("/api/groups/99").status_code == 404


def test_delete_group(client):  # AC1.4
    gid, ids = make_group(client)
    equal_expense(client, gid, ids[0], ids)
    assert client.delete(f"/api/groups/{gid}").status_code == 204
    assert client.get(f"/api/groups/{gid}").status_code == 404
    assert client.get(f"/api/groups/{gid}/expenses").status_code == 404


def test_body_must_be_json_object(client):
    bad = client.post("/api/groups", data="not json", content_type="application/json")
    assert bad.status_code == 400
    assert client.post("/api/groups", json=["x"]).status_code == 400
    assert client.post("/api/groups").status_code == 400


def test_unknown_api_route_is_json_404(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_home_page_is_served(client):
    assert client.get("/").status_code == 200


# --------------------------------------------------------------- members
def test_add_member(client):  # AC2.1
    gid = client.post("/api/groups", json={"name": "G"}).get_json()["id"]
    response = client.post(f"/api/groups/{gid}/members", json={"name": " Ali "})
    assert response.status_code == 201
    assert response.get_json()["name"] == "Ali"


def test_duplicate_member_name_409(client):  # AC2.2
    gid, _ = make_group(client)
    assert client.post(f"/api/groups/{gid}/members", json={"name": "ALI"}).status_code == 409


def test_add_member_unknown_group(client):  # AC2.3
    assert client.post("/api/groups/9/members", json={"name": "Ali"}).status_code == 404


@pytest.mark.parametrize("name", ["", "  ", "x" * 51, None])
def test_add_member_invalid_name(client, name):
    gid, _ = make_group(client)
    assert client.post(f"/api/groups/{gid}/members", json={"name": name}).status_code == 400


def test_remove_member_without_expenses(client):  # AC2.4
    gid, ids = make_group(client)
    assert client.delete(f"/api/groups/{gid}/members/{ids[2]}").status_code == 204


def test_remove_member_with_expenses_409(client):  # AC2.5
    gid, ids = make_group(client)
    equal_expense(client, gid, ids[0], ids[:2])
    assert client.delete(f"/api/groups/{gid}/members/{ids[1]}").status_code == 409


def test_remove_missing_member(client):
    gid, _ = make_group(client)
    assert client.delete(f"/api/groups/{gid}/members/999").status_code == 404


# -------------------------------------------------------------- expenses
def test_equal_split_100_among_3(client):  # AC3.1
    gid, (a, b, c) = make_group(client)
    response = equal_expense(client, gid, a, [a, b, c], amount=10000)
    assert response.status_code == 201
    assert response.get_json()["shares"] == {str(a): 3334, str(b): 3333, str(c): 3333}


def test_equal_split_one_cent(client):  # AC3.2
    gid, (a, b, c) = make_group(client)
    shares = equal_expense(client, gid, a, [a, b, c], amount=1).get_json()["shares"]
    assert shares == {str(a): 1, str(b): 0, str(c): 0}


@pytest.mark.parametrize("amount", [0, -5, "abc", "100", 100_000_001, 12.5, None, True])
def test_invalid_amount_400(client, amount):  # AC3.3
    gid, (a, b, c) = make_group(client)
    assert equal_expense(client, gid, a, [a, b], amount=amount).status_code == 400


def test_max_amount_ok(client):
    gid, (a, b, c) = make_group(client)
    assert equal_expense(client, gid, a, [a, b, c], amount=100_000_000).status_code == 201


def test_exact_split(client):
    gid, (a, b, c) = make_group(client)
    response = client.post(
        f"/api/groups/{gid}/expenses",
        json={
            "description": "Hotel",
            "amount": 6000,
            "payer_id": c,
            "split_type": "EXACT",
            "shares": {str(a): 4000, str(b): 2000},
        },
    )
    assert response.status_code == 201
    assert balances(client, gid) == {str(a): -4000, str(b): -2000, str(c): 6000}


def test_exact_split_wrong_sum_400(client):  # AC3.4
    gid, (a, b, c) = make_group(client)
    response = client.post(
        f"/api/groups/{gid}/expenses",
        json={
            "description": "Hotel",
            "amount": 6000,
            "payer_id": c,
            "split_type": "EXACT",
            "shares": {str(a): 4000, str(b): 1999},
        },
    )
    assert response.status_code == 400


def percent_expense(client, gid, payer, percents, amount=10000):
    return client.post(
        f"/api/groups/{gid}/expenses",
        json={
            "description": "Gift",
            "amount": amount,
            "payer_id": payer,
            "split_type": "PERCENT",
            "percents": {str(k): v for k, v in percents.items()},
        },
    )


def test_percent_split_sums_exactly(client):  # AC3.6
    gid, (a, b, c) = make_group(client)
    response = percent_expense(client, gid, a, {a: "33.33", b: "33.33", c: "33.34"})
    assert response.status_code == 201
    shares = response.get_json()["shares"]
    assert sum(shares.values()) == 10000
    assert shares[str(c)] == 3334


def test_percent_split_wrong_sum_400(client):  # AC3.5
    gid, (a, b, c) = make_group(client)
    assert percent_expense(client, gid, a, {a: "50", b: "49.99"}).status_code == 400


def test_payer_outside_group_400(client):  # AC3.7
    gid, (a, b, c) = make_group(client)
    assert equal_expense(client, gid, 999, [a, b]).status_code == 400


def test_participant_outside_group_400(client):  # AC3.7
    gid, (a, b, c) = make_group(client)
    assert equal_expense(client, gid, a, [a, 999]).status_code == 400


def test_empty_participants_400(client):  # AC3.8
    gid, (a, b, c) = make_group(client)
    assert equal_expense(client, gid, a, []).status_code == 400


def test_missing_or_invalid_fields_400(client):
    gid, (a, b, c) = make_group(client)
    url = f"/api/groups/{gid}/expenses"
    assert client.post(url, json={}).status_code == 400
    assert client.post(url, json={"split_type": "HALF", "amount": 100}).status_code == 400
    no_desc = {"amount": 100, "payer_id": a, "split_type": "EQUAL", "participants": [a]}
    assert client.post(url, json=no_desc).status_code == 400
    bad_payer = dict(no_desc, description="x", payer_id="1")
    assert client.post(url, json=bad_payer).status_code == 400


def test_expense_for_missing_group_404(client):
    assert equal_expense(client, 99, 1, [1]).status_code == 404


def test_list_expenses(client):
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    expenses = client.get(f"/api/groups/{gid}/expenses").get_json()
    assert len(expenses) == 1
    assert expenses[0]["description"] == "Dinner"


# -------------------------------------------------------------- balances
def test_balances_after_dinner(client):  # AC5.1
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert balances(client, gid) == {str(a): 6000, str(b): -3000, str(c): -3000}


def test_balances_zero_without_expenses(client):  # AC5.3
    gid, ids = make_group(client)
    assert set(balances(client, gid).values()) == {0}


def test_balances_sum_to_zero(client):  # AC5.2
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c], amount=10001)
    equal_expense(client, gid, b, [a, c], amount=777)
    percent_expense(client, gid, c, {a: "12.5", b: "37.5", c: "50"}, amount=999)
    assert sum(balances(client, gid).values()) == 0


def test_balances_missing_group(client):
    assert client.get("/api/groups/9/balances").status_code == 404


# ------------------------------------------------------------ settle plan
def test_settle_plan(client):  # AC6.1
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    payments = client.get(f"/api/groups/{gid}/settle-plan").get_json()["payments"]
    assert sorted((p["from"], p["to"], p["amount"]) for p in payments) == sorted(
        [(b, a, 3000), (c, a, 3000)]
    )


def test_settle_plan_empty_when_settled(client):  # AC6.4
    gid, ids = make_group(client)
    assert client.get(f"/api/groups/{gid}/settle-plan").get_json() == {"payments": []}


# ----------------------------------------------------------- settlements
def settle(client, gid, from_member, to_member, amount):
    return client.post(
        f"/api/groups/{gid}/settlements",
        json={"from_member": from_member, "to_member": to_member, "amount": amount},
    )


def test_valid_settlement(client):  # AC7.1
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert settle(client, gid, b, a, 3000).status_code == 201
    assert balances(client, gid) == {str(a): 3000, str(b): 0, str(c): -3000}
    assert len(client.get(f"/api/groups/{gid}/settlements").get_json()) == 1


def test_settlement_above_debt_400(client):  # AC7.2
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert settle(client, gid, b, a, 3001).status_code == 400


@pytest.mark.parametrize("amount", [0, -100, 10.5, "100", None])
def test_settlement_bad_amount_400(client, amount):  # AC7.3
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert settle(client, gid, b, a, amount).status_code == 400


def test_settlement_to_self_400(client):  # AC7.4
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert settle(client, gid, b, b, 100).status_code == 400


def test_settlement_unknown_member_400(client):
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c])
    assert settle(client, gid, 999, a, 100).status_code == 400


def test_settlement_missing_group_404(client):
    assert settle(client, 99, 1, 2, 100).status_code == 404


def test_member_with_settlement_cannot_be_removed(client):
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b])
    settle(client, gid, b, a, 4500)
    assert client.delete(f"/api/groups/{gid}/members/{b}").status_code == 409


def test_every_suggested_payment_can_be_recorded(client):
    gid, (a, b, c) = make_group(client)
    equal_expense(client, gid, a, [a, b, c], amount=9001)
    equal_expense(client, gid, b, [a, c], amount=2500)
    for payment in client.get(f"/api/groups/{gid}/settle-plan").get_json()["payments"]:
        response = settle(client, gid, payment["from"], payment["to"], payment["amount"])
        assert response.status_code == 201
    assert set(balances(client, gid).values()) == {0}


# ---------------------------------------------------- edit / delete expense
def test_edit_expense_recalculates(client):  # AC8.1
    gid, (a, b, c) = make_group(client)
    expense_id = equal_expense(client, gid, a, [a, b, c]).get_json()["id"]
    response = client.put(
        f"/api/groups/{gid}/expenses/{expense_id}",
        json={
            "description": "Dinner (fixed)",
            "amount": 6000,
            "payer_id": b,
            "split_type": "EQUAL",
            "participants": [a, c],
        },
    )
    assert response.status_code == 200
    assert balances(client, gid) == {str(a): -3000, str(b): 6000, str(c): -3000}


def test_delete_expense_restores_balances(client):  # AC8.2
    gid, (a, b, c) = make_group(client)
    before = balances(client, gid)
    expense_id = equal_expense(client, gid, a, [a, b, c]).get_json()["id"]
    assert client.delete(f"/api/groups/{gid}/expenses/{expense_id}").status_code == 204
    assert balances(client, gid) == before


def test_edit_or_delete_missing_expense_404(client):  # AC8.3
    gid, (a, b, c) = make_group(client)
    assert client.delete(f"/api/groups/{gid}/expenses/999").status_code == 404
    response = client.put(
        f"/api/groups/{gid}/expenses/999",
        json={
            "description": "x",
            "amount": 100,
            "payer_id": a,
            "split_type": "EQUAL",
            "participants": [a],
        },
    )
    assert response.status_code == 404


def test_invalid_edit_leaves_expense_unchanged(client):
    gid, (a, b, c) = make_group(client)
    expense_id = equal_expense(client, gid, a, [a, b, c]).get_json()["id"]
    bad = client.put(
        f"/api/groups/{gid}/expenses/{expense_id}",
        json={
            "description": "x",
            "amount": 6000,
            "payer_id": 999,
            "split_type": "EQUAL",
            "participants": [a],
        },
    )
    assert bad.status_code == 400
    assert balances(client, gid) == {str(a): 6000, str(b): -3000, str(c): -3000}
