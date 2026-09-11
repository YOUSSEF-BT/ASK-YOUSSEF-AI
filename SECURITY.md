# Security Policy

Ask Youssef AI is a public AI portfolio application. Security reports are welcome for vulnerabilities that could expose secrets, bypass trust boundaries, allow unauthorized actions, or materially compromise the service or its users.

For implementation details about the application's security architecture, see [`docs/security.md`](docs/security.md).

## Supported deployment

Security fixes target the current `main` branch and the live production service at:

- Portfolio: `https://youssef-bt.github.io/`
- API: `https://ask-youssef-ai.vercel.app/`

Older commits, abandoned deployments and third-party forks are not maintained as supported releases.

## Reporting a vulnerability

Please **do not open a public GitHub issue for a suspected security vulnerability** if the report contains exploit details, secrets, personal data, or information that could put users or infrastructure at risk.

Send a private report to:

**bt.youssef.369@gmail.com**

Use a subject such as:

`[SECURITY] Ask Youssef AI — short vulnerability title`

A useful report should include, when applicable:

- the affected URL, endpoint, file or component;
- a concise description of the issue and its security impact;
- reproducible steps or a minimal proof of concept;
- the conditions required to reproduce it;
- suggested remediation, if known;
- whether any credentials, personal data or destructive actions were involved.

Please redact real secrets and unnecessary personal information. Never send live provider keys, passwords or authentication tokens unless a secure exchange method has first been agreed.

## Automated security controls

The repository continuously applies several automated controls in addition to application-level safeguards:

- exact direct Python dependency pins and a pinned Python 3.12 runtime;
- weekly Dependabot checks for Python packages and GitHub Actions;
- `pip-audit` on pushes, pull requests and a weekly schedule to detect known vulnerabilities in the resolved Python dependency graph;
- GitHub CodeQL v4 static analysis for Python on pushes, pull requests and a weekly schedule;
- deterministic tests for prompt/secret extraction, unsafe history roles, unsupported literals, citation integrity and public API boundaries.

Automated scans reduce risk but do not prove that the application is vulnerability-free.

## Security issues in scope

Examples include:

- exposure of `GEMINI_API_KEY` or another server-side credential;
- a CORS/origin or API-boundary flaw that enables meaningful unauthorized use;
- prompt or retrieval injection that causes secret disclosure or unauthorized actions;
- a grounding/citation bypass that can be exploited for a material security impact;
- arbitrary code execution, injection, path traversal or server-side request abuse;
- unauthorized access to contact-provider functionality;
- leakage of visitor prompts, conversation history, email addresses, IP addresses or other data that the application is designed not to retain/expose;
- dependency vulnerabilities that are demonstrably exploitable in this application.

## Generally out of scope

The following are normally product-quality or availability issues rather than security vulnerabilities unless they can be combined with a concrete security impact:

- ordinary factual hallucinations without secret disclosure or unauthorized action;
- wording, translation, formatting or citation-style mistakes;
- provider/free-tier quota exhaustion or temporary third-party outages;
- denial-of-service reports that require high-volume traffic against the public demo;
- social engineering, phishing or attacks against unrelated third-party accounts;
- vulnerabilities that exist only in unsupported forks or modified deployments.

Quality defects are still valuable and can be reported through a normal GitHub issue when they do not contain sensitive information.

## Safe testing expectations

Please keep testing non-destructive and proportionate to a public portfolio application:

- do not attempt to access another person's accounts or data;
- do not intentionally exfiltrate real secrets or personal information;
- do not send high-volume traffic or deliberately exhaust free-tier quotas;
- do not modify, delete or corrupt data;
- stop testing if you unexpectedly encounter sensitive information and report it privately.

## Disclosure process

Reports will be reviewed and reproduced when possible. Confirmed issues will be prioritized according to impact and exploitability. Public disclosure should wait until a fix is available or a disclosure plan has been mutually agreed.

No bug-bounty program or monetary reward is promised by this repository.

## Security design summary

The production application uses server-side secret storage, bounded requests/history, browser-origin controls, rate limiting, deterministic scope and secret-exfiltration refusals, retrieval-grounded professional facts, citation verification, structured precision facts, provider failover, privacy-safe aggregate telemetry, dependency vulnerability auditing and CodeQL static analysis.

These controls reduce risk but do not make the system immune to vulnerabilities. Responsible reports are appreciated.
