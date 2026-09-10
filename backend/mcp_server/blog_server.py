"""A real MCP server for portfolio search, built with FastMCP.

This runs as its OWN process and exposes the production retrieval stack as an MCP
tool. The agent — a separate process — connects over stdio and calls `search_site`
across the process boundary. The embedding model lives HERE and nowhere else, so
the FastAPI parent stays light in process-transport deployments.

The search stack combines semantic retrieval, BM25 lexical retrieval, and the
synchronized structured professional profile. All three signals are fused by the
HybridRetriever before results are returned to the agent.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # backend/, where rag.py and data/ live
# APPEND (not insert) so nothing here shadows the real `mcp` package FastMCP
# imports; our client module is named mcp_client.py precisely to avoid that.
sys.path.append(ROOT)

from fastmcp import FastMCP  # noqa: E402
from rag import RAG, make_embedder, search_site_text  # noqa: E402
from retrieval.hybrid import HybridRetriever  # noqa: E402
from retrieval.structured import StructuredProfileRetriever  # noqa: E402

mcp = FastMCP("portfolio-search")

# Both sources are generated/synchronized from the public portfolio repository.
# Environment overrides are useful for local evaluation, while the defaults point
# at the committed production snapshot bundled in backend/data/.
CORPUS_DIR = os.environ.get("CORPUS_DIR", os.path.join(ROOT, "data", "site"))
PROFILE_PATH = os.environ.get("PROFILE_PATH", os.path.join(ROOT, "data", "profile.json"))

_SEMANTIC_RAG = RAG(embedder=make_embedder()).build(CORPUS_DIR)
_STRUCTURED = StructuredProfileRetriever.from_path(PROFILE_PATH)
_RAG = HybridRetriever(_SEMANTIC_RAG, structured_retriever=_STRUCTURED)
print(
    f"[portfolio-search] indexed {_RAG.num_chunks} semantic/lexical chunks + "
    f"{_STRUCTURED.count} structured documents from {CORPUS_DIR}",
    file=sys.stderr,
    flush=True,
)


@mcp.tool
def search_site(query: str, k: int = 3, min_score: float = 0.25) -> str:
    """Search Youssef's public portfolio and return the most relevant evidence.

    Each result includes its source and a relevance score. If the best match is
    weak, the result says so — the agent can rephrase and search again.
    """
    # Formatting lives in rag.search_site_text so process and in-process MCP
    # transports expose the same observation format to the agent.
    return search_site_text(_RAG, query, k=k, min_score=min_score)


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
