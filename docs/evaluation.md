# Evaluation & Quality Gates

Ask Youssef AI uses two complementary evaluation layers: a deterministic regression benchmark that runs on every CI change, and an online deployed-assistant evaluation that can be run manually against the production API.

## 1. Deterministic regression benchmark

`evaluation/run_benchmark.py` evaluates the parts of the system that can be reproduced without an external LLM call:

- multilingual intent/language routing;
- structured professional-profile retrieval;
- retrieval Hit@1, Hit@3 and Mean Reciprocal Rank (MRR);
- grounding safety for unsupported metrics, URLs, emails and citations;
- synchronization integrity between the generated profile and portfolio manifest.

The benchmark is executed in strict mode by CI. A regression below any threshold fails the build. CI also publishes the complete JSON report as the `deterministic-portfolio-benchmark` artifact for 30 days so every quality claim can be traced back to an actual run.

Current regression thresholds are defined in `evaluation/dataset.json` rather than hard-coded in the evaluator.

The benchmark deliberately does **not** claim end-to-end LLM answer accuracy. A deterministic retrieval/guardrail score of 1.0 means all defined regression cases passed; it does not mean the assistant is universally 100% accurate.

## 2. Online deployed-assistant evaluation

`evaluation/run_online_eval.py` and `.github/workflows/online-eval.yml` evaluate the real deployed API through `/chat` and `/health`.

This layer is designed to measure behavior that deterministic tests cannot fully prove, including:

- whether factual profile questions actually invoke retrieval;
- whether the final answer cites the expected portfolio evidence;
- whether unsupported claims trigger abstention rather than hallucination;
- whether greetings and non-retrieval interactions avoid unnecessary search;
- multilingual behavior against the deployed model;
- response latency and runtime failures.

The workflow is intentionally manual because it consumes the deployed model/API quota. Its JSON report is uploaded as a workflow artifact and should be used before publishing end-to-end quality numbers.

## 3. Grounding policy

Factual claims about Youssef's public professional profile are retrieval-grounded. The final response passes through a deterministic verifier that checks high-risk facts such as metrics, links and emails against retrieved evidence. Unsupported high-risk details are replaced with an explicit abstention rather than being presented as facts.

Prompt instructions embedded inside retrieved content are treated as data and are not allowed to override the assistant's system behavior.

## 4. Quality rule for public claims

Only measured results may be published. Repository documentation and portfolio material should clearly distinguish between:

1. deterministic regression metrics;
2. online deployed-model metrics;
3. project/model metrics imported from Youssef's portfolio evidence.

These categories must never be mixed into a single accuracy claim.
