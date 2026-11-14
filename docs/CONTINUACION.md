# KatieCAD – estado del trabajo y cómo continuar

Documento de traspaso (noviembre de 2026) para seguir el trabajo en este u otro PC.
Fork: <https://github.com/DanielGTdiabetes/KatieCAD> (original de Merecete, BSD-3).
Objetivo: sustituir EPLAN Pro Panel 2.4 en el taller de cuadros eléctricos.

## 1. Rama y cómo retomarla

- Rama de trabajo: **`feature/numeracion-hilos`** (subida a GitHub). `main` sin tocar, sin PR.
- Clon de trabajo en este PC: `E:\projects\katiecad`. La app original instalada sigue en
  `D:\KatieCAD` (no se toca).

```bash
git clone https://github.com/DanielGTdiabetes/KatieCAD.git
cd KatieCAD
git checkout feature/numeracion-hilos
python -m pip install -r requirements.txt
python main.py
python tests/run_all.py
```

- `requirements.txt` incluye `ezdxf` y `ezdwg` (DXF/DWG). Sin ellas el programa funciona, pero
  no exporta DXF/DWG desde el código fuente. Para la tarea 4 hará falta además
  `cadquery-ocp-novtk` (lector STEP; existe versión para Python 3.14: 8.0.1.1).

## 2. Convenciones del proyecto

- Código y nombres en **alemán**. `model/`, `electrical/` y `reports/` **no importan Tkinter**.
- Todo texto de interfaz en `katiecad/common/i18n.py` en `de`, `en` y `es` con las mismas claves
  y marcadores. `tests/test_sprachen.py` lo comprueba, también que **no haya claves repetidas**
  (Python se queda en silencio con la última).
- Tests sin pantalla con `tests/stub.py`; cada test nuevo se añade a `tests/run_all.py`.
- Cada función nueva se documenta en `docs/CHANGELOG.md` (de), `docs/CHANGELOG.en.md` y
  `docs/USER_GUIDE.md`.
- Commits pequeños en español; nunca push a `main`.
- Hoja activa = `self.elemente`; las demás hojas son JSON en disco
  (`_andere_blaetter_daten`, `_zeichnungsblaetter_einlesen`, `_json_atomar_schreiben`).
- Los cables (`Leitung`) se regeneran solos (`electrical/logic.leitungen_automatisch`); no guardar
  datos en ellos (excepción: el estilo, que se hereda al regenerar, ver más abajo).

### Estado de los tests

`python tests/run_all.py`: todo pasa salvo **4 fallos que ya existían y no son del código nuevo**:

| Test | Motivo |
|---|---|
| `test_funktion` | `sps_art` del símbolo DI (pendiente de investigar aparte) |
| `test_pdf_import` | falta `pypdf` en el Python del sistema |
| `test_schriften` | depende de las fuentes instaladas en el PC |
| `test_pruefung` | rotación del log (`.old`) en este PC |

Con `ezdxf`/`ezdwg` instalados, `test_dxf_linientypen` además genera y relee un DXF y un DWG reales.

## 3. Hecho en esta rama (resumen)

1. **Numeración de hilos** (`electrical/drahtnummern.py`, Proyecto > Numerar hilos…):
   - Formato por defecto `{sheet}{n:02}` con primer número 0 → hoja 10: 1000, 1001…
     (ajuste «Primer número de cada hoja»; proyectos antiguos con formato guardado siguen en 1).
   - Prioridad: manual > automático existente (modo «solo nuevos») > canal PLC (`DI0.00`) >
     **nombre libre de la flecha de potencial** (`+24VDC`, `+24VDC1`, `L1`…, activado por defecto,
     también si la pareja de flechas solo continúa el hilo en otra hoja) > formato.
   - Una etiqueta **en cada rama** de una bifurcación (opción `je_ast`).
   - Los cables del **esquema unifilar** no se numeran (salvo «evaluar también el unifilar»).
   - Color y sección opcionales en la `Drahtnummer` (doble clic); el net guarda por nodo
     `Knoten.draht` y `Knoten.draht_daten`.
2. **Plan de bornes** (`reports/daten.klemmenplan`, `reports/seiten.py`):
   lado externo/interno (modo configurable en el diálogo de documentación), hilo, cable/conductor,
   color y sección por lado; **vista gráfica de regletas** (`reports/leistenbild.py`: topes, tapas,
   separadores `Klemme.trennplatte`, puentes, barras de cable); Excel con una hoja por regleta.
3. **Etiquetas M-Print PRO** (`reports/mprint.py`, Proyecto > Exportar etiquetas para M-Print PRO…):
   hilos (una por extremo), bornes en orden de montaje, equipos; Excel (una hoja por lista, texto en
   A, sin cabecera por defecto) o CSV; aviso de longitud. Número de hilo en la lista de conexiones.
4. **Imán de pines** (`logic.pins_ausrichten`, 1,5 mm) y **limpieza visual** en pantalla
   (Configuración): campos con valor de plantilla, textos < 5 px, pines como punto.
5. **Tipos de línea** en cables (barra o propiedades; se aplica al hilo entero y se conserva al
   regenerar el tramo), nombres traducidos, tipos nuevos «De puntos» y «Raya-dos puntos»;
   exportación a **DXF y DWG** como `DASHED`, `CENTER`, `DIVIDE`, `DOT`
   (`fileio/dxf_linientypen.py`).
6. **Símbolos unifilares nuevos** (`symbols/12 Single-pole`, generador
   `tools/make_symbols_einpolig_extra.py`, nunca sobrescribe): seccionador, interruptor-seccionador,
   contactor, contador kWh, variador, SAI, embarrado (7 tomas), generador e inversor FV.
7. Correcciones: el diálogo de documentación ya no borra otros ajustes de `p.doku`; claves i18n
   duplicadas; `test_reports` cierra el `.xlsx` (bloqueo en Windows).

## 4. Tarea 4 – STEP y modelo 3D por equipo (SIGUIENTE, sin empezar en código)

Petición: importar STEP y asignar un modelo 3D a cada equipo del esquema; el visor es alámbrico
(Tkinter), así que la pieza se convierte a malla `Koerper3D` de tipo `"netz"` simplificada; campo
«modelo 3D» en la ficha del equipo y colocación en el armario 3D.

### 4.1 Lo que ya existe y se reutiliza

- `model/core.Koerper3D(art="netz", netzdaten={"p": [[x,y,z]...], "k": [[i,j]...], "f": [[i,j,k]...]})`:
  `k` = aristas que se dibujan, `f` = caras (solo para ocultar líneas y elegir caras).
- `model/geom3d.Netz` (punkte, kanten, flaechen).
- Armario: `model/schrank.schrank_bauen` (frente hacia −Y, placa de montaje vertical al fondo,
  partes con `bez` "Schaltschrank", "Montageplatte"…). En `model/szene3d.py` (línea ~73) ya se
  buscan esas partes por nombre.
- Colocar con el ratón en 3D: `ui/ansicht3d.py` → `_kopie_starten(quellen)`, `_platz_pos`,
  `_platz_klick`, `_vorschau_zeichnen`. Hoy proyecta el ratón sobre un plano **horizontal**
  (`_bodenpunkt(e, z)`) y engancha esquinas (`S.fang_kandidaten`).
- Ficha del equipo: `CadApp.attribute_bearbeiten` → `BlockAttributeDialog` (ui/dialogs.py).

### 4.2 Diseño propuesto

1. **`katiecad/fileio/modell3d.py`** (sin Tkinter):
   - `lese_step(pfad, toleranz)` con OCP: `STEPControl_Reader` → `BRepMesh_IncrementalMesh`
     (tolerancia lineal ~0,5 mm, angular ~0,5 rad) → recorrer caras (`TopExp_Explorer`,
     `BRep_Tool.Triangulation_s`, respetando la `TopLoc_Location`) → puntos + triángulos.
     Si OCP no está: error claro con `pip install cadquery-ocp-novtk`.
   - `lese_stl(pfad)` (binario y ASCII, Python puro) como alternativa y para los tests.
   - `vereinfachen(punkte, dreiecke, kantenwinkel=25°, max_dreiecke=20000)`: soldar vértices,
     agrupar vértices en rejilla si hay demasiados triángulos, quitar degenerados y dejar como
     aristas solo **contornos y aristas vivas** (ángulo entre normales > kantenwinkel), para que el
     alámbrico sea legible y rápido.
   - `ausrichten(netz, front="+Z")`: girar para que el frente del equipo mire a −Y y arriba sea +Z;
     trasladar a x∈[0,ancho], z∈[0,alto], y∈[−fondo,0] (trasera en y = 0).
   - Caché `.katie3d` (JSON: `{"format": "katiecad-3d", "version": 1, "quelle": …, "front": …,
     "netz": netzdaten}`) en una carpeta `3D` del proyecto, para convertir el STEP una sola vez.
2. **Campo «Modelo 3D» en la ficha**: atributo libre `MODELL3D` del `BlockReferenz` (ruta relativa
   al proyecto del `.katie3d`). En `BlockAttributeDialog`, una fila con botón «…» que abre
   STEP/STL/katie3d, pregunta el eje frontal (+Z / +Y / −Y / +X) y convierte.
3. **Colocar en el armario** (menú 3D > «Colocar equipo en el armario…»): lista de equipos del
   proyecto con modelo (IND, TYP, ya colocado sí/no); el elegido se crea como
   `Koerper3D(art="netz", bez=IND)` con un campo nuevo `geraet=IND` (añadirlo al `__init__` para
   que se guarde y se cargue) y se coloca con el modo de `_kopie_starten`, ampliado con:
   - `ref` = esquina trasera-inferior-izquierda del modelo (no la mínima),
   - plano de colocación = **cara delantera de la placa de montaje** (plano vertical y = cte)
     en lugar del plano horizontal; con OSNAP siguen enganchando las esquinas.
   - Armarios girados un ángulo cualquiera: de momento colocar en el suelo y avisar.
4. Tests: `tests/test_modell3d.py` con un STL pequeño generado en el test (cubo), simplificación
   (un cubo triangulado debe quedar con 12 aristas), orientación, caché, y con OCP instalado un
   STEP generado con OCP (`BRepPrimAPI_MakeBox` + `STEPControl_Writer`) para no depender de
   archivos externos.

### 4.3 Entorno de prueba usado

En la sesión se creó un entorno aislado temporal con `ezdxf 1.4.5`, `ezdwg`, `cadquery-ocp-novtk
8.0.1.1` y Pillow (comprobado: `from OCP.STEPControl import STEPControl_Reader` funciona). Está en
la carpeta temporal de la sesión y puede desaparecer; para recrearlo:

```bash
python -m venv .venv-pruebas
.venv-pruebas\Scripts\python -m pip install -r requirements.txt cadquery-ocp-novtk pillow
.venv-pruebas\Scripts\python tests\run_all.py
```

## 5. Otras tareas y pendientes anotados

- **Potenciales**: además del nombre de la flecha, se habló de un menú de potenciales del proyecto
  (230VAC, 24VDC, 32VAC, 400VAC…) con color/sección por potencial. No implementado; decidir si
  aporta algo frente a las flechas con nombre libre.
- **Numeración «por conexión»** (número distinto por rama de una T): no implementado; hoy un
  potencial = un número, con etiqueta en cada rama.
- **Interfaz**: el lienzo de Tkinter no suaviza líneas (sin antialiasing); mejorarlo exige rehacer el
  dibujo en pantalla (p. ej. renderizar con Pillow). Trabajo grande, aparte.
- Símbolos unifilares con pines fuera de la rejilla de 5 mm: los dos diferenciales y la fuente
  AC-DC (pines a 6 mm o −24 mm); casi nunca se cablean solos.
- Alinear por conexiones como comando explícito y aviso de «pines casi alineados» en la
  comprobación del proyecto (propuestos, no hechos).
- `test_funktion` (`sps_art` del símbolo DI) sigue fallando desde antes.
- La opción «evaluar también la representación unifilar» solo se cambia en el diálogo de
  documentación.
