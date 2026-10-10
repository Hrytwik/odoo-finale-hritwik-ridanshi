# B4 — QC and rolls (real logic) Implementation Plan

> **Summary:** Replaces the example-data stubs for quality control with real, tested logic: recording an inspection (R9), starting a rework run (R10), the QC queue and the Roll Passport (run history, yarn lots, quality checks, a buyer sees only their own rolls). It also fixes a gap found in B3: handing over a dyeing run made its loaded rolls look finished, so a roll's dyeing now counts as finished only when its **latest** dye run has ended. API shapes do not change.
> **Last updated:** 2026-10-10 18:52 IST (Task 1 done)

**Goal:** every endpoint under `/api/qc/queue`, `/api/qc/inspections`, `/api/rework-runs` and `/api/rolls/{code}/passport` runs on real data with the rules R9, R10 and R15 from spec §6, and `contracts/openapi.json` stays **byte-identical**. `POST /qc/analyze` and `GET /qc/model-card` stay example data until B8.

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §4.2, §5, §6 (R9, R10, R15), §9, §11. **Depends on:** B1 to B3 (tables, auth, error format, locks, `db_now`, `v_roll_status`, runs and rolls). Unlocks B5 (a roll must be `in_store` to be loaded) and B6 (rework and rejects are costed).

**How this plan is executed:** inline, one task at a time (atomic-workflow), test first, the full suite twice at each boundary, the important tests mutation-checked, race tests proven by removing the lock. The final code is copied into this plan after each task is verified. Design approved section by section on 2026-10-10 (scope, inspection rules, rework runs and the hand-over gap, queue and passport, task order).

## Status

Task 1 done and verified (2026-10-10 18:52 IST): migration `43caade7e8a6` (`v_roll_latest_dye`, replaced `v_roll_status`, downgrade restores the B3 view; round trip checked), orders `dyed_m` and the quality-check stage and the dyeing output today use the latest dye run, hand-over copies the `dye` and `rework` links (a weaving run's rolls stay put); 11 tests added or changed (`tests/test_roll_latest_run.py`, `tests/test_roll_status.py`: the hand-over gap numbers, two hand-overs, breakdown after hand-over, rework hand-over stays `in_rework`, weaving hand-over unchanged, the latest run decides in both directions). Mutation-proven: no link copy, the earliest run as "latest", `dyed_m` and the stage back to "any ended run", output counting every ended run (double count), copying `produce` links. The B3 test `test_two_dye_links_one_ended_counts_as_awaiting_qc` was replaced by the precise cases. Stale wording fixed in spec §5 and the output-today line, the B2 plan's progress bullet and a correction note in the B3 plan. Full suite 839 passed, twice; contract unchanged. Next: Task 2.

## Global Constraints

- Quantities are `Decimal`; floats appear only at the JSON edge. Numeric request fields keep `Annotated[float, Field(...), NoBool]`.
- Every write is one transaction through `commit(db)`; events (`roll.changed`, `order.changed`, `run.changed`, `machine.changed`) are published **only after a successful commit**.
- Timestamps written here (`inspected_at`, a rework run's `started_at`) come from `floor.service.db_now(db)` read after the locks, never from the transaction-start `now()`.
- Lock order, always: order row, machine row, roll rows (ascending id). A write takes only the ones it needs.
- Roles exactly as the existing routers: `POST /qc/inspections` qc and owner; `GET /qc/queue` qc, owner, supervisor; `POST /rework-runs` supervisor, qc, owner; the passport all logged-in roles.
- Error codes are stable strings; `field` matches the request field name (`roll_code`, `machine_code`, `operator_worker_id`, `defects`, `photo_path`).
- Commit messages: plain imperative subject, no trailers.

## Decisions made in this plan (not spelled out in the spec)

1. **The inspector is the logged-in user's linked worker.** A QC login always has one (database check). The owner has none, so an owner request, or a linked worker who is inactive, is refused with `INSPECTOR_REQUIRED` (409).
2. **Inspection rules (R9):** lock the roll row, then the roll must be `awaiting_qc` (`ROLL_WRONG_STATUS`, 409, the message names the current status); a verdict other than pass needs at least one defect (`DEFECTS_REQUIRED`, 422 on `defects`); a pass **with** defects is allowed (minor flaws are worth recording and B7 counts them); the same defect type twice in one inspection is refused (422 on `defects`); `photo_path` must be an upload path (`uploads/<32 hex>.jpg|png|webp`, full match, 422 on `photo_path`); `overrode_ai` = an AI suggestion was sent and its verdict differs from the inspector's; the suggestion is stored exactly as sent and each defect keeps its own `ai_detected` flag.
3. **No edit or undo of an inspection.** A roll sent for rework gets a new inspection after the rework run ends.
4. **Rework run (R10):** one roll per run; the roll must be `awaiting_rework`; the machine is optional (manual mending), and when given it must be an active **dyeing** machine (`WRONG_STAGE` otherwise) that is not down or busy; the operator must be active. The run has stage `rework`, the roll's order, no input run, and a `rework` link to the roll. It ends through the existing end-run endpoint (no output allowed) and the roll returns to `awaiting_qc`. A breakdown on its machine ends it the same way. Hand-over works for a rework run on a machine and stays refused for manual mending (B3).
5. **A roll's dyeing is finished when its latest dye run has ended** (and its rework is finished when its latest rework run since the inspection has ended). New view `v_roll_latest_dye` (one row per roll: its latest dye run, ordered by `started_at` then id) is used by `v_roll_status`, by the order's `dyed_m` and quality-check stage (B2), and by a dyeing machine's output today (B3). **Hand-over of a dyeing run, or of a rework run on a machine, copies the `dye` and `rework` links to the new run** (the old links stay as history, so costing can still attribute the old run's hours and the passport lists both runs). A weaving run's rolls stay with the run that made them.
6. **QC queue counts:** `awaiting_qc`, `awaiting_rework`, `in_rework`, `rejected` are the statuses of the same names; **`passed`** is every roll whose latest verdict is pass (in store, on a loading dispatch, or dispatched). The rolls list is the three statuses that need attention, oldest first (by roll id).
7. **Passport:** a buyer asking for another buyer's roll or for a roll that does not exist gets the same 404 body (R15). Runs are the weaving run that made the roll, its dye and rework runs, and the spinning run its weaving run points at (`input_run_id`), oldest first, each once. Yarn lots are the lots with a net positive issue (issues minus returns) to that spinning run. If spinning was handed over, the trace follows the one spinning run the weaving run points at, which is what the spec's design records. Cost stays `null` until B6, dispatch `null` until B5. The existing `buyer_view` is reused.
8. **`/qc/analyze` and `/qc/model-card` are not touched** (B8). Both already say the model is not available.
9. The `photo_path` rule is shared: `core/validate.check_upload_path`, and the store's challan photo check uses it too.

## Hand-worked numbers (the tests assert these)

- **Rework story:** a 1,000 m order with two rolls, 600 m and 400 m. Roll 1 passes: `passed_m` = 600. Roll 2 is sent for rework with 2 holes: `awaiting_rework`; a mending run starts: `in_rework`; the run ends: `awaiting_qc`; it passes: `passed_m` = **1,000**, the order's stage is **ready to ship**, and roll 2's passport lists **two** inspections.
- **Queue counts** for six rolls: one awaiting QC, one awaiting rework, one in rework, one in store, one on a loading dispatch, one rejected: awaiting_qc **1**, awaiting_rework **1**, in_rework **1**, passed **2**, rejected **1**; the list holds three rolls.
- **Hand-over gap:** a dyeing run holds rolls of 300 m and 200 m. After a hand-over both rolls are still `dyeing`, the order's `dyed_m` is 0 and its stage is not quality check; after the new run ends, `dyed_m` is **500** (not 1,000: counted once) and the machine's output today is **500 m**.
- **Passport trace:** a lot of 800 kg with 587.5 kg issued to the spinning run and 587.5 kg returned does not appear; with 587.5 issued and 20 returned it appears.

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **Two inspectors judging the same roll at the same moment** → one verdict, the other `ROLL_WRONG_STATUS`. Task 2.
2. **A buyer asking for another buyer's roll and for a nonexistent roll** → identical 404 bodies, message included. Task 5.
3. **A rework run started right after an inspection** shows `in_rework`, not `awaiting_rework` (real-clock stamps). Task 3.
4. **A passport for a roll with hand-overs on weaving and dyeing** lists each run once, in order; a fully returned yarn lot does not appear. Task 5.
5. **A pass with defects, a repeated defect type, an owner with no linked worker, a bad photo path.** Task 2.

---

## File Structure

```
services/api/
  alembic/versions/<id>_roll_status_uses_the_latest_run.py   v_roll_latest_dye + replaced v_roll_status
  app/core/validate.py            check_upload_path(path, field)
  app/modules/store/service.py    uses check_upload_path
  app/modules/floor/service.py    handover copies dye and rework links
  app/modules/floor/board.py      dyeing output today from v_roll_latest_dye
  app/modules/orders/service.py   dyed_m and the quality-check stage from v_roll_latest_dye
  app/modules/qc/service.py       record_inspection, inspection_out, start_rework, queue
  app/modules/qc/router.py        real handlers (analyze and model-card stay examples)
  app/modules/passport/service.py get_passport
  app/modules/passport/router.py  real handler, buyer scoping
  tests/test_roll_latest_run.py  test_qc_inspection.py  test_qc_rework.py  test_qc_queue.py  test_passport.py  test_qc_chain.py
```

---

### Task 1: A roll's dyeing is finished when its latest dye run has ended

**Interfaces — Produces:** SQL view `v_roll_latest_dye(roll_id, run_id, machine_id, started_at, ended_at)`; `handover` copies `dye` and `rework` links.

**Migration (hand-written, revision "roll status uses the latest run", down_revision = `70a0b5bd9a55`):** create the view, then replace `v_roll_status`. Downgrade restores the B3 definition of `v_roll_status` and drops the new view. All of this SQL was run against the real schema before this plan was written (it compiles and returns zero rows on an empty database).

```sql
CREATE VIEW v_roll_latest_dye AS
SELECT DISTINCT ON (rr.roll_id) rr.roll_id, pr.id AS run_id, pr.machine_id, pr.started_at, pr.ended_at
FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
WHERE rr.purpose = 'dye'
ORDER BY rr.roll_id, pr.started_at DESC, pr.id DESC;

CREATE OR REPLACE VIEW v_roll_status AS
SELECT r.id AS roll_id,
  CASE
    WHEN d.state = 'dispatched' THEN 'dispatched'
    WHEN d.state = 'loading' THEN 'loading'
    WHEN li.verdict = 'reject' THEN 'rejected'
    WHEN li.verdict = 'pass' THEN 'in_store'
    WHEN li.verdict = 'rework' THEN
      CASE
        WHEN rw.run_id IS NULL THEN 'awaiting_rework'
        WHEN rw.ended_at IS NULL THEN 'in_rework'
        ELSE 'awaiting_qc'
      END
    WHEN dy.run_id IS NULL THEN 'woven'
    WHEN dy.ended_at IS NULL THEN 'dyeing'
    ELSE 'awaiting_qc'
  END AS status
FROM rolls r
LEFT JOIN dispatch_items di ON di.roll_id = r.id
LEFT JOIN dispatches d ON d.id = di.dispatch_id
LEFT JOIN LATERAL (SELECT q.verdict, q.inspected_at FROM qc_inspections q WHERE q.roll_id = r.id
                   ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) li ON true
LEFT JOIN v_roll_latest_dye dy ON dy.roll_id = r.id
LEFT JOIN LATERAL (SELECT pr.id AS run_id, pr.ended_at FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                   WHERE rr.roll_id = r.id AND rr.purpose = 'rework' AND pr.started_at >= li.inspected_at
                   ORDER BY pr.started_at DESC, pr.id DESC LIMIT 1) rw ON true;
```

**Code changes:** `orders/service.py` progress `dyed_m` becomes `SELECT COALESCE(SUM(r.metres), 0) FROM rolls r JOIN v_roll_latest_dye d ON d.roll_id = r.id WHERE r.order_id = :oid AND d.ended_at IS NOT NULL`; the quality-check stage test uses `EXISTS (SELECT 1 FROM v_roll_latest_dye d WHERE d.roll_id = r.id AND d.ended_at IS NOT NULL)` in place of the old "any ended dye run" test. `floor/board.py` dyeing output today becomes `SELECT d.machine_id, SUM(r.metres) AS qty FROM v_roll_latest_dye d JOIN rolls r ON r.id = d.roll_id WHERE d.ended_at IS NOT NULL AND (d.ended_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY d.machine_id`. `floor/service.handover` flushes the new run, then adds a `RollRun` to the new run for every `dye` and `rework` link of the old run.

**Tests (write first, `tests/test_roll_latest_run.py`; the B3 test `test_two_dye_links_one_ended_counts_as_awaiting_qc` in `test_roll_status.py` is replaced by the precise cases below):** the hand-over gap numbers above; a roll stays `dyeing` after a hand-over and `awaiting_qc` once the new run ends; a breakdown that ends the new run gives `awaiting_qc`; the old run still lists its rolls (history) and the new run lists them too; the order's stage is not quality check while the handed-over run is open; a dye link whose latest run is open beats an older ended one (`dyeing`), the reverse gives `awaiting_qc`; a rework run on a machine handed over stays `in_rework`; weaving hand-over leaves rolls on the old run; every existing roll-status, order progress, order stage and output-today test still passes.

### Task 2: Record an inspection (R9)

**Interfaces — Produces** (`qc/service.py`): `record_inspection(db, user: User, body: InspectionIn) -> QcInspection`; `inspection_out(db, inspection) -> InspectionOut`; (`core/validate.py`): `check_upload_path(path: str, field: str) -> str` (full match of `uploads/[0-9a-f]{32}\.(jpg|png|webp)`, else 422 `VALIDATION_ERROR` on `field`).

**Rules:** exactly decisions 1 and 2. Order of checks: roll exists (404 `roll_code`), inspector, photo path, defects (required and duplicates), then lock the roll row and check `awaiting_qc`; one transaction creates the inspection (`inspector_worker_id` = the user's worker, `inspected_at = db_now(db)`, `ai_suggestion` as sent, `overrode_ai` computed) and its defects. After commit: `roll.changed` (roll id) and `order.changed` (the roll's order id). `POST /qc/inspections` returns 201 `InspectionOut`.

**Tests (write first, `tests/test_qc_inspection.py`):** pass, rework with defects and reject with defects each flip the roll status (`in_store`, `awaiting_rework`, `rejected`) and the order's passed or rejected metres; `DEFECTS_REQUIRED` for rework and reject without defects, pass without defects fine, pass with defects fine; repeated defect type 422; every wrong status (woven, dyeing, in store, rejected, dispatched) is `ROLL_WRONG_STATUS`; unknown roll 404; bad photo paths (the same cases as the challan photo test) 422 and the shared helper still protects the store; `overrode_ai` true when the suggestion's verdict differs, false when it matches or is absent, the suggestion round-trips unchanged; owner without a worker and an inactive worker → `INSPECTOR_REQUIRED`; `inspected_at` from the real clock (the test from B3's style); events after commit only; roles (qc, owner; others 403); **Review Focus 1** (two threads on committed data, 5 repeats, plus the deterministic held-lock version).

### Task 3: Rework runs (R10)

**Interfaces — Produces** (`qc/service.py`): `start_rework(db, body: ReworkIn) -> ProductionRun`.

**Rules:** exactly decision 4: roll exists (404 `roll_code`); if a machine is given, lock it (404 `machine_code`, `MACHINE_INACTIVE`, `WRONG_STAGE` unless dyeing, `MACHINE_DOWN`, `MACHINE_BUSY` from the unique index); lock the roll row, `awaiting_rework` else `ROLL_WRONG_STATUS`; operator exists and is active; create the run (`stage='rework'`, the roll's order, `started_at = db_now(db)`) and the `rework` link; 201 `RunOut` through `floor.board.run_out`; after commit `roll.changed`, `run.changed`, and `machine.changed` when a machine was used.

**Tests (write first, `tests/test_qc_rework.py`):** the rework story numbers above end to end; manual mending (no machine) and re-dye on a dyeing machine; every refusal (wrong roll status, weaving or spinning machine, inactive, down, busy machine, inactive operator, unknown roll, machine and operator) leaving nothing behind; the run ends through `/runs/{id}/end` (no output allowed) and the roll returns to `awaiting_qc`; a breakdown on the machine ends it likewise; hand-over of a rework run on a machine keeps the roll `in_rework`; hand-over of manual mending is `WRONG_STAGE`; **Review Focus 3**; two simultaneous starts on one roll (5 repeats) and a held-roll-lock version; roles (supervisor, qc, owner).

### Task 4: QC queue

**Produces** (`qc/service.py`): `queue(db) -> QcQueue`. **Rules:** decision 6, from `v_roll_status` and the latest inspection verdict; rolls via `rolls.service.roll_outs`.

**Tests (write first, `tests/test_qc_queue.py`):** the six-roll counts and list above; `passed` includes a roll on a loading dispatch and a dispatched roll; oldest first; an empty database gives zero counts and an empty list; roles (qc, owner, supervisor; others 403).

### Task 5: Roll Passport

**Produces** (`passport/service.py`): `get_passport(db, user, roll_code) -> Passport` (applies `buyer_view` for buyers). **Rules:** decision 7. A buyer is scoped by `user.buyer_id` against the roll's order's buyer; both "not yours" and "no such roll" raise the same `AppError("NOT_FOUND", "Roll not found", field="roll_code", status=404)`.

**Tests (write first, `tests/test_passport.py`):** a full life (spinning run with yarn, weaving, dyeing, QC, rework) shows every run once in order, the lots, the inspections with defects; fully returned lot absent, partly returned lot present; hand-over histories show each run once; blocked lot flagged; cost and dispatch null; staff see inspector names, photos and AI output; a buyer sees only status, order, quality checks and dispatch with "Quality team" as the inspector; **Review Focus 2**: another buyer's roll and a missing roll give byte-identical bodies; an unknown roll 404 for staff; all roles can read an allowed roll.

### Task 6: Boundary checks, the chain through QC, live check, docs

- Old example-data tests for the replaced endpoints (`tests/test_contract_floor_qc.py`, `tests/test_contract_asks.py`, passport tests) are replaced by the real ones above; the vision endpoints keep their tests.
- **Contract stability:** `npm run contracts` leaves `contracts/` unchanged.
- **`tests/test_qc_chain.py`:** extends the B3 whole-chain test: after the dyed rolls wait for QC, an inspector passes one roll, sends one for rework (mending run, then a second inspection), rejects one; order progress, stage (through ready to ship), queue and passport agree at each step.
- **Live check** on a throwaway database and a real server: the demo mill plus the QC steps, the buyer's 404, the owner's `INSPECTOR_REQUIRED`, a hand-over of the demo's dyeing run keeping its rolls `dyeing`.
- Full suite twice; update the B3 plan (correction note about the hand-over gap), spec §5 (roll status uses the latest run), `docs/plans/README.md`; dated note to Ridanshi (QC and passport are real, the hand-over fix, `INSPECTOR_REQUIRED`, cost and dispatch still empty, analyze and model-card unchanged); memory; commit.

## Done when

- Suite green twice; `contracts/` byte-identical; the concurrency tests pass five repeated runs; every mutation of a lock, a status check or the latest-run rule makes a test fail.
- A dyed roll can be inspected, sent for rework, re-inspected and passed on a real server, and its passport shows the whole life.
- `docs/plans/README.md` marks B4 done.
