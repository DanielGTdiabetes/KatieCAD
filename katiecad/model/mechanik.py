# -*- coding: utf-8 -*-
"""
katiecad/model/mechanik.py - Machining of cabinets, doors and mounting plates (NO Tkinter).

Cut-outs and holes are placed on a face of a 3D body: rectangular cut-outs for fans or
devices, round holes for push buttons / pilot lights and cable glands, fixing holes.
They are ordinary cut-outs of the body (Koerper3D.ausschnitte) with a label (`bez`) and
the position on the face (`pos`, centre from the lower left corner of the face seen
from outside: X to the right, Y upwards), so a machining list can be printed for the
workshop.

Templates: `mecanizado.json` in report_templates/ of the program and/or the project
(the project wins):

    {"vorlagen": [{"name": "Push button Ø22.5", "form": "rund", "d": 22.5},
                  {"name": "Cut-out 92 x 92", "form": "rechteck", "b": 92, "h": 92}]}
"""

import json
import os

from katiecad.model import geom3d as G

DATEI = "mecanizado.json"
STANDARD_TIEFE = 3.0     # mm: cut into the face (cabinet bodies are solid boxes); 0 = through
FORMEN = ("rund", "rechteck")


def vorlagen_laden(ordner=()):
    """[{"name", "form", "d" | "b","h"}] from the folders (later = higher priority)."""
    out = []
    for o in ordner:
        try:
            with open(os.path.join(o, DATEI), "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        neu = []
        for v in d.get("vorlagen", []) if isinstance(d, dict) else []:
            try:
                form = v.get("form", "rund")
                if form == "rund":
                    neu.append({"name": str(v["name"]), "form": "rund", "d": float(v["d"])})
                elif form == "rechteck":
                    neu.append({"name": str(v["name"]), "form": "rechteck",
                                "b": float(v["b"]), "h": float(v["h"])})
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        if neu:
            out = neu
    return out


# ------------------------------------------------------------------
# Face plane
# ------------------------------------------------------------------
def flaechen_ebene(pts, zentrum):
    """Work plane of a face for machining: origin = lower left corner seen from outside,
    X to the right, Y upwards (horizontal faces: X = world X), normal outwards.
    -> (ebene 9-tuple, width, height) or None."""
    e0 = G.ebene_von_flaeche(pts, zentrum)
    if e0 is None:
        return None
    n = G.ebene_basis(e0)[2]
    if abs(n[2]) > 0.99:                              # top / bottom face
        u = (1.0, 0.0, 0.0)
    else:
        u = G.v_norm(G.v_cross(G.v_mul(n, -1.0), (0.0, 0.0, 1.0)))
    v = G.v_cross(n, u)
    roh = (pts[0][0], pts[0][1], pts[0][2], u[0], u[1], u[2], v[0], v[1], v[2])
    lok = [G.ebene_lokal(roh, p) for p in pts]
    x0, y0 = min(p[0] for p in lok), min(p[1] for p in lok)
    o = G.ebene_punkt(roh, x0, y0)
    e = (o[0], o[1], o[2], u[0], u[1], u[2], v[0], v[1], v[2])
    return e, max(p[0] for p in lok) - x0, max(p[1] for p in lok) - y0


def seite(ebene):
    """Side of the body a face plane looks at: vorne, hinten, links, rechts, oben, unten."""
    n = G.ebene_basis(ebene)[2]
    i = max(range(3), key=lambda k: abs(n[k]))
    return (("links", "rechts"), ("vorne", "hinten"), ("unten", "oben"))[i][n[i] > 0]


# ------------------------------------------------------------------
# Cut-outs
# ------------------------------------------------------------------
def profil(form, cx, cy, d=0.0, b=0.0, h=0.0):
    """-> (outline [(x, y)], round?) centred at (cx, cy)."""
    if form == "rund":
        return G.kreis_profil(cx, cy, d / 2.0, 48), True
    return G.rechteck_profil(cx - b / 2.0, cy - h / 2.0, cx + b / 2.0, cy + h / 2.0), False


def positionen(x, y, nx=1, dx=0.0, ny=1, dy=0.0):
    """Centres of a row / matrix: nx columns with pitch dx, ny rows with pitch dy."""
    return [(x + i * dx, y + j * dy) for j in range(max(1, int(ny))) for i in range(max(1, int(nx)))]


def masse_text(form, d=0.0, b=0.0, h=0.0):
    return ("Ø%g" % d) if form == "rund" else ("%g x %g" % (b, h))


def mechanisieren(elemente, ebene, form, mittelpunkte, d=0.0, b=0.0, h=0.0, tiefe=STANDARD_TIEFE,
                  bez="", koerper=None):
    """Cuts one cut-out per centre into the body whose face lies in `ebene` (see
    flaechen_ebene). koerper: the clicked body - it wins over other bodies with a face in
    the same plane (the door in front of the cabinet body). tiefe 0 / None = through.
    -> number of cut-outs made (centres outside every face are skipped)."""
    from katiecad.model.szene3d import host_finden
    n = 0
    for cx, cy in mittelpunkte:
        prof, rund = profil(form, cx, cy, d, b, h)
        host = None
        if koerper is not None:
            host = host_finden([koerper], ebene, (cx, cy), nur_innen=True)
        if host is None:
            host = host_finden(elemente, ebene, (cx, cy), nur_innen=True)
        if host is None:
            continue
        host.ausschnitt_hinzufuegen(ebene, prof, tiefe if tiefe else None, rund,
                                    bez=bez or masse_text(form, d, b, h), pos=(cx, cy))
        n += 1
    return n


# ------------------------------------------------------------------
# Machining list
# ------------------------------------------------------------------
def _koerper_mit_teil(elemente):
    from katiecad.model.core import Koerper3D, Gruppe3D
    for el in elemente:
        if isinstance(el, Koerper3D):
            yield el, el.bez or ""
        elif isinstance(el, Gruppe3D):
            for t in el.teile:
                yield t, t.bez or el.name or ""


def mechanikliste(blaetter, seiten_namen=None):
    """One row per cut-out made with the machining dialog (it carries a position):
    {"teil", "seite", "art", "masse", "x", "y", "tiefe", "blatt"}, sorted by part, side,
    Y from the top, X."""
    sn = seiten_namen or {}
    zeilen = []
    for b, elemente in blaetter:
        for k, teil in _koerper_mit_teil(elemente):
            for a in getattr(k, "ausschnitte", ()):
                if a.get("pos") is None:
                    continue
                prof = a["profil"]
                xs, ys = [p[0] for p in prof], [p[1] for p in prof]
                breite, hoehe = max(xs) - min(xs), max(ys) - min(ys)
                masse = ("Ø%g" % round(breite, 2)) if a["rund"] else \
                    ("%g x %g" % (round(breite, 2), round(hoehe, 2)))
                s = seite(a["ebene"])
                zeilen.append({"teil": teil, "seite": sn.get(s, s), "art": a.get("bez", ""),
                               "masse": masse, "x": "%.1f" % a["pos"][0],
                               "y": "%.1f" % a["pos"][1],
                               "tiefe": "" if a["tiefe"] is None else "%g" % a["tiefe"],
                               "_s": (teil, s, -a["pos"][1], a["pos"][0]), "blatt": b})
    zeilen.sort(key=lambda z: z["_s"])
    for i, z in enumerate(zeilen, 1):
        z["pos"] = str(i)
        z.pop("_s")
    return zeilen
