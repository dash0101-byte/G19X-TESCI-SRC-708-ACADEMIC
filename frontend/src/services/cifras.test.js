// ============================================================================
// «—» y no un cero
// ============================================================================
//
// Dos funciones de una línea con prueba propia, porque lo que vigilan no es la línea: es
// que las tres pantallas que enseñan estas cifras las lean del mismo sitio. Antes no: el
// panel de desenlaces las tenía escritas dentro, y las dos pantallas de publicaciones
// repetían la comparación a mano en cada celda —y se les quedó fuera la columna del score,
// que es la que se vio mal recorriendo la demostración.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import { NUMERO, PORCENTAJE } from './cifras.js';

describe('una cifra que puede no existir', () => {
  it('«no hay» se enseña como «—», y eso incluye el cero de verdad', () => {
    expect(NUMERO(null)).toBe('—');
    expect(NUMERO(undefined)).toBe('—');
    // Y un cero que sí existe se enseña: son dos hechos distintos y la casilla es la misma.
    expect(NUMERO(0)).toBe(0);
    expect(NUMERO(34.3)).toBe(34.3);
  });

  it('un porcentaje que no existe tampoco es un 0 %', () => {
    expect(PORCENTAJE(null)).toBe('—');
    expect(PORCENTAJE(undefined)).toBe('—');
    expect(PORCENTAJE(0)).toBe('0 %');
    expect(PORCENTAJE(25)).toBe('25 %');
  });
});

describe('quién las lee', () => {
  // La parte que importa. Si mañana una de estas pantallas vuelve a escribir la comparación
  // a mano, la columna nueva se queda fuera otra vez y nadie lo nota: el cero no falla, se
  // lee.
  const PANTALLAS = [
    'src/components/PanelDeDesenlaces.jsx',
    'src/components/InformeDePublicacion.jsx',
    'src/components/Publicaciones.jsx',
  ];

  it('las tres pantallas de cifras importan la tabla en vez de repetirla', () => {
    for (const ruta of PANTALLAS) {
      const codigo = readFileSync(ruta, 'utf8');
      expect(codigo, `${ruta} no importa services/cifras`).toMatch(
        /from '\.\.\/services\/cifras'/,
      );
      expect(
        codigo,
        `${ruta} volvió a comparar contra null a mano en una celda; use NUMERO o PORCENTAJE`,
      ).not.toMatch(/===\s*null\s*\|\|[^\n]*===\s*undefined\s*\?\s*'—'/);
    }
  });
});
