# -*- coding: utf-8 -*-
"""Additional single-pole symbols for the folder "12 Single-pole".

Writes only the symbols defined here into symbols/12 Single-pole and never
overwrites an existing file (use --force to replace them). The style follows
the symbols shipped in that folder:

  * origin = upper pin (0, 0), lower pin usually at (0, -15), 5 mm grid,
  * pins named like the poles they stand for ("1,3,5" / "2,4,6"),
  * the mask is marked as single-pole representation and carries the pole count
    (field POLE, shown beside the pole stroke on the upper connection line),
  * line weight 0.35 mm, text 2 mm.

    python tools/make_symbols_einpolig_extra.py [--force] [output folder]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import make_symbols as MS                                   # noqa: E402
from katiecad.model.core import ElektroMaske, Verbindungspunkt, Linie  # noqa: E402

KATEGORIE = "12 Single-pole"
SYMS = []


class S(MS.Sym):
    def __init__(self, name, de, ind, pole="3", rolle="haupt"):
        super().__init__(name, KATEGORIE, de)
        self.ind, self.pole, self.rolle = ind, pole, rolle
        SYMS.append(self)

    def pol(self, y=-2.5):
        """Pole stroke on the upper connection line; the mask shows POLE beside it."""
        self.line(-1.0, y - 1.0, 1.0, y + 1.0)
        self.pol_y = y

    def anschluesse(self, oben="1,3,5", unten="2,4,6", y_unten=-15.0):
        if oben:
            self.pin(0.0, 0.0, oben)
            self._vp().richtungen = [90]
        if unten:
            self.pin(0.0, y_unten, unten)
            self._vp().richtungen = [270]

    def _vp(self):
        return [e for e in self.el if isinstance(e, Verbindungspunkt)][-1]

    def maske(self, x, y, pol_x=1.6):
        """Mask on the left; POLE is placed starting at x = pol_x beside the stroke
        (right-aligned field: its right edge depends on the text length)."""
        m = ElektroMaske(x, y, {"IND": self.ind, "MAN": "MAN", "TYP": "TYP", "PER": "PER"},
                         rolle=self.rolle, einpolig=True, pole=self.pole, staerke=None,
                         **MS.STYLE)
        m.aufgeloest(False)                          # automatic text positions
        ax, ay = m._anker["POLE"]
        rechts = pol_x + 1.15 * len(self.pole)       # ~1.15 mm per character at 2 mm
        m.versatz["POLE"] = [rechts - ax, getattr(self, "pol_y", -2.5) - ay]
        self.el.append(m)


def offen(s, y1=-5.0, y2=-10.0):
    """Connection lines and an open switch blade between y1 and y2."""
    s.line(0, 0, 0, y1)
    s.line(0, y2, 0, -15)
    s.line(0, y2, -2.5, y1)


# ---- Seccionador / disconnector: bar across the fixed contact
s = S("Disconnector 1p", "Trennschalter einpolig", "-Q")
offen(s)
s.line(-1.0, -5.0, 1.0, -5.0)
s.pol(); s.anschluesse(); s.maske(-5.0, -13.0)

# ---- Interruptor-seccionador / switch disconnector: bar + circle (load switch)
s = S("Switch disconnector 1p", "Lasttrennschalter einpolig", "-Q")
offen(s)
s.line(-1.0, -5.0, 1.0, -5.0)
s.circle(0.0, -4.2, 0.7)
s.line(-1.25, -7.5, -4.0, -7.5, dash=True)          # manual operation
s.line(-4.0, -6.5, -4.0, -8.5)
s.pol(y=-1.75); s.anschluesse(); s.maske(-6.0, -13.0)

# ---- Contactor main contact: half circle at the fixed contact
s = S("Contactor 1p", "Schütz-Hauptkontakt einpolig", "-K", rolle="hilfs")
offen(s)
s.arc(0.0, -5.0, 0.9, 0.0, 180.0)
s.pol(y=-2.0); s.anschluesse(); s.maske(-5.0, -13.0)

# ---- Energy meter (kWh)
s = S("Energy meter 1p", "Energiezähler einpolig", "-P")
s.line(0, 0, 0, -4.0)
s.rect(-3.5, -4.0, 3.5, -11.0)
s.text(0.0, -7.5, "kWh", 2.0)
s.line(0, -11.0, 0, -15.0)
s.pol(y=-2.0); s.anschluesse(); s.maske(-5.0, -13.0)

# ---- Frequency converter (VFD): box, diagonal, ~ / f~
s = S("Frequency converter 1p", "Frequenzumrichter einpolig", "-U")
s.line(0, 0, 0, -3.5)
s.rect(-4.0, -3.5, 4.0, -11.5)
s.line(-4.0, -11.5, 4.0, -3.5)
s.text(-2.0, -5.5, "~", 2.5)
s.text(2.0, -9.5, "f~", 2.0)
s.line(0, -11.5, 0, -15.0)
s.pol(y=-1.75); s.anschluesse("L1,L2,L3", "U,V,W"); s.maske(-5.5, -13.0)

# ---- UPS (SAI): AC/AC converter with battery
s = S("UPS 1p", "USV einpolig", "-G", pole="2")
s.line(0, 0, 0, -3.5)
s.rect(-4.0, -3.5, 4.0, -11.5)
s.line(-4.0, -11.5, 4.0, -3.5)
s.text(-2.0, -5.5, "~", 2.5)
s.text(2.0, -9.5, "~", 2.5)
s.line(4.0, -7.5, 5.2, -7.5)                        # battery on the right
s.line(5.2, -6.0, 5.2, -9.0)
s.line(6.0, -6.8, 6.0, -8.2)
s.line(0, -11.5, 0, -15.0)
s.pol(y=-1.75); s.anschluesse("L,N IN", "L,N OUT"); s.maske(-5.5, -13.0)

# ---- Busbar: thick bar with 7 taps (feeders from above or below)
s = S("Busbar 1p", "Sammelschiene einpolig", "-W", pole="3+N")
s.el.append(Linie(0.0, 0.0, 60.0, 0.0, staerke=1.0, **MS.STYLE))
for i in range(7):
    s.pin(10.0 * i, 0.0, "L1,L2,L3,N")
    vp = s._vp()
    vp.richtungen = [90, 270]
    vp.sichtbar = False                              # the pole count names the bar
s.line(4.0, -1.0, 6.0, 1.0)                         # pole stroke across the bar
s.pol_y = 2.5
s.maske(-2.0, -1.0, pol_x=5.0)

# ---- PV generator: module with light arrows, output at the bottom
s = S("PV generator 1p", "Photovoltaik-Generator einpolig", "-G", pole="2")
s.rect(-4.0, 0.0, 4.0, -8.0)
s.line(-4.0, -8.0, 4.0, 0.0)
s.text(-2.0, -2.5, "=", 2.5)
for dx in (0.0, 1.6):                               # sunlight
    s.line(3.0 + dx, 3.0, 1.8 + dx, 1.2)
    s.poly([(1.6 + dx, 2.0), (1.8 + dx, 1.2), (2.4 + dx, 1.7)])
s.line(0, -8.0, 0, -15.0)
s.pol(y=-11.0)
s.anschluesse(None, "+,-")
s.maske(-5.5, -13.0)

# ---- PV inverter: DC in on top, AC out at the bottom
s = S("PV inverter 1p", "Photovoltaik-Wechselrichter einpolig", "-U", pole="3+N")
s.line(0, 0, 0, -2.5)
s.rect(-4.0, -2.5, 4.0, -10.0)
s.line(-4.0, -10.0, 4.0, -2.5)
s.text(-2.0, -4.5, "=", 2.5)
s.text(2.0, -8.0, "~", 2.5)
s.line(0, -10.0, 0, -15.0)
s.pol(y=-12.0); s.anschluesse("+,-", "L1,L2,L3,N"); s.maske(-5.5, -13.0)


def main(args):
    force = "--force" in args
    rest = [a for a in args if a != "--force"]
    out = rest[0] if rest else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols")
    MS.OUT = out
    ordner = os.path.join(out, KATEGORIE)
    geschrieben, uebersprungen = [], []
    for s in SYMS:
        from katiecad.model.blocks import vorschlag_dateiname
        pfad = os.path.join(ordner, vorschlag_dateiname(s.name))
        if os.path.exists(pfad) and not force:
            uebersprungen.append(s.name)
            continue
        s.save()
        geschrieben.append(s.name)
    print(len(geschrieben), "geschrieben:", ", ".join(geschrieben))
    if uebersprungen:
        print(len(uebersprungen), "vorhanden (mit --force ersetzen):", ", ".join(uebersprungen))


if __name__ == "__main__":
    main(sys.argv[1:])
