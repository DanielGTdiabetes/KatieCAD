# -*- coding: utf-8 -*-
"""
katiecad/reports/mprint.py - Marker lists for label printers such as Weidmüller
M-Print PRO (NO Tkinter).

M-Print PRO imports Excel or CSV files: one marker per row, the text in the first
column, no merged cells. Three lists:

  hilos   wire markers: one per END of every numbered wire (a wire with three
          ends - e.g. with a junction - gets three markers), sorted by number
  bornes  terminal markers: per terminal strip in mounting order (-X1:1, -X1:2 ...)
  equipos device markers: one per equipment identifier (-K1, -Q1 ...)

The text of each marker comes from a format with placeholders:
  hilos:   {nr} wire number, {hier} this end ('-K1:13'), {ziel} the other end(s)
  bornes:  {leiste} strip, {num} terminal number, {ort} installation location
  equipos: {ind} identifier, {ort} installation location
Texts longer than the marker allows (`max`, characters) are reported.
"""

from katiecad.electrical.drahtnummern import draehte
from katiecad.reports import daten as D
from katiecad.reports.netz import knoten_text, natuerlich

ARTEN = ("hilos", "bornes", "equipos")
STANDARD = {
    "hilos": {"aktiv": True, "format": "{nr}", "max": 10},
    "bornes": {"aktiv": True, "format": "{leiste}:{num}", "max": 8},
    "equipos": {"aktiv": True, "format": "{ind}", "max": 12},
    "csv": False,          # False = one Excel workbook, True = one CSV file per list
    "kopf": False,         # header row (M-Print: usually without)
}
PLATZHALTER = {"hilos": ("nr", "hier", "ziel"), "bornes": ("leiste", "num", "ort"),
               "equipos": ("ind", "ort")}


def einstellungen(doku):
    """Settings of the project (doku["mprint"]) merged over the defaults."""
    e = {k: (dict(v) if isinstance(v, dict) else v) for k, v in STANDARD.items()}
    gespeichert = doku.get("mprint") if isinstance(doku, dict) else None
    if isinstance(gespeichert, dict):
        for k, v in gespeichert.items():
            if k in ARTEN and isinstance(v, dict):
                e[k].update({kk: vv for kk, vv in v.items() if kk in STANDARD[k]})
            elif k in ("csv", "kopf"):
                e[k] = bool(v)
    return e


def text(fmt, werte, standard):
    """Fills the format; a broken format falls back to the default."""
    try:
        return str(fmt or standard).format(**werte).strip()
    except (KeyError, IndexError, ValueError):
        return str(standard).format(**werte).strip()


def _enden(d):
    """End points of a wire: device pins and terminal sides (sorted)."""
    return sorted((n for n in d.knoten if n.art in ("pin", "klemme")),
                  key=lambda n: natuerlich(knoten_text(n)))


def hilos(netz, fmt=None):
    """Wire markers: [{"text", "nr", "hier", "ziel"}], one per wire end.
    Only wires that carry a number (Drahtnummer) are listed."""
    zeilen = []
    for d in draehte(netz):
        nr = next((n.draht for n in d.knoten if n.draht), "")
        if not nr:
            continue
        enden = _enden(d)
        for n in enden:
            hier = knoten_text(n)
            ziel = ", ".join(knoten_text(m) for m in enden if m is not n)
            w = {"nr": nr, "hier": hier, "ziel": ziel}
            zeilen.append(dict(w, text=text(fmt, w, STANDARD["hilos"]["format"])))
    zeilen.sort(key=lambda z: (natuerlich(z["nr"]), natuerlich(z["hier"])))
    return zeilen


def bornes(netz, blaetter, nummer, einbauorte=None, fmt=None):
    """Terminal markers in mounting order (same order as the terminal diagram):
    [{"text", "leiste", "num", "ort"}]."""
    zeilen = []
    for z in D.klemmenplan(netz, blaetter, nummer, einbauorte):
        w = {"leiste": z["leiste"], "num": z["num"], "ort": z["einbauort"]}
        t = text(fmt, w, STANDARD["bornes"]["format"])
        if not z["leiste"]:                  # terminal without strip: number only
            t = text("{num}", w, "{num}")
        zeilen.append(dict(w, text=t))
    return zeilen


def equipos(blaetter, nummer, einbauorte=None, fmt=None):
    """Device markers: [{"text", "ind", "ort"}], one per equipment identifier."""
    zeilen = []
    for z in D.geraeteliste(blaetter, nummer, None, False, einbauorte):
        if not z["ind"]:
            continue
        w = {"ind": z["ind"], "ort": z["einbauort"]}
        zeilen.append(dict(w, text=text(fmt, w, STANDARD["equipos"]["format"])))
    return zeilen


def listen(netz, blaetter, nummer, einbauorte=None, einst=None):
    """{kind: rows} of the active lists (see einstellungen)."""
    e = einst or einstellungen({})
    out = {}
    if e["hilos"]["aktiv"]:
        out["hilos"] = hilos(netz, e["hilos"]["format"])
    if e["bornes"]["aktiv"]:
        out["bornes"] = bornes(netz, blaetter, nummer, einbauorte, e["bornes"]["format"])
    if e["equipos"]["aktiv"]:
        out["equipos"] = equipos(blaetter, nummer, einbauorte, e["equipos"]["format"])
    return out


def zu_lang(listen_, einst=None):
    """Texts longer than the marker allows: [(kind, text, length, max)]."""
    e = einst or einstellungen({})
    out = []
    for art, zeilen in listen_.items():
        try:
            m = int(e[art]["max"])
        except (KeyError, TypeError, ValueError):
            continue
        if m <= 0:
            continue
        for z in zeilen:
            if len(z["text"]) > m:
                out.append((art, z["text"], len(z["text"]), m))
    return out


# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------
def _steuer_frei(s):
    return "".join(ch for ch in str(s) if ch >= " " or ch == "\t").replace("\t", " ")


def csv_schreiben(pfad, zeilen, kopf=None):
    """One marker per row, text in the first column (UTF-8 with BOM, ';').
    The texts are written unchanged: designations such as '-X1:1' or '+UV1'
    must reach the label software as they are (this file is meant for M-Print,
    not for opening in Excel)."""
    import csv
    with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if kopf:
            w.writerow([kopf])
        for z in zeilen:
            w.writerow([_steuer_frei(z["text"])])


def exportieren(pfad, listen_, namen, csv=False, kopf=False):
    """Writes the marker lists. Excel: one workbook `pfad` with one sheet per
    list; CSV: `pfad` is a folder, one file per list (<name>.csv).
    namen: {kind: sheet / file name}. -> list of the sheets / files written."""
    import os
    if csv:
        os.makedirs(pfad, exist_ok=True)
        out = []
        for art, zeilen in listen_.items():
            datei = os.path.join(pfad, namen.get(art, art) + ".csv")
            csv_schreiben(datei, zeilen, namen.get(art, art) if kopf else None)
            out.append(datei)
        return out
    from katiecad.reports.xlsx import xlsx_schreiben
    blaetter = [(namen.get(art, art), [(namen.get(art, art), "text", False)], zeilen)
                for art, zeilen in listen_.items()]
    return xlsx_schreiben(pfad, blaetter, ohne_kopf=not kopf)
