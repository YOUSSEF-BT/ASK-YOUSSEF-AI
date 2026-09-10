"""Vercel-only latency patch for the portfolio ReAct agent.

For deterministic factual portfolio routes the router already requires retrieval.
On serverless Vercel there is no reason to ask Gemini *whether* to search first:
pre-run the local search tool, seed the ReAct scratchpad with that observation,
then let Gemini synthesize the final grounded answer. This preserves the normal
ReAct loop for non-profile/general turns while removing one remote model round
trip from the common portfolio path.
"""
from __future__ import annotations

import re

import agent as _agent


def _run_iter(self, question: str, require_retrieval: bool = False):
    steps: list[_agent.Step] = []
    scratchpad = ""

    # Deterministic pre-retrieval for factual portfolio questions. The resulting
    # Step is part of Result.steps, so grounding/citation verification and public
    # tools_used reporting see exactly the same search evidence as before.
    if require_retrieval and "search_site" in self.tools:
        step = _agent.Step(
            thought="Retrieve portfolio evidence first.",
            action="search_site",
            action_input=question,
        )
        yield _agent.Event("tool_call", {"tool": "search_site", "input": question})
        step.observation = self.tools["search_site"].run(question)
        yield _agent.Event(
            "observation", {"tool": "search_site", "output": step.observation}
        )
        steps.append(step)
        scratchpad += (
            f"Thought: {step.thought}\n"
            f"Action: {step.action}\n"
            f"Action Input: {step.action_input}\n"
            f"Observation: {step.observation}\n"
            "Thought: The required portfolio search is complete. Use the evidence "
            "above and produce the Final Answer now; only search again if the "
            "evidence is genuinely insufficient.\n"
        )

    for _ in range(self.max_steps):
        prompt = self.prompt_template.format(
            tool_names=", ".join(self.tools),
            tools=_agent.render_tools(list(self.tools.values())),
            question=question,
            scratchpad=scratchpad,
        )
        yield _agent.Event("thinking", {"prompt": prompt, "brain": self.brain_name})
        raw = self.policy(prompt)
        yield _agent.Event("model", {"text": raw})

        step = _agent._parse(raw)
        searched = any(s.action == "search_site" for s in steps)
        if step.action == "__final__":
            if require_retrieval and not searched and "search_site" in self.tools:
                step = _agent.Step(
                    thought=step.thought or "Portfolio facts require retrieved evidence.",
                    action="search_site",
                    action_input=question,
                )
            else:
                steps.append(_agent.Step(thought=step.thought))
                result = _agent.Result(answer=step.action_input or "", steps=steps)
                yield _agent.Event("final", {"answer": result.answer, "result": result})
                return

        if step.action not in self.tools:
            prose = re.sub(r"^\s*Thought:\s*", "", raw.strip(), flags=re.I).strip()
            tried_to_act = re.search(r"\bAction\s*:", raw, re.IGNORECASE) is not None
            if prose and not tried_to_act and not (require_retrieval and not searched):
                steps.append(_agent.Step(thought=step.thought, observation=prose))
                result = _agent.Result(answer=prose, steps=steps)
                yield _agent.Event("final", {"answer": prose, "result": result})
                return
            if self.fallback_tool in self.tools:
                step.action = self.fallback_tool
                step.action_input = step.action_input or question

        if (
            require_retrieval
            and not searched
            and "search_site" in self.tools
            and step.action != "search_site"
        ):
            step = _agent.Step(
                thought=step.thought or "Retrieve portfolio evidence first.",
                action="search_site",
                action_input=question,
            )

        tool = self.tools.get(step.action or "")
        yield _agent.Event("tool_call", {"tool": step.action, "input": step.action_input})
        step.observation = (
            tool.run(step.action_input or "")
            if tool
            else f"Unknown tool {step.action!r}. Available: {', '.join(self.tools)}."
        )
        yield _agent.Event(
            "observation", {"tool": step.action, "output": step.observation}
        )
        steps.append(step)
        scratchpad += (
            f"Thought: {step.thought}\n"
            f"Action: {step.action}\n"
            f"Action Input: {step.action_input}\n"
            f"Observation: {step.observation}\n"
        )

    forced = self.prompt_template.format(
        tool_names=", ".join(self.tools),
        tools=_agent.render_tools(list(self.tools.values())),
        question=question,
        scratchpad=scratchpad
        + "Thought: I have gathered enough information and will not search again; "
          "I'll answer from the observations above.\nFinal Answer:",
    )
    yield _agent.Event("thinking", {"prompt": forced, "brain": self.brain_name})
    try:
        raw = self.policy(forced)
    except Exception:
        raw = ""
    yield _agent.Event("model", {"text": raw})
    answer = _agent._grab("Final Answer: " + raw, r"Final Answer:\s*(.*)") or raw.strip()
    answer = re.split(r"\n(?:Thought|Action|Observation)\s*:", answer)[0].strip()
    if not answer:
        answer = (
            "I couldn't quite pull that together just now — please try rephrasing, "
            "or reach Youssef directly at the email on his site."
        )
    result = _agent.Result(answer=answer, steps=steps, stopped="max_steps")
    yield _agent.Event("final", {"answer": answer, "result": result})


def apply() -> None:
    if getattr(_agent.ReActAgent, "_vercel_pre_retrieval_patch", False):
        return
    _agent.ReActAgent.run_iter = _run_iter
    _agent.ReActAgent._vercel_pre_retrieval_patch = True

    # Gemini 3.7 Flash supports thinking_level=low. It is enough here because
    # retrieval/ranking is deterministic and the model mainly synthesizes cited
    # evidence; lower thinking also keeps serverless latency predictable.
    original_init = _agent.GeminiPolicy.__init__

    def _gemini_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if str(getattr(self, "model", "")).startswith("gemini-3.7"):
            try:
                self._thinking = self._types.ThinkingConfig(thinking_level="low")
            except Exception:
                pass

    _agent.GeminiPolicy.__init__ = _gemini_init


apply()
