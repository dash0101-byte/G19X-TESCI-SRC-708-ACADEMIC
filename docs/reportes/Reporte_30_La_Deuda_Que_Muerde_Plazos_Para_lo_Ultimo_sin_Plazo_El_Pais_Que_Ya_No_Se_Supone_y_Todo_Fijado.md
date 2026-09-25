# Capítulo 32: La Deuda que Muerde — Plazos para lo Último sin Plazo, el País que ya no se Supone y Todo Fijado por Versión

> **Sobre la numeración.** Este es el **Reporte 30** y el **capítulo 32**. El desfase es de
> dos y se produjo en dos escalones: el capítulo 29 («Lo que dijeron las personas») no
> escribió reporte propio —lo que produjo entró como actualización fechada en los reportes
> 25 a 28— y el capítulo 31 («Congelar y entregar») tampoco: sus cinco entregables fueron el
> documento de congelación, el guion cronometrado, el ensayo de la demostración, la guía de
> defensa y el resumen ejecutivo de la memoria, y ninguno era un reporte. Se deja dicho en
> lugar de renumerar: un reporte que cambia de número rompe las referencias cruzadas de
> todos los anteriores. Los apartados se numeran **32.x**, por el capítulo.

> **Sobre la congelación.** El proyecto está congelado desde el 24 de septiembre de 2026:
> solo entran correcciones de fallos. Este capítulo **no es una excepción a esa regla, es un
> ejemplo de ella**. Cada uno de los ocho puntos que cierra repara algo que el sistema ya
> prometía por escrito —una política de conservación sin filas sin plazo, una ficha que no
> inventa, una guarda que exige versión— y ninguno obligó a añadir una frase nueva al
> README, que es el criterio de §1 de `docs/Congelacion_y_Trabajo_Futuro.md`.

## 32.1. De dónde se parte

El documento de congelación clasificó el trabajo abierto por **de qué depende**. Casi todo
depende de algo que no está en este repositorio: una cuenta de LinkedIn, un CRM que mande
identificadores, seis meses de desenlaces reales, una decisión de PluriOne. Una sección no:
§6.1, «lo que puede morder». Ocho puntos que no dependen de nadie, que se podían hacer ese
mismo día, y que estaban ahí porque en su momento hubo algo más urgente.

«Morder» no es una metáfora suelta. Los ocho comparten una propiedad: **ninguno rompe nada
hoy**. El sistema arranca, sirve, puntúa y pasa el CI con los ocho dentro. Lo que hacen es
esperar. El CSV de realimentación espera a tener datos de personas dentro y a que nadie se
acuerde de borrarlo; la bitácora espera a crecer; el país espera a que alguien exporte una
lista y cuente clientes mexicanos que no lo son; las versiones sin fijar esperan al día en
que Debian publique otra revisión de `libpq5` y dos construcciones del mismo commit den dos
imágenes distintas.

Esta fase cierra **seis de los ocho** de §6.1 —1, 2, 3, 4, 5 y 8— más el 13 y el 22 de las
secciones de al lado. Los dos que quedan, 6 y 7, no se cierran por una razón que no es
falta de tiempo y está explicada en §32.9.

---

## 32.2. La última fila sin plazo: el conjunto de realimentación

### Lo que pasaba

La tabla de conservación de §20.5 tiene una fila por cada sitio donde el sistema guarda
algo. El capítulo 22 le puso plazo a cuatro que no lo tenían, el 28 añadió dos más con su
plazo desde el primer día, y quedó una sola diciendo **«sin mecanismo»**: el conjunto de
realimentación, `ml_pipeline/data/leads_reales*`.

Es la fila más incómoda de las que había. Lo que hay en ese CSV es **una fila por persona
cerrada**: su vector de variables del día que entró al embudo, su desenlace, el motivo y la
fecha. No vive en la base —de donde se exporta y se suprime con la ficha—, no vive en el
control de versiones —está en `.gitignore` desde el capítulo 18— y no vivía bajo ningún
plazo. Es decir: el único sitio del sistema donde datos de personas podían quedarse para
siempre era, precisamente, el que la política decía que estaba fuera de la política.

### Por qué no bastaba con añadir una consulta

`caducidad_service.py` tenía una forma sola de expresar un plazo: una clase `Plazo` con una
consulta que devuelve las filas vencidas y una función que las borra. Sirve para seis tablas
y no sirve para un directorio.

Se añadió una segunda clase, `PlazoDeArchivos`, con el mismo nombre, el mismo ajuste de
configuración y la misma entidad de la bitácora, y **cambiando lo único que tenía que
cambiar: qué se cuenta**. Las dos pasan por el mismo bucle, el mismo tratamiento de errores
y el mismo asiento. Lo que la bitácora anota lleva la unidad correcta: `archivos_borrados`
para este plazo y `filas_borradas` para los demás. Un `filas_borradas: 3` sobre un
directorio sería una cifra correcta con la etiqueta equivocada, y la bitácora se lee meses
después por alguien que no tiene el código delante.

### Tres decisiones que la consulta no enseña

**El patrón es estrecho, y no por prudencia genérica.** La purga mira `leads_reales*.csv` y
`leads_reales*_manifiesto.json`, que es exactamente lo que nombra la fila de §20.5. La
tentación era `*.csv`. En ese mismo directorio vive **`leads_historical.csv`**: el conjunto
sintético con el que se entrenó el artefacto que hoy sirve en producción. No lleva datos de
nadie, es la entrada reproducible del modelo y no tiene plazo. Un `*.csv` se lo habría
llevado a los treinta días y habría dejado el entrenamiento del modelo vigente sin poder
repetirse —el mismo bien que los capítulos 18 y 20 se dedicaron a construir—. La
contrapartida está dicha en §20.5: un conjunto exportado con otro nombre queda fuera del
plazo.

**No se siguen enlaces simbólicos, y solo se mira el primer nivel.** Sin eso, quien pudiera
escribir un nombre en ese directorio convertiría la pasada diaria en una forma de borrar
cualquier archivo de la máquina al que llegara el proceso.

**Una pasada restringida no toca el disco.** `aplicar_caducidad(db, plazos=[...])` aplica
esos plazos y ninguno más. No es una comodidad de firma: `scripts/guarda_del_motor_de_reglas.py`
aplica los plazos de `tareas` y `avisos` para comprobar otra cosa, y si pedir unos plazos
concretos arrastrara también los de archivos, esa guarda borraría el conjunto de
realimentación de quien la ejecutara. Por el mismo motivo, la suite entera corre con
`REALIMENTACION_DIR` apuntando a un directorio temporal: es el mismo argumento por el que la
base de las pruebas está en memoria y no en `lead_scoring.db`.

### El plazo, y el volumen que lo hace real

Treinta días por defecto, mínimo siete. El razonamiento del número está en el código, y es
distinto del de las demás filas: el conjunto de realimentación es un **derivado**. Se vuelve
a extraer de la base cuando haga falta, con la misma consulta y el mismo manifiesto. Lo
único que justifica conservarlo es poder repetir un entrenamiento y comparar el resultado
con el anterior, y eso no se hace un año después: se hace esa semana. Treinta días es lo que
dura una tanda de entrenamiento de principio a fin —extraer, entrenar, comparar contra el
artefacto vigente, decidir—. Pasado eso, el CSV deja de ser material de trabajo y pasa a ser
una copia de datos personales que nadie mira.

Y una pieza sin la cual todo lo anterior habría sido decorativo. En la pila, el extractor
corre **en el contenedor del backend** y la purga corre **en el de retención**. Cada uno con
su sistema de ficheros: sin nada más, el servicio de purga habría aplicado su corte cada día
sobre un directorio que en su contenedor no existe, habría anotado «cero archivos» —que es
cierto— y el CSV habría seguido en el otro contenedor para siempre. Se añadió un **volumen
compartido** (`realimentacion`), montado en los dos servicios, y la guarda del CI comprueba
que los dos lo montan en la misma ruta que dice `REALIMENTACION_DIR`. Un plazo que no alcanza
al archivo es la forma más cara de no tener plazo: cuesta el mismo código y además tranquiliza.

### El defecto que apareció al levantar la pila, y que era más viejo que este capítulo

Con todo escrito, probado y con las guardas en verde, el volumen se montó y el extractor **no
pudo escribir en él**: `PermissionError`. Docker crea el punto de montaje de un volumen
nombrado como `root:root` cuando ese directorio no existe en la imagen, y estos procesos
corren como `plurione`, uid 1001.

Lo importante no es el arreglo —crear los directorios en el Dockerfile con su dueño, para que
Docker copie contenido **y permisos** al volumen vacío— sino lo que se vio al comprobarlo. El
volumen **`deriva`**, que existe desde el capítulo 22, tenía el mismo defecto y llevaba diez
capítulos con él: propiedad de root y vacío. Su comentario en `docker-compose.yml` explica con
todo detalle por qué el estado de las alertas va en un volumen y no en `tmpfs` —«con tmpfs,
cada reinicio del contenedor olvidaría que ya avisó y volvería a avisar de la misma deriva»— y
nunca funcionó. No se había notado porque el monitor solo escribe cuando tiene una alerta que
recordar, y todavía no ha tenido ninguna: la primera habría fallado al guardar el estado y la
segunda habría vuelto a avisar de lo mismo, que es exactamente lo que ese volumen existía para
evitar.

Es la lección de §22.9 otra vez, y por eso se cuenta aquí: **ninguna prueba del repositorio
podía ver esto**. La suite corre contra SQLite en memoria, la guarda de compose lee YAML y la
de la imagen comprobaba que `/app` no fuera escribible —lo contrario de lo que hacía falta
mirar—. Solo aparece levantando la pila de verdad y escribiendo un archivo. Ahora hay un
control en el paso de endurecimiento de la imagen que intenta escribir en los dos puntos de
montaje y falla si no puede.

---

## 32.3. La bitácora gana plazo, y por qué eso no contradice a N-8

### Lo que pasaba

Desde el capítulo 14, la fila de `audit_log` en §20.5 decía «sin plazo en la aplicación ·
decisión de operación». Era una respuesta razonable en su momento y llevaba dieciocho
capítulos siendo la única fila de la tabla cuyo plazo no existía en ninguna parte. La tabla
crecía sin techo, y «decisión de operación» sin número escrito significa, en la práctica,
«nadie ha decidido».

### La tensión, dicha entera

Esta purga **no se parece a las demás**. En las otras tablas, borrar libera espacio y reduce
la exposición de datos personales. Aquí, borrar destruye la prueba de quién hizo qué: el
asiento de que alguien eliminó una ficha, de que alguien lanzó un recálculo que reescribió
la cartera entera, o de que una cuenta encadenó quince denegaciones por rol tanteando sus
límites. N-8 dice exactamente eso, y la guarda del CI que lo vigila lleva desde entonces en
el pipeline.

El plazo no contradice a N-8: lo **delimita**. Lo que N-8 prohíbe es que una petición
autenticada pueda borrar o editar asientos, y eso sigue prohibido y sigue comprobado —la
bitácora no expone ningún método de escritura y solo la lee `System_Admin`—. Una política de
retención con su número escrito y una herramienta de borrado al alcance de quien abusa de
sus permisos son cosas distintas, y la diferencia entera está en tres protecciones:

1. **El mínimo es el más alto de toda la tabla: 365 días.** Un año es el ciclo de revisión
   más corto que tiene sentido; por debajo, la purga se llevaría los asientos antes de que
   nadie haya podido mirar el ejercicio completo. El valor por defecto es de **dos años**, y
   se equivoca del lado de conservar a propósito.
2. **No es alcanzable desde la API.** Corre en el servicio de retención, el mismo proceso
   que resume el historial y aplica los demás plazos.
3. **La propia purga deja su asiento**, diciendo cuántos asientos se llevó y hasta qué
   fecha. Lo que se pierde queda acotado por escrito.

Y sigue siendo una decisión de operación: 730 días es un número técnico y provisional, como
todos los de §20.5, y **no es una valoración jurídica**. Lo que cambia respecto al capítulo
14 es que ahora hay un mecanismo y un número, en lugar de una nota explicando por qué no
había ninguno de los dos.

### Dos detalles del orden

**La bitácora se purga la última de la lista.** Cada plazo que falla escribe su asiento de
`ERROR` durante la pasada. Si la purga de la bitácora corriera antes, podría llevarse en esa
misma pasada el asiento de un fallo que acababa de ocurrir, y el fallo del día quedaría sin
rastro. Hay una prueba que lo fija y una guarda del CI que lee la lista y comprueba que la
última entrada es `audit_log`.

**No se excluyen los asientos de la propia purga.** Serían los únicos que no caducarían
nunca y acabarían siendo lo único que quedara en la tabla: un registro de que hubo purgas y
de nada más.

---

## 32.4. Lo que la ficha dejaba de suponer

Tres restos de los capítulos 21, 24 y 25, con la misma forma: **en la base hay un valor
donde no hubo un dato**.

### El país

Este era el peor de los tres, y lo era por dónde vivía. Los otros dos supuestos que el
proyecto ha quitado —el tamaño de empresa «1-10» del capítulo 25, el cero de ingresos del
24— vivían en un servicio: alguien escribió una línea que rellenaba un hueco, y quitarla
bastó. El país vivía en la **columna**:

```python
country = Column(String(100), default="México", nullable=False)
```

No hacía falta que nadie escribiera nada. Toda ficha que llegara sin país salía con país, y
lo escribía la ausencia de alguien. La página de interés no pregunta el país —su formulario
no tiene ese campo— y producía, una tras otra, fichas que afirmaban que la persona está en
México. Una integración que no lo mandara, igual.

El país **no puntúa**: no está en `COLUMNAS_DEL_MODELO` ni lo mira la regla heurística. Lo
que se corrige aquí no es una predicción, es **lo que la ficha afirma de una persona**, que
es lo que lee el asesor antes de llamar y lo que saldría en cualquier lista que alguien
exporte.

Se tocaron los tres sitios que lo escribían, y un cuarto que lo enseñaba:

| Dónde | Antes | Ahora |
| :--- | :--- | :--- |
| La columna | `default="México", nullable=False` | `nullable=True`, sin valor por defecto |
| El esquema de la API | `country: str = Field("México")` | `country: Optional[str] = Field(None)` |
| El alta del registro de actividad | `datos.get("country", "México")` | `datos.get("country")` |
| La ficha, en el cliente | `{lead.country \|\| 'México'}` y el formulario precargado | «Sin registrar», y el formulario vacío |

El cuarto no estaba en el enunciado de la deuda y había que tocarlo de todas formas: es el
único sitio donde una persona lee el país, y un `|| 'México'` en el cliente reintroduce la
suposición entera sin tocar el servidor. Peor aún, el formulario de edición lo llevaba
precargado: el asesor entraba a corregir un teléfono y salía habiendo declarado un país.

Un detalle menor con consecuencias: el formulario manda `""` cuando el campo se deja en
blanco. Un validador convierte el blanco en ausencia, porque dos formas de decir lo mismo en
la misma columna —`NULL` para las fichas que nunca lo tuvieron y `''` para las que pasaron
por la pantalla— habrían sido peor que la suposición original: cada consulta posterior
tendría que acordarse de las dos.

### La migración de datos, y por qué toca tan poco

Aquí está la decisión que más se pensó. Vaciar «México» de todas las fichas habría sido
sustituir una suposición por otra. Se vacían **solo las fichas de las que consta que nadie
indicó el país**, y hay exactamente un conjunto del que eso se puede demostrar: las que creó
la página de interés. Su formulario no lo pregunta, y su fuente está marcada
`actualiza_prospecto=False`, así que tampoco pudo escribirlo una entrega posterior. Si la
**primera** actividad de una ficha es `pagina_de_interes` y su país es «México», ese «México»
lo puso el valor por defecto de la columna.

Del resto no se puede distinguir, y por eso no se tocan:

* **El alta del panel** enseñaba el campo relleno con «México». Quien dio de alta la ficha lo
  tuvo delante y lo dejó estar. Es una elección débil, pero es una elección, y la base no
  guarda si el campo se tocó.
* **El CRM y los formularios** pueden mandar `country` o no mandarlo. Lo que llegó y lo que
  rellenó el defecto acabaron en la misma columna sin marca que los separe.
* **La bitácora no ayuda**: anota que se creó una ficha, no el cuerpo con el que se creó.

La prueba de la migración comprueba las **dos direcciones** del criterio, porque un criterio
que solo se prueba donde acierta no es un criterio: se vacía la ficha nacida en la página
—también si después recibió una nota manual, porque manda la primera actividad—, y no se
tocan la del panel, la que recibió el envío de la página *después* de existir, la que no
tiene ninguna actividad, la del CRM, ni la que dice «Colombia».

**La reversión vuelve a suponer, y se dice.** Para restaurar `NOT NULL` hay que rellenar los
vacíos, y el único valor posible es «México»: la reversión escribe ese país también en fichas
que nunca lo tuvieron. No hay forma de evitarlo con una columna obligatoria. Está en el
docstring de la migración, en el mensaje que imprime al revertir y en una aserción de la
prueba, para que quien revierta sepa qué está firmando.

### El teléfono de los asesores

El capítulo 21 normalizó el teléfono de los prospectos a E.164 y se olvidó del de los
asesores, que se quedó como texto libre. El arreglo no es la validación —eso son cuatro
líneas— sino **de dónde sale**: el envoltorio de Pydantic vive ahora en `app.core.telefono`
y lo usan los dos esquemas. Mientras cada uno tuvo su copia privada, mantener una sola forma
del número dependía de que quien tocara una se acordara de la otra, que es exactamente cómo
se llegó hasta aquí. La guarda del CI no comprueba que exista la validación: comprueba que
los dos esquemas importen el **mismo módulo**.

La migración normaliza los que ya estaban escritos de otra forma, con la misma copia local
del normalizador que usó la migración del capítulo 21 —una migración no importa código de la
aplicación, porque ese código puede cambiar y la migración tiene que seguir haciendo lo que
hizo el día que se escribió— y con el mismo criterio para lo que no se entiende: se deja como
estaba. Un número ilegible puede seguir siendo la única forma de localizar a esa persona, y
borrarlo sería perder el dato en lugar de corregirlo.

### Los ceros de ingresos

Desde el capítulo 24, ni el alta ni la API ni la ingesta escriben cero cuando no hay cifra.
Los ceros anteriores se quedaron. El extractor ya los leía como ausentes —`ingresos_o_ausente`
descarta todo lo que no sea mayor que cero, porque ninguna empresa a la que se vende este
servicio factura cero—, así que el modelo nunca los creyó. Quien sí los creía era la ficha,
que los enseñaba como «0». La migración alinea la base con la lectura que ya se hacía de
ella. La reversión no los devuelve: escribirlos sería reintroducir a mano el defecto del
capítulo 24, y además en fichas que quizá nunca lo tuvieron.

---

## 32.5. `App.jsx`, con la aplicación montada

`App.jsx` no pinta casi nada: **decide**. Mira si la sesión se pudo restaurar, si hay
usuario y si ese usuario todavía lleva la contraseña que le fijó otra persona, y de esas tres
respuestas salen cuatro pantallas. Hasta este capítulo ese razonamiento estaba comprobado por
lectura y por la prueba del componente de cambio de contraseña, que se monta solo. Es decir:
se sabía que el componente funciona, no que la aplicación lo enseñe.

Se comprueban dos cosas, y las dos vienen del enunciado de la deuda:

**La redirección.** Una cuenta con `must_change_password` ve la pantalla de cambio y no el
panel. Si esa condición se cayera, la aplicación enseñaría el panel entero a una cuenta que
el servidor rechaza para todo salvo cambiar la contraseña, y cada tarjeta fallaría con un
403. Lo que vería el usuario no es «acceso denegado»: es un panel roto.

**Que en ese estado no se lancen cargas de datos.** Ésta es la parte que ninguna prueba de
componente puede ver, porque vive en los efectos de `App` y no en lo que se pinta. Los dos
`useEffect` que cargan analíticas, campañas y prospectos llevan
`if (!user || user.must_change_password) return;`, y ese `return` es media línea que un
cambio razonable se lleva por delante sin romper nada visible: las tres peticiones saldrían,
el servidor respondería 403 a las tres y la consola se llenaría de errores mientras la
pantalla de cambio de contraseña se ve perfecta.

La prueba tiene ocho casos, y uno de ellos existe para que los otros signifiquen algo: el
contraste. Con sesión utilizable, las tres cargas **sí** salen. Sin ese caso, «no se lanzan
cargas» estaría comprobando que unas funciones simuladas no se llaman, que es algo que
también se cumple si `App` no se monta.

Dos detalles de cómo está montada. El módulo `services/api` se simula **export por export**,
enumerándolos desde el módulo real: hacerlo a mano habría dejado fuera cualquier función que
un componente hijo llame sin que la prueba lo sepa, y el fallo llegaría como «no es una
función» desde un archivo que no es el que se está probando. Y los componentes del panel van
sustituidos por marcadores, porque cada uno tiene su propia prueba y aquí lo que se mide es a
cuál se llega; `LoginScreen` y `CambioDeContrasenaObligatorio` son los de verdad, porque son
el destino de la decisión.

---

## 32.6. Todo fijado por versión: `apt-get` y las acciones de GitHub

El capítulo 22 fijó las imágenes base por huella y prohibió `apk upgrade`, y dejó dos
mitades sin hacer. Las dos las cierra la misma guarda, `scripts/renovar_imagenes.py --solo-fijacion`,
que ya era la que corre la suite y el pipeline.

**La guarda exigía versión a `apk` y no a `apt-get`.** Es decir: a la imagen del **cliente**
y no a la del **backend**. Los cuatro parches de seguridad de Debian iban con su versión
porque se escribieron a mano en el capítulo 22, pero `libpq5` —la biblioteca de PostgreSQL
en la imagen final, la más cerca del proceso que atiende peticiones— y las herramientas de
compilación de la primera etapa se resolvían con lo que hubiera ese día. La imagen base iba
por huella y las ruedas de Python por lock con hash; el compilador con el que se construyen
esas ruedas lo elegía el índice de Debian en el momento del build.

Ahora van con versión exacta, y conviene decir hasta dónde llega eso: **`build-essential` es
un metapaquete**. Fijar su versión fija el metapaquete, no cada `gcc` y cada `libc` que
arrastra. Es una mejora real —la línea deja de construir cuando Debian lo renueva, y la
renovación pasa a ser un acto con su diff— y no es fijación total. Fijar el árbol completo
exigiría instalar con la lista resuelta entera, que hay que regenerar en cada renovación de
la base; no compensa para una etapa que no viaja a la imagen final.

**Las acciones de GitHub iban por etiqueta.** `actions/checkout@v4`. El CI fijaba por huella
todo lo que **descarga** y nada de lo que **ejecuta**. Una etiqueta es móvil: quien controle
el repositorio de la acción —o quien le robe la cuenta a quien lo controle— la reapunta, y el
siguiente `push` ejecuta otra cosa, con el token del repositorio y viendo lo que ve el
trabajo, sin que aquí cambie una sola línea. Las siete acciones que usa el pipeline van ahora
por la huella de su commit, con la versión en un comentario al lado para saber qué seguir al
renovar.

Una decisión sobre la renovación: `--aplicar` renueva huellas de **imágenes** y no de
acciones. Subir de versión una acción se lee en el diff y se decide; arrastrarlo
automáticamente sería reintroducir por la puerta de atrás el problema que esto cierra.

---

## 32.7. Que nada de esto sea decorativo

### Las pruebas

Tres archivos nuevos y dos ampliados:

| Archivo | Qué fija |
| :--- | :--- |
| `test_caducidad_de_los_datos.py` (ampliado) | Los dos plazos nuevos, la unidad del asiento, el conjunto sintético que **no** caduca, el enlace simbólico que no se sigue, la pasada restringida que no toca el disco, la bitácora la última, y que el volumen lo compartan quien extrae y quien purga |
| `test_nada_supuesto_en_la_ficha.py` (nuevo) | Columna, esquema, registro de actividad y página de interés sin país; el teléfono de asesor en E.164 por el mismo módulo; los ingresos que no se indicaron |
| `test_migracion_pais_telefonos_e_ingresos.py` (nuevo) | El ciclo completo de la migración con Alembic de verdad: las dos direcciones del criterio del país, los teléfonos, los ceros, y qué recupera y qué no la reversión |
| `test_imagenes_fijadas.py` (ampliado) | `apt-get upgrade`, paquetes de `apt-get` sin versión, `apt-get update` que **no** es un disparo, y acciones por etiqueta |
| `App.test.jsx` (nuevo) | Las cuatro pantallas de `App.jsx` y las cargas que no se lanzan |

### Las guardas del CI

Tres pasos nuevos en `configuracion-peligrosa`, que pasa de 34 a **37 controles**, más la
guarda de fijación ampliada:

* **«El país no se supone»** — los tres sitios que lo escribían y el cuarto que lo enseñaba.
* **«El teléfono se normaliza con un solo módulo»** — que los dos esquemas importen
  `app.core.telefono` y que el alta y la edición lo apliquen.
* **«Nada sin plazo (2)»** — la bitácora con plazo y la última de la lista; el patrón
  estrecho de la purga de archivos; los enlaces simbólicos; la pasada restringida; y el
  volumen compartido.
* **«Imágenes, paquetes y acciones, todo fijado»** — el mismo guion de renovación, ahora
  también sobre `apt-get` y sobre los `uses:`.

Y un control más dentro del paso que ya verificaba el endurecimiento de la imagen: que los
puntos de montaje de los dos volúmenes existan en la imagen y sean **escribibles por el
usuario sin privilegios**. Es el que habría detectado el defecto de `deriva` diez capítulos
antes.

### La reintroducción de defectos

**27 defectos reintroducidos, 27 detectados.** Uno a uno: se copia el archivo, se mete el
defecto, se ejecuta **solo** la guarda o la suite que debería detectarlo, se exige que falle,
y se restaura. Diez son variantes vistas por la suite y diecisiete por las guardas del CI.

El ejercicio encontró **dos guardas que no servían**, y las dos del mismo tipo: comprobaban
la presencia de la línea correcta en lugar de la ausencia de la incorrecta.

La primera es la que vale la pena contar. La guarda del país hacía
`grep -q 'country: Optional[str] = Field(None, max_length=MAX_COUNTRY)'` sobre
`schemas/lead.py`. Con el defecto puesto —`LeadBase` volviendo a escribir «México»— la guarda
**pasaba**, porque `LeadUpdate` declara el mismo campo unas líneas más abajo y el `grep`
seguía encontrándolo allí. Una guarda que encuentra lo que busca en otro sitio es peor que no
tenerla: da una señal verde sobre una comprobación que no se hizo. Ahora se mira la ausencia
de cualquier literal por defecto en ese campo y se exige que las dos declaraciones sean
opcionales.

La segunda fue la del orden de la purga de la bitácora, por una razón parecida: la expresión
que extraía la lista de plazos no reconocía un nombre con dígitos, así que un plazo añadido
después de `audit_log` podía no aparecer en la comparación.

### Una prueba que fallaba sola una vez de cada doscientas

Al correr la suite entera apareció un fallo en `test_informe_de_publicaciones.py` que no se
reproducía al ejecutar esa prueba sola. La línea era
`assert "99" not in str(informe)`, y su intención es correcta: el score del prospecto ajeno
—99.0— no debe salir del servidor cuando pregunta un asesor que no lo lleva.

Lo que no se tuvo en cuenta al escribirla es que la respuesta incluye el **enlace público**, y
dentro el slug: veintidós caracteres aleatorios de `secrets` en base64. La probabilidad de que
la cadena «99» caiga dentro de un slug así es de aproximadamente **una de cada doscientas
ejecuciones**. Es decir: la prueba llevaba desde el capítulo 25 fallando sola con esa
frecuencia, sin que nada estuviera mal, y con un mensaje que apuntaba a una fuga de datos.

Una prueba que falla al azar es peor que una prueba que falta: la primera vez se investiga, la
tercera se vuelve a lanzar el CI, y a partir de ahí un fallo de verdad en esa línea se lee como
«otra vez la flaky». La búsqueda se acotó a todo menos la cabecera de la publicación, que no
lleva datos de ningún prospecto.

---

## 32.8. Comprobación final

| Qué | Resultado |
| :--- | :--- |
| Suite del backend | **1364 pruebas** (y una saltada: el enlace simbólico, que Windows no deja crear sin privilegios y sí corre en el CI), **93 %** de cobertura |
| Suite del cliente | **358 pruebas** en **26 archivos**; cobertura 94,51 / 86,34 / 97,27 / 97,42 |
| `ruff check .` | Sin avisos |
| `npm run lint` | Sin avisos |
| Guardas del CI | Las cuatro de propiedades, en verde; `configuracion-peligrosa` con 37 controles |
| Migración | Ida, vuelta y otra vez ida; el esquema migrado coincide con el declarado por los modelos |
| Imagen del backend | Construida con los paquetes de `apt-get` fijados por versión |
| Pila completa | Levantada con `devops/pila.py`; `/health` responde `healthy` con el modelo cargado, la API sin sesión da 401 y el SPA sirve |
| **La purga, en la pila de verdad** | El servicio de retención borró los dos archivos vencidos del volumen compartido y **dejó intacto `leads_historical.csv`**; su asiento en la bitácora dice `archivos_borrados: 2` con el corte |
| Reintroducción de defectos | **27 de 27** detectados |

---

## 32.9. Lo que esta fase no hizo

**Los puntos 6 y 7 de §6.1 siguen abiertos, y no por falta de tiempo.**

* **6 — La entrega de WhatsApp con varios mensajes no es atómica.** El arreglo es escribible
  —envolver el registro de la tanda en una transacción— pero **no comprobable**: nadie ha
  conectado nunca una cuenta de WhatsApp Business a este sistema, y no se sabe si el
  proveedor reentrega la tanda entera o solo lo que faltaba. De esa respuesta depende si la
  transacción única es la corrección o el problema. El daño mientras tanto está acotado: no
  corrompe nada —el reintento encuentra los primeros como duplicados— y lo que deja es
  trabajo a medias, visible en la bandeja.
* **7 — Sin `event_id`, el CRM se deduplica por contenido.** Aquí no hay nada que escribir.
  Cuando el sistema de origen no manda identificador, la única huella disponible es el
  contenido. La alternativa cambia un caso raro y sin daño —dos eventos reales idénticos byte
  a byte, incluido el instante— por uno frecuente y con daño: cada reentrega duplicaría la
  actividad. Queda **reclasificado a §3** del documento de congelación, con lo demás que
  espera a que alguien del otro lado haga algo.

**Un país escrito por error no se puede vaciar desde el panel**, y tampoco ningún otro campo
de la ficha. La actualización parcial del repositorio aplica `if value is not None`, así que
un `null` explícito se ignora: se puede cambiar «México» por «Perú», no dejarlo en blanco.
Se descubrió al comprobar si las fichas que la migración **no** toca —las del panel, las del
CRM— tenían remedio desde la interfaz. No se corrige aquí porque cambiar esa línea altera el
comportamiento de **todos** los campos a la vez —el cliente manda `null` en varios cuando el
formulario los deja en blanco—, y eso es una decisión de diseño con su propia discusión, no
una corrección de este capítulo. Hay una prueba que fija el comportamiento actual, de modo
que el día que se cambie haya que decidirlo en lugar de descubrirlo, y una entrada nueva en
§6.1 del documento de congelación.

**`App.jsx` no entra en el suelo de cobertura del cliente.** Sus pruebas cubren el **48 %** del
archivo, que es la parte que decide: las cuatro pantallas y los dos efectos. El resto es el
cableado de las pestañas, y cada componente que cuelga de ahí tiene su propia prueba.
Incluirlo en `coverage.include` habría bajado el suelo común de 92 a unos 80 puntos para
acomodar un archivo, debilitando la guarda sobre los cinco que sí llevan lógica. La cifra
queda escrita aquí para que la decisión se pueda revisar con el número delante.

**`build-essential` va fijado como metapaquete, no como árbol completo.** Explicado en §32.6.

**El plazo de la bitácora y el del conjunto de realimentación son técnicos y provisionales.**
Como todos los de §20.5. Que ahora haya un número no los convierte en una valoración
jurídica; los fija quien responda del tratamiento de datos en la empresa.

**Una copia del conjunto de realimentación que alguien se haya llevado a su portátil no la
alcanza ningún plazo.** El que se aplica es el del directorio de la instalación. Lo que sale
de la máquina deja de estar bajo este mecanismo, igual que las copias de seguridad.

**La prueba del enlace simbólico se salta en Windows** sin privilegios para crearlos. Corre
en el CI, que es Linux, y allí es donde la propiedad importa.

**El país sigue sin validarse contra ninguna lista.** Es texto libre, como antes. Lo que se
arregló es que no se invente, no que se normalice: una lista cerrada de países es un campo
nuevo con su pantalla y su migración, y eso cae del lado de «funcionalidad» según §1 de la
congelación.
