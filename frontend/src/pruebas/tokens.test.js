// ============================================================================
// Todo token que el marcado pide, la paleta lo define
// ============================================================================
//
// De dónde sale esta comprobación
// --------------------------------
// Del capítulo 36, que al escribir `clases.test.js` encontró tres pantallas de credenciales
// pidiendo una clase llamada `input` que no existía. La conclusión de entonces fue que un
// nombre mal escrito en el marcado no rompe nada: no hay error en la consola, no falla
// ninguna prueba, el componente se monta, y la pantalla solo se ve distinta.
//
// Lo que ese capítulo no hizo fue sacar la misma conclusión para la **otra** cosa que el
// marcado nombra sin que nadie compruebe que existe: las variables de la paleta. Anotó un
// caso suelto en §6.4 —`var(--accent-primary)` no existe— y lo llamó «cosmético, y en un
// elemento que dura lo que una petición». Eran cinco tokens en nueve sitios, y dos de ellos
// no eran cosméticos:
//
// * `--hot-gradient`, `--warm-gradient` y `--cold-gradient` son el **único** fondo de los
//   tres segmentos de la barra apilada del tablero. La barra se dibujaba vacía: el gráfico
//   que dice cómo se reparte la cartera no pintaba nada.
// * `--accent-primary` es el borde y el halo de la **opción elegida** en la ficha 360. Lo
//   elegido se quedaba sin contorno, y lo elegido y lo no elegido pasaban a distinguirse
//   solo por dos fondos oscuros casi iguales.
//
// Por qué un `var()` inválido es peor que un nombre de clase mal escrito
// ----------------------------------------------------------------------
// Una clase que no existe deja al elemento con el estilo por omisión del navegador, que es
// feo pero visible. Un `var()` que no resuelve hace algo distinto y menos intuitivo: la
// declaración entera pasa a ser **inválida en el momento de calcular el valor**, y no se
// cae al valor anterior sino al inicial. `background: var(--hot-gradient)` no deja el fondo
// que tuviera: lo deja en `transparent`. `borderTop: '4px solid var(--accent-primary)'` no
// deja un borde de otro color: deja `border-top-style: none`, es decir, ningún borde.
//
// Lo que esta comprobación hace, y lo que no
// -------------------------------------------
// Saca la lista **del código**, igual que `clases.test.js` saca las clases, en vez de
// escribirla a mano. Un token nuevo sin definir nace en rojo.
//
// No comprueba que el color elegido sea el correcto —eso es `contraste.test.js`— ni que el
// token se use donde tiene sentido. Comprueba que lo que el marcado nombra existe.

import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { matrizQR } from '../components/qr';
import { HOJA, resolverAlias, variablesDe } from './contraste.js';

/** Los archivos del cliente que pueden nombrar un token, sin las pruebas. */
function fuentes(directorio) {
  const encontrados = [];
  for (const entrada of readdirSync(directorio)) {
    const ruta = join(directorio, entrada);
    if (statSync(ruta).isDirectory()) encontrados.push(...fuentes(ruta));
    else if (/\.(jsx|js|css)$/.test(ruta) && !ruta.includes('.test.')) encontrados.push(ruta);
  }
  return encontrados;
}

/**
 * Se quitan los comentarios antes de buscar.
 *
 * Es la lección del capítulo 37 aplicada aquí: una guarda que busca un texto en un archivo
 * se satisface con su propia documentación. Este archivo nombra `var(--accent-primary)` en
 * su cabecera para explicar de dónde viene, y la cabecera no es código.
 *
 * Las de línea se quitan solo cuando empiezan la línea: `//` en medio de una es casi
 * siempre el de un `https://`.
 */
function sinComentarios(codigo) {
  return codigo.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

/**
 * Los `var(--x)` de un archivo, separados por si llevan respaldo escrito.
 *
 * `var(--bg-panel, transparent)` **no es un defecto**: alguien decidió qué pasa si el token
 * no está, lo escribió, y el elemento se dibuja. Un `var(--bg-panel)` a secas es otra cosa:
 * es una promesa que nadie cumplió. La diferencia es una coma, y es toda la diferencia.
 */
function tokensPedidos(codigo) {
  const sinRespaldo = new Map();
  const conRespaldo = new Map();
  const limpio = sinComentarios(codigo);
  for (const coincidencia of limpio.matchAll(/var\(\s*(--[\w-]+)\s*([,)])/g)) {
    const donde = limpio.slice(0, coincidencia.index).split('\n').length;
    const destino = coincidencia[2] === ',' ? conRespaldo : sinRespaldo;
    if (!destino.has(coincidencia[1])) destino.set(coincidencia[1], donde);
  }
  return { sinRespaldo, conRespaldo };
}

/**
 * Los `var(--x)` con respaldo que la paleta no define, aceptados a sabiendas.
 *
 * Un solo caso, y se inventaría en vez de dejarlo implícito: la diferencia entre «hay un
 * respaldo escrito» y «hay un respaldo escrito y alguien lo miró» es esta lista.
 */
const CON_RESPALDO_ACEPTADO = {
  '--bg-panel': 'AdminPanel — la tarjeta no quiere fondo propio y lo dice: var(--bg-panel, transparent)',
};

describe('los tokens que el marcado pide', () => {
  const definidos = new Set(Object.keys(variablesDe(HOJA)));
  const archivos = fuentes('src');

  it('se leen de verdad la paleta y los archivos', () => {
    // Sin esto, una ruta mal resuelta dejaría las dos listas vacías y la comprobación de
    // abajo pasaría sin haber mirado nada. Es el mismo cuidado que en `clases.test.js` y
    // en `contraste.js`, y por el mismo motivo: la peor prueba no es la que falla, es la
    // que se aprueba a sí misma quedándose sin datos.
    expect(definidos.size).toBeGreaterThan(40);
    expect(archivos.length).toBeGreaterThan(30);
    expect(archivos.some((r) => r.endsWith('index.css'))).toBe(true);
    expect(definidos.has('--bg-surface')).toBe(true);
    expect(definidos.has('--no-existe-este-token')).toBe(false);
  });

  it('ninguno se queda sin definir', () => {
    const huerfanos = [];
    for (const ruta of archivos) {
      for (const [token, linea] of tokensPedidos(readFileSync(ruta, 'utf8')).sinRespaldo) {
        if (definidos.has(token)) continue;
        huerfanos.push(`  ${ruta}:${linea} — var(${token})`);
      }
    }
    expect(
      huerfanos,
      'Estos tokens se piden sin respaldo y la paleta no los define, así que la declaración '
      + 'entera es inválida y la propiedad se cae al valor INICIAL —no al anterior—:\n'
      + `${huerfanos.join('\n')}\n`
      + 'Si el token existe con otro nombre, defina un alias en :root. Si hace falta un '
      + 'color nuevo, escríbalo en la paleta y páselo por contraste.test.js. Si el elemento '
      + 'puede vivir sin él, escriba el respaldo: var(--x, lo-que-sea).',
    ).toEqual([]);
  });

  it('los que llevan respaldo están inventariados, uno por uno', () => {
    // El respaldo es una salida legítima y por eso hay que vigilarla: si no se mirara,
    // bastaría con añadir una coma para silenciar la comprobación de arriba.
    const sinInventariar = [];
    for (const ruta of archivos) {
      for (const [token, linea] of tokensPedidos(readFileSync(ruta, 'utf8')).conRespaldo) {
        if (definidos.has(token) || token in CON_RESPALDO_ACEPTADO) continue;
        sinInventariar.push(`  ${ruta}:${linea} — var(${token}, …)`);
      }
    }
    expect(
      sinInventariar,
      'Estos tokens no están en la paleta y se usan con respaldo. El respaldo vale, pero '
      + 'hay que decir que es a propósito:\n'
      + `${sinInventariar.join('\n')}`,
    ).toEqual([]);
  });

  it('el inventario no guarda tokens que ya están en la paleta', () => {
    const sobrantes = Object.keys(CON_RESPALDO_ACEPTADO).filter((t) => definidos.has(t));
    expect(
      sobrantes,
      `Estos ya están en :root: quítelos de CON_RESPALDO_ACEPTADO — ${sobrantes.join(', ')}`,
    ).toEqual([]);
  });
});

describe('los cinco que faltaban', () => {
  const variables = variablesDe(HOJA);

  it('existen, y los dos que son color resuelven a un color', () => {
    // Los alias se siguen hasta el final: un token que apunte a otro que no existe es
    // exactamente el mismo defecto con un salto de más.
    for (const token of ['--accent-primary', '--color-primary-light']) {
      expect(variables[token], `${token} volvió a desaparecer de la paleta`).toBeDefined();
      expect(resolverAlias(variables[token], variables)).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it('los tres degradados pintan algo, y del color de su cuadrante', () => {
    // La barra se dibujaba vacía. Que el token exista no basta: tiene que ser un fondo de
    // verdad, y del color que la leyenda de justo debajo dice que es. La muestra de la
    // leyenda usa `--hot-text`, `--warm-text` y `--cold-text`; si el degradado no los
    // llevara, la leyenda estaría nombrando un color que el segmento no tiene.
    for (const familia of ['hot', 'warm', 'cold']) {
      const valor = variables[`--${familia}-gradient`];
      expect(valor, `--${familia}-gradient no está en la paleta`).toBeDefined();
      expect(valor).toMatch(/^linear-gradient\(/);
      expect(valor).toContain(`var(--${familia}-dot)`);
      expect(valor).toContain(`var(--${familia}-text)`);
    }
  });

  it('el gráfico del tablero sigue pidiéndolos, y los tres', () => {
    // Si alguien quitara la barra, estos tokens pasarían a ser tres degradados que no
    // pinta nadie y habría que retirarlos. Esta prueba ata el token a su uso.
    const codigo = readFileSync('src/components/AnalyticsCharts.jsx', 'utf8');
    for (const familia of ['hot', 'warm', 'cold']) {
      expect(codigo).toContain(`var(--${familia}-gradient)`);
    }
  });

  it('la opción elegida de la ficha 360 vuelve a tener contorno', () => {
    // El caso concreto del punto 33: con `--accent-primary` sin definir, el `border` de la
    // opción elegida era inválido y se caía a `border-style: none`. No quedaba ni un borde
    // de otro color: no quedaba borde.
    const codigo = readFileSync('src/components/LeadDetailModal.jsx', 'utf8');
    expect(codigo).toContain('var(--accent-primary)');
    expect(variables['--accent-primary']).toBeDefined();
  });
});

describe('el estado apagado de un botón', () => {
  it('la hoja lo dibuja', () => {
    // No había ni un `:disabled` en toda la hoja y quince componentes deshabilitan
    // botones. Con el relleno sólido de `.btn-danger`, «Suprimir definitivamente» apagado
    // se habría visto igual que encendido: la pantalla diciendo algo que no es verdad.
    expect(HOJA).toMatch(/\.btn:disabled/);
    expect(HOJA).toMatch(/cursor:\s*not-allowed/);
  });

  it('y no lo hace con opacidad, que atenúa un texto que nadie mide', () => {
    const regla = /\.btn:disabled[\s\S]*?\{([\s\S]*?)\}/.exec(HOJA);
    expect(regla, 'desapareció la regla de .btn:disabled').not.toBeNull();
    expect(regla[1]).not.toMatch(/opacity/);
    // El par que usa está en la tabla de contraste y da 4.63:1.
    expect(regla[1]).toContain('var(--text-muted)');
  });
});

describe('el tamaño del código QR', () => {
  // Punto 3 del capítulo 39: que se escanee desde un teléfono a la distancia a la que se
  // mira un papel, medido y no a ojo. La unidad es **píxeles CSS por módulo**, y el suelo
  // son 5. Por debajo, la cámara empieza a no resolver los módulos.
  const SUELO = 5;

  /** El `min-width` de la regla del dibujo, en píxeles. */
  function sueloDeclarado() {
    const regla = /\.interes-qr-dibujo svg\s*\{([\s\S]*?)\}/.exec(HOJA);
    expect(regla, 'desapareció la regla que fija el tamaño del código').not.toBeNull();
    const ancho = /min-width:\s*min\((\d+)px,\s*100%\)/.exec(regla[1]);
    expect(
      ancho,
      'el suelo tiene que seguir escrito como min(Npx, 100%): rígido sacaría una barra '
      + 'horizontal a la página entera por debajo de 290 px de ventana (§1.4.10)',
    ).not.toBeNull();
    return Number(ancho[1]);
  }

  it('el enlace público más largo que este panel produce cabe con 5 píxeles por módulo', () => {
    // Los módulos no se escriben aquí: se calculan con el mismo generador que dibuja el
    // código. Un comentario que diga «son 49» caduca el día que el enlace crezca; esto no.
    const enlace = `https://${'p'.repeat(40)}.trycloudflare.com/i/l64mNJBcEElG8jKWvbsp0A?r=whatsapp`;
    expect(enlace.length).toBeGreaterThanOrEqual(100);
    const { lado } = matrizQR(enlace);
    const modulos = lado + 8; // los 4 de zona tranquila a cada lado
    const porModulo = sueloDeclarado() / modulos;
    expect(
      porModulo,
      `un enlace de ${enlace.length} caracteres da ${modulos} módulos con la zona tranquila, `
      + `y el suelo de ${sueloDeclarado()} px solo deja ${porModulo.toFixed(2)} px por módulo`,
    ).toBeGreaterThanOrEqual(SUELO);
  });

  it('el dibujo escala con el sitio que tiene, en vez de quedarse en su tamaño nativo', () => {
    // Sin la hoja, el SVG salía al tamaño que `svgQR` le pone en `width`: 4 px por módulo
    // y nada más, porque no había ninguna regla que lo tocara.
    const regla = /\.interes-qr-dibujo svg\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(regla).toMatch(/width:\s*100%/);
    expect(regla).toMatch(/height:\s*auto/);
    expect(regla).toMatch(/max-width:\s*\d+px/);
  });

  it('el código sigue sobre blanco y con su margen', () => {
    // La zona tranquila la trae el SVG; el relleno blanco de alrededor es para que el
    // borde del panel no haga de quinto patrón de localización.
    const regla = /\.interes-qr-dibujo\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(regla).toMatch(/background:\s*#ffffff/);
    expect(regla).toMatch(/padding:\s*\d+px/);
  });
});
