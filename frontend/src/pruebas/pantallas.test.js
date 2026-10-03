// ============================================================================
// La lista de pantallas auditadas sale del código, no de la memoria de nadie
// ============================================================================
//
// De dónde sale esto
// -------------------
// `accesibilidad.test.jsx` pasa `axe-core` por cada pantalla y exige el nivel AA. Desde el
// capítulo 36 y hasta el 44, **la lista de pantallas estaba escrita a mano**: ocho, de las
// dieciocho que llevan cajas de formulario. Las otras diez no las había mirado ningún motor
// nunca, y llevaban 39 de las 105 cajas del cliente.
//
// Lo que había dentro no era un empate. Tres deslizadores del simulador sin ningún nombre
// accesible —infracción **crítica**—, el selector del rol de cada cuenta sin nombre —otra
// crítica, y es el control que cambia los permisos de una persona—, un `aria-label` sobre un
// `div` sin rol en el alta del segundo factor —ARIA lo prohíbe, así que el único dibujo de
// esa pantalla no tenía nombre— y dos pantallas enteras fuera de toda región.
//
// Y el defecto no estaba repartido al azar: **seguía la lista**. `LoginScreen` lleva escrito
// desde el capítulo 36 «`<main>` y no un `<div>`: es la pantalla entera y no estaba dentro
// de ninguna región». El cambio obligatorio de contraseña y el alta del segundo factor son
// también la pantalla entera, y seguían siendo un `<div>`. La diferencia entre las tres es
// que la auditoría montaba una.
//
// Qué hace esta guarda
// ---------------------
// Lo mismo que `tokens.test.js` con la paleta y que `avisos.test.js` con los pares de
// colores: **deriva el inventario del código**. Recorre los componentes, se queda con los
// que tienen al menos un control de formulario y exige que cada uno aparezca montado en la
// auditoría. Una pantalla nueva nace en rojo, que es el único momento en que alguien está
// mirando: después, nadie vuelve a leer la lista.
//
// Por qué «con controles» y no «todos los componentes»: un control es lo que hay que
// nombrar, etiquetar y alcanzar con el teclado, y es donde se concentra lo que `axe` sabe
// ver sin píxeles. Un componente que solo pinta —una tarjeta, un gráfico, una vista previa—
// se audita de paso, dentro de la pantalla que lo monta.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import { cajasDeFormulario, fuentes, sinComentarios } from './codigo.js';

const AUDITORIA = 'src/pruebas/accesibilidad.test.jsx';

/** El nombre del componente que exporta un archivo: `src/components/Campana.jsx` → `Campana`. */
function nombreDe(ruta) {
  return ruta.split('/').pop().replace(/\.jsx$/, '');
}

/**
 * Los componentes del cliente con al menos un control de formulario.
 *
 * Se descarta `type="hidden"`: no se ve, no se enfoca y no hay nada que nombrar. Todo lo
 * demás cuenta, **incluidos los deslizadores y las casillas**, que es justo donde estaba el
 * defecto de este capítulo: la guarda de `.input-field` los excluye a propósito —no tienen
 * contorno que medir— y por ese hueco pasaron tres controles sin nombre.
 */
function pantallasConControles() {
  const encontradas = [];
  for (const ruta of fuentes('src')) {
    if (!ruta.endsWith('.jsx') || ruta === AUDITORIA) continue;
    const codigo = sinComentarios(readFileSync(ruta, 'utf8'));
    const controles = cajasDeFormulario(codigo)
      .filter(({ etiqueta }) => !/type="hidden"/.test(etiqueta));
    if (controles.length) encontradas.push({ ruta, nombre: nombreDe(ruta), controles: controles.length });
  }
  return encontradas;
}

describe('la auditoría de accesibilidad mira todas las pantallas', () => {
  const PANTALLAS = pantallasConControles();
  const auditoria = sinComentarios(readFileSync(AUDITORIA, 'utf8'));

  // La guarda se comprueba a sí misma antes de afirmar nada. Un barrido que no encontró
  // nada contesta «todo auditado» con la misma cara que uno que lo comprobó, y esa es la
  // forma en que una comprobación de inventario se queda muda sin que nada se ponga rojo.
  it('el barrido encuentra las pantallas y sus controles', () => {
    expect(PANTALLAS.length, 'el barrido no encontró ninguna pantalla con controles')
      .toBeGreaterThan(12);
    const controles = PANTALLAS.reduce((suma, p) => suma + p.controles, 0);
    expect(controles, 'el barrido no encontró controles: el recorrido del marcado falla')
      .toBeGreaterThan(80);
  });

  it('y la auditoría monta todas', () => {
    const sinAuditar = PANTALLAS
      .filter(({ nombre }) => !new RegExp(`<${nombre}[\\s/>]`).test(auditoria))
      .map(({ ruta, nombre, controles }) => `  ${nombre} (${controles} controles) — ${ruta}`);

    expect(
      sinAuditar,
      'Estas pantallas llevan controles de formulario y `accesibilidad.test.jsx` no las '
      + 'monta, así que ningún motor ha mirado su marcado. Añada un `describe` allí con la '
      + 'pantalla montada **como la monta la aplicación** —un bloque de pestaña dentro de '
      + '`<main>`, un modal solo, una pantalla entera con su propia región— y no apague la '
      + 'regla que estorbe:\n'
      + `${sinAuditar.join('\n')}`,
    ).toEqual([]);
  });

  // El nombre del componente se busca como etiqueta JSX y no como texto: `AdminPanel`
  // aparece en la cabecera de media docena de archivos, y una guarda que se conforme con
  // encontrar la palabra se la encuentra en su propia documentación —la lección del
  // capítulo 37—. Por eso los comentarios se quitan antes y el patrón exige el `<`.
  it('el patrón no se conforma con el nombre escrito en un comentario', () => {
    const conComentario = '// Aquí se habla de AdminPanel sin montarlo.\nconst x = 1;\n';
    expect(/<AdminPanel[\s/>]/.test(sinComentarios(conComentario))).toBe(false);
    expect(/<AdminPanel[\s/>]/.test('render(<AdminPanel onBatchRecalculate={f} />);')).toBe(true);
  });
});
