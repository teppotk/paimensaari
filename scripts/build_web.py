#!/usr/bin/env python3
"""Prepare the published site's derived files from the archive.

1. Downscaled images under assets/web/ — the archived originals run to several
   MB each and must never be served directly.
2. data/uutiset.json and data/galleria.json, which the pages load in the
   browser (the site itself has no build step; this only refreshes data).

Usage:
    python3 scripts/build_web.py            # images + data
    python3 scripts/build_web.py --data     # data only (fast)
"""

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "assets" / "photos"
WEB = ROOT / "assets" / "web"
DATA = ROOT / "data"
SIZES = {"thumb": 560, "large": 1400}
QUALITY = "65"


def web_path(rel):
    """Web derivatives are always JPEG, whatever the original was."""
    return rel.with_suffix(".jpg")


# ------------------------------------------------------------------- images
def _resize_pillow(src, dest, px):
    """Pillow-polku: toimii myös GitHubin Linux-koneissa."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return False
    try:
        import pillow_heif  # puhelinten HEIC-kuvat

        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)          # kunnioita kameran kiertotietoa
        im.thumbnail((px, px))
        im.convert("RGB").save(
            dest, "JPEG", quality=int(QUALITY), optimize=True, progressive=True
        )
    return True


def _resize_sips(src, dest, px):
    """macOS-polku, kun Pillow'ta ei ole asennettu."""
    r = subprocess.run(
        ["sips", "-Z", str(px), "-s", "format", "jpeg",
         "-s", "formatOptions", QUALITY, str(src), "--out", str(dest)],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[:200])
    return True


def resize_all(force=False):
    made = skipped = 0
    for src in sorted(PHOTOS.rglob("*")):
        if not src.is_file() or src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp"):
            continue
        rel = src.relative_to(PHOTOS)
        for kind, px in SIZES.items():
            dest = WEB / kind / web_path(rel)
            # Pelkkä olemassaolo riittää ohitukseen: git ei säilytä aikaleimoja,
            # joten aikavertailu pakottaisi palvelimella kaikkien kuvien
            # uudelleenluonnin. Uudelleenluonti tehdään --force-valitsimella.
            if dest.exists() and not force:
                skipped += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                if not _resize_pillow(src, dest, px):
                    _resize_sips(src, dest, px)
            except Exception as e:
                print("  !! %s: %s" % (rel, e))
                continue
            made += 1
            if made % 50 == 0:
                print("  %d kuvaa valmiina..." % made)
    poistettu = 0
    for kind in SIZES:
        juuri = WEB / kind
        for tiedosto in sorted(juuri.rglob("*.jpg")) if juuri.exists() else []:
            rel = tiedosto.relative_to(juuri)
            # Alkuperäinen voi olla mikä tahansa tuettu muoto, josta tehtiin .jpg
            if not any((PHOTOS / rel).with_suffix(p).exists()
                       for p in (".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp",
                                 ".JPG", ".JPEG", ".PNG")):
                tiedosto.unlink()
                poistettu += 1
    print("Kuvat: %d uutta, %d ennallaan, %d poistettua" % (made, skipped, poistettu))


# --------------------------------------------------------------- markdown
def md_to_html(md, image_base=""):
    """Convert the archive's Markdown subset into HTML for the browser."""
    out, in_table = [], False
    for block in re.split(r"\n\s*\n", md.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("|"):
            rows = [r for r in block.split("\n") if r.strip().startswith("|")]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            cells = [c for c in cells if not all(re.fullmatch(r":?-{3,}:?", x) for x in c)]
            out.append("<table>" + "".join(
                "<tr>" + "".join("<td>%s</td>" % _inline(c, image_base) for c in row) + "</tr>"
                for row in cells
            ) + "</table>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", block, re.S)
        if m:
            level = min(6, len(m.group(1)) + 1)      # h1 on the page is the site heading
            out.append("<h%d>%s</h%d>" % (level, _inline(m.group(2), image_base), level))
            continue
        if block.startswith("- "):
            items = "".join("<li>%s</li>" % _inline(l[2:], image_base) for l in block.split("\n") if l.startswith("- "))
            out.append("<ul>%s</ul>" % items)
            continue
        out.append("<p>%s</p>" % _inline(block, image_base).replace("\n", "<br>"))
    return "\n".join(out)


def _inline(text, image_base):
    imgs = []

    def take_image(m):
        alt, src = m.group(1), m.group(2)
        src = re.sub(r"^(\.\./)+assets/photos/(.*)\.\w+$", lambda x: image_base + x.group(2) + ".jpg", src)
        # Many captions are just the original filename; that is noise in alt text.
        if re.fullmatch(r"[\w.\- ]+\.(jpe?g|png|gif)", alt, re.I) or re.fullmatch(r"[\w\-]{0,4}\d{6,}[\w\-]*", alt):
            alt = ""
        if src.startswith("http"):
            # Not archived — the only such link is one that 404s at the source too.
            return ""
        imgs.append('<img src="%s" alt="%s" loading="lazy">' % (src, html.escape(alt)))
        return ""

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", take_image, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return (text.strip() + "".join(imgs)).strip()


def front_matter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.index("\n---\n", 3)
    fm, body = text[4:end], text[end + 5:]
    data, key = {}, None
    for line in fm.split("\n"):
        if line.startswith("  - "):
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(line[4:].strip().strip('"'))
        elif ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            data[key] = [] if value == "[]" else value.strip('"')
    return data, body


# ------------------------------------------------------------------- data
def build_news():
    items = []
    for md in sorted((ROOT / "content" / "uutiset").glob("*.md")):
        if md.name == "index.md":
            continue
        fm, body = front_matter(md.read_text(encoding="utf-8"))
        body = re.sub(r"^#\s+.*$", "", body, count=1, flags=re.M)          # title
        body = re.sub(r"^\d{2}\.\d{2}\.\d{4}\s*$", "", body, count=1, flags=re.M)
        sisalto = md_to_html(body, "assets/web/large/")
        eka = re.search(r'<img src="assets/web/large/([^"]+)"', sisalto)
        items.append(
            {
                "id": fm.get("news_id", md.stem),
                "date": fm.get("date", ""),
                "title": fm.get("title", ""),
                # Listan pikkukuva: uutisen ensimmäinen kuva pienennettynä.
                "kuva": ("assets/web/thumb/" + eka.group(1)) if eka else "",
                "html": sisalto,
            }
        )
    items.sort(key=lambda i: (i["date"], i["id"]), reverse=True)
    _write(DATA / "uutiset.json", items)
    return items


def build_gallery():
    albums = []
    for md in sorted((ROOT / "content" / "galleria").glob("*.md")):
        if md.name == "index.md":
            continue
        fm, body = front_matter(md.read_text(encoding="utf-8"))
        photos = []
        for alt, path in re.findall(r"!\[([^\]]*)\]\(\.\./\.\./assets/photos/([^)]+)\)", body):
            photos.append({"file": re.sub(r"\.\w+$", ".jpg", path), "caption": alt})
        albums.append(
            {
                "slug": md.stem,
                "title": fm.get("title", md.stem),
                "trail": fm.get("trail", []),
                "photos": photos,
            }
        )
    albums.sort(key=lambda a: -len(a["photos"]))
    _write(DATA / "galleria.json", albums)
    return albums


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("  -> %s (%.0f kt)" % (path.relative_to(ROOT), path.stat().st_size / 1024))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", action="store_true", help="skip image resizing")
    ap.add_argument("--force", action="store_true", help="regenerate every derivative image")
    args = ap.parse_args()
    if not args.data:
        resize_all(force=args.force)
    news = build_news()
    albums = build_gallery()
    print("Data: %d uutista, %d albumia, %d kuvaa" % (len(news), len(albums), sum(len(a["photos"]) for a in albums)))


if __name__ == "__main__":
    main()
