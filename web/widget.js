/*
 * Ask Youssef AI — embeddable chat bubble (the product).
 *
 * Zero dependencies, self-contained, style-isolated via Shadow DOM so the host
 * page's CSS can neither leak in nor out. Drop it on any site:
 *
 *   <script src=".../widget.js"
 *           data-api="https://<service>.onrender.com"
 *           data-title="Ask Youssef AI"
 *           data-accent="#f0b429" defer></script>
 *
 * It injects a floating launcher bottom-right; clicking it opens a chat panel
 * that streams the backend's /chat SSE and shows ONLY the final answer (plus a
 * subtle status while the agent works). All the reasoning/tool internals stay
 * hidden here — that's what the demo page is for.
 */
// Defined as a named function and CALLED at the very bottom of this file — not
// an IIFE — because the mount code below reads CSS/TEMPLATE, which are declared
// with `var` further down. Running immediately here would see them as
// `undefined` (var hoisting), so we invoke after they're assigned.
function pcbWidget() {
  "use strict";

  // Find our own <script> tag to read config from. document.currentScript is
  // set for parser-inserted classic scripts, but is null for `defer`/`async`
  // tags and for scripts injected dynamically (the demo page does this) — so
  // fall back to locating the widget.js tag by its data-api attribute.
  var SELF = document.currentScript;
  if (!SELF || !SELF.getAttribute("data-api")) {
    var cands = document.querySelectorAll("script[data-api]");
    for (var i = cands.length - 1; i >= 0; i--) {
      if (/widget\.js(\?|#|$)/.test(cands[i].src)) { SELF = cands[i]; break; }
    }
    if ((!SELF || !SELF.getAttribute("data-api")) && cands.length) {
      SELF = cands[cands.length - 1];   // last resort: the last data-api script
    }
  }
  var API = (SELF && SELF.getAttribute("data-api") || "").replace(/\/$/, "");
  var TITLE = (SELF && SELF.getAttribute("data-title")) || "Ask Youssef AI";
  var ACCENT = (SELF && SELF.getAttribute("data-accent")) || "#f0b429";
  var SUBTITLE = (SELF && SELF.getAttribute("data-subtitle")) ||
    "Explore Youssef's projects, skills, certifications and professional work.";

  if (!API) {
    console.error("[ask-youssef-ai] missing data-api on the <script> tag");
    return;
  }

  // Fetch the indexed pages once so we can hyperlink the [source] citations the
  // bot writes (e.g. [home], [blogs-attention-model]) to their real page URLs.
  // Best-effort: if it fails, citations simply stay as plain text.
  var SOURCES = {};   // { slug: url }
  fetch(API + "/pages")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      (d && d.pages || []).forEach(function (p) {
        if (p.source && p.url) SOURCES[p.source] = p.url;
      });
    })
    .catch(function () {});

  // ---- host + shadow root -------------------------------------------------
  var host = document.createElement("div");
  host.id = "ask-youssef-ai-root";
  host.style.cssText = "all:initial";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  var style = document.createElement("style");
  style.textContent = CSS.replace(/__ACCENT__/g, ACCENT);
  root.appendChild(style);

  var wrap = document.createElement("div");
  wrap.className = "pcb";
  wrap.innerHTML = TEMPLATE
    .replace(/__TITLE__/g, esc(TITLE))
    .replace(/__SUBTITLE__/g, esc(SUBTITLE));
  root.appendChild(wrap);

  var launcher = root.querySelector(".pcb-launcher");
  var panel = root.querySelector(".pcb-panel");
  var closeBtn = root.querySelector(".pcb-close");
  var log = root.querySelector(".pcb-log");
  var form = root.querySelector(".pcb-form");
  var input = root.querySelector(".pcb-input");
  var status = root.querySelector(".pcb-status");

  var open = false;
  var busy = false;
  var history = [];   // [{role,content}] prior turns, sent so follow-ups work

  // --- mobile: keep the panel inside the *visual* viewport ------------------
  // On phones the on-screen keyboard shrinks the visible area but NOT 100vh, so
  // a bottom-anchored near-full-height panel spills off-screen and its header
  // ends up above the top edge. window.visualViewport DOES track the keyboard,
  // so when the panel is open on a small screen we pin it to that box; on
  // desktop / when closed we clear the overrides and let the stylesheet rule.
  var vv = window.visualViewport;
  function fitPanel() {
    var s = panel.style;
    if (open && vv && window.matchMedia("(max-width: 480px)").matches) {
      s.position = "fixed";
      s.top = (vv.offsetTop + 8) + "px";
      s.left = (vv.offsetLeft + 8) + "px";
      s.right = "auto"; s.bottom = "auto";
      s.width = (vv.width - 16) + "px";
      s.height = (vv.height - 16) + "px";
    } else {
      s.position = s.top = s.left = s.right = s.bottom = s.width = s.height = "";
    }
  }
  if (vv) {
    vv.addEventListener("resize", fitPanel);
    vv.addEventListener("scroll", fitPanel);
  }
  window.addEventListener("orientationchange", function () {
    setTimeout(fitPanel, 250);
  });

  function toggle(show) {
    open = show == null ? !open : show;
    wrap.classList.toggle("pcb-open", open);
    launcher.setAttribute("aria-expanded", String(open));
    fitPanel();   // size to the viewport on open; clear overrides on close
    if (open) {
      setTimeout(function () { input.focus(); }, 60);
      if (!log.dataset.greeted) {
        addMsg("bot", "Hi! Ask me anything about Youssef — his work, projects, "
          + "or how to get in touch.");
        log.dataset.greeted = "1";
      }
    }
  }
  launcher.addEventListener("click", function () { toggle(); });
  closeBtn.addEventListener("click", function () { toggle(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && open) toggle(false);
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q || busy) return;
    input.value = "";
    ask(q);
  });

  function ask(question) {
    busy = true;
    addMsg("user", question);
    setStatus("Thinking…");
    var bubble = addMsg("bot", "");   // the answer streams/lands here
    bubble.classList.add("pcb-pending");
    var answer = "";

    streamChat(question, history.slice(), {
      onEvent: function (ev) {
        if (ev.kind === "thinking") setStatus("Thinking…");
        else if (ev.kind === "tool_call") {
          setStatus(ev.tool === "send_message"
            ? "Sending your message…" : "Searching the site…");
        } else if (ev.kind === "final") {
          answer = ev.answer || "(no answer)";
          bubble.classList.remove("pcb-pending");
          bubble.innerHTML = render(answer);
          scroll();
        } else if (ev.kind === "error") {
          bubble.classList.remove("pcb-pending");
          bubble.classList.add("pcb-err");
          bubble.textContent = "Something went wrong: " + (ev.message || "unknown error");
        }
      },
      onDone: function () {
        busy = false; setStatus("");
        if (answer) {                 // remember this turn for follow-ups
          history.push({ role: "user", content: question },
            { role: "assistant", content: answer });
          if (history.length > 16) history = history.slice(-16);
        }
      },
      onError: function (msg) {
        busy = false; setStatus("");
        bubble.classList.remove("pcb-pending");
        bubble.classList.add("pcb-err");
        bubble.textContent = "Couldn't reach the assistant. " + (msg || "");
      },
    });
  }

  // ---- UI helpers ---------------------------------------------------------
  function addMsg(who, text) {
    var row = document.createElement("div");
    row.className = "pcb-msg pcb-" + who;
    var b = document.createElement("div");
    b.className = "pcb-bubble";
    if (text) b.innerHTML = render(text); else b.appendChild(dots());
    row.appendChild(b);
    log.appendChild(row);
    scroll();
    return b;
  }
  function dots() {
    var d = document.createElement("span");
    d.className = "pcb-dots";
    d.innerHTML = "<i></i><i></i><i></i>";
    return d;
  }
  function setStatus(t) {
    status.textContent = t || "";
    status.classList.toggle("pcb-on", !!t);
  }
  function scroll() { log.scrollTop = log.scrollHeight; }

  // ---- rendering: linkify markdown links + bare URLs, escape the rest -----
  function render(text) {
    var out = esc(text);
    // [label](url)
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // [source] citations → link to the cited page. The bot cites the page slug
    // (e.g. [home]); map it to a URL via SOURCES (from /pages). Unknown slugs are
    // left untouched. Runs after the markdown-link pass so it only sees bare tags.
    out = out.replace(/\[([a-z0-9][a-z0-9-]*)\]/g, function (m, slug) {
      var url = SOURCES[slug];
      return url
        ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">[' + slug + ']</a>'
        : m;
    });
    // bare urls not already inside an anchor
    out = out.replace(/(^|[^"'>])(https?:\/\/[^\s<)]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    out = out.replace(/\n/g, "<br>");
    return out;
  }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ---- SSE over fetch (POST) ----------------------------------------------
  function streamChat(question, history, cb) {
    fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history }),
    }).then(function (res) {
      if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
      var reader = res.body.getReader();
      var dec = new TextDecoder();
      var buf = "";
      (function pump() {
        reader.read().then(function (r) {
          if (r.done) { cb.onDone(); return; }
          buf += dec.decode(r.value, { stream: true });
          var chunks = buf.split("\n\n");
          buf = chunks.pop();               // keep the incomplete tail
          chunks.forEach(function (chunk) {
            var line = chunk.split("\n").find(function (l) {
              return l.indexOf("data:") === 0;
            });
            if (!line) return;
            try { cb.onEvent(JSON.parse(line.slice(5).trim())); } catch (e) {}
          });
          pump();
        }).catch(function (e) { cb.onError(e.message); });
      })();
    }).catch(function (e) { cb.onError(e.message); });
  }
}

// ===========================================================================
// markup + styles (kept as strings so the whole widget is one file)
// ===========================================================================
var TEMPLATE = [
  '<button class="pcb-launcher" aria-label="Open chat" aria-expanded="false">',
  '  <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">',
  '    <path fill="currentColor" d="M12 3C6.5 3 2 6.86 2 11.5c0 2.2 1.02 4.2 2.7 5.7L4 21l4.2-1.4c1.16.36 2.44.56 3.8.56 5.5 0 10-3.86 10-8.66S17.5 3 12 3z"/>',
  '  </svg>',
  '</button>',
  '<section class="pcb-panel" role="dialog" aria-label="Chat">',
  '  <header class="pcb-head">',
  '    <div class="pcb-head-txt">',
  '      <div class="pcb-title">__TITLE__</div>',
  '      <div class="pcb-sub">__SUBTITLE__</div>',
  '    </div>',
  '    <button class="pcb-close" aria-label="Close chat">&times;</button>',
  '  </header>',
  '  <div class="pcb-log" role="log" aria-live="polite"></div>',
  '  <div class="pcb-status" aria-live="polite"></div>',
  '  <form class="pcb-form">',
  '    <input class="pcb-input" type="text" autocomplete="off"',
  '           placeholder="Ask a question…" aria-label="Your question">',
  '    <button class="pcb-send" type="submit" aria-label="Send">',
  '      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">',
  '        <path fill="currentColor" d="M3 20.5l19-8.5L3 3.5 3 10l13 2-13 2z"/>',
  '      </svg>',
  '    </button>',
  '  </form>',
  '</section>',
].join("\n");

var CSS = `
:host, .pcb { all: initial; }
.pcb *, .pcb *::before, .pcb *::after { box-sizing: border-box; }
.pcb {
  --accent: __ACCENT__;
  --ink: #0e1016;
  --ink-2: #161a24;
  --line: rgba(255,255,255,.09);
  --text: #eef1f7;
  --muted: #9aa3b2;
  --radius: 18px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  position: fixed; right: 22px; bottom: 22px; z-index: 2147483000;
  color: var(--text);
}
/* launcher */
.pcb-launcher {
  all: unset; cursor: pointer; position: absolute; right: 0; bottom: 0;
  width: 60px; height: 60px; border-radius: 50%;
  display: grid; place-items: center; color: #1a1205;
  background: radial-gradient(120% 120% at 30% 20%, color-mix(in srgb, var(--accent) 92%, #fff) 0%, var(--accent) 55%, color-mix(in srgb, var(--accent) 70%, #000) 100%);
  box-shadow: 0 10px 30px -6px color-mix(in srgb, var(--accent) 55%, transparent), 0 2px 8px rgba(0,0,0,.4);
  transition: transform .22s cubic-bezier(.2,.9,.3,1.3), box-shadow .22s;
}
.pcb-launcher:hover { transform: translateY(-2px) scale(1.05); }
.pcb-launcher:active { transform: scale(.96); }
.pcb-open .pcb-launcher { transform: scale(0); opacity: 0; pointer-events: none; }
@media (prefers-reduced-motion: no-preference) {
  .pcb-launcher::after {
    content: ""; position: absolute; inset: -6px; border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--accent) 60%, transparent);
    animation: pcb-pulse 2.6s ease-out infinite; pointer-events: none;
  }
}
@keyframes pcb-pulse { 0% { transform: scale(.85); opacity: .7; } 100% { transform: scale(1.5); opacity: 0; } }

/* panel */
.pcb-panel {
  position: absolute; right: 0; bottom: 0;
  width: min(384px, calc(100vw - 44px));
  height: min(600px, calc(100vh - 44px));
  display: flex; flex-direction: column; overflow: hidden;
  border-radius: var(--radius); border: 1px solid var(--line);
  background: linear-gradient(180deg, color-mix(in srgb, var(--ink-2) 92%, transparent), color-mix(in srgb, var(--ink) 96%, transparent));
  backdrop-filter: blur(18px) saturate(1.2);
  box-shadow: 0 24px 70px -18px rgba(0,0,0,.7), 0 0 0 1px rgba(255,255,255,.02) inset;
  transform: translateY(16px) scale(.96); opacity: 0; pointer-events: none;
  transform-origin: bottom right;
  transition: transform .26s cubic-bezier(.2,.9,.3,1.15), opacity .2s;
}
.pcb-open .pcb-panel { transform: none; opacity: 1; pointer-events: auto; }
@media (prefers-reduced-motion: reduce) { .pcb-panel, .pcb-launcher { transition: none; } }

.pcb-head {
  display: flex; align-items: center; gap: 12px; padding: 15px 16px;
  border-bottom: 1px solid var(--line);
  background: radial-gradient(140% 100% at 0% 0%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%);
}
.pcb-title { font-family: "Fraunces", Georgia, "Times New Roman", serif; font-weight: 600; font-size: 18px; letter-spacing: .1px; }
.pcb-sub { color: var(--muted); font-size: 11.5px; margin-top: 2px; }
.pcb-head-txt { flex: 1; min-width: 0; }
.pcb-close { all: unset; cursor: pointer; color: var(--muted); font-size: 26px; line-height: 1; padding: 0 4px; border-radius: 8px; }
.pcb-close:hover { color: var(--text); }

.pcb-log { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; scrollbar-width: thin; }
.pcb-log::-webkit-scrollbar { width: 7px; }
.pcb-log::-webkit-scrollbar-thumb { background: var(--line); border-radius: 4px; }

.pcb-msg { display: flex; }
.pcb-user { justify-content: flex-end; }
.pcb-bubble {
  max-width: 84%; padding: 10px 13px; border-radius: 14px; font-size: 14px;
  line-height: 1.5; word-wrap: break-word; animation: pcb-in .28s ease both;
}
@keyframes pcb-in { from { opacity: 0; transform: translateY(6px); } }
.pcb-bot .pcb-bubble {
  background: color-mix(in srgb, var(--ink) 60%, #fff 4%);
  border: 1px solid var(--line); border-bottom-left-radius: 5px;
}
.pcb-user .pcb-bubble {
  background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 22%, var(--ink-2)), color-mix(in srgb, var(--accent) 12%, var(--ink-2)));
  border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
  border-bottom-right-radius: 5px;
}
.pcb-bubble a { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
.pcb-err { color: #ff9b9b; }

.pcb-dots { display: inline-flex; gap: 4px; padding: 2px 0; }
.pcb-dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); display: inline-block; animation: pcb-bounce 1.2s infinite ease-in-out; }
.pcb-dots i:nth-child(2) { animation-delay: .15s; } .pcb-dots i:nth-child(3) { animation-delay: .3s; }
@keyframes pcb-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-5px); opacity: 1; } }

.pcb-status {
  height: 0; overflow: hidden; padding: 0 16px; color: var(--muted);
  font-size: 11.5px; font-style: italic; transition: height .2s, padding .2s;
}
.pcb-status.pcb-on { height: 22px; padding-bottom: 4px; }

.pcb-form { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--line); }
.pcb-input {
  all: unset; flex: 1; padding: 11px 14px; border-radius: 12px; font-size: 14px; color: var(--text);
  background: color-mix(in srgb, var(--ink) 70%, #000); border: 1px solid var(--line);
}
.pcb-input:focus { border-color: color-mix(in srgb, var(--accent) 55%, transparent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent); }
.pcb-input::placeholder { color: var(--muted); }
.pcb-send {
  all: unset; cursor: pointer; width: 44px; display: grid; place-items: center; border-radius: 12px; color: #1a1205;
  background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 95%, #fff), var(--accent));
  transition: transform .15s, filter .15s;
}
.pcb-send:hover { filter: brightness(1.06); } .pcb-send:active { transform: scale(.94); }

@media (max-width: 480px) {
  .pcb { right: 12px; bottom: 12px; }
  /* JS pins the panel to visualViewport when open (keyboard-safe); these are the
     pre-open / no-visualViewport fallbacks. dvh tracks browser chrome; the vh
     line stays first so browsers without dvh support still get a height. */
  .pcb-panel {
    width: calc(100vw - 24px);
    height: calc(100vh - 24px);
    height: calc(100dvh - 24px);
  }
}
`;

// CSS + TEMPLATE are now assigned, so it's safe to mount.
pcbWidget();
