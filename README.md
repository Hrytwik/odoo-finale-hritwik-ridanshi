# Everest Textile Mills

One platform for a textile mill: yarn store, production floor, quality checks, dispatch, buyer portal, wages and month-end costing.

What is in it, by role: **store** receives yarn and keeps the ledger; **supervisor** runs spinning, weaving and dyeing machines and rolls; **qc** photographs and inspects each roll (a defect-detection model suggests a verdict); **dispatch** scans rolls onto trucks and bills them; **accountant** and **owner** see receivables, payables, wages, the true cost and profit of every roll and order, delivery-date and late-order forecasts, yarn shortages and defect root causes, and can ask the assistant questions; **buyers** sign up with an invite code and follow only their own orders. The screens are in English and nine Indian languages. Everything runs locally against PostgreSQL; the language model is optional and the rest works without it.

Stack: React + Vite (`apps/web`), FastAPI + SQLAlchemy + PostgreSQL (`services/api`), a shared API contract (`contracts/`). The design is in `docs/specs/`, the build plans in `docs/plans/`, and `docs/HRITWIK_TEAM_NOTES.md` is the running log between the two tracks.

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

## Logins

After `npm run db:seed` (or `db:month`) every login has the password `everest123`: `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer`. A login the owner creates in the app gets a temporary password and its person must choose their own before doing anything else. Logins are for the demo database only; change them before any real use.

## The demo mill

- `npm run db:demo` loads one working day in the middle of the shift (needs an empty database).
- `npm run db:month` builds a separate database, `everest_month`, with 30 days of mill history made by the real service functions, and checks it with 22 pass-or-fail tests. It never touches `everest`. How to open it, and the real numbers to expect, are in `docs/demo.md`. Rebuild right before a demo.
- With `DEMO_DATA=true` in `.env` the app shows a "Demo data" badge.

## Phone camera over HTTPS

Phone browsers only open the camera on HTTPS. With `npm run dev` running, on **Windows**: `npm run https` (needs Caddy: `winget install CaddyServer.Caddy`); it prints the address to open on the phone, which must be on the same Wi-Fi. On **macOS** (not yet tried on this project): `brew install caddy`, then `LAN_IP=$(ipconfig getifaddr en0) caddy run --config Caddyfile` and open `https://<that address>:8443`. The phone warns about the certificate the first time; accept it. On a Mac, macOS may ask whether `caddy` and `python` may accept incoming connections: answer Allow, or the phone cannot connect (seen on this project's Mac: the HTTPS front answered on `localhost` but connections to the Mac's own Wi-Fi address stalled until allowed).

## Vision model

The defect detector's code and its measured results are in `services/api/ml` and on the Vision model screen. `npm run dev` installs the optional `ml` group (Ultralytics). Its false-alarm rate on clean cloth is not measured yet (no clean-cloth photos exist), and the screen says so.

## Using a hosted database (Neon) for development

Optional and for development only: the demo runs on a local PostgreSQL.

1. In Neon, create a project, then create **two databases** in it: `everest` and `everest_test` (Console → Databases, or run `CREATE DATABASE everest_test;`).
2. Click **Connect**, turn **Connection pooling off** (migrations need the direct connection), pick each database in turn and copy its connection string.
3. In `.env`, change the start of each string from `postgresql://` to `postgresql+psycopg://` and keep `?sslmode=require` at the end:
   ```
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/everest?sslmode=require
   TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/everest_test?sslmode=require
   ```
4. `npm run db:migrate`, then `npm run db:seed`.

Running the tests erases every table in `TEST_DATABASE_URL`, so the test setup refuses to start unless that database's name ends in `_test` and differs from `DATABASE_URL`. The connection string contains your password: it belongs only in `.env`, never in a commit, a note or a screenshot. Tests over the internet are slower than local ones; if that gets annoying, point only `TEST_DATABASE_URL` back at a local PostgreSQL.

## Useful commands

| Command | What it does |
|---|---|
| `npm run dev` | API + web together |
| `npm run test:api` | backend tests (real Postgres `everest_test`) |
| `npm --prefix apps/web test` | web tests |
| `npm run db:month` | build the 30-day demo database `everest_month` |
| `npm run https` | Caddy HTTPS front for phones (Windows) |
| `npm run contracts` | regenerate `contracts/openapi.json` and `contracts/types.ts` |

## Credits

- Defect-detection experiments use [Ultralytics YOLO](https://docs.ultralytics.com/) (AGPL-3.0).
- Public training images: "Fabric Defect Detection Subset" by First Workspace Gan, Roboflow Universe, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): https://universe.roboflow.com/first-workspace-gan/fabric-defect-detection-subset
