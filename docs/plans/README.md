# Implementation Plans

> **Summary:** Ordered list of every implementation plan for both tracks, with status. Plans are written one at a time when a track reaches them; this index is the full backlog.
> **Last updated:** 2026-10-10

Spec: `docs/specs/2026-10-10-textile-mill-design.md`. Mark a plan **done** here (never delete rows) when its "Done when" list is met.

## Track B — Hritwik (backend, data, ML)

| # | Plan | Status |
|---|---|---|
| B1 | Foundation — API skeleton, all 29 tables, login, uploads, live events, master data, full API contract with example data | done: all 13 tasks, plus the test-database guard (branch `b/foundation`) |
| BV | Vision spike — public-data-only pivot (no own photos exist) | PARKED: trained (validation mAP50 0.70) and scored on the public test split (holes 24/26 found, stains 18/29, thread faults 8/32); verdict inconclusive because no matching clean images exist for the false-alarm rate; resume notes and photo checklist in `BV-vision-spike.md` |
| B2 | Store & orders — receiving, ledger, stock and yarn-need views, yarn check, order lifecycle | complete: Tasks 1–7 done (money helpers, code sequences, stock views, receive lot and lot reads, stock endpoint, issue/return/adjust/block with row locking, real orders with yarn check, progress and stage); DONE (all 7 tasks, 504 tests, live check passed); merged to local `main`, not pushed |
| B3 | Floor — runs (`GET /runs` becomes real), hand-over, roll off, dyeing loads, breakdowns, roll status and machine status views, board and machine page, `GET /rolls` real, live events | plan `B3-floor.md` (7 tasks); Tasks 1-4 done (roll codes, roll-status view, reads, start run, end run, hand-over), next Task 5 (breakdown, repair) |
| B4 | QC & rolls — inspections, rework, roll status view, passport data (the passport must use `buyer_view` and refuse rolls that are not the buyer's own; `GET /rolls` becomes real) | not written |
| B5 | Dispatch & money — scan-to-load rules, invoices, receivables, payables, payment limits | not written |
| B6 | Costing engine — shift-wage split, per-roll and per-order cost, month report | not written |
| B7 | Intelligence — delivery date + what-ifs, shortage forecast, root cause, recall | not written |
| B8 | Vision endpoint + model card (after the BV decision) | not written |
| B9 | Seed data + demo scenarios | not written |

## Track A — Ridanshi (web app, people, AI layer)

| # | Plan | Status |
|---|---|---|
| A1 | Web foundation — scaffold, typed client, errors, forms, navigation, login, shell, all routes, live updates, phone HTTPS check | written: `A1-web-foundation.md` |
| A2 | Store & orders screens | not written |
| A3 | Floor screens | not written |
| A4 | QC + Roll Passport screens | not written |
| A5 | Dispatch, invoices, money screens | not written |
| A6 | People module (API + screens) | not written |
| A7 | Owner dashboard, insights, master-data screens | not written |
| A8 | Language-model module (adapters, tools, report card) + AI screens | not written |
| A9 | Buyer portal + end-to-end demo script | not written |
