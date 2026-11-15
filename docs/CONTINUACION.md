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
**HECHO (15-11-2026), primera parte de la importación:** `fileio/modell3d.py` (STEP con OCP 8 y
anteriores, STL, simplificación, orientación, puntos de captura, caché `.katie3d`),
`Koerper3D.geraet` y `netzdaten["fang"]` (se mueven con el cuerpo y son los únicos puntos de
enganche del modelo), menú 3D > «Importar modelo de equipo», colocación sobre la cara de la placa
(`_kopie_starten(ref, ebene_y)`, `_platten_punkt`), test `tests/test_modell3d.py` (STEP real con
OCP generado en el test). Falta: asociación al símbolo/artículo y «Colocar equipos» (punto 4),
puntos de captura definidos por el usuario y carril DIN (punto 7).

4. **HECHO (15-11-2026)** a nivel de equipo y de artículo (`model/geraete3d.py`, «Eléctrico >
   Asignar modelo 3D», «3D > Colocar equipos», test `tests/test_geraete3d.py`). Falta el nivel
   «por símbolo» (atributo `MODELL3D` en la definición del bloque) y puntos de captura propios.
   Diseño original: **Modelo 3D asociado al símbolo** (petición del usuario, 15-11-2026): asignar el STEP una vez y
   tenerlo ya disponible al pasar a 3D. Tres niveles, del más general al más concreto:
   - **por artículo** (TYP + fabricante, en el catálogo de piezas del proyecto `p.daten["bauteile"]`):
     todos los equipos con ese tipo heredan el modelo — lo más útil en taller;
   - **por símbolo** (atributo `MODELL3D` en la definición del bloque / `.katieblock`);
   - **por equipo** (atributo `MODELL3D` del `BlockReferenz`, gana a los anteriores).
   Al entrar en 3D, «Colocar equipos» lista los equipos del proyecto con modelo y sin colocar.
5. **Puntos de captura** (petición del usuario): cada modelo importado necesita uno o varios puntos
   para moverlo y encajarlo: automáticos (esquinas de la caja, centro de la trasera, punto medio de
   la trasera a la altura del carril DIN = punto de enganche) y opcionales definidos al importar
   (taladros de fijación). Guardarlos en el `.katie3d` (`"fang": [[x, y, z, "art"], ...]`) e
   incluirlos en `szene3d.fang_kandidaten` y en `_platz_pos` (el punto de enganche del equipo se
   engancha a la línea del carril).
6. Tests: `tests/test_modell3d.py`
7. **HECHO (15-11-2026):** carril DIN (`Insert > Carril DIN`, modo carril de la herramienta de
   canaleta, `report_templates/hutschienen.json`, `szene3d.auf_hutschiene`, test
   `tests/test_hutschiene.py`). Falta: modelo 3D con sección en sombrero (hoy es una caja).
   Diseño original: **Carril DIN** (petición del usuario): elemento como la canaleta, en barras de **2 m como
   máximo**, perfiles TS 35×7,5 y TS 35×15 (y TS 32, TS 15). El usuario tenía abierto el
   catálogo 3Dfindit de Weidmüller (carriles TS 35X15 2M, TS 35X7.5 2M …) como referencia de
   artículos y modelos. Reutilizar `model/kanal_katalog.py` (tope y partición en barras) con un
   catálogo propio y sección «sombrero»; los equipos con punto «hutschiene» enganchan a su eje. con un STL pequeño generado en el test (cubo), simplificación
   (un cubo triangulado debe quedar con 12 aristas), orientación, caché, y con OCP instalado un
   STEP generado con OCP (`BRepPrimAPI_MakeBox` + `STEPControl_Writer`) para no depender de
   archivos externos.

### 4.3 Mecanizado del armario, canaleta y desplazamiento con offset

Petición del usuario (taller): cortes cuadrados para ventiladores u otros elementos, taladros
circulares para pulsadores, perforaciones para sujetar elementos; canaleta en la placa de
montaje (la habitual: **Unex serie 77**) dibujada como una línea; menú de desplazamiento con
offset en X, Y o Z.

**Lo que ya existe (no rehacer):**

- Cortes en cualquier cara: dibujar rectángulo / círculo / polilínea sobre la cara (puerta,
  lateral, techo, placa) y cortarlo con el icono **«Agujero»** (profundidad 0 = pasante).
  Modelo: `Koerper3D.ausschnitte` (`{"ebene", "profil", "tiefe", "rund"}`) y
  `Koerper3D.loecher` (taladros verticales), métodos `ausschnitt_hinzufuegen` /
  `loch_hinzufuegen`. En 2D los cortes no abiertos hacia arriba salen discontinuos.
- Canaleta: herramienta `DUCT` (barra «Obra»), capa "CD"; en 3D crea un cuerpo con ancho y alto
  sobre la cara bajo el ratón, punto a punto como una polilínea; `DUCTJOIN` crea empalme / codo /
  T. Modelo: `Kabelkanal` (2D) y `Koerper3D.kanal = {"art": "gerade"|"verbinder"|"winkel"|"t",
  "breite"}` (3D).
- Desplazar exacto: arrastrar una flecha del manipulador 3D y teclear la distancia (un eje cada vez).

**Lo que falta (diseño):**

1. **HECHO (15-11-2026):** diálogo de mecanizado (`model/mechanik.py`, `MechanikDialog` y
   `_mechanik_klick` en `ui/ansicht3d.py`, plantillas `report_templates/mecanizado.json`, lista
   `mechanik`, test `tests/test_mechanik.py`). Pendiente: exportar DXF plano por cara para CNC.
   Diseño original: **Diálogo de mecanizado** (menú 3D > «Mecanizado…», sobre la cara elegida):
   - Tipo: rectangular, circular, taladro de fijación, y **plantillas de serie** editables en
     un JSON del programa/proyecto (como `report_templates/`): pulsador/piloto Ø22,5;
     Ø16; prensaestopas M16/M20/M25/M32/M40/M50/M63 (taladro = métrica + holgura);
     ventilador con rejilla (p. ej. 92×92, 125×125, 177×177, 223×223, 291×291 — comprobar con
     el catálogo del fabricante usado); taladro de fijación M4 / M5 / M6 (roscar Ø3,3 / 4,2 / 5,0
     o pasante Ø4,5 / 5,5 / 6,6).
   - Posición **exacta respecto a una esquina o al centro de la cara** (X, Y en la cara) además del
     clic; repetición en fila/matriz (n × paso) para filas de pulsadores o taladros.
   - Reutiliza `ausschnitt_hinzufuegen` / `loch_hinzufuegen`; cada corte guarda además una
     etiqueta (`"bez"`: "Ø22,5 pulsador", "Ventilador 125") para la lista.
   - **Lista de mecanizados** (informe y Excel): pieza (puerta, lateral izq., placa…), cara,
     tipo, medida, X/Y desde la esquina de referencia, cantidad — para el taller o una CNC
     (más adelante, exportar DXF plano por cara para la CNC).
   - Limitación actual a revisar: los cuerpos con cortes no se pueden estirar (STRETCH).
2. **HECHO (15-11-2026), primera parte:** tope de longitud de barra al dibujar (2D y 3D),
   partición en barras, catálogo `report_templates/kanal_katalog.json` (sin referencias Unex:
   rellenar del catálogo), referencia en `Kabelkanal.ref` / `Koerper3D.kanal["ref"]` y lista
   `kanaele` (`model/kanal_katalog.py`, test `tests/test_kanal_katalog.py`). Falta: plano por
   defecto = cara de la placa de montaje y etiqueta «Canaleta» en 3D como en EPLAN.
   Diseño original: **Canaleta como «línea» (estilo EPLAN)** sobre la placa de montaje:
   - Clic en el punto inicial; la canaleta **se estira con el ratón hasta un máximo de 2000 mm**
     (longitud de barra) o se para antes con un segundo clic o tecleando la longitud; si se sigue,
     empieza otra barra (cada barra = un tramo, para la lista de materiales y el corte).
   - Medidas **ancho × alto** de una lista de catálogo editable (Unex serie 77, canal ranurado;
     las medidas exactas deben tomarse del catálogo Unex) más «libre».
   - Por defecto sobre la cara delantera de la placa (plano y = cte, como la colocación de
     equipos) y orientación horizontal/vertical con ORTHO.
   - Para la lista de materiales: referencia, medida, longitud por tramo y total (metros de
     canaleta y número de barras de 2 m). Tapa incluida o aparte (opción).
   - Partir de la herramienta `DUCT` existente: añadir tope de longitud, catálogo y datos de
     artículo al `Koerper3D.kanal` (p. ej. `"ref"`, `"hoehe"`, `"laenge"`).
3. **HECHO (15-11-2026):** menú «Desplazar con offset…» (`CadApp.versatz_verschieben`,
   `VersatzDialog`, `core.versetzen` / `core.kann_z`, test `tests/test_versatz.py`).
   Diseño original: **Menú «Desplazar con offset…»** (menú Editar y clic derecho en 3D, también en 2D):
   diálogo con **ΔX, ΔY, ΔZ** a la vez (y opción «copiar» con número de copias), aplicado a la
   selección con un único paso de deshacer. Reutiliza `verschieben(dx, dy, dz)` de los cuerpos
   (en 2D, ΔZ desactivado).

Orden propuesto: 3 (pequeño, útil ya) → 2 (canaleta) → 1 (mecanizado + lista) → STEP y
colocación de equipos (4.1–4.2), porque la colocación y la canaleta comparten el plano de
la placa de montaje.

### 4.4 Referencia visual: EPLAN Pro Panel (capturas del usuario, 15-11-2026)

El usuario busca algo parecido a EPLAN Pro Panel:

- **Armario 3D:** envolvente transparente con puerta, placa de montaje, equipos con su STEP
  (seccionador rojo, pantalla, PLC, contactores, guardamotores, fuentes), **canaletas con su
  rótulo** («Wire duct»), carriles DIN, prensaestopas en el fondo, baliza en el techo.
- **Regletas en 3D** sobre carril, con colores por tipo (gris, azul N, verde-amarillo PE) y
  **cableado en 3D** por las canaletas, cada hilo con su color.
- **Regleta en 2D** (plano de conexiones de bornes): bornes con tornillos, colores por tipo,
  número arriba, hilos hacia arriba y abajo, carril, cuadro del cable abajo. → La vista gráfica
  de regletas (`reports/leistenbild.py`) ya sigue este estilo (colores, tornillos, carril).

Pendiente para acercarse más: rótulo de canaleta en 3D, carriles DIN como elemento, regletas en
3D generadas desde el esquema, enrutado de hilos por canaleta (muy grande, al final).

**Catálogo Unex Canal 77** (`report_templates/kanal_katalog.json`): 25 medidas tomadas de la
librería BIM de Unex (<https://www.unex.net/es/bim>, sección «Canal 77», archivos STEP
`18.20.77` … `100.150.77`). Referencia = **alto.ancho.77** (confirmado por el usuario el
15-11-2026: `60.40.77` = 60 de alto × 40 de ancho). Los STEP de la canaleta también podrían usarse como modelo 3D real más adelante.

### 4.5 Alternativa: conector con SolidCraft en lugar de ampliar el 3D propio

Idea del usuario: prescindir del 3D de KatieCAD y conectar con **SolidCraft**
(<https://github.com/tangency-labs/solidcraft>, <https://solidcraft.io>).

Comprobado en su README y documentación (noviembre de 2026):

- CAD 3D **paramétrico de código abierto en Rust**, licencia **Apache-2.0** (compatible: serían
  dos programas separados que se pasan archivos, sin mezclar código con KatieCAD, BSD-3).
- Escritorio (instalador Windows), navegador, **CLI sin pantalla** y **servidor MCP**.
- **STEP nativo** (AP203/AP214/AP242, ensamblajes, nombres, colores) de entrada y salida; también
  IGES, STL, OBJ, 3MF, glTF.
- Taladros, patrones, ensamblajes, **chapa con desarrollo plano y exportación DXF** (útil para el
  mecanizado de puertas y laterales en CNC).
- Automatización: un **script JSON** con los mismos comandos de la interfaz, ejecutado con
  `solidcraft-cli run script.json --out cuadro.step` (o `--save` a `.sc`). Comandos vistos:
  `file.insert_step {"path"}`, `solid.box {"length","width","height","corner","body_name"}`,
  `solid.move {"bodies", "matrix" | "translate"/"origin"/"axis"/"angle", "copy"}`,
  `sketch.create`, `sketch.rectangle.two_point`, `solid.extrude`, `file.export`.
  Lista completa: `solidcraft-cli commands` y `docs/features.md` de su repositorio.
- Está en beta (0.x): los comandos pueden cambiar entre versiones → fijar versión y comprobar con
  `solidcraft-cli commands` en un test de integración opcional.

**Diseño del conector (propuesta):**

1. KatieCAD sigue siendo el maestro de los datos eléctricos (equipos con IND, TYP, referencia,
   ruta del STEP del fabricante, posición en placa, canaletas, mecanizados).
2. Exportación «Proyecto > Exportar montaje para SolidCraft…» → `montaje.json` (script):
   - armario: `file.insert_step` del STEP del fabricante, o cajas `solid.box` con las medidas;
   - cada equipo: `file.insert_step` de su STEP + `solid.move` con la matriz de posición sobre la
     placa, `body_name` = IND (`-K1`);
   - canaletas: `solid.box` por tramo (ancho × alto × longitud ≤ 2000) con nombre de artículo;
   - mecanizados: boceto en la cara + corte (pendiente de ver los comandos exactos de corte /
     taladro en `features.md`).
   Luego `solidcraft-cli run --script-relative montaje.json --save cuadro.sc --out cuadro.step`,
   o abrir el resultado en SolidCraft.
3. ¿Dónde se decide la posición de cada equipo? Dos opciones a decidir con el usuario:
   - **a)** en KatieCAD, con un **esquema de montaje 2D** de la placa (vista frontal, rectángulos
     con el tamaño del equipo; estilo «panel layout» 2D de EPLAN), y SolidCraft solo construye el 3D;
   - **b)** en SolidCraft (su interfaz 3D es mejor) y KatieCAD solo envía la lista de piezas; para
     las listas (mecanizado, canaleta) habría que leer de vuelta las posiciones (formato `.sc` o
     el STEP exportado con nombres de cuerpo).
   Recomendación: **a)**, porque mantiene los datos del cuadro en KatieCAD y no depende de leer el
   formato interno de SolidCraft.
4. Ventajas: KatieCAD no necesita OCP ni mallas; STEP y chapa reales; KatieCAD más ligero.
   Inconvenientes: dos programas; SolidCraft en beta; el armario 3D de KatieCAD (vistas en
   presentaciones) quedaría para vistas sencillas o se sustituiría por vistas exportadas.

Decisión pendiente del usuario: 3D propio (4.1–4.3) o conector SolidCraft (4.4). Las partes 4.3.1
(lista de mecanizados), 4.3.2 (datos de canaleta) y 4.3.3 (desplazar con offset) sirven en
ambos casos.

### 4.6 Entorno de prueba usado

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
