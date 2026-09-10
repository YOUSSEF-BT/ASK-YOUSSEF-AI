from pathlib import Path

path = Path("backend/app.py")
text = path.read_text(encoding="utf-8")

# Import HTTPException and the privacy-safe feedback aggregate.
text = text.replace(
    "from fastapi import FastAPI, Request  # noqa: E402",
    "from fastapi import FastAPI, HTTPException, Request  # noqa: E402",
)
if "from feedback import FEEDBACK" not in text:
    text = text.replace(
        "from observability import TELEMETRY  # noqa: E402\n",
        "from observability import TELEMETRY  # noqa: E402\nfrom feedback import FEEDBACK  # noqa: E402\n",
    )

# Add the fixed-schema feedback request. No free-text field exists by design.
chat_model = '''class ChatRequest(BaseModel):
    question: str
    history: list[Turn] = []   # prior turns, oldest→newest (for follow-ups)
'''
feedback_model = chat_model + '''\n\nclass FeedbackRequest(BaseModel):
    rating: str                 # "up" | "down"
    reason: str | None = None   # fixed category only; no free-text comments
'''
if "class FeedbackRequest" not in text:
    if chat_model not in text:
        raise SystemExit("ChatRequest guard not found")
    text = text.replace(chat_model, feedback_model)

old_metrics = '''@app.get("/metrics")
def metrics():
    """Privacy-safe process-lifetime operational metrics; no visitor content."""
    return TELEMETRY.snapshot()
'''
new_metrics = '''@app.get("/metrics")
def metrics():
    """Privacy-safe process-lifetime operational metrics; no visitor content."""
    snapshot = TELEMETRY.snapshot()
    snapshot["feedback"] = FEEDBACK.snapshot()
    return snapshot
'''
if old_metrics in text:
    text = text.replace(old_metrics, new_metrics)
elif new_metrics not in text:
    raise SystemExit("metrics guard not found")

pages_marker = '''@app.get("/pages")
def pages():
'''
product_routes = '''@app.get("/capabilities")
def capabilities():
    """Public, non-secret product metadata used by the portfolio widget."""
    return {
        "name": "Ask Youssef AI",
        "subtitle": "Professional Portfolio Copilot",
        "status": "beta",
        "languages": ["en", "fr", "ar"],
        "retrieval": "semantic+bm25+structured-rrf",
        "features": [
            "grounded portfolio answers",
            "source citations",
            "multilingual routing",
            "conversation context",
            "automatic portfolio synchronization",
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
    try:
        FEEDBACK.record(req.rating, req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True}


'''
if "@app.get(\"/capabilities\")" not in text:
    if pages_marker not in text:
        raise SystemExit("pages route guard not found")
    text = text.replace(pages_marker, product_routes + pages_marker)

# Keep endpoint documentation current.
text = text.replace(
    "  GET  /pages                   → [{title, url, chunks}] for the demo panel\n",
    "  GET  /pages                   → [{title, url, chunks}] for source links\n"
    "  GET  /capabilities            → public product metadata + suggestions\n"
    "  POST /feedback                → fixed-category privacy-safe feedback\n"
    "  GET  /metrics                 → aggregate operational metrics\n",
)

path.write_text(text, encoding="utf-8")
print("Product API routes patched successfully")
