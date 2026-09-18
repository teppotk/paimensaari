"""Minimal HTML -> Markdown converter for the old Kotisivukone markup.

Deliberately stdlib-only. It handles exactly the tag vocabulary the old site
uses (p, br, span, strong, table-as-layout, img, a, object/embed for YouTube)
and treats everything else as a transparent container.
"""

import re
import urllib.parse
from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "noscript"}
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote"}
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:v/|embed/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{6,})")


class Converter(HTMLParser):
    """Convert a fragment of the old site's HTML into Markdown.

    Collects `images` (absolute source URLs with alt text) and `videos`
    (YouTube ids) as a side effect so the caller can archive them.
    """

    def __init__(self, base_url, image_url_map=None):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.image_url_map = image_url_map or {}
        self.images = []
        self.videos = []
        self._bufs = [[]]
        self._skip = 0
        self._link = None
        self._link_buf = None
        self._list_stack = []
        self._table_stack = []
        self._row = None
        self._cell_depth = 0

    # -- buffer plumbing ---------------------------------------------------
    def _emit(self, text):
        self._bufs[-1].append(text)

    def _push(self):
        self._bufs.append([])

    def _pop(self):
        return "".join(self._bufs.pop())

    def _block(self):
        self._emit("\n\n")

    def _abs(self, url):
        return urllib.parse.urljoin(self.base_url, (url or "").strip())

    # -- tags --------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return

        if tag in HEADINGS:
            self._block()
            self._emit("#" * HEADINGS[tag] + " ")
        elif tag in BLOCK_TAGS:
            self._block()
        elif tag == "br":
            self._emit("  \n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a":
            href = self._abs(a.get("href", ""))
            if href and not href.startswith("javascript:"):
                self._link = href
                self._link_buf = len(self._bufs)
                self._push()
        elif tag == "img":
            self._image(a)
        elif tag == "li":
            self._emit("\n" + "  " * max(0, len(self._list_stack) - 1))
            self._emit("1. " if self._list_stack and self._list_stack[-1] == "ol" else "- ")
        elif tag in ("ul", "ol"):
            self._list_stack.append(tag)
        elif tag == "table":
            self._table_stack.append([])
            self._block()
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell_depth += 1
            self._push()
        elif tag in ("object", "embed", "iframe", "param"):
            self._video(a)

    def handle_startendtag(self, tag, attrs):
        if tag in ("br", "img", "param", "embed"):
            self.handle_starttag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return

        if tag in HEADINGS or tag in BLOCK_TAGS:
            if tag in ("ul", "ol") and self._list_stack:
                self._list_stack.pop()
            self._block()
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a" and self._link is not None:
            text = self._pop().strip()
            href = self._link
            self._link = None
            if text.startswith("!["):          # image wrapped in a link
                self._emit(text)
            elif text:
                self._emit("[%s](%s)" % (text, href))
        elif tag in ("td", "th") and self._cell_depth:
            self._cell_depth -= 1
            if self._row is None:
                self._row = []
            self._row.append(self._pop())
        elif tag == "tr":
            self._end_row()
        elif tag == "table":
            self._end_table()

    def _end_row(self):
        if self._row is None:
            return
        row, self._row = self._row, None
        if self._table_stack:
            self._table_stack[-1].append(row)

    def _end_table(self):
        if not self._table_stack:
            return
        rows = self._table_stack.pop()
        if not rows:
            return
        width = max(len(r) for r in rows)
        if width > 1:
            # A real data table: cells are collapsed onto one line each.
            flat = lambda c: re.sub(r"\s+", " ", c).strip().replace("|", "\\|")
            head = rows[0] + [""] * (width - len(rows[0]))
            self._emit("\n\n| " + " | ".join(flat(c) for c in head) + " |\n")
            self._emit("| " + " | ".join(["---"] * width) + " |\n")
            for r in rows[1:]:
                r = r + [""] * (width - len(r))
                self._emit("| " + " | ".join(flat(c) for c in r) + " |\n")
            self._emit("\n")
        else:
            # Layout table: the single cell simply holds the page content,
            # so it is passed through with its paragraph breaks intact.
            for r in rows:
                for cell in r:
                    self._emit("\n\n" + cell + "\n\n")

    # -- media -------------------------------------------------------------
    def _image(self, a):
        raw = (a.get("src") or "").strip()
        if not raw:
            return
        # Some news items are nothing but an inline base64 image, so those are
        # kept too and written out as real files by the caller.
        src = raw if raw.startswith("data:") else self._abs(raw)
        alt = (a.get("alt") or a.get("title") or "").strip()
        self.images.append({"url": src, "alt": alt})
        self._emit("![%s](%s)" % (alt, self.image_url_map.get(src, src)))

    def _video(self, a):
        for key in ("src", "value", "data"):
            m = YOUTUBE_RE.search(a.get(key, "") or "")
            if m:
                vid = m.group(1)
                if vid not in self.videos:
                    self.videos.append(vid)
                    self._emit("\n\n[YouTube-video %s](https://www.youtube.com/watch?v=%s)\n\n" % (vid, vid))
                return

    def handle_data(self, data):
        if self._skip or not data:
            return
        text = re.sub(r"[ \t\r\f\v]+", " ", data.replace("\n", " ").replace("\xa0", " "))
        if text.strip() == "" and not self._bufs[-1]:
            return
        self._emit(text)

    # -- result ------------------------------------------------------------
    def result(self):
        while len(self._bufs) > 1:
            self._pop()
        text = "".join(self._bufs[0])
        # The old editor left a lot of empty <strong></strong> pairs behind.
        text = re.sub(r"\*\*[ \t]*\*\*", " ", text)
        text = re.sub(r"[ \t]+\n", lambda m: "  \n" if m.group(0).startswith("  ") else "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        lines = [ln.rstrip() if not ln.endswith("  ") else ln for ln in text.split("\n")]
        return "\n".join(_balance_bold(ln) for ln in lines).strip() + "\n"


def _balance_bold(line):
    """The old editor emitted unbalanced <strong> tags; close or drop the stray."""
    if line.count("**") % 2 == 0:
        return line
    stripped = line.rstrip()
    if stripped.endswith("**"):
        return stripped[:-2].rstrip()
    if stripped.startswith("**"):
        return stripped + "**"
    return line


def convert(fragment, base_url, image_url_map=None):
    c = Converter(base_url, image_url_map)
    c.feed(fragment)
    c.close()
    return c.result(), c.images, c.videos
