// ============================================================================
// Un aviso está en la página, y lo que escribe un `style` nadie lo mide
// ============================================================================
//
// De dónde sale esto
// -------------------
// Del capítulo 43, y de dos puntos de §6.4 que estaban mal medidos.
//
// El **38** decía «siete errores se avisan con un `alert()` del navegador: seis en el
// recálculo masivo de `App.jsx` y uno en el recálculo de una ficha». Eran seis y todos en
// `App.jsx` —el de la ficha lo había movido el capítulo 40 sin que nadie actualizara el
// punto—, uno no era de ningún recálculo y **dos no eran errores**: uno anunciaba un éxito
// («✅ 312 prospectos recalculados») y otro decía que el trabajo seguía en curso. Un cuadro
// del navegador no forma parte de la página: ningún lector de pantalla lo anuncia como
// contenido, no se puede señalar junto a nada, tapa lo que hay que mirar y al pulsar
// «Aceptar» no queda nada de lo que decía.
//
// El **37** decía que diez avisos conservaban «sus siete propiedades en un `style`» y que
// eso «no incumple ningún mínimo». Las dos frases eran falsas. Los diez que llevan
// `className="alert"` tienen en su `style` **una** propiedad, un margen; los que escribían
// la caja a mano eran otros, los que nunca recibieron la clase. Y sí incumplía: un par de
// colores escrito en un `style` es un par que `contraste.test.js` no puede ver, porque su
// lista de pares se declara a mano. Al derivarla del código aparecieron cinco combinaciones
// que nadie había medido y una de ellas por debajo de los 4.5 de §1.4.3.
//
// Qué comprueba este archivo
// ---------------------------
// Lo que el capítulo arregló, pero sacado del código y no de una lista escrita: un `alert()`
// nuevo, una caja de aviso escrita a mano o un par de colores sin medir nacen en rojo.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import { fuentes, lineaDe, sinComentarios } from './codigo.js';
import { HOJA, PARES } from './contraste.js';

const ARCHIVOS = fuentes('src');

/** El código del cliente sin comentarios, archivo por archivo. */
function codigoLimpio() {
  return ARCHIVOS.map((ruta) => [ruta, sinComentarios(readFileSync(ruta, 'utf8'))]);
}

describe('ningún aviso sale por un cuadro del navegador', () => {
  // `alert`, `confirm` y `prompt` son los tres. `confirm` era el más caro de los tres y el
  // que §6.4 no mencionaba: decidía el borrado de un aviso sin asociar, que es la única
  // operación de esa pantalla que no se puede deshacer.
  const CUADROS = /(?<![\w.$])(?:window\s*\.\s*)?(alert|confirm|prompt)\s*\(/g;

  it('se leen los archivos de verdad', () => {
    expect(ARCHIVOS.length).toBeGreaterThan(30);
    expect(ARCHIVOS.some((r) => r.endsWith('App.jsx'))).toBe(true);
  });

  it('ni uno, en ningún archivo del cliente', () => {
    const encontrados = [];
    for (const [ruta, codigo] of codigoLimpio()) {
      for (const hallazgo of codigo.matchAll(CUADROS)) {
        encontrados.push(`  ${ruta}:${lineaDe(codigo, hallazgo.index)} — ${hallazgo[1]}(`);
      }
    }
    expect(
      encontrados,
      'Un cuadro del navegador no forma parte de la página: no lo anuncia ningún lector de '
      + 'pantalla, no se puede señalar junto a nada y tapa lo que hay que corregir. Lo que '
      + 'haya que decir va en un `.alert` dentro de una región viva:\n'
      + `${encontrados.join('\n')}`,
    ).toEqual([]);
  });

  it('y la guarda sabe encontrarlos, para no aprobarse a sí misma', () => {
    // Sin esto, un día la expresión deja de casar y la comprobación de arriba pasa siempre.
    const ejemplo = sinComentarios(`
      window.alert('x');
      confirm('y');
      if (prompt('z')) return;
    `);
    expect([...ejemplo.matchAll(CUADROS)].map((m) => m[1])).toEqual(['alert', 'confirm', 'prompt']);
  });

  it('no confunde un nombre que acabe en alert ni una propiedad', () => {
    const ejemplo = sinComentarios(`
      const miAlert = 1;
      registro.alert('no es el del navegador');
      setAviso({ tipo: 'alert' });
    `);
    expect([...ejemplo.matchAll(CUADROS)]).toEqual([]);
  });
});

describe('las tres variantes del aviso', () => {
  it('la hoja las define', () => {
    for (const variante of ['.alert-error', '.alert-warn', '.alert-ok']) {
      expect(HOJA, `${variante} desapareció de la hoja`).toContain(variante);
    }
  });

  it('y el cliente las usa, las tres', () => {
    // `.alert-warn` estaba escrita desde el capítulo 40 y **no la usaba nadie**: el ámbar
    // era la variante del aviso que no tenía dónde salir. La usan ahora el resultado en
    // curso del recálculo, el turno ocupado, el enlace caducado de una publicación y la
    // confirmación de un descarte. Una clase que la hoja define y el marcado no pide es una
    // clase que nadie ha visto nunca dibujada.
    const marcado = codigoLimpio().filter(([ruta]) => ruta.endsWith('.jsx'));
    for (const variante of ['alert-error', 'alert-warn', 'alert-ok']) {
      const quienes = marcado.filter(([, codigo]) => codigo.includes(variante));
      expect(quienes.length, `nadie usa ${variante}`).toBeGreaterThan(0);
    }
  });
});

// ---------------------------------------------------------------------------
// Los pares de colores que un `style` forma, contra los que `PARES` mide
// ---------------------------------------------------------------------------
//
// `contraste.js` explica en su cabecera por qué los pares se declaran y no se deducen: «la
// mayoría de los colores de texto se aplican con `style` en el JSX, sobre un fondo que pone
// un componente de más arriba», y deducir ese fondo exigiría maquetar. Es cierto, y tiene
// una excepción que vale mucho: cuando **el mismo `style`** escribe el color y su fondo, el
// par está completo ahí mismo y se puede leer sin maquetar nada.
//
// De los veintiún pares que el cliente formaba así, cinco combinaciones no estaban en
// `PARES`: --text-muted sobre --bg-chip y sobre --bg-subtle, --text-primary y
// --text-secondary sobre --bg-chip, y --error-text sobre --hot-bg. La primera daba 4.47
// sobre el panel y 4.18 sobre el elevado, por debajo de los 4.5 de §1.4.3; la última era un
// error pintado con el fondo de la temperatura HOT, la mezcla que el capítulo 40 separó, y
// pasaba por 0,24 sin que nadie lo supiera.
describe('los pares que el marcado escribe en un mismo style', () => {
  const COLOR = /(?<!border)(?<!Border)color:\s*'?var\((--[\w-]+)\)/gi;
  const FONDO = /background(?:Color)?:\s*'?var\((--[\w-]+)\)/g;

  /** El trozo de `codigo` que empieza en `desde` y acaba en la llave que lo equilibra. */
  function hastaLaLlaveQueCierra(codigo, desde) {
    let profundidad = 0;
    for (let i = desde; i < codigo.length; i += 1) {
      if (codigo[i] === '{') profundidad += 1;
      else if (codigo[i] === '}') {
        profundidad -= 1;
        if (profundidad === 0) return codigo.slice(desde, i + 1);
      }
    }
    return codigo.slice(desde);
  }

  /**
   * Cada objeto de estilo del marcado que escribe a la vez un color y un fondo.
   *
   * No vale buscar `style={{ … }}` a secas: la insignia de una cuenta escribía
   * `style={cond ? {…} : {…}}` —dos objetos completos dentro de un ternario— y ahí estaban
   * dos de los pares sin medir. Se recorre cada objeto literal por separado para no inventar
   * pares cruzados entre las dos ramas, que son estilos que nunca se aplican juntos.
   */
  function paresDelMarcado() {
    const pares = [];
    const vistos = new Set();
    for (const [ruta, codigo] of codigoLimpio()) {
      if (!ruta.endsWith('.jsx')) continue;
      for (const inicio of codigo.matchAll(/style=\{/g)) {
        const expresion = hastaLaLlaveQueCierra(codigo, inicio.index + 'style='.length);
        const objetos = [...expresion.matchAll(/\{/g)]
          .map((llave) => hastaLaLlaveQueCierra(expresion, llave.index));
        for (const objeto of objetos.length ? objetos : [expresion]) {
          const textos = [...objeto.matchAll(COLOR)].map((m) => m[1]);
          const fondos = [...objeto.matchAll(FONDO)].map((m) => m[1]);
          for (const texto of textos) {
            for (const fondo of fondos) {
              // Un objeto anidado se recorre dos veces —dentro del de fuera y por su
              // cuenta—, así que el mismo par aparece dos veces y se cuenta una.
              const donde = `${ruta}:${lineaDe(codigo, inicio.index)}`;
              const huella = `${donde}|${texto}|${fondo}`;
              if (vistos.has(huella)) continue;
              vistos.add(huella);
              pares.push({ texto, fondo, donde });
            }
          }
        }
      }
    }
    return pares;
  }

  /** ¿Está ese par en la tabla que se mide? */
  function declarado(texto, fondo) {
    return PARES.some((par) => {
      if (par.texto !== texto) return false;
      const fondos = Array.isArray(par.fondo) ? par.fondo : [par.fondo];
      return fondos.some((f) => (typeof f === 'string' ? f === fondo : f.sobre === fondo));
    });
  }

  it('se encuentran, y son unos cuantos', () => {
    // La guarda tiene que estar leyendo algo: con el marcado cambiado de forma, la lista
    // saldría vacía y esto pasaría sin haber comprobado ningún par. Quedan pocos porque el
    // capítulo 43 se llevó nueve de los trece a la hoja; los que quedan son los que no son
    // un aviso ni una insignia: el botón blanco de la marca y dos fondos de la barra.
    expect(paresDelMarcado().length).toBeGreaterThanOrEqual(5);
  });

  it('y sabe encontrar el par que vive en las dos ramas de un ternario', () => {
    // Era el caso de las dos insignias del panel de administración, y el que se escapó a la
    // primera versión de esta guarda: `style={{ … }}` no las veía.
    const ejemplo = `
      <span style={activo
        ? { background: 'var(--success-bg)', color: 'var(--success-text)' }
        : { background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}
      >x</span>`;
    const fondos = [...ejemplo.matchAll(FONDO)].map((m) => m[1]);
    expect(fondos).toEqual(['--success-bg', '--bg-subtle']);
  });

  it('todos están en la tabla de contraste', () => {
    const sinMedir = paresDelMarcado()
      .filter(({ texto, fondo }) => !declarado(texto, fondo))
      .map(({ texto, fondo, donde }) => `  ${donde} — ${texto} sobre ${fondo}`);
    expect(
      sinMedir,
      'Estos pares los forma un `style` del marcado y `PARES` no los mide, así que nadie '
      + 'sabe si llegan a 4.5. Añádalos a la tabla de contraste —que los medirá— o use la '
      + 'clase de la hoja que ya tiene ese par medido:\n'
      + `${sinMedir.join('\n')}`,
    ).toEqual([]);
  });
});

describe('los pares que la hoja declara en una regla', () => {
  // La otra mitad de lo mismo, y la que cierra el círculo del capítulo 43: los avisos, las
  // insignias y los chips ya no escriben su par en un `style`, lo escribe la hoja. Si la
  // tabla de contraste no midiera también los pares de la hoja, mover el color de `.chip` a
  // --text-muted volvería a dejar 4.18 sobre el panel elevado sin que nada lo dijera: el par
  // habría cambiado de sitio, no de medida.
  //
  // Aquí sí se puede deducir: una regla que pone `background` y `color` juntos declara los
  // dos colores de ese par, sin maquetar nada. Al derivarlos aparecieron dos combinaciones
  // más que nadie había medido —lo que se escribe dentro de un campo—, de las veintidós que
  // la hoja declara.
  const COLOR_CSS = /(?<!-)\bcolor:\s*var\((--[\w-]+)\)/;
  const FONDO_CSS = /background(?:-color)?:\s*var\((--[\w-]+)\)/;

  function paresDeLaHoja() {
    const pares = [];
    for (const regla of sinComentarios(HOJA).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = regla[1].trim();
      if (selector.startsWith(':root') || selector.includes('@')) continue;
      const texto = COLOR_CSS.exec(regla[2]);
      const fondo = FONDO_CSS.exec(regla[2]);
      if (texto && fondo) pares.push({ selector, texto: texto[1], fondo: fondo[1] });
    }
    return pares;
  }

  it('se encuentran, y son las reglas que visten algo', () => {
    const pares = paresDeLaHoja();
    expect(pares.length).toBeGreaterThan(15);
    expect(pares.map((p) => p.selector)).toContain('.chip');
    expect(pares.map((p) => p.selector)).toContain('.alert-warn');
  });

  it('todos están en la tabla de contraste', () => {
    const sinMedir = paresDeLaHoja()
      .filter(({ texto, fondo }) => !PARES.some((par) => {
        if (par.texto !== texto) return false;
        const fondos = Array.isArray(par.fondo) ? par.fondo : [par.fondo];
        return fondos.some((f) => (typeof f === 'string' ? f === fondo : f.sobre === fondo));
      }))
      .map(({ selector, texto, fondo }) => `  ${selector} — ${texto} sobre ${fondo}`);
    expect(
      sinMedir,
      'Estas reglas de la hoja ponen un color sobre un fondo y `PARES` no mide ese par:\n'
      + `${sinMedir.join('\n')}`,
    ).toEqual([]);
  });
});

describe('las cajas de un formulario llevan la clase de la hoja', () => {
  // El capítulo 39 midió el contorno de un control y el capítulo 40 pintó el borde rojo de
  // un campo inválido, los dos sobre `.input-field`. Once cajas de las ochenta y ocho del
  // cliente no la llevaban: ocho en el panel de administración y tres en el de la sesión,
  // con la caja escrita a mano y el borde en --border-subtle, que son los 1.12:1 que §6.4
  // punto 32 cerró. Y las ocho del alta de una cuenta son de las que el capítulo 40 marca
  // con `aria-invalid`: el lector de pantalla lo anunciaba y en la pantalla no se veía.

  /** Cada `<input|select|textarea …>`, cerrando por el `>` que no está dentro de llaves. */
  function cajas(codigo) {
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

  // Lo que no es una caja de texto: una casilla, un botón de radio, un deslizador y un
  // campo oculto no tienen contorno que medir ni valor que rechazar por campo.
  const NO_SON_CAJAS = ['checkbox', 'radio', 'hidden', 'range', 'file'];

  // La única que la hoja viste por su contenedor y no por su clase, inventariada a mano
  // porque la diferencia entre «se le olvidó» y «la hoja ya la dibuja» es esta línea.
  const VESTIDA_POR_SU_CONTENEDOR = {
    'src/components/CompartirEnRedes.jsx': 'el selector del QR, que `.interes-qr select` dibuja',
  };

  it('todas menos la que la hoja viste por su contenedor', () => {
    const desnudas = [];
    let total = 0;
    for (const [ruta, codigo] of codigoLimpio()) {
      if (!ruta.endsWith('.jsx')) continue;
      for (const { etiqueta, en } of cajas(codigo)) {
        const tipo = /type="(\w+)"/.exec(etiqueta);
        if (tipo && NO_SON_CAJAS.includes(tipo[1])) continue;
        total += 1;
        if (etiqueta.includes('input-field') || etiqueta.includes('interes-')) continue;
        if (ruta in VESTIDA_POR_SU_CONTENEDOR) continue;
        desnudas.push(`  ${ruta}:${lineaDe(codigo, en)} — ${etiqueta.slice(0, 40).replace(/\s+/g, ' ')}…`);
      }
    }
    expect(total, 'no se ha encontrado ninguna caja de formulario: el barrido falla')
      .toBeGreaterThan(50);
    expect(
      desnudas,
      'Estas cajas no llevan `.input-field`, así que no tienen el contorno medido del '
      + 'capítulo 39, ni el aro de foco, ni el borde rojo que el capítulo 40 pinta sobre '
      + '`[aria-invalid="true"]`:\n'
      + `${desnudas.join('\n')}`,
    ).toEqual([]);
  });
});

describe('el ámbar que avisa y el ámbar de un prospecto templado', () => {
  it('son dos familias, con los mismos valores', () => {
    // Mismos valores a propósito: el ámbar de esta paleta es ese y no hay otro, así que lo
    // que se separa no es el color sino la decisión de moverlo. El día que uno cambie, el
    // otro no tiene por qué.
    for (const parte of ['bg', 'border', 'text']) {
      const warm = new RegExp(`--warm-${parte}:\\s*([^;]+);`).exec(HOJA);
      const warn = new RegExp(`--warn-${parte}:\\s*([^;]+);`).exec(HOJA);
      expect(warm, `--warm-${parte} desapareció`).not.toBeNull();
      expect(warn, `--warn-${parte} desapareció`).not.toBeNull();
      expect(warn[1].trim()).toBe(warm[1].trim());
    }
  });

  it('el aviso ámbar de la hoja usa la familia del aviso', () => {
    const regla = /\.alert-warn\s*\{([\s\S]*?)\}/.exec(HOJA);
    expect(regla, 'desapareció la regla de .alert-warn').not.toBeNull();
    expect(regla[1]).toContain('var(--warn-bg)');
    expect(regla[1]).toContain('var(--warn-text)');
    expect(regla[1]).not.toContain('--warm-');
  });

  it('ninguna advertencia del marcado sigue pintada con la temperatura de una ficha', () => {
    // Los sitios que quedaron en §6.4 punto 39: el cartel de las cuentas de baja, la
    // columna de las contraseñas prestadas, el «no le quedan códigos de recuperación», el
    // enlace caducado de una publicación y la confirmación de una supresión. Los cinco
    // avisan de algo, y los cinco usaban --warm-text o --hot-text.
    const ADVIERTEN = [
      ['src/components/AdminPanel.jsx', 'must_change_password ? \'var(--warn-text)\''],
      ['src/components/LoginScreen.jsx', 'códigos de recuperación'],
      ['src/components/Publicaciones.jsx', 'alert alert-warn'],
      ['src/components/DerechosDelTitular.jsx', 'var(--warn-text)'],
      ['src/components/BandejaSinAsociar.jsx', 'alert alert-warn'],
    ];
    for (const [ruta, senal] of ADVIERTEN) {
      const codigo = readFileSync(ruta, 'utf8');
      expect(codigo, `${ruta} dejó de avisar con la familia del aviso`).toContain(senal);
    }
  });
});
