# -*- coding: utf-8 -*-
"""
katiecad/electrical/drahtnummern.py - Wire numbering (BSD-3-Clause, NO Tkinter).

A *wire* (Draht) is everything that is electrically the same conductor between
two devices or terminals: all drawn wire pieces joined by junctions, corners,
paired cross references and the same device pin. A terminal ends the wire
(its top and bottom side are different conductors), so is the other pin of a
device.

Every wire gets ONE number. The number is stored in a ``Drahtnummer`` element
whose insertion point lies on one of the wire pieces (like the connection
definition point of other electrical CAD systems), so it survives when the
automatic wires are rebuilt.

Rules, the first that applies wins:
  1. A manual number (typed or edited by the user) is kept.
  2. Keep mode: a wire that already has an automatic number keeps it.
  3. PLC: the wire reaches a channel of a DI/DO/AI/AO module -> its address
     with the module type as prefix (pin "DI0.00" -> "DI0.00", pin "0.00" or
     Siemens style "I0.0" / "%IX0.0" on a DI module -> "DI0.00" / "DI0.0").
  4. Potential (on by default): the wire reaches a potential arrow (cross
     reference) -> its free text ("+24VDC", "+24VDC1", "L1" ...), also when the
     arrow pair only continues the wire on another sheet.
  5. Format, default "{sheet}{n:02}" with the counter starting at 0: sheet 10
     gives 1000, 1001 ... (counted left to right, top to bottom). The counter
     start is a setting ("start"); "{sheet}.{n}" with start 1 gives 10.1, 10.2 ...

Placeholders of the format: {sheet} / {hoja}, {sheetname} / {nombre}, {n}
(format specs allowed: "{sheet}-{n:02}").
"""

import math
import re
from collections import defaultdict
from string import Formatter

from katiecad.model.core import Leitung, Drahtnummer, BlockReferenz, ist_einpolig

STANDARD = {"format": "{sheet}{n:02}", "start": 0, "sps": True, "potenzial": True,
            "hoehe": 2.5, "je_ast": True}
LAGE_TOL = 0.3          # mm: label insertion point -> wire
ARTEN_SPS = ("DI", "DO", "AI", "AO")


class DrahtformatFehler(ValueError):
    """The wire number format could not yield a free number."""


def einstellungen(doku):
    """Project settings merged over the defaults."""
    e = dict(STANDARD)
    if isinstance(doku, dict) and isinstance(doku.get("drahtnummern"), dict):
        gespeichert = doku["drahtnummern"]
        e.update({k: v for k, v in gespeichert.items() if k in STANDARD})
        if "format" in gespeichert and "start" not in gespeichert:
            e["start"] = 1          # projects saved before "start" existed keep counting from 1
    try:
        e["start"] = max(0, int(e["start"]))
    except (TypeError, ValueError):
        e["start"] = STANDARD["start"]
    return e


def _format_werte(sheet, sheetname, n):
    return {"sheet": sheet, "hoja": sheet, "sheetname": sheetname,
            "nombre": sheetname, "n": n}


def format_gueltig(fmt, start=0):
    """The format must render an actual, varying counter field."""
    try:
        if not any(feld == "n" for _, feld, _, _ in Formatter().parse(fmt)):
            return False
        return (fmt.format(**_format_werte(1, "Blatt", start))
                != fmt.format(**_format_werte(1, "Blatt", start + 1)))
    except (AttributeError, IndexError, KeyError, OverflowError, TypeError, ValueError):
        return False


def format_text(fmt, sheet, sheetname, n):
    """'{sheet}.{n}' -> '3.12'. Invalid formats fall back to the default."""
    werte = _format_werte(sheet, sheetname, n)
    try:
        return str(fmt or STANDARD["format"]).format(**werte)
    except (AttributeError, IndexError, KeyError, OverflowError, TypeError, ValueError):
        return STANDARD["format"].format(**werte)


# ------------------------------------------------------------------
# Geometry
# ------------------------------------------------------------------
def _abstand_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def leitung_unter(leitungen, x, y, tol=LAGE_TOL):
    """Wire piece the point lies on (nearest within tol) or None."""
    best, bd = None, tol
    for l in leitungen:
        d = _abstand_segment(x, y, l.x1, l.y1, l.x2, l.y2)
        if d <= bd:
            best, bd = l, d
    return best


def _laenge(l):
    return math.hypot(l.x2 - l.x1, l.y2 - l.y1)


def platzierung(l):
    """(x, y, winkel) for a new label on wire piece l: centre of the piece,
    text above a horizontal and left of a vertical wire."""
    mx, my = (l.x1 + l.x2) / 2.0, (l.y1 + l.y2) / 2.0
    senkrecht = abs(l.x2 - l.x1) < abs(l.y2 - l.y1)
    return mx, my, (90.0 if senkrecht else 0.0)


def _pkt(x, y):
    return (round(x, 2), round(y, 2))


def aeste(leitungen):
    """Branches of the pieces of ONE wire on ONE sheet: pieces joined only at
    corners (exactly two pieces meet) form one branch; where three or more
    pieces meet (a T without junction symbol) or at the arms of a junction
    symbol (different points) a new branch starts.
    -> [[Leitung]] (every branch of a wire carries its own label)."""
    an = defaultdict(list)
    for l in leitungen:
        an[_pkt(l.x1, l.y1)].append(l)
        an[_pkt(l.x2, l.y2)].append(l)
    uf = _UF()
    for l in leitungen:
        uf.finde(id(l))
    for stuecke in an.values():
        if len(stuecke) == 2 and stuecke[0] is not stuecke[1]:
            uf.vereinen(id(stuecke[0]), id(stuecke[1]))
    gruppen = defaultdict(list)
    for l in leitungen:
        gruppen[uf.finde(id(l))].append(l)
    return sorted(gruppen.values(), key=lambda g: min((min(l.x1, l.x2), -max(l.y1, l.y2))
                                                     for l in g))


# ------------------------------------------------------------------
# Wires = connected wire pieces
# ------------------------------------------------------------------
class _UF:
    def __init__(self):
        self.p = {}

    def finde(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def vereinen(self, a, b):
        ra, rb = self.finde(a), self.finde(b)
        if ra != rb:
            self.p[rb] = ra


class Draht:
    __slots__ = ("leitungen", "knoten", "nummer", "labels")

    def __init__(self):
        self.leitungen = []     # [(sheet, Leitung)]
        self.knoten = []        # net nodes
        self.nummer = ""
        self.labels = []        # [(sheet, Drahtnummer)]

    def blaetter(self):
        out = []
        for b, _l in self.leitungen:
            if b not in out:
                out.append(b)
        return out


def draehte(netz):
    """Groups the wire pieces of a built net into wires.
    -> [Draht] (only groups with at least one drawn wire piece)."""
    uf = _UF()
    for n in netz.knoten:
        uf.finde(id(n))
        for k in n.kanten:
            uf.vereinen(id(k.a), id(k.b))
        if n.art == "qv":
            for p in n.partner:
                uf.vereinen(id(n), id(p))
    gruppen = defaultdict(Draht)
    for n in netz.knoten:
        gruppen[uf.finde(id(n))].knoten.append(n)
    for (blatt, l), kante in netz.leitung_kanten():
        gruppen[uf.finde(id(kante.a))].leitungen.append((blatt, l))
    return [d for d in gruppen.values() if d.leitungen]


def netz_nummern(netz, blaetter):
    """Writes the number of the Drahtnummer labels into the net nodes of their
    wire (Knoten.draht, Knoten.draht_daten = (colour, cross-section)), so that
    reports find the wire number at every terminal side or pin.
    A manual label wins over an automatic one. -> number of wires with a number."""
    blaetter = [(b, el) for b, el in blaetter
                if any(isinstance(e, Drahtnummer) for e in el)]
    if not blaetter:
        return 0
    ds = draehte(netz)
    zu_draht = {}
    for d in ds:
        for b, l in d.leitungen:
            zu_draht[(b, id(l))] = d
    for b, elemente in blaetter:
        leitungen = [l for l in elemente if isinstance(l, Leitung)]
        for lab in elemente:
            if isinstance(lab, Drahtnummer) and lab.inhalt.strip():
                l = leitung_unter(leitungen, lab.x, lab.y)
                d = zu_draht.get((b, id(l))) if l is not None else None
                if d is not None:
                    d.labels.append((b, lab))
    n = 0
    for d in ds:
        labs = [lab for _b, lab in d.labels]
        if not labs:
            continue
        labs.sort(key=lambda lab: not lab.manuell)
        farbe = next((lab.aderfarbe for lab in labs if lab.aderfarbe), "")
        qs = next((lab.querschnitt for lab in labs if lab.querschnitt), "")
        for k in d.knoten:
            k.draht = labs[0].inhalt.strip()
            k.draht_daten = (farbe, qs)
        n += 1
    return n


def gleicher_draht(elemente, leitungen):
    """All wire pieces of ONE sheet that belong to the same wires (up to the next
    terminal or device pin) as `leitungen`, e.g. to give a whole conductor one
    line type. -> [Leitung] (the given ones included)."""
    from katiecad.reports.netz import Netz
    ids = {id(l) for l in leitungen}
    if not ids:
        return []
    out = []
    for d in draehte(Netz.aufbauen([(0, elemente)])):
        stuecke = [l for _b, l in d.leitungen]
        if any(id(l) in ids for l in stuecke):
            out.extend(stuecke)
    gesehen = {id(l) for l in out}
    return out + [l for l in leitungen if id(l) not in gesehen]


# ------------------------------------------------------------------
# Number sources
# ------------------------------------------------------------------
def _sps_art(block):
    a = str((getattr(block, "attribute", None) or {}).get("SPS", "")).strip().upper()
    return a if a in ARTEN_SPS else ""


def sps_adresse(draht):
    """'DI0.00' if the wire reaches a channel of a PLC I/O module, else ''."""
    treffer = []
    for n in draht.knoten:
        if n.art != "pin" or not isinstance(n.bes, BlockReferenz):
            continue
        art = _sps_art(n.bes)
        adr = (n.name or "").strip()
        if not art or not re.search(r"\d", adr):
            continue                     # supply pins (L+, M) are no channels
        # 'DI0.00' stays, '0.00' -> 'DI0.00', Siemens style 'I0.0' / '%IX0.0' -> 'DI0.0'
        rest = adr[len(art):] if adr.upper().startswith(art) else re.sub(r"^[%A-Za-z]+", "", adr)
        treffer.append(art + rest)
    return sorted(treffer)[0] if treffer else ""


def potenzial(draht):
    """Name of the potential arrow (cross reference) the wire reaches: '+24VDC',
    '+24VDC1', 'L1', '0V' ... The text is free, so circuits of the same voltage can
    be told apart. Unpaired arrows (a potential used in many places) come first,
    then a pair outgoing/incoming that continues the wire on another sheet.
    -> '' without arrow."""
    frei = sorted({n.text for n in draht.knoten if n.art == "qv" and not n.partner and n.text})
    if frei:
        return frei[0]
    paar = sorted({n.text for n in draht.knoten if n.art == "qv" and n.partner and n.text})
    return paar[0] if paar else ""


def _einpolige_punkte(blaetter):
    """{(sheet, point)} of the pins of single-pole devices (ignored by the net
    unless 'evaluate single-pole too' is on)."""
    from katiecad.electrical.logic import einrast_punkte
    out = set()
    for b, elemente in blaetter:
        for el in elemente:
            if ist_einpolig(el):
                out.update((b, _pkt(x, y)) for x, y in einrast_punkte(el))
    return out


def _sortierschluessel(draht, blatt):
    """Left to right, top to bottom on the given sheet."""
    pts = [(min(l.x1, l.x2), -max(l.y1, l.y2)) for b, l in draht.leitungen if b == blatt]
    return min(pts) if pts else (0.0, 0.0)


# ------------------------------------------------------------------
# Plan
# ------------------------------------------------------------------
class Plan:
    """Result of `planen`; applied per sheet with `anwenden`."""

    def __init__(self):
        self.draehte = []
        self.neu = defaultdict(list)       # sheet -> [Drahtnummer]
        self.weg = defaultdict(list)       # sheet -> [Drahtnummer]
        self.text = []                     # [(Drahtnummer, new text)]

    @property
    def anzahl(self):
        return (sum(len(v) for v in self.neu.values())
                + sum(len(v) for v in self.weg.values()) + len(self.text))


def planen(blaetter, netz, sheet_nr=None, sheet_name=None, einstellung=None,
           neu_nummerieren=False):
    """Computes the wire numbers of the whole project.

    blaetter:  [(sheet key, elements)] in project order, the same that built `netz`
    netz:      reports.netz.Netz built from `blaetter`
    sheet_nr:  sheet key -> number shown in {sheet} (default: position + 1)
    sheet_name: sheet key -> name for {sheetname}
    neu_nummerieren: True = recompute every automatic number,
                     False = only wires without a number get one.
    -> Plan"""
    e = einstellung or dict(STANDARD)
    reihenfolge = {b: i for i, (b, _el) in enumerate(blaetter)}
    sheet_nr = sheet_nr or (lambda b: reihenfolge.get(b, 0) + 1)
    sheet_name = sheet_name or (lambda b: str(sheet_nr(b)))
    hoehe = float(e.get("hoehe") or STANDARD["hoehe"])

    plan = Plan()
    ds = draehte(netz)
    plan.draehte = ds
    # labels -> wires
    zu_draht = {}
    for d in ds:
        for b, l in d.leitungen:
            zu_draht[(b, id(l))] = d
    for b, elemente in blaetter:
        leitungen = [l for l in elemente if isinstance(l, Leitung)]
        for lab in elemente:
            if not isinstance(lab, Drahtnummer):
                continue
            l = leitung_unter(leitungen, lab.x, lab.y)
            d = zu_draht.get((b, id(l))) if l is not None else None
            if d is not None:
                d.labels.append((b, lab))
            elif not lab.manuell:
                plan.weg[b].append(lab)          # automatic label without wire

    # wires of the single-pole representation (they touch a pin of a single-pole
    # device) are no conductors of their own: no number, automatic labels go
    einpolig = _einpolige_punkte(blaetter)
    if einpolig:
        bleiben = []
        for d in ds:
            if any((b, _pkt(l.x1, l.y1)) in einpolig or (b, _pkt(l.x2, l.y2)) in einpolig
                   for b, l in d.leitungen):
                for b, lab in d.labels:
                    if not lab.manuell:
                        plan.weg[b].append(lab)
            else:
                bleiben.append(d)
        ds = bleiben
        plan.draehte = ds

    # numbers that are fixed (manual, or kept)
    vergeben = set()
    offen = []
    for d in ds:
        manuell = [lab for _b, lab in d.labels if lab.manuell and lab.inhalt.strip()]
        auto = [lab for _b, lab in d.labels if not lab.manuell]
        if manuell:
            d.nummer = manuell[0].inhalt.strip()
        elif auto and not neu_nummerieren:
            d.nummer = auto[0].inhalt.strip()
        elif e.get("sps", True) and sps_adresse(d):
            d.nummer = sps_adresse(d)
        elif e.get("potenzial") and potenzial(d):
            d.nummer = potenzial(d)
        else:
            offen.append(d)
            continue
        vergeben.add(d.nummer)

    # counter per sheet
    offen.sort(key=lambda d: (reihenfolge.get(d.blaetter()[0], 0),
                              _sortierschluessel(d, d.blaetter()[0])))
    start = int(e.get("start", STANDARD["start"]) or 0)
    fmt = str(e.get("format") or STANDARD["format"])
    if offen and not format_gueltig(fmt, start):
        raise DrahtformatFehler(fmt)
    zaehler = defaultdict(lambda: start - 1)
    for d in offen:
        b = d.blaetter()[0]
        nr, name = sheet_nr(b), sheet_name(b)
        # A unique counter format can skip at most one value per reserved label.
        for _ in range(len(vergeben) + 1):
            zaehler[b] += 1
            t = format_text(fmt, nr, name, zaehler[b])
            if t not in vergeben:
                break
        else:
            raise DrahtformatFehler(fmt)
        d.nummer = t
        vergeben.add(t)

    # labels: one per branch (je_ast) or one per wire and sheet
    je_ast = bool(e.get("je_ast", STANDARD["je_ast"]))
    for d in ds:
        for b in d.blaetter():
            stuecke = [l for bb, l in d.leitungen if bb == b]
            gruppen = aeste(stuecke) if je_ast else [stuecke]
            zu_gruppe = {id(l): i for i, g in enumerate(gruppen) for l in g}
            labs_je = defaultdict(list)
            for bb, lab in d.labels:
                if bb == b:
                    # label -> branch of the piece it lies on
                    l = leitung_unter(stuecke, lab.x, lab.y)
                    labs_je[zu_gruppe.get(id(l), 0)].append(lab)
            for i, g in enumerate(gruppen):
                labs = labs_je.get(i, [])
                auto = [lab for lab in labs if not lab.manuell]
                hat_manuell = any(lab.manuell for lab in labs)
                if auto:
                    behalten = [] if hat_manuell else auto[:1]
                    for lab in behalten:
                        if lab.inhalt != d.nummer or lab.auto_text != d.nummer:
                            plan.text.append((lab, d.nummer))
                    plan.weg[b].extend(auto[len(behalten):])
                elif not hat_manuell:
                    l = max(g, key=_laenge)
                    x, y, w = platzierung(l)
                    plan.neu[b].append(Drahtnummer(x, y, d.nummer, hoehe=hoehe,
                                                   winkel=w, auto_text=d.nummer))
    return plan


def anwenden(plan, blatt, elemente):
    """Applies the plan to the element list of ONE sheet (in place).
    -> number of changes on that sheet."""
    n = 0
    weg = {id(x) for x in plan.weg.get(blatt, ())}
    if weg:
        vorher = len(elemente)
        elemente[:] = [el for el in elemente if id(el) not in weg]
        n += vorher - len(elemente)
    ids = {id(el) for el in elemente}
    for lab, text in plan.text:
        if id(lab) in ids:
            lab.inhalt = text
            lab.auto_text = text
            n += 1
    for lab in plan.neu.get(blatt, ()):
        elemente.append(lab)
        n += 1
    return n

