# A2 — Store and Orders Screens

> **Summary:** Track A's second plan, written after the work: the six store and order screens (receive yarn, yarn stock, yarn lot with recall, orders list, new order, order detail), what each one calls, the rules it enforces in the browser, and how it is tested.
> **Last updated:** 2026-10-10 14:31 IST
> **Status:** built and tested on branch `a/web-scaffold`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §6 (rules R1, R3, R14), §8 (delivery date, shortage, recall), §11 (screens). **Contract:** Hritwik's `contracts/types.ts`; the numbers are his example data until plans B2 to B7 land, and the shapes do not change.

## Screens

| Route | File | Roles | What it does | Endpoints |
|---|---|---|---|---|
| `/store/receive` | `pages/store/ReceiveYarn.tsx` | store | Gate form for a delivery. Challan photo optional (uploaded first, path sent with the lot). Success card links to the lot. A duplicate challan shows under the challan field. | `GET /yarn-types`, `/suppliers`, `/orders?state=confirmed`; `POST /uploads`, `POST /lots` |
| `/store/stock` | `pages/store/YarnStock.tsx` | store, owner | Table of on hand / needed / free per yarn type, "Reorder now" flag, KPI row, reorder suggestions (what, from whom, by when, how late). The suggestions card fails on its own without hiding the table. | `GET /stock`, `/insights/shortages` |
| `/store/lots/:code` | `pages/store/LotDetail.tsx` | store, owner | Lot header, KPIs, stock ledger, **Block this lot** (reason required), recall exposure grouped as floor / store / loading / dispatched, buyers to contact. For a usable lot the exposure loads only on request. | `GET /lots/{code}`, `/lots/{code}/recall`; `POST /lots/{code}/block` |
| `/orders` | `pages/orders/OrdersList.tsx` | owner, accountant, supervisor | All orders with stage badge, passed-QC progress, "Yarn ready" / "Short N kg", late badge. Filter pills All / Active / Late / Drafts with counts. "New order" only for owner and accountant. | `GET /orders` |
| `/orders/new` | `pages/orders/NewOrder.tsx` | owner, accountant | Creates a draft; deadline cannot be in the past; opens the new order. | `GET /buyers`, `/fabric-types`; `POST /orders` |
| `/orders/:code` | `pages/orders/OrderDetail.tsx` | owner, accountant, supervisor | Progress bars, **delivery date with the two tested what-ifs and the bottleneck**, yarn check, cost and profit (owner, accountant only; losses in red, caveats shown), confirm / cancel / change deadline in dialogs. | `GET /orders/{code}`, `/eta`, `/yarn-check`, `/costing/orders/{code}`; `POST /confirm`, `/cancel`; `PATCH /orders/{code}` |

## Rules these screens follow

- Every form uses `useSubmitLock` + `SubmitButton` (a double tap sends one request) and `applyServerErrors` (a server field error appears under that field; anything else appears as a message).
- Every data screen uses `QueryBoundary`, so it shows a skeleton, then data or a Retry state, never a blank page.
- Query keys start with the area name (`['stock']`, `['lots', code]`, `['orders', code, 'eta']`), so live events refetch them.
- The browser mirrors validation for quick feedback; the server stays the authority.
- Cost and profit are never requested for roles that may not see them (the test checks the request is not made).

## Tests (`npm --prefix apps/web test`)

`ReceiveYarn` 9, `YarnStock` 8, `LotDetail` 10, `OrdersList` 9, `NewOrder` 8, `OrderDetail` 12. They mock the API client with `src/test/utils.tsx` (`mockApi`, `renderPage`) and cover happy path, validation, server errors, double submit, role differences, empty and error states.

## Not done in A2

- Drafted recall messages to buyers (needs the language-model module, plan A8): the page says so.
- Real numbers: until B2 and B3 land the screens show Hritwik's example data, which is not consistent across endpoints (he warned about this in the team notes).

## Done when

- [x] All six routes are real screens, not placeholders.
- [x] Tests, type-check, lint and build pass.
- [ ] Checked on a real phone (needs Caddy and a phone: A1 Task 7 Step 4).
