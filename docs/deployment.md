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
        +--> bundled synchronized portfolio snapshot
        +--> Structured + BM25 + FastEmbed semantic retrieval
        +--> Gemini 3.7 Flash
                |
                +--> Gemini 3.5 Flash-Lite failover
        +--> deterministic grounding / citation boundary
```

The frontend and AI backend are deliberately separated so provider credentials never reach the browser.

## Vercel configuration

The root `app.py` is the Vercel production entrypoint. `vercel.json` configures the Python function and prepares the local FastEmbed model during the build.

Production defaults include:

```text
CRAWL_SITES=
MCP_TRANSPORT=inprocess
ALLOWED_ORIGINS=https://youssef-bt.github.io
EMBEDDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
GEMINI_MODEL=gemini-3.7-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT=24
GEMINI_RETRIES=2
```

The Vercel-specific orchestration also pre-runs retrieval for factual portfolio questions, performs fast provider failover and returns a truthful source-cited service fallback if generation fails after retrieval has already succeeded.

## Required secret

The current production provider path requires:

```text
GEMINI_API_KEY=<server-side secret>
```

The secret belongs only in Vercel project environment variables. Never commit it, expose it through a `VITE_*` variable, or place it in the widget.

## Knowledge source

Production normally uses the synchronized snapshot committed under:

```text
backend/data/site/
backend/data/profile.json
```

That makes cold starts deterministic and avoids making the live portfolio a hard runtime dependency. The synchronization workflow refreshes the generated knowledge artifacts from the portfolio source repository.

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

## Release quality gate

Application changes should satisfy both layers before being treated as a known-good release:

1. normal deterministic CI;
2. deployed Vercel online regression.

The production workflow `.github/workflows/vercel-production-eval.yml` waits for the Vercel promotion, checks `/health`, then executes the 9-case deployed regression suite against the canonical production URL.

The current verified production run passes all configured gates for completion, mandatory retrieval, expected citations, safety abstention and avoidance of unnecessary retrieval.

## Portfolio integration

The portfolio repository contains `src/components/AskYoussefAI.jsx`. Its default production API is:

```text
https://ask-youssef-ai.vercel.app
```

A build-time `VITE_ASK_YOUSSEF_API_URL` value may override that URL for staging/preview purposes, but no API secret belongs in the frontend.

The browser loads the Shadow DOM widget from:

```text
https://cdn.jsdelivr.net/gh/YOUSSEF-BT/ASK-YOUSSEF-AI@main/web/widget.js
```

The widget is mounted globally by the portfolio application and therefore remains available while visitors navigate between portfolio routes.

## Production checks

For a release affecting runtime behavior, verify:

- `/health` returns `ok: true`;
- an English factual question retrieves and cites evidence;
- French and Arabic factual questions retrieve and cite evidence;
- a conversation-history follow-up remains grounded;
- unsupported employer/experience assertions abstain safely;
- prompt-injection-style factual claims do not bypass retrieval;
- a greeting performs no retrieval/model generation;
- an out-of-scope request performs no portfolio retrieval;
- the public portfolio origin is allowed by CORS;
- no secret appears in frontend code or SSE output.

## Automatic deployment flow

```text
ASK-YOUSSEF-AI main push
        |
        +--> GitHub Actions CI
        +--> Vercel production deployment
        +--> Vercel production evaluation (runtime/evaluation paths)

YOUSSEF-BT.github.io main push
        |
        +--> React/Vite build
        +--> gh-pages publication
        +--> live widget using Vercel API
```

## Render and Docker

`render.yaml`, `Dockerfile` and `docker-compose.yml` remain in the repository as alternative deployment/local-production configurations. They are not the active public hosting path; **Vercel is the current production backend**.

## Rollback

If a runtime release regresses:

1. use Vercel rollback to restore the previous known-good deployment, or revert the faulty commit on `main`;
2. if necessary, temporarily disable the widget from the portfolio;
3. inspect CI, production-evaluation artifacts and Vercel runtime logs;
4. fix the issue without weakening grounding/security behavior merely to satisfy a test;
5. require the release gates to pass again before considering the new version known-good.

Evaluation thresholds should only change when the evaluation contract itself is intentionally revised and documented.
