# Deploying to Render

One-time setup — after this, every push to `main` deploys the changed side
(backend and/or frontend) automatically via GitHub Actions:

1. **Create the services**: Render dashboard → New → Blueprint → pick this
   repo. Render reads `render.yaml` and creates both services:
   - `roll-call-api` (web service, built from `backend/`) — prompts for the
     secret env vars (`sync: false`): `JWT_SECRET`,
     `MONGO_DB_CONNECTION_STRING`, `SERVICE_TOKEN`, `BACKBOARD_API_KEY`,
     `BACKBOARD_ASSISTANT_ID`.
   - `roll-call-frontend` (static site, published from `frontend/`).
2. **Create a deploy hook per service**: each service → Settings →
   Build & Deploy → Deploy Hooks → add one and copy the URL. A hook URL is a
   secret: anyone holding it can trigger a deploy (regenerate it if it leaks).
3. **Store them in GitHub**: repo Settings → Secrets and variables → Actions
   → New repository secret, twice:
   - `RENDER_DEPLOY_HOOK_URL_BACKEND` = the roll-call-api hook URL
   - `RENDER_DEPLOY_HOOK_URL_FRONTEND` = the roll-call-frontend hook URL

From then on:

- A push to `main` touching `backend/**` (or `render.yaml`) runs
  `.github/workflows/deploy-backend.yml`; a push touching `frontend/**` (or
  `render.yaml`) runs `.github/workflows/deploy-frontend.yml`. Each fires its
  hook; Render builds the service's latest commit on `main`.
- Manual deploy: repo Actions tab → the workflow → Run workflow.
- Watch builds in each service's Events / Logs pages in the dashboard.
- Hook responses: `200` deploy started (body carries the deploy ID), `202`
  queued behind an in-progress deploy, `401` the hook was regenerated —
  update the matching GitHub secret.
- Auto-deploys are disabled (`autoDeployTrigger: 'off'` in `render.yaml` for
  both services), so GitHub Actions is the only deploy path.
