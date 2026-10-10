# B2 — Store and Orders (real logic) Implementation Plan

> **Summary:** Replaces the example-data stubs for the yarn store and the order lifecycle with real, tested logic: lot receiving (lot + ledger entry + supplier bill in one transaction), stock from the ledger, yarn issue/return/adjust with row locking, free-stock and "enough yarn?" calculation, order create/confirm/cancel/deadline, order progress and stage, block lot, and live events. API shapes do not change.
> **Last updated:** 2026-10-10 (Tasks 1-3 done)

## Status

Tasks 1, 2 and 3 are done and verified (full suite 395 passed, twice; `contracts/` unchanged). Next: Task 4. Decisions taken while building Task 3 (not in the original plan):

- **Boolean guard on every numeric request field.** pydantic reads JSON `true`/`false` as 1.0/0.0 for a float, so `{"qty_kg": true}` was accepted as 1 kg. `NoBool` (in `app/core/schemas.py`) is now part of every numeric input type, written **after** `Field(...)` (`Annotated[float, Field(gt=0), NoBool]`); in the other order pydantic writes `gt`/`le` into the OpenAPI schema and changes the contract. `tests/test_input_numbers.py` scans every `*In`/`*Patch` model, so new numeric fields are covered automatically. Not covered: `true` for integer id fields (reads as 1).
- **Contract guard:** `tests/test_contract.py::test_committed_contract_matches_the_code` fails if `contracts/openapi.json` differs from what the code produces (after an intended API change run `npm run contracts`).
- IST dates come from `app/core/clock.py` (`today_ist()`), reused by Task 6.
- Events are published directly after `commit(db)` in the service (`broadcaster.publish`); the `pubsub.py` helper in the file list below was not needed.
- A lot's bill is created through the `lot.bill` relationship so lot, receipt and bill go out in one flush and a duplicate challan rolls all three back.

**Goal:** every endpoint under `/api/lots`, `/api/movements`, `/api/stock` and `/api/orders` (except `/api/lots/{code}/recall`, which is B7) runs on real data with the rules from spec §6 (R1, R2, R3, R14), and the generated `contracts/openapi.json` stays **byte-identical**.

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §4.1, §4.5, §5, §6. **Depends on:** B1 (tables, auth, error format, contract stubs).

**How this plan is executed:** inline, one task at a time, test first, full suite twice at each boundary; the final code is copied into this plan after each task is verified (as in B1), so the plan never contains code that was not run.

## Global Constraints

- Quantities are `Decimal` end to end (kg and metres to 3 places, money to 2 places, `ROUND_HALF_UP`); only the JSON edge converts to `float`. Never do arithmetic on floats.
- Every write happens in one transaction and goes through `commit(db)` (which maps database constraint errors to the standard error shape). Live events are published **only after a successful commit**, never on failure.
- Stock is never stored. `on hand` = sum of `yarn_movements.qty_kg` for the lot; it must never go negative, even with two simultaneous requests.
- Buyers have no access to anything in this plan. Roles are exactly those on the existing routers (reads: store, owner, supervisor, accountant as before; writes below).
- Error codes are stable strings; field names in errors match the request field names (`lot_code`, `qty_kg`, `run_id`, `deadline`, `intended_order_code`, `challan_photo_path`).
- Commit messages: plain imperative subject, no trailers.

## Decisions made in this plan (not spelled out in the spec)

1. **Code numbers** (`L-0017`, `ORD-0012`) come from Postgres sequences via one helper, so two simultaneous requests can never get the same number. Gaps after a failed request are acceptable. Test factories use the same helper so tests can never collide with real codes.
2. **Views for stock** (`v_lot_stock`, `v_order_yarn_need`, `v_yarn_type_stock`) are real SQL views created by a hand-written migration. `v_order_yarn_need` includes draft orders (with a `state` column) so "can this draft order start?" can be answered; only `confirmed` orders reserve yarn.
3. **Order progress and stage are computed in the service layer** (SQL queries per order), not as a SQL view. The spec's principle (derived, never stored) holds; this avoids a large SQL view that B3–B5 would have to rewrite. Spec §4.5's `v_order_progress` is therefore implemented as a function; note this in the spec when B2 is done.
4. **Extra rule R2b:** yarn may only be issued to a run whose order's fabric recipe uses that yarn type (`YARN_NOT_IN_RECIPE`), otherwise the need calculation would never see it.
5. **A draft or cancelled order never reserves yarn.** "Enough yarn" for an order compares its outstanding need with stock left after *other confirmed* orders.
6. `delivery_date` and `days_late` stay `null` until B7.

## Hand-worked numbers (the tests assert these)

Order: 5,000 m of Poplin, recipe 30s cotton 0.12 kg/m, wastage 5%.
- need = 5000 × 0.12 × 1.05 = **630.000 kg** per the single recipe line.
- Lot A (30s cotton) received 800 kg at ₹250/kg: bill amount = 800 × 250 = **₹200,000.00**.
- Issue 587.5 kg to the order's spinning run: lot A on hand = 800 − 587.5 = **212.5 kg**; the order's issued = 587.5; outstanding = 630 − 587.5 = **42.5 kg**.
- Another confirmed order needs 400 kg (nothing issued). Free stock for 30s cotton = on hand 212.5 − outstanding (42.5 + 400) = **−230 kg** → below reorder level 300 → `below_reorder = true`.
- Yarn check for the 400 kg order: others' outstanding = 42.5; available = 212.5 − 42.5 = 170; its outstanding 400 → **short 230 kg**, `can_start = false`.
- Return 20 kg from that run: issued = 567.5, outstanding = 62.5, on hand = 232.5.
- Blocking lot A removes its stock from `on_hand` (free becomes −(42.5+400) = −442.5).

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **Two simultaneous issues against the last kilos** → exactly one succeeds, the other gets `INSUFFICIENT_STOCK`, stock never negative (real concurrent database sessions). Task 5.
2. **Same delivery received twice at the same moment** (same supplier, challan, yarn type) → one lot, one `DUPLICATE_CHALLAN`, no orphan bill or ledger row. Task 3.
3. **A `challan_photo_path` that is not one of our upload paths** (`../../etc/passwd`, an external URL) → 422 on `challan_photo_path`, never stored. Task 3.
4. **Decimal edge values:** `qty_kg` with more than 3 decimals, `0.0004`, `1e9`, `NaN`/`Infinity` → clean 422, never a 500 or a silently different number. Task 3.
5. **Returning more than was issued, returning to a run of another lot's yarn type, and issuing from a blocked lot** → specific errors. Task 5.

---

## File Structure

```
services/api/
  alembic/versions/<id>_stock_views_and_code_sequences.py   hand-written: 3 views + 2 sequences
  app/core/codes.py            next_code(db, kind) using sequences
  app/core/money.py            dec(), q_kg(), q_money(), to_float()
  app/core/pubsub.py           publish_after_commit helper (events only after success)
  app/modules/store/service.py     lots, ledger, stock rules (R1, R2, R2b, R14)
  app/modules/store/router.py      real handlers (recall stays the example stub)
  app/modules/orders/service.py    create/confirm/cancel/deadline, progress, stage, yarn check (R3)
  app/modules/orders/router.py     real handlers
  tests/test_codes.py  test_money.py  test_stock_views.py  test_store_*.py  test_orders_*.py
```

Existing `app/modules/store/examples.py` keeps only what the recall stub still uses; `orders/examples.py` is deleted when nothing imports it.

---

### Task 1: Money helpers and code numbers

**Interfaces — Produces:** `dec(value) -> Decimal` (accepts int/float/str/Decimal; rejects NaN/Infinity/booleans with `ValueError`); `q_kg(d) -> Decimal` (3 places), `q_money(d) -> Decimal` (2 places), both `ROUND_HALF_UP`; `to_float(d) -> float`; `next_code(db, kind: Literal["lot","order"]) -> str` returning `L-0001` / `ORD-0001` (zero-padded to 4, longer when needed).

**Migration (hand-written, revision "stock views and code sequences"):** `CREATE SEQUENCE lot_code_seq`, `CREATE SEQUENCE order_code_seq` (both start 1). Downgrade drops them. (The three views are added in Task 2's revision so each step is independently testable.)

**Tests (write first):**
- `dec("12.3456")` → `Decimal("12.3456")`; `dec(0.1)` equals `Decimal("0.1")` (via `str`, not the binary float); `dec(float("nan"))`, `dec(float("inf"))`, `dec(True)` raise `ValueError`.
- `q_kg(Decimal("1.0005"))` = `1.001` (half up); `q_kg(Decimal("1.0004"))` = `1.000`; `q_money(Decimal("2.675"))` = `2.68`.
- `next_code(db, "lot")` returns a string matching `^L-\d{4,}$` and two calls differ; `"order"` gives `ORD-`; an unknown kind raises.
- Two sessions on separate connections calling `next_code` 20 times each concurrently produce 40 distinct values.
- Factories `make_lot` and `make_order` are changed to call `next_code` instead of their own counters; the whole existing suite still passes.

### Task 2: Stock views

**Migration "stock views":** exactly the SQL below.

```sql
CREATE VIEW v_lot_stock AS
SELECT yarn_lot_id, COALESCE(SUM(qty_kg), 0)::numeric(12,3) AS on_hand_kg
FROM yarn_movements GROUP BY yarn_lot_id;

CREATE VIEW v_order_yarn_need AS
WITH recipe AS (
  SELECT o.id AS order_id, o.state, frl.yarn_type_id,
         ROUND(o.qty_metres * frl.kg_per_metre * (1 + ft.wastage_pct / 100), 3) AS need_kg
  FROM orders o
  JOIN fabric_types ft ON ft.id = o.fabric_type_id
  JOIN fabric_recipe_lines frl ON frl.fabric_type_id = ft.id
), issued AS (
  SELECT r.order_id, l.yarn_type_id, -SUM(m.qty_kg) AS issued_kg
  FROM yarn_movements m
  JOIN production_runs r ON r.id = m.production_run_id
  JOIN yarn_lots l ON l.id = m.yarn_lot_id
  WHERE m.kind IN ('issue', 'return')
  GROUP BY r.order_id, l.yarn_type_id
)
SELECT recipe.order_id, recipe.state, recipe.yarn_type_id, recipe.need_kg,
       COALESCE(issued.issued_kg, 0) AS issued_kg,
       GREATEST(0, recipe.need_kg - COALESCE(issued.issued_kg, 0)) AS outstanding_kg
FROM recipe LEFT JOIN issued
  ON issued.order_id = recipe.order_id AND issued.yarn_type_id = recipe.yarn_type_id;

CREATE VIEW v_yarn_type_stock AS
SELECT yt.id AS yarn_type_id, yt.reorder_level_kg,
       COALESCE(oh.on_hand_kg, 0) AS on_hand_kg,
       COALESCE(os.outstanding_kg, 0) AS outstanding_kg,
       COALESCE(oh.on_hand_kg, 0) - COALESCE(os.outstanding_kg, 0) AS free_kg,
       (COALESCE(oh.on_hand_kg, 0) - COALESCE(os.outstanding_kg, 0)) < yt.reorder_level_kg AS below_reorder
FROM yarn_types yt
LEFT JOIN (SELECT l.yarn_type_id, SUM(s.on_hand_kg) AS on_hand_kg
           FROM yarn_lots l JOIN v_lot_stock s ON s.yarn_lot_id = l.id
           WHERE NOT l.is_blocked GROUP BY l.yarn_type_id) oh ON oh.yarn_type_id = yt.id
LEFT JOIN (SELECT yarn_type_id, SUM(outstanding_kg) AS outstanding_kg
           FROM v_order_yarn_need WHERE state = 'confirmed' GROUP BY yarn_type_id) os ON os.yarn_type_id = yt.id;
```
Downgrade drops the three views in reverse order.

**Tests (factories build the data; assert the hand-worked numbers above):**
- `v_lot_stock`: receipt 800, issue −587.5, return +20 → 232.5; a lot with only a receipt → its quantity.
- `v_order_yarn_need`: need 630.000; issued 587.5 → outstanding 42.5; after a 20 kg return → issued 567.5, outstanding 62.5; issued above need → outstanding 0 (never negative); a recipe with two yarn types gives two rows; yarn issued to a *different* order's run is not counted.
- `v_yarn_type_stock`: the −230 scenario (lot 212.5, outstanding 42.5 + 400); a yarn type with no lots has on hand 0; a blocked lot's stock is excluded; **draft and cancelled orders reserve nothing**; `below_reorder` is false exactly at free = reorder level (strictly less-than).
- `test_migrations_in_sync` still passes (views are invisible to it).

### Task 3: Receive lot (R1) and lot reads

**Interfaces — Produces** (`store/service.py`): `receive_lot(db, user, body: LotReceiveIn) -> YarnLot`; `lot_out(db, lot) -> LotOut`; `lot_detail(db, lot) -> LotDetail`; `list_lots(db, yarn_type_id=None, blocked=None) -> list[LotOut]`; `get_lot_or_404(db, lot_code, for_update=False)`.

**Rules:**
- Yarn type, supplier must exist (`NOT_FOUND`, 404, field `yarn_type_id` / `supplier_id`); `intended_order_code`, if given, must exist (`NOT_FOUND`, field `intended_order_code`).
- `qty_kg` and `cost_per_kg` go through `dec()` + `q_kg`/`q_money`; a quantity that rounds to 0.000 is `VALIDATION_ERROR` on `qty_kg`.
- `challan_photo_path`, if given, must match `^uploads/[0-9a-f]{32}\.(jpg|png|webp)$` (else 422 on `challan_photo_path`); `challan_photo_url` in the output is `/api/uploads/<name>`.
- One transaction creates: the lot (`lot_code` from `next_code`, `received_by` = user id), a `receipt` movement (+qty), and a supplier bill (`bill_no` = challan, `amount` = `q_money(qty × cost)`, `bill_date` = today in IST, `due_date` = bill date + 30 days). A duplicate (supplier, challan, yarn type) → `DUPLICATE_CHALLAN` 409 on `challan_no` with **nothing** left behind.
- Output: `LotOut` per the existing schema (`qty_received_kg` = sum of receipts, `on_hand_kg` from `v_lot_stock`).
- After commit: publish `lot.changed` (lot id) and `stock.changed`.
- Roles: `POST /lots` store, owner. `GET /lots`, `GET /lots/{code}` store, owner, supervisor, accountant. Unknown lot → 404.

**Tests (write first):** happy path numbers (₹200,000 bill, +800 receipt, code format); duplicate challan → 409 and row counts unchanged; same challan for another supplier or yarn type → fine; unknown yarn type / supplier / order → 404 with the right field; Review Focus 3 (bad photo paths) and 4 (decimal edges: `0.0004`, `1e9`, `"abc"`, 4-decimal inputs round half up); events published exactly once after success and not at all after a 409 (monkeypatch the broadcaster); list filters (`yarn_type_id`, `blocked`); detail returns movements oldest first; buyer → 403; two simultaneous receives of the same challan with committed data → exactly one 201 and one 409 (Review Focus 2, separate sessions, tables truncated afterwards).

### Task 4: Stock endpoint

**Produces:** `stock_rows(db) -> list[StockRow]` reading `v_yarn_type_stock`, ordered by yarn type code; the existing `GET /stock` handler uses it.

**Tests:** the −230 scenario returns `free_kg = -230`, `below_reorder = true`; a yarn type with no lots appears with zeros; ordering is by code; numbers are floats rounded to 3 places in JSON.

### Task 5: Issue, return, adjust (R2, R2b) and block lot (R14)

**Produces:** `issue_yarn`, `return_yarn`, `adjust_stock`, `block_lot` in `store/service.py`, each `(db, user, body)`; each locks the lot row first with `SELECT … FOR UPDATE` (via `get_lot_or_404(for_update=True)`) and returns a `YarnMovement`; `movement_out(movement) -> MovementOut`.

**Rules:**
- **Issue:** lot exists and is not blocked (`LOT_BLOCKED` 409 on `lot_code`); run exists (404 on `run_id`), is open and a spinning run of a **confirmed** order (`RUN_NOT_OPEN` 409 on `run_id`); the lot's yarn type is in the order's recipe (`YARN_NOT_IN_RECIPE` 409 on `lot_code`); after the lock, `qty ≤ on hand` else `INSUFFICIENT_STOCK` 409 on `qty_kg` with the available kg in the message. Writes `issue`, qty stored negative.
- **Return:** lot and run exist; `qty ≤ (issued from this lot to this run) − (already returned from this lot to this run)` else `RETURN_EXCEEDS_ISSUED` 409. Allowed on a closed run and on a blocked lot.
- **Adjust:** `qty ≠ 0`, note required (existing schema); a negative adjustment cannot exceed on hand (`INSUFFICIENT_STOCK`); allowed on a blocked lot.
- **Block:** sets `is_blocked`, `blocked_reason`, `blocked_at = now`; already blocked → `LOT_ALREADY_BLOCKED` 409. No unblock.
- After commit: `lot.changed`, `stock.changed` (and `run.changed` is not published here).
- Roles unchanged from the stubs: issue/return store, supervisor, owner; adjust/block store, owner.

**Tests:** hand-worked numbers (issue 587.5 → on hand 212.5; return 20 → 232.5); every error code above, each leaving the ledger unchanged; issue exactly equal to on hand succeeds, one milligram more fails; **Review Focus 1**: two threads, each with its own session on committed data, issue 300 kg each from a 500 kg lot → one success, one `INSUFFICIENT_STOCK`, final on hand 200 (repeat 5 times); Review Focus 5 cases; blocking removes the lot from `v_yarn_type_stock`; block twice → 409; events published after success only.

### Task 6: Orders — create, read, confirm, cancel, deadline (R3), progress, stage, yarn check

**Produces** (`orders/service.py`): `create_order(db, user, body) -> Order`; `confirm_order`, `cancel_order`, `change_deadline`; `get_order_or_404(db, code)`; `order_out(db, order) -> OrderOut`; `progress(db, order) -> Progress`; `stage(db, order, progress) -> OrderStage`; `yarn_check(db, order) -> YarnCheckOut`; `list_orders(db, state=None, buyer_id=None)`.

**Rules:**
- **Create:** buyer and fabric type exist (404); `deadline` not before today in IST (`DEADLINE_IN_PAST` 422 on `deadline`); `qty_metres`, `price_per_metre` via `dec()`; state `draft`; code from `next_code`. Publishes `order.changed`.
- **Confirm:** only `draft` (`ORDER_NOT_DRAFT` 409); sets `confirmed_at`; a yarn shortage does **not** block confirmation. Publishes `order.changed`, `stock.changed` (reservation changes).
- **Cancel:** `draft` or `confirmed` with **no production runs** (`ORDER_HAS_RUNS` 409); already cancelled → `ORDER_ALREADY_CANCELLED`. Publishes `order.changed`, `stock.changed`.
- **Deadline change** (`PATCH`): not for cancelled orders (`ORDER_CANCELLED` 409); not before today.
- **Yarn check:** for each recipe line: `need_kg`, `issued_kg`, `outstanding_kg` from `v_order_yarn_need`; `available_kg` = on hand (unblocked lots) − outstanding of **other confirmed orders** for that yarn type (never below 0 in the output); `short_kg = max(0, outstanding − available)`; `can_start` = every line short is 0.
- **`yarn_status`** in `OrderOut`: `not_needed` for cancelled orders or when total outstanding is 0; else `can_start`/`short` from the check; `short_kg` = sum of line shorts.
- **Progress** (all from existing tables, so it is correct as soon as later plans write the data): `need_kg` (sum of recipe lines); `spun_kg` = sum of `output_kg` of ended spinning runs; `woven_m` = sum of the order's roll metres; `dyed_m` = metres of rolls with a `dye` link to an ended run; `passed_m` = metres of rolls whose **latest** inspection verdict is `pass`; `rejected_m` = latest verdict `reject`; `dispatched_m` = metres of rolls on a dispatch in state `dispatched`.
- **Stage** (spec §5, evaluated from furthest to nearest): draft → `draft`; cancelled → `cancelled`; `dispatched_m ≥ qty` → `dispatched`; `dispatched_m > 0` → `partly_dispatched`; `passed_m ≥ qty` → `ready_to_ship`; any undispatched roll that has finished dyeing and has no inspection, or whose latest verdict is `rework` → `quality_check`; any `dyeing` run → `dyeing`; any `weaving` run → `weaving`; any `spinning` run → `spinning`; else `waiting_to_start`.
- `delivery_date`, `days_late`: `null`.
- Roles and URLs exactly as the existing orders router.

**Tests (write first):** create/confirm/cancel/deadline happy paths and every error code; confirming with a shortage still works; the −230 yarn check and `yarn_status` for the hand-worked data, plus `not_needed` after full issue; progress numbers and **every stage transition** built with factories (waiting → spinning → weaving → dyeing → quality check → ready to ship → partly dispatched → dispatched), including the "latest verdict wins" case (reject, then a later pass) and an order whose rolls are all rejected; list filters; the other-orders-reservation case from the numbers above; draft and cancelled orders never reserve; events after commit only; buyer → 403.

### Task 7: Boundary checks, contract stability and docs

- The old example-data tests in `tests/test_contract_store_orders.py` for replaced endpoints are replaced by the real tests above; only the recall endpoint test and the role tests that still apply remain.
- **Contract stability:** `npm run contracts` leaves `contracts/openapi.json` and `contracts/types.ts` **unchanged** (if anything differs, a shape changed by mistake — fix the code, not the contract).
- Live check against a running server with the dev users: receive a lot as `store`, create and confirm an order as `owner`, issue yarn needs a run (B3), so check receive, stock, order create/confirm/yarn-check and the 403s.
- Full suite twice; update spec §4.5 (progress is a function) and `docs/plans/README.md`; add a dated entry to `docs/HRITWIK_TEAM_NOTES.md` telling Track A that store and orders are real (shapes unchanged, example numbers replaced by real ones — stock and yarn-check numbers now agree).

## Done when

- Suite green twice; contract byte-identical; the concurrency tests pass 5 repeated runs.
- Receive → stock → create → confirm → yarn-check works end to end on a real server.
- `docs/plans/README.md` marks B2 done.
