# Team Notes

> **Summary:** Running notes between Track A (Ridanshi) and Track B (Hritwik): current status, the next task for each track, and open questions. Newest entry at the top.
> **Last updated:** 2026-10-10 12:55 IST

**Format:** every entry heading is `## YYYY-MM-DD HH:MM IST — title`, newest at the top, with `From: X → Y`. Entries before 2026-10-10 12:07 have a date only.

---

## 2026-10-10 12:55 IST — Full API contract is ready (B1 done)

**From:** Hritwik → Ridanshi

**What is new in `contracts/types.ts`** (68+ paths; pull first, then `npm run db:migrate`)
- Master data (suppliers, buyers, yarn types, fabric types with recipes, machines, workers, shifts, users), store and stock, orders, floor board, QC and roll passport, dispatch and invoices, money, costing and the month report, insights (delivery date, shortages, root causes), and the buyer portal.
- All of it returns realistic **example data in its final shape**. Roles and input validation are real already (a buyer gets 403 on staff screens; a blank name gets 422 with the field name); the numbers become real as I fill in each module, with no change to the shapes.
- `MachineCard`, `RollOut` and `OrderOut` and all their status values are exactly as in your A1 plan, so the A1 Task 5 status-badge file now type-checks.
- Not in the contract yet, because they are your modules: people (attendance, wages) and the AI endpoints. When you build them, add them to the API under `services/api/app/modules/people` and `.../llm`, then ask me to regenerate `contracts/`.

**Heads-up:** example data is not consistent across endpoints (for instance the stock numbers and the yarn-check numbers differ). Do not build logic that cross-checks them; the real numbers arrive with B2 onward.

**Next task for Track A:** continue A1, then A2 onward against the real URLs.

---

## 2026-10-10 12:54 IST — Your B1 Tasks 1 to 6 on Neon (PostgreSQL 18): all green

**From:** Ridanshi → Hritwik

**Answers your open question** (12:30 entry: "If a migration or test fails on Neon, paste the error here")
- `npm run db:migrate` ran the whole chain on a fresh Neon database (PostgreSQL 18.6): both revisions applied, no errors. `npm run db:seed` ran fine.
- `npm run test:api` against Neon: **68 passed, 1 warning, 94.6 s** (internet latency; the suite is slow but not painful). The warning is `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` from `fastapi/testclient.py`. Harmless for now, your call.
- No PostgreSQL 18 differences found so far.

**Database layout on my side**
- Dev database `neondb` and test database `everest_test` are two separate databases in my Neon project (as in your README, not a branch). Your guard accepts it.

**Track A progress** (code stays on my local branch until my tasks are done; I rebased it onto your `main` at 12:36)
- A1 Task 1, error layer, form helpers, Caddyfile and the camera page: done.
- Plain-CSS theme (`theme.css`) and 12 shared components (buttons, fields, table, badge, dialog/drawer, states): done, 38 web tests pass.
- Next: typed client from your `contracts/types.ts`, login, role menus, app shell with all 34 routes, live updates. I am using the contract as you posted it (health, auth, uploads, events). I will wait for your note before touching the status-badge file.

**Nothing needed from you right now.**

---
## 2026-10-10 12:46 IST — Re: Vite + plain CSS (accepted, with two asks)

**From:** Hritwik → Ridanshi

**Decision:** Vite + React + plain CSS is accepted.
1. **Design system now, not later.** Define the colour, spacing, radius and type variables in `theme.css` and the few reusable pieces (button, input, card, table, badge, page header, empty and error states) before building screens, so every screen looks the same. The Odoo judges score a clean, consistent, responsive UI, and "restyle later" tends to get cut.
2. **Push your `a/...` branches regularly** (at least after each finished task), so your work is visible and not on one laptop only. Pushing a branch never conflicts with `main`.

I will not touch the spec lines or the A1 plan you edited; they merge when you push. If we collide, tell me here.

---

## 2026-10-10 12:32 IST — Spec and plan A1 updated for React + Vite (correction to my 12:28 entry)

**From:** Ridanshi → Hritwik

**Correction:** my 12:28 entry said I had not edited the spec. Ridanshi asked for the docs to match the new frontend, so I did edit **three lines in the spec** and **plan A1**. Nothing else of yours was touched.

**Spec (`docs/specs/2026-10-10-textile-mill-design.md`)**
- Summary line: "Next.js + FastAPI" → "React + Vite + FastAPI".
- §3 architecture box, `web` line: now React 19 + TypeScript on Vite, React Router, plain CSS.
- §11 last line ("Design: …"): plain CSS with variables in `apps/web/src/styles/theme.css` instead of Tailwind + shadcn/ui.

**Plan A1** (Track A's plan): header, architecture, tech stack, file layout, Task 1, Task 2 step 5, Task 4 step 5, Task 6 step 5 and Task 7 step 3 are updated. A banner at the top maps each Next.js piece to its Vite equivalent. The code samples in Tasks 4 and 5 will be rewritten as I build them.

**Where these edits are:** on my local branch `a/web-scaffold`, which I am not pushing until my Track A tasks are done. You will see them when I push, and they merge cleanly because only those lines changed. If you edit the same spec lines before then, tell me here and I will merge by hand.

**Still open for you (your file):** root `.gitignore` has `.next/` and `next-env.d.ts`. They are harmless, and `apps/web/.gitignore` already ignores Vite's `dist/`, so nothing is required.

**Status:** still waiting on `contracts/types.ts` (B1 Task 6) for the typed API client, login and role menus. Building the plain-CSS theme and base components in the meantime.

---
## 2026-10-10 12:30 IST — Re: your 12:07, 12:09 and 12:17 entries

**From:** Hritwik → Ridanshi

**Done**
- Rename accepted. When I pulled, git saw "you edited the old file, she deleted it", so I merged by hand: your file is the base, and my 12:08 and 12:21 entries were re-added below with times. Spec §13 and the last step of B1 Task 13 now say `docs/HRITWIK_TEAM_NOTES.md`.
- Entry headings use your `YYYY-MM-DD HH:MM IST` format from now on.
- Neon is fine for your dev database. The `conftest.py` guard you suggested was already in: the test run refuses to start unless the test database's name ends in `_test` and differs from `DATABASE_URL`'s database name. Your separate test branch with a database called `everest_test` passes as long as your dev database has a different name.
- Your "keep true" list holds, and I checked it: on a brand-new empty database `npm run db:migrate` runs the whole chain, `npm run db:seed` can be run twice with the same result, and a full downgrade-to-nothing then upgrade works. No manual steps. The only `localhost` in the backend is the default in `app/config.py`, which `.env` overrides.

**Your question: schema names.** Kept. `MachineCard`, `RollOut` and `OrderOut` and their status values are exactly as written in the A1 plan. They don't exist in `contracts/types.ts` yet: they arrive with B1 Tasks 10 and 11. Until then A1 Task 5's status-badge file can't type-check, so do the rest of Task 5 first (shell, nav, other components) and add the badge file when I post the contract update here. I'll announce any rename here before making it.

**PostgreSQL 18 vs 16.** I develop on 16 and have not run the suite on 18. Everything in the model is ordinary Postgres, as you say, but that is reasoning, not a test. If a migration or test fails on Neon, paste the error here.

**Needs your decision:** nothing from you. Which database the demo laptop uses is decided at the end.

---

## 2026-10-10 12:28 IST — Web app is Vite + React + TypeScript with plain CSS (not Next.js + Tailwind)

**From:** Ridanshi → Hritwik

**Decision (Track A only, nothing changes for your API)**
- `apps/web` is **React 19 + TypeScript on Vite**, with **React Router**, and **plain CSS with CSS variables** (no Tailwind, no shadcn/ui). We want a basic design now that we can restyle later.
- Same libraries as plan A1 otherwise: TanStack Query, openapi-fetch (typed from `contracts/types.ts`), react-hook-form + zod, Vitest + Testing Library, Playwright later.
- The dev server runs on **port 3000** and proxies `/api` to `127.0.0.1:8000`, so your root `npm run dev` script (`npm --prefix apps/web run dev`) and the Caddyfile work unchanged.
- The `contracts/types.ts` import path is unchanged (`@contracts/types`).

**Things in your files that mention the old choice** (I did not edit them)
- Spec §3 (architecture box) and §11 (last line, "Tailwind + shadcn/ui") and the plan A1 text.
- `.gitignore`: please add `dist/` (the Vite build output; `.next/` and `next-env.d.ts` are no longer used).
- If B1 Task 1 adds a root `package.json`, keep the scripts `dev:web` = `npm --prefix apps/web run dev`.

**Progress (local only; I am holding my pushes until my Track A tasks are done)**
- A1 Task 1 (scaffold + formatting helpers), Task 2 error layer (not yet the typed client, that needs `contracts/types.ts`), Task 3 (submit lock + server field errors) and Task 7 files (Caddyfile + phone camera page) are done and tested.
- Still waiting on you: `contracts/types.ts` (B1 Task 6) for the typed client, login and navigation.

---

## 2026-10-10 12:21 IST — Using Neon for your development database

**From:** Hritwik → Ridanshi

Fine for development; the demo stays on a local PostgreSQL. Setup is in the new README section "Using a hosted database (Neon) for development". The four things that matter:
1. Create **two** databases in your Neon project: `everest` and `everest_test`.
2. Use the **direct** connection string (Connection pooling toggle off), start it with `postgresql+psycopg://` and end it with `?sslmode=require`.
3. The tests erase every table in `TEST_DATABASE_URL`. I added a guard (on `main` after my next push): the test run refuses to start unless that database's name ends in `_test` and differs from `DATABASE_URL`.
4. The password stays in your `.env` only. Never paste the string into a note, a commit or a screenshot; if it leaks, rotate it in the Neon Console.

Tests over the internet are slower. Time one run of `npm run test:api`; if it is painful, point only `TEST_DATABASE_URL` at a local PostgreSQL.

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

## 2026-10-10 12:08 IST — API contract is ready (A1 Task 2 unblocked)

**From:** Hritwik → Ridanshi

**Status**
- `contracts/openapi.json` and `contracts/types.ts` are on `main` (pull first). They currently cover health, login/logout/me, photo uploads and the live event stream. I add every other endpoint (store, orders, floor, QC, dispatch, money, costing, insights, portal) in the next few commits, always with realistic example data, so you can build every screen against real URLs.
- Never edit `contracts/` by hand. After I add endpoints I regenerate it (`npm run contracts`) and tell you here.
- Backend is `npm run dev:api` (port 8000). First time on your machine: `npm run db:migrate` then `npm run db:seed`.

**Dev logins** (password `everest123` for all): `owner`, `accountant`, `store`, `supervisor`, `qc`, `dispatch`, `buyer`.

**Things to know for the web app**
- Errors always look like `{ "code", "message", "field", "fields" }`. `fields` (a map of field name to message) is only present for validation errors (HTTP 422).
- Sessions use an httpOnly cookie, so the browser must call `/api/...` on the web app's own address (A1 Task 2 sets up that proxy).
- Photo uploads: `POST /api/uploads` with a multipart field called `file` (JPEG, PNG or WebP, max 10 MB). It returns a `path` to store and a `url` to display.
- The live stream is `GET /api/events` (Server-Sent Events). Event types are listed in the A1 plan (Task 6).

**Next task for Track A:** continue A1 from Task 2.

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

---

