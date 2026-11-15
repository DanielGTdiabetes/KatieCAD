"""Prueba de concepto: proyecto QElectroTech (.qet) -> montaje neutro (montaje.json).

Lee los equipos del esquema (etiqueta, fabricante, referencia, descripción), les busca
medidas y modelo 3D en un catálogo por referencia y los reparte por los carriles DIN del
armario. El montaje resultante lo convierte `montaje_a_solidcraft.py` en un armario 3D.

QElectroTech no guarda posiciones de montaje: aquí se hace un reparto automático por orden
de etiqueta; la colocación fina se haría después en SolidCraft (y se puede leer de vuelta
con `component.list`).

Uso: python qet_a_montaje.py proyecto.qet catalogo.json montaje.json
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

POR_DEFECTO = {"ancho": 18, "alto": 85, "fondo": 70}  # equipo sin catálogo: 1 módulo


def leer_equipos(pfad):
    """Un equipo por etiqueta; si una etiqueta sale varias veces (unifilar y desarrollado,
    contactos esclavos…) se queda la aparición con más datos de fabricante."""
    raiz = ET.parse(pfad).getroot()
    equipos = {}
    for folio in raiz.iter("diagram"):
        for el in folio.iter("element"):
            info = {i.get("name"): (i.text or "").strip() for i in el.iter("elementInformation")}
            label = info.get("label", "")
            if not label and not info.get("designation"):
                continue
            # sin etiqueta pero con referencia (p. ej. el cofre): se identifica por la referencia
            label = label or "=" + info["designation"]
            datos = {"ind": label, "fabricante": info.get("manufacturer", ""),
                     "ref": info.get("designation", ""), "desc": info.get("description", ""),
                     "folio": folio.get("title", ""), "tipo_qet": el.get("type", "")}
            previo = equipos.get(label)
            if previo is None or (not previo["ref"] and datos["ref"]):
                equipos[label] = datos
    return list(equipos.values())


def clave_orden(ind):
    """D2 antes que D11: letras y luego número."""
    letras = "".join(c for c in ind if not c.isdigit())
    num = "".join(c for c in ind if c.isdigit())
    return (letras, int(num) if num else 0, ind)


def montar(equipos, catalogo, solo_con_ref=True):
    armario = None
    colocables, sin_modelo, omitidos = [], [], []
    for eq in sorted(equipos, key=lambda e: clave_orden(e["ind"])):
        cat = catalogo.get(eq["ref"])
        if cat and cat.get("rol") == "armario":
            armario = cat
            continue
        if solo_con_ref and not eq["ref"]:
            omitidos.append(eq["ind"])
            continue
        if not cat:
            sin_modelo.append(eq["ref"] or eq["ind"])
            cat = POR_DEFECTO
        colocables.append((eq, cat))
    if armario is None:
        raise SystemExit("El catálogo no define ningún armario presente en el esquema (rol: armario)")

    W, H = armario["ancho"], armario["alto"]
    placa = {"ancho": W - 2 * armario.get("margen", 30), "alto": H - 2 * armario.get("margen", 30),
             "grueso": 2, "separacion_fondo": armario.get("separacion_fondo", 15)}
    n, paso, largo = armario["carriles"], armario["paso_carril"], armario["largo_carril"]
    x0 = (W - largo) / 2
    z_primero = H / 2 + paso * (n - 1) / 2
    carriles = [{"x": x0, "z": z_primero - i * paso, "largo": largo} for i in range(n)]

    salida, carril, x = [], 0, x0
    for eq, cat in colocables:
        if x + cat["ancho"] > x0 + largo + 0.01:      # no cabe: siguiente carril
            carril, x = carril + 1, x0
        if carril >= n:
            raise SystemExit(f"No caben todos los equipos en {n} carriles (falta sitio para {eq['ind']})")
        e = {"ind": eq["ind"], "ref": eq["ref"] or "(sin ref.)",
             "desc": eq["desc"], "x": round(x, 2),
             "z": round(carriles[carril]["z"] - cat["alto"] / 2, 2)}
        if cat.get("step"):
            e["step"] = cat["step"]
        else:
            e["caja"] = [cat["ancho"], cat["alto"], cat["fondo"]]
        salida.append(e)
        x += cat["ancho"]
    montaje = {
        "armario": {"ancho": W, "alto": H, "fondo": armario["fondo"], "chapa": 1.5},
        "placa": placa, "carriles": carriles, "canaletas": armario.get("canaletas", []),
        "equipos": salida,
    }
    return montaje, sin_modelo, omitidos


if __name__ == "__main__":
    qet, cat_pfad, out = sys.argv[1:4]
    catalogo = json.loads(Path(cat_pfad).read_text(encoding="utf-8"))
    m, sin_modelo, omitidos = montar(leer_equipos(qet), catalogo)
    Path(out).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(m['equipos'])} equipos en {len(m['carriles'])} carriles -> {out}")
    if sin_modelo:
        print("Sin catálogo (caja por defecto):", ", ".join(sorted(set(sin_modelo))))
    if omitidos:
        print("Sin referencia, no se montan:", ", ".join(omitidos))
