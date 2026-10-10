# A7 — Owner Dashboard, Insights and Master Data

> **Summary:** Track A's seventh plan, written after the work: the owner's month-end dashboard, the insights page (late orders, yarn to reorder, defect causes), and the screens to maintain master data. The master data screens talk to the real database; the owner screens read example data until plans B6 and B7.
> **Last updated:** 2026-10-10 17:20 IST
> **Status:** built and tested on branch `a/web-textile`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).

**Spec:** §4.1 (master data), §7 (costing, month report), §8 (insights), §11 (screens). **Contract:** Hritwik's `contracts/types.ts`.

## Screens

| Route | File | Roles | What it does | Endpoints |
|---|---|---|---|---|
| `/owner` | `pages/owner/OwnerDashboard.tsx` | owner | Month picker. Net profit, cash on hand, machine use and idle labour; a chart of revenue and profit per order; where the money went (invoiced, yarn, wages, machine cost, write-offs, ending in net profit); cash in and out and what is still owed each way; per-machine hours and lost capacity; data warnings shown first. | `GET /reports/month?month=` |
| `/owner/insights` | `pages/owner/Insights.tsx` | owner | Late orders with each stage's finish date, the bottleneck, and what-ifs; yarn about to run short with the supplier, order-by date and suggested quantity; defect causes with rates against the rest of the mill and whether the difference is likely real. | `GET /insights/late-orders`, `/insights/shortages`, `/insights/root-causes` |
| `/admin/suppliers`, `/buyers`, `/yarn-types`, `/machines`, `/shifts`, `/users` | `pages/admin/screens.tsx` | owner | A list with Add and Edit for each kind of master data. The server's refusals appear under the field they are about. | `GET/POST/PATCH` on each resource |
| `/admin/fabric-types` | `pages/admin/FabricTypes.tsx` | owner | Fabric with its width, wastage and a yarn recipe (one or more yarns, each once, with kg per metre). | `GET/POST/PATCH /fabric-types`, `GET /yarn-types` |
| `/people/workers` | `pages/admin/screens.tsx` | accountant, supervisor, owner | The payroll. Only the owner sees Add and Edit. | `GET/POST/PATCH /workers` |

## Rules these screens follow

- **A machine keeps its stage for life, a shift its name, a user its username and role:** those fields appear only when adding.
- **Editing a user changes only the password and the linked worker.** A password left empty is not sent, so it stays as it was.
- **A fabric recipe needs every line complete and no yarn twice**, checked before anything is sent.
- **A loss shows in red** on the dashboard; the chart draws it below the zero line.
- The dashboard refetches on live payment and attendance events (query keys start with `owner`).

## New shared pieces

`pages/admin/MasterScreen.tsx` (one list-and-form screen driven by a description of its fields), `components/common/BarLineChart.tsx` and `lib/chart.ts` (plain SVG chart with a screen-reader table), `lib/ownerReport.ts` (machine use), `formatLakh` and `formatPercent` in `lib/format.ts`.
