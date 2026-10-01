// ============================================================================
// Toda clase que el marcado usa, la hoja la define
// ============================================================================
//
// De dónde sale esta comprobación
// --------------------------------
// Del punto 3 del capítulo 36, que pide medir el contraste. Medirlo obliga a responder a
// una pregunta previa: **¿de dónde salen los colores de esta pantalla?** Y para la pantalla
// de acceso la respuesta era «de ningún sitio»: sus tres campos llevaban `className="input"`,
// y en la hoja la clase se llama `input-field`. Ninguna regla coincidía, así que los campos
// se dibujaban con el estilo por omisión del navegador —cajas blancas sobre un panel
// oscuro— y la paleta que `contraste.test.js` mide no decía nada sobre ellos.
//
// Un `className` mal escrito no rompe nada. No hay error en la consola, no falla ninguna
// prueba, el componente se monta y la pantalla funciona. Solo se ve distinta, y solo si
// alguien la mira.
//
// Al escribir la comprobación aparecieron quince clases más en el mismo estado, y el
// capítulo 36 las anotó en `SIN_DEFINIR` en vez de corregirlas, porque corregirlas era
// escribir la hoja de un panel entero. **El capítulo 39 las escribió**, así que el
// inventario está vacío; por qué el mecanismo se conserva vacío está abajo, en él.

import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { HOJA } from './contraste.js';

/**
 * Clases que el marcado usa y la hoja NO define, aceptadas a sabiendas.
 *
 * **Está vacía, y el capítulo 39 la vació.** Llevaba las catorce clases de
 * `CompartirEnRedes` y `btn-danger`: lo que faltaba no era corregir un nombre —eso fue el
 * caso de `input-field`— sino escribir la hoja de un panel entero y meter un color de
 * acción destructiva en la paleta. Eran los puntos 30 y 31 de §6.4 y están cerrados.
 *
 * **El mecanismo se conserva, vacío, y no es lo mismo que retirarlo.** La pregunta se
 * planteó: si no hay deuda, ¿para qué la lista? La respuesta es que esta lista no existe
 * para guardar nombres, existe para que aceptar una deuda **cueste escribirla con su
 * motivo**. Quitarla dejaría dos salidas peores el día que vuelva a hacer falta: comentar
 * la comprobación, o meter la clase en la hoja con una regla vacía para que la encuentre.
 * Las dos se parecen demasiado a arreglarlo.
 *
 * Hay una prueba abajo que comprueba que sigue vacía. No prohíbe volver a usarla: obliga a
 * borrar esa prueba para hacerlo, que es justo el tamaño de decisión que corresponde.
 */
const SIN_DEFINIR = {};

/**
 * Las clases que la hoja define, leídas de ella.
 *
 * Los comentarios se quitan primero, y no es un detalle: esta hoja nombra sus propias
 * clases dentro de los comentarios para explicar de dónde sale cada decisión. Sin quitarlos,
 * una clase **mencionada** en una explicación contaría como definida, y la comprobación se
 * aprobaría con la documentación de un arreglo en lugar de con el arreglo. Es la misma
 * lección que el capítulo 37 aprendió en las guardas del CI: buscar una forma, no una
 * palabra, y buscarla en el código y no en lo que el código dice de sí mismo.
 */
function clasesDefinidas(css) {
  const sinComentarios = css.replace(/\/\*[\s\S]*?\*\//g, '');
  return new Set([...sinComentarios.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));
}

/** Todos los `.jsx` del cliente que no son pruebas. */
function componentes(directorio) {
  const encontrados = [];
  for (const entrada of readdirSync(directorio)) {
    const ruta = join(directorio, entrada);
    if (statSync(ruta).isDirectory()) encontrados.push(...componentes(ruta));
    else if (ruta.endsWith('.jsx') && !ruta.includes('.test.')) encontrados.push(ruta);
  }
  return encontrados;
}

/**
 * Las clases que un archivo pide, con la línea donde las pide.
 *
 * Se leen las dos formas que el proyecto usa: `className="a b"` y la plantilla
 * `className={`a ${condicion ? 'b' : ''}`}`. De la segunda se descartan los `${...}`, que
 * son expresiones: lo que devuelven no se puede saber sin ejecutar el componente, y las
 * clases que salen de ahí son siempre alguna de las que ya aparecen escritas al lado.
 */
function clasesPedidas(codigo) {
  const pedidas = new Map();
  const lineas = codigo.split('\n');
  const patron = /className=(?:"([^"{}]*)"|\{`([^`]*)`\})/g;
  for (const coincidencia of codigo.matchAll(patron)) {
    const texto = (coincidencia[1] ?? coincidencia[2] ?? '').replace(/\$\{[^}]*\}/g, ' ');
    const linea = codigo.slice(0, coincidencia.index).split('\n').length;
    for (const clase of texto.split(/\s+/).filter(Boolean)) {
      if (!pedidas.has(clase)) pedidas.set(clase, `${linea}: ${lineas[linea - 1]?.trim().slice(0, 80)}`);
    }
  }
  return pedidas;
}

describe('las clases del marcado', () => {
  const definidas = clasesDefinidas(HOJA);
  const archivos = componentes('src');

  it('se leen de verdad la hoja y los componentes', () => {
    // Sin esto, una ruta mal resuelta dejaría las dos listas vacías y la comprobación de
    // abajo pasaría sin haber mirado nada. Es el mismo cuidado que en `contraste.test.js`.
    expect(definidas.size).toBeGreaterThan(45);
    expect(archivos.length).toBeGreaterThan(20);
    expect(definidas.has('input-field')).toBe(true);
    // Y la que empezó todo esto: `input` a secas no existe, y por eso no se puede usar.
    expect(definidas.has('input')).toBe(false);
  });

  it('ninguna clase nueva se queda sin definir', () => {
    const huerfanas = [];
    for (const ruta of archivos) {
      for (const [clase, donde] of clasesPedidas(readFileSync(ruta, 'utf8'))) {
        if (definidas.has(clase) || clase in SIN_DEFINIR) continue;
        huerfanas.push(`  ${ruta} — «${clase}» en la línea ${donde}`);
      }
    }
    expect(
      huerfanas,
      'Estas clases se usan en el marcado y la hoja no las define, así que ese elemento se '
      + 'dibuja con el estilo por omisión del navegador y nadie se entera:\n'
      + `${huerfanas.join('\n')}\n`
      + 'Si la clase existe con otro nombre, corrija el nombre. Si hace falta escribirla, '
      + 'escríbala. Si es deuda aceptada, añádala a SIN_DEFINIR con su motivo.',
    ).toEqual([]);
  });

  it('la lista de deuda aceptada está vacía', () => {
    // El capítulo 39 pagó las quince entradas que el 36 inventarió. Mientras esto siga
    // así, «la hoja define todo lo que el marcado pide» es una frase sin asteriscos.
    //
    // Volver a usar la lista es legítimo y hay casos en que será lo correcto. Lo que esta
    // prueba impide es hacerlo sin mirar: hay que borrarla, y borrar una prueba se ve en
    // el diff.
    expect(
      Object.entries(SIN_DEFINIR).map(([clase, motivo]) => `${clase} — ${motivo}`),
      'Hay deuda aceptada otra vez. Si es una decisión, borre esta prueba y dígalo en el '
      + 'documento de congelación; si no lo es, defina la clase en la hoja.',
    ).toEqual([]);
  });

  it('la lista de deuda aceptada no guarda nombres que ya se arreglaron', () => {
    // Una lista de excepciones que no se limpia acaba tapando defectos nuevos con el nombre
    // de defectos viejos. Si alguien escribe la hoja de `CompartirEnRedes`, esta prueba
    // obliga a quitar sus catorce entradas de arriba.
    const sobrantes = Object.keys(SIN_DEFINIR).filter((clase) => definidas.has(clase));
    expect(
      sobrantes,
      `Estas clases ya están definidas en la hoja: quítelas de SIN_DEFINIR — ${sobrantes.join(', ')}`,
    ).toEqual([]);

    // Y tampoco guarda nombres que ya no usa nadie.
    const usadas = new Set();
    for (const ruta of archivos) {
      for (const clase of clasesPedidas(readFileSync(ruta, 'utf8')).keys()) usadas.add(clase);
    }
    const olvidadas = Object.keys(SIN_DEFINIR).filter((clase) => !usadas.has(clase));
    expect(
      olvidadas,
      `Estas clases ya no las usa ningún componente: quítelas de SIN_DEFINIR — ${olvidadas.join(', ')}`,
    ).toEqual([]);
  });

  it('un «.btn» sin variante sabe de qué color es su texto', () => {
    // Encontrado mirando el panel ya maquetado (capítulo 39), que es lo único que lo
    // encuentra: `.btn` no declaraba `color`, y en los cuatro `<button>` que la usan sin
    // variante eso no se nota, porque un botón hereda el color de lo que lo rodea. En un
    // `<a>` no: la hoja del navegador le pone el azul de enlace, que gana a la herencia.
    // El único `<a class="btn">` del cliente —«Compartir en LinkedIn»— salía en azul
    // marino sobre un panel oscuro, y sin subrayado, porque `.btn` sí quitaba eso.
    const regla = /\n\.btn \{([\s\S]*?)\n\}/.exec(HOJA);
    expect(regla, 'desapareció la regla base de .btn').not.toBeNull();
    expect(
      regla[1],
      '.btn volvió a no declarar color: un <a class="btn"> sin variante sale con el azul '
      + 'de enlace del navegador',
    ).toMatch(/color:\s*inherit/);
  });

  it('y ningún enlace se queda con «btn» a secas', () => {
    // El arreglo de arriba hace legible ese caso; esto impide que vuelva a haber un enlace
    // con aspecto de nada. Las variantes son las que le dan fondo y borde.
    const sueltos = [];
    for (const ruta of archivos) {
      const codigo = readFileSync(ruta, 'utf8');
      for (const anclas of codigo.matchAll(/<a\s+className="([^"]*\bbtn\b[^"]*)"/g)) {
        if (!/btn-(primary|secondary|danger)/.test(anclas[1])) sueltos.push(`${ruta} — «${anclas[1]}»`);
      }
    }
    expect(sueltos, `Estos enlaces usan .btn sin variante:\n${sueltos.join('\n')}`).toEqual([]);
  });

  it('las pantallas de credenciales usan la clase de campo de la hoja', () => {
    // Las tres pantallas donde se escribe una contraseña o un código llevaban `input`, que
    // no existe. Esto fija el arreglo: son las pantallas cuyo contraste `contraste.test.js`
    // afirma medir, y no lo mediría si sus campos se dibujaran con el estilo del navegador.
    for (const ruta of [
      'src/components/LoginScreen.jsx',
      'src/components/CambioDeContrasenaObligatorio.jsx',
      'src/components/AltaDelSegundoFactor.jsx',
    ]) {
      const codigo = readFileSync(ruta, 'utf8');
      expect(codigo, `${ruta} vuelve a usar className="input"`).not.toMatch(/className="input"/);
      expect(codigo, `${ruta} dejó de usar la clase de campo`).toMatch(/className="input-field"/);
    }
  });
});
