# -*- coding: utf-8 -*-
"""Single-pole (one-line) symbols and their flow: style of the new symbols,
automatic wires between them (also from the busbar), no wire numbers / list
entries for the single-pole representation unless 'evaluate single-pole too'."""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
import katiecad.electrical.logic as L
from katiecad.electrical import drahtnummern as DN
from katiecad.reports import netz as N, daten as D
import katiecad.ui.app as A
from katiecad.model.blocks import block_laden
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


app = A.CadApp.__new__(A.CadApp)
ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "symbols", "12 Single-pole")
NEU = ("Disconnector 1p", "Switch disconnector 1p", "Contactor 1p", "Energy meter 1p",
       "Frequency converter 1p", "UPS 1p", "Busbar 1p", "PV generator 1p", "PV inverter 1p")
DEF = {}
for n in NEU:
    pfad = os.path.join(ORDNER, n + ".katieblock")
    check(os.path.exists(pfad), f"Symbol vorhanden: {n}")
    DEF[n] = block_laden(pfad, app._dict_zu_element)


def ref(name, x, y, ind):
    d = DEF[name]
    b = core.BlockReferenz(x, y, d.name, d.elemente)
    b.attribute.update({"IND": ind})
    return b


# ---- style: single-pole mask with pole count, pins on the 5 mm grid
for n, d in DEF.items():
    m = [e for e in d.elemente if isinstance(e, core.ElektroMaske)]
    check(len(m) == 1 and m[0].einpolig and m[0].pole, f"{n}: einpolige Maske mit POLE")
    pins = [e for e in d.elemente if isinstance(e, core.Verbindungspunkt)]
    check(pins and all(abs(p.x / 5 - round(p.x / 5)) < 1e-9 and abs(p.y / 5 - round(p.y / 5)) < 1e-9
                       for p in pins), f"{n}: Anschlüsse im 5-mm-Raster")
    check(all(p.richtungen for p in pins), f"{n}: Anschlussrichtungen gesetzt")
check(DEF["Contactor 1p"].elemente and next(e for e in DEF["Contactor 1p"].elemente
                                            if isinstance(e, core.ElektroMaske)).rolle == "hilfs",
      "Schütz-Hauptkontakt ist Hilfsgerät")
check(sum(isinstance(e, core.Verbindungspunkt) for e in DEF["Busbar 1p"].elemente) == 7,
      "Sammelschiene mit 7 Abgängen")

# ---- a one-line feeder: busbar -> disconnector -> contactor -> VFD
core.EINPOLIG_MIT[0] = False
w = ref("Busbar 1p", 0, 0, "-W1")
q = ref("Disconnector 1p", 10, -10, "-Q1")
k = ref("Contactor 1p", 10, -30, "-K1")
u = ref("Frequency converter 1p", 10, -50, "-U1")
el = [w, q, k, u]
L.leitungen_automatisch(el)
leit = [e for e in el if isinstance(e, core.Leitung)]
check(len(leit) == 3, f"automatische Leitungen Schiene-Q-K-U: {len(leit)}")
check(any(abs(l.x1 - 10) < 1e-9 and {round(l.y1, 3), round(l.y2, 3)} == {0.0, -10.0} for l in leit),
      "Abgang der Sammelschiene nach unten")
check(all(core.ist_einpolig(b) for b in (w, q, k, u)), "alles einpolige Darstellung")

# ---- without the option: no wire numbers, not in the device list
netz = N.Netz.aufbauen([(0, el)])
plan = DN.planen([(0, el)], netz, einstellung=DN.einstellungen({}))
check(sum(len(v) for v in plan.neu.values()) == 0, "keine Drahtnummern im Einlinienschema")
alt = core.Drahtnummer(10, -5, "999", auto_text="999")
el.append(alt)
plan = DN.planen([(0, el)], N.Netz.aufbauen([(0, el)]), einstellung=DN.einstellungen({}))
check(alt in plan.weg[0], "alte automatische Nummer am Einlinienschema wird entfernt")
el.remove(alt)
check(not [z for z in D.geraeteliste([(0, el)], lambda i: 1) if z["ind"] in ("-Q1", "-K1", "-U1")],
      "nicht in der Geräteliste")

# ---- with 'evaluate single-pole too': counted and numbered
core.EINPOLIG_MIT[0] = True
try:
    inds = {z["ind"] for z in D.geraeteliste([(0, el)], lambda i: 1)}
    check({"-Q1", "-K1", "-U1", "-W1"} <= inds, f"mit Option in der Geräteliste: {inds}")
    plan = DN.planen([(0, el)], N.Netz.aufbauen([(0, el)]), einstellung=DN.einstellungen({}))
    check(sum(len(v) for v in plan.neu.values()) == 3, "mit Option nummeriert")
finally:
    core.EINPOLIG_MIT[0] = False

print(f"test_unifilar - OK ({ok} Pruefungen)")
