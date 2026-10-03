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

// Las dos constantes que dicen cómo se lee un rechazo del servidor —el prefijo de Pydantic y
// la tabla por tipo del capítulo 40— viven desde el 45 en `services/rechazos.js`. Estaban
// escritas aquí y otra vez en `api.js`, y la copia de allí no tenía la tabla: seis de nueve
// rechazos de los dos formularios que no reparten llegaban en inglés, con la traducción ya
// escrita en este archivo.
import { POR_TIPO, RUIDO_DE_PYDANTIC } from '../services/rechazos';

export { POR_TIPO };

/** El último tramo de `loc`: `['body', 'email']` → `email`. */
function campoDe(item) {
  if (!Array.isArray(item.loc) || !item.loc.length) return null;
  return String(item.loc[item.loc.length - 1]);
}

/**
 * De qué campos habla un renglón que no puede señalarlos con su `loc` (capítulo 45).
 *
 * Un `model_validator` de Pydantic responde `loc: ['body']`: ve el cuerpo entero y no un
 * campo, así que su rechazo no cabe debajo de ninguno. Los tres del servidor que comprueban
 * los campos sin los que una fila no existe mandan la lista en `ctx.campos` —dato
 * estructurado, no prosa— precisamente para que sí quepa.
 *
 * Y mandan **nombres de campo**, no nombres de columna: lo que el servidor devuelve ahí es lo
 * que el cliente le envió. Por eso se pueden cruzar con los campos de la pantalla sin
 * ninguna tabla de traducción, que es lo que el capítulo 43 decidió no escribir.
 *
 * Se devuelve `null` —y no una lista vacía— cuando el renglón no trae campos, para que quien
 * pregunta distinga «no habla de ningún campo» de «habla de estos».
 */
function camposDelContexto(item) {
  const campos = item && item.ctx && item.ctx.campos;
  if (!Array.isArray(campos)) return null;
  const limpios = campos.filter((c) => typeof c === 'string' && c);
  return limpios.length ? limpios : null;
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
 *
 * Desde el capítulo 45 hay dos maneras de saber de qué campo habla un renglón: su `loc`, y
 * —cuando el `loc` dice `body` porque lo escribió un validador de modelo— la lista de
 * `ctx.campos`. Un renglón de esos se reparte entre **todos** los campos que nombra, con la
 * frase corta de su tipo debajo de cada uno; si la pantalla no pinta ninguno, al aviso de
 * arriba va la frase larga del servidor, que se lee sola.
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
    const traducir = (nombre) => (nombre && renombres[nombre] ? renombres[nombre] : nombre);
    const mensaje = mensajeDelRenglon(item, propios);

    // Un renglón que trae sus campos en el `ctx` habla de varios a la vez, y se reparte
    // entre todos (capítulo 45). Los que esta pantalla no pinta no se pierden: el aviso de
    // arriba dice **la frase del servidor**, que es la larga y no nombra ninguna columna. La
    // corta —«No puede quedar vacío»— solo tiene sentido debajo de un campo.
    const delContexto = camposDelContexto(item);
    if (delContexto) {
      let alguno = false;
      for (const bruto of delContexto) {
        const campo = traducir(bruto);
        if (campos && !campos.includes(campo)) continue;
        // Sigue mandando la regla 1 de `mensajeDelRenglon`: si la pantalla tiene su propia
        // frase para ese campo, esa. Aquí hay que repetirla porque el `loc` de este renglón
        // dice `body`, así que esa función no puede saber de qué campo se trata.
        if (!porCampo[campo]) porCampo[campo] = propios[campo] || mensaje;
        alguno = true;
      }
      if (!alguno) sueltos.push(String(item.msg || mensaje));
      continue;
    }

    const campo = traducir(campoDe(item));
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
 * De qué campo habla cada respuesta conocida del cambio de contraseña (capítulo 43).
 *
 * Las otras siete pantallas del panel no reparten su 422 por campos, y §6.4 lo contaba como
 * «el mismo arreglo en los sitios donde el 422 es menos probable». Al medirlo, el reparto no
 * era posible en casi ninguna: lo que el servidor contesta en esas puertas **no lleva el
 * campo**. Los dos formularios de contraseña son el caso claro, y el que el propio punto 37
 * ponía de ejemplo:
 *
 * * **401** — «La contraseña actual no es correcta.» Habla de la actual.
 * * **422 con `motivos`** — la política la rechaza, y los motivos son todos los que
 *   incumple. Habla de la nueva.
 * * **422 sin `motivos`** — «no puede ser igual a la actual». También de la nueva.
 *
 * Ninguna trae `loc`, porque ninguna sale de un validador de Pydantic: son `HTTPException`
 * escritas en el endpoint. Así que el campo no se **lee**, se **sabe**: es el contrato de esa
 * puerta, y está escrito aquí una vez para los dos formularios que la llaman. No se decide
 * comparando el texto del mensaje, que es lo que caducaría al reescribir una frase.
 *
 * El primer renglón va debajo del campo y los demás al aviso de arriba, que es el reparto
 * que el capítulo 40 dejó montado: el renglón de un campo tiene que caber al lado del campo.
 */
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
