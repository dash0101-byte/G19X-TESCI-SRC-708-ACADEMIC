// ============================================================================
// El 422 repartido: qué se dice de cada campo, y en qué idioma
// ============================================================================
//
// Las pruebas de este archivo parten de renglones de 422 **copiados de los de verdad**, con
// su `type`, su `loc`, su `msg` y su `ctx` tal como los manda el servidor. Es deliberado:
// el valor de esta traducción está en que acierte con lo que Pydantic manda de verdad, y
// un renglón inventado a conveniencia comprobaría que la función hace lo que la función
// hace.
//
// Se obtuvieron ejecutando los esquemas del backend contra datos malos:
//
//     LeadCreate(email="no-es-correo", phone="123", last_name="X")
//
// que devuelve exactamente los tres primeros casos de abajo.

import { describe, expect, it, vi } from 'vitest';

import {
  POR_TIPO,
  comoAviso,
  enfocarPrimerCampoConError,
  erroresDelServidor,
  idDelMensaje,
  mensajeDelRenglon,
  propiedadesDeCampo,
  resumenDeCampos,
  sinElCampo,
} from './erroresDeFormulario';

// Los tres renglones del 422 real, literales.
const FALTA_EL_NOMBRE = {
  type: 'missing',
  loc: ['body', 'first_name'],
  msg: 'Field required',
};
const CORREO_INVALIDO = {
  type: 'value_error',
  loc: ['body', 'email'],
  msg: 'value is not a valid email address: An email address must have an @-sign.',
  ctx: { reason: 'An email address must have an @-sign.' },
};
const TELEFONO_INVALIDO = {
  type: 'value_error',
  loc: ['body', 'phone'],
  msg: 'Value error, El teléfono no es un número válido: revise la lada y el número de dígitos.',
  ctx: { error: 'El teléfono no es un número válido: revise la lada y el número de dígitos.' },
};

describe('qué se dice de un renglón del 422', () => {
  it('un campo que falta se dice en castellano, no «Field required»', () => {
    expect(mensajeDelRenglon(FALTA_EL_NOMBRE)).toBe('Falta este campo.');
  });

  it('el mensaje que escribió este repositorio se conserva, sin el ruido de Pydantic', () => {
    // «Value error, » es el nombre interno de su excepción. Lo que viene detrás lo escribió
    // alguien de aquí, en castellano y para leerse: ya explica qué forma se espera.
    expect(mensajeDelRenglon(TELEFONO_INVALIDO)).toBe(
      'El teléfono no es un número válido: revise la lada y el número de dígitos.',
    );
  });

  it('el de una biblioteca no se enseña en inglés', () => {
    // El validador de correos no es nuestro y contesta en inglés. Sin frase propia se dice
    // algo vago pero legible; lo que no puede pasar es que la pantalla enseñe «value is not
    // a valid email address: An email address must have an @-sign».
    const sinFrasePropia = mensajeDelRenglon(CORREO_INVALIDO);
    expect(sinFrasePropia).toBe('No se admite este valor.');
    expect(sinFrasePropia).not.toMatch(/email address/);

    const conFrasePropia = mensajeDelRenglon(CORREO_INVALIDO, {
      email: 'Escriba un correo con la forma nombre@empresa.com.',
    });
    expect(conFrasePropia).toBe('Escriba un correo con la forma nombre@empresa.com.');
  });

  it('la frase de la pantalla gana a la del servidor', () => {
    // Las del formulario están escritas para quien lo rellena. Esta prueba fija el orden:
    // si se invirtiera, la página pública volvería a decir «Field required» donde hoy dice
    // «Escribe tu nombre».
    expect(mensajeDelRenglon(FALTA_EL_NOMBRE, { first_name: 'Escribe tu nombre.' }))
      .toBe('Escribe tu nombre.');
  });

  it('un tipo con contexto dice el número que el contexto trae', () => {
    expect(mensajeDelRenglon({
      type: 'string_too_short',
      loc: ['body', 'full_name'],
      msg: 'String should have at least 2 characters',
      ctx: { min_length: 2 },
    })).toBe('Tiene que tener al menos 2 caracteres.');
  });

  it('un tipo con contexto incompleto no tumba el formulario', () => {
    // Un `ctx` que no trae lo que su tipo promete es un error del servidor, no de quien
    // rellena el formulario. El objetivo era explicar un error, no provocar otro.
    expect(mensajeDelRenglon({ type: 'greater_than_equal', loc: ['body', 'capacity'], msg: 'x' }))
      .toBe('No se admite este valor.');
  });

  it('un tipo que nunca se ha visto tampoco se enseña en inglés', () => {
    expect(mensajeDelRenglon({
      type: 'un_tipo_que_pydantic_inventara_mañana',
      loc: ['body', 'x'],
      msg: 'Something went sideways',
    })).toBe('No se admite este valor.');
  });
});

describe('el reparto por campos', () => {
  it('cada queja va a su campo, por el último tramo de loc', () => {
    const { porCampo } = erroresDelServidor([FALTA_EL_NOMBRE, TELEFONO_INVALIDO]);
    expect(Object.keys(porCampo)).toEqual(['first_name', 'phone']);
    expect(porCampo.first_name).toBe('Falta este campo.');
  });

  it('lo que la pantalla no pinta no se pierde: se dice aparte', () => {
    // Es la diferencia entre repartir y perder. Un error de un campo que no está en la
    // pantalla no se puede señalar en la pantalla, pero tampoco puede desaparecer: quien
    // rellena el formulario se quedaría con un botón que no hace nada y sin explicación.
    const { porCampo, sueltos } = erroresDelServidor(
      [FALTA_EL_NOMBRE, { type: 'missing', loc: ['body', 'raw_metadata'], msg: 'Field required' }],
      { campos: ['first_name'] },
    );
    expect(Object.keys(porCampo)).toEqual(['first_name']);
    expect(sueltos).toEqual(['Falta este campo.']);
  });

  it('el nombre que viaja se traduce al que la pantalla usa', () => {
    const { porCampo } = erroresDelServidor(
      [{ type: 'missing', loc: ['body', 'end_date'], msg: 'Field required' }],
      { campos: ['fecha_de_cierre'], renombres: { end_date: 'fecha_de_cierre' } },
    );
    expect(porCampo).toEqual({ fecha_de_cierre: 'Falta este campo.' });
  });

  it('dos quejas del mismo campo caben en un renglón: manda la primera', () => {
    const { porCampo } = erroresDelServidor([
      FALTA_EL_NOMBRE,
      { type: 'string_too_short', loc: ['body', 'first_name'], msg: 'x', ctx: { min_length: 2 } },
    ]);
    expect(porCampo.first_name).toBe('Falta este campo.');
  });

  it('el 422 de una clave ajena del capítulo 42 llega entero, en castellano', () => {
    // El renglón, literal, tal como lo manda `app.core.integridad`. Ese módulo no imita un
    // error de validación: construye el mismo que Pydantic daría si un validador pudiera
    // preguntar a la base. Copiarlo aquí tal cual es lo que ata las dos mitades del
    // contrato: si el servidor dejara de poner el prefijo, esta prueba diría «No se admite
    // este valor» y el motivo —que explica qué pasó— se habría perdido por el camino.
    const CLAVE_SIN_DESTINO = {
      type: 'value_error',
      loc: ['body', 'assigned_rep_id'],
      msg: 'Value error, No existe ninguna cuenta con ese identificador.',
      ctx: { error: 'No existe ninguna cuenta con ese identificador.' },
    };
    expect(mensajeDelRenglon(CLAVE_SIN_DESTINO))
      .toBe('No existe ninguna cuenta con ese identificador.');

    // Y en la edición de una ficha, que no pinta ese campo, va al aviso de arriba con el
    // mensaje completo: ni se pierde ni enseña el nombre de la columna.
    const { porCampo, sueltos } = erroresDelServidor([CLAVE_SIN_DESTINO], {
      campos: ['first_name', 'last_name', 'email'],
    });
    expect(porCampo).toEqual({});
    expect(sueltos).toEqual(['No existe ninguna cuenta con ese identificador.']);
  });

  it('un detalle que no es una lista no se interpreta', () => {
    // Un 409 o un 500 traen otra cosa —una cadena, un objeto con `mensaje`—, y el
    // formulario tiene que caer al aviso general en vez de inventarse campos.
    expect(erroresDelServidor('El correo ya existe')).toBeNull();
    expect(erroresDelServidor(undefined)).toBeNull();
    expect(erroresDelServidor([])).toBeNull();
  });
});

describe('lo que se le cuelga al campo', () => {
  const errores = { email: 'Falta este campo.' };

  it('marca el campo y lo ata a su mensaje', () => {
    expect(propiedadesDeCampo('email', errores, 'alta')).toEqual({
      'data-campo': 'email',
      'aria-invalid': 'true',
      'aria-describedby': 'alta-email-error',
    });
  });

  it('un campo correcto no lleva marca ninguna', () => {
    const limpio = propiedadesDeCampo('phone', errores, 'alta');
    expect(limpio['aria-invalid']).toBeUndefined();
    expect(limpio['aria-describedby']).toBeUndefined();
  });

  it('el mensaje de error no se come la ayuda que el campo ya tenía', () => {
    // `aria-describedby` admite una lista de `id`. Sustituirlo en vez de añadir dejaba al
    // campo del texto de la publicación sin su «quedan 940 caracteres» justo cuando el
    // servidor acaba de decir que el texto no vale, que es cuando más falta hace. El
    // atributo sigue siendo válido con un solo `id`, así que esto no se nota mirando.
    const conAyuda = propiedadesDeCampo('description', { description: 'No vale.' }, 'publicacion', 'publicacion-descripcion-restantes');
    expect(conAyuda['aria-describedby'])
      .toBe('publicacion-descripcion-restantes publicacion-description-error');

    // Y sin error se queda solo la ayuda, que es lo que el marcado decía antes.
    const soloAyuda = propiedadesDeCampo('description', {}, 'publicacion', 'publicacion-descripcion-restantes');
    expect(soloAyuda['aria-describedby']).toBe('publicacion-descripcion-restantes');
  });

  it('los dos lados de la cuerda salen de la misma función', () => {
    // Esta es la prueba de por qué el mecanismo es un módulo y no una copia por pantalla.
    const props = propiedadesDeCampo('email', errores, 'alta');
    expect(props['aria-describedby']).toBe(idDelMensaje('alta', 'email'));
  });
});

describe('el foco y el aviso de arriba', () => {
  it('el foco va al primero de la pantalla, no al primero del 422', () => {
    // El servidor manda los renglones en el orden de los campos del esquema, que no tiene
    // por qué ser el de arriba abajo de la pantalla. Llevar el foco al que el 422 nombra
    // primero deja a quien navega con teclado mirando hacia el sitio equivocado.
    const enfocado = [];
    const contenedor = {
      current: {
        querySelector: (selector) => ({ focus: () => enfocado.push(selector) }),
      },
    };
    vi.useFakeTimers();
    const primero = enfocarPrimerCampoConError(
      contenedor,
      { telefono: 'No vale.', nombre: 'Falta este campo.' },
      ['nombre', 'correo', 'telefono'],
    );
    vi.runAllTimers();
    vi.useRealTimers();
    expect(primero).toBe('nombre');
    expect(enfocado).toEqual(['[data-campo="nombre"]']);
  });

  it('si el campo está plegado, se abre antes de buscarlo', () => {
    // Un campo que todavía no está en el documento no puede recibir el foco: `antes` deja
    // que el formulario despliegue la sección y el `setTimeout` espera a ese render.
    const abiertos = [];
    const contenedor = { current: { querySelector: () => null } };
    enfocarPrimerCampoConError(
      contenedor, { telefono: 'No vale.' }, ['nombre', 'telefono'], (campo) => abiertos.push(campo),
    );
    expect(abiertos).toEqual(['telefono']);
  });

  it('sin ningún error no se toca el foco', () => {
    const contenedor = { current: { querySelector: () => { throw new Error('no debió buscar'); } } };
    expect(enfocarPrimerCampoConError(contenedor, {}, ['nombre'])).toBeNull();
  });

  it('el resumen nombra los campos como los nombra la pantalla', () => {
    // Con el nombre de la columna —`first_name`— el resumen sería tan ilegible como el
    // volcado que vino a sustituir.
    expect(resumenDeCampos({ first_name: 'x' }, { first_name: 'Nombre' }))
      .toBe('Revise el campo Nombre.');
    expect(resumenDeCampos({ first_name: 'x', email: 'y' }, { first_name: 'Nombre', email: 'Correo' }))
      .toBe('Revise estos campos: Nombre, Correo.');
    expect(resumenDeCampos({})).toBe('');
  });

  it('el aviso une sus renglones y no empieza en blanco', () => {
    expect(comoAviso(['uno', '', 'dos'])).toBe('uno\ndos');
    expect(comoAviso(['', ''])).toBe('');
  });
});

describe('la tabla de tipos, entera', () => {
  // Se recorre **toda** la tabla y no una selección: una entrada que ninguna prueba
  // ejercita es una entrada que puede estar rota —un `ctx` mal nombrado, una plantilla con
  // un hueco— y nadie lo sabría hasta que un servidor mandara ese tipo. La lista sale del
  // código, como las de `clases.test.js` y `tokens.test.js`.
  //
  // El contexto que cada tipo trae, para los que lo usan. Los demás lo ignoran.
  const CONTEXTO = {
    string_too_short: { min_length: 2 },
    string_too_long: { max_length: 2800 },
    greater_than_equal: { ge: 1 },
    less_than_equal: { le: 1000 },
  };

  it('ninguna entrada contesta en inglés ni se queda a medias', () => {
    const tipos = Object.keys(POR_TIPO);
    // Si la tabla se vaciara, este bucle no comprobaría nada y pasaría.
    expect(tipos.length).toBeGreaterThanOrEqual(12);

    for (const tipo of tipos) {
      const mensaje = mensajeDelRenglon({
        type: tipo,
        loc: ['body', 'un_campo'],
        msg: 'Something only Pydantic would write',
        ctx: CONTEXTO[tipo],
      });
      expect(mensaje, `${tipo} no dice nada`).toBeTruthy();
      expect(mensaje, `${tipo} contesta con el texto del servidor`).not.toMatch(/Something only/);
      expect(mensaje, `${tipo} no acaba la frase`).toMatch(/\.$/);
      // Y ninguna se queda con un hueco sin rellenar de su plantilla.
      expect(mensaje, `${tipo} dejó un hueco sin rellenar`).not.toMatch(/undefined|\[object/);
    }
  });

  it('y sin contexto tampoco se rompen ni enseñan un hueco', () => {
    // Un `ctx` que no llega es un error del servidor, no de quien rellena el formulario.
    for (const tipo of Object.keys(POR_TIPO)) {
      const mensaje = mensajeDelRenglon({ type: tipo, loc: ['body', 'x'], msg: 'In English' });
      expect(mensaje, `${tipo} se rompe sin ctx`).toBeTruthy();
      expect(mensaje).not.toMatch(/undefined|In English/);
    }
  });
});

describe('corregir un campo lo saca de la lista', () => {
  it('borra la clave, no la deja en undefined', () => {
    // Con la clave puesta a `undefined`, el borde rojo y el mensaje desaparecen pero
    // `Object.keys` sigue contando ese campo: el resumen de arriba diría «revise el
    // teléfono» de un teléfono ya corregido. Es la clase de diferencia que no se ve hasta
    // que se ve.
    const corregido = sinElCampo({ phone: 'No vale.', email: 'Falta este campo.' }, 'phone');
    expect(Object.keys(corregido)).toEqual(['email']);
    expect(resumenDeCampos(corregido, { email: 'Correo' })).toBe('Revise el campo Correo.');
  });

  it('y no toca nada si ese campo no estaba marcado', () => {
    const errores = { email: 'Falta este campo.' };
    expect(sinElCampo(errores, 'phone')).toBe(errores);
    expect(sinElCampo(null, 'phone')).toBeNull();
  });
});
