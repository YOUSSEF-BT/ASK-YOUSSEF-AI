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
Ask Youssef AI widget              +--> Vercel production regression
        |
        | HTTPS / SSE
        v
Vercel FastAPI /chat
        |
        v
Deterministic EN / FR / AR router
        |
        +--> greeting ----------> deterministic local response
        |
        +--> out-of-scope ------> scoped model response, no portfolio retrieval
        |
        +--> factual portfolio turn
                    |
             retrieval required
                    |
       +------------+-------------+
       |            |             |
       v            v             v
   Structured      BM25       FastEmbed semantic
    Profile                    vectors / ONNX
       |            |             |
       +------------+-------------+
                    |
                    v
        Reciprocal Rank Fusion (RRF)
        + bounded evidence boosts
                    |
                    v
               search_site
                    |
                    v
          Gemini 3.7 Flash
             |          |
       transient        success
        failure         |
             v          |
     Gemini 3.5 Flash-Lite
             |          |
             +-----+----+
                   |
                   v
        deterministic grounding gate
              /                 \
             v                   v
      grounded answer      safe abstention /
      + real citations     cited service fallback
                   |
                   v
                SSE client
                   |
                   v
        privacy-safe aggregate telemetry
```

## Source-of-truth synchronization

The public portfolio repository is authoritative for professional facts. The synchronization pipeline extracts project data, skills, certifications, experience, education and public professional links without executing portfolio JavaScript.

It writes two retrieval views:

- `backend/data/site/` — concise Markdown evidence used by semantic and lexical retrieval;
- `backend/data/profile.json` — structured entities used for exact project, technology, employer, certification, skill, education and public-link queries.

`.github/workflows/sync-portfolio.yml` refreshes these generated assets periodically and when synchronization logic changes. Generated counts are checked against `backend/data/site/manifest.json`.

## Retrieval layer

The production retriever combines three independent evidence signals over the same professional source of truth:

1. **FastEmbed semantic retrieval** for conceptual similarity;
2. **BM25 lexical retrieval** for exact names, technologies, issuers and sparse identifiers;
3. **structured profile retrieval** for field-aware matching across projects, skills, certifications, work experience, education and public links.

Candidate lists are fused with **Reciprocal Rank Fusion (RRF)**. Structured results receive a bounded confidence contribution and exact-term evidence can receive a small deterministic boost. Retrieval traces retain independent ranks so regressions remain inspectable.

### Vercel production path

Vercel uses `MCP_TRANSPORT=inprocess`. The FastAPI process builds `HybridRetriever` using the bundled synchronized corpus, the structured profile and local FastEmbed/ONNX vectors. The FastEmbed model is prepared during the Vercel build to avoid downloading model files on a user request.

### Alternative runtime path

The optional subprocess MCP transport builds the same structured-aware hybrid retriever inside `backend/mcp_server/blog_server.py`. Docker/Render files remain available as alternative deployment configurations, but they are not the active public production path.

The `/health` endpoint reports the active retrieval strategy, corpus counts and structured-document count without exposing conversation content.

## Routing and orchestration

`backend/router.py` performs deterministic English/French/Arabic language and intent routing before the LLM is called.

Portfolio-factual intents such as projects, skills, certifications, experience, education and public contact information are marked `requires_retrieval=true`.

On Vercel, factual requests are **pre-retrieved deterministically** before the generation call. This means grounding does not depend on Gemini choosing to call `search_site`, and it removes an unnecessary model round trip from the common path.

Short history-dependent references such as “What about the second one?”, French equivalents and Arabic equivalents are also routed back through grounded retrieval.

Greetings use a deterministic localized response and therefore consume neither retrieval nor Gemini generation. Clearly out-of-scope requests avoid portfolio retrieval and are redirected toward the assistant's portfolio scope.

## Provider reliability

The production generation path starts with **Gemini 3.7 Flash**. On quota, overload, timeout or related transient provider signals, the Vercel runtime immediately switches to **Gemini 3.5 Flash-Lite** rather than spending the serverless request window retrying the same unavailable primary model.

Generation timeout/retry settings are bounded to fit inside the Vercel Hobby function duration.

If generation still fails after factual retrieval has already succeeded, the assistant does not invent a requested fact and does not end with an empty error-only turn. It returns a truthful service message explaining that the generated answer could not be verified, together with source IDs that were actually retrieved. The normal grounding boundary still processes that final output.

## Grounding and citation integrity

`backend/grounding.py` is a model-independent output boundary. When search evidence was used, it can:

- validate that bracket citations refer to sources retrieved for the current turn;
- remove hallucinated source labels;
- append a real retrieved citation when supported evidence exists but the answer omitted one;
- block unsupported high-risk literals such as invented numeric metrics, URLs and email addresses;
- replace unsafe high-risk claims with a conservative evidence-based abstention.

This verifier is intentionally not described as full semantic entailment. It is a deterministic guard for high-impact factual failures; broader answer quality is evaluated separately.

## Evaluation

Two complementary evaluation layers are maintained.

### Deterministic regression benchmark

`evaluation/run_benchmark.py` runs without provider calls or an LLM judge. It measures multilingual routing, retrieval Hit@1/Hit@3/MRR, grounding-safety behavior and synchronized-profile integrity against `evaluation/dataset.json`.

CI runs it in strict mode so a threshold regression fails the build. These scores are fixed regression metrics and must not be presented as universal end-to-end LLM accuracy.

### Vercel deployed-system regression

`evaluation/run_online_eval.py` tests the running production API through `/health` and `/chat`.

`.github/workflows/vercel-production-eval.yml` automatically waits for the production deployment promotion and then checks completion, required retrieval, expected citations, safety abstention, unnecessary-retrieval avoidance, history-aware follow-ups and response latency.

The verified 2026-09-10 production run passed all five configured rates at `1.0`, with 9/9 completed cases, median latency of approximately 1.14 seconds and P95 of approximately 1.55 seconds.

This layer exercises the actual router + retrieval + model/failover + grounding + SSE path while still using deterministic assertions rather than subjective semantic scoring.

## Observability and privacy

`backend/observability.py` stores only process-lifetime aggregate operational metrics: request/completion/error counts, retrieval-use counts, grounding interventions, language/intent counters and a bounded latency window. `/metrics` exposes those aggregates.

No prompts, answers, IP addresses, email addresses, tool inputs or conversation history are retained by this telemetry layer. Metrics reset on process restart.

## Security and production boundaries

- Portfolio evidence is the source of truth for claims about Youssef.
- Retrieved text is treated as untrusted data, not executable instructions.
- Internal prompts and raw model reasoning are not emitted through the public SSE API.
- Browser Origin/Referer restrictions reduce unauthorized embedding.
- Per-IP and global request limits bound public provider spend and abuse.
- Secrets stay in server-side deployment environment variables.
- Contact actions require explicit visitor intent and visitor-provided contact data.
- Unsupported professional claims are rejected rather than guessed.
- The frontend contains only the public Vercel API URL, never `GEMINI_API_KEY`.

## Deliberate non-claims

The project does not claim universal semantic entailment checking, subjective LLM-judge accuracy, persistent distributed telemetry or enterprise-scale load/availability guarantees. Such claims should only be added after the corresponding capability is implemented and measured.
