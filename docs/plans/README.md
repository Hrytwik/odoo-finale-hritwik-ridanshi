# Implementation Plans

> **Summary:** Ordered list of every implementation plan for both tracks, with status. Plans are written one at a time when a track reaches them; this index is the full backlog.
> **Last updated:** 2026-10-10

Spec: `docs/specs/2026-10-10-textile-mill-design.md`. Mark a plan **done** here (never delete rows) when its "Done when" list is met.

## Track B — Hritwik (backend, data, ML)

| # | Plan | Status |
|---|---|---|
| B1 | Foundation — API skeleton, all 29 tables, login, uploads, live events, master data, full API contract with example data | done: all 13 tasks, plus the test-database guard (branch `b/foundation`) |
| BV | Vision spike — cloth photos, labelling, YOLO fine-tune, 3-hour kill criteria (runs in parallel from the start) | not written |
| B2 | Store & orders — receiving, ledger, stock and yarn-need views, yarn check, order lifecycle | not written |
| B3 | Floor — runs, hand-over, roll off, dyeing loads, breakdowns, machine status view, live events | not written |
| B4 | QC & rolls — inspections, rework, roll status view, passport data | not written |
| B5 | Dispatch & money — scan-to-load rules, invoices, receivables, payables, payment limits | not written |
| B6 | Costing engine — shift-wage split, per-roll and per-order cost, month report | not written |
| B7 | Intelligence — delivery date + what-ifs, shortage forecast, root cause, recall | not written |
| B8 | Vision endpoint + model card (after the BV decision) | not written |
| B9 | Seed data + demo scenarios | not written |

## Track A — Ridanshi (web app, people, AI layer)

| # | Plan | Status |
|---|---|---|
| A1 | Web foundation — scaffold, typed client, errors, forms, navigation, login, shell, all routes, live updates, phone HTTPS check | **done** except the real-phone camera test: `A1-web-foundation.md` |
| A2 | Store & orders screens | **done**: `A2-store-orders-screens.md` |
| A3 | Floor screens | **done**: `A3-floor-screens.md` |
| A4 | QC + Roll Passport screens | not written |
| A5 | Dispatch, invoices, money screens | not written |
| A6 | People module (API + screens) | not written |
| A7 | Owner dashboard, insights, master-data screens | not written |
| A8 | Language-model module (adapters, tools, report card) + AI screens | not written |
| A9 | Buyer portal + end-to-end demo script | not written |
