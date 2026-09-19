#!/usr/bin/env python3
"""Muunna GitHubin uutislomake (issue) uutiseksi arkistoon.

Lukee issuen rungon, tallentaa liitetyt valokuvat assets/photos/uutiset/
-hakemistoon ja kirjoittaa uutisen content/uutiset/-hakemistoon samassa
muodossa kuin vanhalta sivustolta arkistoidut uutiset.

Käyttö:
    python3 scripts/uutinen_issuesta.py --numero 42 --body-file runko.md \
        --url https://github.com/teppotk/paimensaari/issues/42
"""

import argparse
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KUVAT = ROOT / "assets" / "photos" / "uutiset"
UUTISET = ROOT / "content" / "uutiset"
EI_VASTAUSTA = "_No response_"
PAATTEET = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/heic": ".heic", "image/heif": ".heic",
}
KUVA_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)|<img[^>]+src=\"(https?://[^\"]+)\"")


def slugify(text, fallback="uutinen"):
    text = unicodedata.normalize("NFKD", (text or "").strip().lower())
    text = text.replace("ä", "a").replace("ö", "o").replace("å", "a")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60] or fallback


def osiot(body):
    """Lomakkeen kentät: '### Otsikko' ja sitä seuraava teksti."""
    tulos, avain, rivit = {}, None, []
    for rivi in (body or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.*?)\s*$", rivi)
        if m:
            if avain:
                tulos[avain] = "\n".join(rivit).strip()
            avain, rivit = m.group(1).strip().lower(), []
        elif avain:
            rivit.append(rivi)
    if avain:
        tulos[avain] = "\n".join(rivit).strip()
    return {k: ("" if v == EI_VASTAUSTA else v) for k, v in tulos.items()}


def paivays(teksti):
    teksti = (teksti or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", teksti)
    if m:
        return teksti
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", teksti)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return date.today().isoformat()


def lataa_kuva(url, kohde_ilman_paatetta):
    pyynto = urllib.request.Request(url, headers={"User-Agent": "paimensaari-uutisbotti"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "github" in url:
        pyynto.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(pyynto, timeout=60) as r:
        data = r.read()
        tyyppi = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    paate = PAATTEET.get(tyyppi)
    if not paate:
        paate = Path(urllib.parse.urlparse(url).path).suffix.lower()
        paate = paate if paate in PAATTEET.values() else ".jpg"
    kohde = Path(str(kohde_ilman_paatetta) + paate)
    kohde.parent.mkdir(parents=True, exist_ok=True)
    kohde.write_bytes(data)
    print("  kuva: %s (%d kt)" % (kohde.relative_to(ROOT), len(data) // 1024))
    return kohde


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--numero", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--url", default="")
    args = ap.parse_args()

    body = Path(args.body_file).read_text(encoding="utf-8")
    kentat = osiot(body)
    otsikko = (kentat.get("otsikko") or "").strip()
    if not otsikko:
        print("VIRHE: otsikko puuttuu lomakkeelta.", file=sys.stderr)
        return 2

    pvm = paivays(kentat.get("päivämäärä") or kentat.get("paivamaara"))
    teksti = (kentat.get("uutisen teksti") or "").strip()
    uutis_id = "i" + str(args.numero)

    # Kuvat: lomakkeen kuvakentästä ja varmuuden vuoksi koko rungosta.
    lahteet, nahty = [], set()
    for osa in (kentat.get("kuvat", ""), body):
        for m in KUVA_RE.finditer(osa):
            u = m.group(1) or m.group(2)
            if u and u not in nahty:
                nahty.add(u)
                lahteet.append(u)

    for vanha in KUVAT.glob("uutinen-%s-*" % uutis_id):   # muokkaus: vanhat pois
        vanha.unlink()
    polut = []
    for i, u in enumerate(lahteet, 1):
        try:
            polut.append(lataa_kuva(u, KUVAT / ("uutinen-%s-%d" % (uutis_id, i))))
        except Exception as e:
            print("  !! kuvan lataus epäonnistui (%s): %s" % (u, e), file=sys.stderr)

    runko = [teksti] if teksti else []
    for p in polut:
        runko.append("![](../../assets/photos/uutiset/%s)" % p.name)

    for vanha in UUTISET.glob("*.md"):                   # muokkaus: nimi voi vaihtua
        if 'news_id: "%s"' % uutis_id in vanha.read_text(encoding="utf-8"):
            vanha.unlink()

    tiedosto = UUTISET / ("%s-%s.md" % (pvm, slugify(otsikko, uutis_id)))
    etukentat = [
        '---',
        'title: "%s"' % otsikko.replace('"', '\\"'),
        'date: "%s"' % pvm,
        'news_id: "%s"' % uutis_id,
        'source_url: "%s"' % args.url,
        'captured: "%s"' % date.today().isoformat(),
        'videos: []',
    ]
    if polut:
        etukentat.append("images:")
        etukentat += ['  - "assets/photos/uutiset/%s"' % p.name for p in polut]
    else:
        etukentat.append("images: []")
    etukentat.append("---")

    tiedosto.parent.mkdir(parents=True, exist_ok=True)
    tiedosto.write_text("\n".join(etukentat) + "\n\n" + "\n\n".join(runko).strip() + "\n", encoding="utf-8")
    print("uutinen: %s" % tiedosto.relative_to(ROOT))
    print("uutisen_osoite=uutiset.html#%s" % uutis_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
