from pathlib import Path


path = Path("backend/app.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from retrieval.hybrid import HybridRetriever  # noqa: E402\n",
        "from observability import TELEMETRY  # noqa: E402\n"
        "from retrieval.hybrid import HybridRetriever  # noqa: E402\n",
    ),
    (
        '''    if STATE.agent is None:\n        yield _sse("error", message="agent not ready")\n        return\n    route = route_question(question)\n    contextual = _with_history(question, history or [])\n''',
        '''    started = time.monotonic()\n    route = route_question(question)\n    TELEMETRY.record_request(route)\n    if STATE.agent is None:\n        TELEMETRY.record_error(latency_ms=(time.monotonic() - started) * 1000.0)\n        yield _sse("error", message="agent not ready")\n        return\n    contextual = _with_history(question, history or [])\n''',
    ),
    (
        '''    if not STATE.lock.acquire(timeout=45):\n        yield _sse("error", message="The assistant is busy with another question — "\n                   "give it a moment and try again.")\n        return\n''',
        '''    if not STATE.lock.acquire(timeout=45):\n        TELEMETRY.record_error(latency_ms=(time.monotonic() - started) * 1000.0)\n        yield _sse("error", message="The assistant is busy with another question — "\n                   "give it a moment and try again.")\n        return\n''',
    ),
    (
        '''                    guarded_answer, _report = enforce_grounding(ev.data["answer"], steps)\n                    yield _sse("final", answer=guarded_answer, tools_used=used)\n''',
        '''                    guarded_answer, _report = enforce_grounding(ev.data["answer"], steps)\n                    TELEMETRY.record_completed(\n                        latency_ms=(time.monotonic() - started) * 1000.0,\n                        retrieval_used="search_site" in used,\n                        grounding_intervened=guarded_answer != ev.data["answer"],\n                    )\n                    yield _sse("final", answer=guarded_answer, tools_used=used)\n''',
    ),
    (
        '''        except Exception as exc:  # never leave the stream hanging on a failure\n            low = str(exc).lower()\n''',
        '''        except Exception as exc:  # never leave the stream hanging on a failure\n            TELEMETRY.record_error(latency_ms=(time.monotonic() - started) * 1000.0)\n            low = str(exc).lower()\n''',
    ),
    (
        '''@app.get("/pages")\ndef pages():\n''',
        '''@app.get("/metrics")\ndef metrics():\n    """Privacy-safe process-lifetime operational metrics; no visitor content."""\n    return TELEMETRY.snapshot()\n\n\n@app.get("/pages")\ndef pages():\n''',
    ),
]

for old, new in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"Expected app.py block not found:\n{old[:220]}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Privacy-safe runtime observability wired into FastAPI.")
