---
title: "OpenLegaMa — Moroccan Legal AI Assistant"
url: https://youssef-bt.github.io/projects/openlegama-moroccan-legal-ai
---

# OpenLegaMa — Moroccan Legal AI Assistant

## Description

A Moroccan legal AI assistant available in French, Modern Standard Arabic, and English. OpenLegaMa uses controlled Retrieval-Augmented Generation to retrieve official legal texts, validate exact law and article references, connect legal claims to accepted evidence, and abstain when verified sources are insufficient.

## Project Facts

**Role:** AI Engineer • RAG & Full-Stack Developer

**Company:** Independent Project

**Period:** July 2026

**Location:** Morocco

**Status:** Stable MVP

**GitHub:** https://github.com/YOUSSEF-BT/OpenLegaMa

## Tags

- Legal AI
- Controlled RAG
- NLP
- Next.js
- TypeScript

## Solution

OpenLegaMa uses controlled RAG rather than a direct question-to-LLM pipeline. A semantic router classifies the request, checks whether clarification is required, validates explicit legal references, and decides whether retrieval is permitted. Relevant articles are then ranked and filtered before grounded generation. A final claim-to-citation validation layer connects sourced legal claims to accepted official evidence, while CORPUS_GAP and controlled abstention prevent unsupported answers.

## Key Achievements

- Released OpenLegaMa v1.0.1 as a stable, publicly accessible MVP
- 143 of 143 automated tests passing
- 610 curated benchmark cases and 120 independent holdout cases evaluated
- 100% document recall at 5 on the current curated retrieval benchmark
- 100% exact-article recall and citation integrity on the measured benchmark cases
- 30 active official legal texts and 7,708 indexed legal articles
- French, Modern Standard Arabic, and English interaction with Arabic RTL support
- Production build, TypeScript checks, ESLint, corpus validation, and benchmark thresholds passing

## Technology Stack

- Next.js 16
- React 18
- TypeScript 5
- Tailwind CSS 4
- Controlled RAG
- Groq SDK
- Python
- NLP
- Legal Retrieval
- Vercel

## Results

- **automatedTests:** 143 / 143 passing
- **indexedArticles:** 7,708
- **activeLegalTexts:** 30
- **legalDomains:** 27
- **curatedBenchmark:** 610 cases
- **holdoutBenchmark:** 120 cases
- **documentRecallAt5:** 100% curated
- **exactArticleRecall:** 100% measured

## Results Context

Benchmark figures describe the current evaluation datasets and pipeline behavior. They are not a claim of universal legal accuracy, complete Moroccan-law coverage, or professional legal validation.

## Disclaimer

OpenLegaMa provides structured and sourced legal information, but it does not replace a lawyer or another qualified legal professional. Its legal corpus is curated and partial, and systematic temporal validation of all active texts is not yet complete.

## Evidence Provenance

Generated from `src/data/projects/chatbot.js` in the public portfolio repository. The portfolio source is authoritative for this generated document.
