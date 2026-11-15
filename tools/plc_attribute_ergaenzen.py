# -*- coding: utf-8 -*-
"""
tools/plc_attribute_ergaenzen.py - gives the PLC symbols back their invisible attributes.

The PLC symbols (symbols/10 PLC) were redrawn on 30-10-2026 and lost the invisible
attribute definitions that the PLC list (reports/daten_sps.py) needs:

  SPS              module kind CPU / DI / DO / AI / AO (from the file name)
  STATION, PLATZ   controller and slot (PLATZ not on the CPU)
  VPn_SYM, VPn_KOM symbol and comment of each CHANNEL pin (not of the supply pins
                   M, L+, L1 ...); the redrawn symbols put the supply on VP1, so the
                   channel tags are taken from the pins, not counted from 1

What it does (and ONLY this): attribute definitions that are missing are appended to the
block; nothing else is touched, files without a change are not rewritten, line endings
and the final newline stay as they are. Running it twice changes nothing.

Usage (from the project folder):
    python tools/plc_attribute_ergaenzen.py --pruefen     # only show what would change
    python tools/plc_attribute_ergaenzen.py               # change ./symbols/10 PLC
    python tools/plc_attribute_ergaenzen.py "C:\\path\\to\\symbols\\10 PLC"
"""
import json
import os
import re
import sys

ARTEN = ("CPU", "DI", "DO", "AI", "AO")
VERSORGUNG = {"M", "1M", "2M", "3M", "L+", "1L+", "2L+", "L1", "L2", "L3", "N", "PE",
              "0V", "24V", "+24V", "+24VDC", "0VDC"}


def art_aus_name(name):
    """'PLC DI 8' -> 'DI', 'PLC AI4' -> 'AI', 'PLC channel DO' -> 'DO', else ''."""
    for wort in re.split(r"[\s_\-]+", str(name).upper()):
        for a in ARTEN:
            if wort == a or (wort.startswith(a) and wort[len(a):].isdigit()):
                return a
    return ""


def _attdef(muster, x, y, tag, wert, prompt):
    d = {"typ": "attdef", "layer": muster.get("layer", "0"),
         "farbe": muster.get("farbe", "#c29bff"),
         "linientyp": muster.get("linientyp", "Volllinie (schmal)"), "eig_farbe": True,
         "staerke": None, "x": x, "y": y, "inhalt": "<%s>" % tag, "hoehe": 2.0,
         "winkel": 0.0, "schriftart": "Arial", "einfuegepunkt": "unten_links",
         "tag": tag, "prompt": prompt, "wert": wert, "sichtbar": False}
    return d


def fehlende(block, dateiname):
    """Attribute definitions missing in the block -> [(tag, value, prompt)]."""
    art = art_aus_name(block.get("name") or dateiname)
    if not art:
        return []
    el = [e for e in block.get("elemente", []) if isinstance(e, dict)]
    vorhanden = {e.get("tag") for e in el if e.get("typ") == "attdef"}
    soll = [("SPS", art, "SPS"), ("STATION", "", "Steuerung / Station")]
    if art != "CPU":
        soll.append(("PLATZ", "", "Steckplatz"))
        kanaele = [e for e in el if e.get("typ") == "vpunkt"
                   and str(e.get("wert", "")).strip().upper() not in VERSORGUNG]
        for i, p in enumerate(kanaele, 1):
            t = p.get("tag") or "VP%d" % i
            soll.append((t + "_SYM", "", "Symbol Kanal %d" % i))
            soll.append((t + "_KOM", "", "Kommentar Kanal %d" % i))
    return [s for s in soll if s[0] not in vorhanden]


def datei_bearbeiten(pfad, schreiben=True):
    """-> number of attribute definitions added (0 = file unchanged)."""
    with open(pfad, "r", encoding="utf-8", newline="") as f:
        roh = f.read()
    daten = json.loads(roh)
    block = daten.get("block") if isinstance(daten, dict) else None
    if not isinstance(block, dict):
        return 0
    neu = fehlende(block, os.path.splitext(os.path.basename(pfad))[0])
    if not neu:
        return 0
    el = block.setdefault("elemente", [])
    maske = next((e for e in el if isinstance(e, dict) and e.get("typ") == "maske"), {})
    x, y = float(maske.get("x", 0.0)), float(maske.get("y", 0.0))
    for tag, wert, prompt in neu:
        el.append(_attdef(maske, x, y, tag, wert, prompt))
    if schreiben:
        text = json.dumps(daten, indent=2, ensure_ascii=False)
        if "\r\n" in roh:
            text = text.replace("\n", "\r\n")
        if roh.endswith("\n"):
            text += "\r\n" if "\r\n" in roh else "\n"
        tmp = pfad + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, pfad)
    return len(neu)


def main(argv):
    pruefen = "--pruefen" in argv
    args = [a for a in argv if not a.startswith("--")]
    ordner = args[0] if args else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols", "10 PLC")
    if not os.path.isdir(ordner):
        print("Ordner nicht gefunden:", ordner)
        return 1
    dateien = geaendert = fehler = 0
    for fn in sorted(os.listdir(ordner)):
        if not fn.lower().endswith(".katieblock"):
            continue
        dateien += 1
        voll = os.path.join(ordner, fn)
        try:
            n = datei_bearbeiten(voll, schreiben=not pruefen)
        except (OSError, ValueError) as e:
            fehler += 1
            print("FEHLER", voll, e)
            continue
        if n:
            geaendert += 1
            print(("wuerde ergaenzen: " if pruefen else "ergaenzt: ") + fn, "(%d Attribute)" % n)
    print("%d Dateien geprueft, %d %s, %d Fehler"
          % (dateien, geaendert, "wuerden geaendert" if pruefen else "geaendert", fehler))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
