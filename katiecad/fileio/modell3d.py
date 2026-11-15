# -*- coding: utf-8 -*-
"""
katiecad/fileio/modell3d.py - 3D models of devices from STEP / STL (NO Tkinter).

KatieCAD's 3D view is a wireframe, so a manufacturer's model is turned into a light
mesh (Koerper3D art "netz"):

  1. read:      STEP with OCP (pip install cadquery-ocp-novtk), STL without extra packages
  2. simplify:  weld vertices, cluster them when there are too many triangles, keep only
                outlines and sharp edges (angle between the faces > kantenwinkel) as lines
  3. align:     the front of the device looks to -Y (towards the cabinet door), up is +Z,
                the back lies in y = 0: x in [0, width], y in [-depth, 0], z in [0, height]
  4. snap points: corners of the box, centre of the back and the DIN rail point (middle
                of the back), used to move and place the device; the user may add the
                fixing holes and move the DIN rail point (`eigene_punkte_setzen`)
  5. cache:     a .katie3d file (JSON) so a STEP is converted only once

    {"format": "katiecad-3d", "version": 1, "quelle": "contactor.step", "front": "+Z",
     "netz": {"p": [...], "k": [...], "f": [...]}, "fang": [[x, y, z, "art"], ...],
     "masse": [width, depth, height]}
"""

import hashlib
import json
import math
import os
import struct

FORMAT = "katiecad-3d"
ENDUNGEN = (".step", ".stp", ".stl", ".katie3d")
FRONTEN = ("+Z", "-Z", "+Y", "-Y", "+X", "-X")
KANTENWINKEL = 25.0       # degrees: sharper edges are drawn
MAX_DREIECKE = 6000       # more triangles are clustered (wireframe + hidden lines stay fast)


class ModellFehler(Exception):
    pass


# ------------------------------------------------------------------
# Reading
# ------------------------------------------------------------------
def lese_stl(pfad):
    """-> (points [(x, y, z)], triangles [(i, j, k)]) of a binary or ASCII STL."""
    with open(pfad, "rb") as f:
        daten = f.read()
    if len(daten) >= 84:
        n = struct.unpack_from("<I", daten, 80)[0]
        if 84 + 50 * n == len(daten):                  # binary
            pts, tri = [], []
            for i in range(n):
                v = struct.unpack_from("<12f", daten, 84 + 50 * i)
                base = len(pts)
                pts += [v[3:6], v[6:9], v[9:12]]
                tri.append((base, base + 1, base + 2))
            return pts, tri
    text = daten.decode("latin-1", errors="replace")
    pts = []
    for zeile in text.splitlines():
        t = zeile.strip().split()
        if len(t) == 4 and t[0].lower() == "vertex":
            try:
                pts.append((float(t[1]), float(t[2]), float(t[3])))
            except ValueError:
                raise ModellFehler("STL: invalid vertex")
    if not pts or len(pts) % 3:
        raise ModellFehler("STL: no triangles")
    return pts, [(i, i + 1, i + 2) for i in range(0, len(pts), 3)]


def ocp_verfuegbar():
    try:
        import OCP.STEPControl  # noqa: F401
        return True
    except Exception:
        return False


def _statisch(klasse, name):
    """Static OCP method: older OCP versions use the suffix _s (Face_s), OCP 8 does not."""
    f = getattr(klasse, name + "_s", None)
    return f if f is not None else getattr(klasse, name)


def lese_step(pfad, toleranz=0.5, winkel=0.5):
    """-> (points, triangles) of a STEP file, meshed with OCP (linear deflection
    `toleranz` mm, angular deflection `winkel` rad)."""
    try:
        from OCP.STEPControl import STEPControl_Reader
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
        from OCP.BRep import BRep_Tool
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS
    except Exception as ex:
        raise ModellFehler("OCP fehlt / falta OCP: pip install cadquery-ocp-novtk (%s)" % ex)
    r = STEPControl_Reader()
    if r.ReadFile(str(pfad)) != IFSelect_RetDone:
        raise ModellFehler("STEP: file cannot be read")
    r.TransferRoots()
    form = r.OneShape()
    if form is None or form.IsNull():
        raise ModellFehler("STEP: no shape")
    BRepMesh_IncrementalMesh(form, float(toleranz), False, float(winkel), True)
    pts, tri = [], []
    als_flaeche = _statisch(TopoDS, "Face")
    triangulation = _statisch(BRep_Tool, "Triangulation")
    ex = TopExp_Explorer(form, TopAbs_FACE)
    while ex.More():
        flaeche = als_flaeche(ex.Current())
        loc = TopLoc_Location()
        t = triangulation(flaeche, loc)
        if t is not None:
            trsf = loc.Transformation()
            base = len(pts)
            for i in range(1, t.NbNodes() + 1):
                p = t.Node(i).Transformed(trsf)
                pts.append((p.X(), p.Y(), p.Z()))
            umgedreht = flaeche.Orientation() == TopAbs_REVERSED
            for i in range(1, t.NbTriangles() + 1):
                a, b, c = t.Triangle(i).Get()
                if umgedreht:
                    b, c = c, b
                tri.append((base + a - 1, base + b - 1, base + c - 1))
        ex.Next()
    if not tri:
        raise ModellFehler("STEP: no faces")
    return pts, tri


# ------------------------------------------------------------------
# Simplifying
# ------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _kreuz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    l = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-15 else None


def _schweissen(pts, tri, zelle):
    """Merges points closer than `zelle` (grid); drops degenerate triangles."""
    idx, neu, abb = {}, [], []
    for p in pts:
        k = (round(p[0] / zelle), round(p[1] / zelle), round(p[2] / zelle))
        if k not in idx:
            idx[k] = len(neu)
            neu.append(p)
        abb.append(idx[k])
    out, gesehen = [], set()
    for a, b, c in tri:
        a, b, c = abb[a], abb[b], abb[c]
        if a == b or b == c or a == c:
            continue
        schl = tuple(sorted((a, b, c)))
        if schl in gesehen:
            continue
        gesehen.add(schl)
        out.append((a, b, c))
    return neu, out


def vereinfachen(pts, tri, kantenwinkel=KANTENWINKEL, max_dreiecke=MAX_DREIECKE):
    """-> netzdaten {"p", "k", "f"}: welded / clustered mesh, triangles as faces and only
    outline + sharp edges as lines."""
    if not pts or not tri:
        raise ModellFehler("empty model")
    xs, ys, zs = zip(*pts)
    diag = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
    zelle = max(diag * 1e-5, 1e-4)
    p, t = _schweissen(pts, tri, zelle)
    while len(t) > max_dreiecke and zelle < diag / 4.0:
        zelle *= 1.6                                   # vertex clustering
        p, t = _schweissen(pts, tri, zelle)
    # used points only
    benutzt = sorted({i for d in t for i in d})
    neu = {alt: i for i, alt in enumerate(benutzt)}
    p = [p[i] for i in benutzt]
    t = [(neu[a], neu[b], neu[c]) for a, b, c in t]
    normalen = [_norm(_kreuz(_sub(p[b], p[a]), _sub(p[c], p[a]))) for a, b, c in t]
    kanten = {}
    for fi, (a, b, c) in enumerate(t):
        for i, j in ((a, b), (b, c), (c, a)):
            kanten.setdefault((min(i, j), max(i, j)), []).append(fi)
    grenze = math.cos(math.radians(kantenwinkel))
    k = []
    for (i, j), fl in kanten.items():
        if len(fl) != 2:
            k.append([i, j])                           # outline / non-manifold
            continue
        n1, n2 = normalen[fl[0]], normalen[fl[1]]
        if n1 is None or n2 is None or n1[0] * n2[0] + n1[1] * n2[1] + n1[2] * n2[2] < grenze:
            k.append([i, j])
    return {"p": [[round(c, 4) for c in q] for q in p], "k": k, "f": [list(d) for d in t]}


# ------------------------------------------------------------------
# Orientation, snap points
# ------------------------------------------------------------------
_DREHUNG = {   # model axis of the front -> mapping (x, y, z) to KatieCAD (front -Y, up +Z)
    "+Z": lambda x, y, z: (x, -z, y),
    "-Z": lambda x, y, z: (-x, z, y),
    "+Y": lambda x, y, z: (x, -y, z),
    "-Y": lambda x, y, z: (-x, y, z),
    "+X": lambda x, y, z: (y, -x, z),
    "-X": lambda x, y, z: (-y, x, z),
}


def ausrichten(netz, front="+Z"):
    """Turns the model so its front (the axis `front` of the model) looks to -Y and moves
    it to x in [0, w], y in [-d, 0] (back at y = 0), z in [0, h]. -> (netz, (w, d, h))."""
    f = _DREHUNG.get(front, _DREHUNG["+Z"])
    pts = [f(*q) for q in netz["p"]]
    xs, ys, zs = zip(*pts)
    x0, y1, z0 = min(xs), max(ys), min(zs)
    pts = [[round(x - x0, 4), round(y - y1, 4), round(z - z0, 4)] for x, y, z in pts]
    masse = (max(xs) - x0, y1 - min(ys), max(zs) - z0)
    return dict(netz, p=pts), tuple(round(m, 3) for m in masse)


def fangpunkte(masse):
    """Snap points of an aligned model: the 8 corners, the centre of the back and the DIN
    rail point (middle of the back) -> [[x, y, z, kind]]."""
    w, d, h = masse
    out = [[x, y, z, "ecke"] for x in (0.0, w) for y in (-d, 0.0) for z in (0.0, h)]
    out.append([w / 2.0, 0.0, h / 2.0, "hutschiene"])
    out.append([w / 2.0, -d, h / 2.0, "front"])
    return out


# Own snap points typed by the user: on the back of the device (y = 0), X from the left and
# Z from the bottom as seen from the front, e.g. "10 5; 35 5; 10 75; 35 75; DIN 40"
# (fixing holes + height of the DIN rail clip). Points: [[x, z]] fixing holes, din: z or None.
EIGENE_ART = "befestigung"


class PunkteFehler(ValueError):
    pass


def _zahl(t):
    try:
        return float(str(t).strip().replace(",", "."))
    except ValueError:
        raise PunkteFehler(str(t)) from None


def punkte_lesen(text):
    """'x z; x z; DIN z' -> ([[x, z], ...], din_z or None). Entries are separated by ';'
    or new lines, the numbers of an entry by spaces (or ',' without spaces, then the
    decimal mark is the point)."""
    punkte, din = [], None
    for teil in str(text or "").replace("\n", ";").split(";"):
        teil = teil.strip()
        if not teil:
            continue
        woerter = teil.split()
        if woerter[0].upper() in ("DIN", "H", "TS"):
            if len(woerter) != 2:
                raise PunkteFehler(teil)
            din = _zahl(woerter[1])
            continue
        if len(woerter) == 1:
            woerter = woerter[0].split(",")
        if len(woerter) != 2:
            raise PunkteFehler(teil)
        punkte.append([_zahl(woerter[0]), _zahl(woerter[1])])
    return punkte, din


def punkte_text(modell):
    """Own snap points of a model as text for punkte_lesen (fixing holes, DIN height when it
    is not the default middle of the back)."""
    teile = ["%g %g" % (round(q[0], 3), round(q[2], 3))
             for q in modell.get("fang", ()) if q[3] == EIGENE_ART]
    h = (modell.get("masse") or (0, 0, 0))[2]
    for q in modell.get("fang", ()):
        if q[3] == "hutschiene" and abs(q[2] - h / 2.0) > 1e-6:
            teile.append("DIN %g" % round(q[2], 3))
    return "; ".join(teile)


def eigene_punkte_setzen(modell, punkte, din=None):
    """Replaces the fixing hole points of the model (changed in place) and sets the height
    of the DIN rail point (None = middle of the back). Points outside the back of the
    device raise PunkteFehler. -> True when something changed."""
    w, d, h = modell.get("masse") or (0.0, 0.0, 0.0)
    eps = 1e-6
    for x, z in punkte:
        if not (-eps <= x <= w + eps and -eps <= z <= h + eps):
            raise PunkteFehler("%g %g" % (x, z))
    if din is not None and not (-eps <= din <= h + eps):
        raise PunkteFehler("DIN %g" % din)
    alt = [list(q) for q in modell.get("fang", ())]
    neu = []
    for q in alt:
        if q[3] == EIGENE_ART:
            continue
        if q[3] == "hutschiene":
            q = [w / 2.0, 0.0, h / 2.0 if din is None else float(din), "hutschiene"]
        neu.append(q)
    neu += [[float(x), 0.0, float(z), EIGENE_ART] for x, z in punkte]
    modell["fang"] = neu
    return neu != alt


# ------------------------------------------------------------------
# Whole import and the .katie3d cache
# ------------------------------------------------------------------
def importieren(pfad, front="+Z", toleranz=0.5, max_dreiecke=MAX_DREIECKE):
    """STEP / STL / .katie3d -> model dict (see module doc)."""
    ext = os.path.splitext(str(pfad))[1].lower()
    if ext == ".katie3d":
        return laden(pfad)
    if ext in (".step", ".stp"):
        pts, tri = lese_step(pfad, toleranz)
    elif ext == ".stl":
        pts, tri = lese_stl(pfad)
    else:
        raise ModellFehler("format not supported: " + ext)
    netz, masse = ausrichten(vereinfachen(pts, tri, max_dreiecke=max_dreiecke), front)
    return {"format": FORMAT, "version": 1, "quelle": os.path.basename(str(pfad)),
            "front": front, "netz": netz, "fang": fangpunkte(masse), "masse": list(masse)}


def speichern(pfad, modell):
    tmp = str(pfad) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(modell, f, separators=(",", ":"))
    os.replace(tmp, pfad)


def laden(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or d.get("format") != FORMAT or "netz" not in d:
        raise ModellFehler("not a KatieCAD 3D model")
    return d


def cache_aktuell(cache, quelle):
    """True when the cache file exists and is not older than the source model."""
    try:
        return os.path.getmtime(cache) >= os.path.getmtime(quelle)
    except OSError:
        return False


def laden_oder_importieren(pfad, cache=None, front="+Z", toleranz=0.5, punkte=None):
    """Model of `pfad` through the cache file `cache` (None = no cache): converts only when
    the cache is missing or older, then applies the own snap points `punkte` = (points,
    din) when given and writes the cache when something is new. -> model dict."""
    neu = False
    if cache and cache_aktuell(cache, pfad):
        modell = laden(cache)
    else:
        modell = importieren(pfad, front, toleranz)
        neu = True
    if punkte is not None and eigene_punkte_setzen(modell, *punkte):
        neu = True
    if cache and neu:
        os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
        speichern(cache, modell)
    return modell


def vorgabe_punkte(ordner, quelle, front):
    """Own snap points (text) of an existing, current cache of `quelle`, or ''."""
    cache = cache_pfad(ordner, quelle, front)
    if not cache_aktuell(cache, quelle):
        return ""
    try:
        return punkte_text(laden(cache))
    except (ModellFehler, OSError, ValueError):
        return ""


def cache_pfad(ordner, quelle, front):
    """Cache file keyed by the source path (including suffix) and front axis."""
    quelle = os.path.normcase(os.path.realpath(quelle))
    kennung = hashlib.sha256(os.fsencode(quelle)).hexdigest()[:24]
    name = os.path.splitext(os.path.basename(quelle))[0][:40]
    achse = front.replace("+", "p").replace("-", "m")
    return os.path.join(ordner, f"{name}_{achse}_{kennung}.katie3d")
