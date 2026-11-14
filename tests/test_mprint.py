# -*- coding: utf-8 -*-
"""Marker export for label printers (Weidmüller M-Print PRO): wires (one marker per
end, also at branches), terminals in mounting order, devices, length check,
Excel without header / merged cells, CSV unchanged, wire number in the
connection list."""
import sys, os, csv, shutil, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
from katiecad.electrical import drahtnummern as DN
from katiecad.reports import netz as N, mprint as MP, daten_listen as DL, seiten as S
from katiecad.ui.dialogs import mprint_ergebnis
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


VP = core.Verbindungspunkt
L = core.Leitung
nr = lambda i: i + 1


def geraet(x, y, ind):
    sym = [core.Rechteck(-3, -5, 3, 5), VP(0, 5, wert="1", tag="P1"),
           VP(0, -5, wert="2", tag="P2"), core.ElektroMaske(8, 0)]
    b = core.BlockReferenz(x, y, "Sym", sym)
    b.attribute.update({"IND": ind})
    return b


# K1:2 -> X1:1 top; X1:1 bottom -> M1:1; a T from K2:2 to K3:1 and K4:1
k1, m1 = geraet(0, 0, "-K1"), geraet(0, -60, "-M1")
klemmen = [core.Klemme(x, -30, {"IND": "-X1" if x == 0 else "", "NUM": str(n)})
           for x, n in ((0, 1), (10, 2), (20, 10))]
k2, k3, k4 = geraet(60, 0, "-K2"), geraet(40, -40, "-K3"), geraet(80, -40, "-K4")
x1 = klemmen[0]
el = [k1, m1, k2, k3, k4] + klemmen + [
    L(0, -5, *x1.anschluss_oben()), L(*x1.anschluss_unten(), 0, -55),
    L(60, -5, 60, -20), L(40, -20, 60, -20), L(60, -20, 80, -20),
    L(40, -20, 40, -35), L(80, -20, 80, -35)]
blaetter = [(0, el)]
netz = N.Netz.aufbauen(blaetter)
plan = DN.planen(blaetter, netz, einstellung=DN.einstellungen({}), sheet_nr=lambda k: 10)
DN.anwenden(plan, 0, el)
netz = N.Netz.aufbauen(blaetter)

# ---- wires: one marker per end, sorted by number
h = MP.hilos(netz)
nummern = sorted({z["nr"] for z in h})
check(nummern == ["1000", "1001", "1002"], f"Drahtnummern: {nummern}")
je = {n: [z for z in h if z["nr"] == n] for n in nummern}
check(sorted(len(v) for v in je.values()) == [2, 2, 3], "zwei Enden, T mit drei Enden")
t = next(v for v in je.values() if len(v) == 3)
check({z["hier"] for z in t} == {"-K2:2", "-K3:1", "-K4:1"}, f"Enden der Abzweigung: {t}")
check(all(z["text"] == z["nr"] for z in h), "Standardtext = Nummer")
h2 = MP.hilos(netz, "{nr} {ziel}")
z0 = next(z for z in h2 if z["hier"] == "-K1:2")
check(z0["text"] == z0["nr"] + " -X1:1", f"Format mit Ziel: {z0['text']}")
check(MP.hilos(netz, "{kaputt}")[0]["text"] == h[0]["nr"], "kaputtes Format -> Standard")

# ---- terminals in mounting order, devices
b = MP.bornes(netz, blaetter, nr)
check([z["text"] for z in b] == ["-X1:1", "-X1:2", "-X1:10"], f"Klemmen in Montagereihenfolge: {b}")
e = MP.equipos(blaetter, nr)
check([z["text"] for z in e] == ["-K1", "-K2", "-K3", "-K4", "-M1"], f"Geräte: {[z['text'] for z in e]}")

# ---- settings and length check
einst = MP.einstellungen({"mprint": {"bornes": {"max": 5, "falsch": 1}, "csv": 1}})
check(einst["bornes"]["max"] == 5 and "falsch" not in einst["bornes"] and einst["csv"] is True
      and einst["hilos"]["format"] == "{nr}", "Einstellungen gemischt")
listen = MP.listen(netz, blaetter, nr, None, einst)
check(set(listen) == {"hilos", "bornes", "equipos"}, "drei Listen")
lang = MP.zu_lang(listen, einst)
check([(a, t) for a, t, _l, _m in lang] == [("bornes", "-X1:10")], f"zu lang: {lang}")
aus = MP.einstellungen({"mprint": {"equipos": {"aktiv": False}}})
check("equipos" not in MP.listen(netz, blaetter, nr, None, aus), "Liste abschaltbar")
check(mprint_ergebnis(True, False, {"hilos": (1, " {nr} ", "x")})
      == {"csv": True, "kopf": False, "hilos": {"aktiv": True, "format": "{nr}", "max": 0}},
      "Dialogergebnis")

# ---- Excel: one sheet per list, label in A1, no header, no merged cells
namen = {"hilos": "Hilos", "bornes": "Bornes", "equipos": "Equipos"}
ordner = tempfile.mkdtemp()
try:
    pfad = os.path.join(ordner, "mp.xlsx")
    check(MP.exportieren(pfad, listen, namen) == ["Hilos", "Bornes", "Equipos"], "Blätter")
    with zipfile.ZipFile(pfad) as zf:
        s2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
    check('<c r="A1" t="inlineStr"><is><t xml:space="preserve">-X1:1</t>' in s2,
          "erste Klemme in A1, ohne Kopfzeile")
    check("mergeCell" not in s2 and "autoFilter" not in s2 and "B1" not in s2,
          "keine verbundenen Zellen, nur Spalte A")
    MP.exportieren(os.path.join(ordner, "k.xlsx"), listen, namen, kopf=True)
    with zipfile.ZipFile(os.path.join(ordner, "k.xlsx")) as zf:
        s2k = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
    check('r="A1"' in s2k and ">Bornes<" in s2k and '<c r="A2" t="inlineStr"><is><t xml:space="preserve">-X1:1' in s2k,
          "mit Kopfzeile")
    # CSV: one file per list, texts unchanged (no apostrophe before '-')
    dateien = MP.exportieren(os.path.join(ordner, "csv"), listen, namen, csv=True)
    check(sorted(os.path.basename(d) for d in dateien) == ["Bornes.csv", "Equipos.csv", "Hilos.csv"],
          "CSV-Dateien")
    with open(os.path.join(ordner, "csv", "Bornes.csv"), encoding="utf-8-sig") as f:
        zeilen = [r[0] for r in csv.reader(f, delimiter=";")]
    check(zeilen == ["-X1:1", "-X1:2", "-X1:10"], f"CSV unverändert: {zeilen}")
finally:
    shutil.rmtree(ordner, ignore_errors=True)

# ---- connection list carries the wire number
vl = DL.verbindungsliste(netz, blaetter, nr)
z = next(r for r in vl if r["von"] == "-K1:2" or r["nach"] == "-K1:2")
check(z["draht"] in nummern, f"Verbindungsliste mit Drahtnummer: {z}")
keys = [sp.key for sp in S._ohne_leere_einbauorte(S.lade_spalten("verbindungen")[0], vl)]
check(keys[:2] == ["pos", "draht"], f"Spalte Hilo: {keys}")
vl0 = DL.verbindungsliste(N.Netz.aufbauen([(0, [k1, m1, L(0, -5, 0, -55)])]), [(0, [])], nr)
check("draht" not in [sp.key for sp in S._ohne_leere_einbauorte(S.lade_spalten("verbindungen")[0], vl0)],
      "ohne Drahtnummern keine Spalte")

print(f"test_mprint - OK ({ok} Pruefungen)")
