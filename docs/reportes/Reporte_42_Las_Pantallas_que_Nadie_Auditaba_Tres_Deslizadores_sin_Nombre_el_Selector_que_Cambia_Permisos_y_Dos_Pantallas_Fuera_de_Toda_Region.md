# Reporte 42 — Las pantallas que nadie auditaba: tres deslizadores sin nombre, el selector que cambia permisos y dos pantallas fuera de toda región

**Capítulo 44** · Accesibilidad e inventarios derivados · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 2 de octubre de 2026
**Alcance:** la lista de pantallas de la auditoría de accesibilidad, que estaba escrita a mano y cubría 8 de las 18 que llevan controles de formulario; las cuatro infracciones que aparecieron en las nueve que faltaban —tres deslizadores sin nombre accesible, el selector del rol de una cuenta sin nombre, un `aria-label` que ARIA no admite donde estaba y dos pantallas enteras fuera de toda región—; las tres cajas del cambio de contraseña que se nombraban con el `placeholder` (§6.4 punto 44); la lista derivada del código para que una pantalla nueva nazca en rojo; y un control de regresión con veinticuatro defectos reintroducidos.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 42 es el capítulo 44. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 44.1. Una lista escrita a mano, y un defecto que la seguía

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación para **el punto 44 de §6.4** y para la **mitad medible del punto 18 de §6.3**, y para nada más.

El punto de partida no es ninguno de los dos. Es una frase de la cabecera de `frontend/src/pruebas/accesibilidad.test.jsx`, escrita en el capítulo 36:

> *«Accesibilidad: **las ocho pantallas**, revisadas por un motor y no por una lectura.»*

Era verdad. Ocho pantallas pasan `axe-core` con el nivel AA de WCAG 2.1 en cada ejecución de la suite, y una que deje de cumplirlo pone el `pipeline` en rojo. Lo que la frase no dice es de cuántas: **el cliente tiene dieciocho componentes con controles de formulario**, con 105 controles entre todos. La auditoría montaba ocho de los dieciocho —más la tabla de prospectos y la campana, que caen dentro del tablero que sí se audita—, y las **nueve** restantes, con **39 de las 105 cajas**, no las había mirado ningún motor nunca.

Es exactamente la forma que el capítulo 43 encontró en `PARES`, la tabla de pares de colores de `contraste.test.js`: una comprobación real, que mide bien, sobre **un inventario que alguien escribió a mano**. Lo que la suite mide no es el cliente; es la lista.

Y la prueba de que eso no es una observación teórica está escrita en el propio repositorio. `LoginScreen.jsx` abre así desde el capítulo 36:

```jsx
// `<main>` y no un `<div>`: es la pantalla entera y no estaba dentro de ninguna región,
```

El cambio obligatorio de contraseña y el alta del segundo factor son **también** la pantalla entera —`App.jsx` las devuelve en lugar del panel—, nunca se montaron en la auditoría, y las dos seguían siendo un `<div>`. La diferencia entre las tres no es su naturaleza: es que a una la montaba la lista.

---

## 44.2. Qué cuenta como pantalla, y cuántas hay

«Pantalla» no es una palabra que se pueda dejar sin definir en una guarda, porque de su definición depende la lista. La que se usa aquí es: **un componente con al menos un control de formulario** —`<input>`, `<select>` o `<textarea>`—, descartando los de tipo `hidden`, que no se ven, no se enfocan y no tienen nada que nombrar.

Se elige así por lo que un motor sin píxeles sabe ver: un control es lo que hay que nombrar, etiquetar, asociar a su error y alcanzar con el teclado, y ahí se concentra la mayoría de las reglas estructurales de WCAG. Un componente que solo pinta —una tarjeta de KPI, un gráfico, la vista previa de un post— se audita de paso, dentro de la pantalla que lo monta.

El recuento, derivado del código:

| Componente | Controles | ¿La auditoría lo montaba? |
| :--- | :---: | :--- |
| `LeadDetailModal` | 18 | sí |
| `NewLeadModal` | 16 | sí |
| `AdminPanel` | 12 | **no** |
| `ScoringSimulator` | 11 | **no** |
| `PaginaDeInteres` | 11 | sí |
| `Publicaciones` | 10 | sí |
| `CambioDeContrasenaObligatorio` | 3 | **no** |
| `CerrarProspecto` | 3 | **no** |
| `InformeDePublicacion` | 3 | sí |
| `LoginScreen` | 3 | sí |
| `SessionModal` | 3 | **no** |
| `AltaDelSegundoFactor` | 2 | **no** |
| `BandejaSinAsociar` | 2 | **no** |
| `CompartirEnRedes` | 2 | **no** |
| `DerechosDelTitular` | 2 | sí |
| `PanelDeDesenlaces` | 2 | sí |
| `AsignarAsesor` | 1 | **no** |
| `LeadsTable` | 1 | dentro del tablero |
| **Total** | **105** | **8 de 18 montadas una por una** |

Las nueve sin auditar suman **39 controles**, y entre ellas están las dos pantallas con más cajas después de la ficha y el alta de un prospecto: la gestión de cuentas y el simulador.

El recorrido del marcado no se escribió para esto. Es `cajasDeFormulario`, el mismo que el capítulo 43 tuvo que escribir con un equilibrado de llaves porque `<input[^>]*?>` se corta en el primer `>`, que casi siempre es el de la flecha de un `onChange={(e) => …}`; con ese recorte una cuenta de «19 de 103» pasó por buena hasta que la de verdad resultó ser «11 de 88». Vivía dentro de `avisos.test.js`; este capítulo lo sube a `pruebas/codigo.js`, que es donde el capítulo 39 puso las tres cosas que varias guardas compartían, y por el mismo motivo: dos copias del recorrido son dos ideas distintas de qué es un control, y el día que una se quede corta su barrido seguirá verde sin haber mirado nada.

---

## 44.3. Los tres deslizadores que no decían de qué eran

El simulador de scoring tiene tres deslizadores: páginas vistas, clics en correos y días de inactividad. Estaban escritos así:

```jsx
<div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
  <span>Páginas Vistas:</span>
  <strong style={{ fontFamily: 'var(--font-mono)' }}>{formData.page_views}</strong>
</div>
<input
  type="range"
  min="0"
  max="25"
  value={formData.page_views}
  onChange={(e) => handleChange('page_views', parseInt(e.target.value))}
  style={{ width: '100%', marginTop: '4px' }}
/>
```

Sin `id`. Sin `<label>`, ni envolviéndolo ni apuntándolo. Sin `aria-label`, sin `aria-labelledby`, sin `title` y sin `placeholder`. El rótulo es un `<span>` que está **al lado**, y «al lado» es una relación visual: no existe para el árbol de accesibilidad. Lo que un lector de pantalla anuncia al llegar ahí es:

> «Control de deslizamiento. 6. Mínimo 0, máximo 25.»

Seis de veinticinco de qué, no lo dice. Son tres controles seguidos, los tres con el mismo anuncio y valores distintos, en la pantalla que sirve para entender cómo puntúa el modelo. `axe` lo clasifica como **crítico** —regla `label`, «Form elements must have labels»— y es §4.1.2 (nombre, función, valor) y §1.3.1 (información y relaciones) de WCAG 2.1 sin cumplir.

El arreglo son tres líneas y media: el `<span>` pasa a `<label htmlFor>` y el control recibe su `id`.

```jsx
<label htmlFor="sim-page-views">Páginas Vistas:</label>
…
<input id="sim-page-views" type="range" …
```

El número de la derecha se queda **fuera** de la etiqueta, y eso es una decisión: un `type="range"` ya anuncia su valor por sí mismo, así que meter el `<strong>` dentro de la `<label>` haría que el lector dijera la cifra dos veces.

Lo que vale la pena señalar es lo que había justo encima, escrito en el capítulo 36:

```jsx
/* Cada `label` lleva `htmlFor` y cada control su `id`. Antes eran cuatro etiquetas
   sueltas: se leían bien con los ojos, pero no estaban asociadas a nada. […] Las
   casillas de más abajo no lo necesitan porque el `input` va DENTRO de su propia
   `label`. */
```

El comentario es cierto de los cuatro campos de arriba y de las cuatro casillas de abajo. De los tres deslizadores que hay en medio no dice nada, y son los únicos de la pantalla que no cumplen ninguna de las dos formas que describe.

---

## 44.4. Por qué no lo vio ninguna de las guardas que había

Este proyecto tiene tres cosas mirando esto, y las tres pasaron por encima. Conviene escribir por qué cada una, porque el motivo es distinto y ninguno es un descuido.

**El `linter`.** `eslint-plugin-jsx-a11y` está con sus 34 reglas encendidas desde el capítulo 36, y la que mira esto es `label-has-associated-control`. Su recorrido **empieza por la `<label>`**: comprueba que cada etiqueta tenga un control. Un control que no tiene ninguna etiqueta en ningún sitio no aparece en su recorrido, porque no hay etiqueta de la que partir. La regla hace lo que dice y la pregunta es la contraria.

**La guarda de `.input-field`** (capítulo 43, control 57). Recorre todas las cajas de formulario y exige la clase que la hoja mide, y excluye explícitamente los deslizadores:

```js
// Lo que no es una caja de texto: una casilla, un botón de radio, un deslizador y un
// campo oculto no tienen contorno que medir ni valor que rechazar por campo.
const NO_SON_CAJAS = ['checkbox', 'radio', 'hidden', 'range', 'file'];
```

Para su pregunta, la exclusión es correcta: un `range` no tiene contorno de 3:1 que medir ni 422 que repartir. Pero un control sin nombre accesible es un control sin nombre accesible, sea del tipo que sea, y por ese hueco —abierto a propósito, con su motivo escrito— pasaron los tres.

**`axe`.** Lo caza. Con impacto crítico y con el selector exacto. En la pantalla que la auditoría no montaba.

Es decir: no faltaba una herramienta. Las tres piezas estaban, la que sabía ver el defecto estaba instalada y llamada en cada ejecución, y lo único que faltaba era que la lista de pantallas incluyera esa pantalla.

---

## 44.5. El selector que cambia los permisos de una persona

Al meter la gestión de cuentas en la auditoría apareció una segunda infracción crítica, y esta no estaba en ninguna lista ni en ninguna sospecha. En la tabla de cuentas, cada fila lleva un `<select>` para cambiar el rol:

```jsx
<td>
  <select
    className="input-field" style={{ padding: '4px 6px', fontSize: '0.78rem' }}
    value={usuario.role}
    disabled={ocupado === usuario.id}
    onChange={(e) => cambiarRol(usuario, e.target.value)}
  >
```

Sin nombre accesible —regla `select-name`, **crítica**—. La intuición es que la cabecera de la columna lo nombra, y es falsa: el encabezado de una tabla nombra la celda, no el control que hay dentro. Lo que se anuncia es «lista desplegable, Asesor Comercial», sin decir **de quién**, y hay uno por fila.

El nombre va en un `aria-label` y nombra a la persona, por lo mismo que las filas son varias:

```jsx
aria-label={`Rol de ${usuario.full_name}`}
```

Un texto fijo —«Rol»— habría callado al motor y habría dejado seis controles indistinguibles en una pantalla donde lo que se cambia son los permisos de alguien. Es el mismo criterio que el formulario de restablecer contraseña que el capítulo 43 puso dos filas más abajo, que ya nombraba a la persona en su etiqueta.

---

## 44.6. Un `aria-label` donde ARIA no lo admite, y la prueba verde encima

La tercera infracción es de otra clase, y es la más instructiva. El alta del segundo factor enseña el código QR que hay que escanear, y lo nombraba así:

```jsx
<div
  aria-label="Código QR para la aplicación de autenticación"
  style={{ background: '#fff', padding: '12px', … }}
  dangerouslySetInnerHTML={{ __html: alta.qr_svg }}
/>
```

La intención es correcta y el resultado no existe: **ARIA prohíbe nombrar un elemento genérico**. Un `div` sin `role` no tiene rol en el árbol de accesibilidad, y un elemento sin rol no admite nombre accesible; el atributo se ignora. `axe` lo da como `aria-prohibited-attr`, impacto **serio**. El único dibujo de esa pantalla —el que hay que escanear para poder entrar— no tenía nombre, aunque alguien se hubiera tomado el trabajo de escribírselo.

El arreglo es una línea: `role="img"` junto al `aria-label`, que es exactamente como lo escribe `CompartirEnRedes` desde el capítulo 39 para su propio QR.

Lo que hay que contar es la otra mitad. `AltaDelSegundoFactor.test.jsx` tiene esta prueba, verde desde el capítulo 35:

```js
expect(await screen.findByLabelText(/Código QR/)).toBeInTheDocument();
```

`getByLabelText` de `@testing-library` lee el atributo **tal cual**, sin preguntar si ARIA lo admite en ese elemento. Así que la prueba comprobaba que el atributo estaba escrito, lo cual era verdad, y lo documentaba como «el QR tiene nombre», lo cual no lo era. Es la misma forma que el capítulo 43 encontró en los dos formularios de contraseña —una prueba que pasa por encima de la capa donde está el defecto y lo deja escrito como comprobado—, en otro sitio y con otra herramienta: no un doble puesto demasiado arriba, sino una **consulta más permisiva que la norma que se quiere cumplir**.

De aquí sale la regla que este capítulo deja escrita: una consulta de la biblioteca de pruebas no es una medición de accesibilidad. Lo que decide si un marcado es accesible es el motor que implementa la norma, y por eso la auditoría tiene que pasar por **todas** las pantallas y no por las que alguien listó.

---

## 44.7. Dos pantallas enteras fuera de toda región

La cuarta infracción es `region` —«todo el contenido tiene que estar dentro de una marca de región»—, que no es AA sino una de las tres reglas de `best-practice` que esta auditoría pide por su nombre desde el capítulo 36, con su motivo escrito: sin regiones, quien navega por regiones con un lector de pantalla no tiene por dónde saltar y recorre la pantalla entera elemento a elemento.

`App.jsx` puede devolver tres cosas en lugar del panel:

```jsx
if (user.must_change_password) {
  return <CambioDeContrasenaObligatorio … />;
}
if (faltaElSegundoFactor(user)) {
  return <AltaDelSegundoFactor … />;
}
```

—más la pantalla de acceso cuando no hay sesión—. Las tres son la página completa y en ninguna hay un `<main>` por encima, porque no hay nada por encima. La de acceso lo tiene desde el capítulo 36, con el comentario citado en §44.1. Las otras dos eran un `<div>`.

Las dos son además pantallas de las que no se puede salir: una cuenta recién creada **solo** puede ver el cambio obligatorio, y una cuenta de administración sin segundo factor **solo** puede ver el alta. El texto de la segunda lo dice en su propio párrafo —«hasta que lo active, esta es la única pantalla disponible»—. Es decir: de las tres pantallas que son obligatorias y únicas, dos estaban enteras fuera de cualquier región.

El arreglo es cambiar la etiqueta de la raíz, en los dos casos.

---

## 44.8. §6.4 punto 44: el nombre que desaparece al escribir

El punto decía:

> **44.** *«Los tres campos del cambio de contraseña se nombran con un `placeholder`. No con una etiqueta: el marcador desaparece al escribir, así que quien vuelve al campo ya no sabe cuál es […]. No es un incumplimiento claro de AA —el marcador da nombre accesible al campo— y ponerles etiqueta cambia la maquetación de un modal, así que no entró con el capítulo que sí les dio la clase de la hoja y el reparto de su error.»*

El punto es **correcto en todo**, incluido lo que parece su parte débil. Al montar el panel de la sesión en la auditoría, `axe` da **cero infracciones**: un `placeholder` sí proporciona nombre accesible a un campo, así que ningún motor se queja. Y eso es justamente lo que hay que escribir: la auditoría automática no contesta esta pregunta, porque lo que falla no es que no haya nombre, es que el nombre **se va en cuanto se usa el campo**.

Son tres cajas de contraseña, una debajo de otra, y las tres se ven iguales en cuanto hay algo escrito: una fila de puntos. Con el marcador como único nombre, quien vuelve a la segunda no puede saber si es la nueva o la repetición, y quien usa un lector de pantalla con el campo ya relleno tampoco.

Las tres tienen ahora su `<label>`, con `className="form-label"` —la clase que la hoja ya define, no un `style` nuevo—, y el marcador se queda solo donde dice algo que la etiqueta no dice: «Mínimo 12 caracteres».

```jsx
<label htmlFor="sesion-nueva" className="form-label">Contraseña nueva</label>
<input id="sesion-nueva" type="password" className="input-field" placeholder="Mínimo 12 caracteres" …
```

Y las pruebas de ese formulario dejan de buscar los campos por el marcador y los buscan por su etiqueta, que es la diferencia que el cambio introduce. Hay además una prueba nueva que comprueba lo que el punto describía: que el nombre **sigue ahí con el campo lleno**, que es el estado en que el marcador ya no está.

---

## 44.9. Montarlas como las monta la aplicación, sin apagar la regla que estorba

Meter nueve pantallas en la auditoría no es importarlas y llamar a `axe`. Un bloque de una pestaña del panel vive dentro del `<main>` de `App.jsx`; montado suelto produce media docena de fallos de `region` que **no son suyos**, y la salida fácil —apagar `region`— la apagaría también para las nueve pantallas que hoy la cumplen, que es cambiar un hueco por otro más grande.

Así que lo que se escribe en el archivo es dónde vive cada cosa:

* **un bloque de pestaña** va dentro de `<main>`, con un ayudante de una línea, `enElPanel(…)`, porque ahí lo pone `App.jsx`;
* **un modal** se monta solo: su `role="dialog"` ya es su región;
* **una pantalla entera** se monta sola **y tiene que traer su propia región**, porque no hay nada alrededor. Las dos que no la traían son el arreglo de §44.7, y la prueba lo afirma aparte, con un `expect(document.querySelector('main')).not.toBeNull()`, para que el día que alguien se la quite el fallo diga qué falta y no solo que `region` no pasa.

Cada pantalla se monta además en el estado donde están sus controles, que no es el inicial: la gestión de cuentas con la cartera cargada y con el formulario de restablecer abierto, la bandeja sin asociar con su confirmación de descarte desplegada, el cierre de un prospecto con el desenlace ya elegido —que es cuando aparecen el motivo, el tramo y la fecha—. Auditar solo el estado de reposo es auditar la mitad de la pantalla, que es la lección que el capítulo 40 ya había dejado escrita en este mismo archivo para los campos marcados con `aria-invalid`.

---

## 44.10. La lista sale del código

El arreglo de las cuatro infracciones es pequeño. Lo que impide que vuelva a pasar es `frontend/src/pruebas/pantallas.test.js`, que hace con las pantallas lo que `tokens.test.js` hace con la paleta desde el capítulo 39 y lo que `avisos.test.js` hace con los pares de colores desde el 43: **deriva el inventario del código**.

Recorre los componentes, se queda con los que tienen al menos un control de formulario y exige que cada uno aparezca montado en `accesibilidad.test.jsx`. Una pantalla nueva nace en rojo, con un mensaje que dice cuántos controles tiene y cómo montarla. Es el único momento en que alguien está mirando: después, nadie vuelve a leer la lista.

Tres detalles del diseño de la guarda, los tres por lecciones anteriores:

1. **Se comprueba a sí misma antes de afirmar nada.** Un barrido que no encontró ninguna pantalla contesta «todas auditadas» con la misma cara que uno que lo comprobó. La guarda exige haber encontrado más de doce pantallas y más de ochenta controles antes de decidir que no falta ninguna.
2. **Busca la etiqueta JSX, no el nombre.** `AdminPanel` aparece escrito en la cabecera de media docena de archivos; una guarda que se conforme con encontrar la palabra se la encuentra en su propia documentación, que es la lección del capítulo 37. Se quitan los comentarios primero y el patrón exige el `<`. Hay una prueba de eso: un comentario que nombra `AdminPanel` no cuenta, y un `render(<AdminPanel …/>)` sí.
3. **No comprueba los nombres accesibles.** Eso lo hace `axe`, que sabe la norma. La guarda solo responde «¿se mira esta pantalla?», y es importante que no intente responder más: una guarda que opina de accesibilidad con expresiones regulares es la que después hace creer que algo está comprobado.

---

## 44.11. Un doble con la forma equivocada, que nadie había tenido que usar

Al montar el cierre de un prospecto con el desenlace elegido, la prueba reventó. El doble compartido de la auditoría devolvía esto:

```js
api.fetchOpcionesDeCierre.mockResolvedValue({
  resultados: [{ clave: 'ganado', etiqueta: 'Ganado' }, …],
  motivos: { ganado: [{ clave: 'precio', … }], perdido: [ … ] },
  tramos: [ … ],
});
```

El servidor manda los motivos **dentro de cada resultado** (`OpcionDeResultado.motivos`), con su `pide_tramo` al lado, y de ahí los lee el formulario. El doble los ponía en un diccionario de primer nivel y no traía `pide_tramo`.

Mientras ninguna prueba eligiera un desenlace, la diferencia no salía: la pantalla no llegaba a pintar la lista de motivos, así que la forma equivocada nunca se consultaba. Es la misma familia que la memoria que dejó el capítulo 43 —un doble que no tiene la forma real de la respuesta no está probando el tramo que la interpreta—, con la variante de que aquí el doble no ocultaba un defecto: solo esperaba a que alguien lo usara. Corregido a la forma del servidor.

---

## 44.12. Tres pares de colores que nadie medía, en la misma pantalla

El capítulo 43 extrajo del código los pares de colores que `PARES` no declaraba, y lo hizo recorriendo **cada objeto `style` por separado**: un par existe cuando un mismo objeto escribe el color y el fondo. La caja del decaimiento del simulador está escrita así:

```jsx
<div style={{ background: 'var(--bg-subtle)', … }}>
  <div style={{ …, color: formData.days_since_last_activity > 14 ? 'var(--warm-text)' : 'var(--text-primary)' }}>
```

El relleno lo pone el objeto de fuera y el color el de dentro. Un extractor que mira cada objeto por separado no ve ningún par: ve un fondo sin texto y un texto sin fondo. Juntarlos exige el árbol del marcado, no el archivo, y eso es otro capítulo.

Son tres pares —`--warm-text`, `--text-primary` y `--text-muted` sobre `--bg-subtle` encima del panel— y pasan los tres; el peor es el de la nota de la vida media, **4.64 contra los 4.5 de §1.4.3**, que pasa por 0,14. Entran en `PARES` declarados a mano, con el motivo escrito, para que sigan midiéndose: `--text-muted` es el token que en el capítulo 43 falló **dos veces** encima de este mismo relleno.

Lo que importa de este apartado no son los números, que están bien. Es que la pantalla que ningún motor miraba era también la pantalla cuyos colores nadie había declarado. Las dos listas escritas a mano de este directorio se habían dejado fuera lo mismo.

---

## 44.13. Lo que las otras dos suites no cubren, dicho con número

La accesibilidad del cliente la miran tres archivos, y los tres toman su lista de pantallas a mano. Después de este capítulo:

| Suite | Qué comprueba | Pantallas de las 18 |
| :--- | :--- | :---: |
| `accesibilidad.test.jsx` | WCAG 2.1 AA con `axe-core` sobre el marcado montado | **18** |
| `teclado.test.jsx` | el recorrido real del foco con el tabulador | 2 |
| `anuncios.test.jsx` | que lo que falla llega a un lector de pantalla | 5 |

Las dos últimas no se tocan en este capítulo, y la razón es de alcance: el recorrido con teclado no se puede derivar del código como la lista de `axe`, porque cada pantalla tiene su propio orden esperado y hay que escribirlo. Lo que no se hace se escribe como punto nuevo de §6.4 **con su cuenta**, que es la diferencia entre una deuda anotada y una frase vaga.

---

## 44.14. Control 58 del CI, y veinticuatro defectos reintroducidos

El control 58 de `configuracion-peligrosa` vigila las dos mitades de este capítulo: que la lista siga derivándose del código y que no se arregle apagando lo que mira. Seis comprobaciones:

1. **El inventario.** Cada componente con un control de formulario se monta en la auditoría, con el mismo recorrido que la guarda del cliente, repetido aquí para que el CI no dependa de que esa guarda siga existiendo. Si el barrido encuentra menos de doce pantallas u ochenta controles, el control falla por sí mismo.
2. **El nivel** sigue siendo AA de WCAG 2.1, con las tres reglas de `best-practice` que se piden por su nombre.
3. **Las reglas apagadas** siguen siendo una, `color-contrast`, que necesita píxeles y se mide sobre la paleta; y ninguna prueba se apaga una regla para sí misma.
4. **Las tres pantallas enteras** traen su `<main>`.
5. **Los controles que este capítulo nombró** siguen con su nombre: los tres deslizadores con su `htmlFor` y su `id`, el selector del rol con el nombre de la persona dentro, el QR con su `role="img"` y las tres cajas de contraseña con su etiqueta.
6. **La guarda del cliente sigue derivando** su lista en vez de escribirla.

El arnés reintroduce **veinticuatro defectos** y los veinticuatro se detectan. Cuatro resultados valen escritos:

* **«Apagar la regla que estorba» solo lo detecta el control 58.** Quitar `region` de las reglas pedidas, añadir una regla a la lista de apagadas o bajar el nivel a WCAG 2.0 deja la suite **verde**: una suite no puede detectar que ha dejado de mirar. Eso es lo que hace falta un control aparte.
* **Lo contrario también.** Quitar `role="img"` del QR o el `<main>` de una pantalla entera lo detectan las dos cosas, pero el que dice **qué** está mal es `axe`: el control 58 dice que falta una etiqueta, y la auditoría dice qué regla de la norma se incumple y en qué nodo.
* **Dejar el `import` y cambiar la llamada** —`cajasDeFormulario` sigue escrito en el archivo, pero la guarda recorta con `match(/<input/g)`— no lo veía el control hasta que el arnés lo demostró. Ahora busca la llamada y no el nombre, que es la memoria del capítulo 38 convertida en una línea: comprobar que un símbolo aparece no comprueba que se use.
* **Y el arnés encontró tres veces el mismo error en el control que yo acababa de escribir**, las tres de la misma familia: la comprobación buscaba su respuesta en un texto que no era código. `wcag21a` aparece en el comentario que explica qué es WCAG 2.1; `<main` aparece en el comentario que explica por qué la pantalla tiene que llevarlo; y `Rol de ${usuario.full_name}` aparece también en el aviso de que el rol se cambió, que no tiene nada que ver con el selector. Las tres pasaban con el defecto puesto. Ninguna la vio una lectura.

---

## 44.15. Lo que apareció y no se hizo

Dos cosas, las dos con su punto de §6.4 y su motivo.

**El recorrido con teclado y los anuncios cubren 2 y 5 de las 18 pantallas** (§44.13). Entra como punto **47**. No se deriva del código porque cada pantalla tiene su propio orden de foco esperado, y escribir trece recorridos es más trabajo que este capítulo entero.

**Cuarenta y ocho etiquetas escriben su estilo a mano**, en diez componentes, mientras `.form-label` existe en la hoja y ocho la usan. Entra como punto **48**. Es la misma forma que el punto 37 que cerró el capítulo 43 —la hoja lo tiene y el marcado lo reescribe—, una planta más abajo, y no es un incumplimiento: ninguna de esas etiquetas forma un par de colores sin medir, porque ninguna escribe su propio fondo. Lo que hay es un tamaño y un color de etiqueta que dependen del archivo, con `--text-muted` en unas y `--text-secondary` en otras, y unificarlo toca nueve componentes sin corregir ningún número.

Y por escrito, lo que este capítulo **no** abrió: ninguna línea del servidor, ninguna pantalla nueva, ningún endpoint, ninguna columna, ninguna migración, ningún color nuevo en la paleta, y nada de §3, §4, §5, §6.1 ni §6.2.

---

## 44.16. Estado al cierre

| | |
| :--- | :--- |
| Pruebas del servidor | **1677 pasan**, 2 omitidas |
| Pruebas del cliente | **710 pasan** en 42 archivos (desde 691 en 41) |
| Cobertura del cliente | 96,65 % sentencias · 91,73 % ramas · 98,64 % funciones · 98,70 % líneas (suelos: 96 / 90 / 98 / 98) |
| Pantallas auditadas | **18 de 18** con controles de formulario, 105 controles |
| Infracciones corregidas | 2 críticas (`label`, `select-name`), 1 seria (`aria-prohibited-attr`), 1 moderada (`region`) en dos pantallas |
| `ruff` / `eslint` / `npm run build` | sin avisos |
| Controles del CI | **58** en `configuracion-peligrosa` |
| Arnés de reintroducción | **24 de 24** detectados |
| §6.4 | se cierra el **44**; entran el **47** y el **48** |
| §6.3 | el punto **18** actualizado: la mitad verificable ya no son ocho pantallas sino todas |

El punto 18 de §6.3 —«el panel no se ha recorrido con una persona dentro»— sigue abierto, y es importante que siga. Lo que este capítulo cambia es su mitad medible: decía que el capítulo 40 había cerrado «el último hueco medible», y quedaba este. Lo que sigue sin responder es si lo que se ve y lo que ese lector dice **se entienden**, y eso no lo contesta ninguna herramienta.
