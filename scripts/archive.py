#!/usr/bin/env python3
"""Archive the old Kotisivukone site (www.paimensaari.fi) into this repo.

Writes Markdown into content/, original-resolution media into assets/, the
untouched source HTML into archive/raw/ and a download manifest into
archive/manifest.json.

Usage:
    python3 scripts/archive.py all
    python3 scripts/archive.py pages | news | albums

The old site is served as ISO-8859-1; every fetch is decoded accordingly, so
the archive is UTF-8 throughout.
"""

import argparse
import base64
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from html2md import convert  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.paimensaari.fi"
UA = "Mozilla/5.0 (compatible; paimensaari-archiver/1.0; +https://github.com/teppotk/paimensaari)"
DELAY = 0.3
OFFLINE = False
SOURCE_ENCODING = "ISO-8859-1"

# The old site's sections: numeric Kotisivukone paths, not slugs.
PAGES = [
    ("etusivu", "/1", "Etusivu"),
    ("valokaapeli", "/3", "Valokaapeli"),
    ("rantasauna", "/5", "Rantasauna"),
    ("kuolimo", "/6", "Kuolimo"),
    ("ostetaan-myydaan", "/7", "Ostetaan / Myydään"),
    ("videoklipit", "/8", "Videoklipit"),
    ("yhteystiedot", "/4", "Yhteystiedot"),
    ("palaute", "/lomake.html?id=1", "Palaute"),
]
ALBUM_INDEX = "/albumi.html"

MANIFEST = ROOT / "archive" / "manifest.json"
_manifest = []


# --------------------------------------------------------------------------- io
def encode_url(url):
    """urllib refuses non-ASCII URLs; a few old image links contain ä."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc.encode("idna").decode("ascii") if not parts.netloc.isascii() else parts.netloc,
            urllib.parse.quote(parts.path, safe="/%:@"),
            urllib.parse.quote(parts.query, safe="=&%+"),
            parts.fragment,
        )
    )


def fetch_bytes(url):
    req = urllib.request.Request(encode_url(url), headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(DELAY)
            return data
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise
            print("  retry (%s): %s" % (e, url))
            time.sleep(2 * (attempt + 1))


def fetch_text(url):
    return fetch_bytes(url).decode(SOURCE_ENCODING, errors="replace")


def head_ok(url):
    req = urllib.request.Request(encode_url(url), headers={"User-Agent": UA}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def raw_path(name):
    return ROOT / "archive" / "raw" / (name + ".html")


def fetch_page(url, raw_name):
    """Fetch a page and keep the source HTML; reuse it in --offline mode."""
    cached = raw_path(raw_name)
    if OFFLINE and cached.exists():
        return cached.read_text(encoding="utf-8")
    text = fetch_text(url)
    save_raw(raw_name, text)
    return text


def save_data_uri(uri, dest_dir, stem):
    """Write an inline base64 image out as a real file; return its path."""
    m = re.match(r"data:image/([a-zA-Z0-9.+-]+);base64,(.*)", uri, re.S)
    if not m:
        return None
    ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1).lower(), m.group(1).lower())
    data = base64.b64decode(re.sub(r"\s+", "", m.group(2)))
    dest = dest_dir / ("%s.%s" % (stem, ext))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != len(data):
        dest.write_bytes(data)
        print("  saved %s (%d kt, upotettu kuva)" % (dest.relative_to(ROOT), len(data) // 1024))
    _manifest.append(
        {
            "source": "data:-uri",
            "path": str(dest.relative_to(ROOT)),
            "bytes": len(data),
            "fetched": today(),
        }
    )
    return dest


def save_raw(name, text):
    p = ROOT / "archive" / "raw" / (name + ".html")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def download(url, dest):
    """Download url to dest unless already present; record it in the manifest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        size = dest.stat().st_size
    else:
        data = fetch_bytes(url)
        dest.write_bytes(data)
        size = len(data)
        print("  saved %s (%d kt)" % (dest.relative_to(ROOT), size // 1024))
    _manifest.append(
        {
            "source": url,
            "path": str(dest.relative_to(ROOT)),
            "bytes": size,
            "fetched": datetime.now(timezone.utc).date().isoformat(),
        }
    )
    return dest


# ----------------------------------------------------------------------- helpers
THUMB_RE = re.compile(r"/api/thumbnail\?img=([^&]+)")
_taken = {}


def resolve_image(url):
    """The old site served some images through a 150 px thumbnail endpoint;
    its img= parameter names the full-size file, which is what we want."""
    m = THUMB_RE.search(url)
    if m:
        target = urllib.parse.unquote(m.group(1))
        if target.startswith("/"):
            return urllib.parse.urljoin(BASE, target)
    return url


def image_name(url, fallback):
    """A filename that is unique per source URL — several sources used to
    collapse onto the same name and silently overwrite each other."""
    name = Path(urllib.parse.urlparse(url).path).name
    if not name or "." not in name:
        name = "%s.jpg" % slugify(name or fallback, fallback)
    if _taken.get(name, url) != url:
        stem, _, ext = name.rpartition(".")
        name = "%s-%s.%s" % (stem, abs(hash(url)) % 10000, ext)
    _taken[name] = url
    return name


def slugify(text, fallback="kuva"):
    text = unicodedata.normalize("NFKD", (text or "").strip().lower())
    text = text.replace("ä", "a").replace("ö", "o").replace("å", "a")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60] or fallback


def extract_content(html):
    """Return the page's own content region, without Kotisivukone chrome."""
    start = html.find("<!--Content-->")
    if start == -1:
        start = html.find('<div id="content">')
    if start == -1:
        start = 0
    end = html.find('<div id="content_bottom"', start)
    if end == -1:
        end = html.find('<div id="footer"', start)
    if end == -1:
        end = len(html)
    return html[start:end]


def page_title(html, default=""):
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else default


def yaml_value(v):
    if isinstance(v, list):
        return "\n" + "".join("  - %s\n" % yaml_value(x) for x in v).rstrip("\n") if v else " []"
    s = str(v).replace('"', '\\"')
    return '"%s"' % s


def write_markdown(path, front, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = ["---"]
    for k, v in front.items():
        if isinstance(v, list):
            if not v:
                out.append("%s: []" % k)
            else:
                out.append("%s:" % k)
                out.extend('  - "%s"' % str(x).replace('"', '\\"') for x in v)
        else:
            out.append('%s: "%s"' % (k, str(v).replace('"', '\\"')))
    out.append("---")
    out.append("")
    path.write_text("\n".join(out) + "\n" + body.lstrip("\n"), encoding="utf-8")
    print("  -> %s" % path.relative_to(ROOT))


def today():
    return datetime.now(timezone.utc).date().isoformat()


# ------------------------------------------------------------------------- pages
def archive_pages():
    print("== Sivut ==")
    for slug, path, title in PAGES:
        url = BASE + path
        print("%s  (%s)" % (title, url))
        html = fetch_page(url, "sivu-" + slug)
        fragment = extract_content(html)

        # Pre-scan images so the Markdown can point at the archived copies.
        pre_md, images, _ = convert(fragment, url)
        url_map = {}
        for n, img in enumerate(images, 1):
            if img["url"].startswith("data:"):
                dest = save_data_uri(img["url"], ROOT / "assets" / "photos" / "uutiset", "uutinen-%s-%d" % (news_id, n))
                if dest:
                    url_map[img["url"]] = "../../assets/photos/uutiset/" + dest.name
                continue
            source = resolve_image(img["url"])
            host = urllib.parse.urlparse(source).netloc
            if "kotisivukone" not in host and "paimensaari" not in host:
                continue
            name = image_name(source, "%s-%d" % (slug, n))
            dest = ROOT / "assets" / "photos" / "sivut" / name
            try:
                download(source, dest)
            except Exception as e:
                print("  !! kuva epaonnistui %s (%s)" % (img["url"], e))
                continue
            url_map[img["url"]] = "../../assets/photos/sivut/" + name

        body, images, videos = convert(fragment, url, url_map)
        write_markdown(
            ROOT / "content" / "sivut" / (slug + ".md"),
            {
                "title": title,
                "slug": slug,
                "source_url": url,
                "source_title": page_title(html),
                "captured": today(),
                "videos": ["https://www.youtube.com/watch?v=" + v for v in videos],
                "images": [url_map.get(i["url"], i["url"]) if i["url"].startswith("data:") else i["url"] for i in images],
            },
            body,
        )


# -------------------------------------------------------------------------- news
NEWS_ARCHIVE = "/uutiset.html?a100"
NEWS_ID_RE = re.compile(r'href="\?a\d+=(\d+)"')
NEWS_PAGE_RE = re.compile(r'href="\?(a\d+)"')
NEWS_ITEM_RE = re.compile(r'<div class="news_item"[^>]*>(.*?)<div class="clear">', re.S)
NEWS_DATE_RE = re.compile(r'<div class="small">\s*(\d{1,2})\.(\d{1,2})\.(\d{4})')


def collect_news_ids():
    """Walk the paginated news archive; the RSS feed only carries the last 10."""
    ids, seen_pages, page = [], set(), "a100"
    while page and page not in seen_pages:
        seen_pages.add(page)
        url = "%s/uutiset.html?%s" % (BASE, page)
        html = fetch_page(url, "uutisarkisto-" + page)
        found = NEWS_ID_RE.findall(html)
        ids.extend(i for i in found if i not in ids)
        print("  %s: %d uutista (yhteensa %d)" % (page, len(found), len(ids)))
        nxt = [p for p in NEWS_PAGE_RE.findall(html) if p not in seen_pages]
        page = nxt[0] if nxt else None
    return ids


def archive_news():
    print("== Uutiset ==")
    ids = collect_news_ids()
    print("  arkistoidaan %d uutista" % len(ids))
    index = []
    for news_id in ids:
        url = "%s/uutiset.html?%s" % (BASE, news_id)
        html = fetch_page(url, "uutinen-" + news_id)

        m = NEWS_ITEM_RE.search(html)
        fragment = m.group(1) if m else extract_content(html)
        dm = NEWS_DATE_RE.search(html)
        date = "%s-%02d-%02d" % (dm.group(3), int(dm.group(2)), int(dm.group(1))) if dm else ""
        tm = re.search(r"<h1>(.*?)(?:<!---->)?</h1>", fragment, re.S)
        import html as _h
        title = _h.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip() if tm else "Uutinen %s" % news_id

        pre_md, images, _ = convert(fragment, url)
        url_map = {}
        for n, img in enumerate(images, 1):
            if img["url"].startswith("data:"):
                dest = save_data_uri(img["url"], ROOT / "assets" / "photos" / "uutiset", "uutinen-%s-%d" % (news_id, n))
                if dest:
                    url_map[img["url"]] = "../../assets/photos/uutiset/" + dest.name
                continue
            source = resolve_image(img["url"])
            host = urllib.parse.urlparse(source).netloc
            if "kotisivukone" not in host and "paimensaari" not in host:
                continue
            name = image_name(source, "uutinen-%s-%d" % (news_id, n))
            dest = ROOT / "assets" / "photos" / "uutiset" / name
            try:
                download(source, dest)
            except Exception as e:
                print("  !! kuva epaonnistui %s (%s)" % (img["url"], e))
                continue
            url_map[img["url"]] = "../../assets/photos/uutiset/" + name

        body, images, videos = convert(fragment, url, url_map)
        slug = "%s-%s" % (date or news_id, slugify(title, news_id))
        print("%s  %s" % (date or news_id, title))
        write_markdown(
            ROOT / "content" / "uutiset" / (slug + ".md"),
            {
                "title": title,
                "date": date,
                "news_id": news_id,
                "source_url": url,
                "captured": today(),
                "videos": ["https://www.youtube.com/watch?v=" + v for v in videos],
                "images": [url_map.get(i["url"], i["url"]) if i["url"].startswith("data:") else i["url"] for i in images],
            },
            body,
        )
        index.append((date, title, slug, news_id))

    _write_news_index(index)
    return index


def _write_news_index(index):
    lines = ["Vanhan sivuston uutisarkisto, uusin ensin.", ""]
    for date, title, slug, news_id in sorted(index, key=lambda x: (x[0] or ""), reverse=True):
        lines.append("- %s — [%s](%s.md) (`%s`)" % (date or "?", title, slug, news_id))
    write_markdown(
        ROOT / "content" / "uutiset" / "index.md",
        {
            "title": "Uutiset",
            "source_url": BASE + "/uutiset.html",
            "news_count": len(index),
            "captured": today(),
        },
        "\n".join(lines) + "\n",
    )


# ------------------------------------------------------------------------ albums
# Every photo has a thumbnail, but the lightbox anchor next to it points at
# _large for most and _orig for a few — so the thumbnails drive the crawl and
# the archived variant is resolved per image, largest first.
ALBUM_THUMB_RE = re.compile(
    r'<img src="(https://[^"]+/\.album/([^"/]+)_small\.jpg)"[^>]*alt="([^"]*)"'
)
ALBUM_VARIANTS = ("_orig.jpg", "_large.jpg", "_small.jpg")
ALBUM_FOLDER_RE = re.compile(r'<a class="name" href="(/albumi/[^"]+)">(.*?)</a>', re.S)
ALBUM_PAGE_RE = re.compile(r'<a href="\?p=(\d+)"')


def archive_albums():
    print("== Kuvagalleria ==")
    seen = set()
    albums = []
    _crawl_album(ALBUM_INDEX, [], seen, albums)
    total = sum(len(a["images"]) for a in albums)
    print("  yhteensa %d albumia, %d kuvaa" % (len(albums), total))
    _write_gallery_index(albums)
    return albums


def _crawl_album(path, trail, seen, albums):
    if path in seen:
        return
    seen.add(path)
    url = BASE + path
    raw_name = "albumi-" + (slugify(path.strip("/").replace("/", "-")) or "index")
    html = fetch_page(url, raw_name)

    # Albums are paginated (?p=N) at 16 thumbnails per page.
    pages = sorted({int(n) for n in ALBUM_PAGE_RE.findall(html)})
    extra = []
    for n in pages:
        if n == 1:
            continue
        page_html = fetch_page("%s?p=%d" % (url, n), "%s-p%d" % (raw_name, n))
        extra.append(page_html[page_html.find('<div id="album_content">'):])

    m = re.search(r'<div id="album_content">.*?<h1>(.*?)(?:<!---->)?</h1>', html, re.S)
    import html as _h

    title = _h.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else "Kuva-albumi"
    here = trail + [title] if path != ALBUM_INDEX else []
    print("%s  (%s)" % (" / ".join(here) or title, url))

    body = html[html.find('<div id="album_content">'):] + "".join(extra)
    thumbs = {}
    for thumb_url, stem, alt in ALBUM_THUMB_RE.findall(body):
        thumbs.setdefault(stem, (thumb_url[: -len("_small.jpg")], alt))

    rel_dir = path.strip("/").replace("albumi.html", "").strip("/")
    rel_dir = rel_dir[len("albumi/"):] if rel_dir.startswith("albumi/") else rel_dir
    images = []
    for stem, (prefix, raw_alt) in thumbs.items():
        alt = _h.unescape(raw_alt).strip()
        name = "%s-%s.jpg" % (slugify(alt, stem), stem)
        source = next((prefix + v for v in ALBUM_VARIANTS if head_ok(prefix + v)), prefix + "_large.jpg")
        dest = ROOT / "assets" / "photos" / (rel_dir or "muut") / name
        try:
            download(source, dest)
        except Exception as e:
            print("  !! kuva epaonnistui %s (%s)" % (source, e))
            continue
        images.append(
            {
                "file": str(dest.relative_to(ROOT)),
                "caption": alt,
                "source": source,
                "stem": stem,
            }
        )

    if path != ALBUM_INDEX:
        albums.append({"title": title, "path": path, "trail": here, "images": images, "dir": rel_dir})
        _write_album_md(title, path, here, images, rel_dir)

    for sub_path, sub_title in ALBUM_FOLDER_RE.findall(body):
        _crawl_album(sub_path, here, seen, albums)


def _write_album_md(title, path, trail, images, rel_dir):
    lines = []
    for img in sorted(images, key=lambda i: i["stem"]):
        lines.append("![%s](../../%s)" % (img["caption"], img["file"]))
        lines.append("")
        if img["caption"]:
            lines.append("*%s*" % img["caption"])
            lines.append("")
    slug = slugify(rel_dir.replace("/", "-")) or slugify(title)
    write_markdown(
        ROOT / "content" / "galleria" / (slug + ".md"),
        {
            "title": title,
            "album_path": path,
            "source_url": BASE + path,
            "trail": trail,
            "photo_count": len(images),
            "captured": today(),
        },
        "\n".join(lines),
    )


def _write_gallery_index(albums):
    lines = ["Vanhan sivuston kuva-albumit, arkistoitu alkuperaisessa resoluutiossa.", ""]
    for a in sorted(albums, key=lambda x: " / ".join(x["trail"])):
        slug = slugify(a["dir"].replace("/", "-")) or slugify(a["title"])
        lines.append("- [%s](%s.md) — %d kuvaa (`%s`)" % (" / ".join(a["trail"]), slug, len(a["images"]), a["path"]))
    write_markdown(
        ROOT / "content" / "galleria" / "index.md",
        {
            "title": "Kuvagalleria",
            "source_url": BASE + ALBUM_INDEX,
            "album_count": len(albums),
            "photo_count": sum(len(a["images"]) for a in albums),
            "captured": today(),
        },
        "\n".join(lines) + "\n",
    )


# -------------------------------------------------------------------------- main
def save_manifest():
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if MANIFEST.exists():
        existing = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", [])
    by_path = {f["path"]: f for f in existing}
    for f in _manifest:
        by_path[f["path"]] = f
    files = sorted(by_path.values(), key=lambda f: f["path"])
    MANIFEST.write_text(
        json.dumps(
            {
                "source": BASE,
                "updated": today(),
                "file_count": len(files),
                "total_bytes": sum(f["bytes"] for f in files),
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Manifest: %d tiedostoa, %.1f Mt" % (len(files), sum(f["bytes"] for f in files) / 1e6))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=["all", "pages", "news", "albums"])
    ap.add_argument(
        "--offline",
        action="store_true",
        help="rebuild the Markdown from archive/raw/ without re-fetching the old site",
    )
    args = ap.parse_args()
    global OFFLINE
    OFFLINE = args.offline
    if args.what in ("all", "pages"):
        archive_pages()
    if args.what in ("all", "news"):
        archive_news()
    if args.what in ("all", "albums"):
        archive_albums()
    save_manifest()


if __name__ == "__main__":
    main()
