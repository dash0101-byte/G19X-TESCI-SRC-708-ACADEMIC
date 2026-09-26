// ============================================================================
// Contraste de la paleta contra el mínimo de la norma
// ============================================================================
//
// Por qué esto no lo hace `axe`, y por qué la comprobación es mejor así, está explicado en
// `contraste.js`. En resumen: `jsdom` no dibuja, pero los colores no hacen falta dibujarlos
// para medirlos; están escritos en `index.css` y de ahí se leen.
//
// **Modo claro y modo oscuro.** El proyecto tiene **uno solo**, el oscuro. No hay
// `prefers-color-scheme`, ni `data-theme`, ni una segunda paleta en ninguna parte, y hay una
// prueba abajo que lo comprueba en vez de darlo por sabido: el día que alguien añada un modo
// claro, esa prueba se pone en rojo y recuerda que este archivo mide medio sistema.

import { describe, expect, it } from 'vitest';

import {
  MINIMO_NO_TEXTO,
  MINIMO_TEXTO,
  PARES,
  aRgb,
  componer,
  luminancia,
  medirTodo,
  razon,
  tokensDeTexto,
  variablesDe,
  HOJA as CSS,
} from './contraste.js';

describe('la fórmula, contra valores que se conocen', () => {
  // Antes de creerle a esta comprobación lo que dice de la paleta, hay que saber que sabe
  // calcular. Los tres extremos de la norma son públicos y no dependen de este proyecto.
  it('blanco sobre negro da 21, el máximo posible', () => {
    expect(razon('#ffffff', '#000000')).toBeCloseTo(21, 5);
  });

  it('un color consigo mismo da 1', () => {
    expect(razon('#75849b', '#75849b')).toBeCloseTo(1, 10);
  });

  it('el gris #767676 sobre blanco da 4.54, el ejemplo canónico del límite de AA', () => {
    // Es el gris más oscuro que la norma cita como «justo por encima» de 4.5 sobre blanco.
    expect(razon('#767676', '#ffffff')).toBeCloseTo(4.54, 2);
  });

  it('la luminancia del blanco es 1 y la del negro 0', () => {
    expect(luminancia('#ffffff')).toBeCloseTo(1, 10);
    expect(luminancia('#000000')).toBeCloseTo(0, 10);
  });

  it('compone la transparencia: medio blanco sobre negro es gris medio', () => {
    expect(componer('rgba(255, 255, 255, 0.5)', '#000000').slice(0, 3))
      .toEqual([127.5, 127.5, 127.5]);
  });

  it('lee las tres formas de escribir un color que usa la hoja', () => {
    expect(aRgb('#fff')).toEqual([255, 255, 255, 1]);
    expect(aRgb('#10131a')).toEqual([16, 19, 26, 1]);
    expect(aRgb('rgba(255, 255, 255, 0.07)')).toEqual([255, 255, 255, 0.07]);
  });
});

describe('la paleta', () => {
  const variables = variablesDe(CSS);

  it('se lee de index.css y trae los tokens que la interfaz usa', () => {
    // Si el bloque `:root` se moviera o se renombrara, el lector devolvería un objeto vacío
    // y TODAS las comprobaciones de abajo pasarían por no tener nada que medir. Esto es lo
    // que impide que esta prueba se apruebe a sí misma quedándose sin datos.
    expect(Object.keys(variables).length).toBeGreaterThan(20);
    expect(variables['--bg-surface']).toBe('#10131a');
    expect(variables['--text-primary']).toBe('#f8fafc');
  });

  it.each(medirTodo(variables))(
    '$texto sobre $peor.fondo — $donde',
    ({ texto, minimo, peor, medidas }) => {
      const detalle = medidas
        .map((m) => `${m.fondo}: ${m.razon.toFixed(2)}`)
        .join(' · ');
      expect(
        peor.razon,
        `${texto} necesita ${minimo}:1 y su peor caso da ${peor.razon.toFixed(2)}:1 — ${detalle}`,
      ).toBeGreaterThanOrEqual(minimo);
    },
  );

  it('ningún color de texto de la paleta se queda sin comprobar', () => {
    // La lista de pares se escribe a mano porque no hay forma de deducirla sin maquetar.
    // Esto evita el defecto que tiene toda lista escrita a mano: quedarse corta en el
    // siguiente cambio. Un token nuevo sin par declarado deja esta prueba en rojo, y el
    // mensaje dice cuál es.
    const comprobados = new Set(PARES.map((p) => p.texto));
    const sinComprobar = tokensDeTexto(variables).filter((t) => !comprobados.has(t));

    expect(
      sinComprobar,
      `Estos colores de texto están en :root y no dicen sobre qué fondo van: ${sinComprobar.join(', ')}`,
    ).toEqual([]);
  });

  it('el aro de foco llega al mínimo de lo que no es texto', () => {
    // 1.4.11. Va aparte de la tabla porque el mínimo es otro (3.0) y porque es el único
    // par donde el color del «texto» lleva transparencia y hay que componerlo.
    const aro = medirTodo(variables).find((m) => m.texto === '--border-focus');
    expect(aro.minimo).toBe(MINIMO_NO_TEXTO);
    expect(aro.peor.razon).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);
  });
});

describe('el modo claro', () => {
  it('no existe, y por eso aquí se mide una sola paleta', () => {
    // El punto 3 del capítulo pide comprobar el contraste «en claro y en oscuro si existen
    // los dos». No existen. Esto lo deja comprobado en vez de afirmado: si algún día entra
    // un segundo tema, esta prueba lo dice y obliga a duplicar la tabla de arriba.
    expect(CSS).not.toMatch(/prefers-color-scheme/);
    expect(CSS).not.toMatch(/\[data-theme/);
    expect(CSS.match(/:root\s*\{/g)).toHaveLength(1);
  });
});

describe('el texto pequeño no se aprueba llamándolo grande', () => {
  it('todos los pares se miden contra 4.5, salvo el aro de foco', () => {
    // La norma permite 3.0 para texto de 24 px, o de 18.66 px en negrita. Esta interfaz va
    // de 0.7 a 0.875 rem —de 11 a 14 px— y no tiene nada de ese tamaño, así que no hay
    // ningún par que pueda acogerse a esa excepción. Escrito como prueba para que nadie
    // rebaje un mínimo en lugar de arreglar un color.
    for (const par of PARES) {
      const minimo = par.minimo ?? MINIMO_TEXTO;
      if (par.texto === '--border-focus') expect(minimo).toBe(MINIMO_NO_TEXTO);
      else expect(minimo).toBe(MINIMO_TEXTO);
    }
  });
});
