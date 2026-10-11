# B9 — A Simulated Month: Design

> **Summary:** A script that builds `everest_month`, a separate database holding 30 days of believable mill history ending an hour before the build, by running the real service functions under a simulated clock (12 confirmed orders of 39,500 m, 16 yarn lots, 83 rolls, QC, rework, dispatch, invoices, payments, attendance and wages), with seven built-in stories (a bad yarn lot, a rework-loss order, a late order, low yarn, broken and idle machines, overdue money, a mill still running now) and an audit that proves each one shows up through the real endpoints.
> **Last updated:** 2026-10-11 06:28 IST (built; section 9 added)
> **Status:** Built and checked 2026-10-11 06:28 IST (plan `docs/plans/B9-month-simulation.md`, all 7 tasks); see section 9 for what the build changed

Related: `docs/plans/README.md` (rows B9, R3), `docs/HRITWIK_TEAM_NOTES.md` (Ridanshi's 2026-10-11 00:05 note, item 2, lists what the jury screens need), `docs/specs/2026-10-10-textile-mill-design.md` (§7 costing, §8 intelligence), `docs/plans/B9a-seed-and-demo-mill.md` (the one-day demo mill this replaces for demos).

## 1. Goal and decisions

Hritwik wants to see how the backend and every frontend screen behave on a month of data, and the jury needs screens that tell a story (Ridanshi's note: the demo mill looks empty, the month report shows a loss and no invoices, late orders and root causes are empty).

Decisions made with Hritwik on 2026-10-11:
- **Where:** a separate database, `everest_month`. His `everest` is never touched. One command builds it; he runs the backend against it with `DATABASE_URL`.
- **When:** the 30 days ending today (an hour before the build starts), with the mill still in motion "now".
- **What:** the cast in section 5.
- **How:** run the real service functions under a simulated clock, so every figure is one the real rules produced.

Out of scope: any change to application code, migrations, the language-model settings (no provider key is seeded), photos.

## 2. The time machine

The services take "now" from four places, found by reading the code:

| Source | Where | Handled by |
|---|---|---|
| the database clock (`db_now`, `clock_timestamp()`) | run start and end, hand-overs, breakdowns, repairs, QC inspections, dispatch and invoice times | the timestamp mover |
| a database default (`DEFAULT now()`) | every table's `created_at` (the shared `IdMixin`), a lot's `received_at` | the timestamp mover |
| Python's own clock (`datetime.now`) | an order's `confirmed_at` (`orders/service.py`) | the timestamp mover |
| today's date (`today_ist()`) | a supplier bill's bill date and due date (`store/service.py`), the rule that refuses an order with a past deadline, the rule that refuses a future-dated payment | the date swap |

1. **The timestamp mover.** After every simulated step the script finds every `timestamp with time zone` column in the database (asked of `information_schema`, never a typed list) and, for every value that lies inside that step's real-time window, sets it to the simulated moment plus the same offset inside the window. This works only because the simulated history ends before the real clock; the month therefore ends one hour before the build starts.
2. **The date swap.** Inside the script's own process only, `today_ist` is replaced, in every loaded module that imported it, by a function returning the simulated date.
3. **The leak check.** At the end, no timestamp anywhere may be later than the simulated end.

Unverified until built: that every service tolerates having its timestamps moved afterwards (for example the `ended_at >= started_at` check constraints). The first run shows it.

Attendance and wage payment are router functions, not services; they are called directly with `db` and the user, the pattern `modules/llm/data.py` already uses. Their only date rule is "not in the future", which simulated past dates satisfy.

## 3. The simulation

Facts from `scripts/seed_dev.py` and the floor rules:
- Machines: 2 ring frames (20 and 22 kg of yarn per hour), 6 looms (28 m per hour), 2 dyers (45 m per hour).
- Shifts: A 06:00 to 14:00, B 14:00 to 22:00, C 22:00 to 06:00.
- Workers: 7 operators (W-001, W-006 to W-011), 2 inspectors, 1 supervisor, 1 storekeeper, 1 dispatch. Only operators run machines; one operator may tend several machines at once (the costing splits pay by hours run, §7.2).
- Recipes: poplin 0.12 kg of 30s cotton per metre with 5% wastage; twill 0.16 kg of 40s poly-cotton per metre with 4% wastage. So 5,000 m of poplin needs 630 kg.
- A weaving run needs a spinning run of the same order as its input; a hand-over closes a run and opens a new one on the same machine for the next operator.

Capacity per day running all three shifts: spinning 1,008 kg (about 8,000 m of poplin or 6,000 m of twill), weaving 4,032 m, dyeing 2,160 m. **The dyers are the bottleneck**, then the looms. The month holds about 35,000 m, which is about 54% of the dyers' capacity over 30 days.

The script builds a list of timed events for the whole month and plays it in time order through the real services, order by order in deadline order:
1. spin on the first free ring frame (yarn issued from a lot);
2. weave on one to three free looms, a roll off about every 500 m (420 to 600 m, varying);
3. dye the rolls in batches on a free dyer;
4. inspect each roll a few hours after dyeing;
5. load passed rolls on a truck, confirm the dispatch (this creates the invoice), record the buyer's payment later.

Machines run round the clock. At each shift change a running machine is handed to an operator present that shift. Attendance is marked for all 12 workers every day, about 4% absent and a few half days, with at least one operator always present per shift. Randomness comes from a fixed seed: the same month every time. The calendar is relative: the last day is "today".

## 4. The stories and how each is proven

| Story | How it is made | What must be true at the end |
|---|---|---|
| Bad yarn lot (a lot of its own; `L-0009` in the first build) | cotton, issued to two poplin orders (one per buyer), 12 rolls; those rolls fail QC about 85% of the time against about 12% elsewhere | the root-cause screen flags the lot; an operator with a few extra defects is not flagged (Bonferroni); recall reaches both buyers and at least one dispatched truck |
| Order that loses money | one order gets many rework (re-dye) runs | its profit is negative and rework is a large share of its cost |
| Late order | a large order with a tight deadline given late in the month | the delivery-date engine reports it late, with a bottleneck and a fix, on the late-orders screen |
| Low yarn | the last cotton receipt is small while open orders still need cotton | the shortage forecast lists cotton with a supplier and a reorder quantity |
| Broken and idle machines | 2 or 3 breakdowns with repairs; one loom barely used | utilisation shows idle and down hours |
| Money | most orders invoiced and paid; some invoices unpaid, one partly paid (invoices have no due date, so none is "overdue"); one supplier bill overdue; wages paid for the first two weeks | receivables and payables show them; the month report's invoiced total equals the sum of invoices |
| Mill right now | three orders in progress when the month ends | the floor board shows running, idle and down machines; the QC queue has rolls; one truck is mid-loading |

Verdicts are random from the fixed seed: about 75% pass, 15% rework, 10% reject. The numbers (defect rates, order sizes, deadlines) are tuned until the audit passes; the audit is never weakened.

The audit (`audit.py`) calls the real endpoint functions and prints one pass or fail list. It also checks: the month report shows none of the "hours not covered by attendance" warnings; independent SQL straight from the tables equals the endpoint for a few figures (month revenue, one order's yarn cost, cotton stock on hand), to the paisa; the leak check; logging in as `buyer` shows only that buyer's own orders.

Not checkable from the script: how the screens look in a browser. Hritwik looks at them; `docs/demo.md` says which pages to open.

## 5. The cast (what the month contains)

12 confirmed orders (8 finished, dispatched and invoiced; 3 in progress now and 1 waiting for yarn; plus 1 draft and 1 cancelled; the late one among the open ones), 16 yarn lots, 83 rolls, 2 or 3 breakdowns, attendance and wages, supplier bills and payments, buyer invoices and payments.

## 6. Files, commands and safety

New folder `services/api/scripts/month/`:
- `clock.py`: the simulated clock, the timestamp mover, the date swap, the leak check.
- `plan.py`: the scheduler, plain Python with no database; deterministic for a seed.
- `runner.py`: plays the events through the real services.
- `audit.py`: the pass or fail list.

Plus `scripts/build_month.py` (creates the database, migrates, loads the starter data, plays the month, runs the audit), `npm run db:month` (re-running starts from scratch by dropping and recreating only `everest_month`), `npm run dev:month` (backend and web against `everest_month`, same ports as `npm run dev`, so stop that first), two fake buyer emails in the starter data (`seed_dev.py`, as Ridanshi asked), and `docs/demo.md` (written after the first real run, from its real numbers).

Safety:
- The script refuses to run unless the target database is named `everest_month`, and never writes to `everest`.
- It refuses to start if the simulated month would end after the real clock.
- No application code changes and no migrations, so Hritwik's running app is unaffected.

## 7. Tests

- The scheduler without a database, over many seeds: no machine double-booked, weaving after its spinning, QC after dyeing, nothing dispatched before it passes.
- The timestamp mover on the test database: a real service call stamps "now", the mover moves it, nothing else moves, values from before the window stay put.
- A 3-day mini month with 2 orders, end to end into the test database, whose audit must pass.
- The refusals: a database not named `everest_month`; a month that would end in the future.
- Then the full build on `everest_month` and the full audit with the independent SQL checks.

## 8. Build order

1. The clock and mover. 2. The scheduler. 3. Orders through to rolls. 4. QC, rework, dispatch, money and people. 5. The stories and the audit. 6. The entry point, scripts, seed emails and `docs/demo.md`. 7. The real run, a look at the results, and the sync of docs and memory.

## 9. What building it changed

Found while planning and building (details and evidence in the plan's Status lines); they supersede the text above where they differ.

1. **Invoices have no due date**, only supplier bills do (bill date plus 30 days), so there is no "overdue buyer invoice". The money story is: unpaid invoices of different ages, one part-paid, and an overdue supplier bill. For that bill to be overdue the first order's yarn lot arrives 4 days before the month begins (opening stock) and is left unpaid.
2. **A simulated step is instantaneous.** The clock sets every timestamp written in a step to exactly the planned moment. Keeping the few real milliseconds put a hand-over planned for 14:00:00 at 14:00:00.012, a hair outside the outgoing operator's shift, and the month report warned of uncovered hours.
3. **The end is five minutes before the build** (not an hour): the safety gap only has to exceed the seconds the build takes, and a fresher end keeps the open runs' tail short. Attendance is marked for every shift dated up to the end's own date, so the machines running now stay covered; the audit judges finished runs (an open run is costed up to the real clock, so its tail grows with wall-clock time).
4. **Rejected metres are re-made.** An order is complete only when its good metres reach the ordered metres, and there is no "close short" feature, so without a replacement batch every order with a rejected roll stayed "partly dispatched" for ever and the late-orders screen listed seven orders, the oldest "21 days late". Each rejected metre now gets its own yarn lot, spinning, weaving, dyeing and check.
5. **The scheduler books machine intervals, not a "free from" pointer.** A replacement batch planned days after its order was created pushed the pointer far into the future and every later order queued behind it while the machine sat idle; jobs now take the earliest gap that fits.
6. **The month is 39,500 m** (my sum was wrong), about 61% of the dyers' capacity, 83 rolls (not about 150), 16 lots. The bad lot gets whatever number it gets. The loss-making order is small (2,000 m) so its own lot has fewer than five rolls and is never tested by the root-cause screen, and it sells at ₹48 a metre.
7. **The quantities are tuned to the audit, not the other way round:** the bad lot needed 12 rolls at about 85% defective to clear the Bonferroni correction (p = 0.000005 against a threshold near 0.002); the loss order needed a lower price once rejected metres were re-made.
8. **No `npm run dev:month`**: the repo has a Windows teammate, so `docs/demo.md` gives the command for both shells. `ALLOWED` database names are three fixed ones (`everest_month`, `everest_month_test`, `everest_month_e2e`).
