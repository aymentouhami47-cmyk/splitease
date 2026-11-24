# AI Interaction Log: Developer 2

**Developer:** [Mohamed]  
**Role:** Debt simplification and web front end (HTML, CSS, JavaScript)  
**AI tool:** Claude (Anthropic), chat session with file and code tools  
**Project:** SplitEase

> Format of each entry: what we asked, what the AI produced, what we did with it, and what was wrong or missing.
> Dates: fill in the real date of each session.

---

## D2-01: Debt simplification (`app/simplify.py`, `tests/test_simplify.py`)
- **Date:** [11/22/2026]
- **Prompt (summary):** Given each member's net balance, produce a short list of payments that settles everyone, using the fewest payments.
- **AI output:** A greedy algorithm (largest debtor pays largest creditor) and 9 tests, including a property test that checks the payments settle everyone and that there are at most n − 1 of them. It raises an error if balances do not sum to zero.
- **What we did:** Ran `python -m pytest tests/test_simplify.py`; the result was `9 passed` (the AI had first said 11, which was wrong).
- **Problem found (overclaim):** `SPEC.md` promised the *minimum* number of payments. For balances +5, +4, +4, −5, −8 the code gives 4 payments where 3 are enough (5+4+4 = 13 against −5−8 = −13, and a grouping of {+5, −5}, {+4, +4, −8} needs only 3). The AI's tests only checked "at most n − 1", so they passed.
- **Outcome:** Documented as a known limitation. A true minimum needs subset-sum partitioning and was not implemented.
- **Verdict:** Accepted with a documented limitation.

## D2-02: Web front end (`static/index.html`, `static/style.css`, `static/app.js`)
- **Date:** [11/22/2026]
- **Prompt (summary):** One-page interface in plain HTML, CSS and JavaScript (no framework): groups, members, add and edit expenses (equal, exact, percentage), balances, suggested payments and settlements.
- **AI output:** Complete page with money parsing and formatting done as strings (no floating-point errors), error messages from the API, and an edit mode.
- **Problems found:**
  - When we ran the app, creating a group did nothing. The cause was a missing or empty `app.js` on our branch (and a git commit that reported "no changes added"), not a bug in the logic. The AI's first guesses about the cause were not specific until we sent file sizes and Flask logs.
  - The favicon request returned 404 (a real defect found by the browser check); fixed with an inline favicon link.
  - Design gap: percentage expenses cannot be reopened as percentages; when edited they reopen as exact amounts. Documented as a known limitation.
- **Verdict:** Accepted after fixes.

## D2-03: Browser smoke test (run by the AI, not in the repository)
- **Date:** [11/22/2026]
- **Prompt (summary):** Test the real page in a headless browser.
- **AI output:** A script with 20 checks (create group, add members, add expenses, balances, settle, edit, delete).
- **Problem found:** 2 of 20 checks failed first: one was a flaw in the script itself (it read a stale success message that was still on screen), the other was the real favicon 404 above.
- **Lesson:** Even the AI's tests can be wrong; a failing test is not always a failing app.

## D2-04: Git help and merge problems
- **Date:** [11/22/2026]
- **Prompt (summary):** Pushing and merging our work on GitHub with branches, as a beginner on Windows.
- **Problems:** A push was rejected (remote had new commits), a merge left us in Vim (`:wq` to exit), `git status` failed because of repository permissions, and a missing `simplify.py` on Dev 1's machine caused `ModuleNotFoundError` in the tests until the file was pulled from main.
- **Verdict:** Useful, but only after we sent the exact error text; general instructions alone did not fix our setup.

---

## Summary of my use of AI
| Area | Result |
|---|---|
| Algorithm with clear rules (simplify) | Works and settles everyone, but not always the minimum |
| Front end | Good result, but needed real-browser checks |
| AI's own tests | Sometimes shared its blind spots, or were themselves flawed |
| Explanations (test counts, causes of errors) | Sometimes wrong, so everything was verified by running it |
