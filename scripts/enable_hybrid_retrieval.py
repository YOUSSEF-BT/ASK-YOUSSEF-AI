from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one integration anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/app.py",
    "from rag import RAG, chunk_markdown, parse_frontmatter  # noqa: E402\n",
    "from rag import RAG, chunk_markdown, parse_frontmatter  # noqa: E402\n"
    "from retrieval.hybrid import HybridRetriever  # noqa: E402\n",
)

replace_once(
    "backend/app.py",
    "        rag = RAG(embedder=make_embedder()).build(corpus)\n"
    "        STATE.agent = build_agent(rag=rag, use_mcp=True, mcp_transport=\"inprocess\")\n",
    "        semantic_rag = RAG(embedder=make_embedder()).build(corpus)\n"
    "        rag = HybridRetriever(semantic_rag)\n"
    "        STATE.agent = build_agent(rag=rag, use_mcp=True, mcp_transport=\"inprocess\")\n",
)

replace_once(
    "backend/mcp_server/blog_server.py",
    "from rag import RAG, make_embedder, search_site_text  # noqa: E402\n",
    "from rag import RAG, make_embedder, search_site_text  # noqa: E402\n"
    "from retrieval.hybrid import HybridRetriever  # noqa: E402\n",
)

replace_once(
    "backend/mcp_server/blog_server.py",
    "_RAG = RAG(embedder=make_embedder()).build(CORPUS_DIR)\n"
    "print(f\"[blog-server] indexed {_RAG.num_chunks} chunks from {CORPUS_DIR}\",\n"
    "      file=sys.stderr, flush=True)\n",
    "_SEMANTIC_RAG = RAG(embedder=make_embedder()).build(CORPUS_DIR)\n"
    "_RAG = HybridRetriever(_SEMANTIC_RAG)\n"
    "print(f\"[blog-server] indexed {_RAG.num_chunks} chunks with hybrid retrieval from {CORPUS_DIR}\",\n"
    "      file=sys.stderr, flush=True)\n",
)

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
text = text.replace(
    "> **Current status:** foundation imported and professionally re-scoped. Hybrid retrieval, reranking, automated evaluation, and deep portfolio synchronization are the next implementation milestones. No benchmark metric is published until it is actually measured.",
    "> **Current status:** professional foundation and first hybrid retrieval layer are implemented. Automated evaluation, deeper structured portfolio synchronization, learned reranking, and production deployment remain in progress. No benchmark metric is published until it is actually measured.",
)
text = text.replace(
    "- Retrieval-augmented generation over the live portfolio\n",
    "- Hybrid retrieval combining semantic search with an independent BM25-style lexical index\n"
    "- Reciprocal Rank Fusion (RRF) with deterministic evidence-quality reranking\n"
    "- Retrieval-augmented generation over the live portfolio\n",
)
readme.write_text(text, encoding="utf-8")

architecture = Path("docs/architecture.md")
text = architecture.read_text(encoding="utf-8")
text += """

## Implemented retrieval layer

The current search layer combines the existing semantic vector retriever with an
independent in-memory BM25-style lexical index. Candidate lists are merged with
Reciprocal Rank Fusion (RRF), followed by a small deterministic exact-evidence
boost. Retrieval traces are attached to each result for future evaluation and
observability.

A learned cross-encoder/API reranker is deliberately not claimed yet; it will be
added only after it can be measured against the deterministic baseline.
"""
architecture.write_text(text, encoding="utf-8")

print("Hybrid retrieval integrated into both in-process and MCP search paths.")
