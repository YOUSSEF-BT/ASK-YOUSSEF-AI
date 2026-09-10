from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"Already applied: {path}")
        return
    if old not in text:
        raise SystemExit(f"Expected patch anchor not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


agent = Path("backend/agent.py")
replace_once(
    agent,
    '''    def run_iter(self, question: str):
        """Drive the loop, yielding an Event at each stage so a UI can show the
        agent's reasoning in real time. The final Event carries the Result.
        `run()` is just this generator with the events thrown away."""
        steps: list[Step] = []
''',
    '''    def run_iter(self, question: str, require_retrieval: bool = False):
        """Drive the loop and emit high-level events.

        `require_retrieval=True` is a deterministic orchestration guard used for
        factual portfolio questions. The first valid action is forced to
        `search_site` before any final answer can be accepted, so grounding does
        not depend only on the model following prompt instructions.
        """
        steps: list[Step] = []
''',
)

replace_once(
    agent,
    '''            step = _parse(raw)
            if step.action == "__final__":
                steps.append(Step(thought=step.thought))
                result = Result(answer=step.action_input or "", steps=steps)
                yield Event("final", {"answer": result.answer, "result": result})
                return
''',
    '''            step = _parse(raw)
            searched = any(s.action == "search_site" for s in steps)
            if step.action == "__final__":
                if require_retrieval and not searched and "search_site" in self.tools:
                    step = Step(
                        thought=step.thought or "Portfolio facts require retrieved evidence.",
                        action="search_site",
                        action_input=question,
                    )
                else:
                    steps.append(Step(thought=step.thought))
                    result = Result(answer=step.action_input or "", steps=steps)
                    yield Event("final", {"answer": result.answer, "result": result})
                    return
''',
)

replace_once(
    agent,
    '''            if step.action not in self.tools:
                prose = re.sub(r"^\\s*Thought:\\s*", "", raw.strip(), flags=re.I).strip()
                tried_to_act = re.search(r"\\bAction\\s*:", raw, re.IGNORECASE) is not None
                if prose and not tried_to_act:
                    steps.append(Step(thought=step.thought, observation=prose))
                    result = Result(answer=prose, steps=steps)
                    yield Event("final", {"answer": prose, "result": result})
                    return
                if self.fallback_tool in self.tools:
                    step.action = self.fallback_tool
                    step.action_input = step.action_input or question

            # dispatch the tool
''',
    '''            if step.action not in self.tools:
                prose = re.sub(r"^\\s*Thought:\\s*", "", raw.strip(), flags=re.I).strip()
                tried_to_act = re.search(r"\\bAction\\s*:", raw, re.IGNORECASE) is not None
                if prose and not tried_to_act and not (require_retrieval and not searched):
                    steps.append(Step(thought=step.thought, observation=prose))
                    result = Result(answer=prose, steps=steps)
                    yield Event("final", {"answer": prose, "result": result})
                    return
                if self.fallback_tool in self.tools:
                    step.action = self.fallback_tool
                    step.action_input = step.action_input or question

            # A factual portfolio route must gather evidence before doing anything
            # else. This also prevents a malformed model turn from skipping search.
            if require_retrieval and not searched and "search_site" in self.tools \
                    and step.action != "search_site":
                step = Step(
                    thought=step.thought or "Retrieve portfolio evidence first.",
                    action="search_site",
                    action_input=question,
                )

            # dispatch the tool
''',
)

replace_once(
    agent,
    '''    def run(self, question: str) -> Result:
        result = Result(answer="")
        for ev in self.run_iter(question):
''',
    '''    def run(self, question: str, require_retrieval: bool = False) -> Result:
        result = Result(answer="")
        for ev in self.run_iter(question, require_retrieval=require_retrieval):
''',
)

replace_once(
    agent,
    '''    def run_iter(self, question: str):
        # set up the canned turns for THIS question, then drive the normal loop
''',
    '''    def run_iter(self, question: str, require_retrieval: bool = False):
        # set up the canned turns for THIS question, then drive the normal loop
''',
)

replace_once(
    agent,
    '''        self.policy = ScriptedPolicy(turns)
        yield from super().run_iter(question)
''',
    '''        self.policy = ScriptedPolicy(turns)
        yield from super().run_iter(question, require_retrieval=require_retrieval)
''',
)

app = Path("backend/app.py")
replace_once(
    app,
    '''from retrieval.hybrid import HybridRetriever  # noqa: E402
''',
    '''from retrieval.hybrid import HybridRetriever  # noqa: E402
from router import route_question  # noqa: E402
''',
)

replace_once(
    app,
    '''    contextual = _with_history(question, history or [])
    # bounded wait: if another turn is mid-flight (the agent shares one stdio
''',
    '''    route = route_question(question)
    contextual = _with_history(question, history or [])
    # bounded wait: if another turn is mid-flight (the agent shares one stdio
''',
)

replace_once(
    app,
    '''            for ev in STATE.agent.run_iter(contextual):
                if ev.kind == "thinking":
                    yield _sse("thinking", brain=ev.data["brain"], prompt=ev.data["prompt"])
                elif ev.kind == "model":
                    yield _sse("model", text=ev.data["text"])
                elif ev.kind == "tool_call":
                    yield _sse("tool_call", tool=ev.data["tool"], input=ev.data["input"])
''',
    '''            for ev in STATE.agent.run_iter(
                    contextual, require_retrieval=route.requires_retrieval):
                if ev.kind == "thinking":
                    # Do not expose internal prompts or hidden reasoning on a
                    # public API. The client only gets a high-level progress event.
                    yield _sse("thinking", brain=ev.data["brain"])
                elif ev.kind == "model":
                    # Preserve the event boundary for the technical demo without
                    # leaking raw model reasoning/decision text.
                    yield _sse("model")
                elif ev.kind == "tool_call":
                    tool_input = ev.data["input"] if ev.data["tool"] == "search_site" else None
                    yield _sse("tool_call", tool=ev.data["tool"], input=tool_input)
''',
)

# The demo page should describe public orchestration signals, not claim to show
# private prompts/raw model reasoning.
demo = Path("web/demo.js")
replace_once(
    demo,
    '''      addTBlock("① Prompt sent to " + esc(ev.brain), ev.prompt);
    } else if (ev.kind === "model") {
      addStep("💬", "model", "Model replied — parsing its decision.");
      addTBlock("② Raw model output", ev.text);
''',
    '''      addTBlock("① Orchestration", "Internal prompt and hidden reasoning are intentionally not exposed.");
    } else if (ev.kind === "model") {
      addStep("💬", "model", "Model decision ready — internal reasoning remains private.");
      addTBlock("② Model boundary", "Raw model reasoning is intentionally not exposed by the public API.");
''',
)

print("Intent/language routing, forced factual retrieval, and safe public tracing enabled.")
