"""Prueba de concepto: montaje neutro (JSON) -> script de solidcraft-cli.

Convención (la de KatieCAD, model/schrank.py): Z arriba, frente del armario hacia -Y,
placa de montaje vertical al fondo. Cada equipo en su STEP: ancho en X, alto en Z,
fondo hacia -Y y trasera en y = 0.

Uso: python montaje_a_solidcraft.py montaje.json script.json
"""
import json
import sys
from pathlib import Path


def matriz_traslacion(x, y, z):
    return [1, 0, 0, x, 0, 1, 0, y, 0, 0, 1, z]


def caja(nombre, x0, y0, z0, dx, dy, dz):
    return {"command": "solid.box", "params": {
        "length": dx, "width": dy, "height": dz, "corner": [x0, y0, z0], "body_name": nombre}}


def generar(m):
    a = m["armario"]
    W, H, D, e = a["ancho"], a["alto"], a["fondo"], a.get("chapa", 1.5)
    pl = m["placa"]
    y_placa = -pl["separacion_fondo"]          # cara delantera de la placa
    cmds = []
    # Envolvente (sin puerta): fondo, laterales, techo y suelo
    cmds += [caja("Armario_fondo", 0, -e, 0, W, e, H),
             caja("Armario_izq", 0, -D, 0, e, D, H),
             caja("Armario_der", W - e, -D, 0, e, D, H),
             caja("Armario_techo", 0, -D, H - e, W, D, e),
             caja("Armario_suelo", 0, -D, 0, W, D, e)]
    # Placa de montaje
    px, pz = (W - pl["ancho"]) / 2, (H - pl["alto"]) / 2
    cmds.append(caja("Placa", px, y_placa, pz, pl["ancho"], pl["grueso"], pl["alto"]))
    # Carriles DIN (35 x 7,5) con taladros roscados M5 en los extremos (mecanizado de placa)
    for i, c in enumerate(m.get("carriles", []), 1):
        cmds.append(caja(f"Carril_{i}", c["x"], y_placa - 7.5, c["z"] - 17.5, c["largo"], 7.5, 35))
        for xh in (c["x"] + 10, c["x"] + c["largo"] - 10):
            cmds.append({"command": "solid.hole", "params": {
                "position": [xh, y_placa, c["z"]], "thread": "M5", "depth": pl["grueso"],
                "targets": ["Placa"]}})
    # Canaletas (alto = profundidad desde la placa, ancho en el plano de la placa)
    for i, k in enumerate(m.get("canaletas", []), 1):
        alto, ancho = k["alto"], k["ancho"]
        if k["dir"] == "h":
            cmds.append(caja(f"Canaleta_{i}_{k['ref']}", k["x"], y_placa - alto, k["z"], k["largo"], alto, ancho))
        else:
            cmds.append(caja(f"Canaleta_{i}_{k['ref']}", k["x"], y_placa - alto, k["z"], ancho, alto, k["largo"]))
    # Equipos: un STEP por equipo, colocado sobre el carril; componente = IND
    for eq in m["equipos"]:
        y = y_placa - 7.5 if eq.get("sobre_carril", True) else y_placa
        if eq.get("step"):
            cmds.append({"command": "file.insert_step", "params": {
                "path": str(Path(eq["step"]).resolve()), "name": eq["ind"],
                "matrix": matriz_traslacion(eq["x"], y, eq["z"])}})
        else:
            # Sin modelo 3D: caja con las medidas del catálogo, convertida en componente
            ancho, alto, fondo = eq["caja"]
            cmds.append(caja(eq["ind"], eq["x"], y - fondo, eq["z"], ancho, fondo, alto))
            cmds.append({"command": "component.from_bodies", "params": {"bodies": [eq["ind"]]}})
        cmds.append({"command": "component.metadata.set", "params": {
            "component": eq["ind"], "part_number": eq["ref"],
            "description": eq.get("desc", ""), "bom_type": "purchased"}})
    # Colores básicos
    cmds.append({"command": "appearance.assign", "params": {
        "bodies": ["Placa"], "color": "#c8c8c8"}})
    canal = [f"Canaleta_{i}_{k['ref']}" for i, k in enumerate(m.get("canaletas", []), 1)]
    if canal:
        cmds.append({"command": "appearance.assign", "params": {"bodies": canal, "color": "#7a7a7a"}})
    return cmds


if __name__ == "__main__":
    m = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(json.dumps(generar(m), indent=1), encoding="utf-8")
    print(f"{len(generar(m))} comandos -> {sys.argv[2]}")
