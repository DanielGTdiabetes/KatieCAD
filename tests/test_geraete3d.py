# -*- coding: utf-8 -*-
"""3D models of the schematic devices: own model (attribute MODELL3D) before the model of
the article (parts catalogue, same TYP), device list with model and 'placed', setting
per device / per article, and the parts catalogue dialog keeping the model field."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.model import geraete3d as G3
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


VP = core.Verbindungspunkt


def geraet(x, y, ind, typ="", rolle="haupt"):
    m = core.ElektroMaske(8, 0)
    m.rolle = rolle
    sym = [core.Rechteck(-3, -5, 3, 5), VP(0, 5, wert="1", tag="P1"), VP(0, -5, wert="2", tag="P2"), m]
    b = core.BlockReferenz(x, y, "Sym", sym)
    b.attribute.update({"IND": ind, "TYP": typ})
    return b


katalog = [{"typ": "lc1d09", "hersteller": "Schneider", "bestellnr": "", "beschreibung": "",
            "modell3d": "3D/lc1d09_pZ.katie3d"}]

# ---- own model wins over the article, placeholder TYP = no article
k1 = geraet(0, 0, "-K1", "LC1D09")
check(G3.modell_von(k1, katalog) == ("3D/lc1d09_pZ.katie3d", "artikel"), "Modell des Artikels")
k1.attribute["MODELL3D"] = "3D/eigen.katie3d"
check(G3.modell_von(k1, katalog) == ("3D/eigen.katie3d", "geraet"), "eigenes Modell gewinnt")
check(G3.modell_von(geraet(0, 0, "-K9", "TYP"), katalog) == ("", ""), "Platzhalter TYP")

# ---- device list over two sheets
k10 = geraet(0, 0, "-K10", "LC1D09")
k2 = geraet(20, 0, "-K2", "X")
hilf = geraet(40, 0, "-K2", "X", rolle="hilfs")
hilf.attribute["MODELL3D"] = "3D/k2.katie3d"
ohne = geraet(60, 0, "", "LC1D09")
platz = geraet(80, 0, "IND", "LC1D09")
netz = {"p": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "k": [[0, 1]], "f": [[0, 1, 2]]}
gesetzt = [core.Koerper3D("netz", netzdaten=netz, geraet="-K1"),
           core.Gruppe3D(teile=[core.Koerper3D("netz", netzdaten=netz, geraet="-K2")])]
zeilen = G3.geraete_mit_modell([(0, [k10, k2, ohne, platz]), (1, [k1, hilf])], katalog, gesetzt)
check([z["ind"] for z in zeilen] == ["-K1", "-K2", "-K10"], f"natürlich sortiert: {[z['ind'] for z in zeilen]}")
z = {r["ind"]: r for r in zeilen}
check(z["-K10"]["modell"] == "3D/lc1d09_pZ.katie3d" and z["-K10"]["quelle"] == "artikel"
      and not z["-K10"]["platziert"], "Artikelmodell, nicht platziert")
check(z["-K2"]["modell"] == "3D/k2.katie3d" and z["-K2"]["platziert"], "Modell vom Hilfsteil, im 3D-Block platziert")
check(z["-K1"]["quelle"] == "geraet" and z["-K1"]["platziert"], "eigenes Modell, platziert")
check(G3.platziert(gesetzt) == {"-K1", "-K2"}, "platzierte Geräte")

# ---- set per device / per article
n = G3.geraet_setzen([k10, core.Linie(0, 0, 1, 1)], "3D/neu.katie3d")
check(n == 1 and k10.attribute["MODELL3D"] == "3D/neu.katie3d", "pro Gerät gesetzt")
check(G3.geraet_setzen([k10], "") == 1 and "MODELL3D" not in k10.attribute, "entfernt")
kat = [dict(e) for e in katalog]
G3.artikel_setzen(kat, "LC1D09", "3D/b.katie3d")
G3.artikel_setzen(kat, "GV2ME10", "3D/gv2.katie3d", "Schneider")
check(len(kat) == 2 and kat[0]["modell3d"] == "3D/b.katie3d" and kat[1]["hersteller"] == "Schneider"
      and kat[1]["modell3d"] == "3D/gv2.katie3d", "pro Artikel gesetzt / neu")
check(G3.artikel_setzen(kat, "", "x") is kat and len(kat) == 2, "ohne TYP nichts")

# ---- per symbol: project table and attribute definition MODELL3D in the block
k5 = geraet(0, 0, "-K5", "")
check(G3.modell_von(k5, katalog, {"Sym": "3D/sym.katie3d"}) == ("3D/sym.katie3d", "symbol"),
      "Modell des Symbols (Projekttabelle)")
check(G3.modell_von(geraet(0, 0, "-K6", "LC1D09"), katalog, {"Sym": "3D/sym.katie3d"})[1] == "artikel",
      "Artikel vor Symbol")
m = core.ElektroMaske(8, 0)
ad = core.AttributDefinition(0, 0, None, 2.5, tag="MODELL3D", prompt="MODELL3D", wert="3D/def.katie3d")
k7 = core.BlockReferenz(0, 0, "SymDef", [core.Rechteck(-3, -5, 3, 5), m, ad])
k7.attribute.update({"IND": "-K7"})
check(k7.attribute.get("MODELL3D") == "3D/def.katie3d", "Vorgabe aus der Attributdefinition")
check(G3.modell_von(k7) == ("3D/def.katie3d", "symbol"), "Vorgabe der Definition = Symbol")
check(G3.modell_von(k7, None, {"SymDef": "3D/tab.katie3d"}) == ("3D/tab.katie3d", "symbol"),
      "Projekttabelle vor Definition")
k7.attribute["MODELL3D"] = "3D/k7.katie3d"
check(G3.modell_von(k7) == ("3D/k7.katie3d", "geraet"), "geänderter Wert = eigenes Modell")
zeilen = G3.geraete_mit_modell([(0, [k5])], katalog, (), {"Sym": "3D/sym.katie3d"})
check(zeilen[0]["quelle"] == "symbol", "Geräteliste mit Symbolmodell")
tab = {}
G3.symbol_setzen(tab, ["Sym", "", "SymDef"], "3D/s.katie3d")
check(tab == {"Sym": "3D/s.katie3d", "SymDef": "3D/s.katie3d"}, "pro Symbol gesetzt")
G3.symbol_setzen(tab, ["Sym"], "")
check(tab == {"SymDef": "3D/s.katie3d"}, "Symbolmodell entfernt")

# ---- parts catalogue dialog returns only its columns
vom_dialog = [{"typ": "LC1D09", "hersteller": "Schneider", "bestellnr": "123", "beschreibung": ""}]
neu = G3.katalog_zusammenfuehren(kat, vom_dialog)
check(len(neu) == 1 and neu[0]["modell3d"] == "3D/b.katie3d" and neu[0]["bestellnr"] == "123",
      "Modell bleibt, gelöschte Artikel bleiben weg")

print(f"test_geraete3d - OK ({ok} Pruefungen)")
