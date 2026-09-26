// ============================================================================
// Revisión automática de accesibilidad sobre una pantalla ya montada
// ============================================================================
//
// `axe-core` es el motor que usan las extensiones de navegador para auditar accesibilidad.
// Aquí se llama desde la propia suite del cliente, contra el DOM que `@testing-library`
// acaba de montar, para que una pantalla que deja de cumplir la norma ponga el pipeline en
// rojo el mismo día y no el día que alguien la audite a mano.
//
// **No hay biblioteca nueva.** `axe-core` ya estaba instalado desde el capítulo 17: es
// dependencia de `eslint-plugin-jsx-a11y`, que la usa para saber qué roles y atributos ARIA
// existen. Estaba en `node_modules` y nadie la llamaba nunca. Declararla como dependencia
// de desarrollo directa añadió **una línea** al lockfile y ni un paquete al árbol.
//
// ---------------------------------------------------------------------------
// Lo que este motor SÍ puede ver aquí, y lo que NO
// ---------------------------------------------------------------------------
//
// Corre sobre `jsdom`, que implementa el DOM pero **no dibuja nada**: no hay motor de
// maquetación, ni hojas de estilo aplicadas, ni colores calculados. Eso separa las reglas
// en dos grupos, y conviene tenerlo claro para no creer que esto comprueba más de lo que
// comprueba:
//
// * **Se comprueban aquí** las reglas estructurales, que son la mayoría y las que más
//   fallan: etiquetas sin control, botones sin nombre accesible, `aria-*` con valores que
//   no existen, `id` duplicados a los que apunta un `aria-describedby`, listas mal
//   anidadas, encabezados que saltan niveles, tablas sin cabecera, `role` inventados.
// * **No se pueden comprobar aquí** las que necesitan píxeles: contraste de color y tamaño
//   del área táctil. `axe` las marca como «incompletas» en vez de fingir que pasan, y esta
//   función lo deja dicho en la salida.
//
// El contraste tiene su propia comprobación, que no pasa por el DOM: lee la paleta de
// `index.css` y calcula la razón de la norma sobre los pares declarados
// (`contraste.test.js`). Es la respuesta correcta a un entorno sin píxeles: en vez de
// renunciar a la comprobación, se hace sobre la fuente del color en vez de sobre su
// resultado.

import axe from 'axe-core';

// Las etiquetas de la norma que se exigen. `wcag2a`/`wcag2aa` son WCAG 2.0 y `wcag21a`/
// `wcag21aa` lo que añadió la 2.1. Es el nivel AA, que es el que citan las normativas de
// accesibilidad web que aplican a un sitio corporativo.
//
// **No se incluye `best-practice`.** Son recomendaciones del propio `axe`, no de la norma,
// y mezclarlas haría imposible responder «¿esto cumple AA?» mirando la salida: un fallo de
// la norma y una sugerencia de estilo se verían igual. Las que de verdad importan de ese
// grupo se piden aparte y por su nombre (ver `REGLAS_ANADIDAS`).
export const NIVEL = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// Tres reglas de `best-practice` que sí se exigen, una por una y con su motivo:
//
// * `region` — todo el contenido visible tiene que estar dentro de una marca de región
//   (`main`, `nav`, `header`, `section` con nombre…). Sin ellas, quien navega por regiones
//   con un lector de pantalla no tiene por dónde saltar y recorre la pantalla entera
//   elemento a elemento. No es AA, pero es la diferencia entre una pantalla usable y una
//   que hay que leer entera.
// * `aria-allowed-role` — un `role` puesto sobre un elemento que no lo admite. El navegador
//   lo aplica igual y el resultado es un elemento que se anuncia como algo que no hace.
// * `heading-order` — encabezados que saltan de `h1` a `h3`. El índice que construye el
//   lector de pantalla queda con agujeros.
export const REGLAS_ANADIDAS = ['region', 'aria-allowed-role', 'heading-order'];

// Reglas apagadas, con el motivo escrito. Una lista de exclusiones sin motivo es una lista
// que crece cada vez que alguien tiene prisa.
export const REGLAS_APAGADAS = {
  // Necesita píxeles. `jsdom` no calcula colores, así que `axe` la deja «incompleta» y
  // apagarla evita que esa incompletitud se confunda con un resultado. El contraste se
  // comprueba de verdad en `contraste.test.js`, leyendo la paleta.
  'color-contrast': 'Necesita maquetación: se comprueba en contraste.test.js sobre la paleta',
};

/**
 * Pasa `axe` por el contenedor indicado y devuelve las infracciones encontradas.
 *
 * Devuelve el informe entero en vez de lanzar: quien llama decide qué hacer con él, y las
 * pruebas de rendimiento lo usan para contar sin fallar.
 */
export async function revisar(contenedor = document.body, { reglas = {} } = {}) {
  const apagadas = Object.fromEntries(
    Object.keys(REGLAS_APAGADAS).map((id) => [id, { enabled: false }]),
  );
  const anadidas = Object.fromEntries(REGLAS_ANADIDAS.map((id) => [id, { enabled: true }]));

  const informe = await axe.run(contenedor, {
    runOnly: { type: 'tag', values: [...NIVEL, 'best-practice'] },
    // El filtro por etiquetas de arriba incluiría `best-practice` entera. Esto lo corrige:
    // todo lo de ese grupo queda apagado salvo las tres que se piden por su nombre.
    rules: { ...apagadasDeBestPractice(), ...anadidas, ...apagadas, ...reglas },
    // Sin esto, `axe` intenta leer las hojas de estilo de la página para las reglas de
    // color y `jsdom` tarda segundos en cada prueba sin llegar a ninguna conclusión.
    preload: false,
  });
  return informe;
}

// Todas las reglas que `axe` clasifica como `best-practice` y no están en la lista corta
// de arriba, apagadas. Se calcula del catálogo del propio motor en vez de escribirse a
// mano: una versión nueva de `axe` que añada reglas de ese grupo no debe meter ruido en
// una comprobación que dice medir el nivel AA.
function apagadasDeBestPractice() {
  const fuera = {};
  for (const regla of axe.getRules(['best-practice'])) {
    if (!REGLAS_ANADIDAS.includes(regla.ruleId)) fuera[regla.ruleId] = { enabled: false };
  }
  return fuera;
}

/**
 * Convierte el informe en un texto que dice qué falla, dónde y cómo se arregla.
 *
 * El informe de `axe` es un objeto grande y anidado; volcado tal cual en un `expect`
 * fallido produce cien líneas de las que ninguna es la que hay que leer. Esto deja una
 * línea por elemento con el selector CSS exacto y la explicación del motor.
 */
export function comoTexto(informe) {
  if (!informe.violations.length) return 'sin infracciones';
  return informe.violations
    .map((v) => {
      const nodos = v.nodes
        .map((n) => `      · ${n.target.join(' ')}\n        ${n.failureSummary?.replace(/\n/g, '\n        ')}`)
        .join('\n');
      return `  [${v.impact}] ${v.id}: ${v.help}\n${nodos}`;
    })
    .join('\n');
}

/**
 * Monta la aserción que usan las pruebas: ninguna infracción, y si la hay, se lee.
 */
export async function noDebeTenerInfracciones(contenedor = document.body, opciones) {
  const informe = await revisar(contenedor, opciones);
  if (informe.violations.length) {
    throw new Error(
      `${informe.violations.length} infracción(es) de accesibilidad:\n${comoTexto(informe)}`,
    );
  }
  return informe;
}
