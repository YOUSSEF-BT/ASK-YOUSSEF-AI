# Attribution Notice

## Upstream project

Ask Youssef AI substantially adapts components from
[`adityajn105/portfolio-chatbot`](https://github.com/adityajn105/portfolio-chatbot),
Copyright (c) 2026 Aditya Jain, originally distributed under the MIT License.

The original MIT copyright and permission notice are preserved in [`LICENSE`](LICENSE).

## Ask Youssef AI modifications

The implementation in this repository adds substantial project-specific engineering, including:

- synchronization with Youssef Bouzit's public portfolio as the professional source of truth;
- structured professional-profile generation and deterministic precision-fact resolution;
- BM25 + FastEmbed semantic + structured retrieval with Reciprocal Rank Fusion;
- English, French and Arabic intent/language routing;
- evidence-grounded answers and citation verification;
- safeguards for unsupported professional/personal claims and prompt-injection pressure;
- public-contact and career-status synchronization;
- Gemini provider failover and Vercel serverless reliability controls;
- privacy-safe aggregate observability and bounded feedback;
- deterministic CI, deployed production regression and adversarial QA suites;
- the production Shadow DOM portfolio widget and deployment integration;
- project-specific security, evaluation, architecture and deployment documentation.

## License

Unless a file states otherwise, this repository is distributed under the MIT License in [`LICENSE`](LICENSE). The upstream attribution above and the original MIT notice must be retained in copies or substantial portions of the software.
