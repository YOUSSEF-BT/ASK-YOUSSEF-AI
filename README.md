# Ask Youssef AI

**Professional Portfolio Copilot**

Ask Youssef AI is a production-oriented, multilingual AI assistant designed to help any visitor explore Youssef Bouzit's public professional portfolio through grounded, source-backed conversations.

It is being built for general visitors, recruiters, clients, developers, collaborators, and anyone who wants to understand Youssef's projects, skills, certifications, experience, technical work, or ways to get in touch.

> **Current status:** foundation imported and professionally re-scoped. Hybrid retrieval, reranking, automated evaluation, and deep portfolio synchronization are the next implementation milestones. No benchmark metric is published until it is actually measured.

## Why this project exists

A normal portfolio makes visitors search manually. Ask Youssef AI turns the portfolio into an interactive professional knowledge interface while keeping factual claims grounded in public evidence.

## Core capabilities

- Agentic portfolio Q&A with a ReAct-style tool loop
- Retrieval-augmented generation over the live portfolio
- Conversation history for follow-up questions
- Source-aware answers and page linking
- Automatic portfolio crawling and snapshot refresh
- Streaming responses over Server-Sent Events
- Multilingual response policy for English, French, and Arabic
- Prompt-injection-aware professional scope
- Rate limiting, input caps, and origin allowlisting
- MCP-based search/contact tools
- Embeddable, dependency-free Shadow DOM chat widget

## Production target

The final system extends the imported foundation with:

**structured profile retrieval + lexical retrieval + vector semantic retrieval → rank fusion → reranking → evidence selection → LLM generation → grounding/citation verification → answer or abstention.**

See [`docs/architecture.md`](docs/architecture.md).

## Example questions

- What are Youssef's strongest AI projects?
- Show me his Computer Vision experience.
- What RAG work does he demonstrate?
- Which certifications support his AI profile?
- How was his road-accident detection system designed?
- How can I contact Youssef?
- Quels sont ses projets de Machine Learning ?
- ما هي أبرز مشاريعه في الذكاء الاصطناعي؟

## Repository layout

```text
backend/        FastAPI, agent, RAG, crawler, MCP tools
web/            embeddable widget + technical demo UI
evaluation/     evaluation dataset and future reports
docs/           architecture and engineering documentation
tests/          automated test suite
.github/        crawling, CI and Pages workflows
```

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Copy `.env.example` to `.env` and provide valid server-side secrets before using model-backed features. Never commit secrets.

## Evaluation policy

This repository will report only measured metrics. Planned evaluation dimensions include retrieval recall, ranking quality, citation accuracy, groundedness, abstention accuracy, intent routing, multilingual behavior, and latency.

## Security principles

- Public professional data only
- No secret or private-data retrieval
- Factual claims about Youssef require portfolio evidence
- Retrieved pages are treated as untrusted data
- Unsupported claims are refused rather than invented
- API keys remain server-side
- Public endpoints use rate limits and origin restrictions

## Acknowledgements

This project uses and substantially adapts components from [`adityajn105/portfolio-chatbot`](https://github.com/adityajn105/portfolio-chatbot), Copyright (c) 2026 Aditya Jain, under the MIT License. The original license notice is preserved in [`LICENSE`](LICENSE). See [`NOTICE.md`](NOTICE.md).

## License

MIT. See [`LICENSE`](LICENSE).
