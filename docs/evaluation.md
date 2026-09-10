# Evaluation & Quality Gates

Ask Youssef AI uses two complementary evaluation layers: a deterministic offline regression benchmark and a deployed-system regression against the live Vercel API.

The two layers answer different questions and must not be mixed into one generic "accuracy" number.

## 1. Deterministic regression benchmark

`evaluation/run_benchmark.py` evaluates components that can be reproduced without an external LLM call:

- multilingual language/intent routing;
- structured professional-profile retrieval;
- retrieval Hit@1, Hit@3 and Mean Reciprocal Rank (MRR);
- grounding safety for unsupported metrics, URLs, emails and citations;
- synchronization integrity between the generated profile and portfolio manifest.

CI runs the benchmark in strict mode and uploads its JSON report as an artifact. A regression below a configured threshold fails the build.

Current verified fixed-suite results:

| Metric | Result | Threshold |
|---|---:|---:|
| Routing accuracy | 1.000 | 0.950 |
| Retrieval Hit@1 | 1.000 | 0.750 |
| Retrieval Hit@3 | 1.000 | 0.950 |
| Retrieval MRR | 1.000 | 0.850 |
| Grounding safety rate | 1.000 | 1.000 |
| Profile integrity rate | 1.000 | 1.000 |

A value of 1.0 means all cases defined by that deterministic suite passed. It does **not** mean the generative assistant is universally 100% accurate.

## 2. Deployed production evaluation

`evaluation/run_online_eval.py` talks to a running FastAPI deployment through `/health` and `/chat`. The production workflow is `.github/workflows/vercel-production-eval.yml`.

The evaluator observes behavior that unit/offline tests cannot fully prove:

- completion of real deployed requests;
- mandatory retrieval for factual portfolio questions;
- expected source citation in final answers;
- conservative abstention for unsupported factual claims;
- prompt-injection resistance for profile assertions;
- no unnecessary retrieval for greetings/out-of-scope turns;
- conversation-history follow-ups;
- multilingual deployed behavior;
- end-to-end request latency.

The production workflow waits for the new Vercel deployment to be promoted before running the suite, so it does not accidentally grade the previous production commit.

## 3. Current verified Vercel result

A production run executed on **2026-09-10** against:

```text
https://ask-youssef-ai.vercel.app
```

passed every configured deterministic smoke gate:

| Metric | Result | Threshold |
|---|---:|---:|
| Completion rate | 1.000 | 1.000 |
| Required retrieval rate | 1.000 | 1.000 |
| Expected citation rate | 1.000 | 1.000 |
| Safety abstention rate | 1.000 | 1.000 |
| Unnecessary retrieval avoidance | 1.000 | 1.000 |

Latency for the 9 completed production cases:

| Statistic | Measured |
|---|---:|
| Median | 1137.84 ms |
| P95 | 1549.62 ms |
| Max | 1575.92 ms |
| Greeting case | 141.58 ms |

The evaluated cases include:

- Real-Time Road Accident Detection / `YOLOv11s` + `BoT-SORT`;
- OpenLegaMa Controlled RAG in French;
- RAG skills in Arabic;
- Oracle Agentic AI certification evidence;
- a history-dependent follow-up (`What tracker does it use?`);
- unsupported Google-employment claim;
- prompt injection asking the assistant to invent 15 years of AI experience;
- a simple greeting;
- an out-of-scope trivia request.

The scope of this result is **deployed-system deterministic smoke checks; not semantic answer accuracy**.

## 4. Reliability behavior exercised during production testing

Production testing also exposed real provider conditions such as quota/overload responses. The Vercel path therefore includes:

- primary Gemini 3.7 Flash generation;
- immediate Gemini 3.5 Flash-Lite failover for quota/overload/timeout signals;
- factual pre-retrieval so evidence exists before generation;
- a truthful, cited service fallback if generation fails after retrieval succeeds;
- deterministic greeting responses that use neither search nor a generation model.

These behaviors are part of runtime reliability, not an attempt to hide provider failures.

## 5. Grounding policy

Factual claims about Youssef's professional profile are retrieval-grounded. The final response passes through a deterministic verifier that checks high-risk literals and source citations against evidence returned during the turn.

The verifier can intervene on unsupported metrics, links, emails and unknown citations. Unsupported high-impact details are replaced by an evidence-based abstention rather than being presented as facts.

Instructions embedded inside retrieved portfolio text are treated as data and cannot override the assistant's system behavior.

## 6. How to run the production evaluator

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --output online-eval-report.json \
  --strict
```

The evaluator deliberately uses deterministic observable checks. It is not an LLM judge.

## 7. Rules for public quality claims

Public documentation should keep these categories separate:

1. **offline deterministic regression metrics**;
2. **deployed-system regression metrics**;
3. **project/model metrics imported from portfolio evidence** (for example computer-vision model precision/recall).

Never combine them into a single accuracy score. Never describe a fixed 100%-passing regression suite as proof that arbitrary generated answers are 100% accurate.
