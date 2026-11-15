# -*- coding: utf-8 -*-
"""Cable duct as a 'line' with a bar length: catalogue (program + project), the drawn
piece stops at the bar length, long pieces become whole bars + rest, article reference
on 2D and 3D ducts, and the duct list (pieces, metres, bars, fittings)."""
import sys, os, json, shutil, tempfile
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "es"
import katiecad.model.core as core
from katiecad.model import kanal_katalog as KK
from katiecad.reports import seiten as S
import katiecad.ui.app as A
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROG = os.path.join(WURZEL, "report_templates")

# ---- catalogue: program file, project file wins, broken file ignored
kat = KK.katalog_laden([PROG])
check(kat["max_laenge"] == 2000 and len(kat["kanaele"]) >= 10, f"Programmkatalog: {len(kat['kanaele'])}")
check(any(k["ref"] == "60.40.77" and k["breite"] == 40 and k["hoehe"] == 60 and k["hersteller"] == "Unex"
          for k in kat["kanaele"]), "Unex 77: 60.40.77 = 40 breit x 60 hoch (alto.ancho)")
check(len(kat["kanaele"]) == 25, "25 Größen der Serie 77")
tmp = tempfile.mkdtemp()
try:
    with open(os.path.join(tmp, KK.DATEI), "w", encoding="utf-8") as f:
        json.dump({"max_laenge": 1500, "kanaele": [{"breite": 40, "hoehe": 60, "hersteller": "Unex",
                                                    "ref": "U77-4060"}, {"breite": "x"}]}, f)
    kp = KK.katalog_laden([PROG, tmp])
    check(kp["max_laenge"] == 1500 and [k["ref"] for k in kp["kanaele"]] == ["U77-4060"]
          and kp["kanaele"][0]["name"] == "40 x 60", f"Projektkatalog hat Vorrang: {kp}")
    with open(os.path.join(tmp, KK.DATEI), "w", encoding="utf-8") as f:
        f.write("{kaputt")
    check(KK.katalog_laden([PROG, tmp])["max_laenge"] == 2000, "kaputte Datei ignoriert")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- the drawn piece stops at the bar length
check(KK.begrenzen((0, 0), (3000, 0)) == (2000.0, 0.0), "auf 2000 begrenzt")
check(KK.begrenzen((0, 0), (300, 400)) == (300, 400), "kürzer bleibt")
x, y = KK.begrenzen((0, 0), (3000, 4000), 1000)
check(abs(x - 600) < 1e-9 and abs(y - 800) < 1e-9, "schräg begrenzt")
check(KK.begrenzen((0, 0), (5000, 0), 0) == (5000, 0), "0 = ohne Grenze")
# long pieces: whole bars + rest
check(KK.aufteilen([(0, 0), (4500, 0)]) == [(0, 0), (2000.0, 0.0), (4000.0, 0.0), (4500, 0)],
      f"4500 -> 2000+2000+500: {KK.aufteilen([(0, 0), (4500, 0)])}")
check(KK.aufteilen([(0, 0), (2000, 0)]) == [(0, 0), (2000, 0)], "genau eine Stange")

# ---- app: 2D tool splits into bars and stores the reference
fake = SimpleNamespace(_kanal_breite=40.0, _kanal_hoehe=60.0, _kanal_schraffur="",
                       _kanal_schraffur_abstand=20.0, _kanal_ausrichtung="mitte",
                       _kanal_ref="U77-4060", _kanal_max=None,
                       _kanal_max_laenge=lambda: 2000.0,
                       _kanal_layer_daten=lambda: {"layer": "CD"})
stuecke = A.CadApp._kanal_stuecke(fake, [(0, 0), (4500, 0), (4500, 1200)])
laengen = [round(s.laenge()) for s in stuecke]
check(len(stuecke) == 4 and laengen[:2] == [2000, 2000] and all(s.ref == "U77-4060" for s in stuecke),
      f"Stangen und Referenz: {laengen}")
d = core.Kabelkanal([(0, 0), (10, 0)], ref="X1").to_dict()
check(d["ref"] == "X1" and core.Kabelkanal(**{k: v for k, v in d.items() if k != "typ"}).ref == "X1",
      "Referenz gespeichert")

# ---- duct list
k2d = [core.Kabelkanal([(0, 0), (2000, 0)], breite=40, hoehe=60, ref="U77-4060"),
       core.Kabelkanal([(0, 100), (500, 100)], breite=40, hoehe=60, ref="U77-4060"),
       core.Kabelkanal([(0, 200), (1200, 200)], breite=60, hoehe=60),
       core.Kabelkanal([(0, 0), (40, 0), (40, 40), (0, 40)], art="winkel", breite=40, hoehe=60)]
k3d = core.Koerper3D("prisma", profil=core.kanal_rechteck((0, 0), (1000, 0), 40), hoehe=60,
                     kanal={"art": "gerade", "breite": 40, "hoehe": 60, "ref": "U77-4060"})
blaetter = [(0, k2d), (1, [k3d])]
zeilen = KK.kanalliste(blaetter, dict(kp, max_laenge=2000.0))
z = next(r for r in zeilen if r["ref"] == "U77-4060")
check(z["stueck"] == "3" and z["laenge"] == "3.50" and z["stangen"] == "2" and z["hersteller"] == "Unex",
      f"40 x 60 mit Referenz (2D + 3D): {z}")
z60 = next(r for r in zeilen if r["masse"] == "60 x 60")
check(z60["stueck"] == "1" and z60["laenge"] == "1.20" and z60["stangen"] == "1", f"60 x 60: {z60}")
w = next(r for r in zeilen if r["art"] == "winkel")
check(w["stueck"] == "1" and w["laenge"] == "" and zeilen[-1] is w, "Formstücke am Ende, ohne Länge")
rows = S.listen_zeilen("kanaele", blaetter, lambda i: i + 1, kanal_katalog=kp)
check(any(r["art"] == I.tr("kanal.bez.winkel") for r in rows), "Art übersetzt")
check("kanaele" in S.LISTEN and [s.key for s in S.lade_spalten("kanaele")[0]][-1] == "stangen",
      "Liste und Spalten")

from katiecad.ui.dialogs import katalog_name
check(katalog_name(kat["kanaele"], 60.0, 40.0).startswith("Unex 77 40.60.77"), "Dialog zeigt die Katalogmaße")
check(katalog_name(kp["kanaele"], 1.0, 1.0, "U77-4060") == "40 x 60", "Referenz geht vor")
check(katalog_name(kat["kanaele"], 33.0, 44.0) == "", "freie Maße")

print(f"test_kanal_katalog - OK ({ok} Pruefungen)")
