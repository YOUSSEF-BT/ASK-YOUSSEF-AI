---
title: "Ask Youssef AI — Evidence-Grounded Portfolio Intelligence"
url: https://youssef-bt.github.io/projects/ask-youssef-ai-portfolio-intelligence
---

# Ask Youssef AI — Evidence-Grounded Portfolio Intelligence

## Description

A production AI portfolio copilot that transforms my professional portfolio into a multilingual, evidence-grounded assistant for recruiters, clients, engineers, and collaborators. It combines deterministic professional facts, structured retrieval, BM25, FastEmbed semantic search, Reciprocal Rank Fusion, Gemini generation, grounding safeguards, evaluation, and production deployment.

## Project Facts

**Role:** AI Engineer • RAG / LLM Systems

**Company:** Independent Project

**Period:** September 2026

**Location:** Morocco

**Status:** Live

**GitHub:** https://github.com/YOUSSEF-BT/ASK-YOUSSEF-AI

## Tags

- Hybrid RAG
- FastAPI
- Gemini
- FastEmbed
- BM25
- RRF
- Grounded AI
- Multilingual AI

## Solution

Ask Youssef AI uses a layered architecture instead of a direct prompt-to-LLM flow. Exact questions are resolved from a synchronized structured profile. Open factual questions use structured retrieval, BM25, and FastEmbed semantic search fused through RRF. Gemini handles evidence-backed generation only when generative reasoning is useful. A final grounding boundary validates citations and high-impact claims before answers are returned through the FastAPI SSE API and portfolio widget.

## Key Achievements

- Production deployment integrated directly into the public portfolio
- 218 of 218 Python unit and regression tests passing in the validated project snapshot
- Routing accuracy, Retrieval Hit@1, Retrieval Hit@3, MRR, grounding safety, and profile integrity all measured at 1.000 on the deterministic benchmark suite
- 25 of 25 core production regression cases passed
- 20 of 20 deep adversarial production audit cases passed
- 21 of 21 human recruiter, client, and visitor audit scenarios passed
- English, French, and Arabic professional interaction
- 16 synchronized evidence pages, 161 retrieval chunks, and 81 structured documents
- Automated CI, dependency auditing, CodeQL security analysis, and portfolio synchronization

## Technology Stack

- Python 3.12
- FastAPI
- Gemini 3.7 Flash
- Gemini 3.5 Flash-Lite
- FastEmbed
- BM25
- Reciprocal Rank Fusion
- Structured Retrieval
- Server-Sent Events
- GitHub Actions
- Vercel

## Results

- **automatedTests:** 218 / 218
- **routingAccuracy:** 1.000
- **retrievalHitAt1:** 1.000
- **retrievalHitAt3:** 1.000
- **retrievalMRR:** 1.000
- **groundingSafety:** 1.000
- **coreProduction:** 25 / 25
- **adversarialAudit:** 20 / 20
- **humanAudit:** 21 / 21

## Results Context

Metrics correspond to the defined deterministic, regression, production, adversarial, and human-evaluation suites documented in the project repository. They do not imply universal 100% accuracy for arbitrary future questions.

## Disclaimer

Evaluation scores describe the defined regression and benchmark suites. They are not a claim of universal 100% LLM accuracy or enterprise-scale availability.

## Evidence Provenance

Generated from `src/data/projects/askYoussefAI.js` in the public portfolio repository. The portfolio source is authoritative for this generated document.
