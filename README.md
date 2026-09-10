# Ask Youssef AI

**Professional Portfolio Copilot — multilingual, source-grounded and production-oriented.**

Ask Youssef AI is an intelligent assistant for Youssef Bouzit's public professional portfolio. It helps visitors, recruiters, clients, developers and collaborators explore projects, skills, certifications, professional experience, education and public contact links through answers grounded in synchronized portfolio evidence.

The project is intentionally built as more than a generic portfolio chatbot: factual profile questions are routed through retrieval, evidence comes from the real portfolio source of truth, citations are verified, unsupported high-risk claims are blocked, and quality gates are measured in CI.

> **Release status:** code-complete production candidate. Deterministic CI evaluation, synchronization, security boundaries, observability, feedback, Docker/Render configuration and the embeddable widget are implemented. The remaining external release step is to provision the Render service with the server-side API secret, run the deployed online evaluation, and then point the public portfolio widget to that verified backend URL.

## What it does

- Answers questions about Youssef's public professional profile in **English, French and Arabic**.
- Automatically detects intents such as projects, skills, certifications, experience, education and contact.
- Forces retrieval for factual portfolio questions instead of relying on model memory.
- Synchronizes knowledge from the real `YOUSSEF-BT/YOUSSEF-BT.github.io` portfolio repository.
- Combines **structured profile retrieval + BM25 + semantic search**.
- Fuses independent rankings with **Reciprocal Rank Fusion (RRF)** and deterministic evidence boosts.
- Returns source-backed answers with citations linked to portfolio pages.
- Applies a deterministic grounding boundary that rejects invented metrics, URLs, emails and unknown citations.
- Handles unsupported claims and prompt-injection-style profile assertions conservatively.
- Streams responses over **Server-Sent Events (SSE)**.
- Includes privacy-safe aggregate observability and fixed-category visitor feedback.
- Includes public abuse controls: origin restriction, request-size limits and per-IP/global rate limits.
- Ships as a zero-dependency **Shadow DOM** widget that can be embedded into the portfolio.

## Architecture

```text
YOUSSEF-BT.github.io — source of truth
        |
        | automatic synchronization
        v
Markdown evidence corpus + structured profile.json
        |
        +--------------------------+
        |                          |
        v                          v
Portfolio visitor             CI / evaluation
        |                          |
        v                          +--> deterministic benchmark
Ask Youssef AI widget              +--> deployed online evaluation
        |
        v
FastAPI /chat (SSE)
        |
        v
Deterministic EN / FR / AR router
        |
        +--> greeting / action / out-of-scope
        |
        +--> factual portfolio request
                    |
          retrieval is mandatory
                    |
       +------------+------------+
       |            |            |
       v            v            v
   Structured      BM25       Semantic
    profile                     search
       |            |            |
       +------------+------------+
                    |
                    v
             RRF fusion + rerank
                    |
                    v
             retrieved evidence
                    |
                    v
              ReAct-style LLM
                    |
                    v
        deterministic grounding gate
              /             \
             v               v
   grounded answer      safe abstention
   + real citations
                    |
                    v
               SSE widget
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Source-of-truth synchronization

The assistant does not require duplicated hand-written portfolio facts. `scripts/sync_portfolio.py` extracts public professional information from the portfolio repository and writes:

- `backend/data/site/` — concise Markdown evidence used by semantic and lexical retrieval;
- `backend/data/profile.json` — structured entities used for field-aware matching;
- `backend/data/site/manifest.json` — generated counts used by integrity checks.

The current synchronized snapshot contains:

- **10 projects**
- **6 skill categories**
- **56 certifications**
- **2 professional experiences**
- **2 education entries**
- **3 public professional links**

The synchronization workflow can refresh these artifacts automatically as the portfolio changes.

## Retrieval and grounding

The production retrieval path is:

```text
Structured Profile + BM25 + Semantic Search
                    ↓
          Reciprocal Rank Fusion
                    ↓
       deterministic evidence boosts
                    ↓
              search_site
```

For factual profile intents, the router marks retrieval as required. The final model output is then checked by `backend/grounding.py` against evidence returned during that turn.

The grounding verifier currently protects high-impact literals and citation integrity. It can:

- remove citations to sources that were not retrieved;
- attach a real retrieved citation when evidence exists but the answer omitted one;
- detect unsupported numeric metrics;
- detect unsupported URLs;
- detect unsupported email addresses;
- replace unsafe high-risk claims with an explicit evidence-based abstention.

This is deliberately described as a deterministic safety boundary, not as universal semantic entailment.

## Measured quality gates

The deterministic regression benchmark runs in GitHub Actions without an LLM judge or network dependency. The latest verified benchmark artifact on **2026-09-10** produced:

| Metric | Measured result | CI threshold |
|---|---:|---:|
| Routing accuracy | 1.000 | 0.950 |
| Retrieval Hit@1 | 1.000 | 0.750 |
| Retrieval Hit@3 | 1.000 | 0.950 |
| Retrieval MRR | 1.000 | 0.850 |
| Grounding safety rate | 1.000 | 1.000 |
| Profile integrity rate | 1.000 | 1.000 |

These are **fixed regression-suite results**, not a claim that the generative assistant has 100% end-to-end accuracy. The deployed model is evaluated separately with `evaluation/run_online_eval.py`.

The benchmark covers multilingual routing, exact identifiers such as `YOLOv11s` / `BoT-SORT`, structured retrieval, unsupported metrics/links/emails, citation integrity, unsupported employer claims and prompt-injection-style profile claims.

See [`docs/evaluation.md`](docs/evaluation.md).

## Security and privacy boundaries

- The browser never receives the LLM API key.
- Internal prompts and raw model reasoning are not exposed through the public SSE API.
- Portfolio evidence is treated as untrusted data rather than executable instructions.
- Browser origin checks reduce unauthorized third-party embedding.
- Per-IP and global rate limits bound abuse and provider spend.
- Request and history lengths are bounded.
- Aggregate telemetry does **not** retain prompts, answers, IP addresses, emails or conversation history.
- Feedback uses fixed categories only; no free-text visitor content is stored by the feedback module.
- Secrets are configured only through deployment environment variables.

See [`docs/security.md`](docs/security.md).

## Repository structure

```text
ASK-YOUSSEF-AI/
├── backend/
│   ├── app.py                 # FastAPI + SSE API
│   ├── agent.py               # agent orchestration
│   ├── rag.py                 # semantic retrieval primitives
│   ├── router.py              # deterministic language / intent router
│   ├── grounding.py           # citation + high-risk claim verifier
│   ├── observability.py       # aggregate privacy-safe telemetry
│   ├── feedback.py            # fixed-category feedback
│   ├── retrieval/
│   │   ├── hybrid.py          # BM25 + semantic + structured RRF
│   │   └── structured.py      # field-aware professional profile retrieval
│   └── data/
│       ├── profile.json       # synchronized structured profile
│       └── site/              # synchronized evidence snapshot
├── evaluation/
│   ├── dataset.json
│   ├── run_benchmark.py       # deterministic CI regression benchmark
│   ├── online_cases.json
│   └── run_online_eval.py     # deployed assistant smoke evaluation
├── scripts/
│   ├── sync_portfolio.py
│   └── build_structured_profile.py
├── tests/
├── web/
│   └── widget.js              # embeddable Shadow DOM UI
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── evaluation.md
│   └── security.md
├── Dockerfile
├── docker-compose.yml
└── render.yaml
```

## Local development

Create a local environment file from the example and provide your own server-side provider key:

```bash
cp .env.example .env
```

Then run either the Python backend directly or the production-like container configuration.

### Python

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Docker Compose

```bash
docker compose up --build
```

Useful checks:

```text
GET  /health
GET  /capabilities
GET  /pages
GET  /metrics
POST /chat
POST /feedback
```

## Run the deterministic benchmark

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Run the unit/regression tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## Production deployment

The repository includes a Render Blueprint in `render.yaml` and a complete deployment runbook in [`docs/deployment.md`](docs/deployment.md).

Production topology:

```text
GitHub Pages portfolio
        |
        | HTTPS / SSE
        v
Render FastAPI service
        |
        +--> Gemini model / embeddings
        +--> synchronized bundled portfolio corpus
```

The required deployment secret for the current provider path is:

```text
GEMINI_API_KEY=<server-side secret>
```

Do not commit real API credentials.

After deployment, validate `/health`, run the manual **Online assistant evaluation** workflow against the deployed URL, and only then integrate the widget publicly.

## Portfolio widget

`web/widget.js` is a zero-dependency embeddable client isolated with Shadow DOM.

Example:

```html
<script
  src="https://cdn.jsdelivr.net/gh/YOUSSEF-BT/ASK-YOUSSEF-AI@main/web/widget.js"
  data-api="https://YOUR-VERIFIED-BACKEND.example"
  data-title="Ask Youssef AI"
  data-subtitle="Professional Portfolio Copilot"
  data-accent="#20b2a6"
  defer>
</script>
```

The final production backend URL should only be added after the deployed online quality gate passes.

## CI

`.github/workflows/ci.yml` validates:

- Python compilation;
- JavaScript syntax;
- Docker Compose configuration;
- deterministic retrieval/grounding/runtime tests;
- JSON data integrity;
- deterministic benchmark thresholds;
- required project files;
- synchronized profile counts;
- stale upstream identity references;
- required MIT attribution.

The deterministic benchmark report is uploaded as a GitHub Actions artifact on every CI run.

## Deliberate non-claims

This repository does **not** currently claim:

- a learned cross-encoder reranker;
- universal semantic entailment checking;
- production-scale load guarantees;
- persistent distributed telemetry;
- subjective LLM-judge accuracy scores.

Those should only be advertised after they are actually implemented and measured.

## Attribution and license

Ask Youssef AI substantially adapts components from [`adityajn105/portfolio-chatbot`](https://github.com/adityajn105/portfolio-chatbot), originally released under the MIT License.

The original copyright and MIT terms are preserved in [`LICENSE`](LICENSE), with additional attribution details in [`NOTICE.md`](NOTICE.md).

Additional synchronization, structured retrieval, multilingual routing, grounding, evaluation, observability, production hardening and portfolio-specific work are part of the Ask Youssef AI implementation.

---

**Ask Youssef AI — Professional Portfolio Copilot**
