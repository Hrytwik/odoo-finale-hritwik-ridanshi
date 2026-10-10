# A6 — People: attendance, wages and wage payments

> **Summary:** Track A's sixth plan, written after the work: the first backend module of Track A (`modules/people`) with its screens. It is the only module that already reads and writes the real database for attendance and wages.
> **Last updated:** 2026-10-10 17:30 IST
> **Status:** built and tested on branch `a/web-textile`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).

**Spec:** §4.1 (`attendance`, `wage_payments`), §6 R13 (payment limit) and R16 (attendance), §7.2 (a present shift pays the daily wage, a half day half, an absence nothing), §11 (screens). The tables and models are Hritwik's (plan B1); this plan adds the module on top of them, with no new migration.

## API (`services/api/app/modules/people`)

| Endpoint | Roles | What it does |
|---|---|---|
| `GET /attendance?date=&shift_id=` | supervisor, accountant, owner | One shift on one day: every worker on the payroll with the status already marked, or none yet. A worker who left but has a mark that day still shows. |
| `POST /attendance` | supervisor, owner | Marks the whole sheet in one go. Marking again for the same worker and shift corrects the earlier mark. Refuses a future date (`FUTURE_DATE`), an unknown shift or worker (404), a repeated worker (422). Records who marked it. Sends a live `attendance.changed` event. |
| `GET /wages?month=YYYY-MM` | accountant, owner | For each worker: present, half days, absent, earned, paid, owed, and totals. |
| `POST /payments/wages` | accountant, owner | Records a payment for a period. It cannot exceed what is owed for that period, which is earned minus the payments whose whole period lies inside it (`OVERPAYMENT`). A future date is refused. Sends a live `payment.changed` event. |

**How wages are worked out.** Per attendance record: the daily wage times 1 (present) or 0.5 (half day), summed over the period, to the paisa. A worker present in two shifts on one day is paid for both, as the spec's per-record rule says. Payments count against a period when their whole period lies inside it, so a payment for the first half of a month reduces what is owed for the month.

**Tests:** `tests/test_people.py`, 45 tests (marking, correction, roles, month boundaries, part payments, overpayment, paisa exactness). The whole backend suite passes (258).

**Touches Hritwik's files** (to tell him in the team notes): two lines in `app/main.py` to mount the router, and `contracts/openapi.json` plus `contracts/types.ts` regenerated, additions only.

## Screens

| Route | File | Roles | What it does |
|---|---|---|---|
| `/people/attendance` | `pages/people/Attendance.tsx` | supervisor, owner | Pick the day and shift. Everyone starts as present, the usual day; change the ones who were not (present, half day, absent) or press Mark everyone present. A saved sheet shows Saved, and Save stays off until something changes. |
| `/people/wages` | `pages/people/Wages.tsx` | accountant, owner | Month picker; earned, paid and still-owed totals; per-worker days and money; **Record payment** for the month, starting from what is owed. |
| `/people/workers` | `pages/admin/screens.tsx` | accountant, supervisor, owner | The payroll (built in A7); only the owner can add or edit. |

## Checked against the real server

Marking attendance for five workers, reading the wages (₹2,800 earned from three full days, one half day, one absence), and paying wages: an overpayment, a second overpayment after a part payment, and a future date were all refused with the right codes, and a valid payment was accepted. The test rows were removed afterwards.
