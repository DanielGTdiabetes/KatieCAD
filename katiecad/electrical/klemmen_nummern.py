# -*- coding: utf-8 -*-
"""
katiecad/electrical/klemmen_nummern.py - Renumber terminal strips (no Tk).

The terminals (Klemme) of the chosen strips (field IND, e.g. -X1) get the numbers
start, start + step ... (field NUM, format "{n}" or e.g. "{n:02}") over the whole project:

  "spalten"   by position: sheet by sheet, left to right, top to bottom in a column
  "zeilen"    by position: sheet by sheet, top to bottom, left to right in a row
  "bestehend" keeps the present order of the numbers and only closes the gaps

Terminals that carry the same number in the same strip are ONE terminal drawn twice
(single-pole view, top and bottom on different sheets ...): they keep sharing the new
number. Names with letters (PE, N, L1 ...) are kept when `buchstaben_behalten` is set.

Works on element objects (open sheet) and on the plain dicts of the JSON sheet files.
"""

import re

STANDARD = {"format": "{n}", "start": 1, "schritt": 1, "reihenfolge": "spalten",
            "buchstaben_behalten": True}

_ZAHL = re.compile(r"(\d+)")


def _get(o, k, default=None):
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def _wert(v, tag):
    v = str(v or "").strip()
    return "" if v.upper() == tag else v


def klemmen(elemente):
    """Terminals of a sheet: [(werte dict, x, y)]."""
    out = []
    for el in elemente:
        if _get(el, "typ") != "klemme":
            continue
        w = _get(el, "werte")
        if isinstance(w, dict):
            out.append((w, _get(el, "x", 0.0), _get(el, "y", 0.0)))
    return out


def leisten(blaetter):
    """{strip: number of terminals} of the project (terminals without strip left out)."""
    out = {}
    for _b, elemente in blaetter:
        for w, _x, _y in klemmen(elemente):
            ind = _wert(w.get("IND"), "IND")
            if ind:
                out[ind] = out.get(ind, 0) + 1
    return out


def natuerlich(s):
    return [int(t) if t.isdigit() else t.lower() for t in _ZAHL.split(str(s or ""))]


def hat_buchstaben(num):
    return any(c.isalpha() for c in str(num or ""))


def format_nummer(fmt, n):
    try:
        return str(fmt or "{n}").format(n=n)
    except (KeyError, IndexError, ValueError):
        return str(n)


def format_gueltig(fmt):
    try:
        str(fmt).format(n=1)
    except (KeyError, IndexError, ValueError):
        return False
    return "{n" in str(fmt)


def _pos(x, y, reihenfolge):
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        x, y = 0.0, 0.0
    if reihenfolge == "zeilen":
        return (round(-y, 1), x)
    return (round(x, 1), -y)


def planen(blaetter, auswahl, einstellung=None):
    """New numbers for the strips in `auswahl` (names; None = all).
    -> [(strip, old, new, [werte dicts])] in the new order, strip by strip."""
    e = dict(STANDARD, **(einstellung or {}))
    try:
        start, schritt = int(e["start"]), max(1, int(e["schritt"]))
    except (TypeError, ValueError):
        start, schritt = 1, 1
    reihe = {b: i for i, (b, _el) in enumerate(blaetter)}
    gruppen = {}                       # strip -> {key: [sortkey, old, [werte]]}
    for b, elemente in blaetter:
        for w, x, y in klemmen(elemente):
            leiste = _wert(w.get("IND"), "IND")
            if not leiste or (auswahl is not None and leiste not in auswahl):
                continue
            alt = _wert(w.get("NUM"), "NUM")
            if alt and e["buchstaben_behalten"] and hat_buchstaben(alt):
                continue
            sk = (reihe.get(b, 0),) + _pos(x, y, e["reihenfolge"])
            if e["reihenfolge"] == "bestehend":
                sk = (0, natuerlich(alt), not alt) + sk if alt else (1,) + sk
            schl = ("alt", alt) if alt else ("neu", id(w))
            g = gruppen.setdefault(leiste, {})
            if schl in g:
                g[schl][0] = min(g[schl][0], sk)
                g[schl][2].append(w)
            else:
                g[schl] = [sk, alt, [w]]
    out = []
    for leiste in sorted(gruppen, key=natuerlich):
        n = start
        for sk, alt, werte in sorted(gruppen[leiste].values(), key=lambda g: g[0]):
            out.append((leiste, alt, format_nummer(e["format"], n), werte))
            n += schritt
    return out


def anwenden(plan):
    """Writes the new numbers. -> number of changed terminals (drawn terminals)."""
    n = 0
    for _leiste, _alt, neu, werte in plan:
        for w in werte:
            if w.get("NUM") != neu:
                w["NUM"] = neu
                n += 1
    return n


def blaetter_geaendert(plan, blaetter):
    """Sheet keys whose terminals the plan touches."""
    ids = {id(w) for *_x, werte in plan for w in werte}
    return {b for b, el in blaetter if any(id(w) in ids for w, _x, _y in klemmen(el))}
