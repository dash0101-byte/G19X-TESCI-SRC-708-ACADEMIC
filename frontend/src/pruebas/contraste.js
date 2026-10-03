// ============================================================================
// Contraste: la razón de la norma, calculada sobre la paleta de verdad
// ============================================================================
//
// `axe` sabe medir contraste, pero necesita píxeles: mira el color calculado de un elemento
// y el de lo que tiene detrás. En `jsdom` no hay maquetación ni hojas aplicadas, así que esa
// regla no puede correr —y `axe` lo dice, la marca «incompleta» en vez de darla por buena—.
//
// Renunciar por eso a comprobar el contraste habría sido lo cómodo y lo equivocado: el
// contraste no es una propiedad de los píxeles, es una propiedad de **dos colores**, y los
// dos colores están escritos en `index.css`. Esto los lee de ahí y aplica la fórmula de la
// norma (WCAG 2.1, 1.4.3 para texto y 1.4.11 para lo que no es texto).
//
// Qué se lee y qué se declara, y por qué no es lo mismo
// -----------------------------------------------------
// * **Los colores se leen** del `:root` de `index.css`. Nadie los copia aquí. Cambiar un
//   token en la hoja cambia lo que esta comprobación mide, que es justo lo que hace que no
//   caduque.
// * **Los pares se declaran** abajo, uno por uno y con el sitio donde ocurren. No hay forma
//   honrada de deducirlos: la mayoría de los colores de texto se aplican con `style` en el
//   JSX, sobre un fondo que pone un componente de más arriba. Deducirlos exigiría maquetar,
//   que es justo lo que aquí no se puede hacer.
//
// Para que esa lista declarada no se quede corta —el defecto que el capítulo 33 corrigió en
// los campos obligatorios y el 35 en la copia de una cuenta— la prueba comprueba además que
// **todo token de color de texto del `:root` aparece en la lista**. Añadir un color a la
// paleta sin decir sobre qué fondo va deja la prueba en rojo.

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// La hoja se lee del disco, y encontrarla tiene más historia de la que parece.
//
// `import.meta.url` no sirve: dentro de `jsdom` Vite lo reescribe a una `http://`, y
// `fileURLToPath` la rechaza. `import '../index.css?raw'` tampoco: `vitest` trae `css:
// false` por omisión —no compila hojas para las pruebas, que es lo correcto— y devuelve la
// cadena vacía. Una comprobación que midiera una hoja vacía pasaría siempre sin medir nada,
// que es el peor resultado posible aquí.
//
// Se busca por tanto desde el directorio de trabajo, que es la raíz que `vitest` fija, y se
// falla con un mensaje claro si no está. La prueba comprueba además que lo leído tiene
// tokens dentro: la cadena vacía no puede pasar por paleta.
const CANDIDATAS = ['src/index.css', 'frontend/src/index.css'];

function rutaDeLaHoja() {
  for (const candidata of CANDIDATAS) {
    const ruta = resolve(process.cwd(), candidata);
    if (existsSync(ruta)) return ruta;
  }
  throw new Error(
    `No se encontró index.css desde ${process.cwd()}. Buscado en: ${CANDIDATAS.join(', ')}`,
  );
}

export const HOJA = readFileSync(rutaDeLaHoja(), 'utf8');

// ---------------------------------------------------------------------------
// Leer la paleta
// ---------------------------------------------------------------------------

/** Los `--token: valor;` del bloque `:root` de la hoja, tal cual están escritos. */
export function variablesDe(css = HOJA) {
  const raiz = /:root\s*\{([\s\S]*?)\n\}/.exec(css);
  if (!raiz) throw new Error('No se encontró el bloque :root en index.css');
  const variables = {};
  // Se quitan los comentarios antes de partir por `;`: dentro de uno hay puntos y comas.
  const cuerpo = raiz[1].replace(/\/\*[\s\S]*?\*\//g, '');
  for (const declaracion of cuerpo.split(';')) {
    const par = /^\s*(--[\w-]+)\s*:\s*(.+?)\s*$/.exec(declaracion);
    if (par) variables[par[1]] = par[2];
  }
  return variables;
}

// ---------------------------------------------------------------------------
// Color
// ---------------------------------------------------------------------------

/**
 * Un token puede apuntar a otro: `--accent-primary: var(--color-primary)`.
 *
 * Esa forma de escribirlo entró en el capítulo 39 y es la correcta —el marcado pedía
 * `--accent-primary` desde hacía capítulos y lo que quería era el blanco de la paleta, así
 * que decirlo con un alias no repite el valor y no deja dos copias que se puedan separar—,
 * pero dejaba a esta comprobación sin nada que medir: `aRgb` no sabe leer `var(...)`.
 *
 * Se siguen las referencias hasta llegar a un color. El límite de saltos no es adorno: un
 * alias circular colgaría la suite en vez de fallar, y una suite colgada no dice nada.
 */
export function resolverAlias(valor, variables, saltos = 8) {
  let actual = String(valor).trim();
  for (let i = 0; i < saltos; i += 1) {
    const alias = /^var\(\s*(--[\w-]+)\s*\)$/.exec(actual);
    if (!alias) return actual;
    if (variables[alias[1]] === undefined) {
      throw new Error(`El alias ${alias[1]} no está en :root`);
    }
    actual = String(variables[alias[1]]).trim();
  }
  throw new Error(`Demasiados saltos resolviendo ${valor}: ¿un alias circular?`);
}

/** `#rgb`, `#rrggbb` o `rgba(r, g, b, a)` → `[r, g, b, a]` con los canales en 0-255. */
export function aRgb(valor) {
  const texto = String(valor).trim();

  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(texto);
  if (hex) {
    const d = hex[1].length === 3 ? hex[1].split('').map((c) => c + c).join('') : hex[1];
    return [parseInt(d.slice(0, 2), 16), parseInt(d.slice(2, 4), 16), parseInt(d.slice(4, 6), 16), 1];
  }

  const rgba = /^rgba?\(([^)]+)\)$/i.exec(texto);
  if (rgba) {
    const partes = rgba[1].split(',').map((p) => parseFloat(p.trim()));
    return [partes[0], partes[1], partes[2], partes.length > 3 ? partes[3] : 1];
  }

  throw new Error(`Color que no se sabe leer: ${valor}`);
}

/**
 * Un color con transparencia no tiene contraste propio: lo que se ve es la mezcla con lo
 * que tiene detrás. Esto la calcula.
 *
 * Importa más de lo que parece en esta paleta: los fondos de las insignias HOT/WARM/COLD y
 * todos los bordes están declarados con alfa sobre el panel, así que medirlos sin componer
 * daría el contraste de un color que no existe en ninguna pantalla.
 */
export function componer(encima, debajo) {
  // Los dos admiten ya la forma `[r, g, b, a]`, igual que `luminancia`: un borde se
  // compone a veces sobre un fondo que a su vez salió de una composición.
  const [r1, g1, b1, a] = Array.isArray(encima) ? encima : aRgb(encima);
  const [r2, g2, b2] = Array.isArray(debajo) ? debajo : aRgb(debajo);
  if (a >= 1) return [r1, g1, b1, 1];
  return [r1 * a + r2 * (1 - a), g1 * a + g2 * (1 - a), b1 * a + b2 * (1 - a), 1];
}

/** Luminancia relativa, tal como la define la norma. */
export function luminancia(color) {
  const [r, g, b] = Array.isArray(color) ? color : aRgb(color);
  const canal = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

/** La razón de contraste entre dos colores ya opacos. Entre 1 y 21. */
export function razon(uno, otro) {
  const a = luminancia(uno);
  const b = luminancia(otro);
  const [claro, oscuro] = a >= b ? [a, b] : [b, a];
  return (claro + 0.05) / (oscuro + 0.05);
}

// ---------------------------------------------------------------------------
// Los mínimos de la norma
// ---------------------------------------------------------------------------
//
// 1.4.3 (AA): 4.5 para texto normal, 3.0 para texto grande —24 px, o 18.66 px en negrita—.
// 1.4.11 (AA): 3.0 para lo que identifica un control o su estado.
//
// **Se exige 4.5 casi en todo a propósito.** Esta interfaz es de 0.7 a 0.875 rem —de 11 a
// 14 px—: no hay texto grande. Clasificar algo como «grande» para bajarle el listón sería
// aprobarlo cambiando la vara de medir.
export const MINIMO_TEXTO = 4.5;
export const MINIMO_NO_TEXTO = 3.0;

/**
 * Los pares que de verdad ocurren en las pantallas, con dónde ocurren.
 *
 * `fondo` puede ser una lista: el mismo color de texto sobre los distintos fondos donde se
 * usa. Se exige el peor de todos, que es el que decide si se lee o no.
 */
export const PARES = [
  // --- Texto sobre las superficies del panel ---
  {
    texto: '--text-primary',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'el texto normal de todo el panel (body, encabezados, .btn-secondary)',
  },
  {
    texto: '--text-secondary',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated'],
    donde: 'subtítulos y textos de apoyo (.data-table td, .badge-status, la ficha)',
  },
  {
    texto: '--text-muted',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated'],
    donde: '.form-label, .data-table th, .interes-ayuda, el pie y las cabeceras de sección',
  },

  // --- Las insignias de categoría: color sobre su propio fondo translúcido ---
  //
  // El fondo lleva alfa sobre el panel, así que se compone antes de medir. Y se mide sobre
  // `--bg-surface`, que es el panel donde viven: las filas de la tabla y las tarjetas.
  {
    texto: '--hot-text', fondo: { sobre: '--hot-bg', encima_de: '--bg-surface' },
    donde: '.badge-hot y los demás sitios donde el color dice «este prospecto está '
      + 'caliente»: la muestra de la leyenda, el score por encima del umbral y el KPI',
  },
  {
    texto: '--warm-text', fondo: { sobre: '--warm-bg', encima_de: '--bg-surface' },
    donde: '.badge-warm',
  },
  {
    texto: '--cold-text', fondo: { sobre: '--cold-bg', encima_de: '--bg-surface' },
    donde: '.badge-cold',
  },
  {
    texto: '--success-text', fondo: { sobre: '--success-bg', encima_de: '--bg-surface' },
    donde: 'los avisos de que algo salió bien',
  },

  // --- Los mismos cuatro colores SIN su fondo propio (capítulo 43) ---
  //
  // La insignia es el caso cómodo: trae su relleno, así que el par estaba escrito. Pero
  // estos cuatro colores pintan además texto suelto sobre el panel desnudo —el score de
  // una fila, el número de un KPI, el pie de una tarjeta de calibración, la nota de un
  // enlace caducado— y esos pares **no estaban en esta lista**. No se notaba porque la
  // comprobación de abajo pide que cada token de texto aparezca en `PARES` al menos una
  // vez, y todos aparecían: en la fila de su insignia.
  //
  // Es el mismo defecto que esta tabla vigila en otros —medir el token y no el uso— una
  // planta más arriba. Van sobrados los cuatro, lo que no quita que nadie lo supiera.
  {
    texto: '--hot-text',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'el score por encima del umbral en LeadsTable y en la ficha, el KPI de los HOT '
      + 'y el umbral de la tarjeta de calibración, sin relleno propio detrás',
  },
  {
    texto: '--warm-text',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'lo mismo para la temperatura templada, y el peso heurístico de la tarjeta de '
      + 'calibración, que se dibuja sobre --bg-base',
  },
  {
    texto: '--cold-text',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'el score de una ficha fría, sin relleno propio detrás',
  },
  {
    texto: '--success-text',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'el «✓ copiado» y los demás textos de que algo salió bien que no llevan caja',
  },

  // --- La advertencia (capítulo 43) ---
  //
  // El tercer corte de la serie que empezó el 39: --warn-* es el ámbar que avisa, separado
  // del ámbar que dice que un prospecto está templado. Mismos valores y dos tokens, porque
  // lo que se separa no es el color sino la decisión de moverlo.
  {
    texto: '--warn-text',
    fondo: { sobre: '--warn-bg', encima_de: ['--bg-base', '--bg-surface', '--bg-surface-elevated'] },
    donde: '.alert-warn — el aviso ámbar de una pantalla, sobre su propio fondo translúcido',
  },
  {
    texto: '--warn-text',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    donde: 'las advertencias sin caja: «no le quedan códigos de recuperación», la columna '
      + 'de las contraseñas prestadas, el enlace caducado de una publicación y el título '
      + 'de la confirmación de una supresión',
  },

  // --- El texto de apoyo DENTRO de un aviso (capítulo 43) ---
  //
  // Dentro de una caja de aviso el fondo no es el panel: es el panel con el rojo o el
  // ámbar translúcido encima, que lo **aclara**. Un texto claro pierde contraste ahí, y
  // --text-muted se queda en 3.78 — por debajo de §1.4.3. Pasó en la nota del simulador y
  // en la dirección pública que no responde, las dos escritas a mano dentro de la caja.
  {
    texto: '--text-secondary',
    fondo: { sobre: '--error-bg', encima_de: ['--bg-base', '--bg-surface', '--bg-surface-elevated'] },
    donde: 'la segunda línea de un .alert-error: la nota del simulador y la dirección que '
      + 'no contesta',
  },
  {
    texto: '--text-secondary',
    fondo: { sobre: '--bg-chip', encima_de: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'] },
    donde: '.chip — los datos sueltos de la ficha 360, donde --text-muted daba 4.47',
  },
  {
    texto: '--text-secondary',
    fondo: { sobre: '--bg-subtle', encima_de: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'] },
    donde: '.badge-status — la insignia de un estado, que tres pantallas reescribían a '
      + 'mano con --text-muted encima del mismo relleno',
  },

  // --- La caja del decaimiento del simulador (capítulo 44) ---
  //
  // Tres pares más que la extracción del capítulo 43 **no puede ver**, y por un motivo
  // distinto al de entonces: allí el par estaba dentro de un `style` y la lista se escribía
  // a mano; aquí el relleno lo pone el `style` del `div` de fuera y el color el del `div` de
  // dentro. Un extractor que recorre cada objeto por separado no ve ningún par: ve un fondo
  // sin texto y un texto sin fondo. Juntarlos exige el árbol del marcado, no el archivo.
  //
  // Aparecieron al meter el simulador en la auditoría, que es la otra lista escrita a mano
  // de este directorio: la pantalla que ningún motor miraba era también la pantalla cuyos
  // colores nadie había declarado. Los tres pasan —el peor, 4.64— y entran para que sigan
  // midiéndose: el de la nota es --text-muted, que es el token que en el capítulo 43 falló
  // dos veces encima de este mismo relleno.
  {
    texto: '--warm-text',
    fondo: { sobre: '--bg-subtle', encima_de: ['--bg-surface'] },
    donde: 'el rótulo de los días de inactividad del simulador cuando pasan de catorce, '
      + 'dentro de la caja del decaimiento',
  },
  {
    texto: '--text-primary',
    fondo: { sobre: '--bg-subtle', encima_de: ['--bg-surface'] },
    donde: 'el mismo rótulo mientras el decaimiento no ha empezado',
  },
  {
    texto: '--text-muted',
    fondo: { sobre: '--bg-subtle', encima_de: ['--bg-surface'] },
    donde: 'la nota de la vida media debajo del deslizador, el único --text-muted que '
      + 'queda encima de este relleno: 4.64, que pasa por 0,14',
  },

  // --- Lo que se escribe dentro de un campo (capítulo 43) ---
  //
  // Estos dos los declara la propia hoja —`.input-field` y `.interes-boton` ponen el fondo y
  // el color en la misma regla— y tampoco estaban aquí: `--bg-field` y `--bg-field-focus`
  // subieron a la paleta en el capítulo 39 y nadie midió lo que se escribe encima. Van
  // sobrados los dos; lo que importa es que ya se miden.
  {
    texto: '--text-primary', fondo: ['--bg-field', '--bg-field-focus'],
    donde: 'el valor que se escribe en un .input-field, y el texto de la opción elegida',
  },
  {
    texto: '--text-secondary', fondo: ['--bg-field', '--bg-field-focus'],
    donde: '.interes-boton — una opción de la página pública sin elegir',
  },

  // --- El estado de error (capítulo 40) ---
  //
  // Hasta este capítulo el rojo de los errores era `--hot-text`, el de la temperatura de
  // un prospecto, y en cuatro avisos de tres pantallas no era ningún token: era #ef4444
  // escrito a mano en un `style` del JSX, que es el único sitio de esta aplicación donde
  // un color no pasa por aquí. Daba 4.43 sobre el panel y 4.17 sobre el elevado.
  {
    texto: '--error-text',
    fondo: { sobre: '--error-bg', encima_de: ['--bg-base', '--bg-surface', '--bg-surface-elevated'] },
    donde: '.alert-error — el aviso de una pantalla, sobre su propio fondo translúcido',
  },
  // Y el mismo color sin fondo propio: el mensaje que va pegado a un campo.
  {
    texto: '--error-text', fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated'],
    donde: '.form-error y .interes-error — «falta este campo», junto al campo que falta',
  },

  // --- El botón principal: texto oscuro sobre blanco ---
  {
    texto: '--color-primary-text', fondo: ['--color-primary', '--color-primary-hover'],
    donde: '.btn-primary y su estado :hover',
  },

  // --- El botón de acción destructiva (capítulo 39) ---
  {
    texto: '--danger-text', fondo: ['--danger-bg', '--danger-bg-hover'],
    donde: '.btn-danger y su :hover — «Cerrar sesión» y los dos botones de suprimir',
  },

  // --- Los tokens que el marcado pedía y la paleta no tenía (capítulo 39) ---
  //
  // Dos de los cinco se usan como **color de texto**, así que entran en la tabla con el
  // mínimo de texto aunque su nombre no acabe en `-text` y `tokensDeTexto` no los reclame.
  // Que una lista automática no los exija no significa que no haya que medirlos.
  {
    texto: '--accent-primary', fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated'],
    donde: 'el nombre del prospecto en el informe de publicación, que es un botón-enlace',
  },
  {
    texto: '--color-primary-light', fondo: ['--bg-surface', '--bg-surface-elevated'],
    donde: 'el «⏳ Evaluando…» del simulador de scoring',
  },

  // --- Lo que no es texto (1.4.11) ---
  //
  // `componer_sobre_el_fondo` en lugar del antiguo `componer_texto_sobre`: un borde
  // translúcido se mezcla con **el fondo que tiene detrás**, que es distinto en cada sitio
  // donde el control vive. Mezclarlo siempre con `--bg-surface` y después compararlo con
  // `--bg-base` medía un color que en esa pantalla no existe. La diferencia era pequeña
  // —centésimas— y el resultado no cambiaba de lado, pero medir bien no es opcional
  // cuando lo medido es el argumento.
  {
    texto: '--border-control',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover', '--bg-field'],
    minimo: MINIMO_NO_TEXTO,
    componer_sobre_el_fondo: true,
    donde: 'el contorno en reposo de .input-field, .btn-secondary, .interes-boton, '
      + '.interes-red-casilla y el selector del QR (§6.4 punto 32)',
  },
  {
    texto: '--border-focus',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover', '--bg-field-focus'],
    minimo: MINIMO_NO_TEXTO,
    componer_sobre_el_fondo: true,
    donde: 'el aro de foco: .input-field:focus, .interes-boton:has(input:focus-visible) '
      + 'y los :focus-visible del panel de difusión',
  },
  {
    texto: '--border-error',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover', '--bg-field'],
    minimo: MINIMO_NO_TEXTO,
    donde: 'el contorno de un campo cuyo valor no vale: .input-field[aria-invalid="true"] '
      + '(§6.4 punto 36). No baja a la primera parada que pasa porque este borde no cambia '
      + 'con el foco, y cuanto más claro sea menos sitio queda para que el foco se note',
  },
  // Las tres etapas de la barra del embudo. Llevan información —el ancho dice cuántas
  // fichas hay en cada etapa—, así que §1.4.11 les pide 3.0, y se miden contra la pista
  // sobre la que se dibujan y no contra el panel, que es lo que hay detrás de verdad.
  {
    texto: '--funnel-won',
    fondo: { sobre: '--bg-chip', encima_de: ['--bg-surface', '--bg-surface-elevated'] },
    minimo: MINIMO_NO_TEXTO,
    donde: 'el segmento de las fichas ganadas en el embudo de AnalyticsCharts',
  },
  {
    texto: '--funnel-qualified',
    fondo: { sobre: '--bg-chip', encima_de: ['--bg-surface', '--bg-surface-elevated'] },
    minimo: MINIMO_NO_TEXTO,
    donde: 'el segmento de las cualificadas — el más justo de los tres, 3.56',
  },
  {
    texto: '--funnel-rest',
    fondo: { sobre: '--bg-chip', encima_de: ['--bg-surface', '--bg-surface-elevated'] },
    minimo: MINIMO_NO_TEXTO,
    donde: 'el segmento de las demás etapas, que es el punto de WARM escrito una vez',
  },
  {
    texto: '--danger-border',
    fondo: ['--bg-base', '--bg-surface', '--bg-surface-elevated', '--bg-surface-hover'],
    minimo: MINIMO_NO_TEXTO,
    donde: 'el contorno de .btn-danger — su relleno solo da 2.87:1 contra el panel, así '
      + 'que lo que delimita el botón es el borde',
  },
];

/**
 * Los dos sitios donde el foco **cambia** el aspecto de un control, medidos.
 *
 * Esto no lo pide WCAG 2.1 por número —§2.4.7 solo exige que el foco sea visible—, y por
 * eso no está en la tabla de arriba, que es la de los mínimos de la norma. Está aquí
 * porque el capítulo 39 estuvo a un paso de arreglar §1.4.11 rompiendo §2.4.7: subir el
 * borde en reposo a 3.0 lo dejaba a 1.11 del aro de foco, es decir, con el contorno por
 * fin visible y el foco invisible. Dos criterios que se empujan, y un número que lo dice.
 *
 * Se mide el color compuesto del borde en reposo contra el color compuesto del borde con
 * foco, en los dos controles donde el cambio ocurre y los fondos no son los mismos.
 */
export const CAMBIOS_DE_ESTADO = [
  {
    donde: 'un campo: .input-field pasa de --bg-field a --bg-field-focus',
    reposo: { borde: '--border-control', fondo: '--bg-field' },
    foco: { borde: '--border-focus', fondo: '--bg-field-focus' },
  },
  {
    donde: 'un botón secundario: .btn-secondary:hover pasa a --bg-surface-hover',
    reposo: { borde: '--border-control', fondo: '--bg-surface-elevated' },
    foco: { borde: '--border-focus', fondo: '--bg-surface-hover' },
  },
  // El tercero es de otra clase, y por eso está escrito con el fondo en los dos lados.
  //
  // En un campo inválido el borde rojo **no cambia** al recibir el foco: el error no se
  // va porque se esté escribiendo en el campo. Lo que aparece es un aro por fuera, y lo
  // que hay que medir es ese aro contra **lo que había en ese sitio antes**, que es el
  // panel. No es una elección estética: no existe ningún rojo que llegue a 3.0 por encima
  // de --border-error —el blanco puro da 1.96—, así que señalar el foco cambiando el color
  // del borde dejaría §2.4.7 incumplido en todos los campos inválidos de la aplicación.
  // `contraste.test.js` recalcula esa imposibilidad para que quede escrita y no se olvide.
  {
    donde: 'un campo inválido: el aro de foco aparece por fuera, sobre el panel',
    reposo: { borde: '--bg-surface', fondo: '--bg-surface' },
    foco: { borde: '--border-focus', fondo: '--bg-surface' },
  },
];

/** La razón entre el borde en reposo y el borde con el estado puesto, ya compuestos. */
export function medirCambios(variables = variablesDe()) {
  const color = ({ borde, fondo }) => {
    const detras = resolverAlias(variables[fondo], variables);
    return componer(resolverAlias(variables[borde], variables), detras);
  };
  return CAMBIOS_DE_ESTADO.map((cambio) => ({
    ...cambio,
    razon: razon(color(cambio.reposo), color(cambio.foco)),
  }));
}

/** Los tokens del `:root` que son color de texto y por tanto tienen que estar en `PARES`. */
export function tokensDeTexto(variables) {
  return Object.keys(variables).filter(
    (token) => token.startsWith('--text-') || token.endsWith('-text'),
  );
}

/**
 * Resuelve un par a colores opacos y devuelve la peor razón con su fondo.
 */
export function medir(par, variables) {
  const resolver = (token) => {
    const valor = variables[token];
    if (valor === undefined) throw new Error(`El token ${token} no está en :root`);
    return resolverAlias(valor, variables);
  };

  const texto = aRgb(resolver(par.texto));

  // `encima_de` admite una lista: el mismo fondo translúcido se compone sobre cada una de
  // las superficies donde el elemento aparece de verdad. El aviso de error vive en tres
  // —el panel, el modal y el fondo de las pantallas de credenciales—, y medirlo solo
  // sobre una elegiría el color con la medida más cómoda de las tres.
  const debajoDe = (par.fondo && par.fondo.encima_de) || [];
  const fondos = Array.isArray(par.fondo)
    ? par.fondo.map((token) => ({ nombre: token, color: aRgb(resolver(token)) }))
    : (Array.isArray(debajoDe) ? debajoDe : [debajoDe]).map((debajo) => ({
      nombre: `${par.fondo.sobre} sobre ${debajo}`,
      color: componer(resolver(par.fondo.sobre), resolver(debajo)),
    }));

  // Un color translúcido que se mezcla con cada fondo, y no con uno fijo: es lo que pasa
  // de verdad con un borde, que no es el mismo color sobre un campo que sobre un panel.
  const medidas = fondos.map((f) => ({
    fondo: f.nombre,
    razon: razon(par.componer_sobre_el_fondo ? componer(resolver(par.texto), f.color) : texto, f.color),
  }));
  const peor = medidas.reduce((a, b) => (a.razon <= b.razon ? a : b));
  return { ...par, minimo: par.minimo ?? MINIMO_TEXTO, medidas, peor };
}

/** Todas las medidas, para la prueba y para la tabla del reporte. */
export function medirTodo(variables = variablesDe()) {
  return PARES.map((par) => medir(par, variables));
}
