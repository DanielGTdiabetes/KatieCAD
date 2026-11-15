# -*- coding: utf-8 -*-
"""
katiecad/reports/seiten.py - Assemble report sheets (NO Tkinter).

Creates cover sheet, table of contents, device list, terminal diagram and
cable plan as lists of layout elements (A4 landscape, sheet frame and
title block from the chosen template). The application writes ordinary
sheets into the project from them.

Order of the sheets:
    cover sheet, table of contents | drawing sheets | device list,
    terminal diagram, cable plan
The sheet numbers of the drawing sheets depend on the number of sheets
before them; the function iterates until the page counts are stable.
"""

import datetime
import json
import os

from katiecad.model.core import (Text, Linie, Rechteck, FARBEN, ZEICHEN_FARBE,
                                 ZEICHNUNGSFORMATE)
from katiecad.model import titleblock as TB
from katiecad.common.i18n import tr, datum_text
from katiecad.reports import tabelle as TAB
from katiecad.reports import daten as D
from katiecad.reports import daten_listen as DL
from katiecad.reports import daten_sps as DS
from katiecad.reports import leistenbild as LB
from katiecad.model import kanal_katalog as KK
from katiecad.model import mechanik as MECH
from katiecad.reports.netz import Netz
from katiecad.reports.tabelle import (Spalte, tabellen_seiten,
                                      zeilen_vorbereiten, TEXT, LINIE)

FORMAT = "A4 (297x210)"
FORMATE = {"a4": "A4 (297x210)", "a3": "A3 (420x297)"}


def format_name(schluessel):
    """'a4' / 'a3' -> drawing format name (unknown -> A4)."""
    return FORMATE.get(str(schluessel or "").lower(), FORMAT)


def skala_fuer(fmt):
    """Scale factor of a format compared to A4 (A3 = 1.414)."""
    return ZEICHNUNGSFORMATE[fmt][0] / ZEICHNUNGSFORMATE[FORMAT][0]
STANDARD_TYPEN = ("deckblatt", "inhalt", "geraete", "klemmen", "kabel")
TYPEN = STANDARD_TYPEN + ("verbindungen", "stueckliste", "querverweise",
                          "potenziale", "stecker", "etiketten", "revisionen", "sps",
                          "kanaele", "mechanik", "leistenbild")
LISTEN = ("geraete", "klemmen", "kabel", "verbindungen", "stueckliste",
          "querverweise", "potenziale", "stecker", "etiketten", "revisionen", "sps", "kanaele",
          "mechanik")
NETZ_LISTEN = {"sps", "klemmen", "kabel", "verbindungen", "stueckliste", "querverweise",
               "potenziale", "stecker", "etiketten", "leistenbild"}
GRAFIKEN = ("leistenbild",)        # drawings (no table, not in CSV / Excel)
SEITEN_MODI = D.SEITEN_MODI        # terminal diagram: external / internal side

TITEL_TAGS = TB.DATA_TAGS          # (kept for compatibility)
DATEN_SCHLUESSEL = ("anlage", "kunde", "auftrag", "zeichnungsnummer", "firma",
                    "gezeichnet", "geprueft", "revision", "datum")


class BlattInfo:
    """A drawing sheet of the project (without report sheets)."""

    def __init__(self, name, elemente, beschreibung="", einbauort="", art=""):
        self.einbauort = einbauort
        self.art = art
        self.name = name
        self.elemente = elemente
        self.beschreibung = beschreibung


class BerichtSeite:
    def __init__(self, typ, name, elemente, format=FORMAT):
        self.typ, self.name, self.elemente = typ, name, elemente
        self.format = format


class Vorlage:
    """Title block template (elements with origin at the bottom right)."""

    def __init__(self, name, elemente):
        self.name = name
        self.elemente = list(elemente)
        xs, ys = [0.0], [0.0]
        for e in self.elemente:
            b = e.bbox()
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        self.breite = max(0.0, -min(xs))
        self.hoehe = max(0.0, max(ys))


# ------------------------------------------------------------------
# Column definitions (customisable via report_templates/<type>.json)
# ------------------------------------------------------------------
_STANDARD = {
    "inhalt": [("nr", "rep.col.blatt", 8, "r"), ("name", "rep.col.bezeichnung", 40, "l"),
               ("beschreibung", "rep.col.beschreibung", 70, "l"),
               ("typ", "rep.col.art", 24, "l")],
    "geraete": [("pos", "rep.col.pos", 6, "r"), ("ind", "rep.col.ind", 18, "l"),
                ("einbauort", "rep.col.einbauort", 26, "l"),
                ("hersteller", "rep.col.hersteller", 26, "l"),
                ("typ", "rep.col.typ", 40, "l"), ("per", "rep.col.per", 40, "l"),
                ("anzahl", "rep.col.anzahl", 9, "r"),
                ("ort", "rep.col.fundstellen", 50, "l"),
                ("funktion", "rep.col.funktion", 40, "l")],
    # "rep.col.s_xxx|extern": title with the side name (see _titel)
    "klemmen": [("leiste", "rep.col.leiste", 14, "l"),
                ("einbauort", "rep.col.einbauort", 22, "l"),
                ("hersteller", "rep.col.hersteller", 16, "l"),
                ("typ", "rep.col.typ", 18, "l"),
                ("extern_kabel", "rep.col.s_kabel|extern", 18, "l"),
                ("extern_leiter", "rep.col.s_leiter|extern", 16, "l"),
                ("extern_draht", "rep.col.s_draht|extern", 14, "l"),
                ("extern", "rep.col.s_ziel|extern", 40, "l"),
                ("num", "rep.col.num", 9, "l"),
                ("bruecke", "rep.col.bruecke", 12, "c"),
                ("intern", "rep.col.s_ziel|intern", 40, "l"),
                ("intern_draht", "rep.col.s_draht|intern", 14, "l"),
                ("intern_leiter", "rep.col.s_leiter|intern", 16, "l"),
                ("intern_kabel", "rep.col.s_kabel|intern", 18, "l"),
                ("ort", "rep.col.ort", 16, "l"),
                ("funktion", "rep.col.funktion", 34, "l")],
    "kabel": [("cab", "rep.col.cab", 14, "l"),
              ("einbauort", "rep.col.einbauort", 26, "l"),
              ("hersteller", "rep.col.hersteller", 22, "l"),
              ("typ", "rep.col.typ", 26, "l"),
              ("ader", "rep.col.ader", 10, "l"), ("von", "rep.col.von", 50, "l"),
              ("nach", "rep.col.nach", 50, "l"), ("ort", "rep.col.ort", 18, "l")],
    "verbindungen": [("pos", "rep.col.pos", 6, "r"), ("draht", "rep.col.draht", 12, "l"),
                     ("von", "rep.col.vl_von", 50, "l"),
                     ("nach", "rep.col.vl_nach", 50, "l"),
                     ("kabel", "rep.col.kabelader", 24, "l"),
                     ("ort", "rep.col.ort", 18, "l"),
                     ("einbauort", "rep.col.einbauort", 26, "l")],
    "stueckliste": [("pos", "rep.col.pos", 6, "r"), ("anzahl", "rep.col.anzahl", 8, "r"),
                    ("typ", "rep.col.typ", 34, "l"),
                    ("hersteller", "rep.col.hersteller", 26, "l"),
                    ("bestellnr", "rep.col.bestellnr", 28, "l"),
                    ("beschreibung", "rep.col.beschreibung", 40, "l"),
                    ("kennzeichen", "rep.col.kennzeichen", 50, "l")],
    "querverweise": [("name", "rep.col.qv_name", 30, "l"),
                     ("abgehend", "rep.col.abgehend", 60, "l"),
                     ("ankommend", "rep.col.ankommend", 60, "l"),
                     ("anzahl", "rep.col.anzahl", 9, "r")],
    "potenziale": [("potenzial", "rep.col.potenzial", 24, "l"),
                   ("anzahl", "rep.col.anzahl", 9, "r"),
                   ("anschluesse", "rep.col.anschluesse", 90, "l"),
                   ("orte", "rep.col.fundstellen", 40, "l")],
    "stecker": [("stecker", "rep.col.stecker", 18, "l"),
                ("einbauort", "rep.col.einbauort", 26, "l"),
                ("pin", "rep.col.pin", 10, "l"),
                ("ziele", "rep.col.anschluesse", 90, "l"),
                ("ort", "rep.col.ort", 18, "l")],
    "etiketten": [("etikett", "rep.col.etikett", 34, "l"),
                  ("art", "rep.col.art", 16, "l"),
                  ("einbauort", "rep.col.einbauort", 26, "l"),
                  ("typ", "rep.col.typ", 34, "l"), ("ort", "rep.col.ort", 18, "l")],
    "sps": [("station", "rep.col.station", 18, "l"),
            ("baugruppe", "rep.col.baugruppe", 16, "l"),
            ("platz", "rep.col.platz", 10, "l"),
            ("art", "rep.col.art", 8, "l"),
            ("adresse", "rep.col.adresse", 12, "l"),
            ("datentyp", "rep.col.datentyp", 10, "l"),
            ("symbol", "rep.col.symbol", 26, "l"),
            ("kommentar", "rep.col.kommentar", 40, "l"),
            ("anschluss", "rep.col.anschluesse", 40, "l"),
            ("ort", "rep.col.ort", 16, "l")],
    "kanaele": [("ref", "rep.col.bestellnr", 26, "l"),
                ("hersteller", "rep.col.hersteller", 20, "l"),
                ("masse", "rep.col.kanal_masse", 18, "l"),
                ("art", "rep.col.art", 22, "l"),
                ("stueck", "rep.col.anzahl", 10, "r"),
                ("laenge", "rep.col.laenge_m", 14, "r"),
                ("stangen", "rep.col.stangen", 14, "r")],
    "mechanik": [("pos", "rep.col.pos", 6, "r"), ("teil", "rep.col.teil", 22, "l"),
                 ("seite", "rep.col.seite", 14, "l"), ("art", "rep.col.art", 40, "l"),
                 ("masse", "rep.col.masse", 16, "l"), ("x", "rep.col.x", 12, "r"),
                 ("y", "rep.col.y", 12, "r"), ("tiefe", "rep.col.tiefe", 14, "r")],
    "revisionen": [("stand", "rep.col.stand", 12, "l"),
                   ("aenderung", "rep.col.aenderung", 100, "l"),
                   ("name", "rep.col.name", 30, "l"),
                   ("datum", "rep.col.datum", 22, "l")],
}
_OPTIONEN = {"textgroesse": 2.5, "zeilenhoehe": 6.0}


def _titel(t, seiten="auto"):
    """Column title: 'rep.col.s_draht|extern' -> 'Wire ext.'; in the mode
    'oben_unten' the external side is 'top' and the internal one 'bottom'."""
    if "|" not in t:
        return tr(t)
    schl, seite = t.split("|", 1)
    if seiten == "oben_unten":
        seite = {"extern": "oben", "intern": "unten"}.get(seite, seite)
    return tr(schl, seite=tr("rep.seite." + seite))


def lade_spalten(typ, ordner=(), seiten="auto"):
    """(columns, options). `ordner`: folders containing <type>.json (later =
    higher priority). Faulty files are ignored. `seiten`: side mode of the
    terminal diagram (only changes the built-in titles)."""
    spalten = [Spalte(k, _titel(t, seiten), g, a) for k, t, g, a in _STANDARD[typ]]
    opt = dict(_OPTIONEN)
    for o in ordner:
        pfad = os.path.join(o, typ + ".json")
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        neue = []
        for s in d.get("spalten", []) if isinstance(d.get("spalten"), list) else []:
            if isinstance(s, dict) and s.get("key"):
                try:
                    neue.append(Spalte(str(s["key"]), str(s.get("titel", s["key"])),
                                       float(s.get("breite", 10)),
                                       str(s.get("ausrichtung", "l"))))
                except (TypeError, ValueError):
                    pass
        if neue:
            spalten = neue
        for k in opt:
            try:
                v = float(d[k])
                if 1.0 <= v <= 20.0:
                    opt[k] = v
            except (KeyError, TypeError, ValueError):
                pass
    return spalten, opt


def spalten_ordner(programm_ordner, projekt_ordner=None):
    out = [os.path.join(programm_ordner, "report_templates")]
    if projekt_ordner:
        out.append(os.path.join(projekt_ordner, "report_templates"))
    return out


# ------------------------------------------------------------------
# Frame, title block, area
# ------------------------------------------------------------------
def _rahmen(fmt=FORMAT):
    b, h = ZEICHNUNGSFORMATE[fmt]
    aussen, innen = TB.frame_rects(b, h)
    dick = {"layer": "0", "farbe": ZEICHEN_FARBE, "linientyp": "Volllinie (breit)",
            "eig_farbe": True, "staerke": 0.7}
    duenn = {"layer": "0", "farbe": ZEICHEN_FARBE, "linientyp": "Volllinie (schmal)",
             "eig_farbe": True, "staerke": 0.35}
    return aussen, innen, [Rechteck(*aussen, **dick), Rechteck(*innen, **duenn)]


def inhaltsflaeche(vorlage, fmt=FORMAT):
    """(x1, y1, x2, y2) for tables: sheet frame minus title block."""
    _a, innen, _el = _rahmen(fmt)
    tb = vorlage.hoehe if vorlage is not None else 0.0
    return (innen[0] + 2.0, innen[1] + tb + 3.0, innen[2] - 2.0, innen[3] - 3.0)


def kurzes_datum(heute, sprache):
    """Short date for narrow title block fields (15 mm): 23.10.26 / 26-10-23."""
    return datum_text(heute, sprache, kurz=True)


def titel_werte(daten, titel1, projektname, heute, sprache):
    """Tag values for the title block from the project data
    (title: customer, project name, page title)."""
    return TB.daten_werte(daten, projektname, titel1, sprache, heute)


def _seite(typ, name, titel1, inhalt, ctx, nr, gesamt):
    """Frame + content + title block of a report page."""
    fmt = ctx.get("format", FORMAT)
    _a, _i, rahmen = _rahmen(fmt)
    el = list(rahmen) + list(inhalt)
    v = ctx["vorlage"]
    if v is not None:
        b, h = ZEICHNUNGSFORMATE[fmt]
        ref = TB.make_block(v.name, v.elemente, b, h, layer="0")
        ref.setze_attribute(titel_werte(ctx["daten"], titel1, ctx["projekt"],
                                        ctx["heute"], ctx["sprache"]))
        info = TB.info_values(nr, gesamt, name, ctx["projekt"], ctx["sprache"],
                              fmt, ctx["heute"], ctx["daten"], "")
        TB.refresh_fields([ref], info, "")
        el.append(ref)
    return BerichtSeite(typ, name, el, fmt)


# ------------------------------------------------------------------
# Cover sheet
# ------------------------------------------------------------------
def deckblatt_inhalt(daten, projektname, flaeche, heute, sprache, skala=1.0):
    f = skala
    x1, y1, x2, y2 = flaeche
    cx = (x1 + x2) / 2.0
    hoehe = y2 - y1
    el = []
    anlage = daten.get("anlage") or projektname
    el.append(Text(cx, y2 - 0.26 * hoehe, anlage, 10.0 * f, 0.0, TAB.SCHRIFT[0],
                   einfuegepunkt="mitte_zentriert", **TEXT))
    el.append(Text(cx, y2 - 0.38 * hoehe, tr("rep.deck.untertitel"), 5.0 * f, 0.0,
                   TAB.SCHRIFT[0], einfuegepunkt="mitte_zentriert", **TEXT))
    ly = y2 - 0.45 * hoehe
    el.append(Linie(cx - 70 * f, ly, cx + 70 * f, ly, staerke=0.5, **LINIE))
    datum = daten.get("datum") or datum_text(heute, sprache)
    zeilen = [(tr("rep.deck.kunde"), daten.get("kunde", "")),
              (tr("rep.deck.auftrag"), daten.get("auftrag", "")),
              (tr("rep.deck.zeichnungsnummer"), daten.get("zeichnungsnummer", "")),
              (tr("rep.deck.firma"), daten.get("firma", "")),
              (tr("rep.deck.gezeichnet"), daten.get("gezeichnet", "")),
              (tr("rep.deck.geprueft"), daten.get("geprueft", "")),
              (tr("rep.deck.revision"), daten.get("revision", "")),
              (tr("rep.deck.datum"), datum)]
    zeilen = [(k, v) for k, v in zeilen if v]
    start = ly - 10.0 * f
    schritt = min(8.0 * f, max(4.5 * f, (start - y1 - 2.0) / max(1, len(zeilen))))
    for i, (k, v) in enumerate(zeilen):
        y = start - i * schritt
        el.append(Text(cx - 4.0 * f, y, k, 3.5 * f, 0.0, TAB.SCHRIFT[0],
                       einfuegepunkt="mitte_rechts", **TEXT))
        el.append(Text(cx + 4.0 * f, y, v, 3.5 * f, 0.0, TAB.SCHRIFT[0],
                       einfuegepunkt="mitte_links", **TEXT))
    return el


# ------------------------------------------------------------------
# Rows per report type (also for the CSV export)
# ------------------------------------------------------------------
def listen_zeilen(typ, blaetter, nummer, netz=None, klemmen_in_geraeteliste=True,
                  einbauorte=None, katalog=None, projektdaten=None, klemmen_seiten="auto",
                  kanal_katalog=None):
    """Rows of a list report. blaetter: [(idx, elements)];
    einbauorte: {idx: installation location of the sheet};
    klemmen_seiten: side mode of the terminal diagram (SEITEN_MODI)."""
    if typ == "geraete":
        return D.geraeteliste(blaetter, nummer, netz, klemmen_in_geraeteliste,
                              einbauorte)
    if typ in ("klemmen", "leistenbild"):
        return D.klemmenplan(netz, blaetter, nummer, einbauorte, klemmen_seiten)
    if typ == "kabel":
        return D.kabelplan(netz, blaetter, nummer, einbauorte)
    if typ == "verbindungen":
        return DL.verbindungsliste(netz, blaetter, nummer, einbauorte)
    if typ == "stueckliste":
        return DL.stueckliste(blaetter, nummer, netz, katalog, einbauorte)
    if typ == "querverweise":
        return DL.querverweisliste(netz, blaetter, nummer)
    if typ == "potenziale":
        return DL.potenzialuebersicht(netz, blaetter, nummer)
    if typ == "stecker":
        return DL.steckeruebersicht(netz, blaetter, nummer, einbauorte)
    if typ == "etiketten":
        return DL.etikettenliste(blaetter, nummer, netz, einbauorte,
                                 {"geraet": tr("rep.art.geraet"),
                                  "klemme": tr("rep.art.klemme"),
                                  "kabel": tr("rep.art.kabel")})
    if typ == "revisionen":
        return DL.revisionsuebersicht(projektdaten)
    if typ == "sps":
        return DS.sps_liste(netz, blaetter, nummer, einbauorte)
    if typ == "mechanik":
        return MECH.mechanikliste(blaetter, {s: tr("mech.seite." + s) for s in
                                             ("vorne", "hinten", "links", "rechts", "oben", "unten")})
    if typ == "kanaele":
        return [dict(z, art=tr("kanal.bez." + z["art"]))
                for z in KK.kanalliste(blaetter, kanal_katalog)]
    raise ValueError(typ)


def netz_aufbauen(blaetter):
    return Netz.aufbauen(blaetter)


_OPTIONAL = {"einbauort", "funktion", "draht"} | {
    p + "_" + k for p in D.SEITEN for k in ("draht", "kabel", "farbe", "querschnitt",
                                             "leiter")}


def _ohne_leere_einbauorte(spalten, zeilen):
    """Columns without content disappear: 'einbauort' without any location,
    'bruecke' without any bridge, wire / cable / conductor columns of the
    terminal diagram without any value."""
    return [sp for sp in spalten
            if not (sp.key in _OPTIONAL and not any(z.get(sp.key) for z in zeilen))
            and not (sp.key == "bruecke" and not any(z.get("_bruecke") for z in zeilen))]


def tabellen_fuer_export(blaetter, nummer, ordner=(), klemmen_in_geraeteliste=True,
                         einbauorte=None, katalog=None, projektdaten=None,
                         klemmen_seiten="auto"):
    """{type: (columns, rows)} for all lists (device list, terminal diagram,
    cable plan, connection list, parts list ...)."""
    netz = netz_aufbauen(blaetter)
    out = {}
    for typ in LISTEN:
        spalten, _opt = lade_spalten(typ, ordner, klemmen_seiten)
        zeilen = listen_zeilen(typ, blaetter, nummer, netz,
                               klemmen_in_geraeteliste, einbauorte,
                               katalog, projektdaten, klemmen_seiten,
                               KK.katalog_laden(ordner))
        out[typ] = (_ohne_leere_einbauorte(spalten, zeilen), zeilen)
    return out


_GRUPPE = {"klemmen": ("_gk", ("leiste", "einbauort")),
           "kabel": ("_gk", ("cab", "einbauort", "hersteller", "typ")),
           "stecker": ("_gk", ("stecker", "einbauort")),
           "sps": ("_gk", ("station", "baugruppe", "einbauort"))}


def _liste_tabelle(typ, zeilen, ordner, flaeche, titel, skala=1.0, seiten="auto"):
    if typ in GRAFIKEN:
        return LB.leistenbild_seiten(zeilen, flaeche, titel, skala,
                                     tr("rep.lb.leiste"))
    spalten, opt = lade_spalten(typ, ordner, seiten)
    spalten = _ohne_leere_einbauorte(spalten, zeilen)
    gruppe, leer = _GRUPPE.get(typ, (None, ()))
    if gruppe:
        zeilen = zeilen_vorbereiten(zeilen, gruppe, leer)
    return tabellen_seiten(spalten, zeilen, flaeche, titel,
                           opt["textgroesse"] * skala, opt["zeilenhoehe"] * skala,
                           tr("rep.leer"),
                           seite_pro_gruppe=(typ == "klemmen"), skala=skala)


def seitennamen(typ, basis, seiten):
    """Sheet names of the pages of a list. Terminal diagram: 'Klemmenplan X1'
    (location first: 'Klemmenplan +1 -X1'; '... -X1 2/3' if the strip needs several sheets);
    otherwise 'Name 1/3'."""
    n = len(seiten)
    if typ not in ("klemmen", "leistenbild"):
        return [_name(basis, k + 1, n) for k in range(n)]
    labels = []
    for sp in seiten:
        kopf = getattr(sp, "kopf", None)
        eo, leiste = kopf if isinstance(kopf, tuple) and len(kopf) == 2 else ("", "")
        t = leiste or "-"
        labels.append((eo + " " if eo else "") + t)
    zaehler, out = {}, []
    for lab in labels:
        zaehler[lab] = zaehler.get(lab, 0) + 1
    lauf = {}
    for lab in labels:
        lauf[lab] = lauf.get(lab, 0) + 1
        out.append(f"{basis} {_name(lab, lauf[lab], zaehler[lab])}")
    return out


def _name(basis, k, n):
    return basis if n == 1 else f"{basis} {k}/{n}"


# ------------------------------------------------------------------
# Main function
# ------------------------------------------------------------------
def _berichte_erzeugen(blaetter, projektname, daten, aktiv, vorlage, sprache,
                      ordner=(), heute=None, klemmen_in_geraeteliste=True,
                      format=FORMAT, katalog=None, klemmen_seiten="auto"):
    """Creates the requested report sheets (format: drawing format name, A4 or A3;
    texts and row heights are scaled with the sheet).

    blaetter: [BlattInfo] of the drawing sheets in project order
    aktiv:    set of requested types from TYPEN
    vorlage:  template or None (without title block)
    -> (vorne, hinten): lists of BerichtSeite"""
    heute = heute or datetime.date.today()
    aktiv = set(aktiv)
    ctx = {"vorlage": vorlage, "daten": dict(daten), "projekt": projektname,
           "heute": heute, "sprache": sprache, "format": format}
    flaeche = inhaltsflaeche(vorlage, format)
    skala = skala_fuer(format)
    basis = [(i, b.elemente) for i, b in enumerate(blaetter)]
    einbauorte = {i: getattr(b, "einbauort", "") for i, b in enumerate(blaetter)}
    brauchen_netz = bool(aktiv & NETZ_LISTEN) or (
        "geraete" in aktiv and klemmen_in_geraeteliste)
    netz = netz_aufbauen(basis) if brauchen_netz else None
    namen = {t: tr("rep." + t) for t in TYPEN}

    n_deck = 1 if "deckblatt" in aktiv else 0
    n_inh = 1 if "inhalt" in aktiv else 0
    for _ in range(8):
        vorn = n_deck + n_inh

        def nummer(idx, v=vorn):
            return v + idx + 1

        listen = {}
        for typ in LISTEN + GRAFIKEN:
            if typ in aktiv:
                zeilen = listen_zeilen(typ, basis, nummer, netz,
                                       klemmen_in_geraeteliste, einbauorte,
                                       katalog, ctx["daten"], klemmen_seiten,
                                       KK.katalog_laden(ordner))
                listen[typ] = _liste_tabelle(typ, zeilen, ordner, flaeche,
                                             namen[typ], skala, klemmen_seiten)
        hinten_n = sum(len(p) for p in listen.values())
        gesamt = vorn + len(blaetter) + hinten_n
        if "inhalt" not in aktiv:
            break
        # Table-of-contents entries in sheet order
        eintraege = []
        if n_deck:
            eintraege.append((namen["deckblatt"], "", namen["deckblatt"]))
        for k in range(n_inh):
            eintraege.append((_name(namen["inhalt"], k + 1, n_inh), "",
                              namen["inhalt"]))
        for b in blaetter:
            eintraege.append((b.name, b.beschreibung,
                              getattr(b, "art", "") or tr("rep.art.zeichnung")))
        for typ in LISTEN + GRAFIKEN:
            seiten = listen.get(typ, [])
            for nm in seitennamen(typ, namen[typ], seiten):
                eintraege.append((nm, "", namen[typ]))
        zeilen = D.inhaltsverzeichnis(
            [{"nr": i + 1, "name": n, "beschreibung": b, "typ": t}
             for i, (n, b, t) in enumerate(eintraege)])
        spalten, opt = lade_spalten("inhalt", ordner)
        inh_seiten = tabellen_seiten(spalten, zeilen, flaeche, namen["inhalt"],
                                     opt["textgroesse"] * skala,
                                     opt["zeilenhoehe"] * skala,
                                     tr("rep.leer"), skala=skala)
        if len(inh_seiten) == n_inh:
            break
        n_inh = len(inh_seiten)

    vorne, nr = [], 0
    if n_deck:
        nr += 1
        vorne.append(_seite("deckblatt", namen["deckblatt"], namen["deckblatt"],
                            deckblatt_inhalt(ctx["daten"], projektname, flaeche,
                                             heute, sprache, skala), ctx, nr, gesamt))
    if "inhalt" in aktiv:
        n = len(inh_seiten)
        for k, el in enumerate(inh_seiten):
            nr += 1
            vorne.append(_seite("inhalt", _name(namen["inhalt"], k + 1, n),
                                namen["inhalt"], el, ctx, nr, gesamt))
    hinten = []
    nr = len(vorne) + len(blaetter)
    for typ in LISTEN + GRAFIKEN:
        seiten = listen.get(typ, [])
        for nm, el in zip(seitennamen(typ, namen[typ], seiten), seiten):
            nr += 1
            hinten.append(_seite(typ, nm, namen[typ], el, ctx, nr, gesamt))
    return vorne, hinten


def _first_tag(attribute, *namen):
    for n in namen:
        v = str(attribute.get(n, "")).strip()
        if v:
            return v
    return ""


def beschreibung_aus_layouts(layouts):
    """Title from the title block (TITLE1..3 / TITEL1..3 or TITLE) of the first layout with a
    title block, e.g. 'Main circuit - drive'."""
    for lay in layouts:
        for e in lay.elemente:
            if TB.is_title_block(e):
                teile = [_first_tag(e.attribute, *t) for t in
                         (("TITLE1", "TITEL1"), ("TITLE2", "TITEL2"),
                          ("TITLE3", "TITEL3"), ("TITLE", "TITEL"))]
                teile = [t for t in teile if t]
                if teile:
                    return " - ".join(teile[:2])
    return ""


def berichte_erzeugen(*args, schrift="Arial", **kw):
    """Creates the report sheets (see _berichte_erzeugen); `schrift` = font of all report texts."""
    TAB.SCHRIFT[0] = schrift or "Arial"
    try:
        return _berichte_erzeugen(*args, **kw)
    finally:
        TAB.SCHRIFT[0] = "Arial"
