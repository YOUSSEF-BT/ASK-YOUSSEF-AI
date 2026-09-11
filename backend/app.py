"""FastAPI backend — the deployed brain behind the portfolio chatbot.

Replaces the old Gradio app. It is a thin HTTP/SSE shell around the from-scratch
pipeline; almost all of the work lives in the modules it reuses (crawl, rag,
agent, mcp_client) — this file only wires them to the web and to the browser.

On boot it loads the committed crawl snapshot in backend/data/site (refreshed in
CI, not at boot — see .github/workflows/sync-portfolio.yml) and spins up the agent.
Set CRAWL_SITES to re-enable a live boot crawl.

Exact whole-dataset facts (for example certification totals and issuer-specific
inventories) are resolved directly from the synchronized structured profile.
This prevents a top-k retrieval slice from ever being mistaken for the complete
set.

Endpoints:
  POST /chat    {question, history?}  → text/event-stream of agent events
  GET  /health                  → {ok, pages, chunks, transport, brain}
  GET  /pages                   → [{title, url, chunks}] for source links
  GET  /capabilities            → public product metadata + suggestions
  POST /feedback                → fixed-category privacy-safe feedback
  GET  /metrics                 → aggregate operational metrics

Run:  uvicorn app:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Literal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import crawl  # noqa: E402
from rag import RAG, chunk_markdown, parse_frontmatter  # noqa: E402
from observability import TELEMETRY  # noqa: E402
from feedback import FEEDBACK  # noqa: E402
from retrieval.hybrid import HybridRetriever  # noqa: E402
from retrieval.structured import StructuredProfileRetriever  # noqa: E402
from structured_facts import StructuredFactResolver  # noqa: E402
from router import route_question  # noqa: E402


# --- config -----------------------------------------------------------------
DEFAULT_SITES = ["https://youssef-bt.github.io", "https://youssef-bt.github.io/projects"]
CRAWL_SITES = os.environ.get("CRAWL_SITES", " ".join(DEFAULT_SITES)).split()
CORPUS_DIR = os.environ.get("CORPUS_DIR", "/tmp/site")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "process").lower()
BUNDLED_SNAPSHOT = os.path.join(os.path.dirname(__file__), "data", "site")
PROFILE_PATH = os.environ.get(
    "PROFILE_PATH", os.path.join(os.path.dirname(__file__), "data", "profile.json")
)

# --- abuse guards -----------------------------------------------------------
# The endpoint is public and provider-backed, so keep request size and frequency
# bounded even on a free-tier deployment. Counters are process-local and reset
# on cold start/deploy, which is appropriate for this portfolio-scale service.
MAX_QUESTION_CHARS = int(os.environ.get("MAX_QUESTION_CHARS", "600"))
MAX_TURN_CHARS = int(os.environ.get("MAX_TURN_CHARS", "600"))
MAX_HISTORY_ITEMS = int(os.environ.get("MAX_HISTORY_ITEMS", "16"))
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "6"))
RATE_PER_DAY = int(os.environ.get("RATE_PER_DAY", "40"))
GLOBAL_PER_DAY = int(os.environ.get("GLOBAL_PER_DAY", "800"))
# Only the most recent subset is injected into the model prompt; accepting up to
# 16 matches the public widget while still bounding direct-API payload structure.
_MAX_HISTORY = min(8, MAX_HISTORY_ITEMS)


class _RateLimiter:
    """Sliding-window per-IP + global request limiter, stdlib-only."""

    def __init__(self, per_min: int, per_day: int, global_per_day: int) -> None:
        self.per_min, self.per_day, self.global_per_day = per_min, per_day, global_per_day
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}
        self._global: list[float] = []
        self._last_sweep = 0.0

    def check(self, ip: str) -> str | None:
        now = time.time()
        day_ago, min_ago = now - 86400, now - 60
        with self._lock:
            if now - self._last_sweep > 300:
                self._hits = {
                    k: t
                    for k, t in (
                        (k, [x for x in v if x > day_ago]) for k, v in self._hits.items()
                    )
                    if t
                }
                self._global = [x for x in self._global if x > day_ago]
                self._last_sweep = now
            self._global = [x for x in self._global if x > day_ago]
            if self.global_per_day and len(self._global) >= self.global_per_day:
                return (
                    "This assistant has reached its daily limit for everyone — "
                    "please try again tomorrow."
                )
            ts = [x for x in self._hits.get(ip, []) if x > day_ago]
            if self.per_day and len(ts) >= self.per_day:
                return "You've reached the daily question limit — please come back tomorrow."
            if self.per_min and sum(1 for x in ts if x > min_ago) >= self.per_min:
                return (
                    "You're sending questions a bit too fast — "
                    "give it a few seconds and try again."
                )
            ts.append(now)
            self._hits[ip] = ts
            self._global.append(now)
            return None


_limiter = _RateLimiter(RATE_PER_MIN, RATE_PER_DAY, GLOBAL_PER_DAY)
_feedback_limiter = _RateLimiter(20, 100, 5000)


def _client_ip(request: Request) -> str:
    """Return the first forwarded client hop, falling back to the socket peer."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _origin_allowed(request: Request) -> bool:
    """Allow the configured portfolio origins; non-browser callers can forge
    headers, so this complements rather than replaces the rate limiter."""
    if "*" in ALLOWED_ORIGINS:
        return True
    allow = [o.rstrip("/") for o in ALLOWED_ORIGINS]
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin:
        return origin in allow
    ref = request.headers.get("referer") or ""
    return any(ref.startswith(o) for o in allow)


class _State:
    agent = None
    structured_facts = None
    pages: list[dict] = []
    chunks = 0
    structured_docs = 0
    brain = "?"
    lock = threading.Lock()


STATE = _State()


def _refresh_corpus() -> str:
    """Resolve the corpus to index, preferring the committed snapshot."""
    if not CRAWL_SITES:
        if os.path.isdir(BUNDLED_SNAPSHOT) and os.listdir(BUNDLED_SNAPSHOT):
            print(
                f"[boot] no boot crawl (CRAWL_SITES empty); using committed snapshot {BUNDLED_SNAPSHOT}",
                flush=True,
            )
            return BUNDLED_SNAPSHOT
        print(
            "[boot] CRAWL_SITES empty and no committed snapshot yet; falling back to a one-time live crawl",
            flush=True,
        )
        sites = DEFAULT_SITES
    else:
        sites = CRAWL_SITES
    try:
        print(f"[boot] crawling {sites} → {CORPUS_DIR}", flush=True)
        pages = crawl.crawl(sites)
    except Exception as exc:
        print(f"[boot] crawl failed ({exc!r}); using bundled snapshot", flush=True)
        pages = []
    if pages:
        crawl.save_snapshot(pages, CORPUS_DIR)
        print(f"[boot] snapshot: {len(pages)} pages → {CORPUS_DIR}", flush=True)
        return CORPUS_DIR
    if os.path.isdir(BUNDLED_SNAPSHOT) and os.listdir(BUNDLED_SNAPSHOT):
        print(f"[boot] falling back to bundled snapshot {BUNDLED_SNAPSHOT}", flush=True)
        return BUNDLED_SNAPSHOT
    raise RuntimeError("no pages crawled and no bundled snapshot to fall back on")


def _page_index(corpus_dir: str) -> tuple[list[dict], int]:
    """Read snapshot metadata and chunk counts without embedding."""
    import glob

    pages: list[dict] = []
    total = 0
    for path in sorted(
        glob.glob(os.path.join(corpus_dir, "*.md"))
        + glob.glob(os.path.join(corpus_dir, "*.mdx"))
    ):
        slug = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as fh:
            md = fh.read()
        fm = parse_frontmatter(md)
        n = len(
            chunk_markdown(
                md,
                slug,
                url=fm.get("url", ""),
                title=fm.get("title", ""),
            )
        )
        total += n
        pages.append(
            {
                "title": fm.get("title") or slug.replace("-", " ").title(),
                "url": fm.get("url", ""),
                "source": slug,
                "chunks": n,
            }
        )
    pages.sort(key=lambda p: p["title"].lower())
    return pages, total


app = FastAPI(title="Ask Youssef AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


@app.on_event("startup")
def _startup() -> None:
    from agent import build_agent

    corpus = _refresh_corpus()
    STATE.pages, STATE.chunks = _page_index(corpus)
    structured_retriever = StructuredProfileRetriever.from_path(PROFILE_PATH)
    STATE.structured_docs = structured_retriever.count
    STATE.structured_facts = StructuredFactResolver(structured_retriever.profile)

    if MCP_TRANSPORT == "process":
        os.environ["CORPUS_DIR"] = corpus
        os.environ["PROFILE_PATH"] = PROFILE_PATH
        STATE.agent = build_agent(rag=None, use_mcp=True, mcp_transport="process")
    else:
        from rag import make_embedder

        semantic_rag = RAG(embedder=make_embedder()).build(corpus)
        rag = HybridRetriever(
            semantic_rag, structured_retriever=structured_retriever
        )
        STATE.agent = build_agent(rag=rag, use_mcp=True, mcp_transport="inprocess")
    STATE.brain = getattr(STATE.agent, "brain_name", "?")
    print(
        f"[boot] ready — {len(STATE.pages)} pages, {STATE.chunks} chunks, "
        f"{STATE.structured_docs} structured docs, transport={MCP_TRANSPORT}, brain={STATE.brain}",
        flush=True,
    )


class Turn(BaseModel):
    # Literal prevents forged roles such as "system" from being relabelled as an
    # assistant turn inside the history transcript.
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


class FeedbackRequest(BaseModel):
    rating: str
    reason: str | None = None


def _with_history(question: str, history: list[Turn]) -> str:
    """Fold a bounded prior transcript into a follow-up question."""
    turns = [t for t in history if t.content.strip()][-_MAX_HISTORY:]
    if not turns:
        return question
    lines = []
    for t in turns:
        who = "User" if t.role == "user" else "Assistant"
        lines.append(f"{who}: {t.content.strip()[:MAX_TURN_CHARS]}")
    convo = "\n".join(lines)
    return (
        f"Conversation so far:\n{convo}\n\n"
        f"Given that conversation, answer this follow-up. Resolve any references to earlier turns.\n"
        f"Follow-up: {question}"
    )


def _sse(kind: str, **data) -> str:
    return f"data: {json.dumps({'kind': kind, **data})}\n\n"


def _error_stream(message: str) -> StreamingResponse:
    def _gen():
        yield _sse("error", message=message)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _safe_runtime_error(exc: Exception) -> str:
    """Log provider/internal detail server-side and return only public-safe copy."""
    print(f"[chat] runtime failure: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
    low = str(exc).lower()
    if any(s in low for s in ("timed out", "timeout", "deadline")):
        return (
            "That took longer than I expected — the model was slow to respond just now. "
            "Please try asking again in a moment."
        )
    return "I couldn't complete that request just now. Please try again in a moment."


def _stream(question: str, history: list[Turn] | None = None):
    """Drive exact structured facts or the agent, then stream public SSE events."""
    started = time.monotonic()
    route = route_question(question)
    TELEMETRY.record_request(route)
    if STATE.agent is None:
        TELEMETRY.record_error(latency_ms=(time.monotonic() - started) * 1000.0)
        yield _sse("error", message="The assistant is starting up. Please try again in a moment.")
        return

    exact = (
        STATE.structured_facts.resolve(question, history or [])
        if STATE.structured_facts is not None
        else None
    )
    if exact is not None:
        yield _sse("tool_call", tool=exact.tool, input=question)
        yield _sse("observation", tool=exact.tool, output=exact.evidence)
        TELEMETRY.record_completed(
            latency_ms=(time.monotonic() - started) * 1000.0,
            retrieval_used=True,
            grounding_intervened=False,
        )
        yield _sse("final", answer=exact.answer, tools_used=[exact.tool])
        return

    contextual = _with_history(question, history or [])
    if not STATE.lock.acquire(timeout=45):
        TELEMETRY.record_error(latency_ms=(time.monotonic() - started) * 1000.0)
        yield _sse(
            "error",
            message="The assistant is busy with another question — give it a moment and try again.",
        )
        return
    try:
        try:
            for ev in STATE.agent.run_iter(
                contextual, require_retrieval=route.requires_retrieval
            ):
                if ev.kind == "thinking":
                    yield _sse("thinking", brain=ev.data["brain"])
                elif ev.kind == "model":
                    yield _sse("model")
                elif ev.kind == "tool_call":
                    tool_input = (
                        ev.data["input"] if ev.data["tool"] == "search_site" else None
                    )
                    yield _sse(
                        "tool_call", tool=ev.data["tool"], input=tool_input
                    )
                elif ev.kind == "observation":
                    yield _sse(
                        "observation",
                        tool=ev.data["tool"],
                        output=ev.data["output"],
                    )
                elif ev.kind == "final":
                    steps = ev.data["result"].steps
                    used = sorted(
                        {
                            s.action
                            for s in steps
                            if s.action and s.action not in ("__final__",)
                        }
                    )
                    from grounding import enforce_grounding

                    guarded_answer, _report = enforce_grounding(
                        ev.data["answer"], steps
                    )
                    TELEMETRY.record_completed(
                        latency_ms=(time.monotonic() - started) * 1000.0,
                        retrieval_used="search_site" in used,
                        grounding_intervened=guarded_answer != ev.data["answer"],
                    )
                    yield _sse(
                        "final", answer=guarded_answer, tools_used=used
                    )
        except Exception as exc:
            TELEMETRY.record_error(
                latency_ms=(time.monotonic() - started) * 1000.0
            )
            yield _sse("error", message=_safe_runtime_error(exc))
    finally:
        STATE.lock.release()


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    # Apply the site-origin boundary even to an empty request, so every /chat
    # response follows the same public API contract.
    if not _origin_allowed(request):
        return _error_stream("This assistant only runs on Youssef's site.")

    question = (req.question or "").strip()
    if not question:
        def _empty():
            yield _sse(
                "final", answer="Ask me something about Youssef.", tools_used=[]
            )

        return StreamingResponse(_empty(), media_type="text/event-stream")

    if len(question) > MAX_QUESTION_CHARS:
        return _error_stream(
            f"That question is a bit long (max {MAX_QUESTION_CHARS} characters) — please shorten it."
        )
    limited = _limiter.check(_client_ip(request))
    if limited:
        return _error_stream(limited)
    return StreamingResponse(
        _stream(question, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    return {
        "ok": STATE.agent is not None,
        "pages": len(STATE.pages),
        "chunks": STATE.chunks,
        "structured_docs": STATE.structured_docs,
        "retrieval": "semantic+bm25+structured-rrf",
        "transport": MCP_TRANSPORT,
        "brain": STATE.brain,
    }


@app.get("/metrics")
def metrics():
    """Privacy-safe process-lifetime operational metrics; no visitor content."""
    snapshot = TELEMETRY.snapshot()
    snapshot["feedback"] = FEEDBACK.snapshot()
    return snapshot


@app.get("/capabilities")
def capabilities():
    """Public, non-secret product metadata used by the portfolio widget."""
    return {
        "name": "Ask Youssef AI",
        "subtitle": "Professional Portfolio Copilot",
        "status": "live",
        "languages": ["en", "fr", "ar"],
        "retrieval": "semantic+bm25+structured-rrf",
        "features": [
            "grounded portfolio answers",
            "source citations",
            "multilingual routing",
            "conversation context",
            "automatic portfolio synchronization",
            "exact structured aggregate facts",
            "privacy-safe feedback",
        ],
        "suggestions": [
            "Show me Youssef's strongest AI projects",
            "What is his Computer Vision experience?",
            "Show evidence of his RAG and LLM skills",
            "Which certifications does he have?",
            "How can I contact Youssef?",
        ],
    }


@app.post("/feedback")
def feedback(req: FeedbackRequest, request: Request):
    """Collect fixed-category aggregate feedback without retaining visitor text."""
    if not _origin_allowed(request):
        raise HTTPException(status_code=403, detail="origin not allowed")
    limit_reason = _feedback_limiter.check(_client_ip(request))
    if limit_reason:
        raise HTTPException(status_code=429, detail="feedback rate limit reached")
    try:
        FEEDBACK.record(req.rating, req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/pages")
def pages():
    return {
        "sites": CRAWL_SITES,
        "total_chunks": STATE.chunks,
        "pages": [
            {
                "title": p["title"],
                "url": p["url"],
                "source": p["source"],
                "chunks": p["chunks"],
            }
            for p in STATE.pages
        ],
    }
