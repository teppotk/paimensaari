# Ohje: uutisen julkaiseminen

Tämä ohje on Paimensaaren asukasyhdistyksen hallitukselle. Uutisen julkaisemiseen
ei tarvita ohjelmointia eikä ohjelmien asentamista — pelkkä selain riittää.

## Kerran alkuun: GitHub-tili

1. Luo maksuton tili osoitteessa <https://github.com/signup>.
2. Kerro käyttäjätunnuksesi puheenjohtajalle, joka lisää sinut sivuston ylläpitäjäksi.
3. Hyväksy sähköpostiisi tuleva kutsu.

Ilman ylläpitäjän oikeuksia lähetetty uutinen ei julkaistu automaattisesti.

## Uutisen julkaiseminen

1. Paina sivuston valikossa **Lisää uutinen** — tai avaa
   **[uutislomake](https://github.com/teppotk/paimensaari/issues/new?template=uutinen.yml)** suoraan.
   GitHub kysyy ensin tunnuksesi, jos et ole kirjautuneena.
2. Kirjoita otsikko ja teksti. Tyhjä rivi aloittaa uuden kappaleen.
3. Päivämäärä muodossa `25.10.2026`. Jos jätät sen tyhjäksi, käytetään kuluvaa päivää.
4. Raahaa valokuvat Kuvat-kenttään. Niitä voi olla useita.
5. Paina vihreää **Create**-painiketta.

Noin minuutin kuluttua lomakkeelle ilmestyy vahvistus ja linkki julkaistuun uutiseen.
Sivujen päivittyminen kestää tämän jälkeen vielä pari minuuttia.

## Uutisen korjaaminen

Avaa sama lomake uudelleen (löytyy
[Issues-listalta](https://github.com/teppotk/paimensaari/issues?q=is%3Aissue)),
paina otsikon vieressä **Edit**, korjaa teksti ja tallenna. Korjaus päivittyy
sivuille itsestään. Sama koskee kuvien lisäämistä tai poistamista.

## Uutisen poistaminen

Poistaminen on toistaiseksi ylläpitäjän tehtävä: uutinen poistetaan
`content/uutiset/`-hakemistosta, minkä jälkeen sivusto päivittyy itsestään.
Pyydä poistoa puheenjohtajalta tai sivuston ylläpitäjältä.

## Mitä konepellin alla tapahtuu

Lomakkeen lähettäminen käynnistää automatiikan, joka

1. tallentaa uutisen tekstin arkistoon `content/uutiset/`-hakemistoon,
2. tallentaa valokuvat alkuperäisessä koossa `assets/photos/uutiset/`-hakemistoon,
3. tekee niistä pienennetyt versiot sivustoa varten ja
4. päivittää sivuston uutistiedoston.

Alkuperäiset valokuvat säilyvät aina täysikokoisina. Sivuilla näytetään
pienennetty versio, jotta sivut latautuvat nopeasti myös mobiiliyhteydellä.

## Uuden julkaisijan lisääminen

Sivuston omistaja lisää henkilön osoitteessa
`https://github.com/teppotk/paimensaari/settings/access` valitsemalla
**Add people** ja oikeudeksi **Write**.
