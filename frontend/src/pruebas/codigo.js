// ============================================================================
// Los archivos del cliente, leídos del disco una sola vez y de la misma forma
// ============================================================================
//
// Tres comprobaciones de este directorio recorren el código fuente buscando lo que el
// marcado nombra: `clases.test.js` las clases de CSS, `tokens.test.js` las variables de la
// paleta y `colores.test.js` los colores escritos a mano. Las tres tenían su propia copia
// de «qué archivos son el cliente» y de «qué es un comentario».
//
// Eso no es duplicación de tres líneas: es el riesgo de que dos guardas no estén mirando
// el mismo sitio. El día que una de las copias deje fuera un directorio nuevo, su barrido
// seguirá verde sin haber mirado nada de lo que hay dentro, y nada lo dirá. Está aquí una
// vez, y las tres lo importan.

import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Los archivos del cliente que pueden nombrar una clase, un token o un color.
 *
 * Las pruebas se excluyen por el nombre: hablan de clases y de colores para comprobarlos,
 * y contarlas sería preguntarle a la guarda por su propio texto.
 */
export function fuentes(directorio = 'src') {
  const encontrados = [];
  for (const entrada of readdirSync(directorio)) {
    const ruta = join(directorio, entrada);
    if (statSync(ruta).isDirectory()) encontrados.push(...fuentes(ruta));
    else if (/\.(jsx|js|css)$/.test(ruta) && !ruta.includes('.test.')) encontrados.push(ruta);
  }
  // Las rutas salen con la barra del sistema: en Windows, `src\components\x.jsx`. Se
  // normalizan aquí para que un inventario escrito con barras normales valga en las dos
  // plataformas, y para que el mensaje de un fallo se pueda pegar en un editor.
  return encontrados.map((ruta) => ruta.split('\\').join('/'));
}

/**
 * Se quitan los comentarios antes de buscar.
 *
 * Es la lección del capítulo 37 aplicada aquí: una guarda que busca un texto en un archivo
 * se satisface con su propia documentación. Las cabeceras de estos archivos nombran
 * `var(--accent-primary)` y `#ef4444` para explicar de dónde vienen, y una cabecera no es
 * código.
 *
 * Las de línea se quitan solo cuando empiezan la línea: `//` en medio de una es casi
 * siempre el de un `https://`.
 */
export function sinComentarios(codigo) {
  return codigo.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

/** El número de línea de una posición dentro de un texto, para que un fallo se pueda abrir. */
export function lineaDe(texto, posicion) {
  return texto.slice(0, posicion).split('\n').length;
}

/**
 * Cada `<input|select|textarea …>` del marcado, con su etiqueta completa.
 *
 * Cierra por el `>` que **no** está dentro de llaves. Un `<input[^>]*?>` se queda corto y
 * no se nota: el primer `>` de un atributo es el de la flecha de `onChange={(e) => …}`, así
 * que el recorte deja fuera todo lo que venga después —la clase, el `id`, el `type`— y la
 * guarda contesta sobre media etiqueta. Con eso una cuenta de 19 de 103 pasó por buena
 * hasta el capítulo 43, cuando la de verdad eran 11 de 88.
 *
 * Vivía dentro de `avisos.test.js`. Está aquí desde el capítulo 44 porque la guarda de las
 * pantallas auditadas necesita el mismo recorrido con **otro** filtro: a la de la clase un
 * deslizador no le interesa —no tiene contorno que medir— y a la de la auditoría sí, porque
 * un control sin nombre accesible es un control sin nombre accesible. Dos filtros, un
 * barrido; dos barridos serían dos ideas distintas de qué es un control.
 */
export function cajasDeFormulario(codigo) {
  const encontradas = [];
  for (const inicio of [...codigo.matchAll(/<(input|select|textarea)\b/g)]) {
    let profundidad = 0;
    for (let i = inicio.index; i < codigo.length; i += 1) {
      const c = codigo[i];
      if (c === '{') profundidad += 1;
      else if (c === '}') profundidad -= 1;
      else if (c === '>' && profundidad === 0) {
        encontradas.push({ etiqueta: codigo.slice(inicio.index, i + 1), en: inicio.index });
        break;
      }
    }
  }
  return encontradas;
}
