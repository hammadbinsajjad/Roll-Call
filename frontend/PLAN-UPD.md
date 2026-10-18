# Roll-Call Frontend — Implementation Plan (v2.1, decisions resolved)

> **v2.1 changes** (see §10): persisted selected date + Today button on summaries;
> proper markdown typography for rendered summaries and chat replies.

Goal: a clean, modern, responsive static frontend (HTML + CSS + JS, no build step) for
Roll-Call, developed entirely against a local mock API (`frontend/temp-mock/`) so no
frontend code hardcodes data. `temp-mock/` is fully deletable at the end.

All open questions from v1 are resolved (see §9).

---

## 1. Tech stack

**Plain HTML + CSS + vanilla JS, no framework, no build step.**

- **Multi-page site** (one `.html` per page) — static hosts serve it with zero routing config.
- **Shared CSS/JS** included by every page (nav, auth guard, API client).
- **Markdown rendering**: vendored `marked` + `DOMPurify` in `frontend/vendor/`
  (committed, no CDN at runtime). LLM output is rendered as markdown and sanitized
  before insertion.
- **Fonts**: Inter via Google Fonts `<link>` with a system-font fallback stack.

## 2. Design system — "Terminal Green"

Dark, professional, dev-tool aesthetic (Linear / Vercel dashboard feel), green + black.

**Colors live in a single JS object** (`THEME` in `js/config.js`) and are applied as CSS
custom properties at load time by `js/theme.js` (loaded synchronously in `<head>`).
`css/tokens.css` carries the same values as fallbacks so nothing flashes unstyled.
To re-skin the whole site, edit the one object — nothing else.

| Token | Default | Use |
|---|---|---|
| `--bg` | `#0A0F0C` (near-black, green-tinted) | page background |
| `--surface` | `#111915` | cards, panels, inputs |
| `--surface-2` | `#182420` | hover states, nested panels |
| `--border` | `#223028` | hairlines, card borders |
| `--text` | `#E6EFE9` | primary text |
| `--text-dim` | `#8CA396` | secondary text, labels |
| `--accent` | `#34D399` (emerald) | primary buttons, links, active nav, highlights |
| `--accent-dim` | `#0F3B2E` | accent backgrounds, badges, focus rings |
| `--danger` | `#F87171` | delete/error states |

- Branding: wordmark **"Roll-Call"** only, no logo.
- Radius 10px, hairline borders over shadows, generous whitespace.
- Typography: Inter 400/500/600; ~15px body; monospace for repo names, usernames, ids.
- Components (`css/components.css`): buttons (primary/ghost/danger), inputs with focus
  rings, cards, badges, tables that collapse to stacked cards on mobile, empty states,
  toasts, confirm modal, skeleton loaders, chat bubbles.

## 3. File structure

```
frontend/
├── PLAN.md
├── index.html                # redirect -> summaries.html or login.html
├── login.html
├── register.html
├── summaries.html            # member standup summaries (dashboard)
├── config.html               # repos + team members
├── chats.html                # chat list
├── chat.html                 # chat interface (?id=<chat_id>; no id = new chat)
├── css/
│   ├── tokens.css            # CSS variables (fallbacks for the THEME object)
│   ├── base.css              # reset, shell, nav, responsive breakpoints
│   └── components.css        # buttons, cards, forms, tables, toasts, chat, skeletons
├── js/
│   ├── config.js             # ROLLCALL = { API_BASE, THEME }  <- the one config file
│   ├── theme.js              # applies THEME to CSS vars (sync, in <head>)
│   ├── api.js                # fetch wrapper: base URL, auth header, JSON, errors
│   ├── auth.js               # token get/set, login/register/logout, route guard
│   ├── ui.js                 # nav render, toast, escapeHtml, dates, empty states
│   ├── markdown.js           # marked + DOMPurify wrapper
│   └── page-*.js             # one file per page (login, register, summaries,
│                             #   config, chats, chat)
├── vendor/
│   ├── marked.min.js
│   └── purify.min.js
└── temp-mock/                # DELETE WHEN DONE — never imported by frontend code
    ├── README.md
    ├── serve.py              # mock API server (stdlib only), port 8787, CORS on
    └── data/
        ├── auth.json
        ├── config.json
        ├── member-summary-YYYY-MM-DD.json
        ├── chats.json
        ├── chat-<id>.json
        └── chat-reply.json
```

## 4. API layer & auth

`js/api.js` is the **only** place that knows URLs. `js/config.js` holds `API_BASE`
(`http://localhost:8787` in dev, the Render URL in prod — one constant at deploy).

**Auth (token-based, confirmed):**

- `POST /auth/register` `{username, password}` → `201 {token, username}`
- `POST /auth/login` `{username, password}` → `200 {token, username}`
- Token in `localStorage`, sent as `Authorization: Bearer <token>`.
- `401` from any call → clear token, redirect to `login.html`.
- All pages except login/register run a route guard on load.

### Endpoint contracts (final)

| Endpoint | Request | Response |
|---|---|---|
| `GET /config` | — | `{repos: ["owner/repo", ...], team_members: [{github_username, linear_email, member_name}, ...]}` |
| `POST /config/repos` | `{name}` | `{ok: true, repos: [...]}` — upsert by `name` |
| `DELETE /config/repos` | `{name}` (JSON body) | `{ok: true, repos: [...]}` |
| `POST /config/members` | `{github_username, linear_email, member_name}` | `{ok: true, team_members: [...]}` — upsert by `github_username` |
| `DELETE /config/members` | `{github_username}` (JSON body) | `{ok: true, team_members: [...]}` |
| `GET /member-summary?date=YYYY-MM-DD` | — | `[{member_name, github_username, linear_email, summary, date}]` — `summary` is markdown; empty list when no data |
| `GET /chats` | — | `[{chat_id, title, created_at, updated_at}]` |
| `GET /chat/{chat_id}` | — | `{chat_id, messages: [{role: "user"\|"assistant", content, created_at}]}` |
| `POST /chat` (new chat) | `{message}` | `{chat_id, reply}` — **server returns the new chat_id** |
| `POST /chat/{chat_id}` (continue) | `{message}` | `{reply}` |

Notes:
- Config is **per-item** (confirmed) — the UI adds/removes with an immediate API call
  per item, no bulk Save button.
- Repos/members are **removable** (confirmed) via a confirm modal + `DELETE`.
- Chat timestamps are ISO strings (UTC). New-chat flow: after `POST /chat` returns a
  `chat_id`, the frontend does `history.replaceState` to `chat.html?id=<chat_id>` so a
  refresh continues the same conversation.

## 5. Pages

### 5.1 `login.html` / `register.html`
Centered card on the dark background (subtle green glow), "Roll-Call" wordmark,
username + password fields, loading state on submit, inline errors. Register adds
confirm-password (client-side match). Success → `summaries.html`.

### 5.2 `summaries.html` — member standups (main page)
- Date picker (`<input type="date">`), default = today (UTC), max = today; loads on change.
  - **v2.1**: the selected date is **persisted** in `localStorage` (`rollcall_summary_date`)
    and restored on the next visit (a stored date in the future, e.g. after midnight UTC,
    falls back to today). A **"Today"** button next to the picker resets it to today (UTC),
    clears the stored value, and reloads the summaries.
- Member cards in a responsive grid (1 col → 2 col @900px → 3 col @1300px).
- Card: member name, `@github_username` + linear email (mono/dim), sanitized markdown
  summary. Skeletons while loading; empty state for dates with no data; error toast.
- **v2.1 — markdown typography**: rendered summaries (and assistant chat bubbles) get a
  real type scale instead of the browser defaults that made headings dominate the cards:
  section headings (h1–h3) render at ~0.95em/600 weight in `--text` with clear top margin
  and tight bottom margin; list items get normal line-height with breathing room between
  items; bullets indent inside the card; paragraphs and inline `code` styled consistently.
  Lives in `css/components.css` as a shared `.summary-body` block.

### 5.3 `config.html` — sources & team
Two panels (stacked on mobile):

- **Repositories**: rows of `owner/repo` (mono), inline add input with format
  validation (`^[^/\s]+/[^/\s]+$`), remove with confirm modal.
- **Team members**: rows (name, github, email), add form (3 fields), remove with
  confirm modal.
- Every add/remove fires its per-item endpoint immediately; optimistic UI + toast.

### 5.4 `chats.html` — chat history
Rows: title, relative "last updated", click → `chat.html?id=<chat_id>`.
"New chat" button → `chat.html`. Empty state for first-time users.

### 5.5 `chat.html` — chat interface
- With `?id=`: load `GET /chat/{id}` history. Without: empty ("Ask about your team…").
- User bubbles right (accent-tinted) / assistant bubbles left (surface, markdown).
- Composer fixed at bottom: Enter sends, Shift+Enter newline; disabled + "thinking…"
  while awaiting the reply. Optimistic user-message append.
- New chat: `POST /chat`; when the response `chat_id` arrives, `replaceState` the URL.

## 6. Mock server (`temp-mock/serve.py`)

Stdlib-only Python (`http.server`), `python3 serve.py` on port 8787:

- Maps every endpoint in §4 to `data/*.json`; `GET /member-summary?date=` with no
  matching file → `200 []` (tests empty states).
- `POST /auth/*` validates against `auth.json` and returns a mock token;
  `401` when the `Authorization` header is missing/invalid (tests the guard).
- `POST /chat` mints a `chat_id`; `POST /chat/{id}` appends both messages to
  `chat-<id>.json` (in-memory) and replies from `chat-reply.json` so continued
  conversation works while the mock runs.
- CORS headers + `OPTIONS` handling so the frontend can be served separately
  (`python3 -m http.server` in `frontend/`).
- Mock data: ~3 members with realistic markdown summaries (headings, bullets, inline
  code), 2–3 chats with several messages, covering all UI states.

**Nothing outside `temp-mock/` imports from it.** Deletion is clean; only `API_BASE`
in `js/config.js` changes to the real backend URL.

## 7. Responsive strategy

Mobile-first. Breakpoints 640px (nav → slide-down menu), 900px, 1300px (grid columns).
Chat uses flex + `dvh` for mobile keyboards. Config tables → stacked cards < 640px.
Touch targets ≥ 40px.

## 8. Implementation order

1. Theme/config (`js/config.js`, `js/theme.js`, `css/tokens.css`) + base layout + nav
2. `api.js`, `auth.js`, `ui.js`, `markdown.js`, vendored libs
3. `temp-mock/` (mock server + data) — early, so every page is built against it
4. login/register
5. summaries
6. config
7. chats + chat
8. Responsive/empty/error/loading pass + smoke test against the mock server

## 9. Resolved decisions (from review)

1. **Auth**: token-based, `Authorization: Bearer` — confirmed. ✅
2. **Config**: per-item add/update/delete endpoints — confirmed. ✅
3. **Removal**: yes, repos and members removable from the UI. ✅
4. **Summary fields**: `[{member_name, github_username, linear_email, summary, date}]`
   is fine to code against. Display is summary-only (no raw `input_data` expander);
   easy to add later if wanted. ✅
5. **New chat**: server returns `chat_id` in the response to the first message;
   frontend handles it via URL `replaceState`. ✅
6. **Dates**: UTC end-to-end (matches the ingestion's `date` field). ✅
7. **Branding**: wordmark "Roll-Call", no logo. Colors as a JS object in a config
   file (`THEME` in `js/config.js`) applied site-wide via CSS variables — one place to
   change. ✅
8. **v2.1**: summaries date picker persists its selection across visits; "Today" button
   resets it. ✅
9. **v2.1**: markdown rendering gets a proper type scale (headings, lists, spacing) in
   `css/components.css`, shared by summary cards and assistant chat bubbles. ✅

---

## 10. v2.1 changes (this revision)

1. **Persisted date + Today button (§5.2)**: store the picked date in
   `localStorage[rollcall_summary_date]`; restore on load (invalid/future → today UTC).
   "Today" button next to the picker: sets the picker to today, clears the stored value,
   and reloads.
2. **Markdown formatting (§5.2, §2)**: replace default heading/list rendering with a
   tuned type scale — compact section headings (~0.95em, 600 weight), consistent
   paragraph and list spacing, indented bullets, styled inline code — applied to both
   `.summary-body` (summaries) and assistant chat bubbles.
