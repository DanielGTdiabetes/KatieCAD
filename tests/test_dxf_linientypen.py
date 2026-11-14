# -*- coding: utf-8 -*-
"""Line types in the DXF / DWG export: names, patterns, layout patterns back to
the type, DWG table + entity attribute, and (when ezdxf is installed) a DXF round
trip through the KatieCAD DXF import."""
import sys, os, tempfile, shutil
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.fileio import dxf_linientypen as DLT
from katiecad.fileio import dwg_schreiben as DW
from katiecad.fileio.cad_import import _linientyp_name
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


# ---- names and patterns
check(DLT.dxf_name("Volllinie (schmal)") is None and DLT.attribute("Volllinie (breit)") == {},
      "Volllinie ohne Linientyp")
check(DLT.attribute("Strich-Zweipunktlinie") == {"linetype": "DIVIDE"}, "Strich-Zweipunkt = DIVIDE")
check(DLT.attribute(None) == {} and DLT.attribute("gibt es nicht") == {}, "unbekannt: nichts")
m = DLT.muster("Strichpunktlinie (Achse)")
check(m[0] == round(sum(abs(v) for v in m[1:]), 4) and m[1] > 0 and m[2] < 0 and len(m) == 5,
      f"Muster Strichpunkt: {m}")
check(DLT.dashes("Punktlinie")[0] == 0.0 and DLT.dashes("Punktlinie")[1] < 0, "Punktlinie = Punkte")
# every exported name is read back as the same line type by the DXF import
for k, name in DLT.DXF_NAMEN.items():
    if k in ("Freihandlinie", "Schraffur"):
        continue
    check(_linientyp_name(name) == k, f"Import erkennt {name} als {k}: {_linientyp_name(name)}")

# ---- layout / project export only knows the PDF dash pattern
for k in DLT.DXF_NAMEN:
    check(DLT.schluessel_aus_dash(DLT.pdf_dash(k)) == k, f"Muster -> Typ: {k}")
check(DLT.schluessel_aus_dash(None) is None and DLT.schluessel_aus_dash((9.9, 9.9)) is None,
      "fremdes Muster: kein Typ")


# ---- ezdxf documents: definitions are added once
class Tabelle(dict):
    def add(self, name, pattern, description=""):
        self[name] = (pattern, description)


doc = SimpleNamespace(linetypes=Tabelle())
namen = DLT.definieren(doc)
check(namen == set(DLT.DXF_NAMEN.values()) and set(doc.linetypes) == namen,
      f"LTYPE-Tabelle: {sorted(doc.linetypes)}")
check(DLT.definieren(SimpleNamespace()) == set(), "Dokument ohne LTYPE-Tabelle")
check(DLT.attribute("Punktlinie", set()) == {} and DLT.attribute("Punktlinie", {"DOT"})
      == {"linetype": "DOT"}, "nur definierte Linientypen verwenden")
doc.linetypes["DASHED"] = "eigene"
DLT.definieren(doc)
check(doc.linetypes["DASHED"] == "eigene", "vorhandene Definition bleibt")

# ---- DWG: table and entity attribute
bericht = DW.SchreibBericht()
s = DW._Schreiber(SimpleNamespace(linetypes={}), bericht, "AC1032")
s.linientypen()
check(set(s.d.linetypes) == set(DLT.DXF_NAMEN.values())
      and s.d.linetypes["CENTER"]["dashes"] == DLT.dashes("Strichpunktlinie (Achse)"),
      "DWG-Linientypen")


class Ent:
    def __init__(self, **dxf):
        self.dxf = SimpleNamespace(**dxf)


check(DW._flaeche_kw(Ent(layer="E", linetype="DIVIDE")).get("linetype") == "DIVIDE",
      "DWG-Element mit Linientyp")
check("linetype" not in DW._flaeche_kw(Ent(layer="E", linetype="BYLAYER")), "BYLAYER bleibt weg")
s2 = DW._Schreiber(SimpleNamespace(), DW.SchreibBericht(), "AC1015")     # no table support
s2.linientypen()
check("linetype" not in DW._flaeche_kw(Ent(layer="E", linetype="DIVIDE")) and s2.b.fehler,
      "ohne Tabelle kein Verweis auf fehlende Linientypen")

# ---- real round trip with ezdxf (optional)
try:
    import ezdxf
except ImportError:
    ezdxf = None
if ezdxf is not None:
    import katiecad.ui.app as A
    app = A.CadApp.__new__(A.CadApp)
    l1 = core.Leitung(0, 0, 0, -20, linientyp="Strich-Zweipunktlinie")
    l2 = core.Linie(10, 0, 10, -20, linientyp="Punktlinie")
    l3 = core.Linie(20, 0, 20, -20)
    d = ezdxf.new(dxfversion="R2010")
    app._dxf_lt_namen = DLT.definieren(d)
    msp = d.modelspace()
    for e in (l1, l2, l3):
        app._element_zu_dxf(msp, e)
    ordner = tempfile.mkdtemp()
    try:
        pfad = os.path.join(ordner, "lt.dxf")
        d.saveas(pfad)
        d2 = ezdxf.readfile(pfad)
        lts = sorted(e.dxf.linetype for e in d2.modelspace())
        check(lts == ["BYLAYER", "DIVIDE", "DOT"], f"DXF-Datei: {lts}")
        check("DIVIDE" in d2.linetypes, "LTYPE in der Datei")
    finally:
        shutil.rmtree(ordner, ignore_errors=True)
    print("(mit ezdxf)")
else:
    print("(ezdxf nicht installiert: Rundreise übersprungen)")

print(f"test_dxf_linientypen - OK ({ok} Pruefungen)")
