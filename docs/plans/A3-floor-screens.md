# A3 — Floor Screens

> **Summary:** Track A's third plan, written after the work: the live Floor board and the Machine page where the supervisor starts runs, hands over, rolls off, loads rolls, issues yarn and reports breakdowns.
> **Last updated:** 2026-10-10 14:40 IST
> **Status:** built and tested on branch `a/web-scaffold`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).

**Spec:** §3 (live updates), §5 (machine status), §6 rules R2 to R8, §11 (screens). **Contract:** Hritwik's `contracts/types.ts`; example data until plan B3.

## Screens

| Route | File | Roles | What it does | Endpoints |
|---|---|---|---|---|
| `/floor` | `pages/floor/FloorBoard.tsx` | supervisor, owner | Machines grouped by stage as tiles: status, order, operator, progress, output today in kg or m, and for a broken machine the reason and the time. Running / idle / down counters. Refetches on live events (query key `['floor']`). | `GET /floor` |
| `/floor/machines/:code` | `pages/floor/MachineDetail.tsx` | supervisor, owner | Header, running job with progress, recent runs, and only the actions that make sense for the machine's state and stage (below). | `GET /machines/{code}`, `/workers`, `/orders`, `/floor`, `/lots` |

## Actions on the Machine page

| Action | Shown when | Sends |
|---|---|---|
| Start run | machine idle | `POST /runs`: order, operator; weaving also the spinning run number (quick picks from open spinning runs of that order) |
| End run | machine running | `POST /runs/{id}/end`; spinning asks for the kilos spun |
| Hand over | machine running | `POST /runs/{id}/handover` with the new operator |
| Roll off | weaving, running | `POST /runs/{id}/rolls` with metres (> 0); the toast names the new roll |
| Load rolls | dyeing, running | `POST /runs/{id}/load-rolls` from a list of roll codes |
| Issue yarn | spinning, running | `POST /movements/issue` from a usable (not blocked) lot |
| Report breakdown | not down | `POST /machines/{code}/breakdown` with a reason |
| Mark repaired | machine down | `POST /machines/{code}/repair` |

Only active operators are offered; inspectors and people who left cannot be put on a machine. Every action locks against double taps, shows the server's reason inside its dialog when refused, and refetches the board, machine, orders and stock.

## Shared pieces added

`lib/useAction.ts` (run one server action from a dialog, with toast, refetch and error) and `components/common/ActionDialog.tsx`.

## Tests

`FloorBoard` 9, `MachineDetail` 19 (what each state shows, each action's exact request, validation, server refusal).

## Not done in A3

- Scanning a roll code with the camera when loading rolls (codes are typed or pasted for now; QR scanning arrives with the Roll Passport work in A4).
- A list of woven rolls to pick from: the contract has no endpoint for it yet. Asking Hritwik would remove the typing.

## Done when

- [x] `/floor` and `/floor/machines/:code` are real screens.
- [x] Tests, type-check and lint pass.
- [ ] Checked on a real phone.
