# -*- coding: utf-8 -*-
"""Wire numbering: grouping, rules (manual, PLC, potential, sheet counter),
labels on the wire, keep / renumber, save and load."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as katiecad_i18n; katiecad_i18n.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.electrical import drahtnummern as DN
from katiecad.reports import netz as N
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


VP = core.Verbindungspunkt
L = core.Leitung


def geraet(x, y, ind):
    """Two-pin device: pin 1 at (x, y+5), pin 2 at (x, y-5)."""
    sym = [core.Rechteck(-5, -5, 5, 5), VP(0, 5, wert="1", tag="P1"),
           VP(0, -5, wert="2", tag="P2"), core.ElektroMaske(8, 0)]
    b = core.BlockReferenz(x, y, "Sym", sym)
    b.attribute.update({"IND": ind, "TYP": "", "PER": ""})
    return b


def sps_di(x, y, adressen):
    """DI module with channel pins along the top edge."""
    sym = [core.Rechteck(-3, -18, 30, -2)]
    for i, a in enumerate(adressen):
        sym.append(VP(i * 5, 0, wert=a, tag=f"VP{i + 1}"))
    b = core.BlockReferenz(x, y, "PLC DI", sym)
    b.attribute.update({"IND": "-A1", "SPS": "DI"})
    return b


def labels(el):
    return [e for e in el if isinstance(e, core.Drahtnummer)]


def nummerieren(blaetter, **kw):
    netz = N.Netz.aufbauen(blaetter)
    plan = DN.planen(blaetter, netz, **kw)
    for b, el in blaetter:
        DN.anwenden(plan, b, el)
    return plan


# ---- sheet 1: K1 -- junction-free wire -- K2, terminal X1:1 between K2 and K3
k1 = geraet(0, 0, "-K1")             # pins (0,5) (0,-5)
k2 = geraet(0, -40, "-K2")           # pins (0,-35) (0,-45)
kl = core.Klemme(0, -60, {"IND": "-X1", "NUM": "1"})
ko, ku = kl.anschluss_oben(), kl.anschluss_unten()
k3 = geraet(0, -100, "-K3")          # pins (0,-95) (0,-105)
# K1:2 -> corner -> K2:1 (two wire pieces, one wire)
w1 = L(0, -5, 0, -20)
w2 = L(0, -20, 0, -35)
# K2:2 -> X1:1 top
w3 = L(0, -45, *ko)
# X1:1 bottom -> K3:1
w4 = L(*ku, 0, -95)
blatt1 = [k1, k2, kl, k3, w1, w2, w3, w4]

netz = N.Netz.aufbauen([(0, blatt1)])
ds = DN.draehte(netz)
check(len(ds) == 3, f"3 Drähte (w1+w2, w3, w4), nicht {len(ds)}")
check(any({id(l) for _b, l in d.leitungen} == {id(w1), id(w2)} for d in ds),
      "zwei Leitungsstücke ohne Gerät dazwischen = ein Draht")

plan = nummerieren([(0, blatt1)])
txt = sorted(l.inhalt for l in labels(blatt1))
check(txt == ["1.1", "1.2", "1.3"], f"Blatt + Zähler: {txt}")
check(len(labels(blatt1)) == 3, "ein Etikett je Draht und Blatt")
lab_w12 = next(l for l in labels(blatt1) if DN.leitung_unter([w1, w2], l.x, l.y))
check(lab_w12.inhalt == "1.1", "oben links beginnt die Zählung")
check(lab_w12.winkel == 90.0, "senkrechte Leitung: Text gedreht")
check(not lab_w12.manuell, "automatisches Etikett ist nicht manuell")

# ---- second run without changes: nothing to do
plan = nummerieren([(0, blatt1)])
check(plan.anzahl == 0, f"zweiter Lauf ändert nichts ({plan.anzahl})")

# ---- manual number survives renumbering
lab_w12.inhalt = "K-100"
check(lab_w12.manuell, "geänderter Text = manuell")
nummerieren([(0, blatt1)], neu_nummerieren=True)
check(lab_w12.inhalt == "K-100", "manuelle Nummer bleibt")
txt = sorted(l.inhalt for l in labels(blatt1))
check(txt == ["1.1", "1.2", "K-100"], f"Neu nummerieren füllt Lücke: {txt}")

# ---- label whose wire disappeared is removed (only automatic ones)
blatt1.remove(w4)
nummerieren([(0, blatt1)])
check(sorted(l.inhalt for l in labels(blatt1)) == ["1.1", "K-100"],
      "verwaistes automatisches Etikett entfernt")

# ---- format setting
b = [geraet(0, 0, "-K1"), geraet(40, 0, "-K2")]
b += [L(0, -5, 0, -15), L(0, -15, 40, -15), L(40, -15, 40, -5)]
e = DN.einstellungen({"drahtnummern": {"format": "W{sheet}-{n:02}"}})
nummerieren([(4, b)], einstellung=e, sheet_nr=lambda k: k + 1)
check([l.inhalt for l in labels(b)] == ["W5-01"], f"Format: {[l.inhalt for l in labels(b)]}")
check(DN.format_text("{kaputt}", 2, "2", 3) == "2.3", "ungültiges Format -> Standard")
check(DN.format_text("{hoja}/{n}", 7, "7", 1) == "7/1", "spanische Platzhalter")

# ---- PLC: wire to DI channel takes the address, also on the terminal side
a1 = sps_di(0, 0, ["DI0.00", "0.01", "M", "I1.2"])
s1 = geraet(0, 40, "-S1")            # pins (0,45) (0,35)
s2 = geraet(5, 40, "-S2")            # pins (5,45) (5,35)
s3 = geraet(10, 40, "-S3")           # pins (10,45) (10,35)
s4 = geraet(15, 40, "-S4")            # pins (15,45) (15,35)
b = [a1, s1, s2, s3, s4, L(0, 35, 0, 0), L(5, 35, 5, 0), L(10, 35, 10, 0), L(15, 35, 15, 0)]
nummerieren([(0, b)])
txt = sorted(l.inhalt for l in labels(b))
check(txt == ["1.1", "DI0.00", "DI0.01", "DI1.2"], f"SPS-Adressen: {txt}")
b2 = [sps_di(0, 0, ["DI0.00"]), geraet(0, 40, "-S1"), L(0, 35, 0, 0)]
nummerieren([(0, b2)], einstellung=DN.einstellungen({"drahtnummern": {"sps": False}}))
check([l.inhalt for l in labels(b2)] == ["1.1"], "SPS-Regel abschaltbar")

# ---- cross references join the wire over two sheets; potential option
qa = core.Querverweis(0, -20, text="A", art="abgehend", richtung=270)
qe = core.Querverweis(0, 0, text="A", art="ankommend", richtung=270)
ba = [geraet(0, 0, "-K1"), qa, L(0, -5, *qa.basis_punkt())]
bb = [qe, geraet(0, -30, "-K2"), L(*qe.spitze_punkt(), 0, -25)]
nummerieren([(0, ba), (1, bb)])
check([l.inhalt for l in labels(ba)] == ["1.1"] and [l.inhalt for l in labels(bb)] == ["1.1"],
      "Querverweis: gleicher Draht, gleiche Nummer auf beiden Blättern")
pl = core.Querverweis(0, -20, text="L1", art="abgehend", richtung=270)
bp = [geraet(0, 0, "-F1"), pl, L(0, -5, *pl.basis_punkt())]
nummerieren([(0, bp)], einstellung=DN.einstellungen({"drahtnummern": {"potenzial": True}}))
check([l.inhalt for l in labels(bp)] == ["L1"], "Potenzial-Regel")

# ---- save / load
d = lab_w12.to_dict()
check(d["typ"] == "drahtnummer" and d["auto_text"] == "1.1", "to_dict")
kw = {k: v for k, v in d.items() if k != "typ"}
neu = core.Drahtnummer(**kw)
check(neu.inhalt == "K-100" and neu.manuell and neu.typ == "drahtnummer", "laden")
check(isinstance(neu, core.Text), "Drahtnummer ist ein Text (Anzeige, PDF, DXF)")

# ---- app: whole project, other sheet on disk, settings kept in project
import json, tempfile
from types import SimpleNamespace
import katiecad.ui.app as A
from katiecad.model.project import Projekt
A.messagebox = SimpleNamespace(showerror=lambda *a, **k: None)
with tempfile.TemporaryDirectory() as tmp:
    p = Projekt.erstellen("Anlage", tmp)
    for nm in ("Steuerung", "Ausgaenge"):
        p.blatt_hinzufuegen(nm)
    p.aktiv = 0
    s1 = [geraet(0, 0, "-K1"), geraet(0, -40, "-K2"), L(0, -5, 0, -35)]
    s2 = [geraet(0, 0, "-K3"), geraet(0, -40, "-K4"), L(0, -5, 0, -35),
          geraet(30, 0, "-K5"), geraet(30, -40, "-K6"), L(30, -5, 30, -35)]
    dlg = A.CadApp.__new__(A.CadApp)
    with open(p.blatt_pfad(0), "w", encoding="utf-8") as f:
        json.dump({"elemente": []}, f)
    with open(p.blatt_pfad(1), "w", encoding="utf-8") as f:
        json.dump({"elemente": [e.to_dict() for e in s2], "layouts": []}, f)
    fake = SimpleNamespace(projekt=p, root=None, elemente=s1, _draht_einst={}, layers={},
                           layouts=[], aktives_layout=0, _einh_faktor=lambda: 1.0,
                           dezimalkomma=SimpleNamespace(get=lambda: False))
    fake.status = SimpleNamespace(set=lambda t: setattr(fake, "meldung", t))
    fake._ist_layout = lambda: False
    fake._blatt_sichern = lambda: True
    fake._snapshot = lambda: setattr(fake, "snap", True)
    fake.redraw = lambda: None
    fake._einpolig_sync = lambda: A.CadApp._einpolig_sync(fake)
    fake._standard_layers = lambda: {}
    fake._dict_zu_element = dlg._dict_zu_element
    fake._json_atomar_schreiben = A.CadApp._json_atomar_schreiben
    for m in ("_blatt_druckkontext", "_zeichnungsblaetter_einlesen", "_andere_blaetter_daten"):
        setattr(fake, m, getattr(A.CadApp, m).__get__(fake))
    A.DrahtnummernDialog = lambda *a, **k: SimpleNamespace(result={
        "format": "{hoja}-{n:02}", "sps": True, "potenzial": False, "hoehe": 3.0,
        "neu": False, "projekt": True})
    A.CadApp.drahtnummern_vergeben(fake)
    check([l.inhalt for l in labels(s1)] == ["1-01"], f"App: aktives Blatt {[l.inhalt for l in labels(s1)]}")
    check(labels(s1)[0].hoehe == 3.0 and getattr(fake, "snap", False), "App: Höhe, Undo-Schnappschuss")
    d = json.load(open(p.blatt_pfad(1), encoding="utf-8"))
    dn = sorted(e["inhalt"] for e in d["elemente"] if e["typ"] == "drahtnummer")
    check(dn == ["2-01", "2-02"], f"App: anderes Blatt auf Platte: {dn}")
    check(len(d["elemente"]) == len(s2) + 2, "App: übrige Elemente unverändert")
    check(Projekt.laden(p.projektdatei).doku["drahtnummern"]["format"] == "{hoja}-{n:02}",
          "App: Einstellung im Projekt gespeichert")
    geladen = [fake._dict_zu_element(e) for e in d["elemente"]]
    check(sum(isinstance(e, core.Drahtnummer) for e in geladen) == 2, "App: Etiketten wieder ladbar")
    A.CadApp.drahtnummern_vergeben(fake)
    check("aktuell" in fake.meldung, f"App: zweiter Lauf: {fake.meldung}")

print(f"test_drahtnummern - OK ({ok} Pruefungen)")
