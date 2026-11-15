# -*- coding: utf-8 -*-
"""DIN rail: own catalogue (several heights), drawn with the duct tool in rail mode
(bars of max. length, sizes kept apart from the ducts), counted as rail in the duct
list, and device models snap with their DIN rail point onto the rail axis."""
import sys, os
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
from katiecad.model import kanal_katalog as KK, szene3d as S
from katiecad.reports import seiten as SEI
import katiecad.ui.app as A
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


PROG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report_templates")

# ---- catalogue with several heights
kat = KK.katalog_laden([PROG], KK.DATEI_SCHIENE)
hoehen = sorted({k["hoehe"] for k in kat["kanaele"] if k["breite"] == 35})
check(kat["max_laenge"] == 2000 and hoehen == [7.5, 15.0], f"TS 35 in 7,5 und 15: {hoehen}")
check(len(kat["kanaele"]) == 4 and all(k["hersteller"] for k in kat["kanaele"]), "vier Profile")

# ---- app: rail mode keeps its own sizes
app = SimpleNamespace(_kanal_breite=60.0, _kanal_hoehe=40.0, _kanal_ref="60.40.77", _kanal_max=None,
                      _kanal_schiene=False, _kanal_saetze=None)
A.CadApp._kanal_satz_wechseln(app, True)
check((app._kanal_breite, app._kanal_hoehe, app._kanal_schiene) == (35.0, 7.5, True), "Schienenmaße")
app._kanal_hoehe, app._kanal_ref = 15.0, "0236400000"
A.CadApp._kanal_satz_wechseln(app, False)
check((app._kanal_breite, app._kanal_hoehe, app._kanal_ref) == (60.0, 40.0, "60.40.77"), "Kanal zurück")
A.CadApp._kanal_satz_wechseln(app, True)
check((app._kanal_hoehe, app._kanal_ref) == (15.0, "0236400000"), "Schiene gemerkt")

# ---- 2D rail pieces: bars of 2000, flag saved
fake = SimpleNamespace(_kanal_breite=35.0, _kanal_hoehe=7.5, _kanal_schraffur="",
                       _kanal_schraffur_abstand=20.0, _kanal_ausrichtung="mitte", _kanal_ref="0383400000",
                       _kanal_schiene=True, _kanal_max_laenge=lambda: 2000.0,
                       _kanal_layer_daten=lambda: {"layer": "CD"})
stuecke = A.CadApp._kanal_stuecke(fake, [(0, 0), (2600, 0)])
check(len(stuecke) == 2 and all(s.schiene for s in stuecke), "2600 mm -> 2 Stangen")
d = stuecke[0].to_dict()
check(d["schiene"] is True and core.Kabelkanal(**{k: v for k, v in d.items() if k != "typ"}).schiene,
      "Schiene gespeichert")

# ---- list: rail counted as rail, with manufacturer
zeilen = KK.kanalliste([(0, stuecke)], KK.katalog_laden([PROG]), kat)
check(len(zeilen) == 1 and zeilen[0]["art"] == "schiene" and zeilen[0]["laenge"] == "2.60"
      and zeilen[0]["stangen"] == "2" and zeilen[0]["hersteller"] == "Weidmüller", f"Liste: {zeilen}")
rows = SEI.listen_zeilen("kanaele", [(0, stuecke)], lambda i: 1,
                         kanal_katalog=dict(KK.katalog_laden([PROG]), _ordner=[PROG]))
check(rows[0]["art"] == "Carril DIN", f"übersetzt: {rows[0]['art']}")

# ---- device snaps onto a horizontal rail in front of the plate
schiene = core.Koerper3D("prisma", profil=core.kanal_rechteck((0, 500), (400, 500), 35), hoehe=7.5,
                         ebene=(0, 282, 0, 1, 0, 0, 0, 0, 1),
                         kanal={"art": "gerade", "breite": 35, "hoehe": 7.5, "schiene": True})
b = schiene.bbox3()
check(abs(b[1] - 274.5) < 1e-6 and abs((b[2] + b[5]) / 2 - 500) < 1e-6, f"Schiene vor der Platte: {b}")
hut = (22.5, 0.0, 37.5)                              # DIN rail point of a 45 x 75 device
r = S.auf_hutschiene([schiene], (100.0, 282.0, 470.0), hut)
check(r is not None and r[0] == (100.0, 274.5, 462.5), f"auf die Schienenachse: {r}")
check(S.auf_hutschiene([schiene], (100.0, 282.0, 300.0), hut) is None, "weit weg: kein Fang")
check(S.auf_hutschiene([schiene], (900.0, 282.0, 470.0), hut) is None, "neben der Schiene: kein Fang")

print(f"test_hutschiene - OK ({ok} Pruefungen)")
