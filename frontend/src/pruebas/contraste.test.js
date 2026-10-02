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
  medirCambios,
  medirTodo,
  razon,
  resolverAlias,
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

  it('el contorno de un control en reposo también llega a 3.0', () => {
    // §6.4 punto 32, abierto desde el capítulo 36: el borde de un campo sin foco daba
    // 1.12:1 contra el fondo del campo, es decir, el contorno no existía hasta que llegaba
    // el foco. Lo que §1.4.11 pide no es que un control se vea cuando se usa, es que se
    // vea que está ahí.
    const reposo = medirTodo(variables).find((m) => m.texto === '--border-control');
    expect(reposo, '--border-control dejó de estar en la tabla de pares').toBeDefined();
    expect(reposo.minimo).toBe(MINIMO_NO_TEXTO);
    expect(reposo.peor.razon).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);
    // Y se mide sobre los cinco fondos donde hay controles, no sobre uno cómodo.
    expect(reposo.medidas.map((m) => m.fondo)).toContain('--bg-field');
  });

  it('el borde del botón destructivo delimita el botón', () => {
    // El relleno rojo sólido solo da 2.87:1 contra el panel: por debajo de 3.0. Si el
    // borde desapareciera, el botón dejaría de tener contorno perceptible y §1.4.11 se
    // incumpliría con el mismo color de relleno que parece suficiente a la vista.
    const borde = medirTodo(variables).find((m) => m.texto === '--danger-border');
    expect(borde.minimo).toBe(MINIMO_NO_TEXTO);
    expect(borde.peor.razon).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);
    expect(razon(variables['--danger-bg'], variables['--bg-surface'])).toBeLessThan(MINIMO_NO_TEXTO);
  });
});

describe('arreglar un criterio sin romper el otro', () => {
  const variables = variablesDe(CSS);

  it('el foco se sigue distinguiendo del reposo en los dos controles donde cambia', () => {
    // Esta es la prueba que el capítulo 39 necesitaba antes de tocar nada. Subir el borde
    // en reposo de 0.07 a 0.34 cumple §1.4.11; dejar el aro de foco en 0.35 lo habría
    // puesto a 1.11 del reposo, es decir, habría cumplido §1.4.11 **incumpliendo** §2.4.7,
    // que pide que el foco sea visible. Los dos tokens se mueven juntos o ninguno.
    for (const cambio of medirCambios(variables)) {
      expect(
        cambio.razon,
        `${cambio.donde}: el cambio de estado solo da ${cambio.razon.toFixed(2)}:1, así que `
        + 'el foco no se distingue del reposo',
      ).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);
    }
  });

  it('mide los tres sitios donde el cambio ocurre, no uno', () => {
    // El campo da 3.30 y el botón secundario 3.06: es el **botón** el que obliga a 0.71,
    // porque pasa de un fondo más claro a otro más claro todavía. Medir solo el campo
    // habría dejado pasar 0.70, que en el botón se queda en 2.99. El tercero lo añade el
    // capítulo 40: un campo inválido, donde el borde no cambia y el aro se añade.
    const cambios = medirCambios(variables);
    expect(cambios).toHaveLength(3);
    expect(cambios.map((c) => c.donde).join(' ')).toMatch(/campo[\s\S]*bot[\s\S]*inválido/);
  });

  it('en un campo inválido el foco no se puede señalar cambiando el color del borde', () => {
    // Esta prueba no comprueba un arreglo: comprueba **por qué el arreglo es el que es**.
    //
    // El capítulo 39 encontró que subir el borde en reposo a 3.0 dejaba el aro de foco a
    // 1.11, y la salida fue mover los dos tokens juntos. Aquí esa salida no existe: el
    // borde de un campo inválido es rojo y no puede cambiar al recibir el foco —si
    // cambiara, el error desaparecería justo mientras se escribe en el campo—, y los dos
    // candidatos naturales a sustituirlo se quedan cortos:
    //
    // * el aro de foco de esta paleta, rgba(255,255,255,0.71), compuesto sobre el fondo
    //   del campo con foco: **1.96**;
    // * el rojo más claro que sigue siendo rojo, #fecaca, que ya es casi rosa: **2.60**.
    //
    // Pasar de 3.0 exige el blanco puro (3.76), que no es ni un rojo —se perdería el
    // error— ni el aro de foco de esta paleta —sería un quinto token de borde inventado
    // para un solo caso—. De ahí que el foco de un campo inválido sea un aro **añadido**
    // por fuera: cuando no hay salida cromática, la salida es geométrica.
    //
    // Si algún día --border-error se oscurece lo bastante como para que el aro de foco de
    // la paleta sí alcance 3.0 sobre él, esta prueba se pone en rojo y hay que volver a
    // decidir. Es la única forma de que una decisión tomada por imposibilidad no sobreviva
    // a la imposibilidad.
    const invalido = componer(variables['--border-error'], variables['--bg-field']);
    const aroDeLaPaleta = componer(variables['--border-focus'], variables['--bg-field-focus']);
    expect(
      razon(aroDeLaPaleta, invalido),
      'el aro de foco de la paleta ya alcanza 3.0 sobre --border-error: un cambio de color '
      + 'bastaría para señalar el foco, y hay que revisar si el aro añadido sigue siendo '
      + 'la solución correcta',
    ).toBeLessThan(MINIMO_NO_TEXTO);
    expect(razon('#fecaca', invalido)).toBeLessThan(MINIMO_NO_TEXTO);
    // Y lo que sí llegaría, dicho con su número para que no se busque dos veces.
    expect(razon('#ffffff', invalido)).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);

    // El aro, que es la salida que se tomó, sí se distingue de lo que había debajo: el
    // panel. Es el tercer renglón de CAMBIOS_DE_ESTADO, medido de la paleta.
    const aro = medirCambios(variables).find((c) => c.donde.includes('inválido'));
    expect(aro.razon).toBeGreaterThanOrEqual(MINIMO_NO_TEXTO);
  });
});

describe('un token puede apuntar a otro', () => {
  const variables = variablesDe(CSS);

  it('sigue el alias hasta el color', () => {
    expect(variables['--accent-primary']).toBe('var(--color-primary)');
    expect(resolverAlias(variables['--accent-primary'], variables)).toBe('#ffffff');
    expect(resolverAlias('#abcdef', variables)).toBe('#abcdef');
  });

  it('no se cuelga con un alias circular: lo dice', () => {
    // Una suite colgada no informa de nada. Esto es lo que diferencia un límite de saltos
    // de una recursión sin fondo.
    const circulo = { '--a': 'var(--b)', '--b': 'var(--a)' };
    expect(() => resolverAlias('var(--a)', circulo)).toThrow(/circular/);
  });

  it('un alias a un token que no existe no pasa por color', () => {
    expect(() => resolverAlias('var(--no-existe)', {})).toThrow(/no está en :root/);
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
  // Los únicos pares que se miden contra 3.0 son los que no son texto: §1.4.11 habla de
  // bordes, de estados y de objetos gráficos con información, no de letras. Se enumeran
  // aquí, y no se deduce del nombre del token, para que bajarle el mínimo a un color de
  // texto obligue a tocar esta lista.
  const NO_TEXTO = [
    '--border-control', '--border-focus', '--border-error', '--danger-border',
    '--funnel-won', '--funnel-qualified', '--funnel-rest',
  ];

  it('todos los pares se miden contra 4.5, salvo los bordes y las barras', () => {
    // La norma permite 3.0 para texto de 24 px, o de 18.66 px en negrita. Esta interfaz va
    // de 0.7 a 0.875 rem —de 11 a 14 px— y no tiene nada de ese tamaño, así que no hay
    // ningún par que pueda acogerse a esa excepción. Escrito como prueba para que nadie
    // rebaje un mínimo en lugar de arreglar un color.
    for (const par of PARES) {
      const minimo = par.minimo ?? MINIMO_TEXTO;
      if (NO_TEXTO.includes(par.texto)) expect(minimo).toBe(MINIMO_NO_TEXTO);
      else expect(minimo, `${par.texto} — ${par.donde}`).toBe(MINIMO_TEXTO);
    }
  });

  it('y ningún par con 3.0 se cuela sin estar en esa lista', () => {
    const colados = PARES.filter((p) => p.minimo === MINIMO_NO_TEXTO && !NO_TEXTO.includes(p.texto));
    expect(
      colados.map((p) => p.texto),
      'Estos pares se miden contra 3.0 y no están en la lista de arriba: o son texto y les '
      + 'toca 4.5, o hay que decir aquí por qué no lo son',
    ).toEqual([]);
  });
});
