`# A5 — Dispatch, Invoices and Money
`
`> **Summary:** Track A's fifth plan, written after the work: the dispatch list and the scan-to-load screen (built earlier), and now the printable invoice, receivables and payables with payment recording.
`> **Last updated:** 2026-10-10 17:11 IST
`> **Status:** built and tested on branch `a/web-textile`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).
`
`**Spec:** §4.3 (dispatch, invoices, payments), §6 R11 and R12 (a roll leaves once, only to its buyer; payments cannot exceed the balance), §11 (screens). **Contract:** Hritwik's `contracts/types.ts`; example data until plan B5.
`
`## Screens
`
`| Route | File | Roles | What it does | Endpoints |
`|---|---|---|---|---|
`| `/dispatch` | `pages/dispatch/DispatchList.tsx` | dispatch, owner | Trucks being loaded first, then sent ones, with buyer, vehicle, rolls, metres and invoice link; **New dispatch**. | `GET /dispatches`, `/buyers`; `POST /dispatches` |
`| `/dispatch/:code` | `pages/dispatch/DispatchDetail.tsx` | dispatch, owner | Scan or type a roll code to load it. A roll that is not ready, or belongs to another buyer, is refused loudly with the server's reason. **Send** creates the invoice. | `GET /dispatches/{code}`; `POST …/load`, `…/send` |
`| `/invoices/:no` | `pages/money/InvoicePage.tsx` | dispatch, accountant, owner, buyer | The invoice laid out like paper: buyer, dispatch, vehicle, lines with rolls, metres, rate and amount, total, received and balance due. **Print** hides the app chrome. | `GET /invoices/{invoice_no}` |
`| `/money/receivables` | `pages/money/Receivables.tsx` | accountant, owner | Invoiced, received and still-to-receive totals; each invoice marked Paid, Part paid or Unpaid; **Record payment**. | `GET /money/receivables`; `POST /payments/buyer` |
`| `/money/payables` | `pages/money/Payables.tsx` | accountant, owner | Still-to-pay and overdue totals; bills sorted overdue first then by due date; each links to its yarn lot; **Record payment**. | `GET /money/payables`; `POST /payments/supplier` |
`
`## Rules these screens follow
`
`- **A payment cannot be more than the balance, or zero, or in the future.** The dialog says so under the field before anything is sent; the server's own refusal is still shown if it differs. The amount starts as the full balance, the usual case.
`- **Double taps cannot pay twice** (`useSubmitLock`). A failed payment keeps the dialog open with the reason.
`- Money lists refetch on live `payment.changed` and `dispatch.changed` events (query keys start with `money`).
`- A buyer opening an invoice sees the dispatch code as text, not a link into staff screens.
`
`## New shared pieces
`
``pages/money/PaymentDialog.tsx` (one dialog for both payment kinds), `components/common/StageBar.tsx` (orders list), print styles in `styles/textile.css`.
