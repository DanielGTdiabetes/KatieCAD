# -*- coding: utf-8 -*-
"""Terminal diagram: external / internal side, wire number, cable and conductor
per side, partition plates, terminal strip drawing and Excel with one sheet
per strip."""
import sys, os, json, shutil, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as katiecad_i18n; katiecad_i18n.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.reports import netz as N, daten as D, seiten as S, anwenden as ANW
from katiecad.reports import leistenbild as LB
from katiecad.electrical.drahtnummern import netz_nummern
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


VP = core.Verbindungspunkt
L = core.Leitung
nr = lambda i: i + 1


def geraet(x, y, ind):
    """Two-pin device: pin 1 at (x, y+5), pin 2 at (x, y-5)."""
    sym = [core.Rechteck(-5, -5, 5, 5), VP(0, 5, wert="1", tag="P1"),
           VP(0, -5, wert="2", tag="P2"), core.ElektroMaske(8, 0)]
    b = core.BlockReferenz(x, y, "Sym", sym)
    b.attribute.update({"IND": ind, "TYP": "", "PER": ""})
    return b


def blatt(mit_nummern=True, farbe=""):
    """K1 above terminal X1:1, X1:1 bottom -> cable -W3 (core BN) -> M1.
    X1:2 is bridged with X1:1 on top and carries a partition plate."""
    k1 = geraet(0, 0, "-K1")                       # pins (0,5) (0,-5)
    x1 = core.Klemme(0, -30, {"IND": "-X1", "NUM": "1", "TYP": "UT 2,5"})
    x2 = core.Klemme(10, -30, {"NUM": "2", "TYP": "UT 2,5"}, trennplatte=True)
    m1 = geraet(0, -85, "-M1")                     # pin 1 at (0,-80)
    kb = core.Kabel(-10, -55, {"CAB": "-W3", "TYP": "4G1,5"}, laenge=40)
    kb.kreuzungen = [0.0]
    kb.adern[kb.ader_schluessel(10.0)] = "BN"
    el = [k1, x1, x2, m1, kb,
          L(0, -5, 0, -29),                        # K1:2 -> X1:1 top
          L(0, -29, 10, -29),                      # bridge X1:1 top -> X1:2 top
          L(0, -31, 0, -80)]                       # X1:1 bottom -> cable -> M1:1
    if mit_nummern:
        el.append(core.Drahtnummer(0, -15, "101", auto_text="101", aderfarbe=farbe,
                                   querschnitt="2,5" if farbe else ""))
        el.append(core.Drahtnummer(0, -40, "102", auto_text="102"))
    return el


# ---- wire numbers in the net
el = blatt()
n = N.Netz.aufbauen([(0, el)])
x1 = n.klemmen[0]
check(x1["oben"].draht == "101" and x1["unten"].draht == "102",
      f"Drahtnummer je Klemmenseite: {x1['oben'].draht} / {x1['unten'].draht}")
check(netz_nummern(n, [(0, blatt(False))]) == 0, "ohne Etiketten keine Nummern")

# ---- automatic sides: the side with the cable is external
kp = D.klemmenplan(n, [(0, el)], nr)
z = kp[0]
check(z["num"] == "1" and z["_seiten"] == {"intern": "oben", "extern": "unten"},
      f"auto: Kabel unten = extern: {z['_seiten']}")
check(z["intern_draht"] == "101" and z["extern_draht"] == "102",
      f"Draht intern/extern: {z['intern_draht']} / {z['extern_draht']}")
check(any("-K1:2" in t for t in z["intern"]), f"Ziel intern: {z['intern']}")
check(any(t.startswith("-M1:1") for t in z["extern"]), f"Ziel extern: {z['extern']}")
check(z["extern_kabel"] == ["-W3 / BN"], f"Kabel / Ader: {z['extern_kabel']}")
check(z["extern_farbe"] == "BN" and z["extern_querschnitt"] == "1,5",
      f"Farbe aus Adername, Querschnitt aus Kabeltyp: {z['extern_farbe']} {z['extern_querschnitt']}")
check(z["extern_leiter"] == "BN 1,5 mm²", f"Leitertext: {z['extern_leiter']}")
check(z["intern_kabel"] == [] and z["intern_leiter"] == "", "intern ohne Kabel")
check(z["oben"] == z["intern"] and z["unten"] == z["extern"], "oben/unten bleiben erhalten")
check(kp[1]["_trenn"] and not z["_trenn"], "Trennplatte aus der Klemme")
check(kp[1]["intern_draht"] == "101", "Brücke: gleicher Draht an der zweiten Klemme")

# ---- fixed modes
kp = D.klemmenplan(n, [(0, el)], nr, seiten="unten_intern")
check(kp[0]["intern_draht"] == "102" and kp[0]["extern_draht"] == "101", "unten intern")
kp = D.klemmenplan(n, [(0, el)], nr, seiten="oben_unten")
check(kp[0]["extern_draht"] == "101", "oben/unten: oben in der ersten Spalte")
titel = lambda modus: {sp.key: sp.titel for sp in S.lade_spalten("klemmen", (), modus)[0]}
check(titel("oben_unten")["extern"] == "Ziel oben" and titel("oben_unten")["intern_draht"]
      == "Draht unten", "Spaltentitel oben/unten")
check(titel("auto")["extern"] == "Ziel extern", "Spaltentitel extern")

# ---- manual colour / cross-section on the wire number
el2 = blatt(farbe="BU")
kp = D.klemmenplan(N.Netz.aufbauen([(0, el2)]), [(0, el2)], nr)
check(kp[0]["intern_leiter"] == "BU 2,5 mm²", f"Farbe/Querschnitt am Etikett: {kp[0]['intern_leiter']}")

# ---- empty columns disappear
el3 = blatt(False)
kp3 = D.klemmenplan(N.Netz.aufbauen([(0, el3)]), [(0, el3)], nr)
keys = [sp.key for sp in S._ohne_leere_einbauorte(S.lade_spalten("klemmen")[0], kp3)]
check("extern_draht" not in keys and "extern_kabel" in keys and "intern_kabel" not in keys,
      f"leere Spalten weg: {keys}")
check(D.querschnitt_aus_typ("ÖLFLEX 3x2.5") == "2.5" and D.querschnitt_aus_typ("NYM") == "",
      "Querschnitt aus Typ")

# ---- terminal strip drawing
kp = D.klemmenplan(n, [(0, el)], nr)
flaeche = (10.0, 40.0, 285.0, 200.0)
seiten = LB.leistenbild_seiten(kp, flaeche, "Klemmenleistenbild", 1.0, "Klemmenleiste {leiste}")
check(len(seiten) == 1 and seiten[0].kopf == ("", "-X1"), f"eine Seite je Leiste: {len(seiten)}")
texte = [e for e in seiten[0] if isinstance(e, core.Text)]
inhalte = [t.inhalt for t in texte]
check("Klemmenleiste -X1" in inhalte and "-W3" in inhalte, f"Kopf und Kabel: {inhalte[:6]}")
check(any(t.inhalt == "102" and t.winkel == 90.0 for t in texte), "Drahtnummer senkrecht")
check(sum(isinstance(e, core.Schraffur) for e in seiten[0]) >= 2,
      "Trennplatte und Brückenpunkte gefüllt")
ausser = [e for e in seiten[0] if isinstance(e, (core.Linie, core.Rechteck))
          and not (flaeche[0] - 1 <= e.bbox()[0] and e.bbox()[2] <= flaeche[2] + 1
                   and flaeche[1] - 1 <= e.bbox()[1] and e.bbox()[3] <= flaeche[3] + 1)]
check(not ausser, f"alles innerhalb der Fläche: {len(ausser)}")

# colours as in panel tools: PE green-yellow, N blue, others grey; screws and DIN rail
check([LB.klemmen_art(z) for z in ({"num": "PE"}, {"num": "7", "typ": "UT 2,5-PE"},
                                    {"num": "N"}, {"num": "3", "typ": "UT 2,5 BU"},
                                    {"num": "3", "typ": "UT 2,5"})] == ["pe", "pe", "n", "n", ""],
      "Klemmenart aus Nummer/Typ")
farben = {e.farbe for e in seiten[0] if isinstance(e, core.Schraffur) and e.eig_farbe}
check(LB.FARBE_KLEMME in farben and LB.FARBE_SCHIENE in farben, f"Klemmen grau, Tragschiene: {farben}")
check(sum(isinstance(e, core.Kreis) for e in seiten[0]) == 2 * len(kp), "zwei Schrauben je Klemme")

# many terminals -> several pages, two strips -> separate pages
viele = []
for i in range(60):
    viele.append(core.Klemme(i * 10, 0, {"IND": "-X5" if i < 50 else "-X6", "NUM": str(i + 1)}))
kv = D.klemmenplan(N.Netz.aufbauen([(0, viele)]), [(0, viele)], nr)
sv = LB.leistenbild_seiten(kv, flaeche)
check([s.kopf[1] for s in sv] == ["-X5", "-X5", "-X6"], f"Umbruch je Leiste: {[s.kopf for s in sv]}")

# ---- report sheets
vorne, hinten = S.berichte_erzeugen([S.BlattInfo("1", el)], "P", {}, {"klemmen", "leistenbild"},
                                    None, "de")
namen = [s.name for s in hinten]
check(any(nm.startswith("Klemmenleistenbild") for nm in namen)
      and any(nm.startswith("Klemmenplan") for nm in namen), f"Berichtsseiten: {namen}")

# ---- Excel: one sheet per strip
tab = S.tabellen_fuer_export([(0, viele + el)], nr)
ordner = tempfile.mkdtemp()
try:
    pfad = os.path.join(ordner, "k.xlsx")
    blaetter = ANW.xlsx_exportieren(pfad, tab, {"klemmen": "Klemmenplan"}, ["klemmen"])
    check(blaetter == ["-X1", "-X5", "-X6"], f"ein Excel-Blatt je Leiste: {blaetter}")
    with zipfile.ZipFile(pfad) as zf:
        x = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    check("102" in x and "-W3 / BN" in x, "Drahtnummer und Kabel im Excel")
finally:
    shutil.rmtree(ordner, ignore_errors=True)

# ---- save / load
d = json.loads(json.dumps(core.Drahtnummer(0, 0, "5", aderfarbe="BK").to_dict()))
check(d.get("aderfarbe") == "BK" and "querschnitt" not in d, "Drahtnummer speichert nur gesetzte Werte")
check(core.Drahtnummer(**{k: v for k, v in d.items() if k != "typ"}).aderfarbe == "BK", "laden")
dk = core.Klemme(0, 0, trennplatte=True).to_dict()
check(dk.get("trennplatte") is True and "trennplatte" not in core.Klemme(0, 0).to_dict(),
      "Trennplatte nur gespeichert wenn gesetzt")

print(f"test_klemmenplan - OK ({ok} Pruefungen)")
