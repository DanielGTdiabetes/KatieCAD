# -*- coding: utf-8 -*-
"""
katiecad/model/geraete3d.py - 3D models of the devices of the schematic (NO Tkinter).

A device gets its 3D model (a .katie3d file made by fileio/modell3d.py, path relative to
the project folder) in two ways; the first that applies wins:

  1. per device:  attribute MODELL3D of the device block (BlockReferenz.attribute)
  2. per article: entry of the project parts catalogue with the same TYP
                  (p.daten["bauteile"]: {"typ", "hersteller", ..., "modell3d"})

`geraete_mit_modell` lists the devices of the project with their model and whether they
are already placed in 3D (a Koerper3D whose `geraet` is the device identifier).
"""

from katiecad.model.core import BlockReferenz, Koerper3D, Gruppe3D

ATTR = "MODELL3D"


def _typ(obj):
    a = getattr(obj, "attribute", {}) or {}
    t = str(a.get("TYP", "") or "").strip()
    return "" if t.upper() == "TYP" else t


def _man(obj):
    a = getattr(obj, "attribute", {}) or {}
    m = str(a.get("MAN", "") or "").strip()
    return "" if m.upper() == "MAN" else m


def artikel_modell(katalog, typ):
    """Model of the article TYP in the parts catalogue, or ''."""
    t = str(typ or "").strip().upper()
    for e in katalog or []:
        if isinstance(e, dict) and str(e.get("typ", "")).strip().upper() == t and t:
            return str(e.get("modell3d", "") or "")
    return ""


def modell_von(obj, katalog=None):
    """-> (model path, source 'geraet' | 'artikel' | '')."""
    eigen = str((getattr(obj, "attribute", {}) or {}).get(ATTR, "") or "").strip()
    if eigen:
        return eigen, "geraet"
    a = artikel_modell(katalog, _typ(obj))
    return (a, "artikel") if a else ("", "")


def platziert(elemente):
    """Identifiers of the devices that already have a placed 3D model."""
    out = set()
    for el in elemente:
        teile = el.teile if isinstance(el, Gruppe3D) else [el]
        for t in teile:
            if isinstance(t, Koerper3D) and getattr(t, "geraet", ""):
                out.add(t.geraet)
    return out


def geraete_mit_modell(blaetter, katalog=None, elemente_3d=()):
    """One row per device identifier (main symbol first):
    [{"ind", "typ", "man", "modell", "quelle", "platziert", "_obj"}], sorted by identifier.
    blaetter: [(sheet key, elements)]; elemente_3d: elements of the 3D scene."""
    from katiecad.electrical.logic import geraete
    from katiecad.reports.netz import natuerlich
    gesehen = {}
    for b, el in blaetter:
        for g in geraete(el, b):
            obj = g["obj"]
            if not isinstance(obj, BlockReferenz):
                continue
            ind = str(g.get("ind") or "").strip()
            if not ind or ind.upper() == "IND":
                continue
            alt = gesehen.get(ind)
            if alt is not None and (alt["_haupt"] or g["rolle"] != "haupt"):
                if not alt["modell"]:                  # an auxiliary part may carry the model
                    m, q = modell_von(obj, katalog)
                    if m:
                        alt.update(modell=m, quelle=q)
                continue
            m, q = modell_von(obj, katalog)
            gesehen[ind] = {"ind": ind, "typ": _typ(obj), "man": _man(obj), "modell": m,
                            "quelle": q, "_haupt": g["rolle"] == "haupt", "_obj": obj}
    gesetzt = platziert(elemente_3d)
    out = []
    for ind in sorted(gesehen, key=natuerlich):
        z = gesehen[ind]
        z["platziert"] = ind in gesetzt
        z.pop("_haupt", None)
        out.append(z)
    return out


def geraet_setzen(objekte, pfad):
    """Sets (pfad) or removes ('') the model of the given device blocks. -> count."""
    n = 0
    for o in objekte:
        if isinstance(o, BlockReferenz) and o.geraet_maske() is not None:
            if pfad:
                o.attribute[ATTR] = pfad
            else:
                o.attribute.pop(ATTR, None)
            n += 1
    return n


def artikel_setzen(katalog, typ, pfad, hersteller=""):
    """Sets the model of the article TYP in the parts catalogue (list, changed in place);
    a missing article is added. -> the catalogue."""
    t = str(typ or "").strip()
    if not t:
        return katalog
    for e in katalog:
        if isinstance(e, dict) and str(e.get("typ", "")).strip().upper() == t.upper():
            e["modell3d"] = pfad
            return katalog
    katalog.append({"typ": t, "hersteller": hersteller, "bestellnr": "", "beschreibung": "",
                    "modell3d": pfad})
    return katalog


def katalog_zusammenfuehren(alt, neu):
    """After editing the parts catalogue (the dialog knows only its columns): keeps extra
    fields such as modell3d of the entries with the same TYP."""
    alte = {str(e.get("typ", "")).strip().upper(): e for e in alt or [] if isinstance(e, dict)}
    out = []
    for e in neu or []:
        a = alte.get(str(e.get("typ", "")).strip().upper())
        if a:
            e = dict({k: v for k, v in a.items() if k not in e}, **e)
        out.append(e)
    return out
