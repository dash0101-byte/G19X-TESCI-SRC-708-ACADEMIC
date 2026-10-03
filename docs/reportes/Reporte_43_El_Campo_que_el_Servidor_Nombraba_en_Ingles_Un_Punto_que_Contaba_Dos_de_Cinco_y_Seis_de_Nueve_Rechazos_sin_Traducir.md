# Reporte 43 — El campo que el servidor nombraba en inglés: un punto que contaba dos de cinco y seis de nueve rechazos sin traducir

**Capítulo 45** · Mensajes de rechazo e inventarios derivados · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 2 de octubre de 2026
**Alcance:** los tres validadores de modelo que escribían el nombre de la columna de la base dentro de una frase en castellano; la separación de ese mensaje en una frase que se lee sola y un contexto que el cliente puede repartir; la traducción de los diecinueve tipos de rechazo que las diecisiete puertas con cuerpo pueden contestar, de los que el cliente traducía once; la tabla que estaba escrita dos veces y la copia que la veía todo; dos guardas derivadas con su propia autocomprobación; el control 59 del CI; y la mitad del punto 46 de §6.4 que se queda abierta porque cambiar el `loc` es cambiar el contrato.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 43 es el capítulo 45. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 45.1. Un punto que contaba dos, y eran cinco

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación para **el punto 46 de §6.4**, y para nada más.

El punto 46 dice, literalmente:

> **El cierre de un prospecto y el registro de una actividad rechazan sin nombrar el campo.** Los **dos** validan con `model_validator(mode="after")`, así que su 422 lleva `loc: ['body']` y nunca puede señalar un campo —el docstring del cierre dice lo contrario, «la convierte en un 422 que señala el campo», y no es cierto para un validador de modelo—.

Todo lo que afirma es verdad, incluida la observación fina sobre el docstring. Lo que no es cierto es la cuenta. En los esquemas del servidor hay **cinco** validadores de modelo:

| Esquema | Validador | Qué comprueba |
| :--- | :--- | :--- |
| `activity.ActivityCreate` | `_la_fecha_es_de_la_reunion` | que la fecha de reunión solo venga en una reunión, y en el futuro |
| `desenlaces.CierreDelProspecto` | `_comprobar` | que el desenlace, su motivo y su tramo encajen entre sí |
| `lead.LeadUpdate` | `_vaciar_solo_lo_que_la_ficha_admite_vaciar` | los campos sin los que la fila no existe |
| `user.UsuarioUpdate` | `_vaciar_solo_lo_que_la_cuenta_admite_vaciar` | lo mismo, para una cuenta |
| `user._CamposDePublicacion` | `_vaciar_solo_lo_que_la_publicacion_admite_vaciar` | lo mismo, para una publicación |

Los dos que el punto nombra son los dos primeros. Los tres que no cuenta son los de las **ediciones parciales**, y no es casualidad que falten: el primero lo escribió el capítulo 33 y los otros dos los repartió el **41**, que es cuando se descubrió que la regla derivada de una tabla estaba escrita dentro del esquema de esa tabla. El punto 46 se escribió antes.

Es la tercera vez seguida. El capítulo 43 encontró que `contraste.test.js` medía con la fórmula de la norma sobre una tabla de pares **escrita a mano**; el 44, que la auditoría de accesibilidad pasaba `axe-core` por una lista de pantallas **escrita a mano**; y el 45, que un punto de la deuda técnica describía con precisión un mecanismo sobre un inventario **escrito a mano**. Y las tres veces el defecto estaba exactamente en lo que la lista no incluía.

---

## 45.2. Lo que contestaba cada una de esas tres puertas

Pedido de verdad, con una petición:

```
PUT /api/v1/users/{id}   {"full_name": null}   → 422
{
 "type": "value_error",
 "loc": ["body"],
 "msg": "Value error, La cuenta no existe sin estos campos, así que no se pueden
         dejar vacíos: full_name. Envíe un valor, o no envíe el campo si no
         quiere cambiarlo."
}
```

`full_name` es el nombre de la columna de la base de datos, en una frase en castellano, en un producto escrito entero en castellano. Lo mismo en las otras dos: `name` al vaciar el nombre de una publicación, `last_name` al vaciar el apellido de una ficha. Y con `budget` —`Optional[float]` sobre una columna `NOT NULL`— también, porque la regla no es de los textos: es de las columnas sin las que la fila no existe.

La frase sale de ahí:

```python
raise ValueError(
    "La cuenta no existe sin estos campos, así que no se pueden dejar vacíos: "
    + ", ".join(prohibidos)
    + ". Envíe un valor, o no envíe el campo si no quiere cambiarlo."
)
```

y `prohibidos` lo calcula `vacios_prohibidos`, cruzando lo que el cliente envió con lo que dice `__table__`:

```python
return frozenset(columna.name for columna in modelo.__table__.columns if not columna.nullable)
```

`columna.name`. El nombre con el que la base conoce esa columna, puesto en el texto que lee una persona.

**Y es justo lo que el capítulo 43 quitó.** Ese capítulo cerró el punto 37 de §6.4 arrancándole a `parseApiError` el `campo: mensaje` que ponía delante de cada renglón, con su motivo escrito en el código:

> *Quitarlo y no traducirlo: una tabla de nombre de columna a etiqueta aquí sería una segunda verdad sobre cómo se llama cada campo, y la primera es la etiqueta que cada pantalla tiene escrita al lado de su `input`.*

Quitó el **prefijo**. Un prefijo lo alcanza una expresión regular; dentro de la frase no lo alcanza nada. Y con `loc: ['body']` el cliente no puede repartir el renglón debajo de ningún campo, así que cae entero en el aviso de arriba, con la columna dentro. El capítulo 43 dejó esta línea en pantalla.

---

## 45.3. Por qué estaba ahí: la regla estaba escrita y no se podía cumplir

Tres funciones más arriba, en el mismo archivo, el capítulo 41 escribió `exigir_texto` con este docstring:

> *El mensaje no dice qué campo es: lo dice el `loc` del 422, y el capítulo 40 lo pone debajo del campo con la etiqueta que la pantalla usa. **Repetir el nombre de la columna en el texto es lo que hacía que la pantalla dijera «source»**.*

La regla estaba escrita, con su ejemplo y su motivo, en el archivo donde vivía el defecto. Lo que nadie escribió es **qué hacer cuando no hay `loc`**. `exigir_texto` es un validador de campo: tiene dónde poner el nombre y no necesita decirlo. `vacios_prohibidos` alimenta un validador de modelo, que ve el cuerpo entero y responde `loc: ['body']`, así que su autor hizo lo único que quedaba —decirlo en el texto—, y las dos mitades no son evitables por separado: o se nombra el campo en una frase, o no se nombra en ningún sitio.

Ese es el hallazgo del capítulo, y no es «a alguien se le olvidó». Una regla que no dice qué hacer en el caso que no cumple la condición es una regla que ese caso incumple con razón.

---

## 45.4. Qué se arregla y qué no: un `loc` distinto es contrato

El punto 46 propone pasar los cinco validadores a validadores de campo, y advierte, con razón, que eso **cambia lo que la API contesta a un cliente que ya existe**. Es cierto y es serio: `loc` es la parte del 422 por la que un cliente sabe de qué campo se habla, y moverlo de `['body']` a `['body', 'full_name']` cambia la forma de la respuesta.

Las dos mitades del punto son separables, y se separan:

| | |
| :--- | :--- |
| **Lo que es una corrección** | que el mensaje no escriba el nombre de la columna. No hace falta tocar `loc`: hace falta que el nombre viaje donde es dato y no prosa. |
| **Lo que es un cambio de contrato** | que el 422 de estos validadores señale el campo en su `loc`. Sigue abierto, con su cuenta ya bien: **cinco** validadores, no dos. |

Así que el `loc` de estos tres rechazos sigue siendo `['body']` después del capítulo 45. Lo que cambia es el `type` —de `value_error` a `campos_vacios_prohibidos`— y lo que lleva dentro.

---

## 45.5. Las dos cosas que ese mensaje mezclaba, cada una en su sitio

El arreglo es una función compartida en `app/core/texto.py`, junto a la que calcula la lista:

```python
def rechazo_de_vacios(sujeto: str, campos: List[str]) -> PydanticCustomError:
    return PydanticCustomError(
        "campos_vacios_prohibidos",
        f"{sujeto} no existe sin alguno de los campos que llegaron vacíos. Envíe un valor, "
        "o no envíe el campo si no quiere cambiarlo.",
        {"campos": list(campos)},
    )
```

y en el cable:

```
PUT /api/v1/leads/{id}   {"last_name": null}   → 422
{
 "type": "campos_vacios_prohibidos",
 "loc": ["body"],
 "msg": "La ficha no existe sin alguno de los campos que llegaron vacíos. Envíe un
         valor, o no envíe el campo si no quiere cambiarlo.",
 "ctx": {"campos": ["last_name"]}
}
```

Tres decisiones, cada una con su motivo:

1. **La frase no termina en dos puntos.** Tiene que poder leerse entera en el aviso de arriba de una pantalla que no reparta su 422, y ahí no hay nada que la complete. Una frase que acaba en `:` y se queda sin lista no es una frase a la que le falte un dato: es una frase rota.
2. **Los campos van en `ctx`**, que es dato estructurado y no prosa. Es el camino que el propio sistema ya usa en dos sitios: el 409 del recálculo masivo manda el trabajo que ocupa el turno, y la política de contraseñas manda `motivos` con todos los que la contraseña incumple.
3. **El `type` es el nombre propio del rechazo**, y es lo que el cliente mira. Un tipo es parte del contrato de la API; una cadena en castellano es texto que se reescribe. Esa decisión la tomó el capítulo 40 para la tabla de traducciones y aquí se aplica igual.

Y un detalle que importa más de lo que parece: los nombres que van en `ctx` son nombres **del esquema**, no de la tabla, aunque salgan de cruzar con `__table__`. `vacios_prohibidos` recorre `model_fields_set`, así que lo que devuelve es siempre un campo que **el cliente envió**. Por eso se le pueden dar: no se le está contando la forma de la base, se le está devolviendo lo que mandó.

---

## 45.6. El cliente reparte lo que el `loc` no sabe señalar

En `components/erroresDeFormulario.js`, el reparto aprende una segunda forma de saber de qué campo habla un renglón:

```js
const delContexto = camposDelContexto(item);
if (delContexto) {
  let alguno = false;
  for (const bruto of delContexto) {
    const campo = traducir(bruto);
    if (campos && !campos.includes(campo)) continue;
    if (!porCampo[campo]) porCampo[campo] = propios[campo] || mensaje;
    alguno = true;
  }
  if (!alguno) sueltos.push(String(item.msg || mensaje));
  continue;
}
```

Lo que se ve en la ficha 360 al vaciar un apellido y guardar: el borde rojo en **Apellidos**, debajo «No puede quedar vacío.», y arriba «Revise el campo Apellidos.» —con la etiqueta de esa pantalla, que es la única verdad sobre cómo se llama ese campo—. En ningún sitio aparece `last_name`.

Dos frases para el mismo rechazo, y las dos son correctas en su sitio:

* **debajo del campo**, la corta. Ya está al lado del campo del que habla; repetir cuál es sería ruido.
* **en el aviso de arriba**, la larga del servidor. «No puede quedar vacío» allí no dice **qué** no puede quedar vacío.

Ponerlas al revés es la única forma de equivocarse aquí, y es la que una prueba vigila. Para distinguirlas hace falta saber qué mensajes los escribió este repositorio: los que levantan un `ValueError` se reconocen por el prefijo «Value error, » que Pydantic antepone, y los que levantan un `PydanticCustomError` **no llevan prefijo**, así que se nombran por su tipo en una lista de una entrada.

---

## 45.7. Lo que apareció al medirlo: seis de nueve rechazos en inglés

El punto 5 del guion de este capítulo pedía medir cuántas puertas pueden contestar una lista cerrada a una pantalla que no reparte su 422, y decidir **con el número delante**. El número resultó ser de otra cosa.

Los dos formularios del panel que no reparten su 422 por campos son el de **actividad** de la ficha 360 y el de **cierre** de un prospecto. Nueve rechazos alcanzables entre los dos, y esto es lo que enseñaban:

| Formulario | Qué se hace mal | Lo que salía en pantalla |
| :--- | :--- | :--- |
| actividad | no elegir el tipo | `Field required` |
| actividad | un tipo que no existe | `Input should be 'PAGE_VIEW', 'FORM_SUBMIT', 'EMAIL_OPEN', …` (catorce claves) |
| actividad | una fecha que no es fecha | `Input should be a valid datetime or date, input is too short` |
| actividad | una reunión en el pasado | «La reunión tiene que ser en el futuro; una pasada no se recuerda.» |
| actividad | notas larguísimas | `String should have at most 500 characters` |
| cierre | no elegir el resultado | `Field required` |
| cierre | un resultado que no existe | ««REGALADO» no es un desenlace. Los desenlaces son: ganado, perdido.» |
| cierre | una fecha que no es fecha | `Input should be a valid date or datetime, input is too short` |
| cierre | un tramo que no existe | ««DE_100K_A_250K» no es un tramo de la lista.» |

**Seis de nueve en inglés.** Y cinco de los seis eran de un tipo que el cliente **ya sabía traducir**: la tabla `POR_TIPO`, escrita en el capítulo 40, convierte `missing` en «Falta este campo.» y `enum` en «Elija una de las opciones de la lista.» desde entonces.

La tabla la usan las cuatro pantallas que reparten su 422 por campos. La función que ve **todas las demás** —`renglonesDelCuerpo`, en `services/api.js`— no la tenía:

```js
const mensaje = String(item.msg || '').replace(RUIDO_DE_PYDANTIC, '');
```

Quitaba el prefijo —eso es lo que arregló el capítulo 43— y entregaba el texto de la biblioteca. No faltaba la traducción. Faltaba que la viera quien la necesitaba.

---

## 45.8. Diecinueve tipos, y una tabla de once

Con la pregunta ya planteada, la respuesta no se adivina: se deriva. Las puertas con cuerpo de petición salen de las rutas de la aplicación, y los tipos que cada una puede contestar salen de mandarle a cada campo algo que no es lo que pide.

**Diecisiete** esquemas son cuerpo de una petición, repartidos entre 67 puertas. Entre todos pueden contestar **diecinueve** clases de rechazo, y la tabla del cliente cubría **once**. Los ocho que faltaban:

| Tipo | Qué significa |
| :--- | :--- |
| `string_type`, `int_type`, `float_type`, `bool_type`, `date_type`, `datetime_type`, `dict_type` | lo que llegó no es de la clase del campo |
| `date_from_datetime_inexact` | una fecha con hora donde se espera un día |

Y faltaban por un motivo con forma: **la tabla se escribió mirando lo que un formulario rompe**, y un formulario manda siempre una cadena. Lo que rompe un cliente de la API es otra lista —una lista donde va un texto, un número donde va un objeto—, y es la mitad de los tipos.

A eso hay que sumar el que el propio capítulo encontró al medir: la tabla tenía `date_from_datetime_parsing` y `datetime_parsing`, pero no `datetime_from_date_parsing`. Pydantic tiene un nombre **por cada dirección** de la conversión y la tabla tenía dos de los tres, así que la misma errata de teclado contestaba en castellano en la fecha de un cierre y en inglés en la de una reunión, **en el mismo panel**.

La tabla tiene ahora veinticinco entradas y cubre los diecinueve tipos alcanzables. Lo que queda fuera es `value_error`, que son nuestros propios mensajes: llegan con el prefijo de Pydantic, en castellano, y explican el caso concreto. No necesitan traducción; necesitan que no se les ponga una por delante.

---

## 45.9. La tabla estaba escrita dos veces, y la copia sin tabla era la que lo veía todo

`RUIDO_DE_PYDANTIC` —la expresión regular del prefijo— estaba declarada en `services/api.js` **y** en `components/erroresDeFormulario.js`, con el mismo nombre y el mismo valor. Dos copias de la misma decisión, que es la forma que este repositorio ya conoce: `texto_o_nada` vivía dos veces en el servidor hasta el capítulo 41, y mientras cada puerta tuvo su definición de «vacío», mantenerlas de acuerdo dependía de que quien tocara una se acordara de la otra.

Aquí ya se habían separado, y de la peor manera posible: una de las dos copias tenía la tabla de traducciones y la otra no, y la que no la tenía era la que veía **todas las pantallas que no reparten**.

Las dos constantes viven desde este capítulo en `services/rechazos.js`, con la función que `api.js` necesitaba:

```js
export function textoDelRenglon(item) {
  const crudo = String((item && item.msg) || '');
  if (RUIDO_DE_PYDANTIC.test(crudo)) return crudo.replace(RUIDO_DE_PYDANTIC, '');
  if (item && TIPOS_PROPIOS.includes(item.type)) return crudo;
  const deLaTabla = POR_TIPO[item && item.type];
  if (deLaTabla) { … }
  return 'No se admite este valor.';
}
```

El último renglón es una decisión con coste y conviene decirlo: un tipo que no esté en la tabla ya **no** enseña el texto en inglés, enseña una frase genérica. Es la doctrina del capítulo 40 —«un mensaje que no se entiende no es mejor que uno vago»— aplicada al aviso de arriba, y lo que la hace sostenible no es el criterio sino la guarda: una prueba del servidor saca de los esquemas los tipos que sus puertas pueden contestar y exige que la tabla los cubra. El hueco existe y no se puede llenar en silencio.

---

## 45.10. El blanco que esta red no atrapa: cero de quince

El punto 4 del guion pedía medir, no arreglar a ciegas, una cosa que se vio de paso: Pydantic **no ejecuta** un `model_validator(mode="after")` si algún campo falló antes. Así que la red de los campos obligatorios es inalcanzable en cuanto cualquier otro campo del cuerpo también falla.

Medido campo a campo sobre las tres entradas —los **quince** campos que el esquema admite editar y la tabla declara obligatorios:

| | `null` explícito | un blanco (`'   '`) |
| :--- | :---: | :---: |
| llegan a la red | **14 de 15** | **0 de 15** |
| los atrapa alguien antes, nombrando el campo | 1 (`source`, con su propio validador) | **15** |

Ningún blanco llega a esta red, en ninguno de los quince campos: los dos nombres de una ficha y el de una cuenta tienen `min_length`, `email` lo rechaza su tipo, las listas cerradas su enumeración, `budget` su conversión a número, `estado` su validador propio y `source` el suyo. Y quien los atrapa lo hace **mejor**, porque nombra el campo en el `loc` y el mensaje acaba debajo del campo.

El capítulo 41 cambió una palabra en esta red —`is None` pasó a ser `en_blanco`— y escribió en el docstring de `LeadUpdate` que «esto es la red que no depende de que cada campo se acuerde de declarar un mínimo». Esa frase sobrevalora lo que hace. Y lo curioso es que el **mismo capítulo** lo había medido bien en otro sitio: el docstring de su propia prueba, `test_la_red_de_la_tabla_ve_un_blanco_y_no_solo_un_nulo`, dice «con el recorte delante, ningún campo de hoy llega a este validador en blanco, así que su parte de blanco no se puede provocar desde una petición». Dos textos del mismo capítulo, uno exacto y el otro no, a cuatro archivos de distancia.

Qué se hace con eso: **nada en el código**. La red no sobra —es la que atrapará la columna obligatoria que alguien añada sin declararle un mínimo, que es el descuido más probable porque el mínimo es opcional y la columna no— y quitarle la palabra sería trabajo sin ningún número que corregir. Lo que se corrige es la frase que la describía mal, con su cifra, en el sitio donde estaba.

---

## 45.11. Dos pruebas que tenían el inglés escrito como resultado correcto

Al cambiar lo que `renglonesDelCuerpo` entrega, dos pruebas de `api.test.js` se pusieron rojas, y lo que enseñaron vale más que el arreglo:

```js
await expect(api.createLead({})).rejects.toThrow('Field required\nno es un correo válido');
```

`'Field required'` estaba escrito **como valor esperado**. La prueba pasaba, y lo que documentaba era que la pantalla enseña inglés.

Y pasaba por una razón concreta: sus renglones del 422 **no traían `type`**, que es el único campo por el que se puede saber de qué clase de error se trata. Eran renglones escritos a mano, y sin tipo no hay nada que traducir. La cabecera de `erroresDeFormulario.test.js` ya exigía lo contrario desde el capítulo 40 —«las pruebas de este archivo parten de renglones de 422 copiados de los de verdad»— y los de `api.test.js` no lo cumplían.

Es la forma del 43 y del 44 en una tercera capa. El 43: un doble puesto por encima del fallo convierte la prueba en una tautología. El 44: una consulta de la biblioteca de pruebas no es una medición de accesibilidad. El 45: **un renglón del 422 escrito a mano no es la respuesta del servidor**, y una prueba que lo afirma comprueba lo que la función hace, no lo que tiene que hacer.

---

## 45.12. Las dos guardas, y por qué se comprueban a sí mismas

La suite entera del servidor —1677 pruebas— pasa igual con la columna dentro de la frase y sin ella. Ninguna miraba lo que esas tres puertas contestan. Así que las guardas nuevas derivan sus listas, y cada una exige haber encontrado algo antes de contestar que no falta nada, que es la lección del capítulo 44 convertida en código.

**`test_el_nombre_de_la_columna_no_viaja_en_la_frase.py`** (10 pruebas) pregunta **a Pydantic** por los validadores que va a ejecutar, y no al texto del archivo. La diferencia no es de estilo: `_CamposDePublicacion` declara el suyo una vez y lo heredan cuatro clases, así que un recuento por clase daría **ocho** validadores donde hay cinco, y un `grep` por el decorador daría cinco sin ver que uno vigila dos puertas —el alta de una publicación incluida, donde hoy no puede saltar porque sus campos son obligatorios, y mañana depende de cómo estén declarados—. De los cinco, los tres de las ediciones parciales se distinguen por lo que **usan** y no por su nombre: son los que llaman a `vacios_prohibidos`.

**`test_lo_que_el_cliente_sabe_decir_de_un_rechazo.py`** (8 pruebas) deriva las 17 puertas con cuerpo de las rutas, provoca los 19 tipos, **lee la tabla del archivo del cliente** y compara cobertura. Está en el servidor porque la lista de tipos la decide el servidor y solo él puede derivarla; el cliente no puede saber qué le van a contestar. Hay precedente: `test_publicaciones.py` lee la ruta pública de `main.jsx` desde el capítulo 34.

Sus autocomprobaciones, que son las que impiden el fallo del 44:

* que **encontró** la tabla del cliente: si el archivo se renombra o el formato de sus claves cambia, la expresión regular devuelve un conjunto vacío y **todas** las comprobaciones de cobertura pasarían, porque un conjunto vacío no contiene ningún tipo sin traducir.
* que encontró cinco validadores, más de cien columnas y al menos catorce campos alcanzables.
* que provocó diecinueve tipos y no tres.

Y una tercera, que salió gratis al escribir la segunda: **ninguna de las 17 puertas levanta algo que no sea un 422**. Un validador que levanta un `KeyError` sobre un valor del cuerpo no contesta 422, contesta **500**, y entonces no hay ningún renglón que traducir.

Hay además una cifra de esta guarda que conviene contar, porque la equivocó la primera versión. Las puertas eran **quince** y son **diecisiete**: las rutas que un enrutador incluye llevan su camino **sin el prefijo**, así que `POST /leads` y `POST /campaigns` son las dos `POST ''`, y al indexarlas por `(método, ruta)` una pisaba a la otra. Dos esquemas desaparecían del recuento sin que nada fallara —`LeadCreate` entre ellos—, que es el fallo que este capítulo entero estudia, cometido mientras se escribía la guarda contra él. La clave es ahora la función que atiende la puerta, y la cifra está fijada en una prueba.

---

## 45.13. Control 59 del CI, y veinticinco defectos reintroducidos

El control 59 de `configuracion-peligrosa` —sesenta pasos, cincuenta y nueve controles— lee los dos lados y comprueba seis cosas:

1. **El rechazo compartido** existe, levanta un error **con tipo** —un `ValueError` no puede llevar contexto, y entonces el único sitio donde caben los campos es la frase— y su mensaje no interpola ninguna lista.
2. **Los tres validadores** de los campos obligatorios lo usan. Se cuentan los que **llaman** a `vacios_prohibidos`, y si no encuentra exactamente tres, el control falla por sí mismo.
3. **La tabla del cliente** tiene sus veinticinco entradas, conoce el tipo nuevo, distingue los mensajes propios y **vive en un solo archivo**: ni `api.js` ni `erroresDeFormulario.js` vuelven a declarar su copia.
4. **Quien veía el inglés la usa.** Se comprueba la llamada, `textoDelRenglon(item)`, y no el nombre: dejar el `import` y volver a `item.msg` deja la palabra en el archivo y la pantalla en inglés.
5. **Las dos guardas siguen derivando** sus listas en vez de escribirlas, **y siguen comprobándose a sí mismas**: las siete afirmaciones que les exigen haber encontrado cinco validadores, más de cien columnas, catorce campos, diecisiete puertas y diecinueve tipos se piden por su texto.
6. **Ningún `raise` de ningún esquema nombra una columna.** Se le preguntan sus columnas a los modelos —152— en vez de buscar una lista de palabras, y se miran los `raise` y no el archivo entero, porque un `Field(description=...)` es documentación de la API, donde el nombre de la columna es el dato correcto.

El arnés reintroduce **veinticinco defectos**, uno a uno, y comprueba que algo se pone rojo. Cinco resultados valen escritos:

* **La mitad de los defectos solo los ve el control 59.** Volver a copiar la tabla en los dos archivos, dejar de derivar la lista de validadores, borrar una guarda: la suite se queda **verde**, porque una suite no puede detectar que ha dejado de mirar.
* **Y la otra mitad solo los ven las pruebas.** Cambiar la frase corta por el párrafo del servidor debajo de un campo, o perder lo que la pantalla no pinta en vez de mandarlo al aviso de arriba, son cosas que el control no puede ver: pasa por el código y no por la pantalla.
* **El control 59 encontró su propia respuesta en un comentario**, igual que el 58 tres veces. El docstring de `rechazo_de_vacios` **cita el mensaje viejo entero**, con `full_name` dentro, para explicar por qué se quitó. La comprobación lo encontraba ahí y daba por hecho el defecto. Todas las lecturas van sin comentarios.
* **Y encontró una columna llamada `texto`.** El control busca nombres de columna dentro de las frases de los `raise`, y hay una columna que es una palabra del castellano: «Cada opción es un texto.» la delataba. El inventario de excepciones —trece nombres, cada uno porque es una palabra del idioma en que están escritos los mensajes— es lo único escrito a mano de este control, y está escrito con su motivo.
* **La primera pasada fue 22 de 25, y los tres que faltaban eran del mismo sitio: las guardas se podían vaciar sin que nada avisara.** Cambiar `validadores = _validadores_de_modelo()` por `validadores = {}` deja la función usada en otra prueba del mismo archivo —así que el control seguía viéndola— y la afirmación comparando un diccionario vacío con una lista, que es verdad. Y bajar el umbral de una autocomprobación de `>= 5` a `>= 0` no lo miraba nadie. **Un umbral que baja a cero es la forma en que una guarda deja de mirar sin dejar de existir**, que es el capítulo 44 dicho desde el otro lado: lo que delata una lista corta no es el verde, es la cifra. El control exige ahora las siete autocomprobaciones por su texto, y el arnés cierra en 25 de 25. El tercero —renombrar la función que lee la tabla del cliente— lo detecta la propia suite, porque sus llamadas se quedan sin destino; eso no lo ve el control y está bien que no lo vea.

---

## 45.14. Lo que apareció y no se hizo

**La mitad del punto 46 que es un cambio de contrato** sigue abierta, con su cuenta corregida: pasar los cinco validadores de modelo a validadores de campo permitiría repartir sus rechazos en la pantalla, y cambia el `loc` que un cliente ya recibe. El punto queda reescrito, no cerrado.

**El reparto por campos del formulario de actividad y del de cierre** entra como punto **49**. Son los dos formularios del panel que no reparten, y ya **no** es un problema de idioma —el capítulo 45 lo resolvió— sino de dónde cae el renglón: en el aviso de arriba y no debajo de su campo. Los dos tienen pocos campos y sus rechazos son casi todos de listas cerradas que el propio desplegable ofrece, así que el reparto corregiría poco; y el del cierre depende de la mitad abierta del 46, porque sus rechazos son todos de un validador de modelo.

**Y una corrección en el punto 45**, que escribió el capítulo 43: decía que el simulador es «el único de los formularios que quedan donde un rechazo por campo es alcanzable», y el de actividad recibe `missing`, `enum` y `string_too_long` con el campo en su `loc`. Lo que el punto argumenta sigue siendo bueno —un 422 sobre una lista cerrada que el propio desplegable ofrece es un fallo de programación y no un dato mal escrito— y vale para los tres; lo que no era cierto es la exclusividad.

**El hueco del tipo desconocido** entra como punto **50**: un tipo que la tabla no conozca sale como «No se admite este valor», que no dice nada. Es mejor que el inglés y peor que una frase, la guarda impide que se llene en silencio, y lo que falta —que el cliente pudiera decir algo sensato de un tipo que nadie ha visto— no tiene arreglo sin una segunda fuente de verdad.

Y por escrito, lo que este capítulo **no** abrió: ninguna pantalla nueva, ningún endpoint, ninguna columna, ninguna migración, ningún color, ningún cambio en `loc`, y nada de §3, §4, §5, §6.1 ni §6.2.

---

## 45.15. Estado al cierre

| | |
| :--- | :--- |
| Pruebas del servidor | **1695 pasan**, 2 omitidas (desde 1677) |
| Pruebas del cliente | **730 pasan** en 43 archivos (desde 710 en 42) |
| Cobertura del cliente | 96,65 % sentencias · 91,75 % ramas · 98,52 % funciones · 98,68 % líneas (suelos: 96 / 90 / 98 / 98) |
| Validadores de modelo | **5**, derivados de Pydantic; los **3** de las ediciones parciales, corregidos |
| Columnas en una frase | **0** de 152, comprobado sobre los `raise` de los esquemas |
| Tipos de rechazo | **19** alcanzables desde 17 puertas, **25** entradas en la tabla, **0** sin frase |
| `ruff` / `eslint` / `npm run build` | sin avisos |
| Controles del CI | **59** en `configuracion-peligrosa` |
| Arnés de reintroducción | **25 de 25** detectados |
| §6.4 | el **46** reescrito y partido; entran el **49** y el **50** |

Lo que queda dicho de este capítulo: una guarda tiene dos mitades —cómo mide y sobre qué— y solo la primera se revisa. Lo que el 45 añade es que **un punto de la deuda técnica es también una guarda**: describe un mecanismo, afirma un alcance, y nadie vuelve a contar si el alcance sigue siendo ese. El punto 46 era exacto en todo lo que explicaba y contaba dos de cinco, y los tres que no contaba eran los únicos que tenían el defecto.
