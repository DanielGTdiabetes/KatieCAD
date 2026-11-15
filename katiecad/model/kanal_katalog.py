# -*- coding: utf-8 -*-
"""
katiecad/model/kanal_katalog.py - Cable duct catalogue, bar length and the duct list
(NO Tkinter).

The catalogue is a JSON file `kanal_katalog.json` in report_templates/ of the program
and/or of the project (the project wins):

    {"max_laenge": 2000,
     "kanaele": [{"name": "40 x 60", "breite": 40, "hoehe": 60,
                  "hersteller": "Unex", "ref": "..."}]}

`max_laenge` is the length of one duct bar: a drawn duct stops at that length and longer
pieces are split into bars. The list counts the straight pieces per size / reference,
their total length and the bars needed, plus the fittings.
"""

import json
import math
import os

MAX_LAENGE = 2000.0
DATEI = "kanal_katalog.json"
DATEI_SCHIENE = "hutschienen.json"   # DIN rails: same format, drawn with the duct tool


def katalog_laden(ordner=(), datei=DATEI):
    """-> {"max_laenge": float, "kanaele": [dict]} from the folders (later = higher
    priority). Faulty files are ignored. datei: DATEI (ducts) or DATEI_SCHIENE (DIN rails)."""
    out = {"max_laenge": MAX_LAENGE, "kanaele": []}
    for o in ordner:
        try:
            with open(os.path.join(o, datei), "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        try:
            m = float(d.get("max_laenge", out["max_laenge"]))
            if m > 0:
                out["max_laenge"] = m
        except (TypeError, ValueError):
            pass
        eintraege = []
        for e in d.get("kanaele", []) if isinstance(d.get("kanaele"), list) else []:
            try:
                eintraege.append({"name": str(e.get("name") or "%g x %g" % (e["breite"], e["hoehe"])),
                                  "breite": float(e["breite"]), "hoehe": float(e["hoehe"]),
                                  "hersteller": str(e.get("hersteller", "")),
                                  "ref": str(e.get("ref", ""))})
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        if eintraege:
            out["kanaele"] = eintraege
    return out


def begrenzen(q, p, max_l=MAX_LAENGE):
    """End point p of a duct piece starting at q, limited to max_l (the bar length)."""
    dx, dy = p[0] - q[0], p[1] - q[1]
    d = math.hypot(dx, dy)
    if max_l <= 0 or d <= max_l:
        return p
    f = max_l / d
    return (q[0] + dx * f, q[1] + dy * f)


def aufteilen(punkte, max_l=MAX_LAENGE):
    """Inserts points so that no segment is longer than max_l: a long typed piece becomes
    whole bars plus the rest, as cut in the workshop (4500 -> 2000 + 2000 + 500)."""
    if max_l <= 0 or len(punkte) < 2:
        return list(punkte)
    out = [tuple(punkte[0])]
    for a, b in zip(punkte, punkte[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        s = max_l
        while s < d - 1e-6:
            out.append((a[0] + (b[0] - a[0]) * s / d, a[1] + (b[1] - a[1]) * s / d))
            s += max_l
        out.append(tuple(b))
    return out


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------
def _stuecke(elemente):
    """[(art, breite, hoehe, ref, length)] of the duct pieces (2D and 3D) of one sheet."""
    from katiecad.model.core import Kabelkanal, Koerper3D, Gruppe3D, kanal_aus_koerper
    out = []

    def nehmen(el):
        if isinstance(el, Kabelkanal):
            art = "schiene" if getattr(el, "schiene", False) and el.art == "gerade" else el.art
            out.append((art, el.breite, el.hoehe, getattr(el, "ref", ""), el.laenge()))
        elif isinstance(el, Koerper3D) and el.kanal:
            kd = el.kanal
            m = kanal_aus_koerper(el)
            laenge = math.hypot(m[1][0] - m[0][0], m[1][1] - m[0][1]) if m else 0.0
            art = kd.get("art", "gerade")
            if kd.get("schiene") and art == "gerade":
                art = "schiene"
            out.append((art, float(kd.get("breite") or 0.0),
                        float(kd.get("hoehe") or abs(el.hoehe)), kd.get("ref", ""), laenge))
        elif isinstance(el, Gruppe3D):
            for t in el.teile:
                nehmen(t)

    for el in elemente:
        nehmen(el)
    return out


def kanalliste(blaetter, katalog=None, schienen_katalog=None):
    """One row per duct size / reference: rows {"ref", "hersteller", "masse", "art",
    "stueck", "laenge" (m), "stangen"} - straight pieces first (with the bars of
    max_laenge needed), then the fittings (coupler, elbow, tee) as pieces. DIN rails
    drawn with the duct tool appear as art "schiene" (manufacturer from schienen_katalog)."""
    kat = katalog or {"max_laenge": MAX_LAENGE, "kanaele": []}
    m = kat["max_laenge"]
    herst = {(round(e["breite"], 1), round(e["hoehe"], 1), e["ref"]): e["hersteller"]
             for e in kat["kanaele"] + list((schienen_katalog or {}).get("kanaele", []))}
    gruppen = {}
    for _b, el in blaetter:
        for art, b, h, ref, laenge in _stuecke(el):
            # straight ducts and DIN rails (by the metre / bar) first, then fittings
            schl = (art not in ("gerade", "schiene"), art, round(b, 1), round(h, 1), ref)
            z = gruppen.setdefault(schl, {"stueck": 0, "laenge": 0.0})
            z["stueck"] += 1
            z["laenge"] += laenge
    zeilen = []
    m_schiene = (schienen_katalog or {}).get("max_laenge", m)
    for (form, art, b, h, ref), z in sorted(gruppen.items()):
        mm = m_schiene if art == "schiene" else m
        zeilen.append({
            "ref": ref, "hersteller": herst.get((b, h, ref), ""),
            "masse": "%g x %g" % (b, h), "art": art, "stueck": str(z["stueck"]),
            "laenge": ("%.2f" % (z["laenge"] / 1000.0)) if not form else "",
            "stangen": str(int(math.ceil(z["laenge"] / mm - 1e-9))) if not form and mm > 0 else ""})
    return zeilen
