from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"guard not found for {label}")
    return text.replace(old, new, 1)


app_path = Path("backend/app.py")
app = app_path.read_text(encoding="utf-8")

app = app.replace(".github/workflows/crawl.yml", ".github/workflows/sync-portfolio.yml")

app = replace_once(
    app,
    '''app.add_middleware(\n    CORSMiddleware,\n    allow_origins=ALLOWED_ORIGINS,   # public, read-only, no cookies\n    allow_methods=["*"],\n    allow_headers=["*"],\n)''',
    '''app.add_middleware(\n    CORSMiddleware,\n    allow_origins=ALLOWED_ORIGINS,\n    allow_credentials=False,\n    allow_methods=["GET", "POST", "OPTIONS"],\n    allow_headers=["Accept", "Content-Type"],\n)''',
    "CORS policy",
)

app = replace_once(
    app,
    '''_limiter = _RateLimiter(RATE_PER_MIN, RATE_PER_DAY, GLOBAL_PER_DAY)''',
    '''_limiter = _RateLimiter(RATE_PER_MIN, RATE_PER_DAY, GLOBAL_PER_DAY)\n# Feedback has no model cost, but a separate limiter prevents public metric\n# poisoning without consuming the visitor's chat allowance.\n_feedback_limiter = _RateLimiter(20, 100, 5000)''',
    "feedback limiter",
)

old_feedback = '''@app.post("/feedback")\ndef feedback(req: FeedbackRequest, request: Request):\n    """Collect fixed-category aggregate feedback without retaining visitor text."""\n    if not _origin_allowed(request):\n        raise HTTPException(status_code=403, detail="origin not allowed")\n    try:\n        FEEDBACK.record(req.rating, req.reason)\n    except ValueError as exc:\n        raise HTTPException(status_code=422, detail=str(exc)) from exc\n    return {"ok": True}\n'''
new_feedback = '''@app.post("/feedback")\ndef feedback(req: FeedbackRequest, request: Request):\n    """Collect fixed-category aggregate feedback without retaining visitor text."""\n    if not _origin_allowed(request):\n        raise HTTPException(status_code=403, detail="origin not allowed")\n    limit_reason = _feedback_limiter.check(_client_ip(request))\n    if limit_reason:\n        raise HTTPException(status_code=429, detail="feedback rate limit reached")\n    try:\n        FEEDBACK.record(req.rating, req.reason)\n    except ValueError as exc:\n        raise HTTPException(status_code=422, detail=str(exc)) from exc\n    return {"ok": True}\n'''
app = replace_once(app, old_feedback, new_feedback, "feedback endpoint")

app_path.write_text(app, encoding="utf-8")

agent_path = Path("backend/agent.py")
agent = agent_path.read_text(encoding="utf-8")
agent = agent.replace(
    "Generation only; embeddings\n    are local, so the free tier is spent on reasoning, not on indexing.",
    "Generation is provider-backed; the embedding backend is configured separately\n    so generation and retrieval remain independently swappable.",
)
agent_path.write_text(agent, encoding="utf-8")

rag_path = Path("backend/rag.py")
rag = rag_path.read_text(encoding="utf-8")
rag = rag.replace("CI (crawl.yml)", "CI (sync-portfolio.yml)")
rag_path.write_text(rag, encoding="utf-8")

print("Runtime hardening applied")
