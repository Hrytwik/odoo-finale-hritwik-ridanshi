# Demo: a simulated month at Everest Mills

> **Summary:** How to build and open `everest_month`, a separate database holding 30 days of mill history built by the real service functions, with the logins, the real numbers of the current build, and the page to open for each of the seven stories (a bad yarn lot, a loss-making order, a late order, low yarn, a broken and an idle machine, overdue and part-paid money, a mill still running now).
> **Last updated:** 2026-10-11 07:23 IST (numbers re-checked on the build made at 07:21 IST on 11 Oct 2026 after the merge, 22 of 22; the truck-loading and machine-down stories are now relative to the end of the month; nobody has yet looked at the screens in a browser)

## Build it

From the repository root:

```
npm run db:month
```

It drops and recreates only the database `everest_month` (it refuses any other name, so `everest` is never touched), migrates it, loads the starter data, plays 30 days of mill life through the real service functions under a simulated clock, and prints a pass or fail list of 22 checks. It takes about 10 seconds. The month always **ends five minutes before you run it**, so rebuild right before a demo and the mill on screen is as fresh as the build. The plan is seeded: a rebuild gives the same orders, lots, rolls and money, except for whatever is mid-way at the moment of building.

## Open the app on it

macOS or Linux (stop your normal `npm run dev` first: it uses the same ports):

```
DATABASE_URL=postgresql+psycopg://localhost:5432/everest_month npm run dev
```

Windows PowerShell:

```
$env:DATABASE_URL = "postgresql+psycopg://localhost:5432/everest_month"; npm run dev
```

Your normal `npm run dev` (without the variable) keeps showing `everest`.

Logins, all with the password `everest123`: `owner`, `accountant`, `supervisor`, `qc`, `store`, `dispatch`, and `buyer` (Sharma Fabrics). The two buyers have emails for sign-up: `accounts@sharmafabrics.example` and `orders@kavyagarments.example`.

## The month in numbers (this build)

14 orders (12 confirmed, 1 draft, 1 cancelled), 16 yarn lots, 83 rolls, 421 machine runs, 83 quality inspections (56 rolls passed, 11 rejected and re-made), 10 invoices, 372 attendance records. The mill runs from 11 Sep to 11 Oct 2026; the first yarn arrived on 7 Sep.

- **Month-end, September:** invoiced ₹20,62,000; yarn issued ₹9,74,940; wages earned ₹1,85,000; idle labour ₹13,607; support staff ₹74,600; machine running cost ₹1,29,277; **profit ₹7,72,783**.
- **Month-end, October (the first 11 days):** invoiced ₹8,16,000; profit ₹99,611; received from buyers ₹14,80,500; receivables outstanding ₹13,97,500.
- **Wages, September:** earned ₹1,85,000, paid ₹1,28,450, owed ₹56,550.

Every one of these was recalculated independently from the tables in SQL and matches to the paisa (the build's audit does it, plus a second pass for wages, one order's machine cost, verdict counts and money outstanding).

## The seven stories and where to look

| Story | Open | What you see |
|---|---|---|
| **A bad yarn lot** | Owner, **Insights** (`/owner/insights`), then **Yarn lot** `L-0009` (`/store/lots/L-0009`) | Defect causes flags lot **L-0009**: 92% of its rolls defective against 20% elsewhere (p = 0.000005). Its recall reaches both buyers (Sharma and Kavya) and 6 dispatched rolls. The unlucky operator is not flagged. |
| **An order that loses money** | **Orders** `ORD-0007` (`/orders/ORD-0007`) | Kavya's red poplin, ₹48 a metre: revenue ₹96,000, cost ₹1,23,576 (rework ₹5,770, 1,000 m rejected and re-made), **profit −₹27,576**. |
| **A late order** | Insights (late orders), order `ORD-0012` | Sharma's 6,000 m burgundy poplin, deadline on the build day, **5 days late**, bottleneck **dyeing**, with what-ifs. It is the only late order. |
| **Low yarn** | Insights (reorder suggestions), **Yarn stock** (`/store/stock`) | Cotton is **56 kg short** after open orders (reorder level 300 kg): order 400 kg. `ORD-0013` is waiting for yarn that has not arrived. |
| **Broken and idle machines** | **Floor board** (`/floor`), Month-end machines table | Right now 4 machines running, 5 idle, 1 down (**SPIN-02**, drive belt slipping). **LOOM-06** never ran in the month and was down for 40 hours (belt snapped). |
| **Money** | **Receivables**, **Payables** (`/money/*`), **Wages** (`/people/wages`) | Receivables: 10 invoices, 4 still unpaid, 1 half-paid. Payables: lot **L-0001**'s bill (₹1,42,450) was due on 7 Oct and is **overdue**. Wages: September part-paid. |
| **A mill still running now** | Floor board, **Quality check** (`/qc`), **Dispatch** (`/dispatch`), the buyer portal | 3 orders in progress (one weaving, two at quality check) and `ORD-0013` waiting for yarn; 4 rolls waiting for a quality check; one truck is loaded and not yet signed out; the buyer sees their own orders only, with delivery dates. |

## What to know before showing it

- **Open runs are costed up to now.** Orders with a machine still running show their cost as *provisional*, and the October month report lists "is still open, so its cost is provisional" warnings for the 3 or 4 runs open at the end. That is true and expected; it is not missing data.
- **Attendance for the shifts still to come today is already marked**, so the machines running now are covered. Left for many hours after the build, an open run is eventually costed past the next shift change, so rebuild before a long demo.
- **Known gap: build between about 07:50 and 08:40 IST and the QC queue may be empty** (the audit then fails its one check "the QC queue has rolls waiting"; the app is fine). The four rolls waiting for inspection come from a dyeing batch that finishes at about 08:30 on the final day, so a month that ends before that has none waiting. Every other story (the truck still loading, the machine down now, the late order, the bad lot, the loss order) holds at every hour of the day: they are placed relative to the end of the month, and `test_month_plan.py` checks that across the whole day. A sweep of full builds at 30 different end times passed 22 of 22 everywhere except that window. If you build in it, rebuild after 08:45.
- **Rejected metres are re-made.** An order is complete only when its good metres reach the ordered metres, so a rejected roll leads to a replacement batch (its own yarn lot, spinning, weaving, dyeing and check). That is why there are 16 lots for 12 orders.
- **The two buyers' payments are real receipts against real invoices**, made by the same service the Receivables screen uses.
- Every figure is made by the real rules. Nothing was typed in. The 22 checks and the independent SQL recalculations are in `services/api/scripts/month/audit.py`.
- **Not done:** looking at these pages in a real browser. The numbers were read through the real API as every role (owner, accountant, supervisor, qc, store, dispatch, buyer); the buyer is correctly refused the floor board and the money screens.
