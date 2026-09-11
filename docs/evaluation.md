# Evaluation & Quality Gates

Ask Youssef AI uses layered evaluation instead of relying on a single vague "accuracy" score.

The validation strategy separates **deterministic component quality, deployed end-to-end behavior, adversarial robustness, professional usefulness and security hygiene**.

A 100% pass rate below means that every predefined assertion in that suite passed. It is **not** a claim that every arbitrary future model response will be universally correct.

## Final Validation Snapshot

| Validation Layer | Verified Result | Purpose |
|---|---:|---|
| Python unit & regression suite | **218 / 218** | Routing, retrieval, grounding, structured facts, multilingual output, recruiter/client reasoning, API contracts |
| Offline routing accuracy | **1.000** | Deterministic language/intent routing |
| Retrieval Hit@1 | **1.000** | Top-result retrieval quality |
| Retrieval Hit@3 | **1.000** | Top-3 retrieval coverage |
| Retrieval MRR | **1.000** | Retrieval ranking quality |
| Grounding safety | **1.000** | Unsupported high-risk literal/citation blocking |
| Profile integrity | **1.000** | Synchronization and structured-profile consistency |
| Career-state production regression | **3 / 3** | Current work + simultaneous full-time/CDI availability |
| Core production regression | **25 / 25** | End-to-end production API contract |
| Deep adversarial production audit | **20 / 20** | Safety, multilingual ambiguity, false claims, citation integrity |
| Human recruiter/client/visitor audit | **21 / 21** | Professional usefulness and evidence prioritization |
| Targeted final client regressions | **2 / 2** | Client-risk calibration and strongest client-ready project selection |
| Dependency audit | **Passed** | Known vulnerable dependency detection with `pip-audit` |
| Static analysis | **Passed** | Python CodeQL security analysis |

The exact unit-test count can increase as new regressions are added. The final validated snapshot described here contains **218 passing tests**.

## Evaluation Philosophy

The project follows four principles:

### 1. Test deterministic components deterministically

Routing, retrieval, structured facts, citation cleanup and synchronization integrity should be evaluated without asking another LLM to judge them.

### 2. Test the real deployed system

Offline correctness is not enough. The public Vercel API is exercised directly through SSE production evaluations.

### 3. Convert discovered failures into regressions

When a manual recruiter/client audit exposes a real weakness, that failure class should become a repeatable test rather than a one-time manual observation.

### 4. Keep claims scoped

A fixed suite passing at 100% demonstrates protection against those tested scenarios. It does not prove universal model correctness.

## Offline Deterministic Benchmark

`evaluation/run_benchmark.py` measures reproducible components without depending on a live generative response.

It covers:

- multilingual routing;
- intent classification;
- structured retrieval;
- hybrid retrieval ranking;
- Hit@1;
- Hit@3;
- Mean Reciprocal Rank;
- grounding safety;
- synchronized-profile integrity.

Maintained thresholds:

| Metric | Required Threshold | Final Result |
|---|---:|---:|
| Routing accuracy | >= 0.950 | **1.000** |
| Retrieval Hit@1 | >= 0.750 | **1.000** |
| Retrieval Hit@3 | >= 0.950 | **1.000** |
| Retrieval MRR | >= 0.850 | **1.000** |
| Grounding safety | 1.000 | **1.000** |
| Profile integrity | 1.000 | **1.000** |

## Unit and Regression Suite

The final validated Python suite contains **218 passing tests**.

Important protected behaviors include:

- recruiter-style evidence ranking;
- NEXTRONIC professional-experience recognition;
- Computer Vision evidence prioritization;
- OpenLegaMa RAG evidence and client-ready positioning;
- Agentic AI calibration without overstating public proof;
- PostgreSQL and structured-data evidence;
- exact top-N project responses;
- false-employer handling;
- issuer/employer disambiguation;
- current freelance + CDI/full-time positioning;
- English/French/Arabic routing;
- Arabic output-language enforcement;
- history-aware language behavior;
- citation cleanup;
- unsupported literal blocking;
- private-profile handling;
- prompt/secret-exfiltration refusal;
- public API and SSE contracts;
- dependency/runtime configuration contracts.

## Career-State Production Regression

Dataset: `evaluation/career_cases.json`

This suite protects a professionally sensitive distinction:

> independent freelance activity does not imply that Youssef is unavailable for a full-time/CDI role.

The deployed API must represent both facts consistently and in the visitor's language.

Final verified result:

**3 / 3 passed**

## Core Production Regression

Dataset: `evaluation/core_production_cases.json`

This is the main end-to-end public API evaluation.

It validates:

- English, French and Arabic profile questions;
- exact certification totals;
- Oracle certification inventory;
- complete structured counts;
- Computer Vision evidence;
- Python evidence;
- RAG evidence;
- current professional role;
- full-time/CDI availability;
- public email handling;
- unavailable-phone handling;
- employer/issuer disambiguation;
- conversation-history follow-ups;
- exact technical identifiers;
- unsupported-employer abstention;
- prompt injection;
- greetings;
- out-of-scope handling;
- citation integrity.

Final verified result:

**25 / 25 passed**

All configured strict correctness and safety metrics passed at their required thresholds.

## Deep Adversarial Production Audit

Dataset: `evaluation/deep_audit_cases.json`

The adversarial suite deliberately searches for failure instead of demonstrating only happy paths.

It covers:

- typo-heavy and conversational French;
- multilingual ambiguity;
- unsupported employers;
- unsupported salary/address/marital-status claims;
- fake-citation pressure;
- prompt injection;
- hidden prompt requests;
- secret/API-key extraction attempts;
- current-work localization;
- Controlled RAG evidence;
- out-of-scope behavior;
- citation integrity.

Final verified result:

**20 / 20 passed**

## Human Professional Audit

Automated tests cannot fully answer whether a recruiter or client would find a response professionally useful.

Final validation therefore included role-based questioning as:

- a recruiter evaluating experience, evidence, strengths and limitations;
- a client evaluating delivery readiness, RAG reliability, structured data and project risk;
- a normal visitor asking simple profile, contact and privacy questions.

The final human audit passed:

**21 / 21 scenarios**

Two additional client-focused cases were rechecked independently:

**2 / 2 passed**

These checks specifically protected:

- candid client-risk positioning;
- OpenLegaMa as the strongest public client-ready AI/RAG product where appropriate.

## Multilingual Output Contract

The production output policy is explicit:

- English question -> English prose;
- French question -> French prose;
- Arabic question -> Arabic-script prose;
- technical names and citations may remain in canonical Latin form.

For history-aware prompts, the language of the current visitor question takes precedence over older turns or internal wrapper text.

## Security Validation

Security validation is split from semantic QA.

### Dependency audit

`pip-audit` evaluates the resolved Python dependency graph against known vulnerability data.

### Static analysis

GitHub CodeQL v4 analyzes the Python codebase for supported vulnerability classes.

### Application security regressions

The unit/regression suite also protects:

- secret-exfiltration boundaries;
- invalid history roles;
- unsupported citations;
- unsafe literal claims;
- public endpoint contracts;
- synchronized profile integrity.

Automated scanning improves confidence but does not prove the absence of every vulnerability.

## Latency Interpretation

Latency is operational telemetry, **not an SLA and not a correctness metric**.

Individual request duration can vary due to:

- Vercel cold starts;
- provider load;
- model failover;
- network conditions;
- question complexity;
- retrieval/generation path differences.

The project therefore does not advertise an enterprise latency guarantee.

## Reproducing the Evaluation

Offline benchmark:

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Unit/regression suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Core production suite:

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

Dependency audit:

```bash
python -m pip install pip-audit
python -m pip_audit -r requirements.txt --strict
```

## Public Quality Claims

Keep these categories separate:

- deterministic offline metrics;
- deployed-system regression results;
- human professional QA;
- security scan results;
- project-specific ML metrics imported from portfolio evidence.

They should never be merged into a universal "assistant accuracy" percentage.

The strongest defensible statement is that Ask Youssef AI is **extensively regression-tested across deterministic, production, adversarial, security and human professional evaluation layers**.
