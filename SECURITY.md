# Security Policy

Ask Youssef AI is a public AI portfolio system designed to expose only verified professional information while protecting provider credentials, internal configuration and visitor privacy.

Security reports are welcome for issues that could materially compromise confidentiality, integrity, availability, trust boundaries or the public service.

For the implementation-level security design, see [`docs/security.md`](docs/security.md).

## Supported Scope

Security fixes target:

- the current `main` branch;
- the production API at `https://ask-youssef-ai.vercel.app`;
- the live portfolio integration at `https://youssef-bt.github.io/`.

Older commits, abandoned deployments, third-party forks and modified copies are not maintained as supported releases.

## Reporting a Vulnerability

Please **do not open a public GitHub issue** when a report includes exploit details, credentials, personal data or information that could put users or infrastructure at risk.

Send private reports to:

**bt.youssef.369@gmail.com**

Suggested subject:

```text
[SECURITY] Ask Youssef AI — short vulnerability title
```

A useful report should include, when applicable:

- affected endpoint, URL, file or component;
- concise description of the issue;
- expected security impact;
- reproducible steps or a minimal proof of concept;
- conditions required to reproduce it;
- suggested remediation, if known;
- whether credentials, private data or destructive actions were involved.

Please redact real secrets and unnecessary personal information. Do not send live API keys, passwords or access tokens unless a secure exchange method has first been agreed.

## Automated Security Controls

The repository applies several independent security controls:

- Python `3.12` runtime pinning;
- exact direct dependency versions;
- weekly Dependabot checks for Python packages and GitHub Actions;
- `pip-audit` on pushes, pull requests and schedule;
- GitHub CodeQL v4 static analysis for Python;
- deterministic tests for prompt and secret extraction;
- strict conversation-role validation;
- public API boundary tests;
- citation and unsupported-claim regressions;
- synchronized profile and corpus integrity checks.

Automated scanning reduces risk but does not prove that the application is vulnerability-free.

## Security Issues in Scope

Examples include:

- exposure of `GEMINI_API_KEY` or another server-side credential;
- a meaningful CORS/origin-boundary bypass;
- unauthorized use of protected backend actions;
- prompt or retrieval injection that causes secret disclosure or unauthorized behavior;
- arbitrary code execution, injection, path traversal or server-side request abuse;
- leakage of visitor prompts, conversation history, email addresses, IP addresses or other data the application is designed not to retain;
- dependency vulnerabilities that are demonstrably exploitable in the deployed system;
- a grounding or citation bypass that creates a material security or trust impact.

## Generally Out of Scope

The following are normally product-quality or availability issues rather than security vulnerabilities unless they create a concrete security impact:

- ordinary factual mistakes without secret disclosure or unauthorized action;
- wording, translation, formatting or citation-style issues;
- provider or free-tier quota exhaustion;
- temporary third-party outages;
- denial-of-service reports requiring high-volume traffic against the public demo;
- social engineering or phishing against unrelated third-party accounts;
- issues that exist only in unsupported forks or modified deployments.

Quality defects that do not contain sensitive information can be reported through a normal GitHub issue.

## Safe Testing Expectations

Please keep testing non-destructive and proportionate to a public portfolio system:

- do not attempt to access another person's accounts or data;
- do not intentionally exfiltrate real secrets or personal information;
- do not send high-volume traffic or deliberately exhaust public quotas;
- do not modify, delete or corrupt data;
- stop testing if sensitive information is unexpectedly exposed and report it privately.

## Disclosure Process

Reports will be reviewed and reproduced when possible. Confirmed issues will be prioritized according to impact and exploitability.

Public disclosure should wait until a fix is available or a disclosure plan has been mutually agreed.

No bug-bounty program or monetary reward is promised by this repository.

## Security Design Summary

The production application combines:

- server-side secret storage;
- bounded request and conversation sizes;
- browser-origin controls;
- process-level abuse limits;
- strict history roles;
- deterministic prompt/secret-exfiltration refusal;
- retrieval-grounded professional facts;
- structured precision facts;
- citation verification;
- unsupported-claim protection;
- provider failover;
- privacy-safe aggregate telemetry;
- dependency auditing;
- static security analysis;
- automated regression testing.

These controls are appropriate for the project's public portfolio scope and are deliberately documented without claiming enterprise-scale guarantees.
