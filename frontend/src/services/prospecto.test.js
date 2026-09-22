import { describe, expect, it } from 'vitest';

import { ingresosDelFormulario } from './prospecto';

describe('ingresosDelFormulario', () => {
  it.each(['', null, undefined, '0', 0, '-10', 'abc'])('%p no es una cifra: se envía null', (valor) => {
    expect(ingresosDelFormulario(valor)).toBeNull();
  });

  it('respeta una cifra declarada', () => {
    expect(ingresosDelFormulario('4500000')).toBe(4500000);
    expect(ingresosDelFormulario(250000.5)).toBe(250000.5);
  });
});
