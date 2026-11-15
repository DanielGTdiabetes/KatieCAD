# -*- coding: utf-8 -*-
"""Move by offset (ΔX, ΔY, ΔZ) with optional copies in a row: 2D objects ignore ΔZ,
3D bodies take it; units; no pin magnet; commands do not clash with OFFSET."""
import sys, os
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
import katiecad.ui.app as A
from katiecad.ui.dialogs import versatz_ergebnis, zahl_text
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


# ---- model
lin = core.Linie(0, 0, 10, 0)
box = core.quader(0, 0, 100, 50, 0, 20)
check(not core.kann_z(lin) and core.kann_z(box), "2D ohne Z, 3D-Körper mit Z")
check(core.versetzen([lin, box], 5, -2, 30) == 1, "eine Linie ohne ΔZ")
b = box.bbox3()
check((lin.x1, lin.y1, lin.x2) == (5, -2, 15), f"Linie verschoben: {(lin.x1, lin.y1, lin.x2)}")
check(abs(b[0] - 5) < 1e-9 and abs(b[1] + 2) < 1e-9 and abs(b[2] - 30) < 1e-9, f"Körper xyz: {b}")
check(core.versetzen([lin], 1, 0, 0) == 0, "ΔZ 0: kein Hinweis")

# ---- dialog parsing
check(versatz_ergebnis({"dx": "10,5", "dy": "", "dz": "-3"}, False, "4")
      == {"dx": 10.5, "dy": 0.0, "dz": -3.0, "kopien": 0}, "Komma, leer = 0, ohne Kopien")
check(versatz_ergebnis({"dx": "1"}, True, "5000")["kopien"] == 999, "Kopien begrenzt")
check(versatz_ergebnis({"dx": "x"}, False, "1") is None, "keine Zahl")
check(zahl_text(0.5) == "0.5" and zahl_text(10.0) == "10" and zahl_text(0) == "0", "Zahltext")

# ---- commands: OFFSET stays the offset tool
check(core.BEFEHLE["OFFSET"] == "versatz" and core.BEFEHLE["O"] == "versatz"
      and core.BEFEHLE["VERSATZ"] == "versatz", "OFFSET/VERSATZ bleiben Versatz-Werkzeug")
check(core.BEFEHLE["DESPLAZAR"] == "versatz_verschieben" and core.BEFEHLE["MOVEOFFSET"]
      == "versatz_verschieben", "neue Befehle")

# ---- app: move and copies, unit factor, no magnet, one undo step
liste = []
log = {"snap": 0, "magnet": [], "msg": []}


def fake(auswahl, ergebnis, faktor=1.0):
    A.VersatzDialog = lambda *a, **k: SimpleNamespace(result=ergebnis, args=a)
    f = SimpleNamespace(auswahl=auswahl, _einh_faktor=lambda: faktor,
                        einheit=SimpleNamespace(get=lambda: "cm" if faktor == 10 else "mm"),
                        _ziel_liste=lambda: liste, _ansicht3d=None,
                        _snapshot=lambda: log.__setitem__("snap", log["snap"] + 1),
                        _dict_zu_element=lambda d: A.CadApp._dict_zu_element(A.CadApp.__new__(A.CadApp), d),
                        _einrasten=lambda objs, magnet=True: log["magnet"].append(magnet),
                        redraw=lambda: None, root=None, status=SimpleNamespace(set=log["msg"].append))
    return f


l1 = core.Linie(0, 0, 10, 0)
k1 = core.quader(0, 0, 10, 10, 0, 10)
liste[:] = [l1, k1]
f = fake([l1, k1], {"dx": 2, "dy": 0, "dz": 3, "kopien": 0}, faktor=10.0)     # cm
A.CadApp.versatz_verschieben(f)
check((l1.x1, l1.x2) == (20, 30) and abs(k1.bbox3()[2] - 30) < 1e-9, "cm: 2 cm / 3 cm")
check(log["snap"] == 1 and log["magnet"] == [False], "ein Undo-Schritt, kein Pin-Magnet")
check("objeto(s) 2D sin ΔZ" in log["msg"][-1], f"Hinweis 2D: {log['msg'][-1]}")
check(f._versatz_letzt == {"dx": 20, "dy": 0, "dz": 30, "kopien": 0}, "letzter Versatz gemerkt (mm)")

c = core.Linie(0, 0, 0, 5)
liste[:] = [c]
f = fake([c], {"dx": 50, "dy": 0, "dz": 0, "kopien": 3})
A.CadApp.versatz_verschieben(f)
xs = sorted(e.x1 for e in liste)
check(xs == [0, 50, 100, 150] and c.x1 == 0, f"3 Kopien in einer Reihe: {xs}")
check(len(f.auswahl) == 1 and f.auswahl[0].x1 == 150, "letzte Kopie ausgewählt")
f = fake([c], {"dx": 0, "dy": 0, "dz": 0, "kopien": 0})
n = log["snap"]
A.CadApp.versatz_verschieben(f)
check(log["snap"] == n and "no se ha movido" in log["msg"][-1], "Versatz 0: nichts")
f = fake([], None)
A.CadApp.versatz_verschieben(f)
check("selecciona" in log["msg"][-1], "ohne Auswahl Hinweis")

print(f"test_versatz - OK ({ok} Pruefungen)")
