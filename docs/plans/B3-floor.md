# B3 — Floor (real logic) Implementation Plan

> **Summary:** Replaces the example-data stubs for the shop floor with real, tested logic: start/end/hand-over of production runs, breakdown and repair, roll off and loading rolls into dyeing, the roll-status view (spec §5, all five rules), machine status and "output today", the floor board, machine page, `GET /runs` and `GET /rolls`. Every write locks the machine row (start also locks the order row). API shapes do not change.
> **Last updated:** 2026-10-10 17:22 IST (Tasks 1-4 done)

**Goal:** every endpoint under `/api/floor`, `/api/machines/{code}` (read, breakdown, repair), `/api/runs` (list, start, end, hand-over, roll off, load rolls) and `/api/rolls` (list) runs on real data with the rules R4–R8 from spec §6, and the generated `contracts/openapi.json` stays **byte-identical**.

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §4.2, §4.5, §5, §6 (R4–R8). **Depends on:** B1 (tables, auth, error format) and B2 (money/codes/clock/validate helpers, order locking, stock, order progress).

**How this plan is executed:** inline, one task at a time (atomic-workflow), test first, the full suite twice at each boundary, the important tests mutation-checked (break the code, see the test fail, restore), race tests proven by removing the lock. The final code is copied into this plan after each task is verified, so the plan never contains code that was not run. Design approved section by section on 2026-10-10 (scope, start run, end/hand-over/breakdown/repair, rolls and roll status, reads and task order).

## Status

Task 1 done and verified (2026-10-10 17:12 IST): migration `b0eaa59f8a3b` (roll_code_seq + `v_roll_status`, identical to the SQL in Task 1, downgrade/upgrade round trip checked on a scratch database), `next_code(db, "roll")`, `make_roll` uses it; 17 new tests (one per status rule, mutation-proven: oldest-verdict-wins, ignoring the "started after the inspection" condition, verdict-before-dispatch and swapped dyeing/awaiting_qc each make a test fail). Full suite 521 passed, twice; contract unchanged. 
Task 2 done and verified (2026-10-10 17:16 IST): migration `70a0b5bd9a55` (`v_machine_status`, round trip checked), `floor/board.py` (`run_out`, `list_runs`, `machine_card`, `floor_board`, `machine_detail`, `output_today`), `orders.service.progress_row` made public, real `GET /floor`, `GET /machines/{code}`, `GET /runs`; 26 new tests (worked numbers 640 / 300 / 500, India-day boundary, progress 50.0 / 46.2 / 30.8 / 100.0 cap, ordering, roles, statement count independent of machine count); mutation-proven (UTC day, running-beats-down, open dye runs counted, no cap, oldest-first, weaving counting every day). Old example-data tests for these endpoints replaced (`test_contract_asks.py`, `test_contract_floor_qc.py`). Full suite 546 passed, twice; contract unchanged. 
Task 3 done and verified (2026-10-10 17:19 IST): `floor/service.py` (`db_now`, `get_machine_or_404`, `lock_machine`, `locked_open_run`, `start_run`), the B1 mapping of the open-downtime index renamed to `MACHINE_ALREADY_DOWN`, real `POST /runs`; 27 new tests (every refusal with status, code and field, weaving input cases, the one-operator-two-machines case, the two races: simultaneous starts 5x on committed data and a start waiting on an order lock held by a cancel, plus the clock test); mutation-proven (no order lock, transaction-clock `started_at`, no confirmed check, wrong-order input, wrong-stage input, inactive and down machines allowed). One old example-data test (`test_posting_a_run_still_works_next_to_the_new_get`) rewritten with real data. Full suite 573 passed, twice; contract unchanged. Note: the machine lock in start is not what stops two simultaneous starts on one machine (the database's unique index does, and the test passes without the lock); the machine lock matters for breakdown-versus-start (Task 5). 
Task 4 done and verified (2026-10-10 17:22 IST): `end_run` and `handover` in `floor/service.py`, real `POST /runs/{id}/end` and `/handover`; 36 new tests (spinning output required / zero allowed / blank refused / rounding / bad numbers, weaving and dyeing refuse output, ended and unknown runs, hand-over copies order, machine, stage and input run at the same instant and leaves rolls on the old run, same and inactive operator, machine-less rework run, roles, the clock hazard, an end waiting on a held lock then `RUN_NOT_OPEN`, two simultaneous hand-overs 3x leaving exactly one open run). Mutation-proven: transaction-clock `ended_at`, output not required, same operator allowed, different instants, input run dropped. **Two mutations survive, deliberately:** (1) removing `lock_machine` from `locked_open_run` changes nothing observable for end, hand-over, roll off and load rolls, because `locked_open_run` also takes the run row's own `FOR UPDATE` and that is what serialises them; the machine lock is what makes start-versus-breakdown safe (Task 5 proves it) and keeps the documented lock order uniform. (2) removing the explicit `db.flush()` before inserting the new run changes nothing, because SQLAlchemy already emits the UPDATE before the INSERT in one flush; the flush stays so correctness does not depend on the ORM's ordering. Full suite 609 passed, twice; contract unchanged. Next: Task 5.

**Amendment found while building Task 2:** `machine_card` (and the board) cover **active** machines only, because `v_machine_status` lists active machines only. So Task 5's `breakdown` and `repair` refuse an inactive machine with `MACHINE_INACTIVE` (409, field `machine_code`), the same code start-run uses; an inactive machine must be reactivated first (master data) before a downtime can be opened or closed on it.

## Global Constraints

- Quantities are `Decimal` end to end (kg and metres to 3 places, `ROUND_HALF_UP`); only the JSON edge converts to `float`. Never arithmetic on floats. Numeric request fields keep `Annotated[float, Field(...), NoBool]` (NoBool **after** Field).
- Every write happens in one transaction and goes through `commit(db)`. Live events (`run.changed`, `machine.changed`, `roll.changed`) are published **only after a successful commit**, never on failure.
- **Timestamps set by a write (`started_at`, `ended_at`) come from `clock_timestamp()` read after the locks are taken, never from the transaction-start `now()`.** A request that began earlier but waited for a lock would otherwise stamp an end earlier than another request's start and break the `end_after_start` constraint.
- **Lock order, always:** order row → machine row → roll rows (ascending id). A write that needs only some of them takes those in this order. No write takes them in another order, so they cannot deadlock.
- Roles exactly as the existing floor router: reads `supervisor`, `owner`, `accountant`; writes `supervisor`, `owner`; `GET /rolls` all staff roles (buyers 403).
- Error codes are stable strings; `field` names match request field names (`order_code`, `machine_code`, `operator_worker_id`, `input_run_id`, `run_id`, `output_kg`, `roll_codes`, `reason`).
- Commit messages: plain imperative subject, no trailers.

## Decisions made in this plan (not spelled out in the spec)

1. **The stage of a run is its machine's stage.** `RunStartIn` has no stage field. `WRONG_STAGE` is therefore used for two things only: a weaving `input_run_id` that is not a spinning run (409 on `input_run_id`), and an operation on a run of the wrong stage (roll off on a non-weaving run, load rolls on a non-dyeing run, 409 on `run_id`).
2. **New codes** (the spec names only some): `ORDER_NOT_CONFIRMED`, `MACHINE_INACTIVE`, `OPERATOR_INACTIVE`, `MACHINE_NOT_DOWN`, `OUTPUT_REQUIRED` (422), `OUTPUT_NOT_ALLOWED` (422), `ROLL_WRONG_ORDER`. `RUN_NOT_OPEN` (B2) is reused for every operation on an ended run. **`MACHINE_DOWN` means "tried to start on a down machine" (spec R4); the B1 mapping of the open-downtime unique index changes from `MACHINE_DOWN` to `MACHINE_ALREADY_DOWN`** (a second breakdown). Nothing consumes it yet.
3. **Spinning output.** `POST /runs/{id}/end` on a spinning run requires `output_kg` (0 allowed, blank refused); on weaving/dyeing runs `output_kg` is refused. Output is **not** capped by the yarn issued to the run (hand-over splits one job across runs: yarn sits on the old run, output lands on the new one). A spinning run ended by hand-over or breakdown keeps a blank output (their request shapes have no field), so `spun_kg` under-counts in that case. Recorded, not fixed (a fix would change the contract).
4. **Hand-over** to the same operator is refused (422 on `operator_worker_id`); old run ends and the new run starts at the same instant; the old run is flushed before the new one is inserted so the one-open-run index never sees two open runs; the new run copies order, machine, stage and `input_run_id`, starts with no rolls; rolls already made stay on the old run.
5. **Breakdown** opens a downtime and ends any open run on that machine at the same instant (spinning output left blank); **repair** closes the downtime and does **not** reopen the run, someone starts a new run.
6. **Machine row lock** in start, end, hand-over, breakdown, repair, roll off and load rolls. It is **required** for start, breakdown and repair: without it a breakdown that ends the open run could pass a start run that slips in at the same moment (a down machine with a running job). For end, hand-over, roll off and load rolls the run row's own `FOR UPDATE` (taken in `locked_open_run`) is what stops a roll attaching to a run that has just ended or a run ending twice; the machine lock there keeps the documented lock order uniform and costs nothing. `locked_open_run` (Task 3) takes a run id, locks its machine, re-reads the run and refuses an ended one.
7. **Roll status is a SQL view** (`v_roll_status`, spec §5, all five rules) because lists filter by status. "A rework run linked after the inspection" has no timestamp of its own, so it is `production_runs.started_at >= inspection.inspected_at`.
8. **`GET /rolls` becomes real in B3** (it was planned for B4): once runs are real, the example rolls would not exist and the dyeing tick-list would show nothing real. Same roles and filters (`status`, `order_code`); an unknown `order_code` gives an empty list. The roll passport stays B4.
9. **Roll codes** `R-0142` come from a Postgres sequence through `next_code(db, "roll")`; the test factory `make_roll` switches to it (as lots and orders did in B2).
10. **Board and machine page show active machines only** (`v_machine_status` excludes inactive ones); an inactive machine's detail is 404, its history stays in `GET /runs`.
11. **Output today** uses the India-time calendar day: spinning = `output_kg` of that machine's runs ended today (kg); weaving = metres of rolls made today through that machine's runs (m); dyeing = metres of rolls in that machine's dye runs ended today (m); an open dye run counts nothing.
12. **`order_progress_pct`** (spec silent): progress of the run's own stage for its order, from the B2 progress numbers: spinning `spun_kg / need_kg`, weaving `woven_m / qty_metres`, dyeing `dyed_m / qty_metres`, rework 0; times 100, capped at 100, one decimal, 0 when the denominator is 0. `spun_kg` counts ended spinning runs only, so an open spinning run shows the progress up to the previous runs.
13. **No rule stops one operator running two machines** (spec silent; weavers tend several looms). A roll may exceed the order quantity (only dispatch warns about over-shipping). `GET /runs` has no pagination.
14. `orders.service._progress_row` is renamed `progress_row` (public) because the board reuses it.

## Hand-worked numbers (the tests assert these)

- **Output today (IST):** a spinning machine with a run ended today (640 kg) and one ended yesterday (100 kg) shows **640 kg**. A weaving machine with rolls made today of 100 + 120 + 80 m and one made yesterday of 50 m shows **300 m**. A dyeing machine with a dye run ended today holding rolls of 300 + 200 m shows **500 m**; a second, still-open dye run with a 100 m roll adds nothing.
- **India-time boundary:** a run ended at 23:30 IST yesterday (18:00 UTC) and a run ended at 00:30 IST today (19:00 UTC yesterday) fall on different days although their UTC dates are the same day.
- **`order_progress_pct`:** order 5,000 m with recipe 0.12 kg/m and 5% wastage (need 630 kg): an ended spinning run with 315 kg → **50.0**; weaving with 2,310 m woven → **46.2**; dyeing with 1,540 m dyed → **30.8**; woven above the order (5,500 m) → **100.0** (capped).
- **Status:** a machine with an open downtime and an open run is `down`; an open run only → `running`; neither → `idle`; counts on the board add up to the number of active machines.
- **Roll status chain** for one roll: made → `woven`; loaded into an open dye run → `dyeing`; dye run ended → `awaiting_qc`; inspection pass → `in_store`; on a loading dispatch → `loading`; dispatch confirmed → `dispatched`.

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **Two simultaneous starts on one machine** → exactly one run, the other `MACHINE_BUSY`, never two open runs (real concurrent sessions, repeated 5 times). Task 3.
2. **Cancel against start** → a cancel that holds the order lock and commits first makes the waiting start fail with `ORDER_NOT_CONFIRMED`; the reverse cancel gets `ORDER_HAS_RUNS`. Task 3.
3. **Breakdown against start** (deterministic, one session holds the machine lock) and the **clock hazard**: a breakdown whose transaction began before another start committed must still end the run without violating `end_after_start`. Task 5.
4. **The same roll loaded into two dyeing runs at the same moment** → one succeeds, the other `ROLL_WRONG_STATUS`, the roll is linked once. A roll made on a run that has just ended is refused (`RUN_NOT_OPEN`), never attached. Task 6.
5. **India-time day boundary for "output today"** and zero/empty cases (machine with no runs shows 0, not null). Task 2.

---

## File Structure

```
services/api/
  alembic/versions/<id>_roll_codes_and_roll_status.py    hand-written: roll_code_seq + v_roll_status
  alembic/versions/<id>_machine_status_view.py           hand-written: v_machine_status
  app/core/codes.py            next_code kind "roll" -> R-0142
  app/core/errors.py           uq_open_downtime_per_machine -> MACHINE_ALREADY_DOWN
  app/modules/rolls/service.py roll_out, list_rolls (roll status from v_roll_status)
  app/modules/rolls/router.py  real GET /rolls
  app/modules/floor/board.py   reads: run_out, list_runs, machine_card, floor_board, machine_detail, output today
  app/modules/floor/service.py writes: locks, start_run, end_run, handover, breakdown, repair
  app/modules/floor/rolls.py   writes: roll_off, load_rolls
  app/modules/floor/router.py  real handlers (thin)
  app/modules/orders/service.py  _progress_row -> progress_row
  tests/test_roll_status.py  test_floor_reads.py  test_floor_start.py  test_floor_end.py  test_floor_breakdown.py
  tests/test_floor_rolls.py  test_floor_chain.py
```

`app/modules/floor/examples.py` stays: dispatch, passport and qc examples import its `NOW` and `ROLL`; only the floor router stops using it.

---

### Task 1: Roll codes and the roll-status view

**Interfaces — Produces:** `next_code(db, "roll") -> "R-0142"` style (zero-padded to 4); SQL view `v_roll_status(roll_id, status)` with `status` one of the nine `RollStatus` values; factory `make_roll` uses `next_code`.

**Migration (hand-written, revision "roll codes and roll status", down_revision = the B2 stock-views revision `4958ba00e7a2`):** `CREATE SEQUENCE roll_code_seq`; then the view below (this SQL was run against the real schema before this plan was written; it compiles and returns zero rows on an empty database). Downgrade drops the view, then the sequence.

```sql
CREATE VIEW v_roll_status AS
SELECT r.id AS roll_id,
  CASE
    WHEN d.state = 'dispatched' THEN 'dispatched'
    WHEN d.state = 'loading' THEN 'loading'
    WHEN li.verdict = 'reject' THEN 'rejected'
    WHEN li.verdict = 'pass' THEN 'in_store'
    WHEN li.verdict = 'rework' THEN
      CASE
        WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                     WHERE rr.roll_id = r.id AND rr.purpose = 'rework'
                       AND pr.started_at >= li.inspected_at AND pr.ended_at IS NOT NULL) THEN 'awaiting_qc'
        WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                     WHERE rr.roll_id = r.id AND rr.purpose = 'rework'
                       AND pr.started_at >= li.inspected_at AND pr.ended_at IS NULL) THEN 'in_rework'
        ELSE 'awaiting_rework'
      END
    WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                 WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NOT NULL) THEN 'awaiting_qc'
    WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                 WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NULL) THEN 'dyeing'
    ELSE 'woven'
  END AS status
FROM rolls r
LEFT JOIN dispatch_items di ON di.roll_id = r.id
LEFT JOIN dispatches d ON d.id = di.dispatch_id
LEFT JOIN LATERAL (SELECT q.verdict, q.inspected_at FROM qc_inspections q WHERE q.roll_id = r.id
                   ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) li ON true;
```

**Tests (write first; `tests/test_roll_status.py`, plus a case in `test_codes.py`):**
- `next_code(db, "roll")` matches `^R-\d{4,}$`, two calls differ; the factory `make_roll` uses it and the whole existing suite still passes.
- One test per status, built with factories (`make_inspection`, `put_on_dispatch`, `dye` exist in `tests/factories.py`): no links → `woven`; open dye run → `dyeing`; ended dye run → `awaiting_qc`; latest pass → `in_store`; latest reject → `rejected`; reject then a later pass → `in_store`; pass then a later rework → `awaiting_rework`; rework with an ended rework run started after the inspection → `awaiting_qc`; with an open one → `in_rework`; a rework run that **started before** the latest rework inspection is ignored → `awaiting_rework`; dispatch `dispatched` beats a reject verdict; dispatch `loading` beats a pass verdict; an inspected roll ignores an open dye run (pass + open dye run → `in_store`); two dye links, one ended → `awaiting_qc`.
- `test_migrations_in_sync` still passes (the view is invisible to it).

### Task 2: Reads — machine status, output today, run list, floor board, machine page

**Interfaces — Consumes:** `orders.service.progress_row(db, order) -> dict[str, Decimal]` (renamed in this task), `core.clock.today_ist()`, `core.money.to_float`. **Produces** (`floor/board.py`): `run_out(db, run) -> RunOut` (roll_codes and metres = the rolls linked to the run, any purpose, ordered by roll id); `list_runs(db, stage=None, order_code=None) -> list[RunOut]` (newest first by `started_at`, then id); `machine_card(db, machine) -> MachineCard`; `floor_board(db) -> FloorBoard`; `machine_detail(db, machine_code) -> MachineDetail` (404 on unknown or inactive machine, last 10 runs newest first); `output_today(db) -> dict[machine_id, Decimal]`.

**Migration (hand-written, revision "machine status view"):** the view below plus nothing else. Downgrade drops it. The three output queries are used from the service with `:today = today_ist()` (all four statements were run against the real schema before this plan was written).

```sql
CREATE VIEW v_machine_status AS
SELECT m.id AS machine_id,
  CASE
    WHEN EXISTS (SELECT 1 FROM machine_downtimes dt WHERE dt.machine_id = m.id AND dt.ended_at IS NULL) THEN 'down'
    WHEN EXISTS (SELECT 1 FROM production_runs pr WHERE pr.machine_id = m.id AND pr.ended_at IS NULL) THEN 'running'
    ELSE 'idle'
  END AS status
FROM machines m WHERE m.active;
```
```sql
-- spinning kg, runs ended today (IST)
SELECT pr.machine_id, COALESCE(SUM(pr.output_kg), 0) AS qty FROM production_runs pr
 WHERE pr.stage = 'spinning' AND pr.ended_at IS NOT NULL
   AND (pr.ended_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id;
-- weaving metres, rolls made today (IST)
SELECT pr.machine_id, SUM(r.metres) AS qty FROM rolls r
  JOIN roll_runs rr ON rr.roll_id = r.id AND rr.purpose = 'produce'
  JOIN production_runs pr ON pr.id = rr.run_id
 WHERE (r.created_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id;
-- dyeing metres, dye runs ended today (IST)
SELECT pr.machine_id, SUM(r.metres) AS qty FROM roll_runs rr
  JOIN rolls r ON r.id = rr.roll_id JOIN production_runs pr ON pr.id = rr.run_id
 WHERE rr.purpose = 'dye' AND pr.ended_at IS NOT NULL
   AND (pr.ended_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id;
```

**Rules:** the board lists active machines ordered by stage (spinning, weaving, dyeing) then code, with `running` / `idle` / `down` counts and `generated_at` (database clock); a card carries the current run as `RunBrief` (open run on that machine, `operator` as `Ref(id, name)`, `order_progress_pct` per decision 12), the open downtime (`reason`, `started_at`), `output_today` and `output_unit` (`kg` for spinning, `m` otherwise). The set-wide queries are run once per request, not once per machine. Routes: `GET /floor`, `GET /machines/{code}`, `GET /runs` (filters `stage` from the existing enum, `order_code`; unknown `order_code` → empty list).

**Tests (write first, `tests/test_floor_reads.py`):** statuses (down beats running, running, idle) and counts equal the number of active machines; inactive machine absent from the board and its detail is 404, unknown code 404; every output-today number from the worked numbers, the India-time boundary pair, a machine with no runs shows 0.0; `order_progress_pct` 50.0 / 46.2 / 30.8 / 100.0 (cap) / 0 when the denominator is 0; current run and downtime shown; machine detail has at most 10 runs newest first; `GET /runs` filters by stage and order, newest first, includes ended runs with `roll_codes` and `metres`, unknown order empty, bad stage 422; roles (viewers 200; qc, dispatch, store, buyer 403).

### Task 3: Start run (R4)

**Interfaces — Consumes:** `get_order_or_404(db, code, for_update=True)` (B2), `core.validate.not_found/invalid`. **Produces** (`floor/service.py`): `lock_machine(db, machine_id) -> Machine` (SELECT … FOR UPDATE, `populate_existing`); `get_machine_or_404(db, code)`; `locked_open_run(db, run_id, stage=None) -> ProductionRun` (404 on `run_id`; locks the run's machine, skipped for a rework run, which has no machine, then re-reads the run FOR UPDATE; `RUN_NOT_OPEN` if ended; `WRONG_STAGE` if `stage` is given and differs); `start_run(db, body: RunStartIn) -> ProductionRun`; `db_now(db)` (`SELECT clock_timestamp()`).

**Rules (checks in this order, nothing left behind on failure):** order exists (404 `order_code`) then its row is locked, confirmed else `ORDER_NOT_CONFIRMED`; machine exists (404 `machine_code`), its row is locked, `active` else `MACHINE_INACTIVE`; operator exists (404 `operator_worker_id`), `active` else `OPERATOR_INACTIVE`; weaving needs `input_run_id`: missing → `INPUT_RUN_REQUIRED` (422), unknown id → 404 `input_run_id`, a run of another order or not a spinning run → `INPUT_RUN_REQUIRED` (409, message says which); an `input_run_id` on a spinning/dyeing machine → `VALIDATION_ERROR` on `input_run_id`; open downtime → `MACHINE_DOWN` (409); open run → `MACHINE_BUSY` (409, from the unique index through `commit`). `started_at = db_now(db)` after the locks. Returns 201 `RunOut`; publishes `run.changed` (run id) and `machine.changed` (machine id).

**Tests (write first, `tests/test_floor_start.py`):** happy path for a spinning, a weaving (with its input run) and a dyeing machine, response matches `RunOut`; every refusal with its status, code and field, each leaving the run count unchanged and publishing nothing; weaving input cases (missing, another order's spinning run, a weaving run as input, unknown id, an ended spinning run is accepted); spinning with an `input_run_id` → 422; draft and cancelled orders → `ORDER_NOT_CONFIRMED`; down machine → `MACHINE_DOWN`; busy machine → `MACHINE_BUSY` with exactly one open run left; one operator on two machines is allowed; events after commit only; roles (supervisor and owner only); **Review Focus 1** (two threads, committed data, 5 repeats); **Review Focus 2** (a session holds the order lock and cancels; the start waits, then `ORDER_NOT_CONFIRMED`; the other way round `ORDER_HAS_RUNS`); a test that `started_at` is taken from `clock_timestamp()` (an earlier-beginning transaction's start still gets a real current time).

### Task 4: End run and hand-over (R6)

**Produces** (`floor/service.py`): `end_run(db, run_id, body: RunEndIn) -> ProductionRun`; `handover(db, run_id, body: HandoverIn) -> ProductionRun` (returns the **new** run).

**Rules:** `end_run`: `locked_open_run`; spinning requires `output_kg` (≥ 0, rounded half up to 3 places, 0 allowed) else `OUTPUT_REQUIRED` (422 on `output_kg`); weaving/dyeing/rework given an `output_kg` → `OUTPUT_NOT_ALLOWED` (422); sets `ended_at = db_now(db)`. `handover`: `locked_open_run`; operator exists/active; a run with no machine (rework) → `WRONG_STAGE` on `run_id`; same operator as the current one → 422 on `operator_worker_id`; one instant `t = db_now(db)`: old run `ended_at = t`, **flush**, new run (same order, machine, stage, `input_run_id`, new operator) `started_at = t`. Both publish `run.changed` (each run id) and `machine.changed`.

**Tests (write first, `tests/test_floor_end.py`):** spinning end with 640 saves output and end time; 0 accepted; missing → `OUTPUT_REQUIRED`; `1.0005` stores `1.001`; negative, NaN, `true`, `1e9` → 422; weaving/dyeing with output → `OUTPUT_NOT_ALLOWED`; already ended → `RUN_NOT_OPEN`; unknown run 404; hand-over: new run copies order/machine/stage/input run, new operator, old `ended_at == new started_at`, the index never trips, old rolls stay on the old run, new run has no rolls and 0 metres; same operator 422; inactive operator; ended run → `RUN_NOT_OPEN`; a machine-less rework run (built with a factory) → `WRONG_STAGE`; events; roles; an end that waits behind a session holding the machine lock sees the run already ended (`RUN_NOT_OPEN`).

### Task 5: Breakdown and repair (R5)

**Produces** (`floor/service.py`): `breakdown(db, machine_code, body: BreakdownIn) -> Machine`; `repair(db, machine_code) -> Machine`; both routes return `machine_card(db, machine)` from Task 2.

**Rules:** `breakdown`: machine exists (404 `machine_code`), row locked, `active` else `MACHINE_INACTIVE` (409, so `machine_card` always gets an active machine); opens a downtime (`reason` trimmed) at `db_now(db)`; ends any open run on the machine at the same instant (spinning output stays blank); a second breakdown while down → `MACHINE_ALREADY_DOWN` (409, unique index via `commit`, field `machine_code`). `repair`: locked, `active` else `MACHINE_INACTIVE`; no open downtime → `MACHINE_NOT_DOWN` (409); else `ended_at = db_now(db)`; the ended run is **not** reopened. Publishes `machine.changed`, plus `run.changed` for a run that was ended.

**Tests (write first, `tests/test_floor_breakdown.py`):** breakdown with a running job → card `down`, run ended at the downtime's start, downtime reason shown; breakdown on an idle machine; second breakdown → `MACHINE_ALREADY_DOWN` (and no extra downtime row); blank reason 422; repair → card `idle`, no run reopened, a new start works afterwards; repair when not down → `MACHINE_NOT_DOWN`; unknown machine 404; inactive machine → `MACHINE_INACTIVE` on both; events; roles; **Review Focus 3**: a session holds the machine lock and runs a breakdown while a start waits and then gets `MACHINE_DOWN`; and **the clock hazard**: session Y starts a transaction (`select 1`), session X starts a run and commits, then Y runs `breakdown` on that machine and must succeed (the run's `ended_at >= started_at`).

### Task 6: Roll off and load rolls (R7, R8), real `GET /rolls`

**Produces** (`floor/rolls.py`): `roll_off(db, run_id, body: RollOffIn) -> Roll`; `load_rolls(db, run_id, body: LoadRollsIn) -> ProductionRun`. (`rolls/service.py`): `roll_out(db, roll) -> RollOut` (buyer name, fabric name, order colour, status from `v_roll_status`); `list_rolls(db, status=None, order_code=None) -> list[RollOut]` (newest first by id).

**Rules:** `roll_off`: `locked_open_run(run_id, stage="weaving")` (`RUN_NOT_OPEN`, `WRONG_STAGE`); metres rounded half up to 3 places, rounding to zero → 422 on `metres`; creates the roll (`code` from `next_code(db, "roll")`, order = the run's order) and a `produce` link; 201 `RollOut` with status `woven`; publishes `roll.changed` and `run.changed`. `load_rolls`: `locked_open_run(run_id, stage="dyeing")`; a duplicate code in the list → 422 on `roll_codes`; every code must exist (404 on `roll_codes`); roll rows are locked in ascending id order **after** the machine, then each must belong to the run's order (`ROLL_WRONG_ORDER`, 409) and have status `woven` (`ROLL_WRONG_STATUS`, 409); all or nothing, the message names the first bad code; creates `dye` links; returns `RunOut` with the loaded `roll_codes` and total metres; publishes `roll.changed` for each roll and `run.changed`. `GET /rolls` uses `list_rolls` (all staff roles, buyers 403, bad status 422).

**Tests (write first, `tests/test_floor_rolls.py`):** roll off creates a roll with the `R-` code, order, produce link and `woven` status; `0`, `0.0004`, `-1`, `NaN`, `true`, `1e9` → 422; wrong stage → `WRONG_STAGE`; ended run → `RUN_NOT_OPEN`; unknown run 404; a roll above the order quantity is accepted; load rolls happy path (status becomes `dyeing`, response metres sum), every refusal (`ROLL_WRONG_STATUS` for an already-loaded roll and for an inspected one, `ROLL_WRONG_ORDER`, unknown code 404, duplicate code 422, wrong stage, ended run) leaving every roll untouched when any one is bad; events; roles; `GET /rolls` filters (status, order), unknown order empty, bad status 422, roles (buyer 403); **Review Focus 4**: two dyeing runs loading the same roll with a session holding the roll locks (deterministic) and with two real threads (5 repeats) → one `ROLL_WRONG_STATUS`, one link; a roll-off that waits behind an end on the same machine is refused with `RUN_NOT_OPEN`.

### Task 7: Boundary checks, the whole chain live, docs, merge

- Old example-data floor and rolls tests (`tests/test_contract_floor_qc.py` floor parts, `GET /rolls` example tests, anything importing the floor stubs for these endpoints) are replaced by the real tests above; the QC and passport parts stay (still examples until B4).
- **Contract stability:** `npm run contracts` leaves `contracts/openapi.json` and `types.ts` unchanged (and `test_committed_contract_matches_the_code` passes).
- **`tests/test_floor_chain.py`** (one real chain through the API): receive 800 kg → create and confirm a 5,000 m order → start a spinning run → issue 587.5 kg to it → end it with 590 kg → start weaving on that input → roll off 2,310 m in three rolls → start dyeing → load the rolls → end dyeing; after each step the order's `progress` and `stage` move as expected (`waiting_to_start` → `spinning` → `weaving` → `dyeing` → `quality_check`) and stock shows on hand 212.5.
- **Live check** against a running server on a throwaway database with the dev users, the same chain as above (this is the part B2 could not check because it needed real runs), plus breakdown/repair, a second breakdown, the `403`s and the board counts.
- Full suite twice; update spec §4.5 (`v_roll_status`, `v_machine_status` are real views; spinning output rule), `docs/plans/README.md`, and add a dated entry to `docs/HRITWIK_TEAM_NOTES.md` telling Track A that the floor is real (shapes unchanged; the list of new error codes; `true`/`false` already refused; issuing yarn now works against real runs; `GET /rolls` is real; `npm run db:migrate` for the two new migrations). Then merge to `main` and tell Hritwik to push.

## Done when

- Suite green twice; contract byte-identical; the concurrency tests pass five repeated runs; every mutation of a lock, a state check or the India-time day makes a test fail.
- Receive → order → spinning (issue, end with output) → weaving (rolls) → dyeing (load) works end to end on a real server, with order progress and stage moving.
- `docs/plans/README.md` marks B3 done.
