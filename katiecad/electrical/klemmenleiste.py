# -*- coding: utf-8 -*-
"""
katiecad/electrical/klemmenleiste.py - Terminal strip editor, data part (no Tk).

Like EPLAN's terminal strip editor: one row per terminal of a strip (-X1) in mounting
order, editable, written back to the terminals of the schematic on every sheet:

  num, typ, man, per   fields NUM / TYP / MAN / PER of the terminal
  trenn                partition plate after the terminal (Klemme.trennplatte)
  bruecke              jumper to the NEXT terminal: "" / "oben" / "unten" / "beide"
  order                the row order = mounting order (Klemme.montage); when it is
                       simply the order of the numbers, no explicit position is stored

Terminals with the same number in the same strip are ONE terminal drawn several times
(single-pole view, on two sheets ...): one row, every drawing gets the changes.
Works on element objects (open sheet) and on the plain dicts of the JSON sheet files.
"""

from katiecad.electrical.klemmen_nummern import (klemmen_mit_leiste, natuerlich, _wert, _get,
                                                  _setzen, hat_buchstaben, format_nummer)

FELDER = ("num", "typ", "man", "per")
_TAG = {"num": "NUM", "typ": "TYP", "man": "MAN", "per": "PER"}


def _zahl_pos(x, y):
    try:
        return (-float(y), float(x))
    except (TypeError, ValueError):
        return (0.0, 0.0)


def zeilen(blaetter, leiste, ziele=None):
    """Rows of the strip in mounting order:
    [{"num", "typ", "man", "per", "trenn", "bruecke", "oben", "unten", "anzahl", "_glieder"}].
    ziele: {(sheet, x, y): (top text, bottom text)} of the terminal diagram (optional)."""
    reihe = {b: i for i, (b, _e) in enumerate(blaetter)}
    gruppen = {}
    for b, elemente in blaetter:
        for ind, w, x, y, el in klemmen_mit_leiste(elemente):
            if ind != leiste:
                continue
            num = _wert(w.get("NUM"), "NUM")
            schl = ("n", num) if num else ("e", id(el))
            m = _get(el, "montage")
            sk = (m is None, m or 0, not num, natuerlich(num) if num else [],
                  reihe.get(b, 0)) + _zahl_pos(x, y)
            g = gruppen.get(schl)
            if g is None:
                z = {"num": num, "typ": _wert(w.get("TYP"), "TYP"),
                     "man": _wert(w.get("MAN"), "MAN"), "per": _wert(w.get("PER"), "PER"),
                     "trenn": bool(_get(el, "trennplatte", False)),
                     "bruecke": _get(el, "bruecke", "") or "", "oben": "", "unten": "",
                     "_glieder": [], "_sk": sk}
                gruppen[schl] = z
                g = z
            g["_sk"] = min(g["_sk"], sk)
            g["_glieder"].append(el)
            if ziele:
                o, u = ziele.get((b, _rund(x), _rund(y)), ("", ""))
                g["oben"] = g["oben"] or o
                g["unten"] = g["unten"] or u
    out = sorted(gruppen.values(), key=lambda z: z["_sk"])
    for z in out:
        z["anzahl"] = len(z["_glieder"])
        z.pop("_sk")
    return out


def _rund(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return 0.0


def ziele_index(plan_zeilen):
    """{(sheet, x, y): (top text, bottom text)} from the rows of reports.daten.klemmenplan."""
    out = {}
    for z in plan_zeilen:
        x, y = z.get("_pos", (0.0, 0.0))
        out[(z.get("_blatt"), _rund(x), _rund(y))] = (", ".join(z.get("oben") or []),
                                                      ", ".join(z.get("unten") or []))
    return out


def umnummerieren(rows, start=1, fmt="{n}", buchstaben_behalten=True):
    """Numbers start, start+1 ... in the row order (rows changed in place); names with
    letters (PE, N ...) are kept when buchstaben_behalten."""
    n = start
    for z in rows:
        if buchstaben_behalten and hat_buchstaben(z["num"]):
            continue
        z["num"] = format_nummer(fmt, n)
        n += 1
    return rows


def nach_nummer_sortiert(rows):
    """Rows in the order of their numbers (empty numbers last, stable)."""
    return sorted(rows, key=lambda z: (not z["num"], natuerlich(z["num"])))


def pruefen(rows):
    """Problems of the edited strip: [(row index, 'doppelt' | 'leer')]."""
    out, gesehen = [], {}
    for i, z in enumerate(rows):
        n = (z["num"] or "").strip()
        if not n:
            out.append((i, "leer"))
        elif n.upper() in gesehen:
            out.append((i, "doppelt"))
        else:
            gesehen[n.upper()] = i
    return out


def anwenden(rows):
    """Writes the rows to the terminals (every drawing of each row). The row order becomes
    the mounting position, unless it is the plain order of the numbers (then none is
    stored). The jumper of the last row is dropped. -> number of changed drawings."""
    natuerlich_sortiert = [id(z) for z in nach_nummer_sortiert(rows)] == [id(z) for z in rows]
    n = 0
    for i, z in enumerate(rows):
        bruecke = z.get("bruecke") or ""
        if i == len(rows) - 1:
            bruecke = ""
        montage = None if natuerlich_sortiert else i
        for el in z["_glieder"]:
            w = _get(el, "werte")
            vorher = (dict(w), bool(_get(el, "trennplatte", False)), _get(el, "bruecke", "") or "",
                      _get(el, "montage"))
            for f in FELDER:
                wert = (z.get(f) or "").strip()
                if wert or w.get(_TAG[f]) not in (None, "", _TAG[f]):
                    w[_TAG[f]] = wert
            _setzen(el, "trennplatte", bool(z.get("trenn")) if not isinstance(el, dict)
                    else (True if z.get("trenn") else None))
            _setzen(el, "bruecke", bruecke if not isinstance(el, dict) else (bruecke or None))
            _setzen(el, "montage", montage)
            nachher = (dict(w), bool(_get(el, "trennplatte", False)), _get(el, "bruecke", "") or "",
                       _get(el, "montage"))
            if vorher != nachher:
                n += 1
    return n


def blaetter_von(rows, blaetter):
    """Sheet keys holding drawings of the rows."""
    ids = {id(el) for z in rows for el in z["_glieder"]}
    return {b for b, els in blaetter if any(id(el) in ids for el in els)}
