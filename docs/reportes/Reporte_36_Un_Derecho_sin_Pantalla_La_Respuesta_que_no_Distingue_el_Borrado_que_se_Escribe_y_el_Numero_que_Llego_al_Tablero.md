# Reporte 36 — Un derecho sin pantalla: la respuesta que no distingue, el borrado que se escribe y el número que llegó al tablero

**Capítulo 38** · Interfaz y gobierno del dato · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 1 de octubre de 2026
**Alcance:** pantalla de derechos del titular para administración (consulta, exportación y supresión con su constancia), casilla del aviso de privacidad en el alta manual, contador de «nuevos sin asesor» en el tablero del líder, los tres controles de regresión que vigilan todo ello, y tres defectos que aparecieron al usar el panel —entre ellos un código QR que no leía ningún lector desde el capítulo 27—.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 36 es el capítulo 38. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 38.1. Tres huecos de la misma familia, y por qué entran en un repositorio congelado

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para tres puntos concretos de §6.2 y para ninguno más**, y la pregunta de si tiene derecho a hacerlo hay que contestarla antes de escribir una línea de código.

El criterio está en el §1 del propio documento:

> *«si para explicarlo hay que añadir una frase nueva al README, es funcionalidad; si la frase ya está escrita y el código no la cumple, es un fallo»*

Los tres puntos pasan esa prueba, y conviene verlo uno por uno porque el caso más claro es también el más incómodo:

| Punto | Lo que decía §6.2 | La frase que ya estaba escrita |
| :---: | :--- | :--- |
| **16** | «No hay interfaz para exportar ni para explicar la supresión. Los derechos del titular son API. Funcionan y están comprobados; no tienen pantalla» | El README promete, desde el capítulo 20, *«exportación y supresión del titular comprobadas tabla por tabla»*. Lo que no decía es **quién** podía usarlas |
| **14** | «El alta del panel no ofrece la casilla del aviso de privacidad. La API la admite (`privacy_notice_accepted`); la pantalla, no» | `LeadCreate` declara el campo desde la Fase 15, y la página pública lo pide. El alta del panel lo dejaba sin usar |
| **11** | «El contador de "sin asesor" vive en "Publicaciones". No en el tablero, que es donde el líder mira primero. **Es la nota de usabilidad que el capítulo 28 dio por cerrada sin estarlo**» | El propio §6.2 lo dice: se dio por cerrada |

Los tres son el mismo fallo con tres caras: **una capacidad que existe, está probada y no se puede usar desde donde hay que usarla**. No hay endpoint nuevo, ni tabla nueva, ni migración, ni campo nuevo en ningún esquema. El servidor de este capítulo es, byte a byte, el del capítulo 37 más un archivo de pruebas.

El punto 16 merece una frase más, porque es el que de verdad dolía. Un derecho de acceso y supresión que solo se puede ejercer construyendo una petición HTTP con un token de líder comercial no es un derecho de la persona: es un derecho de quien sabe usar `curl`. El sistema sabía responder «¿qué datos tenéis de mí?» desde la Fase 14 y nadie dentro de PluriOne podía preguntárselo.

### Lo que este capítulo decidió NO abrir

De los ocho puntos de §6.2, cuatro siguen abiertos y se quedan abiertos a propósito: el **9** (las integraciones no atribuyen la ficha a una campaña), el **10** (la asignación automática es solo para las `HOT`), el **12** (el reparto de la cartera de una baja es todo o nada) y el **15** (no hay pantalla para configurar integraciones). Los cuatro exigen decidir comportamiento nuevo del servidor, y eso es funcionalidad, no corrección. §3, §4 y §5 no se tocan.

---

## 38.2. La pantalla no añade lógica: añade lo que faltaba alrededor

`frontend/src/components/DerechosDelTitular.jsx` pide tres cosas que ya existían:

| Paso | Qué llama | Desde cuándo |
| :--- | :--- | :--- |
| Encontrar a la persona | `GET /api/v1/leads?search=<correo>` | Fase 1 |
| Ver qué consta y reunirlo | `GET /api/v1/leads/{id}/exportar` | Fase 14 (R-11) |
| Suprimir | `DELETE /api/v1/leads/{id}` | Fase 1, reescrito en la 14 |

Lo que añade es el alrededor, y es casi todo el capítulo:

1. **Que se diga qué hace cada acción antes de ofrecerla.** Las tres descripciones están en un `<dl>` arriba, visibles mientras se escribe el correo. No en un `confirm()` delante del botón: un «¿seguro?» delante de un borrado irreversible llega tarde, porque quien lo lee ya decidió.
2. **Que la consulta sea la entrega.** La exportación se pide en el paso de consultar, no al pulsar «Descargar». Enseñar en pantalla un resumen de los datos de una persona **ya es entregárselos** a quien mira, así que el asiento `lead.exportar` tiene que existir desde ese momento. «Descargar» no vuelve a pedir nada: guarda en un archivo el documento que ya está en memoria.
3. **Que el borrado se escriba.**
4. **Que la pantalla diga lo que no hace.**
5. **Que un asesor no la alcance.**
6. **Que haya constancia de la supresión**, y que esa constancia diga de dónde salen sus números.

---

## 38.3. La respuesta que no distingue, que es la propiedad que más fácil se pierde

La consulta tiene **una sola forma de contestar**. Cuando no hay ficha, no responde un error, no dice «no encontrado» y no dice «esa persona no está»: responde el mismo panel, con el mismo encabezado, sin nada dentro y con esta frase:

> *No consta ninguna ficha con esta dirección.*

Y debajo, el motivo escrito para quien atiende la petición:

> *Esta respuesta es la misma para una dirección que nunca entró y para una cuya ficha ya no está, y lo es a propósito: distinguirlas convertiría esta pantalla en una forma de averiguar quién figura en la base consultando correos uno a uno.*

No es cortesía. Es la tercera vez que este proyecto toma la misma decisión, y las dos anteriores están escritas en el código:

* **El 404 de la cartera ajena** (capítulo 15). Un prospecto que existe y es de otro responde exactamente igual que uno que no existe, porque lo contrario permite recorrer identificadores y dibujar la cartera completa sin ver un solo dato.
* **La huella con clave de la bitácora** (capítulo 14). El asiento del borrado no guarda el correo: guarda un HMAC con `SECRET_KEY`. Así, quien **ya conoce** un correo puede comprobar que se suprimió, y quien lee la bitácora no averigua a quién.

Una pantalla que dijera «suprimida el 1 de octubre» echaría a perder la segunda de un plumazo: bastaría una lista de correos y un rato para saber quién pidió el borrado de sus datos, que es precisamente la información que el HMAC existe para no dar. Por eso, al terminar una supresión, el estado de la pantalla se deja **exactamente** en la forma vacía:

```jsx
// La ficha ya no está: la consulta se deja en su forma vacía, que es la misma que
// habría contestado si esta dirección no hubiera entrado nunca.
setConsulta({ correo: suprimido, ficha: null, documento: null });
```

Esa línea es media línea, y es la que un cambio bienintencionado se lleva por delante sin que nada falle: añadir `suprimida: true` para poder enseñar un mensaje más útil no rompe ninguna prueba que no esté escrita a propósito. Hay dos escritas a propósito —una en la suite del cliente y una en el control 46 del CI—, y la de la suite es esta:

```js
it('después de suprimir, la pantalla contesta lo mismo que si nunca hubiera entrado', ...)
```

### La consulta en vacío no deja asiento, y también es a propósito

La pantalla promete que *«cada petición queda en la bitácora con quién la pidió y cuándo»*, y hay que decir con precisión a qué llama petición: a las que **tratan datos**. Consultar un correo que consta deja `lead.exportar`; suprimir deja `lead.eliminar`. Buscar un correo que no consta no deja nada, porque el único dato personal que habría que anotar para dejar el asiento es **el correo de alguien de quien el sistema no guarda nada**. Registrarlo sería crear el dato en vez de contestar sobre él.

Está comprobado por el lado del servidor, que es donde se puede comprobar de verdad:

```python
def test_consultar_un_correo_que_no_consta_no_escribe_nada_en_la_bitacora(...):
    client.get(LEADS, headers=lead_headers, params={"search": "nadie@ejemplo.com"})
    assert db_session.query(AuditLog).count() == 0
```

---

## 38.4. La igualdad del correo la decide el cliente, y es el defecto más caro que no ocurrió

Para resolver un correo a una ficha, la pantalla usa el listado, que es el único sitio que sabe buscar y el único que aplica el alcance de cartera. Pero el `search` del listado es un `LIKE` sobre cinco columnas:

```python
search_pattern = f"%{filters.search.lower()}%"
or_(
    func.lower(Lead.first_name).like(search_pattern),
    func.lower(Lead.last_name).like(search_pattern),
    func.lower(Lead.email).like(search_pattern),
    func.lower(Lead.company).like(search_pattern),
    func.lower(Lead.job_title).like(search_pattern),
)
```

Está bien que lo sea: es el buscador de la matriz de prospectos, donde escribir media palabra tiene que encontrar. Lo que no se puede es usarlo tal cual para exportar o para borrar. Buscar `ana@ejemplo.com` trae también a `diana@ejemplo.com`, y quedarse con la primera fila de la respuesta significa **entregar los datos de otra persona, o destruirlos**.

Por eso la igualdad se comprueba en el cliente:

```js
return fichas.find((ficha) => (ficha.email || '').trim().toLowerCase() === buscado) || null;
```

Es el mismo cuidado que el servicio de derechos ya tenía al rastrear el correo dentro de las cargas del CRM —un `LIKE` para no leer la tabla entera, y una comparación exacta sobre los valores para no llevarse a «diana» al buscar a «ana»—, y la prueba que lo cubre usa el mismo escenario de dos correos que se contienen.

Lo delicado de este defecto es **cuándo se habría notado**: con una sola persona en la base, quedarse con la primera fila funciona. Funciona en la demo, funciona en la prueba manual, funciona el primer mes. Falla el día que entra alguien cuyo correo contiene el de otro, y lo que falla es un borrado irreversible.

Hay una segunda mitad, menos vistosa y del mismo tipo. La búsqueda pide `limit: 200`, que es el tope que el endpoint admite, y no el 50 por omisión:

```js
// El tope de página del servidor. Un `LIKE` sobre un dominio corriente puede traer
// muchas filas, y la que interesa no tiene por qué venir primera: se pide el máximo
// que el endpoint admite y se busca la igualdad dentro.
```

Con 50, un dominio corriente —todas las fichas de `@unaempresa.com`— podía dejar fuera de la página la ficha buscada, y la pantalla habría contestado «no consta» sobre una persona que está. El fallo más incómodo de los dos: no entrega datos de nadie, pero **le dice a una persona que el sistema no tiene nada suyo cuando lo tiene**.

### Y el servidor fija su parte

Que el listado busque por coincidencia parcial es una propiedad del servidor de la que depende una decisión del cliente, así que está escrita como prueba del servidor y no solo como comentario:

```python
def test_la_busqueda_por_correo_trae_tambien_a_quien_solo_se_parece(...):
    assert correos == [ana.email, diana.email], (
        "El listado busca por coincidencia parcial; si dejara de hacerlo, la igualdad "
        "exacta del cliente seguiría siendo correcta, pero este aviso ya no haría falta."
    )
```

Y otra fija lo que no es obvio: **el alcance de cartera también acota esa búsqueda**. Podría parecer que buscar por un correo no revela nada, porque quien pregunta ya lo tiene en la mano. Revela dos cosas —que esa persona está en el sistema, y toda su ficha—, y las dos son de la cartera de otro. Funciona porque el filtro vive en el repositorio y no en el endpoint, que es lo que hace que valga para esta búsqueda sin que nadie se acordara de ella al escribirla.

---

## 38.5. El borrado se escribe, y la constancia dice de dónde salen sus números

El botón de suprimir no está disponible hasta que se escribe **el correo completo** en un campo aparte:

```js
const puedeSuprimir = escrito.trim().toLowerCase() === (consulta?.correo || '\u0000');
```

El centinela `\u0000` no es adorno: comparar con `''` habría hecho que el botón naciera habilitado cuando no hay consulta.

El motivo de pedir que se escriba, y no una casilla ni un «¿seguro?», está en el código:

> *Una confirmación que se resuelve con un clic en el mismo sitio donde estaba el ratón no es una confirmación: es un segundo botón. Escribir la dirección obliga a leer de quién se está hablando.*

### La constancia, y el número que se quitó

`DELETE /leads/{id}` responde **204 sin cuerpo**. Lo que salió de cada tabla queda en el asiento `lead.eliminar`, junto a la huella con clave del correo. Así que la constancia que la pantalla descarga —`constancia-de-supresion-<correo>.json`— se arma con los recuentos del documento de acceso que el servidor construyó segundos antes, y **lo dice con todas sus letras**:

```json
"procedencia_de_los_recuentos":
  "Del documento de acceso generado inmediatamente antes de suprimir, no de la propia
   supresión: el servidor responde al borrado sin cuerpo. El registro de lo que salió de
   cada tabla está en la bitácora, en el asiento «lead.eliminar» de esta fecha, con una
   huella con clave del correo en lugar del correo."
```

Esto se podía haber disimulado. Nadie iba a notar la diferencia leyendo el archivo, y un campo `registros_borrados: 18` habría quedado mejor. Es justo lo que no se hace: la constancia dice de dónde salen sus números y nombra el asiento donde está el registro que vale.

Por el mismo motivo **se quitó un número** que la primera versión del bloque de confirmación enseñaba. Decía:

> *Se borran la ficha y los **8 registros** de la lista de arriba.*

El número sumaba los recuentos de la tabla, y entre ellos están los `tratamientos_registrados`: los asientos de la bitácora sobre esta persona. Y esos **no se borran**: se les retiran los datos personales y se quedan, porque «quién dio de alta a esta persona y cuándo» sigue siendo cierto después de suprimirla. Un «se borrarán 23 registros» que en realidad borra 18 y limpia 5 es peor que no dar número, porque el que da no es el que ocurre, y además acaba en la constancia de la persona. El texto dice ahora qué se borra y qué no, sin total, y hay una prueba que impide que el total vuelva:

```js
it('no promete un número de registros borrados', ...)
expect(screen.queryByText(/\d+ registros/)).not.toBeInTheDocument();
```

### Un hallazgo del mismo sitio: `fuera_de_la_base` no es una sección

La tabla «Qué guarda el sistema» no enumera secciones a mano: recorre el documento del servidor y enseña las que son listas, con su recuento. Es el mismo criterio con el que el asiento `lead.exportar` anota qué se entregó, y la razón es la de siempre: una tabla nueva que entre en el mapa de la supresión aparece en la pantalla el mismo día, sin que nadie se acuerde de añadirla.

La primera versión lo hacía con `Array.isArray(valor)` a secas, y en la pantalla salió esta fila:

```
fuera de la base        3
```

`fuera_de_la_base` también es una lista, y lleva dentro tres **párrafos** que explican qué copias existen donde el sistema no llega. La fila no decía que hubiera tres registros de la persona en ninguna parte: decía que hay tres avisos escritos. Lo encontró la prueba que compara el conjunto exacto de filas con el conjunto de listas del documento, y el arreglo no fue una excepción por nombre —`if (clave !== 'fuera_de_la_base')` habría caducado con la siguiente lista de texto— sino una condición sobre el contenido:

```js
.filter(([, valor]) => Array.isArray(valor) && valor.every((e) => e && typeof e === 'object'))
```

Una lista de frases no es una tabla de registros. Dicho así, una sección nueva de registros entra sola y una nueva de texto se queda fuera sola.

---

## 38.6. Lo que la pantalla dice que no hace

El §5.3 de la congelación se titula «Suprimir aquí no suprime en el CRM», y hasta este capítulo esa advertencia vivía en dos sitios: un documento de trabajo futuro y el campo `fuera_de_la_base` del JSON de exportación. Ninguno de los dos lo lee quien atiende una petición de borrado.

Ahora está delante de los ojos, dentro del bloque de confirmación:

> ***Suprimir aquí no suprime en el CRM** ni en LinkedIn, Calendly o WhatsApp. Si la persona pidió el borrado completo, hay que pedirlo también allí; y mientras exista allí, una nueva entrega volvería a crear la ficha aquí.*

La segunda mitad es la que no es obvia y la que cambia lo que hay que hacer: no es solo que los datos sigan allí, es que **volverán**. Y el aviso vuelve a aparecer después, en el mensaje de éxito, porque es ahí donde alguien podría irse creyendo que terminó.

La lista completa de lo que no se alcanza no se escribe en la pantalla: se enseña tal como la manda el servidor (`fuera_de_la_base`), que es quien sabe qué copias existen —los volcados de PostgreSQL con sus días de retención, los CSV de reentrenamiento, los sistemas de origen—. Dos listas de lo mismo se habrían desincronizado en el primer cambio de política de copias.

---

## 38.7. La casilla del aviso de privacidad: lo delicado no es que exista

El punto 14 se cierra con quince líneas de JSX, y ninguna de las tres decisiones que lleva dentro es sobre esas quince líneas.

**Nace sin marcar.** Marcada por omisión guardaría una aceptación que nadie dio, con la fecha de ahora al lado, y esa fecha la volvería **indistinguible de las de verdad**. Es exactamente el error del país que el capítulo 32 quitó de cuatro sitios, y de los ingresos que el 24 dejó de inventar: lo que nadie dijo no se escribe. La diferencia es que aquí el dato supuesto no es un atributo comercial, es un consentimiento.

**Sin marcar se envía `false`, no se omite el campo.** Omitirlo funcionaría —el esquema declara `privacy_notice_accepted: bool = False`— y sería peor: el cliente dejaría de decir lo que quiere, y el día que el servidor cambiara ese valor por omisión el alta cambiaría de comportamiento sin que nadie tocara esta pantalla. Hay una prueba que lo fija por su forma y no por su valor:

```js
expect(enviado).toHaveProperty('privacy_notice_accepted');
expect(enviado.privacy_notice_accepted).toBe(false);
```

**No es obligatoria para guardar la ficha.** La página pública sí la exige; aquí no, y la diferencia es deliberada. Allí la marca la persona; aquí la marcaría el asesor por ella. Obligarla garantizaría que se marque siempre, que es justo lo contrario de que signifique algo. Es el §5.2 de la congelación —«Aceptar el aviso de privacidad no es condición para crear la ficha»—, que sigue siendo una decisión no técnica y sigue sin tomarse.

Y la fuente que se anota dice **quién** la marcó: `manual` desde el panel, `pagina_de_interes` desde la página pública, `linkedin_lead_gen` desde el conector. Si las tres escribieran lo mismo, la respuesta de acceso del titular no podría decir la diferencia, y la diferencia es lo que hace que la constancia valga algo.

El texto de la pantalla explica las dos ramas, porque la segunda no se adivina:

> *Al marcarla queda registrada la fecha y la hora de ahora, con origen «manual». Sin marcarla el campo se queda vacío: «no consta» y «no aceptó» no son lo mismo, y la ficha no supone ninguno de los dos.*

---

## 38.8. El contador que llegó al tablero sin irse de «Publicaciones»

El punto 11 lleva abierto desde el capítulo 25 y el propio §6.2 dice algo más duro que «está pendiente»: *«es la nota de usabilidad que el capítulo 28 dio por cerrada sin estarlo»*.

El contador se ha movido a su propio componente, `ContadorSinAsesor`, y se monta en dos sitios: el tablero y «Publicaciones». No se copió el bloque, y el motivo es la avería del capítulo 27: cuando el número y la lista se calculaban en dos sitios, **el número decía tres y en la lista había una sola marca**, y el líder no tenía manera de saber cuál de los dos mentía. Dos copias del texto se habrían desincronizado en el primer cambio de redacción, con el mismo resultado a menor escala.

Tres detalles que no son obvios:

**`null` no es cero.** «No se ha preguntado» y «no hay nadie esperando» son respuestas distintas, y la segunda es una afirmación: un cero inventado le dice al líder que no tiene nada que repartir. El componente lo comprueba explícitamente —`total === null || total === undefined`— y no por veracidad, que haría desaparecer un cero real y convertiría una falta de respuesta en un cero. Y el efecto de `App` tiene su propio `catch`: si el servidor no contesta el contador, el tablero se dibuja igual y el aviso **no aparece**.

**Se pide solo a quien dirige la cartera.** El endpoint es de dirección, así que pedirlo con la cuenta de un asesor se traga un 403 y llena la bitácora de accesos denegados que nadie provocó a propósito. Es el mismo criterio que «Publicaciones» ya seguía.

**Lleva a donde se reparten.** El botón «Ver y repartir» cambia a la matriz de prospectos, que es donde cada ficha que espera lleva su marca «Nuevo, sin asesor» —decidida por el servidor, `esperando_asesor`, con la misma condición que cuenta el contador— y donde se abre la ficha para asignarla. Dentro de «Publicaciones» el botón no se dibuja: quien está ahí vino a gestionar publicaciones, y el salto le sacaría de lo que estaba haciendo.

De paso, `App.jsx` tenía la comparación `currentRole === 'Sales_Lead' || currentRole === 'System_Admin'` escrita tres veces y este capítulo necesitaba una cuarta. Pasó a ser un `esDireccion` único, porque de esa condición cuelga **qué se le pide al servidor**, y una de las cuatro que se quedara atrás pediría datos que el servidor niega.

---

## 38.9. Los dos controles nuevos, y los veintidós defectos que se les reintrodujeron

`configuracion-peligrosa` pasa de **45 a 48 controles**. Los dos de esta sección —el 46 y el 47— vigilan los tres huecos de §6.2; el 48 sale del §38.10 y se describe allí. Los tres leen los archivos **sin sus comentarios**, y eso no es un detalle de implementación: es la lección que el capítulo 37 pagó tres veces. `grep certifi` disparaba con los cinco párrafos que explican por qué no se usa `certifi`. Cuanto mejor documentado está el motivo de no hacer algo, más fácil es que un control escrito a base de palabras crea que se está haciendo.

**El 46, «La pantalla de derechos no es un oráculo ni borra sin que se escriba»**, vigila seis familias de propiedades: que tras suprimir la pantalla vuelva a la forma vacía y que la frase de «no consta» sea **una sola**; que no aparezcan en el archivo las frases que distinguen («ya se suprimió», «no existe»); que la búsqueda compare la igualdad del correo, no se quede con la primera fila y pida la página entera; que el borrado dependa de lo escrito; que el aviso del CRM siga ahí; que las secciones se deriven del documento y distingan registros de frases; y que la pantalla mire el rol y viva **solo** dentro de la pestaña de administración.

**El 47, «El alta no supone el consentimiento y el contador llegó al tablero»**, vigila que la casilla exista, se envíe, nazca sin marcar y **no** sea obligatoria; y que el contador esté en el tablero y en «Publicaciones», enlazado a repartir, pedido detrás de la guarda del rol, y distinguiendo `null` de cero.

Hay la misma división de trabajo que en el capítulo 37: **la suite comprueba el comportamiento** —monta la pantalla, escribe en los campos, pulsa los botones y lee lo que sale— y **el control comprueba la estructura**, es decir, las líneas que, borradas por descuido, dejarían la prueba pasando y la propiedad perdida.

### La comprobación de que los controles sirven

Un control que no se ha visto en rojo es una conjetura. Se escribió un arnés que reintroduce cada defecto, corre el control extraído **del propio YAML** y restaura el archivo:

```
  control 46  rojo  OK   tras suprimir se recuerda que se suprimió
  control 46  rojo  OK   la frase de «no consta» cambia y deja de ser única
  control 46  rojo  OK   la pantalla cuenta que la ficha ya se suprimió
  control 46  rojo  OK   la búsqueda se queda con la primera fila del LIKE
  control 46  rojo  OK   la búsqueda pide solo la primera página
  control 46  rojo  OK   suprimir deja de exigir lo escrito
  control 46  rojo  OK   el botón de suprimir deja de mirar la confirmación
  control 46  rojo  OK   desaparece el aviso de que el CRM no se entera
  control 46  rojo  OK   las secciones dejan de distinguir registros de frases
  control 46  rojo  OK   las secciones se escriben a mano
  control 46  rojo  OK   la pantalla se dibuja sin mirar el rol
  control 46  rojo  OK   la pantalla deja de montarse
  control 46  rojo  OK   la pantalla se monta fuera de administración
  control 47  rojo  OK   la casilla del aviso nace marcada
  control 47  rojo  OK   el alta deja de mandar la casilla
  control 47  rojo  OK   la casilla se vuelve obligatoria
  control 47  rojo  OK   el contador desaparece del tablero
  control 47  rojo  OK   el contador del tablero deja de llevar a repartir
  control 47  rojo  OK   el contador desaparece de «Publicaciones»
  control 47  rojo  OK   el contador confunde «no se preguntó» con cero
  control 47  rojo  OK   el tablero deja de preguntar el contador
  control 47  rojo  OK   el tablero se lo pide también a un asesor

Los 22 defectos reintroducidos ponen su control en rojo.
```

### Dos cosas que el arnés enseñó y que no eran los controles

**La primera pasada dijo 13 de 13 y era mentira.** El arnés lanzaba el control con una ruta relativa y el proceso hijo corría en la raíz del repositorio, donde ese archivo no está: Python salía con código 1 por «no puedo abrir el archivo», y el arnés leía el 1 como «el control disparó». **Los trece aciertos eran trece fallos de arranque.** El arnés lleva ahora una comprobación de que el hijo no escribió nada en `stderr`, que es la diferencia entre «el control dijo que no» y «el control no llegó a correr».

Tiene su moraleja, y es la del propio capítulo: un arnés que verifica guardas es código sin verificar. Lo que lo destapó fue mirar **qué mensaje** daba cada disparo en vez de contar los que disparaban.

**Y dos de los defectos no eran defectos de lo que decían ser.** El que debía mover la pantalla fuera de administración la borraba, así que disparaba la comprobación de «se monta en más de un sitio o en ninguno» y no la de «ya no vive dentro de administración». El que debía escribir las secciones a mano dejaba un `Object.entries` de adorno en el reemplazo, y el control —que buscaba esa cadena— lo daba por bueno. Los dos se reescribieron para ser el defecto que nombran, y el segundo fue además un disparo en falso al revés: el control habría pasado por alto una lista escrita a mano que conservara la llamada por casualidad.

---

## 38.10. Lo que apareció al usarlo: un QR que no leía nadie, un botón mudo y un enlace muerto

Hasta aquí, el capítulo. Lo que sigue apareció **levantando la pila y usando el panel con un teléfono en la mano**, que es la costumbre escrita desde el capítulo 32 y la que ha encontrado todo lo que ninguna lista preveía. Esta vez encontró tres cosas, y la primera llevaba once capítulos rota.

### a) El código QR no lo leía **ningún** lector, y la suite estaba verde

Es el punto 17 de §6.3 cumpliéndose: *«el código QR no se ha escaneado con un teléfono… es lo primero que habría que hacer antes de repartir material impreso»*. Se escaneó. No detectó nada —ni un intento de lectura fallido: la cámara no veía que allí hubiera un código—.

**Lo que estaba mal era una línea, y no era la del dibujo.** Un QR se lee en dos tiempos: primero los quince bits de la *información de formato*, que dicen con qué nivel de corrección y con **qué máscara** está hecho, y solo después los datos. Sin esos quince bits no se sabe qué máscara quitar, así que no se puede leer un solo bit de nada.

Esos quince bits se escribían con la fila y la columna cambiadas de sitio. El resto del archivo trabaja en `modulos[fila][columna]`, y el bucle ponía el primer bit en `modulos[8][0]` —fila 8, columna 0— cuando la norma lo quiere en la **columna** 8, fila 0.

Todo lo demás estaba bien, y conviene decirlo porque es lo que hace el fallo tan difícil de ver: leyendo la matriz vieja con un lector estándar y quitando la máscara **a mano**, los codewords salen exactos:

```
40 44 84 f4 c4 10 ec 11 ec 11 …
└┬┘ └──┬──┘ └──────┬──────┘
 │     │           └ 'H' 'O' 'L' 'A', relleno ec/11
 │     └ longitud 4
 └ modo binario
```

Datos, Reed-Solomon, zigzag y máscaras: correctos. Lo único que faltaba era poder saber **qué** máscara quitar.

**Por qué ninguna de las diecinueve pruebas del QR lo vio.** Porque todas miden propiedades **simétricas respecto de la diagonal**: tres localizadores en esquinas simétricas, dos patrones de sincronismo que son uno el reflejo del otro, separadores simétricos, y las dos bandas del formato —la fila 8 y la columna 8— que `matrizBase` reserva a la vez. Transponer no rompe ninguna. Es una familia entera de pruebas ciega a un error concreto, y la cabecera del archivo lo decía sin saber lo que decía:

> *«estas pruebas no leen el código… Queda pendiente escanear un código impreso con un teléfono, que es lo único que prueba que una cámara real lo lee.»*

Había **un** módulo que podría haberlo delatado: el oscuro fijo de `(lado-8, 8)`, que el bucle pisaba con el bit 7 de la segunda copia. Hay una prueba que lo vigila —`expect(matriz[lado - 8][8]).toBe(1)`— y **pasaba por casualidad**: en los enlaces que la suite usa, ese bit valía 1. Al reintroducir el defecto hoy, esa prueba sigue en verde. Es la definición de una prueba que no prueba.

**El arreglo y la prueba que sí lo ve.** El arreglo son seis líneas con los índices en el orden de la norma. La prueba es un **lector mínimo escrito dentro de la suite** —no una biblioteca: la cadena de suministro del cliente se mantiene corta por la misma razón por la que el generador está escrito a mano— que hace lo que hace una cámara y en el mismo orden: lee los quince bits de donde la norma los nombra, comprueba su BCH, saca la máscara, recorre el zigzag y devuelve el texto. Cinco pruebas nuevas; con el defecto reintroducido, cuatro se ponen en rojo.

Su alcance está acotado y escrito: el recorrido completo se hace sobre la **versión 1**, que no tiene patrones de alineación ni reparto en bloques, de modo que el mapa de módulos de función es exacto sin reimplementar medio generador. Sobre un enlace de verdad —versión 6— se lee la información de formato, que es idéntica en todas las versiones y es donde estaba el fallo.

Durante el diagnóstico sí se usó un lector independiente (`jsQR`, fuera del repositorio, en un directorio temporal) para confirmar que el problema no era el tamaño del dibujo sino el contenido. Antes del arreglo no leía ninguno de los cuatro casos; después, los cuatro.

### b) El botón de la vista previa no hacía nada y no decía por qué

En la vista previa de la página de interés, el botón «Quiero que me contacten» está **desactivado**, y debe estarlo: desde ahí no se envía. El motivo se decía en un `role="note"` encima del título.

El formulario mide varias pantallas de alto dentro de un marco de 375 px. Quien baja hasta el botón tiene ese aviso cuatrocientos píxeles más arriba y fuera de la vista; pulsa, y no pasa nada —un botón desactivado ni siquiera dispara el evento, así que no hay ni un parpadeo—. El aviso era verdad y no servía.

La explicación va ahora **pegada al botón**, y el botón la señala con `aria-describedby` para quien no ve la pantalla. El botón sigue desactivado.

### c) El enlace y el QR de una dirección que no responde se ven igual que los buenos

El tercero no es un defecto del código: es lo que faltaba decir. Con el túnel caído, «Publicaciones» ya avisa arriba —*«La dirección pública no responde. Quien abra un enlace de estas publicaciones no llega a ninguna parte»*—, y ese aviso se queda fuera de la vista en cuanto se despliega una publicación para compartirla.

El panel de compartir es justamente donde alguien **actúa** sobre el enlace: lo copia, lo reparte, lo imprime. Y un código QR de una dirección muerta **se ve exactamente igual que uno bueno**; el único momento en que se descubre es con el teléfono delante del papel ya impreso. Lleva ahora su propio aviso, que además dice la mitad que no es obvia: que el código no está mal, que lo que no responde es el otro extremo. Sin esa frase, lo razonable sería volver a generar el QR.

Distingue `responde === false` de `responde === null`: «no se ha comprobado» es lo que contesta un despliegue sin túnel delante, y avisar entonces sería inventar una avería.

### Qué afecta cada una

| | Qué deja de funcionar | Qué **no** toca |
| :--- | :--- | :--- |
| **QR transpuesto** | Todo código QR generado desde el panel, desde el capítulo 27. Nadie podía llegar por un QR, y el informe de la publicación lo contaba como «cero visitas», indistinguible de «nadie lo escaneó» | El enlace de texto, los botones de compartir, la página de interés y el registro de prospectos: ninguno pasa por el QR |
| **Botón mudo** | Nada del sistema: es la vista previa, y no enviar es su comportamiento correcto. Lo que fallaba era la explicación | El envío real desde el enlace público |
| **Dirección caída** | **Todo lo público a la vez**: el enlace de los posts, el QR y la página de interés. Quien pulse no llega, y los prospectos que habrían llegado por ahí no existen | El panel entero: sesión, scoring, prospectos ya registrados, bandeja «Hoy», informes. Es la puerta de entrada la que está cerrada, no el sistema |

La tercera no se arregla con código: la dirección del túnel gratuito **cambia en cada arranque** (§6.4, punto 28), hay que copiarla a `PUBLICACIONES_URL_BASE` y volver a levantar la pila. Lo que este capítulo añade es que se diga donde se actúa, no solo arriba.

---

## 38.11. Lo que este capítulo NO hizo

* **No se escribió ni una línea de lógica de supresión.** El mapa de tablas, el rastreo del correo en las cargas del CRM, el retirado de datos de la bitácora y la huella con clave son los del capítulo 20, intactos. El servidor no cambió: solo ganó un archivo de pruebas.
* **No se añadió ningún endpoint.** Se consideró uno —una búsqueda por correo exacta, que habría hecho innecesaria la comparación del cliente— y se descartó: es API nueva en un repositorio congelado, y la comparación en el cliente resuelve lo mismo con una línea y una prueba.
* **No se añadió un filtro «sin asesor» al listado.** El contador del tablero lleva a la matriz, donde las fichas que esperan están marcadas, pero la lista **no** se filtra por esa condición. Filtrarla exigiría un parámetro nuevo en el servidor; hacerlo en el cliente sobre una página de cincuenta habría reproducido la discrepancia del capítulo 27 —un número que dice siete y una lista con dos marcas—. Queda escrito en §6.2.
* **No se hizo obligatoria la casilla del aviso de privacidad** (§5.2). Sigue siendo una decisión no técnica.
* **No se tocaron los puntos 9, 10, 12 ni 15 de §6.2**, ni nada de §3, §4 o §5.
* **No se añadió ninguna biblioteca.** `Blob`, `URL.createObjectURL` y un `<a download>` son del navegador; la descarga no sale a la red.
* **No se cambió el 204 de la supresión.** Devolver los recuentos en el cuerpo habría hecho la constancia más exacta y habría tocado un contrato probado. La constancia dice en su lugar de dónde salen sus números.

---

## 38.12. Qué queda abierto después de esto

1. **La pantalla no alcanza a quien no tiene ficha.** Un mensaje de WhatsApp de un número desconocido, o una ingesta del CRM que falló antes de crear el alta, son datos de una persona que viven en la bandeja «Sin asociar» y en los registros de ingesta revertida. La exportación los incluye **cuando hay ficha** —los busca por correo y por teléfono—, pero sin ficha la pantalla contesta «no consta». Es correcto para lo que la pantalla dice y es incompleto para lo que la persona pregunta.
2. **La lista no se filtra por «sin asesor».** El enlace del tablero lleva a la matriz, no al subconjunto que el contador cuenta. Con cartera pequeña basta; con cartera grande hay que buscar las marcas a mano.
3. **Nadie ha atendido una petición de derechos de verdad con esta pantalla.** Las pruebas ejercitan los tres caminos, pero el recorrido con una persona delante sigue siendo el punto 18 de §6.3. Lo que sí se puede decir es que la pantalla pasa el nivel AA de WCAG 2.1 en sus tres estados —formulario, resultado y confirmación del borrado—, medido por `axe` desde la propia suite. El ensayo cronometrado del guion de la demo **no** la recorre: la demo cuenta el camino del post al prospecto puntuado, y esta pantalla no está en él.
4. **La constancia es un JSON.** Sirve para adjuntarla a una respuesta y para archivarla; no es un documento con formato que se pueda enviar tal cual a quien lo pidió. Convertirla en uno es trabajo de maquetación, no de ingeniería, y no se ha hecho.
5. **Suprimir sigue sin suprimir en el CRM** (§5.3). Ahora la pantalla lo dice dos veces, que es todo lo que puede hacer el software: lo que falta es un procedimiento para el otro lado, y eso no se decide aquí.
