# -*- coding: utf-8 -*-
"""
katiecad/reports/leistenbild.py - Graphic view of a terminal strip (NO Tkinter).

One drawing per terminal strip, as it is mounted on the DIN rail and printed
to hang in the cabinet: the terminals side by side in mounting order, end
brackets at both ends, an end cover after the last terminal and wherever the
terminal type changes, partition plates where a terminal is marked
(Klemme.trennplatte), bridges as bars with dots, and above / below each
terminal its wire number, target and cable core (internal side on top, the
external / field side with its cables below, as mounted in the cabinet).

Input: the rows of reports.daten.klemmenplan (one strip = rows with the same
`_gk`). Output: pages (tabelle.Seite) with ordinary lines, texts and hatches.
"""

import re

from katiecad.model.core import Linie, Rechteck, Schraffur, Text, Polylinie, Kreis
from katiecad.reports import tabelle as TAB
from katiecad.reports.tabelle import LINIE, TEXT, Seite

TEILUNG = 8.0          # mm terminal pitch (A4)
KLEMME_H = 34.0        # mm terminal height
TOPE_B = 4.0           # mm end bracket width
DECKEL_B = 1.2         # mm end cover / partition plate thickness
BAND = 3.0             # mm per bridge lane
TEXT_H = 2.0           # mm texts at the terminals
NUM_H = 2.5            # mm terminal number
MIN_H = 1.4            # mm smallest text when shrinking
ZONE = 42.0            # mm longest text column above / below the terminals
# Colours of the terminals (as printed by other panel tools): normal grey, protective
# earth green with a yellow band, neutral blue; the DIN rail behind them
FARBE_KLEMME = "#c8c8c8"
FARBE_PE = "#2e9e44"
FARBE_PE_BAND = "#f2d22e"
FARBE_N = "#3d7fd1"
FARBE_SCHIENE = "#d9b400"
SCHIENE_H = 7.5          # mm visible height of the rail band (35 mm rail, scaled)
SCHRAUBE_R = 1.4         # mm screw head radius
# As mounted in the cabinet: internal wiring from above, field cables from below
OBEN, UNTEN = "intern", "extern"


def _gruppen(zeilen):
    """[(group key, [rows])] in row order."""
    out = []
    for z in zeilen:
        if not out or out[-1][0] != z.get("_gk"):
            out.append((z.get("_gk"), []))
        out[-1][1].append(z)
    return out


def _txt(x, y, s, h, winkel=0.0, anker="mitte_zentriert"):
    return Text(x, y, s, h, winkel, TAB.SCHRIFT[0], einfuegepunkt=anker, **TEXT)


def _passend(s, laenge, h):
    """Text height so that `s` fits into `laenge` (down to MIN_H)."""
    while h > MIN_H and TAB._breite(s, h) > laenge:
        h = round(h - 0.1, 3)
    return h


def _platte(el, x, yu, yo, b, voll=True):
    """Plate (end cover / partition): narrow filled rectangle."""
    pts = [(x, yu), (x + b, yu), (x + b, yo), (x, yo)]
    el.append(Polylinie(pts, True, staerke=0.25, **LINIE))
    if voll:
        el.append(Schraffur(pts, "solid", staerke=0.25, **LINIE))


def _tope(el, x, yu, yo, b, links):
    """End bracket: trapezoid, the wide side towards the terminals."""
    e = b * 0.45
    if links:
        pts = [(x, yu + e * 2), (x + b, yu), (x + b, yo), (x, yo - e * 2)]
    else:
        pts = [(x, yu), (x + b, yu + e * 2), (x + b, yo - e * 2), (x, yo)]
    el.append(Polylinie(pts, True, staerke=0.35, **LINIE))
    el.append(Linie(pts[0][0], (yu + yo) / 2.0, pts[1][0], (yu + yo) / 2.0,
                    staerke=0.18, **LINIE))


def _ziel_text(z, p):
    """Targets without the cable in brackets (the cable bar and core show it)."""
    ziele = z.get(p) or []
    if not isinstance(ziele, (list, tuple)):
        ziele = [ziele]
    return ", ".join(re.sub(r" \(.*\)$", "", str(t)) for t in ziele if str(t))


def leistenbild_seiten(zeilen, flaeche, titel="", skala=1.0, titel_leiste=""):
    """Draws every terminal strip of the terminal diagram rows.
    flaeche: (x1, y1, x2, y2); titel: page heading ('Terminal strip');
    titel_leiste: format of the strip line, e.g. 'Terminal strip {leiste}'.
    -> [Seite] (kopf = group key (installation location, strip))."""
    f = skala
    x1, y1, x2, y2 = flaeche
    teil, kh = TEILUNG * f, KLEMME_H * f
    tope, deckel = TOPE_B * f, DECKEL_B * f
    seiten = []
    for gk, reihe in _gruppen(zeilen):
        if not reihe:
            continue
        lanes = {"extern": 0, "intern": 0}
        for z in reihe:
            for seite, lane, *_r in z.get("_bruecke_s", ()):
                p = "intern" if z["_seiten"]["intern"] == seite else "extern"
                lanes[p] = max(lanes[p], lane + 1)
        # how many terminals fit on one page (plates take extra room)
        platz = (x2 - x1) - 2 * tope - 4 * f
        stuecke, akt, breite = [], [], 0.0
        for i, z in enumerate(reihe):
            w = teil + (deckel if z.get("_trenn") or _deckel_nach(reihe, i) else 0.0)
            if akt and breite + w > platz:
                stuecke.append(akt)
                akt, breite = [], 0.0
            akt.append(i)
            breite += w
        stuecke.append(akt)
        for k, idx in enumerate(stuecke):
            seiten.append(_seite(reihe, idx, gk, flaeche, titel, titel_leiste,
                                 lanes, f, k + 1, len(stuecke)))
    return seiten


def klemmen_art(z):
    """'pe', 'n' or '' (normal) from the terminal number / type: PE, PEN or a type
    with -PE / PE / GNYE; N or a blue type (-N, BU)."""
    num = str(z.get("num") or "").strip().upper()
    typ = str(z.get("typ") or "").strip().upper().replace(" ", "")
    if num in ("PE", "PEN") or "PE" in typ.replace("SPE", "") or "GNYE" in typ:
        return "pe"
    if num == "N" or typ.endswith(("-N", "BU", "-BL")):
        return "n"
    return ""


def _flaeche(el, x1, y1, x2, y2, farbe):
    """Coloured fill (own colour, printed in colour)."""
    pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    el.append(Schraffur(pts, "solid", staerke=0.1, layer="0", farbe=farbe, eig_farbe=True,
                        linientyp="Volllinie (schmal)"))


def _deckel_nach(reihe, i):
    """End cover after terminal i: last terminal, or the type changes."""
    if i == len(reihe) - 1:
        return True
    a, b = reihe[i].get("typ", ""), reihe[i + 1].get("typ", "")
    return bool(a and b and a != b)


def _seite(reihe, idx, gk, flaeche, titel, titel_leiste, lanes, f, k, n):
    x1, y1, x2, y2 = flaeche
    teil, kh = TEILUNG * f, KLEMME_H * f
    tope, deckel = TOPE_B * f, DECKEL_B * f
    band = BAND * f
    el = []
    eo, leiste = gk if isinstance(gk, tuple) and len(gk) == 2 else ("", "")
    kopf = (eo + " " if eo else "") + (leiste or "-")
    if titel:
        el.append(_txt(x1, y2, titel, TAB.TITEL_HOEHE * f, anker="oben_links"))
    zeile = titel_leiste.format(leiste=kopf) if titel_leiste else kopf
    if n > 1:
        zeile += f"  ({k}/{n})"
    el.append(_txt(x1, y2 - TAB.TITEL_PLATZ * f, zeile, 3.5 * f, anker="oben_links"))
    # vertical layout: cable bar | texts | bridges | terminal | bridges | texts | cable bar
    oben = y2 - TAB.TITEL_PLATZ * f - 8.0 * f
    unten = y1 + 2.0 * f
    ym = (oben + unten) / 2.0 + (lanes[UNTEN] - lanes[OBEN]) * band / 2.0
    ko, ku = ym + kh / 2.0, ym - kh / 2.0
    b_o = ko + lanes[OBEN] * band                # end of the upper bridge band
    b_u = ku - lanes[UNTEN] * band
    # text zones (from, to): as long as the longest text (at most ZONE);
    # the cable bar follows right after
    l_o, l_u = (min(ZONE * f, max([TAB._breite(t, TEXT_H * f) for i in idx
                                   for t in _teile(reihe[i], p)] or [0.0]) + 2.0 * f)
                for p in (OBEN, UNTEN))
    t_o = (b_o + 1.5 * f, min(oben - 5.0 * f, b_o + 1.5 * f + l_o))
    t_u = (max(unten + 5.0 * f, b_u - 1.5 * f - l_u), b_u - 1.5 * f)
    kabel_o, kabel_u = t_o[1] + 2.0 * f, t_u[0] - 2.0 * f
    # horizontal: centred
    breite = sum(teil + (deckel if reihe[i].get("_trenn") or _deckel_nach(reihe, i)
                         else 0.0) for i in idx)
    x = (x1 + x2) / 2.0 - breite / 2.0
    # DIN rail band behind the whole strip (from bracket to bracket)
    sh = SCHIENE_H * f / 2.0
    _flaeche(el, x - tope - 3 * f, ym - sh, x + breite + tope + 3 * f, ym + sh, FARBE_SCHIENE)
    _tope(el, x - tope, ku - 2 * f, ko + 2 * f, tope, True)
    xs = {}
    for i in idx:
        z = reihe[i]
        art = klemmen_art(z)
        _flaeche(el, x, ku, x + teil, ko, {"pe": FARBE_PE, "n": FARBE_N}.get(art, FARBE_KLEMME))
        if art == "pe":                                   # green-yellow: yellow band
            _flaeche(el, x + teil * 0.3, ku, x + teil * 0.7, ko, FARBE_PE_BAND)
        el.append(Rechteck(x, ku, x + teil, ko, staerke=0.35, **LINIE))
        # screws (top / bottom connection) and the rail fixing line
        r = SCHRAUBE_R * f
        for ys in (ko - kh * 0.27, ku + kh * 0.27):
            el.append(Kreis(x + teil / 2.0, ys, r, staerke=0.25, **LINIE))
            el.append(Linie(x + teil / 2.0 - r * 0.7, ys - r * 0.7, x + teil / 2.0 + r * 0.7,
                            ys + r * 0.7, staerke=0.18, **LINIE))
        el.append(Linie(x, ym - kh * 0.32, x + teil, ym - kh * 0.32, staerke=0.13, **LINIE))
        # terminal number near the top edge
        num = z.get("num") or "?"
        h = _passend(num, kh * 0.5, NUM_H * f)
        yn = ko - kh * 0.1
        if TAB._breite(num, h) > teil - 1.0 * f:
            el.append(_txt(x + teil / 2.0, ym + kh * 0.05, num, h, 90.0))
        else:
            el.append(_txt(x + teil / 2.0, yn, num, h))
        cx = x + teil / 2.0
        xs[i] = cx
        _anschluss(el, z, OBEN, cx, ko, t_o, teil, f, True)
        _anschluss(el, z, UNTEN, cx, ku, t_u, teil, f, False)
        x += teil
        if z.get("_trenn"):
            _platte(el, x, ku - 3 * f, ko + 3 * f, deckel)
            x += deckel
        elif _deckel_nach(reihe, i):
            _platte(el, x, ku, ko, deckel, voll=False)
            el.append(Linie(x, ku, x + deckel, ko, staerke=0.13, **LINIE))
            x += deckel
    _tope(el, x, ku - 2 * f, ko + 2 * f, tope, False)
    _bruecken(el, reihe, idx, xs, ko, ku, band, f)
    for p, y_bar, nach_oben in ((OBEN, kabel_o, True), (UNTEN, kabel_u, False)):
        _kabel_balken(el, reihe, idx, xs, p, y_bar, teil, f, nach_oben)
    sp = Seite(el)
    sp.kopf = gk
    return sp


def _teile(z, p):
    """Texts of side p of a row: wire number, target, core + conductor."""
    ziel = _ziel_text(z, p)
    draht = z.get(p + "_draht", "")
    leiter = z.get(p + "_leiter", "")
    kabel = z.get(p + "_kabel") or []
    ader = ""
    if isinstance(kabel, (list, tuple)) and kabel:
        ader = str(kabel[0]).split(" / ")[-1]
    if ader and leiter.startswith(ader):
        ader = ""                                # colour = core name: show it once
    return [t for t in (draht, ziel, " ".join(t for t in (ader, leiter) if t)) if t]


def _anschluss(el, z, p, cx, y0, zone, teil, f, nach_oben):
    """Wire number + target + core of side p as vertical text in `zone`."""
    von, bis = zone
    laenge = abs(bis - von)
    if laenge <= 2 * f:
        return
    teile = _teile(z, p)
    if not teile:
        return
    ziel, draht = _ziel_text(z, p), z.get(p + "_draht", "")
    # short stub from the terminal to the text
    if ziel or draht:
        el.append(Linie(cx, y0, cx, von if nach_oben else bis, staerke=0.25, **LINIE))
    # one column of text per part (rotated 90 degrees, reads bottom-up)
    n = len(teile)
    h = min(TEXT_H * f, (teil - 0.6 * f) / max(1, n) / TAB.TEXT_ZEILE * 1.1)
    for t in teile:
        h = min(h, _passend(t, laenge, h))
    abst = h * TAB.TEXT_ZEILE
    x0 = cx - (n - 1) * abst / 2.0
    for j, t in enumerate(teile):
        if nach_oben:
            el.append(_txt(x0 + j * abst, von + 0.5 * f, t, h, 90.0, "mitte_links"))
        else:
            el.append(_txt(x0 + j * abst, bis - 0.5 * f, t, h, 90.0, "mitte_rechts"))


def _bruecken(el, reihe, idx, xs, ko, ku, band, f):
    """Bridge bars with dots on the side of the bridge. A bar runs while the
    rows say it continues (`_bruecke_s`: side, lane, dot, up, down)."""
    offen = {}                                  # (p, lane) -> [(i, dot)]
    laeufe = []

    def schliessen(schl):
        if offen.get(schl):
            laeufe.append((schl, offen.pop(schl)))

    for i in idx:
        z = reihe[i]
        for seite, lane, punkt, hoch, runter in z.get("_bruecke_s", ()):
            p = "intern" if z["_seiten"]["intern"] == seite else "extern"
            schl = (p, lane)
            if not hoch:
                schliessen(schl)
            offen.setdefault(schl, []).append((i, punkt))
            if not runter:
                schliessen(schl)
    for schl in list(offen):
        schliessen(schl)
    for (p, lane), lauf in laeufe:
        y = (ko + (lane + 0.5) * band) if p == OBEN else (ku - (lane + 0.5) * band)
        y0 = ko if p == OBEN else ku
        el.append(Linie(xs[lauf[0][0]], y, xs[lauf[-1][0]], y, staerke=0.5, **LINIE))
        for i, punkt in lauf:
            if punkt:
                el.append(TAB._punkt(xs[i], y, f))
                el.append(Linie(xs[i], y0, xs[i], y, staerke=0.25, **LINIE))


def _kabel_balken(el, reihe, idx, xs, p, y, teil, f, nach_oben):
    """Bar over the terminals that lead to the same cable, with its name."""
    laeufe = []
    for i in idx:
        cab = reihe[i].get("_" + p + "_cab", "")
        if cab and laeufe and laeufe[-1][0] == cab and laeufe[-1][2] == i - 1:
            laeufe[-1][2] = i
        elif cab:
            laeufe.append([cab, i, i])
    for cab, a, b in laeufe:
        xa, xb = xs[a] - teil * 0.4, xs[b] + teil * 0.4
        el.append(Linie(xa, y, xb, y, staerke=0.5, **LINIE))
        d = 1.2 * f if nach_oben else -1.2 * f
        for xx in (xa, xb):
            el.append(Linie(xx, y, xx, y - d, staerke=0.35, **LINIE))
        el.append(_txt((xa + xb) / 2.0, y + (0.8 * f if nach_oben else -0.8 * f), cab,
                       TEXT_H * f, anker="unten_zentriert" if nach_oben else "oben_zentriert"))
