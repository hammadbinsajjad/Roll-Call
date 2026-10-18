# Roll-Call Backend — Implementation Plan

Status: **ready for implementation** — all questions resolved 2026-10-18, recorded in
[Section 11](#11-decisions-resolved-2026-10-18). Nothing implemented yet.

Confirmed with the project owner (2026-10-18):
- The architecture diagram's "Jira API" is the **Linear** integration (`ingestion/linear.py`)
  — the diagram predates the Linear switch.
- **All browser traffic goes through this backend API** — no direct DB access from the
  frontend, including the member-summary reads (the diagram's direct DB→Web UI arrow is
  just shorthand for "via the API").

---

## 1. Context & current state

| Piece | State |
|---|---|
| `ingestion/` | Working pipeline: GitHub + Linear → LLM summary → MongoDB (`roll_call` DB). Reads `repos` and `team_members` collections, writes `daily_reports`. |
| `backend/` | Boilerplate only: FastAPI app with `/health` and a placeholder `/embed`. |
| Frontend | Plain HTML/CSS/JS in the `lunar-clover` worktree. Its `temp-mock/serve.py` is a **precise API contract** we must match (shapes, status codes, error format). |
| External AI | Backboard.io — threads (chats), one assistant, documents (RAG over member data). |

**Framework: FastAPI.** Already in the boilerplate, Pydantic request validation for free
(we need strict input limits anyway), trivially deploys to Render with uvicorn, and the
sync-style `def` endpoints keep the whole codebase simple (no async pitfalls). Flask would
mean hand-rolling validation, error handling, and OpenAPI — no speed advantage.

**HTTP/data stack (all sync, no async complexity):** `pymongo` (same driver the ingestion
uses), `httpx` for Backboard REST calls, `PyJWT` for tokens, `bcrypt` for passwords,
`slowapi` for rate limiting.

---

## 2. External API contract (must match the frontend exactly)

The FE mock (`frontend/temp-mock/serve.py`) defines these shapes. **The real backend must
be a drop-in replacement**, including error format.

- Auth header: `Authorization: Bearer <token>` (FE stores token in localStorage).
- Success responses are plain JSON objects as below.
- **Error responses are always `{"error": "<message>"}`** with a 4xx/5xx status. FastAPI's
  default `{"detail": ...}` would break the FE — we add a global exception handler.
- `401` makes the FE clear the session and redirect to login.

| Method & path | Auth | Request body / params | Response |
|---|---|---|---|
| `POST /auth/register` | — | `{username, password}` | `201 {token, username}`; `409 {"error": "username already taken"}` |
| `POST /auth/login` | — | `{username, password}` | `200 {token, username}`; `401 {"error": ...}` |
| `GET /config` | Bearer | — | `{repos: ["owner/repo", ...], team_members: [{github_username, linear_email, member_name}]}` |
| `POST /config/repos` | Bearer | `{name: "owner/repo"}` | `{ok: true, repos: [...]}` (full list) |
| `DELETE /config/repos` | Bearer | `{name: "owner/repo"}` | `{ok: true, repos: [...]}` |
| `POST /config/members` | Bearer | `{github_username, linear_email, member_name}` | `{ok: true, team_members: [...]}` (full list) |
| `DELETE /config/members` | Bearer | `{github_username}` | `{ok: true, team_members: [...]}` |
| `GET /member-summary?date=YYYY-MM-DD` | Bearer | `date` (required; validated ISO) | `[{member_name, github_username, linear_email, date, summary}]` (empty list if none) |
| `GET /member-summary/{member_id}` | Bearer | `member_id` = github_username **or** linear_email; optional `?date=YYYY-MM-DD` (default: latest report) | `{member_name, github_username, linear_email, date, summary}` or `404` |
| `GET /chats` | Bearer | — | `[{chat_id, title, created_at, updated_at}]` sorted by `updated_at` desc |
| `POST /chat` | Bearer | `{message}` | `{chat_id, reply}` — creates a new chat |
| `GET /chat/{chat_id}` | Bearer | — | `{chat_id, messages: [{role, content, created_at}]}` |
| `POST /chat/{chat_id}` | Bearer | `{message}` | `{reply}` — continues the conversation |
| `POST /embed` | **Service token** (see §6) | `{"data": <any JSON>, "filename"?: "..."}` — the `data` object is uploaded **whole** to Backboard as one `.json` document | `{document_id, filename, status}` |

Notes:
- Your brief said `/login & /register`; the FE already calls **`/auth/login` and
  `/auth/register`** — the plan follows the FE.
- `GET /config` and `GET /member-summary` are **not** auth-guarded in the mock, but every
  page that calls them requires login. The real backend will require a Bearer token on
  everything except `/auth/*` and `/health`.
- The FE's `API_BASE` is `http://localhost:8787` → dev server runs on port 8787, and
  `frontend/js/config.js` gets pointed at the Render URL at deploy time.
- Chat responses are **non-streaming** (the FE waits for the full `{reply}`). Backboard
  supports SSE streaming, but v1 keeps the simple contract.

---

## 3. Data model (MongoDB `roll_call` DB — shared with ingestion)

Collections the **ingestion already owns** (backend is read-only except config):

- `repos` — `{name: "owner/repo"}` (read+write via `/config`)
- `team_members` — `{github_username, linear_email, member_name}` (read+write via `/config`)
- `daily_reports` — ingestion writes `{date, github_username, linear_email, member_name,
  input_data, summary, stored_at}`; backend **reads only** for `/member-summary*`.
  Index: `{date: 1, github_username: 1}` (ingestion upserts on this key; we query on it).

New collections the backend owns — exactly **two**:

- `users`
  ```
  {username, password_hash, created_at,
   usage_date: "YYYY-MM-DD", usage_count: int}    unique index on username
  ```
  `usage_*` is the per-UTC-day chat-message counter behind the daily cap (§6) — rolled
  over in place when `usage_date` is behind today, so no separate `usage` collection.
- `chats`
  ```
  {chat_id: "uuid4-hex",                          unique index
   username,                                      ownership — every query filters on it
   thread_id: "<backboard thread uuid>",          index on {username, updated_at}
   title,                                         first user message, truncated ~60 chars
   message_count,                                 count only — +2 per turn (user+assistant)
   created_at, updated_at}
  ```
  **Message bodies are not stored** (decision Q4): the Backboard thread holds the history
  and `GET /chat/{id}` fetches it from there. We keep only counts — the per-chat cap
  reads `message_count`, the per-day cap reads `users.usage_count`.

`chat_id` is our own UUID string — Backboard's `thread_id` stays internal, exactly as you
specified. It's stored on the chat doc but **never returned by any endpoint**.

---

## 4. Auth

- **Register/login**: username + password (FE only has those two fields). Password hashed
  with bcrypt. `409` on duplicate username.
- **Token**: JWT (HS256) with `{sub: username, exp}` — **2-day expiry** (decision Q8),
  no refresh tokens; after 2 days the user logs in again. This is an in-and-out demo,
  not a production product — one token in localStorage is enough. Signed with
  `JWT_SECRET` env var. Stateless verification via a `get_current_user` dependency.
- Every non-auth endpoint resolves the token → username → ownership checks on chats.

---

## 5. Backboard integration (`services/backboard.py`)

Thin REST client over `https://app.backboard.io/api` with `X-API-Key` (from
`BACKBOARD_API_KEY`), using `httpx`. Endpoints used:
`POST /threads/messages`, the thread-messages listing endpoint (serves `GET /chat/{id}`
history — confirm its exact path on docs.backboard.io → *Conversation threads* at
implementation time), `POST /assistants/{id}/documents`, `GET /documents/{id}/status`,
`GET /assistants/{id}/documents`, `DELETE /documents/{id}`.

**Fallback note:** `GET /chat/{chat_id}` depends on that thread-messages listing endpoint,
which isn't in the doc pages read so far (it's on the *Conversation threads* page). If it
behaves differently than expected, the fallback is a slim local message cache — but try
the Backboard endpoint first.

**Assistant**: exactly **one** shared assistant for the whole app, created manually in the
Backboard web UI — its id is passed via the `BACKBOARD_ASSISTANT_ID` env var (required).
The backend never creates assistants. Rationale:
- Documents uploaded at the **assistant** level are shared across all threads → the member
  data RAG works for every chat, which is what we want (it's team-wide data).
- **Memory stays `off`** (Backboard's memory is per-assistant and shared across threads —
  enabling it would leak one user's conversation facts to another).
- Per-user isolation comes from thread-per-chat + our ownership checks.

**Chat flow** (`POST /chat` and `POST /chat/{id}`):
1. Auth + quota checks (chat count, message count, daily message budget) — **before** any
   Backboard call, so rejected users cost us nothing.
2. `POST /threads/messages` with `{content, thread_id (if continuing), assistant_id,
   system_prompt, stream: false, memory: "off"}`. First message of a new chat: omit
   `thread_id`; Backboard creates it and we store it on the chat doc.
3. Bump `message_count` by 2 (user + assistant) and `updated_at` on the chat doc; bump
   the user's `usage_count` by 2 (rolling `usage_date` forward if it's behind today);
   return `{reply}` / `{chat_id, reply}`. Message bodies are not persisted (Q4) —
   `GET /chat/{id}` fetches history from the Backboard thread and maps it to
   `{role, content, created_at}`.
4. Backboard errors → `502 {"error": "AI service unavailable"}` (never leak upstream
   details), timeout ~60s.

System prompt (env-overridable): Roll-Call's team-reporting assistant — answers questions
about team members' daily work, grounded in the uploaded member documents.

**`/embed` flow** (called by the ingestion pipeline, per the architecture diagram):
1. Authenticate with a **service token** — `X-Service-Token: <SERVICE_TOKEN>` header. It's
   a **shared secret we invent ourselves** (e.g. `openssl rand -hex 32`), not something
   from a provider: one copy in Render's env for the backend, the same value in
   `ingestion/.env` for the caller. Machine-to-machine — the only endpoint not reachable
   with a user JWT.
2. Request body is `{"data": <anything>}` — the `data` object is written out **whole** as
   one `.json` file and uploaded to Backboard (which accepts `.json` docs natively). No
   parsing, reshaping, or per-member splitting on our side (decision Q3). Optional
   `filename` field; default is a content hash (`sha256(data)[:16].json`).
3. **Idempotent re-ingest**: `GET /assistants/{id}/documents`, `DELETE /documents/{id}`
   for any existing doc with the same filename, then upload — re-runs replace instead of
   piling up duplicate RAG documents. (Done via the Backboard listing API; no local
   `documents` collection needed.)
4. `POST /assistants/{assistant_id}/documents` (multipart) → return
   `{document_id, filename, status}`. Indexing (`pending → indexed`) finishes on
   Backboard's side; `GET /documents/{id}/status` exists for debugging but we don't poll.

---

## 6. Abuse prevention & rate limiting (layered)

You're right that AI spend is the real risk. The strategy: **cheap rejections in front of
every expensive call**, with persistent limits in Mongo so they survive redeploys.

1. **Per-IP rate limits** (slowapi, in-memory — fine for a single Render instance):
   - `POST /auth/*`: 10/min (brute-force + bot signup)
   - chat endpoints: 10/min per user
   - everything else: 30/min
   - `POST /embed`: 20/min + service token required
   *(If we ever scale to multiple instances, swap slowapi's storage for Redis — noted as
   a limitation, not built now.)*
2. **Per-user persistent quotas** (checked in Mongo before any Backboard call):
   - **≤ 10 chats per user** (lifetime)
   - **≤ 50 messages per chat** (counted on the chat doc)
   - **≤ 100 chat messages per user per UTC day** (reset daily — this is the hard cost cap)
3. **Input limits** (Pydantic): `message` 1–2000 chars; repo name must match
   `owner/repo` regex; member fields length-capped; `date` must be valid ISO.
4. **Secrets server-side only**: Backboard key and service token never leave the server.
   CORS locked to `CORS_ORIGINS` env (the FE origin).
5. **Registration stays open** (decision Q1 — public demo, unknown audience). Accepted
   risk: the per-IP limit on `POST /auth/*` (10/min) and the per-day message cap bound
   what a single signup can burn. Keep the provider/Backboard budget caps as backstop.
6. Second line of defense (yours, outside this code): budget caps on the LLM provider and
   on Backboard, as you planned.

---

## 7. Project layout

```
backend/
  .env.example             env template — committed; real `.env` stays out of git
  requirements.txt          fastapi, uvicorn[standard], pymongo, httpx,
                            pyjwt, bcrypt, slowapi, pydantic
  app/
    main.py                 app creation, CORS, rate limiter, exception handler
                            (maps all errors to {"error": ...}), router mounting
    config.py               env settings (single place)
    db.py                   Mongo client + collection/index helpers (startup index setup)
    auth.py                 bcrypt hashing, JWT create/verify, get_current_user dep
    models.py               Pydantic request/response models (incl. length limits)
    routers/
      auth.py               /auth/register, /auth/login
      config.py             /config + /config/repos + /config/members
      member_summary.py     /member-summary, /member-summary/{member_id}
      chats.py              /chats, /chat, /chat/{chat_id}
      embed.py              /embed (service-auth)
    services/
      backboard.py          Backboard REST client
```

Deliberately no test framework scaffolding unless requested — a few `httpx` smoke curls
against the running server are the fastest verification for a project on this timeline.

## 8. Environment variables

| Var | Used for |
|---|---|
| `MONGO_DB_CONNECTION_STRING` | MongoDB Atlas (same as ingestion) |
| `JWT_SECRET` | JWT signing |
| `BACKBOARD_API_KEY` | Backboard `X-API-Key` |
| `BACKBOARD_ASSISTANT_ID` | required — assistant created manually in the Backboard UI |
| `BACKBOARD_PROVIDER` / `BACKBOARD_MODEL` | chat model: **`openrouter` / `google/gemma-4-26b-a4b-it`** (Q6) |
| `SERVICE_TOKEN` | `/embed` machine auth — shared secret we generate (`openssl rand -hex 32`); same value goes in `ingestion/.env` |
| `CORS_ORIGINS` | FE origin(s), comma-separated |
| `CHAT_MAX_MESSAGES` / `CHAT_MAX_CHATS` / `CHAT_DAILY_LIMIT` | quota knobs (defaults 50 / 10 / 100) |

A committed `backend/.env.example` documents every var and marks which are secrets
(`# SECRET` lines carry no real values — devs copy to `.env` and fill in; real `.env`
never gets committed):

```bash
# --- SECRET: real values live only in .env / Render env ---
MONGO_DB_CONNECTION_STRING=  # SECRET — MongoDB Atlas connection string
JWT_SECRET=                  # SECRET — e.g. openssl rand -hex 32
BACKBOARD_API_KEY=           # SECRET — Backboard X-API-Key
SERVICE_TOKEN=               # SECRET — shared with ingestion/.env; openssl rand -hex 32

# --- Non-secret config ---
BACKBOARD_ASSISTANT_ID=      # from the Backboard web UI (required)
BACKBOARD_PROVIDER=openrouter
BACKBOARD_MODEL=google/gemma-4-26b-a4b-it
CORS_ORIGINS=http://localhost:8787
CHAT_MAX_MESSAGES=50
CHAT_MAX_CHATS=10
CHAT_DAILY_LIMIT=100
```

## 9. Deployment (Render)

- **Web Service** from the repo, root directory `backend/`,
  start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Env vars above set in the Render dashboard; Mongo is Atlas (external).
- FE deployed as a Render **Static Site** (or any static host) with `js/config.js`
  `API_BASE` pointed at the service URL; CORS env matches it.
- Cold starts on the free tier are acceptable; rate-limit counters reset on redeploy
  (the persistent quotas in Mongo don't — that's why the cost caps live there).
- The ingestion cron (GitHub Actions) keeps running unchanged and additionally POSTs to
  `/embed` after each `store_member_data` (one small addition to `ingestion/ingestion.py`).

## 10. Implementation order (≈ half a day of work)

1. Skeleton: config, db, error handler, CORS, `/health` — boots locally on :8787.
2. Auth (register/login/JWT dependency) + users collection.
3. Config endpoints (repos + team members) — trivial, unblocks the FE config page.
4. `/member-summary*` read endpoints over `daily_reports`.
5. Backboard client + `/chat*` with quotas.
6. `/embed` + ingestion hook (one POST per stored member-day).
7. Rate limits pass, end-to-end smoke run against the real FE.

## 11. Decisions (resolved 2026-10-18)

1. **Registration: open** — public demo, unknown audience, no invite code. Mitigated by
   per-IP auth limits + per-user daily caps + provider budget caps.
2. **`/member-summary/{member_id}`**: optional `?date=` (ISO), defaults to the member's
   **latest** report; `404` if no report exists for that date / at all.
3. **`/embed` payload**: `{"data": <JSON>}` accepted as-is and uploaded **whole** to
   Backboard as a `.json` document. Optional `filename` for idempotent replace
   (default: content hash). No parsing or reshaping on our side.
4. **Chat messages**: counts only in our DB (`chats.message_count`, `users.usage_*`);
   history lives in Backboard and is fetched on `GET /chat/{id}`.
5. **`/config` editing**: any authenticated user.
6. **Chat model**: `google/gemma-4-26b-a4b-it` via OpenRouter
   (`BACKBOARD_PROVIDER=openrouter`, `BACKBOARD_MODEL=google/gemma-4-26b-a4b-it`).
7. **Quotas**: 10 chats/user, 50 msgs/chat, 100 msgs/user/day — as planned, env knobs.
8. **JWT**: 2-day expiry, no refresh — re-login after 2 days. Demo scope, not production.

## 12. Explicitly out of scope (v1)

- Streaming chat responses (FE contract is non-streaming; SSE can be added later).
- Refresh tokens / logout / password reset.
- Admin roles (any authenticated user can edit `/config` — decision Q5).
- Redis-backed rate limiting (single Render instance → in-memory is fine).
- Any changes to `ingestion/` beyond the one-line `/embed` POST hook.
