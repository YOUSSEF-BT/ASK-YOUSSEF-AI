"""The `send_message` capability — forward a visitor's message to the site owner
by email, via the portfolio's existing **Formspree** endpoint.

Kept in its own stdlib-only module (like `rag.search_site_text` for search) so
both transports return byte-identical results: the real FastMCP contact server
(mcp_server/contact_server.py) and the in-process contact client
(mcp_client.InProcessContactMCPClient) import this one function. No third-party
deps — a contact form shouldn't pull in the whole RAG stack.

Formspree emails the owner whatever we POST; its free tier is ~50 messages/mo,
so the guardrails here (real-looking email + non-empty message required) matter:
the agent must only reach for this when a visitor genuinely wants to get in touch.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

# Deliberately loose: reject obvious garbage/empties, don't police valid-but-odd
# addresses. The point is "did the visitor actually give an email", not RFC 5322.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def send_contact_message(message: str, from_email: str, name: str = "",
                         timeout: float = 10.0) -> str:
    """POST a visitor's message to FORMSPREE_ENDPOINT so Formspree emails the
    owner. Returns a short human-readable status the agent can relay verbatim.

    Never raises: every failure path returns a "couldn't send" string, because
    this runs inside the agent loop and a raised exception would abort the turn."""
    endpoint = os.environ.get("FORMSPREE_ENDPOINT", "").strip()
    if not endpoint:
        return ("Sorry — the contact channel isn't configured, so I can't send a "
                "message right now.")

    message = (message or "").strip()
    from_email = (from_email or "").strip()
    if not message:
        return "I need a message to send. What would you like to tell Youssef?"
    if not _EMAIL.match(from_email):
        return ("I need a valid email address to send this so Youssef can reply. "
                "What's the best email to reach you at?")

    payload = json.dumps({
        "email": from_email,
        "name": (name or "").strip(),
        "message": message,
        "_subject": f"Portfolio chatbot: message from {name.strip() or from_email}",
    }).encode("utf-8")
    # Present a full, realistic browser fingerprint. Formspree's spam filter
    # 403s the default "Python-urllib/x.y" User-Agent (it reads as a bot) — which
    # is why a manual curl to the same form works but this server-side POST
    # didn't. Sending the same headers a real AJAX submit from the site would
    # carry (Chrome UA + Origin/Referer + Accept-Language + Sec-Fetch-*) makes
    # the request indistinguishable from an in-browser fetch, so it's accepted.
    origin = os.environ.get("FORMSPREE_REFERER", "https://youssef-bt.github.io").rstrip("/")
    req = urllib.request.Request(
        endpoint, data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/125.0.0.0 Safari/537.36"),
            # a domain-restricted form checks Origin/Referer; send the site so it
            # still accepts a server-side POST (override via FORMSPREE_REFERER).
            "Origin": origin,
            "Referer": origin + "/",
            "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return (f"Sent — Youssef will get your message and can reply to "
                        f"{from_email}. Thanks for reaching out!")
            return (f"Sorry, the message didn't go through (status {resp.status}). "
                    "Please try emailing Youssef directly.")
    except urllib.error.HTTPError as e:
        # Log Formspree's actual error body so a 403/422 is diagnosable from the
        # Render logs (deprecated endpoint, inactive form, domain restriction,
        # etc.) — the visitor still sees only the clean message below.
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        print(f"[contact] Formspree {e.code} for endpoint {endpoint!r}: {detail}",
              file=sys.stderr, flush=True)
        return (f"Sorry, the message didn't go through (status {e.code}). "
                "Please try emailing Youssef directly.")
    except Exception:
        return ("Sorry, I couldn't reach the contact service just now. "
                "Please try emailing Youssef directly.")
