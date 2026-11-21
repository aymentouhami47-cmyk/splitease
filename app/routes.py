"""REST API for SplitEase. See docs/API.md for the contract."""
from flask import Blueprint, current_app, jsonify, request

from . import db
from .balances import SettlementError, compute_balances, validate_settlement
from .simplify import simplify
from .splits import SplitError, split_equal, split_exact, split_percent, validate_amount

api = Blueprint("api", __name__, url_prefix="/api")


def conn():
    return current_app.extensions["conn"]


# ------------------------------------------------------------ error mapping
@api.errorhandler(db.ValidationError)
@api.errorhandler(SplitError)
@api.errorhandler(SettlementError)
def _bad_request(error):
    return jsonify({"error": str(error)}), 400


@api.errorhandler(db.NotFoundError)
def _not_found(error):
    return jsonify({"error": str(error)}), 404


@api.errorhandler(db.ConflictError)
def _conflict(error):
    return jsonify({"error": str(error)}), 409


# ----------------------------------------------------------------- helpers
def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise db.ValidationError("request body must be a JSON object")
    return data


def _int(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise db.ValidationError(f"{label} must be an integer")
    return value


def _int_list(value, label):
    if not isinstance(value, list):
        raise db.ValidationError(f"{label} must be a list")
    return [_int(v, label) for v in value]


def _int_key_dict(value, label):
    """JSON object keys are strings; turn them back into member ids."""
    if not isinstance(value, dict):
        raise db.ValidationError(f"{label} must be an object")
    result = {}
    for key, item in value.items():
        try:
            result[int(key)] = item
        except (TypeError, ValueError):
            raise db.ValidationError(f"{label} keys must be member ids")
    return result


def _str_keys(mapping):
    return {str(k): v for k, v in mapping.items()}


def _expense_json(expense):
    result = dict(expense)
    result["shares"] = _str_keys(expense["shares"])
    return result


def _parse_expense(data):
    split_type = data.get("split_type")
    if split_type not in db.SPLIT_TYPES:
        raise db.ValidationError("split_type must be EQUAL, EXACT or PERCENT")
    amount = data.get("amount")
    validate_amount(amount)
    payer_id = _int(data.get("payer_id"), "payer_id")

    if split_type == "EQUAL":
        shares = split_equal(amount, _int_list(data.get("participants"), "participants"))
    elif split_type == "EXACT":
        shares = split_exact(amount, _int_key_dict(data.get("shares"), "shares"))
    else:
        shares = split_percent(amount, _int_key_dict(data.get("percents"), "percents"))
    return data.get("description"), amount, payer_id, split_type, shares


def _balances(group_id):
    return compute_balances(*db.load_ledger(conn(), group_id))


# ------------------------------------------------------------------ groups
@api.post("/groups")
def create_group():
    group = db.create_group(conn(), body().get("name"))
    return jsonify(group), 201


@api.get("/groups")
def list_groups():
    return jsonify(db.list_groups(conn()))


@api.get("/groups/<int:group_id>")
def get_group(group_id):
    return jsonify(db.get_group(conn(), group_id))


@api.delete("/groups/<int:group_id>")
def delete_group(group_id):
    db.delete_group(conn(), group_id)
    return "", 204


# ----------------------------------------------------------------- members
@api.post("/groups/<int:group_id>/members")
def add_member(group_id):
    member = db.add_member(conn(), group_id, body().get("name"))
    return jsonify(member), 201


@api.delete("/groups/<int:group_id>/members/<int:member_id>")
def remove_member(group_id, member_id):
    db.remove_member(conn(), group_id, member_id)
    return "", 204


# --------------------------------------------------------------- expenses
@api.post("/groups/<int:group_id>/expenses")
def add_expense(group_id):
    db.get_group(conn(), group_id)  # 404 before any 400
    description, amount, payer_id, split_type, shares = _parse_expense(body())
    expense = db.add_expense(
        conn(), group_id, description, amount, payer_id, split_type, shares
    )
    return jsonify(_expense_json(expense)), 201


@api.get("/groups/<int:group_id>/expenses")
def list_expenses(group_id):
    return jsonify([_expense_json(e) for e in db.list_expenses(conn(), group_id)])


@api.put("/groups/<int:group_id>/expenses/<int:expense_id>")
def update_expense(group_id, expense_id):
    db.get_expense(conn(), group_id, expense_id)  # 404 before any 400
    description, amount, payer_id, split_type, shares = _parse_expense(body())
    expense = db.update_expense(
        conn(), group_id, expense_id, description, amount, payer_id, split_type, shares
    )
    return jsonify(_expense_json(expense))


@api.delete("/groups/<int:group_id>/expenses/<int:expense_id>")
def delete_expense(group_id, expense_id):
    db.delete_expense(conn(), group_id, expense_id)
    return "", 204


# ------------------------------------------------- balances and settlements
@api.get("/groups/<int:group_id>/balances")
def get_balances(group_id):
    return jsonify({"balances": _str_keys(_balances(group_id))})


@api.get("/groups/<int:group_id>/settle-plan")
def get_settle_plan(group_id):
    return jsonify({"payments": simplify(_balances(group_id))})


@api.post("/groups/<int:group_id>/settlements")
def add_settlement(group_id):
    balances = _balances(group_id)  # also gives 404 for a missing group
    data = body()
    from_member = _int(data.get("from_member"), "from_member")
    to_member = _int(data.get("to_member"), "to_member")
    amount = data.get("amount")
    validate_settlement(balances, from_member, to_member, amount)
    settlement = db.add_settlement(conn(), group_id, from_member, to_member, amount)
    return jsonify(settlement), 201


@api.get("/groups/<int:group_id>/settlements")
def list_settlements(group_id):
    return jsonify(db.list_settlements(conn(), group_id))
