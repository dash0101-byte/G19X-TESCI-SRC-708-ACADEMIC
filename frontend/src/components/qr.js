/**
 * Código QR del enlace de una publicación, generado aquí mismo (capítulo 27).
 *
 * Por qué escrito y no una biblioteca
 * -----------------------------------
 * Los generadores de QR que se usan de una línea son servicios: se les manda la dirección
 * y devuelven la imagen. Eso significa mandar a un tercero cada enlace de cada publicación
 * —y, si algún día el enlace lleva algo más, ese algo más—, justo lo que esta parte del
 * sistema evita. Y una dependencia nueva de npm entra en la cadena de suministro del
 * cliente, que el proyecto mantiene corta a propósito.
 *
 * Qué hace y qué no
 * -----------------
 * Modo binario (UTF-8), corrección de errores nivel M (recupera un 15 %) y versiones 1 a 10,
 * que llegan a 213 bytes: de sobra para un enlace. Un texto más largo da error en lugar de
 * un código a medias.
 *
 * No implementa los modos numérico ni alfanumérico. Comprimen más, pero un enlace con
 * minúsculas no entra en el alfanumérico, así que no se usarían nunca aquí.
 */

// ----------------------------------------------------------------- aritmética de Galois
// Reed-Solomon trabaja en GF(256) con el polinomio primitivo 0x11D, que es el que fija la
// norma del QR. Las tablas de exponentes y logaritmos evitan multiplicar bit a bit.
const EXP = new Uint8Array(512);
const LOG = new Uint8Array(256);
(() => {
  let x = 1;
  for (let i = 0; i < 255; i += 1) {
    EXP[i] = x;
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255];
})();

const mul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

/** El polinomio generador de `grado` símbolos de corrección. */
function generador(grado) {
  let poly = [1];
  for (let i = 0; i < grado; i += 1) {
    const siguiente = new Array(poly.length + 1).fill(0);
    for (let j = 0; j < poly.length; j += 1) {
      siguiente[j] ^= mul(poly[j], 1);
      siguiente[j + 1] ^= mul(poly[j], EXP[i]);
    }
    poly = siguiente;
  }
  return poly;
}

/** Los símbolos de corrección de un bloque de datos. */
function correccion(datos, grado) {
  const gen = generador(grado);
  const resto = new Uint8Array(grado);
  for (const byte of datos) {
    const factor = byte ^ resto[0];
    resto.copyWithin(0, 1);
    resto[grado - 1] = 0;
    for (let i = 0; i < grado; i += 1) resto[i] ^= mul(gen[i + 1], factor);
  }
  return resto;
}

// --------------------------------------------------------------- las tablas de la norma
// Por versión (1 a 10) y nivel M: [símbolos de corrección por bloque, bloques del grupo 1,
// datos por bloque del grupo 1, bloques del grupo 2, datos por bloque del grupo 2].
const BLOQUES_M = {
  1: [10, 1, 16, 0, 0],
  2: [16, 1, 28, 0, 0],
  3: [26, 1, 44, 0, 0],
  4: [18, 2, 32, 0, 0],
  5: [24, 2, 43, 0, 0],
  6: [16, 4, 27, 0, 0],
  7: [18, 4, 31, 0, 0],
  8: [22, 2, 38, 2, 39],
  9: [22, 3, 36, 2, 37],
  10: [26, 4, 43, 1, 44],
};

// Centros de los patrones de alineación de cada versión.
const ALINEACION = {
  1: [],
  2: [6, 18],
  3: [6, 22],
  4: [6, 26],
  5: [6, 30],
  6: [6, 34],
  7: [6, 22, 38],
  8: [6, 24, 42],
  9: [6, 26, 46],
  10: [6, 28, 50],
};

export const MAX_VERSION = 10;
const NIVEL_M = 0b00;

const datosDeLaVersion = (version) => {
  const [ecc, b1, d1, b2, d2] = BLOQUES_M[version];
  return { ecc, b1, d1, b2, d2, total: b1 * d1 + b2 * d2 };
};

// ------------------------------------------------------------------------- los bits
class Bits {
  constructor() {
    this.bits = [];
  }

  push(valor, longitud) {
    for (let i = longitud - 1; i >= 0; i -= 1) this.bits.push((valor >> i) & 1);
  }

  get length() {
    return this.bits.length;
  }
}

/**
 * La versión más pequeña en la que caben estos bytes. `null` si no cabe en ninguna.
 *
 * El contador de caracteres ocupa 8 bits hasta la versión 9 y 16 desde la 10, así que la
 * cuenta se hace versión por versión y no con una tabla de capacidades.
 */
function versionPara(bytes) {
  for (let version = 1; version <= MAX_VERSION; version += 1) {
    const { total } = datosDeLaVersion(version);
    const contador = version >= 10 ? 16 : 8;
    if (4 + contador + bytes.length * 8 <= total * 8) return version;
  }
  return null;
}

function flujoDeDatos(bytes, version) {
  const { total } = datosDeLaVersion(version);
  const bits = new Bits();
  bits.push(0b0100, 4); // modo binario
  bits.push(bytes.length, version >= 10 ? 16 : 8);
  for (const byte of bytes) bits.push(byte, 8);
  // Terminador, hasta cuatro ceros, y relleno hasta completar bytes.
  const hueco = total * 8 - bits.length;
  bits.push(0, Math.min(4, hueco));
  while (bits.length % 8 !== 0) bits.push(0, 1);
  const codigos = [];
  for (let i = 0; i < bits.length; i += 8) {
    let byte = 0;
    for (let j = 0; j < 8; j += 1) byte = (byte << 1) | bits.bits[i + j];
    codigos.push(byte);
  }
  // Los dos bytes de relleno que fija la norma, alternándose.
  const RELLENO = [0xec, 0x11];
  while (codigos.length < total) codigos.push(RELLENO[(codigos.length - bits.length / 8) % 2]);
  return codigos;
}

/** Datos y corrección, repartidos en bloques y entrelazados como manda la norma. */
function codigosFinales(bytes, version) {
  const { ecc, b1, d1, b2, d2 } = datosDeLaVersion(version);
  const datos = flujoDeDatos(bytes, version);

  const bloques = [];
  let i = 0;
  for (let b = 0; b < b1; b += 1, i += d1) bloques.push(datos.slice(i, i + d1));
  for (let b = 0; b < b2; b += 1, i += d2) bloques.push(datos.slice(i, i + d2));
  const correcciones = bloques.map((bloque) => correccion(bloque, ecc));

  const salida = [];
  const maxDatos = Math.max(d1, d2);
  for (let c = 0; c < maxDatos; c += 1) {
    for (const bloque of bloques) if (c < bloque.length) salida.push(bloque[c]);
  }
  for (let c = 0; c < ecc; c += 1) {
    for (const bloque of correcciones) salida.push(bloque[c]);
  }
  return salida;
}

// ------------------------------------------------------------------- la matriz
const FINDER = [
  [1, 1, 1, 1, 1, 1, 1],
  [1, 0, 0, 0, 0, 0, 1],
  [1, 0, 1, 1, 1, 0, 1],
  [1, 0, 1, 1, 1, 0, 1],
  [1, 0, 1, 1, 1, 0, 1],
  [1, 0, 0, 0, 0, 0, 1],
  [1, 1, 1, 1, 1, 1, 1],
];

/** Divide con el polinomio de un código BCH; se usa para el formato y para la versión. */
function resto(valor, generadorBCH, bitsDelGenerador) {
  let v = valor;
  for (let i = bitsDelGenerador - 1; i >= 0; i -= 1) {
    if (v & (1 << (i + bitsDelGenerador))) v ^= generadorBCH << i;
  }
  return v;
}

/** Los 15 bits de la información de formato: nivel de corrección y máscara. */
function bitsDeFormato(mascara) {
  const datos = (NIVEL_M << 3) | mascara;
  const bch = resto(datos << 10, 0b10100110111, 10);
  return ((datos << 10) | bch) ^ 0b101010000010010;
}

/** Los 18 bits de la información de versión. Solo existe desde la versión 7. */
function bitsDeVersion(version) {
  return (version << 12) | resto(version << 12, 0b1111100100101, 12);
}

const MASCARAS = [
  (f, c) => (f + c) % 2 === 0,
  (f) => f % 2 === 0,
  (f, c) => c % 3 === 0,
  (f, c) => (f + c) % 3 === 0,
  (f, c) => (Math.floor(f / 2) + Math.floor(c / 3)) % 2 === 0,
  (f, c) => ((f * c) % 2) + ((f * c) % 3) === 0,
  (f, c) => (((f * c) % 2) + ((f * c) % 3)) % 2 === 0,
  (f, c) => (((f + c) % 2) + ((f * c) % 3)) % 2 === 0,
];

function matrizBase(version) {
  const lado = version * 4 + 17;
  const modulos = Array.from({ length: lado }, () => new Array(lado).fill(null));
  const reservado = Array.from({ length: lado }, () => new Array(lado).fill(false));

  const poner = (fila, col, valor) => {
    modulos[fila][col] = valor;
    reservado[fila][col] = true;
  };

  // Los tres localizadores, con su separador de un módulo en blanco.
  for (const [df, dc] of [[0, 0], [0, lado - 7], [lado - 7, 0]]) {
    for (let f = -1; f <= 7; f += 1) {
      for (let c = -1; c <= 7; c += 1) {
        const fila = df + f;
        const col = dc + c;
        if (fila < 0 || col < 0 || fila >= lado || col >= lado) continue;
        const dentro = f >= 0 && f < 7 && c >= 0 && c < 7;
        poner(fila, col, dentro ? FINDER[f][c] : 0);
      }
    }
  }

  // Patrones de alineación, salvo donde chocarían con un localizador.
  const centros = ALINEACION[version];
  for (const f of centros) {
    for (const c of centros) {
      const enLocalizador =
        (f === 6 && c === 6) || (f === 6 && c === lado - 7) || (f === lado - 7 && c === 6);
      if (enLocalizador) continue;
      for (let df = -2; df <= 2; df += 1) {
        for (let dc = -2; dc <= 2; dc += 1) {
          const borde = Math.max(Math.abs(df), Math.abs(dc));
          poner(f + df, c + dc, borde === 1 ? 0 : 1);
        }
      }
    }
  }

  // Los dos patrones de sincronismo.
  for (let i = 8; i < lado - 8; i += 1) {
    poner(6, i, i % 2 === 0 ? 1 : 0);
    poner(i, 6, i % 2 === 0 ? 1 : 0);
  }

  // El módulo siempre oscuro y las dos bandas reservadas para el formato.
  poner(lado - 8, 8, 1);
  for (let i = 0; i < 9; i += 1) {
    if (!reservado[8][i]) poner(8, i, 0);
    if (!reservado[i][8]) poner(i, 8, 0);
  }
  for (let i = 0; i < 8; i += 1) {
    if (!reservado[8][lado - 1 - i]) poner(8, lado - 1 - i, 0);
    if (!reservado[lado - 1 - i][8]) poner(lado - 1 - i, 8, 0);
  }

  // La información de versión, desde la 7.
  if (version >= 7) {
    const bits = bitsDeVersion(version);
    for (let i = 0; i < 18; i += 1) {
      const bit = (bits >> i) & 1;
      poner(Math.floor(i / 3), lado - 11 + (i % 3), bit);
      poner(lado - 11 + (i % 3), Math.floor(i / 3), bit);
    }
  }

  return { modulos, reservado, lado };
}

/** Recorre la zona de datos en zigzag, de abajo a la derecha hacia arriba. */
function colocarDatos(modulos, reservado, lado, codigos) {
  let bit = 0;
  const siguiente = () => {
    const byte = codigos[bit >> 3];
    const valor = byte === undefined ? 0 : (byte >> (7 - (bit & 7))) & 1;
    bit += 1;
    return valor;
  };

  let arriba = true;
  for (let col = lado - 1; col > 0; col -= 2) {
    // La columna 6 es el sincronismo vertical: se salta entera.
    const c = col <= 6 ? col - 1 : col;
    for (let i = 0; i < lado; i += 1) {
      const fila = arriba ? lado - 1 - i : i;
      for (const cc of [c, c - 1]) {
        if (!reservado[fila][cc]) modulos[fila][cc] = siguiente();
      }
    }
    arriba = !arriba;
  }
}

function penalizacion(modulos, lado) {
  let total = 0;

  // Regla 1: rachas de cinco o más del mismo color, en filas y en columnas.
  const racha = (leer) => {
    for (let a = 0; a < lado; a += 1) {
      let previo = -1;
      let largo = 0;
      for (let b = 0; b < lado; b += 1) {
        const valor = leer(a, b);
        if (valor === previo) {
          largo += 1;
          if (largo === 5) total += 3;
          else if (largo > 5) total += 1;
        } else {
          previo = valor;
          largo = 1;
        }
      }
    }
  };
  racha((f, c) => modulos[f][c]);
  racha((c, f) => modulos[f][c]);

  // Regla 2: cada cuadrado de 2×2 del mismo color.
  for (let f = 0; f < lado - 1; f += 1) {
    for (let c = 0; c < lado - 1; c += 1) {
      const v = modulos[f][c];
      if (v === modulos[f][c + 1] && v === modulos[f + 1][c] && v === modulos[f + 1][c + 1]) {
        total += 3;
      }
    }
  }

  // Regla 3: el patrón que se confunde con un localizador.
  const PATRON = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
  const INVERSO = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1];
  const busca = (leer) => {
    for (let a = 0; a < lado; a += 1) {
      for (let b = 0; b <= lado - 11; b += 1) {
        let coincidePatron = true;
        let coincideInverso = true;
        for (let k = 0; k < 11; k += 1) {
          const valor = leer(a, b + k);
          if (valor !== PATRON[k]) coincidePatron = false;
          if (valor !== INVERSO[k]) coincideInverso = false;
        }
        if (coincidePatron) total += 40;
        if (coincideInverso) total += 40;
      }
    }
  };
  busca((f, c) => modulos[f][c]);
  busca((c, f) => modulos[f][c]);

  // Regla 4: lo lejos que queda del 50 % de módulos oscuros.
  let oscuros = 0;
  for (let f = 0; f < lado; f += 1) for (let c = 0; c < lado; c += 1) oscuros += modulos[f][c];
  const porcentaje = (oscuros * 100) / (lado * lado);
  total += Math.floor(Math.abs(porcentaje - 50) / 5) * 10;
  return total;
}

/**
 * La matriz del código QR de `texto`: `matriz[fila][columna]` vale 1 (oscuro) o 0 (claro).
 *
 * Sin zona tranquila: la añade quien dibuja, porque depende del soporte.
 */
export function matrizQR(texto) {
  const bytes = new TextEncoder().encode(String(texto ?? ''));
  const version = versionPara(bytes);
  if (version === null) {
    throw new Error(`El texto no cabe en un código QR de hasta ${MAX_VERSION} versiones.`);
  }
  const codigos = codigosFinales(bytes, version);

  let mejor = null;
  for (let mascara = 0; mascara < 8; mascara += 1) {
    const { modulos, reservado, lado } = matrizBase(version);
    colocarDatos(modulos, reservado, lado, codigos);
    // Los localizadores, el sincronismo y la versión no se enmascaran; los datos sí.
    for (let f = 0; f < lado; f += 1) {
      for (let c = 0; c < lado; c += 1) {
        if (!reservado[f][c] && MASCARAS[mascara](f, c)) modulos[f][c] ^= 1;
      }
    }
    const formato = bitsDeFormato(mascara);
    for (let i = 0; i < 15; i += 1) {
      const bit = (formato >> i) & 1;
      // Copia junto al localizador superior izquierdo…
      if (i < 6) modulos[8][i] = bit;
      else if (i === 6) modulos[8][7] = bit;
      else if (i === 7) modulos[8][8] = bit;
      else if (i === 8) modulos[7][8] = bit;
      else modulos[14 - i][8] = bit;
      // …y la segunda copia, repartida entre los otros dos.
      if (i < 8) modulos[lado - 1 - i][8] = bit;
      else modulos[8][lado - 15 + i] = bit;
    }
    const puntos = penalizacion(modulos, lado);
    if (mejor === null || puntos < mejor.puntos) mejor = { puntos, modulos, lado, version };
  }
  return { matriz: mejor.modulos, lado: mejor.lado, version: mejor.version };
}

export const ZONA_TRANQUILA = 4;

/**
 * El código QR como SVG, listo para descargar o para pintar.
 *
 * Un solo `path` con un cuadrado por módulo oscuro: un `rect` por módulo daría un archivo
 * varias veces mayor para el mismo dibujo. `shape-rendering="crispEdges"` evita que el
 * navegador suavice los bordes y desdibuje los módulos al imprimir.
 */
export function svgQR(texto, { escala = 8, margen = ZONA_TRANQUILA } = {}) {
  const { matriz, lado } = matrizQR(texto);
  const total = lado + margen * 2;
  let trazo = '';
  for (let f = 0; f < lado; f += 1) {
    for (let c = 0; c < lado; c += 1) {
      if (matriz[f][c]) trazo += `M${c + margen} ${f + margen}h1v1h-1z`;
    }
  }
  const tamano = total * escala;
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${tamano}" height="${tamano}"`,
    ` viewBox="0 0 ${total} ${total}" shape-rendering="crispEdges">`,
    `<rect width="${total}" height="${total}" fill="#ffffff"/>`,
    `<path d="${trazo}" fill="#000000"/>`,
    '</svg>',
  ].join('');
}
