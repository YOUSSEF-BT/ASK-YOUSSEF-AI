# Ask Youssef AI

**Live multilingual, retrieval-grounded professional portfolio copilot for Youssef Bouzit.**

[![Portfolio](https://img.shields.io/badge/Portfolio-Live-20b2a6)](https://youssef-bt.github.io/)
[![API](https://img.shields.io/badge/API-Vercel-black)](https://ask-youssef-ai.vercel.app/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Ask Youssef AI turns Youssef Bouzit's public portfolio into a conversational, evidence-grounded assistant for recruiters, clients, developers and collaborators. It answers questions about projects, skills, certifications, professional experience, education, career availability and public contact information in **English, French and Arabic**.

This is not a generic chatbot placed on top of a static prompt. Factual portfolio turns are deterministically routed, evidence is synchronized from the real portfolio, exact structured facts are resolved without asking an LLM to count or infer them, hybrid retrieval fuses multiple strategies, citations are verified, unsupported high-risk claims are blocked, and the deployed system is continuously regression-tested.

> **Status: LIVE.** The FastAPI backend is deployed on Vercel at `https://ask-youssef-ai.vercel.app`, the production widget is integrated into `https://youssef-bt.github.io`, CI is passing, and the current production regression and adversarial audit suites pass all configured strict gates.

## Live system

- **Portfolio + widget:** https://youssef-bt.github.io/
- **Production API:** https://ask-youssef-ai.vercel.app/
- **Health:** https://ask-youssef-ai.vercel.app/health
- **Capabilities:** https://ask-youssef-ai.vercel.app/capabilities
- **API docs:** https://ask-youssef-ai.vercel.app/docs

The API root intentionally returns a small service descriptor. The visitor-facing product is the **Ask Youssef AI widget embedded in the portfolio**.

## Core capabilities

- Multilingual responses in **English, French and Arabic**.
- Deterministic language/intent routing before generation.
- Mandatory evidence retrieval for factual portfolio claims.
- **Precision-fact lane** for exact counts, complete inventories, employer checks, current work, career availability and other structured facts.
- Portfolio synchronization from `YOUSSEF-BT/YOUSSEF-BT.github.io`.
- **Structured Profile + BM25 + FastEmbed Semantic Search** retrieval.
- **Reciprocal Rank Fusion (RRF)** with deterministic evidence boosts.
- Citation-backed answers linked to real portfolio evidence.
- Citable `structured-profile` aggregate evidence for portfolio counts.
- Explicit `career-status` evidence synchronized from public About/Contact positioning.
- Deterministic grounding checks for unsupported metrics, URLs, emails and citations.
- Conservative handling of unsupported employers, personal details, prompt injection and false-source pressure.
- Conversation-history support for grounded follow-up questions.
- Server-Sent Events (**SSE**) streaming.
- Privacy-safe aggregate telemetry and fixed-category feedback.
- Public-origin, request-size, per-IP and global rate limits.
- Instant deterministic greetings and out-of-scope responses without unnecessary model calls.
- Production provider failover from Gemini 3.7 Flash to Gemini 3.5 Flash-Lite.
- Evidence-cited safe fallback if generation fails after retrieval has already succeeded.
- Zero-dependency **Shadow DOM** widget embedded in the live portfolio.

## Architecture

```text
YOUSSEF-BT.github.io — source of truth
        |
        | scheduled + manual sync
        v
Markdown evidence + structured profile.json
        |
        +--> career/contact enrichments
        |       +--> career-status.md
        |       +--> public email evidence
        |
        +--> structured-profile.md (citable aggregates)
        |
        v
Vercel FastAPI /chat (SSE)
        |
        v
Deterministic EN / FR / AR router
        |
        +--> greeting / out-of-scope / secret request
        |          -> deterministic bounded response
        |
        +--> precision structured fact
        |          -> profile.json -> exact answer + citations
        |
        +--> open factual portfolio question
                   |
           retrieval required
                   |
      +------------+-------------+
      |            |             |
      v            v             v
 Structured      BM25       FastEmbed / ONNX
  Profile                    semantic search
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
          Gemini 3.7 Flash
             |        |
          failure   success
             v        v
 Gemini 3.5 Flash-Lite
             \        /
              v      v
       deterministic grounding gate
              |
       grounded answer / safe abstention
              |
              v
            SSE widget
```

See [`docs/architecture.md`](docs/architecture.md) for deeper implementation details.

## Source-of-truth synchronization

The synchronization pipeline extracts public professional information from the portfolio and produces:

- `backend/data/site/` — Markdown evidence used by lexical/semantic retrieval and citations;
- `backend/data/profile.json` — structured entities used for exact facts and field-aware retrieval;
- `backend/data/site/manifest.json` — integrity/count metadata;
- `career-status.md` — explicit public full-time/CDI availability evidence;
- `structured-profile.md` — citable synchronized aggregate counts.

Current synchronized snapshot:

| Entity | Count |
|---|---:|
| Projects | 10 |
| Skill categories | 6 |
| Certifications | 56 |
| Professional experiences | 2 |
| Education entries | 2 |
| Public professional contacts/links | 4 |

The current live health snapshot contains **16 evidence pages, 161 chunks and 81 structured documents**. Counts are synchronized from the portfolio and can evolve when the source portfolio changes.

## Retrieval, precision facts and grounding

Open factual questions use:

```text
Structured Profile + BM25 + FastEmbed Semantic Search
                         ↓
               Reciprocal Rank Fusion
                         ↓
            deterministic evidence boosts
                         ↓
                    search_site
```

Questions that should never be answered from only a top-k subset — for example *How many certifications?*, *Which Oracle certifications?*, *Did Youssef work at IBM?*, *What is he doing now?* or *Is he seeking a full-time role?* — use the precision-fact lane against the complete synchronized `profile.json`. This prevents a retrieved subset from being mistaken for the complete portfolio.

`backend/grounding.py` validates generated claims against evidence returned during the turn. It removes unknown citations, verifies supported citation IDs, rejects unsupported URLs/emails/numeric claims where applicable, and replaces unsupported high-impact claims with evidence-based abstention. Retrieved portfolio content is data, not instructions.

This is deliberately described as a **deterministic safety boundary**, not universal semantic entailment.

## Verified quality gates

### Offline deterministic CI benchmark

| Metric | Result | Threshold |
|---|---:|---:|
| Routing accuracy | 1.000 | 0.950 |
| Retrieval Hit@1 | 1.000 | 0.750 |
| Retrieval Hit@3 | 1.000 | 0.950 |
| Retrieval MRR | 1.000 | 0.850 |
| Grounding safety rate | 1.000 | 1.000 |
| Profile integrity rate | 1.000 | 1.000 |

### Live career-state regression — 3/3 passed

Executed against the production Vercel API on **2026-09-11**. It verifies localized current work plus the explicit fact that freelance activity and the full-time/CDI search coexist.

- **Median:** 77.53 ms
- **P95:** 171.56 ms
- **Max:** 182.01 ms

### Live core production regression — 25/25 passed

The strict core suite validates multilingual factual retrieval, 56 certifications and 3 Oracle credentials, exact portfolio aggregates, Computer Vision/Python/RAG facts, current work, career availability, email and phone handling, history-aware follow-ups, unsupported employers, prompt injection, greetings, scope control and citation integrity.

Every configured strict metric passed at **1.000 / 1.000**.

- **Median:** 102.16 ms
- **P95:** 2.674 s
- **Max:** 3.842 s

### Live adversarial production audit — 20/20 passed

The bug-hunting suite tests conversational phrasing and typos, multilingual safety, false employers, unsupported salary/address/marital status, fake citations, prompt/secret exfiltration, Controlled RAG, current-work localization and out-of-scope behavior.

Every configured strict metric passed at **1.000 / 1.000**, including completion, retrieval, required sources, expected content, forbidden-content absence, safety abstention, citation integrity and unnecessary-retrieval avoidance.

- **Median:** 132.56 ms
- **P95:** 2.281 s
- **Max:** 3.399 s

These are **fixed regression-suite measurements**, not a claim of 100% semantic accuracy for arbitrary future questions. The evaluator uses observable deterministic assertions rather than an LLM judge.

See [`docs/evaluation.md`](docs/evaluation.md).

## Reliability on Vercel

The production serverless path is optimized for portfolio-scale reliability while staying within a no-card/free-tier setup:

- synchronized corpus bundled with the application;
- FastEmbed/ONNX model prepared during build and reused at runtime;
- deterministic precision facts for exact/high-risk portfolio questions;
- deterministic pre-retrieval for factual generative turns;
- fast provider failover on quota, overload or timeout signals;
- bounded generation retry/timeout budget;
- evidence-based fallback if generation is temporarily unavailable;
- no model call for deterministic greetings, scope responses and secret-exfiltration refusals.

Provider and hosting quotas still apply. The project does not claim enterprise-scale availability or load guarantees.

## Security and privacy

- `GEMINI_API_KEY` remains server-side and is never sent to the browser.
- The public widget receives only the public API base URL.
- Internal prompts and private model reasoning are not exposed through SSE.
- Requests for hidden prompts, API keys or private configuration are rejected.
- Retrieved portfolio text is treated as untrusted data.
- CORS/origin controls restrict browser embedding to approved portfolio origins.
- Request and history sizes are bounded and history roles are validated.
- Per-IP and global limits bound public abuse/provider usage.
- Aggregate telemetry does not retain prompts, answers, IPs, emails or conversation history.
- Feedback uses fixed categories rather than arbitrary visitor text.

See [`docs/security.md`](docs/security.md).

## Repository structure

```text
ASK-YOUSSEF-AI/
├── app.py                          # Vercel production entrypoint
├── backend/
│   ├── app.py                      # FastAPI + SSE API
│   ├── agent.py                    # core orchestration
│   ├── router.py                   # deterministic EN/FR/AR intent routing
│   ├── precision_facts.py          # exact structured portfolio facts
│   ├── structured_facts.py         # precision compatibility/career layer
│   ├── grounding.py                # citation/high-risk-claim verifier
│   ├── vercel_agent_patch.py       # serverless retrieval/reliability path
│   ├── vercel_gemini_failover.py   # provider failover
│   ├── rag.py                      # retrieval primitives/embedders
│   ├── observability.py            # aggregate privacy-safe telemetry
│   ├── feedback.py                 # fixed-category feedback
│   ├── retrieval/
│   │   ├── hybrid.py               # semantic + BM25 + structured RRF
│   │   └── structured.py           # field-aware structured retrieval
│   └── data/
│       ├── profile.json
│       ├── fastembed_cache/
│       └── site/
├── evaluation/
│   ├── dataset.json                # offline deterministic benchmark
│   ├── career_cases.json           # live career regression
│   ├── core_production_cases.json  # live strict core suite
│   ├── deep_audit_cases.json       # live adversarial QA suite
│   ├── run_benchmark.py
│   └── run_online_eval.py
├── scripts/
│   ├── sync_portfolio.py
│   ├── build_structured_profile.py
│   ├── enrich_public_contact.py
│   └── enrich_career_status.py
├── tests/
├── web/widget.js                   # Shadow DOM portfolio widget
├── docs/
├── vercel.json
├── render.yaml                     # optional alternative deployment blueprint
├── Dockerfile
├── docker-compose.yml
├── LICENSE
└── NOTICE.md
```

## Local development

Create a local environment file without committing secrets:

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

Offline deterministic benchmark:

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Unit/regression tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Live strict suite:

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --dataset evaluation/core_production_cases.json \
  --output online-eval-report.json \
  --strict
```

Live adversarial suite:

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --dataset evaluation/deep_audit_cases.json \
  --output deep-audit-report.json \
  --delay 11 \
  --strict
```

## Production widget

The live portfolio loads `web/widget.js` from jsDelivr and points it to the public Vercel API. No Gemini secret is embedded in the frontend.

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

GitHub Actions covers:

- Python compilation and unit/regression tests;
- widget JavaScript validation;
- container configuration validation;
- synchronized profile/corpus integrity;
- deterministic retrieval/grounding benchmark;
- required license/attribution files;
- fail-fast deployed career-state regression;
- strict deployed core regression;
- deep adversarial production audit after backend/runtime changes.

Vercel is connected to `main`, so backend changes deploy automatically. The portfolio repository independently publishes its built output to GitHub Pages.

## Deliberate non-claims

This repository does **not** claim:

- universal semantic entailment verification;
- 100% accuracy for arbitrary future generated answers;
- enterprise-scale load or availability guarantees;
- persistent distributed telemetry;
- subjective LLM-judge scores;
- capabilities that are not represented by committed code and measured tests.

## Attribution and license

Ask Youssef AI substantially adapts components from [`adityajn105/portfolio-chatbot`](https://github.com/adityajn105/portfolio-chatbot), originally released under the MIT License.

The original copyright and MIT terms are preserved in [`LICENSE`](LICENSE), with additional attribution details in [`NOTICE.md`](NOTICE.md).

Synchronization, structured/hybrid retrieval, deterministic precision facts, multilingual routing, grounding, evaluation, observability, production hardening, Vercel serverless reliability and portfolio-specific integration are part of the Ask Youssef AI implementation.

---

**Ask Youssef AI — Professional Portfolio Copilot**
