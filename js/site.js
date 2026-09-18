/* Paimensaaren asukasyhdistys — sivuston toiminnallisuus.
   Uutiset ja galleria ladataan selaimessa data/-hakemiston JSONista:
   sivustolla ei ole käännösvaihetta, joten sivuja ei generoida etukäteen. */

(function () {
  "use strict";

  var pvm = function (iso) {
    if (!iso) return "";
    var o = iso.split("-");
    return o[2].replace(/^0/, "") + "." + o[1].replace(/^0/, "") + "." + o[0];
  };

  var haeJSON = function (polku) {
    return fetch(polku, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(polku + ": " + r.status);
      return r.json();
    });
  };

  var virhe = function (elementti, teksti) {
    elementti.innerHTML = "";
    var p = document.createElement("p");
    p.className = "lataus";
    p.textContent = teksti;
    elementti.appendChild(p);
  };

  /* ---------------------------------------------------- etusivun uutiset */
  var tuoreet = document.querySelector("[data-tuoreet]");
  if (tuoreet) {
    var maara = parseInt(tuoreet.getAttribute("data-tuoreet"), 10) || 3;
    haeJSON("data/uutiset.json")
      .then(function (uutiset) {
        tuoreet.innerHTML = "";
        uutiset.slice(0, maara).forEach(function (u) {
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.href = "uutiset.html#" + u.id;
          a.innerHTML =
            '<span class="uutislista__pvm">' + pvm(u.date) + "</span>" +
            '<span class="uutislista__otsikko"></span>' +
            (u.kuva ? '<img class="uutislista__kuva" src="" alt="" loading="lazy" width="120" height="90">' : "");
          a.querySelector(".uutislista__otsikko").textContent = u.title;
          if (u.kuva) a.querySelector(".uutislista__kuva").src = u.kuva;
          li.appendChild(a);
          tuoreet.appendChild(li);
        });
      })
      .catch(function () {
        virhe(tuoreet, "Uutisten lataus ei onnistunut. Päivitä sivu.");
      });
  }

  /* --------------------------------------------------------- uutissivu */
  var lista = document.querySelector("[data-uutislista]");
  var nakyma = document.querySelector("[data-uutisnakyma]");
  var juttu = document.querySelector("[data-uutinen]");
  if (lista && juttu && nakyma) {
    var kaikki = [];

    var naytaLista = function () {
      juttu.hidden = true;
      nakyma.hidden = false;
      document.title = "Uutiset – Paimensaaren asukasyhdistys";
    };

    var naytaJuttu = function (id) {
      var u = kaikki.filter(function (x) { return x.id === id; })[0];
      if (!u) { naytaLista(); return; }
      nakyma.hidden = true;
      juttu.hidden = false;
      juttu.innerHTML = "";

      var paluu = document.createElement("a");
      paluu.className = "paluu";
      paluu.href = "uutiset.html";
      paluu.textContent = "← Kaikki uutiset";
      var h = document.createElement("h1");
      h.textContent = u.title;
      var p = document.createElement("p");
      p.className = "uutinen__pvm";
      p.textContent = pvm(u.date);
      var sisalto = document.createElement("div");
      sisalto.className = "uutinen";
      sisalto.innerHTML = u.html;

      juttu.append(paluu, h, p, sisalto);
      document.title = u.title + " – Paimensaaren asukasyhdistys";
      juttu.focus();
    };

    var reititys = function () {
      var id = location.hash.replace("#", "");
      if (id) naytaJuttu(id); else naytaLista();
      window.scrollTo(0, 0);
    };

    haeJSON("data/uutiset.json")
      .then(function (uutiset) {
        kaikki = uutiset;
        lista.innerHTML = "";
        var vuosi = null;
        uutiset.forEach(function (u) {
          var v = (u.date || "").slice(0, 4) || "Aiemmin";
          if (v !== vuosi) {
            vuosi = v;
            var otsikko = document.createElement("h2");
            otsikko.className = "vuosi";
            otsikko.textContent = v;
            lista.appendChild(otsikko);
          }
          var ul = lista.lastElementChild;
          if (!ul || ul.tagName !== "UL") {
            ul = document.createElement("ul");
            ul.className = "uutislista";
            lista.appendChild(ul);
          }
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.href = "#" + u.id;
          a.innerHTML =
            '<span class="uutislista__pvm">' + pvm(u.date) + "</span>" +
            '<span class="uutislista__otsikko"></span>' +
            (u.kuva ? '<img class="uutislista__kuva" src="" alt="" loading="lazy" width="120" height="90">' : "");
          a.querySelector(".uutislista__otsikko").textContent = u.title;
          if (u.kuva) a.querySelector(".uutislista__kuva").src = u.kuva;
          li.appendChild(a);
          ul.appendChild(li);
        });
        reititys();
      })
      .catch(function () {
        virhe(lista, "Uutisten lataus ei onnistunut. Päivitä sivu.");
      });

    window.addEventListener("hashchange", reititys);
  }

  /* --------------------------------------------------------- galleria */
  var galleria = document.querySelector("[data-galleria]");
  if (galleria) {
    var katselin = document.querySelector("[data-katselin]");
    var katselinKuva = katselin.querySelector("[data-katselin-kuva]");
    var katselinTeksti = katselin.querySelector("[data-katselin-teksti]");
    var nykyinen = { kuvat: [], i: 0 };

    var avaa = function (kuvat, i) {
      nykyinen = { kuvat: kuvat, i: i };
      var k = kuvat[i];
      katselinKuva.src = "assets/web/large/" + k.file;
      katselinKuva.alt = k.caption || "";
      katselinTeksti.textContent =
        (k.caption ? k.caption + " — " : "") + (i + 1) + " / " + kuvat.length;
      if (!katselin.open) katselin.showModal();
    };

    var siirry = function (suunta) {
      if (!nykyinen.kuvat.length) return;
      var i = (nykyinen.i + suunta + nykyinen.kuvat.length) % nykyinen.kuvat.length;
      avaa(nykyinen.kuvat, i);
    };

    katselin.querySelector("[data-edellinen]").addEventListener("click", function () { siirry(-1); });
    katselin.querySelector("[data-seuraava]").addEventListener("click", function () { siirry(1); });
    katselin.querySelector("[data-sulje]").addEventListener("click", function () { katselin.close(); });
    katselin.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") { e.preventDefault(); siirry(-1); }
      if (e.key === "ArrowRight") { e.preventDefault(); siirry(1); }
    });

    haeJSON("data/galleria.json")
      .then(function (albumit) {
        galleria.innerHTML = "";
        albumit.forEach(function (albumi) {
          var osio = document.createElement("section");
          osio.className = "albumi";
          var h = document.createElement("h2");
          h.textContent = albumi.title;
          var maarap = document.createElement("p");
          maarap.className = "albumi__maara";
          maarap.textContent = albumi.photos.length + " kuvaa";
          var ul = document.createElement("ul");
          ul.className = "ruudukko";

          albumi.photos.forEach(function (kuva, i) {
            var li = document.createElement("li");
            var nappi = document.createElement("button");
            nappi.type = "button";
            nappi.setAttribute(
              "aria-label",
              "Avaa kuva" + (kuva.caption ? ": " + kuva.caption : "") + " (" + (i + 1) + "/" + albumi.photos.length + ")"
            );
            var img = document.createElement("img");
            img.src = "assets/web/thumb/" + kuva.file;
            img.alt = kuva.caption || "";
            img.loading = "lazy";
            img.width = 560;
            img.height = 420;
            nappi.appendChild(img);
            nappi.addEventListener("click", function () { avaa(albumi.photos, i); });
            li.appendChild(nappi);
            ul.appendChild(li);
          });

          osio.append(h, maarap, ul);
          galleria.appendChild(osio);
        });
      })
      .catch(function () {
        virhe(galleria, "Kuvien lataus ei onnistunut. Päivitä sivu.");
      });
  }
})();
