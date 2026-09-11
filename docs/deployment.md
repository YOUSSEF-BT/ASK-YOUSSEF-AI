# Production Deployment

Ask Youssef AI is live on Vercel and embedded in the GitHub Pages portfolio.

## Current production topology

```text
Portfolio — https://youssef-bt.github.io
        |
        | HTTPS / SSE
        v
Vercel FastAPI — https://ask-youssef-ai.vercel.app
        |
        +--> deterministic EN / FR / AR router
        +--> precision structured-fact resolver
        +--> bundled synchronized portfolio snapshot
        +--> Structured + BM25 + FastEmbed semantic retrieval
        +--> Gemini 3.7 Flash
                |
                +--> Gemini 3.5 Flash-Lite failover
        +--> deterministic grounding / citation boundary
```

The frontend and AI backend are deliberately separated so provider credentials never reach the browser.

## Vercel configuration

The root `app.py` is the Vercel production entrypoint. `vercel.json` configures the Python function and prepares the local FastEmbed model during the build so cold starts do not consume Gemini embedding quota.

Production defaults include:

```text
CRAWL_SITES=
MCP_TRANSPORT=inprocess
ALLOWED_ORIGINS=https://youssef-bt.github.io
EMBEDDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
GEMINI_MODEL=gemini-3.7-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
```

The production orchestration pre-runs retrieval for generative factual questions, resolves exact structured facts directly when possible, performs fast provider failover and returns a truthful evidence-based fallback if generation fails after retrieval has already succeeded.

## Required secret

The production generation path requires:

```text
GEMINI_API_KEY=<server-side secret>
```

The secret belongs only in Vercel project environment variables. Never commit it, expose it through a `VITE_*` variable, place it in the widget, or send it through the public API.

## Knowledge source and synchronization

Production uses the synchronized snapshot committed under:

```text
backend/data/site/
backend/data/profile.json
```

The portfolio repository remains the source of truth. The synchronization workflow periodically rebuilds the corpus and structured profile, then enriches them with:

- public contact evidence, including the published email;
- explicit career availability from the public About/Contact copy;
- localized experience fields;
- citable structured aggregate facts.

The current health snapshot exposes **16 evidence pages, 161 chunks and 81 structured documents**.

## Production endpoints

```text
GET  /                 service descriptor
GET  /health           health + indexed corpus summary
GET  /capabilities     public assistant metadata
GET  /pages            synchronized evidence pages
GET  /metrics          aggregate privacy-safe metrics
POST /chat             SSE assistant response
POST /feedback         fixed-category feedback
```

Production health URL:

```text
https://ask-youssef-ai.vercel.app/health
```

## Production quality gates

Runtime-affecting changes are not considered known-good until the relevant automated layers pass:

1. **CI** — compilation, unit/regression tests, synchronized-data validation and deterministic benchmark.
2. **Career-state deployed regression** — fail-fast check that current freelance work and the explicit CDI/full-time search are represented correctly.
3. **Strict core deployed regression** — 25 end-to-end production scenarios.
4. **Deep adversarial audit** — 20 bug-hunting/safety/localization scenarios on the live API.

`.github/workflows/vercel-production-eval.yml` waits for the production deployment, checks `/health`, runs the career suite, cools down to avoid self-triggering the public rate limit, then runs the strict core suite.

`.github/workflows/deep-production-audit.yml` runs after backend/runtime-affecting changes and deliberately tests hostile, ambiguous and typo-heavy inputs.

Current verified production results on **2026-09-11**:

- career-state regression: **3/3 passed**;
- strict core production regression: **25/25 passed**;
- deep adversarial audit: **20/20 passed**;
- latest adversarial median: **132.56 ms**;
- latest adversarial P95: **2.281 s**;
- latest adversarial max: **3.399 s**.

These are fixed-suite QA results, not a universal accuracy guarantee.

## Portfolio integration

The portfolio repository contains `src/components/AskYoussefAI.jsx`. Its default production API is:

```text
https://ask-youssef-ai.vercel.app
```

A build-time `VITE_ASK_YOUSSEF_API_URL` value may override that URL for staging/preview builds. No provider secret belongs in the frontend.

The browser loads the Shadow DOM widget from:

```text
https://cdn.jsdelivr.net/gh/YOUSSEF-BT/ASK-YOUSSEF-AI@main/web/widget.js
```

The widget is mounted globally by the portfolio application and remains available across portfolio routes.

## Operational production checks

For runtime changes, verify automatically or manually that:

- `/health` returns `ok: true`;
- exact structured questions return complete facts instead of interpreting a top-k subset as the whole profile;
- English, French and Arabic factual questions retrieve/cite evidence;
- current-work and career-status answers remain localized and consistent;
- conversation-history follow-ups remain grounded;
- unsupported employer/personal-detail assertions abstain safely;
- fake citations and prompt-injection attempts do not bypass grounding;
- hidden prompt/internal reasoning/API-key requests are refused;
- greeting and out-of-scope paths avoid unnecessary retrieval/model calls;
- the public portfolio origin is allowed by CORS;
- no provider secret appears in frontend code or SSE output.

## Automatic deployment flow

```text
ASK-YOUSSEF-AI main push
        |
        +--> GitHub Actions CI
        +--> Vercel production deployment
        +--> deployed career/core evaluation (runtime/evaluation changes)
        +--> deep adversarial audit (backend/runtime changes)

YOUSSEF-BT.github.io main push
        |
        +--> React/Vite build
        +--> gh-pages publication
        +--> live widget using Vercel API
```

## Free-tier/no-card operating model

The active setup uses Vercel Hobby and Gemini free-tier-compatible models. The local FastEmbed model avoids consuming Gemini embedding requests. Provider and platform quotas still apply, so this deployment is positioned as a production portfolio/demo system rather than an enterprise SLA-backed service.

## Render and Docker

`render.yaml`, `Dockerfile` and `docker-compose.yml` remain as alternative deployment/local-production configurations. They are not the active public hosting path; **Vercel is the production backend**.

## Rollback

If a runtime change regresses:

1. restore the previous known-good Vercel deployment or revert the faulty commit;
2. if necessary, temporarily disable the portfolio widget;
3. inspect CI artifacts, deployed regression reports, adversarial-audit reports and Vercel runtime logs;
4. fix the root cause rather than weakening grounding/security just to satisfy a test;
5. require the affected automated gates to pass again.

Evaluation thresholds should only change when the evaluation contract itself is intentionally revised and documented.
