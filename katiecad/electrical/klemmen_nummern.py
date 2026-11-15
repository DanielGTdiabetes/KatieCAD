# -*- coding: utf-8 -*-
"""
katiecad/electrical/klemmen_nummern.py - Renumber terminal strips (no Tk).

The terminals (Klemme) of the chosen strips (field IND, e.g. -X1) get the numbers
start, start + step ... (field NUM, format "{n}" or e.g. "{n:02}") over the whole project:

  "spalten"   by position: sheet by sheet, left to right, top to bottom in a column
  "zeilen"    by position: sheet by sheet, top to bottom, left to right in a row
  "bestehend" keeps the present mounting order (the position set in the terminal strip
              editor, otherwise the numbers) and only closes the gaps

After renumbering by position the mounting order follows the numbers again (Klemme.montage
of the whole strip cleared); "bestehend" keeps it.

Terminals that carry the same number in the same strip are ONE terminal drawn twice
(single-pole view, top and bottom on different sheets ...): they keep sharing the new
number. Names with letters (PE, N, L1 ...) are kept when `buchstaben_behalten` is set.

Works on element objects (open sheet) and on the plain dicts of the JSON sheet files.
"""

import re
from types import SimpleNamespace

from katiecad.reports.netz import leisten_ermitteln

STANDARD = {"format": "{n}", "start": 1, "schritt": 1, "reihenfolge": "spalten",
            "buchstaben_behalten": True}

_ZAHL = re.compile(r"(\d+)")


def _get(o, k, default=None):
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def _wert(v, tag):
    v = str(v or "").strip()
    return "" if v.upper() == tag else v


def klemmen(elemente, mit_element=False):
    """Terminals of a sheet: [(werte dict, x, y)] or, with mit_element,
    [(werte dict, x, y, element)]."""
    out = []
    for el in elemente:
        if _get(el, "typ") != "klemme":
            continue
        w = _get(el, "werte")
        if isinstance(w, dict):
            t = (w, _get(el, "x", 0.0), _get(el, "y", 0.0))
            out.append(t + (el,) if mit_element else t)
    return out


def klemmen_mit_leiste(elemente):
    """Resolved strip and original element for each terminal on a sheet."""
    daten = klemmen(elemente, True)
    klemmen_objekte = [SimpleNamespace(werte=w, x=x, y=y) if isinstance(el, dict) else el
                       for w, x, y, el in daten]
    zuordnung = leisten_ermitteln(klemmen_objekte)
    for klemme, (w, x, y, el) in zip(klemmen_objekte, daten):
        yield zuordnung[id(klemme)], w, x, y, el


def gewaehlte_leisten(elemente, auswahl):
    """Resolve the selection using the full sheet, in selection order."""
    if not auswahl:
        return []
    zuordnung = {id(el): leiste for leiste, _, _, _, el in klemmen_mit_leiste(elemente)}
    return [zuordnung[id(el)] for el in auswahl if zuordnung.get(id(el))]


def leisten(blaetter):
    """{strip: number of terminals} of the project (terminals without strip left out)."""
    out = {}
    for _b, elemente in blaetter:
        for ind, _, _, _, _ in klemmen_mit_leiste(elemente):
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
    -> [(strip, old, new, [terminal elements])] in the new order, strip by strip; names
    kept because of their letters come with new == old."""
    e = dict(STANDARD, **(einstellung or {}))
    try:
        start, schritt = int(e["start"]), max(1, int(e["schritt"]))
    except (TypeError, ValueError):
        start, schritt = 1, 1
    reihe = {b: i for i, (b, _el) in enumerate(blaetter)}
    gruppen = {}                       # strip -> {key: [sortkey, old, [werte]]}
    for b, elemente in blaetter:
        for leiste, w, x, y, el in klemmen_mit_leiste(elemente):
            if not leiste or (auswahl is not None and leiste not in auswahl):
                continue
            alt = _wert(w.get("NUM"), "NUM")
            fest = bool(alt and e["buchstaben_behalten"] and hat_buchstaben(alt))
            sk = (reihe.get(b, 0),) + _pos(x, y, e["reihenfolge"])
            if e["reihenfolge"] == "bestehend":
                m = _get(el, "montage")
                mk = (0, m) if m is not None else (1, 0)
                sk = mk + ((0, natuerlich(alt)) if alt else (1, [])) + sk
            schl = ("alt", alt) if alt else ("neu", id(w))
            g = gruppen.setdefault(leiste, {})
            if schl in g:
                g[schl][0] = min(g[schl][0], sk)
                g[schl][2].append(el)
            else:
                g[schl] = [sk, alt, [el], fest]
    out = []
    for leiste in sorted(gruppen, key=natuerlich):
        n = start
        for sk, alt, werte, fest in sorted(gruppen[leiste].values(), key=lambda g: g[0]):
            if fest:
                out.append((leiste, alt, alt, werte))
                continue
            out.append((leiste, alt, format_nummer(e["format"], n), werte))
            n += schritt
    return out


def _setzen(el, k, v):
    if isinstance(el, dict):
        if v is None:
            el.pop(k, None)
        else:
            el[k] = v
    else:
        setattr(el, k, v)


def _aendert(el, neu, montage_behalten):
    return (_wert(_get(el, "werte").get("NUM"), "NUM") != neu
            or (not montage_behalten and _get(el, "montage") is not None))


def anwenden(plan, montage_behalten=False):
    """Writes the new numbers; unless montage_behalten, clears the explicit mounting position
    (the order follows the numbers again). -> number of changed terminals."""
    n = 0
    for _leiste, _alt, neu, elemente in plan:
        for el in elemente:
            if not _aendert(el, neu, montage_behalten):
                continue
            if neu:
                _get(el, "werte")["NUM"] = neu
            if not montage_behalten:
                _setzen(el, "montage", None)
            n += 1
    return n


def offen(plan, montage_behalten=False):
    """Rows of the plan that change something (number or explicit position)."""
    return [z for z in plan if any(_aendert(el, z[2], montage_behalten) for el in z[3])]


def blaetter_geaendert(plan, blaetter):
    """Sheet keys whose terminals the plan touches."""
    ids = {id(el) for *_x, elemente in plan for el in elemente}
    return {b for b, els in blaetter if any(id(el) in ids for el in els)}
