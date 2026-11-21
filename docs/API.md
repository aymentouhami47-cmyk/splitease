# SplitEase API contract

Agreed between Developer 1 (builds it) and Developer 2 (uses it from the web page).
Change this file in a pull request if the contract changes, so both sides stay in sync.

## Conventions
- Base path: `/api`. All bodies and responses are JSON.
- **Money is always integer cents** (`9000` = 90.00). The web page converts to and from `12.34` for display.
- Member ids in JSON objects are strings (`{"1": 3000}`), because JSON keys are always strings.
- Errors have the form `{"error": "readable message"}` with status:
  - `400` invalid input, `404` not found, `409` conflict.

## Groups
| Method and path | Body | Success | Errors |
|---|---|---|---|
| `POST /api/groups` | `{"name": "Trip"}` | `201` `{"id": 1, "name": "Trip"}` | 400 empty / over 60 chars |
| `GET /api/groups` | | `200` `[{"id": 1, "name": "Trip"}]` | |
| `GET /api/groups/<gid>` | | `200` `{"id": 1, "name": "Trip", "members": [{"id": 1, "group_id": 1, "name": "Ali"}]}` | 404 |
| `DELETE /api/groups/<gid>` | | `204` | 404 |

## Members
| Method and path | Body | Success | Errors |
|---|---|---|---|
| `POST /api/groups/<gid>/members` | `{"name": "Ali"}` | `201` `{"id": 1, "group_id": 1, "name": "Ali"}` | 400 bad name, 404 group, 409 duplicate name (case-insensitive) |
| `DELETE /api/groups/<gid>/members/<mid>` | | `204` | 404, 409 member appears in an expense or settlement |

## Expenses
Body for `POST /api/groups/<gid>/expenses` and `PUT /api/groups/<gid>/expenses/<eid>`:

```json
{
  "description": "Dinner",
  "amount": 9000,
  "payer_id": 1,
  "split_type": "EQUAL",
  "participants": [1, 2, 3]
}
```
- `split_type` is `EQUAL`, `EXACT` or `PERCENT`.
- `EQUAL` uses `"participants": [ids]`.
- `EXACT` uses `"shares": {"1": 4000, "2": 5000}` (cents, must sum to `amount`).
- `PERCENT` uses `"percents": {"1": "33.33", "2": "66.67"}` (up to 2 decimals, must sum to 100).

Response (`201` on create, `200` on update):
```json
{
  "id": 1, "group_id": 1, "description": "Dinner", "amount": 9000,
  "payer_id": 1, "split_type": "EQUAL",
  "shares": {"1": 3000, "2": 3000, "3": 3000}
}
```
| Method and path | Success | Errors |
|---|---|---|
| `POST /api/groups/<gid>/expenses` | `201` expense | 400 (amount, split rules, member not in group), 404 group |
| `GET /api/groups/<gid>/expenses` | `200` list of expenses | 404 |
| `PUT /api/groups/<gid>/expenses/<eid>` | `200` expense | 400, 404 |
| `DELETE /api/groups/<gid>/expenses/<eid>` | `204` | 404 |

## Balances and settling
| Method and path | Body | Success | Errors |
|---|---|---|---|
| `GET /api/groups/<gid>/balances` | | `200` `{"balances": {"1": 6000, "2": -3000, "3": -3000}}` (positive = is owed) | 404 |
| `GET /api/groups/<gid>/settle-plan` | | `200` `{"payments": [{"from": 2, "to": 1, "amount": 3000}]}` | 404 |
| `POST /api/groups/<gid>/settlements` | `{"from_member": 2, "to_member": 1, "amount": 3000}` | `201` settlement | 400 (amount, self-payment, over the limit), 404 |
| `GET /api/groups/<gid>/settlements` | | `200` list of settlements | 404 |

### Settlement rule (changes SPEC.md BR8)
A settlement from X to Y may not exceed `min(what X owes overall, what Y is owed overall)`. This is based on net balances, not on direct debts between the two people, so **every payment suggested by `settle-plan` can be recorded as-is**. (The original wording "what the payer owes the receiver" would reject payments like A to C in a chain A to B to C.)

## Static files
Flask serves the `static/` folder at the site root, so `static/index.html` is `/` and the page loads `style.css` and `app.js` from the same folder.
