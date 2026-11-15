# -*- coding: utf-8 -*-
"""
katiecad/fileio/dxf_linientypen.py - Line types for the DXF / DWG export (NO Tkinter).

KatieCAD stores line types by name (LINIENTYPEN in model.core) with a screen dash
pattern in pixels. For DXF/DWG they are written as simple LTYPE definitions in
millimetres, scaled like the PDF output (factor 0.45), under the usual AutoCAD
names so other programs (and the KatieCAD DXF import) recognise them:

    Strichlinie (verdeckt)   -> DASHED
    Strichpunktlinie (Achse) -> CENTER
    Strich-Zweipunktlinie    -> DIVIDE
    Punktlinie               -> DOT
    Freihandlinie / Schraffur -> KATIE_FREIHAND / KATIE_SCHRAFFUR
Continuous types get no linetype (BYLAYER).
"""

from katiecad.model.core import LINIENTYPEN

FAKTOR = 0.45           # screen pixels -> mm, the same as the PDF output
MIN_STRICH = 0.3        # mm, like the PDF output

DXF_NAMEN = {
    "Strichlinie (verdeckt)": "DASHED",
    "Strichpunktlinie (Achse)": "CENTER",
    "Strich-Zweipunktlinie": "DIVIDE",
    "Punktlinie": "DOT",
    "Freihandlinie": "KATIE_FREIHAND",
    "Schraffur": "KATIE_SCHRAFFUR",
}
BESCHREIBUNG = {
    "DASHED": "Dashed __ __ __", "CENTER": "Center ____ _ ____ _",
    "DIVIDE": "Divide ____ . . ____ . .", "DOT": "Dot . . . .",
    "KATIE_FREIHAND": "KatieCAD freehand", "KATIE_SCHRAFFUR": "KatieCAD hatch",
}
PUNKT = {"Punktlinie"}       # its short dashes are written as true dots (0 length)


def pdf_dash(schluessel):
    """Dash pattern of the PDF output (mm) or None for continuous lines."""
    lt = LINIENTYPEN.get(schluessel)
    if not lt or not lt["dash"]:
        return None
    return tuple(max(MIN_STRICH, d * FAKTOR) for d in lt["dash"])


def dxf_name(schluessel):
    """DXF linetype name of a KatieCAD line type, None = continuous (BYLAYER)."""
    return DXF_NAMEN.get(schluessel) if pdf_dash(schluessel) else None


def dashes(schluessel):
    """Signed dash list (dash > 0, gap < 0, dot = 0) in mm."""
    d = pdf_dash(schluessel) or ()
    out = []
    for i, v in enumerate(d):
        if i % 2:
            out.append(-round(v, 4))
        else:
            out.append(0.0 if schluessel in PUNKT else round(v, 4))
    return out


def muster(schluessel):
    """ezdxf simple pattern: [total length, dash, -gap, ...]."""
    ds = dashes(schluessel)
    return [round(sum(abs(v) for v in ds), 4)] + ds


def schluessel_aus_dash(dash):
    """KatieCAD line type of a PDF dash pattern (the layout export only knows the
    pattern) - None if it matches none."""
    if not dash:
        return None
    dash = tuple(round(v, 4) for v in dash)
    for k in DXF_NAMEN:
        d = pdf_dash(k)
        if d and tuple(round(v, 4) for v in d) == dash:
            return k
    return None


def definieren(doc):
    """Adds the LTYPE definitions to an ezdxf document (existing ones are kept).
    -> set of names that exist in the document afterwards (empty if the document
    has no linetype table); only these may be referenced by entities."""
    tabelle = getattr(doc, "linetypes", None)
    if tabelle is None:
        return set()
    out = set()
    for k, name in DXF_NAMEN.items():
        if not pdf_dash(k):
            continue
        try:
            if name not in tabelle:
                try:
                    tabelle.add(name, pattern=muster(k), description=BESCHREIBUNG[name])
                except TypeError:                 # older ezdxf
                    tabelle.new(name, dxfattribs={"description": BESCHREIBUNG[name],
                                                  "pattern": muster(k)})
            out.add(name)
        except Exception as ex:                   # the line then stays continuous
            print(f"[KatieCAD] DXF-Linientyp {name}: {ex}")
    return out


def attribute(schluessel, erlaubt=None):
    """{'linetype': name} for dxfattribs, or {} for continuous lines.
    erlaubt: names defined in the document (see definieren); None = all."""
    name = dxf_name(schluessel)
    if not name or (erlaubt is not None and name not in erlaubt):
        return {}
    return {"linetype": name}


def dwg_tabelle():
    """{name: {'description', 'dashes'}} for ezdwg Drawing.linetypes."""
    return {name: {"description": BESCHREIBUNG[name], "dashes": dashes(k)}
            for k, name in DXF_NAMEN.items() if pdf_dash(k)}
