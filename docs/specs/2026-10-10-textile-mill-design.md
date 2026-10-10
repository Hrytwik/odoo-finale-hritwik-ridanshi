# Everest Textile Mills — System Design

> **Summary:** Full design for the textile mill platform: architecture (Next.js + FastAPI + local Postgres), 29-table data model, business rules, per-roll costing, delay/shortage/root-cause engines, vision QC, provider-agnostic LLM layer, screens, API surface, two-track split, testing and demo.
> **Last updated:** 2026-10-10
> **Status:** Draft for team review

---

## 1. Goal

Build one working platform that replaces Everest Textile Mills' notebooks, paper slips, registers and phone calls. Every scene in the brief must work end to end with live data:

1. **Yarn arrives at the gate** — record the lot (quantity, type, colour, which order it is for); always know stock; warn before it runs low; answer "is there enough yarn to start this order?"
2. **Production floor** — which order is on which machine, how far along, which machines are idle, what each machine produced today; breakdowns, shift changes, workers moving between jobs.
3. **Fabric checking** — pass / rework / reject; every roll traceable to its order and machines; clear record of passed, failed, waiting.
4. **Buyer asks about an order** — the buyer sees exactly where the order stands and when it will arrive, without anyone walking the floor.
5. **Dispatch** — right rolls, right quantity, right buyer, matching invoice; finished stock on the shelf always visible; nothing dispatched twice.
6. **Owner closes the books** — cost of each order, output of each machine, wages paid; raw material bills, wages and buyer payments in one place; did the mill make money this month.
7. **Attendance and wages** — listed in "how things run today" and needed by the owner scene.

**Headline answer to the brief:** *"nobody knows the real cost of a single roll of fabric"* → the **Roll Passport**: scan any roll's QR code and see its whole life — yarn lot → machines → operators → QC → true cost per metre (rework and rejects included) → buyer → invoice.

### Judging standard we build to (Odoo hackathon guidelines)

- **Must have:** live/dynamic data (no static JSON beyond early prototyping); responsive, clean UI with a consistent colour scheme and layout; robust input validation; intuitive navigation; Git used properly by **both** team members.
- **Nice to have:** our own backend APIs, data model and **local** database; works offline / without depending on cloud tools; AI used only where it adds real value.

---

## 2. Scope

| In scope (must ship) | Stretch | Out |
|---|---|---|
| All 7 scenes above, thin but end to end | Challan photo → auto-fill gate form | Real WhatsApp/SMS sending (we show the drafted message) |
| Roll Passport + printed QR tags | Colour-mismatch check against an approved swatch (ΔE) | Separate native mobile app (responsive web instead) |
| Per-roll costing + month-end profit / cash | | Inventory valuation of work-in-progress |
| Delay warning + delivery date, shortage forecast, defect root cause, recall | | Voice entry |
| Vision QC (subject to the spike's kill criteria, §9) | | |
| LLM layer, provider-agnostic, with report card | | |

---

## 3. Architecture

```
laptop: npm run dev   (native processes — no containers; works on macOS and Windows)
├── web     Next.js (App Router) + TypeScript + Tailwind + shadcn/ui
├── api     FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 (single process)
├── db      PostgreSQL (tables + derived-status views)
├── proxy   Caddy — HTTPS on the local network (local certificate)
└── ollama  optional, local language model for offline AI
phones / tablets → https://<laptop LAN address>
```

- **Runs natively on both team laptops (macOS and Windows):** PostgreSQL 16 installed locally (Homebrew on macOS, the official installer on Windows), `uv` for Python, npm for the web app. From the repo root, `npm run dev` starts the API and the web app together; Caddy runs separately when phones need HTTPS.
- **Development database:** while building, a developer may point `DATABASE_URL` at a hosted PostgreSQL (for example Neon) using its direct connection string; the demo runs on a local one. The test setup refuses to run unless `TEST_DATABASE_URL` names a *different* database whose name ends in `_test`, because the tests erase every table in that database.
- **All business rules live in the API** and in database constraints. The web app never decides a rule on its own; it mirrors validation for fast feedback only.
- **Contract:** FastAPI generates an OpenAPI description from the Pydantic models. A script (`npm run contracts`) writes `contracts/openapi.json` and generates `contracts/types.ts` with `openapi-typescript`. The web app imports only these types. A contract change regenerates the types and breaks the web build immediately if anything no longer matches.
- **Example-data stubs first:** every endpoint exists from the start with its final request/response shape, returning realistic example data. Logic replaces the example data module by module with no change to the shape.
- **Live updates:** after each committed write, the API publishes a small event (e.g. `{"type": "machine.changed", "id": 4}`) to an in-process broadcaster; `GET /api/events` streams them as Server-Sent Events. The web app listens and invalidates the matching queries (TanStack Query), which re-fetch. Limitation: in-process broadcasting requires the API to run as one process — fine for one laptop.
- **Errors:** every error response has one shape: `{"code": "ROLL_NOT_PASSED", "message": "Roll R-0142 has not passed QC", "field": "roll_code"}`. Field errors show under the field; rule errors show as a message; database constraints are the last line of defence. Buttons that submit lock on first tap (ref-based guard) so double taps cannot double-submit.
- **Login:** username + password → signed token (JWT) in an httpOnly cookie. Every endpoint declares the roles allowed. Buyer endpoints take the buyer from the token, never from the URL or body.
- **Offline:** database, API, vision model and (optionally) the language model all run locally. Fonts and icons are bundled — no CDN.
- **Camera over the network:** browsers allow live camera access only on HTTPS (or on `localhost`). Caddy serves HTTPS with a local certificate; this must be tested on a real phone early. Fallback: `<input type="file" accept="image/*" capture="environment">`, which works over plain HTTP.
- **Files:** QC photos and challan photos are saved under `data/uploads/` (git-ignored); the database stores the path.

---

## 4. Data model

**Principle: anything that can be worked out from other records is never stored as a typed-in value.** Stock is the sum of the yarn ledger; machine, roll and order status are derived in SQL views from runs, downtimes, inspections and dispatches. The only typed-in states are decisions people make: an order's `draft/confirmed/cancelled`, a dispatch's `loading/dispatched`, a QC verdict, a lot's blocked flag.

All tables have `id` (integer primary key) and `created_at` (timestamptz). Text fields marked *required* are trimmed and must be non-empty. All timestamps are stored as timestamptz and shown in IST.

### 4.1 Store, yarn and orders

| Table | Columns and constraints |
|---|---|
| `suppliers` | `name` required unique; `phone`; `lead_time_days` int ≥ 0 |
| `yarn_types` | `code` required unique (e.g. `30S-COT-RAW`); `name` required (e.g. "30s cotton"); `colour` required; `reorder_level_kg` numeric ≥ 0 |
| `fabric_types` | `name` required unique (e.g. "Poplin 58in"); `width_in` > 0; `wastage_pct` 0–50 |
| `fabric_recipe_lines` | `fabric_type_id`, `yarn_type_id`, `kg_per_metre` > 0; unique (`fabric_type_id`, `yarn_type_id`) |
| `yarn_lots` | `lot_code` unique (generated, e.g. `L-0017`); `yarn_type_id`; `supplier_id`; `cost_per_kg` > 0; `challan_no` required; `challan_photo_path` nullable; `intended_order_id` nullable (information only — does not reserve); `received_at`; `received_by` (user); `is_blocked` bool default false; `blocked_reason`, `blocked_at` nullable; unique (`supplier_id`, `challan_no`, `yarn_type_id`) to stop the same delivery being entered twice |
| `yarn_movements` | the ledger. `yarn_lot_id`; `kind` ∈ receipt / issue / return / adjustment; `qty_kg` signed, ≠ 0 (receipt > 0, issue < 0, return > 0, adjustment either sign); `production_run_id` required for issue/return, null otherwise; `note` required for adjustment; `moved_by` (user) |
| `buyers` | `name` required unique; `contact_name`; `phone`; `email` |
| `orders` | `code` unique (generated, `ORD-0012`); `buyer_id`; `fabric_type_id`; `colour` required; `qty_metres` > 0; `price_per_metre` > 0; `deadline` date (≥ creation date); `state` ∈ draft / confirmed / cancelled; `confirmed_at` nullable |

### 4.2 Floor, runs, rolls and QC

| Table | Columns and constraints |
|---|---|
| `machines` | `code` unique (`LOOM-04`); `name`; `stage` ∈ spinning / weaving / dyeing; `rated_output_per_hour` > 0 (kg/h for spinning, m/h for weaving and dyeing); `running_cost_per_hour` ≥ 0; `active` bool. **No status column.** |
| `machine_downtimes` | `machine_id`; `started_at`; `ended_at` nullable (null = still down); `reason` required; partial unique index: at most one open downtime per machine; `ended_at` ≥ `started_at` |
| `production_runs` | `order_id`; `machine_id` (nullable only when `stage` = rework, for manual mending); `stage` ∈ spinning / weaving / dyeing / rework; `operator_worker_id`; `started_at`; `ended_at` nullable; `output_kg` nullable (spinning only, entered when the run ends); `input_run_id` nullable (required for weaving: the spinning run of the same order whose yarn it uses); partial unique index: at most one open run per machine; `ended_at` ≥ `started_at` (a zero-length run from an immediate breakdown or hand-over is allowed) |
| `rolls` | `code` unique (generated, `R-0142`, printed as QR pointing to `/r/R-0142`); `order_id`; `metres` > 0 |
| `roll_runs` | `roll_id`, `run_id`, `purpose` ∈ produce / dye / rework; primary key (`roll_id`, `run_id`) |
| `qc_inspections` | `roll_id`; `inspector_worker_id`; `inspected_at`; `photo_path` nullable; `ai_suggestion` jsonb nullable (`{model_version, verdict, boxes:[{x,y,w,h,defect_type,confidence}]}`); `verdict` ∈ pass / rework / reject; `overrode_ai` bool (computed by the server: AI suggestion present and verdict differs); `notes` |
| `qc_defects` | final, inspector-confirmed defects only. `inspection_id`; `defect_type` ∈ hole / stain / thread_fault / colour_mismatch / other; `count` int > 0; `ai_detected` bool |

### 4.3 Dispatch, money and people

| Table | Columns and constraints |
|---|---|
| `dispatches` | `code` unique (`DSP-0007`); `buyer_id`; `vehicle_no` required; `driver_name`; `state` ∈ loading / dispatched; `dispatched_at` nullable |
| `dispatch_items` | `dispatch_id`; `roll_id` **unique** (a roll can be on only one dispatch, ever) |
| `invoices` | `invoice_no` unique (`INV-0007`); `dispatch_id` unique; `buyer_id`; `issued_at`; `total_amount` |
| `invoice_lines` | `invoice_id`; `order_id`; `metres`; `rate`; `amount` — frozen at issue |
| `buyer_payments` | `invoice_id`; `amount` > 0; `received_at`; `reference` |
| `supplier_bills` | `supplier_id`; `yarn_lot_id` unique; `bill_no` (= challan no); `amount` (= received kg × cost/kg); `bill_date`; `due_date` (bill_date + 30 days default) |
| `supplier_payments` | `bill_id`; `amount` > 0; `paid_at`; `reference` |
| `workers` | `code` unique; `name` required; `role` ∈ operator / inspector / storekeeper / supervisor / dispatch / helper; `daily_wage` > 0; `active` bool |
| `shifts` | `name` unique (A/B/C); `start_time`; `end_time` (may cross midnight, e.g. C = 22:00–06:00) |
| `attendance` | `worker_id`; `date` (not in the future); `shift_id`; `status` ∈ present / half_day / absent; `marked_by`; unique (`worker_id`, `date`, `shift_id`) |
| `wage_payments` | `worker_id`; `period_start`; `period_end` (≥ start); `amount` > 0; `paid_at` |
| `users` | `username` unique; `password_hash`; `role` ∈ owner / accountant / store / supervisor / qc / dispatch / buyer; `worker_id` nullable; `buyer_id` nullable; CHECK: `buyer_id` is set **if and only if** role = buyer; CHECK: role = qc requires `worker_id` (the inspector on `qc_inspections` comes from the logged-in user's worker) |

### 4.4 LLM settings (added for the provider-agnostic layer, §10)

| Table | Columns and constraints |
|---|---|
| `llm_settings` | single active row: `provider` ∈ anthropic / openai_compatible; `model` required; `base_url` nullable (required for openai_compatible); `api_key_encrypted` nullable (encrypted with a server secret from `.env`; never returned by any endpoint); `supports_tools` bool; `supports_vision` bool; `updated_by` |
| `llm_eval_runs` | `provider`; `model`; `run_at`; `score`; `total`; `details` jsonb (per question: question, expected, answer, pass) |

Total: 29 tables.

### 4.5 Derived views

| View | What it answers |
|---|---|
| `v_lot_stock` | kg on hand per lot = sum of its movements |
| `v_order_yarn_need` | per confirmed order and yarn type: `need_kg` = qty_metres × kg_per_metre × (1 + wastage_pct/100); `issued_kg` = issues − returns, from lots of that yarn type, to that order's runs; `outstanding_kg` = max(0, need − issued) |
| `v_yarn_type_stock` | per yarn type: `on_hand_kg` (unblocked lots), `outstanding_kg` (all confirmed orders), `free_kg` = on_hand − outstanding, `below_reorder` = free_kg < reorder_level_kg |
| `v_machine_status` | **down** if an open downtime exists; else **running** if an open run exists; else **idle** (active machines only) |
| `v_roll_status` | see §5 |
| `v_order_progress` | spun_kg vs need_kg; woven / dyed / passed / rejected / dispatched metres vs qty_metres; buyer-facing stage (§5) |
| `v_order_timeline` | union of dated events per order (confirmed, first spinning/weaving/dyeing run, rolls passed, dispatches) for the buyer portal |

---

## 5. Derived status rules

**Roll status**, evaluated in this order:
1. On a dispatch that is `dispatched` → **dispatched**; on a dispatch still `loading` → **loading**.
2. Latest inspection verdict = reject → **rejected**.
3. Latest inspection verdict = pass → **in_store**.
4. Latest inspection verdict = rework → if a rework run linked after that inspection has ended → **awaiting_qc**; if one is open → **in_rework**; else → **awaiting_rework**.
5. No inspection yet → if a dye run has ended → **awaiting_qc**; if a dye run is open → **dyeing**; else → **woven**.

**Order buyer-facing stage** (furthest reached): cancelled → draft → *Waiting to start* (confirmed, no runs) → *Spinning* → *Weaving* → *Dyeing* → *Quality check* (any roll awaiting_qc / in rework) → *Ready to ship* (passed metres ≥ ordered) → *Partly dispatched* → *Dispatched* (dispatched metres ≥ ordered).

**Machine "output today"**: spinning = sum of `output_kg` of runs ended today; weaving = metres of rolls produced today; dyeing = metres of rolls in dye runs ended today.

---

## 6. Business rules and invariants

Every rule is enforced in the API inside one database transaction; the ones marked **DB** are also enforced by a database constraint. Error codes in brackets.

| # | Rule |
|---|---|
| R1 | **Receive lot:** creates the lot, its receipt movement and its supplier bill in one transaction. qty_kg > 0, cost_per_kg > 0. Duplicate (supplier, challan, yarn type) refused [`DUPLICATE_CHALLAN`] **DB**. |
| R2 | **Issue yarn:** lot not blocked [`LOT_BLOCKED`]; target run is an open spinning run of a confirmed order [`RUN_NOT_OPEN`]; lock the lot row (`SELECT … FOR UPDATE`), then qty ≤ on hand [`INSUFFICIENT_STOCK`]. Stock can never go negative, even with two simultaneous issues. **Return:** qty ≤ issued from that lot to that run minus earlier returns. |
| R3 | **Orders:** draft → confirmed → (cancelled only while no runs exist) [`ORDER_HAS_RUNS`]. After confirmation only the deadline may change. |
| R4 | **Start run:** machine active; not down [`MACHINE_DOWN`]; no open run [`MACHINE_BUSY`] **DB**; machine stage = run stage [`WRONG_STAGE`]; order confirmed; operator active. Weaving requires `input_run_id` = a spinning run of the same order [`INPUT_RUN_REQUIRED`]. |
| R5 | **Breakdown:** opens a downtime and ends any open run on that machine at the same moment. **Repair:** ends the downtime. |
| R6 | **Hand over (shift change / worker moves):** ends the current run and starts a new one on the same machine and order with the new operator (same `input_run_id`). Each run has exactly one operator. |
| R7 | **Roll off:** only on an open weaving run; metres > 0; creates the roll (order = the run's order) and a `produce` link. |
| R8 | **Load dyeing:** dye run open; every roll belongs to the run's order and has status `woven` [`ROLL_WRONG_STATUS`]; creates `dye` links. |
| R9 | **QC:** roll status `awaiting_qc` [`ROLL_WRONG_STATUS`]; verdict required; at least one defect when verdict ≠ pass [`DEFECTS_REQUIRED`]; `overrode_ai` computed server-side. |
| R10 | **Rework run:** roll's status `awaiting_rework`; machine is a dyeing machine (re-dye) or null (manual mending); creates a `rework` link. |
| R11 | **Load dispatch:** dispatch is `loading`; roll's order belongs to the dispatch's buyer [`WRONG_BUYER`]; roll status `in_store` [`ROLL_NOT_PASSED`]; roll on no other dispatch [`ALREADY_DISPATCHED`] **DB**. Response includes per-order metres loaded vs remaining and an over-shipping warning. Removing a roll is allowed while loading. |
| R12 | **Confirm dispatch:** ≥ 1 roll [`EMPTY_DISPATCH`]; sets `dispatched`, and creates the invoice and its lines (metres × that order's price) in the same transaction. Dispatches and invoices are immutable afterwards [`DISPATCH_LOCKED`]. |
| R13 | **Payment limits:** buyer payment ≤ invoice balance; supplier payment ≤ bill balance; wage payment ≤ wages owed for that worker and period [`OVERPAYMENT`]. |
| R14 | **Block lot (recall):** sets `is_blocked`; refuses further issues (R2); recall exposure is computed (§8.4). |
| R15 | **Buyer scoping:** every buyer-facing query filters by the buyer in the token; another buyer's order returns 404, not 403. |
| R16 | **Attendance:** unique per worker/date/shift **DB**; no future dates [`FUTURE_DATE`]. |
| R17 | **General validation:** required text trimmed and non-empty; numbers within the ranges in §4; dates sane. Validation is in Pydantic (API), mirrored in Zod (web), and backed by CHECK constraints (DB). |

---

## 7. Costing method

### 7.1 Cost sources

1. **Yarn:** kg issued × that lot's cost/kg, minus returns. Belongs to the order of the spinning run it was issued to.
2. **Machine:** run duration (hours) × machine `running_cost_per_hour`.
3. **Labour:** shift wages split across runs (§7.2).
4. **Rework:** machine + labour cost of rework runs.

### 7.2 Labour split (shift-wage allocation)

For each attendance record (worker, date, shift) with status present or half_day (absent records are skipped — no pay, nothing to split):
- `pay` = daily_wage × (1 for present, 0.5 for half_day).
- `paid_hours` = shift length × (1 or 0.5). Shift length handles midnight crossing.
- `h_i` = hours each of that worker's runs overlaps the shift window; `H` = Σ h_i.
- Each run receives `pay × h_i / max(H, paid_hours)`.
- `idle_labour` = `pay × max(0, 1 − H / paid_hours)`.

This guarantees Σ allocated + idle = pay exactly. One worker minding three looms: H > paid_hours, so pay is split three ways and idle = 0. A run whose operator has no present/half_day attendance record for that time (missing, or marked absent) is reported as a **data warning** (never silently costed at zero).

### 7.3 From runs to rolls

- Weaving run cost → split across the rolls it produced, by metres.
- Dye run cost → split across the rolls loaded into it, by metres.
- Rework run cost → the roll(s) it reworked, by metres.
- Spinning runs + yarn → split across **all** the order's rolls, by metres.
- **Rejected rolls'** total cost is redistributed across the order's non-rejected rolls by metres, so a roll's cost per metre is the true cost of a *good* metre. If no good rolls exist yet, the cost is shown on the order as "not yet absorbed".
- Order-level shares (spinning, yarn, rejects) are spread over the rolls produced **so far**, so a roll's cost per metre is **provisional** until the order's last roll is inspected; the Roll Passport labels it "provisional" or "final".

### 7.4 Order and month

- **Order profit** = good metres × price per metre − order cost (§7.1).
- **Month-end, three panels:**
  - **Profit:** invoiced in the month − yarn issued in the month − wages earned in the month (idle labour as its own line) − machine running cost in the month − stock write-offs (negative adjustments × lot cost/kg, its own line).
  - **Cash:** received from buyers − paid to suppliers − paid in wages; plus receivables and payables outstanding.
  - **Machines:** per machine, hours running / idle / down within shift time; idle and down hours shown as **lost capacity** (hours × rated output), never as rupees.
- **Reconciliation invariant (tested):** Σ order costs incurred in the month + idle labour = yarn issued + wages earned + machine running cost for the month.

### 7.5 Implementation

Computed on request in `modules/costing` (no stored totals). Endpoints return the breakdown, not just the total, so the Roll Passport and order page can show each component.

---

## 8. Calculated intelligence (no language model)

### 8.1 Delivery date and delay warning

- **Remaining work per order per stage:** spinning kg = outstanding need; weaving m = qty − woven (excluding rejected); dyeing m = woven − dyed. QC is not capacity-modelled (see the fixed QC day below).
- **Daily capacity per stage** = Σ over active, not-down machines of rated output × shift hours per day × the stage's **observed efficiency** (actual output ÷ rated output over run hours in the last 7 days; default 0.8 when there is no history).
- **Queue:** earliest-deadline-first at every stage. An order cannot finish a stage before finishing the previous one: `finish(stage) = max(finish(previous stage), queue completion time at this stage)`.
- **Delivery date** = dyeing finish + 1 day QC + 1 day dispatch buffer (both constants in config).
- **Late warning** when the delivery date > deadline: days late and the bottleneck stage (the stage that adds the most delay).
- **What-ifs (code, not the language model):** (a) +1 shift at the bottleneck stage (capacity × (shifts + 1) / shifts) — offered only when fewer than 3 shifts are configured; (b) move this order to the front of every queue. Each returns the new delivery date.
- Simplification: each stage is one pool of capacity; changeover time is ignored.

### 8.2 Yarn shortage forecast (reorder-point rule)

For each yarn type: spread each confirmed order's outstanding need evenly over its spinning window from §8.1; project on-hand stock day by day; find the first day it falls below the reorder level. `order_by` = that day − supplier lead time (the yarn type's most recent supplier). `suggested_kg` = outstanding need − on hand + reorder level, rounded up to 50 kg. If `order_by` is in the past: "order now — N days late".

### 8.3 Defect root cause

Factors: weaving machine, dyeing machine, weaving operator, weaving shift (from the weaving run's start time), yarn lot. For each value, compare the share of inspected rolls with defects against all other rolls using **Fisher's exact test** (one-sided, `scipy.stats.fisher_exact`), only for groups with ≥ 5 inspected rolls, with a **Bonferroni** correction (α = 0.05 ÷ number of tests). Output per flagged value: counts, rates and p-value, e.g. "Lot L-17: 9 of 20 rolls defective vs 4% elsewhere". Uses only inspector-confirmed defects (`qc_defects`).

### 8.4 Recall chain

Blocked lot → its issue movements → spinning runs → weaving runs whose `input_run_id` is one of those → rolls produced → each roll's status, order, buyer and dispatch. Output grouped by: on the floor / in store / loading / dispatched (with buyer and dispatch code). Simplification stated openly: each weaving run draws from one spinning run.

---

## 9. Vision QC

- **Flow:** inspector photographs a stretch of the roll → `POST /api/qc/analyze` → boxes with defect type and confidence drawn over the photo → inspector confirms or overrides (R9). QC works fully without the model.
- **Detected classes:** hole, stain, thread_fault. **Colour mismatch** is marked by the inspector (a detector cannot know the target shade; phone cameras shift colour). Stretch: photograph roll + approved swatch in one frame and compute ΔE (CIEDE2000).
- **Model:** a small YOLO detector (Ultralytics) fine-tuned on (a) public fabric-defect datasets — each licence verified on its official page and credited in the README — and (b) ~100 of our own labelled phone photos of real cloth with holes, stains and pulled threads. Runs locally on the laptop (offline).
- **Spike, timeboxed to 3 hours, with kill criteria.** Held-out test on our own photos the model never trained on: ≥ 30 defective, ≥ 30 clean.
  - Holes found ≥ 80% **and** false alarms on clean cloth ≤ 20% → headline feature.
  - Otherwise → the configured language model (if it supports images) gives an "unvalidated AI suggestion", clearly labelled.
  - If that is unavailable → manual QC only.
- **Model card page:** held-out results per class (found / missed / false alarms, confusion matrix), dataset sources, model version. Real numbers only.
- Training code and scripts live in `services/api/ml/`; datasets and training runs are git-ignored; the final small model file is committed to `services/api/ml/models/`.

---

## 10. Language-model layer (provider-agnostic)

### 10.1 Purpose

The system works without it. It handles the language parts of the mill's day: (1) turning a free-form question into the right data lookups, (2) answering buyers without a phone call, (3) drafting messages people would otherwise write, (4) reading messy input (challan photos).

### 10.2 Rules

- **The model never calculates a number.** It calls our functions and words the results.
- **Tools are read-only.** No tool writes to the database. Challan auto-fill only pre-fills a form the storekeeper submits through normal validation.
- **Fixed functions only** — no model-written SQL.
- **Every answer carries its sources:** the list of tools called with their inputs and a summary of their outputs, shown in a "Sources" panel.
- **Buyer tools never accept a buyer id;** the server injects it from the login.

### 10.3 Provider adapters (adapter pattern)

- One internal interface: `complete(system, messages, tools, options) → {text, tool_calls}` with our own neutral message and tool formats (tool schemas generated from Pydantic models).
- **`anthropic` adapter:** official `anthropic` Python SDK.
- **`openai_compatible` adapter:** official `openai` Python SDK with a configurable `base_url` — covers OpenAI, Groq, OpenRouter and local models via Ollama or LM Studio.
- **Our own tool loop** (max 6 iterations), identical across providers.
- **Capability flags** per configured model: `supports_tools`, `supports_vision`. A feature whose capability is missing is disabled with a clear message; nothing fails silently.
- **Settings page** (owner only): provider, model, base URL, API key (stored encrypted server-side, never sent back to the browser).
- **Default configuration:** provider `anthropic`, model `claude-opus-5-5`. Provider-specific options (e.g. effort level) are passed through `options` and ignored by adapters that don't support them.
- **No provider reachable:** every AI surface shows "AI unavailable — check Settings or connection"; all number screens keep working. No pre-recorded answers.

### 10.4 Features (priority order)

1. **Owner Copilot** (owner, accountant, supervisor). Tools: `get_order_status`, `get_order_cost`, `get_month_summary`, `get_machine_utilisation`, `get_late_orders`, `get_shortage_forecast`, `get_defect_root_causes`, `get_stock`.
2. **Buyer assistant** (portal). Tools: `get_my_orders`, `get_my_order_status`, `get_my_order_eta`.
3. **Delay explanation:** words the §8.1 result and its two what-ifs; cannot propose fixes the code did not test.
4. **Recall drafts and month summary:** per-buyer recall message from §8.4; one-paragraph month summary from §7.4. Shown for a person to review and copy.
5. **Challan photo → auto-fill (stretch):** requires `supports_vision`; returns a fixed schema (supplier, challan_no, yarn type, kg, rate) that pre-fills the gate form.

### 10.5 Report card

15 questions about the current data (e.g. "How many kg of 30s cotton are free right now?"). **Expected answers are computed live by the engines at run time** (so they stay correct as data changes). An answer passes if it contains the expected value (numbers normalised). Results are saved in `llm_eval_runs` and shown per model, e.g. "11/15", with every failure listed.

---

## 11. Screens (web app)

Phone-first for floor roles; laptop layout for owner and accountant. Menus show only what the logged-in role may use.

| Area | Route | Roles | What it does |
|---|---|---|---|
| Login | `/login` | all | username/password |
| Gate | `/store/receive` | store | receive a lot in ~20 seconds (yarn type, supplier, kg, cost/kg, challan no, optional order, optional photo) |
| Stock | `/store/stock` | store, owner | stock per yarn type: on hand, needed by orders, free, low-stock warning; reorder suggestions |
| Lot | `/store/lots/[code]` | store, owner | lot ledger; block lot → recall exposure + drafted buyer messages |
| Orders | `/orders`, `/orders/new`, `/orders/[code]` | owner, accountant, supervisor | list with "can start / short X kg" and late badges; detail: progress bars, delivery date, delay explanation + what-ifs, cost breakdown, profit |
| Floor board | `/floor` | supervisor, owner | live grid of machines (running / idle / down), current order and operator, progress, output today |
| Machine | `/floor/machines/[code]` | supervisor | start run, hand over, roll off (weaving), load rolls (dyeing), issue yarn (spinning), breakdown, repair |
| QC queue | `/qc` | qc | rolls awaiting QC / rework; passed / failed / waiting counts |
| QC inspect | `/qc/[rollCode]` | qc | camera, AI box overlay, verdict, defects |
| Model card | `/qc/model` | qc, owner | held-out results |
| Roll Passport | `/r/[code]` | all logged-in (buyers: own rolls only) | full life of the roll + cost per metre |
| Dispatch | `/dispatch`, `/dispatch/[code]` | dispatch | create dispatch; scan-to-load with live checks; per-order loaded vs remaining; confirm |
| Invoice | `/invoices/[no]` | dispatch, accountant, buyer (own) | printable invoice |
| Money | `/money/receivables`, `/money/payables` | accountant, owner | invoices and bills with balances; record payments |
| People | `/people/workers`, `/people/attendance`, `/people/wages` | supervisor (attendance), accountant | worker list; mark attendance per shift (all present, untick absent); wages earned / paid / owed; record wage payment |
| Owner | `/owner` | owner | month-end: profit, cash, machines (lost capacity), idle labour; month summary |
| Insights | `/owner/insights` | owner | late orders, reorder suggestions, defect root causes |
| Copilot | `/copilot` | owner, accountant, supervisor | chat with Sources panel |
| AI settings | `/settings/ai`, `/settings/ai/report-card` | owner | provider/model/key; run and view report card |
| Buyer portal | `/portal`, `/portal/orders/[code]` | buyer | own orders, timeline, delivery date, assistant chat |
| Master data | `/admin/suppliers`, `/admin/buyers`, `/admin/yarn-types`, `/admin/fabric-types`, `/admin/machines`, `/admin/shifts`, `/admin/users` | owner | create and edit the reference records (fabric types include their yarn recipe; users include role, linked worker or buyer) |

Design: Tailwind + shadcn/ui; one colour scheme and spacing scale; a "Demo data" badge in the header whenever seeded data is loaded.

---

## 12. API surface

All under `/api`. Request/response shapes are the Pydantic models in each module; the generated `contracts/` files are the source of truth for the web app.

- **auth:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- **master data:** `GET/POST/PATCH` on `/suppliers`, `/yarn-types`, `/fabric-types` (with recipe lines), `/buyers`, `/machines`, `/workers`, `/shifts`, `/users` (owner only for writes)
- **store:** `POST /lots` (receive), `GET /lots`, `GET /lots/{code}`, `POST /lots/{code}/block`, `GET /lots/{code}/recall`, `POST /movements/issue`, `POST /movements/return`, `POST /movements/adjust`, `GET /stock`
- **orders:** `GET/POST /orders`, `GET /orders/{code}`, `POST /orders/{code}/confirm`, `POST /orders/{code}/cancel`, `PATCH /orders/{code}` (deadline), `GET /orders/{code}/yarn-check`
- **floor:** `GET /floor` (board), `GET /machines/{code}` (open run, open downtime, output today, recent runs), `POST /runs` (start), `POST /runs/{id}/end`, `POST /runs/{id}/handover`, `POST /runs/{id}/rolls` (roll off), `POST /runs/{id}/load-rolls` (dyeing), `POST /machines/{code}/breakdown`, `POST /machines/{code}/repair`
- **qc:** `GET /qc/queue`, `POST /qc/analyze` (photo → AI suggestion), `POST /qc/inspections`, `POST /rework-runs`, `GET /qc/model-card`
- **rolls:** `GET /rolls/{code}/passport`
- **dispatch:** `GET/POST /dispatches`, `GET /dispatches/{code}`, `POST /dispatches/{code}/items` (scan), `DELETE /dispatches/{code}/items/{roll_code}`, `POST /dispatches/{code}/confirm`, `GET /invoices/{no}`
- **money:** `GET /money/receivables`, `GET /money/payables`, `POST /payments/buyer`, `POST /payments/supplier`
- **people:** `GET/POST /attendance`, `GET /wages?month=`, `POST /payments/wages`
- **costing:** `GET /costing/rolls/{code}`, `GET /costing/orders/{code}`, `GET /reports/month?month=YYYY-MM`
- **intelligence:** `GET /insights/late-orders`, `GET /orders/{code}/eta` (with what-ifs), `GET /insights/shortages`, `GET /insights/root-causes`
- **llm:** `POST /ai/copilot`, `POST /ai/buyer-assistant`, `POST /ai/explain-delay/{order_code}`, `POST /ai/recall-drafts/{lot_code}`, `POST /ai/month-summary`, `POST /ai/challan-read`, `GET/PUT /ai/settings`, `POST /ai/report-card/run`, `GET /ai/report-card`
- **portal (buyer):** `GET /portal/orders`, `GET /portal/orders/{code}` (timeline + delivery date)
- **events:** `GET /events` (Server-Sent Events)

---

## 13. Two tracks

| | **Track A — Ridanshi** | **Track B — Hritwik** |
|---|---|---|
| Web | the entire web app: shell, login, role menus, design system, every screen in §11, QR printing/scanning, HTTPS phone check | — |
| API | `modules/llm` (adapters, tools, prompts, report card) and `modules/people` (attendance, wages, wage payments) | everything else: models, migrations, views, contract + example data, store, orders, floor, qc, dispatch, money, costing, intelligence, vision, events, auth, seed data |
| Tests | end-to-end demo script (Playwright); tests for `llm` and `people` | engine tests, rule tests, vision evaluation |

**Repository layout**

```
apps/web/                     Track A
services/api/app/main.py      Track B (Track A may add one router line)
services/api/app/db/          Track B — SQLAlchemy models, session, views
services/api/alembic/         Track B — migrations
services/api/app/modules/     one folder per module; owner per table above
services/api/tests/           tests live with their module's owner
services/api/ml/              Track B — training, evaluation, model file
contracts/                    generated by Track B (`npm run contracts`); Track A reads only
docs/specs/  docs/plans/      design and plans
docs/TEAM_NOTES.md            notes between the two tracks
docs/demo.md                  demo script with real numbers
package.json (root scripts: dev, test, contracts)  Caddyfile  .env.example  README.md
```

**Collaboration rules**

1. Only Track B writes migrations; Track A asks for column changes.
2. `contracts/` changes need both people to agree (a change breaks the other side's build).
3. Each track edits only its own folders; shared edits are one-line additions (a menu item, a router registration).
4. Short branches named `a/<topic>` and `b/<topic>`; both people commit; merge to `main` only when backend tests pass, the web app builds, `npm run dev` starts cleanly and the demo script passes.
5. Commit messages: plain imperative subject line, optional body, no trailers.
6. Work follows `docs/specs` and `docs/plans`; questions go to `docs/TEAM_NOTES.md` or directly to Hritwik — no improvised design changes.

---

## 14. Testing

1. **Engine tests (written first), Track B:** costing — half day, one weaver on three looms, worker with no runs, run across a shift change, reconciliation invariant; free stock and yarn check; reorder date; delivery date on small hand-checked queues; root cause flags a seeded bad lot and stays quiet on random noise.
2. **Rule tests against a real Postgres (no mocks), Track B:** same roll on two dispatches concurrently; another buyer's roll; unpassed roll; two concurrent issues against the last 50 kg; overpayment; run on a broken machine; issue from a blocked lot; buyer A opening buyer B's order → 404. Each also gets: zero / negative / boundary numbers, empty or whitespace text, individually valid but jointly invalid combinations, double submit, type mismatches.
3. **Contract:** FastAPI validates every response against its model; regenerated types break the web build on a mismatch.
4. **End-to-end demo script (Playwright), Track A:** gate → floor → QC → passport → recall → dispatch → portal → month-end.
5. **AI:** vision held-out evaluation (§9); language-model report card (§10.5).
6. **Real-device checklist, both:** HTTPS camera on real phones, QR scanning, gate entry in ~20 seconds.

**Merge gate:** backend tests pass + web builds + `npm run dev` starts cleanly + demo script passes.

---

## 15. Demo

One continuous story, same order / lot / rolls throughout, "Demo data" badge visible. One person talks and drives the projected laptop; the other drives the phone.

1. **Gate (phone):** log a lot in ~20 s → laptop stock updates; confirm a new order → "short 230 kg" → "reorder 450 kg by 14 Oct".
2. **Floor:** phone logs a breakdown on Loom 4 → board turns red within a second; order shows "late 2 days, bottleneck: weaving"; what-if "add a shift → on time".
3. **QC:** photograph cloth (ideally the judge's) → boxes → inspector confirms rework; flash the model card.
4. **Roll Passport (moment 1):** scan a printed tag → full life + true cost per metre.
5. **Recall (moment 2):** root cause has flagged lot L-17; block it → 6 rolls in store, 3 on yesterday's truck to one buyer, message drafted.
6. **Dispatch:** scan rolls; a rejected roll and an already-dispatched roll are refused; invoice matches.
7. **Buyer portal:** "Will my order make the 20th?" with sources; another buyer's order URL → not found.
8. **Month-end (moment 3):** profit + cash, wages paid/owed, idle labour line, Loom 4 lost capacity; the "profitable" order that lost money to rework.
9. **Close:** Wi-Fi off, switch to the local model, everything still works; real report-card scores.

**Cut order if short:** 9, then the second half of 6, then the model card in 3.
**Needs:** seeded scenarios (bad lot L-17, rework-loss order, late order, low yarn type, idle machine), printed QR tags, cloth. All numbers above are placeholders; `docs/demo.md` is updated with the real seeded figures.

---

## 16. Simplifications and unverified assumptions

**Simplifications (deliberate, stated openly):**
- Each weaving run draws from one spinning run.
- Each production stage is one pool of capacity; changeover time ignored; QC time is a fixed day.
- Costs counted in the month production happens, revenue when invoiced; no work-in-progress valuation.
- A lot's "intended order" is information only; it does not reserve stock.
- Live updates assume a single API process.
- Stages follow the brief (spinning → weaving → dyeing) even though mills that buy yarn usually do not spin it.

**Unverified — to be measured or checked during the build:**
- Weavers commonly mind several looms at once (the costing handles it either way).
- Gemini's OpenAI-compatible endpoint (not needed for the default setup).
- Public fabric-defect dataset contents, quality and licences.
- Training and labelling time on the laptop; final vision accuracy.
- Live camera on phones over our local HTTPS setup.
- Tool-calling quality and speed of local models; response times of the default model.
