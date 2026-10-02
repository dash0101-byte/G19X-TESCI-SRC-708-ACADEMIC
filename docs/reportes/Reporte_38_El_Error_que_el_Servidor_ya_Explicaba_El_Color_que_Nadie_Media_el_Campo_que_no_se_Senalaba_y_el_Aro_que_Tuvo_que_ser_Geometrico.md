# Reporte 38 — El error que el servidor ya explicaba: el color que nadie medía, el campo que no se señalaba y el aro que tuvo que ser geométrico

**Capítulo 40** · Interfaz y accesibilidad · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 1 de octubre de 2026
**Alcance:** el estado de error que la hoja no dibujaba (§6.4 punto 36), el rojo de los avisos que no llegaba al mínimo de WCAG §1.4.3 por estar escrito donde nadie lo mide, el barrido que saca del código todos los colores escritos a mano, el reparto del 422 por campos en los cuatro formularios del panel, la traducción de los mensajes de Pydantic por su tipo y no por su texto, tres controles de regresión con veintiocho defectos reintroducidos, y cuatro guardas del propio capítulo que el arnés encontró débiles.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 38 es el capítulo 40. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 40.1. Un resto menor, y lo que apareció al ir a medirlo

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para un punto de §6.4 y para ninguno más**: el **36**, que el capítulo 39 encontró y no pagó.

El punto decía:

> *«La hoja no tiene estado de error para los campos. Un `.input-field` con un valor inválido se ve exactamente igual que uno correcto: lo que avisa es el `.form-error` de debajo. Cumple la norma —el error no se comunica solo por color— pero deja al ojo sin pista de **qué** campo, y en un formulario de ocho campos eso es leer ocho mensajes para encontrar uno.»*

Lo primero que se hizo fue ir a medirlo, y al medirlo aparecieron **tres cosas que no estaban en ningún punto** y que pasan el criterio del §1 del propio documento —la frase ya está escrita y el código no la cumple— con el mismo incómodo argumento del capítulo anterior: **el README promete el nivel AA de WCAG 2.1 para las nueve pantallas**.

| Lo que se fue a arreglar | Lo que había debajo |
| :--- | :--- |
| Un `.input-field` inválido no se distingue de uno correcto | Cierto. Y el atributo que lo dice —`aria-invalid`— llevaba puesto en la página pública **desde el capítulo 34**, y la hoja no lo miraba: ya había dos verdades sobre el mismo campo, una para el ojo y otra para quien no mira |
| — | El rojo de los avisos de cuatro pantallas estaba escrito a mano en un `style` del JSX y **no llegaba a 4.5**: 4.43:1 sobre el panel y 4.17:1 sobre el elevado |
| — | De los once formularios del panel, **ninguno** señalaba qué campo había rechazado el servidor, aunque el servidor lo dice desde el capítulo 33; el de la ficha 360 lo avisaba con un `alert()` del navegador |
| — | `--hot-text`, el rojo de un prospecto caliente, pintaba también **catorce mensajes de error**: un token con dos oficios y solo uno con nombre |

### Lo que este capítulo decidió NO abrir

Por escrito: rediseñar ninguna pantalla, validación nueva en el cliente que el servidor no haga ya, las otras siete formas del panel, un tema claro, y cualquier cosa de §3, §4, §5, §6.1, §6.2 o §6.3. Los únicos colores nuevos de la paleta son los cuatro del estado de error, y entran porque el punto 36 pide exactamente eso.

---

## 40.2. El hueco entre dos guardas que están bien escritas

Esta es la parte del capítulo que conviene leer aunque no se lea el resto, porque no habla de un color: habla de **cómo se esconde un defecto entre dos comprobaciones correctas**.

El cliente tiene dos guardas de accesibilidad, y las dos dicen la verdad sobre sí mismas en su cabecera:

> `accesibilidad.test.jsx`: *«Lo que esto NO comprueba… **contraste** —necesita píxeles, y `jsdom` no dibuja—: va en `contraste.test.js`»*

> `contraste.test.js`: *«**Los colores se leen** del `:root` de `index.css`. Nadie los copia aquí.»*

Las dos frases son ciertas, y entre las dos queda un sitio: **un color escrito en un `style` del JSX no está en ninguna de las dos**. No lo mide la primera porque no dibuja; no lo mide la segunda porque no está en la paleta. Cada una delega en la otra la parte que no le toca, y la que no le toca a ninguna es justo esa.

Trece archivos del cliente tenían colores ahí. Cuatro de ellos —los avisos de error del acceso, del segundo paso del acceso, del cambio obligatorio de contraseña y del alta del segundo factor— usaban `#ef4444` como **color de texto** sobre su propio fondo translúcido:

| Dónde | Razón | Mínimo §1.4.3 |
| :--- | :---: | :---: |
| `#ef4444` sobre la banda roja, en `--bg-base` | 4.78 | 4.5 ✅ |
| `#ef4444` sobre la banda roja, en `--bg-surface` | **4.43** | 4.5 ❌ |
| `#ef4444` sobre la banda roja, en `--bg-surface-elevated` | **4.17** | 4.5 ❌ |
| `--hot-text` (`#f87171`), el token que la paleta ya tenía | 6.02 | 4.5 ✅ |

La última fila es la que define el defecto: **el color no estaba mal elegido, estaba elegido donde no se mide**. El token que la paleta ya tenía para ese sitio pasaba de sobra. Lo que falló no fue el criterio de quien eligió el color: fue que nadie se lo pudo decir.

---

## 40.3. Una familia propia para el error, y por qué no vale ninguna de las que había

El capítulo 39 separó `--danger-*` de `--hot-*` con un argumento que aquí se usa dos veces: *ese rojo es una temperatura de prospecto, y pintar «Cerrar sesión» con él diría que ese botón es un prospecto caliente*. Para un mensaje de error el argumento vale igual, y además hay una segunda familia que tampoco sirve:

* **`--hot-*` no**, porque es la temperatura de una ficha. El día que los colores de los cuadrantes cambien, los mensajes de error no tienen por qué cambiar con ellos.
* **`--danger-*` tampoco**, porque es el de una **acción** destructiva: un relleno sólido con aspecto de botón. Un aviso no es un botón, y pintarlo con el relleno de uno lo convertiría en algo que parece que se puede pulsar.

De ahí los tres tokens nuevos, más el borde:

```css
--error-bg: rgba(239, 68, 68, 0.12);
--error-border: rgba(239, 68, 68, 0.35);
--error-text: #f05353;
--border-error: #ef4444;
```

`--error-text` es la primera parada de la rampa de `#ef4444` hacia el blanco que pasa 4.5 en los tres fondos donde hay avisos, con el fondo translúcido **ya compuesto**: 5.19 sobre `--bg-base`, 4.82 sobre `--bg-surface` y 4.54 sobre `--bg-surface-elevated`. La parada anterior, `#f05151`, se queda en 4.49. Se elige la primera que pasa y no una cómoda, que es el criterio con el que se eligieron `--text-muted` en el capítulo 36 y `--border-control` en el 39.

`--border-error` se queda en `#ef4444`, que da **4.28:1** en el peor de los cinco fondos donde hay controles, muy por encima de los 3.0 que pide §1.4.11. Aquí **sí** se elige un valor con holgura, y por un motivo medido que se explica en §40.5: este borde no cambia cuando el campo recibe el foco, y cuanto más claro sea, menos sitio queda por encima para que algo se note.

### El token que hacía dos oficios

`--hot-text` pintaba, a la vez, la insignia de un prospecto caliente y **catorce mensajes de error** repartidos por el panel. Es el mismo caso que `--border-subtle` en el capítulo 39 —un token con dos oficios y solo uno regulado— y se resuelve igual: **partiendo, no subiendo**. Los catorce avisos pasan a `--error-text`; las insignias, los scores por encima del umbral y la muestra de la leyenda del tablero se quedan con `--hot-text`, que vuelve a significar una sola cosa.

### Y los avisos dejan de escribirse siete veces

El mismo bloque de siete propiedades estaba copiado en cada componente que tuviera algo que decir. Ahora hay cuatro reglas en la hoja, con la forma de `.btn` y sus variantes —la geometría en `.alert` y el color en la variante—:

```css
.alert       { border: 1px solid transparent; border-radius: …; padding: …; white-space: pre-line; }
.alert-error { background: var(--error-bg);   border-color: var(--error-border);   color: var(--error-text); }
.alert-warn  { background: var(--warm-bg);    border-color: var(--warm-border);    color: var(--warm-text); }
.alert-ok    { background: var(--success-bg); border-color: var(--success-border); color: var(--success-text); }
```

`.alert-warn` reutiliza la familia WARM y **eso contradice en parte el argumento de arriba**: el ámbar de esta paleta es el de una temperatura. Se reutiliza porque no hay otro ámbar y porque inventar una quinta familia para dos avisos sería peor; queda anotado en §6.4 como lo que es, un token con dos oficios que todavía no se ha partido. `--success-*` no tiene ese problema: ya era semántico.

El `white-space: pre-line` de `.alert` no es adorno, y se explica en §40.7.

---

## 40.4. El barrido: sacar la lista del código, otra vez

El arreglo de §40.2 es escribir cuatro colores en el `:root`. Lo que impide que vuelva a pasar no es haberlos escrito: es `frontend/src/pruebas/colores.test.js`, que **saca la lista del código** igual que `clases.test.js` con las clases y `tokens.test.js` con los tokens. Recorre el cliente, quita los comentarios, recorta el bloque `:root` —el único sitio donde un color literal está en su casa— y exige que todo lo demás esté inventariado con su motivo escrito.

El inventario tiene cuatro entradas y ninguna es una excepción cómoda: son colores que **no deben** seguir esta paleta.

| Archivo | Por qué no es un token |
| :--- | :--- |
| `VistaPreviaDelPost.jsx` | Son los colores de LinkedIn. La tarjeta imita la que se verá en la red (§3.4); tematizarla con nuestra paleta enseñaría una tarjeta que no existe |
| `qr.js` | El negro y el blanco de un código QR son parte del código, no del tema. El capítulo 38 ya pagó una vez el precio de un QR impecable que ningún lector podía decodificar |
| `AltaDelSegundoFactor.jsx` | El papel blanco de debajo del QR del segundo factor, por lo mismo |
| `index.css` | El mismo papel blanco, el del QR de la página de interés. **No** es un token, para que nadie lo tematice por error |

### El color escondido en el respaldo de un `var()`

Al escribir el barrido apareció un caso que ninguna guarda miraba. Tres sitios decían:

```jsx
color: error ? 'var(--hot-text, #b42318)' : 'var(--success-text)'
```

`#b42318` es un rojo de tema claro —sobre el panel oscuro daría 2.2:1— y **no se aplica nunca**, porque `--hot-text` existe. Y por existir, `tokens.test.js` tampoco lo mira: esa guarda solo inventaría los respaldos de tokens que **faltan**. Así que ahí vivía, invisible para todo: para la prueba de tokens porque el token está, para la de contraste porque no está en la paleta, y para `axe` porque no dibuja. Los tres se han quitado, y el barrido los busca.

---

## 40.5. El estado de error se dibuja sobre el atributo, no sobre una clase

```css
.input-field[aria-invalid='true'] { border-color: var(--border-error); }
```

Sobre `[aria-invalid='true']` y no sobre una clase propia, y es la decisión que más importa de esta regla: **así la hoja pinta exactamente lo que el lector de pantalla anuncia**. Con una clase habría dos verdades sobre el mismo campo y nada que impidiera que se separasen — de hecho ya estaban separadas, porque el atributo llevaba puesto en la página pública desde el capítulo 34 y la hoja no lo miraba.

El rojo no sustituye al mensaje de debajo: §1.4.1 no admite que el color sea el único portador de la información, y el `.form-error` sigue ahí. Lo que añade es **cuál** de los ocho campos es, que es lo que no se podía saber sin leerlos todos.

---

## 40.6. El aro que tuvo que ser geométrico

Este es el hallazgo del capítulo, y es el del 39 un piso más abajo.

El capítulo 39 encontró que subir el borde en reposo a los 3.0 de §1.4.11 lo dejaba a 1.11 del aro de foco: §1.4.11 cumplido **incumpliendo §2.4.7**. La salida fue mover los dos tokens juntos. Aquí esa salida no existe, y conviene ver por qué.

El borde de un campo inválido es rojo y **no puede cambiar al recibir el foco**: si cambiara, el error desaparecería justo mientras se escribe la corrección. Entonces, ¿con qué se señala el foco? Las dos opciones naturales son cambiar ese borde a otro color o aclararlo. Las dos se quedan cortas, y las tres medidas están recalculadas en `contraste.test.js`:

| Si el foco cambiara el borde a… | Razón contra el rojo en reposo | ¿Llega a 3.0? |
| :--- | :---: | :---: |
| el aro de foco de esta paleta, `rgba(255,255,255,0.71)` | **1.96** | no |
| el rojo más claro que sigue siendo rojo, `#fecaca` | **2.60** | no |
| blanco puro | 3.76 | sí, **pero no es un rojo** |

Es decir: lo único que pasaría de 3.0 cambiando el color del borde es el blanco puro, que no es un rojo —el error se perdería— ni es el aro de foco de esta paleta —sería un quinto token de borde inventado para un solo caso—. **Cuando no hay salida cromática, la salida es geométrica:**

```css
.input-field[aria-invalid='true']:focus {
  border-color: var(--border-error);        /* el error no se va */
  background: var(--bg-field-focus);
  box-shadow: 0 0 0 2px var(--border-focus); /* y el foco aparece por fuera */
}
```

El aro se mide contra **lo que había en ese sitio antes de aparecer**, que es el panel, y da 3.10. Es el tercer renglón de `CAMBIOS_DE_ESTADO`, junto a los dos que el capítulo 39 escribió.

Y hay una prueba que no comprueba el arreglo sino **por qué el arreglo es el que es**: recalcula las tres razones de la tabla y exige que las dos primeras sigan por debajo de 3.0. Si algún día `--border-error` se oscurece lo bastante como para que un cambio de color sí alcance 3.0, esa prueba se pone en rojo y obliga a volver a decidir. Es la única forma de que una decisión tomada por imposibilidad no sobreviva a la imposibilidad.

---

## 40.7. El 422 llegaba al servidor y se perdía en la última pulgada

El capítulo 33 se tomó un trabajo considerable para que vaciar un campo que la ficha no puede no tener conteste **422 nombrando el campo**, en vez del 200 mentiroso que había antes. El 422 trae `loc`, y `loc` dice qué campo es.

Lo que hacían con esa respuesta los cuatro formularios del panel era volcarla entera en un aviso de arriba. Literalmente, al dar de alta un prospecto con dos campos mal:

```
first_name: Field required email: value is not a valid email address: An email address must have an @-sign.
```

Tres cosas en un renglón:

1. **El nombre de la columna de la base de datos**, en un producto escrito entero en castellano.
2. **El idioma de Pydantic**, que es el de la biblioteca y no el de nadie que use esto.
3. **Un solo renglón**, porque `parseApiError` une los campos con saltos de línea y **un salto de línea en HTML no es un salto**. De los veinticuatro avisos del cliente, solo dos conservaban los saltos.

Y en el formulario de la ficha 360 —el que más campos tiene, trece, y el que el capítulo 33 se encargó de que recibiera ese 422— el aviso era:

```js
} catch (err) {
  alert('Error al actualizar prospecto: ' + err.message);
}
```

Un cuadro del navegador. No se puede poner junto a un campo, no forma parte de la página —ningún lector de pantalla lo anuncia como contenido—, tapa justamente el formulario que hay que corregir y enseña el nombre de la columna. El trabajo del capítulo 33 llegaba hasta el servidor y se perdía en la última pulgada.

### El mecanismo se extrae, no se copia

La página pública hacía bien las cuatro cosas desde el capítulo 34: repartir cada error junto a su campo, marcar el campo con `aria-invalid`, atarlo a su mensaje con `aria-describedby` y llevar el foco al primero que falla. Eso se saca a `erroresDeFormulario.js` y lo usan **las cinco** pantallas; la página pública pasa a importarlo en vez de quedarse con su copia.

La parte delicada no es el reparto: es que **el `id` del mensaje y el `aria-describedby` del campo digan lo mismo**. Dos cadenas construidas a mano en dos sitios son dos cadenas que algún día se separan, y el día que se separen el lector de pantalla dejará de leer el error **sin que nada se ponga rojo**: el atributo sigue siendo válido apuntando a un `id` que no existe, y el campo se pinta igual. Por eso las dos salen de `idDelMensaje`, y por eso el control 54 del CI prohíbe que un formulario vuelva a escribir ese `id`.

Tres detalles que el reparto tuvo que aprender:

* **El orden del foco es el de la pantalla, no el del 422.** El servidor manda los renglones en el orden de los campos del esquema. Llevar el foco al que el 422 nombra primero deja a quien navega con teclado mirando hacia el sitio equivocado.
* **El nombre que viaja no siempre es el que la pantalla usa.** La «fecha de cierre» del formulario de publicaciones es `end_date` para el servidor. Sin traducirlo, su error no encontraría su campo.
* **`aria-describedby` admite una lista, y hay que añadir, no sustituir.** Dos campos ya tenían una ayuda propia —«quedan 940 caracteres», «al terminar ese día se cierra sola»—. Sustituirla dejaba al campo sin la explicación de lo que se espera de él **justo cuando más falta hace**, y no se nota mirando la pantalla porque el atributo sigue siendo válido con un solo `id`.

---

## 40.8. El idioma: por el tipo y no por el texto

Traducir los mensajes comparando el texto en inglés habría funcionado hasta la siguiente versión de Pydantic. El `detail` de un 422 trae un `type` —`missing`, `string_too_short`, `value_error`— que es parte del contrato de la API, y es lo que se mira.

El orden en que se decide qué decir es el que hace que la pantalla hable castellano:

1. **La frase de la pantalla, si la tiene.** Las del formulario están escritas para quien lo rellena: «Escribe un correo válido, como nombre@empresa.com».
2. **El mensaje que escribió este repositorio.** Pydantic antepone `Value error, ` a lo que lanza un validador propio, y ese prefijo no es ruido: **distingue nuestros mensajes de los suyos**. Lo que viene detrás está en castellano y ya explica qué forma se espera —«El teléfono no es un número válido: revise la lada y el número de dígitos»—.
3. **La tabla por tipo**, que dice «Falta este campo», «Tiene que tener al menos 2 caracteres», «Elija una de las opciones de la lista».
4. **Y si el tipo no se conoce, una frase genérica.** No el texto en inglés: un mensaje que no se entiende no es mejor que uno vago, y así el inglés no se cuela por el hueco de un tipo que todavía no se ha visto.

Los renglones con los que se prueba todo esto están **copiados de los de verdad**, con su `type`, su `loc`, su `msg` y su `ctx`, obtenidos ejecutando el esquema del backend contra datos malos. Un renglón inventado a conveniencia comprobaría que la función hace lo que la función hace.

---

## 40.9. Lo que el arnés encontró: cuatro guardas que buscaban un nombre y no un uso

Los tres controles nuevos del CI se verifican reintroduciendo, uno a uno, los defectos que vigilan. En la primera pasada, **cuatro de veintiocho defectos no se detectaron**, y los cuatro por el mismo motivo:

| Defecto reintroducido | Lo que la guarda miraba | Por qué pasaba |
| :--- | :--- | :--- |
| `CAMBIOS_DE_ESTADO` se queda con dos sitios | `modulo.count("donde:") < 3` | `PARES` también usa `donde:`; sobraban de lejos |
| Un formulario deja de repartir el 422 | `"erroresDelServidor" not in codigo` | El `import` sigue ahí aunque la llamada no |
| Se quita la distinción del prefijo de Pydantic | `"RUIDO_DE_PYDANTIC" not in codigo` | El nombre sigue en los usos aunque la comprobación no esté |
| El `id` del mensaje deja de salir de una función | `"idDelMensaje" not in componente` | El `import` sigue ahí aunque el uso sea otro |

Es la lección del capítulo 37 —**buscar una forma, no una palabra**— con una vuelta más: renombrar o quitar solo una parte deja el nombre en las demás, así que una guarda que busque el nombre sigue verde con el código roto. Las cuatro pasaron a buscar el uso: `erroresDelServidor(err.detalle`, `RUIDO_DE_PYDANTIC.test(`, `id={idDelMensaje(`, y los `donde:` contados **dentro** del bloque y no en todo el módulo.

Esto es exactamente para lo que existe el arnés. Las cuatro guardas estaban escritas por quien acababa de escribir el código que vigilan, en el mismo rato, con la intención correcta — y cuatro de ellas no servían.

Tras corregirlas: **28 defectos reintroducidos, 28 detectados.**

---

## 40.10. Lo que se midió en un navegador de verdad

El capítulo 39 encontró su peor defecto —`.btn` sin `color`, un enlace en azul de navegador a 1.87:1— mirando la pantalla ya maquetada, que es lo único que lo encuentra. Aquí se repitió el ejercicio con una página servida por HTTP que carga la hoja de verdad.

| Qué | Medido en el navegador |
| :--- | :--- |
| Campo correcto | borde `rgba(255, 255, 255, 0.34)` |
| Campo inválido | borde `rgb(239, 68, 68)` |
| Campo inválido con el foco | borde `rgb(239, 68, 68)` **y** `box-shadow: rgba(255,255,255,0.71) 0 0 0 2px` |
| Fondo del campo con foco | `rgb(17, 20, 30)` = `--bg-field-focus` |
| `.alert-error` | texto `rgb(240, 83, 83)`, fondo `rgba(239,68,68,0.12)`, `white-space: pre-line` |
| El aviso de dos renglones | **dos renglones**, no uno corrido |

Ampliado cuatro veces, el campo inválido con foco se ve como lo que es: un aro rojo dentro y uno blanco fuera, dos anillos distintos y no uno grueso.

Un detalle del método, por si vuelve: el panel del navegador no tiene el foco del sistema operativo, así que `:focus` no coincide y `getComputedStyle` devuelve el estado en reposo. Se comprueba inyectando una regla de hoja —no un estilo en línea— con las mismas declaraciones. **No vale un estilo en línea**: asignar una abreviatura con `var()` por CSSOM deja las longhands pendientes y el color no se aplica, que es justo lo que hizo creer durante un rato que la regla no funcionaba.

---

## 40.11. Los tres controles del CI

| # | Qué repite por su cuenta | Defectos |
| :---: | :--- | :---: |
| **52** | El barrido de colores escritos a mano sobre los 44 archivos del cliente, con el `:root` recortado y el inventario de cuatro archivos; los colores escondidos en el respaldo de un `var()`; y que la prueba de la suite siga sacando la lista del código | 8/8 |
| **53** | La fórmula de WCAG reimplementada —que se comprueba a sí misma: blanco sobre negro = 21—, el texto del aviso contra 4.5 en los tres fondos, el borde del campo inválido contra 3.0 en los cinco, las tres razones de la imposibilidad del §40.6, y las reglas que lo dibujan | 10/10 |
| **54** | Que las cinco pantallas repartan el 422 con el mismo mecanismo, que ninguna construya el `id` del mensaje a mano, que ninguna vuelva al `alert()`, que el módulo no devuelva el `msg` en inglés, y que el `join` del cliente y el `white-space` de la hoja sigan siendo los dos extremos de la misma cuerda | 10/10 |

El trabajo `configuracion-peligrosa` pasa de **51 a 54 controles**.

---

## 40.12. Lo que este capítulo no pagó

Tres cosas se encontraron, se midieron y **no se arreglaron**, y entran en §6.4 con su número:

* **Las otras siete formas del panel siguen enseñando el nombre de la columna**, y diez avisos siguen escribiendo su geometría en línea. En las formas que este capítulo no cableó, un 422 sale todavía por `parseApiError` como `nueva: La contraseña está en la lista de filtradas`: el mensaje ya es castellano —lo escribió este repositorio— y el nombre de delante no. Son las formas donde un 422 es menos probable, y hacerlo toca diez componentes más sin corregir ningún número.
* **Siete `alert()` del navegador siguen en pie**, seis en el recálculo masivo de `App.jsx` y uno en el recálculo de una ficha. El del formulario de edición se cambió porque es el del 422 que este capítulo reparte; los demás no son errores de un campo y cambiarlos es otra decisión.
* **`--warm-*` sigue haciendo dos oficios**, la temperatura WARM y el ámbar de un aviso, y lo mismo dos usos de `--hot-text` que no son errores sino advertencias —el enlace caducado de una publicación y la confirmación de un borrado—. Partir esa familia es el mismo trabajo que este capítulo hizo con el rojo, y no se hace a medias.

---

## 40.13. Estado al cerrar

* **Servidor:** sin cambios. El backend del capítulo 40 es, byte a byte, el del 39: **1530 pruebas, 2 omitidas**.
* **Cliente:** **636 pruebas** en 40 archivos, con la cobertura en 96,3 / 90,6 / 98,6 / 98,5 y el suelo subido con ella a 96 / 90 / 98 / 98. `erroresDeFormulario.js` entra en la lista de archivos medidos —es código que decide y lo usan las cinco pantallas con formulario— y la media **sube**, que es lo único que pasa cuando un archivo nuevo llega probado.
* **Guardas de propiedades:** seis en `src/pruebas/` — `clases`, `contraste`, `tokens`, `colores`, `linter`, `csp` — más `accesibilidad`, `anuncios` y `teclado`.
* **CI:** 54 controles de regresión en `configuracion-peligrosa`, con 28 defectos reintroducidos y 28 detectados en este capítulo.
* **§6.4:** de once entradas abiertas de dieciséis a diez de diecinueve: se cierra la 36 y entran la 37, la 38 y la 39.
