# -*- coding: utf-8 -*-
"""Terminal strip editor (data part): rows in mounting order, one row per terminal drawn
twice, editing fields / partition plate / jumper / order, renumbering in table order,
explicit mounting position only when needed, jumpers and order in the terminal diagram,
renumbering a strip clears the position, and the app command with a fake dialog."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.electrical import klemmenleiste as KL, klemmen_nummern as KN
from katiecad.reports import netz as N, daten as D
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


def kl(x, y, leiste, num, **kw):
    return core.Klemme(x, y, {"IND": leiste, "NUM": num, "TYP": "TYP", "MAN": "MAN", "PER": "PER"}, **kw)


# sheet 0 (objects): -X1 3, 1, PE, 2 ; sheet 1 (dicts): 1 drawn again, -X2
s0 = [kl(0, 0, "-X1", "3"), kl(10, 0, "-X1", "1"), kl(20, 0, "-X1", "PE"), kl(30, 0, "", "2"),
      kl(40, 0, "-X1", "")]
s1 = [kl(0, 0, "-X1", "1").to_dict(), kl(0, 0, "-X2", "1").to_dict()]
blaetter = [(0, s0), (1, s1)]

rows = KL.zeilen(blaetter, "-X1")
check([z["num"] for z in rows] == ["1", "2", "3", "PE", ""], f"Montagefolge nach Nummer: {[z['num'] for z in rows]}")
check(rows[0]["anzahl"] == 2 and rows[0]["typ"] == "" and not rows[0]["trenn"], "doppelt gezeichnet = eine Zeile")
check(KL.pruefen(rows) == [(4, "leer")], "Prüfung: leere Nummer")
blatt_geerbt = [kl(0, 0, "-X1", "5").to_dict(), kl(10, 0, "IND", "6").to_dict()]
rows_geerbt = KL.zeilen([(1, blatt_geerbt)], "-X1")
check([z["num"] for z in rows_geerbt] == ["5", "6"], "geerbte Leiste im gespeicherten Blatt")
rows_geerbt[1]["num"] = "7"
check(KL.anwenden(rows_geerbt) == 1 and blatt_geerbt[1]["werte"]["NUM"] == "7"
      and blatt_geerbt[1]["werte"]["IND"] == "IND", "geerbte Klemme wird gespeichert")

# ---- edit: PE between 1 and 2, type for all, jumper 1-PE top, plate after 3
rows = [rows[0], rows[3], rows[1], rows[2], rows[4]]
for z in rows:
    z["typ"] = "WDU 2.5"
rows[0]["bruecke"] = "oben"
rows[3]["trenn"] = True
rows[4]["num"] = "4"
rows[4]["bruecke"] = "unten"                # last row: dropped
n = KL.anwenden(rows)
check(n == 6, f"geänderte Zeichnungen {n}")
check([k.montage for k in s0] == [3, 0, 1, 2, 4] and s1[0]["montage"] == 0, "Montageposition gespeichert")
check(s0[1].bruecke == "oben" and s1[0]["bruecke"] == "oben" and s0[4].bruecke == "", "Brücke, letzte ohne")
check(s0[0].trennplatte and s0[0].werte["TYP"] == "WDU 2.5" and s1[0]["werte"]["TYP"] == "WDU 2.5"
      and s0[4].werte["NUM"] == "4", "Felder auf alle Zeichnungen")
check(s0[1].werte["MAN"] == "MAN", "leeres Feld lässt Platzhalter")
check(s1[1]["werte"]["TYP"] == "TYP" and "montage" not in s1[1], "andere Leiste unberührt")
check(KL.blaetter_von(rows, blaetter) == {0, 1}, "betroffene Blätter")
check(KL.anwenden(rows) == 0, "zweimal = keine Änderung")
rows2 = KL.zeilen(blaetter, "-X1")
check([z["num"] for z in rows2] == ["1", "PE", "2", "3", "4"], f"neu gelesen in Montagefolge {[z['num'] for z in rows2]}")

# ---- terminal diagram: order and stored jumper
s1_obj = [core.Klemme(**{k: v for k, v in d.items() if k != "typ"}) for d in s1]
bl = [(0, s0), (1, s1_obj)]
kp = [z for z in D.klemmenplan(N.Netz.aufbauen(bl), bl, lambda i: i + 1) if z["leiste"] == "-X1"]
check([z["num"] for z in kp] == ["1", "1", "PE", "2", "3", "4"], f"Klemmenplan-Folge {[z['num'] for z in kp]}")
check(any(b for b in kp[1].get("_bruecke_s", []) if b[0] == "oben") and "PE" in kp[0].get("bruecke", ""),
      f"Brücke 1-PE oben im Klemmenplan: {kp[0].get('bruecke')} {kp[1].get('_bruecke_s')}")
check(not kp[3].get("_bruecke_s"), "2 ohne Brücke")

# ---- table order equal to the numbers: no position stored; renumber in table order
rows = KL.nach_nummer_sortiert(KL.zeilen(blaetter, "-X1"))
check([z["num"] for z in rows] == ["1", "2", "3", "4", "PE"], "nach Nummer sortiert")
KL.anwenden(rows)
check(all(k.montage is None for k in s0) and "montage" not in s1[0], "keine Position bei Nummernfolge")
rows = KL.zeilen(blaetter, "-X1")
rows = [rows[2], rows[0], rows[4], rows[1], rows[3]]           # 3, 1, PE, 2, 4
KL.umnummerieren(rows, 1, "{n:02}")
check([z["num"] for z in rows] == ["01", "02", "PE", "03", "04"], f"in Tabellenfolge nummeriert {[z['num'] for z in rows]}")
KL.anwenden(rows)
check(s0[0].werte["NUM"] == "01" and s1[0]["werte"]["NUM"] == "02" and s0[2].montage == 2,
      "PE behält Platz 3 (Position gespeichert)")

# ---- renumbering the strip (keep order) follows the mounting order and clears it
plan = KN.planen(blaetter, {"-X1"}, {"reihenfolge": "bestehend", "buchstaben_behalten": False})
check([p[1] for p in plan] == ["01", "02", "PE", "03", "04"], f"bestehend = Montagefolge {[p[1] for p in plan]}")
KN.anwenden(KN.planen(blaetter, {"-X1"}, {"reihenfolge": "bestehend"}))
check(all(k.montage is None for k in s0) and "montage" not in s1[0],
      "Neunummerieren löscht die Position")

# ---- targets from the terminal diagram rows
idx = KL.ziele_index([{"_blatt": 0, "_pos": (10.0, 0.0), "oben": ["-K1:A1"], "unten": []}])
rows = KL.zeilen(blaetter, "-X1", idx)
check(any(z["oben"] == "-K1:A1" for z in rows), "Ziele aus dem Klemmenplan")

# ---- app
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
    a1 = [kl(0, 0, "-X1", "2"), kl(10, 0, "-X1", "1")]
    with open(p.blatt_pfad(0), "w", encoding="utf-8") as f:
        json.dump({"elemente": []}, f)
    with open(p.blatt_pfad(1), "w", encoding="utf-8") as f:
        json.dump({"elemente": [kl(0, 0, "-X1", "3").to_dict()], "layouts": []}, f)
    fake = SimpleNamespace(projekt=p, root=None, elemente=a1, auswahl=[a1[0]])
    fake.status = SimpleNamespace(set=lambda t: setattr(fake, "meldung", t))
    fake._ist_layout = lambda: False
    fake._blatt_sichern = lambda: True
    fake._snapshot = lambda: setattr(fake, "snap", True)
    fake.redraw = lambda: None
    fake._json_atomar_schreiben = A.CadApp._json_atomar_schreiben
    fake._andere_blaetter_daten = A.CadApp._andere_blaetter_daten.__get__(fake)
    fake._klemmen_ziele = lambda: {}
    gesehen = {}

    def dialog(root, leisten, start, laden):
        gesehen.update(leisten=leisten, start=start)
        r = laden("-X1")
        gesehen["nums"] = [z["num"] for z in r]
        r = [r[2], r[0], r[1]]
        r[0]["bruecke"] = "beide"
        return SimpleNamespace(result={"-X1": r})
    A.KlemmenleisteDialog = dialog
    A.CadApp.klemmenleiste_bearbeiten(fake)
    check(gesehen["leisten"] == ["-X1"] and gesehen["start"] == "-X1" and gesehen["nums"] == ["1", "2", "3"],
          f"App: Dialog {gesehen}")
    check(a1[1].montage == 1 and a1[0].montage == 2 and fake.snap, "App: offenes Blatt")
    d = json.load(open(p.blatt_pfad(1), encoding="utf-8"))
    check(d["elemente"][0]["montage"] == 0 and d["elemente"][0]["bruecke"] == "beide",
          "App: anderes Blatt auf Platte")

print(f"test_klemmenleiste - OK ({ok} Pruefungen)")
