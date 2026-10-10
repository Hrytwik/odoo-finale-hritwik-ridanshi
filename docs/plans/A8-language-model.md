# A8 — Language-model module and AI screens

> **Summary:** Track A's eighth plan, written while building: the provider-agnostic language-model module (`modules/llm`) and its screens. The backend and the three main screens are built and tested; some wiring and screen tests are still to do (listed at the end).
> **Last updated:** 2026-10-10 17:44 IST
> **Status:** done on branch `a/web-textile`. Works end to end against the demo mill with a stand-in provider; a live check with a real provider key is the owner's step on `/settings/ai`.

**Spec:** §10 (language-model layer), §4.4 (settings tables, already in the schema, no migration), §11 (screens). The rules the module follows: the model never calculates a number, tools are read-only and fixed, every answer lists its sources, buyer tools never take a buyer id, and with no provider every AI surface says so while all number screens keep working.

## Backend (`services/api/app/modules/llm`)

| Piece | File | What it does |
|---|---|---|
| Neutral formats | `types.py` | Our own message, tool and completion types; adapters translate to and from them. |
| Key encryption | `crypto.py` | The API key is encrypted (Fernet, from `LLM_KEY_SECRET`, falling back to the login secret) before it is stored, and is never returned. A key that cannot be decrypted after the secret changes reads as "not set". |
| Adapters | `adapters.py` | `anthropic` and `openai_compatible` (OpenAI, Groq, OpenRouter, Ollama, LM Studio), over plain HTTPS JSON with no SDK, so there is nothing extra to install. Failures become `unreachable`, `auth`, `bad_request` or `server`, and the key never appears in a message. |
| Tools | `tools.py` | 11 fixed read-only tools with Pydantic input models. Each has a role list: a supervisor is not offered cost tools; a buyer gets only `get_my_orders`, `get_my_order_status`, `get_my_order_eta`. A tool outside the role's list cannot run even if the model asks. |
| Data seam | `data.py` | The only place that reads the mill's numbers, by calling the other modules' own endpoint functions (so roles and real calculations stay where they are written). When a module changes how it gets its data, only this file follows. |
| Tool loop | `engine.py` | Ask the model, run the tools it asks for, give back the results, at most 6 steps. Bad input and failing tools are reported to the model so it can try again. Results are cut at 6,000 characters. A provider failure becomes `AI_UNAVAILABLE` (503). |
| Settings | `runtime.py`, `router.py` | One saved row; defaults are Anthropic and `claude-opus-5-5`; "configured" needs a key (Anthropic) or an address (compatible). |
| Report card | `reportcard.py`, `router.py` | Up to 15 questions about the current data whose right answers are read from the data at run time; numbers are matched to the paisa after removing commas and rupee signs. Runs are saved in `llm_eval_runs`. |

| Endpoint | Roles |
|---|---|
| `GET/PUT /ai/settings` | owner |
| `POST /ai/copilot` | owner, accountant, supervisor |
| `POST /ai/buyer-assistant` | buyer |
| `POST /ai/explain-delay/{order_code}` | owner, accountant, supervisor |
| `POST /ai/recall-drafts/{lot_code}` | owner, store |
| `POST /ai/month-summary` | owner, accountant |
| `POST /ai/report-card/run`, `GET /ai/report-card` | owner |

**Tests:** `tests/test_llm_core.py` (57) and `tests/test_llm_api.py` (52): encryption, both adapters' request and reply shapes, every HTTP failure, which tools each role gets, the tool loop (retries, forbidden tools, the six-step stop), settings validation and secrecy of the key, each endpoint's roles, and the report card with a perfect, a wrong and a half-right model. All use a scripted provider; none needs a real key. The whole suite is 367 passed.

**Dependency added:** `cryptography` (in `pyproject.toml` and `uv.lock`). **Not built:** the challan photo reader (a stretch goal in the spec).

## Screens

| Route | File | Roles | What it does |
|---|---|---|---|
| `/copilot` | `pages/ai/Copilot.tsx`, `components/ai/ChatPanel.tsx` | owner, accountant, supervisor | Chat with suggested questions. Each answer has a "Where this came from" list of the figures it used. If the question fails it stays in the box. |
| `/settings/ai` | `pages/ai/AiSettings.tsx` | owner | Provider, model, address (with Groq, OpenAI and Ollama presets), a write-only API key field, what the model can do, and a button that sends one test question. |
| `/settings/ai/report-card` | `pages/ai/ReportCard.tsx` | owner | Run the report card; compare recent runs by score; every question with the right figure, the model's answer and right or wrong. |
| (components) | `components/ai/Drafts.tsx` | | Explain a delay, month summary and recall drafts, each with a Copy button. |

## Still to do in A8

Screen tests for the three AI pages; place `ExplainDelay` on the insights cards, `MonthSummary` on the owner dashboard and `RecallDrafts` on the lot page; a live run against a real provider once the owner has entered a key on the settings screen.

## Finishing notes

- The draft buttons are on their pages: "Explain this delay" on each late order in Insights, "Write a summary of the month" on Month-end, "Draft messages to buyers" on a blocked lot.
- The model is told today's date in India time, so "this month" means something.
- A request the provider refuses (for example a malformed tool call) is tried once more before an error is shown.
- Requests send a plain User-Agent: providers behind Cloudflare, Groq among them, turn away Python's default one with a 403.
- A hosted address (Groq, OpenAI) with no key is "not set up"; only an address on this computer or network may go without a key.
- Tests: `Ai.test.tsx` (Copilot, settings, report card, drafts) and the additions in `test_llm_core.py` and `test_llm_api.py`.
