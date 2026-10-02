# Reporte 41 — Los avisos que no estaban en la página: el cuadro que pedía una contraseña en claro, el par que nadie medía y los motivos que el cliente tiraba

**Capítulo 43** · Interfaz, accesibilidad y mensajes de error · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 2 de octubre de 2026
**Alcance:** los cuadros del navegador que quedaban en el cliente —seis `alert()`, un `confirm` que decidía un borrado y un `prompt` que pedía la contraseña de otra cuenta en claro— (§6.4 punto 38); los diecinueve avisos que escribían su caja a mano y los once campos de formulario que no eran `.input-field`, con los dos pares de colores que por eso nadie medía y que no llegaban a los 4.5 de §1.4.3 (§6.4 punto 37); el nombre de la columna que seguía saliendo delante del mensaje, escrito en un solo sitio; los motivos de la política de contraseñas que el servidor manda enteros y el cliente tiraba desde el primer día; el ámbar que hacía dos oficios (§6.4 punto 39); el velo que tapaba la página sin decir que estaba trabajando; y un control de regresión con veintinueve defectos reintroducidos.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 41 es el capítulo 43. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 43.1. Tres restos menores, y los tres mal medidos

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para tres puntos de §6.4 y para ninguno más**: el **37**, el **38** y el **39**, que son los tres que quedaban del lado del cliente y que el capítulo 40 dejó anotados al cerrar los suyos.

Lo que decían:

> **37.** *«Las otras siete formas del panel siguen enseñando el nombre de la columna, y diez avisos escriben su geometría en línea. […] en las demás, un 422 sigue saliendo por `parseApiError` como `nueva: La contraseña está en la lista de filtradas`, con el nombre del campo del esquema delante […] **No incumple ningún mínimo**: es el mismo arreglo en los sitios donde el 422 es menos probable, y hacerlo toca diez componentes más sin corregir ningún número.»*

> **38.** *«Siete errores del panel se avisan con un `alert()` del navegador: seis en el recálculo masivo de `App.jsx` y uno en el recálculo de una ficha.»*

> **39.** *«`--warm-*` hace dos oficios, y dos usos de `--hot-text` también. […] Es el mismo trabajo que el rojo y no se hace a medias.»*

Al medirlos, los tres estaban mal contados, y uno de ellos en la frase que decidía que podía esperar:

| Lo que el punto decía | Lo que había |
| :--- | :--- |
| **38:** siete errores, seis en el recálculo masivo y uno en el recálculo de una ficha | Seis `alert()` y **todos en `App.jsx`**: el de la ficha lo había movido el capítulo 40 sin que nadie actualizara el punto. Uno está en `handleSelectLead` y no es ningún recálculo |
| **38:** «siete **errores**» | Dos de los seis no eran errores: uno anunciaba un éxito —«✅ 312 prospectos recalculados»— y otro decía que el trabajo seguía en curso. `alert()` no era solo cómo el panel avisaba de un fallo: era la única forma que tenía de decir cualquier cosa fuera de un formulario |
| **38:** los `alert()` | El punto no mencionaba los otros dos cuadros del navegador, y uno de ellos era **el peor de los tres**: un `window.prompt` pedía la contraseña de otra cuenta, y un `prompt` **escribe en claro** (§43.3) |
| **37:** diez avisos escriben su geometría en línea | Los diez que llevan `className="alert"` tienen **una** propiedad en su `style`, un margen; las siete las escribió el capítulo 40 en la hoja. Los que escribían la caja a mano eran otros diecinueve, los que nunca recibieron la clase (§43.5) |
| **37:** «no incumple ningún mínimo» | Sí lo incumplía, y en dos sitios: un par de colores escrito en un `style` es un par que la suite de contraste **no puede ver**, y de las siete combinaciones que aparecieron al derivarlas del código, dos estaban por debajo de los 4.5 de §1.4.3 (§43.6) |
| **37:** `nueva: La contraseña está en la lista de filtradas` | Ese renglón no existe. El campo no se llama `nueva` sino `nueva_contrasena`, y ese rechazo **no llega como un renglón por campo**: llega como un detalle estructurado cuyos motivos el cliente tiraba (§43.9) |
| **37:** «hacerlo toca diez componentes más» | El nombre de la columna lo escribía **una función, en un sitio**: `parseApiError` (§43.8) |
| **39:** `--warm-*` hace dos oficios y dos usos de `--hot-text` también | Cierto, y además de `.alert-warn` había cuatro advertencias más con la familia de la temperatura (§43.11) |

### Lo que este capítulo decidió NO abrir

Por escrito: **ninguna línea del servidor** —los mensajes ya vienen en castellano desde el 40 y con el campo desde el 42—, ninguna pantalla nueva, ningún endpoint, ninguna columna, ninguna migración, ningún color nuevo en la paleta y nada de §3, §4, §5, §6.1, §6.2 ni §6.3. Lo que apareció y no se hizo está en §43.12, con su motivo y su punto de §6.4.

---

## 43.2. Seis cuadros del navegador, y dos daban buenas noticias

Un `alert()` no forma parte de la página. Esa frase suena a detalle y tiene cuatro consecuencias, las cuatro medibles:

1. **Ningún lector de pantalla lo anuncia como contenido.** Es un diálogo del navegador: interrumpe, se lee con otra voz y no está en el documento.
2. **No se puede señalar junto a nada.** Un error de un campo no puede salir al lado del campo si sale en una ventana que flota sobre la página.
3. **Tapa lo que hay que corregir** y hay que cerrarlo para volver a verlo.
4. **No deja rastro.** Al pulsar «Aceptar» no queda nada de lo que decía: ni para releerlo, ni para copiarlo, ni para una prueba.

La cuarta es la que explica por qué este defecto llevaba desde el primer día: **lo que no está en la página no lo ve ni una persona con lector de pantalla ni una prueba**. `App.test.jsx` no probaba el recálculo masivo —no había nada que consultar—, y en `jsdom` `window.alert` existe y lanza «not implemented», que `userEvent` se traga sin que nadie lo note.

Los seis, con lo que cada uno decía:

| Dónde | Qué decía | Qué es |
| :--- | :--- | :---: |
| `handleSelectLead` | «Error al cargar detalle del lead: …» | error |
| recálculo, `FAILED` | «El recálculo no pudo completarse: …» | error |
| recálculo, `COMPLETED` | «✅ 312 prospectos recalculados» | **éxito** |
| recálculo, sondeo agotado | «El recálculo sigue en curso; puede tardar unos minutos más…» | **aviso** |
| recálculo, 409 | «Ya hay un recálculo masivo en curso. Va por 40 de 120. Lo lanzó ana@…» | aviso |
| recálculo, fallo genérico | «Error en recálculo masivo: …» | error |

Los seis pasan al mecanismo que el capítulo 40 dejó montado: `.alert` con su variante, dentro de una región viva. Y **dos regiones y no una**, con el mismo reparto que la pantalla de derechos del titular: `role="alert"` para lo que falló y `role="status"` para lo que no. Un error anunciado como estado espera a que el lector de pantalla termine lo que esté diciendo; un éxito anunciado como alerta interrumpe para dar una buena noticia.

Son dos regiones permanentes y vacías, no una con el `role` cambiante, y el motivo es el mismo que el capítulo 38 escribió para los derechos del titular: un lector de pantalla registra la región cuando entra en el documento, así que cambiarle el papel la convierte en otra región y lo que aparezca dentro de una región recién nacida no se anuncia.

El aviso lleva un botón **Cerrar** y no un temporizador. Un error que se va a los cuatro segundos se va justo mientras se lee; uno que no se puede quitar se queda para siempre. Lo cierra quien lo ha leído.

Y están en `<main>`, encima de la pestaña que sea: el botón del recálculo vive en administración, pero el resultado llega minutos después y quien lo lanzó puede estar mirando cualquier otra cosa.

---

## 43.3. El séptimo cuadro, que no estaba en ninguna lista, pedía una contraseña en claro

`window.prompt`, en el panel de administración, para fijar la contraseña de otra persona:

```js
const nueva = window.prompt(
  `Contraseña nueva para ${usuario.full_name}.\n\n` +
    'Mínimo 12 caracteres. Una frase larga y fácil de recordar es mejor que una ' +
    'palabra corta con símbolos.\n\n' +
    'Se cerrarán todas sus sesiones y tendrá que cambiarla al entrar.',
);
```

Las cuatro consecuencias de §43.2 valen aquí también, y hay una quinta que es de otra clase: **un `prompt` no tiene campo de contraseña**. Lo que se teclea se ve. Fijar la credencial de una cuenta ajena obligaba a escribirla a la vista de cualquiera que pasara por detrás, en la pantalla de un administrador que casi siempre está acompañado por la persona a la que se le está restableciendo.

Y faltaban tres cosas más que no son estéticas:

* **No hay repetición.** El servidor no puede comprobarla —solo le llega una contraseña—, así que una errata de teclado se descubría cuando la otra persona no podía entrar.
* **Los requisitos no están delante mientras se escribe**, sino en el texto del cuadro, que desaparece al empezar a teclear en algunos navegadores y que no se puede releer sin cancelar.
* **El 422 de la política no tiene dónde salir.** Ese rechazo llega con **todos** los motivos por los que la contraseña no vale, y cuando llega el cuadro ya se cerró con la contraseña dentro: el aviso aparecía arriba, sin la contraseña y sin el campo.

Ahora es un formulario de la página, debajo de la fila de la cuenta de la que habla: dos campos de tipo `password` con `.input-field`, los requisitos a la vista, el foco en el primero al abrirse —lo único que el cuadro del navegador hacía bien— y el 422 de la política repartido debajo del campo, con sus motivos en el aviso de arriba. Si sale mal, el formulario se queda abierto y con lo escrito: cerrarlo obligaría a teclear otra vez doce caracteres por un motivo que ya está en pantalla.

El `confirm` era el tercero, y decidía el borrado de un aviso sin asociar: «se borra y no queda nada de él salvo el registro en la bitácora». La única operación de esa pantalla que no se puede deshacer, decidida en una ventana que no está en la página. Ahora la pregunta está dentro, pegada al aviso del que habla, en ámbar —todavía no ha pasado nada—, con el foco en el botón que confirma y sin tocar lo que el botón hace.

---

## 43.4. El velo que tapaba la página entera y no decía nada

El recálculo masivo recorre la cartera completa y puede durar minutos. Mientras corre, `App.jsx` tapa la página con un velo fijo —`position: fixed`, `inset: 0`, `z-index: 9999`— que escribe el avance: «Recalculando 37/200 prospectos (18%)…».

Ese bloque no llevaba `role`, ni `aria-live`, ni `aria-busy`. Para quien no ve la pantalla, la aplicación se quedaba **cubierta y muda**: sin forma de saber si estaba trabajando, si había terminado o si se había colgado. Y el barrido de `axe` del capítulo 36, que recorre las nueve pantallas, no lo encontró por un motivo que conviene anotar: **el velo es condicional y ninguna prueba lo montaba encendido**. Una herramienta que mide lo que está en el documento no mide lo que solo aparece durante una operación larga.

Lleva ya `role="status"`, `aria-live="polite"` y `aria-busy="true"`. `polite` y no `assertive` porque el avance cambia cada vez que el sondeo contesta —cada segundo y medio— y un anuncio que interrumpe a esa cadencia no deja oír nada más.

---

## 43.5. Diecinueve avisos escribían su caja a mano, no diez

El capítulo 40 escribió `.alert` y sus tres variantes en la hoja y las usó en los diez sitios que tocó. §6.4 anotó que «diez avisos conservan sus siete propiedades en un `style`», y eso es lo contrario de lo que había: los diez con la clase llevan **un** margen en su `style`, y los que escribían la caja entera son los que nunca la recibieron.

Son diecinueve, en catorce componentes:

| Variante | Dónde |
| :--- | :--- |
| error (11) | `AsignarAsesor` —un `<span>` con un color y **sin caja**—, `BandejaDeHoy`, `BandejaSinAsociar`, `Campana`, `CerrarProspecto`, `DerechosDelTitular`, `InformeDePublicacion`, `PanelDeDesenlaces`, `SessionModal`, `ScoringSimulator`, `Publicaciones` (la dirección pública que no responde) |
| error (1) | el registro de actividad de la ficha 360 |
| éxito (5) | `BandejaSinAsociar`, `DerechosDelTitular`, `Publicaciones` y dos de la ficha 360 |
| aviso (2) | el cartel de las cuentas de baja y el enlace caducado de una publicación |

Cada una con su relleno, su radio, su borde y su tamaño de letra, todos parecidos y ninguno igual: `0.8rem`, `0.78rem`, `0.82rem`, `0.825rem`, `0.75rem`. Y una de ellas, la de `SessionModal`, **sin `role`**: era el único aviso del panel que no lo llevaba, así que al fallar el cambio de contraseña la pantalla no decía nada a quien no la ve.

Ahora las dibuja la hoja: treinta y un avisos en dieciocho componentes usan `.alert` con su variante. Lo que queda en un `style` es lo que de verdad varía de un sitio a otro —un margen, una disposición en fila— y nunca un color.

---

## 43.6. Lo importante no es el arreglo: un par de colores en un `style` es un par que nadie mide

Aquí está el motivo por el que este capítulo no era cosmético, y la frase de §6.4 que lo retrasaba —«no incumple ningún mínimo»— es justo la que no era verdad.

`pruebas/contraste.js` dice en su cabecera por qué su lista de pares se declara a mano:

> *«Los pares se declaran abajo, uno por uno y con el sitio donde ocurren. No hay forma honrada de deducirlos: la mayoría de los colores de texto se aplican con `style` en el JSX, sobre un fondo que pone un componente de más arriba. Deducirlos exigiría maquetar, que es justo lo que aquí no se puede hacer.»*

Es cierto, y tiene una excepción que vale mucho: **cuando el mismo `style` escribe el color y su fondo, el par está completo ahí mismo** y se puede leer sin maquetar nada. El cliente formaba trece pares así, en seis combinaciones distintas. Cinco de esas seis **no estaban en la tabla**:

| Par | Dónde | Razón en el peor fondo real |
| :--- | :--- | :---: |
| `--text-muted` sobre `--bg-chip` | los cinco datos sueltos de la ficha 360 | **4.47** sobre el panel, **4.18** sobre el elevado |
| `--text-muted` sobre `--bg-subtle` | las dos insignias «De baja» del panel de administración | **4.64** en reposo y **4.36** con el ratón sobre la fila |
| `--text-primary` sobre `--bg-chip` | dos de los mismos chips | 13.74 |
| `--text-secondary` sobre `--bg-chip` | otros dos | 6.20 |
| `--error-text` sobre `--hot-bg` | el aviso del simulador de scoring | **4.74** sobre el panel elevado |

Las dos primeras **incumplen §1.4.3**, que pide 4.5 para texto normal. Y la segunda enseña algo que ninguna medida estática habría encontrado: `.data-table tr:hover td` añade `--bg-subtle` debajo del relleno de la insignia, que es otro `--bg-subtle`, así que el mismo texto pasa de 4.64 a **4.36** cuando el puntero entra en la fila. El fallo aparece al pasar el ratón.

La causa es siempre la misma y es de aritmética: `--bg-chip` es blanco al 4 % y `--bg-subtle` al 2.5 %. Los dos **aclaran** el fondo, y un texto claro sobre un fondo más claro tiene menos contraste. `--text-muted` es, por decisión del capítulo 39, **la primera parada de su rampa que pasa 4.5 sobre las tres superficies desnudas**: cualquier relleno translúcido por debajo lo tumba. Dentro de un aviso pasa lo mismo y peor —3.78 sobre el rojo translúcido—, que es lo que le ocurría a la segunda línea del aviso del simulador y a la dirección pública que no responde.

El quinto par es de otra clase: el aviso del simulador pintaba un **error** con el fondo y el borde de HOT —la temperatura de un prospecto— y el rojo de `--error-text` encima. Es exactamente la mezcla que el capítulo 40 separó, sobreviviendo en el único sitio donde no se mira. Pasa, por 0,24, y nadie lo sabía.

### El arreglo es estructural, y la guarda también

Los chips de la ficha 360 eran la misma cosa cinco veces, escrita cinco veces, con **tres colores de texto distintos** para el mismo objeto. Son ahora `.chip`, con `--text-secondary` —el token de un dato de apoyo, y el que ya usaban dos de los cinco—: 5.61 en la peor de las cuatro superficies.

Las dos insignias del panel de administración tenían algo más cómico: la de baja reescribía a mano, con un color que falla, una clase que **la hoja ya tenía escrita** —`.badge-status`, con `--text-secondary`, que pasa—. La activa no tenía clase ninguna y ahora es `.badge-ok`.

Y la guarda nueva, en `frontend/src/pruebas/avisos.test.js`, hace las dos mitades:

* **Deriva del marcado** cada par que un mismo objeto de estilo forma y exige que esté en `PARES`. No vale buscar `style={{ … }}`: las dos insignias escribían `style={cond ? {…} : {…}}`, y la primera versión de esta guarda no las veía. Se recorre cada objeto literal por separado, para no inventar pares cruzados entre las dos ramas de un ternario.
* **Deriva de la hoja** cada par que una regla declara con `background` y `color` juntos, y exige lo mismo. Sin esta mitad, mover el color de `.chip` a `--text-muted` volvería a dejar 4.18 sobre el panel elevado sin que nada lo dijera: el par habría cambiado de sitio, no de medida. Al derivarla aparecieron **dos combinaciones más** que nadie medía —lo que se escribe dentro de un campo, `--text-primary` y `--text-secondary` sobre `--bg-field`—, de las veintidós que la hoja declara. Las dos van sobradas (18.55 y 7.57); lo que importa es que ya se miden.

Siete combinaciones sin medir en total, cinco del marcado y dos de la hoja. Dos por debajo del mínimo.

---

## 43.7. Once campos de formulario que no eran campos

Al pasar los avisos a la hoja apareció la misma historia una planta más abajo. De las ochenta y ocho cajas de formulario del cliente, **once no llevaban `.input-field`**: ocho en el panel de administración y tres en el de la sesión, con la caja escrita a mano en un objeto llamado `campo`.

Lo que se perdía en esas once:

* **El contorno medido del capítulo 39.** El borde era `--border-subtle`, que da **1.12:1** contra lo que lo rodea: exactamente el número que §6.4 punto 32 denunció y que ese capítulo cerró creando `--border-control` (3.02:1) **para los controles**. Estas once se quedaron fuera del arreglo sin que nada lo dijera, porque la guarda de contraste mide tokens de la paleta y estos campos no pedían ningún token nuevo: pedían el viejo.
* **El aro de foco** de `.input-field:focus`, con el 3.0 que el mismo capítulo midió.
* **El borde rojo del capítulo 40**, que la hoja pinta sobre `.input-field[aria-invalid='true']`.

La tercera es la que más duele, y hay que decirla entera: **el panel de administración es una de las cuatro pantallas que el capítulo 40 arregló**. Reparte el 422 del alta de una cuenta por campos y pone `aria-invalid` en el que falla —hay una prueba que lo comprueba— y la hoja pinta el borde rojo sobre `[aria-invalid='true']` de `.input-field`. Sin la clase, ese atributo **se anunciaba y no se veía**: el lector de pantalla decía «campo no válido» y en la pantalla no cambiaba nada. Son las dos verdades sobre el mismo campo que el comentario de ese capítulo decía estar evitando:

> *«Se dibuja sobre `[aria-invalid='true']` y no sobre una clase propia, y es la decisión que más importa de esta regla: así la hoja pinta **exactamente** lo que el lector de pantalla anuncia. Con una clase habría dos verdades sobre el mismo campo —una para el ojo y otra para quien no mira— y nada que impida que se separen.»*

Las había, en la pantalla donde ese mismo capítulo puso el atributo.

Las once llevan ya la clase. De las noventa cajas que hay ahora —las dos nuevas son las del restablecimiento—, **ochenta y nueve** la llevan, y la que falta la viste la hoja por su contenedor: el selector del código QR, que `.interes-qr select` dibuja desde el capítulo 39. Está inventariada a mano en la guarda, porque la diferencia entre «se le olvidó» y «la hoja ya la dibuja» es esa línea.

---

## 43.8. El nombre de la columna lo escribía una función, no siete pantallas

§6.4 punto 37 contaba las pantallas: «las otras siete formas del panel siguen enseñando el nombre de la columna […] hacerlo toca diez componentes más». Al buscarlo, el nombre de la columna no lo escribía ninguna de las siete. Lo escribía `parseApiError`, en `services/api.js`, una vez:

```js
const field = item.loc ? item.loc.filter((x) => x !== 'body').join('.') : '';
const mensaje = String(item.msg || '').replace(RUIDO_DE_PYDANTIC, '');
return field ? `${field}: ${mensaje}` : mensaje;
```

Las cuatro pantallas del capítulo 40 no lo veían porque reparten el 422 **antes** de llegar aquí; las demás volcaban lo que esta función devolviera. Así que el arreglo no toca diez componentes: toca cinco líneas en uno.

Y lo que se hace con el campo es **quitarlo, no traducirlo**. Una tabla de nombre de columna a etiqueta en `api.js` sería una segunda verdad sobre cómo se llama cada campo, y la primera es la etiqueta que cada pantalla tiene escrita al lado de su `input`: `first_name` es «Nombre(s)» en la ficha y «Nombre» en el alta, `email` es «Correo corporativo» en una y «Correo electrónico» en la otra. Esa es la razón por la que las cuatro tablas de etiquetas del capítulo 40 son de cada pantalla y no una global. Donde hace falta decir cuál es el campo, se reparte por campos; donde no, el mensaje se explica solo.

Dos detalles del arreglo:

* **Los renglones repetidos se colapsan.** «Falta este campo.» tres veces no dice qué tres campos faltan: dice tres veces lo mismo.
* **El ejemplo del propio punto 37 no existe.** Decía `nueva: La contraseña está en la lista de filtradas`, y el campo no se llama `nueva` sino `nueva_contrasena`. Pero sobre todo: ese rechazo **no llega como un renglón por campo**. Llega como un detalle estructurado, y lo que le pasaba es peor.

---

## 43.9. Los motivos que el servidor manda enteros, y que el cliente tiraba desde el primer día

La política de contraseñas devuelve **todos** los motivos por los que una contraseña no vale, y lo hace a propósito. Su propio código lo explica:

```python
class ContrasenaDebil(ValueError):
    """
    La contraseña no cumple la política. Lleva **todos** los motivos, no el primero.

    Devolver uno solo obliga a descubrir la política a base de intentos, y cada intento
    fallido es una ocasión más para que quien la elige acabe poniendo lo primero que pase.
    """
```

Los dos endpoints que la aplican —el cambio de la propia contraseña y el restablecimiento de otra— contestan un 422 con `{"mensaje": …, "motivos": [...]}`. Y `parseApiError` hacía esto:

```js
if (typeof err.detail.mensaje === 'string') return err.detail.mensaje;
```

El titular, y la lista a la basura. En pantalla salía «La contraseña no cumple la política del sistema.» y nada que se pudiera corregir. Desde el primer commit del repositorio.

Lo que hace que esto sea una lección y no una errata es **por qué nadie lo vio**. Los dos formularios tenían su prueba, y las dos decían comprobarlo:

```js
// SessionModal.jsx
} catch (err) {
  // El backend devuelve la lista completa de motivos cuando la política la rechaza;
  // enseñarlos todos evita que la persona tenga que descubrirla a base de intentos.
  setError(err.message || 'No se pudo cambiar la contraseña.');
}
```

```js
// SessionModal.test.jsx
changeOwnPassword.mockRejectedValue(
  new Error(
    'La contraseña no cumple la política:\n- Debe tener al menos 12 caracteres\n- No puede ser una contraseña conocida',
  ),
);
// …
expect(await screen.findByText(/al menos 12 caracteres/)).toBeInTheDocument();
```

La prueba **fabricaba la respuesta del servidor con los motivos ya dentro del mensaje**, una capa por debajo de donde estaba el fallo. Y pasaba, claro: enseñaba lo que la propia prueba le había dado. El tramo que nadie probaba era el de en medio —de `detail` a `message`—, y ahí estaba el defecto. Un comentario del componente afirmaba desde el capítulo 23 que los motivos se enseñaban todos; no llegaba ninguno.

Las tres capas tienen hoy su prueba, y cada una mide la suya:

* **La forma de la respuesta**, en `backend/tests/test_politica_de_contrasenas.py`: que el 401 traiga un detalle de texto, que el 422 de la política traiga `mensaje` y `motivos` con esos nombres y sin `loc`, y que el restablecimiento de otra cuenta tenga la misma forma.
* **La lectura**, en `frontend/src/services/api.test.js`: que los motivos salgan detrás del mensaje, un renglón cada uno.
* **El reparto**, en los dos formularios: que cada motivo se vea y que el campo quede señalado.

---

## 43.10. El campo del que habla una puerta que no dice ningún campo

Al medir qué pantallas podían repartir su 422 por campos apareció que §6.4 punto 37 daba por hecho algo que no se cumple: que esas siete pantallas reciben rechazos **con el campo dentro**. La lista de entradas de la API se saca del propio enrutador —hay veinte esquemas de cuerpo— y lo que esas puertas contestan cuando rechazan es, casi siempre, otra cosa:

| Qué contesta | Lleva el campo | Ejemplos |
| :--- | :---: | :--- |
| Un 422 de Pydantic con `loc` por campo | sí | el alta y la edición de una ficha, el alta de una cuenta, la publicación, la página pública —las cinco que ya lo reparten— |
| Un 422 de un `model_validator(mode="after")` | **no**: `loc` es `['body']` | el cierre de un prospecto, el registro de una actividad |
| Un detalle estructurado `{mensaje, motivos}` | **no** | la política de contraseñas, en sus dos puertas |
| Un detalle de texto | **no** | «La contraseña actual no es correcta», «no puede ser igual a la actual» |

Es decir: en las pantallas que quedaban, **no había un campo que leer**. Por eso el arreglo general es el de §43.8 —quitar el nombre de la columna, que no sirve para nada— y el reparto por campos solo entra donde se puede saber de qué campo habla el servidor sin adivinarlo.

Los dos formularios de contraseña son ese caso, y son el ejemplo que el propio punto 37 ponía. El campo no se lee: **se sabe**, porque es el contrato de esa puerta, y está escrito una vez para los dos formularios que la llaman:

```js
export function erroresDeLaContrasena(err) {
  if (!err || !err.status) return null;
  const renglones = String(err.message || '').split('\n').filter(Boolean);
  if (!renglones.length) return null;
  if (err.status === 401) {
    return { porCampo: { contrasena_actual: renglones[0] }, sueltos: renglones.slice(1) };
  }
  if (err.status === 422) {
    return { porCampo: { nueva_contrasena: renglones[0] }, sueltos: renglones.slice(1) };
  }
  return null;
}
```

Por el código y no por el texto del mensaje, que es lo que caducaría al reescribir una frase. El primer renglón va debajo del campo y los demás al aviso de arriba, que es el reparto que el capítulo 40 dejó montado: lo que es de un campo cabe al lado del campo, y una lista no cabe ahí. Lo que se ve al rechazar una contraseña es:

> **Revise el campo Contraseña nueva.**
> Debe tener al menos 12 caracteres.
> Está en la lista de contraseñas filtradas: elija otra.

con el campo marcado, el borde rojo puesto y el foco dentro. Lo que no es ni 401 ni 422 —un 500, un fallo de red— no se reparte: no se sabe de qué campo habla, y señalar uno sería inventarlo.

Esta dependencia entre capas tiene su guarda del lado del servidor, que es donde puede romperse sin que el cliente se entere: si alguien cambiara un código de estado o moviera los motivos a otra clave, la pantalla señalaría el campo equivocado y nada del lado de Python se pondría rojo. Ahora sí.

---

## 43.11. El ámbar que hacía dos oficios, y solo uno tenía nombre

Es el tercer corte de la misma serie. El capítulo 39 separó `--danger-*` de `--hot-*` porque el rojo de HOT es una **temperatura de prospecto** y pintar «Cerrar sesión» con él diría que ese botón es un prospecto caliente. El 40 separó `--error-*` por el mismo argumento. Y dejó el ámbar sin partir, con la razón escrita en la hoja:

> *«Se reutiliza porque el ámbar de esta paleta es ese y no hay otro, y queda anotado en §6.4: el token hace dos oficios y solo uno tiene nombre.»*

`--warm-*` era a la vez la temperatura WARM de una ficha —el score en la matriz, el KPI, la muestra de la leyenda, el degradado de la barra del tablero— y una advertencia: `.alert-warn`, el cartel de las cuentas de baja, la columna de las contraseñas prestadas, el aviso de los códigos de recuperación agotados y el del enlace caducado de una publicación. Y `--hot-text` advertía en dos sitios más, uno de ellos la confirmación de una supresión.

Hay ahora una familia `--warn-*` con **los mismos valores**, y eso no es un rediseño: sigue sin haber otro ámbar en esta paleta. Lo que se separa no es el color, es la decisión de moverlo. Con un solo token, el día que la temperatura WARM necesite otro ámbar habría que elegir entre tocar el gráfico del tablero o dejar el aviso mal, y esa elección no debería existir. Un token es un sitio donde se decide; dos oficios en un token son dos decisiones atadas que nadie ató a propósito.

Medido: el texto va de 10.76 a 8.43 sobre `--warn-bg` según la superficie que haya debajo, y de 11.85 a 9.64 sobre el fondo desnudo. El problema de este color nunca fue el contraste, era el nombre.

Un detalle que la guarda vigila: `.alert-warn` estaba escrita en la hoja desde el capítulo 40 y **no la usaba ningún componente**. El ámbar era la variante del aviso que no tenía dónde salir. Ahora la usan el recálculo que sigue en curso, el turno ocupado, el enlace caducado y la confirmación de un descarte. Una clase que la hoja define y el marcado no pide es una clase que nadie ha visto dibujada.

---

## 43.12. Lo que apareció y no se hizo

Tres cosas, con su punto de §6.4 y su motivo:

**Los tres campos del cambio de contraseña se nombran con un `placeholder`** y no con una etiqueta. Un `placeholder` desaparece al escribir, así que quien vuelve al campo ya no sabe cuál es, y no es lo mismo que una etiqueta para quien navega con lector de pantalla. No es un incumplimiento claro de AA —el marcador da nombre accesible al campo—, y ponerles etiqueta cambia la maquetación de un modal. Entra como punto **44**.

**El simulador de scoring no reparte su 422 por campos.** Es el único formulario de los que quedan donde un rechazo por campo es alcanzable —veintisiete campos en el cuerpo—, y todos sus valores salen de deslizadores y listas, así que un 422 ahí es un fallo de programación y no un dato mal escrito. Con el nombre de la columna fuera, lo que se ve es el mensaje del servidor; repartir veintisiete campos para eso es trabajo sin número que corregir. Entra como punto **45**.

**El cierre de un prospecto y el registro de una actividad validan con `model_validator(mode="after")`**, así que su 422 nunca puede nombrar un campo: `loc` es `['body']`. El docstring del cierre dice lo contrario —«ponerla aquí la convierte en un 422 que señala el campo en lugar de un 400 con una frase»—, y no es cierto para un validador de modelo. Pasarlos a validadores de campo permitiría repartirlos, y cambia lo que la API contesta a un cliente que ya existe. Entra como punto **46**.

Y lo que no se tocó por decisión y no por falta de tiempo: **ni una línea del servidor**. Los mensajes ya venían en castellano desde el capítulo 40 y con el campo desde el 42; lo que faltaba estaba todo de este lado.

---

## 43.13. El control 57 y los veintinueve defectos

El control **57** del CI cierra el trabajo `configuracion-peligrosa`, que pasa a tener **58 pasos y 57 controles**. Comprueba ocho cosas, y todas derivadas del código:

1. Que no haya ni un `alert(`, `confirm(` ni `prompt(` en ningún archivo del cliente, con los comentarios quitados antes de buscar —la lección del capítulo 37: una guarda que busca un texto se satisface con su propia documentación, y las cabeceras de este capítulo nombran los tres—.
2. Que `--warn-*` y `--warm-*` sigan valiendo lo mismo y que `.alert-warn` use la familia del aviso.
3. Que la hoja defina `.alert` y sus tres variantes, `.chip`, `.badge-status`, `.badge-ok` e `.input-field`, y que el marcado las pida todas.
4. Que ningún `style` vuelva a escribir el relleno de un chip o de una insignia junto a un color.
5. Que las noventa cajas de formulario lleven la clase que la hoja mide, con la única excepción inventariada.
6. Que `api.js` no vuelva a escribir el nombre de la columna ni a tirar los motivos, y que el reparto del rechazo de una contraseña siga existiendo.
7. Que el velo siga diciendo que está ocupado y que las dos regiones vivas sigan en `App.jsx`.
8. Que la guarda del cliente siga derivando sus listas del código.

El arnés reintrodujo **veintinueve defectos** —uno por arreglo, y los que más importan por duplicado desde distintos ángulos— y los veintinueve se detectaron. Dos resultados que merecen quedar escritos:

* **El defecto «los motivos vuelven a tirarse» lo detectan el control y `services/api.test.js`, y no las pruebas de los dos formularios.** Es exactamente lo que había pasado: las pruebas de componente construyen el error ya resuelto, así que no pueden ver el tramo que lo resuelve. Que el arnés lo diga confirma que la prueba que faltaba estaba en la capa de abajo, y que ahora está.
* **El defecto «el texto de un chip vuelve al apagado que daba 4.47» lo detecta la mitad nueva de la guarda**, la que deriva los pares de la hoja. Sin ella, mover ese color habría dejado el mismo incumplimiento en otro sitio sin que nada se pusiera rojo, que es la forma más barata de perder un arreglo.

---

## 43.14. Las cuentas

| | Antes | Después |
| :--- | :---: | :---: |
| Pruebas del servidor | 1673 (2 omitidas) | **1677** (2 omitidas) |
| Pruebas del cliente | 637 | **691** |
| Cuadros del navegador en el cliente | 8 | **0** |
| Avisos que dibuja la hoja | 10 | **31** |
| Cajas de formulario con `.input-field` | 77 de 88 | **89 de 90** |
| Pares de colores sin medir | 7 | **0** |
| Controles del CI | 56 | **57** |
| Defectos reintroducidos y detectados | — | **29 / 29** |

Cobertura del cliente: **96.2 / 90.9 / 98.64 / 98.44** sobre suelos de 96 / 90 / 98 / 98. `ruff`, `eslint` y `npm run build` sin avisos.

§6.4 cierra la **37**, la **38** y la **39** —los tres puntos que quedaban del lado del cliente— y abre la **44**, la **45** y la **46**.

---

## 43.15. Lo que este capítulo enseña

**Un cuadro del navegador es invisible para las dos cosas a la vez.** No lo anuncia un lector de pantalla y no lo puede consultar una prueba, y las dos invisibilidades tienen la misma causa: no está en la página. Por eso un `alert()` sobrevive años en un repositorio con 691 pruebas de cliente, y por eso el único que pedía una contraseña la pedía en claro sin que nadie lo hubiera notado.

**Un par de colores escrito en un `style` es un par que nadie mide.** El capítulo 40 lo dijo de pasada —«un color en un `style` del JSX no está en ninguno de los dos»— y arregló los cuatro avisos que tenía delante. Quedaban diecinueve, y en ellos dos incumplimientos de §1.4.3 esperando a que alguien derivara la lista en vez de escribirla. La diferencia entre una guarda que mide **tokens** y una que mide **usos** es, otra vez, la lección del capítulo 40: buscar un uso y no un nombre.

**Una prueba que fabrica la respuesta del servidor no puede ver el tramo que la interpreta.** Los motivos de la política no llegaron a la pantalla desde el primer día, con un comentario afirmando lo contrario y una prueba verde debajo, porque la prueba construía el mensaje con los motivos ya dentro. El fallo estaba entre la respuesta y el mensaje, que es justo el trozo que la prueba sustituía.

**Y un atributo que se anuncia y no se ve son dos verdades sobre el mismo campo.** El capítulo 40 escribió esa frase para justificar pintar sobre `[aria-invalid]` en vez de sobre una clase propia, y en la misma pantalla donde puso el atributo los campos no tenían la clase de la hoja. Lo que decía la frase era verdad; lo que no se comprobó es que las dos mitades se tocaran.
