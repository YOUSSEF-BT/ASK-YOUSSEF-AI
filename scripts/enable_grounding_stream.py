from pathlib import Path


path = Path("backend/app.py")
text = path.read_text(encoding="utf-8")
old = '''                elif ev.kind == "final":
                    steps = ev.data["result"].steps
                    used = sorted({s.action for s in steps
                                   if s.action and s.action not in ("__final__",)})
                    yield _sse("final", answer=ev.data["answer"], tools_used=used)
'''
new = '''                elif ev.kind == "final":
                    steps = ev.data["result"].steps
                    used = sorted({s.action for s in steps
                                   if s.action and s.action not in ("__final__",)})
                    # Final model output gets a second, deterministic grounding
                    # boundary. Retrieved source citations are guaranteed and
                    # unsupported metrics/URLs/emails are blocked before SSE.
                    from grounding import enforce_grounding
                    guarded_answer, _report = enforce_grounding(ev.data["answer"], steps)
                    yield _sse("final", answer=guarded_answer, tools_used=used)
'''

if new in text:
    raise SystemExit("Grounding stream integration already applied")
if old not in text:
    raise SystemExit("Expected app.py final-event block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Grounding verifier integrated into final SSE output.")
