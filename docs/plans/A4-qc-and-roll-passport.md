# A4 — Quality Check and Roll Passport

> **Summary:** Track A's fourth plan, written after the work: the QC queue, the inspection screen with the AI suggestion and the human verdict, the vision model card, and the Roll Passport with its QR tag and scanner.
> **Last updated:** 2026-10-10 14:52 IST
> **Status:** built and tested on branch `a/web-scaffold`. Not pushed yet (Ridanshi pushes when her Track A tasks are done).

**Spec:** §4.2 (rolls, QC), §5 (roll status), §6 R9 and R10, §7 (costing), §9 (vision QC), §11 (screens). **Contract:** Hritwik's `contracts/types.ts`; example data until plans B4, B6 and B8.

## Screens

| Route | File | Roles | What it does | Endpoints |
|---|---|---|---|---|
| `/qc` | `pages/qc/QcQueue.tsx` | qc | Counters (waiting, needs rework, in rework, passed, rejected), the rolls that need attention, **Inspect** for a roll waiting for QC, **Start rework** (operator, dyeing machine or mend by hand) for a roll that needs it, **Scan a roll**. | `GET /qc/queue`, `/workers`, `/machines`; `POST /rework-runs` |
| `/qc/:rollCode` | `pages/qc/QcInspect.tsx` | qc | Photo (optional) → **Analyse** → the model's boxes drawn over the photo → inspector sets the verdict and defects → **Record verdict**. | `GET /rolls/{code}/passport`; `POST /uploads`, `/qc/analyze`, `/qc/inspections` |
| `/qc/model` | `pages/qc/ModelCard.tsx` | qc, owner | Held-out results per defect type, confusion matrix, datasets with their licences, and whether the model clears the spec's bar (holes found ≥ 80%, false alarms ≤ 20%). Honest empty state when no model exists. | `GET /qc/model-card` |
| `/r/:code` | `pages/rolls/RollPassport.tsx` | everyone logged in | The roll's whole life: status, order, buyer, QR tag (print label), yarn lots (a recalled one is flagged), machines in time order, quality checks, dispatch with invoice link, and the **true cost per metre** labelled provisional or final. | `GET /rolls/{code}/passport` |

## Rules these screens follow

- **The AI only suggests.** Nothing is recorded until the inspector presses Record verdict. The suggestion prefills the verdict and defect counts, which stay editable. If the verdict differs from the suggestion, the screen says "You are overriding the AI … the override is recorded" (the server sets `overrode_ai`).
- **QC works without the model.** If the analysis is unavailable or fails, the screen says so and manual checking continues. A suggestion from a model that is not validated is labelled "Unvalidated suggestion".
- **A photo is uploaded once** even if it is analysed again.
- **Buyers never see internal data on the passport:** no cost, no yarn lots, no machines or operators. They get status, quality checks and dispatch, and the order link goes to the portal.
- **Scans cannot misdirect:** `lib/rollCode.ts` accepts only `R-<digits>` or `https://…/r/R-<digits>`, so a QR can never open another site or another kind of record.
- A photo preview is freed when the screen closes. Model dataset links open only if they are `http(s)`.

## New shared pieces

`lib/rollCode.ts` (parse a scan or typed code, build the tag address), `lib/defects.ts` (defect labels), `components/common/QrScanner.tsx` (camera scan with `jsqr`, typed fallback), `RollQr.tsx` (`qrcode.react`), `PhotoWithBoxes.tsx`, `lib/useAction.ts` and `ActionDialog.tsx` (from A3).

## Tests

`rollCode` 7, `QrScanner` 5, `PhotoWithBoxes` 4, `RollPassport` 15, `QcQueue` 12, `QcInspect` 21, `ModelCard` 10. The whole web suite is 252 tests.

## Not done in A4 / for Hritwik

- **Live camera capture** in the inspection (a photo is taken through the phone's camera picker, which works over plain HTTP). A live viewfinder needs the HTTPS check from A1 Task 7.
- **The passport sends `cost` to every role.** The screen hides it from buyers, but the backend should leave it out for buyers too. Asked in the team notes.
- **Printed tags** print one roll's QR label (`window.print()` with a print stylesheet); a sheet of many labels is not built.

## Done when

- [x] `/qc`, `/qc/:rollCode`, `/qc/model` and `/r/:code` are real screens.
- [x] Tests, type-check, lint and build pass.
- [ ] Scanned with a real phone camera over HTTPS.
