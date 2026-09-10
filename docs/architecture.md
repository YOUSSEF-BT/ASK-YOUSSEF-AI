# Architecture

## Target production architecture

```text
Any portfolio visitor
        |
        v
Ask Youssef AI widget
        |
        v
    FastAPI
        |
Intent + language routing
        |
+-------+----------------+----------------+
|                        |                |
v                        v                v
Structured retrieval  Lexical search  Vector search
|                        |                |
+------------------------+----------------+
                         |
                         v
                  Rank fusion + reranking
                         |
                         v
                    Evidence builder
                         |
                         v
                        LLM
                         |
                         v
               Grounding + citation checks
                         |
                 +-------+-------+
                 |               |
                 v               v
               Answer          Abstain
```

## Design principles

- Public professional data only.
- Portfolio evidence is the source of truth for claims about Youssef.
- Exact facts should prefer structured data; semantic questions use retrieval.
- Unsupported claims must be rejected rather than guessed.
- Retrieved content is treated as untrusted data for prompt-injection resistance.
- Provider-specific LLM/embedding choices should remain replaceable.


## Implemented retrieval layer

The current search layer combines the existing semantic vector retriever with an
independent in-memory BM25-style lexical index. Candidate lists are merged with
Reciprocal Rank Fusion (RRF), followed by a small deterministic exact-evidence
boost. Retrieval traces are attached to each result for future evaluation and
observability.

A learned cross-encoder/API reranker is deliberately not claimed yet; it will be
added only after it can be measured against the deterministic baseline.
