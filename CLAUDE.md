# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Modernization of **https://www.paimensaari.fi/** — the site of the Paimensaari residents'
association (Savitaipale, Finland). Code lives at https://github.com/teppotk/paimensaari and
the result is published from this repo via **GitHub Pages** at the same public address.

Two constraints override everything else:

1. **Nothing from the old site may be lost.** All text, news items, photos and video clips are
   archived into this repo before/while the new site is built. Preservation beats redesign.
2. **Navigation, layout and visual design may be reworked freely.** The old information
   architecture is a starting point, not a specification.

All user-facing content is in **Finnish**. Never translate archived content; keep Finnish
spelling, including ä/ö, intact.

## Stack

Plain static **HTML + CSS + vanilla JS**. Deliberately **no build step, no framework, no
npm dependencies** — the files in the repo are exactly what GitHub Pages serves. Do not
introduce a bundler, a static site generator or a `package.json` without asking first.

The 8 section pages are hand-written HTML. The 183 news items and 157 gallery photos are not
pages at all: `js/site.js` fetches `data/uutiset.json` and `data/galleria.json` and renders them
in the browser. A news item's address is a fragment, `uutiset.html#<news_id>`, which
`js/site.js` routes on load and on `hashchange`.

Consequences to work around, not to "fix":

- There are no template partials. Header/nav/footer markup is **duplicated in every HTML
  page**. When changing shared markup, change it in *all* pages (`grep -l '<nav' *.html`) —
  a change applied to one page only is a bug. Exactly one nav link per page carries
  `aria-current="page"`. The nav's last item (`.navi__toiminto`, "Lisää uutinen") is not a page
  but a link to the GitHub news form, and it stays visible to everyone — GitHub's own login and
  the workflow's membership check are what gate publishing, not hiding the link.
- **Every path is relative, never root-relative.** The site has to work both at
  `teppotk.github.io/paimensaari/` and at the domain root; a leading `/` breaks the first.
- News and gallery content is invisible to search engines and to a reader with JavaScript off.
  That was a deliberate trade for not generating 183 pages — don't "fix" it by adding a
  generator without asking.
- Shared styling and behaviour belong in the single shared `css/` and `js/` files, not inline.
- `data/*.json` and `assets/web/` are generated from `content/` and `assets/photos/` by
  `scripts/build_web.py`. Edit the archive, then re-run it — never hand-edit the generated
  files.

## Commands

The association publishes news through a GitHub issue form, not by editing files. Only
`OWNER`/`MEMBER`/`COLLABORATOR` submissions publish — the repo is public, so that check is
what keeps strangers from posting to the site. Don't loosen it without asking.

The same form handles the whole lifecycle: editing the issue republishes (the old Markdown file
is deleted first, so a renamed headline leaves no duplicate), and ticking "Poista tämä uutinen
sivustolta" deletes the item and its photos. News published this way has `news_id: "i<issue>"`,
which keeps it from colliding with the archived numeric ids.

Two workflows commit to `main`, so **every push from CI must survive a race**: both pull-rebase
and retry up to five times. A lost race used to fail the job silently, and the news simply did
not update. On failure the workflow now comments on the issue and reopens it.

```bash
# Local preview (no build); open http://localhost:8000
python3 -m http.server 8000

# Deploy: GitHub Pages serves the default branch directly
git push origin main

# Re-archive the old site (network); `all` = pages + news + albums
python3 scripts/archive.py all
python3 scripts/archive.py news

# Rebuild the Markdown from archive/raw/ without touching the old site.
# Use this whenever the converter changes — a full re-fetch is ~250 requests.
python3 scripts/archive.py all --offline

# Rebuild the published site's data and downscaled images from the archive
python3 scripts/build_web.py            # images + JSON, minutes
python3 scripts/build_web.py --data     # JSON only, seconds
```

Screenshots for review: headless Chrome works, but **macOS Chrome clamps the window to about
500 px wide**, so a `--window-size=390` screenshot is a crop of a 500 px layout, not a phone
view. To check narrow layouts, load the page in a 360 px `<iframe>` inside a wider window.

There are no tests and no linter. Verification is manual: preview locally, check every page
listed in the nav, and check narrow (≈375px) and wide viewports.

## Repository layout

- `content/` — the archive of the old site as Markdown with YAML front matter (`source_url`,
  `captured`, `images`, …). This is the source of truth for wording.
  - `content/sivut/` — the 8 section pages.
  - `content/uutiset/` — 183 news items, 2013-2026, named `<date>-<slug>.md`, plus `index.md`.
  - `content/galleria/` — 11 albums, 157 photos, plus `index.md`.
- `assets/photos/` — the photos themselves (~270 MB), mirroring the album structure, plus
  `sivut/` and `uutiset/`. Filenames are `<caption-slug>-<original-stem>.jpg`.
- `archive/raw/` — the source HTML of every page fetched, converted to UTF-8. `--offline`
  rebuilds from these, and they are the evidence that the archive is complete.
- `archive/manifest.json` — every downloaded file with its source URL, size and fetch date.
- `assets/web/thumb/`, `assets/web/large/` — what the pages actually serve: 560 px and 1400 px
  JPEGs, generated from the originals. Always JPEG, whatever the original format was.
  Resizing uses Pillow when it is installed (CI) and falls back to macOS `sips` (this machine),
  so output differs slightly between the two — regenerate a whole directory, not single files,
  if that ever matters.
- `assets/liitteet/` — PDFs that used to live on the old host.
- `data/uutiset.json`, `data/galleria.json` — what the browser loads.
- `scripts/archive.py` — the archiver (subcommands `pages`, `news`, `albums`, `all`).
- `scripts/build_web.py` — derives `assets/web/` and `data/` from the archive.
- `scripts/uutinen_issuesta.py` — turns a submitted news form (a GitHub issue) into an
  archive entry plus downloaded photos.
- `.github/workflows/` — `julkaise-uutinen.yml` publishes from the news form;
  `paivita-sivusto.yml` rebuilds `data/` and `assets/web/` after any edit to the archive.
  Both commit to `main`; they share a `concurrency` group so they cannot race.
- `OHJE.md` — the association's own instructions, in Finnish. Keep it non-technical.
- `scripts/html2md.py` — stdlib HTML→Markdown converter written for this site's tag
  vocabulary. Change it and re-run with `--offline` rather than hand-editing `content/`.
- `index.html` plus one file per section at the repo root — what Pages actually serves.
- `CNAME` — required for the custom domain; deleting it silently breaks the public address.
- `.nojekyll` — required so Pages serves files and directories starting with `_` untouched.

## The original site (for scraping and content checks)

Built on **Kotisivukone**. Facts that repeatedly matter:

- Pages are served as **ISO-8859-1**, not UTF-8. Decode accordingly before parsing, or every
  ä and ö turns into mojibake.
- Sections are numeric paths, not slugs:
  `/1` Etusivu · `/3` Valokaapeli · `/4` Yhteystiedot · `/5` Rantasauna · `/6` Kuolimo ·
  `/7` Ostetaan / Myydään · `/8` Videoklipit · `/albumi.html` Valokuvagalleria ·
  `/uutiset.html` Uutiset (individual items at `/uutiset.html?<id>`) ·
  `/lomake.html?id=1` Palaute.
- **Everything is paginated, and the pagination is easy to miss.** Each trap below silently
  costs content, and each was hit during the first archive run:
  - The news RSS feed carries only the 10 newest items. The real archive is
    `/uutiset.html?a100`, paged onward via `?a200`, `?a300`… — 183 items in total.
  - Album pages show 16 thumbnails, the rest hide behind `?p=2`, `?p=3`…
  - Photo variants are `_small`, `_large` and `_orig` (largest, and the one to archive).
    Most lightbox anchors point at `_large`, a few at `_orig`, so the crawl is driven by the
    `_small` thumbnails — those always exist — and resolves the largest variant per image.
  - Some news items are nothing but an inline base64 `data:` image; skipping data URIs makes
    those items look empty. 22 photos are only preserved this way.
  - Three news items genuinely have a title and no body. That is faithful, not a bug.
- The old markup carries Kotisivukone chrome (Osano cookie banner, prototype.js, jQuery UI,
  inline `positionLogo` scripts). None of it is carried over. On a news page the item itself is
  `div.news_item`; the "other news" table after it is chrome and must not be archived as body.
- `/lomake.html?id=1` is a server-side feedback form. GitHub Pages is static and cannot host
  one; the replacement has to be an external form service or a plain mailto/contact block —
  flag the choice rather than silently dropping the feature.

## Conventions

- Finnish page filenames and URLs, lowercase, no ä/ö in paths (`valokaapeli.html`,
  `ostetaan-myydaan.html`).
- Photos keep their original filename stem so an archived image can always be traced back to
  the source URL recorded in `archive/manifest.json`.
- Every image needs a Finnish `alt`; galleries need `loading="lazy"` and explicit
  `width`/`height` to avoid layout shift.
- **Never serve the archived originals directly.** They run to several MB each (~270 MB in
  total). The published pages need downscaled derivatives; the originals stay in the repo as
  the preservation copy.
