# -*- coding: utf-8 -*-
"""Pin magnet (devices beside another pin snap onto its line, so the automatic
wire connects them) and the screen clean-up of template values."""
import sys, os, glob
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as katiecad_i18n; katiecad_i18n.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
import katiecad.electrical.logic as L
import katiecad.ui.app as A
from katiecad.model.blocks import block_laden
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


app = A.CadApp.__new__(A.CadApp)
wurzel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols")
LS = block_laden(glob.glob(os.path.join(wurzel, "03 Protection", "Circuit breaker 3-pole.katieblock"))[0],
                 app._dict_zu_element)


def ls(x, y):
    b = core.BlockReferenz(x, y, LS.name, LS.elemente)
    b.attribute.update({"IND": "-F", "MAN": "MAN", "TYP": "TYP", "PER": "PER"})
    return b


def verbunden(el, a, b):
    """Number of automatic wires between the pins of a and b."""
    pa = {(round(x, 3), round(y, 3)) for x, y in L.einrast_punkte(a)}
    pb = {(round(x, 3), round(y, 3)) for x, y in L.einrast_punkte(b)}
    n = 0
    for x1, y1, x2, y2, _b in L.gewuenschte_leitungen(el):
        e = {(round(x1, 3), round(y1, 3)), (round(x2, 3), round(y2, 3))}
        n += bool(e & pa) and bool(e & pb)
    return n


# ---- a device 0.7 mm beside the column of another one snaps onto it
f1, f2 = ls(0, 0), ls(0.7, -40)
el = [f1, f2]
check(verbunden(el, f1, f2) == 0, "versetzt: keine Leitung")
dx, dy = L.pins_ausrichten(el, [f2])
check(abs(dx + 0.7) < 1e-9 and dy == 0.0 and abs(f2.x) < 1e-9, f"Magnet zieht 0,7 mm: {dx} {dy} {f2.x}")
check(verbunden(el, f1, f2) == 3, f"drei Leitungen nach dem Ausrichten: {verbunden(el, f1, f2)}")

# ---- farther than the magnet: nothing happens
f3 = ls(3.0, -80)
check(L.pins_ausrichten(el + [f3], [f3]) == (0.0, 0.0) and f3.x == 3.0, "3 mm: kein Magnet")
# ---- already aligned: nothing to do
check(L.pins_ausrichten(el, [f2]) == (0.0, 0.0), "schon ausgerichtet")
# ---- a pin column 5 mm further also counts (shift picks most pins)
f4 = ls(5.4, -120)
check(L.pins_ausrichten([f1, f4], [f4]) == (-0.4, 0.0) and verbunden([f1, f4], f1, f4) == 2,
      "zwei von drei Polen getroffen")

# ---- objects moved together keep their positions to each other
g1, g2, w = ls(10.5, -40), ls(10.5, -80), core.Linie(10.5, -100, 20.5, -100)
fest = ls(10, 0)
d = L.pins_ausrichten([fest, g1, g2, w], [g1, g2, w])
check(d == (-0.5, 0.0) and g1.x == g2.x == 10.0 and w.x1 == 10.0, f"Gruppe gemeinsam verschoben: {d}")
check(L.pins_ausrichten([core.Linie(0, 0, 5, 0), f1], [f1]) == (0.0, 0.0), "ohne andere Anschlüsse nichts")

# ---- terminal under a device
kl = core.Klemme(0.6, -70, {"IND": "-X1", "NUM": "1"})
check(L.pins_ausrichten([f1, kl], [kl])[0] == -0.6 and kl.x == 0.0, "Klemme rastet unter dem Pin ein")

# ---- app: _einrasten uses the magnet only when switched on
class Var:
    def __init__(self, v): self.v = v
    def get(self): return self.v


meldungen = []
fake = SimpleNamespace(_ist_layout=lambda: False, view={"zoom": 3.0},
                       status=SimpleNamespace(set=meldungen.append),
                       pin_magnet_var=Var(False))
liste = [ls(0, 0), ls(0.8, -40)]
fake._ziel_liste = lambda: liste
A.CadApp._einrasten(fake, [liste[1]])
check(liste[1].x == 0.8, "Magnet aus: unverändert")
fake.pin_magnet_var = Var(True)
A.CadApp._einrasten(fake, [liste[1]])
check(abs(liste[1].x) < 1e-9 and any("Pin-Magnet" in m for m in meldungen), f"Magnet an: {meldungen}")

# ---- screen clean-up: template values (TYP in field TYP) are not drawn
maske = next(k for k in f1.aufgeloest() if isinstance(k, core.ElektroMaske))
texte = [t.inhalt for t in A.CadApp._ohne_vorlagewerte(maske) if isinstance(t, core.Text)]
check("-F" in texte and not {"MAN", "TYP", "PER"} & set(texte), f"Vorlagewerte ausgeblendet: {texte}")
check({"TYP", "PER"} <= {t.inhalt for t in maske.aufgeloest() if isinstance(t, core.Text)},
      "Modell unverändert (Druck/Listen)")
check(maske.werte.get("TYP") == "TYP", "Werte nach dem Zeichnen zurückgesetzt")

print(f"test_pin_magnet - OK ({ok} Pruefungen)")
