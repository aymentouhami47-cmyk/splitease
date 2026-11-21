"""SQLite storage layer for SplitEase.

All amounts are integer cents. Functions take an open connection from
connect() and raise ValidationError / NotFoundError / ConflictError, which
the API layer maps to HTTP 400 / 404 / 409.
"""
import sqlite3

MAX_GROUP_NAME = 60
MAX_MEMBER_NAME = 50
MAX_DESCRIPTION = 100
SPLIT_TYPES = ("EQUAL", "EXACT", "PERCENT")


class ValidationError(ValueError):
    """Bad input (HTTP 400)."""


class NotFoundError(LookupError):
    """Row does not exist (HTTP 404)."""


class ConflictError(Exception):
    """Request conflicts with current data (HTTP 409)."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_member_name ON members(group_id, lower(name));
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount INTEGER NOT NULL,
    payer_id INTEGER NOT NULL REFERENCES members(id),
    split_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expense_shares (
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    member_id INTEGER NOT NULL REFERENCES members(id),
    share INTEGER NOT NULL,
    PRIMARY KEY (expense_id, member_id)
);
CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    from_member INTEGER NOT NULL REFERENCES members(id),
    to_member INTEGER NOT NULL REFERENCES members(id),
    amount INTEGER NOT NULL
);
"""


def connect(path=":memory:"):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def _clean(value, max_len, label):
    """Trim and check length (BR7 for member names; same rule for others)."""
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    value = value.strip()
    if not value:
        raise ValidationError(f"{label} must not be empty")
    if len(value) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters")
    return value


# ---------------------------------------------------------------- groups
def create_group(conn, name):
    name = _clean(name, MAX_GROUP_NAME, "group name")
    with conn:
        cur = conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
    return {"id": cur.lastrowid, "name": name}


def list_groups(conn):
    rows = conn.execute("SELECT id, name FROM groups ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_group(conn, group_id):
    row = conn.execute("SELECT id, name FROM groups WHERE id = ?", (group_id,)).fetchone()
    if row is None:
        raise NotFoundError("group not found")
    group = dict(row)
    group["members"] = list_members(conn, group_id)
    return group


def delete_group(conn, group_id):
    get_group(conn, group_id)
    with conn:
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))


# --------------------------------------------------------------- members
def add_member(conn, group_id, name):
    get_group(conn, group_id)
    name = _clean(name, MAX_MEMBER_NAME, "member name")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO members (group_id, name) VALUES (?, ?)", (group_id, name)
            )
    except sqlite3.IntegrityError:
        raise ConflictError("a member with this name already exists in the group")
    return {"id": cur.lastrowid, "group_id": group_id, "name": name}


def list_members(conn, group_id):
    rows = conn.execute(
        "SELECT id, group_id, name FROM members WHERE group_id = ? ORDER BY id", (group_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_member(conn, group_id, member_id):
    row = conn.execute(
        "SELECT id, group_id, name FROM members WHERE id = ? AND group_id = ?",
        (member_id, group_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("member not found")
    return dict(row)


def member_has_activity(conn, member_id):
    """True if the member appears in any expense or settlement."""
    for sql in (
        "SELECT 1 FROM expenses WHERE payer_id = ?",
        "SELECT 1 FROM expense_shares WHERE member_id = ?",
        "SELECT 1 FROM settlements WHERE from_member = ? OR to_member = ?",
    ):
        params = (member_id,) * sql.count("?")
        if conn.execute(sql, params).fetchone():
            return True
    return False


def remove_member(conn, group_id, member_id):
    """BR6/AC2.4-2.5: a member who appears in any expense or settlement
    cannot be removed (this also covers every non-zero balance)."""
    get_member(conn, group_id, member_id)
    if member_has_activity(conn, member_id):
        raise ConflictError("member has expenses or settlements and cannot be removed")
    with conn:
        conn.execute("DELETE FROM members WHERE id = ?", (member_id,))


def _check_members(conn, group_id, member_ids):
    found = {
        r["id"]
        for r in conn.execute("SELECT id FROM members WHERE group_id = ?", (group_id,))
    }
    missing = sorted(set(member_ids) - found)
    if missing:
        raise ValidationError(f"member(s) not in this group: {missing}")


# -------------------------------------------------------------- expenses
def _validate_expense(conn, group_id, description, amount, payer_id, split_type, shares):
    description = _clean(description, MAX_DESCRIPTION, "description")
    if split_type not in SPLIT_TYPES:
        raise ValidationError("split_type must be EQUAL, EXACT or PERCENT")
    if not shares:
        raise ValidationError("at least one participant is required")
    if sum(shares.values()) != amount:
        raise ValidationError("shares must sum to the expense amount")
    _check_members(conn, group_id, [payer_id, *shares])
    return description


def _expense_dict(conn, row):
    expense = dict(row)
    share_rows = conn.execute(
        "SELECT member_id, share FROM expense_shares WHERE expense_id = ? ORDER BY member_id",
        (row["id"],),
    ).fetchall()
    expense["shares"] = {r["member_id"]: r["share"] for r in share_rows}
    return expense


def get_expense(conn, group_id, expense_id):
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ? AND group_id = ?", (expense_id, group_id)
    ).fetchone()
    if row is None:
        raise NotFoundError("expense not found")
    return _expense_dict(conn, row)


def list_expenses(conn, group_id):
    get_group(conn, group_id)
    rows = conn.execute(
        "SELECT * FROM expenses WHERE group_id = ? ORDER BY id", (group_id,)
    ).fetchall()
    return [_expense_dict(conn, r) for r in rows]


def add_expense(conn, group_id, description, amount, payer_id, split_type, shares):
    """shares: {member_id: cents} already computed by app.splits."""
    get_group(conn, group_id)
    description = _validate_expense(
        conn, group_id, description, amount, payer_id, split_type, shares
    )
    with conn:
        cur = conn.execute(
            "INSERT INTO expenses (group_id, description, amount, payer_id, split_type)"
            " VALUES (?, ?, ?, ?, ?)",
            (group_id, description, amount, payer_id, split_type),
        )
        conn.executemany(
            "INSERT INTO expense_shares (expense_id, member_id, share) VALUES (?, ?, ?)",
            [(cur.lastrowid, m, s) for m, s in shares.items()],
        )
    return get_expense(conn, group_id, cur.lastrowid)


def update_expense(conn, group_id, expense_id, description, amount, payer_id, split_type, shares):
    get_expense(conn, group_id, expense_id)
    description = _validate_expense(
        conn, group_id, description, amount, payer_id, split_type, shares
    )
    with conn:
        conn.execute(
            "UPDATE expenses SET description = ?, amount = ?, payer_id = ?, split_type = ?"
            " WHERE id = ?",
            (description, amount, payer_id, split_type, expense_id),
        )
        conn.execute("DELETE FROM expense_shares WHERE expense_id = ?", (expense_id,))
        conn.executemany(
            "INSERT INTO expense_shares (expense_id, member_id, share) VALUES (?, ?, ?)",
            [(expense_id, m, s) for m, s in shares.items()],
        )
    return get_expense(conn, group_id, expense_id)


def delete_expense(conn, group_id, expense_id):
    get_expense(conn, group_id, expense_id)
    with conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ----------------------------------------------------------- settlements
def add_settlement(conn, group_id, from_member, to_member, amount):
    get_group(conn, group_id)
    _check_members(conn, group_id, [from_member, to_member])
    with conn:
        cur = conn.execute(
            "INSERT INTO settlements (group_id, from_member, to_member, amount)"
            " VALUES (?, ?, ?, ?)",
            (group_id, from_member, to_member, amount),
        )
    return {
        "id": cur.lastrowid,
        "group_id": group_id,
        "from_member": from_member,
        "to_member": to_member,
        "amount": amount,
    }


def list_settlements(conn, group_id):
    get_group(conn, group_id)
    rows = conn.execute(
        "SELECT id, group_id, from_member, to_member, amount FROM settlements"
        " WHERE group_id = ? ORDER BY id",
        (group_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- ledger
def load_ledger(conn, group_id):
    """Everything compute_balances() needs, for one group:
    (member_ids, expenses, settlements)."""
    group = get_group(conn, group_id)
    member_ids = [m["id"] for m in group["members"]]
    expenses = [
        {"payer": e["payer_id"], "amount": e["amount"], "shares": e["shares"]}
        for e in list_expenses(conn, group_id)
    ]
    settlements = [
        {"from": s["from_member"], "to": s["to_member"], "amount": s["amount"]}
        for s in list_settlements(conn, group_id)
    ]
    return member_ids, expenses, settlements
