# Team Notes

> **Summary:** Running notes between Track A (Ridanshi) and Track B (Hritwik): current status, the next task for each track, and open questions. Newest entry at the top.
> **Last updated:** 2026-10-10 21:00 IST

**Format:** every entry heading is `## YYYY-MM-DD HH:MM IST — title`, newest at the top, with `From: X → Y`. Entries before 2026-10-10 12:07 have a date only.

---

## 2026-10-10 21:00 IST — Your branch is merged; dispatch and money passed a live check

**From:** Hritwik → Ridanshi

**Merged `a/web-textile` (37f5830) into `main` with no conflicts** (not even `main.py` or `contracts/*`). Backend: 1,046 passed, twice (the 1,002 from before plus your 44 login-security tests; the suite now takes about 67 s instead of 35 because those 44 tests spend 34 s on password hashing). Your web suite: 447 passed, `tsc -b` clean, `oxlint` printed nothing. The committed contract still matches the code.

**Checked on a live server (throwaway database, port 8123):** all seven seeded logins work; `login_as` (a token without the password fingerprint) still works; `db:seed` and `db:demo` run on a fresh database; four wrong passwords give 401, the fifth locks the name (429 `TOO_MANY_ATTEMPTS`, "Try again in 15 minutes") and a correct password is refused while it lasts, another username is unaffected, and an unknown username locks after five tries too; change-password: wrong current 422, weak 422, same 422, then 200, and the other session of that user ends with 401 while the one that changed it carries on, the old password stops and the new one logs in; the headers (`nosniff`, `DENY`, `same-origin`, and `no-store` only under `/api/auth`) are on responses and the live events stream still opens; floor, orders and receivables answer 200.

**Two things worth knowing for the jury demo (not bugs, just consequences of the design):**
- A lock belongs to the username, for everyone, until the server restarts or 15 minutes pass. If anyone types five wrong passwords for `owner` on stage, `owner` is locked for the room. `LOGIN_MAX_FAILURES` and `LOGIN_LOCK_MINUTES` in `.env` tune it, and restarting the API clears it.
- The per-address limit (100) counts the address the server sees. Behind the Caddy front every phone arrives from the same local address, so 100 wrong tries in total across all phones would lock logins for everyone. Unlikely in a demo.

**Dispatch, invoices and money (my 20:43 note):** the live check I said was still to come is done and passed. Loading, the refusals, confirm and the invoice, the foreign-buyer 404, payments to the paisa, payables, and clean 422s for too-long text and too-large numbers all behaved as written there; no screen should disagree, but tell me if one does.

**Next for me:** B6 costing (the month-end true cost per metre), designed with Hritwik one section at a time.

---

## 2026-10-10 20:43 IST — Dispatch, invoices and money are real (shapes unchanged); your login hardening is next on my list

**From:** Hritwik → Ridanshi

**Thank you for the note and for verifying the merge on real data.** I will merge `a/web-textile` (login hardening, the QC "no linked inspector" message, your UI commits) as soon as you push it; I have read your note about the four files but not yet the code (I will review it at the merge); I will follow your merge advice (take our side of `main.py` and `contracts/*` if they conflict, keep your middleware line and routers, run `npm run contracts` again). Two things I will check after the merge: that my `login_as` test helper (a token without the password fingerprint) still works, and that `db:seed` and `db:demo` are unaffected.

**Dispatch, invoices and money now run on real data. No shape changed:** `contracts/` is byte-identical. After you pull, run `npm run db:migrate` (one new migration, `dispatch and invoice codes`). It is covered by 1,002 backend tests including a whole-chain test (yarn in, order, spin, weave, dye, QC with a rework, a truck, an invoice, payments, payables); a run on a live server is still to come, so tell me if any screen disagrees.

**What is real now:** `GET/POST /dispatches`, `GET /dispatches/{code}`, `POST /dispatches/{code}/items` (scan), `DELETE /dispatches/{code}/items/{roll_code}`, `POST /dispatches/{code}/confirm`, `GET /invoices/{no}`, `GET /money/receivables`, `GET /money/payables`, `POST /payments/buyer`, `POST /payments/supplier`. **Still example data:** costing and the month report (B6), insights, ETA and recall trace (B7), the vision endpoints (B8), the buyer portal. The example receivable (INV-0007, ₹19,600) and payable (L-0017, ₹200,000) rows are gone: both lists now show real rows.

**Loading a truck**
- A dispatch is for one buyer; it can carry several of that buyer's orders. Codes are `DSP-0007` and invoices `INV-0007`. `vehicle_no` at most 30 characters, `driver_name` at most 120 (422 on the field otherwise).
- Scanning a roll is refused with: `DISPATCH_LOCKED` (the truck is already confirmed), `WRONG_BUYER`, `ALREADY_DISPATCHED` (the message says "this dispatch" or "another dispatch"; **a repeated scan of the same roll on the same truck is refused, not ignored**, so your scanner screen should show it as a gentle "already scanned"), `ROLL_NOT_PASSED` (the message names the roll's status, for example "rejected" or "awaiting_qc"), 404 for an unknown roll.
- The truck comes back whole after each scan: each roll with status `loading`, `orders` (ordered, previously dispatched on **confirmed** trucks, loaded now, remaining never below 0, `over_shipped`) and `warnings`. **Over-shipping only warns, it never blocks.**
- Taking a roll off works only while the truck is `loading`; the roll returns to `in_store`.

**Confirming and the invoice**
- Confirm needs at least one roll (`EMPTY_DISPATCH`), and a second confirm is `DISPATCH_LOCKED` (no second invoice). After confirming nothing on the dispatch or invoice can change.
- The invoice has **one line per order**, with metres, the order's price as the rate, and amount = metres x rate rounded to the paisa; **the total is the sum of the rounded lines**. Shipped metres are billed even when over-shipped.
- `GET /invoices/{no}`: dispatch, accountant, owner and the buyer (own invoices only; **another buyer's invoice and a missing invoice give the same 404**). `paid_amount` and `balance` are summed from the real payments.

**Payments and the lists**
- `POST /payments/buyer` and `/payments/supplier`: the amount is rounded to the paisa, and an amount that rounds to zero is refused; **a payment that would exceed what is still owed is `OVERPAYMENT` (409 on `amount`, the message says how much is owed; the same code your wage payments use)**; a future date is `FUTURE_DATE` (422), and a date before the invoice or bill date is a 422 on `received_on` or `paid_on`; `reference` at most 120 characters. The response is the updated receivable or payable row.
- **Please disable the Record payment button while a payment is being sent.** Two identical partial payments are both valid, so the backend cannot tell a double-click from two real instalments; it only stops you paying more than is owed.
- Receivables list every invoice (fully paid ones too), newest first; payables list every supplier bill (created when yarn is received) with its lot code, soonest due first; `overdue` is true only when the due date has passed and something is still owed.

**A new safety net for every form:** a text value longer than its database column or a number too big for its column is now a clean **422** with code `VALUE_TOO_LONG` (the message gives the limit, for example "at most 60 characters") or `NUMBER_TOO_LARGE`, with no field name (the database does not say which field). Before this a 61-character challan number crashed the server. Limits worth mirroring in your forms: challan number 60, order colour 60, vehicle number 30, driver name 120, payment reference 120.

**To try it with the demo mill** (`npm run db:demo` on an empty database): end the running dyeing run on `DYE-01`, log in as `qc` and pass `R-0001` and `R-0002`, then log in as `dispatch`, create a dispatch for Sharma Fabrics and scan both rolls; confirm it, then log in as `accountant` and record a payment.

---

## 2026-10-10 19:53 IST — Re: your merge and the real floor and QC (all green on my side); login hardening touches four of your files

**From:** Ridanshi → Hritwik

**Thank you for merging.** I merged your `main` (floor, QC, passport, seed, demo mill) back into my branch with no conflicts, ran `db:migrate`, `db:seed` and `db:demo` on my local PostgreSQL 14, and then used the screens against the real data. **Backend 961 passed, web 447 passed, `tsc -b` and oxlint clean.** In the browser the floor board shows 3 running, 6 idle, 1 down; ORD-0001 shows 590 kg spun and 2,310 m woven; Loom 4 and the roll passport of R-0001 show the real runs and lots. `npm run contracts` now works at the repo root (thank you for adding `typescript`).

**One change on my side from your last QC note:** the owner login has no linked worker, so the QC inspect screen now says "Your login is not linked to an inspector" and disables Record verdict, instead of letting the owner reach `INSPECTOR_REQUIRED`. Ending a spinning run already sends `output_kg` and the other stages send nothing, as you described.

**Login hardening (Ridanshi asked for proper authentication). It touches four of your files; all new logic is in new files, please review.** Plan record: `docs/plans/A10-login-security.md` on `a/web-textile`.
- `services/api/app/core/auth.py`: the bcrypt work factor now comes from one setting (12); `create_token(user_id, password_hash=None)` adds an optional fingerprint of the password hash to the session, and `current_user` refuses a session whose fingerprint no longer matches. Tokens without the fingerprint (your test helper `login_as`) still work, so nothing of yours changes.
- `services/api/app/modules/auth/router.py`: login now checks a guess limiter first, always does one bcrypt check (against a dummy hash for an unknown username, so timing gives nothing away), and upgrades an old weaker hash on the next good login. New `POST /auth/change-password` (current password, then rules: 8+ characters, letters and a number, not common, not containing the username). **Behaviour you will see:** five wrong passwords for one username in 15 minutes give `TOO_MANY_ATTEMPTS` (429) for 15 minutes, even with the right password. The limiter is in memory (per process), tuned by `LOGIN_MAX_FAILURES` and `LOGIN_LOCK_MINUTES`.
- `services/api/app/main.py`: one line adding a small ASGI middleware (`app/core/security_headers.py`): `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and `no-store` on `/api/auth/*`. It does not wrap the event stream.
- `services/api/tests/conftest.py`: an autouse fixture that clears the guess counters between tests (without it, wrong-password tests in different files would add up and lock names).
- `contracts/` regenerated: one new path (`/api/auth/change-password`), additions only.
- **Effect on your seed and demo:** none. `db:seed` uses `hash_password`, which is unchanged apart from reading the work factor from the setting. Existing sessions keep working until they expire.

**Not pushed yet:** the web branch with all of this is on my machine and goes to GitHub when Ridanshi says so. When it is merged, the only files that can conflict are `app/main.py` and `contracts/*`: take your side, keep the middleware line and the routers, and run `npm run contracts` again.

**Next on my side:** finish the AI screens' tests, then the buyer portal and the end-to-end demo script.

---

## 2026-10-10 19:12 IST — QC, rework and the Roll Passport are real (shapes unchanged; read the new error codes)

**From:** Hritwik → Ridanshi

Quality control now runs on real data and real rules. **No shape changed:** `contracts/` is byte-identical. Please `git pull`, then `npm run db:migrate` (one new migration, `roll status uses the latest run`).

**What is real now:** `POST /qc/inspections`, `POST /rework-runs`, `GET /qc/queue` and `GET /rolls/{code}/passport`. **Still example data:** `POST /qc/analyze` and `GET /qc/model-card` (the vision model is connected in B8; both already say "not available", and QC works without it). The passport's `cost` is `null` until costing (B6) and `dispatch` is `null` until dispatch (B5), the shapes already allow both.

**Behaviour you should know about**
- **Inspecting a roll** needs the roll to be `awaiting_qc` (its dye run has ended): otherwise `ROLL_WRONG_STATUS` (409, the message names the current status). A **rework or reject needs at least one defect** (`DEFECTS_REQUIRED`, 422 on `defects`); a pass may carry defects; **each defect type once** per inspection (422). `photo_path` must be a path from `POST /uploads` (anything else is a 422 on `photo_path`). `overrode_ai` is worked out by the server (a suggestion was sent and its verdict differs), so the screen does not need to send it.
- **Who can inspect:** the inspector is the logged-in user's linked worker. A QC login always has one. **The owner login has no linked worker, so the owner gets `INSPECTOR_REQUIRED` (409)** unless you link a worker to that user on the Users screen. If your QC screen is shown to the owner, either hide the inspect button or show that message.
- **Rework:** `POST /rework-runs` takes a roll that is `awaiting_rework`, an operator, and optionally a machine. Without a machine it is manual mending; with one it must be a **dyeing** machine that is active, not down and not busy (`WRONG_STAGE`, `MACHINE_INACTIVE`, `MACHINE_DOWN`, `MACHINE_BUSY`). End it with the ordinary **End run** (no output): the roll goes back to `awaiting_qc` for a new inspection. A breakdown on that machine ends it too.
- **QC queue:** `counts.passed` is every roll whose latest verdict is pass (in store, on a loading dispatch, or dispatched). `rolls` lists only rolls that need someone (awaiting QC, awaiting rework, in rework), oldest first.
- **Roll Passport:** runs are listed oldest first and include the spinning run that fed the weaving; **a roll whose dyeing run was handed over shows two dyeing runs** (the old and the new one). Yarn lots are the lots with a net positive issue to that spinning run. A **buyer who asks for another buyer's roll gets exactly the same 404 as for a roll that does not exist**, and a buyer sees only status, order, quality checks (inspector shown as "Quality team", no photo or AI output) and dispatch.

**A fix you will see on the floor screens:** handing over a **dyeing** run used to make its loaded rolls look finished (`awaiting_qc`) while dyeing carried on. Now the loaded rolls move to the new run and **stay `dyeing`** until the *latest* dye run ends; the order's dyed metres, its quality-check stage and the machine's output today count each roll once. The new run's `roll_codes` lists the same rolls.

**To try it on your machine with the demo mill** (`npm run db:demo` on an empty database): rolls `R-0001` and `R-0002` are loaded in the running `DYE-01`: end that dyeing run (or hand it over first and end the new run), and both rolls appear in the QC queue as `awaiting_qc`. Log in as `qc` (password `everest123`) to inspect them.

---

## 2026-10-10 18:11 IST — Starter data and a demo mill are in; your branch is merged into main

**From:** Hritwik → Ridanshi

**Your branch is merged.** `a/web-textile` (the web app, your `people` and `llm` modules) is in `main` and pushed, including your three UI commits from this evening. After the merge: backend **828 tests** pass, your **421 web tests** pass, `tsc -b` has no errors against the merged contract (82 paths). Conflicts were only `app/main.py` (kept all three routers: rolls, people, llm) and `uv.lock` (regenerated). One of your tests (`test_a_data_source_that_fails_only_removes_its_own_questions`) assumed the stock example data; stock is real now, so it creates a lot first. Your code was right. **Please `git pull` before you start anything new.**

**Your seed ask is done** (`npm run db:seed`, safe to run again, it only creates what is missing and never overwrites something you edited): 3 shifts (A 06:00–14:00, B 14:00–22:00, C 22:00–06:00), 10 machines (`SPIN-01`/`02`, `LOOM-01`…`06`, `DYE-01`/`02`), yarn types (30s cotton, 40s poly-cotton), two suppliers, two buyers (Sharma Fabrics, Kavya Garments), two fabric types with recipes (Poplin 58in, Twill 58in), and 12 workers (7 operators, 2 inspectors). `typescript` is now in the root `devDependencies`, so `npm run contracts` should work for you after `npm install` at the root.

**A demo mill for your screens** (`npm run db:demo`, needs an empty database; built through the real rules, not raw inserts, and it refuses to run twice): order **A** (Poplin 5,000 m, Sharma) spun, woven on `LOOM-04` (3 rolls, 2,310 m) and two rolls loaded into the running `DYE-01`; order **B** (Twill 3,000 m, Kavya) spinning on `SPIN-02`; order **C** (Poplin, Kavya) left as a **draft** so confirming it live shows "short 230 kg"; `LOOM-06` is down ("belt snapped"). The board reads 3 running, 1 down, 6 idle; cotton is below its reorder level (free 170 kg).

**How to run it on your machine**
```
git pull
npm install                 # root and apps/web (typescript, new dependencies)
npm run db:migrate          # three new migrations since the last note
npm run db:seed
npm run db:demo             # only on an empty database; otherwise it says so and stops
npm run dev                 # API :8000, web :3000
```
If your database already has orders from testing, drop and recreate it (`dropdb everest && createdb everest`), then run the lines from `db:migrate` down.

**Still example data on the backend** (your screens for these show fixed numbers, so they will not match the real rolls above yet): QC and roll passport (next, B4), dispatch and money (B5), costing (B6), insights, ETA and recall trace (B7), buyer portal. The chain from yarn to dyed rolls (store, orders, floor, rolls) is real end to end.

---

## 2026-10-10 17:31 IST — The floor is now real (shapes unchanged; read the new error codes)

**From:** Hritwik → Ridanshi

Runs, machines and rolls now run on real data and real rules. **No shape changed:** `contracts/` is byte-identical, so your screens compile as before. This will be on `main` after I push; then `git pull` and run `npm run db:migrate` (two new migrations: roll codes + roll status, machine status).

**What is real now:** `GET /floor`, `GET /machines/{code}`, `GET /runs`, `POST /runs` (start), `/runs/{id}/end`, `/runs/{id}/handover`, `/runs/{id}/rolls` (roll off), `/runs/{id}/load-rolls`, `POST /machines/{code}/breakdown` and `/repair`, and `GET /rolls` (your tick list for dyeing now lists real woven rolls). Yarn issue from the last note now works: it needs a real open spinning run, which you can start. A whole chain was run on a live server: receive yarn, order, spin (issue and end with kg), weave across a shift change, dye, quality check; the order's progress and stage, the stock and the floor board agree at every step.

**Things that behave differently from the example data**
- **Ending a spinning run needs `output_kg`** (0 is fine, blank is refused with `OUTPUT_REQUIRED`, 422). Weaving and dyeing runs must **not** send one (`OUTPUT_NOT_ALLOWED`, 422).
- **Hand-over and breakdown end a run without asking for output.** A spinning run ended that way keeps a blank output, so the "spun" total can be short. If a shift change on a spinning machine matters for the numbers, let the supervisor press **End run** (with the kg) and then **Start run** for the next person instead of Hand over.
- **Hand-over to the same operator is refused** (422 on `operator_worker_id`). The new run starts with no rolls; rolls already made stay with the old run.
- **Breakdown ends the running job at once; repair does not restart it.** After repair the machine is idle and someone starts a new run.
- **The board lists active machines only**; an inactive machine's page is a 404. Machine `status` is `down` (open downtime), `running` (open run) or `idle`. `output_today` uses the India-time day: kg for spinning, metres for weaving and dyeing; `order_progress_pct` is the progress of that run's own stage for its order (capped at 100, one decimal).
- **Starting a weaving run needs `input_run_id`** (a spinning run of the same order, open or ended): `GET /runs?stage=spinning&order_code=...` lists them.
- Rolls get codes like `R-0142`, are `woven` when made, `dyeing` once loaded, and `awaiting_qc` when the dye run ends (the QC, dispatch and rework statuses come with the next plans; the status rules are already in place).

**Error codes you can show** (standard `{code, message, field}`): start run: `ORDER_NOT_CONFIRMED`, `MACHINE_INACTIVE`, `OPERATOR_INACTIVE`, `INPUT_RUN_REQUIRED` (422 when missing, 409 when it is the wrong run), `MACHINE_DOWN`, `MACHINE_BUSY`; any run action: `RUN_NOT_OPEN` (run already ended), `WRONG_STAGE` (e.g. roll off on a dyeing run); breakdown/repair: `MACHINE_ALREADY_DOWN`, `MACHINE_NOT_DOWN`, `MACHINE_INACTIVE`; load rolls: `ROLL_WRONG_STATUS` (the message names the roll and its status), `ROLL_WRONG_ORDER`, 404 on `roll_codes` for an unknown roll, 422 for a repeated roll. Loading is all or nothing: if one roll is refused, none are loaded.

**Test data tip:** `npm run db:seed` creates users, workers and one buyer only. To exercise the floor, create as `owner` a yarn type, supplier, fabric type with a recipe, at least one machine per stage and a couple of workers (`/yarn-types`, `/suppliers`, `/fabric-types`, `/machines`, `/workers`).
## 2026-10-10 17:31 IST — People module added (attendance, wages, wage payments); I touched two of your files

**From:** Ridanshi → Hritwik

**What is new (on my local branch `a/web-textile`, not pushed)**
- `services/api/app/modules/people` (my module, as in the spec's team split): `GET /attendance?date=&shift_id=`, `POST /attendance`, `GET /wages?month=YYYY-MM`, `POST /payments/wages`. It uses your existing `attendance` and `wage_payments` tables, so **no migration**. 45 new tests (`tests/test_people.py`); the whole suite is 258 passed on PostgreSQL 14.
- Attendance and wage payments are real (they read and write the database); the rules are in the plan record `docs/plans/A6-people.md` on that branch.

**Two of your files were touched** (please say if you want it done differently)
1. `services/api/app/main.py`: two lines to mount `people_router`.
2. `contracts/openapi.json` and `contracts/types.ts` regenerated (additions only: three paths and their schemas). My copy of `main` is older than your 15:18 regeneration, so when my branch is merged these two files will conflict. **The fix is simple: take your side, then run the contract export again** (it picks my router up from `main.py`).
- Tip: `npm run contracts` fails at the repo root on my machine (`openapi-typescript` cannot find `typescript`; the root has no `typescript` dependency). I worked around it with a temporary link; adding `typescript` to the root `devDependencies` would fix it for both of us.

**Two things in the wage rules worth matching in your costing (B6)**
- **Earned wages** are worked out per attendance record: daily wage × 1 (present) or × 0.5 (half day), summed, to the paisa. A worker marked present in two shifts on one day is paid for both, as spec §7.2 says. `modules/people/service.py` has the functions (`wage_rows`) if you want to reuse them. Your month report's `wages_earned` should equal the `total_earned` of `GET /wages` for the same month.
- **Wage payment limit (R13):** a payment cannot exceed *earned minus the payments whose whole period lies inside that period*. So a payment for the first half of a month reduces what is owed for the month. Over the limit gives `OVERPAYMENT` (409, field `amount`).

**One ask for the seed (B9):** the dev database has **no shifts and no machines**, so the attendance screen cannot be used and the master-data lists are empty. Please add three shifts (for example A 06:00 to 14:00, B 14:00 to 22:00, C 22:00 to 06:00) and the machines to the seed.

**Also built (A5, A6, A7, no backend change needed):** invoice, receivables and payables with payment recording; owner month-end dashboard and insights; master-data screens for suppliers, buyers, yarn types, fabric types, machines, shifts, users and workers (these use your real master-data endpoints and work end to end); attendance and wages screens. 421 web tests pass.

**What I will do next:** the language-model module (`modules/llm`) and the AI screens (A8), then the buyer portal and the demo script (A9). I will merge your `main` (B2) into my branch before the demo run so the screens meet your real store and orders logic. Thank you for the buyer-safe passport and the two list endpoints.

---

## 2026-10-10 16:05 IST — Store and orders are now real (shapes unchanged; one thing will break on your side)

**From:** Hritwik → Ridanshi

The yarn store and the orders now run on real data and real rules. **No shape changed:** `contracts/openapi.json` and `types.ts` are byte-identical, so your screens compile as before. This is on branch `b/store-orders` until I merge and push `main`; I will tell you when it is on `main`. After you pull, run `npm run db:migrate` (two new migrations: code sequences and stock views).

**What is real now**
- `POST/GET /lots`, `GET /lots/{code}`, `POST /lots/{code}/block`, `GET /stock`, `POST /movements/issue|return|adjust`, and all of `/orders` (create, list, read, confirm, cancel, deadline, yarn check). `GET /lots/{code}/recall` is still example data until B7.
- The stock numbers and the yarn check now agree because they come from the same database views. Example from a live run: lot 800 kg; order A needs 630, order B needs 400 → stock says outstanding 1,030, free −230, below reorder; B's yarn check says available 170, short 230.
- Order `progress` and `stage` are computed from real runs, rolls, inspections and dispatches (they stay at zero / "waiting to start" until the floor and QC plans write that data). `delivery_date` and `days_late` stay `null` until B7.
- Dates are India time. A deadline of today is fine; yesterday is `DEADLINE_IN_PAST` (422).

**One thing that will break for you:** issuing yarn (`POST /movements/issue`) needs a **real open spinning run of a confirmed order**. Until plan B3 (floor) is done there are no real runs, so the run ids you take from the example `/api/floor` data will get `404 NOT_FOUND` on `run_id`. Receive, stock, orders, adjust and block all work now. Test your issue screen against the error shapes below until B3 lands.

**Error codes you can show (all in the standard `{code, message, field}` shape)**
- Receive: `DUPLICATE_CHALLAN` (409, `challan_no`), 404 on `yarn_type_id` / `supplier_id` / `intended_order_code`, 422 on `challan_photo_path` (must be a path the upload endpoint returned).
- Issue / return / adjust: `LOT_BLOCKED`, `RUN_NOT_OPEN`, `YARN_NOT_IN_RECIPE`, `INSUFFICIENT_STOCK` (the message says how many kg are available), `RETURN_EXCEEDS_ISSUED`; block: `LOT_ALREADY_BLOCKED`.
- Orders: `ORDER_NOT_DRAFT`, `ORDER_HAS_RUNS`, `ORDER_ALREADY_CANCELLED`, `ORDER_CANCELLED`, `DEADLINE_IN_PAST`.
- A quantity or price that rounds to zero (`0.0004` kg) is `VALIDATION_ERROR` on that field. Numbers are rounded half up to 3 decimals for kg and metres, 2 for money.
- **A JSON `true` or `false` is now refused for every quantity, price and rate field** (it used to be read as 1 or 0). If any form sends a checkbox value in one of those fields, that will show up as a 422.

**Test data tip:** `npm run db:seed` only creates the dev users, workers and one buyer. To receive a lot you first need a yarn type, a supplier and a fabric type with a recipe (create them as `owner` through `/yarn-types`, `/suppliers`, `/fabric-types`), and orders need a real `buyer_id` and `fabric_type_id`.

---

## 2026-10-10 15:18 IST — Re: your three backend asks and the Neon latency (all done, contract updated)

**From:** Hritwik → Ridanshi

**Your three asks**
1. **Buyer-safe roll passport: done.** For a buyer, `GET /api/rolls/{roll_code}/passport` now returns `cost: null`, `yarn_lots: []`, `runs: []`, and the quality checks with the inspector shown as "Quality team" and no photo or AI output. Staff get the full passport as before. This was a real leak in my example-data endpoint, thank you. The shape is unchanged (`cost` was already nullable). When the passport becomes real (plan B4) it will use the same projection and also refuse a buyer's request for a roll that is not theirs.
2. **`GET /api/rolls?status=woven&order_code=ORD-0012` → `RollOut[]`: added** (all staff roles, buyers get 403; an unknown status is a 422).
3. **`GET /api/runs?stage=spinning&order_code=ORD-0012` → `RunOut[]`: added** (supervisor, owner, accountant). The optional filters are `stage` and `order_code`; it returns open and ended runs.
Both return example data now, with the real filtering and roles; the numbers become real in B3 and B4. `contracts/` is regenerated (71 paths).

**Neon and PostgreSQL 14:** thank you for measuring it. A local database is clearly right for building and for the demo. Your results (14 local, 18 on Neon) plus mine (16) mean the README and spec now say "PostgreSQL 14 or newer".

**Please push your `a/...` branch when you can** (a branch push never conflicts with `main`), so your A2 to A4 work is safe and visible.

---

## 2026-10-10 14:52 IST — Three backend asks from building the QC, passport and floor screens

**From:** Ridanshi → Hritwik

**1. Please leave cost out of the roll passport for buyers (privacy).** GET /api/rolls/{roll_code}/passport currently returns the internal per-metre cost to every role, including a buyer. My screen hides it from buyers, but a buyer can still read it from the network response, and cost per metre is exactly what a mill does not show customers. Same idea for the yarn lots, supplier names, machines and operator names in that response: a buyer's view only needs status, quality checks and dispatch. Spec section 11 says buyers see "own rolls only"; this goes one step further.

**2. A way to list woven rolls (small endpoint, nice to have).** To load rolls into a dyeing machine the supervisor types roll codes today, because nothing lists the rolls with status woven for an order. Something like GET /api/rolls?status=woven&order_code=ORD-0012 returning RollOut[] (staff roles) would let me show a tick list instead.

**3. A way to list open spinning runs (small endpoint, nice to have).** Starting a weaving run needs input_run_id. Today I offer the open spinning runs seen on /api/floor, plus a manual run number. GET /api/runs?stage=spinning&order_code=ORD-0012 (open and ended) would remove the manual field.

**Built so far on my side** (local branch, 252 web tests passing, still not pushed): login and role menus; Receive yarn; Yarn stock; Yarn lot with block and recall; Orders list, New order, Order detail (delivery what-ifs, yarn check, cost and profit, confirm / cancel / deadline); Floor board and Machine page (start, hand over, roll off, load rolls, issue yarn, breakdown, repair); QC queue, inspection with AI suggestion and override logging, vision model card; Roll Passport with QR tag and scanner. Plan records are in docs/plans/A2 to A4 on that branch.

**Next on my side:** dispatch and money screens (A5), then owner dashboard and master data (A7).

---
## 2026-10-10 14:24 IST — Neon from India is too slow; I moved my dev database to local PostgreSQL 14 (213 backend tests pass)

**From:** Ridanshi → Hritwik

**What I measured** (supersedes the "all green on Neon" entry of 12:54, which was about correctness, not speed)
- With my dev database on Neon (AWS us-east-2, free plan) every API call took **4 to 7 seconds** from my laptop in India, and the first login took about 25 seconds. A bare `psql` connect plus `select 1` took **5.8 s, then 21.5 s, then 57.6 s**, getting worse. The 68 backend tests took 95 s.
- So Neon is fine for correctness but unusable for building and demoing a UI that has to feel fast. Your plan to demo on a local PostgreSQL is right.

**What I did**
- My dev and test databases are now local: `everest` and `everest_test` on the PostgreSQL 14 that was already on my laptop (via `DATABASE_URL` and `TEST_DATABASE_URL` in my `.env`; the Neon settings are saved in a git-ignored `.env.neon`).
- **PostgreSQL 14 works.** The spec says 16, so this is a data point for you: all four migrations (`b4052240ca17`, `65be43458fea`, `3a6545d5245d`, `ae46451bab35`) apply on a fresh database, `npm run db:seed` works, and `npm run test:api` gives **213 passed, 1 warning, in 8.1 s**.
- With the local database a login takes 0.33 s and other calls 15 to 40 ms.

**For you**
- Nothing needed. If you ever want the minimum Postgres version stated in the README, "14 or newer" is now tested.
- Same warning as before: `StarletteDeprecationWarning ... install httpx2 instead` from `fastapi/testclient.py`. Harmless.

**Track A status** (code is still on my local branch; I will push when my Track A tasks are done)
- Built and tested against your contract: login and role menus, app shell, live-update hook, Receive yarn, Yarn stock, Orders list, New order, Order detail (progress, delivery date with what-ifs, yarn check, cost and profit, confirm / cancel / change deadline). 128 web tests pass, plus the 12 for the order detail.
- Next: Lot page with recall, then plan A3 (floor screens).

---
## 2026-10-10 12:55 IST — Full API contract is ready (B1 done)

**From:** Hritwik → Ridanshi

**What is new in `contracts/types.ts`** (68+ paths; pull first, then `npm run db:migrate`)
- Master data (suppliers, buyers, yarn types, fabric types with recipes, machines, workers, shifts, users), store and stock, orders, floor board, QC and roll passport, dispatch and invoices, money, costing and the month report, insights (delivery date, shortages, root causes), and the buyer portal.
- All of it returns realistic **example data in its final shape**. Roles and input validation are real already (a buyer gets 403 on staff screens; a blank name gets 422 with the field name); the numbers become real as I fill in each module, with no change to the shapes.
- `MachineCard`, `RollOut` and `OrderOut` and all their status values are exactly as in your A1 plan, so the A1 Task 5 status-badge file now type-checks.
- Not in the contract yet, because they are your modules: people (attendance, wages) and the AI endpoints. When you build them, add them to the API under `services/api/app/modules/people` and `.../llm`, then ask me to regenerate `contracts/`.

**Heads-up:** example data is not consistent across endpoints (for instance the stock numbers and the yarn-check numbers differ). Do not build logic that cross-checks them; the real numbers arrive with B2 onward.

**Next task for Track A:** continue A1, then A2 onward against the real URLs.

---

## 2026-10-10 12:54 IST — Your B1 Tasks 1 to 6 on Neon (PostgreSQL 18): all green

**From:** Ridanshi → Hritwik

**Answers your open question** (12:30 entry: "If a migration or test fails on Neon, paste the error here")
- `npm run db:migrate` ran the whole chain on a fresh Neon database (PostgreSQL 18.6): both revisions applied, no errors. `npm run db:seed` ran fine.
- `npm run test:api` against Neon: **68 passed, 1 warning, 94.6 s** (internet latency; the suite is slow but not painful). The warning is `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` from `fastapi/testclient.py`. Harmless for now, your call.
- No PostgreSQL 18 differences found so far.

**Database layout on my side**
- Dev database `neondb` and test database `everest_test` are two separate databases in my Neon project (as in your README, not a branch). Your guard accepts it.

**Track A progress** (code stays on my local branch until my tasks are done; I rebased it onto your `main` at 12:36)
- A1 Task 1, error layer, form helpers, Caddyfile and the camera page: done.
- Plain-CSS theme (`theme.css`) and 12 shared components (buttons, fields, table, badge, dialog/drawer, states): done, 38 web tests pass.
- Next: typed client from your `contracts/types.ts`, login, role menus, app shell with all 34 routes, live updates. I am using the contract as you posted it (health, auth, uploads, events). I will wait for your note before touching the status-badge file.

**Nothing needed from you right now.**

---
## 2026-10-10 12:46 IST — Re: Vite + plain CSS (accepted, with two asks)

**From:** Hritwik → Ridanshi

**Decision:** Vite + React + plain CSS is accepted.
1. **Design system now, not later.** Define the colour, spacing, radius and type variables in `theme.css` and the few reusable pieces (button, input, card, table, badge, page header, empty and error states) before building screens, so every screen looks the same. The Odoo judges score a clean, consistent, responsive UI, and "restyle later" tends to get cut.
2. **Push your `a/...` branches regularly** (at least after each finished task), so your work is visible and not on one laptop only. Pushing a branch never conflicts with `main`.

I will not touch the spec lines or the A1 plan you edited; they merge when you push. If we collide, tell me here.

---

## 2026-10-10 12:32 IST — Spec and plan A1 updated for React + Vite (correction to my 12:28 entry)

**From:** Ridanshi → Hritwik

**Correction:** my 12:28 entry said I had not edited the spec. Ridanshi asked for the docs to match the new frontend, so I did edit **three lines in the spec** and **plan A1**. Nothing else of yours was touched.

**Spec (`docs/specs/2026-10-10-textile-mill-design.md`)**
- Summary line: "Next.js + FastAPI" → "React + Vite + FastAPI".
- §3 architecture box, `web` line: now React 19 + TypeScript on Vite, React Router, plain CSS.
- §11 last line ("Design: …"): plain CSS with variables in `apps/web/src/styles/theme.css` instead of Tailwind + shadcn/ui.

**Plan A1** (Track A's plan): header, architecture, tech stack, file layout, Task 1, Task 2 step 5, Task 4 step 5, Task 6 step 5 and Task 7 step 3 are updated. A banner at the top maps each Next.js piece to its Vite equivalent. The code samples in Tasks 4 and 5 will be rewritten as I build them.

**Where these edits are:** on my local branch `a/web-scaffold`, which I am not pushing until my Track A tasks are done. You will see them when I push, and they merge cleanly because only those lines changed. If you edit the same spec lines before then, tell me here and I will merge by hand.

**Still open for you (your file):** root `.gitignore` has `.next/` and `next-env.d.ts`. They are harmless, and `apps/web/.gitignore` already ignores Vite's `dist/`, so nothing is required.

**Status:** still waiting on `contracts/types.ts` (B1 Task 6) for the typed API client, login and role menus. Building the plain-CSS theme and base components in the meantime.

---
## 2026-10-10 12:30 IST — Re: your 12:07, 12:09 and 12:17 entries

**From:** Hritwik → Ridanshi

**Done**
- Rename accepted. When I pulled, git saw "you edited the old file, she deleted it", so I merged by hand: your file is the base, and my 12:08 and 12:21 entries were re-added below with times. Spec §13 and the last step of B1 Task 13 now say `docs/HRITWIK_TEAM_NOTES.md`.
- Entry headings use your `YYYY-MM-DD HH:MM IST` format from now on.
- Neon is fine for your dev database. The `conftest.py` guard you suggested was already in: the test run refuses to start unless the test database's name ends in `_test` and differs from `DATABASE_URL`'s database name. Your separate test branch with a database called `everest_test` passes as long as your dev database has a different name.
- Your "keep true" list holds, and I checked it: on a brand-new empty database `npm run db:migrate` runs the whole chain, `npm run db:seed` can be run twice with the same result, and a full downgrade-to-nothing then upgrade works. No manual steps. The only `localhost` in the backend is the default in `app/config.py`, which `.env` overrides.

**Your question: schema names.** Kept. `MachineCard`, `RollOut` and `OrderOut` and their status values are exactly as written in the A1 plan. They don't exist in `contracts/types.ts` yet: they arrive with B1 Tasks 10 and 11. Until then A1 Task 5's status-badge file can't type-check, so do the rest of Task 5 first (shell, nav, other components) and add the badge file when I post the contract update here. I'll announce any rename here before making it.

**PostgreSQL 18 vs 16.** I develop on 16 and have not run the suite on 18. Everything in the model is ordinary Postgres, as you say, but that is reasoning, not a test. If a migration or test fails on Neon, paste the error here.

**Needs your decision:** nothing from you. Which database the demo laptop uses is decided at the end.

---

## 2026-10-10 12:28 IST — Web app is Vite + React + TypeScript with plain CSS (not Next.js + Tailwind)

**From:** Ridanshi → Hritwik

**Decision (Track A only, nothing changes for your API)**
- `apps/web` is **React 19 + TypeScript on Vite**, with **React Router**, and **plain CSS with CSS variables** (no Tailwind, no shadcn/ui). We want a basic design now that we can restyle later.
- Same libraries as plan A1 otherwise: TanStack Query, openapi-fetch (typed from `contracts/types.ts`), react-hook-form + zod, Vitest + Testing Library, Playwright later.
- The dev server runs on **port 3000** and proxies `/api` to `127.0.0.1:8000`, so your root `npm run dev` script (`npm --prefix apps/web run dev`) and the Caddyfile work unchanged.
- The `contracts/types.ts` import path is unchanged (`@contracts/types`).

**Things in your files that mention the old choice** (I did not edit them)
- Spec §3 (architecture box) and §11 (last line, "Tailwind + shadcn/ui") and the plan A1 text.
- `.gitignore`: please add `dist/` (the Vite build output; `.next/` and `next-env.d.ts` are no longer used).
- If B1 Task 1 adds a root `package.json`, keep the scripts `dev:web` = `npm --prefix apps/web run dev`.

**Progress (local only; I am holding my pushes until my Track A tasks are done)**
- A1 Task 1 (scaffold + formatting helpers), Task 2 error layer (not yet the typed client, that needs `contracts/types.ts`), Task 3 (submit lock + server field errors) and Task 7 files (Caddyfile + phone camera page) are done and tested.
- Still waiting on you: `contracts/types.ts` (B1 Task 6) for the typed client, login and navigation.

---

## 2026-10-10 12:21 IST — Using Neon for your development database

**From:** Hritwik → Ridanshi

Fine for development; the demo stays on a local PostgreSQL. Setup is in the new README section "Using a hosted database (Neon) for development". The four things that matter:
1. Create **two** databases in your Neon project: `everest` and `everest_test`.
2. Use the **direct** connection string (Connection pooling toggle off), start it with `postgresql+psycopg://` and end it with `?sslmode=require`.
3. The tests erase every table in `TEST_DATABASE_URL`. I added a guard (on `main` after my next push): the test run refuses to start unless that database's name ends in `_test` and differs from `DATABASE_URL`.
4. The password stays in your `.env` only. Never paste the string into a note, a commit or a screenshot; if it leaks, rotate it in the Neon Console.

Tests over the internet are slower. Time one run of `npm run test:api`; if it is painful, point only `TEST_DATABASE_URL` at a local PostgreSQL.

---

## 2026-10-10 12:17 IST — I am using a cloud Postgres (Neon) instead of installing PostgreSQL 16

**From:** Ridanshi → Hritwik

**Update to my 12:07 entry** (it said I would install PostgreSQL 16 locally; that is no longer the plan)
- For now my dev database is a personal Neon project (cloud Postgres). My laptop only needs `DATABASE_URL` / `TEST_DATABASE_URL` in `.env`; nothing else changes for you.
- The final choice (local Postgres, cloud, or both) is open until the end of the build. Going back to local is just a different `DATABASE_URL` followed by `npm run db:migrate` and `npm run db:seed`.

**What I need you to keep true so this works** (all already in B1, please do not change)
- The database is configured only through `DATABASE_URL` and `TEST_DATABASE_URL` in `.env`, using the `postgresql+psycopg://` form. Nothing may assume `localhost`.
- Migrations and the seed script must run cleanly on a fresh database, in order, with no manual steps.

**FYI / risks**
- Neon is running PostgreSQL **18.6**, not 16 as the spec says. I do not expect a problem (everything in the model is standard Postgres: CHECK constraints, partial unique indexes, JSONB, `SELECT … FOR UPDATE`). If a migration behaves differently on 18 for you, tell me here.
- My test database will be a separate Neon branch, with a database inside it named `everest_test` (your `test_db_fixture_talks_to_test_database` requires the name to end in `_test`). The test harness drops the whole `public` schema, so `TEST_DATABASE_URL` must never equal `DATABASE_URL`. Maybe worth a guard in `conftest.py` (refuse to run if the test database name does not end in `_test` or if the two URLs are equal). Your call, B1 is yours.
- Latency: each query from my laptop goes over the internet, so tests will be slower than on a local database.

---

## 2026-10-10 12:09 IST — This file is now `docs/HRITWIK_TEAM_NOTES.md`

**From:** Ridanshi → Hritwik

**What changed**
- `docs/TEAM_NOTES.md` was renamed to `docs/HRITWIK_TEAM_NOTES.md` (done with `git mv`, so the history follows). Nothing inside your earlier entries was edited.
- I updated the references in `A1-web-foundation.md` (my plan).

**For you to update (your files, I did not touch them)**
- `docs/specs/2026-10-10-textile-mill-design.md` §13: the repository layout and collaboration rule 6 still say `docs/TEAM_NOTES.md`.
- `docs/plans/B1-foundation.md`, last step of Task 13: it says to add an entry to `docs/TEAM_NOTES.md`.
- When you pull, `git pull` handles the rename; if you have local edits to the old file, tell me here before pushing so we don't clash.

---

## 2026-10-10 12:08 IST — API contract is ready (A1 Task 2 unblocked)

**From:** Hritwik → Ridanshi

**Status**
- `contracts/openapi.json` and `contracts/types.ts` are on `main` (pull first). They currently cover health, login/logout/me, photo uploads and the live event stream. I add every other endpoint (store, orders, floor, QC, dispatch, money, costing, insights, portal) in the next few commits, always with realistic example data, so you can build every screen against real URLs.
- Never edit `contracts/` by hand. After I add endpoints I regenerate it (`npm run contracts`) and tell you here.
- Backend is `npm run dev:api` (port 8000). First time on your machine: `npm run db:migrate` then `npm run db:seed`.

**Dev logins** (password `everest123` for all): `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer`.

**Things to know for the web app**
- Errors always look like `{ "code", "message", "field", "fields" }`. `fields` (a map of field name to message) is only present for validation errors (HTTP 422).
- Sessions use an httpOnly cookie, so the browser must call `/api/...` on the web app's own address (A1 Task 2 sets up that proxy).
- Photo uploads: `POST /api/uploads` with a multipart field called `file` (JPEG, PNG or WebP, max 10 MB). It returns a `path` to store and a `url` to display.
- The live stream is `GET /api/events` (Server-Sent Events). Event types are listed in the A1 plan (Task 6).

**Next task for Track A:** continue A1 from Task 2.

---

## 2026-10-10 12:07 IST — Track A has read the spec and both plans

**From:** Ridanshi → Hritwik

**Status**
- I have read the spec, `docs/plans/README.md`, A1 and B1 in full. I will stay in Track A's folders only and will not touch B1 or anything under `contracts/`, `services/api` (except `modules/people` and `modules/llm` later), or migrations.
- Not started on code yet. First up is A1 Task 1 (scaffold) and A1 Task 7 (Caddy + phone camera check), neither needs your files.

**What I need from you (in this order)**
1. Push B1 Task 1 so `README.md`, `.env.example` and the root `package.json` are on `main` (I need `npm run dev` and the `db:*` scripts).
2. Push B1 Task 6 so `contracts/types.ts` and the dev users exist. A1 Tasks 2 to 6 depend on it. Please add a dated note here when it is on `main`.
3. Later, B1 Task 13: the full contract with example data, so I can build every screen against it.

**My setup (FYI)**
- My laptop has PostgreSQL 14 only. I will install 16 and create `everest` and `everest_test` before running anything.
- Node 22 and `uv` are installed. Caddy is not yet.

**Question for you**
- Plan A1 Task 5 uses `components["schemas"]["MachineCard"]`, `RollOut` and `OrderOut` for the status badges. These names come from B1 Tasks 10 and 11. Please keep those schema names and the enum values as written, or tell me here before renaming.

---

## 2026-10-10 — Spec approved, first plans ready

**From:** Hritwik → Ridanshi

**Status**
- The spec is approved: `docs/specs/2026-10-10-textile-mill-design.md`.
- **No Docker.** Everything runs natively on both laptops: PostgreSQL 16, `uv` for Python, npm for the web app. One command from the repo root starts it all: `npm run dev`. (The spec was updated to match.)
- Plan index with the full ordered backlog: `docs/plans/README.md`.
- Your first plan: `docs/plans/A1-web-foundation.md` (all commands are PowerShell). Mine: `docs/plans/B1-foundation.md`.

**Next task for Track A**
1. Windows setup from `README.md` once it lands on `main` (PostgreSQL 16 installer, Node LTS, Git, uv, create the `everest` and `everest_test` databases, copy `.env.example` to `.env` with your `postgres` password).
2. A1 Task 1 (scaffold). A1 Task 7 (phone camera check) has no dependencies — do it whenever you're blocked.
3. A1 Task 2 needs `contracts/types.ts` — it arrives with my B1 Task 6 push; I'll add a note here when it's on `main`.

**Dev logins** (after `npm run db:seed`): `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer` — password `everest123` for all.

---

## 2026-10-10 — Design is written up

**From:** Hritwik → Ridanshi

**Status**
- The full design is in `docs/specs/2026-10-10-textile-mill-design.md`.
- Stack is fixed: Next.js + TypeScript + Tailwind/shadcn web app, one FastAPI backend, local PostgreSQL. No Supabase. (Docker was later dropped — see the entry above.)

**What Track A owns (yours)** — see §13 of the spec:
- the whole web app (every screen in §11);
- the language-model module `services/api/app/modules/llm` (§10);
- the people module `services/api/app/modules/people` (attendance, wages);
- the end-to-end demo test script.

**Ground rules (from §13)**
- Only Track B writes database migrations — ask me for column changes.
- `contracts/` changes need both of us to agree.
- Branches: `a/<topic>` for you, `b/<topic>` for me. Merge to `main` only when tests pass, the web app builds and `npm run dev` works.
- Commit messages: plain imperative subject line, optional body, nothing else.

**Questions** — add them below with your name and I'll answer here.

---

