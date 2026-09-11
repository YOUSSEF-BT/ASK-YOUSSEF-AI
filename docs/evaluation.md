# Evaluation & Quality Gates

Ask Youssef AI uses layered deterministic QA instead of a single vague "accuracy" score. Offline tests validate reproducible components; deployed suites validate the real Vercel API; adversarial and persona-oriented checks deliberately search for regressions, unsafe behavior, misleading professional claims, and language drift.

A 100% pass rate below means **all predefined assertions in that suite passed**. It is not a claim that every arbitrary future model answer will be universally correct.

## Current validation status

The current production architecture is validated through the following layers:

| Layer | Current verified result | Purpose |
|---|---:|---|
| Python unit/regression suite | 218+ tests* | Routing, grounding, structured facts, retrieval, recruiter/client reasoning, widget/runtime contracts, output-language policy |
| Offline deterministic benchmark | All configured gates passed | Routing, retrieval Hit@1/Hit@3/MRR, grounding safety, profile integrity |
| Career-state production regression | 3/3 passed | Current freelance role + simultaneous full-time/CDI search |
| Core production regression | 25/25 passed | End-to-end public API contract |
| Deep adversarial production audit | 20/20 passed | Prompt injection, false claims, private data, multilingual ambiguity, citation integrity |
| Human recruiter/client/visitor audit | 21/21 final scenarios passed | Professional usefulness and evidence ranking |
| Targeted final client regressions | 2/2 passed | Client-risk calibration and OpenLegaMa client-ready ranking |
| Dependency vulnerability audit | `pip-audit` gate | Known-vulnerability scan of the resolved Python dependency graph |
| Static security analysis | CodeQL | Python static security analysis on push/PR/schedule |

\*The exact unit-test count can increase as new regressions are added; the CI result is authoritative.

## Latency interpretation

Latency is **observed telemetry, not an SLA and not a correctness gate**. Vercel cold starts, provider load, Gemini failover, network conditions and question complexity can materially change individual response times.

Older latency numbers in repository history or README benchmark snapshots are valid for the specific runs that produced them, but they should not be interpreted as the latest guaranteed performance. During final 2026-09-11 validation, the system remained correct while at least one provider-dependent adversarial request took roughly 11 seconds. The service therefore makes no enterprise latency guarantee.

For this portfolio-scale product, the quality gates prioritize:

1. completion;
2. factual evidence and required retrieval;
3. citation integrity;
4. absence of unsupported high-risk claims;
5. correct professional positioning;
6. safe abstention and privacy behavior;
7. language consistency;
8. then latency as an operational observation.

## 1. Offline deterministic CI benchmark

`evaluation/run_benchmark.py` checks reproducible components without depending on a live LLM response:

- multilingual language/intent routing;
- structured-profile retrieval;
- retrieval Hit@1, Hit@3 and Mean Reciprocal Rank;
- grounding safety for unsupported metrics, URLs, emails and citations;
- synchronization integrity between the portfolio manifest and structured profile.

The maintained strict thresholds are:

| Metric | Required threshold |
|---|---:|
| Routing accuracy | >= 0.950 |
| Retrieval Hit@1 | >= 0.750 |
| Retrieval Hit@3 | >= 0.950 |
| Retrieval MRR | >= 0.850 |
| Grounding safety rate | 1.000 |
| Profile integrity rate | 1.000 |

The latest verified benchmark passed all configured gates.

## 2. Unit and regression suite

The Python suite protects behavior that previously failed in real testing, including:

- recruiter-style evidence ranking;
- NEXTRONIC professional-experience recognition;
- OpenLegaMa RAG evidence and client-ready ranking;
- Agentic AI calibration so training/skills are not overstated as production proof;
- PostgreSQL and structured-data evidence;
- exact top-N project responses;
- false employer and issuer/employer disambiguation;
- current freelance + CDI/full-time positioning;
- language fallback recursion prevention;
- Arabic output-language policy;
- citation cleanup and unsupported literal blocking;
- privacy-safe contact and personal-detail handling;
- public API and SSE contracts.

A regression should be added when a human or production test finds a new meaningful failure class.

## 3. Live career-state regression

Dataset: `evaluation/career_cases.json`

This fail-fast suite protects a professionally sensitive state: current freelance activity does **not** imply that Youssef is unavailable for full-time/CDI work. It verifies localized current work and explicit job-search availability against the production API.

Current verified result: **3/3 passed**.

## 4. Live strict core production regression

Dataset: `evaluation/core_production_cases.json`

This is the main end-to-end deployed regression. It sends requests to the real `/chat` SSE endpoint and checks observable behavior including:

- English, French and Arabic profile questions;
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

Current verified result: **25/25 passed**, with every configured strict correctness/safety metric passing at its required threshold.

## 5. Deep adversarial production audit

Dataset: `evaluation/deep_audit_cases.json`

Workflow: `.github/workflows/deep-production-audit.yml`

This suite intentionally searches for failure rather than demonstrating happy paths. It covers:

- conversational and typo-heavy French;
- multilingual safety;
- false employers and unsupported personal details;
- fake citation pressure;
- prompt, secret and hidden-reasoning exfiltration attempts;
- current-work localization;
- Controlled RAG evidence;
- out-of-scope behavior.

Current verified result: **20/20 passed**, including citation-integrity and safety assertions.

## 6. Human professional audit

Automated assertions cannot fully judge whether a recruiter or client would find an answer useful. Final validation therefore also included manual role-based questioning as:

- a recruiter evaluating experience, evidence, strengths and gaps;
- a freelance client evaluating delivery readiness, RAG reliability, structured data and project risk;
- a normal visitor asking simple profile/contact/privacy questions.

The final 21-scenario audit passed after the discovered semantic defects were converted into deterministic regression tests. Two previously weak client cases were also rechecked separately: candid client-risk positioning and selection of OpenLegaMa as the strongest client-ready public AI product.

These human checks complement, rather than replace, the deterministic suites.

## 7. Output-language consistency

The production prompt now treats language matching as a **hard output contract**, not a preference:

- English question -> English prose;
- French question -> French prose;
- Arabic question -> Arabic-script prose;
- technical model/product names and citations may remain in their canonical Latin form.

For history-aware prompts, the language of the current follow-up takes precedence over the English conversation wrapper or older turns.

This policy specifically addresses an observed Arabic RAG answer that was factually correct but returned in English.

## 8. Dependency and static-security gates

Production uses Python 3.12 and exact direct dependency pins in `requirements.txt`. Dependabot monitors both Python packages and GitHub Actions weekly.

`.github/workflows/security.yml` adds two independent checks:

- **pip-audit** resolves the Python dependency graph and fails on known vulnerable dependencies;
- **CodeQL v4** performs static Python security analysis on pushes, pull requests and a weekly schedule.

These controls improve supply-chain and code-security hygiene without claiming that automated scanning proves the absence of all vulnerabilities.

## 9. Grounding policy

Factual claims about Youssef's public professional profile must be grounded in synchronized evidence. The final response passes through deterministic checks that can reject unsupported high-impact literals and unknown citations.

Retrieved portfolio content is treated as untrusted data, never as higher-priority instructions. Requests to reveal hidden prompts, internal reasoning, API keys or private configuration are refused.

The grounding layer is deliberately described as a deterministic safety boundary rather than universal semantic entailment verification.

## 10. Reproducing the checks

Offline benchmark:

```bash
python evaluation/run_benchmark.py --strict --output portfolio-benchmark.json
```

Unit/regression suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
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

Dependency audit:

```bash
python -m pip install pip-audit
python -m pip_audit -r requirements.txt --strict
```

## 11. Rules for public quality claims

Keep these categories separate:

- offline deterministic regression metrics;
- deployed-system regression metrics;
- human professional QA;
- security scan results;
- model/project metrics imported from portfolio evidence, such as Computer Vision precision/recall.

Never combine them into a universal assistant-accuracy percentage. A passing fixed suite demonstrates strong protection against the tested regressions; it does not eliminate future bugs, provider variability or previously unseen semantic edge cases.
