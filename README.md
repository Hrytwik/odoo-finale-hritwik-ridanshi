# Everest Textile Mills

One platform for a textile mill: yarn store, production floor, quality checks, dispatch, buyer portal, wages and month-end costing.

## Setup

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
npm run db:seed
npm run dev                 # API on :8000, web on :3000
```

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
| `npm run contracts` | regenerate `contracts/openapi.json` and `contracts/types.ts` |

## Credits

- Defect-detection experiments use [Ultralytics YOLO](https://docs.ultralytics.com/) (AGPL-3.0).
- Public training images: "Fabric Defect Detection Subset" by First Workspace Gan, Roboflow Universe, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): https://universe.roboflow.com/first-workspace-gan/fabric-defect-detection-subset
