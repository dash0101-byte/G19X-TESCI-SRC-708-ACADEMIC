// ============================================================================
// El módulo de sesión (N-9)
// ============================================================================
//
// Es la parte del cliente donde un fallo no se ve: un refresco de más no rompe la
// pantalla, solo multiplica peticiones; una sesión que revive tras cerrarla tampoco
// avisa. Por eso se prueba primero, y por eso las pruebas miran las llamadas que se
// hacen, no solo lo que devuelve la función.
//
// Cada `it` importa el módulo de nuevo con `vi.resetModules()`: el token vive en una
// variable de módulo, así que sin eso la sesión de una prueba se filtraría a la
// siguiente y el orden de ejecución cambiaría el resultado.

import { beforeEach, describe, expect, it, vi } from 'vitest';

const USUARIO = {
  id: 1,
  email: 'ana@plurione.test',
  role: 'Sales_Lead',
  full_name: 'Ana Ruiz',
};

/** Carga una instancia limpia del módulo. */
async function moduloLimpio() {
  vi.resetModules();
  return import('./api.js');
}

/** Construye una respuesta como la que devuelve `fetch`. */
function respuesta(status, cuerpo) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => cuerpo,
  };
}

/**
 * Un `fetch` de mentira gobernado por una tabla de rutas.
 *
 * Cada entrada puede ser una respuesta fija o una función que recibe el número de
 * llamada, para poder decir «el primer intento falla y el segundo funciona».
 */
function fetchSimulado(rutas) {
  const llamadas = [];
  const cuentas = {};
  const fn = vi.fn(async (url, opciones = {}) => {
    llamadas.push({ url, opciones });
    const clave = Object.keys(rutas).find((r) => url.includes(r));
    if (!clave) throw new Error(`Ruta no prevista en la prueba: ${url}`);
    cuentas[clave] = (cuentas[clave] || 0) + 1;
    const valor = rutas[clave];
    return typeof valor === 'function' ? valor(cuentas[clave], opciones) : valor;
  });
  fn.llamadas = llamadas;
  fn.vecesDe = (ruta) => llamadas.filter((l) => l.url.includes(ruta)).length;
  globalThis.fetch = fn;
  return fn;
}

let api;

beforeEach(async () => {
  api = await moduloLimpio();
});

// ----------------------------------------------------------------- almacenamiento
describe('dónde vive el token', () => {
  it('no escribe nada en localStorage ni en sessionStorage al iniciar sesión', async () => {
    const escrituras = [];
    for (const almacen of [globalThis.localStorage, globalThis.sessionStorage]) {
      vi.spyOn(almacen, 'setItem').mockImplementation((k, v) => escrituras.push([k, v]));
    }
    fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'tk-1', user: USUARIO }),
    });

    await api.login('ana@plurione.test', 'secreta');

    // Es la propiedad que sostiene toda la decisión de la Fase 3: un XSS puede leer
    // esos almacenes, y lo que hay allí sobrevive al cierre de la pestaña.
    expect(escrituras).toEqual([]);
    expect(api.isAuthenticated()).toBe(true);
  });

  it('el token acompaña a la petición pero no es legible desde fuera del módulo', async () => {
    const f = fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'tk-secreta', user: USUARIO }),
      '/leads': respuesta(200, []),
    });
    await api.login('ana@plurione.test', 'secreta');
    await api.fetchLeads();

    const cabeceras = f.llamadas.at(-1).opciones.headers;
    expect(cabeceras.Authorization).toBe('Bearer tk-secreta');
    // El módulo no exporta ninguna forma de leerlo.
    expect(Object.keys(api)).not.toContain('accessToken');
    expect(Object.keys(api)).not.toContain('getAccessToken');
  });

  it('todas las llamadas viajan con credentials para que la cookie de refresco vaya y vuelva', async () => {
    const f = fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'tk', user: USUARIO }),
      '/leads': respuesta(200, []),
    });
    await api.login('a@b.c', 'x');
    await api.fetchLeads();

    for (const llamada of f.llamadas) {
      expect(llamada.opciones.credentials).toBe('same-origin');
    }
  });
});

// ----------------------------------------------------------------- 401 y reintento
describe('401 y renovación', () => {
  it('renueva el token y reintenta la petición una vez', async () => {
    const f = fetchSimulado({
      '/auth/refresh': respuesta(200, { access_token: 'tk-nuevo', user: USUARIO }),
      '/leads': (n) => (n === 1 ? respuesta(401, {}) : respuesta(200, [{ id: 7 }])),
    });

    const leads = await api.fetchLeads();

    expect(leads).toEqual([{ id: 7 }]);
    expect(f.vecesDe('/auth/refresh')).toBe(1);
    expect(f.vecesDe('/leads')).toBe(2);
    // El reintento debe llevar el token NUEVO, no el que acababa de ser rechazado.
    const reintento = f.llamadas.at(-1);
    expect(reintento.opciones.headers.Authorization).toBe('Bearer tk-nuevo');
  });

  it('no reintenta indefinidamente: si el segundo intento vuelve a dar 401, la sesión expira', async () => {
    const expirada = vi.fn();
    api.setSessionExpiredHandler(expirada);
    const f = fetchSimulado({
      '/auth/refresh': respuesta(200, { access_token: 'tk-nuevo', user: USUARIO }),
      '/leads': respuesta(401, {}),
    });

    await expect(api.fetchLeads()).rejects.toThrow(/sesión ha expirado/i);

    expect(f.vecesDe('/leads')).toBe(2);
    expect(expirada).toHaveBeenCalledTimes(1);
    expect(api.isAuthenticated()).toBe(false);
    expect(api.getCurrentUser()).toBeNull();
  });

  it('si el propio refresco falla, no se reintenta la petición y la sesión se cierra', async () => {
    const expirada = vi.fn();
    api.setSessionExpiredHandler(expirada);
    const f = fetchSimulado({
      '/auth/refresh': respuesta(401, {}),
      '/leads': respuesta(401, {}),
    });

    await expect(api.fetchLeads()).rejects.toThrow(/sesión ha expirado/i);

    // Una sola llamada al listado: sin token nuevo, repetirla solo añade ruido.
    expect(f.vecesDe('/leads')).toBe(1);
    expect(expirada).toHaveBeenCalledTimes(1);
  });

  it('un refresco que revienta por red se trata como refresco fallido, no como excepción', async () => {
    api.setSessionExpiredHandler(vi.fn());
    fetchSimulado({
      '/auth/refresh': () => {
        throw new TypeError('Failed to fetch');
      },
      '/leads': respuesta(401, {}),
    });

    // Lo que llega a quien llama es el mensaje de sesión, no un `TypeError` crudo.
    await expect(api.fetchLeads()).rejects.toThrow(/sesión ha expirado/i);
  });

  it('un 403 no dispara renovación: el token es válido, lo que falta es permiso', async () => {
    const f = fetchSimulado({
      '/users': respuesta(403, { detail: 'Requiere rol ADMIN' }),
    });

    await expect(api.fetchUsers()).rejects.toThrow('Requiere rol ADMIN');
    expect(f.vecesDe('/auth/refresh')).toBe(0);
  });
});

// ----------------------------------------------------------------- concurrencia
describe('refresco concurrente', () => {
  it('cinco peticiones que reciben 401 a la vez comparten un único refresco', async () => {
    let resolverRefresco;
    const refrescoPendiente = new Promise((r) => {
      resolverRefresco = r;
    });

    const f = fetchSimulado({
      '/auth/refresh': async () => {
        await refrescoPendiente;
        return respuesta(200, { access_token: 'tk-nuevo', user: USUARIO });
      },
      '/leads': (n) => (n <= 5 ? respuesta(401, {}) : respuesta(200, [])),
      '/analytics/summary': (n) => (n <= 1 ? respuesta(401, {}) : respuesta(200, {})),
    });

    const enVuelo = [
      api.fetchLeads(),
      api.fetchLeads(),
      api.fetchLeads(),
      api.fetchLeads(),
      api.fetchLeads(),
      api.fetchAnalyticsSummary(),
    ];
    // Se deja avanzar la cola de microtareas para que las seis lleguen al 401.
    await Promise.resolve();
    await Promise.resolve();

    resolverRefresco();
    await Promise.all(enVuelo);

    // UNA renovación, no seis. Sin la promesa compartida, cada 401 abriría la suya y el
    // backend recibiría una tormenta de refrescos por cada caducidad del token.
    expect(f.vecesDe('/auth/refresh')).toBe(1);
  });

  it('tras completarse un refresco, un 401 posterior puede pedir otro', async () => {
    const f = fetchSimulado({
      '/auth/refresh': (n) => respuesta(200, { access_token: `tk-${n}`, user: USUARIO }),
      '/leads': (n) => (n % 2 === 1 ? respuesta(401, {}) : respuesta(200, [])),
    });

    await api.fetchLeads();
    // La promesa compartida se libera en el siguiente tick; sin esta espera la segunda
    // tanda reutilizaría la primera y el token nunca se renovaría de nuevo.
    await new Promise((r) => setTimeout(r, 0));
    await api.fetchLeads();

    expect(f.vecesDe('/auth/refresh')).toBe(2);
  });
});

// ----------------------------------------------------------------- restaurar y salir
describe('restaurar la sesión y cerrarla', () => {
  it('restoreSession devuelve el usuario cuando la cookie sigue siendo válida', async () => {
    fetchSimulado({
      '/auth/refresh': respuesta(200, { access_token: 'tk', user: USUARIO }),
    });

    await expect(api.restoreSession()).resolves.toEqual(USUARIO);
    expect(api.getCurrentUserRole()).toBe('Sales_Lead');
  });

  it('restoreSession devuelve null sin cookie, y no deja media sesión montada', async () => {
    fetchSimulado({ '/auth/refresh': respuesta(401, {}) });

    await expect(api.restoreSession()).resolves.toBeNull();
    expect(api.isAuthenticated()).toBe(false);
    expect(api.getCurrentUserRole()).toBeNull();
  });

  it('logout limpia la sesión aunque la llamada al servidor falle', async () => {
    fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'tk', user: USUARIO }),
      '/auth/logout': () => {
        throw new TypeError('Failed to fetch');
      },
    });
    await api.login('a@b.c', 'x');

    await api.logout();

    // Quien pulsa «salir» ha decidido salir. Que el servidor no conteste no puede
    // dejar el token vivo en la pestaña.
    expect(api.isAuthenticated()).toBe(false);
    expect(api.getCurrentUser()).toBeNull();
  });

  it('logout sin sesión activa no llama al servidor', async () => {
    const f = fetchSimulado({ '/auth/logout': respuesta(204, null) });
    await api.logout();
    expect(f.vecesDe('/auth/logout')).toBe(0);
  });

  it('tras cerrar sesión, la renovación vuelve a funcionar en la sesión siguiente', async () => {
    // Este caso lo encontró la comprobación de que ninguna prueba es vacía: quitar la
    // línea que descarta la renovación en curso al cerrar sesión no hacía fallar NADA.
    //
    // El detalle: la promesa compartida se libera en un `setTimeout` que solo actúa si
    // la sesión sigue siendo la misma. Si al cerrar sesión no se descarta a mano, ese
    // temporizador ya no la libera nunca —la época cambió—, y queda pegada una promesa
    // ya resuelta a `false`. A partir de ahí, cada 401 la reutiliza y da por fallada la
    // renovación sin llegar a pedirla: la sesión nueva se cae a los cinco minutos, al
    // caducar su primer token, y no hay forma de seguir trabajando sin recargar.
    let resolverPrimera;
    const f = fetchSimulado({
      '/auth/login': (n) => respuesta(200, { access_token: `tk-${n}`, user: USUARIO }),
      '/auth/logout': respuesta(204, null),
      '/auth/refresh': (n) =>
        n === 1
          ? new Promise((r) => {
              resolverPrimera = () => r(respuesta(401, {}));
            })
          : respuesta(200, { access_token: 'tk-renovado', user: USUARIO }),
      // Un 401 en cada sesión: el primero abre la renovación que se queda colgada, y el
      // segundo —ya en la sesión nueva— es el que tiene que provocar una renovación
      // NUEVA. El tercero es el reintento, que ya funciona.
      '/leads': (n) => (n <= 2 ? respuesta(401, {}) : respuesta(200, [])),
    });

    await api.login('a@b.c', 'x');
    api.setSessionExpiredHandler(vi.fn());

    // Un 401 abre la renovación...
    const enVuelo = api.fetchLeads().catch(() => {});
    await Promise.resolve();
    await Promise.resolve();

    // ...y en mitad de ella, la persona cierra sesión y vuelve a entrar.
    await api.logout();
    resolverPrimera();
    await enVuelo;
    await new Promise((r) => setTimeout(r, 0));

    await api.login('a@b.c', 'x');
    f.llamadas.length = 0;

    // El 401 de la sesión NUEVA tiene que pedir una renovación nueva.
    await api.fetchLeads();

    expect(f.vecesDe('/auth/refresh')).toBe(1);
    expect(api.isAuthenticated()).toBe(true);
  });

  it('un refresco en vuelo no puede resucitar una sesión ya cerrada', async () => {
    let resolverRefresco;
    const refrescoPendiente = new Promise((r) => {
      resolverRefresco = r;
    });
    fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'tk-viejo', user: USUARIO }),
      '/auth/logout': respuesta(204, null),
      '/auth/refresh': async () => {
        await refrescoPendiente;
        return respuesta(200, { access_token: 'tk-renovado', user: USUARIO });
      },
      // El primer intento da 401 y el reintento posterior al refresco SI funciona. Es
      // importante: si el reintento tambien diera 401, el propio apiFetch volveria a
      // limpiar la sesion y la prueba pasaria sin haber comprobado nada.
      '/leads': (n) => (n === 1 ? respuesta(401, {}) : respuesta(200, [])),
    });

    await api.login('a@b.c', 'x');
    api.setSessionExpiredHandler(vi.fn());

    // Una petición tropieza con un 401 y arranca la renovación...
    const enVuelo = api.fetchLeads().catch(() => {});
    await Promise.resolve();
    await Promise.resolve();

    // ...y mientras esa renovación sigue en el aire, la persona cierra sesión.
    await api.logout();
    expect(api.isAuthenticated()).toBe(false);

    // El refresco termina DESPUÉS del logout.
    resolverRefresco();
    await enVuelo;
    await new Promise((r) => setTimeout(r, 0));

    // Si el refresco escribiera el token sin mirar, la pestaña volvería a estar dentro
    // sin que nadie haya vuelto a entrar: la sesión se cerró y sigue cerrada.
    expect(api.isAuthenticated()).toBe(false);
    expect(api.getCurrentUser()).toBeNull();
  });
});

// ----------------------------------------------------------------- errores
describe('traducción de errores de la API', () => {
  it('un detalle de texto llega tal cual', async () => {
    fetchSimulado({ '/leads': respuesta(400, { detail: 'Correo ya registrado' }) });
    await expect(api.fetchLeads()).rejects.toThrow('Correo ya registrado');
  });

  // El nombre de la columna ya no se escribe (capítulo 43)
  // ------------------------------------------------------
  // Esta función ponía `campo: mensaje` con el `campo` tal como viaja, que es el nombre de
  // la columna: `company_size`, `nueva_contrasena`, `assigned_rep_id`. Las cuatro pantallas
  // del capítulo 40 no lo veían porque reparten el 422 por campos antes de llegar aquí; las
  // otras siete sí, y lo que lo escribía no estaba en ellas: estaba aquí, una vez.
  //
  // Y en castellano (capítulo 45)
  // ------------------------------
  // Los renglones de estas dos pruebas **no traían `type`**, que es el único campo del 422
  // por el que se puede saber qué clase de error es, y su valor esperado era el texto en
  // inglés de Pydantic: `'Field required'` estaba escrito aquí como lo correcto. Pasaban, y
  // lo que documentaban era que la pantalla enseña inglés. Ahora los renglones son los que
  // manda el servidor —con su `type`— y lo esperado es la frase de la tabla del capítulo 40,
  // que esta función no consultaba.
  it('los errores de validación de Pydantic llegan sin el nombre de la columna', async () => {
    fetchSimulado({
      '/leads': respuesta(422, {
        detail: [
          {
            type: 'value_error',
            loc: ['body', 'email'],
            msg: 'Value error, no es un correo válido',
          },
          {
            type: 'greater_than_equal',
            loc: ['body', 'company_size'],
            msg: 'Input should be greater than or equal to 1',
            ctx: { ge: 1 },
          },
        ],
      }),
    });
    await expect(api.createLead({})).rejects.toThrow(
      'no es un correo válido\nTiene que ser 1 o más.',
    );
  });

  it('dos campos que fallan por lo mismo dicen una sola vez por qué', async () => {
    // «Falta este campo.» repetido tres veces no dice qué tres campos faltan: dice tres
    // veces lo mismo. Quien necesita saber cuál es el campo reparte el 422 por campos.
    fetchSimulado({
      '/leads': respuesta(422, {
        detail: [
          { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
          { type: 'missing', loc: ['body', 'last_name'], msg: 'Field required' },
          {
            type: 'value_error',
            loc: ['body', 'email'],
            msg: 'Value error, no es un correo válido',
          },
        ],
      }),
    });
    await expect(api.createLead({})).rejects.toThrow(
      'Falta este campo.\nno es un correo válido',
    );
  });

  // Los seis de nueve que llegaban en inglés (capítulo 45)
  // ------------------------------------------------------
  // Renglones copiados de los de verdad: salen de `ActivityCreate` y `CierreDelProspecto`,
  // que son los dos esquemas de los dos formularios del panel que no reparten su 422 por
  // campos. El de la lista cerrada es el que mejor se ve: catorce claves en inglés, mayúsculas
  // y con comillas simples, dentro del aviso de un formulario cuyo desplegable las ofrece
  // todas traducidas.
  it('los rechazos que la biblioteca escribe en inglés salen en castellano', async () => {
    fetchSimulado({
      '/leads/7/activities': respuesta(422, {
        detail: [
          { type: 'missing', loc: ['body', 'activity_type'], msg: 'Field required' },
          {
            type: 'datetime_from_date_parsing',
            loc: ['body', 'inicio_de_la_reunion'],
            msg: 'Input should be a valid datetime or date, input is too short',
          },
          {
            type: 'enum',
            loc: ['body', 'activity_type'],
            msg: "Input should be 'PAGE_VIEW', 'FORM_SUBMIT' or 'CUSTOM'",
            ctx: { expected: "'PAGE_VIEW', 'FORM_SUBMIT' or 'CUSTOM'" },
          },
        ],
      }),
    });
    const fallo = await api.addLeadActivity(7, {}).catch((e) => e);
    expect(fallo.message).toBe(
      'Falta este campo.\nEscriba una fecha válida.\nElija una de las opciones de la lista.',
    );
    expect(fallo.message).not.toMatch(/Field required|PAGE_VIEW|valid datetime/);
  });

  // La frase larga del validador de modelo (capítulo 45)
  // -----------------------------------------------------
  // Este renglón trae sus campos en `ctx` y no en `loc`, así que una pantalla que reparta lo
  // pone debajo de cada campo con la frase corta. Aquí no se reparte nada: lo que se enseña
  // es la frase del servidor, que se lee sola y no nombra ninguna columna.
  it('el rechazo de un validador de modelo enseña su frase entera, no la corta', async () => {
    fetchSimulado({
      '/leads/7': respuesta(422, {
        detail: [
          {
            type: 'campos_vacios_prohibidos',
            loc: ['body'],
            msg: 'La ficha no existe sin alguno de los campos que llegaron vacíos. Envíe un valor, o no envíe el campo si no quiere cambiarlo.',
            ctx: { campos: ['last_name'] },
          },
        ],
      }),
    });
    const fallo = await api.updateLead(7, { last_name: null }).catch((e) => e);
    expect(fallo.message).toMatch(/^La ficha no existe sin alguno de los campos/);
    expect(fallo.message).not.toMatch(/last_name|No puede quedar vacío/);
  });

  it('«Value error,» no llega a la pantalla: es el nombre de la excepción, no el mensaje', async () => {
    fetchSimulado({
      '/interes/abc123': respuesta(422, {
        detail: [
          {
            loc: ['body', 'linkedin'],
            msg: 'Value error, El perfil tiene que ser una dirección de LinkedIn como https://www.linkedin.com/in/su-perfil',
          },
        ],
      }),
    });
    await expect(api.enviarInteres('abc123', {})).rejects.toThrow(
      'El perfil tiene que ser una dirección de LinkedIn como https://www.linkedin.com/in/su-perfil',
    );
  });

  it('los motivos de una contraseña rechazada llegan todos, detrás del mensaje', async () => {
    // El servidor manda la lista completa a propósito —su propio código lo explica: dar un
    // motivo cada vez obliga a descubrir la política a base de intentos— y esta función se
    // quedaba con el `mensaje` y tiraba la lista. En pantalla salía «La contraseña no
    // cumple la política del sistema.» y nada que se pudiera corregir.
    fetchSimulado({
      '/auth/change-password': respuesta(422, {
        detail: {
          mensaje: 'La contraseña no cumple la política del sistema.',
          motivos: [
            'Debe tener al menos 12 caracteres.',
            'Está en la lista de contraseñas filtradas: elija otra.',
          ],
        },
      }),
    });

    await expect(api.changeOwnPassword('vieja', 'corta')).rejects.toThrow(
      'La contraseña no cumple la política del sistema.\n'
      + 'Debe tener al menos 12 caracteres.\n'
      + 'Está en la lista de contraseñas filtradas: elija otra.',
    );
  });

  it('un detalle estructurado sin motivos sigue siendo solo su mensaje', async () => {
    fetchSimulado({
      '/auth/change-password': respuesta(422, {
        detail: { mensaje: 'La contraseña nueva no puede ser igual a la actual.' },
      }),
    });
    await expect(api.changeOwnPassword('a', 'a')).rejects.toThrow(
      'La contraseña nueva no puede ser igual a la actual.',
    );
  });

  it('el 409 del recálculo masivo muestra el mensaje y conserva el detalle', async () => {
    const detalle = {
      mensaje: 'Ya hay un recálculo masivo en curso.',
      job_id: 'abc-123',
      estado: 'RUNNING',
      procesados: 40,
      total: 120,
      solicitado_por: 'ana@plurione.test',
    };
    fetchSimulado({ '/batch/recalculate-all': respuesta(409, { detail: detalle }) });

    const error = await api.recalculateAllScores().catch((e) => e);

    // Antes se volcaba el objeto con JSON.stringify y en pantalla salía el JSON entero.
    expect(error.message).toBe('Ya hay un recálculo masivo en curso.');
    // Y el detalle sigue disponible para que la pantalla muestre el avance.
    expect(error.status).toBe(409);
    expect(error.detalle).toEqual(detalle);
  });

  it('un cuerpo que no es JSON no tapa el error con un fallo de parseo', async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON');
      },
    }));

    const error = await api.fetchLeads().catch((e) => e);
    expect(error.message).toBe('Error al cargar prospectos');
    expect(error.status).toBe(502);
  });

  it('un 204 devuelve null en vez de reventar al leer un cuerpo vacío', async () => {
    fetchSimulado({ '/campaigns': respuesta(204, null) });
    await expect(api.deactivateCampaign(3)).resolves.toBeNull();
  });
});

// ----------------------------------------------------------------- construcción de URLs
describe('construcción de peticiones', () => {
  it('los filtros del listado viajan como parámetros y se omiten los vacíos', async () => {
    const f = fetchSimulado({ '/leads': respuesta(200, []) });
    await api.fetchLeads({ category: 'HOT', search: 'acme s.a. & co', limit: 50, status: '' });

    const url = f.llamadas[0].url;
    const params = new URLSearchParams(url.split('?')[1]);
    expect(params.get('score_category')).toBe('HOT');
    expect(params.get('search')).toBe('acme s.a. & co');
    expect(params.get('limit')).toBe('50');
    expect(params.has('status')).toBe(false);
  });

  it('el rol se escapa al cambiarlo, para que no se pueda inyectar otro parámetro', async () => {
    const f = fetchSimulado({ '/users': respuesta(200, {}) });
    await api.changeUserRole(4, 'ADMIN&forzar=1');

    expect(f.llamadas[0].url).toContain('rol=ADMIN%26forzar%3D1');
    expect(f.llamadas[0].url).not.toContain('&forzar=1');
  });

  it('las peticiones sin cuerpo no declaran Content-Type', async () => {
    const f = fetchSimulado({ '/leads': respuesta(200, []) });
    await api.fetchLeads();
    expect(f.llamadas[0].opciones.headers['Content-Type']).toBeUndefined();
  });
});

// ----------------------------------------------------------------- catálogo de rutas
describe('el catálogo de endpoints', () => {
  // Cada envoltorio de esta lista es una línea que nadie vuelve a mirar, y en la que un
  // error —un plural de más, un PUT donde iba un POST— no se nota al escribirla: la
  // llamada sale, el backend devuelve 404 o 405 y en pantalla aparece un mensaje
  // genérico. Esta tabla fija el contrato del cliente con la API en un solo sitio.
  const RUTAS = [
    ['fetchAnalyticsSummary', [], 'GET', '/api/v1/analytics/summary'],
    ['fetchCampaigns', [], 'GET', '/api/v1/analytics/campaigns'],
    ['fetchLeadDetail', [7], 'GET', '/api/v1/leads/7'],
    ['createLead', [{ email: 'a@b.c' }], 'POST', '/api/v1/leads'],
    ['updateLead', [7, { status: 'WON' }], 'PUT', '/api/v1/leads/7'],
    ['addLeadActivity', [7, { kind: 'CALL' }], 'POST', '/api/v1/leads/7/activities'],
    ['recalculateLeadScore', [7], 'POST', '/api/v1/leads/7/recalculate-score'],
    ['recalculateAllScores', [50], 'POST', '/api/v1/leads/batch/recalculate-all'],
    ['getRecalculationJob', ['j-1'], 'GET', '/api/v1/leads/batch/jobs/j-1'],
    ['predictScoreLive', [{ job_title: 'CTO' }], 'POST', '/api/v1/scoring/predict'],
    ['fetchSalesReps', [], 'GET', '/api/v1/sales-reps'],
    ['createUser', [{ email: 'a@b.c' }], 'POST', '/api/v1/users'],
    ['updateUser', [3, { full_name: 'X' }], 'PUT', '/api/v1/users/3'],
    ['deactivateUser', [3], 'DELETE', '/api/v1/users/3'],
    ['activateUser', [3], 'POST', '/api/v1/users/3/activate'],
    ['resetUserPassword', [3, 'nueva-frase-larga'], 'POST', '/api/v1/users/3/reset-password'],
    ['changeOwnPassword', ['vieja', 'nueva'], 'POST', '/api/v1/auth/change-password'],
    ['transferPortfolio', [7, 3], 'POST', '/api/v1/sales-reps/7/cartera'],
    ['fetchCampaignList', [], 'GET', '/api/v1/campaigns'],
    ['createCampaign', [{ name: 'Q4' }], 'POST', '/api/v1/campaigns'],
    ['updateCampaign', [2, { name: 'Q1' }], 'PUT', '/api/v1/campaigns/2'],
    ['deactivateCampaign', [2], 'DELETE', '/api/v1/campaigns/2'],
    ['activateCampaign', [2], 'PUT', '/api/v1/campaigns/2'],
    ['fetchInformeDePublicacion', [2], 'GET', '/api/v1/publicaciones/2/informe'],
    ['fetchVistaPreviaDePublicacion', [2], 'GET', '/api/v1/publicaciones/2/vista-previa'],
    ['duplicateCampaign', [2], 'POST', '/api/v1/campaigns/2/duplicar'],
    ['cambiarEstadoDePublicacion', [2, 'pausada'], 'PUT', '/api/v1/campaigns/2'],
    ['fetchComparativaDePublicaciones', [], 'GET', '/api/v1/publicaciones/comparativa'],
    ['fetchNuevosSinAsesor', [], 'GET', '/api/v1/publicaciones/nuevos-sin-asesor'],
    ['fetchPublicacionDeInteres', ['abc123'], 'GET', '/api/v1/interes/abc123'],
    ['enviarInteres', ['abc123', { correo: 'a@b.c' }], 'POST', '/api/v1/interes/abc123'],
    ['fetchEventosSinAsociar', [], 'GET', '/api/v1/eventos-sin-asociar'],
    ['vincularEventoSinAsociar', [11, 7], 'POST', '/api/v1/eventos-sin-asociar/11/vincular'],
    ['descartarEventoSinAsociar', [11], 'DELETE', '/api/v1/eventos-sin-asociar/11'],
    // El desenlace (capítulo 30). Cerrar vive bajo `/leads` porque es algo que se le hace
    // a un prospecto y necesita el alcance de cartera; leer, bajo `/desenlaces`.
    ['fetchOpcionesDeCierre', [], 'GET', '/api/v1/desenlaces/opciones'],
    ['cerrarProspecto', [7, { resultado: 'perdido', motivo: 'precio', cerrado_el: '2026-09-01' }], 'POST', '/api/v1/leads/7/desenlace'],
    ['fetchPanelDeDesenlaces', [], 'GET', '/api/v1/desenlaces/panel'],
    // La agenda del día (capítulo 28) y el segundo factor (capítulo 35). Ninguna de las
    // dos familias estaba en esta tabla, y las cinco del segundo factor no las tocaba
    // ninguna prueba: el módulo bajó del suelo de cobertura el día que entraron.
    ['fetchBandejaDeHoy', [], 'GET', '/api/v1/agenda/hoy'],
    ['marcarTareaHecha', [4], 'POST', '/api/v1/agenda/tareas/4/hecha'],
    ['fetchAvisos', [], 'GET', '/api/v1/agenda/avisos'],
    ['marcarAvisosLeidos', [], 'POST', '/api/v1/agenda/avisos/leidos'],
    ['fetchHotQueSeEnfrian', [], 'GET', '/api/v1/agenda/enfriandose'],
    ['fetchEstadoDeLaDireccionPublica', [], 'GET', '/api/v1/publicaciones/direccion-publica'],
    ['fetchEstadoDelSegundoFactor', [], 'GET', '/api/v1/auth/segundo-factor'],
    ['altaDelSegundoFactor', [], 'POST', '/api/v1/auth/segundo-factor/alta'],
    ['activarSegundoFactor', ['123456'], 'POST', '/api/v1/auth/segundo-factor/activar'],
    ['bajaDelSegundoFactor', ['123456'], 'POST', '/api/v1/auth/segundo-factor/baja'],
    // Los derechos del titular (capítulo 38). Los dos endpoints existen desde la Fase 14
    // y están comprobados tabla por tabla en el backend; lo que entró ahora es la forma
    // de pedirlos desde el panel.
    ['exportarDatosDelTitular', [42], 'GET', '/api/v1/leads/42/exportar'],
    ['suprimirTitular', [42], 'DELETE', '/api/v1/leads/42'],
  ];

  it.each(RUTAS)('%s → %s %s', async (nombre, argumentos, metodo, ruta) => {
    const f = vi.fn(async () => respuesta(200, {}));
    globalThis.fetch = f;

    await api[nombre](...argumentos);

    const [url, opciones] = f.mock.calls[0];
    expect(url.split('?')[0]).toBe(ruta);
    // `apiFetch` no pone `method` en las lecturas: `fetch` usa GET por defecto.
    expect(opciones.method ?? 'GET').toBe(metodo);
  });

  it('el panel de desenlaces solo manda el periodo cuando lo hay', async () => {
    // Un `?desde=&hasta=` vacío no es inocente: llega al servidor como dos fechas vacías
    // que hay que interpretar, y la pregunta «todos los cierres» deja de distinguirse de
    // «los cierres de un periodo que nadie acotó».
    const f = fetchSimulado({ '/desenlaces/panel': respuesta(200, {}) });

    await api.fetchPanelDeDesenlaces();
    expect(f.llamadas[0].url).toBe('/api/v1/desenlaces/panel');

    await api.fetchPanelDeDesenlaces({ desde: '2026-01-01' });
    expect(f.llamadas[1].url).toBe('/api/v1/desenlaces/panel?desde=2026-01-01');

    await api.fetchPanelDeDesenlaces({ desde: '2026-01-01', hasta: '2026-03-31' });
    expect(f.llamadas[2].url).toBe('/api/v1/desenlaces/panel?desde=2026-01-01&hasta=2026-03-31');

    await api.fetchPanelDeDesenlaces({ hasta: '2026-03-31' });
    expect(f.llamadas[3].url).toBe('/api/v1/desenlaces/panel?hasta=2026-03-31');
  });

  it('los listados con «incluir inactivos» solo mandan el parámetro cuando se pide', async () => {
    const f = fetchSimulado({ '/sales-reps': respuesta(200, []), '/campaigns': respuesta(200, []) });

    await api.fetchSalesReps();
    await api.fetchSalesReps({ incluirInactivos: true });
    await api.fetchCampaignList();
    await api.fetchCampaignList({ incluirInactivas: true });

    const urls = f.llamadas.map((l) => l.url);
    expect(urls[0]).not.toContain('incluir_inactivos');
    expect(urls[1]).toContain('incluir_inactivos=true');
    expect(urls[2]).not.toContain('incluir_inactivas');
    expect(urls[3]).toContain('incluir_inactivas=true');
  });

  it('las publicaciones se piden por canal y reactivar solo manda el estado', async () => {
    const f = fetchSimulado({ '/campaigns': () => respuesta(200, {}) });

    await api.fetchCampaignList({ incluirInactivas: true, canal: 'LinkedIn' });
    await api.activateCampaign(4);

    expect(f.llamadas[0].url).toContain('incluir_inactivas=true');
    expect(f.llamadas[0].url).toContain('canal=LinkedIn');
    expect(JSON.parse(f.llamadas[1].opciones.body)).toEqual({ is_active: true });
  });

  it('cambiar el estado de una publicación solo manda el estado', async () => {
    const f = fetchSimulado({ '/campaigns': () => respuesta(200, {}) });

    await api.cambiarEstadoDePublicacion(4, 'pausada');

    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({ estado: 'pausada' });
  });

  it('dos aperturas simultáneas de la página son una sola petición (y una visita)', async () => {
    // En desarrollo React monta dos veces: sin esto cada apertura contaba dos visitas.
    const f = fetchSimulado({ '/interes/abc123': () => respuesta(200, { titulo: 'X' }) });

    const [a, b] = await Promise.all([api.fetchPublicacionDeInteres('abc123'), api.fetchPublicacionDeInteres('abc123')]);
    expect(a).toEqual(b);
    expect(f.vecesDe('/interes/abc123')).toBe(1);

    // Una apertura posterior sí vuelve a pedir: es otra visita.
    await api.fetchPublicacionDeInteres('abc123');
    expect(f.vecesDe('/interes/abc123')).toBe(2);
  });

  it('dos redes distintas son dos visitas, no una compartida', async () => {
    // El reparto por red del capítulo 27 solo vale si cada red cuenta por su lado: con la
    // clave del slug a secas, abrir por WhatsApp y por Facebook a la vez contaba una sola.
    const f = fetchSimulado({ '/interes/abc123': () => respuesta(200, { titulo: 'X' }) });

    await Promise.all([
      api.fetchPublicacionDeInteres('abc123', 'whatsapp'),
      api.fetchPublicacionDeInteres('abc123', 'facebook'),
    ]);

    expect(f.vecesDe('/interes/abc123')).toBe(2);
    const redes = f.mock.calls.map(([url]) => new URL(url, 'http://x').searchParams.get('r'));
    expect(redes.sort()).toEqual(['facebook', 'whatsapp']);
  });

  it('la red se saca de la dirección de la página', () => {
    // Esta lectura vivía suelta en el arranque, que ninguna prueba monta: si devolvía
    // siempre vacío, todo el mundo llegaba «sin red» y nada lo decía.
    expect(api.redDeLaUrl('?r=whatsapp')).toBe('whatsapp');
    expect(api.redDeLaUrl('?otra=1&r=x')).toBe('x');
    expect(api.redDeLaUrl('')).toBe('');
    expect(api.redDeLaUrl('?r=')).toBe('');
  });

  it('una carga fallida de la página no se queda guardada', async () => {
    const f = fetchSimulado({ '/interes/abc123': (n) => (n === 1 ? respuesta(429, { detail: 'Demasiadas' }) : respuesta(200, { titulo: 'X' })) });

    await expect(api.fetchPublicacionDeInteres('abc123')).rejects.toThrow('Demasiadas');
    await expect(api.fetchPublicacionDeInteres('abc123')).resolves.toEqual({ titulo: 'X' });
    expect(f.vecesDe('/interes/abc123')).toBe(2);
  });

  it('el filtro de rol del listado de cuentas viaja como parámetro', async () => {
    const f = fetchSimulado({ '/users': respuesta(200, []) });
    await api.fetchUsers({ rol: 'System_Admin', incluirInactivos: true });
    expect(f.llamadas[0].url).toContain('rol=System_Admin');
    expect(f.llamadas[0].url).toContain('incluir_inactivos=true');
  });

  it('el recálculo masivo sin tamaño de lote manda un cuerpo vacío, no «undefined»', async () => {
    const f = fetchSimulado({ '/batch/recalculate-all': respuesta(202, {}) });
    await api.recalculateAllScores();
    expect(f.llamadas[0].opciones.body).toBe('{}');
  });

  it('con tamaño de lote lo manda en el cuerpo', async () => {
    const f = fetchSimulado({ '/batch/recalculate-all': respuesta(202, {}) });
    await api.recalculateAllScores(25);
    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({ batch_size: 25 });
  });

  it('el cambio de contraseña propia manda los nombres que espera el backend', async () => {
    const f = fetchSimulado({ '/auth/change-password': respuesta(200, {}) });
    await api.changeOwnPassword('la-vieja', 'la-nueva');
    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({
      contrasena_actual: 'la-vieja',
      nueva_contrasena: 'la-nueva',
    });
  });

  it('el restablecimiento por un administrador también', async () => {
    const f = fetchSimulado({ '/reset-password': respuesta(200, {}) });
    await api.resetUserPassword(3, 'una-frase-larga');
    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({
      nueva_contrasena: 'una-frase-larga',
    });
  });
});

// ============================================================================
describe('el acceso en dos pasos (capítulo 35)', () => {
  // Estas cinco funciones entraron en el capítulo 35 y ninguna prueba las tocaba: el
  // módulo bajó del suelo de cobertura que `vite.config.js` declara, y el trabajo del
  // capítulo 36 se encontró el pipeline ya en rojo por esto.
  //
  // No son cinco envoltorios cualesquiera. `login` es la única función del cliente que
  // puede devolver DOS cosas distintas —una sesión o un desafío—, y confundirlas tiene
  // consecuencias en los dos sentidos: abrir sesión con un desafío deja al panel creyendo
  // que hay usuario, y tratar una sesión como desafío pide un código que nadie ha pedido.

  it('un login normal abre sesión y devuelve al usuario', async () => {
    fetchSimulado({
      '/auth/login': respuesta(200, { access_token: 'un-token', user: USUARIO }),
      '/auth/me': respuesta(200, USUARIO),
    });

    const devuelto = await api.login('ana@plurione.test', 'una-frase-larga');

    expect(devuelto).toEqual(USUARIO);
    expect(api.isAuthenticated()).toBe(true);
    expect(api.getCurrentUser()).toEqual(USUARIO);
  });

  it('un login que pide segundo factor devuelve el desafío y NO abre sesión', async () => {
    // Lo que de verdad se comprueba: que el desafío no se confunde con una sesión. Si
    // `accessToken` se llenara aquí, el panel se dibujaría entero para alguien que solo ha
    // demostrado saber la contraseña, y el segundo factor sería decorado.
    fetchSimulado({
      '/auth/login': respuesta(200, {
        tipo: 'segundo_factor', desafio: 'un-desafio', expira_en: 300,
        codigos_de_recuperacion_restantes: 7,
      }),
    });

    const devuelto = await api.login('ana@plurione.test', 'una-frase-larga');

    expect(devuelto.tipo).toBe('segundo_factor');
    expect(devuelto.desafio).toBe('un-desafio');
    expect(api.isAuthenticated()).toBe(false);
    expect(api.getCurrentUser()).toBeNull();
  });

  it('el segundo paso manda el desafío en el cuerpo, nunca como Authorization', async () => {
    // El desafío acredita haber superado el primer paso y no es una credencial de sesión.
    // Si viajara en la cabecera, el segundo factor se saltaría sin más que no pedirlo.
    const f = fetchSimulado({
      '/auth/login/segundo-factor': respuesta(200, { access_token: 'un-token', user: USUARIO }),
    });

    const devuelto = await api.completarLoginConSegundoFactor('un-desafio', '  123456  ');

    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({
      desafio: 'un-desafio',
      // Y el código va sin los espacios que deja un pegado desde el teléfono.
      codigo: '123456',
    });
    expect(f.llamadas[0].opciones.headers.Authorization).toBeUndefined();
    expect(devuelto).toEqual(USUARIO);
    expect(api.isAuthenticated()).toBe(true);
  });

  it('un código equivocado no abre sesión y dice por qué', async () => {
    fetchSimulado({
      '/auth/login/segundo-factor': {
        ok: false, status: 401,
        json: async () => ({ detail: 'El código no es válido.' }),
      },
    });

    await expect(api.completarLoginConSegundoFactor('un-desafio', '000000'))
      .rejects.toThrow('El código no es válido.');
    expect(api.isAuthenticated()).toBe(false);
  });

  it('activar y quitar el segundo factor recortan el código', async () => {
    const f = fetchSimulado({
      '/segundo-factor/activar': respuesta(200, {}),
      '/segundo-factor/baja': respuesta(200, {}),
    });

    await api.activarSegundoFactor(' 123456 ');
    await api.bajaDelSegundoFactor('\t654321\n');

    expect(JSON.parse(f.llamadas[0].opciones.body)).toEqual({ codigo: '123456' });
    expect(JSON.parse(f.llamadas[1].opciones.body)).toEqual({ codigo: '654321' });
  });

  it('un login incorrecto dice «Email o contraseña incorrectos», no el detalle del servidor', async () => {
    // El 401 del acceso se traduce en el cliente a propósito: el mensaje del servidor puede
    // distinguir «no existe esa cuenta» de «la contraseña no es esa», y eso es precisamente
    // lo que no debe llegar a la pantalla.
    fetchSimulado({
      '/auth/login': { ok: false, status: 401, json: async () => ({ detail: 'usuario inexistente' }) },
    });

    await expect(api.login('quien@plurione.test', 'x')).rejects.toThrow('Email o contraseña incorrectos.');
  });
});

describe('los avisos, con y sin filtro', () => {
  it('«solo sin leer» viaja en la consulta solo cuando se pide', async () => {
    const f = fetchSimulado({ '/agenda/avisos': respuesta(200, { sin_leer: 0, avisos: [] }) });

    await api.fetchAvisos();
    expect(f.llamadas[0].url).toBe('/api/v1/agenda/avisos');

    await api.fetchAvisos({ soloSinLeer: true });
    expect(f.llamadas[1].url).toBe('/api/v1/agenda/avisos?solo_sin_leer=true');
  });

  it('marcar leídos sin lista manda un cuerpo vacío, no «undefined»', async () => {
    // El endpoint recibe la lista dentro de un objeto, y un cuerpo ausente no es lo mismo
    // que uno sin lista: sin cuerpo, el servidor no sabe si se le pide «todos» o nada.
    const f = fetchSimulado({ '/agenda/avisos/leidos': respuesta(200, { leidos: 3 }) });

    await api.marcarAvisosLeidos();
    expect(f.llamadas[0].opciones.body).toBe('{}');

    await api.marcarAvisosLeidos([1, 2]);
    expect(JSON.parse(f.llamadas[1].opciones.body)).toEqual({ ids: [1, 2] });
  });
});

// ----------------------------------------------------------------- derechos del titular
describe('buscar al titular por su correo (capítulo 38)', () => {
  // La pantalla de derechos exporta y BORRA lo que esta función devuelve. El listado busca
  // por `LIKE` sobre cinco columnas, así que lo que trae no es «la persona de ese correo»
  // sino «todo lo que contiene ese texto en alguna parte». La igualdad la decide aquí, y
  // si no la decidiera nadie se notaría tarde: con una sola persona en la base funciona.
  const ANA = { id: 42, email: 'ana@ejemplo.test', first_name: 'Ana' };
  const DIANA = { id: 43, email: 'diana@ejemplo.test', first_name: 'Diana' };

  it('devuelve la ficha cuyo correo es exactamente el buscado', async () => {
    fetchSimulado({ '/leads': respuesta(200, { items: [DIANA, ANA], total: 2 }) });

    await expect(api.buscarTitularPorCorreo('ana@ejemplo.test')).resolves.toEqual(ANA);
  });

  it('no devuelve a quien solo contiene el correo buscado', async () => {
    // El caso que convierte un derecho en un daño: suprimir a «diana@ejemplo.test» porque
    // alguien pidió el borrado de «ana@ejemplo.test». Es el mismo cuidado que tiene el
    // servicio al rastrear el correo dentro de las cargas del CRM.
    fetchSimulado({ '/leads': respuesta(200, { items: [DIANA], total: 1 }) });

    await expect(api.buscarTitularPorCorreo('ana@ejemplo.test')).resolves.toBeNull();
  });

  it('la igualdad no distingue mayúsculas ni espacios alrededor', async () => {
    fetchSimulado({ '/leads': respuesta(200, { items: [ANA], total: 1 }) });

    await expect(api.buscarTitularPorCorreo('  ANA@Ejemplo.TEST ')).resolves.toEqual(ANA);
  });

  it('pide la página entera que el endpoint admite', async () => {
    // Un `LIKE` sobre un dominio corriente puede traer muchas filas y la que interesa no
    // tiene por qué venir primera: con el tope por omisión de 50 la ficha buscada podía
    // quedarse fuera de la página y la pantalla habría contestado «no consta» sobre una
    // persona que está.
    const f = fetchSimulado({ '/leads': respuesta(200, { items: [], total: 0 }) });

    await api.buscarTitularPorCorreo('ana@ejemplo.test');

    expect(f.llamadas[0].url).toContain('limit=200');
    expect(f.llamadas[0].url).toContain('search=ana%40ejemplo.test');
  });

  it('un correo en blanco no pregunta nada', async () => {
    const f = fetchSimulado({ '/leads': respuesta(200, { items: [ANA], total: 1 }) });

    await expect(api.buscarTitularPorCorreo('   ')).resolves.toBeNull();
    await expect(api.buscarTitularPorCorreo(null)).resolves.toBeNull();
    expect(f.llamadas).toEqual([]);
  });

  it('una respuesta sin lista no revienta: es «no consta»', async () => {
    fetchSimulado({ '/leads': respuesta(200, {}) });

    await expect(api.buscarTitularPorCorreo('ana@ejemplo.test')).resolves.toBeNull();
  });
});

describe('exportar y suprimir al titular (capítulo 38)', () => {
  it('la exportación devuelve el documento del servidor sin tocarlo', async () => {
    const documento = { formato: 'plurione.titular/1', prospecto_id: 42, actividades: [{ id: 1 }] };
    fetchSimulado({ '/leads/42/exportar': respuesta(200, documento) });

    await expect(api.exportarDatosDelTitular(42)).resolves.toEqual(documento);
  });

  it('la supresión acepta el 204 sin cuerpo', async () => {
    // `apiFetch` devuelve `null` ante un 204 en lugar de intentar leer un JSON que no
    // existe. Sin eso, un borrado correcto habría llegado a la pantalla como un error de
    // análisis, y el asesor habría vuelto a pulsar sobre una ficha ya borrada.
    fetchSimulado({ '/leads/42': { ok: true, status: 204, json: async () => { throw new Error('sin cuerpo'); } } });

    await expect(api.suprimirTitular(42)).resolves.toBeNull();
  });

  it('un 403 llega con su código, no como un error cualquiera', async () => {
    fetchSimulado({
      '/leads/42': respuesta(403, { detail: 'No tiene permisos para esta operación.' }),
    });

    await expect(api.suprimirTitular(42)).rejects.toMatchObject({
      status: 403,
      message: 'No tiene permisos para esta operación.',
    });
  });
});
