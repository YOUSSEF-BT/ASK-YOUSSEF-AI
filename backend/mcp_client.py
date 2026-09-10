"""Phase 3 — a minimal MCP client, from scratch, standard library only.

MCP (Model Context Protocol) over stdio is just **JSON-RPC 2.0, one JSON object
per line**, exchanged with a server subprocess over its stdin/stdout. There's no
magic: launch the process, do a three-message handshake, then call tools. This
file is that, in ~70 lines — so it runs even on Python 3.9, while the *server*
(mcp_server/blog_server.py) uses the FastMCP framework on 3.12. Client and
server never share a runtime; that decoupling is the whole point of a protocol.

    client = MCPStdioClient([PY312, "mcp_server/blog_server.py"])
    print(client.call_tool("search_site", {"query": "what is PPO?"}))
    client.close()

Two clients, one contract. `MCPStdioClient` is the real thing: it talks to a
separate server process over stdio. `InProcessMCPClient` speaks the *same*
JSON-RPC `tools/call` contract but to an in-memory handler — no subprocess, no
second runtime — so it deploys to a single-container host (Hugging Face Spaces)
while the agent and UI still treat search as an MCP tool call.
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from agent import Tool
from contact import send_contact_message
from rag import search_site_text

PROTOCOL_VERSION = "2025-06-18"


class MCPStdioClient:
    def __init__(self, command: list[str]) -> None:
        # stderr stays separate (server logs there); stdout carries protocol JSON.
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._id = 0
        self._handshake()

    # --- wire helpers --------------------------------------------------------
    def _send(self, msg: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        # read lines until we see the response with our id (skip notifications)
        assert self.proc.stdout is not None
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                raise RuntimeError("MCP server closed the connection")
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"MCP error: {msg['error']}")
                return msg.get("result", {})

    # --- protocol ------------------------------------------------------------
    def _handshake(self) -> None:
        self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "blog-agent", "version": "0.1"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        # result.content is a list of typed blocks; concatenate the text ones.
        parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
        text = "\n".join(p for p in parts if p)
        return text or "(no text content returned)"

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def make_mcp_search_tool(client: Any, k: int = 3) -> Tool:
    """Expose an MCP `search_site` tool as a local agent Tool. The agent can't
    tell the difference — it emits `Action: search_site` as always; the call goes
    out through MCP (a subprocess for MCPStdioClient, an in-memory handler for
    InProcessMCPClient)."""
    def _run(query: str) -> str:
        return client.call_tool("search_site", {"query": query, "k": k})
    return Tool(
        name="search_site",
        description="Search Youssef's website — blog posts, projects, about/contact "
                    "— for a topic (via an MCP server). Input: a short query. Returns "
                    "relevant passages with scores; if weak, rephrase and search again.",
        run=_run,
    )


# --- the contact / send_message tool ---------------------------------------
# Unlike search_site (one string in), send_message needs an email + a message.
# The ReAct protocol only gives a tool a single string, so the agent passes a
# small JSON object as its Action Input; we parse it here (leniently) into the
# three fields the capability expects.

_CONTACT_DESC = (
    "Email a message to Youssef (the site owner) on the visitor's behalf. Use this "
    "ONLY when the visitor explicitly wants to contact Youssef or leave him a "
    "question AND has given their own email. Input: a JSON object "
    '{"email": "visitor@example.com", "message": "what to send", "name": "optional"}. '
    "Returns whether the message was sent. Do NOT use for questions you can answer "
    "or search for — this emails a real person."
)


def _parse_contact_input(raw: str) -> tuple[str, str, str]:
    """Pull (message, from_email, name) out of the agent's Action Input. Prefers
    a JSON object; falls back to sniffing an email address out of free text so a
    slightly-malformed turn still reaches the owner."""
    raw = (raw or "").strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return (str(obj.get("message", "")).strip(),
                    str(obj.get("email") or obj.get("from_email", "")).strip(),
                    str(obj.get("name", "")).strip())
    except (ValueError, TypeError):
        pass
    m = re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw)
    email = m.group(0) if m else ""
    message = raw.replace(email, "").strip(" ,;:-") if email else raw
    return message, email, ""


def make_contact_tool() -> Tool:
    """Direct (no-MCP) send_message tool — calls the Formspree capability itself."""
    def _run(raw: str) -> str:
        message, email, name = _parse_contact_input(raw)
        return send_contact_message(message, email, name)
    return Tool(name="send_message", description=_CONTACT_DESC, run=_run)


def make_mcp_contact_tool(client: Any) -> Tool:
    """send_message routed through an MCP client (subprocess or in-process). The
    agent can't tell the difference — same JSON Action Input, same string back."""
    def _run(raw: str) -> str:
        message, email, name = _parse_contact_input(raw)
        return client.call_tool(
            "send_message",
            {"message": message, "from_email": email, "name": name},
        )
    return Tool(name="send_message", description=_CONTACT_DESC, run=_run)


# ===========================================================================
# In-process MCP — same JSON-RPC contract, no subprocess (deployable anywhere)
# ===========================================================================

class _InProcessServer:
    """The blog server's `tools/call` handler, in-memory. It answers the exact
    same JSON-RPC messages a real MCP server would — we just hand it dicts
    directly instead of writing them to a subprocess's stdin."""

    def __init__(self, rag: Any) -> None:
        self._rag = rag

    def handle(self, req: dict) -> dict:
        rid, method = req.get("id"), req.get("method")
        if method == "initialize":
            return _ok(rid, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                             "serverInfo": {"name": "blog-search-inproc", "version": "0.1"}})
        if method == "tools/call":
            params = req.get("params", {})
            if params.get("name") != "search_site":
                return {"jsonrpc": "2.0", "id": rid,
                        "error": {"code": -32601, "message": f"unknown tool {params.get('name')}"}}
            args = params.get("arguments", {})
            text = search_site_text(self._rag, args.get("query", ""),
                                    k=args.get("k", 3), min_score=args.get("min_score", 0.25))
            return _ok(rid, {"content": [{"type": "text", "text": text}]})
        return _ok(rid, {})


def _ok(rid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


class InProcessMCPClient:
    """MCPStdioClient's twin, without the process boundary. Same call_tool/close
    surface, same JSON-RPC round-trip — just to an in-memory server object."""

    def __init__(self, rag: Any) -> None:
        self._server = _InProcessServer(rag)
        self._id = 0
        self._request("initialize", {"protocolVersion": PROTOCOL_VERSION,
                                     "capabilities": {}, "clientInfo": {"name": "blog-agent"}})

    def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        resp = self._server.handle({"jsonrpc": "2.0", "id": self._id,
                                    "method": method, "params": params})
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result", {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
        return "\n".join(p for p in parts if p) or "(no text content returned)"

    def close(self) -> None:
        pass  # nothing to tear down — no process, no socket


class _InProcessContactServer:
    """In-memory twin of the FastMCP contact server: same `send_message`
    tools/call contract, but calls the Formspree capability directly."""

    def handle(self, req: dict) -> dict:
        rid, method = req.get("id"), req.get("method")
        if method == "initialize":
            return _ok(rid, {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                             "serverInfo": {"name": "contact-inproc", "version": "0.1"}})
        if method == "tools/call":
            params = req.get("params", {})
            if params.get("name") != "send_message":
                return {"jsonrpc": "2.0", "id": rid,
                        "error": {"code": -32601, "message": f"unknown tool {params.get('name')}"}}
            args = params.get("arguments", {})
            text = send_contact_message(args.get("message", ""),
                                        args.get("from_email", ""), args.get("name", ""))
            return _ok(rid, {"content": [{"type": "text", "text": text}]})
        return _ok(rid, {})


class InProcessContactMCPClient:
    """InProcessMCPClient's sibling for the contact server — same surface, no
    subprocess. Lets MCP_TRANSPORT=inprocess wire send_message offline too."""

    def __init__(self) -> None:
        self._server = _InProcessContactServer()
        self._id = 0
        self._request("initialize", {"protocolVersion": PROTOCOL_VERSION,
                                     "capabilities": {}, "clientInfo": {"name": "blog-agent"}})

    def _request(self, method: str, params: dict) -> dict:
        self._id += 1
        resp = self._server.handle({"jsonrpc": "2.0", "id": self._id,
                                    "method": method, "params": params})
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result", {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
        return "\n".join(p for p in parts if p) or "(no text content returned)"

    def close(self) -> None:
        pass  # nothing to tear down — no process, no socket
