# Roll-Call temp mock API

Development-only mock backend so the frontend can be built without the real API.

```
python3 serve.py        # port 8787, CORS enabled
```

Seeded login: `alice` / `hunter2` (see `data/auth.json`). Register any new user.

`data/` files are read (and rewritten) live — edit them to change what the UI sees.
`member-summary-<date>.json` files: any date without one returns `[]` (empty state).
Sample summaries exist for **2025-01-15** — pick that date to see populated cards.

**Delete this folder when the real backend is wired up.** Nothing outside
`temp-mock/` imports from it; only `API_BASE` in `js/config.js` changes.
