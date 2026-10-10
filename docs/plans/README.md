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
| B3 | Floor — runs (`GET /runs` becomes real), hand-over, roll off, dyeing loads, breakdowns, roll status and machine status views, board and machine page, `GET /rolls` real, live events | complete: Tasks 1-7 done (roll codes and roll status, reads, start run, end run and hand-over, breakdown and repair, roll off and load rolls, real `GET /rolls`, whole-chain test and live check); on local `main`, not pushed |
| B4 | QC & rolls — inspections, rework, QC queue, real roll passport (buyer sees only their own rolls), plus the fix that a roll's dyeing is finished when its latest dye run has ended | complete: Tasks 1-6 done (latest-dye-run fix, record an inspection, rework runs, QC queue, Roll Passport, whole-chain test and live check); `/qc/analyze` and `/qc/model-card` still examples until B8 |
| B5 | Dispatch & money — scan-to-load rules, invoices, receivables, payables, payment limits, plus the safety net for too-long text and too-large numbers | plan `B5-dispatch-money.md` (5 tasks): **DONE** (Tasks 1-5: error safety net, code sequences, load a dispatch, confirm and the invoice, payments and the real lists, whole-chain test; live check passed 2026-10-10 20:55 IST) |
| B6 | Costing engine — shift-wage split, per-roll and per-order cost, month report | design approved section by section 2026-10-10 21:20 IST and written into spec §7 (+ R18); plan `B6-costing.md` not yet written |
| B7 | Intelligence — delivery date + what-ifs, shortage forecast, root cause, recall | not written |
| B8 | Vision endpoint + model card (after the BV decision) | not written |
| B9 | Seed data + demo scenarios | not written |
| B9a | Starter data and the mid-day demo mill (3 shifts, 10 machines, master data, a working-day story built through the real services) | complete: base seed (3 shifts, 10 machines, master data, 12 workers), `typescript` for the contract script, `npm run db:demo` (a mill in the middle of a working day); B9 proper still waits for B4-B7 |

## Track A — Ridanshi (web app, people, AI layer)

| # | Plan | Status |
|---|---|---|
| A1 | Web foundation — scaffold, typed client, errors, forms, navigation, login, shell, all routes, live updates, phone HTTPS check | **done** except the real-phone camera test: `A1-web-foundation.md` |
| A2 | Store & orders screens | **done**: `A2-store-orders-screens.md` |
| A3 | Floor screens | **done**: `A3-floor-screens.md` |
| A4 | QC + Roll Passport screens | **done**: `A4-qc-and-roll-passport.md` |
| A5 | Dispatch, invoices, money screens | **done**: `A5-dispatch-invoices-money.md` |
| A6 | People module (API + screens) | **done**: `A6-people.md` |
| A7 | Owner dashboard, insights, master-data screens | **done**: `A7-owner-insights-master-data.md` |
| A8 | Language-model module (adapters, tools, report card) + AI screens | **in progress**: backend and screens built, wiring and screen tests left: `A8-language-model.md` |
| A9 | Buyer portal + end-to-end demo script | not written |
| A10 | Login security (guess limiting, password rules, change password, session binding, headers) | **done**: `A10-login-security.md` |
