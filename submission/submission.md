*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

Picture the daily standup. The whole team gathers — remote folks dial in — and each person recites what they did yesterday from memory. Nobody likes these meetings. The updates get fudged, the quiet work goes unmentioned, and thirty minutes of everyone's day is spent talking about work instead of doing it.

**Roll-Call is the AI teammate that sits in the meeting so nobody has to.** Every night, automatically:

1. **It reads the team's real activity** — pull requests, commits and pushes from GitHub, issues and comments from Linear. PRs touched today are separated from ongoing work, and every issue is cross-linked to the PR that implements it.
2. **An open-weight Gemma model writes a plain-English standup** for each team member.
3. **Everything is stored in MongoDB Atlas** — and every report is uploaded to **Backboard** as a document, so the chat agent is grounded in the team's real history through RAG. Ask *"who touched the auth service this week?"* and it answers from ingested data — with a tool that pulls live reports straight from MongoDB when it needs fresh facts.
4. **That's the whole standup.** One dashboard card per person, ready when you wake up. No meeting.

And this is a real, unedited output — Roll-Call tracking its own development:

> **Hammad Bin Sajjad**
>
> **Completed Work**
>
> - **Ingestion of Linear issues and Github PRs (ROL-5):** Implemented the ingestion layer, including GitHub PR and Linear issue data retrieval, LLM processing with Gemma, and MongoDB storage. This was completed via PR #2 (branch ROL-5) with commits covering LiteLLM/DB boilerplate and final database integration.
> - **Automate Ingestion using Github Actions Workflow (ROL-6):** Set up a GitHub Actions workflow to automate data ingestion at 1 AM UTC. This was implemented in PR #3 (branch ROL-6).
> - **Roll Call Frontend (ROL-8):** Implemented the frontend using HTML, CSS, and JS. This work was captured in PR #4 (branch ROL-8), which included updates to system architecture design diagrams.
> - **Roll Call Backend (ROL-7):** Implemented the backend APIs, including Backboard Chat integration. This was completed via PR #5 (branch ROL-7), with commits addressing backend implementation, model settings, and error fixes.
> - **Tool output in message bug fix (ROL-10):** Fixed a bug regarding tool output in messages via PR #6 (branch ROL-10).
> - **Sentry Agent Tracing (ROL-9):** Integrated Sentry error and agent tracing for both ingestion (LiteLLM) and chat (Backboard). This was handled in PR #7 (branch ROL-9), which included fixing Sentry sample-rate crashes and workflow changes.
>
> **Ongoing Work**
>
> - **FE and BE Bug Fixes (ROL-10):** Ongoing work to address bugs identified during production testing.
>
> **Direct Pushes**
>
> - Pushed a fix for commit duplication to the Roll-Call repository.
> - Pushed an update to the API URL in the Roll-Call repository.

Note what the model got right: every PR is tied to the Linear issue it implements, completed work is separated from ongoing work, and even the direct pushes (commits that never went through a PR) made it in — while only stating what the data shows. The system prompt forbids inventing activity.

**Who pays for this:** engineering leads and project managers of small remote teams (5–20 people), and agencies juggling client repos. Existing tools still make humans do the work — typing updates into a form, or sitting through the meeting. Roll-Call reads the sources of truth directly — so nobody has to remember anything, and nobody has to report anything.

## Demo

Live on Render: **https://roll-call-frontend-2xea.onrender.com**

Registration is open — create an account and everything's live. One heads-up: if the backend has been idle, the first request can take 30–60 seconds to wake it up.

**Summaries** — the standup, already written, one card per member:

![Summaries dashboard](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/summaries.png)

**Config** — manage tracked repos and team members from the UI:

![Config page](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/config.png)

**Chat** — the agent answers from ingested history, citing the PRs and issues behind every answer:

![Chat page](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/chat.png)

## Code

{% embed https://github.com/hammadbinsajjad/Roll-Call %}

```
ingestion/      Nightly pipeline — GitHub + Linear → Gemma → MongoDB → Backboard
backend/        FastAPI app — auth, summaries, config, chats, /embed
frontend/       Static UI, no build step
.github/        Workflows — nightly ingestion + deploy pipelines
render.yaml     Render Blueprint — both services
```

## How I Built It

One loop: **collect → summarize → store → ground → answer.** The whole data flow:

![System data flow design](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/architecture/system-data-flow-design.png)

The pieces:

- **Nightly ingestion (GitHub Actions, 01:00 UTC).** Collectors pull GitHub PRs/commits/pushes and Linear issues/comments, cross-link issues to the PRs implementing them, and build one payload per member. Then **Gemma** writes each standup through `litellm`. This is the only AI part that can work fully locally — the chat can't run locally, because it depends on Backboard. During development I tested the ingestion with **Gemma 4 E4B** on my own machine; the hosted pipeline runs **Gemma 4 26B A4B via OpenRouter**. Members with no activity skip the LLM call entirely — quiet days cost nothing.
- **Storage (MongoDB Atlas).** One `roll_call` database shared by the pipeline (writer) and the API (reader). Each report is also POSTed to the backend's `/embed` endpoint — machine-to-machine, secret-token guarded — which uploads it to Backboard, replacing (not duplicating) the old document on re-runs.
- **Chat agent (Backboard).** Chats map 1:1 to Backboard threads; history lives there, grounded in the uploaded reports. The assistant has one tool — `get_daily_summaries` — querying live reports from MongoDB. The chat runs on **Gemma 4 26B A4B via OpenRouter**, the only model this assistant runs.
- **Backend (FastAPI).** The only thing the browser talks to: JWT auth, per-user quotas checked in MongoDB *before* any AI call (rejected users cost nothing), and rate-limited chat endpoints.
- **Frontend.** Plain HTML/CSS/vanilla JS, no build step — deploys to static hosting as-is, with a "Terminal Green" dark theme.
- **Hosting & deploys (Render + GitHub Actions).** `render.yaml` defines both services. Auto-deploys are off — pushes to `main` trigger Actions workflows that fire each service's deploy hook, so the same automation runs the data pipeline and the releases.
- **Sentry Agent Tracing on both AI paths.** The ingestion Gemma calls flow through the `litellm` integration; the Backboard client (no Sentry integration of its own) got custom `gen_ai` span instrumentation with conversation IDs. Both AI paths show up as first-class traces in one dashboard.

A small footnote I enjoy: even the tooling behind the project is open — the local Gemma test ran on **llama.cpp**, the architecture diagram above was drawn in **Drawy** (open source, from KDE), and the code was written primarily with **GLM 5.3, GLM 5.3 Flash, and Mimo V2.6 Pro** — all open-weight models too.

Both sides, running live — the nightly ingestion runs, the deployments to Render, and both AI paths traced in Sentry:

![GitHub Actions nightly ingestion run](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/github-actions.png)

![Sentry Agent Tracing — both AI paths in one dashboard](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/sentry-agent-tracing.jpg.png)

And the ingestion side of that tracing — each nightly report run showing up as its own agent trace:

![Sentry Agent Tracing — the ingestion Gemma runs](https://raw.githubusercontent.com/hammadbinsajjad/Roll-Call/main/screenshots/sentry-agent-tracing-ingestion.png)

## Why Does Open Innovation Matter?

**1. Private data stays on hardware you control.** Teams can have private data they don't want to send to a closed service — or to any server they don't control. Because Gemma is an open model, they don't have to: they can run it on their own computers, or self-host on their own servers. In my project, the ingestion part — the step that reads private GitHub and Linear activity — can be run fully locally. I tested it during development with **Gemma 4 E4B** on my own machine, with nothing leaving it.

**2. One model, many providers — and cost goes where it matters.** Open models work across providers, and not every provider is the same — so you never get stuck with one provider and their pricing. Roll-Call has two uses of AI: the ingestion and the chat. The ingestion happens overnight, when nobody's watching — so it can use a cheaper model or tier — while the faster, more capable models are kept for the customer-facing chat agent. That puts the cost where it matters. This flexibility isn't as extensive with closed providers. **OpenRouter**, the provider I used, has tiers made for exactly this.


## Prize Categories

Entering:

- **Best Use of Gemma** — Gemma powers both AI paths: the standup ingestion — which I tested fully locally with **Gemma 4 E4B** through `litellm`, and which runs hosted on **Gemma 4 26B A4B via OpenRouter** — and the chat agent on Backboard, running **Gemma 4 26B A4B via OpenRouter**.
- **Best Use of Render** — the whole product runs on two Render services defined in one `render.yaml` Blueprint (FastAPI web service + static site), with GitHub Actions deploy hooks for deliberate releases.
- **Best Use of GitHub Copilot** — GitHub runs the automation: Actions powers the nightly data-ingestion pipeline (collect GitHub + Linear → Gemma summary → MongoDB → RAG upload) and the deploy pipelines for both services. One cron, one push to `main`, and the system works while you sleep.
- **Best Use of Backboard** — the agent's memory and RAG: every ingested GitHub/Linear report is uploaded as a Backboard document, chats run on Backboard threads with a `get_daily_summaries` tool
- **Best Use of MongoDB Atlas** — the primary database: one `roll_call` DB written by the ingestion pipeline and read by the API (repos, team members, daily reports, users, chats), plus the assistant's live tool queries straight from the summaries collection.
- **Best Use of Sentry Agent Tracing** — both AI paths are traced: the ingestion Gemma calls through the `litellm` integration, and the Backboard chat client through custom `gen_ai` span instrumentation with conversation IDs and error typing.
