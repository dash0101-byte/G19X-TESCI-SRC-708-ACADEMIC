# Reporte 34 — Accesibilidad comprobada: la ventana que no era ventana, el color que no llegaba y la consulta por fila

**Capítulo 36** · Calidad del cliente · ≈ 1 día · sin cuentas externas
**Fecha:** 25 de septiembre de 2026
**Alcance:** revisión automática de accesibilidad sobre las ocho pantallas montadas, recorrido con teclado, contraste contra el mínimo de la norma, anuncio de errores y aciertos a un lector de pantalla, y medición del rendimiento con volumen realista.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 34 es el capítulo 36. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 36.1. De dónde sale este capítulo, y por qué no es funcionalidad nueva

No sale de una idea. Sale de un comentario que el propio proyecto se dejó escrito hace diecinueve capítulos, en `frontend/eslint.config.js`:

> *«Se entra con una sola regla del plugin, no con su `recommended` entero. El conjunto completo señala además cosas de otras familias (roles ARIA, orden de foco, texto alternativo) **que no se han revisado todavía**; meterlas de golpe llenaría la salida de errores ajenos a lo que aquí se arregló, y eso es exactamente cómo se aprende a ignorar al `linter`.»*

Era una deuda anotada con su motivo, y el motivo tenía fecha de caducidad: valía hasta el día en que esas familias se revisaran. Este capítulo es ese día.

**Encaja en la congelación** (§1 de `docs/Congelacion_y_Trabajo_Futuro.md`) sin forzar nada, y conviene decir por dónde:

| Lo que entra, según §1 | Lo que este capítulo hizo |
| :--- | :--- |
| «Una prueba que falla, o una guarda del CI en rojo» | El suelo de cobertura del cliente **ya estaba roto en `main`** (§36.9) |
| «Un comportamiento que contradice lo que dice su reporte, el README o una prueba» | La hoja de estilos declara una clase de campo que tres pantallas no usaban (§36.6) |
| «Documentación que describe algo que el código no hace» | Ninguna pantalla nueva, ningún campo nuevo, ninguna frase nueva en el README |

Y lo que **no** entra se respetó: no se rediseñó ninguna pantalla, no se cambió la tipografía y la paleta se tocó en **un solo token**, el mínimo imprescindible para que una afirmación que el sistema ya hacía fuera cierta (§36.4). Lo que habría exigido diseñar —catorce clases de un panel que no existen— se midió, se documentó y **no se tocó** (§36.8).

---

## 36.2. La biblioteca que ya estaba instalada y nadie llamaba

El punto 1 pide una comprobación automática de accesibilidad integrada en la suite del cliente. Eso significa `axe-core`: el motor que usan las extensiones de auditoría de los navegadores.

Traer una biblioteca a un proyecto congelado exige justificarlo. Aquí la justificación resultó ser más corta de lo previsto:

```
$ npm install --save-dev --save-exact axe-core@4.13.0
up to date, audited 361 packages in 4s
found 0 vulnerabilities
```

**«up to date».** `axe-core` estaba en `node_modules` desde el capítulo 17: la arrastra `eslint-plugin-jsx-a11y`, que la usa para saber qué roles y atributos ARIA existen. El diff del lock es de **una línea**:

```diff
         "@vitest/coverage-v8": "5.0.0",
+        "axe-core": "4.13.0",
         "eslint": "9.39.5",
```

Ni un paquete nuevo en el árbol, ni una versión movida, ni un byte más en la imagen —es dependencia de desarrollo y no viaja al bundle—. La herramienta para auditar accesibilidad llevaba diecinueve capítulos instalada. Lo que faltaba era llamarla.

Se declara directa aunque llegue sola, y hay un control del CI que lo exige (§36.10): una dependencia que solo llega de forma transitiva desaparece el día que su portador cambie de versión, y entonces la revisión se cae con un error de importación que parece un problema de instalación.

---

## 36.3. Lo que el motor ve, lo que no, y cómo se cubre lo que no

`axe` corre sobre `jsdom`, que implementa el DOM pero **no dibuja nada**. Eso parte las reglas en dos, y decir cuál es cuál es la mitad del trabajo de este capítulo:

| | Se comprueba con `axe` | Se comprueba de otra forma |
| :--- | :--- | :--- |
| Roles, nombres accesibles, `aria-*` válidos, encabezados, tablas, regiones | ✔ `accesibilidad.test.jsx` | |
| **Contraste de color** | ✘ necesita píxeles | `contraste.test.js`: lee la paleta de `index.css` y aplica la fórmula de la norma |
| **Orden real del foco** | ✘ `axe` mira el marcado, no el recorrido | `teclado.test.jsx`: pulsa `Tab` de verdad |
| **Que el aro de foco se vea** | ✘ | `teclado.test.jsx` comprueba que la hoja no quite el aro sin poner otro; el color de ese otro lo mide `contraste.test.js` |
| **Si un lector de pantalla lo anuncia bien** | ✘ y ninguna herramienta lo puede decir | `anuncios.test.jsx` comprueba que el marcado que esos lectores leen esté puesto |

`axe` marca como «incompletas» las reglas que no puede ejecutar, en vez de darlas por buenas. Esa honradez del motor se conserva aquí: `color-contrast` se **apaga explícitamente** y con el motivo escrito, para que su incompletitud no se confunda con un resultado. Hay un control del CI que exige que esa siga siendo la **única** regla apagada.

La reacción cómoda habría sido renunciar a medir el contraste porque el entorno no dibuja. Pero el contraste no es una propiedad de los píxeles: es una propiedad de **dos colores**, y los dos colores están escritos en `index.css`. En vez de renunciar, se mide sobre la fuente del color en lugar de sobre su resultado.

---

## 36.4. Lo que encontró cada comprobación

### a) Las ocho pantallas contra WCAG 2.1 AA

Se montan enteras, con datos realistas, y se les pasa `axe` exigiendo el nivel **AA** de WCAG 2.1 (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`), más tres reglas que el motor clasifica como recomendación y que aquí se piden por su nombre: `region`, `aria-allowed-role` y `heading-order`.

**Seis de las ocho pasaron a la primera.** La página de interés —la única pública, y la más cuidada del sistema desde el capítulo 25— pasó también con el formulario enseñando sus errores y con el enlace caducado. Las dos que no:

**La pantalla de acceso no estaba dentro de ninguna región.** Un `<div>` que ocupa la pantalla entera. Para quien navega por regiones con un lector, no había a dónde saltar: la única forma de llegar al campo de correo era recorrer el documento desde el principio. Corregido cambiando el elemento por `<main>` —mismo estilo, misma caja, ni un píxel de diferencia—.

**La ficha 360 tampoco**, y ahí el `region` era el síntoma de algo mayor. Ver §36.5.

Además, el modo edición de la ficha saltaba de `h2` a `h4` en sus tres títulos de sección, dejando un agujero en el índice que construye el lector. Ahora son `h3`.

### b) Contraste: un token fallaba, y no era un adorno

La tabla completa, calculada sobre la paleta real. La columna «razón» es **el peor** de los fondos sobre los que ese color se usa:

| Color | Sobre | Razón | Mínimo | |
| :--- | :--- | ---: | ---: | :---: |
| `--text-primary` | `--bg-surface-hover` | 15.38 | 4.5 | ✔ |
| `--text-secondary` | `--bg-surface-elevated` | 6.86 | 4.5 | ✔ |
| **`--text-muted`** | **`--bg-surface-elevated`** | **3.70 → 4.63** | **4.5** | **✘ → ✔** |
| `--hot-text` | `--hot-bg` sobre `--bg-surface` | 6.29 | 4.5 | ✔ |
| `--warm-text` | `--warm-bg` sobre `--bg-surface` | 9.91 | 4.5 | ✔ |
| `--cold-text` | `--cold-bg` sobre `--bg-surface` | 6.47 | 4.5 | ✔ |
| `--success-text` | `--success-bg` sobre `--bg-surface` | 8.70 | 4.5 | ✔ |
| `--hot-text` | `--bg-surface` (el error del formulario, sin fondo propio) | 6.72 | 4.5 | ✔ |
| `--color-primary-text` | `--color-primary-hover` | 16.04 | 4.5 | ✔ |
| `--border-focus` (aro de foco) | `--bg-surface` | 3.21 | 3.0 (1.4.11) | ✔ |

**`--text-muted` era `#64748b` y no llegaba en ninguna de las tres superficies**: 4.16 sobre `--bg-base`, 3.90 sobre `--bg-surface` y 3.70 sobre `--bg-surface-elevated`, contra los 4.5 que exige §1.4.3 para texto normal.

Y no pinta adornos. Pinta **las etiquetas de todos los formularios** (`.form-label`), **las cabeceras de todas las tablas** (`.data-table th`), el texto de ayuda de la página pública y el pie. Es el token que dice **qué es cada campo**.

El valor nuevo es `#75849b`: el **primer peldaño de la misma rampa** —un 35 % del camino de este color al de `--text-secondary`— que alcanza 4.63 en el peor de los tres fondos. Se eligió el primero que pasa y no uno cómodo a propósito: subirlo más acercaría este token al de texto secundario y borraría la jerarquía de tres niveles que la paleta tiene desde el principio. Sigue siendo claramente el más apagado (4.63 contra 6.86).

**Esto es lo más cerca que el capítulo estuvo de «cambiar la paleta», que quedaba fuera de su alcance.** La distinción que se aplicó: cambiar la paleta es elegir otros colores; esto es mover un color la distancia mínima que hace verdadera una afirmación que el sistema ya hacía. Si la decisión se considera fuera de sitio, revertirla es cambiar un valor hexadecimal, y `contraste.test.js` dirá inmediatamente cuánto cuesta.

Los mínimos no se pueden rebajar llamando «grande» al texto pequeño: la norma permite 3.0 a partir de 24 px, o 18.66 px en negrita, y esta interfaz va de 0.7 a 0.875 rem —de 11 a 14 px—. Hay una prueba que lo fija.

**Modo claro y modo oscuro.** El punto 3 pedía comprobar los dos «si existen los dos». No existen: hay un solo tema, el oscuro. Eso también se comprueba en vez de afirmarse —ni `prefers-color-scheme`, ni `data-theme`, ni un segundo `:root`—, para que el día que entre un segundo tema esa prueba lo diga y obligue a duplicar la tabla.

### c) El recorrido con teclado

La página de interés se rellena y se envía **entera sin un solo clic**, en el orden en que se lee la pantalla, y el campo trampa del antispam queda fuera del recorrido —si entrara, quien navega con el teclado lo rellenaría sin saberlo y el servidor le descartaría la solicitud en silencio: el fallo más cruel posible, porque la persona lo hace todo bien y el sistema no le dice nada—.

Lo que sí apareció, en el panel: **cuatro controles que solo se podían pulsar con el ratón**. Eran `<div onClick>`, que no entra en el recorrido del tabulador y no responde a Enter. Se ven pulsables —llevan `cursor: pointer`— y con el teclado no se pueden pulsar:

* las **tres tarjetas de categoría** del tablero (HOT, WARM, COLD), que filtran la lista;
* y la **pastilla de la sesión** de la barra superior.

La cuarta es la grave. Esa pastilla es la **única puerta** al menú de la sesión, y por tanto la única forma de **cerrar sesión** y de **cambiarse la contraseña**. Sin ratón no se podía hacer ninguna de las dos.

Los cuatro son ahora `<button>`, con la tipografía, el color y la alineación devueltos a los del panel para que se vean exactamente igual. La cuarta tarjeta —«Total Prospectos»— **no** se convirtió: no filtra nada, y anunciarla como control diría que se puede pulsar algo que no hace nada.

### d) Los anuncios

Tres cosas distintas, y el proyecto ya hacía bien casi todas:

* **Los errores de campo se asocian** (`aria-invalid` + `aria-describedby`). La página de interés lo hacía entero desde el capítulo 25, incluido el detalle de poner el `aria-describedby` **en el grupo** de «¿Qué necesitas?» y no en el primer radio, porque el error es de no haber elegido ninguno.
* **Los errores generales se anuncian** (`role="alert"`). Veinte sitios ya lo hacían. **Faltaba uno**: el error del **primer** paso del acceso, «correo o contraseña incorrectos». Y la asimetría lo delataba, porque el error del **segundo** paso —el del código, del capítulo 35— sí lo tenía. Quien escribe mal la contraseña veía el mensaje; quien no ve la pantalla se quedaba esperando a que ocurriera algo.
* **Los aciertos también.** Faltaba `role="status"` en «Prospecto actualizado» de la ficha 360 y en el error del alta de prospecto. Lo primero tiene su ironía: es exactamente el mensaje que el capítulo 33 se encargó de que no mintiera —antes decía que había guardado un vaciado que no guardaba—, y no llegaba a quien no ve la pantalla.

Y la cuarta cosa, la que no es un `role` y se olvida siempre: **cuando la pantalla se sustituye entera, el foco tiene que ir a algún sitio**. Ver §36.5.

---

## 36.5. La ficha 360 no era una ventana

Las tres ventanas modales del panel —la ficha 360, el alta de prospecto y la de sesión— se dibujaban con un `<div>` encima de la pantalla. Se veían bien y se cerraban con el ratón, y eso bastó durante diecinueve capítulos para no notar que para el teclado y para un lector de pantalla **no eran una ventana**: eran un trozo más del documento, dibujado por casualidad delante del resto.

Lo que eso significaba, punto por punto:

| Lo que faltaba | Lo que ocurría |
| :--- | :--- |
| `role="dialog"` | El lector no decía que se hubiera abierto nada: aparecía contenido nuevo en medio del documento y ya |
| Un nombre (`aria-labelledby`) | Aun con el rol, habría dicho «diálogo» y no «ficha de Ana Ruiz» |
| Foco inicial dentro | Al abrir la ficha, el foco seguía en el botón de la fila de la tabla: para llegar a la ventana había que recorrer la tabla entera, el menú y el pie |
| Atrapado del foco | Al llegar al último botón, el siguiente `Tab` llevaba a la **página de debajo**: una página tapada por el velo, donde el foco es invisible. A partir de ahí no se sabe dónde se está |
| `aria-modal` | El lector seguía pudiendo navegar por los encabezados y las regiones de lo que hay detrás |
| `Escape` | Con el ratón se cierra pulsando fuera; sin ratón no había forma de cerrarla salvo encontrar la «×» a base de tabulador |
| Devolver el foco al cerrar | Volvía al `<body>`, así que el siguiente `Tab` empezaba desde el principio de la página |

El patrón **ya estaba en el proyecto**: `Campana` tiene `role="dialog"` y su nombre desde el capítulo 28. Se había aplicado en un sitio y en uno solo.

Se escribe una vez, en `frontend/src/components/ventanaModal.js`, y lo usan las tres. Es un *hook* y no un componente que envuelva: un `<Modal>` obligaría a mover el marcado de las tres ventanas dentro de él, y las tres tienen su propio `.modal-content` con sus estilos y su cabecera. El *hook* da las propiedades y no toca la estructura.

**Un detalle del velo, que salió del `linter`.** Al encender el conjunto de reglas de accesibilidad, las tres ventanas señalaban dos manejadores de clic sobre contenido que no es pulsable: uno en el velo, para cerrar, y otro dentro que solo hacía `stopPropagation` para que un clic en la ventana no la cerrara. Lo mismo se consigue mirando **dónde** se pulsó —si el objetivo es el velo y no algo de dentro, se cierra—, así que el de dentro desaparece y el velo queda con `role="presentation"`, que es lo que es: un cristal ahumado, no un control. Para el teclado está `Escape`, que es el equivalente correcto y no un `onKeyDown` colgado de un `<div>`.

**Y el acuse de recibo de la página pública.** El mismo problema en otra forma. Al enviar, el formulario entero desaparece y con él el botón que tenía el foco, que caía al `<body>`. Además, la región `aria-live` que anunciaba el mensaje **se creaba en el mismo instante que su contenido**, que es justo el caso en que los lectores no la leen: una región viva anuncia lo que *cambia* dentro de ella, y para eso tiene que haber estado ahí antes. Llevar el foco al título resuelve las dos cosas a la vez.

---

## 36.6. La clase que no existía, y las quince que tampoco

Medir el contraste obliga a responder una pregunta previa: **¿de dónde salen los colores de esta pantalla?** Para la pantalla de acceso, la respuesta era «de ningún sitio».

Sus tres campos llevaban `className="input"`. En la hoja, la clase se llama `input-field`. Ninguna regla coincidía, así que los campos se dibujaban con el estilo por omisión del navegador —**cajas blancas sobre un panel oscuro**— y la paleta que `contraste.test.js` dice medir no decía nada sobre ellos.

Un `className` mal escrito no rompe nada: no hay error en la consola, no falla ninguna prueba, el componente se monta y la pantalla funciona. Solo se ve distinta, y solo si alguien la mira. Afectaba a **siete campos en tres pantallas**: el acceso, el cambio de contraseña obligatorio y el alta del segundo factor. Las tres donde se escribe una credencial.

Corregido, y comprobado en el navegador antes y después.

Al escribir la comprobación que lo impide aparecieron **quince clases más en el mismo estado**, y esas **no se corrigen**:

| Cuántas | Dónde | Por qué no se corrige aquí |
| :---: | :--- | :--- |
| 14 | `CompartirEnRedes` — el panel de difusión y el del QR | El componente no usa ni un estilo en línea: se apoya entero en catorce clases que no existen, así que se dibuja **sin ningún estilo**. Corregirlo no es escribir bien un nombre: es **diseñar** el panel, elegir colores, espaciados y estados. Eso es rediseñar una pantalla, y el capítulo lo excluyó por escrito |
| 1 | `SessionModal`, el botón «Cerrar sesión» (`btn-danger`) | Pide un aspecto de acción destructiva que la paleta no tiene. Hoy se dibuja como un `.btn` a secas: borde transparente y sin fondo, es decir, no parece un botón. Darle uno exige **un color nuevo en la paleta** |

Quedan anotadas en §6.4 del documento de congelación, y la lista vive en `clases.test.js` con el motivo de cada una. Hace dos cosas: deja constancia de qué falta exactamente, e **impide que la deuda crezca**, porque una clase nueva sin definir no está en la lista y pone la prueba en rojo. Y al revés: si algún día alguien escribe la hoja de `CompartirEnRedes`, la prueba obliga a quitar sus catorce entradas.

---

## 36.7. El rendimiento con volumen, y la consulta por fila

Toda la suite trabaja con seis prospectos. Eso es lo correcto para comprobar reglas —un caso por regla, escrito a mano y legible— y es exactamente lo que **no** detecta un problema de rendimiento: con seis filas, una consulta por fila y una consulta para todas tardan lo mismo.

Se siembran **300 prospectos y 5 000 actividades**, con una distribución **sesgada** a propósito: unos pocos prospectos concentran la mayoría de las actividades. Repartirlas a razón de dieciséis por cabeza mediría una ficha promedio y ninguna cara, y el caso que hay que vigilar es justamente la ficha del prospecto más trabajado de la cartera.

Se miden **dos cosas**, y las dos por motivos distintos:

* **El tiempo** interesa a quien usa el panel y no se puede convertir en una condición estricta: depende de la máquina, y el CI corre en un ejecutor compartido. Los topes van holgados.
* **El número de consultas SQL** no depende de la máquina **en absoluto**. Si un endpoint hace una consulta por prospecto, el contador lo dice con exactitud y lo dice igual en cualquier ordenador. Ahí los topes van apretados, y son los que guardan la puerta.

### La tabla

| Pantalla | Mediana | Consultas (antes → después) |
| :--- | ---: | :---: |
| Lista de prospectos (50 de 300) | 41 ms | 3 |
| Lista filtrada HOT + búsqueda por texto | 35 ms | 3 |
| Ficha 360, el peor caso (289 actividades) | 56 ms | 4 |
| **Bandeja «Hoy» (40 tareas abiertas)** | **54 → 28 ms** | **42 → 2** |
| Informe de publicación (100 perfiles) | 44 ms | 12 |

> **Qué mide y qué no.** SQLite en memoria, sobre este equipo, siete repeticiones descartando la primera —que lleva dentro el arranque y la compilación de las consultas— y tomando la mediana. **Estos milisegundos no son los de producción**: PostgreSQL es más lento en lecturas pequeñas y añade latencia de red. Lo que sí se traslada tal cual es **el número de consultas** y la forma de la curva: un N+1 lo es en los dos motores.

### Lo que encontró

**La bandeja «Hoy» hacía una consulta por tarea.** Cuarenta tareas abiertas, cuarenta consultas de más. La consulta ya hacía `join` con la tabla de prospectos —lo necesita para filtrar y para ordenar por score—, pero no los **cargaba**, así que al pintar el nombre, la empresa y el score de cada tarea, SQLAlchemy iba a buscarlos uno a uno.

En SQLite en memoria eso costaba **el doble de tiempo**. Sobre PostgreSQL por un socket, cuarenta viajes de ida y vuelta cuestan bastante más que el doble.

La corrección es `contains_eager(Tarea.lead)` y no `joinedload`: el `join` ya está hecho, y `joinedload` añadiría un segundo `join` a la misma tabla. **La campana tenía el mismo defecto**, acotado a treinta por `MAX_AVISOS`; se corrigió igual, porque es el mismo defecto y la campana se dibuja en **todas** las pantallas del panel.

### Lo que impide que vuelva

Medir «cuarenta tareas cuestan cuarenta consultas» sirve para encontrarlo una vez. Lo que lo fija es la propiedad, no el caso:

> **Dos tareas y veinte tareas tienen que costar el mismo número de consultas.**

Da igual el número que salga y da igual la máquina. Si crece, hay una consulta por fila. Hay tres pruebas de esa forma —la bandeja, la campana y la lista de prospectos con 10 y con 200— y ninguna necesita sembrar 5 300 filas: cuestan menos de un segundo y se leen enteras.

---

## 36.8. Lo que no se corrigió, y por qué

| Qué | Por qué no |
| :--- | :--- |
| **Las catorce clases de `CompartirEnRedes`** | Escribirlas es diseñar un panel. §36.6, y §6.4 del documento de congelación |
| **`btn-danger`, el botón de cerrar sesión** | Exige un color nuevo en la paleta. Mismo sitio |
| **El borde de los campos sin foco** | `--border-subtle` compuesto sobre el panel da **1.12:1** contra lo que lo rodea: el contorno de un campo es prácticamente invisible hasta que se le pone el foco. WCAG §1.4.11 pide 3.0 para lo que identifica un control. Subirlo es una decisión de paleta con efecto en **todas** las pantallas, no una corrección |
| **El historial de la ficha no se pagina** | Trae las actividades enteras. Con 289 tarda 56 ms y va sobrado; el número queda medido para el día que alguien tenga 3 000 |
| **Que un lector de pantalla real lo anuncie bien** | Ninguna herramienta automática responde a eso. Lo comprobado es que el marcado que esos lectores leen esté puesto y bien puesto. Sigue siendo tarea del punto 18 de §6.3, «el panel no se ha recorrido con una persona dentro» |
| **`var(--accent-primary)` en el girador de carga de `App.jsx`** | Ese token no existe en la paleta —el que hay se llama `--color-primary`—, así que el borde superior del girador se queda sin color. Es cosmético y de un elemento que dura lo que una petición; queda anotado |

---

## 36.9. Un suelo de cobertura que ya estaba roto

Al medir la cobertura del cliente con el trabajo de este capítulo dentro, el pipeline se puso en rojo. La primera sospecha —lo nuevo bajó la media— resultó falsa: **quitando todos los archivos nuevos, el resultado era el mismo**.

La comprobación honrada era medir `main` tal cual. Con un árbol de trabajo aparte sobre `092a215`:

```
Tests  385 passed (385)
api.js   87.5 | 83.44 | 91.78 | 90.85 | ...133-163,660
ERROR: Coverage for lines (93.68%) does not meet global threshold (94%)
ERROR: Coverage for functions (93.1%) does not meet global threshold (94%)
ERROR: Coverage for statements (91.04%) does not meet global threshold (92%)
ERROR: Coverage for branches (85.37%) does not meet global threshold (86%)
```

**El suelo estaba roto antes de empezar este capítulo.** Las líneas 133-163 de `api.js` son las **cinco funciones del segundo factor** que entró el capítulo 35, y ninguna tenía prueba. El trabajo de aquel capítulo se verificó ejecutando la suite, que pasaba; la cobertura se mide con otra orden (`npm run test:coverage`), y es la que el CI ejecuta.

Entra por §1 —«una guarda del CI en rojo»— así que se corrigió aquí: se prueban las cinco del segundo factor y, de paso, las cinco de la agenda del capítulo 28 y la de la dirección pública del 34, que tampoco estaban en la tabla de rutas del cliente.

Las pruebas del acceso en dos pasos no son cinco envoltorios cualesquiera. `login` es la única función del cliente que puede devolver **dos cosas distintas** —una sesión o un desafío—, y confundirlas tiene consecuencias en los dos sentidos: abrir sesión con un desafío deja al panel creyendo que hay usuario, y tratar una sesión como desafío pide un código que nadie ha pedido. También se fija que el desafío viaja **en el cuerpo y nunca como `Authorization`**, que es lo que impide saltarse el segundo factor no pidiéndolo.

La cobertura pasa de **91.0 / 85.4 / 93.1 / 93.7** a **95.7 / 89.4 / 98.3 / 98.3**, y el suelo sube con ella a 95 / 89 / 98 / 98, como el propio archivo de configuración decía que debía pasar.

---

## 36.10. Las guardas, y la prueba de que vigilan

### En la suite

| Archivo | Qué fija |
| :--- | :--- |
| `pruebas/accesibilidad.test.jsx` | Las ocho pantallas contra WCAG 2.1 AA, en trece estados distintos |
| `pruebas/contraste.test.js` | La paleta contra el mínimo de la norma, leyéndola de `index.css`; y que ningún color de texto se quede sin par declarado |
| `pruebas/teclado.test.jsx` | El recorrido real del tabulador, el atrapado del foco, `Escape`, la devolución del foco y que no haya `tabindex` positivos |
| `pruebas/anuncios.test.jsx` | Que cada error se asocie o se anuncie, y los aciertos también |
| `pruebas/clases.test.js` | Que toda clase del marcado exista en la hoja, salvo la deuda declarada |
| `pruebas/linter.test.js` | Que el conjunto de reglas de accesibilidad **siga encendido** |
| `tests/test_rendimiento_con_volumen.py` | El coste de las cuatro pantallas con 300 prospectos, y que ninguna crezca por fila |

El último merece una nota. `eslint` es la mitad barata de este capítulo —encontró los cuatro `<div onClick>` sin ejecutar nada—, pero una regla se apaga escribiendo `'off'`, y **cuando se apaga el pipeline se pone verde**, al revés de lo que hace una prueba al quitarla. Por eso la configuración se comprueba desde la suite: ahí, apagar una regla pone algo en rojo. Es el mismo criterio con el que el capítulo 22 obligó a que las imágenes llevaran huella y el 34 a que ninguna ruta de gestión entrara en la puerta pública.

Lo que `linter.test.js` **no** hace es exigir las 34 reglas por su nombre: eso ataría el proyecto a una versión del plugin y se rompería al actualizarlo por motivos de seguridad, que es justo cuando no conviene tener el pipeline en rojo por algo que no es el problema. Lo que exige es que el conjunto entre entero, y que lo apagado esté declarado con su motivo escrito en el propio archivo.

**Una regla apagada:** `no-autofocus`, en los dos únicos sitios donde el proyecto usa `autoFocus`, los dos en la pantalla de acceso. La regla prohíbe sin excepciones y el motivo que da es real: en una página con contenido, mover el foco a un campo al cargar se salta el título, los avisos y la navegación. Aquí no hay nada que saltarse —la pantalla **es** el formulario— y en el segundo paso es más que cómodo: el formulario anterior acaba de desaparecer con el foco dentro, así que sin `autoFocus` el foco caería al `<body>`. Es el mismo problema que el acuse de recibo de §36.5, y la misma solución.

### En el CI

`configuracion-peligrosa` pasa de **40 a 42 controles**:

* **Las ocho pantallas siguen bajo revisión.** Las ocho por el componente que montan —el `import`, no el título del `describe`, que se puede cambiar sin querer—; las cuatro etiquetas del nivel AA; y que `color-contrast` siga siendo la **única** regla apagada.
* **Dependencias declaradas y sin silencios.** `axe-core` directa y fijada a una versión exacta; ningún `eslint-disable` de una regla de accesibilidad en todo `src/` —silenciarla en línea la apaga en el sitio exacto donde algo está mal y no deja rastro en ninguna prueba—; las seis comprobaciones en su sitio; y el `contains_eager` de la bandeja.

### La reinyección

Una guarda que no falla al reintroducir el defecto que dice vigilar no está vigilando nada. Se reintrodujeron **veinte** defectos, uno por uno, comprobando que la guarda correspondiente se pone en rojo y restaurando el archivo después:

| | Defecto reintroducido | Lo detecta |
| :---: | :--- | :--- |
| 1 | La ventana modal deja de ser una ventana (quitar `role="dialog"`) | accesibilidad + teclado |
| 2 | El foco vuelve a escaparse de la ventana | teclado |
| 3 | Al cerrar, el foco ya no vuelve | teclado |
| 4 | `Escape` deja de cerrar la ficha | teclado |
| 5 | El texto apagado vuelve a `#64748b` | contraste |
| 6 | La pantalla de acceso se queda sin región | accesibilidad |
| 7 | «Correo o contraseña incorrectos» deja de anunciarse | anuncios |
| 8 | «Prospecto actualizado» deja de anunciarse | anuncios |
| 9 | El acuse de recibo deja de recibir el foco | teclado |
| 10 | Las tarjetas de categoría dejan de ser alcanzables | teclado |
| 11 | Un `tabindex` positivo rompe el orden del foco | teclado |
| 12 | Una clase mal escrita vuelve a entrar | clases |
| 13 | La bandeja «Hoy» vuelve al N+1 | rendimiento |
| 14 | La campana vuelve al N+1 | rendimiento |
| 15 | El conjunto de reglas del `linter` se vuelve a apagar | linter |
| 16 | Una pantalla sale de la revisión de accesibilidad | CI |
| 17 | Se apaga una regla más de `axe` | CI |
| 18 | `axe-core` deja de ir fijada a una versión exacta | CI |
| 19 | Un `eslint-disable` de accesibilidad en el código | CI |
| 20 | Desaparece el `contains_eager` de la bandeja | CI |

**20 de 20 detectados.** El 16 no lo detectó a la primera: comentar el `import` con `//` seguía contando como presente, porque el `grep` no estaba anclado al principio de la línea. La guarda se corrigió y volvió a probarse con las dos formas de quitarlo —comentado y borrado—.

---

## 36.11. Lo medido

| | |
| :--- | :--- |
| Pruebas del cliente | **472** en 34 archivos (antes 385 en 29) |
| Cobertura del cliente | **95.7 / 89.4 / 98.3 / 98.3** (antes 91.0 / 85.4 / 93.1 / 93.7, **por debajo del suelo**) |
| Pruebas del backend | **1494** y 2 omitidas (antes 1485) |
| `ruff check .` y `npm run lint` | Limpios, con **34 reglas** de accesibilidad encendidas (antes 1) |
| Pantallas contra WCAG 2.1 AA | **8 de 8**, en 13 estados |
| Pares de color medidos | **10**, uno corregido |
| Controles de `configuracion-peligrosa` | **42** (antes 40) |
| Defectos reinyectados / detectados | **20 / 20** |
| Dependencias nuevas en el lock | **1 línea**, 0 paquetes, 0 versiones movidas |

---

## 36.12. Qué queda abierto de esto

Entra en §6.4 del documento de congelación:

* **30.** `CompartirEnRedes` se dibuja sin ningún estilo: catorce clases que el marcado pide y la hoja no define. Escribirlas es diseñar el panel.
* **31.** `btn-danger` no existe; «Cerrar sesión» no parece un botón. Exige un color nuevo en la paleta.
* **32.** El borde de un campo sin foco tiene 1.12:1 contra lo que lo rodea, y WCAG §1.4.11 pide 3.0 para lo que identifica un control. Es una decisión de paleta con efecto en todas las pantallas.
* **33.** `var(--accent-primary)` no existe: el girador de carga de `App.jsx` se queda sin color en su borde.

Y sigue abierto, donde ya estaba, el punto **18** de §6.3: **el panel no se ha recorrido con una persona dentro**. Este capítulo comprueba que el marcado que un lector de pantalla necesita esté puesto y bien puesto, que es la parte verificable sin una persona delante. Si lo que ese lector dice se entiende, no lo puede responder ninguna herramienta.

---

## 36.13. Apéndice del 29-09-2026: el panel servía un bundle de cinco días antes

Este apartado se añade cuatro días después de cerrar el capítulo, y cuenta algo que el
capítulo no hizo sino que **encontró al comprobarse**. Se deja aquí, y no en un capítulo
nuevo, porque el defecto llevaba desde el capítulo 17 y lo único que lo sacó a la luz fue
levantar la pila para mirar el trabajo del 36.

### Lo que pasó

Con la pila arriba y sana —las cinco comprobaciones en verde, la migración del segundo
factor aplicada contra PostgreSQL por primera vez y la puerta estrecha negando sus 25
rutas—, el panel seguía enseñando **campos blancos sobre el panel oscuro**. Es decir, el
defecto de §36.6, el que este capítulo corrigió.

Preguntándole al navegador por la clase del campo:

```
clase: "input"      ← la que no existe
--text-muted: #64748b   ← el color anterior a §36.4
```

El contenedor servía el bundle del **24 de septiembre**. El capítulo 36 se cerró el 25.

### Por qué, y por qué no había ningún síntoma

El `Dockerfile` del cliente tiene cuatro etapas, y las dos últimas son destinos:

```
FROM ... AS build-stage
FROM ... AS servidor
FROM servidor AS production-stage     ← compila la SPA desde el código
FROM servidor AS desde-artefacto      ← NO compila: copia el dist/ del contexto
```

`devops/docker-compose.yml` no declaraba `target`. **Cuando un servicio de Compose no
declara `target`, Docker construye la última etapa del archivo**, y la última es
`desde-artefacto` — la del pipeline, que existe precisamente para *no* compilar: el CI
compila una vez en el trabajo `frontend`, corre ahí las pruebas y el `linter` sobre ese
mismo código, y mete el artefacto probado en la imagen.

En un portátil eso significa copiar el `frontend/dist/` que haya en la carpeta. Y como
`dist/` está en `.gitignore`, ese directorio es lo que dejó la última vez que alguien
ejecutó `npm run build`, sin fecha ni relación con la revisión que se está levantando.

**La cabecera del propio Dockerfile afirmaba lo contrario**, con estas palabras:
*«production-stage (por defecto) — compila la SPA aquí dentro. Es lo que usa
`docker compose up --build` en un portátil»*. No lo era. La etiqueta «por defecto» era
cierta el día que se escribió, cuando `production-stage` era la última; dejó de serlo en
cuanto se añadió una etapa debajo, y nada volvió a leer esa frase.

Lo que hace a este defecto difícil de ver es que **`desde-artefacto` lleva su propia
comprobación dentro**, escrita en el capítulo 17 justo para que un artefacto vacío no pasara
inadvertido:

```dockerfile
RUN test -f /usr/share/nginx/html/index.html && test -d /usr/share/nginx/html/assets
```

Esa comprobación pasa perfectamente con un bundle de hace cinco días. Comprueba que el
artefacto **no llegue vacío**, no que sea el de este código. Son dos preguntas distintas y
solo se estaba haciendo la primera.

En una máquina limpia el fallo sí es ruidoso —sin `dist/`, la construcción se detiene ahí—.
En cualquier máquina que haya compilado alguna vez, sirve algo antiguo **para siempre** y
sin decir nada.

### Lo corregido

1. `devops/docker-compose.yml` declara `target: production-stage`, con el motivo escrito al
   lado.
2. La cabecera del `Dockerfile` deja de afirmar que hay una etapa «por defecto», y explica
   que la que Docker elige es la última.
3. Un control nuevo del CI, el **43**: lee el compose como YAML —no con expresiones
   regulares, que fue el primer intento y cruzaba las fronteras entre servicios— y, para
   cada servicio que se construye, calcula **qué etapa se construiría de verdad** y exige
   tres cosas:
   * que un `target` declarado **exista** en su Dockerfile;
   * que un Dockerfile de **tres etapas o más** declare `target`. Con dos, la última es la
     de ejecución y no hay ambigüedad; a partir de tres, cuál es la buena no se deduce del
     orden, y el orden es lo único que Docker mira;
   * que **nunca** se construya la etapa que consume un artefacto ya compilado.

   Reinyectados los tres casos —quitar el `target`, apuntarlo a una etapa que no existe y
   apuntarlo a la del pipeline—, el control los detecta los tres y nombra cuál es.

Tras reconstruir con el `target` correcto, el bundle de la imagen pasa de 341 580 a 352 215
bytes, `--text-muted` es `#75849b`, la clase del campo es `input-field` y aparecen
`aria-modal` y `ficha-360-titulo`. Es decir: el capítulo 36 estaba en el disco desde el
día 25 y no había llegado nunca a ejecutarse.

### Lo que esto dice, y que vale más que el arreglo

Todo lo que este capítulo midió lo midió sobre el **código fuente**: `vitest` monta los
componentes del repositorio, `axe` los audita, el contraste se lee de `index.css`. Ninguna
de esas comprobaciones tiene forma de saber qué acabó dentro de la imagen, y ninguna es
menos válida por ello: lo que fallaba no era el código ni su verificación, era el empaquetado.

Es exactamente la lección que el documento de congelación ya se había llevado en el capítulo
32 con el volumen `deriva` —un defecto que ninguna lista preveía y que solo apareció al
levantar la pila de verdad— y la razón de que el proyecto tenga esa costumbre escrita. La
suite responde «¿hace el código lo que promete?». Levantar la pila responde otra pregunta:
«¿es ese el código que se está ejecutando?».
