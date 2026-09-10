/*
 * Ask Youssef AI — Professional Portfolio Copilot
 * Zero-dependency embeddable widget, isolated with Shadow DOM.
 *
 * Usage:
 * <script src=".../widget.js"
 *   data-api="https://<service>.onrender.com"
 *   data-title="Ask Youssef AI"
 *   data-subtitle="Professional Portfolio Copilot"
 *   data-accent="#20b2a6" defer></script>
 */
function askYoussefWidget() {
  "use strict";

  var scripts = document.querySelectorAll("script[data-api]");
  var self = document.currentScript;
  if (!self || !self.getAttribute("data-api")) {
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (/widget\.js(?:\?|#|$)/.test(scripts[i].src || "")) {
        self = scripts[i];
        break;
      }
    }
  }

  var API = ((self && self.getAttribute("data-api")) || "").replace(/\/$/, "");
  var TITLE = (self && self.getAttribute("data-title")) || "Ask Youssef AI";
  var SUBTITLE = (self && self.getAttribute("data-subtitle")) || "Professional Portfolio Copilot";
  var ACCENT = (self && self.getAttribute("data-accent")) || "#20b2a6";

  if (!API) {
    console.error("[ask-youssef-ai] Missing data-api on widget script.");
    return;
  }
  if (document.getElementById("ask-youssef-ai-root")) return;

  var copy = getCopy();
  var sources = {};
  var capabilities = null;
  var history = [];
  var busy = false;
  var isOpen = false;

  var host = document.createElement("div");
  host.id = "ask-youssef-ai-root";
  host.style.cssText = "all:initial";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  var style = document.createElement("style");
  style.textContent = CSS.replace(/__ACCENT__/g, ACCENT);
  root.appendChild(style);

  var shell = document.createElement("div");
  shell.className = "aya";
  shell.innerHTML = TEMPLATE
    .replace(/__TITLE__/g, esc(TITLE))
    .replace(/__SUBTITLE__/g, esc(SUBTITLE))
    .replace(/__PLACEHOLDER__/g, esc(copy.placeholder))
    .replace(/__NEW_CHAT__/g, esc(copy.newChat))
    .replace(/__CLOSE__/g, esc(copy.close));
  root.appendChild(shell);

  var launcher = root.querySelector(".aya-launcher");
  var panel = root.querySelector(".aya-panel");
  var log = root.querySelector(".aya-log");
  var form = root.querySelector(".aya-form");
  var input = root.querySelector(".aya-input");
  var send = root.querySelector(".aya-send");
  var close = root.querySelector(".aya-close");
  var reset = root.querySelector(".aya-reset");
  var status = root.querySelector(".aya-status");
  var connection = root.querySelector(".aya-connection");

  launcher.addEventListener("click", function () { toggle(true); });
  close.addEventListener("click", function () { toggle(false); });
  reset.addEventListener("click", resetChat);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen) toggle(false);
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var question = input.value.trim();
    if (!question || busy) return;
    input.value = "";
    ask(question);
  });

  // Public metadata only. Failure never prevents chat from rendering.
  Promise.all([
    fetch(API + "/pages").then(jsonOrThrow),
    fetch(API + "/capabilities").then(jsonOrThrow)
  ]).then(function (values) {
    var pages = values[0];
    capabilities = values[1];
    (pages.pages || []).forEach(function (page) {
      if (page.source && page.url) sources[page.source] = page.url;
    });
    setConnection(true);
    if (!log.dataset.initialized) renderWelcome();
  }).catch(function () {
    // The backend may still accept chat even when metadata fetch failed.
    setConnection(false);
    if (!log.dataset.initialized) renderWelcome();
  });

  var vv = window.visualViewport;
  if (vv) {
    vv.addEventListener("resize", fitMobileViewport);
    vv.addEventListener("scroll", fitMobileViewport);
  }
  window.addEventListener("orientationchange", function () {
    setTimeout(fitMobileViewport, 200);
  });

  function getCopy() {
    var lang = ((document.documentElement.lang || navigator.language || "en") + "").toLowerCase();
    if (lang.indexOf("ar") === 0) {
      return {
        greeting: "مرحباً، أنا Ask Youssef AI.",
        intro: "يمكنني مساعدتك في استكشاف مشاريع يوسف ومهاراته وشهاداته وخبرته المهنية، مع إجابات مبنية على مصادر محفظته.",
        suggestions: [
          "ما هي أقوى مشاريع يوسف في الذكاء الاصطناعي؟",
          "ما خبرته في الرؤية الحاسوبية؟",
          "اعرض أدلة على مهاراته في RAG و LLM",
          "ما هي شهاداته المهنية؟",
          "كيف يمكنني التواصل مع يوسف؟"
        ],
        placeholder: "اسأل عن يوسف...",
        newChat: "محادثة جديدة",
        close: "إغلاق",
        thinking: "جارٍ التحليل...",
        searching: "جارٍ البحث في المصادر...",
        sending: "جارٍ إرسال الرسالة...",
        feedback: "هل كانت الإجابة مفيدة؟",
        thanks: "شكراً لملاحظتك",
        sourceLabel: "المصادر",
        error: "تعذر الوصول إلى المساعد. حاول مرة أخرى.",
        reasons: { incorrect: "غير صحيحة", not_relevant: "غير ذات صلة", missing_source: "المصدر ناقص", too_long: "طويلة جداً" }
      };
    }
    if (lang.indexOf("fr") === 0) {
      return {
        greeting: "Bonjour, je suis Ask Youssef AI.",
        intro: "Je peux vous aider à explorer les projets, compétences, certifications et l'expérience professionnelle de Youssef avec des réponses fondées sur les sources de son portfolio.",
        suggestions: [
          "Montre-moi ses projets IA les plus solides",
          "Quelle est son expérience en Computer Vision ?",
          "Montre les preuves de ses compétences RAG et LLM",
          "Quelles certifications possède-t-il ?",
          "Comment puis-je contacter Youssef ?"
        ],
        placeholder: "Posez une question sur Youssef...",
        newChat: "Nouvelle conversation",
        close: "Fermer",
        thinking: "Analyse en cours...",
        searching: "Recherche dans les sources...",
        sending: "Envoi du message...",
        feedback: "Cette réponse était-elle utile ?",
        thanks: "Merci pour votre retour",
        sourceLabel: "Sources",
        error: "Impossible de joindre l'assistant. Réessayez dans un instant.",
        reasons: { incorrect: "Incorrecte", not_relevant: "Pas pertinente", missing_source: "Source manquante", too_long: "Trop longue" }
      };
    }
    return {
      greeting: "Hi, I'm Ask Youssef AI.",
      intro: "I can help you explore Youssef's projects, skills, certifications and professional experience with answers grounded in his portfolio sources.",
      suggestions: [
        "Show me Youssef's strongest AI projects",
        "What is his Computer Vision experience?",
        "Show evidence of his RAG and LLM skills",
        "Which certifications does he have?",
        "How can I contact Youssef?"
      ],
      placeholder: "Ask about Youssef...",
      newChat: "New chat",
      close: "Close",
      thinking: "Thinking...",
      searching: "Searching portfolio sources...",
      sending: "Sending your message...",
      feedback: "Was this answer useful?",
      thanks: "Thanks for your feedback",
      sourceLabel: "Sources",
      error: "Couldn't reach the assistant. Please try again in a moment.",
      reasons: { incorrect: "Incorrect", not_relevant: "Not relevant", missing_source: "Missing source", too_long: "Too long" }
    };
  }

  function toggle(show) {
    isOpen = show == null ? !isOpen : !!show;
    shell.classList.toggle("aya-open", isOpen);
    launcher.setAttribute("aria-expanded", String(isOpen));
    fitMobileViewport();
    if (isOpen) {
      if (!log.dataset.initialized) renderWelcome();
      setTimeout(function () { input.focus(); }, 80);
    }
  }

  function resetChat() {
    if (busy) return;
    history = [];
    log.innerHTML = "";
    delete log.dataset.initialized;
    renderWelcome();
    input.focus();
  }

  function renderWelcome() {
    if (log.dataset.initialized) return;
    log.dataset.initialized = "1";

    var card = document.createElement("section");
    card.className = "aya-welcome";
    card.innerHTML =
      '<div class="aya-orb" aria-hidden="true">' + SPARK_ICON + '</div>' +
      '<div class="aya-welcome-title">' + esc(copy.greeting) + '</div>' +
      '<p>' + esc(copy.intro) + '</p>' +
      '<div class="aya-trust"><span></span> Hybrid retrieval · grounded answers · citations</div>';
    log.appendChild(card);

    var suggestions = (capabilities && capabilities.suggestions && capabilities.suggestions.length)
      ? capabilities.suggestions.slice(0, 5)
      : copy.suggestions;
    // Prefer localized suggestions when the UI itself is localized.
    if ((document.documentElement.lang || "").toLowerCase().indexOf("en") !== 0 && copy.suggestions) {
      suggestions = copy.suggestions;
    }

    var group = document.createElement("div");
    group.className = "aya-suggestions";
    suggestions.forEach(function (label) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "aya-suggestion";
      button.innerHTML = '<span aria-hidden="true">' + ARROW_ICON + '</span><span>' + esc(label) + '</span>';
      button.addEventListener("click", function () { if (!busy) ask(label); });
      group.appendChild(button);
    });
    log.appendChild(group);
    scrollLog();
  }

  function ask(question) {
    busy = true;
    setBusy(true);
    removeSuggestions();
    addMessage("user", question);
    setStatus(copy.thinking);

    var pending = addMessage("bot", "", true);
    var finalAnswer = "";

    streamChat(question, history.slice(), {
      onEvent: function (event) {
        if (event.kind === "thinking" || event.kind === "model") {
          setStatus(copy.thinking);
        } else if (event.kind === "tool_call") {
          setStatus(event.tool === "send_message" ? copy.sending : copy.searching);
        } else if (event.kind === "final") {
          finalAnswer = event.answer || "";
          completeAnswer(pending, finalAnswer);
        } else if (event.kind === "error") {
          markError(pending, event.message || copy.error);
        }
      },
      onDone: function () {
        busy = false;
        setBusy(false);
        setStatus("");
        if (finalAnswer) {
          history.push({ role: "user", content: question });
          history.push({ role: "assistant", content: finalAnswer });
          if (history.length > 16) history = history.slice(-16);
        }
      },
      onError: function () {
        busy = false;
        setBusy(false);
        setStatus("");
        markError(pending, copy.error);
      }
    });
  }

  function addMessage(who, text, pending) {
    var row = document.createElement("div");
    row.className = "aya-msg aya-" + who;

    var bubble = document.createElement("div");
    bubble.className = "aya-bubble" + (pending ? " aya-pending" : "");
    if (pending) bubble.appendChild(typingDots());
    else if (who === "bot") bubble.innerHTML = renderAnswer(text);
    else bubble.textContent = text;

    row.appendChild(bubble);
    log.appendChild(row);
    scrollLog();
    return { row: row, bubble: bubble };
  }

  function completeAnswer(message, answer) {
    message.bubble.classList.remove("aya-pending", "aya-error");
    message.bubble.innerHTML = renderAnswer(answer);
    appendFeedback(message.row);
    scrollLog();
  }

  function markError(message, text) {
    message.bubble.classList.remove("aya-pending");
    message.bubble.classList.add("aya-error");
    message.bubble.textContent = text;
    scrollLog();
  }

  function appendFeedback(row) {
    var area = document.createElement("div");
    area.className = "aya-feedback";
    area.innerHTML = '<span class="aya-feedback-label">' + esc(copy.feedback) + '</span>';

    var up = feedbackButton("up", THUMB_UP_ICON, "Helpful");
    var down = feedbackButton("down", THUMB_DOWN_ICON, "Not helpful");
    area.appendChild(up);
    area.appendChild(down);

    up.addEventListener("click", function () {
      if (area.dataset.sent) return;
      sendFeedback("up", "helpful");
      thankFeedback(area);
    });
    down.addEventListener("click", function () {
      if (area.dataset.sent || area.querySelector(".aya-reasons")) return;
      var reasons = document.createElement("div");
      reasons.className = "aya-reasons";
      Object.keys(copy.reasons).forEach(function (key) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = copy.reasons[key];
        btn.addEventListener("click", function () {
          if (area.dataset.sent) return;
          sendFeedback("down", key);
          thankFeedback(area);
        });
        reasons.appendChild(btn);
      });
      area.appendChild(reasons);
      scrollLog();
    });

    row.appendChild(area);
  }

  function feedbackButton(kind, icon, label) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "aya-feedback-btn";
    button.setAttribute("aria-label", label);
    button.innerHTML = icon;
    button.dataset.kind = kind;
    return button;
  }

  function sendFeedback(rating, reason) {
    fetch(API + "/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: rating, reason: reason })
    }).catch(function () {});
  }

  function thankFeedback(area) {
    area.dataset.sent = "1";
    area.innerHTML = '<span class="aya-thanks">' + CHECK_ICON + esc(copy.thanks) + '</span>';
  }

  function renderAnswer(text) {
    var safe = esc(text || "");
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    safe = safe.replace(/\[([a-z0-9][a-z0-9_.:-]{1,120})\]/gi, function (match, slug) {
      var url = sources[slug];
      if (!url) return '<span class="aya-citation">[' + esc(slug) + ']</span>';
      return '<a class="aya-citation" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">[' + esc(slug) + ']</a>';
    });
    safe = safe.replace(/(^|[^"'=])(https?:\/\/[^\s<)]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    safe = safe.replace(/\n/g, "<br>");
    return safe;
  }

  function setConnection(ok) {
    connection.classList.toggle("aya-offline", !ok);
    connection.querySelector("span:last-child").textContent = ok ? "Grounded portfolio copilot" : "Portfolio copilot";
  }

  function setStatus(text) {
    status.textContent = text || "";
    status.classList.toggle("aya-visible", !!text);
  }

  function setBusy(value) {
    input.disabled = value;
    send.disabled = value;
    shell.classList.toggle("aya-busy", value);
  }

  function removeSuggestions() {
    var suggestions = log.querySelector(".aya-suggestions");
    if (suggestions) suggestions.remove();
  }

  function typingDots() {
    var dots = document.createElement("span");
    dots.className = "aya-dots";
    dots.innerHTML = "<i></i><i></i><i></i>";
    return dots;
  }

  function scrollLog() {
    requestAnimationFrame(function () { log.scrollTop = log.scrollHeight; });
  }

  function fitMobileViewport() {
    if (!vv || !isOpen || !window.matchMedia("(max-width: 520px)").matches) {
      panel.style.removeProperty("top");
      panel.style.removeProperty("left");
      panel.style.removeProperty("right");
      panel.style.removeProperty("bottom");
      panel.style.removeProperty("width");
      panel.style.removeProperty("height");
      return;
    }
    panel.style.position = "fixed";
    panel.style.top = (vv.offsetTop + 8) + "px";
    panel.style.left = (vv.offsetLeft + 8) + "px";
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    panel.style.width = Math.max(280, vv.width - 16) + "px";
    panel.style.height = Math.max(360, vv.height - 16) + "px";
  }

  function streamChat(question, priorHistory, callbacks) {
    fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: priorHistory })
    }).then(function (response) {
      if (!response.ok || !response.body) throw new Error("HTTP " + response.status);
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";

      function pump() {
        reader.read().then(function (result) {
          if (result.done) {
            if (buffer.trim()) parseSseChunk(buffer, callbacks.onEvent);
            callbacks.onDone();
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";
          blocks.forEach(function (block) { parseSseChunk(block, callbacks.onEvent); });
          pump();
        }).catch(function () { callbacks.onError(); });
      }
      pump();
    }).catch(function () { callbacks.onError(); });
  }

  function parseSseChunk(block, onEvent) {
    var lines = block.split("\n");
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].indexOf("data:") !== 0) continue;
      try { onEvent(JSON.parse(lines[i].slice(5).trim())); } catch (error) {}
    }
  }

  function jsonOrThrow(response) {
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  var SPARK_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l1.5 5.2L19 9l-5.5 1.8L12 16l-1.5-5.2L5 9l5.5-1.8L12 2Zm7 12 .8 2.7L22.5 18l-2.7.8L19 21.5l-.8-2.7-2.7-.8 2.7-.8L19 14ZM5 14l.9 3.1L9 18l-3.1.9L5 22l-.9-3.1L1 18l3.1-.9L5 14Z" fill="currentColor"/></svg>';
  var ARROW_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11m-4-4 4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var RESET_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 6h8.2A3.8 3.8 0 0 1 16 9.8v.4a3.8 3.8 0 0 1-3.8 3.8H7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="m7 3-3 3 3 3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CLOSE_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 5 10 10M15 5 5 15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
  var SEND_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="m3.5 10 12.8-5.5-3.1 11-3.1-4.1L3.5 10Zm6.6 1.4 6.2-6.9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var THUMB_UP_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7 17H4.6A1.6 1.6 0 0 1 3 15.4V10a1.6 1.6 0 0 1 1.6-1.6H7m0 8.6V8.4l2.6-5.1c.3-.6 1-.8 1.6-.5.8.4 1.2 1.3.9 2.2l-.8 2.5h3.3a2.2 2.2 0 0 1 2.1 2.8l-1.4 5.1A2.2 2.2 0 0 1 13.2 17H7Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var THUMB_DOWN_ICON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7 3H4.6A1.6 1.6 0 0 0 3 4.6V10a1.6 1.6 0 0 0 1.6 1.6H7M7 3v8.6l2.6 5.1c.3.6 1 .8 1.6.5.8-.4 1.2-1.3.9-2.2l-.8-2.5h3.3a2.2 2.2 0 0 0 2.1-2.8l-1.4-5.1A2.2 2.2 0 0 0 13.2 3H7Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK_ICON = '<svg viewBox="0 0 18 18" aria-hidden="true"><path d="m4 9 3 3 7-7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  // Icons are defined after function declarations but before first user interaction.
  root.querySelector(".aya-brand-icon").innerHTML = SPARK_ICON;
  root.querySelector(".aya-launcher-icon").innerHTML = SPARK_ICON;
  reset.innerHTML = RESET_ICON;
  close.innerHTML = CLOSE_ICON;
  send.innerHTML = SEND_ICON;
}

var TEMPLATE = [
  '<button class="aya-launcher" type="button" aria-label="Open Ask Youssef AI" aria-expanded="false">',
  '  <span class="aya-launcher-icon"></span>',
  '  <span class="aya-launcher-copy"><strong>Ask Youssef AI</strong><small>Portfolio Copilot</small></span>',
  '</button>',
  '<section class="aya-panel" role="dialog" aria-modal="false" aria-label="Ask Youssef AI">',
  '  <header class="aya-head">',
  '    <div class="aya-brand-icon"></div>',
  '    <div class="aya-head-copy">',
  '      <strong>__TITLE__</strong>',
  '      <span>__SUBTITLE__</span>',
  '      <div class="aya-connection"><span class="aya-dot"></span><span>Portfolio copilot</span></div>',
  '    </div>',
  '    <button class="aya-icon-btn aya-reset" type="button" aria-label="__NEW_CHAT__" title="__NEW_CHAT__"></button>',
  '    <button class="aya-icon-btn aya-close" type="button" aria-label="__CLOSE__" title="__CLOSE__"></button>',
  '  </header>',
  '  <div class="aya-log" role="log" aria-live="polite" aria-relevant="additions"></div>',
  '  <div class="aya-status" aria-live="polite"></div>',
  '  <form class="aya-form">',
  '    <input class="aya-input" type="text" autocomplete="off" maxlength="600" placeholder="__PLACEHOLDER__" aria-label="__PLACEHOLDER__">',
  '    <button class="aya-send" type="submit" aria-label="Send"></button>',
  '  </form>',
  '  <div class="aya-foot"><span>Grounded in Youssef\'s public portfolio</span><span>EN · FR · AR</span></div>',
  '</section>'
].join("\n");

var CSS = `
:host { all: initial; }
.aya, .aya *, .aya *::before, .aya *::after { box-sizing: border-box; }
.aya {
  --accent: __ACCENT__;
  --bg: #0f1418;
  --card: #141a1f;
  --surface: #1a2329;
  --muted-bg: #252e37;
  --text: #f0f2f5;
  --muted: #8c98a5;
  --border: #242b32;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 2147483000;
  color: var(--text);
  direction: ltr;
}
.aya button, .aya input { font: inherit; }
.aya button:focus-visible, .aya input:focus-visible, .aya a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.aya-launcher {
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--border));
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(20px) saturate(1.2);
  color: var(--text);
  min-height: 58px;
  padding: 8px 14px 8px 9px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  box-shadow: 0 16px 45px rgba(0,0,0,.42), 0 0 30px color-mix(in srgb, var(--accent) 12%, transparent), inset 0 1px rgba(255,255,255,.04);
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.aya-launcher:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--accent) 70%, var(--border)); box-shadow: 0 20px 55px rgba(0,0,0,.48), 0 0 35px color-mix(in srgb, var(--accent) 18%, transparent); }
.aya-launcher-icon, .aya-brand-icon {
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 95%, #fff 5%), color-mix(in srgb, var(--accent) 78%, #062723));
  color: #fff;
  box-shadow: 0 0 24px color-mix(in srgb, var(--accent) 28%, transparent);
}
.aya-launcher-icon { width: 40px; height: 40px; border-radius: 13px; flex: 0 0 40px; }
.aya-launcher-icon svg { width: 21px; height: 21px; }
.aya-launcher-copy { display: flex; flex-direction: column; text-align: left; line-height: 1.15; }
.aya-launcher-copy strong { font-size: 13px; font-weight: 700; letter-spacing: -.01em; }
.aya-launcher-copy small { font-size: 10.5px; color: var(--muted); margin-top: 4px; }
.aya-open .aya-launcher { opacity: 0; transform: translateY(8px) scale(.96); pointer-events: none; }

.aya-panel {
  position: absolute;
  right: 0;
  bottom: 0;
  width: min(410px, calc(100vw - 44px));
  height: min(650px, calc(100vh - 44px));
  min-height: 500px;
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--accent) 18%, var(--border));
  background: linear-gradient(180deg, rgba(20,26,31,.98), rgba(15,20,24,.985));
  backdrop-filter: blur(26px) saturate(1.15);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 32px 90px rgba(0,0,0,.58), 0 0 50px color-mix(in srgb, var(--accent) 8%, transparent), inset 0 1px rgba(255,255,255,.035);
  opacity: 0;
  pointer-events: none;
  transform: translateY(14px) scale(.97);
  transform-origin: bottom right;
  transition: opacity .18s ease, transform .24s cubic-bezier(.2,.85,.25,1.05);
}
.aya-open .aya-panel { opacity: 1; pointer-events: auto; transform: none; }

.aya-head {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 14px 14px;
  border-bottom: 1px solid var(--border);
  background: radial-gradient(120% 140% at 0% 0%, color-mix(in srgb, var(--accent) 11%, transparent), transparent 58%);
}
.aya-brand-icon { width: 42px; height: 42px; flex: 0 0 42px; border-radius: 13px; }
.aya-brand-icon svg { width: 22px; height: 22px; }
.aya-head-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.aya-head-copy strong { font-family: "Playfair Display", Georgia, serif; font-size: 17px; line-height: 1.15; font-weight: 650; }
.aya-head-copy > span { margin-top: 2px; color: var(--muted); font-size: 10.5px; }
.aya-connection { display: flex; align-items: center; gap: 5px; margin-top: 5px; color: #9fb1b0; font-size: 9.5px; }
.aya-dot { width: 6px; height: 6px; border-radius: 50%; background: #3ddc97; box-shadow: 0 0 8px rgba(61,220,151,.6); }
.aya-offline .aya-dot { background: #83909b; box-shadow: none; }
.aya-icon-btn {
  appearance: none; border: 0; background: transparent; color: var(--muted); width: 34px; height: 34px; border-radius: 10px;
  display: grid; place-items: center; cursor: pointer; transition: background .15s ease, color .15s ease;
}
.aya-icon-btn:hover { background: var(--muted-bg); color: var(--text); }
.aya-icon-btn svg { width: 18px; height: 18px; }

.aya-log {
  flex: 1;
  overflow-y: auto;
  padding: 16px 15px 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: #34404a transparent;
}
.aya-welcome {
  border: 1px solid color-mix(in srgb, var(--accent) 18%, var(--border));
  background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 6%, var(--card)), var(--card));
  border-radius: 17px;
  padding: 15px;
}
.aya-orb { width: 34px; height: 34px; border-radius: 11px; display: grid; place-items: center; color: var(--accent); background: color-mix(in srgb, var(--accent) 10%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 20%, transparent); margin-bottom: 10px; }
.aya-orb svg { width: 18px; height: 18px; }
.aya-welcome-title { font-family: "Playfair Display", Georgia, serif; font-size: 17px; font-weight: 650; }
.aya-welcome p { color: #aab3bd; font-size: 12.5px; line-height: 1.55; margin: 7px 0 11px; }
.aya-trust { font-size: 9.5px; color: #83909b; display: flex; align-items: center; gap: 6px; }
.aya-trust span { width: 5px; height: 5px; border-radius: 50%; background: var(--accent); }
.aya-suggestions { display: grid; gap: 7px; }
.aya-suggestion {
  appearance: none;
  width: 100%;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--surface) 68%, transparent);
  color: #dce2e8;
  border-radius: 12px;
  padding: 9px 11px;
  display: flex;
  align-items: center;
  gap: 9px;
  text-align: left;
  font-size: 11.5px;
  line-height: 1.35;
  cursor: pointer;
  transition: border-color .15s ease, background .15s ease, transform .15s ease;
}
.aya-suggestion:hover { border-color: color-mix(in srgb, var(--accent) 45%, var(--border)); background: color-mix(in srgb, var(--accent) 7%, var(--surface)); transform: translateX(2px); }
.aya-suggestion svg { width: 16px; height: 16px; color: var(--accent); flex: 0 0 16px; }

.aya-msg { display: flex; flex-direction: column; animation: aya-in .22s ease both; }
.aya-user { align-items: flex-end; }
.aya-bot { align-items: flex-start; }
.aya-bubble { max-width: 88%; border-radius: 15px; padding: 10px 12px; font-size: 12.5px; line-height: 1.55; overflow-wrap: anywhere; }
.aya-user .aya-bubble { color: #f4fffd; background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 28%, var(--surface)), color-mix(in srgb, var(--accent) 17%, var(--surface))); border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border)); border-bottom-right-radius: 5px; }
.aya-bot .aya-bubble { color: #e3e8ed; background: #161d22; border: 1px solid var(--border); border-bottom-left-radius: 5px; }
.aya-bubble a { color: #55cfc5; text-decoration: underline; text-decoration-color: color-mix(in srgb, var(--accent) 45%, transparent); text-underline-offset: 3px; }
.aya-citation { display: inline; font-size: .92em; }
.aya-error { color: #ffb1b1 !important; border-color: rgba(255,120,120,.2) !important; }
.aya-feedback { max-width: 88%; margin-top: 5px; min-height: 25px; display: flex; flex-wrap: wrap; align-items: center; gap: 5px; color: #73808c; font-size: 9.5px; }
.aya-feedback-label { margin-right: 2px; }
.aya-feedback-btn { appearance: none; border: 0; background: transparent; color: #73808c; width: 28px; height: 25px; border-radius: 8px; display: grid; place-items: center; cursor: pointer; }
.aya-feedback-btn:hover { color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, transparent); }
.aya-feedback-btn svg { width: 15px; height: 15px; }
.aya-reasons { flex-basis: 100%; display: flex; gap: 5px; flex-wrap: wrap; margin-top: 2px; }
.aya-reasons button { appearance: none; border: 1px solid var(--border); background: transparent; color: #95a0aa; border-radius: 999px; padding: 4px 7px; font-size: 9px; cursor: pointer; }
.aya-reasons button:hover { color: var(--text); border-color: color-mix(in srgb, var(--accent) 35%, var(--border)); }
.aya-thanks { display: inline-flex; align-items: center; gap: 4px; color: #82918f; }
.aya-thanks svg { width: 13px; height: 13px; color: var(--accent); }

.aya-dots { display: inline-flex; align-items: center; gap: 4px; height: 16px; }
.aya-dots i { display: block; width: 5px; height: 5px; border-radius: 50%; background: #7f8a95; animation: aya-bounce 1s ease-in-out infinite; }
.aya-dots i:nth-child(2) { animation-delay: .12s; }
.aya-dots i:nth-child(3) { animation-delay: .24s; }
.aya-status { min-height: 0; max-height: 0; opacity: 0; padding: 0 16px; overflow: hidden; color: #77838e; font-size: 9.5px; transition: all .15s ease; }
.aya-status.aya-visible { min-height: 23px; max-height: 23px; opacity: 1; padding-top: 5px; }

.aya-form { border-top: 1px solid var(--border); padding: 10px 11px; display: flex; gap: 8px; background: rgba(15,20,24,.72); }
.aya-input { appearance: none; border: 1px solid var(--border); outline: none; min-width: 0; flex: 1; color: var(--text); background: #11171b; border-radius: 13px; padding: 10px 12px; font-size: 12px; transition: border-color .15s ease, box-shadow .15s ease; }
.aya-input::placeholder { color: #68747f; }
.aya-input:focus { border-color: color-mix(in srgb, var(--accent) 58%, var(--border)); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 10%, transparent); }
.aya-send { appearance: none; border: 0; width: 39px; height: 39px; flex: 0 0 39px; border-radius: 12px; display: grid; place-items: center; cursor: pointer; color: #fff; background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 94%, #fff 6%), color-mix(in srgb, var(--accent) 82%, #082b28)); box-shadow: 0 8px 22px color-mix(in srgb, var(--accent) 18%, transparent); }
.aya-send svg { width: 18px; height: 18px; }
.aya-send:disabled, .aya-input:disabled { opacity: .62; cursor: wait; }
.aya-foot { padding: 0 12px 8px; display: flex; justify-content: space-between; gap: 8px; color: #56616b; font-size: 8.5px; background: rgba(15,20,24,.72); }

@keyframes aya-in { from { opacity: 0; transform: translateY(4px); } }
@keyframes aya-bounce { 0%, 60%, 100% { opacity: .45; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-4px); } }
@media (prefers-reduced-motion: reduce) { .aya *, .aya *::before, .aya *::after { animation-duration: .001ms !important; transition-duration: .001ms !important; } }
@media (max-width: 520px) {
  .aya { right: 12px; bottom: 12px; }
  .aya-launcher { min-height: 54px; border-radius: 17px; }
  .aya-launcher-copy small { display: none; }
  .aya-panel { width: calc(100vw - 16px); height: calc(100dvh - 16px); min-height: 0; border-radius: 18px; }
  .aya-log { padding: 14px 12px 8px; }
  .aya-bubble, .aya-feedback { max-width: 92%; }
}
`;

// TEMPLATE and CSS are initialized before mounting the widget.
askYoussefWidget();
