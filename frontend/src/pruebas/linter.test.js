// ============================================================================
// Que el análisis estático de accesibilidad siga encendido
// ============================================================================
//
// `eslint` es la mitad barata de este capítulo: encuentra un `<div onClick>` sin ejecutar
// nada, y encontró cuatro —tres tarjetas de KPI y la pastilla de la sesión, que era la única
// puerta a cerrar sesión—. Pero una regla de `eslint` se apaga escribiendo `'off'`, y
// cuando se apaga **el pipeline se pone verde**, que es exactamente al revés de lo que hace
// una prueba al quitarla.
//
// Por eso la configuración se comprueba desde la suite: aquí, apagar una regla pone algo en
// rojo. Es el mismo criterio con el que el capítulo 22 obligó a que las imágenes llevaran
// huella y el 34 a que ninguna ruta de gestión entrara en la puerta pública: lo que protege
// al sistema no puede depender de que nadie toque una línea de configuración.
//
// Lo que NO hace: exigir que estén las 34 reglas por su nombre. Eso ataría el proyecto a
// una versión del plugin y se rompería al actualizarlo por motivos de seguridad, que es
// justo cuando no conviene tener el pipeline en rojo por algo que no es el problema. Lo que
// se exige es **que el conjunto entre entero**, y que las exclusiones sean las declaradas.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import jsxA11y from 'eslint-plugin-jsx-a11y';
import configuracion from '../../eslint.config.js';

/**
 * Las reglas que se apagan a sabiendas, con quién las apaga.
 *
 * Igual que `SIN_DEFINIR` en `clases.test.js`: una lista de excepciones sin motivo escrito
 * es una lista que crece cada vez que alguien tiene prisa. El motivo largo de esta vive en
 * `eslint.config.js`, junto a la línea que la apaga.
 */
const APAGADAS_A_PROPOSITO = {
  'jsx-a11y/no-autofocus':
    'Las dos pantallas que lo usan tienen el formulario como único contenido; el motivo '
    + 'entero está escrito en eslint.config.js.',
};

/** El bloque de la configuración que trae las reglas de los componentes. */
function bloqueDeComponentes() {
  const bloque = configuracion.find(
    (b) => b.rules && b.plugins && 'jsx-a11y' in b.plugins,
  );
  expect(bloque, 'no se encontró el bloque que carga el plugin de accesibilidad').toBeTruthy();
  return bloque;
}

describe('la configuración del linter', () => {
  const bloque = bloqueDeComponentes();
  const recomendadas = Object.keys(jsxA11y.flatConfigs.recommended.rules);

  it('trae el conjunto de accesibilidad entero, no una selección', () => {
    // Que estén las 34 de la versión instalada. Si el plugin sube de versión y añade dos,
    // esta comprobación las exige también, que es el comportamiento buscado: entrar con el
    // conjunto significa entrar con el conjunto.
    expect(recomendadas.length).toBeGreaterThan(30);
    const ausentes = recomendadas.filter((regla) => !(regla in bloque.rules));
    expect(
      ausentes,
      `El conjunto de accesibilidad ya no entra entero. Faltan: ${ausentes.join(', ')}`,
    ).toEqual([]);
  });

  it('ninguna regla de accesibilidad está apagada salvo las declaradas', () => {
    // Se compara contra lo que el PLUGIN trae encendido, no contra la lista entera. El
    // propio `recommended` incluye tres reglas apagadas de fábrica —`anchor-ambiguous-text`,
    // `control-has-associated-label` y `label-has-for`, las dos últimas obsoletas—, y
    // exigirle al proyecto que justifique una decisión que no tomó sería obligarle a
    // explicar algo que no sabe. Lo que hay que justificar es apagar lo que venía encendido.
    const nivelDe = (valor) => (Array.isArray(valor) ? valor[0] : valor);
    const estaApagada = (valor) => nivelDe(valor) === 'off' || nivelDe(valor) === 0;
    const encendidasDeFabrica = recomendadas.filter(
      (regla) => !estaApagada(jsxA11y.flatConfigs.recommended.rules[regla]),
    );

    const apagadas = encendidasDeFabrica.filter((regla) => estaApagada(bloque.rules[regla]));

    const sinDeclarar = apagadas.filter((regla) => !(regla in APAGADAS_A_PROPOSITO));
    expect(
      sinDeclarar,
      'Estas reglas de accesibilidad se apagaron y nadie dijo por qué: '
      + `${sinDeclarar.join(', ')}. Si hay un motivo, escríbalo en eslint.config.js y `
      + 'añádalo a APAGADAS_A_PROPOSITO.',
    ).toEqual([]);

    // Y al revés: una excepción que ya no hace falta se quita.
    const sobrantes = Object.keys(APAGADAS_A_PROPOSITO).filter((r) => !apagadas.includes(r));
    expect(
      sobrantes,
      `Estas reglas ya no están apagadas: quítelas de APAGADAS_A_PROPOSITO — ${sobrantes.join(', ')}`,
    ).toEqual([]);
  });

  it('el motivo de cada regla apagada está escrito en el propio archivo', () => {
    // No basta con declararla aquí: quien lea `eslint.config.js` tiene que encontrar allí
    // por qué, sin venir a buscarlo a una prueba.
    const fuente = readFileSync(resolve(process.cwd(), 'eslint.config.js'), 'utf8');
    for (const regla of Object.keys(APAGADAS_A_PROPOSITO)) {
      const nombreCorto = regla.replace('jsx-a11y/', '');
      // La línea que la apaga, y además una explicación cerca: se exige que el archivo
      // mencione la regla por su nombre corto más de una vez —la línea y el comentario—.
      const apariciones = fuente.split(nombreCorto).length - 1;
      expect(
        apariciones,
        `${regla} se apaga sin explicación en eslint.config.js`,
      ).toBeGreaterThan(1);
    }
  });

  it('la regla que encontró los cuatro divs pulsables sigue en «error»', () => {
    // `no-static-element-interactions` y `click-events-have-key-events` son las dos que
    // señalaron las tres tarjetas de KPI y la pastilla de la sesión. Bajarlas a «warn» las
    // dejaría pasar el pipeline: un aviso no rompe nada, y por eso se acumulan.
    for (const regla of [
      'jsx-a11y/no-static-element-interactions',
      'jsx-a11y/click-events-have-key-events',
      'jsx-a11y/label-has-associated-control',
      'jsx-a11y/tabindex-no-positive',
    ]) {
      const valor = bloque.rules[regla];
      const nivel = Array.isArray(valor) ? valor[0] : valor;
      expect(nivel, `${regla} debería ser «error» y es «${nivel}»`).toBe('error');
    }
  });
});
