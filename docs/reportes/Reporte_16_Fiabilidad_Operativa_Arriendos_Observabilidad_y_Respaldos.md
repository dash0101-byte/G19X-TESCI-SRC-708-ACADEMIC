# Capítulo 16: Fiabilidad Operativa — Arriendos, Observabilidad y Respaldos

## 16.1. Por qué existe esta fase

Los capítulos anteriores se ocuparon de que el sistema fuera **correcto**: que la identidad
se pruebe, que la sesión caduque, que nadie vea cartera ajena, que la ingesta no se repita.
Esta fase se ocupa de algo distinto y hasta ahora ausente: qué pasa cuando algo **se rompe**
o cuando hace falta **mirar por dentro**.

| Hallazgo | Enunciado | Naturaleza |
| :--- | :--- | :--- |
| **N-5** | Un recálculo cuyo proceso muere queda en `RUNNING` para siempre y bloquea a los demás | Un estado que nada obliga a caducar |
| **N-11** | El despliegue documentado no aplicaba las migraciones | Cerrado en el capítulo 14; aquí se documenta y se guarda |
| **N-12** | Los contenedores corren con los valores de fábrica de Docker | Ausencia de límites, no un fallo de código |
| **N-13** | No hay copias de seguridad, ni forma de saber si servirían | Una operación que no existe |
| **N-14** | Una línea de texto por evento, sin correlación, y ninguna métrica | Se puede diagnosticar, pero no medir |

Los cinco comparten una propiedad incómoda: **ninguno produce un error**. Un trabajo colgado
en `RUNNING` responde 200. Un contenedor sin techo de memoria funciona perfectamente hasta
el día que no. Un registro sin `request_id` se lee sin problema, renglón a renglón. Una copia
de seguridad que no se puede restaurar es un archivo con el tamaño correcto. Son defectos que
solo se manifiestan el día en que se necesita lo que no se hizo.

---

## 16.2. N-5 — Un estado que nadie obliga a caducar

### El defecto

`ScoringJob.status` decía qué se **pretendía** hacer, no qué estaba pasando:

```python
trabajo.status = JobStatus.RUNNING.value
trabajo.started_at = utc_now()
db.commit()
```

A partir de ahí, la fila afirma «se está ejecutando» hasta que alguien la cambie. Si el
contenedor muere a mitad del recorrido —un despliegue, un OOM, un `docker compose down`—
nadie la cambia nunca. La consecuencia tiene dos caras:

* quien consulta el estado ve `RUNNING` con un `processed_leads` congelado, y **no puede
  distinguir** «va despacio» de «lleva parado desde el martes»;
* el sistema, si algún día se le pusiera un control de concurrencia, creería que hay un
  recálculo vivo y rechazaría los siguientes indefinidamente.

Y no había tal control. Dos peticiones simultáneas lanzaban dos recorridos completos sobre
la misma tabla: no el doble de rápido, sino el doble de trabajo recalculando los mismos
prospectos, pisándose al escribir y multiplicando la carga de inferencia justo cuando la
base ya estaba ocupada. Basta con pulsar dos veces el botón.

### La corrección: un plazo que se renueva con el progreso

```python
lease_until = Column(DateTime(timezone=True), nullable=True)
heartbeat_at = Column(DateTime(timezone=True), nullable=True)
worker_id = Column(String(120), nullable=True)
lease_key = Column(String(40), nullable=True)
```

`lease_until` es el instante hasta el que el proceso que tomó el trabajo **afirma seguir
vivo**. Vencido y sin renovar, el trabajo se considera abandonado y cualquiera puede
cerrarlo. La distinción entre «murió» y «sigue trabajando» no la da un ping a nadie: la da
un plazo que solo se prolonga mientras haya progreso.

Y ahí está la decisión que importa. La señal de vida viaja **en el mismo commit que el
progreso**, dentro del bucle de lotes:

```python
trabajo.processed_leads = procesados
trabajo.failed_leads = fallidos
_renovar_arriendo(trabajo)
db.commit()
```

No en un hilo aparte con un temporizador. Un latido independiente seguiría diciendo «vivo»
aunque el bucle llevara media hora bloqueado en una consulta: mediría que el **proceso**
existe, no que el **trabajo** avanza, que es lo único que interesa saber. La prueba que
guarda esto no comprueba que se renueve, sino **cuántas veces**: seis prospectos en lotes
de dos deben producir cuatro renovaciones —una al arrancar y tres lotes—, y cada una con
más trabajo hecho que la anterior.

Un detalle que parece menor y no lo es: un trabajo con `lease_until` a `NULL` cuenta como
**vencido**, no como vigente. Las filas anteriores a la migración tienen esa columna vacía;
leer el `NULL` como «vigente para siempre» habría hecho que un trabajo viejo colgado
bloqueara el turno de forma permanente —exactamente el defecto que el arriendo viene a
cerrar, reintroducido por la propia migración—.

### El turno exclusivo: lo impone la base, no el `if`

La forma natural de escribir «uno a la vez» es:

```python
if hay_uno_activo(db):
    raise Conflicto()
db.add(trabajo_nuevo)
```

Y es una carrera. Entre la lectura y el `INSERT` caben dos peticiones; con dos workers de
uvicorn eso no es una hipótesis remota, es lo que ocurre cuando alguien pulsa dos veces.
Aquí el turno es una columna con **índice único** que vale `RECALCULATE_ALL` mientras el
trabajo está vivo y `NULL` en cuanto termina:

```python
Index("uq_scoring_jobs_lease_key", "lease_key", unique=True)
```

`NULL` no colisiona consigo mismo ni en PostgreSQL ni en SQLite, así que los trabajos
terminados no ocupan turno y no hace falta ningún barrido para liberarlo. La comprobación
previa se mantiene —sirve para dar un mensaje útil—, pero quien impide de verdad el segundo
recorrido es el motor, y el `IntegrityError` se traduce en el mismo 409.

La respuesta dice **cuál** es el trabajo que ocupa el turno:

```json
{"detail": {"mensaje": "Ya hay un recálculo masivo en curso…",
            "job_id": "trabajo-de-otro-worker", "estado": "RUNNING",
            "procesados": 340, "total": 5000,
            "solicitado_por": "lider.ventas@plurione.com"}}
```

Un «inténtelo más tarde» obliga a quien lo pidió a ir a buscar qué hay atascado. El
conflicto ya lo sabe.

### El barrido, y lo que deliberadamente no hace

Los arriendos vencidos se recogen en **dos** sitios, y los dos hacen falta:

* al arrancar la aplicación, para que un reinicio tras una caída no deje trabajos fantasma;
* **antes de crear uno nuevo**, porque si nadie reinicia nada, el barrido del arranque no
  vuelve a ocurrir y el turno quedaría ocupado por un muerto hasta la próxima vez que
  alguien reiniciara la pila.

Lo que el barrido **no** hace es cerrar los trabajos con arriendo vigente. Reiniciar un
worker no autoriza a dar por muerto lo que otra instancia pueda estar ejecutando. Es la
mitad que se olvida al implantar este patrón: un barrido que cierra todo lo que encuentra
en `RUNNING` mata recálculos sanos en cada despliegue.

---

## 16.3. N-14 — De renglones sueltos a eventos correlacionados

### El defecto

```python
logging.basicConfig(format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s")
```

Sirve mientras lo lee una persona en una terminal. Deja de servir en cuanto hay **dos
workers escribiendo sobre el mismo descriptor** y una traza multilínea partida entre ambos:
`grep` devuelve fragmentos, el nivel se busca por subcadena —«ERROR» aparece también dentro
de los mensajes— y no hay forma de reunir los cinco renglones que produjo *una* petición.

Y había algo peor, porque era una promesa incumplida. El manejador global de errores
devolvía al cliente un identificador para soporte:

```python
request_id = uuid.uuid4().hex
logger.error(f"[request_id={request_id}] Excepción no controlada …")
```

Ese identificador **se inventaba allí mismo**. No aparecía en ningún otro renglón del
registro. El dato que soporte pedía —«deme el request_id»— no llevaba a ninguna parte:
identificaba el mensaje que lo contenía y nada más.

### La corrección

Un objeto JSON por línea, y un `request_id` que viaja por `contextvars` y aparece en
**todos** los renglones que esa petición genere, incluidos los de librerías que no saben
nada de esto:

```json
{"ts": "2026-09-10T03:01:36.707+00:00", "nivel": "INFO", "logger": "uvicorn.access",
 "mensaje": "127.0.0.1:36030 - \"GET /health HTTP/1.1\" 200",
 "request_id": "c1dde3cc9f1c4e09b869b6bca36e505f"}
{"ts": "2026-09-10T03:01:36.712+00:00", "nivel": "INFO", "logger": "plurione.acceso",
 "mensaje": "GET /health 200", "request_id": "c1dde3cc9f1c4e09b869b6bca36e505f",
 "metodo": "GET", "ruta": "/health", "estado": 200, "duracion_ms": 507.44}
```

Los dos renglones son de la misma petición, uno lo emite uvicorn y el otro la aplicación, y
comparten identificador sin que uvicorn haya tenido que enterarse.

`contextvars` y no `threading.local`: el servidor es asíncrono, así que dos peticiones
pueden turnarse en el **mismo hilo** mientras esperan a la base de datos, y un almacén por
hilo les daría el mismo valor a las dos.

### El identificador entrante es una entrada del usuario

Se acepta un `X-Request-ID` del cliente —así se encadena con el de un balanceador o de otro
servicio; si cada salto inventa el suyo, la traza se corta en cada salto—. Pero aceptarlo
tal cual es **inyección en el registro**: con un objeto JSON por línea, un cliente que mande

```
X-Request-ID: algo\n{"nivel":"CRITICAL","mensaje":"todo bien"}
```

escribe renglones enteros en el log del servidor, indistinguibles de los reales. Se filtra
con `^[A-Za-z0-9._-]{1,64}$`, y lo que no encaja **se descarta** en lugar de limpiarse: un
saneado parcial es una lista de casos que alguien acabará rodeando.

### Un defecto que apareció al escribir la prueba

La prueba del 500 falló, y por una razón que no habría encontrado leyendo el código.
`ServerErrorMiddleware` —el que atiende las excepciones no controladas y construye la
respuesta— es el middleware **más externo** de Starlette: se instala antes que cualquiera
de los declarados por la aplicación. El `finally` que restablecía el contexto se ejecutaba
**antes** de que ese manejador corriera, así que encontraba el contexto vacío y volvía a
inventarse un identificador. Es decir: el arreglo de N-14 reintroducía N-14 en el único
sitio donde el identificador se le entrega a un humano.

```python
except BaseException:
    # A propósito NO se restablece el contexto aquí. …
    raise
else:
    _request_id.reset(testigo)
```

No restablecerlo no filtra nada entre peticiones: cada una se atiende en su propia tarea, y
una tarea recibe una **copia** del contexto.

---

## 16.4. Métricas: qué se publica y con cuánta confianza

`GET /metrics` en formato de exposición de Prometheus. Lo interesante no es la lista de
métricas sino de **dónde sale cada una**, porque no todas tienen la misma fiabilidad.

| Métrica | Origen | Exactitud |
| :--- | :--- | :--- |
| `plurione_http_peticiones_total` | Memoria del proceso | Solo del worker que responde |
| `plurione_http_duracion_segundos` | Memoria del proceso | Solo del worker que responde |
| `plurione_scores_calculados_total` | Memoria del proceso | Solo del worker que responde |
| `plurione_recalculos_en_curso` | Consulta a la base | Exacta |
| `plurione_recalculos_total` | Consulta a la base | Exacta |
| `plurione_prospectos_total` | Consulta a la base | Exacta |

La imagen sirve con `--workers 2`, así que una recogida la atiende **uno** de los dos y
devuelve su mitad de los contadores de proceso. Es el mismo defecto que tenía la limitación
de tasa con `memory://` (capítulo 14), y aquí **no se puede resolver igual**: un contador en
Redis por petición costaría más que la petición.

Se hicieron tres cosas en su lugar. Todo lo que puede leerse de la base **se lee de la
base**, y esas salen exactas venga la respuesta de donde venga. Los contadores de proceso se
etiquetan con `plurione_worker_info`, de modo que la limitación queda visible en los propios
datos y no solo en un comentario. Y se documenta cómo tener números exactos: una réplica por
contenedor con `--workers 1`, y que Prometheus recoja de todas.

**No se usa `prometheus_client`.** No por evitar una dependencia, sino porque su modo
multiproceso exige un directorio compartido en el que cada worker escribe sus ficheros
—incompatible con el `read_only: true` de §16.5— y hay que limpiarlo cuando un worker muere.

### La cardinalidad, y el defecto que casi se cuela

Se mide por **plantilla** de ruta (`/api/v1/leads/{lead_id}`) y no por ruta concreta
(`/api/v1/leads/8123`). Con la ruta concreta, cada prospecto consultado crea una serie
temporal nueva y la memoria del proceso —y la del Prometheus que lo recoja— crece sin tope:
es el modo clásico de tumbar un sistema de métricas con una instrumentación descuidada.

Obtener la plantilla resultó ser lo más delicado del capítulo. Starlette 1.6 deja en el
scope el `endpoint` y los `path_params`, pero **no** la ruta. La reconstrucción evidente
—sustituir en la ruta concreta los valores de los parámetros— es una trampa: en
`/api/v1/leads/1`, sustituir el valor `"1"` produce `/api/v{lead_id}/leads/1`, porque el
`1` que aparece antes es el de la versión de la API.

Se resolvió con un mapa `id(función del endpoint) → ruta declarada`. La primera versión
recorría `app.routes` en un solo nivel, y **funcionaba para `/health` y `/metrics` y para
nada más**: FastAPI 0.141 dejó de aplanar los routers incluidos, guarda envoltorios anidados
con su prefijo y deja en las rutas hoja la ruta *relativa*. Toda la API se estaba midiendo
como `<sin_ruta>` — sin un solo error, sin nada roto, con el volcado saliendo puntualmente
y sin decir nada.

Como el mapa se apoya en atributos internos de FastAPI, hay dos pruebas que lo guardan: una
comprueba que las rutas conocidas se traducen, y otra pide de verdad y exige que el volcado
**no contenga** `ruta="<sin_ruta>"`. Si una versión futura vuelve a cambiar la disposición,
lo dirá una prueba y no un panel vacío dentro de tres meses.

### Quién puede pedirlas

Prometheus no sabe iniciar sesión, así que esta ruta no puede depender del JWT del resto de
la API: se compara `METRICS_TOKEN` con `compare_digest` —la comparación de cadenas de Python
corta en el primer byte distinto, y ese tiempo es medible desde fuera—.

Sin testigo, la ruta queda **abierta en desarrollo y apagada en producción y staging**. El
volcado dice cuántos prospectos hay y cómo se reparten por categoría: es poco para quien
busca entrar y bastante para un competidor, y en todo caso información que nadie eligió
publicar. Que haya que declarar el testigo para encenderla convierte esa publicación en una
decisión.

Responde **404** y no 403, por la misma razón que un prospecto ajeno responde 404 en el
capítulo 15: un 403 confirma que la ruta existe, y con ella que hay algo que pedir.

Y no cuelga de `/api/v1`. El nginx de la pila solo hace de pasarela para `/api/`, así que
dejarla fuera de ese prefijo la mantiene inalcanzable desde el puerto público sin depender
de una regla de denegación que alguien pueda borrar.

---

## 16.5. N-12 — Los contenedores dejan de correr con los valores de fábrica

| | Antes | Ahora |
| :--- | :--- | :--- |
| Memoria y CPU | Sin techo | Declarados por servicio y ajustables |
| Privilegios | Se podían ganar con un binario setuid | `no-new-privileges` |
| Capacidades del núcleo | La quincena que trae cualquier imagen | `cap_drop: ALL` + lo justo |
| Sistema de ficheros | Escribible | Solo lectura salvo PostgreSQL |
| Registros | Crecen sin límite | `max-size` + `max-file` |

Sin techo de memoria, un recálculo desbocado consume la del anfitrión y se lleva por delante
**también a la base de datos**: el problema de un servicio se convierte en la caída de la
pila. Con techo, el que se pasa muere él solo. Va documentado que un techo demasiado justo
no produce un error legible sino un proceso que el núcleo mata con código 137 y sin un
renglón en el registro, y por eso los valores vienen holgados y son ajustables por variable.

Las capacidades se conceden desde cero. `postgres` necesita cinco para dejar el directorio
de datos en manos de su usuario y pasar a ejecutarse como él; `redis` y `nginx`, las de
cambiar de usuario, y nginx además `NET_BIND_SERVICE` para atarse al 80. El backend **no
necesita ninguna**: corre como `plurione` (uid 1001) y escucha en el 8000, por encima de los
puertos privilegiados. Esa línea vacía dice más de la imagen que cualquier comentario.

PostgreSQL es la única excepción a `read_only`, y se comprueba explícitamente en las pruebas
para que quede claro que es una decisión y no un servicio que se saltó la revisión: su
entrypoint ajusta permisos y escribe fuera del volumen al inicializar, y una base de datos
es por definición un proceso que escribe.

La rotación de registros importa más desde esta fase que antes: un objeto JSON por petición
llena un disco bastante más rápido que una línea por evento, y el disco que se llena es el
mismo en el que vive PostgreSQL.

---

## 16.6. N-13 — Copias, y la única prueba que las convierte en copias

Hay tres guiones, y el del medio es el que da sentido a los otros dos.

**`respaldo.sh`** vuelca en formato personalizado y **no da el resultado por bueno porque
`pg_dump` terminara**:

* comprueba que el archivo **se puede leer** (`pg_restore --list`). Un volcado escrito a
  medias —disco lleno, contenedor detenido— pesa lo suyo y parece bueno hasta el día que
  hace falta;
* comprueba que no sea sospechosamente pequeño. Una base vacía por error produce un volcado
  perfectamente legible de unos kilobytes, que pasaría la comprobación anterior sin problema;
* deja su huella SHA-256 al lado;
* escribe como `.parcial` y renombra al final, para que un volcado interrumpido **nunca**
  quede con el nombre de uno bueno y la retención no lo trate como una copia válida.

**`prueba_de_restauracion.sh`** restaura el volcado en una base **desechable** del mismo
servidor y compara el recuento de filas tabla por tabla contra la real. Dos detalles la
separan de un ritual:

* `pg_restore --exit-on-error`. Sin esa opción, `pg_restore` informa de los errores y
  **termina con código 0**: una restauración a medias se leería como un éxito y el informe
  diría que las copias funcionan;
* una guarda de tres líneas que se niega a continuar si el nombre de la base desechable
  coincide con el de la real. El nombre es configurable, y una errata haría que la *prueba*
  de restauración borrara producción antes de restaurar.

**`restaurar.sh`** es la operación destructiva. Exige `CONFIRMO_SOBRESCRIBIR=si` y el
**archivo exacto**: no coge el más reciente por su cuenta, porque el más reciente puede ser
justo el que ya contiene el borrado del que se quiere volver. Restaura con
`--single-transaction`, de modo que un fallo a mitad deja la base como estaba en lugar de
convertirla en una mezcla de dos versiones, que es el estado más difícil de arreglar.

Dos límites, escritos porque callarlos sería el mismo defecto que el resto del capítulo
persigue. Las copias viven en un volumen del **mismo disco**: protegen de un `DROP TABLE` o
de una migración que salió mal, **no** de que se muera el disco. Y la prueba demuestra que el
archivo sirve, no que se podría reconstruir el servicio entero en otra máquina; ese ensayo
es distinto y no lo cubre este guion.

---

## 16.7. La verificación sobre la pila real, y los dos defectos que encontró

El capítulo 14 terminó aprendiendo que «no hay motivo para esperar un fallo» no es
«comprobado». Aquí se levantó la pila sobre un volumen vacío desde el principio.

**Lo que salió bien a la primera.** `docker compose up --build` sobre un volumen recién
creado levantó la pila entera con `read_only`, `cap_drop: ALL` y techos de recursos:
`migrate` salió con código 0, el backend quedó sano y nginx sirvió la SPA. El endurecimiento
se comprobó aplicado de verdad, no declarado:

```
f10verif_backend  | ReadonlyRootfs=true  | Memory=2147483648 | CapDrop=[ALL] | CapAdd=<no value>
f10verif_db       | ReadonlyRootfs=false | Memory=1073741824 | CapDrop=[ALL] | CapAdd=[CHOWN DAC_OVERRIDE FOWNER SETGID SETUID]
f10verif_redis    | ReadonlyRootfs=true  | Memory=268435456  | CapDrop=[ALL] | CapAdd=[SETGID SETUID]
f10verif_frontend | ReadonlyRootfs=true  | Memory=134217728  | CapDrop=[ALL] | CapAdd=[CHOWN NET_BIND_SERVICE SETGID SETUID]
```

```
$ docker exec f10verif_backend touch /app/intruso.txt
touch: cannot touch '/app/intruso.txt': Read-only file system
```

Lo demás confirmado de extremo a extremo:

| Comprobación | Resultado |
| :--- | :--- |
| `X-Request-ID` propio del cliente | Se devuelve tal cual (`trazado-por-el-balanceador`) |
| `X-Request-ID` con espacios | Descartado; se genera uno propio |
| `/metrics` sin testigo / con testigo malo / con el bueno | 404 / 404 / 200 |
| `/metrics` por el puerto público (nginx) | Devuelve el `index.html` de la SPA: no hay pasarela |
| Segundo recálculo con uno vivo | **409** con el `job_id`, el avance y quién lo pidió |
| `INSERT` directo de un segundo turno en PostgreSQL | `duplicate key value violates unique constraint "uq_scoring_jobs_lease_key"` |
| Reinicio con un arriendo vencido | `RUNNING` → `FAILED`, `lease_key` liberado, motivo escrito |
| Copia + prueba de restauración | 11 tablas idénticas, salida 0 |
| Prueba contra un volcado corrompido a propósito | Salida **1** |

Y la limitación de los contadores por worker, medida en lugar de supuesta. Ocho recogidas
seguidas: la primera la atendió el worker `:8`, que ni siquiera tenía la serie; las siete
siguientes, el `:9`, cuyo contador iba de 2 a 8. Dos procesos, dos verdades parciales, y
`plurione_worker_info` diciendo cuál se está leyendo.

### Defecto 1: el listado de volcados se tragaba su propia salida

Al pedir una restauración sin nombrar el archivo, el guion debe listar los disponibles.
Listaba nada:

```
Disponibles:

```

La causa es el orden de las redirecciones:

```sh
ls -1t "$DIR"/*.dump 2>/dev/null >&2      # mal
ls -1t "$DIR"/*.dump >&2 2>/dev/null      # bien
```

En la primera forma stderr va a `/dev/null` y **después** stdout se apunta a stderr, que ya
es `/dev/null`: el listado desaparece entero. Leyendo el guion no salta a la vista;
ejecutándolo, sí. Y la información que se perdía era justo la que necesita quien está a
punto de restaurar.

### Defecto 2: la base desechable sobrevivía al fallo

Al probar el guion contra un volcado corrompido a propósito —para comprobar que la prueba
falla cuando debe—, falló correctamente, y dejó la base `lead_scoring_prueba_de_restauracion`
en el servidor con la restauración a medias dentro. Con `set -e`, el `pg_restore` que falla
aborta el guion **antes** del `DROP` final.

Es el caso que más se repite: el que se reintenta mientras se investiga. Cada intento dejaba
otra base huérfana en el servidor de producción. La retirada pasó a colgar de un `trap … EXIT`,
y se volvió a medir: salida 1 con el volcado corrupto, cero bases huérfanas después.

Los dos defectos tienen prueba de regresión, y ambas se comprobaron no vacías.

---

## 16.8. Evidencia

| Medida | Antes de la fase | Después |
| :--- | :--- | :--- |
| Pruebas | 428 | **536** |
| Cobertura | 91 % | **92 %** (3337 sentencias, 277 sin cubrir) |
| `ruff check .` | Limpio | Limpio |
| Trabajos de CI / pasos | 10 / 69 | 10 / **75** |
| Guardas de «configuración peligrosa» | 14 | **19** |
| Migraciones | `alembic check` limpio, reversible | Ídem, con la nueva revisión |

Las 108 pruebas nuevas se reparten en tres archivos: `test_fiabilidad_del_recalculo.py` (17)
para el arriendo y el turno, `test_observabilidad.py` (31) para el registro y las métricas, y
`test_endurecimiento_de_la_pila.py` (60) para los contenedores y las copias.

### Que ninguna prueba es vacía

Una prueba que no ha fallado nunca no ha demostrado nada. Se reintrodujo cada defecto de la
fase, uno por uno, y se corrió **la suite entera** con cada uno puesto:

| Defecto reintroducido | Fallos | Dónde |
| :--- | ---: | :--- |
| El turno deja de ser exclusivo | 4 | `test_fiabilidad_del_recalculo.py` |
| El trabajo terminado no libera el turno | 3 | `test_fiabilidad_del_recalculo.py`, `test_security_rbac.py` |
| El arriendo se renueva solo al empezar | 1 | `test_fiabilidad_del_recalculo.py` |
| Un arriendo vencido ya no se recoge | 5 | `test_fiabilidad_del_recalculo.py` |
| El manejador global vuelve a inventarse el `request_id` | 1 | `test_observabilidad.py` |
| Se acepta cualquier `X-Request-ID` | 6 | `test_observabilidad.py` |
| Se etiqueta por ruta concreta y no por plantilla | 1 | `test_observabilidad.py` |
| `/metrics` queda abierta en producción | 1 | `test_observabilidad.py` |
| El backend vuelve a escribir en su sistema de ficheros | 2 | `test_endurecimiento_de_la_pila.py` |
| La prueba de restauración deja de fallar cuando falla | 1 | `test_endurecimiento_de_la_pila.py` |

**25 fallos en total**, cada uno en el archivo que debe responder por él. La única fuga es
la segunda fila, y es correcta: un trabajo que no suelta el turno hace que el recálculo de
una prueba posterior de RBAC reciba 409 en lugar de 202. Que el bloqueo se propague así es
precisamente la consecuencia que el turno tiene en producción.

### El defecto que esta comprobación encontró en sí misma

La primera pasada dejó una fila en cero: retirar `--exit-on-error` del `pg_restore` real
**no hizo fallar ni una** de las 535 pruebas. La prueba que lo vigilaba buscaba esa cadena
en el archivo entero, y la cadena aparece dos veces: en la orden y en el comentario que
explica por qué hace falta. Quitarla de la orden dejaba el comentario, y la prueba pasaba.

Es el mismo error que ya había aparecido dos veces en este proyecto —con
`$proxy_add_x_forwarded_for` en el capítulo 14 y con `hashed_password` en el 15—: **el
comentario que documenta un arreglo termina siendo lo único que sostiene la guarda de ese
arreglo.** Aquí afectaba a cinco comprobaciones distintas: `pg_restore --list`,
`--exit-on-error`, `--single-transaction`, `CONFIRMO_SOBRESCRIBIR` y `compare_digest`, más
las cuatro claves de endurecimiento del compose, cuya cabecera las nombra todas.

Se corrigió mirando **directivas, no prosa**: un ayudante que descarta las líneas de
comentario en las pruebas, y un `grep -v` previo en el pipeline.

### Las guardas del pipeline también se comprobaron

No basta con escribirlas. Se extrajeron las cinco guardas nuevas del propio `ci.yml` —no
copiadas a mano, que se desincronizan— y se ejecutaron contra el árbol correcto y contra
quince defectos reintroducidos. **Las quince disparan y el árbol correcto pasa.**

Esa comprobación encontró cuatro guardas que no servían:

| Guarda | Por qué no servía |
| :--- | :--- |
| El barrido de huérfanos | Buscaba el nombre de la función, que sigue en la línea del `import` aunque nadie la llame |
| El 409 del recálculo | Igual: `RecalculoEnCurso` importado pero no capturado la dejaba en verde |
| El filtro del `X-Request-ID` | Buscaba la constante, no su uso; declararla y no comprobar nada pasaba |
| El endurecimiento de contenedores | Comprobaba que cada directiva apareciera «alguna vez»: con ocho servicios, quitársela a uno dejaba siete |

Y una quinta que fallaba sobre un árbol correcto —contaba once servicios porque incluía
los volúmenes y las redes—. Ese caso importa tanto como los otros: una guarda que siempre
falla acaba desactivada, y entonces no protege nada.

---

## 16.9. Lo que queda dicho y no hecho

* **Las copias no salen de la máquina.** Están en un volumen distinto del de la base —un
  `down -v` no se las lleva— pero en el mismo disco. Sacarlas fuera es un paso de operación
  que depende de dónde se despliegue, y no se ha inventado uno.
* **No hay planificador.** El respaldo se invoca a mano. Añadir un `cron` dentro de un
  contenedor habría sido fácil y habría añadido un proceso más que vigilar; la decisión de
  cada cuánto respaldar es de quien opera.
* **Los contadores por worker siguen siendo parciales.** Se documenta, se etiqueta y se
  explica cómo obtener números exactos, pero con `--workers 2` la recogida no es exacta.
* **La prueba de restauración no es un simulacro de recuperación ante desastre.** Demuestra
  que el archivo sirve; no que el servicio se podría reconstruir en otra máquina.
* **No hay alertas.** Hay métricas y hay registros correlacionados; quién avisa a quién
  cuando `plurione_recalculos_en_curso` lleva una hora a 1 es una decisión de operación que
  este repositorio no toma.
* **El mapa de rutas de las métricas depende de atributos internos de FastAPI.** Es lo que
  hace falta para etiquetar por plantilla en la versión instalada, y no hay API pública que
  lo dé. Se compensa con dos pruebas que lo guardan, pero conviene saber que una
  actualización de FastAPI puede exigir tocarlo.
* **El arriendo dura cinco minutos y no se puede configurar.** Es un compromiso entre
  vencer trabajando —un lote de mil prospectos con inferencia— y dejar el turno atascado
  tras una caída. El valor está razonado en el código; convertirlo en variable de entorno
  sin nadie que lo ajuste habría sido una palanca más que documentar.

---

## 16.10. Estado de los hallazgos de esta ronda

| Hallazgo | Estado | Dónde |
| :--- | :--- | :--- |
| **N-5** | Corregido: arriendo, señal de vida pegada al progreso y turno impuesto por índice único | `entities.py`, `recalculation_service.py`, `c7f4a1b90e52`, `endpoints/leads.py`, `main.py` |
| **N-11** | Cerrado en el capítulo 14; aquí queda documentado en el README y guardado en el pipeline | `devops/docker-compose.yml`, `README.md` |
| **N-12** | Corregido y comprobado aplicado sobre la pila levantada, no solo declarado | `devops/docker-compose.yml`, `devops/.env.example` |
| **N-13** | Corregido, con la prueba de restauración ensayada —y fallando— contra un volcado corrupto | `devops/backup/*.sh`, `devops/docker-compose.yml` |
| **N-14** | Corregido, con dos límites explícitos en §16.4 y §16.9 | `core/observabilidad.py`, `core/metricas.py`, `main.py`, `core/config.py` |

Los cinco tienen prueba de regresión que falla si se revierten, y los cinco tienen además
una guarda en el pipeline que los detecta sin ejecutar la suite. Los dos defectos que
encontró levantar la pila (§16.7) tienen la suya propia.
