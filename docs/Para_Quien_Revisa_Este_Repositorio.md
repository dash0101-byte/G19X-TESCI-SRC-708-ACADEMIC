# Para quien revisa este repositorio

Escrito el **07-10-2026** para quien llega de fuera: alguien que va a evaluar el trabajo, o un
programa que va a clonarlo, levantarlo y buscarle fallos. Supone que no se ha leído nada más
del repositorio y no pide leer nada antes.

Son seis cosas, y la primera cambia lo que miden todas las demás.

---

## 1. Un clon limpio no trae el modelo, y sin él el sistema arranca igual

`ml_pipeline/models/lead_scorer_model.joblib` **no está versionado** —`.gitignore`, línea 77—.
Es deliberado: `joblib.load` deserializa con *pickle*, que ejecuta código al cargar, así que un
binario de 900 KB comprometido en el árbol es un fichero que nadie sabe cuándo se entrenó y que
el backend ejecuta con sus credenciales. El CI lo entrena en el trabajo `modelo` y lo pasa al
trabajo `imagenes` como artefacto, de modo que la imagen se construye con el modelo que ese
mismo pipeline acaba de validar.

Fuera del CI no hay quien lo reponga. Y esto es lo que pasa si no se repone:

* `backend/Dockerfile` copia `ml_pipeline/models` a la imagen. El directorio existe —lleva tres
  ficheros `.json` que sí se versionan—, así que la copia **no falla**.
* `NativeMLScoringAdapter` no encuentra el artefacto, lo anota en el registro con nivel `info` y
  **cae al heurístico calibrado**, que es su diseño: una instancia sin modelo sigue sirviendo.
* Los seis contenedores se ponen verdes, el panel funciona, las fichas se puntúan y el embudo se
  dibuja. **No hay ningún síntoma.**

Lo que se está midiendo entonces es el heurístico, que es exactamente **la línea base contra la
que este trabajo se defiende**: el modelo aporta `+0,0519` de ROC-AUC sobre él. Medir el
heurístico y llamarlo modelo no da un error; da una conclusión equivocada.

**Así que el entrenamiento es el primer paso del primer arranque**, antes de `pila.py`:

```bash
pip install --require-hashes -r backend/requirements.lock
python ml_pipeline/src/train_model.py
```

Los datos ya están en el repositorio —`ml_pipeline/data/leads_historical.csv`, sintético,
3000 filas, semilla 42—, así que no hace falta nada de fuera. Tarda **unos dos minutos**.

Y reproduce: el 07-10-2026 se entrenó de cero sobre el entorno del lock (Python 3.13.15,
scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.5, joblib 1.6.0) y el artefacto salió **idéntico
byte a byte** al que produjo el entrenamiento original del 16-09-2026 —misma huella SHA-256,
`98ed8bd1…`— con todas las cifras iguales hasta el último decimal: ROC-AUC 0,9469, IC 95 %
[0,9275, 0,9635], aporte +0,0519 con IC [+0,0296, +0,0761], F1 0,8405, Brier 0,0872. Esa es
también la razón de que la huella de `metrics.json` pueda fijarse en el despliegue:

```bash
ML_MODEL_SHA256=98ed8bd179414ea724102600fffcc5db4adeb753e15161eea5c3df80e49d2a63
```

Con otras versiones de `scikit-learn` o `numpy` el artefacto puede salir equivalente y con otra
huella; en ese caso se fija la que imprima el entrenamiento, o no se fija ninguna. Una huella
fijada que no cuadra **impide cargar el modelo** —a propósito— y devuelve el sistema al
heurístico, con un `logger.error` que lo dice.

Un detalle que conviene saber antes de ejecutarlo: el entrenamiento **reescribe** los tres
`.json` versionados de `ml_pipeline/models/`. Si las cifras no cambian, el único cambio real es
la marca de tiempo del perfil de referencia y una entrada nueva en el registro de modelos. No es
un fallo: es el registro de procedencia haciendo su trabajo.

### El primer arranque entero, en orden

Cuatro pasos. Se ejecutaron en este orden, sobre un clon limpio, el 07-10-2026:

```bash
# 1. EL MODELO. Dos minutos. Sin esto se mide el heurístico, como dice todo lo de arriba.
pip install --require-hashes -r backend/requirements.lock
python ml_pipeline/src/train_model.py

# 2. EL CLIENTE COMPILADO. Tampoco viaja en el repositorio —`dist/` está en `.gitignore`— y
#    la imagen del backend lo copia para poder servir la SPA ella sola en el 8000.
cd frontend && npm ci && npm run build && cd ..

# 3. LA PILA. `iniciar` crea ~/.plurione/pila.env con los dos secretos ya generados.
python devops/pila.py iniciar
python devops/pila.py up --build -d

# 4. LOS DATOS. Recién migrada, la base no tiene NI UNA CUENTA: el panel pide credenciales
#    que todavía no existen. Esto crea las siete cuentas, 4 publicaciones y 12 prospectos.
python devops/pila.py exec -e ENVIRONMENT=development -e SEED_ADMIN_PASSWORD=PluriOne2026! -e SEED_SALES_LEAD_PASSWORD=PluriOne2026! -e SEED_EXECUTIVE_PASSWORD=PluriOne2026! -e SEED_ASESOR_PASSWORD=PluriOne2026! backend python /app/scripts/seed_data.py
```

El panel queda en [http://localhost:3000](http://localhost:3000) y se entra con
`lider.ventas@plurione.com` y esa contraseña. `curl -s http://127.0.0.1:8000/health` tiene que
decir `"ml_model_loaded": true`.

**Por qué el `-e ENVIRONMENT=development` del paso 4**, que parece una trampa y no lo es: el
sembrado de demostración **vacía las tablas de negocio** antes de regenerarlas, así que se niega
a correr contra un entorno endurecido —y la pila arranca en `production`—. La variable se pasa a
**ese** proceso y no a la pila. En una instalación de verdad lo que se usa es `--solo-usuarios`,
que crea las cuentas y no toca ningún otro dato; está en [Si algo falla](Si_Algo_Falla.md). Y sin
`--force`, el sembrado completo se niega en cuanto la base **ya** tiene datos de negocio y
enumera lo que borraría: en una recién migrada no los tiene, así que no hace falta.

**En Windows, clone con `core.longpaths`.** La ruta relativa más larga del repositorio mide **169
caracteres** —el informe de un capítulo, con su título entero en el nombre—, de modo que con el
límite de 260 de Windows la carpeta donde clone tiene que medir menos de **90**. Si no, `git
clone` escribe los que caben, deja fuera unos cuantos con `unable to create file … Filename too long`,
y el índice se queda **vacío**: `git status` dice entonces que están **todos borrados**, 434
líneas de `D `, que es lo último que describe lo que pasó. Se evita de una vez:

```bash
git clone -c core.longpaths=true <url>
```

---

## 2. Cómo saber qué motor está puntuando

No hace falta leer registros. La respuesta está en `/health`:

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{ "status": "healthy", "database": "connected",
  "ml_engine": "NativeMLScoringAdapter", "ml_model_loaded": true }
```

**`ml_model_loaded` es el campo que importa.** En `false`, lo que puntúa es el heurístico: hay
que volver al punto 1. `ml_engine` dice qué adaptador está montado, no si tiene artefacto, así
que no sirve para esto.

Y después del hecho, cada puntuación lo lleva escrito. La auditoría guarda
`v1.0.0-hybrid+ml:98ed8bd1` o `v1.0.0-hybrid+heuristico` según quién puntuó de verdad. Eso fue
el segundo tramo del hallazgo A-5: se arregló que el modelo llegara a la imagen y el historial
seguía afirmando que todo venía del modelo. Un historial que no distingue con qué se calculó no
sirve para auditar.

### Qué se puede comprobar sin levantar nada

Casi todo. Con el entorno del lock instalado y **sin Docker**:

```bash
python -m pytest backend/tests -q                   # 2093 pruebas; 13 min 5 s con cobertura
ruff check backend/ scripts/
python scripts/guarda_de_la_pagina_publica.py       # la única ruta sin sesión que escribe
python scripts/guarda_del_motor_de_reglas.py        # lo que decide de madrugada
python scripts/guarda_de_los_desenlaces.py          # lo que produce etiquetas de entrenamiento
python scripts/guarda_del_reparto_automatico.py     # lo que decide en el alta
python -m pytest scripts/test_hojas_de_observacion.py -q
python scripts/renovar_imagenes.py --solo-fijacion  # que ninguna imagen quede sin huella
cd frontend && npx vitest run && npx eslint src && npm run build   # 748 pruebas
```

La suite corre sobre **SQLite en memoria** y cada guarda se monta su propia base temporal y
habla con la aplicación por `TestClient`: ninguna necesita la pila, ni PostgreSQL, ni red.

**Una regla que cuesta tiempo aprender por las malas: nunca dos `pytest` a la vez.** Comparten
la base de pruebas y producen cientos de fallos falsos —una vez, 227 rojas sobre un árbol
correcto—. Si va a repartir el trabajo entre varios agentes, que solo uno corra la suite.

Lo que **sí** necesita Docker es la construcción de las imágenes, la pila, la comprobación de
la puerta pública (`scripts/comprobar_puerta_publica.py`) y las copias con su prueba de
restauración.

---

## 3. Qué se defiende, y sobre qué datos

Las cifras del modelo **se miden sobre datos sintéticos** cuya etiqueta se genera con una
fórmula conocida a partir de las propias variables más ruido. Eso no es un atajo que se intenta
disimular; está escrito en `metrics.json`, en el README, en la memoria y en la salida del propio
entrenamiento. Lo que verifican es que **el pipeline está íntegro** —que las variables llegan,
que el preprocesado no las corrompe, que la calibración funciona—, no el rendimiento comercial,
que solo puede medirse con conversiones reales que todavía no existen.

Por eso la cifra que se defiende no es el 0,9469 sino el **aporte sobre las líneas base del
mismo conjunto**: azar 0,5, ordenar por una sola columna 0,9053, heurístico sin modelo 0,8950,
modelo 0,9469. Aporte **+0,0519**, IC 95 % [+0,0296, +0,0761]. Un trabajo que presentara el
0,9469 a secas estaría presentando sobre todo la facilidad del conjunto.

---

## 4. Si esto parece un fallo

Esta tabla es lo que una revisión —humana o automática— encuentra primero y marca, y que está
decidido así. No es una lista de excusas: cada fila dice **dónde** se decidió, y si la razón no
convence, la discusión es con ese sitio.

| Lo que se ve | Por qué es así | Dónde está decidido |
| :--- | :--- | :--- |
| `/api/v1/interes/{slug}` contesta **404 con el mismo texto** si la publicación no existe, si no está activa y si no es de LinkedIn | Es la única ruta sin sesión. Distinguir los tres casos deja enumerar publicaciones desde fuera | `interes.py`, cabecera · C25 |
| El `POST` de esa ruta contesta **202 siempre**: exista o no el correo, sea la primera vez o la quinta, y también cuando el **campo trampa** viene relleno | Un robot no debe poder distinguir si su envío sirvió. Y lo que pase después —si crea ficha, si se suma a una que existía, qué score sale— no es asunto de quien envía | `interes.py`, cabecera · C25 |
| `is_healthy()` del adaptador ML devuelve `True` sin comprobar nada | Sin artefacto el servicio **sigue siendo útil**: cae al heurístico. Marcar la instancia como enferma la sacaría del balanceador por una degradación que no impide atender | `main.py::health`, comentario |
| La **bitácora de auditoría no se borra nunca**, ni al ejercer el derecho de supresión | La supresión recorre cada tabla que apunta al prospecto y en la bitácora **sustituye el correo por una huella con clave**: queda que algo se suprimió, sin el dato. Una bitácora que se puede borrar no es una bitácora | `derechos_del_titular.py::suprimir_prospecto` |
| `users.capacity` se declara y **no limita nada**: el reparto automático no la mira | Es la cartera **máxima declarada**, no la cartera abierta. Que fuera un tope de verdad exige decidir qué pasa cuando se alcanza —no repartir la ficha es peor—, y eso es funcionalidad | §6.4 punto 59 · `reparto_automatico.py` |
| El motor de reglas tiene **granularidad de un día**: una ficha nueva no tiene tarea hasta la pasada siguiente | Barre **estado**, no eventos. Bajar de un día convierte una pasada diaria en un servicio. Los cierres sí son inmediatos | §7, fila «Granularidad menor de un día» |
| La suite corre sobre **SQLite en memoria**, así que `FOR UPDATE` no se ejercita | Lo que solo existe en PostgreSQL se comprueba sobre la **sentencia compilada** contra el dialecto real. Dar por bueno lo que no se ha podido ejecutar es lo que costó el capítulo 46 | `AGENTS.md` §3 · C46 |
| Suprimir un prospecto aquí **no lo suprime en el CRM** | El sistema no tiene permiso de escritura de borrado en el CRM ajeno. Prometerlo sería peor que decirlo | §5.3 |
| Aceptar el aviso de privacidad **no es condición** para crear la ficha desde el panel | El consentimiento se exige en la página pública, donde lo da la persona. En el panel lo daría quien teclea, que no es la misma cosa | §5.2 |
| «¿Qué necesitas?» del formulario público **no pesa** en el score | Es texto libre. Un peso inventado para texto libre es indistinguible de una medición para quien lea el resultado seis meses después | §5.4 · §7 |
| El alta de una ficha contesta **400 y 409 para el mismo conflicto** | El 400 lo da su propia comprobación; el 409, la carrera que detecta la base. Unificarlo cambia lo que un cliente ya recibe sin corregir ningún dato | §6.4 punto 43 |
| El panel puede enseñar en rojo **«la dirección pública no responde»** con el túnel funcionando | La sonda sale **desde el contenedor**. En una red con TLS interceptado —proxy corporativo— el certificado lo firma una CA que no está en el almacén del contenedor y la comprobación falla siempre. Se apaga con `COMPROBAR_DIRECCION_PUBLICA=false` | `Poner_la_Direccion_de_la_Empresa.md` |
| El `pip install` de la construcción de la imagen falla con **«No matching distribution found for aiosqlite==0.22.1»** | **No es el lock.** Dos líneas más arriba está la causa: `CERTIFICATE_VERIFY_FAILED`. En una red que intercepta TLS —un proxy corporativo— el certificado de PyPI lo firma una autoridad que no está en el almacén del contenedor, pip no puede leer el índice y lo cuenta como «ninguna versión disponible». Es la misma red que pinta de rojo la dirección pública, dos filas más abajo | medido el 07-10-2026 |
| Las órdenes con rutas de dentro del contenedor —`/app/scripts/seed_data.py`— fallan en **Git Bash** con `can't open file '/app/C:/Program Files/Git/app/…'` | Es del shell, no del sistema: Git Bash traduce lo que empieza por `/` a una ruta de Windows. En PowerShell y en `cmd` funcionan tal cual; en Git Bash, con `MSYS_NO_PATHCONV=1` delante | medido el 07-10-2026 |
| La contraseña `PluriOne2026!` está **en el README** | Es la de desarrollo de `seed_data.py`, documentada desde el principio; en un entorno endurecido el sembrado genera una aleatoria. Es la única excepción a «nunca secretos en el árbol» | `AGENTS.md` §5 |
| Hay **56 puntos anotados** de deuda menor, 40 abiertos | Están anotados **a propósito**: desde la congelación, lo que no impide levantar la pila ni enseñar la demostración se escribe en lugar de arreglarse. Esa lista es parte del entregable | §6.4 |

Dos listas más largas que esta tabla, y que son la autoridad:

* **[`Congelacion_y_Trabajo_Futuro.md`](Congelacion_y_Trabajo_Futuro.md) §6.4** — los 56 restos
  menores, con su origen y las 16 tachaduras de los que se cerraron después.
* **El mismo documento, §7 — «Lo que no se va a hacer, y por qué».** Trece decisiones que no
  están pendientes: están decididas. Si una incidencia propone algo de esa tabla, ya tiene
  respuesta escrita.

---

## 5. Lo que el repositorio no trae, y es a propósito

| Qué falta | Por qué | Cómo se repone |
| :--- | :--- | :--- |
| `ml_pipeline/models/lead_scorer_model.joblib` | *pickle* ejecuta código al cargar; un binario versionado es procedencia desconocida | `python ml_pipeline/src/train_model.py` |
| Cualquier `.env` y la base de datos | En la Fase 0 hubo que rotar una clave que había viajado dentro de la carpeta. El lanzador se **niega** a arrancar si encuentra un `.env` en el árbol | `python devops/pila.py iniciar` crea `~/.plurione/pila.env` con los secretos generados |
| `docs/docs_residencias/` | Papeles institucionales con datos de personas y de la empresa: acuerdos, cartas, el informe en `.docx`. No son parte del sistema | No se repone. Los documentos del repositorio no dependen de ellos |
| `ml_pipeline/data/leads_reales*` | Es el único archivo del proyecto con desenlaces de prospectos concretos. Vive en el **mismo** directorio que el CSV sintético, y esa vecindad es lo que hace probable el descuido | `feedback_dataset.py`, cuando haya desenlaces reales |
| `frontend/dist/` | Se compila. El CI lo compila una vez y construye la imagen con `--target desde-artefacto` para no compilar dos veces y servir un bundle distinto del que pasaron las pruebas | `npm run build`, o el destino por omisión del Dockerfile |

---

## 6. Dónde está escrito el resto

| Si busca… | Lea |
| :--- | :--- |
| Las reglas de este repositorio antes de tocar nada | [`AGENTS.md`](../AGENTS.md) |
| Qué está congelado, qué queda abierto y qué no se va a hacer | [`Congelacion_y_Trabajo_Futuro.md`](Congelacion_y_Trabajo_Futuro.md) |
| Los 44 reportes de capítulo compilados, con portada e índice | [`Memoria_Tecnica_Final_Lead_Scoring.md`](Memoria_Tecnica_Final_Lead_Scoring.md) |
| Cómo se enseña el sistema, paso a paso y con tiempos | [`Guion_Cronometrado_de_la_Demo.md`](Guion_Cronometrado_de_la_Demo.md) |
| Qué hacer cuando algo falla, sin programar | [`Si_Algo_Falla.md`](Si_Algo_Falla.md) |
| Dónde se pone la dirección pública de la empresa | [`Poner_la_Direccion_de_la_Empresa.md`](Poner_la_Direccion_de_la_Empresa.md) |
| Las preguntas de la defensa, con su respuesta | [`GUIA_DEFENSA_ORAL.md`](GUIA_DEFENSA_ORAL.md) |

**Numeración, por si un índice parece roto:** el reporte va **dos** por detrás del capítulo —el
Reporte 44 es el capítulo 46—, y los capítulos 29 y 31 no escribieron reporte propio. Está
explicado en `docs/compile_reports.py` en lugar de renumerar cuarenta y cuatro ficheros.
