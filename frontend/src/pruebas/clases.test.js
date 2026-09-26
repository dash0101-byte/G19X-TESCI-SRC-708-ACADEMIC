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
// Al escribir la comprobación aparecieron quince clases más en el mismo estado. No se
// corrigen aquí y el motivo está escrito abajo, en `SIN_DEFINIR`.

import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { HOJA } from './contraste.js';

/**
 * Clases que el marcado usa y la hoja NO define, aceptadas a sabiendas.
 *
 * Esto **no** es una lista de excepciones cómodas: es un inventario de una deuda que este
 * capítulo encontró y decidió no pagar, con el motivo. Corregirla no es escribir bien un
 * nombre —lo que se hizo con `input-field`— sino **diseñar** un panel entero: elegir
 * colores, espaciados y estados para catorce clases que hoy no existen. Eso es rediseñar
 * una pantalla, y el capítulo 36 lo excluyó de su alcance por escrito.
 *
 * Queda anotado en §6.4 del documento de congelación. Mientras tanto esta lista hace dos
 * cosas: deja constancia de qué falta exactamente, y **impide que la deuda crezca**, porque
 * una clase nueva sin definir no está aquí y pone la prueba en rojo.
 */
const SIN_DEFINIR = {
  // `CompartirEnRedes` no usa ni un solo estilo en línea: se apoya entera en estas catorce
  // clases, y ninguna existe. El panel de difusión y el del QR se dibujan por tanto sin
  // ningún estilo. Es el panel de «Compartir en redes» dentro de Publicaciones; la página
  // pública, que usa el prefijo `interes-` de verdad, sí está definida entera.
  'interes-redes': 'CompartirEnRedes — el panel de difusión no tiene hoja (§6.4)',
  'interes-redes-lista': 'CompartirEnRedes (§6.4)',
  'interes-red-casilla': 'CompartirEnRedes (§6.4)',
  'interes-compartir': 'CompartirEnRedes (§6.4)',
  'interes-compartir-lista': 'CompartirEnRedes (§6.4)',
  'interes-compartir-red': 'CompartirEnRedes (§6.4)',
  'interes-compartir-cuenta': 'CompartirEnRedes (§6.4)',
  'interes-compartir-acciones': 'CompartirEnRedes (§6.4)',
  'interes-compartir-sin-boton': 'CompartirEnRedes (§6.4)',
  'interes-compartir-aviso': 'CompartirEnRedes (§6.4)',
  'interes-qr': 'CompartirEnRedes (§6.4)',
  'interes-qr-dibujo': 'CompartirEnRedes (§6.4)',
  'form-hint': 'CompartirEnRedes — texto de ayuda sin estilo propio (§6.4)',
  'form-error': 'CompartirEnRedes — texto de error sin estilo propio (§6.4)',
  // El botón de cerrar sesión pide un aspecto de acción destructiva que la paleta no tiene.
  // Hoy se dibuja como un `.btn` a secas: borde transparente y sin fondo, es decir, no
  // parece un botón. Darle uno exige un color nuevo en la paleta, que el capítulo excluyó.
  'btn-danger': 'SessionModal, «Cerrar sesión» — la paleta no tiene color de acción destructiva (§6.4)',
};

/** Las clases que la hoja define, leídas de ella. */
function clasesDefinidas(css) {
  return new Set([...css.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));
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
    expect(definidas.size).toBeGreaterThan(30);
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
