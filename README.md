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
npm install
npm run db:migrate
npm run db:seed
npm run dev                 # API on :8000, web on :3000
```

## Useful commands

| Command | What it does |
|---|---|
| `npm run dev` | API + web together |
| `npm run test:api` | backend tests (real Postgres `everest_test`) |
| `npm run contracts` | regenerate `contracts/openapi.json` and `contracts/types.ts` |
