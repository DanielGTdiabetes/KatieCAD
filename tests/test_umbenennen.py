# -*- coding: utf-8 -*-
"""Batch renaming of devices with a counter: format with sheet / letters / counter,
counter per letter and per sheet, order by columns or rows, names in use skipped, and
every part of the device follows (auxiliary contacts on other sheets as JSON dicts,
loose masks, single-pole copies, placed 3D models)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.electrical import umbenennen as U
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


VP = core.Verbindungspunkt


def geraet(x, y, ind, rolle="haupt", einpolig=False):
    m = core.ElektroMaske(8, 0)
    m.rolle = rolle
    m.einpolig = einpolig
    sym = [core.Rechteck(-3, -5, 3, 5), VP(0, 5, wert="1", tag="P1"), VP(0, -5, wert="2", tag="P2"), m]
    b = core.BlockReferenz(x, y, "Sym", sym)
    b.attribute.update({"IND": ind})
    return b


# ---- helpers
check(U.kennbuchstaben("-K12") == "K" and U.kennbuchstaben("-10K1") == "K"
      and U.kennbuchstaben("2q1") == "Q" and U.kennbuchstaben("-K") == "K"
      and U.kennbuchstaben("") == "" and U.kennbuchstaben("123") == "", "Kennbuchstaben")
check(U.format_name("{sheet}{kz}{n}", 10, "10", "K", 1) == "10K1", "Format 10K1")
check(U.format_name("-{hoja}{letras}{n:02}", 3, "x", "Q", 4) == "-3Q04", "spanische Platzhalter")
check(U.format_name("{oops}", 2, "", "K", 5) == "2K5", "ungültig -> Standard")
check(U.format_gueltig("-{sheet}{kz}{n}") and not U.format_gueltig("{sheet}{kz}")
      and not U.format_gueltig("{x}{n}"), "Format prüfen")

# ---- sheet 0 (open, objects), sheet 1 (JSON dicts)
k_a = geraet(100, 0, "-K1")              # right column
k_b = geraet(20, 50, "-K7")              # left column, top
k_c = geraet(20, 0, "-K")                # left column, below: prefix only
q1 = geraet(60, 0, "-Q1")
k1_hilf = geraet(140, 0, "-K1", rolle="hilfs")
k7_einpolig = geraet(200, 0, "-K7", einpolig=True)
lose = core.ElektroMaske(300, 0, {"IND": "-K1"}, rolle="hilfs")
fremd = geraet(400, 0, "-K10")           # not selected, its name is in use
koerper = core.Koerper3D("netz", netzdaten={"p": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "k": [[0, 1]],
                                            "f": [[0, 1, 2]]}, bez="-K1", geraet="-K1")
gruppe = core.Gruppe3D(teile=[core.Koerper3D("netz", netzdaten=dict(koerper.netzdaten), bez="X",
                                             geraet="-K7")])
blatt0 = [k_a, k_b, k_c, q1, k1_hilf, k7_einpolig, lose, fremd, koerper, gruppe]
k2 = geraet(0, 0, "-K2")
blatt1 = [e.to_dict() for e in (geraet(50, 0, "-K1", rolle="hilfs"), geraet(80, 0, "-K7", rolle="hilfs"))]
blatt1_k2 = k2.to_dict()
blatt1.append(blatt1_k2)
blaetter = [(0, blatt0), (9, blatt1)]

auswahl = [k_a, k_b, k_c, q1, k1_hilf]   # an auxiliary part in the selection is ignored
plan = U.planen(blaetter, auswahl, {"format": "{sheet}{kz}{n}", "start": 10, "schritt": 1},
                sheet_nr=lambda b: 10)
namen = [(a if isinstance(a, str) else "<-K>", n) for a, n in plan]
check(namen == [("-K7", "10K10"), ("<-K>", "10K11"), ("-Q1", "10Q10"), ("-K1", "10K12")],
      f"Reihenfolge Spalten, Zähler je Buchstabe: {namen}")

# names in use are skipped
fremd.attribute["IND"] = "10K11"
plan = U.planen(blaetter, auswahl, {"format": "{sheet}{kz}{n}", "start": 10}, sheet_nr=lambda b: 10)
check([n for _a, n in plan] == ["10K10", "10K12", "10Q10", "10K13"], f"belegte Namen übersprungen: {plan}")
fremd.attribute["IND"] = "-K10"

# rows order, step
plan = U.planen(blaetter, auswahl, {"format": "-{kz}{n}", "start": 1, "schritt": 2,
                                    "reihenfolge": "zeilen"})
check([n for _a, n in plan] == ["-K1", "-K3", "-Q1", "-K5"], f"Zeilen + Schritt: {plan}")
plan = U.planen(blaetter, [k_a], {"format": "-{kz}{n}", "start": 7})
check(plan == [("-K1", "-K8")], f"-K7 bleibt belegt (nicht ausgewählt): {plan}")

# ---- apply: all parts follow
plan = U.planen(blaetter, auswahl, {"format": "{sheet}{kz}{n}", "start": 1}, sheet_nr=lambda b: 10)
geaendert = U.anwenden(plan, blaetter)
check(k_a.attribute["IND"] == "10K3" and k_b.attribute["IND"] == "10K1"
      and k_c.attribute["IND"] == "10K2" and q1.attribute["IND"] == "10Q1", "Hauptsymbole")
check(k1_hilf.attribute["IND"] == "10K3" and lose.werte["IND"] == "10K3", "Hilfskontakte und lose Maske")
check(k7_einpolig.attribute["IND"] == "10K1", "einpolige Kopie folgt")
check(fremd.attribute["IND"] == "-K10", "nicht ausgewähltes Gerät bleibt")
check(koerper.geraet == "10K3" and koerper.bez == "10K3", "3D-Modell folgt (mit Bezeichnung)")
check(gruppe.teile[0].geraet == "10K1" and gruppe.teile[0].bez == "X", "3D-Gruppe, eigene Bezeichnung bleibt")
check(blatt1[0]["attribute"]["IND"] == "10K3" and blatt1[1]["attribute"]["IND"] == "10K1"
      and blatt1[2]["attribute"]["IND"] == "-K2", "andere Seite (JSON) folgt, -K2 bleibt")
check(geaendert == {0: 9, 9: 2}, f"geänderte Felder je Blatt: {geaendert}")

# ---- swapping names in one run
a, b = geraet(0, 0, "-K1"), geraet(10, 0, "-K2")
h = geraet(20, 0, "-K2", rolle="hilfs")
bl = [(0, [b, a, h])]
plan = U.planen(bl, [a, b], {"format": "-{kz}{n}", "start": 1, "reihenfolge": "zeilen"})
check(plan == [("-K1", "-K1"), ("-K2", "-K2")], f"gleiche Namen: {plan}")
plan = U.planen(bl, [a, b], {"format": "-{kz}{n}", "start": 1, "reihenfolge": "zeilen"})
plan = [("-K1", "-K2"), ("-K2", "-K1")]
U.anwenden(plan, bl)
check(a.attribute["IND"] == "-K2" and b.attribute["IND"] == "-K1" and h.attribute["IND"] == "-K1",
      "Tausch in einem Schritt")

# ---- placeholder IND is never renamed
check(U.planen([(0, [geraet(0, 0, "IND")])], None, {}) == [], "Platzhalter IND")

# ---- app: selection on the open sheet, contacts on the other sheet (on disk) follow
import json, tempfile
from types import SimpleNamespace
import katiecad.ui.app as A
from katiecad.model.project import Projekt
A.messagebox = SimpleNamespace(showerror=lambda *a, **k: None)
with tempfile.TemporaryDirectory() as tmp:
    p = Projekt.erstellen("Anlage", tmp)
    for nm in ("Leistung", "Steuerung"):
        p.blatt_hinzufuegen(nm)
    p.aktiv = 0
    s1 = [geraet(0, 0, "-K1"), geraet(40, 0, "-K2"), geraet(80, 0, "-Q1")]
    s2 = [geraet(0, 0, "-K1", rolle="hilfs"), geraet(30, 0, "-K2", rolle="hilfs")]
    with open(p.blatt_pfad(0), "w", encoding="utf-8") as f:
        json.dump({"elemente": []}, f)
    with open(p.blatt_pfad(1), "w", encoding="utf-8") as f:
        json.dump({"elemente": [e.to_dict() for e in s2], "layouts": []}, f)
    fake = SimpleNamespace(projekt=p, root=None, elemente=s1, auswahl=[s1[0], s1[1]],
                           _qv_cache={}, _ge_cache={})
    fake.status = SimpleNamespace(set=lambda t: setattr(fake, "meldung", t))
    fake._ist_layout = lambda: False
    fake._blatt_sichern = lambda: True
    fake._snapshot = lambda: setattr(fake, "snap", True)
    fake.redraw = lambda: None
    fake._json_atomar_schreiben = A.CadApp._json_atomar_schreiben
    fake._andere_blaetter_daten = A.CadApp._andere_blaetter_daten.__get__(fake)
    gesehen = {}

    def dialog(root, vorgabe, bereiche, vorschau):
        gesehen["bereiche"] = bereiche
        gesehen["vorschau"] = vorschau(dict(vorgabe, format="{sheet}{kz}{n}"), "auswahl")
        return SimpleNamespace(result=dict(vorgabe, format="{sheet}{kz}{n}", bereich="auswahl"))
    A.UmbenennenDialog = dialog
    A.CadApp.geraete_umbenennen(fake)
    check(gesehen["bereiche"] == ["auswahl", "blatt", "projekt"], f"App: Bereiche {gesehen['bereiche']}")
    check(gesehen["vorschau"] == [("-K1", "1K1"), ("-K2", "1K2")], f"App: Vorschau {gesehen['vorschau']}")
    check([e.attribute["IND"] for e in s1] == ["1K1", "1K2", "-Q1"] and fake.snap, "App: offenes Blatt")
    d = json.load(open(p.blatt_pfad(1), encoding="utf-8"))
    check([e["attribute"]["IND"] for e in d["elemente"]] == ["1K1", "1K2"],
          "App: Kontakte auf dem anderen Blatt (Platte) folgen")
    check(Projekt.laden(p.projektdatei).doku["umbenennen"]["format"] == "{sheet}{kz}{n}"
          and "bereich" not in Projekt.laden(p.projektdatei).doku["umbenennen"],
          "App: Einstellung im Projekt gespeichert")
    A.CadApp.geraete_umbenennen(fake)
    check(fake.meldung == I.tr("msg.umb.nichts"), f"App: zweiter Lauf ändert nichts: {fake.meldung}")

print(f"test_umbenennen - OK ({ok} Pruefungen)")
