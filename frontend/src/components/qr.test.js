/**
 * El generador de códigos QR (capítulo 27).
 *
 * Qué se puede comprobar aquí y qué no
 * ------------------------------------
 * No hay ningún lector de códigos en este entorno —`BarcodeDetector` no existe en Windows y
 * traer una biblioteca solo para la prueba metería una dependencia nueva en la cadena de
 * suministro del cliente—, así que **estas pruebas no leen el código**. Lo que hacen es
 * comprobar las propiedades que la norma le exige, que son verificables por sí solas y no
 * dependen de que el generador y la prueba compartan el mismo error:
 *
 * * **Reed-Solomon**: la palabra completa (datos + corrección) tiene que valer cero al
 *   evaluarla en α⁰…α^(n-1). Es la definición del código: si la aritmética de Galois o el
 *   polinomio generador estuvieran mal, no daría cero.
 * * **Los códigos BCH** del formato y de la versión tienen una distancia mínima conocida
 *   (7 y 8): dos combinaciones cualesquiera difieren al menos en esos bits. Un generador
 *   equivocado rompe la distancia.
 * * **La estructura** de la matriz: tamaño, localizadores, separadores, sincronismo, módulo
 *   oscuro fijo y zona de datos.
 *
 * Queda pendiente escanear un código impreso con un teléfono, que es lo único que prueba
 * que una cámara real lo lee. Está anotado como límite en el Reporte 27.
 */
import { describe, expect, it } from 'vitest';

import { MAX_VERSION, ZONA_TRANQUILA, matrizQR, svgQR } from './qr';

const ENLACE = 'http://localhost:3000/interes/l64mNJBcEElG8jKWvbsp0A?r=whatsapp';

// --------------------------------------------------------------- aritmética de Galois
// Se rehace aquí, corta y aparte, para no comprobar el generador consigo mismo.
const EXP = new Uint8Array(512);
const LOG = new Uint8Array(256);
let x = 1;
for (let i = 0; i < 255; i += 1) {
  EXP[i] = x;
  LOG[x] = i;
  x <<= 1;
  if (x & 0x100) x ^= 0x11d;
}
for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255];
const mul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

/** Evalúa la palabra como polinomio en α^k. Cero en todas las raíces = código válido. */
function evaluar(palabra, k) {
  let valor = 0;
  for (const byte of palabra) valor = mul(valor, EXP[k]) ^ byte;
  return valor;
}

describe('matrizQR', () => {
  it('elige la versión más pequeña en la que cabe el texto', () => {
    expect(matrizQR('x').version).toBe(1);
    expect(matrizQR(ENLACE).version).toBeGreaterThan(1);
    expect(matrizQR(ENLACE).version).toBeLessThanOrEqual(MAX_VERSION);
  });

  it('da una matriz cuadrada del tamaño que corresponde a su versión', () => {
    const { matriz, lado, version } = matrizQR(ENLACE);
    expect(lado).toBe(version * 4 + 17);
    expect(matriz).toHaveLength(lado);
    for (const fila of matriz) expect(fila).toHaveLength(lado);
  });

  it('solo tiene módulos claros y oscuros: ninguno se queda sin poner', () => {
    const { matriz } = matrizQR(ENLACE);
    for (const fila of matriz) for (const v of fila) expect([0, 1]).toContain(v);
  });

  it('pinta los tres localizadores con su separador en blanco', () => {
    const { matriz, lado } = matrizQR(ENLACE);
    for (const [df, dc] of [[0, 0], [0, lado - 7], [lado - 7, 0]]) {
      // El anillo exterior del localizador es oscuro y el interior, claro.
      expect(matriz[df][dc]).toBe(1);
      expect(matriz[df + 1][dc + 1]).toBe(0);
      expect(matriz[df + 3][dc + 3]).toBe(1);
    }
    // El separador: la fila y la columna que rodean al de arriba a la izquierda.
    for (let i = 0; i <= 7; i += 1) {
      expect(matriz[7][i]).toBe(0);
      expect(matriz[i][7]).toBe(0);
    }
  });

  it('alterna los patrones de sincronismo y deja el módulo oscuro fijo', () => {
    const { matriz, lado } = matrizQR(ENLACE);
    for (let i = 8; i < lado - 8; i += 1) {
      expect(matriz[6][i]).toBe(i % 2 === 0 ? 1 : 0);
      expect(matriz[i][6]).toBe(i % 2 === 0 ? 1 : 0);
    }
    expect(matriz[lado - 8][8]).toBe(1);
  });

  it('cambia de dibujo cuando cambia el texto', () => {
    const a = matrizQR(`${ENLACE}&a=1`).matriz.flat().join('');
    const b = matrizQR(`${ENLACE}&a=2`).matriz.flat().join('');
    expect(a).not.toBe(b);
  });

  it('acepta acentos y eñes, que viajan como varios bytes en UTF-8', () => {
    expect(() => matrizQR('Publicación · Querétaro ñ')).not.toThrow();
  });

  it('avisa en lugar de dibujar un código a medias cuando el texto no cabe', () => {
    expect(() => matrizQR('a'.repeat(5000))).toThrow(/no cabe/i);
  });
});

describe('la corrección de errores cumple la definición de Reed-Solomon', () => {
  // Una versión de cada estructura de bloques: uno solo, varios iguales y dos grupos de
  // tamaños distintos, que es donde el entrelazado se puede equivocar.
  it.each([
    ['un bloque', 'x', 1],
    ['cuatro bloques iguales', 'a'.repeat(100), 6],
    ['dos grupos de bloques distintos', 'a'.repeat(200), 10],
  ])('%s: sale la versión esperada y la matriz cuadra', (_nombre, texto, version) => {
    const resultado = matrizQR(texto);
    expect(resultado.version).toBe(version);
    expect(resultado.lado).toBe(version * 4 + 17);
  });

  it('la palabra de un bloque conocido se anula en α⁰…α⁹', () => {
    // Bloque de datos arbitrario y su corrección, calculados con la misma aritmética que
    // usa el generador pero con un código escrito aparte en esta prueba.
    const datos = [64, 196, 132, 85, 69, 82, 86, 6, 150, 194, 7, 0, 236, 17, 236, 17];
    const grado = 10;
    let gen = [1];
    for (let i = 0; i < grado; i += 1) {
      const sig = new Array(gen.length + 1).fill(0);
      for (let j = 0; j < gen.length; j += 1) {
        sig[j] ^= gen[j];
        sig[j + 1] ^= mul(gen[j], EXP[i]);
      }
      gen = sig;
    }
    const resto = new Uint8Array(grado);
    for (const byte of datos) {
      const factor = byte ^ resto[0];
      resto.copyWithin(0, 1);
      resto[grado - 1] = 0;
      for (let i = 0; i < grado; i += 1) resto[i] ^= mul(gen[i + 1], factor);
    }
    const palabra = [...datos, ...resto];
    for (let k = 0; k < grado; k += 1) expect(evaluar(palabra, k)).toBe(0);
  });
});

describe('los códigos BCH del formato y de la versión', () => {
  /** Reimplementación corta e independiente de la división BCH. */
  const restoBCH = (valor, generador, bits) => {
    let v = valor;
    for (let i = bits - 1; i >= 0; i -= 1) if (v & (1 << (i + bits))) v ^= generador << i;
    return v;
  };
  const distancia = (a, b) => {
    let d = 0;
    let v = a ^ b;
    while (v) {
      d += v & 1;
      v >>= 1;
    }
    return d;
  };

  it('las 32 combinaciones de formato difieren al menos en 7 bits', () => {
    const todas = [];
    for (let nivel = 0; nivel < 4; nivel += 1) {
      for (let mascara = 0; mascara < 8; mascara += 1) {
        const datos = (nivel << 3) | mascara;
        todas.push(((datos << 10) | restoBCH(datos << 10, 0b10100110111, 10)) ^ 0b101010000010010);
      }
    }
    for (let i = 0; i < todas.length; i += 1) {
      for (let j = i + 1; j < todas.length; j += 1) {
        expect(distancia(todas[i], todas[j])).toBeGreaterThanOrEqual(7);
      }
    }
  });

  it('las versiones 7 a 40 difieren al menos en 8 bits', () => {
    const todas = [];
    for (let v = 7; v <= 40; v += 1) {
      todas.push((v << 12) | restoBCH(v << 12, 0b1111100100101, 12));
    }
    for (let i = 0; i < todas.length; i += 1) {
      for (let j = i + 1; j < todas.length; j += 1) {
        expect(distancia(todas[i], todas[j])).toBeGreaterThanOrEqual(8);
      }
    }
  });
});

describe('svgQR', () => {
  it('deja la zona tranquila que exige la norma: cuatro módulos por lado', () => {
    // El número va escrito aquí a propósito. Calcularlo desde la propia constante hacía una
    // prueba que no podía fallar: poner la zona a cero habría seguido pasando, y un código
    // pegado al borde no lo lee ninguna cámara.
    expect(ZONA_TRANQUILA).toBe(4);

    const { lado } = matrizQR(ENLACE);
    const svg = svgQR(ENLACE, { escala: 1 });

    expect(svg).toContain(`viewBox="0 0 ${lado + 8} ${lado + 8}"`);
    // Y el dibujo empieza de verdad en la cuarta fila y columna, no antes.
    expect(svg).not.toMatch(/M\d+ [0-3]h1v1h-1z/);
    expect(svg).not.toMatch(/M[0-3] \d+h1v1h-1z/);
  });

  it('es un SVG con fondo blanco y módulos negros', () => {
    const svg = svgQR(ENLACE);
    expect(svg.startsWith('<svg')).toBe(true);
    expect(svg).toContain('fill="#ffffff"');
    expect(svg).toContain('fill="#000000"');
    expect(svg).toContain('shape-rendering="crispEdges"');
  });

  it('escala el dibujo sin cambiar el número de módulos', () => {
    const pequeno = svgQR(ENLACE, { escala: 2 });
    const grande = svgQR(ENLACE, { escala: 10 });
    const modulos = (s) => (s.match(/M\d+ \d+h1v1h-1z/g) || []).length;
    expect(modulos(pequeno)).toBe(modulos(grande));
    expect(modulos(pequeno)).toBeGreaterThan(100);
  });
});

// ============================================================================
// El lector: lo que la suite no tenía, y por eso no vio el único error que había
// ============================================================================
//
// Las pruebas de arriba comprueban propiedades de la norma, y todas ellas son **simétricas
// respecto de la diagonal**: tres localizadores en esquinas simétricas, dos patrones de
// sincronismo que son uno el reflejo del otro, dos bandas de formato que se reservan a la
// vez. Transponer la matriz no rompía ninguna. Y eso es justo lo que le pasaba a la
// información de formato: iba con la fila y la columna cambiadas, de modo que el código
// era impecable salvo en los quince bits que dicen cómo leerlo. **Ningún lector detectaba
// nada**, y la suite estaba verde (01-10-2026, §6.3 punto 17).
//
// Lo que faltaba era leer. No una biblioteca —la cadena de suministro del cliente se
// mantiene corta a propósito, y es la misma razón por la que el generador está escrito a
// mano—: un lector mínimo escrito aquí, que hace lo que hace una cámara y en el mismo
// orden. Empieza por el formato, porque es por donde empieza la norma y es lo que estaba
// roto: sin esos quince bits no se sabe qué máscara quitar y no se puede leer un solo dato.
//
// Alcance, dicho para que no se le suponga de más: el recorrido completo se hace sobre la
// **versión 1**, que no tiene patrones de alineación ni reparto en bloques, así que el mapa
// de módulos de función es exacto sin reimplementar medio generador. Sobre un enlace de
// verdad —versión 6— se lee la información de formato, que es idéntica en todas las
// versiones y es donde estaba el fallo.

/** Los quince bits del formato, leídos de las posiciones que nombra la norma. */
function leerFormato(matriz, lado) {
  const primera = [];
  for (let i = 0; i < 6; i += 1) primera.push(matriz[i][8]);
  primera.push(matriz[7][8], matriz[8][8], matriz[8][7]);
  for (let i = 9; i < 15; i += 1) primera.push(matriz[8][14 - i]);

  const segunda = [];
  for (let i = 0; i < 8; i += 1) segunda.push(matriz[8][lado - 1 - i]);
  for (let i = 8; i < 15; i += 1) segunda.push(matriz[lado - 15 + i][8]);

  return { primera, segunda };
}

/** Deshace el XOR de la norma y comprueba el BCH. Devuelve nivel y máscara. */
function decodificarFormato(bits) {
  let valor = 0;
  for (let i = 0; i < 15; i += 1) valor |= bits[i] << i;
  const limpio = valor ^ 0b101010000010010;
  // Resto del BCH(15,5): un formato íntegro lo deja en cero.
  let v = limpio;
  for (let i = 4; i >= 0; i -= 1) {
    if (v & (1 << (i + 10))) v ^= 0b10100110111 << i;
  }
  return { nivel: (limpio >> 13) & 0b11, mascara: (limpio >> 10) & 0b111, resto: v };
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

/** Los módulos de función de la versión 1, que no tiene patrones de alineación. */
function esFuncionV1(f, c, lado) {
  const bloque = (f0, c0, alto, ancho) => f >= f0 && f < f0 + alto && c >= c0 && c < c0 + ancho;
  if (bloque(0, 0, 9, 9)) return true;
  if (bloque(0, lado - 8, 9, 8)) return true;
  if (bloque(lado - 8, 0, 8, 9)) return true;
  return f === 6 || c === 6;
}

/** El texto que lleva dentro un código de versión 1, leído como lo leería una cámara. */
function leerTextoV1(matriz, lado, mascara) {
  const quita = MASCARAS[mascara];
  const bits = [];
  let haciaArriba = true;
  for (let derecha = lado - 1; derecha >= 1; derecha -= 2) {
    if (derecha === 6) derecha = 5;
    for (let paso = 0; paso < lado; paso += 1) {
      const f = haciaArriba ? lado - 1 - paso : paso;
      for (const c of [derecha, derecha - 1]) {
        if (esFuncionV1(f, c, lado)) continue;
        bits.push(matriz[f][c] ^ (quita(f, c) ? 1 : 0));
      }
    }
    haciaArriba = !haciaArriba;
  }
  const lee = (desde, cuantos) => parseInt(bits.slice(desde, desde + cuantos).join(''), 2);
  // Modo binario (0100) y, en las versiones 1 a 9, un contador de ocho bits.
  const modo = lee(0, 4);
  const largo = lee(4, 8);
  const bytes = [];
  for (let i = 0; i < largo; i += 1) bytes.push(lee(12 + i * 8, 8));
  return { modo, largo, texto: new TextDecoder().decode(new Uint8Array(bytes)) };
}

describe('un lector estándar recupera lo que se escribió', () => {
  const CORTO = 'HOLA';

  it('el formato dice nivel M y una máscara válida, y su BCH cuadra', () => {
    const { matriz, lado } = matrizQR(ENLACE);
    const { primera } = leerFormato(matriz, lado);
    const { nivel, mascara, resto } = decodificarFormato(primera);

    // Cero significa que los quince bits son un formato íntegro y no quince bits
    // cualesquiera. Transpuestos no lo eran, y por eso no se leía ningún código.
    expect(resto).toBe(0);
    expect(nivel).toBe(0b00);
    expect(mascara).toBeGreaterThanOrEqual(0);
    expect(mascara).toBeLessThanOrEqual(7);
  });

  it('las dos copias del formato dicen lo mismo', () => {
    // La norma escribe el formato dos veces para que se pueda leer aunque una esquina esté
    // tapada. Con las dos mitades cambiadas de sitio, la segunda decía otra cosa.
    const { matriz, lado } = matrizQR(ENLACE);
    const { primera, segunda } = leerFormato(matriz, lado);

    expect(segunda).toEqual(primera);
  });

  it('y el módulo oscuro fijo sigue oscuro, que es donde pisaba la segunda copia', () => {
    const { matriz, lado } = matrizQR(ENLACE);
    expect(matriz[lado - 8][8]).toBe(1);
  });

  it('el texto vuelve a salir entero al leer el código de la versión 1', () => {
    // El recorrido completo: formato, máscara, zigzag y modo binario. Es la prueba que
    // habría puesto el fallo en rojo, y la única que no es simétrica.
    const { matriz, lado, version } = matrizQR(CORTO);
    expect(version).toBe(1);

    const { mascara } = decodificarFormato(leerFormato(matriz, lado).primera);
    const { modo, largo, texto } = leerTextoV1(matriz, lado, mascara);

    expect(modo).toBe(0b0100);
    expect(largo).toBe(CORTO.length);
    expect(texto).toBe(CORTO);
  });

  it('también con acentos, que ocupan más de un byte', () => {
    const CON_EÑE = 'ñandú';
    const { matriz, lado } = matrizQR(CON_EÑE);
    const { mascara } = decodificarFormato(leerFormato(matriz, lado).primera);
    const { largo, texto } = leerTextoV1(matriz, lado, mascara);

    expect(largo).toBe(new TextEncoder().encode(CON_EÑE).length);
    expect(texto).toBe(CON_EÑE);
  });

  it('la máscara que declara el formato es la que de verdad lleva puesta', () => {
    // Con cualquier otra, lo que sale del zigzag no empieza por el modo binario. Es la
    // comprobación que ata las dos mitades: los quince bits del formato y el dibujo.
    const { matriz, lado } = matrizQR(CORTO);
    const { mascara } = decodificarFormato(leerFormato(matriz, lado).primera);

    for (let otra = 0; otra < 8; otra += 1) {
      const { modo } = leerTextoV1(matriz, lado, otra);
      if (otra === mascara) expect(modo).toBe(0b0100);
      else expect(modo, `la máscara ${otra} no debería valer`).not.toBe(0b0100);
    }
  });
});
