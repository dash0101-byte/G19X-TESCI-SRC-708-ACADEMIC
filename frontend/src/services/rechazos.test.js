// ============================================================================
// Cómo se lee un rechazo del servidor cuando no va debajo de ningún campo
// ============================================================================
//
// `textoDelRenglon` es la mitad de la traducción que `api.js` no tenía. La otra —la que
// reparte cada renglón debajo de su campo— vive en `components/erroresDeFormulario.js` y la
// prueba su propio archivo; aquí se comprueba la que ven **todas las demás pantallas**, que
// son las que enseñaban inglés.
//
// Los renglones son los que manda el servidor, con su `type`, su `loc`, su `msg` y su `ctx`.
// Es la condición que el capítulo 45 añadió a este repositorio después de encontrarse con lo
// contrario: dos pruebas de `api.test.js` llevaban renglones sin `type` —el único campo por el
// que se puede saber qué clase de error es— y esperaban el texto en inglés como resultado
// correcto. Pasaban en verde documentando el defecto.

import { describe, expect, it } from 'vitest';

import { POR_TIPO, TIPOS_PROPIOS, textoDelRenglon } from './rechazos';

describe('el texto de un renglón del 422 para un aviso general', () => {
  it('un tipo de la tabla se dice en castellano, y no se enseña el inglés', () => {
    expect(textoDelRenglon({ type: 'missing', loc: ['body', 'x'], msg: 'Field required' }))
      .toBe('Falta este campo.');
  });

  it('la lista de un enum no sale: catorce claves en inglés no son una opción que elegir', () => {
    const texto = textoDelRenglon({
      type: 'enum',
      loc: ['body', 'activity_type'],
      msg: "Input should be 'PAGE_VIEW', 'FORM_SUBMIT', 'EMAIL_OPEN' or 'CUSTOM'",
      ctx: { expected: "'PAGE_VIEW', 'FORM_SUBMIT', 'EMAIL_OPEN' or 'CUSTOM'" },
    });
    expect(texto).toBe('Elija una de las opciones de la lista.');
    expect(texto).not.toMatch(/PAGE_VIEW/);
  });

  it('el mensaje que escribió este repositorio se conserva: dice más que la tabla', () => {
    expect(textoDelRenglon({
      type: 'value_error',
      loc: ['body'],
      msg: 'Value error, La reunión tiene que ser en el futuro; una pasada no se recuerda.',
    })).toBe('La reunión tiene que ser en el futuro; una pasada no se recuerda.');
  });

  it('un tipo propio sin prefijo también conserva su frase, que es la larga', () => {
    // La tabla tiene para este tipo «No puede quedar vacío», que debajo de un campo dice
    // lo que hay que saber y en un aviso de arriba no dice de qué habla. Las dos frases son
    // correctas, y ponerlas al revés es el único modo de equivocarse aquí.
    const largo = 'La ficha no existe sin alguno de los campos que llegaron vacíos. '
      + 'Envíe un valor, o no envíe el campo si no quiere cambiarlo.';
    expect(textoDelRenglon({
      type: 'campos_vacios_prohibidos',
      loc: ['body'],
      msg: largo,
      ctx: { campos: ['first_name', 'last_name'] },
    })).toBe(largo);
    expect(POR_TIPO.campos_vacios_prohibidos({})).toBe('No puede quedar vacío.');
  });

  it('cada tipo propio está en la tabla y en la lista: las dos mitades se necesitan', () => {
    // Si un tipo propio se quedara fuera de `POR_TIPO`, el reparto por campos lo enseñaría
    // con la frase larga debajo de un campo; si se quedara fuera de `TIPOS_PROPIOS`, el aviso
    // de arriba enseñaría la corta. Las dos listas tienen que nombrarlo.
    expect(TIPOS_PROPIOS.length).toBeGreaterThan(0);
    for (const tipo of TIPOS_PROPIOS) {
      expect(POR_TIPO[tipo], `${tipo} no está en la tabla`).toBeTypeOf('function');
    }
  });

  it('un tipo que no está en la tabla no se enseña en inglés, aunque se pierda el detalle', () => {
    // Es la decisión del capítulo 40 aplicada al aviso de arriba: un mensaje que no se
    // entiende no es mejor que uno vago. Lo que impide que este hueco se llene en silencio
    // está en el servidor —`tests/test_lo_que_el_cliente_sabe_decir_de_un_rechazo.py` saca de
    // los esquemas los tipos que las puertas pueden contestar y exige que la tabla los cubra—,
    // porque la lista de tipos la decide quien los manda.
    const texto = textoDelRenglon({
      type: 'un_tipo_que_pydantic_todavia_no_tenia',
      loc: ['body', 'x'],
      msg: 'Input should be something nobody translated',
    });
    expect(texto).toBe('No se admite este valor.');
    expect(texto).not.toMatch(/Input should/);
  });

  it('un renglón sin nada tampoco deja el aviso vacío', () => {
    expect(textoDelRenglon({})).toBe('No se admite este valor.');
    expect(textoDelRenglon(null)).toBe('No se admite este valor.');
  });

  it('un ctx que no trae lo que su tipo promete no deja la pantalla sin aviso', () => {
    // `greater_than_equal` lee `ctx.ge`. Sin `ctx` la plantilla reventaría, y lo que
    // reventaría es el aviso del error, no el error.
    expect(textoDelRenglon({ type: 'greater_than_equal', loc: ['body', 'x'], msg: 'x' }))
      .toBe('No se admite este valor.');
  });
});

describe('la tabla entera, también desde este lado', () => {
  const CONTEXTO = {
    string_too_short: { min_length: 2 },
    string_too_long: { max_length: 2800 },
    greater_than_equal: { ge: 1 },
    less_than_equal: { le: 1000 },
  };

  it('ninguna de las veinticinco entradas contesta en inglés ni deja un hueco', () => {
    const tipos = Object.keys(POR_TIPO);
    // Si la tabla se vaciara, el bucle no comprobaría nada y pasaría. Son 25 desde el
    // capítulo 45: las 15 del 40, las siete de la familia `*_type`, las dos de las fechas que
    // faltaban —una por cada dirección de la conversión— y la de los campos vacíos.
    expect(tipos.length).toBe(25);

    for (const tipo of tipos) {
      const texto = POR_TIPO[tipo]({ type: tipo, ctx: CONTEXTO[tipo] });
      expect(texto, `${tipo} no dice nada`).toBeTruthy();
      expect(texto, `${tipo} no acaba la frase`).toMatch(/\.$/);
      expect(texto, `${tipo} dejó un hueco`).not.toMatch(/undefined|\[object|null/);
      // Ninguna frase de esta tabla nombra un campo: lo nombra el sitio donde sale.
      expect(texto, `${tipo} nombra una columna`).not.toMatch(/[a-z]+_[a-z]+/);
    }
  });
});
