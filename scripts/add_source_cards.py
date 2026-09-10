from pathlib import Path

path = Path("web/widget.js")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"guard not found: {label}")
    text = text.replace(old, new, 1)


replace_once(
    "  var sources = {};\n  var capabilities = null;",
    "  var sources = {};\n  var sourceMeta = {};\n  var capabilities = null;",
    "source metadata state",
)

replace_once(
    '''    (pages.pages || []).forEach(function (page) {\n      if (page.source && page.url) sources[page.source] = page.url;\n    });''',
    '''    (pages.pages || []).forEach(function (page) {\n      if (page.source && page.url) {\n        sources[page.source] = page.url;\n        sourceMeta[page.source] = {\n          url: page.url,\n          title: page.title || page.source\n        };\n      }\n    });''',
    "page metadata mapping",
)

replace_once(
    '''    message.bubble.classList.remove("aya-pending", "aya-error");\n    message.bubble.innerHTML = renderAnswer(answer);\n    appendFeedback(message.row);''',
    '''    message.bubble.classList.remove("aya-pending", "aya-error");\n    message.bubble.innerHTML = renderAnswer(answer);\n    appendSourceCards(message.row, answer);\n    appendFeedback(message.row);''',
    "source card invocation",
)

marker = '''  function appendFeedback(row) {\n'''
source_fn = '''  function appendSourceCards(row, answer) {\n    var seen = {};\n    var cited = [];\n    var regex = /\\[([a-z0-9][a-z0-9_.:-]{1,120})\\]/gi;\n    var match;\n    while ((match = regex.exec(answer || "")) && cited.length < 3) {\n      var slug = match[1];\n      if (!seen[slug] && sourceMeta[slug] && sourceMeta[slug].url) {\n        seen[slug] = true;\n        cited.push({ slug: slug, meta: sourceMeta[slug] });\n      }\n    }\n    if (!cited.length) return;\n\n    var wrap = document.createElement("div");\n    wrap.className = "aya-source-wrap";\n    var label = document.createElement("div");\n    label.className = "aya-source-label";\n    label.textContent = copy.sourceLabel;\n    wrap.appendChild(label);\n\n    cited.forEach(function (entry) {\n      var card = document.createElement("a");\n      card.className = "aya-source-card";\n      card.href = entry.meta.url;\n      card.target = "_blank";\n      card.rel = "noopener noreferrer";\n      card.innerHTML =\n        '<span class="aya-source-icon">' + ARROW_ICON + '</span>' +\n        '<span class="aya-source-copy"><strong>' + esc(entry.meta.title) + '</strong>' +\n        '<small>' + esc(entry.slug) + '</small></span>' +\n        '<span class="aya-source-open" aria-hidden="true">↗</span>';\n      wrap.appendChild(card);\n    });\n    row.appendChild(wrap);\n  }\n\n'''
if source_fn not in text:
    if marker not in text:
        raise SystemExit("feedback function marker missing")
    text = text.replace(marker, source_fn + marker, 1)

css_marker = '''.aya-feedback { max-width: 88%; margin-top: 5px; min-height: 25px; display: flex; flex-wrap: wrap; align-items: center; gap: 5px; color: #73808c; font-size: 9.5px; }'''
css_source = '''.aya-source-wrap { width: min(92%, 340px); margin-top: 7px; display: grid; gap: 6px; }\n.aya-source-label { color: #6f7b86; font-size: 9px; font-weight: 650; letter-spacing: .08em; text-transform: uppercase; }\n.aya-source-card {\n  color: inherit; text-decoration: none; border: 1px solid var(--border); background: color-mix(in srgb, var(--surface) 76%, transparent);\n  border-radius: 11px; padding: 8px 9px; display: flex; align-items: center; gap: 8px; transition: border-color .15s ease, background .15s ease, transform .15s ease;\n}\n.aya-source-card:hover { border-color: color-mix(in srgb, var(--accent) 40%, var(--border)); background: color-mix(in srgb, var(--accent) 6%, var(--surface)); transform: translateY(-1px); }\n.aya-source-icon { width: 24px; height: 24px; flex: 0 0 24px; display: grid; place-items: center; border-radius: 8px; color: var(--accent); background: color-mix(in srgb, var(--accent) 9%, transparent); }\n.aya-source-icon svg { width: 14px; height: 14px; }\n.aya-source-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; }\n.aya-source-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #dce3e8; font-size: 10.5px; font-weight: 620; }\n.aya-source-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; color: #6f7b86; font-size: 8.5px; }\n.aya-source-open { color: #65717c; font-size: 12px; }\n''' + css_marker
replace_once(css_marker, css_source, "source card CSS")

path.write_text(text, encoding="utf-8")
print("Source cards added")
