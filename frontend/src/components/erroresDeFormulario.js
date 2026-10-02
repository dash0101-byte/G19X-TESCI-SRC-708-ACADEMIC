// ============================================================================
// Un 422 llega al campo que lo causó, y en castellano
// ============================================================================
//
// De dónde sale esto
// -------------------
// La página de interés hacía bien las cuatro cosas que hay que hacer con un 422 desde el
// capítulo 34: repartir cada error junto a su campo, marcar el campo con `aria-invalid`,
// atar el mensaje con `aria-describedby` y llevar el foco al primero que falla. Los
// formularios del panel no hacían ninguna: volcaban `err.message` en un aviso arriba.
//
// Y lo que volcaban no era ni castellano. `parseApiError` une los renglones del 422 con
// `campo: mensaje`, así que la pantalla de alta de un prospecto decía, literalmente:
//
//     first_name: Field required
//     email: value is not a valid email address: An email address must have an @-sign.
//
// El nombre de la columna de la base y el idioma de Pydantic, en un producto escrito
// entero en castellano. Y en una sola línea, porque el salto de línea que `parseApiError`
// pone no es un salto en HTML (eso lo arregla `.alert`, en la hoja).
//
// El servidor **ya decía qué campo**: el 422 trae `loc`, y el capítulo 33 se tomó el
// trabajo de que nombrara el campo en vez de contestar un 200 mentiroso. Lo que faltaba no
// era información del servidor: era recogerla.
//
// Por qué un módulo y no cuatro copias
// -------------------------------------
// Porque son cuatro formularios y la parte delicada no es el reparto: es que el `id` del
// mensaje y el `aria-describedby` del campo **digan lo mismo**. Dos cadenas que se
// construyen a mano en dos sitios son dos cadenas que algún día se separan, y el día que
// se separen el lector de pantalla dejará de leer el error sin que nada se ponga rojo. Aquí
// se construyen en la misma función. El renglón que se pinta debajo del campo es lo único
// que no está aquí: vive en `MensajeDeCampo.jsx`, porque un archivo que exporta un
// componente y además funciones rompe la recarga en caliente de Vite, y el `linter` lo
// dice. Las dos mitades comparten `idDelMensaje`, que es la que importa que no se separe.

/**
 * Pydantic antepone «Value error, » a lo que dice un validador propio.
 *
 * Es el nombre interno de su excepción y no significa nada para quien lo lee, pero sirve
 * para algo mejor que quitarlo: **distingue nuestros mensajes de los suyos**. Un
 * `value_error` con este prefijo lo escribió alguien de este repositorio, en castellano y
 * para leerse —«El teléfono no es un número válido: revise la lada…»—. Uno sin prefijo
 * viene de una biblioteca y está en inglés —«value is not a valid email address»—.
 */
const RUIDO_DE_PYDANTIC = /^(Value error|Assertion failed),\s*/;

/**
 * Lo que se dice de cada clase de error, por el `type` que manda Pydantic y no por su
 * texto en inglés.
 *
 * Por el tipo y no por el texto porque el texto es de ellos: cambia entre versiones, y una
 * tabla que compare cadenas en inglés se queda muda en la primera actualización sin que
 * ninguna prueba lo note. El tipo es parte del contrato de la API.
 */
export const POR_TIPO = {
  missing: () => 'Falta este campo.',
  string_too_short: (item) => (item.ctx && item.ctx.min_length
    ? `Tiene que tener al menos ${item.ctx.min_length} caracteres.`
    : 'Es demasiado corto.'),
  string_too_long: (item) => (item.ctx && item.ctx.max_length
    ? `No puede pasar de ${item.ctx.max_length} caracteres.`
    : 'Es demasiado largo.'),
  string_pattern_mismatch: () => 'No tiene la forma que se espera.',
  greater_than_equal: (item) => `Tiene que ser ${item.ctx.ge} o más.`,
  less_than_equal: (item) => `Tiene que ser ${item.ctx.le} o menos.`,
  int_parsing: () => 'Escriba un número entero.',
  float_parsing: () => 'Escriba un número.',
  bool_parsing: () => 'Tiene que ser sí o no.',
  enum: () => 'Elija una de las opciones de la lista.',
  literal_error: () => 'Elija una de las opciones de la lista.',
  date_from_datetime_parsing: () => 'Escriba una fecha válida.',
  datetime_parsing: () => 'Escriba una fecha válida.',
  url_parsing: () => 'Escriba una dirección web completa, con https://.',
  extra_forbidden: () => 'Este dato no se admite aquí.',
};

/** El último tramo de `loc`: `['body', 'email']` → `email`. */
function campoDe(item) {
  if (!Array.isArray(item.loc) || !item.loc.length) return null;
  return String(item.loc[item.loc.length - 1]);
}

/**
 * Qué decir de un renglón del 422.
 *
 * El orden importa y es el que decide si la pantalla habla castellano:
 *
 * 1. Si la pantalla tiene su propia frase para ese campo, esa. Las del formulario están
 *    escritas para quien lo rellena —«Escribe un correo válido, como nombre@empresa.com»—
 *    y ganan a cualquier mensaje genérico.
 * 2. Si el mensaje lo escribió un validador de este repositorio —lleva el prefijo de
 *    Pydantic—, ese, sin el prefijo. Ya explica qué forma se espera y está en castellano.
 * 3. Si no, lo que diga la tabla de arriba para su tipo.
 * 4. Y si el tipo no está en la tabla, una frase genérica. **No** el texto en inglés: un
 *    mensaje que no se entiende no es mejor que uno vago, y así el inglés no se cuela por
 *    el hueco de un tipo que todavía no se ha visto.
 */
export function mensajeDelRenglon(item, propios = {}) {
  const campo = campoDe(item);
  if (campo && propios[campo]) return propios[campo];
  const texto = String(item.msg || '');
  if (RUIDO_DE_PYDANTIC.test(texto)) return texto.replace(RUIDO_DE_PYDANTIC, '');
  const deLaTabla = POR_TIPO[item.type];
  if (deLaTabla) {
    try {
      return deLaTabla(item);
    } catch {
      // Un `ctx` que no trae lo que su tipo promete no puede tumbar el formulario: el
      // objetivo era explicar un error, no provocar otro.
      return 'No se admite este valor.';
    }
  }
  return 'No se admite este valor.';
}

/**
 * El `detail` de un 422 repartido por campo: `{ email: 'Falta este campo.' }`.
 *
 * `campos`, si se pasa, es la lista de los que el formulario pinta: un error de un campo
 * que no está en la pantalla no se puede señalar en la pantalla, y dejarlo en el reparto lo
 * haría desaparecer. Esos se devuelven aparte, en `sueltos`, para que el aviso de arriba
 * los diga. Es la diferencia entre repartir y perder.
 */
export function erroresDelServidor(detalle, { propios = {}, campos = null, renombres = {} } = {}) {
  if (!Array.isArray(detalle)) return null;
  const porCampo = {};
  const sueltos = [];
  for (const item of detalle) {
    // `renombres` traduce el nombre que viaja al que la pantalla usa. No siempre son el
    // mismo: el formulario de publicaciones tiene un campo «fecha de cierre» que el
    // servidor conoce como `end_date`, y sin la traducción el error de esa fecha acabaría
    // en el aviso de arriba —o peor, en ningún sitio— en vez de debajo de su campo.
    const bruto = campoDe(item);
    const campo = bruto && renombres[bruto] ? renombres[bruto] : bruto;
    const mensaje = mensajeDelRenglon(item, propios);
    if (!campo || (campos && !campos.includes(campo))) {
      sueltos.push(mensaje);
      continue;
    }
    // El primero que llega manda: dos quejas del mismo campo caben en un solo renglón
    // debajo de él, y la segunda taparía a la primera.
    if (!porCampo[campo]) porCampo[campo] = mensaje;
  }
  if (!Object.keys(porCampo).length && !sueltos.length) return null;
  return { porCampo, sueltos };
}

/**
 * Las propiedades que conectan un campo con su error.
 *
 * `aria-invalid` es lo que un lector de pantalla anuncia al llegar al campo, y **es también
 * lo que la hoja usa para pintarle el borde rojo** (capítulo 40): el atributo es la única
 * verdad sobre el estado del campo, así que lo que se ve y lo que se oye no se pueden
 * separar. `data-campo` es por donde se le devuelve el foco.
 *
 * `ademasDescritoPor` es el `id` de la ayuda que el campo ya tuviera —«quedan 940
 * caracteres», «al terminar ese día se cierra sola»—. `aria-describedby` admite una lista
 * de `id`, y aquí se juntan en vez de sustituirse: un campo con error no puede perder la
 * explicación de lo que se espera de él justo cuando hace falta. Escribirlo mal es fácil y
 * no se nota, porque el atributo sigue siendo válido con un solo `id`.
 */
export function propiedadesDeCampo(nombre, errores, prefijo, ademasDescritoPor = null) {
  const tiene = Boolean(errores && errores[nombre]);
  const descriptores = [
    ademasDescritoPor,
    tiene ? idDelMensaje(prefijo, nombre) : null,
  ].filter(Boolean);
  return {
    'data-campo': nombre,
    'aria-invalid': tiene ? 'true' : undefined,
    'aria-describedby': descriptores.length ? descriptores.join(' ') : undefined,
  };
}

/** El `id` del mensaje de un campo. Una sola función para los dos lados de la cuerda. */
export function idDelMensaje(prefijo, nombre) {
  return `${prefijo}-${nombre}-error`;
}

/**
 * El foco al primer campo que falla, en el orden en que la pantalla los pinta.
 *
 * En el orden de la pantalla y no en el del 422: el servidor los manda en el orden de los
 * campos del esquema, que no tiene por qué ser el de arriba abajo de la pantalla. Llevar el
 * foco a un campo que está debajo del primero que falla deja a quien navega con teclado
 * mirando hacia el sitio equivocado.
 *
 * `antes` deja que el formulario abra lo que haga falta —una sección plegada— antes de
 * buscar el nodo, y el `setTimeout` espera al render que eso provoca: un campo que todavía
 * no está en el documento no puede recibir el foco.
 */
export function enfocarPrimerCampoConError(contenedor, errores, orden, antes = null) {
  const primero = orden.find((campo) => errores && errores[campo]);
  if (!primero) return null;
  if (antes) antes(primero);
  setTimeout(() => {
    const nodo = contenedor.current
      && contenedor.current.querySelector(`[data-campo="${primero}"]`);
    if (nodo) nodo.focus();
  }, 0);
  return primero;
}

/**
 * Los errores sin el de un campo, para cuando ese campo se corrige.
 *
 * Se **borra la clave** en vez de ponerla a `undefined`: con la clave puesta, un
 * `Object.keys` posterior seguiría contando ese campo —el resumen de arriba diría «revise
 * el teléfono» de un teléfono ya corregido— aunque el borde rojo y el mensaje hayan
 * desaparecido. Es una diferencia que no se ve hasta que se ve.
 */
export function sinElCampo(errores, campo) {
  if (!errores || errores[campo] === undefined) return errores;
  const resto = { ...errores };
  delete resto[campo];
  return resto;
}

/**
 * Los renglones de un aviso, unidos como el aviso los sabe pintar.
 *
 * Un renglón por cosa que decir, y el salto de línea en un solo sitio: `.alert` lleva
 * `white-space: pre-line` precisamente para esto, y los dos lados tienen que estar de
 * acuerdo. Lo vacío se cae, para que un aviso no empiece con una línea en blanco.
 */
export function comoAviso(renglones) {
  return renglones.filter(Boolean).join('\n');
}

/**
 * Lo que queda para el aviso de arriba cuando los errores ya están junto a sus campos.
 *
 * No repite los mensajes: nombra los campos con **la etiqueta que la pantalla usa**, no con
 * el nombre de la columna. Sirve para dos cosas que el renglón de debajo del campo no
 * puede: que un lector de pantalla anuncie de una vez cuántas cosas hay que revisar, y que
 * quien tenga el formulario desplazado sepa que el problema está más arriba.
 */
export function resumenDeCampos(errores, etiquetas = {}) {
  const nombres = Object.keys(errores || {}).map((campo) => etiquetas[campo] || campo);
  if (!nombres.length) return '';
  if (nombres.length === 1) return `Revise el campo ${nombres[0]}.`;
  return `Revise estos campos: ${nombres.join(', ')}.`;
}
