# -*- coding: utf-8 -*-
"""Device models from STL / STEP: reading, simplifying to outline + sharp edges,
clustering big meshes, aligning (front -> -Y, back at y = 0), snap points, the
.katie3d cache and the mesh body with snap points (saved, moved, used for snapping).
The STEP part runs only when OCP (cadquery-ocp-novtk) is installed."""
import sys, os, json, math, struct, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stub  # noqa: F401
import katiecad.common.i18n as I; I.SPRACHE["aktuell"] = "de"
import katiecad.model.core as core
from katiecad.model import szene3d as S
from katiecad.fileio import modell3d as MD
ok = 0


def check(c, m):
    global ok
    assert c, "FEHLER: " + m
    ok += 1


def quader_dreiecke(w, h, d):
    """12 triangles of a box 0..w x 0..h x 0..d (outward)."""
    p = [(x, y, z) for x in (0, w) for y in (0, h) for z in (0, d)]
    i = {q: n for n, q in enumerate(p)}
    def P(x, y, z): return i[(x * w, y * h, z * d)]
    flaechen = [((0,0,0),(0,1,0),(0,1,1),(0,0,1)), ((1,0,0),(1,0,1),(1,1,1),(1,1,0)),
                ((0,0,0),(0,0,1),(1,0,1),(1,0,0)), ((0,1,0),(1,1,0),(1,1,1),(0,1,1)),
                ((0,0,0),(1,0,0),(1,1,0),(0,1,0)), ((0,0,1),(0,1,1),(1,1,1),(1,0,1))]
    tri = []
    for a, b, c, dd in flaechen:
        tri += [(P(*a), P(*b), P(*c)), (P(*a), P(*c), P(*dd))]
    return p, tri


def stl_binaer(pfad, pts, tri):
    with open(pfad, "wb") as f:
        f.write(b"\0" * 80 + struct.pack("<I", len(tri)))
        for a, b, c in tri:
            f.write(struct.pack("<12fH", 0, 0, 0, *pts[a], *pts[b], *pts[c], 0))


ordner = tempfile.mkdtemp()
try:
    pts, tri = quader_dreiecke(10, 20, 30)
    stl = os.path.join(ordner, "schuetz.stl")
    stl_binaer(stl, pts, tri)
    p2, t2 = MD.lese_stl(stl)
    check(len(t2) == 12 and len(p2) == 36, "binäre STL")
    asc = os.path.join(ordner, "a.stl")
    with open(asc, "w") as f:
        f.write("solid x\n")
        for a, b, c in tri:
            f.write("facet normal 0 0 0\nouter loop\n" + "".join(
                "vertex %g %g %g\n" % pts[k] for k in (a, b, c)) + "endloop\nendfacet\n")
        f.write("endsolid x\n")
    check(len(MD.lese_stl(asc)[1]) == 12, "ASCII-STL")

    # ---- simplify: a box keeps 8 points, 12 edges (no face diagonals), 12 triangles
    nz = MD.vereinfachen(p2, t2)
    check(len(nz["p"]) == 8 and len(nz["k"]) == 12 and len(nz["f"]) == 12,
          f"Quader: {len(nz['p'])} Punkte, {len(nz['k'])} Kanten")
    # fine sphere-like mesh is clustered below the limit, smooth faces give no lines
    kp, kt = [], []
    n = 60
    for i in range(n + 1):
        for j in range(n):
            th, ph = math.pi * i / n, 2 * math.pi * j / n
            kp.append((10 * math.sin(th) * math.cos(ph), 10 * math.sin(th) * math.sin(ph), 10 * math.cos(th)))
    for i in range(n):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = (i + 1) * n + j, (i + 1) * n + (j + 1) % n
            kt += [(a, c, b), (b, c, d)]
    kn = MD.vereinfachen(kp, kt, max_dreiecke=2000)
    check(len(kn["f"]) <= 2000, f"Kugel geclustert: {len(kn['f'])} Dreiecke")
    check(len(kn["k"]) < len(kn["f"]), "glatte Flächen: wenige Linien")

    # ---- align: front +Z of the model looks to -Y, back at y = 0
    al, masse = MD.ausrichten(nz, "+Z")
    xs, ys, zs = zip(*al["p"])
    check(masse == (10, 30, 20) and min(xs) == 0 and max(ys) == 0 and min(ys) == -30 and min(zs) == 0,
          f"ausgerichtet: {masse}")
    check(MD.ausrichten(nz, "+Y")[1] == (10, 20, 30), "Vorderseite +Y")
    f = MD.fangpunkte(masse)
    check(len(f) == 10 and [5.0, 0.0, 10.0, "hutschiene"] in f, "Fangpunkte (Ecken, Hutschiene, Front)")

    # ---- whole import + cache
    m = MD.importieren(stl, "+Z")
    check(m["format"] == MD.FORMAT and m["masse"] == [10, 30, 20] and m["quelle"] == "schuetz.stl",
          "Import STL")
    cache = MD.cache_pfad(os.path.join(ordner, "3D"), stl, "+Z")
    check(cache.endswith("schuetz_pZ.katie3d"), f"Cache-Name: {cache}")
    os.makedirs(os.path.dirname(cache))
    MD.speichern(cache, m)
    check(MD.importieren(cache)["netz"] == m["netz"], "Cache laden")
    try:
        MD.importieren(os.path.join(ordner, "x.obj"))
        check(False, "unbekanntes Format")
    except MD.ModellFehler:
        check(True, "unbekanntes Format abgelehnt")

    # ---- mesh body with snap points
    body = core.Koerper3D("netz", netzdaten=dict(m["netz"], fang=m["fang"]), bez="-K1", geraet="-K1")
    d = json.loads(json.dumps(body.to_dict()))
    b2 = core.Koerper3D(**{k: v for k, v in d.items() if k != "typ"})
    check(b2.geraet == "-K1" and len(b2.netzdaten["fang"]) == 10, "Gerät und Fangpunkte gespeichert")
    b2.verschieben(100, -15, 400)
    check([105.0, -15.0, 410.0, "hutschiene"] in b2.netzdaten["fang"], "Fangpunkte verschoben")
    kand = S.fang_kandidaten([b2])
    check(len(kand) == 10 and ((105.0, -15.0, 410.0), "zentrum") in kand,
          f"Fang nur über die Modellpunkte: {len(kand)}")
    check(core.Koerper3D("netz", netzdaten=m["netz"]).geraet == "", "ohne Gerät")

    # ---- STEP (only with OCP)
    if MD.ocp_verfuegbar():
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        w = STEPControl_Writer()
        w.Transfer(BRepPrimAPI_MakeBox(45.0, 75.0, 80.0).Shape(), STEPControl_AsIs)
        sp = os.path.join(ordner, "geraet.step")
        w.Write(sp)
        ms = MD.importieren(sp, "+Z")
        check(ms["masse"] == [45.0, 80.0, 75.0] and len(ms["netz"]["k"]) == 12,
              f"STEP: {ms['masse']}, {len(ms['netz']['k'])} Kanten")
        print("(mit OCP)")
    else:
        print("(OCP nicht installiert: STEP übersprungen)")
finally:
    shutil.rmtree(ordner, ignore_errors=True)

print(f"test_modell3d - OK ({ok} Pruefungen)")
