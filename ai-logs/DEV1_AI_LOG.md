# AI Interaction Log: Developer 1

**Developer:** [Aymen ]  
**Role:** Backend (split logic, balances, database, REST API)  
**AI tool:** Claude (Anthropic), chat session with file and code tools  
**Project:** SplitEase

> Format of each entry: what we asked, what the AI produced, what we did with it, and what was wrong or missing.
> Dates: fill in the real date of each session.

---

## D1-01: Split logic (`app/splits.py`, `tests/test_splits.py`)
- **Date:** [date]
- **Prompt (summary):** Write pure functions that divide an expense among members in integer cents: equal, exact amounts and percentages. Shares must always add up exactly to the total. Reject invalid input.
- **AI output:** `split_equal`, `split_exact`, `split_percent`, a `SplitError` exception, and 22 tests. Leftover cents go to the lowest member ids. Percentages use decimal arithmetic with the largest-remainder method.
- **What we did:** Copied the files, ran `python -m pytest tests/test_splits.py`, all tests passed.
- **Problem found:** The AI first told us to expect "20 passed", but the real result was `22 passed`. Its own count of its tests was wrong. We trusted the real pytest output, not the AI's statement.
- **Verdict:** Accepted. Well-defined arithmetic with clear rules was correct at the first attempt.

## D1-02: Balances and settlement rules (`app/balances.py`)
- **Date:** [date]
- **Prompt (summary):** Compute each member's net balance from expenses and settlements, and validate a settlement payment (rule BR8 in `SPEC.md`).
- **AI output:** `compute_balances`, `validate_settlement`, 13+ tests.
- **Problem found (rules contradicted each other):** Our first BR8 said a payment is only allowed from a debtor to someone they directly owe. But the debt-simplification feature suggests payments between people with no direct debt (A owes B, B owes C, so A should pay C). The app refused its own suggestion. The AI had not checked the two rules against each other; this appeared when we asked it to test "every suggested payment can be recorded".
- **Fix:** Rule changed to net balances: the amount must be at most the smaller of the payer's total debt and the receiver's total credit. A test `test_every_suggested_payment_can_be_recorded_and_settles_group` (100 random groups) was added.
- **Verdict:** Accepted after the fix. The `SPEC.md` wording of BR8 was updated by us.

## D1-03: SQLite database layer (`app/db.py`)
- **Date:** [date]
- **Prompt (summary):** Store groups, members, expenses, expense shares and settlements in SQLite, with validation and clear errors (validation, not found, conflict).
- **AI output:** Full data layer with foreign keys, cascading deletes and a transaction per write, plus 30+ tests.
- **Problem found (wrong assumption):** Duplicate member names were prevented with `CREATE UNIQUE INDEX ... lower(name)`. SQLite's `lower()` only handles ASCII letters, so "Émile" and "émile" were accepted as two different members, against the spec (409). All earlier tests used ASCII names, so they passed. We found it only when we asked the AI to probe its own code with unusual inputs.
- **Fix:** A `name_key` column computed in Python with Unicode casefold and normalisation, plus automatic upgrade of old database files. Tests added for accents and for composed versus decomposed characters.
- **Verdict:** Accepted after the fix.

## D1-04: REST API (`app/__init__.py`, `app/routes.py`, `docs/API.md`)
- **Date:** [date]
- **Prompt (summary):** Flask app with endpoints for groups, members, expenses (create, edit, delete), balances, settlement plan and settlements. Return JSON errors with correct status codes.
- **AI output:** App factory `create_app`, a blueprint under `/api`, error handlers (400, 404, 409), the API contract in `docs/API.md`, and 74 API tests.
- **Problem found:** A request with a huge id (larger than the database integer size) returned HTTP 500. No test had tried it.
- **Fix:** `OverflowError` mapped to 404, with tests for GET, PUT, POST and DELETE.
- **Verdict:** Accepted after the fix.

## D1-05: Git and environment help
- **Date:** [date]
- **Prompt (summary):** Step-by-step GitHub and Git help for a beginner on Windows (cmd).
- **Problems with the AI's answers:**
  - It first gave Git Bash commands (`touch`) that do not work in cmd; we asked again and it gave cmd versions (`type nul >`, `move /Y`).
  - It said Git ignores empty files; this was wrong (Git ignores only empty folders). It corrected itself when we pointed it out.
  - Merge errors (`untracked working tree files would be overwritten`, `dubious ownership`, a repository inside `C:\Windows\System32`) took several rounds of questions. The fix was a fresh clone in Documents.
- **Verdict:** Useful for concepts, but exact commands needed checking against our real error messages.

---

## Summary of my use of AI
| Area | Result |
|---|---|
| Pure calculation (splits, balances) | Correct first time, 22 + 18 tests |
| Interacting rules (BR8 vs. simplification) | AI missed a contradiction; found by testing |
| Unusual inputs (accented names, huge ids) | AI missed them; found when asked to attack its own code |
| Its own explanations (test counts, Git commands) | Sometimes wrong, so everything was verified by running it |
