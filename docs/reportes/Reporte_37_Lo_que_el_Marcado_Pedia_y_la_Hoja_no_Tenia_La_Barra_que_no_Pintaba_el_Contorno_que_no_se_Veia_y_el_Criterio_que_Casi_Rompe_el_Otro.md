# Reporte 37 — Lo que el marcado pedía y la hoja no tenía: la barra que no pintaba, el contorno que no se veía y el criterio que casi rompe el otro

**Capítulo 39** · Interfaz y accesibilidad · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 1 de octubre de 2026
**Alcance:** los cinco tokens de la paleta que el marcado nombraba y nadie había definido, la prueba que saca esa lista del código, el contorno de los controles contra el mínimo de WCAG §1.4.11, el color de acción destructiva, el estado apagado de los botones, la hoja del panel de difusión y del código QR con su tamaño medido en módulos por píxel, tres controles de regresión con veintisiete defectos reintroducidos, y dos defectos que solo aparecieron al mirar la pantalla ya maquetada.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 37 es el capítulo 39. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 39.1. Cuatro restos menores, y por qué uno de ellos no lo era

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para cuatro puntos de §6.4 y para ninguno más**: el 30, el 31, el 32 y el 33.

El criterio es el del §1 del propio documento:

> *«si para explicarlo hay que añadir una frase nueva al README, es funcionalidad; si la frase ya está escrita y el código no la cumple, es un fallo»*

Los cuatro pasan esa prueba sin forzarla, y de la forma más incómoda posible: **el README promete el nivel AA de WCAG 2.1 para las nueve pantallas**, y había un par de colores que no llegaba. La hoja declara un sistema de diseño, y el marcado le pedía clases y tokens que no existían. No hay pantalla nueva, ni endpoint, ni esquema, ni migración. El servidor de este capítulo es, byte a byte, el del capítulo 38.

| Punto | Lo que decía §6.4 | Lo que resultó ser |
| :---: | :--- | :--- |
| **33** | «`var(--accent-primary)` no existe en la paleta —el token se llama `--color-primary`—, así que el borde superior del girador de carga se queda sin color. **Cosmético**, y en un elemento que dura lo que una petición» | **Cinco** tokens en nueve sitios, y dos no eran cosméticos: la barra de distribución del tablero se dibujaba **vacía** y la opción elegida de la ficha 360 se quedaba **sin contorno** |
| **30** | «`CompartirEnRedes` se dibuja sin ningún estilo: se apoya entero en catorce clases que la hoja no define» | Exacto, y además el único enlace con aspecto de botón del cliente salía en azul de navegador sobre un panel oscuro: 1.87:1 |
| **31** | «`btn-danger` no existe. "Cerrar sesión" se dibuja como un `.btn` a secas y no parece un botón» | Exacto, y al darle un relleno sólido apareció que **la hoja no tenía ningún `:disabled`** y quince componentes apagan botones |
| **32** | «El borde de un campo sin foco tiene 1.12:1. WCAG §1.4.11 pide 3.0» | Exacto, y arreglarlo a la primera habría **roto §2.4.7** |

El punto 33 merece una frase más. «Cosmético» era una conclusión razonable mirando el sitio que el capítulo 36 miró —un girador de carga— y falsa mirando los otros ocho. Es el riesgo de anotar un defecto por el ejemplar que uno tiene delante en vez de por su forma: **el defecto no era «falta un color», era «el marcado nombra cosas que nadie comprueba que existan»**, y eso tiene tantos ejemplares como nombres haya.

### Lo que este capítulo decidió NO abrir

Por escrito, y para que no haya duda de qué se quedó fuera: rediseñar ninguna pantalla, un tema claro, pantallas nuevas, los puntos de §6.2 que siguen abiertos, y cualquier cosa de §3, §4 o §5. Se escribe la hoja que falta con los tokens que ya existen; los únicos colores nuevos de la paleta son los cuatro de la acción destructiva, y entran porque el punto 31 pide exactamente eso.

---

## 39.2. Por qué un `var()` inválido es peor que un nombre de clase mal escrito

El capítulo 36 encontró que tres pantallas de credenciales pedían una clase llamada `input` y que en la hoja se llamaba `input-field`. La conclusión de entonces sigue siendo buena: **un `className` mal escrito no rompe nada.** No hay error en la consola, no falla ninguna prueba, el componente se monta, y la pantalla solo se ve distinta. De ahí salió `clases.test.js`.

Lo que ese capítulo no hizo fue sacar la misma conclusión para **la otra cosa que el marcado nombra**: las variables de la paleta. Y el caso de las variables es peor, por un detalle de la norma de CSS que no es intuitivo:

> Una clase que no existe deja al elemento con el estilo por omisión del navegador: feo, pero **visible**.
> Un `var()` que no resuelve deja la declaración entera **inválida en el momento de calcular el valor** — y entonces la propiedad no se queda en el valor anterior: toma el **valor inicial**.

En números concretos de este repositorio:

```jsx
<div style={{ width: `${hotWidth}%`, background: 'var(--hot-gradient)' }} />
```

Sin `--hot-gradient`, esto no dibuja un fondo de otro color. Dibuja `transparent`. Y como los tres segmentos de la barra apilada del tablero no tienen más fondo que ese, **la barra estaba vacía desde el día que se escribió**.

```js
border: `1px solid ${elegida ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
boxShadow: elegida ? '0 0 0 1px var(--accent-primary)' : 'none',
```

Sin `--accent-primary`, esto no deja un borde de otro color: `border` es una abreviatura, y al caerse entera se lleva `border-style`, que vuelve a `none`. **No queda borde.** Lo elegido y lo no elegido quedaban separados solo por dos fondos oscuros casi iguales — en el mismo componente que lleva escrito, unas líneas más arriba, un comentario sobre que el color solo no basta para quien no lo ve. El color tampoco estaba para quien sí ve.

---

## 39.3. Los cinco, uno por uno

El barrido completo sobre `frontend/src` da cinco tokens pedidos sin respaldo y no definidos, en nueve sitios:

| Token | Dónde se pide | Qué pasaba |
| :--- | :--- | :--- |
| `--hot-gradient` `--warm-gradient` `--cold-gradient` | `AnalyticsCharts` (4 sitios) | La barra de segmentación de cartera del tablero y la de rendimiento por asesor, **sin fondo** |
| `--accent-primary` | `LeadDetailModal` (2), `App` (1), `InformeDePublicacion` (1), `PanelDeDesenlaces` (1) | La opción elegida de la ficha 360 sin contorno; el arco del girador sin color; el nombre del prospecto en el informe sin color; la barra de progreso de desenlaces sin relleno cuando aún no se ha alcanzado el mínimo |
| `--color-primary-light` | `ScoringSimulator` (1) | El «⏳ Evaluando…» sin color |

Y uno más que **no** es un defecto, y que importa distinguir:

```js
const tarjeta = { padding: '24px', background: 'var(--bg-panel, transparent)' };
```

`AdminPanel` pide un token que tampoco existe, pero **escribió qué pasa si no está**. El elemento se dibuja. La diferencia entre un defecto y una decisión es una coma, y es toda la diferencia; §39.4 vuelve sobre esto.

### Qué se definió, y por qué así

```css
--accent-primary: var(--color-primary);
--color-primary-light: var(--color-primary-hover);
--hot-gradient: linear-gradient(90deg, var(--hot-dot), var(--hot-text));
--warm-gradient: linear-gradient(90deg, var(--warm-dot), var(--warm-text));
--cold-gradient: linear-gradient(90deg, var(--cold-dot), var(--cold-text));
```

Tres decisiones dentro de esas cinco líneas:

**Alias y no copia.** `--accent-primary` es el blanco de la paleta: el marcado lo pedía con otro nombre, no pedía otro color. Escribirlo como `var(--color-primary)` deja un solo sitio donde cambiar ese blanco. La copia habría dejado dos valores iguales esperando a separarse.

**El degradado va del punto al texto de su propio cuadrante.** Justo debajo de la barra, la leyenda dibuja su muestra con `--hot-text`, `--warm-text` y `--cold-text`. Si el segmento no llevara esos colores, **la leyenda estaría nombrando un color que el segmento no tiene**, que es una forma peor de estar mal que no pintar nada.

**`--color-primary-light` es un fósil, y se dice.** Con `--color-primary` en blanco puro no existe ningún «light» por encima; el nombre viene de una paleta que nunca se escribió. Se conserva porque es lo que el marcado pide, apunta al blanco atenuado —que es lo que ese sitio quería— y lleva el comentario que explica por qué su nombre no significa nada.

### Y una línea oscura entre segmentos

Una vez que la barra pinta, hay que poder decir dónde acaba un segmento y empieza el otro. Medidos: el rojo y el ámbar vecinos se separan **1.75:1** entre sí, y el ámbar y el gris **2.85:1**. Cada segmento lleva ahora `inset -1px 0 0 var(--bg-base)`, una línea del color del fondo de la página, que da de **5.26 a 9.21** contra los colores que separa.

No se suben los colores de los cuadrantes para resolverlo: son los mismos tres de las insignias de toda la aplicación, y moverlos aquí los movería allí.

---

## 39.4. La prueba saca la lista del código, y la coma es toda la diferencia

`frontend/src/pruebas/tokens.test.js` recorre los `.jsx`, `.js` y `.css` del cliente, les quita los comentarios, saca cada `var(--x)` con una expresión y exige que esté en `:root`. **Un token nuevo sin definir nace en rojo.** Es `clases.test.js` para la otra mitad del problema, y por el mismo motivo: una lista escrita a mano caduca en el siguiente cambio.

Tres detalles que no son adorno:

**Se quitan los comentarios antes de buscar.** Es la lección de las guardas del capítulo 37 aplicada aquí: una comprobación que busca un texto en un archivo se satisface con su propia documentación. La cabecera de ese archivo nombra `var(--accent-primary)` para explicar de dónde viene el capítulo, y una cabecera no es código. De paso se corrigió el mismo agujero en `clases.test.js`, que leía la hoja **con** los comentarios: una clase mencionada en una explicación contaba como definida.

**Se comprueba que se leyó algo.** Si una ruta se resolviera mal, las dos listas quedarían vacías y la comprobación pasaría sin haber mirado nada — el peor resultado posible. Hay un mínimo de tokens y un mínimo de archivos, igual que en `contraste.js`.

**El respaldo es una salida legítima y por eso se vigila.** `var(--x, loquesea)` no es un defecto. Pero si no se mirara, bastaría con **añadir una coma** para silenciar la comprobación de arriba. Los tokens con respaldo que la paleta no define están inventariados uno por uno, con su motivo: hoy hay exactamente uno, el `--bg-panel` de `AdminPanel`.

---

## 39.5. El contorno que no se veía, y el criterio que casi rompe el otro

Este es el hallazgo del capítulo, y no es el defecto: es lo que apareció al arreglarlo.

§6.4 punto 32 decía que el borde de un campo sin foco daba **1.12:1** contra lo que lo rodea, cuando WCAG 2.1 §1.4.11 pide **3.0** para lo que identifica un control. Es cierto, y es un fallo contra una frase ya escrita: el README afirma el nivel AA.

La corrección parece aritmética. Se busca la primera alfa de blanco que alcanza 3.0 sobre el peor de los cinco fondos donde hay controles, y sale **0.34**:

| Fondo | `rgba(255,255,255,0.34)` |
| :--- | ---: |
| `--bg-base` | 3.02 |
| `--bg-field` | 3.06 |
| `--bg-surface-hover` | 3.08 |
| `--bg-surface` | 3.10 |
| `--bg-surface-elevated` | 3.11 |

Y entonces aparece el problema. **El aro de foco de esta paleta era `rgba(255,255,255,0.35)`.** Subir el borde en reposo a 0.34 y dejar el foco donde estaba habría dejado los dos a una razón de **1.11:1** entre sí: el contorno por fin visible y **el foco invisible**. Es decir, §1.4.11 cumplido **incumpliendo §2.4.7**, que pide que el foco sea visible.

Dicho de otra manera: la corrección que la auditoría pedía, hecha literalmente, habría empeorado la pantalla para quien navega con teclado, y la comprobación de contraste habría salido más verde que antes. Un número que sube no es lo mismo que una pantalla mejor.

### Los dos tokens se mueven juntos

El aro de foco sube a **0.71**, que es la primera alfa en que el cambio de estado alcanza 3.0 **en los dos sitios donde el cambio ocurre**:

| Dónde | Reposo → foco | Razón |
| :--- | :--- | ---: |
| Un campo | 0.34 sobre `--bg-field` → 0.71 sobre `--bg-field-focus` | **3.30** |
| Un botón secundario | 0.34 sobre `--bg-surface-elevated` → 0.71 sobre `--bg-surface-hover` | **3.06** |

El que manda es el botón, que pasa de un fondo claro a otro más claro todavía. Con 0.70 se queda en **2.99**, y medir solo el campo habría dejado pasar ese valor sin enterarse. Está escrito como prueba —`medirCambios`— y como control del CI, con un defecto reintroducido que es exactamente «se mide solo el campo y se deja en 0.70».

Que esto no sea un número que exige la norma 2.1 —§2.4.7 solo pide que el foco sea visible, sin cifra— es justamente por lo que hace falta escribirlo: lo que ninguna herramienta mide es lo que se pierde en el siguiente cambio.

### De dónde salieron `--bg-field` y `--bg-field-focus`

Para medir el borde de un campo contra el fondo de un campo hace falta que ese fondo sea un token. Estaba escrito a mano, `#0b0d14`, en tres reglas distintas de la hoja. Ahora es `--bg-field`, y su versión con foco `--bg-field-focus`, por un motivo que no es el orden: **`contraste.test.js` solo sabe medir lo que está en `:root`**. Un color escrito a mano en una regla es un color que ninguna comprobación mira.

---

## 39.6. Dónde se para el borde: un control no es un separador

La decisión más fácil de equivocar era subir `--border-subtle` y acabar. §6.4 lo planteaba así: *«subirlo es una decisión de paleta con efecto en todas las pantallas»*.

No se hizo, y el motivo es que §1.4.11 habla de **controles y estados**, no de líneas. `--border-subtle` dibuja a la vez el contorno de un campo y la raya entre dos filas de una tabla. Subirlo a 3.0 habría puesto todas las separaciones decorativas de la aplicación —cada panel, cada fila, cada sección— a un gris claro y evidente. Eso sí es rediseñar, y estaba excluido por escrito.

La paleta tiene ahora dos familias de borde, y la diferencia está escrita en la hoja:

* `--border-subtle` y `--border-medium`, para **separar**: paneles, filas, secciones. No identifican nada y la norma no les pide contraste. Se quedan donde estaban.
* `--border-control`, para **delimitar un control**: `.input-field`, `.btn-secondary`, `.interes-boton`, `.interes-red-casilla` y el selector del código QR.

Y una más, encontrada por el camino: el tirador de la barra de desplazamiento personalizada llevaba `--border-subtle` como **fondo**, 1.15:1 contra la canaleta. Es un control: no se veía dónde estaba. Sube con los campos.

---

## 39.7. Un color de acción destructiva, y por qué no es el de HOT

La tentación evidente era reutilizar la familia `--hot-*`, que ya es roja. No se hizo: **ese rojo es una temperatura de prospecto**, y pintar «Cerrar sesión» con él diría que ese botón es un prospecto caliente. Que dos cosas se parezcan en la pantalla no las hace lo mismo en la paleta, y el día que los cuadrantes cambien de color el botón de cerrar sesión cambiaría con ellos sin que nadie lo haya pedido.

```css
--danger-bg: #b91c1c;
--danger-bg-hover: #dc2626;
--danger-border: #ef4444;
--danger-text: #f8fafc;
```

Relleno sólido y no translúcido como las insignias, porque el problema que cierra es que el botón **no parecía un botón**. Las medidas, todas en la tabla de `contraste.test.js`:

| Par | Mínimo | Medido |
| :--- | :---: | ---: |
| `--danger-text` sobre `--danger-bg` | 4.5 | 6.18 |
| `--danger-text` sobre `--danger-bg-hover` | 4.5 | **4.62** |
| `--danger-border` sobre las cuatro superficies | 3.0 | **4.28** (peor) |

El borde no es adorno y por eso tiene su propia entrada: **el relleno solo da 2.87:1 contra el panel**, por debajo de los 3.0 que §1.4.11 pide a lo que delimita un control. Lo que hace que ese botón tenga contorno perceptible es el borde más claro. Hay una prueba que lo dice al revés —comprueba que el relleno *no* llega a 3.0— para que nadie quite el borde pensando que sobra.

Lo usan tres botones: «Cerrar sesión», y los dos de la pantalla de derechos del titular. El segundo caso es una corrección de significado además de una de color: **«Suprimir definitivamente» era `btn-primary`**, el mismo blanco que «Buscar». En esta paleta el blanco significa «la acción esperada de esta pantalla», y borrar los datos de una persona no lo es.

---

## 39.8. El estado apagado no existía, y el relleno sólido lo hizo visible

No hay ni un `:disabled` en toda la hoja, y quince componentes deshabilitan botones.

Mientras los botones fueron blancos o grises, nadie lo notó: un `.btn-primary` apagado se veía igual que uno encendido, y eso era un defecto que no dolía porque la diferencia visual entre los dos estados ya era pequeña. Con un relleno rojo sólido deja de ser pequeño: **«Suprimir definitivamente» está apagado hasta que se escribe el correo completo**, y un botón rojo, lleno y aparentemente pulsable que no hace nada es la pantalla diciendo algo que no es verdad.

```css
.btn:disabled,
.btn[aria-disabled='true'] {
  background: var(--bg-surface-elevated);
  border-color: var(--border-subtle);
  color: var(--text-muted);
  box-shadow: none;
  cursor: not-allowed;
}
```

Se apaga con colores y no con `opacity`. La opacidad es el gesto habitual y habría atenuado el texto hasta un valor que **ninguna comprobación mide**; este par —`--text-muted` sobre `--bg-surface-elevated`— ya está en la tabla y da 4.63:1, así que el botón apagado se sigue leyendo. Hay un control del CI que falla si vuelve el `opacity`.

Es un hallazgo del capítulo, no uno de los cuatro puntos abiertos. Entra porque sin él la corrección del punto 31 habría introducido un defecto peor que el que cierra.

---

## 39.9. Catorce clases, y un aviso que deja de llevar el estilo a mano

`CompartirEnRedes` no usa ni un estilo en línea: se apoyaba entero en catorce clases que la hoja no definía, así que el panel de difusión y el del código QR salían con el estilo por omisión del navegador —casillas de sistema, listas con viñetas, botones pegados—. Es §6.4 punto 30 y llevaba tres capítulos abierto, porque escribirlo no era corregir un nombre: era decidir cómo se ve un panel.

Están escritas, con los tokens que ya existían y sin añadir ni un color: lo que faltaba era la hoja, no la paleta. Dos decisiones que merecen nombre:

**La casilla de cada red es un blanco de 44 px.** La casilla y su texto van dentro de la misma caja, con el alto mínimo que una persona acierta con el pulgar — el mismo criterio que la página pública usa en sus campos desde el capítulo 33.

**El aviso de la dirección caída tiene clase propia.** El capítulo 38 le puso borde y color a mano, y dijo por qué: las catorce clases no existían y un aviso que se ve igual que el cuerpo del texto no lo lee nadie. Ahora que la hoja está escrita, el estilo en línea se retira — pero **no** compartiendo clase con las notas de cada red. Eso es lo que tenía antes y es lo contrario de lo que hace falta: este aviso dice que lo que se está haciendo no sirve para nada, y una nota al pie no.

### Y el defecto que solo apareció al mirarlo

Con el panel ya maquetado y delante, en el navegador, salta una cosa que ninguna de las pruebas de este capítulo veía: **«Compartir en LinkedIn» estaba en azul marino.**

`.btn` no declaraba `color`. En los cuatro `<button>` que usan la clase sin variante eso no se nota, porque un botón hereda el color de lo que lo rodea. En el **único** `<a class="btn">` del cliente sí: la hoja del navegador le pone el azul de enlace, que gana a la herencia. Medido: **1.87:1** sobre el panel. Y como `.btn` sí quitaba el subrayado, no era ni un enlace con aspecto de enlace: era un texto azul oscuro sobre fondo oscuro.

```css
.btn {
  …
  color: inherit;
}
```

`inherit` y no un token: lo que hace falta es que un `.btn` sin variante se comporte en un enlace igual que en un botón, que es lo que cualquiera que escriba la clase espera. Además, ese enlace lleva ya `btn-secondary`, a propósito y no `btn-primary`: compartir en una red concreta es una de varias acciones, igual de importante que «Copiar texto», que está justo al lado.

Es el defecto de siempre —el marcado pide algo que la hoja no dice— en la propiedad que menos se mira, y lo encontró mirar la pantalla. Queda vigilado por los dos lados: `.btn` tiene que declarar color, y ningún `<a>` puede quedarse con `btn` a secas.

---

## 39.10. El tamaño del código QR, en módulos por píxel

El capítulo 38 arregló que el código fuera **correcto**. Este arregla que sea **legible**, que es otra cosa y se mide en otra unidad.

Sin ninguna regla que lo tocara, el SVG salía a su tamaño nativo: `svgQR` lo genera con escala 4, es decir, cuatro píxeles por módulo y nada más. La unidad que importa no es el ancho del dibujo sino **píxeles CSS por módulo**, porque un enlace más largo mete más módulos en el mismo ancho y encoge cada uno.

El suelo son **5**, y sale de contar y no de mirar:

* El enlace público más largo que ese panel produce —con la red en la consulta— ronda los cien caracteres.
* Cien caracteres en modo byte, nivel M, caben en una **versión 6**: 41 módulos de lado.
* Más los 8 de la zona tranquila, cuatro a cada lado: **49**.
* `min-width: min(248px, 100%)` da **5.06** por módulo en el peor caso, y `max-width: 320px` da 6.53 en el mejor.

Medido en el navegador con el enlace real, el código sale a **293,6 px**, es decir, **5,99 píxeles por módulo**.

El suelo va escrito como `min(248px, 100%)` y no como 248 a secas, y eso también es una decisión: un mínimo rígido sacaría una barra de desplazamiento horizontal a la página entera por debajo de unos 290 px de ventana, que es lo que WCAG §1.4.10 no quiere. Donde hay sitio, el suelo manda; donde no lo hay, el código se encoge y se amplía con los dedos.

La prueba **no se cree ese comentario**: calcula los módulos de un enlace de cien caracteres con el mismo generador que dibuja el código, lee el `min-width` de la hoja y divide. El día que el enlace crezca, el número cambia solo.

---

## 39.11. El inventario de deuda aceptada se queda vacío, y se conserva

`clases.test.js` llevaba quince entradas en `SIN_DEFINIR` desde el capítulo 36: las catorce de `CompartirEnRedes` y `btn-danger`. Están pagadas, y la lista queda a cero.

La pregunta de si retirar el mecanismo se planteó y la respuesta es **no**. Esta lista no existe para guardar nombres: existe para que aceptar una deuda **cueste escribirla con su motivo**. Quitarla dejaría dos salidas peores el día que vuelva a hacer falta —comentar la comprobación, o meter la clase en la hoja con una regla vacía para que la encuentre—, y las dos se parecen demasiado a arreglarlo.

Hay una prueba que comprueba que sigue vacía. No prohíbe volver a usarla: obliga a **borrar esa prueba** para hacerlo, que es justo el tamaño de decisión que corresponde, porque borrar una prueba se ve en el diff.

---

## 39.12. Los tres controles, y los veintisiete defectos que se les reintrodujeron

Los controles 49, 50 y 51 se suman a `configuracion-peligrosa`, que pasa a tener **51**.

Los tres **miden**, no comprueban que exista una prueba. Es la diferencia que este capítulo quiso marcar: un control que solo verifica que un archivo de pruebas sigue ahí se satisface con un archivo de pruebas vacío.

| Control | Qué hace de verdad |
| :---: | :--- |
| **49** | Repite el barrido de tokens en Python, sobre los 41 archivos del cliente y los 52 tokens de `:root`. Si mañana alguien borra `tokens.test.js`, el barrido sigue corriendo aquí. Comprueba además que los degradados llevan los colores que la leyenda del tablero dice que tienen |
| **50** | Reimplementa la fórmula de contraste de la norma y recalcula el contorno en reposo sobre los cinco fondos y el cambio de estado en los dos controles. Se autocomprueba antes: blanco sobre negro tiene que dar 21, o la guarda se para |
| **51** | Repite el barrido de clases **sin lista de excepciones** —aquí no hay forma de volver a llenar `SIN_DEFINIR`—, mide el botón destructivo y su estado apagado, y divide el `min-width` del código QR entre sus módulos |

### Que los controles sirven

Veintisiete defectos reintroducidos de verdad, en una copia del cliente, cada uno corriendo el control con el directorio de trabajo puesto ahí:

```
control 49: 9/9
control 50: 7/7
control 51: 11/11
TOTAL: 27/27
```

El arnés lleva incorporadas las dos cosas que el capítulo 38 aprendió por las malas:

* **La ruta del control se resuelve absoluta antes de cambiar de directorio.** La vez anterior se lanzaba relativa, Python salía con 1 por «can't open file», y el arnés leía ese 1 como «detectado»: trece de trece falsos.
* **Se exige que la sustitución ocurra.** Un defecto que no se aplica deja el árbol intacto y el resultado sería «no detectado» cuando en realidad no se probó nada. Si el texto no está, el arnés se para y lo dice — cosa que hizo dos veces al escribirlo, con dos recuentos de apariciones que eran de más.

Entre los veintisiete hay cuatro que son el capítulo en miniatura: *el borde de un control se queda a una centésima del mínimo* (0.33, que da 2.90), *el aro de foco se queda donde estaba* (§1.4.11 cumplido y el foco invisible), *el aro de foco se mide solo en el campo y se deja en 0.70* (que falla en el botón), y *el suelo del código QR se vuelve rígido* (que cumple el número y saca barra horizontal en un teléfono). Los cuatro son formas de tener razón en el número y estar equivocado en la pantalla.

---

## 39.13. Lo que este capítulo NO hizo

* **No rediseñó ninguna pantalla.** Las separaciones decorativas de la aplicación están donde estaban; lo que subió es el contorno de los controles.
* **No tocó el servidor.** Ni un archivo de `backend/`.
* **No añadió un tema claro.** `contraste.test.js` sigue comprobando que no existe, y seguirá poniéndose en rojo el día que entre uno, porque entonces este archivo mediría medio sistema.
* **No subió los colores de los cuadrantes** para que los segmentos vecinos de la barra se separasen 3.0 entre sí. Son los mismos tres de las insignias de toda la aplicación: moverlos aquí los movería allí. Se resolvió con una línea de separación, y la leyenda sigue dando cada cifra en texto.
* **No cerró §6.4 punto 25** —el alta que guarda `''` donde la edición guarda `NULL`—, que es un fallo real, cabe en el criterio y lleva migración: merece su propio capítulo.

---

## 39.14. Qué queda abierto después de esto

De §6.4 se cierran los puntos **30, 31, 32 y 33**. Siguen abiertos el 19, 20, 21, 23, 25, 26, 27, 28, 29 y 34, y se añade uno nuevo que este capítulo encontró y no pagó: **la hoja no tiene estados de error para los campos**. Un `.input-field` con un valor inválido se ve exactamente igual que uno correcto; hoy lo que avisa es el texto de `.form-error` debajo, que es suficiente para la norma —el error no se comunica solo por color— pero deja al ojo sin pista de **qué** campo.

Y queda dicho lo que ninguna de estas comprobaciones contesta, que es lo mismo que decía §6.3 punto 18: las nueve pantallas pasan WCAG 2.1 AA medido por `axe`, se recorren con teclado, su contraste se calcula contra la norma leyendo `index.css`, y ahora además todo lo que el marcado nombra existe. **Lo que sigue sin responder es si lo que se ve se entiende**, y eso no lo contesta ninguna herramienta.
