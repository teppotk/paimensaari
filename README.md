# paimensaari.fi

Paimensaaren asukasyhdistys ry:n verkkosivujen uudistus. Sivusto julkaistaan GitHub Pagesin
kautta osoitteessa https://www.paimensaari.fi/.

## Vaihe 1: vanhan sivuston arkistointi (valmis)

Vanha Kotisivukone-sivusto on arkistoitu kokonaisuudessaan tähän repositorioon, jotta mikään
teksti tai valokuva ei ole enää riippuvainen vanhasta palvelusta.

| Aineisto | Määrä | Sijainti |
| --- | --- | --- |
| Sivut | 8 | `content/sivut/` |
| Uutiset (2013–2026) | 183 | `content/uutiset/` |
| Kuva-albumit | 11 | `content/galleria/` |
| Valokuvat | 248 (n. 270 Mt) | `assets/photos/` |
| Videot | 3 YouTube-linkkiä | `content/sivut/videoklipit.md` |
| Alkuperäinen HTML | kaikki haetut sivut | `archive/raw/` |

Jokainen `.md`-tiedosto kertoo alkuperässään `source_url`-kentässä, mistä sisältö on peräisin
ja milloin se on haettu. Latausten täydellinen luettelo on `archive/manifest.json`-tiedostossa.

Valokuvat on tallennettu suurimmassa saatavilla olleessa koossa (`_orig`), eli suurempina kuin
vanha galleria niitä näytti.

### Arkiston päivittäminen

```bash
python3 scripts/archive.py all              # hae vanhalta sivustolta uudelleen
python3 scripts/archive.py all --offline    # muunna uudelleen archive/raw/-kopioista
```

Skriptit eivät vaadi asennettavia riippuvuuksia — pelkkä Python 3 riittää.

## Vaihe 2: uusi sivusto

Toteutus on staattista HTML/CSS/JS:ää ilman käännösvaihetta: repositorion tiedostot ovat
sellaisenaan se, mitä GitHub Pages tarjoilee.

```bash
python3 -m http.server 8000     # esikatselu osoitteessa http://localhost:8000
```

Sivut: `index.html`, `uutiset.html`, `rantasauna.html`, `valokaapeli.html`, `kuolimo.html`,
`galleria.html`, `ilmoitukset.html`, `yhteystiedot.html`. Vanhan sivuston kymmenen
valikkokohtaa tiivistyivät kahdeksaan: videoklipit siirtyivät gallerian yhteyteen ja
palautelomake yhteystietoihin, koska GitHub Pages ei voi ajaa lomakkeen vastaanottoa.

Uutiset ja kuvagalleria eivät ole omia HTML-sivujaan, vaan selain hakee ne
`data/uutiset.json`- ja `data/galleria.json`-tiedostoista. Yksittäiseen uutiseen pääsee
osoitteella `uutiset.html#<uutisen-id>`.

Julkaistavat kuvat ovat pienennettyjä versioita (`assets/web/`); alkuperäiset täysikokoiset
kuvat säilyvät `assets/photos/`-hakemistossa säilytyskopioina.

```bash
python3 scripts/build_web.py            # pienennä kuvat ja päivitä JSON
python3 scripts/build_web.py --data     # pelkkä JSON
```
