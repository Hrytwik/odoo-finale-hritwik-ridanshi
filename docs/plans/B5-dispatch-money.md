# B5 — Dispatch and money (real logic) Implementation Plan

> **Summary:** Replaces the example-data stubs for dispatch, invoices and money with real, tested logic: loading a truck with passed rolls (R11), confirming it and creating the invoice (R12), reading an invoice, recording buyer and supplier payments within their limits and the real receivables and payables lists (R13). It also adds a safety net so a text value longer than its column or a number larger than its column returns a clean 422 instead of a server error. API shapes do not change.
> **Last updated:** 2026-10-10 19:47 IST (Tasks 1-2 done)

**Goal:** every endpoint under `/api/dispatches`, `/api/invoices`, `/api/money/*` and `/api/payments/buyer|supplier` runs on real data with the rules R11, R12, R13 and R15 from spec §6, and `contracts/openapi.json` stays **byte-identical**.

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §4.3, §5, §6 (R11 to R13, R15), §11. **Depends on:** B1 to B4 (tables, auth, error format, locks, `db_now`, `v_roll_status`, QC passing a roll to `in_store`). Completes the chain from yarn to cash and gives B6 real invoices and payments.

**How this plan is executed:** inline, one task at a time (atomic-workflow), test first, the full suite twice at each boundary, the important tests mutation-checked, race tests proven by removing the lock. Design approved section by section on 2026-10-10 (scope, loading rules, confirm and invoice, payments and lists, task order).

## Status

Task 1 done and verified (2026-10-10 19:40 IST): migration `422bff951354` (`dispatch_code_seq`, `invoice_code_seq`, round trip checked and **applied to Hritwik's dev database `everest`** in the same step), `next_code` kinds `dispatch` and `invoice`, `core/errors.map_data_error` used by `commit`, `flush` and a new app-wide `DataError` handler (a data error raised anywhere, for example by an automatic flush during a query, is also a clean 422); 11 new tests (60-character challan accepted, 61 and 200 give `VALUE_TOO_LONG` with the limit in the message, an order colour of 61 characters, a lot of 1,000,000 kg at 100,000,000 gives `NUMBER_TOO_LARGE`, nothing left behind and no event on committed data, an ordinary value still works, the handler mapped for all three SQLSTATEs). Mutation-proven: too-long not recognised, `commit` not catching, handler missing, limit not read from the message, numbers reported as text. One stale B2 test fixed: `test_unknown_kind_is_refused` used `"invoice"` as its example of an unknown kind. **Plan correction:** an order's price times quantity only overflows when the invoice line is made, so that test ("an order of 1,000,000 m at 100,000,000") moves to Task 3 (confirming must answer 422 `NUMBER_TOO_LARGE` and leave the dispatch `loading`). Full suite 928 passed, twice; contract unchanged. 
Task 2 done and verified (2026-10-10 19:47 IST): `dispatch/service.py` (`create_dispatch`, `get_dispatch_or_404`, `scan_roll`, `unload_roll`, `dispatch_out`, `list_dispatches`), real `GET/POST /dispatches`, `GET /dispatches/{code}`, `POST /dispatches/{code}/items`, `DELETE /dispatches/{code}/items/{roll_code}`; `get_roll_or_404` moved to `rolls/service.py` (QC uses it too); 27 new tests (create and its checks; scanning with the summary numbers; the earlier-truck and over-shipping summary 1,000 / 2,500 / 0 / over-shipped with the warning, still loading; two orders of one buyer on one truck; every refusal with its code and field and nothing left behind: wrong buyer, repeated scan on the same truck, a roll on another truck, rejected, awaiting rework, awaiting QC, woven, unknown roll, unknown dispatch, a confirmed dispatch; taking a roll off and loading it again; list, filter and roles; two clerks and one roll 5x on committed data and a held-roll-lock test). Mutation-proven: no buyer check, no already-on-a-dispatch check (the unique index then answers `ROLL_NOT_PASSED`/the race test fails), no in-store check, no roll lock, a confirmed dispatch not locked, over-shipping blocking, `remaining_m` going negative, and rolls on another truck still loading counted as previously dispatched (this one first survived, so its test was added). The `Dispatch` model has no `buyer` relationship, so `dispatch_out` looks the buyer up by id. The example test for `GET /dispatches/DSP-0007` was removed (the real tests cover it). Full suite 953 passed, twice; contract unchanged. Next: Task 3.

## Global Constraints

- Quantities and money are `Decimal`; floats appear only at the JSON edge. Money is rounded half up to 2 places. Numeric request fields keep `Annotated[float, Field(...), NoBool]`.
- Every write is one transaction through `commit(db)` (or `flush(db)` for a mid-transaction flush); events (`dispatch.changed`, `roll.changed`, `payment.changed`, the names the web app already listens for) are published **only after a successful commit**.
- Timestamps written here (`dispatched_at`, the invoice's `issued_at`) come from `floor.service.db_now(db)` read after the locks.
- Lock order, always: order row, machine row, dispatch row, roll rows (ascending id), invoice or bill row. A write takes only the ones it needs.
- Roles exactly as the existing routers: dispatch endpoints dispatch and owner; `GET /invoices/{no}` dispatch, accountant, owner, buyer (own); money endpoints accountant and owner.
- Error codes are stable strings; `field` matches the request field name (`buyer_id`, `vehicle_no`, `roll_code`, `invoice_no`, `bill_id`, `amount`, `received_on`, `paid_on`).
- Commit messages: plain imperative subject, no trailers.

## Decisions made in this plan (not spelled out in the spec)

1. **Safety net (Task 1):** `commit(db)` and `flush(db)` also catch the database's "value too long" (SQLSTATE 22001) and "number out of range" (22003) errors, roll back, and answer 422: `VALUE_TOO_LONG` ("A text value is too long (at most N characters)", N read from the database message) or `NUMBER_TOO_LARGE`; any other data error is `INVALID_VALUE`. The field is not known from the database message, so `field` is null; where the schema can name it the explicit checks below give a field. Reproduced before this plan: a 61-character challan number crashes with an unhandled error today, and all money columns are `numeric(12,2)` (largest 9,999,999,999.99), so a lot of 1,000,000 kg at 100,000,000 a kg overflows its bill.
2. **Explicit field checks:** `vehicle_no` at most 30 characters and `driver_name` at most 120, checked in the service with a 422 on the field (no contract change); payment `reference` at most 120 the same way.
3. **Codes:** `next_code(db, "dispatch")` gives `DSP-0007` and `"invoice"` gives `INV-0007` from two new sequences.
4. **Loading rules (R11), in order:** the dispatch exists and is `loading` (else `DISPATCH_LOCKED`, 409); the roll exists (404); the roll's order belongs to the dispatch's buyer (`WRONG_BUYER`, 409); the roll is not already on a dispatch, this one or another (`ALREADY_DISPATCHED`, 409, the message says which; a repeated scan is refused, not ignored); the roll is `in_store` (`ROLL_NOT_PASSED`, 409, the current status in the message). The dispatch row is locked, then the roll row; the unique index on a roll's dispatch item stays as the last defence.
5. **Per-order summary:** `ordered_m`; `previously_dispatched_m` = metres of that order on OTHER dispatches that are `dispatched`; `loaded_m` = this dispatch; `remaining_m` = ordered - previous - loaded, never below 0; `over_shipped` = previous + loaded > ordered. Over-shipping is a **warning** (text in `warnings`), never a refusal.
6. **Taking a roll off** is allowed only while `loading` (else `DISPATCH_LOCKED`); the roll must be on this dispatch (404 otherwise); it returns to `in_store` by itself. An abandoned empty dispatch simply stays `loading` (the spec has no cancel).
7. **Confirm (R12):** lock the dispatch; it must be `loading` (`DISPATCH_LOCKED` also for a second confirm) and hold at least one roll (`EMPTY_DISPATCH`, 409); then `dispatched`, `dispatched_at = db_now`, and the invoice (`INV-` number, `issued_at` equal to `dispatched_at`) with **one line per order**: metres of that order's rolls on the truck, the order's price per metre as the rate, amount = metres x rate rounded half up to the paisa; the invoice total is the **sum of the rounded line amounts**. Shipped metres are billed even when over-shipped. Nothing on a confirmed dispatch or its invoice can change (no edit endpoint; scan and unload give `DISPATCH_LOCKED`).
8. **Invoice read:** `paid_amount` is the sum of the real buyer payments and `balance` is total minus paid (never stored). A buyer sees only their own invoices; another buyer's invoice and a missing invoice give the identical 404 (R15), like the passport.
9. **Payments (R13):** lock the invoice (or bill) row; the amount is rounded half up to the paisa and an amount that rounds to zero is refused; paid so far plus the amount must not exceed the total (`OVERPAYMENT`, 409 on `amount`, the message says how much is still owed; the same code and field as Ridanshi's wage payments); `received_on` and `paid_on` may not be in the future (`FUTURE_DATE`, 422) nor before the invoice date or the bill date (422 on the field). The response is the updated receivable or payable row; `payment.changed` is published.
10. **Lists:** receivables = every invoice (fully paid ones too), newest first; payables = every supplier bill with its lot code, soonest due first; `overdue` = due date before today (India date) and a balance left. `paid` and `balance` are always summed from the payment tables.
11. **Double-click on a payment:** two identical partial payments both succeed (each is valid; the limit stops over-paying, not repeating). The guard belongs on the button (Ridanshi's side); no time-window duplicate check on the backend, because it would block two genuine equal instalments.

## Hand-worked numbers (the tests assert these)

- **Invoice:** an order's rolls of 1,000 + 800 = 1,800 m at 120 give **216,000.00**; a second order on the same truck with 333.333 m at 120.50 gives 40,166.6265, rounded **40,166.63**; the truck's invoice total is **256,166.63** as two lines.
- **Payments:** on that invoice, paying 100,000.00 leaves **156,166.63**; paying 156,166.64 is `OVERPAYMENT`; paying 156,166.63 gives balance **0.00**, and one more paisa is refused.
- **Supplier bill:** 800 kg at 250 = **200,000.00**; paying 50,000 leaves **150,000.00**; with a past due date it is `overdue`, and not once fully paid.
- **Summary:** an order of 3,000 m with 1,000 m already on a confirmed truck and 2,500 m now loading: previous 1,000, loaded 2,500, remaining **0**, `over_shipped` true (500 m over).
- **Chain:** the 1,000 m order of the B4 chain (rolls of 600 + 400 at 120) gives an invoice of **120,000.00**; paying 70,000 leaves **50,000.00**.

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **Text or numbers too long or too large:** a 61-character challan number, order colour and vehicle number, a 121-character payment reference, a bill amount that overflows its column, each a clean 422 on every endpoint. Task 1 (and the field checks in Tasks 2 and 4).
2. **A buyer opening another buyer's invoice versus a missing invoice** give identical 404 bodies. Task 3.
3. **Over-shipping** warns but does not block, and the invoice bills what was shipped. Tasks 2 and 3.
4. **A rejected roll, a roll awaiting rework, a roll already on a truck, another buyer's roll, and the same roll scanned twice on one truck**, each refused with the right code. Task 2.
5. **Payment edges:** one paisa over, zero, rounds to zero, negative, NaN, `true`, a future date, a date before the invoice. Task 4.
6. **Rounding:** the invoice total equals the sum of its rounded lines. Task 3.

---

## File Structure

```
services/api/
  alembic/versions/<id>_dispatch_and_invoice_codes.py     dispatch_code_seq + invoice_code_seq
  app/core/codes.py               next_code kinds "dispatch" (DSP) and "invoice" (INV)
  app/core/errors.py              commit() and flush() map DataError (too long, out of range) to 422
  app/modules/dispatch/service.py create/list/read/scan/unload/confirm, invoice_out
  app/modules/dispatch/router.py  real handlers
  app/modules/money/service.py    receivables, payables, buyer and supplier payments
  app/modules/money/router.py     real handlers
  tests/test_value_limits.py  test_dispatch_load.py  test_dispatch_confirm.py  test_money.py  test_dispatch_chain.py
```

---

### Task 1: The safety net and the two code sequences

**Interfaces — Produces:** `next_code(db, "dispatch") -> "DSP-0007"`, `next_code(db, "invoice") -> "INV-0007"`; `commit(db)` / `flush(db)` raise `AppError("VALUE_TOO_LONG" | "NUMBER_TOO_LARGE" | "INVALID_VALUE", status=422)` for a database data error, after rolling back.

**Migration (hand-written, revision "dispatch and invoice codes", down_revision = `43caade7e8a6`):** `CREATE SEQUENCE dispatch_code_seq`, `CREATE SEQUENCE invoice_code_seq` (the statements were run against the real schema before this plan was written). Downgrade drops both.

**Code:** in `core/errors.py`, a `map_data_error(exc: DataError) -> AppError` (SQLSTATE 22001 reads the limit from `character varying(N)` in the database message; 22003 is `NUMBER_TOO_LARGE`; anything else `INVALID_VALUE`), caught next to `IntegrityError` in `commit` and `flush`.

**Tests (write first, `tests/test_value_limits.py`, plus cases in `test_codes.py`):** `next_code` for both kinds matches `^DSP-\d{4,}$` / `^INV-\d{4,}$` and two calls differ; a 60-character challan number is accepted, 61 and 200 are a 422 `VALUE_TOO_LONG` whose message contains 60, and nothing is stored; a 61-character order colour is a 422; a lot of 1,000,000 kg at 100,000,000 a kg is a 422 `NUMBER_TOO_LARGE` and leaves no lot, movement or bill; the events are not published; an ordinary value still works; the migration round-trips. (A real constraint failure rolls back the whole test transaction, so each such case is the last step of its test.)

### Task 2: Load a dispatch (R11)

**Interfaces — Consumes:** `next_code`, `floor.service.db_now`, `rolls.service.roll_out(s)`, `rolls.service.roll_status`. **Produces** (`dispatch/service.py`): `create_dispatch(db, body: DispatchIn) -> Dispatch`; `get_dispatch_or_404(db, code, for_update=False)`; `scan_roll(db, code, body: ScanIn) -> Dispatch`; `unload_roll(db, code, roll_code) -> Dispatch`; `dispatch_out(db, dispatch) -> DispatchOut`; `list_dispatches(db, state=None) -> list[DispatchOut]`.

**Rules:** decisions 2 to 6. The order summary query (run against the real schema before this plan was written):

```sql
SELECT o.id AS order_id, o.code AS order_code, o.qty_metres AS ordered_m,
  COALESCE((SELECT SUM(r2.metres) FROM rolls r2
              JOIN dispatch_items di2 ON di2.roll_id = r2.id JOIN dispatches d2 ON d2.id = di2.dispatch_id
            WHERE r2.order_id = o.id AND d2.state = 'dispatched' AND d2.id <> :did), 0) AS previously_dispatched_m,
  SUM(r.metres) AS loaded_m
FROM dispatch_items di JOIN rolls r ON r.id = di.roll_id JOIN orders o ON o.id = r.order_id
WHERE di.dispatch_id = :did GROUP BY o.id ORDER BY o.code
```

`GET /dispatches?state=` newest first, unknown state 422. Events `dispatch.changed` (dispatch id) and `roll.changed` (roll id) after commit.

**Tests (write first, `tests/test_dispatch_load.py`):** create (buyer 404, vehicle and driver length checks, code format, roles); scan: happy path with rolls `loading` and the order summary numbers above; **every refusal with its code and field** leaving nothing behind: `WRONG_BUYER`, a repeated scan on the same truck, a roll on another truck, a rejected roll, awaiting rework, awaiting QC, woven, unknown roll, a locked (confirmed) dispatch; a truck with rolls of two of the buyer's orders; over-shipping warns and still loads; take a roll off (not on this truck 404, locked dispatch) and the roll is `in_store` again; list and filters; events after commit only; roles (dispatch, owner; others 403); **two clerks, one roll, two trucks at once** (committed data, 5 repeats) and a held-roll-lock version.

### Task 3: Confirm and the invoice (R12)

**Produces** (`dispatch/service.py`): `confirm_dispatch(db, code) -> Dispatch`; `invoice_out(db, user, invoice_no) -> InvoiceOut`.

**Rules:** decisions 7 and 8. One `InvoiceLine` per order: `metres` the exact sum, `rate` the order's price, `amount = q_money(metres x rate)`; `total_amount` the sum of the line amounts. `InvoiceOut.lines` carry fabric name, colour and the roll codes of that order on the truck; `paid_amount` is summed from `buyer_payments`. After commit: `dispatch.changed` and `roll.changed` for every roll.

**Tests (write first, `tests/test_dispatch_confirm.py`):** an invoice line too large for its column (1,000,000 m at 100,000,000 a metre) is a 422 `NUMBER_TOO_LARGE`, the dispatch stays `loading` and no invoice exists; the invoice numbers above (two orders, two lines, total 256,166.63) and the rounding invariant (total equals the sum of the line amounts, also for awkward values); the dispatch becomes `dispatched` with `invoice_no` and the rolls `dispatched`; the order's dispatched metres and stage (`partly_dispatched`, `dispatched`); the roll passport shows the dispatch and invoice number; `EMPTY_DISPATCH`; a second confirm and any scan or unload after it are `DISPATCH_LOCKED` and create no second invoice; over-shipped metres are billed; `GET /invoices/{no}` for each allowed role, `paid_amount` 0 and balance equal to total; **Review Focus 2**: a buyer's own invoice is readable, another buyer's and a missing one give byte-identical 404s; dispatch, accountant and owner read any invoice, others 403; events; roles; **two confirms at once** (5 repeats, exactly one invoice), a held-dispatch-lock version, and a scan that waits for a confirm and is then refused.

### Task 4: Payments and the real lists (R13)

**Produces** (`money/service.py`): `receivables(db) -> list[ReceivableRow]`; `payables(db) -> list[PayableRow]`; `record_buyer_payment(db, body) -> ReceivableRow`; `record_supplier_payment(db, body) -> PayableRow`. The list queries (run against the real schema before this plan was written):

```sql
SELECT i.id, i.invoice_no, i.buyer_id, i.issued_at, i.total_amount,
       COALESCE((SELECT SUM(p.amount) FROM buyer_payments p WHERE p.invoice_id = i.id), 0) AS paid
FROM invoices i ORDER BY i.issued_at DESC, i.id DESC;

SELECT b.id, b.bill_no, b.supplier_id, l.lot_code, b.bill_date, b.due_date, b.amount,
       COALESCE((SELECT SUM(p.amount) FROM supplier_payments p WHERE p.bill_id = b.id), 0) AS paid
FROM supplier_bills b JOIN yarn_lots l ON l.id = b.yarn_lot_id ORDER BY b.due_date, b.id;
```

**Rules:** decisions 9 and 10 (the invoice or bill row is locked before the limit check; `payment.changed` after commit).

**Tests (write first, `tests/test_money.py`):** the payment numbers above for invoices and for supplier bills (100,000.00, 156,166.63 left, one paisa over refused, exact balance to 0.00, one more paisa refused); **Review Focus 5**: zero, rounds to zero (0.004), negative, NaN, `true`, 1e9, a future date, a date before the invoice or bill, a 121-character reference, an unknown invoice or bill (404); `OVERPAYMENT` message names the amount still owed; lists: receivables include paid invoices and are newest first, payables soonest due first with the lot code, `overdue` true only when past due with a balance, fully paid not overdue, the numbers match the invoice's `paid_amount` and `balance`; the supplier bill from receiving a lot (B2) appears in payables; events; roles (accountant, owner; others 403); **two payments at once that together exceed the balance** (5 repeats, one `OVERPAYMENT`) for an invoice and for a bill, plus a held-lock version of each.

### Task 5: Boundary checks, the chain through dispatch and payment, live check, docs

- Old example-data tests for the replaced endpoints (`tests/test_contract_trade.py`, anything importing the dispatch or money examples for these endpoints) are replaced by the real ones above.
- **Contract stability:** `npm run contracts` leaves `contracts/` unchanged.
- **`tests/test_dispatch_chain.py`:** extends the B4 chain: after both rolls are in store, a dispatch is created for the order's buyer, a rejected-or-unpassed roll is refused, both rolls are scanned, the dispatch is confirmed (invoice 120,000.00), the buyer reads the invoice, 70,000 is paid (balance 50,000.00), an overpayment is refused, the order is `dispatched`, the passport shows the dispatch and invoice, the receivables list agrees, and the supplier bill for the lot shows in payables.
- **Live check** on a throwaway database and a real server through the web dev server, with the demo mill taken through QC, dispatch, invoice and payment, plus the refusals and the buyer's 404.
- Full suite twice; update the spec (R11 to R13 notes, the safety net), `docs/plans/README.md`; dated note to Ridanshi (dispatch, invoices and money are real; the new codes; **the payment button must be disabled while a payment is being sent**; `VALUE_TOO_LONG` and `NUMBER_TOO_LARGE`; `npm run db:migrate`); apply the migration to Hritwik's dev database in the same step; memory; commit.

## Done when (not yet met)

- Suite green twice; `contracts/` byte-identical; the concurrency tests pass five repeated runs; every mutation of a lock, a status check, the invoice maths or a payment limit makes a test fail.
- A passed roll can be loaded, confirmed into an invoice, and paid for on a real server, with receivables, payables, the order stage and the passport all agreeing.
- `docs/plans/README.md` marks B5 done.
