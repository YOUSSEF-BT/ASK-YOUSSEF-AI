from pathlib import Path

path = Path("web/widget.js")
text = path.read_text(encoding="utf-8")

start = '(function () {\n  "use strict";'
end = '''  close.innerHTML = CLOSE_ICON;\n  send.innerHTML = SEND_ICON;\n})();\n\nvar TEMPLATE = ['''
if start not in text or end not in text:
    raise SystemExit("widget bootstrap guard not found")

text = text.replace(start, 'function askYoussefWidget() {\n  "use strict";', 1)
text = text.replace(
    end,
    '''  close.innerHTML = CLOSE_ICON;\n  send.innerHTML = SEND_ICON;\n}\n\nvar TEMPLATE = [''',
    1,
)
if not text.rstrip().endswith('`;'):
    raise SystemExit("widget CSS end guard not found")
text = text.rstrip() + "\n\n// TEMPLATE and CSS are initialized before mounting the widget.\naskYoussefWidget();\n"
path.write_text(text, encoding="utf-8")
print("Widget bootstrap order fixed")
