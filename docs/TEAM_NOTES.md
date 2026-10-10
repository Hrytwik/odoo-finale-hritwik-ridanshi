# Team Notes

> **Summary:** Running notes between Track A (Ridanshi) and Track B (Hritwik): current status, the next task for each track, and open questions. Newest entry at the top.
> **Last updated:** 2026-10-10

---

## 2026-10-10 — Using Neon for your development database

**From:** Hritwik → Ridanshi

Fine for development; the demo stays on a local PostgreSQL. Setup is in the new README section "Using a hosted database (Neon) for development". The four things that matter:
1. Create **two** databases in your Neon project: `everest` and `everest_test`.
2. Use the **direct** connection string (Connection pooling toggle off), start it with `postgresql+psycopg://` and end it with `?sslmode=require`.
3. The tests erase every table in `TEST_DATABASE_URL`. I added a guard (on `main` after my next push): the test run refuses to start unless that database's name ends in `_test` and differs from `DATABASE_URL`.
4. The password stays in your `.env` only. Never paste the string into a note, a commit or a screenshot; if it leaks, rotate it in the Neon Console.

Tests over the internet are slower. Time one run of `npm run test:api`; if it is painful, point only `TEST_DATABASE_URL` at a local PostgreSQL.

---

## 2026-10-10 — API contract is ready (A1 Task 2 unblocked)

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
