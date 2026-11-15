# -*- coding: utf-8 -*-
"""Machining: face plane seen from outside (X right, Y up), templates, round /
rectangular cut-outs in rows, depth, label and position saved, machining list,
cabinet parts (door) and the dialog parser."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
from katiecad.model import mechanik as M, schrank as SCHR, geom3d as G
from katiecad.reports import seiten as S
from katiecad.ui.ansicht3d import mechanik_ergebnis
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


def flaeche(k, seite):
    """Points of the face of body k that looks at `seite`."""
    nz, zen = k.netz(), k.zentrum3()
    for f in nz.flaechen:
        pts = [nz.punkte[i] for i in f]
        e = G.ebene_von_flaeche(pts, zen)
        if e is not None and M.seite(e) == seite:
            return pts
    return None


# ---- templates of the program
V = M.vorlagen_laden([os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "report_templates")])
namen = [v["name"] for v in V]
check(any("22,5" in n for n in namen) and any("M20" in n for n in namen)
      and any(v["form"] == "rechteck" for v in V), f"Vorlagen: {len(V)}")

# ---- front face of a box 600 x 300 x 1000: origin lower left, X right, Y up
box = core.quader(0, 0, 600, 300, 0, 1000)
e, bw, bh = M.flaechen_ebene(flaeche(box, "vorne"), box.zentrum3())
u, v, w = G.ebene_basis(e)
check(tuple(round(c, 6) for c in e[:3]) == (0, 0, 0) and round(bw) == 600 and round(bh) == 1000,
      f"Ursprung links unten, 600 x 1000: {e[:3]} {bw} {bh}")
check(tuple(round(c, 6) for c in u) == (1, 0, 0) and tuple(round(c, 6) for c in v) == (0, 0, 1)
      and tuple(round(c, 6) for c in w) == (0, -1, 0), "X rechts, Y oben, Normale nach vorne")
er, bwr, _ = M.flaechen_ebene(flaeche(box, "rechts"), box.zentrum3())
ur = G.ebene_basis(er)[0]
check(tuple(round(c, 6) for c in ur) == (0, 1, 0) and round(bwr) == 300 and M.seite(er) == "rechts",
      "rechte Seite: X nach hinten (von außen gesehen)")

# ---- a row of 3 push button holes + a fan cut-out
elemente = [box]
n = M.mechanisieren(elemente, e, "rund", M.positionen(100, 900, 3, 40), d=22.5, tiefe=3,
                    bez="Pulsador Ø22,5")
check(n == 3 and len(box.ausschnitte) == 3, "drei Bohrungen")
a = box.ausschnitte[1]
xs = [p[0] for p in a["profil"]]
check(a["rund"] and abs(max(xs) - min(xs) - 22.5) < 0.1 and a["pos"] == [140.0, 900.0]
      and a["tiefe"] == 3 and a["bez"] == "Pulsador Ø22,5", f"zweite Bohrung: {a['pos']}")
check(M.mechanisieren(elemente, e, "rechteck", [(300, 200)], b=125, h=125, tiefe=0) == 1
      and box.ausschnitte[-1]["tiefe"] is None and box.ausschnitte[-1]["bez"] == "125 x 125",
      "Ventilator-Ausschnitt durch, Standard-Bezeichnung")
check(M.mechanisieren(elemente, e, "rund", [(5000, 5000)], d=10) == 0, "außerhalb der Fläche")

# ---- saved and loaded with label and position; moving keeps them
d = json.loads(json.dumps(box.to_dict()))
k2 = core.Koerper3D(**{kk: vv for kk, vv in d.items() if kk != "typ"})
check(k2.ausschnitte[0]["bez"] == "Pulsador Ø22,5" and k2.ausschnitte[0]["pos"] == [100.0, 900.0],
      "Bezeichnung und Position gespeichert")
alt = {"ebene": [0, 0, 0, 1, 0, 0, 0, 1, 0], "profil": [[0, 0], [1, 0], [1, 1]], "tiefe": None, "rund": False}
check("bez" not in core.Koerper3D(ausschnitte=[alt]).to_dict()["ausschnitte"][0], "alte Ausschnitte unverändert")
k2.verschieben(10, 0, 0)
check(k2.ausschnitte[0]["bez"] and k2.ausschnitte[0]["pos"] == [100.0, 900.0], "Verschieben behält die Daten")

# ---- machining list
zeilen = M.mechanikliste([(0, elemente)], {"vorne": "frontal"})
check(len(zeilen) == 4 and zeilen[0]["seite"] == "frontal", f"vier Zeilen: {len(zeilen)}")
check([z["x"] for z in zeilen[:3]] == ["100.0", "140.0", "180.0"] and zeilen[0]["masse"] == "Ø22.5"
      and zeilen[0]["tiefe"] == "3", f"oben zuerst, links nach rechts: {zeilen[0]}")
check(zeilen[-1]["masse"] == "125 x 125" and zeilen[-1]["tiefe"] == "", "Ausschnitt durch")
rows = S.listen_zeilen("mechanik", [(0, elemente)], lambda i: 1)
check(rows[0]["seite"] == I.tr("mech.seite.vorne") and "mechanik" in S.LISTEN, "Liste übersetzt")

# ---- cabinet: the door is a part of the cabinet block
sch = SCHR.schrank_bauen(600, 800, 300, tuer=True)
tuer = next(t for t in sch.teile if t.bez == "Tür")
et, _b, _h = M.flaechen_ebene(flaeche(tuer, "vorne"), tuer.zentrum3())
check(M.mechanisieren([sch], et, "rund", [(100, 600)], d=22.5, tiefe=0, koerper=tuer) == 1
      and len(tuer.ausschnitte) == 1, "Bohrung in der Tür")
zt = M.mechanikliste([(0, [sch])])
check(zt and zt[0]["teil"] == "Tür", f"Teil = Tür: {zt}")

# ---- dialog parser
r = mechanik_ergebnis("rund", {"d": "22,5", "x": "100", "y": "50", "nx": "3", "dx": "40",
                               "ny": "1", "dy": "0", "tiefe": "0", "b": "", "h": ""}, " P ")
check(r["d"] == 22.5 and r["nx"] == 3 and r["tiefe"] == 0 and r["bez"] == "P", "Dialog gelesen")
check(mechanik_ergebnis("rund", {"d": "0"}) is None, "Ø 0 abgelehnt")
check(mechanik_ergebnis("rechteck", {"b": "10", "h": "x"}) is None, "keine Zahl")
check(mechanik_ergebnis("rund", {"d": "5", "nx": "0"}) is None, "0 Spalten abgelehnt")

print(f"test_mechanik - OK ({ok} Pruefungen)")
