# B9a — Starter data and the mid-day demo mill

> **Summary:** Two scripts that give an empty database something to show: a base seed of the starter facts every mill has (3 shifts, 10 machines, yarn types, suppliers, buyers, fabric types with recipes, more operators) run by `npm run db:seed`, and `npm run db:demo`, which builds a mill in the middle of a working day by calling the same service functions the API uses. B9 proper (the bad lot L-17, the rework-loss order, the late order, `docs/demo.md`) still needs B4 to B7.
> **Last updated:** 2026-10-10 18:11 IST (Tasks 1-2 done)

**Why now:** Ridanshi's note asks for shifts and machines in the seed (her attendance screen and master-data lists are empty without them), and the backend and web app are being connected tonight: connected screens need real rows to show. Approved by Hritwik on 2026-10-10 (full version).

## Decisions

1. **Base seed = create only if missing**, by each thing's unique key (shift name, machine code, yarn type code, supplier name, buyer name, fabric type name, worker code). Running it twice changes nothing; it never overwrites a row someone edited. It stays inside `npm run db:seed` (users, workers and the Sharma buyer as before).
2. **The demo mill goes through the real services** (`receive_lot`, `create_order`, `confirm_order`, `start_run`, `issue_yarn`, `end_run`, `roll_off`, `load_rolls`, `breakdown`), not raw inserts, so every number is one the rules produced and a rule change shows up as a failing test. It refuses to run if any lot or order already exists and says to use an empty database. (An earlier idea, a `--force` flag that adds a second mill, was dropped: a second mill would try to start runs on machines that are already running or down, so it could only ever half-work.)
3. Dates are relative to the day it runs (deadline = today + 10 days), never hard-coded.
4. Names: yarn types and codes match the example data Ridanshi built against (`30S-COT-RAW`, `40S-PC-RAW`, "Poplin 58in"); the second supplier and the second buyer are fictional.

## The starter facts

3 shifts (A 06:00–14:00, B 14:00–22:00, C 22:00–06:00). 10 machines: `SPIN-01`, `SPIN-02` (20 and 22 kg/h), `LOOM-01`…`LOOM-06` (28 m/h), `DYE-01`, `DYE-02` (45 m/h). Yarn types: 30s cotton (reorder 300 kg), 40s poly-cotton (reorder 250 kg). Suppliers: Vardhman Yarns, Coastal Spinners. Buyers: Sharma Fabrics, Kavya Garments. Fabric types: Poplin 58in (30s cotton 0.12 kg/m, wastage 5%), Twill 58in (40s poly-cotton 0.16 kg/m, wastage 4%). Workers: the five existing plus six operators and one inspector.

## Hand-worked numbers for the demo mill (the tests assert these)

- Lot 1: 800 kg of 30s cotton at ₹250; lot 2: 1,450 kg of 40s poly-cotton at ₹280.
- **Order A**: Poplin 5,000 m for Sharma, confirmed: need 5000 × 0.12 × 1.05 = **630 kg**. `SPIN-01` run, **587.5 kg** issued, ended with **590 kg**: cotton on hand **212.5 kg**, outstanding **42.5 kg**, free **170 kg** (below the 300 reorder level). `LOOM-04` runs on it and has made rolls of 1,000 + 800 + 510 = **2,310 m** (46.2%); `DYE-01` has the first two rolls (1,800 m) loaded and is still running; the third roll is still woven. Order A's stage is dyeing.
- **Order B**: Twill 3,000 m for Kavya, confirmed: need 3000 × 0.16 × 1.04 = **499.2 kg**; `SPIN-02` runs on it with **300 kg** issued: poly-cotton on hand 1,150 kg, outstanding 199.2 kg.
- **Order C**: Poplin 3,174.603 m for Kavya, left as a **draft**: need **400 kg**; its yarn check says available **170**, **short 230 kg**, which is the "confirm a new order, short 230 kg" step of the demo.
- Board: **3 running** (`SPIN-02`, `LOOM-04`, `DYE-01`), **1 down** (`LOOM-06`, "belt snapped"), **6 idle**.

## Status

Task 1 done and verified (2026-10-10 18:05 IST): `scripts/seed_dev.py` now has `seed_users`, `seed_master` and `seed_all` (create only if missing by unique key; `main()` calls `seed_all`), 7 more workers (12 in all), and `typescript` is in the root `devDependencies` (`npm run contracts` leaves `contracts/` byte-identical). 6 new tests in `tests/test_seed_base.py`; mutation-proven (overwriting an edited row, a wrong reorder level, a seed that stops completing a partly seeded database, a wrong recipe). 
Task 2 done and verified (2026-10-10 18:11 IST): `scripts/seed_demo.py` (`build_demo`, `DemoRefused`, `main`) and `npm run db:demo`; 8 tests in `tests/test_seed_demo.py` through the real API (board 3 running / 1 down / 6 idle, cotton on hand 212.5 / outstanding 42.5 / free 170 and below its reorder level, poly-cotton 1,150 / 199.2 / 950.8, order A in dyeing with 590 kg spun and 2,310 m woven, order B spinning with need 499.2, order C a draft that is short 230 kg, rolls 2 dyeing + 1 woven, LOOM-04 at 46.2% with 2,310 m today, SPIN-01 590 kg today, the lots, the refusal on a second run, and a database that was already seeded); mutation-proven (a wrong issue quantity, order C confirmed, no breakdown, the refusal removed, one roll not loaded). The seed tests swap bcrypt for a fast stand-in so the suite stays at about 20 seconds. Run for real on a throwaway database: `db:migrate`, `db:seed` twice (same row counts), `db:demo` (3 orders, 2 lots, 4 runs, 3 rolls), a second `db:demo` refused with exit code 1 and nothing added. **`--force` was dropped** (a second mill would collide with the machines the first one is using). Full suite 828 passed, twice; contract unchanged. B9a is complete; B9 proper (L-17, the rework-loss order, the late order, `docs/demo.md`) still waits for B4 to B7.

## Tasks

1. **Base seed and `typescript`:** `seed_master(db)` and `seed_all(db)` in `scripts/seed_dev.py` (the CLI calls `seed_all`), the extra workers, and `typescript` in the root `devDependencies` (Ridanshi's `npm run contracts` failed without it). Tests: all starter facts present with the right values; running twice adds nothing; an edited row is not overwritten.
2. **Demo mill:** `scripts/seed_demo.py` with `build_demo(db, force=False)`, and `npm run db:demo`. Tests: every number above through the API; a second run is refused with a message that names the fix; it also works on a database that is already seeded.
3. **Sync:** README setup lines, plan index, team note to Ridanshi, memory, commit.

## Done when

Both scripts run on an empty database (`db:migrate`, `db:seed`, `db:demo`), the suite is green twice, `contracts/` is byte-identical, and a real server started on that data shows the board and stock numbers above.
