# Team Notes

> **Summary:** Running notes between Track A (Ridanshi) and Track B (Hritwik): current status, the next task for each track, and open questions. Newest entry at the top.
> **Last updated:** 2026-10-10

---

## 2026-10-10 — Design is written up

**From:** Hritwik → Ridanshi

**Status**
- The full design is in `docs/specs/2026-10-10-textile-mill-design.md`. It's a draft under final review; I'll add a note here once it's approved.
- Stack is fixed: Next.js + TypeScript + Tailwind/shadcn web app, one FastAPI backend, local PostgreSQL, everything via `docker compose`. No Supabase.

**What Track A owns (yours)** — see §13 of the spec:
- the whole web app (every screen in §11);
- the language-model module `services/api/app/modules/llm` (§10);
- the people module `services/api/app/modules/people` (attendance, wages);
- the end-to-end demo test script.

**Next task for Track A**
- Read the spec end to end, especially §3 (architecture), §6 (rules), §11 (screens), §13 (tracks and collaboration rules).
- Don't start building yet — the step-by-step plan will land in `docs/plans/` and I'll note it here.
- Meanwhile, make sure your laptop has Docker Desktop, Node 20+, Python 3.11+ and Git working, and that your phone can reach your laptop over the same Wi-Fi.

**Ground rules (from §13)**
- Only Track B writes database migrations — ask me for column changes.
- `contracts/` changes need both of us to agree.
- Branches: `a/<topic>` for you, `b/<topic>` for me. Merge to `main` only when tests pass, the web app builds and `docker compose up` works.
- Commit messages: plain imperative subject line, optional body, nothing else.

**Questions** — add them below with your name and I'll answer here.
