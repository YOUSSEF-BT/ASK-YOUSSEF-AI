# Security Policy

Ask Youssef AI is a public AI portfolio system. Its security policy focuses on protecting provider credentials, preserving trust in professional answers and limiting misuse of the public service.

Implementation details are documented in [`docs/security.md`](docs/security.md).

## Supported Scope

Security fixes target:

- the current `main` branch;
- the production API at `https://ask-youssef-ai.vercel.app/`;
- the live portfolio integration at `https://youssef-bt.github.io/`.

Older commits, abandoned deployments and modified copies are not maintained as supported releases.

## Reporting a Vulnerability

Please do not publish exploit details, secrets or personal data in a public issue.

Send private security reports to:

**bt.youssef.369@gmail.com**

Suggested subject:

```text
[SECURITY] Ask Youssef AI — short vulnerability title
```

A useful report should include, when applicable:

- affected endpoint, file or component;
- concise description of the issue;
- expected impact;
- reproducible steps or a minimal proof of concept;
- conditions required to reproduce it;
- suggested remediation, if known.

Please redact real credentials and unnecessary personal information.

## Security Controls

The project combines application-level and software-supply-chain controls:

- server-side provider secrets;
- browser-origin restrictions;
- bounded question and history sizes;
- strict conversation roles;
- per-IP and global usage limits;
- prompt and secret-exfiltration refusal;
- retrieval-grounded professional facts;
- deterministic precision facts;
- citation validation;
- unsupported-claim protection;
- Python 3.12 runtime pinning;
- exact direct dependency versions;
- Dependabot;
- `pip-audit`;
- GitHub CodeQL;
- automated security and regression tests.

Automated controls reduce risk but do not prove that the application is vulnerability-free.

## In Scope

Examples include:

- exposure of `GEMINI_API_KEY` or another server-side credential;
- meaningful CORS/origin-boundary bypasses;
- unauthorized backend actions;
- prompt or retrieval injection that leads to secret disclosure or unauthorized behavior;
- arbitrary code execution, injection, path traversal or server-side request abuse;
- leakage of visitor prompts, conversation history or other data the service is designed not to retain;
- exploitable dependency vulnerabilities;
- grounding or citation bypasses with a material trust or security impact.

## Generally Out of Scope

Unless they create a concrete security impact, the following are normally product-quality or availability issues:

- ordinary factual mistakes;
- wording or translation issues;
- temporary provider outages;
- free-tier quota exhaustion;
- high-volume denial-of-service testing against the public demo;
- issues limited to unsupported forks or modified deployments.

## Safe Testing Expectations

Please keep testing non-destructive and proportionate to a public portfolio system:

- do not attempt to access another person's accounts or data;
- do not intentionally exfiltrate real secrets;
- do not exhaust public quotas;
- do not modify or destroy data;
- stop and report privately if sensitive information is unexpectedly exposed.

## Disclosure Process

Reports will be reviewed and reproduced when possible. Confirmed issues will be prioritized according to impact and exploitability.

Public disclosure should wait until a fix is available or a disclosure plan has been agreed.

No bug-bounty program or monetary reward is promised by this repository.

## Security Positioning

The implemented controls are appropriate for a public production portfolio system. The project deliberately does not claim enterprise-scale security, multi-tenant authorization, distributed rate limiting or formal SLA guarantees.
