# -*- coding: utf-8 -*-
"""Line types of wires: new types (dotted, dash-double-dot), translated names,
the line type survives when an automatic wire piece is rebuilt, and it is
applied to the whole wire."""
import sys, os, glob
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I
I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
import katiecad.electrical.logic as L
from katiecad.electrical import drahtnummern as DN
from katiecad.fileio.cad_import import _linientyp_name
import katiecad.ui.app as A
from katiecad.model.blocks import block_laden
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


# ---- line types and names
check({"Punktlinie", "Strich-Zweipunktlinie"} <= set(core.LINIENTYPEN), "neue Linientypen")
check(all(core.LINIENTYPEN[k]["dash"] for k in ("Punktlinie", "Strich-Zweipunktlinie")),
      "neue Typen gestrichelt")
check(core.linientyp_text("Volllinie (schmal)") == "Continua (fina)", "spanischer Name")
check(core.linientyp_schluessel("Raya-dos puntos") == "Strich-Zweipunktlinie", "Name -> Schlüssel")
check(core.linientyp_schluessel("Punktlinie") == "Punktlinie", "Schlüssel bleibt Schlüssel")
check(core.linientyp_text("Eigene") == "Eigene" and core.linientyp_schluessel("Eigene") == "Eigene",
      "unbekannte Typen unverändert")
check(len(set(core.linientypen_texte())) == len(core.LINIENTYPEN), "Namen eindeutig")
I.SPRACHE["aktuell"] = "de"
check(core.linientyp_text("Strichlinie (verdeckt)") == "Strichlinie (verdeckt)", "deutsch = Schlüssel")
I.SPRACHE["aktuell"] = "es"
check(_linientyp_name("PHANTOM") == "Strich-Zweipunktlinie" and _linientyp_name("DOT") == "Punktlinie"
      and _linientyp_name("CENTER") == "Strichpunktlinie (Achse)", "DXF-Linientypen")

# ---- the line type survives when a device is moved and the piece is rebuilt
app = A.CadApp.__new__(A.CadApp)
wurzel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols")
LS = block_laden(glob.glob(os.path.join(wurzel, "03 Protection", "Circuit breaker 3-pole.katieblock"))[0],
                 app._dict_zu_element)
f1 = core.BlockReferenz(0, 0, LS.name, LS.elemente)
f2 = core.BlockReferenz(0, -40, LS.name, LS.elemente)
el = [f1, f2]
L.leitungen_automatisch(el)
draehte = [e for e in el if isinstance(e, core.Leitung)]
check(len(draehte) == 3, f"drei Leitungen: {len(draehte)}")
w = min(draehte, key=lambda l: l.x1)
w.linientyp = "Strichpunktlinie (Achse)"
f2.verschieben(0, -20)
L.leitungen_automatisch(el)
neu = [e for e in el if isinstance(e, core.Leitung)]
links = [l for l in neu if abs(l.x1 - w.x1) < 1e-6]
check(len(neu) == 3 and links and links[0].linientyp == "Strichpunktlinie (Achse)"
      and abs(min(links[0].y1, links[0].y2) + 60) < 1e-6,
      f"Linientyp bleibt nach dem Verschieben: {[(l.x1, l.linientyp) for l in neu]}")
check(sum(l.linientyp == "Volllinie (schmal)" for l in neu) == 2, "andere Leitungen unverändert")
check(L.leitung_stil(core.Leitung(0, 0, 1, 0)) == {}, "neue Leitung ohne eigenen Stil")

# ---- whole wire: pieces joined by a corner, up to the terminal
VP = core.Verbindungspunkt
k1 = core.BlockReferenz(0, 0, "S", [VP(0, -5, wert="2", tag="P2"), core.ElektroMaske(8, 0)])
kl = core.Klemme(20, -30, {"IND": "-X1", "NUM": "1"})
a, b = core.Leitung(0, -5, 0, -29), core.Leitung(0, -29, *kl.anschluss_oben())
c = core.Leitung(*kl.anschluss_unten(), 20, -60)
blatt = [k1, kl, a, b, c]
alle = DN.gleicher_draht(blatt, [a])
check({id(x) for x in alle} == {id(a), id(b)}, "ganzer Draht bis zur Klemme")
check(DN.gleicher_draht(blatt, []) == [], "ohne Auswahl leer")

# ---- toolbar: applies to the whole wire, the wire keeps its width "by layer"
meld = []
fake = SimpleNamespace(auswahl=[a], elemente=blatt, _snapshot=lambda: None, redraw=lambda: None,
                       _ist_layout=lambda: False, _staerke_neu=lambda: None,
                       linientyp=SimpleNamespace(get=lambda: "Punktlinie"),
                       status=SimpleNamespace(set=meld.append))
fake._mit_ganzem_draht = lambda z: A.CadApp._mit_ganzem_draht(fake, z)
A.CadApp._stil_auf_auswahl(fake)
check(a.linientyp == b.linientyp == "Punktlinie" and c.linientyp == "Volllinie (schmal)",
      "Werkzeugleiste: ganzer Draht")
check(a.staerke == core.LEITUNG_STAERKE, "Leitungsstärke bleibt bei 'von Layer'")
check(meld and "De puntos" in meld[-1], f"Meldung mit übersetztem Namen: {meld}")

print(f"test_linientyp - OK ({ok} Pruefungen)")
