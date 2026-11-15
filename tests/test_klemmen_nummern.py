# -*- coding: utf-8 -*-
"""Renumbering terminal strips: by columns / rows / present order, start and step,
format, one terminal drawn twice keeps one number, PE / N kept, other strips and
sheets on disk (dicts), and the app command with a fake dialog."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.electrical import klemmen_nummern as KN
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


def kl(x, y, leiste, num):
    return core.Klemme(x, y, {"IND": leiste, "NUM": num})


def nums(liste):
    return [k.werte["NUM"] if isinstance(k, core.Klemme) else k["werte"]["NUM"] for k in liste]


# sheet 0: a vertical column of -X1 (top to bottom 7, 3, 9), PE, a second column, -X2
a, b, c = kl(0, 0, "-X1", "7"), kl(0, -10, "-X1", "3"), kl(0, -20, "-X1", "9")
pe = kl(0, -30, "-X1", "PE")
d = kl(20, 0, "-X1", "")
x2 = kl(50, 0, "-X2", "5")
blatt0 = [a, b, c, pe, d, x2, core.Linie(0, 0, 1, 1)]
# sheet 1 on disk: terminal 3 drawn again, and a new one
blatt1 = [kl(0, 0, "-X1", "3").to_dict(), kl(10, 0, "-X1", "12").to_dict()]
blaetter = [(0, blatt0), (1, blatt1)]

check(KN.leisten(blaetter) == {"-X1": 7, "-X2": 1}, f"Leisten {KN.leisten(blaetter)}")
check(KN.format_gueltig("{n:02}") and not KN.format_gueltig("X") and not KN.format_gueltig("{m}"),
      "Format prüfen")

plan = KN.planen(blaetter, {"-X1"})
check(("PE", "PE") in [(p[1], p[2]) for p in plan], "PE bleibt (im Plan, unverändert)")
plan = [p for p in plan if p[1] != "PE"]
check([(p[1], p[2]) for p in plan] == [("7", "1"), ("3", "2"), ("9", "3"), ("", "4"), ("12", "5")],
      f"spaltenweise: {[(p[1], p[2]) for p in plan]}")
check(len(plan[1][3]) == 2, "Klemme 3 doppelt gezeichnet = eine Klemme")

plan = [p for p in KN.planen(blaetter, {"-X1"}, {"reihenfolge": "zeilen"}) if p[1] != "PE"]
check([p[1] for p in plan] == ["7", "", "3", "9", "12"], f"zeilenweise: {[p[1] for p in plan]}")

plan = [p for p in KN.planen(blaetter, {"-X1"}, {"reihenfolge": "bestehend", "start": 10,
                                                 "schritt": 2, "format": "{n:03}"}) if p[1] != "PE"]
check([(p[1], p[2]) for p in plan] == [("3", "010"), ("7", "012"), ("9", "014"), ("12", "016"), ("", "018")],
      f"bestehende Reihenfolge, Lücken zu: {[(p[1], p[2]) for p in plan]}")

plan = KN.planen(blaetter, None, {"buchstaben_behalten": False})
check([p[0] for p in plan].count("-X1") == 6 and plan[-1][0] == "-X2" and plan[-1][2] == "1",
      "alle Leisten, PE mitnummeriert, -X2 eigener Zähler")

plan = KN.planen(blaetter, {"-X1"})
check(KN.blaetter_geaendert(plan, blaetter) == {0, 1}, "betroffene Blätter")
n = KN.anwenden(plan)
check(nums([a, b, c, pe, d]) == ["1", "2", "3", "PE", "4"] and nums(blatt1) == ["2", "5"],
      f"angewendet: {nums([a, b, c, pe, d])} {nums(blatt1)}")
check(n == 6 and x2.werte["NUM"] == "5", f"geänderte Klemmen {n}, -X2 unverändert")
check(KN.anwenden(KN.planen(blaetter, {"-X1"})) == 0, "zweiter Lauf ändert nichts")

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
    s1 = [kl(0, 0, "-X1", "4"), kl(0, -10, "-X1", "2"), kl(30, 0, "-X2", "8")]
    with open(p.blatt_pfad(0), "w", encoding="utf-8") as f:
        json.dump({"elemente": []}, f)
    with open(p.blatt_pfad(1), "w", encoding="utf-8") as f:
        json.dump({"elemente": [kl(0, 0, "-X1", "9").to_dict()], "layouts": []}, f)
    fake = SimpleNamespace(projekt=p, root=None, elemente=s1, auswahl=[s1[1]])
    fake.status = SimpleNamespace(set=lambda t: setattr(fake, "meldung", t))
    fake._ist_layout = lambda: False
    fake._blatt_sichern = lambda: True
    fake._snapshot = lambda: setattr(fake, "snap", True)
    fake.redraw = lambda: None
    fake._json_atomar_schreiben = A.CadApp._json_atomar_schreiben
    fake._andere_blaetter_daten = A.CadApp._andere_blaetter_daten.__get__(fake)
    gesehen = {}

    def dialog(root, vorgabe, leisten, gewaehlt, vorschau):
        gesehen.update(leisten=leisten, gewaehlt=gewaehlt,
                       vorschau=vorschau(vorgabe, gewaehlt))
        return SimpleNamespace(result=dict(vorgabe, leisten=gewaehlt))
    A.KlemmenNummernDialog = dialog
    A.CadApp.klemmen_nummerieren(fake)
    check(gesehen["leisten"] == [("-X1", 3), ("-X2", 1)] and gesehen["gewaehlt"] == ["-X1"],
          f"App: Leisten / Auswahl {gesehen['leisten']} {gesehen['gewaehlt']}")
    check(gesehen["vorschau"] == [("-X1", "4", "1"), ("-X1", "2", "2"), ("-X1", "9", "3")],
          f"App: Vorschau {gesehen['vorschau']}")
    check(nums(s1) == ["1", "2", "8"] and fake.snap, "App: offenes Blatt")
    dd = json.load(open(p.blatt_pfad(1), encoding="utf-8"))
    check(dd["elemente"][0]["werte"]["NUM"] == "3", "App: anderes Blatt auf Platte")
    check("leisten" not in Projekt.laden(p.projektdatei).doku["klemmen_nummern"],
          "App: Einstellung gespeichert (ohne Leisten)")
    A.CadApp.klemmen_nummerieren(fake)
    check(fake.meldung == I.tr("msg.kln.nichts"), f"App: zweiter Lauf {fake.meldung}")

print(f"test_klemmen_nummern - OK ({ok} Pruefungen)")
