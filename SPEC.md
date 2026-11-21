# SplitEase: Group Expense Splitter

## 1. Description
SplitEase is a small web application (REST API plus a simple web page) that lets a group of people record shared expenses and see who owes whom. It supports equal, exact-amount and percentage splits, records settlements, and simplifies debts into the fewest possible payments.

All money is stored as **integer cents** to avoid floating-point errors.

## 2. Team and Roles
| Role | Responsibility |
|---|---|
| Developer 1 | Backend: data model, API, split and balance logic |
| Developer 2 | Frontend (simple HTML/JS page), validation, debt simplification, integration |
| Tester 1 | Test plan, manual test cases, bug reports, API tests |
| Tester 2 | Test automation (pytest, Playwright UI tests), test data, boundary and negative tests |

Every member must have commits in the repo. AI interaction logs live in `/ai-logs/` (see section 8).

## 3. Core Features
- **F1 Groups:** create a group, list groups, delete a group.
- **F2 Members:** add and remove members of a group.
- **F3 Expenses:** add an expense with description, amount, payer and split among participants.
- **F4 Split types:** EQUAL, EXACT (amounts per person), PERCENT (percentage per person).
- **F5 Balances:** show each member's net balance (positive = is owed, negative = owes).
- **F6 Debt simplification:** compute the minimum set of payments that settles the group.
- **F7 Settlements:** record a payment from one member to another, which updates balances.
- **F8 Edit and delete expenses:** balances update accordingly.

## 4. User Stories
- US1: As a user, I want to create a group so that I can track shared costs with friends.
- US2: As a user, I want to add members to my group so that everyone involved is included.
- US3: As a user, I want to add an expense paid by one person and split equally, so that nobody has to calculate it manually.
- US4: As a user, I want to split an expense by exact amounts or percentages so that unequal shares are handled.
- US5: As a user, I want to see each member's balance so that I know who is owed money.
- US6: As a user, I want a simplified list of payments so that the group settles with as few transfers as possible.
- US7: As a user, I want to record a settlement so that paid-off debts disappear from the balances.
- US8: As a user, I want to edit or delete a mistaken expense so that balances stay correct.

## 5. Business Rules
- BR1: Amounts are positive integers in cents. Maximum single expense: 100,000,000 cents (1,000,000.00).
- BR2: EQUAL split of N people: each pays `floor(amount / N)`; leftover cents are distributed one cent each to the first participants in member-ID order, so the shares always sum exactly to the amount.
- BR3: EXACT split: the amounts must sum exactly to the expense total.
- BR4: PERCENT split: percentages must sum to exactly 100 (up to 2 decimals). Shares are computed with the largest-remainder method so they sum exactly to the total.
- BR5: The payer must be a member of the group. All participants must be members of the group.
- BR6: A member cannot be removed while their balance is non-zero.
- BR7: Member names are unique within a group (case-insensitive), 1 to 50 characters, trimmed.
- BR8: A settlement amount must be positive and cannot exceed the amount the payer currently owes the receiver.
- BR9: The sum of all balances in a group is always exactly 0.

## 6. Acceptance Criteria

### F1 Groups
- AC1.1: Creating a group with a valid name (1 to 60 chars) returns 201 and the new group with an ID.
- AC1.2: Creating a group with an empty or whitespace-only name returns 400.
- AC1.3: Names longer than 60 characters return 400.
- AC1.4: Deleting a group removes it and all its members, expenses and settlements; a later GET returns 404.

### F2 Members
- AC2.1: Adding a valid, unique member returns 201.
- AC2.2: Adding a duplicate name (case-insensitive) returns 409.
- AC2.3: Adding to a non-existent group returns 404.
- AC2.4: Removing a member with balance 0 and no expenses succeeds (204).
- AC2.5: Removing a member with a non-zero balance returns 409 (BR6).

### F3/F4 Expenses and splits
- AC3.1: A 100.00 expense split equally among 3 gives shares 33.34, 33.33, 33.33.
- AC3.2: A 0.01 expense split equally among 3 gives 0.01, 0.00, 0.00 (still sums to the total).
- AC3.3: Amount 0, negative, non-numeric or above the maximum returns 400.
- AC3.4: EXACT split whose amounts do not sum to the total returns 400.
- AC3.5: PERCENT split whose percentages do not sum to 100 returns 400.
- AC3.6: PERCENT split of 100.00 at 33.33/33.33/33.34 gives shares that sum to exactly 100.00.
- AC3.7: A payer or participant outside the group returns 400.
- AC3.8: An empty participant list returns 400.
- AC3.9: The payer may or may not be among the participants; both cases compute balances correctly.

### F5 Balances
- AC5.1: After A pays 90.00 split equally among A, B, C: A = +60.00, B = -30.00, C = -30.00.
- AC5.2: Balances in any group always sum to 0 (BR9).
- AC5.3: A new group with members and no expenses shows all balances as 0.

### F6 Simplification
- AC6.1: For balances A +60, B -30, C -30 the result is two payments: B to A 30 and C to A 30.
- AC6.2: A chain (A owes B 10, B owes C 10) simplifies to a single payment A to C 10.
- AC6.3: Applying all suggested payments brings every balance to 0.
- AC6.4: When all balances are 0, the result is an empty list.
- AC6.5: The number of payments is at most (number of members with non-zero balance - 1).

### F7 Settlements
- AC7.1: Recording a valid settlement reduces the payer's debt and the receiver's credit by the amount.
- AC7.2: A settlement above the current debt returns 400 (BR8).
- AC7.3: A settlement of 0 or a negative amount returns 400.
- AC7.4: A settlement from a member to themselves returns 400.

### F8 Edit/delete expenses
- AC8.1: Editing an expense recalculates all balances as if the original never existed.
- AC8.2: Deleting an expense restores balances to their previous values.
- AC8.3: Editing or deleting a non-existent expense returns 404.

## 7. Technology Stack
| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Backend framework | Flask |
| Database | SQLite (via the `sqlite3` module) |
| Frontend | Plain HTML, CSS and JavaScript (single page, served by Flask) |
| Unit and API tests | pytest, Flask test client |
| UI tests | Playwright for Python |
| Coverage | pytest-cov |
| Version control | Git and GitHub, feature branches and pull requests |
| AI tools | Claude (web interface) for development and test generation |

## 8. Repository Structure and AI Logs
```
splitease/
  app/            # Flask app, models, split logic, simplification
  static/         # HTML, CSS, JS
  tests/          # unit, API and UI tests
  docs/           # TEST_PLAN.md, bug reports
  ai-logs/        # DEV_AI_LOG.md, TEST_AI_LOG.md
  SPEC.md
  README.md
  requirements.txt
```
Each log entry records: date, member, prompt, summary of AI output, what was wrong or changed, and final outcome. Entries about AI failures are tagged `[FAIL]` so they can be pulled into the final report.

## 9. Out of Scope
Authentication, multiple currencies, receipts and image upload, notifications, mobile apps.
