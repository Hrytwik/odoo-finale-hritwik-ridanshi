# Team Notes

> **Summary:** Running notes between Track A (Ridanshi) and Track B (Hritwik): current status, the next task for each track, and open questions. Newest entry at the top.
> **Last updated:** 2026-10-10 12:17 IST

**Format:** every entry heading is `## YYYY-MM-DD HH:MM IST — title`, newest at the top, with `From: X → Y`. Entries before 2026-10-10 12:07 have a date only.

---

## 2026-10-10 12:17 IST — I am using a cloud Postgres (Neon) instead of installing PostgreSQL 16

**From:** Ridanshi → Hritwik

**Update to my 12:07 entry** (it said I would install PostgreSQL 16 locally; that is no longer the plan)
- For now my dev database is a personal Neon project (cloud Postgres). My laptop only needs `DATABASE_URL` / `TEST_DATABASE_URL` in `.env`; nothing else changes for you.
- The final choice (local Postgres, cloud, or both) is open until the end of the build. Going back to local is just a different `DATABASE_URL` followed by `npm run db:migrate` and `npm run db:seed`.

**What I need you to keep true so this works** (all already in B1, please do not change)
- The database is configured only through `DATABASE_URL` and `TEST_DATABASE_URL` in `.env`, using the `postgresql+psycopg://` form. Nothing may assume `localhost`.
- Migrations and the seed script must run cleanly on a fresh database, in order, with no manual steps.

**FYI / risks**
- Neon is running PostgreSQL **18.6**, not 16 as the spec says. I do not expect a problem (everything in the model is standard Postgres: CHECK constraints, partial unique indexes, JSONB, `SELECT … FOR UPDATE`). If a migration behaves differently on 18 for you, tell me here.
- My test database will be a separate Neon branch, with a database inside it named `everest_test` (your `test_db_fixture_talks_to_test_database` requires the name to end in `_test`). The test harness drops the whole `public` schema, so `TEST_DATABASE_URL` must never equal `DATABASE_URL`. Maybe worth a guard in `conftest.py` (refuse to run if the test database name does not end in `_test` or if the two URLs are equal). Your call, B1 is yours.
- Latency: each query from my laptop goes over the internet, so tests will be slower than on a local database.

---

## 2026-10-10 12:09 IST — This file is now `docs/HRITWIK_TEAM_NOTES.md`

**From:** Ridanshi → Hritwik

**What changed**
- `docs/TEAM_NOTES.md` was renamed to `docs/HRITWIK_TEAM_NOTES.md` (done with `git mv`, so the history follows). Nothing inside your earlier entries was edited.
- I updated the references in `A1-web-foundation.md` (my plan).

**For you to update (your files, I did not touch them)**
- `docs/specs/2026-10-10-textile-mill-design.md` §13: the repository layout and collaboration rule 6 still say `docs/TEAM_NOTES.md`.
- `docs/plans/B1-foundation.md`, last step of Task 13: it says to add an entry to `docs/TEAM_NOTES.md`.
- When you pull, `git pull` handles the rename; if you have local edits to the old file, tell me here before pushing so we don't clash.

---

## 2026-10-10 12:07 IST — Track A has read the spec and both plans

**From:** Ridanshi → Hritwik

**Status**
- I have read the spec, `docs/plans/README.md`, A1 and B1 in full. I will stay in Track A's folders only and will not touch B1 or anything under `contracts/`, `services/api` (except `modules/people` and `modules/llm` later), or migrations.
- Not started on code yet. First up is A1 Task 1 (scaffold) and A1 Task 7 (Caddy + phone camera check), neither needs your files.

**What I need from you (in this order)**
1. Push B1 Task 1 so `README.md`, `.env.example` and the root `package.json` are on `main` (I need `npm run dev` and the `db:*` scripts).
2. Push B1 Task 6 so `contracts/types.ts` and the dev users exist. A1 Tasks 2 to 6 depend on it. Please add a dated note here when it is on `main`.
3. Later, B1 Task 13: the full contract with example data, so I can build every screen against it.

**My setup (FYI)**
- My laptop has PostgreSQL 14 only. I will install 16 and create `everest` and `everest_test` before running anything.
- Node 22 and `uv` are installed. Caddy is not yet.

**Question for you**
- Plan A1 Task 5 uses `components["schemas"]["MachineCard"]`, `RollOut` and `OrderOut` for the status badges. These names come from B1 Tasks 10 and 11. Please keep those schema names and the enum values as written, or tell me here before renaming.

---

## 2026-10-10 — Spec approved, first plans ready

**From:** Hritwik → Ridanshi

**Status**
- The spec is approved: `docs/specs/2026-10-10-textile-mill-design.md`.
- **No Docker.** Everything runs natively on both laptops: PostgreSQL 16, `uv` for Python, npm for the web app. One command from the repo root starts it all: `npm run dev`. (The spec was updated to match.)
- Plan index with the full ordered backlog: `docs/plans/README.md`.
- Your first plan: `docs/plans/A1-web-foundation.md` (all commands are PowerShell). Mine: `docs/plans/B1-foundation.md`.

**Next task for Track A**
1. Windows setup from `README.md` once it lands on `main` (PostgreSQL 16 installer, Node LTS, Git, uv, create the `everest` and `everest_test` databases, copy `.env.example` to `.env` with your `postgres` password).
2. A1 Task 1 (scaffold). A1 Task 7 (phone camera check) has no dependencies — do it whenever you're blocked.
3. A1 Task 2 needs `contracts/types.ts` — it arrives with my B1 Task 6 push; I'll add a note here when it's on `main`.

**Dev logins** (after `npm run db:seed`): `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer` — password `everest123` for all.

---

## 2026-10-10 — Design is written up

**From:** Hritwik → Ridanshi

**Status**
- The full design is in `docs/specs/2026-10-10-textile-mill-design.md`.
- Stack is fixed: Next.js + TypeScript + Tailwind/shadcn web app, one FastAPI backend, local PostgreSQL. No Supabase. (Docker was later dropped — see the entry above.)

**What Track A owns (yours)** — see §13 of the spec:
- the whole web app (every screen in §11);
- the language-model module `services/api/app/modules/llm` (§10);
- the people module `services/api/app/modules/people` (attendance, wages);
- the end-to-end demo test script.

**Ground rules (from §13)**
- Only Track B writes database migrations — ask me for column changes.
- `contracts/` changes need both of us to agree.
- Branches: `a/<topic>` for you, `b/<topic>` for me. Merge to `main` only when tests pass, the web app builds and `npm run dev` works.
- Commit messages: plain imperative subject line, optional body, nothing else.

**Questions** — add them below with your name and I'll answer here.
