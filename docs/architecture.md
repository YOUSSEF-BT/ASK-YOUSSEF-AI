# Architecture

## Production architecture

```text
YOUSSEF-BT.github.io (source of truth)
        |
        | scheduled + on-change synchronization
        v
Markdown evidence corpus + structured profile.json
        |
        +--> public-contact enrichment
        +--> career-status enrichment + localization
        +--> citable structured-profile aggregates
        |
        +---------------------------+
        |                           |
        v                           v
Portfolio visitor             CI / deployed QA
        |                           |
        v                           +--> deterministic offline benchmark
Ask Youssef AI widget              +--> career-state regression
        |                           +--> strict core regression
        | HTTPS / SSE               +--> deep adversarial audit
        v
Vercel FastAPI /chat
        |
        v
Deterministic EN / FR / AR router
        |
        +--> greeting / out-of-scope / secret request
        |          -> deterministic response
        |
        +--> exact/high-risk structured fact
        |          -> complete profile.json
        |          -> deterministic answer + source IDs
        |
        +--> open factual portfolio turn
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
      + real citations     evidence fallback
                   |
                   v
                SSE client
                   |
                   v
        privacy-safe aggregate telemetry
```

## Source-of-truth synchronization

The public portfolio repository is authoritative for public professional facts. The synchronization pipeline extracts projects, skills, certifications, experience, education and professional contact information without executing portfolio JavaScript.

It creates complementary evidence views:

- `backend/data/site/` — Markdown pages used by semantic/lexical retrieval and citation cards;
- `backend/data/profile.json` — structured entities used by exact-fact and field-aware retrieval;
- `career-status.md` — explicit public full-time/CDI availability evidence;
- `structured-profile.md` — citable synchronized aggregate counts.

Dedicated enrichment scripts preserve information that the generic parser should not infer:

- `scripts/enrich_public_contact.py` synchronizes published contact evidence such as `mailto:` email;
- `scripts/enrich_career_status.py` extracts explicit career availability and localized work-experience fields from the portfolio.

`.github/workflows/sync-portfolio.yml` refreshes generated assets periodically and when synchronization logic changes. It validates entity counts, email evidence, career availability and generated documents before committing changes.

Current production health reports **16 evidence pages, 161 chunks and 81 structured documents**.

## Deterministic routing

`backend/router.py` detects English, French and Arabic and assigns intent before any generation call.

Important properties:

- portfolio facts require evidence retrieval;
- colloquial/typo-heavy French variants are recognized;
- short ordinal/history follow-ups are returned to grounded handling;
- greetings avoid retrieval and generation;
- unrelated trivia stays outside portfolio scope;
- hidden prompt/internal reasoning/API-key extraction requests are refused deterministically.

The router is deliberately conservative: forcing a factual turn through evidence is preferable to allowing an unsupported profile answer.

## Precision structured-fact lane

`backend/precision_facts.py` and `backend/structured_facts.py` handle questions where a top-k retrieval result must **never** be treated as the complete portfolio.

Examples include:

- total certification count and issuer breakdown;
- Oracle certification inventory and ordinal follow-ups;
- project/skill/experience/education/contact counts;
- complete Python/Computer Vision/RAG project facts supported by structured metadata;
- employer checks and issuer/employer disambiguation;
- current professional role;
- explicit CDI/full-time availability;
- selected high-value project facts such as OpenLegaMa Controlled RAG.

This lane reads the complete synchronized `profile.json`, emits observable `structured_profile` tool usage and returns canonical source IDs. It removes an entire class of errors where a model could mistake the first few retrieved results for the full inventory.

## Hybrid retrieval layer

Open-ended factual questions use three independent signals over the same source of truth:

1. **FastEmbed semantic retrieval** for conceptual similarity;
2. **BM25 lexical retrieval** for names, technologies, issuers and exact identifiers;
3. **structured profile retrieval** for field-aware matching.

Candidate lists are fused with **Reciprocal Rank Fusion (RRF)** plus bounded deterministic evidence boosts.

### Vercel production path

Vercel uses `MCP_TRANSPORT=inprocess`. `HybridRetriever` uses the bundled corpus and profile. The `BAAI/bge-small-en-v1.5` FastEmbed/ONNX model is prepared during the Vercel build and reused at runtime, avoiding Gemini embedding quota and avoiding a model download during a visitor request.

### Alternative runtime path

The subprocess MCP path uses the same structured-aware hybrid retrieval design. Docker/Render configuration remains available as an alternative/local path but is not the active public production host.

## Provider reliability

The primary generation model is **Gemini 3.7 Flash**. On quota, overload, timeout or related transient failures, the runtime switches quickly to **Gemini 3.5 Flash-Lite**.

Generation retry/timeout budgets are bounded for the serverless request window. If generation still fails after evidence retrieval succeeds, the assistant returns a truthful evidence-based service fallback rather than inventing a requested fact or ending with an empty error.

Exact precision-fact answers do not depend on a generative model at all.

## Grounding and citation integrity

`backend/grounding.py` is a model-independent output boundary. It can:

- validate bracketed source IDs against evidence available for the turn;
- remove unknown/hallucinated citations;
- normalize canonical source IDs;
- block unsupported high-risk numbers, URLs and email literals where applicable;
- replace unsupported high-impact claims with an evidence-based abstention;
- preserve the visitor language for safety/fallback responses.

Retrieved portfolio text is treated as untrusted data, not executable instructions.

This boundary is not presented as universal semantic entailment. Broader quality is covered by production regression and adversarial QA.

## Evaluation architecture

### Offline deterministic CI

`evaluation/run_benchmark.py` measures multilingual routing, retrieval Hit@1/Hit@3/MRR, grounding safety and profile-integrity checks without an LLM judge.

### Career-state production regression

`evaluation/career_cases.json` verifies the current freelance role, localized French response and explicit full-time/CDI availability. The verified production run on **2026-09-11** passed **3/3** cases.

### Strict core production regression

`evaluation/core_production_cases.json` exercises the actual deployed `/chat` SSE endpoint. The verified production run on **2026-09-11** passed **25/25** cases with every configured strict metric at `1.0`. Median latency was **102.16 ms**, P95 **2.674 s**, max **3.842 s**.

### Deep adversarial production audit

`evaluation/deep_audit_cases.json` deliberately probes ambiguous language, typos, false employers, unsupported personal details, fake citations, prompt injection, secret extraction, localization, Controlled RAG and out-of-scope behavior.

The verified production audit on **2026-09-11** passed **20/20** cases. Every configured strict metric passed at `1.0`; no unknown or malformed citations were observed. Median latency was **132.56 ms**, P95 **2.281 s**, max **3.399 s**.

These are fixed deterministic QA suites, not a universal claim of perfect semantic accuracy.

## Observability and privacy

`backend/observability.py` keeps process-lifetime aggregate operational counters and a bounded latency window. `/metrics` exposes only aggregates.

The telemetry layer does not retain prompts, answers, IP addresses, email addresses, tool inputs or conversation history. Metrics reset when a process restarts.

## Security boundaries

- Portfolio evidence is the source of truth for Youssef's public professional facts.
- Provider secrets remain server-side.
- Browser Origin/Referer restrictions reduce unauthorized embedding.
- Request/history sizes and history roles are validated.
- Per-IP/global limits bound public abuse and provider usage.
- Internal prompts and private reasoning are not emitted through SSE.
- Fake-source and prompt-injection pressure cannot authorize unsupported profile claims.
- Unsupported professional/personal claims are refused rather than guessed.
- Contact actions require explicit visitor intent and visitor-provided contact data.
- The frontend contains only the public Vercel API URL, never `GEMINI_API_KEY`.

## Deliberate non-claims

The system does not claim universal semantic entailment verification, arbitrary-question 100% accuracy, persistent distributed observability or enterprise SLA/load guarantees. Such claims should only be added after the corresponding capabilities are implemented and measured.
