# Reporte 39 — El mínimo que no medía nada: un blanco en cinco puertas, la regla que solo tenía una tabla y el espacio que duplicaba un evento

**Capítulo 41** · Validación de entrada y datos · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 2 de octubre de 2026
**Alcance:** el texto en blanco que el alta de una ficha guardaba y la edición normalizaba (§6.4 punto 25), el orden entre una comprobación de longitud y el recorte que la dejaba midiendo otra cadena, la regla de los campos sin los que una fila no existe —que el capítulo 33 derivó de la tabla y escribió para una sola—, el sobre del webhook del CRM, una migración que iguala los vacíos que ya hay en la base y cuenta los que no puede tocar, un control de regresión con treinta y tres defectos reintroducidos, y dos arreglos de este mismo capítulo que el arnés demostró que no arreglaban nada.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 39 es el capítulo 41. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 41.1. Un resto menor, y lo que apareció al ir a medirlo

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para un punto de §6.4 y para ninguno más**: el **25**, que el capítulo 33 encontró, dejó escrito en su propio docstring y no pagó.

El punto decía:

> *«El **alta** no normaliza los textos en blanco: `LeadCreate` guarda `''` donde la edición guarda `NULL` desde el capítulo 33. Es el mismo arreglo en otro camino, y afecta también a las integraciones que dan de alta fichas, así que tiene su propia discusión.»*

Lo primero que se hizo fue medirlo, y la frase resultó estar **corta en tres sitios**:

| Lo que el punto decía | Lo que había |
| :--- | :--- |
| El alta guarda `''` donde la edición guarda `NULL` | Cierto, en nueve campos. Pero el alta y la edición no son dos puertas: son dos de **cinco**, y cada una respondía algo distinto a «qué es un vacío» |
| — | El alta de una **cuenta** declaraba un mínimo de dos caracteres y recortaba **después** de comprobarlo: dos espacios pasaban el mínimo y se guardaban como `''` en una columna `NOT NULL`, y `' A '` se guardaba como una sola letra |
| — | La regla que el capítulo 33 escribió para que un vacío sobre una columna obligatoria no llegara al `commit` estaba derivada de la tabla —lo difícil— y escrita dentro del esquema de **una** tabla. Las otras dos ediciones parciales del sistema contestaban **500** |
| — | `crm_platform`, en el sobre del webhook, es el prefijo del identificador con el que un evento del CRM queda marcado para siempre. Nadie lo recortaba, así que «HubSpot» y «HubSpot » eran dos eventos distintos: **el mismo evento entraba dos veces** |
| «Afecta también a las integraciones» | No: las dos integraciones ya normalizaban, con una copia privada de la misma función y otro nombre. Lo que no normalizaba era el **sobre** del webhook, que es otra cosa |

El barrido que se hizo antes de tocar nada, sobre los dieciocho cuerpos de petición de la API:

| De los 61 campos de texto de las entradas | |
| :--- | :---: |
| **Guardaban el blanco tal cual** | **34** |
| Lo normalizaban a vacío | 15 |
| Lo rechazaban | 12 |

Y los doce que lo rechazaban eran **el formulario público y tres listas cerradas**. El formulario público lo rechazaba con una línea de configuración —`str_strip_whitespace=True`— que llevaba ahí desde el capítulo 34 y que no tenía ninguna otra entrada del sistema. **El arreglo estaba escrito desde hacía siete capítulos, en una puerta de cinco.**

### Lo que este capítulo decidió NO abrir

Por escrito: ninguna pantalla, ningún campo nuevo, ninguna columna nueva, ninguna validación de contenido —este capítulo no decide qué es un nombre válido, solo que tres espacios no son un nombre—, y nada de §3, §4, §5, §6.1, §6.2 ni §6.3. Los puntos 26, 37, 38 y 39 de §6.4 siguen abiertos y se dice en §41.14 por qué.

---

## 41.2. El orden: una comprobación y una normalización puestas para no servir

El defecto del capítulo, entero, son estas cinco líneas tal como estaban:

```python
class UsuarioCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)

    @field_validator("full_name")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        return valor.strip()
```

Las dos piezas son correctas. Una dice que un nombre tiene al menos dos caracteres; la otra, que los espacios de los bordes no son parte del nombre. Lo que está mal es el **orden**, y el orden no se elige aquí: Pydantic aplica las restricciones declaradas del campo a lo que **llega** y corre los validadores después. Así que el mínimo medía una cadena y la base recibía otra:

| Lo que se envía | Caracteres medidos | Lo que se guarda | Caracteres guardados |
| :--- | :---: | :--- | :---: |
| `'  '` | 2 ✔ | `''` | **0** |
| `' A '` | 3 ✔ | `'A'` | **1** |
| `'  Ana Pérez  '` | 13 ✔ | `'Ana Pérez'` | 9 |

`users.full_name` es `NOT NULL` porque una cuenta sin nombre no identifica a nadie: es lo que aparece en la bitácora de quién hizo qué, en el reparto de cartera y en cada ficha que esa persona atiende. El esquema que prometía dos caracteres admitía cero.

Lo que hace que esto sea un defecto y no una errata es que **no se ve**. El campo tiene su mínimo declarado, el validador tiene su nombre bien puesto, y nada en el archivo dice que uno corre después del otro. Pydantic tiene dos formas de recortar un texto y solo una ocurre antes de medirlo:

* `str_strip_whitespace=True` en la configuración del modelo recorta **antes** de las restricciones del campo;
* un `field_validator` recorta **después**.

El arreglo es cambiar la primera por la segunda. No se añade ninguna comprobación nueva: **la que ya estaba declarada empieza a funcionar**, y `'  '` choca con el `min_length=2` que el campo siempre tuvo.

### Y el 422 que sale solo es el bueno

Hay una consecuencia que no se buscaba y que vale la pena anotar, porque explica por qué recortar antes es mejor que rechazar aparte. Un blanco recortado a `''` produce un error **del campo**, con su nombre en `loc` y su tipo `string_too_short`, y eso es exactamente lo que el capítulo 40 sabe repartir: el mensaje aparece **debajo del campo**, en castellano y con la etiqueta que la pantalla usa, sin escribir una línea nueva de traducción. Rechazar el blanco en un validador propio habría dado un error de modelo, sin campo, que acaba en el aviso de arriba y no pone rojo a nadie.

Los dos capítulos encajan sin que ninguno de los dos lo hubiera previsto.

---

## 41.3. Cinco puertas, cinco respuestas

Por el sistema entra texto por cinco caminos. Esto es lo que cada uno hacía con un campo en blanco antes del capítulo 41:

| Puerta | Qué hacía con un blanco |
| :--- | :--- |
| **Alta de una ficha** (`LeadCreate`) | Normalizaba `country` y `phone` y guardaba los otros nueve campos de texto tal cual |
| **Edición de una ficha** (`LeadUpdate`) | Normalizaba los siete textos y rechazaba el nulo sobre lo obligatorio (capítulo 33) |
| **Alta y edición de una publicación** | No normalizaba ninguno de los ocho |
| **Alta y edición de una cuenta** | Recortaba el nombre **después** de medirlo (§41.2) |
| **Webhook del CRM** | Normalizaba la carga desde el capítulo 25, y el sobre, nunca |
| **Integraciones** (LinkedIn, formulario web) | Normalizaba todo, con una copia privada de la misma función y otro nombre |
| **Formulario público** | Lo rechazaba, con la línea que nadie más tenía |

La función que decide qué es un vacío existía desde el capítulo 32 —`_texto_o_vacio`, escrita para el país— y se extendió en el 33 a la edición. Nunca se mudó a un sitio compartido, y la cuarta vez que hizo falta ya había dos: `_texto_o_vacio` en los esquemas de la ficha y `_texto` en el servicio de integraciones, el mismo cuerpo con dos nombres. **Las dos eran correctas y estaban de acuerdo por casualidad**, porque quien tocara una no tenía por qué saber de la otra.

Ahora las dos son `app.core.texto.texto_o_nada`, en el módulo donde el capítulo 32 puso ya el teléfono por este mismo motivo. Y la configuración que recorta antes de medir es una constante, `ENTRADA_DE_TEXTO`, para que «¿esta entrada normaliza?» tenga una respuesta que se pueda buscar.

El resultado del mismo barrido, después:

| De los 61 campos de texto de las entradas | antes | después |
| :--- | :---: | :---: |
| Guardan el blanco | 34 | **0** sin inventariar |
| Lo normalizan a vacío | 15 | 31 |
| Lo rechazan | 12 | 21 |

Los once que quedan guardándolo están inventariados con su motivo, y ninguno escribe en una columna desde ahí: cuatro contraseñas, el campo trampa del formulario público, los tres valores del segundo factor, los dos de una actividad —que normaliza el registro, §41.8— y el simulador de scoring, que no persiste nada.

---

## 41.4. La regla que solo tenía una tabla, y los dos 500

El capítulo 33 hizo dos cosas y la segunda es la buena:

1. el repositorio aplica lo que vino, incluido lo que vino vacío;
2. el esquema rechaza con 422 el vacío sobre un campo que la tabla declara `NOT NULL`, **y la lista de esos campos se deriva de la tabla**.

Lo segundo es lo difícil y es lo que hace que el arreglo no caduque. Pero se escribió como una función privada de `app.schemas.lead`, y eso dejó fuera lo demás: el sistema tiene **tres** ediciones parciales —una ficha, una cuenta, una publicación— y las tres aplican lo que vino con un `setattr` en bucle. En las dos que no eran `Lead`, un nulo explícito llegaba al `commit`:

```
PUT /api/v1/campaigns/5   {"name": null}       →  500
PUT /api/v1/users/12      {"full_name": null}  →  500
```

No es el mismo fallo que el del 33 —aquel contestaba 200 a algo que no había hecho, y esto no finge nada—, pero sale del mismo sitio y es peor de lo que un número sugiere: un 500 se anota como un fallo **del servidor** y no del cuerpo que se envió, no dice qué campo fue, y en la pantalla sale como «algo ha ido mal». Quien acaba de borrar el nombre de una publicación no se entera de que lo que no se admite es haberlo borrado.

La derivación se mudó a `campos_sin_los_que_no_existe(modelo)` y la tienen las tres. Y el validador del 33 cambia una palabra: donde miraba `is None` ahora mira `en_blanco`, porque su propio mensaje —«La ficha no existe sin estos campos»— no se aplicaba al único caso en que la ficha de verdad no los tenía.

### Un cero y un falso no son vacíos

`en_blanco` es una función de tres líneas y existe por una razón que no se ve hasta que se rompe: escribirla como `not valor` habría sido natural y habría hecho que **desactivar una cuenta** —`is_active: false`, sobre una columna `NOT NULL`— respondiera «este campo no puede quedar vacío», con un mensaje convincente. Un presupuesto de cero es una cifra y una cuenta desactivada es un estado; los dos son falsos para un `if`. Tiene prueba propia, y el arnés la provocó.

---

## 41.5. Quién decide si un blanco se rechaza o se anula

Una sola regla, y la decide la tabla:

* **columna que admite nulo** → el blanco se normaliza a `NULL`, en todas las puertas;
* **columna que no lo admite** → 422 nombrando el campo, allí donde hay alguien a quien decírselo.

La lista de los textos de una ficha que se anulan está escrita en un sitio y la usan el alta y la edición —tener el alta su propia lista, con nueve campos de diez, es el defecto del punto 25— y lleva prueba contra las columnas de la tabla: tiene que ser exactamente las de texto que admiten nulo **menos dos**, cada una nombrada con su motivo (`phone`, que ya pasa por E.164, y `privacy_notice_source`, que la escribe el servidor).

`leads.source` merece una línea aparte: su columna es `NOT NULL`, no tenía mínimo declarado, y el mismo canal en blanco respondía **201 en el alta y 422 en la edición**. Ahora declara su mínimo en el alta —no en `LeadBase`, de la que heredan las respuestas: un canal en blanco que ya esté en la base convertiría la **lectura** de esa ficha en un error, que es el mismo motivo por el que `LeadResponse` no hereda el mínimo del nombre— y en la edición tiene su propio validador, para que el 422 llegue con el campo y no al aviso de arriba.

---

## 41.6. El blanco que se queda, y por qué

Hay una asimetría que **no** se corrige, y se fija por escrito para que nadie la corrija por error:

```python
# en _crear_prospecto, desde el capítulo 25
first_name=datos.get("first_name", ""),
```

Una ficha que entra por el webhook de un CRM que no mandó el nombre **se queda sin nombre a propósito**. El capítulo 25 quitó de este sistema los «Prospecto», «Sin Apellido» y «Empresa no identificada», y `LeadResponse` perdió el mínimo del nombre justamente para que esas fichas se puedan leer.

La diferencia no es el campo: es si hay alguien a quien decírselo.

* Donde hay una persona delante —el alta del panel, la edición— un campo indispensable en blanco es un 422: puede corregirlo ahora.
* Donde no hay nadie —un CRM que entrega lo que tiene— rechazar el evento perdería el prospecto entero, y un nombre vacío es mejor que uno inventado.

La regla de este capítulo es que el blanco signifique **una sola cosa**, no que se responda lo mismo a todo el mundo.

---

## 41.7. El sobre que deduplicaba

`crm_platform` es un campo del sobre del webhook, con un valor por defecto y un máximo de cincuenta caracteres, y es el valor que más lejos llega de todo el cuerpo:

* es el canal de la actividad (`lead_activities.channel`);
* es la plataforma de las dos trazas (`crm_integration_logs`, `webhook_deliveries`);
* es el prefijo del identificador con el que el evento queda marcado **para siempre**: `HubSpot:evt-7`.

Las tres primeras son columnas `NOT NULL` que un blanco cumple sin ser un dato. La cuarta es peor: «HubSpot» y «HubSpot » producen dos identificadores distintos para el mismo evento del mismo CRM, así que la segunda entrega **vuelve a entrar** —una actividad repetida en la ficha y un score recalculado sobre un hecho que ocurrió una vez—. Un espacio de más en una plantilla de integración basta, y nadie lo habría buscado ahí: la idempotencia del webhook está probada desde el capítulo 34 y es correcta; lo que no estaba normalizado era la cadena con la que se construye su clave.

El sobre recorta ahora, y `crm_platform` y `event` llevan mínimo: un webhook sin plataforma no identifica a su emisor. Es un 422 y no un apaño porque al otro lado hay un sistema que puede corregirlo.

---

## 41.8. Las capas que ya estaban

Tres cosas que este capítulo fue a arreglar y no hubo que arreglar, porque el borde por el que pasan ya lo hacía:

| Camino | Quién normalizaba ya |
| :--- | :--- |
| Los campos del prospecto en la carga del webhook | `_prospecto_normalizado`, desde el capítulo 25: recorta cada uno y **descarta el que se queda en nada** |
| El canal y la nota de una actividad | `registrar_evento`, desde el capítulo 24: `(evento.canal or "").strip() or CANAL_POR_TIPO[tipo]` |
| Los campos de las dos integraciones | Su propio `_texto`, que ahora es el compartido |

Esto cambia cómo se cuenta el capítulo. No es que nadie normalizara: es que **los caminos que pasan por un borde compartido estaban bien y los que van derechos a una columna, no**. `registrar_evento` es el borde del panel, del webhook y de las dos integraciones a la vez, y por eso lleva la regla desde hace diecisiete capítulos. `LeadCreate` no tiene ningún borde debajo: de ahí va al `INSERT`.

Es también la razón por la que `ActivityCreate` **no** lleva un normalizador de blancos, aunque el primer impulso fue ponérselo. Está explicado en §41.12.

---

## 41.9. La contraseña, la única cadena que no se recorta

El recorte general no puede alcanzar a una contraseña, y la razón no es que un espacio sea válido en un secreto —aunque lo sea—, sino esto, que está en la política desde el capítulo 23:

> *«No puede empezar ni terminar con espacios: se pierden al copiarla y luego no coincide.»*

Si la contraseña llegara ya recortada, esa regla **no tendría nunca nada que rechazar**: aprobaría en silencio exactamente lo que dice prohibir, y la cuenta se crearía con una contraseña que su dueño no podría volver a escribir igual. Las cinco contraseñas del sistema llevan un tipo propio, `Contrasena`, con `strip_whitespace=False` declarado en el campo, que pesa más que la configuración del modelo.

El control 55 lo comprueba por el **tipo declarado** y no por el nombre: `must_change_password` también lleva «password» y es un booleano.

---

## 41.10. La migración: lo que se iguala y lo que se cuenta

La revisión `d8b3e5f09a71` no cambia ni una columna, solo lo que hay escrito en ellas. Iguala a `NULL` los blancos de las catorce columnas de texto que admiten nulo de las tres tablas que un cuerpo de petición escribe, reconociendo las tres formas que llegaban —`''`, `' '`, `'   '`— con `TRIM`.

Y aquí hay una diferencia con la migración del capítulo 32 que conviene decir, porque es la misma pregunta con otra respuesta. Aquella solo vació el país de las fichas de las que **constaba** que nadie lo había indicado, porque «México» podía ser una suposición de la columna o la elección de una persona y la fila no guarda cuál. **Aquí no hay esa duda**: nadie escribe tres espacios en «Ciudad» a propósito. Un blanco no es un dato, y eso sí se puede demostrar fila a fila.

Lo que no puede tocar son las seis columnas obligatorias —`leads.first_name`, `last_name`, `source`, `users.full_name`, `campaigns.name`, `channel`—. Un nombre no se inventa, y además un nombre vacío **puede ser correcto**: es el vacío deliberado del webhook de §41.6, y la fila no guarda por dónde entró. Es exactamente la situación del capítulo 32 con el país, así que se hace lo mismo: **se cuentan y se nombran en la salida**, para que alguien pueda ir a corregirlas. Que se puedan corregir se comprobó, que es la lección del punto 24: la edición admite un nombre de verdad y la ficha se encuentra por su correo.

La reversión no escribe nada, y hay una prueba de que no escribe nada: un `NULL` que fue `''` no se distingue de uno que siempre fue `NULL`.

Dos detalles de la condición, los dos con prueba:

* `TRIM(NULL) = ''` es nulo y no verdadero, así que las filas que ya estaban bien **no se reescriben**. Es la diferencia entre tocar cuatro filas y reescribir `leads` entera, y en PostgreSQL eso es un bloqueo de escritura en producción.
* Un dato con espacios alrededor —`' Monterrey '`— **no se recorta**. Lo que esta migración corrige es un vacío con dos representaciones, no el formato de lo que alguien escribió; recortarlo sería un cambio de datos que nadie pidió. A partir de este capítulo lo recorta el esquema al guardarlo.

---

## 41.11. La guarda: la lista sale de las rutas

El fallo de este capítulo no es de un campo, es de los campos que nadie miró, y una prueba por campo habría cubierto los diez del alta y habría dejado fuera el siguiente que alguien añadiera. Que es exactamente lo que pasó entre el capítulo 33 y el 41: el 33 dejó dicho en su propio docstring que el alta quedaba sin hacer, y el alta siguió sin hacerse mientras se añadían campos.

Así que `test_un_blanco_no_es_un_dato.py` saca la lista del código, como `tokens.test.js` y `colores.test.js` sacan la suya de los fuentes del cliente, y por **las dos** vías por las que un cuerpo puede llegar:

1. recorriendo las rutas de la aplicación y leyendo el esquema de cada cuerpo;
2. buscando en los endpoints una llamada `X.model_validate(` **sobre el cuerpo de la petición**, que es como llega el único que no aparece en ninguna firma: el webhook del CRM toma el cuerpo en crudo porque el HMAC se calcula sobre los bytes exactos del emisor.

La segunda vía existe porque una lista escrita a mano habría olvidado precisamente esa, que es la entrada con menos vigilancia humana del sistema. El argumento tiene que mirar al cuerpo y no solo al nombre del método: `model_validate` se usa cuatro veces más en los endpoints para construir **respuestas** a partir de un objeto de la base.

Lo escrito a mano es un cuerpo válido de ejemplo por entrada —no puede no estarlo: un cuerpo válido depende de qué significa cada campo— y el inventario de excepciones. Las dos cosas llevan prueba: una entrada nueva sin cuerpo de ejemplo pone la prueba en rojo **con su nombre**, y una excepción que ya no hace falta también, porque una excepción que sobra es una vigilancia apagada que nadie recuerda haber apagado.

---

## 41.12. Lo que el arnés encontró: dos arreglos que no arreglaban nada

Treinta y tres defectos reintroducidos. En la primera pasada se detectaron **veintisiete**, y los seis que escaparon enseñaron dos cosas distintas.

Cuatro eran huecos de las pruebas y se cerraron con pruebas:

* el normalizador compartido dejaba de recortar y nada se ponía rojo, porque en los esquemas el recorte ya ocurre antes; donde sí importa es en las dos integraciones, que leen cargas crudas. Se prueba ahora llamando al adaptador de LinkedIn, que es el formulario que rellenan personas en un teléfono;
* `en_blanco` pasaba a ser `not valor` y nadie lo notaba: ahora lo notan una prueba de la función y otra que desactiva una cuenta y pone un presupuesto a cero;
* la red derivada de la tabla volvía a mirar solo `None` y nada cambiaba, **porque hoy ningún campo llega a ella en blanco**: los que tienen mínimo se rechazan antes. Se prueba la función directamente, y se dice en su docstring que la red existe para la columna obligatoria que alguien añada sin declararle un mínimo, que es el descuido más probable de todos;
* la guarda pasaba de recorrer las rutas a una lista escrita, y eso lo mira el control 55.

Los otros dos fueron más interesantes, porque el defecto reintroducido **era un arreglo de este capítulo** y quitarlo no cambiaba nada:

* `ActivityCreate` recibió un normalizador para `channel` y `notes`. Se quitó y ninguna prueba se puso roja: `registrar_evento` ya hacía eso desde el capítulo 24. **Era de adorno**, y se quitó del código en lugar de dejarlo con una prueba que lo acompañara: una guarda que no se puede falsear es peor que ninguna, porque parece cubrir algo.
* El recorte del canal en `registrar_evento` tampoco se puede falsear ya, porque el esquema recorta antes. Esa sí se queda —`Evento` lo construyen cuatro caminos y no todos vienen de un esquema— y no entra en el arnés, con el motivo escrito en el propio arnés.

El arnés dejó de medir guardas por un momento y empezó a medir **arreglos**, y encontró uno que no arreglaba nada. Es la vuelta de tuerca del capítulo 40 —donde encontró cuatro guardas que buscaban un nombre y no un uso— sobre otra superficie: ahí la guarda no servía, aquí el arreglo no hacía falta.

Con los cuatro huecos cerrados y los dos casos resueltos: **33 defectos reintroducidos, 33 detectados.**

---

## 41.13. El control 55 del CI

El trabajo de este control no es comprobar el síntoma, es comprobar **la forma del defecto**, que cabe en una línea y vuelve sin que nada se ponga rojo:

| Qué vigila | Por qué |
| :--- | :--- |
| `ENTRADA_DE_TEXTO` es **solo** el recorte | Añadirle `extra="forbid"` cambia de golpe cómo responden dieciséis endpoints a un campo desconocido |
| Ningún validador de esquema vuelve a recortar | Es la forma exacta del defecto: corre después del mínimo y lo deja midiendo otra cadena |
| Todo campo de contraseña lleva su tipo, mirando el **tipo declarado** | `must_change_password` también lleva «password» y es un booleano |
| `integraciones` no vuelve a definir su propio «vacío» | Dos definiciones de acuerdo por casualidad |
| La red derivada de la tabla existe para las **tres** | Es lo que faltaba, y lo que faltaba no se veía |
| El alta y la edición de una ficha comparten la lista de textos | Que el alta tuviera la suya, con nueve de diez, es el punto 25 |
| La guarda sigue sacando la lista de las rutas | Una lista escrita deja de cubrir el endpoint de mañana |
| La migración reconoce un blanco de espacios y no solo `''` | Las tres formas llegaban |
| El cliente no vuelve a recortar lo que envía | Un recorte en el navegador no es una garantía: ni el webhook ni las integraciones pasan por ahí |

El último merece una frase. `AdminPanel` recortaba tres campos y `NewLeadModal` ninguno, así que «aquí los espacios no cuentan» era verdad **según la pantalla**. Tener la mitad de una regla escrita en el sitio por el que no pasan las integraciones hacía creer que la regla existía. Los recortes del cliente se quitaron: lo garantiza el esquema, que es por donde pasan las cinco puertas.

---

## 41.14. Lo que este capítulo no pagó

* **§6.4 punto 26** —el `except IntegrityError` de la edición traduce cualquier violación de integridad a «el correo ya existe»— sigue abierto. Es del mismo renglón del documento que el 25 y es otro asunto: saber qué restricción falló obliga a leer el error del motor, específico de PostgreSQL y de SQLite por separado. Lo que este capítulo sí hizo es quitarle un camino: con el 422 delante, un nulo sobre una columna `NOT NULL` ya no llega a ese `commit` en ninguna de las tres tablas.
* **El alta de una ficha no tiene la red del `IntegrityError`** que sí tiene la edición: entre la comprobación del correo duplicado y el `INSERT` cabe otra transacción, y eso sería un 500. Entra como punto nuevo.
* **Los puntos 37, 38 y 39** —las siete formas que enseñan el nombre de la columna, los siete `alert()` y el ámbar que hace dos oficios— son del capítulo 40 y siguen como estaban.
* **Un espacio en el campo trampa** del formulario público lo desactiva: el recorte lo deja en vacío y `es_robot` da falso. Un robot que escriba espacios en un campo oculto es difícil de distinguir de un autorrelleno, así que se deja y se anota.

---

## 41.15. Estado al cerrar

| | |
| :--- | :--- |
| **Servidor** | 1 587 pruebas, 2 omitidas |
| **Cliente** | 636 pruebas en 40 archivos; cobertura 96,35 / 90,67 / 98,63 / 98,59 sobre suelos 96 / 90 / 98 / 98 |
| **`eslint`** | sin avisos; `npm run build` limpio |
| **CI** | 56 controles de regresión; el 55 es de este capítulo |
| **Arnés** | 33 defectos reintroducidos, 33 detectados |
| **§6.4** | se cierra el **25**; entra el **40** |
| **Archivos nuevos** | `backend/app/core/texto.py`, la revisión `d8b3e5f09a71`, tres archivos de pruebas |

Ni una pantalla cambia de aspecto. Lo que cambia es que «vacío» significa una sola cosa en las cinco puertas, que el mínimo de un campo mide lo que se guarda, y que un `null` sobre una columna obligatoria responde con el nombre del campo en las tres ediciones parciales y no solo en una.
