# Evaluation & Quality Gates

Ask Youssef AI uses layered deterministic QA instead of a single vague "accuracy" score. Offline tests validate components; deployed suites validate the real Vercel API; an adversarial suite deliberately searches for regressions and unsafe behavior.

A 100% pass rate below means **all predefined assertions in that suite passed**. It is not a claim that arbitrary future model answers are universally 100% correct.

## 1. Offline deterministic benchmark

`evaluation/run_benchmark.py` checks reproducible components without depending on a live LLM response:

- multilingual language/intent routing;
- structured-profile retrieval;
- retrieval Hit@1, Hit@3 and Mean Reciprocal Rank;
- grounding safety for unsupported metrics, URLs, emails and citations;
- synchronization integrity between the portfolio manifest and structured profile.

Current verified results:

| Metric | Result | Threshold |
|---|---:|---:|
| Routing accuracy | 1.000 | 0.950 |
| Retrieval Hit@1 | 1.000 | 0.750 |
| Retrieval Hit@3 | 1.000 | 0.950 |
| Retrieval MRR | 1.000 | 0.850 |
| Grounding safety rate | 1.000 | 1.000 |
| Profile integrity rate | 1.000 | 1.000 |

CI also compiles the backend, validates synchronized data, validates the widget JavaScript and runs the regression/unit-test suite.

## 2. Live career-state regression

Dataset: `evaluation/career_cases.json`

This small fail-fast suite protects a high-risk professional fact that previously exposed a misleading inference: current freelance work does **not** imply that Youssef is not looking for a full-time/CDI role. The portfolio explicitly documents both facts.

The suite checks:

- current role in French with localized fields;
- explicit full-time/CDI availability in French;
- explicit full-time availability in English;
- required citations and structured retrieval behavior.

Verified against `https://ask-youssef-ai.vercel.app` on **2026-09-11**:

- **3/3 cases passed**;
- Median: **77.53 ms**;
- P95: **171.56 ms**;
- Max: **182.01 ms**.

## 3. Live strict core production regression

Dataset: `evaluation/core_production_cases.json`

This is the main end-to-end deployed regression. It sends requests to the real `/chat` SSE endpoint and verifies observable behavior including:

- English/French/Arabic profile questions;
- exact certification counts and issuer inventories;
- the three Oracle credentials;
- complete structured counts;
- Computer Vision, Python and RAG project facts;
- current role and job-search status;
- public email and unavailable-phone handling;
- employer/issuer disambiguation;
- conversation-history follow-ups;
- exact identifiers such as `YOLOv11s` and `BoT-SORT`;
- unsupported-employer abstention;
- prompt-injection handling;
- greeting and out-of-scope paths;
- citation integrity.

Verified against production on **2026-09-11**:

- **25/25 cases passed**;
- every configured strict metric passed at **1.000 / 1.000**;
- Median: **102.16 ms**;
- P95: **2.674 s**;
- Max: **3.842 s**.

The strict metrics include completion, required retrieval, expected citations, required sources, expected content, forbidden-content absence, safety abstention, citation integrity and unnecessary-retrieval avoidance where applicable.

## 4. Deep adversarial production audit

Dataset: `evaluation/deep_audit_cases.json`

Workflow: `.github/workflows/deep-production-audit.yml`

This is intentionally a bug-hunting suite rather than a happy-path demo. It tests:

- conversational French and typo-heavy phrasing;
- biography/summary requests that must not be mistaken for contact actions;
- current-work localization;
- full-time/CDI follow-ups;
- Oracle ordinal follow-ups;
- employer vs certification-issuer confusion;
- unsupported salary, home address and marital status;
- false-employer assertions;
- prompt injection;
- fake citation pressure;
- hidden system prompt/internal reasoning/API-key exfiltration requests;
- OpenLegaMa Controlled RAG;
- Arabic career/employer cases;
- out-of-scope trivia.

Verified against production on **2026-09-11**:

- **20/20 cases passed**;
- Completion: **1.000 / 1.000**;
- Required retrieval: **1.000 / 1.000**;
- Required sources: **1.000 / 1.000**;
- Expected content: **1.000 / 1.000**;
- Forbidden-content absence: **1.000 / 1.000**;
- Safety abstention: **1.000 / 1.000**;
- Citation integrity: **1.000 / 1.000**;
- Unnecessary-retrieval avoidance: **1.000 / 1.000**;
- Median: **132.56 ms**;
- P95: **2.281 s**;
- Max: **3.399 s**.

The final adversarial run contained no unknown or malformed citations.

## 5. Why there are several suites

A single benchmark can hide entire classes of failures. The project therefore separates concerns:

1. **Offline CI** catches deterministic code/data regressions quickly.
2. **Career regression** fails fast on a professionally sensitive state.
3. **Core production regression** checks the real deployed system broadly.
4. **Deep adversarial audit** actively probes safety, ambiguity, language and regression edge cases.

GitHub Actions waits for Vercel production promotion before deployed tests. Long suites are paced so the test harness does not trigger the public per-IP rate limit and create false failures.

## 6. Reliability behavior exercised by tests

Production testing has encountered real provider conditions such as quota/overload responses. The deployed path therefore includes:

- Gemini 3.7 Flash as the primary generator;
- immediate Gemini 3.5 Flash-Lite failover for quota/overload/timeout signals;
- local FastEmbed/ONNX retrieval rather than consuming Gemini embedding quota;
- factual pre-retrieval so evidence exists before generative synthesis;
- deterministic precision facts for exact/high-risk portfolio questions;
- evidence-based fallback when generation fails after successful retrieval;
- deterministic greetings, scope responses and secret-exfiltration refusals.

## 7. Grounding policy

Factual claims about Youssef's public professional profile must be grounded in synchronized evidence. The final response passes through deterministic checks that can reject unsupported high-impact literals and unknown citations.

Retrieved portfolio content is treated as untrusted data, never as higher-priority instructions. Requests to reveal hidden prompts, internal reasoning, API keys or private configuration are refused.

## 8. Reproducing the checks

Offline benchmark:

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Core deployed suite:

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --dataset evaluation/core_production_cases.json \
  --output online-eval-report.json \
  --strict
```

Deep adversarial suite:

```bash
python evaluation/run_online_eval.py \
  --api-url "https://ask-youssef-ai.vercel.app" \
  --origin "https://youssef-bt.github.io" \
  --dataset evaluation/deep_audit_cases.json \
  --output deep-audit-report.json \
  --delay 11 \
  --strict
```

## 9. Rules for public quality claims

Keep these categories separate:

- offline deterministic regression metrics;
- deployed-system regression metrics;
- adversarial QA results;
- model/project metrics imported from portfolio evidence, such as Computer Vision precision/recall.

Never combine them into a universal assistant-accuracy percentage. A passing fixed suite demonstrates protection against the tested regressions; it does not eliminate the possibility of future bugs or model/provider variability.
