# Capítulo 33: Vaciar un Campo es un Cambio — El Nulo que se Ignoraba y la Lista que Dicta la Tabla

> **Sobre la numeración.** Este es el **Reporte 31** y el **capítulo 33**. El desfase de dos
> viene de los capítulos 29 y 31, que no escribieron reporte propio; está explicado al
> principio del Reporte 30. Los apartados se numeran **33.x**, por el capítulo.

> **Sobre la congelación.** El proyecto sigue congelado desde el 24 de septiembre de 2026.
> Este capítulo corrige **un** fallo, el punto 24 de §6.1, y no añade nada: el README ya
> decía que la ficha se edita y que un dato que no se indicó está ausente. Lo que no decía
> nadie es que un dato escrito no se podía retirar. Con el criterio de §1 de
> `docs/Congelacion_y_Trabajo_Futuro.md` —«si para explicarlo hay que añadir una frase nueva
> al README, es funcionalidad; si la frase ya está escrita y el código no la cumple, es un
> fallo»— esto es un fallo, y de los que se explican solos.

## 33.1. De dónde se parte

El capítulo 32 fue a quitar el país supuesto. Cambió la columna, cambió el esquema, cambió
el alta del registro de actividad y escribió una migración que vaciaba exactamente las
fichas de las que consta que nadie eligió el país. Al final, comprobando lo obvio —que un
asesor pudiera corregir a mano las fichas que la migración no podía tocar— se encontró con
que no podía. Pedir que el país quedara vacío devolvía **200**, la ficha entera, y el país
intacto.

No era del país. Era de todos los campos, y llevaba ahí desde que existe la edición.

El capítulo 32 lo anotó como punto **24** de §6.1 y lo dejó abierto a propósito, con una
prueba de fijación que afirmaba el comportamiento equivocado para que se pusiera roja el día
que alguien lo corrigiera. El motivo de no tocarlo entonces está escrito y sigue pareciendo
correcto: el arreglo afecta a **todos** los campos de la ficha a la vez, y eso es una
decisión que se toma, no una línea que se cambia de paso mientras se hace otra cosa.

Este capítulo la toma.

## 33.2. El fallo, y por qué es peor de lo que parece

### La línea

```python
update_data = lead_in.model_dump(exclude_unset=True)
...
for field, value in update_data.items():
    if hasattr(lead, field) and value is not None:
        setattr(lead, field, value)
```

`exclude_unset=True` hace exactamente lo que hay que hacer: deja en el diccionario **solo
los campos que venían en el cuerpo**. Un campo que el cliente no mandó no aparece. Un campo
que el cliente mandó a nulo aparece, con valor `None`. La distinción que hacía falta ya
estaba hecha, y estaba hecha bien.

Y la línea siguiente la deshacía. `value is not None` vuelve a juntar los dos casos y los
resuelve igual: tirándolos. Con esa condición puesta, `model_dump(exclude_unset=True)` y
`model_dump()` producen el mismo resultado observable para los campos vacíos; el
`exclude_unset` era decoración.

### Lo que producía

Conviene decirlo con precisión, porque «no se podía vaciar un campo» suena a limitación y
esto no era una limitación.

Un sistema que no puede hacer algo y lo dice tiene un límite. La petición habría vuelto con
un 422, o con un 405, o con cualquier cosa que significara «esto no». Lo que volvía era un
**200 con la ficha entera**, que es la respuesta que este endpoint da cuando ha guardado.
El panel enseñaba «Prospecto actualizado y rescoreado dinámicamente». Y el dato seguía ahí.

La diferencia importa para quién lo descubre y cuándo. Un límite lo descubre quien lo
intenta, en el momento. Esto lo descubre alguien **después**: el asesor que borró un país
equivocado hace dos semanas y se lo encuentra otra vez, o —peor— nadie, y la ficha sigue
afirmando de una persona algo que un compañero ya había intentado retirar.

### Dónde se nota más

En el campo que el capítulo 32 acababa de tocar. Esa migración solo vacía las fichas de las
que consta que la suposición fue suposición: las de la página de interés, cuyo formulario no
pregunta el país. De las demás no se puede demostrar nada, y el capítulo 32 escribió que
quedaban «a que un asesor las corrigiera». No se podían corregir. La mitad del arreglo era
teórica y nadie lo había comprobado hasta el final.

También en los ingresos. El capítulo 24 existe entero por la diferencia entre «cero» y
«ausente», y llegó a migrar los ceros que ya había en la base. Un asesor que se equivocara
al teclear una cifra podía sustituirla por otra cifra, no retirarla: el único camino de
vuelta a «ausente» era el de la migración, que ya había pasado.

## 33.3. Las dos mitades del arreglo

Quitar `and value is not None` es media línea. La otra mitad es la que decide qué pasa
cuando el vacío llega a un campo que la ficha no puede no tener.

### Primera mitad: se aplica lo que vino

```python
for field, value in update_data.items():
    if hasattr(lead, field):
        setattr(lead, field, value)
```

Lo que había que conservar, y que era fácil romper arreglando lo otro: el `exclude_unset`.
Un arreglo apresurado —quitar la condición *y* el `exclude_unset`, que es lo que parece
coherente si uno mira el bucle y no el dump— habría hecho que cada edición vaciara todos los
campos que el formulario no incluyera. Es el fallo simétrico, y bastante más destructivo que
el que se corrige. Tiene prueba propia (`test_lo_que_no_se_manda_no_se_toca`) y su línea en
la guarda del CI.

### Segunda mitad: el 422, y de dónde sale la lista

Cuatro campos de la ficha no admiten vacío porque la tabla los declara `NOT NULL`: nombre,
apellido, correo y fuente, más la etapa y el estado de calificación, que son enumeraciones
obligatorias. Vaciar uno de esos tiene que responder **422 nombrando el campo**, nunca 200.

La pregunta interesante no es esa, es de dónde sale la lista. Escribirla a mano es lo que
pide el cuerpo:

```python
OBLIGATORIOS = {"first_name", "last_name", "email", "status"}   # no
```

Esa línea es correcta el día que se escribe. Y se queda atrás en la primera migración que
añada o quite un `nullable`, en silencio, sin que ninguna prueba se ponga roja, porque nada
la relaciona con la tabla. El fallo que produce aparece meses después del cambio que lo
causó y en una de estas dos formas, las dos malas: un 500 desde el `INSERT` cuando la lista
se quedó corta, o un 422 a un campo que la base sí admite vacío cuando se quedó larga.

Así que se le pregunta a la tabla:

```python
def _campos_que_no_admiten_vacio() -> frozenset:
    return frozenset(columna.name for columna in Lead.__table__.columns if not columna.nullable)
```

El conjunto incluye `id`, `current_score`, `created_at` y las demás columnas calculadas, y no
estorban: ninguna está en `LeadUpdate`, así que el cruce con lo que el cliente envió no las
alcanza. La comprobación vive en un `model_validator` de `LeadUpdate`, que es lo que hace
que el 422 sea un 422 de verdad —el de FastAPI, con el campo en `loc`— y no un error
traducido a mano en el endpoint.

Y mira `model_fields_set`, no qué campos valen `None`:

```python
vacios = {campo for campo in self.model_fields_set if getattr(self, campo, None) is None}
prohibidos = sorted(vacios & CAMPOS_QUE_NO_ADMITEN_VACIO)
```

La diferencia es el capítulo entero. `model_fields_set` son los campos que **vinieron en el
cuerpo**. Si en vez de eso se recorrieran todos los campos del modelo, un campo ausente —que
vale `None` por defecto— se confundiría con uno vaciado y **ninguna ficha se podría editar**:
cualquier PUT que no mandara los seis obligatorios se rechazaría.

### Un vacío, no dos

Al arreglarlo apareció algo que no estaba en el enunciado y que había que resolver para que
el enunciado tuviera sentido. El formulario del panel manda `""` en los campos de texto y
`null` en los que pasan por un conversor. Con el arreglo puesto y sin nada más, borrar
«Ciudad» habría guardado `''` y borrar «País» habría guardado `NULL`: dos vacíos distintos,
en la misma fila, producidos por la misma pantalla, y toda consulta posterior obligada a
acordarse de los dos.

El capítulo 32 ya había escrito esa regla para el país (`_pais_o_vacio`). Aquí se generaliza
a `_texto_o_vacio` y se aplica a los campos de texto de la **edición**. Sin esto, «vaciar un
campo» no era una operación sino dos, según por dónde se vaciara.

## 33.4. La bitácora distingue lo que se borró

El asiento de la edición ya decía qué campos se tocaron, y deliberadamente no copiaba los
valores: la bitácora se consulta con otro criterio de acceso que la tabla de negocio, y un
teléfono o un correo copiados allí salen del alcance que los protege (R-11).

Ahora dice además cuáles se vaciaron:

```python
enviados = lead_in.model_dump(exclude_unset=True)
auditoria.anotar(
    campos=sorted(enviados.keys()),
    campos_vaciados=sorted(campo for campo, valor in enviados.items() if valor is None),
)
```

Siguen siendo **nombres de campo**, no valores: `campos_vaciados` tiene la misma forma que
`campos` y la misma discreción. Lo que añade es una distinción que antes no se podía hacer,
y no por falta de sitio donde anotarla: un asiento con `campos: ["country"]` podía ser un
cambio de país o un intento de borrado que el servidor ignoró, y desde fuera eran idénticos.
Ante quien pida cuentas, borrar el dato de una persona y corregirlo no son la misma acción.

La clave se escribe **siempre**, con lista vacía cuando no se vació nada. Si solo apareciera
cuando hay vaciados, su ausencia significaría dos cosas a la vez —una edición que no borró
nada y una edición anterior a este capítulo— y la consulta «qué ediciones borraron datos» no
tendría un criterio único.

## 33.5. El panel

Tres cosas, y la segunda no estaba prevista.

**El vacío viaja.** Los campos de texto ya mandaban `""` y los ingresos ya pasaban por
`ingresosDelFormulario`, que devuelve `null` —el camino del capítulo 24, intacto: cero es una
cifra y diría que la empresa factura cero—. Con el servidor arreglado, esos vacíos empiezan a
tener efecto sin tocar el cliente.

**«Empresa» y «Cargo» dejan de ser obligatorios en la edición.** Las dos columnas son
`nullable` en la tabla, pero los dos campos llevaban `required` en el formulario, así que el
navegador bloqueaba el envío antes de que saliera. El panel era **más estricto que la API sin
decirlo**, y la corrección de una empresa mal tecleada no tenía dónde hacerse por mucho que
el servidor la aceptara. Se les quita el `required` y el asterisco. Los que lo conservan
—nombre y correo— lo conservan porque la tabla los declara `NOT NULL`, que es el único motivo
que vale. El **alta** sigue pidiéndolos: preguntar por un dato al capturarlo y poder retirarlo
después, cuando se comprueba que era falso, son dos decisiones distintas y no tienen por qué
coincidir.

**El apellido borrado a propósito deja de omitirse en silencio.** Aquí había una decisión
anterior que tapaba dos casos muy distintos con la misma solución:

```js
last_name: editForm.last_name.trim() ? editForm.last_name : undefined,
```

El caso que había que tapar es real: las fichas de la página de interés guardan el nombre
entero y los apellidos en blanco, y mandar `""` haría que la edición de **cualquier otro
campo** de esas fichas respondiera 422. El caso que no hay que tapar es el asesor que borra a
propósito un apellido que estaba escrito: omitirlo es precisamente lo que hacía que la
pantalla dijera «Prospecto actualizado» con el apellido intacto.

Se distinguen mirando lo que la ficha tenía:

```js
const obligatorio = (valor, original) =>
  (valor || '').trim() || (original || '').trim() ? valor : undefined;
```

Si había contenido y ahora no, el vacío viaja y el servidor contesta 422 nombrando el campo,
que es lo que hay que enseñar. Si no lo había, no viaja, y la ficha de la página de interés
se sigue pudiendo editar.

Y la cabecera aprende a enseñar los campos vacíos. `{lead.job_title} • {lead.company}` con
los dos vacíos quedaba « • (General)», que parece la ficha rota y no una ficha sin esos
datos; ahora dice «Sin cargo» y «Sin empresa», como el «Sin registrar» que el capítulo 32
puso en la línea de contacto.

## 33.6. Que nada de esto sea decorativo

### Las pruebas

`backend/tests/test_vaciar_un_campo_es_un_cambio.py`, **22 casos**, uno por cada cosa que el
enunciado pedía comprobar:

| Qué | Cómo |
| :--- | :--- |
| Vaciar uno que se puede | Siete campos, uno por prueba, y **releyendo la ficha**: la respuesta la construye el endpoint con el objeto que acaba de tocar y podría enseñar un vacío que no llegó a la base |
| Rechazar uno que no | Cinco campos obligatorios, 422, el nombre del campo en la respuesta y la ficha intacta al releerla |
| No mandarlo y que no cambie | Una edición de un solo campo, comprobando que los otros seis siguen como estaban |
| Vaciar los ingresos | En la columna **y en el vector**: `extract_features_from_lead` tiene que devolver `None`, que es lo que llega al modelo |
| Vaciar un campo que puntúa | `job_title`, con el score antes y después |
| La bitácora | `campos_vaciados` con lo vaciado, y el valor nuevo **ausente** del asiento |
| La lista sale de la tabla | Contra `Lead.__table__` y contra los dos extremos conocidos |
| Un cuerpo mixto no escribe a medias | Ciudad válida + nombre vacío: 422, y la ciudad sin tocar |

Y `LeadDetailModal.test.jsx` gana cinco: el vacío viaja, los obligatorios de verdad siguen
marcados y los otros dos no, el apellido borrado sí viaja, los ingresos van por el camino del
capítulo 24, y tras vaciar la pantalla no vuelve a enseñar el valor anterior.

Se invierte además la prueba de fijación del capítulo 32. Estaba escrita para lo que el
sistema hacía, no para lo que convenía, con el encargo explícito de ponerse roja el día que
alguien lo corrigiera. Es lo que hizo: fue el primer fallo de la primera ejecución.

### La guarda del CI

Un paso nuevo, «Vaciar un campo es un cambio». `configuracion-peligrosa` pasa de 37 a **38
controles**. Mira seis propiedades, no seis casos:

1. El bucle del repositorio no vuelve a llevar `and value is not None`.
2. Sigue habiendo `exclude_unset=True` —el fallo simétrico—.
3. La lista de obligatorios se deriva de `Lead.__table__`, no de un literal.
4. El rechazo mira `model_fields_set`, no todos los campos del modelo.
5. Los textos en blanco de la edición se normalizan, para que el vacío sea uno.
6. El panel no exige `required` en las columnas que la tabla declara `nullable`, y el cliente
   no vuelve a omitir un obligatorio vacío.

La cuarta comprobación del formulario es de las que fallan al revés: si el campo se renombra,
la guarda no encuentra el bloque y **falla diciendo que no puede comprobar lo que ya no
está**, en vez de pasar en verde por no encontrar nada.

### La reintroducción de defectos

Nueve defectos reintroducidos de uno en uno, midiendo si la guarda y la suite se ponen rojas:
**9 de 9 detectados, y los nueve por los dos caminos**. La primera pasada dejó uno —quitar la
normalización de los textos en blanco— detectado solo por la suite; la guarda se amplió con la
quinta comprobación y la segunda pasada salió completa.

## 33.7. Comprobación final

| Qué | Resultado |
| :--- | :--- |
| Suite del backend | **1386 pruebas**, 1 omitida, cobertura **93 %** |
| Suite del cliente | **363 pruebas** en 26 archivos |
| `ruff check .` | Sin avisos |
| `npm run lint` | Sin avisos |
| Guardas del CI | Las cuatro de propiedades, en verde; `configuracion-peligrosa` con 38 controles |
| Reintroducción de defectos | 9 de 9 detectados, por guarda y por suite |
| Migraciones | Ninguna: la corrección no cambia el esquema |

## 33.8. Lo que esta fase no hizo, y por qué

**El alta no normaliza los textos en blanco.** `LeadCreate` sigue guardando `''` si el
formulario de alta manda un campo de texto vacío. Este capítulo es sobre la **actualización
parcial**, que es donde vivía el fallo del punto 24, y extender la normalización al alta es
un cambio del mismo tipo pero en otro camino, con sus propias pruebas y su propia discusión
sobre qué pasa con las integraciones que dan de alta fichas. Queda anotado en §6.4.

**No se tocó el `IntegrityError` del repositorio.** El `except` que envuelve el commit
traduce cualquier violación de integridad a «el correo ya existe», que es lo único que podía
producirla hasta ahora. Con el 422 del esquema delante, un nulo sobre una columna `NOT NULL`
no llega a ese commit; si alguna vez llegara, el mensaje sería equivocado. No se cambia
porque distinguir qué restricción falló obliga a leer el error del motor, y eso es específico
de PostgreSQL y de SQLite por separado. Queda anotado en §6.4.

**No se tocó el vector del modelo ni el alta de campos.** Estaba fuera del encargo y sigue
fuera. Vaciar `annual_revenue` llega al modelo como ausente porque `ingresos_o_ausente` ya lo
hacía; no hubo que cambiar nada para eso, solo comprobarlo.

**Los puntos 6 y 7 de §6.1 siguen abiertos.** Los dos dependen de un sistema externo —una
cuenta de WhatsApp Business que nadie ha conectado, un CRM que mande `event_id`— y sus
motivos están escritos uno por uno en el documento de congelación desde el capítulo 32. No se
tocan aquí, y no por falta de tiempo: escribir el arreglo del 6 es fácil y comprobarlo es
imposible sin el proveedor real, que es una razón distinta y peor.

## 33.9. Qué queda de §6.1

El punto 24 se cierra. Con él, **§6.1 vuelve a no tener ningún punto que este equipo pueda
cerrar por su cuenta**: quedan el 6 y el 7, los dos esperando a alguien de fuera.

Que el 24 existiera un solo capítulo dice algo que conviene no perder. No lo encontró una
prueba, ni una revisión, ni el CI: lo encontró alguien comprobando si el arreglo que acababa
de escribir se podía usar de verdad. El capítulo 32 quitó el país supuesto de la columna, del
esquema, del alta y de la cabecera, con su migración y su guarda, y ninguna de esas cuatro
cosas habría servido de nada para las fichas que la migración no podía tocar. La diferencia
entre haberlo arreglado y no haberlo arreglado estaba en una pregunta que no era parte del
encargo: «y ahora, ¿alguien puede corregir las demás?».
