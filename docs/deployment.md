# Production Deployment

This document defines the intended production path for Ask Youssef AI. It is a runbook, not a claim that the service is already deployed.

## Target topology

```text
Portfolio (GitHub Pages)
        |
        | HTTPS / SSE
        v
FastAPI service (Render)
        |
        +--> LLM / embedding provider
        |
        +--> bundled synchronized portfolio snapshot
        |
        +--> optional contact provider
```

The portfolio remains static on GitHub Pages. The AI backend runs separately so API credentials never reach the browser.

## 1. Pre-deployment quality gate

A production candidate must pass the normal GitHub Actions CI workflow. Required gates include:

- Python compilation;
- unit tests;
- deterministic portfolio benchmark;
- structured profile/manifest integrity;
- JSON validation;
- JavaScript syntax validation for the embeddable widget;
- stale-upstream-identity guard.

Online LLM evaluation is a separate provider-backed workflow and should not be confused with the deterministic regression benchmark.

## 2. Render service

The repository includes `render.yaml` with the intended service configuration:

- service name: `ask-youssef-ai`;
- root directory: `backend`;
- build: `pip install -r requirements.txt`;
- start: `uvicorn app:app --host 0.0.0.0 --port $PORT`;
- health check: `/health`.

Connect the GitHub repository to Render and create the service from the Blueprint or equivalent Web Service flow.

## 3. Required secrets

Set secrets only in Render's environment settings. Never paste real values into the public repository.

Required for the current provider path:

```text
GEMINI_API_KEY=<server-side secret>
```

Optional contact capability:

```text
FORMSPREE_ENDPOINT=<server-side endpoint>
```

The remaining non-secret configuration is declared in `render.yaml` and/or `.env.example`.

## 4. Production origin

Keep:

```text
ALLOWED_ORIGINS=https://youssef-bt.github.io
```

Do not set `*` in production unless intentionally testing outside the portfolio. When testing a local development origin, use a separate environment rather than weakening the production service.

## 5. Knowledge source

The production service normally uses the synchronized snapshot committed under `backend/data/site` plus `backend/data/profile.json`. This keeps startup deterministic and avoids making the live portfolio a hard runtime dependency.

The scheduled synchronization workflow refreshes those generated artifacts from the portfolio repository. A future project added to the source portfolio can therefore enter the assistant's knowledge base through the sync pipeline rather than a hand-written chatbot response.

## 6. Smoke tests after deploy

Do not integrate the production URL into the public portfolio until all of these pass:

```text
GET /health          -> ok: true
GET /capabilities    -> Ask Youssef AI metadata and suggestions
GET /pages           -> synchronized source pages
GET /metrics         -> aggregate metrics only
POST /chat           -> valid SSE response
POST /feedback       -> {"ok": true} for an allowed fixed category
```

Also test:

- English portfolio question;
- French portfolio question;
- Arabic portfolio question;
- exact technical identifier question (for example YOLOv11s);
- unsupported employer/metric question -> cautious abstention;
- follow-up question using conversation history;
- prompt-injection-style profile claim;
- rate-limit behavior;
- request from a non-allowed browser origin.

## 7. Portfolio integration

After the backend URL is verified, embed the production widget into `YOUSSEF-BT/YOUSSEF-BT.github.io` with the backend URL supplied as `data-api`.

The visual integration must use the portfolio's existing design tokens, particularly:

```text
background: #0f1418
card:       #141a1f
primary:    #20b2a6
foreground: #f0f2f5
border:     #242b32
```

The browser must never contain the LLM API key.

## 8. Final public verification

Before announcing the project on CV, LinkedIn, Fiverr, or Upwork:

- verify the production backend URL from an external browser;
- verify the widget on desktop and mobile;
- verify source links from answers;
- run the deterministic benchmark against the exact release commit;
- run the provider-backed online evaluation and publish only real measured results;
- confirm that no private credentials appear in repository history or frontend code;
- create a short demo capture/GIF;
- finalize README, architecture diagram, and portfolio project page.

## Rollback

If a production change degrades responses or breaks the widget:

1. remove/disable the widget from the public portfolio if necessary;
2. redeploy the previous known-good backend commit;
3. inspect CI and online-evaluation reports;
4. fix on `main` only after deterministic gates pass again.

Never hide a failed benchmark by lowering thresholds merely to make CI green. Change thresholds only when the evaluation contract itself is intentionally revised and documented.
