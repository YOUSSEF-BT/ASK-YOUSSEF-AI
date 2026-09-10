# Ask Youssef AI

**Live multilingual, retrieval-grounded professional portfolio copilot for Youssef Bouzit.**

[![Portfolio](https://img.shields.io/badge/Portfolio-Live-20b2a6)](https://youssef-bt.github.io/)
[![API](https://img.shields.io/badge/API-Vercel-black)](https://ask-youssef-ai.vercel.app/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Ask Youssef AI is an AI Engineering project that turns Youssef Bouzit's public portfolio into a conversational, evidence-grounded assistant for recruiters, clients, developers and collaborators. It answers questions about projects, skills, certifications, professional experience, education and public contact information in **English, French and Arabic**.

This is not a generic chatbot placed on top of a static prompt. Factual profile questions are deterministically routed through retrieval, evidence is synchronized from the real portfolio, multiple retrieval strategies are fused, citations are verified, unsupported high-risk claims are blocked, and the deployed system is continuously evaluated.

> **Release status: LIVE.** The FastAPI backend is deployed on Vercel at `https://ask-youssef-ai.vercel.app`, the production widget is integrated into `https://youssef-bt.github.io`, CI is passing, and the deployed online regression suite passes all configured gates.

## Live system

- **Portfolio + widget:** https://youssef-bt.github.io/
- **Production API:** https://ask-youssef-ai.vercel.app/
- **Health:** https://ask-youssef-ai.vercel.app/health
- **Capabilities:** https://ask-youssef-ai.vercel.app/capabilities
- **API docs:** https://ask-youssef-ai.vercel.app/docs

Opening the API root intentionally returns a small service descriptor. The visitor-facing experience is the **Ask Youssef AI widget embedded in the portfolio**.

## Core capabilities

- Multilingual responses in **English, French and Arabic**.
- Deterministic intent/language routing before the LLM.
- Mandatory retrieval for factual claims about Youssef.
- Portfolio synchronization from `YOUSSEF-BT/YOUSSEF-BT.github.io`.
- **Structured Profile + BM25 + Semantic Search** retrieval.
- **Reciprocal Rank Fusion (RRF)** with deterministic evidence boosts.
- Citation-backed answers linked to real portfolio evidence.
- Deterministic grounding checks for unsupported metrics, URLs, emails and citations.
- Conservative handling of unsupported employer/experience claims and prompt injection.
- Conversation-history support for grounded follow-up questions.
- Server-Sent Events (**SSE**) streaming.
- Privacy-safe aggregate telemetry and fixed-category feedback.
- Public origin, request-size, per-IP and global rate limits.
- Instant deterministic greeting path that consumes neither retrieval nor Gemini generation.
- Production provider failover from Gemini 3.7 Flash to Gemini 3.5 Flash-Lite.
- Graceful evidence-cited fallback if generation fails after retrieval already succeeded.
- Zero-dependency **Shadow DOM** widget embedded in the live portfolio.

## Architecture

```text
YOUSSEF-BT.github.io — source of truth
        |
        | automatic synchronization
        v
Markdown evidence + structured profile.json
        |
        +-----------------------------+
        |                             |
        v                             v
 Portfolio visitor                CI / Evaluation
        |                             |
        v                             +--> deterministic benchmark
Ask Youssef AI widget                  +--> deployed online regression
        |
        v
Vercel FastAPI /chat (SSE)
        |
        v
Deterministic EN / FR / AR router
        |
        +--> greeting --------------------> deterministic response
        |
        +--> out-of-scope ----------------> scoped assistant response
        |
        +--> factual portfolio request
                    |
             retrieval required
                    |
       +------------+-------------+
       |            |             |
       v            v             v
   Structured      BM25       Semantic Search
    Profile                  FastEmbed / ONNX
       |            |             |
       +------------+-------------+
                    |
                    v
             RRF fusion + rerank
                    |
                    v
             retrieved evidence
                    |
                    v
     Gemini 3.7 Flash generation
          |             |
          | failure     | success
          v             v
 Gemini 3.5 Flash-Lite  answer
          |             |
          +------+------+ 
                 |
                 v
       deterministic grounding gate
            /               \
           v                 v
 grounded answer        safe abstention
 + verified citations   / service fallback
                 |
                 v
              SSE widget
```

See [`docs/architecture.md`](docs/architecture.md) for deeper implementation details.

## Source-of-truth synchronization

`scripts/sync_portfolio.py` extracts public professional information from the portfolio and produces:

- `backend/data/site/` — Markdown evidence used by lexical and semantic retrieval;
- `backend/data/profile.json` — structured entities used for field-aware matching;
- `backend/data/site/manifest.json` — integrity/count metadata.

Current synchronized snapshot:

| Entity | Count |
|---|---:|
| Projects | 10 |
| Skill categories | 6 |
| Certifications | 56 |
| Professional experiences | 2 |
| Education entries | 2 |
| Public professional links | 3 |

These counts describe the synchronized snapshot used by the current regression suite; the sync workflow can update them as the portfolio evolves.

## Retrieval and grounding

The production retrieval path is:

```text
Structured Profile + BM25 + FastEmbed Semantic Search
                         ↓
               Reciprocal Rank Fusion
                         ↓
            deterministic evidence boosts
                         ↓
                    search_site
```

For factual portfolio questions, Vercel pre-runs retrieval before generation. That design has three benefits: grounding no longer depends on the model deciding whether to search, the common factual path requires fewer remote model round trips, and retrieved evidence remains available for a truthful fallback if the model provider is temporarily unavailable.

`backend/grounding.py` then checks the generated answer against evidence returned during that turn. It can remove unknown citations, attach retrieved citations when appropriate, detect unsupported numeric metrics, URLs and email addresses, and replace unsafe high-impact claims with evidence-based abstention.

This is intentionally described as a **deterministic safety boundary**, not universal semantic entailment.

## Evaluation

### Deterministic CI benchmark

The fixed offline regression suite currently passes the configured thresholds:

| Metric | Result | Threshold |
|---|---:|---:|
| Routing accuracy | 1.000 | 0.950 |
| Retrieval Hit@1 | 1.000 | 0.750 |
| Retrieval Hit@3 | 1.000 | 0.950 |
| Retrieval MRR | 1.000 | 0.850 |
| Grounding safety rate | 1.000 | 1.000 |
| Profile integrity rate | 1.000 | 1.000 |

### Deployed production regression

The production evaluation executed against the live Vercel API on **2026-09-10** passed all configured deterministic smoke gates:

| Metric | Result | Threshold |
|---|---:|---:|
| Completion rate | 1.000 | 1.000 |
| Required retrieval rate | 1.000 | 1.000 |
| Expected citation rate | 1.000 | 1.000 |
| Safety abstention rate | 1.000 | 1.000 |
| Unnecessary retrieval avoidance | 1.000 | 1.000 |

Measured latency across the 9-case deployed regression run:

- **Median:** 1.138 s
- **P95:** 1.550 s
- **Max:** 1.576 s
- **Deterministic greeting:** 0.142 s

The deployed suite includes English/French/Arabic factual questions, exact technical identifiers (`YOLOv11s`, `BoT-SORT`), conversational follow-ups, unsupported employer claims, prompt injection, greeting behavior and an out-of-scope request.

These numbers are **regression-suite measurements**, not a claim of 100% semantic accuracy for arbitrary questions. `evaluation/run_online_eval.py` uses deterministic observable checks rather than an LLM judge.

See [`docs/evaluation.md`](docs/evaluation.md).

## Reliability on Vercel

The live serverless path is optimized for predictable portfolio-scale operation:

- bundled synchronized corpus; no live crawl required at cold start;
- FastEmbed/ONNX semantic retrieval in-process;
- deterministic pre-retrieval for factual portfolio turns;
- low-latency Gemini generation configuration;
- immediate model failover on quota, overload or timeout signals;
- bounded generation timeout/retry budget below the Vercel Hobby request window;
- graceful source-cited response if generation fails after evidence retrieval;
- deterministic greetings without a model call.

The current deployment is a portfolio/demo production deployment on **Vercel Hobby**. The project does not claim enterprise-scale availability or load guarantees.

## Security and privacy

- `GEMINI_API_KEY` remains server-side and is never sent to the browser.
- The public widget receives only the public API base URL.
- Internal prompts and raw chain-of-thought/model reasoning are not exposed through SSE.
- Retrieved portfolio text is treated as untrusted data, not executable instructions.
- CORS/origin controls limit browser embedding to the portfolio origin.
- Request and history sizes are bounded.
- Per-IP and global rate limits bound public abuse/provider spend.
- Aggregate telemetry does not retain prompts, answers, IPs, emails or conversation history.
- Feedback uses fixed categories rather than storing arbitrary visitor text.

See [`docs/security.md`](docs/security.md).

## Repository structure

```text
ASK-YOUSSEF-AI/
├── app.py                         # Vercel production entrypoint
├── backend/
│   ├── app.py                     # FastAPI + SSE API
│   ├── agent.py                   # core ReAct-style orchestration
│   ├── vercel_agent_patch.py      # serverless retrieval/reliability path
│   ├── vercel_gemini_failover.py  # fast provider failover
│   ├── rag.py                     # retrieval primitives / embedders
│   ├── router.py                  # deterministic language + intent routing
│   ├── grounding.py               # citation/high-risk-claim verifier
│   ├── observability.py           # aggregate privacy-safe telemetry
│   ├── feedback.py                # fixed-category feedback
│   ├── retrieval/
│   │   ├── hybrid.py              # semantic + BM25 + structured RRF
│   │   └── structured.py          # field-aware profile retrieval
│   └── data/
│       ├── profile.json
│       ├── fastembed_cache/
│       └── site/
├── evaluation/
│   ├── dataset.json
│   ├── run_benchmark.py
│   ├── online_cases.json
│   └── run_online_eval.py
├── scripts/
│   ├── sync_portfolio.py
│   └── build_structured_profile.py
├── tests/
├── web/
│   └── widget.js                  # Shadow DOM portfolio widget
├── docs/
├── vercel.json
├── render.yaml                    # optional alternative deployment blueprint
├── Dockerfile
├── docker-compose.yml
├── LICENSE
└── NOTICE.md
```

## Local development

Copy the safe environment template and add your own provider key locally:

```bash
cp .env.example .env
```

Run the backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Or use Docker Compose:

```bash
docker compose up --build
```

Useful endpoints:

```text
GET  /
GET  /health
GET  /capabilities
GET  /pages
GET  /metrics
POST /chat
POST /feedback
```

## Quality checks

Run the deterministic benchmark:

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Run unit/regression tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Run the deployed-system evaluator against a compatible deployment:

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --output online-eval-report.json \
  --strict
```

## Production widget

The live portfolio loads `web/widget.js` from jsDelivr and points it to the verified Vercel API. The API key is never embedded in the frontend.

Standalone integration example:

```html
<script
  src="https://cdn.jsdelivr.net/gh/YOUSSEF-BT/ASK-YOUSSEF-AI@main/web/widget.js"
  data-api="https://ask-youssef-ai.vercel.app"
  data-title="Ask Youssef AI"
  data-subtitle="Professional Portfolio Copilot"
  data-accent="#20b2a6"
  defer>
</script>
```

## CI/CD

GitHub Actions currently covers:

- Python compilation;
- widget JavaScript validation;
- container configuration validation;
- unit/regression tests;
- synchronized JSON/profile integrity;
- deterministic retrieval/grounding benchmark;
- required license/attribution files;
- production online regression against Vercel;
- automated GitHub Pages portfolio deployment.

Vercel is connected to `main`, so production backend changes deploy automatically. The portfolio repository independently publishes its built `dist/` output to `gh-pages`.

## Deliberate non-claims

This repository does **not** claim:

- universal semantic entailment verification;
- 100% accuracy for arbitrary generated answers;
- enterprise-scale load/availability guarantees;
- persistent distributed telemetry;
- subjective LLM-judge scores;
- capabilities that are not represented by committed code and measured tests.

## Attribution and license

Ask Youssef AI substantially adapts components from [`adityajn105/portfolio-chatbot`](https://github.com/adityajn105/portfolio-chatbot), originally released under the MIT License.

The original copyright and MIT terms are preserved in [`LICENSE`](LICENSE), with additional attribution details in [`NOTICE.md`](NOTICE.md).

Synchronization, structured/hybrid retrieval, multilingual routing, grounding, evaluation, observability, production hardening, Vercel serverless reliability and portfolio-specific integration are part of the Ask Youssef AI implementation.

---

**Ask Youssef AI — Professional Portfolio Copilot**
