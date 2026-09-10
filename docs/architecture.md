# Architecture

## Production architecture

```text
YOUSSEF-BT.github.io (source of truth)
        |
        | scheduled + on-change synchronization
        v
Markdown evidence corpus + structured profile.json
        |
        +---------------------------+
        |                           |
        v                           v
Portfolio visitor             CI / evaluation
        |                           |
        v                           +--> deterministic regression benchmark
Ask Youssef AI widget              +--> deployed smoke evaluation harness
        |
        v
FastAPI /chat (SSE)
        |
        v
Deterministic language + intent router
        |
        +--> greeting / contact action / out-of-scope handling
        |
        +--> factual portfolio turn -> retrieval required
                                      |
                     +----------------+----------------+
                     |                |                |
                     v                v                v
             Structured profile     BM25         Semantic vectors
                     |                |                |
                     +----------------+----------------+
                                      |
                                      v
                          Reciprocal Rank Fusion
                         + bounded evidence boosts
                                      |
                                      v
                               search_site tool
                                      |
                                      v
                              ReAct-style LLM
                                      |
                                      v
                       Deterministic grounding gate
                                      |
                     +----------------+----------------+
                     |                                 |
                     v                                 v
              supported answer                  conservative abstention
              + real citations                  on unsafe literals
                     |
                     v
                  SSE client
                     |
                     v
          privacy-safe aggregate telemetry
```

## Source-of-truth synchronization

The public portfolio repository is authoritative for professional facts. The
synchronization pipeline extracts project data, skills, certifications,
experience, education, and public professional links without executing portfolio
JavaScript. It writes two retrieval views:

- `backend/data/site/`: concise Markdown evidence documents used by semantic and
  lexical retrieval.
- `backend/data/profile.json`: field-aware structured professional entities used
  for exact project, technology, employer, certification, skill, education, and
  public-link queries.

`.github/workflows/sync-portfolio.yml` refreshes these generated assets
periodically and whenever the synchronization code changes. Generated counts are
validated against `backend/data/site/manifest.json` before changes are committed.

## Retrieval layer

The production retriever uses three independent evidence signals over the same
public professional source of truth:

1. **Semantic retrieval** for conceptual similarity.
2. **BM25 lexical retrieval** for exact names, technologies, issuers, model IDs,
   and other sparse terms.
3. **Structured profile retrieval** for field-aware matching across projects,
   skills, certifications, work experience, education, and public links.

Candidate lists are fused with **Reciprocal Rank Fusion (RRF)**. Structured
results receive only a bounded confidence contribution, and exact-term evidence
gets a small deterministic boost. Retrieval traces retain semantic, lexical, and
structured ranks so quality regressions remain inspectable.

Both supported runtime paths are wired to the structured retriever:

- Render's configured `inprocess` transport builds `HybridRetriever` with the
  structured profile directly in the FastAPI process.
- The optional subprocess MCP transport builds the same structured-aware hybrid
  retriever inside `backend/mcp_server/blog_server.py`.

The `/health` endpoint reports the active retrieval strategy and structured
document count so a deployment can be checked without exposing user content.

## Routing and orchestration

`backend/router.py` performs deterministic English/French/Arabic language and
intent routing before the LLM is called. Portfolio-factual intents such as
projects, skills, certifications, experience, education, and contact information
are marked `requires_retrieval=true`.

The ReAct-style agent can use `search_site` and the explicit contact action. A
portfolio-factual turn cannot bypass retrieval and rely only on model memory.
Greetings and clearly out-of-scope general questions do not have to spend a
retrieval call. Tool inputs containing visitor contact information are not
exposed in the public SSE stream.

## Grounding and citation integrity

`backend/grounding.py` is a model-independent output boundary. When search
evidence was used, it:

- validates that bracket citations refer to sources actually retrieved for the
  current turn;
- removes hallucinated source labels;
- appends a real retrieved source citation when a supported answer omitted one;
- blocks unsupported high-risk literals such as invented numeric metrics, URLs,
  and email addresses;
- replaces unsafe high-risk claims with a conservative evidence-based
  abstention.

This verifier is intentionally not described as full semantic entailment. It is
a deterministic production guard for high-impact factual failures; broader
answer quality is evaluated separately.

## Evaluation

Two complementary evaluation layers are maintained.

### Deterministic regression benchmark

`evaluation/run_benchmark.py` runs without network calls or an LLM judge. It
measures multilingual routing, structured retrieval Hit@1/Hit@3/MRR, grounding
safety behavior, and synchronized-profile integrity against
`evaluation/dataset.json`. CI runs it in strict mode so a threshold regression
fails the build.

These scores are regression metrics on a fixed benchmark and must not be
presented as end-to-end LLM accuracy.

### Deployed-system smoke evaluation

`evaluation/run_online_eval.py` can test a real running API through `/health` and
`/chat`. It observes completion, required retrieval, expected source citations,
safety abstention, unnecessary-retrieval avoidance, and response latency. The
manual `.github/workflows/online-eval.yml` workflow publishes the resulting JSON
report as an artifact.

This layer exercises the actual model + routing + retrieval + tool orchestration
+ grounding + SSE path, while still using deterministic assertions rather than
claiming subjective semantic scoring.

## Observability and privacy

`backend/observability.py` records only process-lifetime aggregate operational
metrics: request/completion/error counts, retrieval-use counts, grounding
interventions, language/intent counters, and a bounded latency window. The public
`/metrics` endpoint returns those aggregates.

No prompts, answers, IP addresses, email addresses, tool inputs, or conversation
history are retained by this telemetry layer. Metrics reset on process restart.

## Security and production boundaries

- Portfolio evidence is the source of truth for claims about Youssef.
- Retrieved text is treated as untrusted data, not as executable instructions.
- Internal prompts and raw model reasoning are not emitted through the public SSE
  API.
- Browser Origin/Referer restrictions reduce unauthorized embedding of the
  public endpoint.
- Per-IP and global request limits bound public model spend and abuse.
- Secrets stay in deployment environment variables and are not committed.
- Contact actions require explicit visitor intent and user-provided contact data.
- Unsupported professional claims are rejected rather than guessed.

## Deliberate non-claims

A learned cross-encoder reranker, persistent distributed telemetry, semantic LLM
judge scores, and production-scale load guarantees are not claimed. They should
only be added to the project description after implementation and measurement.
