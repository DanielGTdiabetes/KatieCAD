# -*- coding: utf-8 -*-
"""
katiecad/electrical/umbenennen.py - Rename devices in a batch with a counter (no Tk).

Like EPLAN's "number devices": the chosen main symbols get a new identifier from a
format with a counter, e.g. "{sheet}{kz}{n}" -> 10K1, 10K2 ... on sheet 10, and EVERY
part of the same device follows: auxiliary contacts and other parts with the same
identifier (on all sheets), single-pole copies and placed 3D models (Koerper3D.geraet).
Without that the contact mirror would lose its contacts.

Placeholders of the format:
  {sheet} / {hoja}            number of the sheet (position in the project, 1 ...)
  {sheetname} / {nombre}      name of the sheet
  {kz} / {letras}             identifying letters of the old identifier (-K12 -> K, -2Q1 -> Q)
  {n}                         counter (format specs allowed: {n:02})

The counter runs per identifying letter (K, Q, F ... each from `start`) and, when
`je_blatt` is set, again on every sheet. Names already used by devices that are not
renamed are skipped. Devices are taken in project order, on each sheet by columns
(left to right, then top to bottom: "spalten") or by rows ("zeilen").

Works on element objects (open sheet) and on the plain dicts of the JSON sheet files.
"""

import re

from katiecad.electrical.nummerierung import geraete_felder, zerlegen

STANDARD = {"format": "{sheet}{kz}{n}", "start": 1, "schritt": 1, "je_blatt": True,
            "reihenfolge": "spalten"}

_KZ = re.compile(r"^[-=+]?\s*\d*\s*([A-Za-z]+)")


def kennbuchstaben(ind):
    """'-K12' -> 'K', '-10K1' -> 'K', '2Q1' -> 'Q', '-K' -> 'K', '' -> ''."""
    m = _KZ.match(str(ind or "").strip())
    return m.group(1).upper() if m else ""


def format_name(fmt, sheet, sheetname, kz, n):
    """'{sheet}{kz}{n}' -> '10K1'. Invalid formats fall back to the default."""
    werte = {"sheet": sheet, "hoja": sheet, "sheetname": sheetname, "nombre": sheetname,
             "kz": kz, "letras": kz, "n": n}
    try:
        return str(fmt or STANDARD["format"]).format(**werte)
    except (KeyError, IndexError, ValueError):
        return STANDARD["format"].format(**werte)


def format_gueltig(fmt):
    """True when the format works and contains the counter {n}."""
    try:
        str(fmt).format(sheet=1, hoja=1, sheetname="", nombre="", kz="K", letras="K", n=1)
    except (KeyError, IndexError, ValueError):
        return False
    return "{n" in str(fmt)


def _get(o, k, default=None):
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def _typ(el):
    return _get(el, "typ")


def ind_felder(el):
    """All IND fields of an element that name a device: (holder, key) of masks and
    blocks with a mask, also auxiliary parts and single-pole copies."""
    t = _typ(el)
    if t == "maske":
        w = _get(el, "werte")
        if isinstance(w, dict) and "IND" in w:
            yield w, "IND"
    elif t == "block":
        a = _get(el, "attribute")
        if not (isinstance(a, dict) and "IND" in a):
            return
        if isinstance(el, dict):
            hat = any(isinstance(k, dict) and k.get("typ") == "maske"
                      for k in el.get("elemente", []) or [])
        else:
            hat = hasattr(el, "geraet_maske") and el.geraet_maske() is not None
        if hat:
            yield a, "IND"


def _koerper(el):
    """3D bodies of an element (also inside 3D groups)."""
    teile = _get(el, "teile")
    if isinstance(teile, list):
        for t in teile:
            yield from _koerper(t)
    elif _get(el, "geraet") is not None:
        yield el


def _setzen(o, k, v):
    if isinstance(o, dict):
        o[k] = v
    else:
        setattr(o, k, v)


def _position(x, y, reihenfolge):
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        x, y = 0.0, 0.0
    if reihenfolge == "zeilen":
        return (round(-y, 1), x)
    return (round(x, 1), -y)


def planen(blaetter, auswahl=None, einstellung=None, sheet_nr=None, sheet_name=None):
    """New identifiers for the main symbols.

    blaetter:  [(sheet key, elements)] in project order (all sheets: needed to rename
               the parts and to know the names in use)
    auswahl:   the main symbols to rename (elements), or None = all of `blaetter`
    -> [(alt, neu)] in counter order; old names that are only prefixes ('-K') are
    renamed one by one (no parts follow them)."""
    e = dict(STANDARD, **(einstellung or {}))
    reihen = {b: i for i, (b, _el) in enumerate(blaetter)}
    sheet_nr = sheet_nr or (lambda b: reihen.get(b, 0) + 1)
    sheet_name = sheet_name or (lambda b: str(sheet_nr(b)))
    ids = None if auswahl is None else {id(a) for a in auswahl}
    kandidaten, behalten = [], set()
    for b, elemente in blaetter:
        for el in elemente:
            f = geraete_felder(el)
            if f is None:
                for h, k in ind_felder(el):
                    behalten.add(str(h.get(k, "")).strip())
                continue
            holder, key, rolle, x, y = f
            alt = str(holder.get(key, "") or "").strip()
            if (rolle == "haupt" and (ids is None or id(el) in ids) and alt.upper() != "IND"
                    and kennbuchstaben(alt)):
                kandidaten.append((reihen.get(b, 0), _position(x, y, e["reihenfolge"]),
                                   b, el, holder, key, alt))
            else:
                behalten.add(alt)
    kandidaten.sort(key=lambda c: (c[0], c[1]))
    alte = {c[6] for c in kandidaten if zerlegen(c[6])[1] is not None}
    belegt = {n.upper() for n in behalten if n and n not in alte}
    zaehler, out, gesehen = {}, [], {}
    try:
        start, schritt = int(e["start"]), max(1, int(e["schritt"]))
    except (TypeError, ValueError):
        start, schritt = 1, 1
    for _r, _p, b, el, holder, key, alt in kandidaten:
        voll = zerlegen(alt)[1] is not None
        if voll and alt in gesehen:            # second main symbol with the same name
            continue
        kz = kennbuchstaben(alt)
        zk = (b, kz) if e["je_blatt"] else kz
        n = zaehler.get(zk, start)
        while True:
            neu = format_name(e["format"], sheet_nr(b), sheet_name(b), kz, n)
            n += schritt
            if neu.upper() not in belegt:
                break
        zaehler[zk] = n
        belegt.add(neu.upper())
        if voll:
            gesehen[alt] = neu
            out.append((alt, neu))
        else:
            out.append((holder, neu))       # prefix only: just this symbol
    return out


def anwenden(plan, blaetter):
    """Applies the plan to all sheets (in place). -> {sheet key: number of changed
    fields}; sheets without changes are left out."""
    namen = {alt: neu for alt, neu in plan if isinstance(alt, str) and alt != neu}
    einzeln = [(h, neu) for h, neu in plan if not isinstance(h, str)]
    geaendert = {}
    einzel_ids = {id(h): neu for h, neu in einzeln}
    for b, elemente in blaetter:
        n = 0
        for el in elemente:
            for h, k in ind_felder(el):
                if id(h) in einzel_ids:
                    h[k] = einzel_ids[id(h)]
                    n += 1
                    continue
                alt = str(h.get(k, "") or "").strip()
                if alt in namen:
                    h[k] = namen[alt]
                    n += 1
            for kp in _koerper(el):
                g = str(_get(kp, "geraet", "") or "")
                if g in namen:
                    if _get(kp, "bez", "") == g:
                        _setzen(kp, "bez", namen[g])
                    _setzen(kp, "geraet", namen[g])
                    n += 1
        if n:
            geaendert[b] = n
    return geaendert
