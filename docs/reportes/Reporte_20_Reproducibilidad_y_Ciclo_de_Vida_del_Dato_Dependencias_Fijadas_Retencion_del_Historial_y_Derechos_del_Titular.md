# Capítulo 20: Reproducibilidad y Ciclo de Vida del Dato — Dependencias Fijadas, Retención del Historial y Derechos del Titular

## 20.1. Por qué existe esta fase

La hoja de ruta que abre esta fase la llama «Reproducibilidad y ciclo de vida del dato» y
le asigna tres riesgos:

| Riesgo | Enunciado | Sección |
| :--- | :--- | :--- |
| **R-2** | Las dependencias se declaran por rangos: lo que se instala depende del día | §20.2 |
| **R-3** | `score_histories` crece sin límite y sin política de conservación | §20.3 |
| **R-11** | No hay forma de entregar ni de suprimir lo que el sistema sabe de una persona | §20.4 |

Parecen tres temas distintos y son el mismo defecto visto desde tres sitios: **el sistema no
podía decir qué tenía**. No qué versiones llevaba instalado, porque dependía de lo que
sirviera el índice de paquetes ese día. No cuánto guardaba de cada persona ni hasta cuándo,
porque nada lo decidía. Y no qué sabía de alguien concreto, porque esa información estaba
repartida en seis tablas y en el texto libre de la bitácora.

La política de retención que pide la hoja de ruta está en §20.5, escrita como tabla: qué se
guarda, dónde, cuánto tiempo, con qué mecanismo y en qué estado está ese mecanismo. Incluye
las filas en las que la respuesta es «ninguno todavía».

Esta fase encontró además dos defectos que no le correspondían y que tienen una raíz común
con R-2: definiciones que nunca se habían ejecutado (§20.2, al final).

---

## 20.2. R-2 — Lo que se instala es lo que está escrito

### El estado de partida

`backend/requirements.txt` declaraba rangos: `fastapi>=0.110.0,<1.0.0`,
`scikit-learn>=1.4.1.post1`, `numpy>=1.26.4`. Los rangos son la forma correcta de decir qué
versiones son **aceptables**, y la incorrecta de decir cuáles se **instalan**. Con ellos:

* **La imagen** ejecutaba `pip install --upgrade pip && pip install -r requirements.txt`.
  Dos construcciones separadas por un mes llevaban versiones distintas, y la primera orden
  —actualizar pip— era una descarga sin versión ni huella en la etapa que construye todo lo
  demás.
* **El CI** instalaba `ruff` y `pip-audit` con un `pip install` a secas. Una regla nueva de
  ruff publicada un martes podía poner el pipeline en rojo sin que nadie hubiera tocado el
  código.
* **`pip-audit` auditaba los rangos.** `pip-audit --requirement requirements.txt` resuelve
  versiones en el momento de auditar; esas versiones no tenían por qué ser las que llevaba
  la imagen construida una hora antes. La auditoría podía salir verde sobre paquetes que no
  estaban desplegados.
* **El entorno de desarrollo** divergía. El día que se generó el lock, el entorno local de
  trabajo difería en **11 de 93 paquetes**: `scikit-learn` 1.9.0 frente a 1.9.1, `numpy`
  2.5.2 frente a 2.5.3, `alembic`, `anyio`, `psycopg2-binary`, `ruff`, `wrapt`… La suite
  pasaba, pero pasaba sobre otras versiones que la imagen.

### Los locks

Dos ficheros nuevos, generados con `uv pip compile`:

| Fichero | Paquetes | Uso |
| :--- | ---: | :--- |
| `backend/requirements.lock` | 58 | La imagen, las migraciones |
| `backend/requirements-dev.lock` | 91 | La suite, el entrenamiento, `ruff`, `pip-audit` |

Cada entrada lleva versión exacta y la huella SHA-256 de **cada** fichero publicado para esa
versión. Con `pip install --require-hashes`, pip rechaza cualquier paquete —dependencias
transitivas incluidas— que no esté en el lock o cuyo fichero no coincida byte a byte.

Tres decisiones de cómo se generan:

**`--universal`, no `pip-compile`.** El lock se generó en Windows y la imagen es Linux. Un
`pip-compile` resuelve para la plataforma donde corre: el lock no llevaría `uvloop` —que
`uvicorn[standard]` solo pide fuera de Windows— y sí `tzdata` y `colorama`, que solo se piden
en Windows. `--universal` resuelve para todas a la vez y deja los marcadores escritos
(`uvloop==0.22.1 ; sys_platform != 'win32'`). Se comprobó instalando el lock de producción
para `x86_64-manylinux_2_28` desde Windows: `uvloop` entra, `tzdata` no.

**El de desarrollo, con el de producción como restricción** (`-c requirements.lock`). Sin
eso, resolver `pytest` o `pip-audit` podía mover una dependencia compartida, y la suite
volvería a correr sobre un FastAPI distinto del de la imagen. La suite compara las dos
listas: cada paquete de producción está en desarrollo con la misma versión y las mismas
huellas.

**Sin comprobación de frescura en CI.** Regenerar el lock en cada ejecución y compararlo
fallaría cada vez que PyPI publique una rueda nueva para una versión ya fijada —por ejemplo,
para una versión nueva de Python—, sin que nada hubiera cambiado aquí. Lo que se comprueba es
la **coherencia**: que el lock satisfaga los rangos del `.txt`, que no le falten huellas y que
el de desarrollo contenga al de producción.

### `xgboost`: lo primero que enseñó el lock

Escribir por primera vez la lista completa de lo que se instalaba dejó a la vista una línea:
`nvidia-nccl-cu13==2.31.2 ; sys_platform == 'linux'`. Es una biblioteca de comunicación
entre GPU, y la traía `xgboost` 3.x.

`xgboost` estaba en `requirements.txt` desde el capítulo 5. No lo importa ninguna línea de
código: el modelo es un `GradientBoostingClassifier` de scikit-learn, el artefacto no
contiene referencias a él y la única mención es una cadena de documentación. Se quitó. Las
dos ruedas que dejan de entrar en la imagen Linux suman **310 MB comprimidos**
(`xgboost` 57.6 MB, `nvidia-nccl-cu13` 252.4 MB), en una imagen sin GPU.

### Instalar y auditar lo instalado

| Dónde | Antes | Ahora |
| :--- | :--- | :--- |
| Imagen del backend | `pip install --upgrade pip && pip install -r requirements.txt` | `pip install --require-hashes -r requirements.lock` |
| CI: estilo, modelo, pruebas, migraciones | `pip install` de rangos o de nombres sueltos | `pip install --require-hashes -r backend/requirements*.lock` |
| CI: `pip-audit` | `--requirement requirements.txt` (rangos) | la lista de **lo instalado**, con `--no-deps --disable-pip` |
| Imagen construida | nada | se comprueba **dentro** del contenedor y se audita esa lista |

La pieza nueva es `scripts/comprobar_instalado.py`. Compara el entorno de Python que lo
ejecuta con un lock: cada paquete cuyo marcador aplica a esa plataforma tiene que estar en
esa versión exacta, y **no puede haber nada instalado que el lock no mencione** —un paquete
que entró por otro camino es código que nadie fijó ni auditó—. Con `--listar` escribe lo
instalado como `nombre==versión`.

En el trabajo de imágenes el guion se ejecuta dentro del contenedor, montado en solo lectura.
Evaluar los marcadores en el runner diría qué le tocaría a Ubuntu, no qué tiene la imagen.
Después se audita la lista que devuelve, y antes se exige que no esté vacía: la primera vez
que se ensayó en local, la imagen no llegó a construirse, la lista salió vacía y `pip-audit`
respondió «No known vulnerabilities found». Sobre cero paquetes, esa frase también es cierta.

### Una excepción, y solo una

Con la lista real —57 paquetes dentro de la imagen— `pip-audit` encontró un aviso:
**PYSEC-2026-1325** en `ecdsa` 0.19.2, que llega como dependencia de `python-jose`. Es un ataque
de temporización (Minerva) sobre la curva P-256 que permite, midiendo el tiempo de muchas
firmas, recuperar la clave privada. Afecta a **firmar** y a generar claves ECDSA; verificar no
está afectado. El proyecto `python-ecdsa` considera los canales laterales fuera de su alcance y
no tiene arreglo previsto.

No es un aviso de esta fase. Auditar los rangos de `requirements.txt`, como hacía el CI, lo
encuentra igual: el trabajo de dependencias llevaba en rojo desde que se publicó el aviso, y
nadie lo había visto porque no consta que ese trabajo haya corrido.

La aplicación firma sus tokens con **HMAC**. `python-jose` solo recurre a `ecdsa` para los
algoritmos ES*. Así que se ignora ese aviso, y solo ese, con tres condiciones que se comprueban
en lugar de suponerse:

1. **La aplicación no puede firmar con ECDSA.** Hasta ahora `JWT_ALGORITHM` aceptaba cualquier
   valor por variable de entorno; ahora solo admite HS256, HS384 y HS512, y con otro valor la
   aplicación no arranca. Sin este cambio la excepción habría sido cierta por configuración y
   no por construcción.
2. **Ningún módulo importa `ecdsa`** directamente.
3. **La excepción sigue haciendo falta y es la única.** Si `ecdsa` desaparece del lock, la
   prueba pide retirar la excepción; si en el CI aparece otro `--ignore-vuln`, la prueba y la
   guarda fallan hasta que alguien lo escriba y lo defienda.

### El artefacto, del mismo entorno

Fijar las dependencias no sirve si el modelo que se despliega salió de otro entorno. El
`.joblib` es un pickle de objetos de scikit-learn: cargarlo con otra versión produce un
aviso y, entre versiones menores, puede producir predicciones distintas sin ningún error. El
artefacto versionado se había entrenado con scikit-learn **1.9.0**; el lock fija **1.9.1**.

El registro de modelos no guardaba con qué versiones se entrenaba cada artefacto. Ahora cada
entrada lleva `entorno` —Python, scikit-learn, numpy, pandas y joblib— y la suite exige que
la publicación correspondiente al artefacto versionado coincida con el lock. La prueba se
escribió antes de reentrenar y falló como debía: `scikit-learn None`, porque la entrada
anterior no tenía el campo.

El modelo se reentrenó en un entorno instalado exclusivamente desde el lock:

| | Antes | Después |
| :--- | :--- | :--- |
| Artefacto | `0a2632a2…` | `372d843e…` |
| scikit-learn | 1.9.0 (no registrado) | 1.9.1 (registrado) |
| ROC-AUC | 0.952394 | 0.952394 |
| IC 95 % | [0.9354, 0.9681] | [0.9354, 0.9681] |
| Huella de los datos | `cd42cf4f…` | `cd42cf4f…` |

Las cifras son idénticas y la huella del fichero no. Que las métricas no cambien con la
versión menor es lo esperable; que el fichero sí cambie es lo que justifica registrar el
entorno. El perfil de referencia del monitor de deriva quedó atado al artefacto nuevo
(capítulo 19).

El primer intento de ese entorno se hizo en la carpeta temporal del sistema y salió
incompleto: a `pip` le faltaba un módulo interno y, en un intento posterior, a `joblib` otro.
Algo en esa carpeta retiraba ficheros durante la instalación. El entorno definitivo se
instaló fuera de ella, y antes de entrenar se comprobó que existían los **9 925 ficheros**
que declaran los `RECORD` de sus paquetes. Un entorno «instalado desde el lock» que no
contiene lo que el lock instala no es una comprobación de nada.

### Dos defectos que no eran de esta fase

Verificar de verdad —construir la imagen, revertir las migraciones contra PostgreSQL— sacó
dos defectos anteriores, los dos silenciosos:

**La imagen del backend no se construía desde la Fase 12.** El `Dockerfile` copia
`ml_pipeline/src/feedback_dataset.py` para que el extractor del bucle viaje en la imagen
(capítulo 18), pero `.dockerignore` excluye `ml_pipeline/src/` y solo readmitía
`drift_monitor.py` y `model_registry.py`. `docker build` fallaba con
`"/ml_pipeline/src/feedback_dataset.py": not found`. Se añadió la excepción, y una prueba que
recorre cada `COPY` del `Dockerfile` y comprueba contra `.dockerignore` que su origen llega al
contexto de construcción. Esa prueba habría detectado el defecto el día que se introdujo, e
impide también que el lock quede fuera.

**Revertir las migraciones fallaba en PostgreSQL.** La reversión de `a23deac578cf` (identidad
unificada, capítulo 15) recreaba la tabla `sales_reps` con `sa.DATETIME()`, el tipo de SQLite
con el que se autogeneró; en PostgreSQL no existe: `type "datetime" does not exist`. Se
comprobó que fallaba igual sin la migración de esta fase y se corrigió con
`DateTime(timezone=True)`, que además es el tipo que tenía la tabla en la revisión a la que se
vuelve.

Los dos tenían la misma causa que R-2: **una definición que nadie había ejecutado**. El
pipeline declara un paso que construye la imagen y otro que revierte las migraciones dos
veces, y los dos habrían fallado. En esta máquina el proyecto no está bajo control de
versiones, y no consta que el workflow haya corrido sobre este árbol. Escribir el paso no es
lo mismo que haberlo visto pasar.

---

## 20.3. R-3 — El historial tiene plazo

### El estado de partida

`score_histories` recibe una fila por cada recálculo: al crear el prospecto, con cada
actividad, al editarlo y en cada recálculo masivo. Cada fila lleva el vector de variables del
momento (`feature_snapshot`) y la explicación generada. Nada la recortaba: crecía de forma
lineal con la actividad comercial, sin techo, y el detalle de un prospecto que dejó de
interesar hace años seguía ahí igual que el primer día.

El requisito de partida, RNF-05, decía «registro histórico **inmutable**». Esa palabra se
leía como «para siempre», y nadie había decidido que lo fuera.

La hoja de ruta pedía también un índice por `(lead_id, calculated_at)`. **Ya existía** desde la
migración de base: `idx_score_history_lead_time`. No se volvió a crear —dos índices idénticos
cuestan en cada inserción y no aportan nada—; se añadió una prueba que impide que desaparezca.

### La regla

Se conserva el detalle de los últimos `SCORE_HISTORY_RETENTION_MONTHS` **meses completos**
más el mes en curso. Por defecto 12; con menos de 3 la aplicación no arranca y el guion de
purga sale con código 2. Lo anterior se agrega a una tabla nueva, `score_history_monthly`,
con una fila por prospecto y mes, y se borra en la misma transacción.

| Guarda el resumen | No guarda |
| :--- | :--- |
| Número de puntuaciones, **suma**, mínimo y máximo | El vector de variables de cada instante |
| Primera y última puntuación del mes, con su instante | La explicación generada |
| Cuántas veces estuvo en cada categoría | El desglose de reglas |
| Con qué versiones de modelo se puntuó | |

**El corte se alinea al primer día del mes.** Con un corte a «hoy menos doce meses», cada
pasada diaria agregaría un día más del mismo mes y el resumen se reescribiría treinta veces.
Alineado, un mes se agrega de una vez, cuando vence entero.

**Se guarda la suma y no la media.** Si un mes se agrega en dos pasadas —una fila que llega
tarde, una purga interrumpida—, dos medias no se pueden combinar sin saber cuántas filas
había detrás de cada una; dos sumas sí. La suite lo prueba con una fila que llega después de
que su mes ya esté resumido: el resumen se **fusiona**, no se duplica, y el índice único sobre
`(lead_id, month)` impide lo segundo aunque el código fallara.

### Lo que no se purga nunca

Dos filas por prospecto sobreviven a cualquier plazo.

**La instantánea de entrada.** El bucle de realimentación del capítulo 18 entrena con la
**primera** instantánea de cada prospecto que llega a un desenlace: la del momento en que entró
al embudo, antes de que el avance comercial la contaminara. Una purga ingenua la borraría a
los doce meses, y el ciclo de venta de un cliente corporativo puede ser más largo.

Borrarla **no produciría ningún error**. El extractor tomaría como «de entrada» la siguiente
instantánea que quedara —ya con reunión agendada o propuesta enviada— y el reentrenamiento
aprendería con fuga de información: exactamente el error que el capítulo 18 construyó el
bucle para no cometer, reintroducido por una tarea de mantenimiento.

Para que la purga y el extractor no puedan discrepar sobre cuál es esa fila, el criterio es
**una sola función**, `consulta_instantanea_de_entrada`, que vive en el backend y el extractor
importa. La purga usa una versión por lotes —dos consultas para doscientos prospectos en
lugar de cuatrocientas—, y la suite comprueba que elige las mismas filas que la de uno en uno,
con empates de instante incluidos, que es donde dos formas de ordenar discrepan. El caso que
se prueba es el que motivó la regla: filas antiguas **sin** instantánea delante de la de
entrada real. La purga se lleva la más antigua de todas y deja la de entrada, que no es la
primera fila sino la primera con vector.

**La puntuación vigente.** La ficha del prospecto muestra la explicación de su última
puntuación. Un prospecto sin actividad en un año sigue teniendo un score, y ese score tiene
que poder explicarse.

### Dos purgas a la vez

La pila despliega un solo servicio de purga, pero eso es una convención, no una garantía. Si
dos pasadas agregaran el mismo lote, el resumen contaría dos veces las mismas filas.

Por eso la purga **borra antes de sumar** y compara cuántas filas borró con cuántas había
leído. Si otra transacción se llevó alguna entre medias, el lote se deshace entero y se deja
para la pasada siguiente: se resume exactamente lo que esta transacción borró. La suite lo
provoca borrando una fila del lote entre la lectura y el borrado.

Y la paginación es **por clave** (`lead_id` creciente), no por desplazamiento: al borrar
mientras se pagina, un `OFFSET` se saltaría prospectos, porque la página siguiente se calcula
sobre un conjunto que ya encogió.

### Programada, y con constancia

`backend/scripts/retencion_historial.py` ejecuta la purga; `--simular` cuenta lo que haría sin
escribir; `--cada N` la repite. En la pila corre como el servicio `retencion-historial`, con la
misma imagen que el backend, una pasada al día, en solo lectura y sin capacidades. Es un
servicio aparte y no una tarea dentro del backend: con varios workers de uvicorn, una tarea
programada en el proceso correría una vez por worker.

Cada pasada real deja un asiento en la bitácora (`historial.retencion`, sin actor) con el
corte, las filas resumidas, las protegidas y los lotes descartados. La simulación no se
anota: la bitácora dice lo que pasó, no lo que se consultó que pasaría. En modo servicio, un
fallo de una pasada se informa y se reintenta al día siguiente; un plazo inválido termina el
proceso, porque repetirlo cada día no lo arregla y un contenedor que se reinicia en bucle se
ve.

### Contra PostgreSQL

Todo lo anterior está probado sobre SQLite en memoria, que es donde corre la suite. Se repitió
contra PostgreSQL 16 real, sobre el esquema migrado:

| Comprobación | Resultado |
| :--- | :--- |
| Subir desde la revisión anterior, en una ejecución aparte | Correcto |
| `alembic check` tras subir | Sin diferencias |
| Bajar una revisión: el tipo `scorecategory`, que comparten tres tablas | Sobrevive |
| Ciclo completo base → head, dos veces | 7 reversiones y 7 migraciones por vuelta |
| Columnas temporales sin zona | 0 |
| Purga: prospecto con fila sin vector, entrada, empate y vigente | 4 filas resumidas en 3 meses; la entrada se conserva |
| Segunda pasada | 0 filas |

El tipo enumerado merece una línea. Tal como la genera `--autogenerate`, la columna
`last_category` declara un `sa.Enum` con nombre `scorecategory`, y en PostgreSQL eso emite
`CREATE TYPE` al subir —falla, porque el tipo existe— y `DROP TYPE` al bajar —se lo quita a
`leads` y a `score_histories`—. En el CI ninguna de las dos cosas se habría visto: allí se sube
desde cero en una sola ejecución, y el tipo se crea una vez. La migración declara la variante
de PostgreSQL con `create_type=False`.

---

## 20.4. R-11 — Lo que el sistema sabe de una persona

### El estado de partida

Un prospecto es una persona con nombre, correo, teléfono, cargo y empresa. El sistema guarda
además qué páginas vio, qué correos abrió, cómo se la puntuó en cada momento y por qué.

* **No había forma de responder «¿qué sabéis de mí?»** sin abrir la base a mano.
* **El borrado dejaba cosas atrás.** `DELETE /leads/{id}` seguía las cascadas del ORM, que
  llegan a actividades, historial y registros CRM vinculados, pero no a:
  * las **entregas de webhook**, cuya clave foránea es `SET NULL`: la fila se quedaba, sin
    prospecto y con la respuesta original dentro;
  * los **registros de ingesta revertida**, que no tienen `lead_id` porque el alta no llegó a
    existir, y guardan la carga completa del CRM, correo incluido;
  * **la bitácora**: el asiento de `lead.crear` anotaba el correo y la empresa, y el asiento
    del propio borrado **también el correo**, a propósito, desde el capítulo 14.
* **El registro de texto del servidor** escribía el correo del prospecto en dos líneas —el alta
  y la asignación automática—. Ese registro rota, pero no se puede editar después.

### Exportar

`GET /api/v1/leads/{id}/exportar` devuelve un documento JSON (`plurione.titular/1`) como
adjunto y con `Cache-Control: no-store`:

| Sección | Contenido |
| :--- | :--- |
| `datos_del_prospecto` | Todas las columnas de la ficha |
| `campana`, `asesor_asignado` | La relación con esta persona; del asesor, nombre y no correo |
| `actividades`, `historial_de_puntuacion`, `resumen_mensual_de_puntuacion`, `integraciones_crm`, `entregas_de_webhook` | Todas las filas, todas las columnas |
| `integraciones_crm_sin_vincular` | Ingestas revertidas con su correo |
| `tratamientos_registrados` | Qué se hizo con sus datos y cuándo, por rol |
| `conservacion` | Cuánto tiempo se guarda cada cosa |
| `fuera_de_la_base` | Copias de seguridad, conjuntos de entrenamiento, sistema de origen |

Tres decisiones:

**Las columnas no se listan a mano.** Se exportan todas las del modelo, y la suite compara las
claves exportadas con las del modelo tabla por tabla: una columna nueva sale en la exportación
el mismo día que se crea.

**Los datos de los empleados no se entregan.** Quién atendió o dio de alta a la persona se da
por rol. El correo, la IP y el navegador del empleado son datos personales del empleado.

**Lo que el sistema no alcanza, se dice.** Una respuesta de acceso que calla que existen copias
de seguridad o un CSV de entrenamiento no responde a la pregunta.

La exportación la tramitan `Sales_Lead` y `System_Admin`, los mismos roles que la supresión, y
queda en la bitácora con cuántos registros se entregaron de cada sección, nunca su contenido.

### Suprimir

`DELETE /api/v1/leads/{id}` pasa por `suprimir_prospecto`, que en **una transacción** borra lo
que cuelga del prospecto, las ingestas sin vincular que llevan su correo, retira sus datos de
la bitácora y borra la ficha. Si algo falla a mitad, no se borra nada; la suite lo provoca.

Exportar y suprimir recorren **el mismo mapa** de tablas, `TABLAS_DEL_PROSPECTO`, y la suite lo
compara con las claves foráneas reales del esquema. Así se vio que `score_history_monthly`
tenía que entrar el mismo día que se creó, y así se verá la próxima tabla: una tabla nueva que
apunte a `leads` rompe las pruebas hasta que alguien decida qué hacer con ella.

La prueba que sostiene la supresión no mira las tablas conocidas. **Recorre todas las filas de
todas las tablas buscando el correo** de la persona, después de haberlo sembrado en cada rincón
donde el sistema guarda algo. Lo que hay que demostrar no es que las tablas previstas queden
vacías, sino que el dato no está en ninguna parte.

Las ingestas sin vincular se buscan en dos pasos: un `LIKE` sobre el JSON como texto, para no
leer la tabla entera, y una comparación **exacta** sobre los valores, para no llevarse a
`diana.titular@…` al buscar a `ana.titular@…`. El escenario de la suite incluye esa trampa.

### La bitácora: los hechos se quedan, los datos se van

La bitácora no se borra. Quién dio de alta a esta persona, quién la editó y cuándo sigue siendo
cierto después de suprimirla, y es justo lo que se consulta cuando se investiga qué pasó. Lo que
se retira es el dato personal que los asientos llevaban dentro: los valores que contienen su
correo, su nombre completo, su teléfono o su empresa pasan a `[suprimido]`. El asiento, su
autor, su rol y su fecha no cambian, y la suite lo comprueba campo a campo.

**El asiento del borrado ya no guarda el correo**, y es un cambio de criterio respecto al
capítulo 14, que lo anotaba para que el asiento no fuera «solo un número» cuando alguien
preguntara qué se perdió. El argumento era bueno y la conclusión no: guardar el correo de quien
pidió ser borrado era no borrarlo. El asiento guarda ahora cuántas filas salieron de cada tabla
y una **huella con clave** del correo: HMAC-SHA256 con la clave del servidor.

Con clave y no un SHA-256 a secas. Sin clave, cualquiera con una lista de correos —el propio
CRM, sin ir más lejos— recorrería la bitácora y sabría quién pidió que lo borraran. Con clave,
solo quien opera el sistema puede comprobar si una persona concreta fue suprimida. Rotar
`SECRET_KEY` deja las huellas anteriores sin forma de comprobarse, un efecto aceptable para un
registro de supresiones.

Las dos líneas del registro de texto que escribían el correo del prospecto lo escriben ahora
por identificador.

Contra PostgreSQL: tras exportar y suprimir un prospecto sembrado en todas las tablas, el
recorrido completo de la base no encontró su correo en ninguna fila, y el tipo `scorecategory`
seguía existiendo.

---

## 20.5. Política de conservación y tratamiento

Lo que sigue es la política tal como el sistema la **aplica hoy**, no como convendría que
fuera. Donde no hay mecanismo se dice. Los plazos son decisiones técnicas razonadas y
provisionales: fijarlos corresponde a quien responda del tratamiento de datos en la empresa.

| Dato | Dónde | Datos personales | Conservación | Mecanismo | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Ficha del prospecto | `leads` | Sí | Mientras exista la relación comercial | Supresión bajo petición | **Sin caducidad automática** |
| Actividades | `lead_activities` | Sí, de comportamiento | Igual que la ficha | Supresión | Sin caducidad automática |
| Historial detallado de puntuación | `score_histories` | Sí: vector y explicación | 12 meses completos + mes en curso; entrada y vigente, siempre | `retencion-historial`, diario | **Aplicado** |
| Resumen mensual | `score_history_monthly` | Seudónimo: identificador y cifras | Igual que la ficha | Supresión | Aplicado |
| Registros de integración CRM | `crm_integration_logs` | Sí: correo, nombre y empresa; sin texto de mensajes desde la Fase 15 | 90 días desde la sincronización (`CONSERVACION_REGISTROS_CRM_DIAS`, mínimo 30) | `retencion-historial`, diario; supresión, vinculados y sin vincular | **Aplicado** (capítulo 22) |
| Bandeja «Sin asociar» | `unmatched_events` | Sí: correo, teléfono y nombre de quien aún no es prospecto | 90 días desde que llegó el aviso (`CONSERVACION_SIN_ASOCIAR_DIAS`, mínimo 30) | `retencion-historial`, diario; supresión con la ficha | **Aplicado** (capítulo 22) |
| Entregas de webhook | `webhook_deliveries` | Respuesta con datos | Ventana antirrepetición (15 min) | Purga en cada ingesta | Aplicado |
| Bitácora | `audit_log` | De empleados; del prospecto, hasta su supresión | Sin plazo en la aplicación | Fuera de la aplicación (capítulo 14); datos del titular retirados al suprimir | Decisión de operación |
| Sesiones | `refresh_tokens` | IP del empleado | 30 días después de caducar (`CONSERVACION_SESIONES_DIAS`, mínimo 7) | `purgar_tokens_caducados`, desde la pasada diaria de `retencion-historial` | **Aplicado** (capítulo 22) |
| Trabajos de recálculo | `scoring_jobs` | Correo del empleado que lo pidió | 90 días desde que terminó; los vivos no caducan (`CONSERVACION_TRABAJOS_DIAS`, mínimo 7) | `retencion-historial`, diario | **Aplicado** (capítulo 22) |
| Copias de seguridad | volumen `pgrespaldos` | Todo | `RETENCION_DIAS`, 14 por defecto | `respaldo.sh` (capítulo 16) | Aplicado; una supresión persiste en ellas hasta 14 días |
| Registro de texto de los contenedores | `json-file` de Docker | De empleados; del prospecto, ya no | 3 × 10 MB por servicio | Rotación de Docker | Aplicado |
| Conjunto de realimentación | `ml_pipeline/data/leads_reales*` | Sí | Fuera de la base | Excluido del control de versiones (capítulo 18) | **Sin mecanismo** |
| Artefacto del modelo | `.joblib` | No contiene filas individuales | Registro de modelos | — | — |

> **Nota (capítulo 21).** Desde la Fase 15 las actividades llevan procedencia y no guardan el
> texto de ningún mensaje, y `crm_integration_logs` ya no conserva la carga completa: pasa
> por la misma minimización que las actividades. Hay además una fila que esta tabla no tenía:
> la bandeja «Sin asociar» (`unmatched_events`), con correo, teléfono y nombre de personas
> que todavía no son prospecto. Se exporta y se suprime con la ficha a la que corresponde,
> y **no tiene caducidad automática**.

> **Nota (capítulo 22).** La tabla está actualizada a lo que el sistema aplica desde el
> capítulo 22. Sesiones, trabajos de recálculo, registros CRM y la bandeja «Sin asociar» tienen
> plazo en días, con mínimo, y los aplica la misma pasada diaria que resume el historial, con un
> asiento por plazo en la bitácora. Los plazos siguen siendo técnicos y provisionales.

Leída de arriba abajo, la tabla dice tres cosas. Que el dato que más crecía —el historial—
tiene ahora plazo y mecanismo. Que una persona puede ejercer acceso y supresión, y que la
supresión alcanza todo lo que está en la base. Y que al cerrar esta fase **cuatro filas no
tenían mecanismo**: los registros CRM, las sesiones, los trabajos de recálculo y el CSV de
realimentación. Se escribieron aquí para que no se leyeran como resueltas. Las tres primeras lo
tienen desde el capítulo 22; el CSV de realimentación sigue sin él.

En términos de la legislación mexicana de protección de datos, esta fase da soporte técnico a
dos de los derechos ARCO: **acceso** y **cancelación**. La **rectificación** ya existía
(`PUT /leads/{id}`). La **oposición** a un tratamiento concreto —por ejemplo, a entrar en el
conjunto de entrenamiento— no está modelada. Nada de esto es una valoración jurídica.

---

## 20.6. Que nada de esto sea decorativo

### Las pruebas

Se reintrodujeron **32 defectos**, uno a uno, ejecutando con cada uno solo las pruebas de
su pieza: **32 los detectan**, con 58 fallos en total.

| Pieza | Defectos reintroducidos |
| :--- | :--- |
| Retención | corte no alineado al mes; plazo mínimo ignorado al arrancar y en el guion; entrada sin proteger; vigente sin proteger; desempate distinto del extractor; fusionar sobrescribiendo; resumir lo leído y no lo borrado; simular escribiendo; paginación que se salta prospectos; el guion anota simulaciones; un fallo detiene el servicio; el extractor vuelve a elegir por su cuenta |
| Derechos del titular | el mapa pierde una tabla; ingestas sin vincular no suprimidas; suprimir a quien solo se parece; la bitácora conserva los datos; supresión no atómica; el asiento vuelve a guardar el correo; una columna sin exportar; el correo del empleado exportado; un asesor exporta; la exportación cacheable; huella sin clave |
| Dependencias | la imagen instala desde rangos; el `.dockerignore` vuelve a excluir el extractor; la comparación no ve lo que sobra; un rango en el lock; marcadores sin evaluar; un `pip install` suelto en CI; la aplicación admite firmar con ECDSA; se ignora un aviso más de `pip-audit` |

El registro del entorno de entrenamiento no está en la tabla porque reintroducirlo exige
reentrenar; su prueba se vio fallar antes del reentrenamiento, con el artefacto real (§20.2).

### Las guardas del pipeline

Cuatro guardas —tres nuevas y una ampliada—, **17 reintroducciones, 17
disparos**, y las cuatro pasan sobre el árbol correcto. Como en el capítulo 19, el arnés exige que el fallo sea el
correcto, con la palabra `FALLO` en la salida, y esta vez copia cada archivo a disco antes de
tocarlo y restaura al arrancar lo que haya quedado. El arnés de pruebas del capítulo 19 murió
a mitad de una inyección y dejó el defecto dentro del código; se detectó al revisar las
fuentes antes de seguir, y se restauró.

| Guarda | Reintroducciones |
| :--- | :--- |
| Las dependencias se instalan desde el lock | la imagen desde `requirements.txt`; `pip install ruff` suelto; migraciones desde rangos; el lock fuera del contexto |
| Las dependencias y las imágenes se auditan (ampliada) | `pip-audit` sobre rangos; listar sin comparar en CI; listar sin comparar en la imagen; auditar una lista vacía; ignorar un aviso más |
| El historial de puntuación tiene plazo | purga sin programar; extractor con criterio propio; entrada y vigente sin proteger; resumir lo leído |
| La supresión alcanza todo | volver a las cascadas del ORM; el asiento guarda el correo; desaparece la exportación; el mapa pierde una tabla |

Al diseñar dos de esas reintroducciones se vio que **la primera versión de la guarda las habría
dejado pasar**, y se corrigió antes de ejecutar el arnés: buscaba el nombre del guion de
comprobación, y ese nombre aparece también en la orden que solo lista. Quitar la comparación
dejando el listado habría seguido en verde. Ahora exige la línea que compara.

---

## 20.7. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend, en el entorno instalado desde el lock | **673 pruebas**, 92 % de cobertura |
| Suite del backend, en el entorno local sin fijar | 673 pruebas, también en verde |
| Suite del cliente | **126 pruebas** |
| `ruff` / `eslint` | Sin avisos |
| Locks | 58 paquetes en producción, 91 en desarrollo; todos con versión exacta y huella |
| Entorno de desarrollo desde el lock | 90 paquetes aplicables en Windows, versiones exactas; 9 925 ficheros presentes |
| Imagen del backend | Se construye instalando desde el lock con `--require-hashes`; dentro, **57 paquetes idénticos al lock**, sin `xgboost`, `pip` ni `setuptools`; 825 MB (entorno virtual, 454 MB) |
| `pip-audit` sobre lo instalado en la imagen | Un aviso sin arreglo publicado (`ecdsa`, PYSEC-2026-1325), anterior a esta fase, ignorado con justificación comprobada |
| Extractor del bucle y guion de purga dentro de la imagen | Importan y arrancan |
| Artefacto del modelo | `372d843e…`, entrenado con scikit-learn 1.9.1; mismas métricas e intervalo |
| PostgreSQL 16 | Migración, reversión completa ×2, purga, exportación y supresión correctas |
| Integración continua | 10 trabajos, 107 pasos, 26 guardas en `configuracion-peligrosa` |
| Guardas | 4 guardas, 17 reintroducciones, 17 disparos |

---

## 20.8. Lo que esta fase no hizo

* **Cuatro datos siguen sin caducidad** (§20.5): registros CRM con la carga completa, sesiones
  —la función de purga existe y nada la invoca—, trabajos de recálculo y el CSV de
  realimentación. Los registros CRM son el más serio: guardan todo lo que envió el CRM, sin plazo.
  *Tres de los cuatro, cerrados en el capítulo 22 —sesiones, trabajos de recálculo y registros
  CRM, junto con la bandeja del capítulo 21—. El CSV de realimentación sigue sin mecanismo.*
* **Suprimir aquí no suprime en el CRM**, y una entrega posterior del CRM vuelve a crear a la
  persona. La huella con clave permitiría reconocerla y rechazar la ingesta, pero bloquear una
  entrada de negocio es una decisión que no corresponde a esta fase.
* **Las copias de seguridad conservan a la persona suprimida** hasta 14 días. No se editan
  volcados; está dicho en la propia exportación.
* **No hay interfaz** para exportar ni para explicar la supresión en el cliente: es API.
* **`python-jose` sigue arrastrando `ecdsa`.** La excepción de §20.2 está acotada y comprobada,
  pero la corrección de fondo es sustituir la biblioteca de JWT por una que no dependa de él.
  Es un cambio en la autenticación y merece su propia fase.
  *Cerrado en el capítulo 23: PyJWT sustituye a python-jose, salen del lock `ecdsa`, `rsa`,
  `pyasn1` y `cryptography`, y `pip-audit` audita sin ninguna excepción.*
* **Las imágenes base no están fijadas por huella.** `python:3.13-slim` y `postgres:16-alpine`
  se resuelven por etiqueta, y `anchore/syft:latest` en el CI también. Lo que instala pip es
  reproducible; la capa del sistema operativo, todavía no.
  *Cerrado en el capítulo 22: todas las imágenes de terceros —las bases, las de la pila y las
  herramientas del CI— van por huella, con renovación explícita (`scripts/renovar_imagenes.py`).*
* **El lock no se regenera solo.** Cuando se publique un aviso sobre una versión fijada,
  `pip-audit --strict` pondrá el pipeline en rojo y habrá que regenerar a mano. Es el
  comportamiento buscado: la alternativa es que el arreglo entre sin que nadie lo decida.
* **No hay valoración jurídica.** Los plazos de §20.5 son técnicos y provisionales, y la
  oposición al tratamiento no está modelada.
