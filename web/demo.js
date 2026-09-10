/*
 * Demo page client — the "behind the scenes" explainer.
 *
 * Consumes the SAME /chat SSE stream the widget does, but renders EVERY event
 * kind (thinking / model / tool_call / observation / final) so a visitor can
 * watch the ReAct loop and the MCP tool calls happen. Also loads /health and
 * /pages for the header stats and the indexed-pages panel.
 */
(function () {
  "use strict";

  // ---- config: edit API_DEFAULT after deploy, or pass ?api=… for local dev --
  var API_DEFAULT = "http://localhost:8000";  // ← Render backend URL
  var params = new URLSearchParams(location.search);
  var API = (params.get("api") || API_DEFAULT).replace(/\/$/, "");

  // let the inline bootstrap in index.html attach the widget with this API
  document.dispatchEvent(new CustomEvent("pcb:config", { detail: { api: API } }));

  var $ = function (id) { return document.getElementById(id); };
  var steps = $("steps"), tbody = $("transcript-body"), transcript = $("transcript");
  var thread = $("thread"), threadEmpty = $("thread-empty"), activityTurn = $("activity-turn");
  var form = $("ask"), q = $("q"), send = $("send"), resetBtn = $("reset");

  var history = [];   // [{role,content}] prior turns, sent so follow-ups work
  var turnNo = 0;

  var EXAMPLES = [
    "What are Youssef's strongest AI projects?",
    "Show me Youssef's Computer Vision experience.",
    "Which certifications support his AI profile?",
    "How can I contact Youssef?",
  ];
  var exWrap = $("examples");
  EXAMPLES.forEach(function (t) {
    var b = document.createElement("button");
    b.className = "ex"; b.type = "button"; b.textContent = t;
    b.addEventListener("click", function () { q.value = t; form.requestSubmit(); });
    exWrap.appendChild(b);
  });

  // ---- health + pages -----------------------------------------------------
  fetch(API + "/health").then(function (r) { return r.json(); }).then(function (h) {
    $("st-status").textContent = h.ok ? "online" : "starting";
    $("st-brain").textContent = h.brain || "—";
    $("st-pages").textContent = h.pages;
    $("st-chunks").textContent = h.chunks;
    $("st-transport").textContent = h.transport === "process" ? "subprocess" : h.transport;
  }).catch(function () { $("st-status").textContent = "unreachable"; });

  fetch(API + "/pages").then(function (r) { return r.json(); }).then(function (d) {
    var el = $("pages"); el.innerHTML = "";
    $("pg-count").textContent = (d.pages.length) + " pages · " + d.total_chunks + " chunks";
    if (!d.pages.length) { el.innerHTML = '<span class="pages-empty">No pages indexed.</span>'; return; }
    d.pages.forEach(function (p) {
      var row = document.createElement("div"); row.className = "pg";
      var title = p.url
        ? '<a href="' + attr(p.url) + '" target="_blank" rel="noopener">' + esc(p.title) + '</a>'
        : '<span class="t">' + esc(p.title) + '</span>';
      row.innerHTML = title + '<span class="c">' + p.chunks + '</span>';
      el.appendChild(row);
    });
  }).catch(function () {
    $("pages").innerHTML = '<span class="pages-empty">Couldn\'t load pages.</span>';
  });

  // ---- ask ----------------------------------------------------------------
  var stepNo = 0;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var question = q.value.trim();
    if (!question || send.disabled) return;
    q.value = "";

    if (threadEmpty) threadEmpty.remove();
    turnNo++;
    addMsg("user", question);
    var answerBubble = addMsg("bot", "");        // filled on `final`
    answerBubble.classList.add("pending");
    resetActivity();
    send.disabled = true;
    var answer = "";

    streamChat(question, history.slice(), {
      onEvent: function (ev) { answer = handleEvent(ev, answerBubble) || answer; },
      onDone: function () {
        send.disabled = false; q.focus();
        if (answer) {                            // remember for follow-ups
          history.push({ role: "user", content: question },
            { role: "assistant", content: answer });
          if (history.length > 16) history = history.slice(-16);
        }
      },
      onError: function (msg) {
        send.disabled = false;
        answerBubble.classList.remove("pending");
        answerBubble.classList.add("err");
        answerBubble.textContent = "Stream failed: " + (msg || "unknown");
        addStep("⚠️", "err", "Stream failed: " + esc(msg || "unknown"));
      },
    });
  });

  resetBtn.addEventListener("click", function () {
    if (send.disabled) return;                   // don't nuke a turn in flight
    history = []; turnNo = 0;
    thread.innerHTML = '<div class="thread-empty" id="thread-empty">'
      + 'Ask anything about Youssef — his blogs, projects, or how to reach him. '
      + 'Then keep the conversation going; it remembers what you asked.</div>';
    threadEmpty = $("thread-empty");
    resetActivity();
    q.focus();
  });

  // clear only the current-turn reasoning view (the conversation thread stays)
  function resetActivity() {
    stepNo = 0;
    steps.innerHTML = ""; tbody.innerHTML = "";
    transcript.hidden = true; transcript.open = false;
    if (activityTurn) activityTurn.textContent = turnNo ? "· turn " + turnNo : "";
  }

  function handleEvent(ev, answerBubble) {
    if (ev.kind === "thinking") {
      stepNo++;
      addStep("🧠", "think", "<b>Step " + stepNo + "</b> — reasoning, calling <code>"
        + esc(ev.brain) + "</code>…");
      addTBlock("① Orchestration", "Internal prompt and hidden reasoning are intentionally not exposed.");
    } else if (ev.kind === "model") {
      addStep("💬", "model", "Model decision ready — internal reasoning remains private.");
      addTBlock("② Model boundary", "Raw model reasoning is intentionally not exposed by the public API.");
    } else if (ev.kind === "tool_call") {
      var verb = ev.tool === "send_message" ? "Emailing Youssef via" : "Searching via";
      addStep("🔧", "tool", verb + " MCP tool <code>" + esc(ev.tool) + "</code>",
        "input: " + esc(ev.input || ""));
      addTBlock("③ MCP tool call → " + esc(ev.tool), "input: " + (ev.input || ""));
    } else if (ev.kind === "observation") {
      addStep("📚", "obs", "Observation received — handing results back to the model.");
      addTBlock("④ Observation (tool result)", ev.output);
    } else if (ev.kind === "final") {
      var used = (ev.tools_used && ev.tools_used.length)
        ? "used " + ev.tools_used.map(function (t) { return "`" + t + "`"; }).join(", ")
        : "answered directly from its own knowledge";
      addStep("✅", "final", "<b>Done</b> — the agent " + esc(used) + ".");
      var answer = ev.answer || "(no answer)";
      answerBubble.classList.remove("pending");
      answerBubble.innerHTML = render(answer);
      scrollThread();
      return answer;
    } else if (ev.kind === "error") {
      answerBubble.classList.remove("pending");
      answerBubble.classList.add("err");
      answerBubble.textContent = "Error: " + (ev.message || "unknown");
      addStep("⚠️", "err", "Error: " + esc(ev.message || "unknown"));
    }
  }

  // ---- conversation thread ------------------------------------------------
  function addMsg(who, text) {
    var row = document.createElement("div");
    row.className = "msg msg-" + who;
    var b = document.createElement("div");
    b.className = "msg-bubble";
    if (text) b.innerHTML = render(text); else b.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
    row.appendChild(b);
    thread.appendChild(row);
    scrollThread();
    return b;
  }
  function scrollThread() { thread.scrollTop = thread.scrollHeight; }

  function addStep(icon, kind, html, meta) {
    var d = document.createElement("div");
    d.className = "step k-" + kind;
    d.innerHTML = '<div class="ic">' + icon + '</div><div class="tx">' + html
      + (meta ? '<div class="meta">' + meta + "</div>" : "") + "</div>";
    steps.appendChild(d);
  }

  function addTBlock(title, text) {
    transcript.hidden = false;
    var b = document.createElement("div"); b.className = "tblock";
    var pre = document.createElement("pre"); pre.textContent = text || "";
    var h = document.createElement("div"); h.className = "th"; h.textContent = title;
    b.appendChild(h); b.appendChild(pre); tbody.appendChild(b);
  }

  // ---- rendering ----------------------------------------------------------
  function render(text) {
    var out = esc(text);
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    out = out.replace(/(^|[^"'>])(https?:\/\/[^\s<)]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    return out.replace(/\n/g, "<br>");
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function attr(s) { return esc(s).replace(/'/g, "&#39;"); }

  // ---- SSE over fetch (POST) ----------------------------------------------
  function streamChat(question, history, cb) {
    fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history }),
    }).then(function (res) {
      if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
      var reader = res.body.getReader(), dec = new TextDecoder(), buf = "";
      (function pump() {
        reader.read().then(function (r) {
          if (r.done) { cb.onDone(); return; }
          buf += dec.decode(r.value, { stream: true });
          var parts = buf.split("\n\n"); buf = parts.pop();
          parts.forEach(function (chunk) {
            var line = chunk.split("\n").find(function (l) { return l.indexOf("data:") === 0; });
            if (!line) return;
            try { cb.onEvent(JSON.parse(line.slice(5).trim())); } catch (e) {}
          });
          pump();
        }).catch(function (e) { cb.onError(e.message); });
      })();
    }).catch(function (e) { cb.onError(e.message); });
  }
})();
