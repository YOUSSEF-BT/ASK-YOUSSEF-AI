"""Site crawler — turn a live website into a local corpus for RAG.

Phase 1 indexed hand-written markdown in `data/posts`. This crawls the *whole
site* instead: it reads each domain's sitemap, fetches every page, strips the
HTML down to readable prose, and writes one markdown file per page (with the
page title and canonical URL in the frontmatter). `RAG.build()` then indexes
those files exactly like the local posts — and citations link to the real URL.

Stdlib only (urllib + html.parser + xml) so it runs anywhere, no pip install.

    python src/crawl.py --out data/site \\
        https://youssef-bt.github.io https://youssef-bt.github.io/projects

Design choice: we snapshot to disk (committed) rather than crawl at app boot.
The deployed Space then starts fast and offline, and the index is reproducible;
re-run this script to refresh the snapshot when the site changes.
"""
from __future__ import annotations

import argparse
import os
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

_UA = "chat-with-my-blog crawler (+https://youssef-bt.github.io)"
# elements whose entire subtree is chrome, not content
_DROP_TAGS = {"script", "style", "svg", "noscript", "form", "button", "nav",
              "footer", "aside", "template"}
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_BLOCK = {"p", "div", "section", "article", "ul", "ol", "table", "tr",
          "blockquote", "pre", "figure", "figcaption"}
_VOID = {"br", "hr", "img", "meta", "link", "input", "source", "col", "base"}
# elements whose CSS class marks them as chrome (matched as whole class tokens):
# the site nav, the "All posts" back-link, the date/author byline, comments.
_DROP_CLASSES = {"nav", "mobile-menu", "comments", "post-back", "post-datemeta",
                 "post-nav", "related", "footer"}


def fetch(url: str, timeout: int = 20) -> str:
    """GET a URL as text (follows redirects via urllib's default handler)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def sitemap_urls(base: str) -> list[str]:
    """Collect every page URL for a site from its sitemap.

    Handles a sitemap *index* (points to child sitemaps) and plain sitemaps.
    Falls back to just the base URL if no sitemap is reachable."""
    base = base.rstrip("/")
    to_visit = [f"{base}/sitemap-index.xml", f"{base}/sitemap.xml"]
    seen_maps: set[str] = set()
    pages: list[str] = []
    while to_visit:
        sm = to_visit.pop()
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            xml = fetch(sm)
        except Exception:
            continue
        # strip the default namespace so tag names are simple ("loc", not "{..}loc")
        xml = re.sub(r'\sxmlns="[^"]+"', "", xml, count=1)
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError:
            continue
        if root.tag.endswith("sitemapindex"):
            to_visit += [loc.text.strip() for loc in root.iter("loc") if loc.text]
        else:  # urlset
            pages += [loc.text.strip() for loc in root.iter("loc") if loc.text]
    # de-dup, preserve order; fall back to the base page itself
    pages = list(dict.fromkeys(pages)) or [base]
    return pages


class _Extractor(HTMLParser):
    """Pull the readable prose (and <title>) out of an HTML page.

    Skips whole chrome subtrees (nav, footer, scripts, comment widgets) and
    emits lightweight markdown: headings as `#…`, list items as `- …`, blank
    lines between blocks. Good enough for retrieval — we want the words, not
    pixel-perfect structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0          # >0 while inside a dropped subtree
        self._in_title = False
        self._heading = 0       # current heading level, 0 if not in a heading
        self._stack: list[tuple[str, bool]] = []   # (tag, is_drop) for open elems

    def _dropped(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        if tag in _DROP_TAGS:
            return True
        # match whole class tokens so e.g. "post-header" (content, holds the <h1>)
        # is kept while "nav"/"post-back"/"post-datemeta" (chrome) are dropped.
        classes = set((dict(attrs).get("class") or "").split())
        return bool(_DROP_CLASSES & classes)

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            if tag == "br" and not self._skip:
                self.parts.append("\n")
            return
        drop = self._skip > 0 or self._dropped(tag, attrs)
        self._stack.append((tag, drop))
        if drop:
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
        elif tag in _HEADINGS:
            self._heading = _HEADINGS[tag]
            self.parts.append("\n\n" + "#" * self._heading + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        # unwind to the matching open tag (tolerates minor nesting errors)
        while self._stack:
            open_tag, drop = self._stack.pop()
            if drop:
                self._skip -= 1
            if open_tag == tag:
                break
        if tag == "title":
            self._in_title = False
        elif tag in _HEADINGS:
            self._heading = 0
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip == 0:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]*\n[ \t]*", "\n", raw)   # trim spaces around newlines
        raw = re.sub(r"[ \t]{2,}", " ", raw)          # collapse runs of spaces
        # drop artifact-only lines: empty bullets/headings and skip links
        lines = [ln for ln in raw.split("\n")
                 if ln.strip() not in ("-", "#", "Skip to content")
                 and not re.fullmatch(r"#{1,6}", ln.strip())]
        raw = "\n".join(lines)
        raw = re.sub(r"\n{3,}", "\n\n", raw)          # cap blank lines
        return raw.strip()


@dataclass
class Page:
    url: str
    title: str
    text: str


def extract(url: str, html: str) -> Page:
    p = _Extractor()
    p.feed(html)
    title = " ".join(p.title.split())
    if title:
        # sites append the brand as the LAST segment ("How GPT Works — Part 2 —
        # Youssef Bouzit"): drop only that, keeping the FULL (possibly multi-part)
        # page title rather than truncating at the first dash.
        parts = re.split(r"\s+[—–|]\s+", title)
        title = " — ".join(parts[:-1]).strip() if len(parts) > 1 else title
    else:
        title = url
    return Page(url=url, title=title, text=p.text())


def slug_for(url: str) -> str:
    """A stable, readable filename for a page URL, unique across subdomains."""
    u = urlparse(url)
    host = u.netloc.split(":")[0]
    sub = host.split(".youssef-bt.github.io")[0] if host.endswith(".youssef-bt.github.io") else host
    label = "" if sub in ("youssef-bt.github.io", "") else sub  # main site → no prefix
    path = u.path.strip("/")
    path = re.sub(r"\.html?$", "", path).replace("/", "-")
    stem = path or "home"
    slug = f"{label}-{stem}" if label else stem
    return re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")


def crawl(bases: list[str]) -> list[Page]:
    """Fetch every page across the given sites and extract its prose."""
    urls: list[str] = []
    for base in bases:
        urls += sitemap_urls(base)
    urls = list(dict.fromkeys(urls))          # de-dup across sitemaps
    pages: list[Page] = []
    for url in urls:
        try:
            page = extract(url, fetch(url))
        except Exception as exc:              # skip a bad page, keep going
            print(f"  ! skipped {url}: {exc}")
            continue
        if page.text.strip():
            pages.append(page)
            print(f"  ✓ {url}  ({len(page.text)} chars)")
        else:
            print(f"  ∅ {url}  (no extractable text)")
    return pages


def save_snapshot(pages: list[Page], out_dir: str) -> None:
    """Write one markdown file per page, with title + url frontmatter, so
    RAG.build() indexes them like any other post."""
    os.makedirs(out_dir, exist_ok=True)
    for page in pages:
        slug = slug_for(page.url)
        safe_title = page.title.replace('"', "'")
        body = f'---\ntitle: "{safe_title}"\nurl: {page.url}\n---\n\n{page.text}\n'
        with open(os.path.join(out_dir, f"{slug}.md"), "w", encoding="utf-8") as fh:
            fh.write(body)


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl site(s) into a markdown corpus.")
    ap.add_argument("bases", nargs="+", help="site roots, e.g. https://youssef-bt.github.io")
    ap.add_argument("--out", default="data/site", help="output corpus directory")
    args = ap.parse_args()

    print(f"Crawling {len(args.bases)} site(s)…")
    pages = crawl(args.bases)
    save_snapshot(pages, args.out)
    print(f"\nSaved {len(pages)} pages → {args.out}")


if __name__ == "__main__":
    main()
