from pathlib import Path


path = Path("backend/app.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from retrieval.hybrid import HybridRetriever  # noqa: E402\nfrom router import route_question  # noqa: E402\n",
        "from retrieval.hybrid import HybridRetriever  # noqa: E402\n"
        "from retrieval.structured import StructuredProfileRetriever  # noqa: E402\n"
        "from router import route_question  # noqa: E402\n",
    ),
    (
        "BUNDLED_SNAPSHOT = os.path.join(os.path.dirname(__file__), \"data\", \"site\")\n",
        "BUNDLED_SNAPSHOT = os.path.join(os.path.dirname(__file__), \"data\", \"site\")\n"
        "PROFILE_PATH = os.environ.get(\n"
        "    \"PROFILE_PATH\", os.path.join(os.path.dirname(__file__), \"data\", \"profile.json\")\n"
        ")\n",
    ),
    (
        "    chunks = 0\n    brain = \"?\"\n",
        "    chunks = 0\n    structured_docs = 0\n    brain = \"?\"\n",
    ),
    (
        "    STATE.pages, STATE.chunks = _page_index(corpus)\n\n    if MCP_TRANSPORT == \"process\":\n",
        "    STATE.pages, STATE.chunks = _page_index(corpus)\n"
        "    structured_retriever = StructuredProfileRetriever.from_path(PROFILE_PATH)\n"
        "    STATE.structured_docs = structured_retriever.count\n\n"
        "    if MCP_TRANSPORT == \"process\":\n",
    ),
    (
        "        os.environ[\"CORPUS_DIR\"] = corpus\n"
        "        STATE.agent = build_agent(rag=None, use_mcp=True, mcp_transport=\"process\")\n",
        "        os.environ[\"CORPUS_DIR\"] = corpus\n"
        "        os.environ[\"PROFILE_PATH\"] = PROFILE_PATH\n"
        "        STATE.agent = build_agent(rag=None, use_mcp=True, mcp_transport=\"process\")\n",
    ),
    (
        "        semantic_rag = RAG(embedder=make_embedder()).build(corpus)\n"
        "        rag = HybridRetriever(semantic_rag)\n"
        "        STATE.agent = build_agent(rag=rag, use_mcp=True, mcp_transport=\"inprocess\")\n",
        "        semantic_rag = RAG(embedder=make_embedder()).build(corpus)\n"
        "        rag = HybridRetriever(\n"
        "            semantic_rag, structured_retriever=structured_retriever\n"
        "        )\n"
        "        STATE.agent = build_agent(rag=rag, use_mcp=True, mcp_transport=\"inprocess\")\n",
    ),
    (
        "    print(f\"[boot] ready — {len(STATE.pages)} pages, {STATE.chunks} chunks, \"\n"
        "          f\"transport={MCP_TRANSPORT}, brain={STATE.brain}\", flush=True)\n",
        "    print(f\"[boot] ready — {len(STATE.pages)} pages, {STATE.chunks} chunks, \"\n"
        "          f\"{STATE.structured_docs} structured docs, transport={MCP_TRANSPORT}, \"\n"
        "          f\"brain={STATE.brain}\", flush=True)\n",
    ),
    (
        "    return {\"ok\": STATE.agent is not None, \"pages\": len(STATE.pages),\n"
        "            \"chunks\": STATE.chunks, \"transport\": MCP_TRANSPORT, \"brain\": STATE.brain}\n",
        "    return {\"ok\": STATE.agent is not None, \"pages\": len(STATE.pages),\n"
        "            \"chunks\": STATE.chunks, \"structured_docs\": STATE.structured_docs,\n"
        "            \"retrieval\": \"semantic+bm25+structured-rrf\",\n"
        "            \"transport\": MCP_TRANSPORT, \"brain\": STATE.brain}\n",
    ),
]

for old, new in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"Expected runtime block not found:\n{old[:180]}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Structured retrieval wired into FastAPI runtime and health metadata.")
