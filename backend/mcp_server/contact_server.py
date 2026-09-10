"""A real MCP server for contacting the site owner, built with FastMCP.

The second MCP server in this project (the first is blog_server.py). It runs as
its OWN process and exposes a single tool, `send_message`, that forwards a
visitor's message to Youssef by email via his portfolio's Formspree endpoint.
The agent connects over stdio and calls it exactly like `search_site` — same
protocol, different capability. No index, no model: this server is tiny.

The actual send lives in contact.send_contact_message (stdlib only), shared with
the in-process client so both transports behave identically.

Run standalone (stdio):  python mcp_server/contact_server.py
The agent normally launches this for you (see agent.build_agent).
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # the backend/ dir, where contact.py lives
sys.path.append(ROOT)                 # APPEND: never shadow the real `mcp` package

from fastmcp import FastMCP  # noqa: E402
from contact import send_contact_message  # noqa: E402

mcp = FastMCP("contact")
print(f"[contact-server] ready (formspree {'set' if os.environ.get('FORMSPREE_ENDPOINT') else 'MISSING'})",
      file=sys.stderr, flush=True)


@mcp.tool
def send_message(message: str, from_email: str, name: str = "") -> str:
    """Email a visitor's message to Youssef (the site owner).

    Use ONLY when the visitor explicitly wants to contact Youssef or leave him a
    question AND has given their own email. `message` is what to send,
    `from_email` is the visitor's address (so Youssef can reply), `name` is
    optional. Returns whether it was sent. Never use this to answer questions —
    it emails a real person.
    """
    return send_contact_message(message, from_email, name)


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
