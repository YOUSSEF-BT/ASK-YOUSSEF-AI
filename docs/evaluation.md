# Evaluation & Quality Gates

Ask Youssef AI uses layered evaluation instead of relying on a single vague "accuracy" score.

The validation strategy separates **deterministic component quality, deployed end-to-end behavior, adversarial robustness, professional usefulness and security hygiene**.

A 100% pass rate below means every predefined assertion in that suite passed. It is not a claim that every arbitrary future model response will be universally correct.

## Final Validation Snapshot

| Validation Layer | Verified Result | Purpose |
|---|---:|---|
| Python unit & regression suite | **218 / 218** | Routing, retrieval, grounding, structured facts, multilingual output, recruiter/client reasoning, API contracts |
| Routing accuracy | **1.000** | Deterministic language and intent routing |
| Retrieval Hit@1 | **1.000** | Top-result retrieval quality |
| Retrieval Hit@3 | **1.000** | Top-3 retrieval coverage |
| Retrieval MRR | **1.000** | Retrieval ranking quality |
| Grounding safety | **1.000** | Unsupported high-risk literal and citation blocking |
| Profile integrity | **1.000** | Synchronization and structured-profile consistency |
| Career-state production regression | **3 / 3** | Current freelance role + simultaneous full-time/CDI search |
| Core production regression | **25 / 25** | End-to-end production API contract |
| Deep adversarial production audit | **20 / 20** | Safety, ambiguity, false claims and citation integrity |
| Human recruiter/client/visitor audit | **21 / 21** | Professional usefulness and evidence prioritization |
| Targeted client regressions | **2 / 2** | Client-risk calibration and strongest client-ready project ranking |
| Dependency audit | **Passed** | Known-vulnerability scan with `pip-audit` |
| Static security analysis | **Passed** | Python CodeQL analysis |

The final validated snapshot contains **218 passing Python tests**. That count may grow as new regressions are added.

## Evaluation Principles

### Deterministic components are tested deterministically

Routing, retrieval, structured facts, citation cleanup and synchronization integrity are evaluated without relying on another LLM as a judge.

### The real deployed system is tested

Offline correctness is not enough. Production suites call the public Vercel `/chat` SSE endpoint.

### Discovered failures become regressions

Meaningful weaknesses found during human or production testing are converted into repeatable tests.

### Public claims stay scoped

Passing a fixed suite demonstrates protection against those tested scenarios. It does not prove universal model correctness.

## Offline Deterministic Benchmark

`evaluation/run_benchmark.py` measures reproducible behavior including:

- multilingual routing;
- intent classification;
- structured retrieval;
- hybrid retrieval ranking;
- Hit@1;
- Hit@3;
- Mean Reciprocal Rank;
- grounding safety;
- synchronized-profile integrity.

| Metric | Required Threshold | Final Result |
|---|---:|---:|
| Routing accuracy | >= 0.950 | **1.000** |
| Retrieval Hit@1 | >= 0.750 | **1.000** |
| Retrieval Hit@3 | >= 0.950 | **1.000** |
| Retrieval MRR | >= 0.850 | **1.000** |
| Grounding safety | 1.000 | **1.000** |
| Profile integrity | 1.000 | **1.000** |

## Unit & Regression Suite

The final validated suite protects behavior such as:

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
- prompt and secret-exfiltration refusal;
- public API and SSE contracts;
- dependency and runtime configuration contracts.

## Career-State Production Regression

Dataset: `evaluation/career_cases.json`

This suite protects one professionally sensitive distinction: independent freelance activity does not imply that Youssef is unavailable for a full-time/CDI role.

**Final verified result: 3 / 3 passed.**

## Core Production Regression

Dataset: `evaluation/core_production_cases.json`

The core suite validates:

- English, French and Arabic profile questions;
- exact certification totals and issuer inventories;
- complete structured counts;
- Computer Vision, Python and RAG evidence;
- current professional role;
- full-time/CDI availability;
- public email handling;
- unavailable-phone handling;
- employer/issuer disambiguation;
- conversation-history follow-ups;
- exact technical identifiers;
- unsupported-employer abstention;
- prompt injection;
- greetings and scope control;
- citation integrity.

**Final verified result: 25 / 25 passed.**

## Deep Adversarial Production Audit

Dataset: `evaluation/deep_audit_cases.json`

This suite deliberately searches for failure. It covers:

- typo-heavy and conversational French;
- multilingual ambiguity;
- unsupported employers;
- unsupported salary, address and marital-status claims;
- fake-citation pressure;
- prompt injection;
- hidden-prompt requests;
- secret/API-key extraction attempts;
- current-work localization;
- Controlled RAG evidence;
- out-of-scope behavior;
- citation integrity.

**Final verified result: 20 / 20 passed.**

## Human Professional Audit

Automated assertions do not fully capture whether an answer is useful to a recruiter or client.

Final validation therefore included role-based questioning as:

- a recruiter evaluating experience, evidence, strengths and limitations;
- a client evaluating delivery readiness, RAG reliability, structured data and project risk;
- a normal visitor asking profile, contact and privacy questions.

**Final result: 21 / 21 scenarios passed.**

Two additional client-focused regressions also passed **2 / 2**.

## Multilingual Output Contract

The production output policy is explicit:

- English question -> English prose;
- French question -> French prose;
- Arabic question -> Arabic-script prose;
- technical names and citations may remain in canonical Latin form.

For history-aware prompts, the current visitor question takes precedence over older turns.

## Security Validation

Security validation is separate from semantic QA.

- `pip-audit` checks the resolved Python dependency graph for known vulnerabilities.
- GitHub CodeQL v4 performs static analysis for supported vulnerability classes.
- Application regressions protect secret boundaries, history roles, citation integrity, unsupported literals and public API contracts.

Automated scanning improves confidence but does not prove the absence of every vulnerability.

## Latency Interpretation

Latency is operational telemetry, not an SLA and not a correctness metric.

Individual request duration can vary because of:

- Vercel cold starts;
- provider load;
- failover;
- network conditions;
- question complexity;
- retrieval/generation path differences.

The project therefore does not advertise an enterprise latency guarantee.

## Reproducing the Checks

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
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

Dependency audit:

```bash
python -m pip install pip-audit
python -m pip_audit -r requirements.txt --strict
```

## Public Quality Positioning

The strongest defensible statement is that Ask Youssef AI is **extensively regression-tested across deterministic, production, adversarial, security and human professional evaluation layers**.

That is a stronger engineering claim than an unsupported universal "AI accuracy" percentage.
