# Everest Textile Mills

One platform for a textile mill: yarn store, production floor, quality checks with a defect-detection model, dispatch, a buyer portal, wages and month-end costing. Everything runs locally against PostgreSQL. The language model is optional and every number screen works without it.

Stack: React + Vite + TypeScript (`apps/web`), FastAPI + SQLAlchemy + PostgreSQL (`services/api`), and a shared API contract (`contracts/`). The design is in `docs/specs/`, the build plans are in `docs/plans/`, and `docs/HRITWIK_TEAM_NOTES.md` is the running log between the two tracks.

## What it does

| Role (login) | What they do in the app |
|---|---|
| **Store** (`store`) | Receives yarn lots against a challan and supplier bill, sees the yarn ledger, stock, what open orders still need and reorder suggestions. |
| **Supervisor** (`supervisor`) | Runs the floor board: starts and ends spinning, weaving and dyeing runs, issues yarn to a run, cuts rolls off a loom, loads rolls into a dye machine, marks breakdowns and attendance. |
| **QC inspector** (`qc`) | Works the quality-check queue. Photographs a roll, the defect model suggests a verdict and the defects, and the inspector adds a remark and saves. Starts rework on rolls that need it. |
| **Dispatch** (`dispatch`) | Creates a truck, loads rolls by typing a roll code or scanning its QR tag with the camera, confirms the truck (which creates the invoice). |
| **Accountant** (`accountant`) | Receivables, payables, payments, wages, workers, orders. |
| **Owner** (`owner`) | Everything above plus: the month-end report (profit, cash, machine use, idle labour, revenue and cost per order), insights (late orders, yarn shortages, what is behind the defects), the vision model photo log and metrics, the Copilot, AI settings and all master data (suppliers, buyers, buyer invites, yarn and fabric types, machines, shifts, users). |
| **Buyer** (`buyer`) | Signs up with an invite code and sees only their own orders: progress, trucks, notices about delays, and an assistant that answers questions about those orders. |

Public pages need no login: the landing page, sign-in, buyer sign-up, and the **roll passport** at `/r/<roll code>`, which is what a roll's QR tag opens (its full journey from yarn to truck).

## Features worth knowing about

- **Ten languages, everywhere.** English plus Hindi, Kannada, Tamil, Telugu, Marathi, Bengali, Gujarati, Malayalam and Punjabi, chosen from the language switcher. Every screen, message, chart label, unit and date follows the choice. A test fails the build if any text is missing in any language. Text that comes from the server (API error messages, some timeline labels) is still English.
- **Voice.** The assistant box has a microphone (speak your question in the chosen language) and a speaker (read the answer aloud). It uses the browser's own speech tools, so it works best in Chrome or Edge and needs HTTPS or localhost. The assistant answers in the language you chose.
- **Quality check with a defect model.** Choosing a photo sends it to the model straight away. The model's verdict, defects and a draft remark are filled in. The inspector adds a remark and saves. Disagreeing with the model is allowed and is recorded as an override.
- **Vision model page.** A photo log of every checked photo (order, batch, result, inspector remark) with search, filters (order, batch, result, date) and sorting; a "Check a photo" dialog; and a Model metrics tab (precision, recall, false alarms, confusion matrix) measured on photos the model never saw.
- **Search, filters and sorting** on the long lists: yarn stock, master data, receivables, payables, dispatch, the QC queue, wages, fabric types and buyer invites.
- **Root-cause table.** For each machine, operator, shift and yarn lot with at least 5 inspected rolls, the app compares its defective-roll rate with the rest of the mill using Fisher's exact test (exact fractions, Bonferroni-corrected for the number of groups). Groups least likely to be bad luck come first. A pattern is not proof, so check what else those rolls share.
- **Reorder suggestions.** Free stock = on hand minus what open orders still need. The date it falls below the reorder level, minus the supplier's lead time, is the "order by" date.
- **Live updates.** Screens refresh through a server-sent event stream when something changes (a roll is inspected, a truck confirmed, stock moves).
- **Buyer notices.** An in-app bell with an unread count and delay notices; a `wa.me` button opens a ready-made WhatsApp message. Sending WhatsApp messages automatically is not built (it needs a paid WhatsApp Business account).
- **Honest costing.** Costs and profit are computed from what was actually recorded (yarn used, wages, machine time). A month with orders still in progress shows their cost without an invoice, and the report says so.

## Setup

PostgreSQL 14 or newer works (the backend tests pass on 14, 16 and 18).

**macOS:** `brew install postgresql@16 uv node` · `brew services start postgresql@16` · `createdb everest` · `createdb everest_test`

**Windows:** install PostgreSQL 16 (official installer, remember the `postgres` password), Node.js LTS, Git, and uv:
`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
Then: `psql -U postgres -c "CREATE DATABASE everest"` and `psql -U postgres -c "CREATE DATABASE everest_test"`.

**Both:**
```bash
cp .env.example .env        # then edit DATABASE_URL / TEST_DATABASE_URL for your machine
                            # also set JWT_SECRET to a random value (the repo is public, so never keep the default):
                            #   uv run --directory services/api python -c "import secrets; print(secrets.token_urlsafe(48))"
npm install
npm run db:migrate
npm run db:seed             # logins, workers, 3 shifts, 10 machines, yarn types, suppliers, buyers, fabrics (safe to run again)
npm run db:demo             # optional: a mill in the middle of a working day (needs an empty database)
npm run dev                 # API on :8000, web on :3000
```

Running the tests erases every table in `TEST_DATABASE_URL`, so the test setup refuses to start unless that database's name ends in `_test` and differs from `DATABASE_URL`.

## Logins

After `npm run db:seed` (or `db:month`) every login has the password `everest123`: `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer`. Change these before showing the app to anyone outside the team. A login the owner creates in the app gets a temporary password, and its person must choose their own before using the app (the server refuses every other request until they do).

Only the `qc` login is linked to an inspector, so only it can record a quality verdict. The owner can open the photo log and the model page but cannot sign a verdict.

## The demo mill

- `npm run db:demo` loads one working day in the middle of the shift (needs an empty database).
- `npm run db:month` builds a separate database, `everest_month`, with 30 days of mill history made by the real service functions, and checks it with 22 pass-or-fail tests. It never touches `everest`. How to open it and the real numbers to expect are in `docs/demo.md`. Rebuild it right before a demo. The history includes a bad yarn lot (L-0009) that the root-cause table finds, an order that loses money to rework, a late order, a cotton shortage, an overdue supplier bill and a truck still loading.
- To run the app on the month database, set `DATABASE_URL` to it before starting the API (see `docs/demo.md`). Settings saved in the app, such as AI settings, live in the database, so they have to be entered again on a different database.
- `npm run demo:flow` (Windows, API and web running, after `db:demo`) walks the demo mill forward through the app's own endpoints so the money and dispatch pages have data.
- With `DEMO_DATA=true` in `.env` the app shows a "Demo data" badge.

A short demo path: scan a roll's QR tag (roll passport) → check a photo (the model gives the verdict, the inspector adds a remark) → scan rolls onto a truck → the buyer sees the progress → month-end profit → insights and the root-cause table → switch language and ask the Copilot a question by voice.

## The assistant and AI settings

The Copilot (owner, accountant, supervisor) and the buyer assistant answer questions by calling tools that read the mill's own data, so the numbers come from the database and not from the model. Configure the model on the **AI settings** page (owner only):

| Provider | Model name to type | Notes |
|---|---|---|
| OpenAI-compatible, Groq | `openai/gpt-oss-120b` or `llama-3.3-70b-versatile` | The Groq button fills the address. Free tier. Tick "It can call tools". |
| OpenAI-compatible, OpenAI | `gpt-4o-mini` | Paid key. |
| OpenAI-compatible, Ollama | `llama3.1` | Local, no key. |
| Anthropic | `claude-opus-5-5` | Paid key. |

After saving a key, "Show the models my key can use" lists what the key can call. API keys are stored encrypted and never shown again; type them on the page, never in a file or in the repository. The **Report card** asks the model questions whose right answers come from the data and marks it.

## Phone camera over HTTPS

Phone browsers only open the camera on HTTPS. With `npm run dev` running, on **Windows**: `npm run https` (needs Caddy: `winget install CaddyServer.Caddy`); it prints the address to open on the phone, which must be on the same Wi-Fi. On **macOS** (not yet tried on this project): `brew install caddy`, then `LAN_IP=$(ipconfig getifaddr en0) caddy run --config Caddyfile` and open `https://<that address>:8443`. The phone warns about the certificate the first time; accept it. On a Mac, macOS may ask whether `caddy` and `python` may accept incoming connections: answer Allow, or the phone cannot connect (seen on this project's Mac: the HTTPS front answered on `localhost` but connections to the Mac's own Wi-Fi address stalled until allowed).

On a phone the photo box opens the camera; on a laptop it opens the file picker.

## Vision model

The defect detector's code and its measured results are in `services/api/ml` and on the Vision model screen. `npm run dev` installs the optional `ml` group (Ultralytics). The first photo analysed takes a while because the model loads; after that it takes well under a second. Its false-alarm rate on clean cloth is not measured yet (no clean-cloth photos exist), and the screen says so. Without the `ml` group the app still works and says the vision libraries are not installed.

## Useful commands

| Command | What it does |
|---|---|
| `npm run dev` | API + web together |
| `npm run test:api` | backend tests (real Postgres `everest_test`) |
| `npm --prefix apps/web test` | web tests |
| `npm --prefix apps/web run lint` | lint the web app (oxlint) |
| `npm --prefix apps/web run build` | type-check and build the web app |
| `npm run db:migrate` | apply database migrations |
| `npm run db:month` | build the 30-day demo database `everest_month` |
| `npm run https` | Caddy HTTPS front for phones (Windows) |
| `npm run contracts` | regenerate `contracts/openapi.json` and `contracts/types.ts` after an API change |

## Troubleshooting

- **The API stops answering after a code change.** `npm run dev` runs the API with auto-reload, and open live-update connections can stall a restart. Stop it and start it again.
- **"Vision libraries are not installed."** The API was started without the `ml` group. Start it with `uv run --group ml --directory services/api uvicorn app.main:app --port 8000`, or use `npm run dev`.
- **The page shows English after choosing a language.** Reload once; if it persists, check that the web dev server was restarted after pulling.
- **A new login can't open any page.** It must choose its own password first (see Logins).
- **The roll dropdown in "Check a photo" is empty.** Only rolls waiting for quality check appear: a roll must finish dyeing first.

## Team

Built by Ridanshi Agarwal (the web app, the buyer portal, the assistant and its languages) and Hritwik Bali (the data model, the rules and calculations, the vision model, the simulated month).

## Credits

- Defect-detection experiments use [Ultralytics YOLO](https://docs.ultralytics.com/) (AGPL-3.0).
- Public training images: "Fabric Defect Detection Subset" by First Workspace Gan, Roboflow Universe, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): https://universe.roboflow.com/first-workspace-gan/fabric-defect-detection-subset
