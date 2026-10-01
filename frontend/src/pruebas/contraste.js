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
    donde: '.badge-hot, y el mismo color en .interes-error y .interes-aviso',
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
  // El rojo de los errores también se escribe directamente sobre el panel, sin su fondo
  // translúcido: es el caso de `.interes-error`, que es el texto que hay que poder leer
  // cuando el formulario dice qué falta.
  {
    texto: '--hot-text', fondo: ['--bg-surface'],
    donde: '.interes-error — el mensaje de «falta este campo», sin fondo propio',
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

  const fondos = Array.isArray(par.fondo)
    ? par.fondo.map((token) => ({ nombre: token, color: aRgb(resolver(token)) }))
    : [{
      nombre: `${par.fondo.sobre} sobre ${par.fondo.encima_de}`,
      color: componer(resolver(par.fondo.sobre), resolver(par.fondo.encima_de)),
    }];

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
