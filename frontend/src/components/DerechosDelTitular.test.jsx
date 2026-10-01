// ============================================================================
// La pantalla de los derechos del titular
// ============================================================================
//
// Lo que se comprueba aquí es lo que distingue una pantalla de un formulario con tres
// botones encima de una API que ya existía:
//
// 1. **Que no sea un oráculo.** Un correo que no consta y uno que acaba de suprimirse
//    responden lo mismo, palabra por palabra. Es la propiedad que hace que la pantalla no
//    sirva para averiguar quién figura en la base consultando correos uno a uno, y es la
//    única que se rompe sola: basta con que a alguien le parezca más útil decir «ya se
//    suprimió».
// 2. **Que la igualdad del correo la decida el cliente.** El listado busca por `LIKE`:
//    pedir «ana@x.com» trae también a «diana@x.com». Una pantalla que exportara o borrara
//    la primera fila de esa búsqueda entregaría —o destruiría— los datos de otra persona.
// 3. **Que el borrado exija escribir.** No una casilla ni un «¿seguro?»: el correo entero.
// 4. **Que avise de lo que no hace.** Suprimir aquí no suprime en el CRM, y eso tiene que
//    estar delante de los ojos de quien pulsa, no en un documento de congelación.
// 5. **Que un asesor no la alcance.** El servidor ya le responde 403 a los dos endpoints
//    (`test_un_asesor_no_exporta_ni_suprime`); esto comprueba la otra mitad, que es no
//    ofrecerle un formulario cuyos botones van a fallar.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import * as api from '../services/api';
import DerechosDelTitular from './DerechosDelTitular.jsx';

const CORREO = 'ana.titular@ejemplo.test';
const FICHA = { id: 42, email: CORREO, first_name: 'Ana', last_name: 'Titular' };

const DOCUMENTO = {
  formato: 'plurione.titular/1',
  generado_en: '2026-10-01T12:00:00+00:00',
  prospecto_id: 42,
  datos_del_prospecto: {
    id: 42,
    first_name: 'Ana',
    last_name: 'Titular',
    email: CORREO,
    phone: '+525512345678',
    company: 'Conservas Titular',
    job_title: 'CTO',
    source: 'WhatsApp',
    privacy_notice_accepted_at: '2026-09-20T09:30:00+00:00',
    privacy_notice_source: 'pagina_de_interes',
  },
  campana: { id: 5, name: 'Post · Talento TI septiembre', channel: 'LinkedIn' },
  asesor_asignado: { id: 3, nombre: 'Laura Líder' },
  actividades: [{ id: 1 }, { id: 2 }, { id: 3 }],
  historial_de_puntuacion: [{ id: 1 }, { id: 2 }],
  resumen_mensual_de_puntuacion: [],
  integraciones_crm: [{ id: 7 }],
  entregas_de_webhook: [],
  tareas: [{ id: 9 }],
  avisos: [],
  desenlace: [],
  integraciones_crm_sin_vincular: [],
  eventos_sin_asociar: [],
  tratamientos_registrados: [{ accion: 'lead.crear' }],
  conservacion: { resto_de_datos: 'Mientras el prospecto exista.' },
  fuera_de_la_base: [
    'Copias de seguridad: los volcados diarios conservan los datos.',
    'Sistemas de origen: los datos pudieron llegar desde un CRM. Suprimirlos aquí no los '
    + 'suprime allí.',
  ],
};

// Las secciones que la pantalla tiene que enseñar: las listas de REGISTROS del documento.
// `fuera_de_la_base` también es una lista y no entra, porque lo que lleva dentro son tres
// frases y no tres registros de esta persona; tiene su propio bloque y su propia prueba.
const SECCIONES = Object.entries(DOCUMENTO)
  .filter(([, valor]) => Array.isArray(valor) && valor.every((e) => e && typeof e === 'object'))
  .map(([clave]) => clave.replace(/_/g, ' '));

function montar() {
  return render(<DerechosDelTitular />);
}

/**
 * El texto de un `Blob`, leído como lo leería el navegador.
 *
 * `blob.text()` no existe en `jsdom`, pero `FileReader` sí. Es el único sitio de la suite
 * del cliente donde hace falta y no merece un ayudante compartido.
 */
function textoDelBlob(blob) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(lector.result);
    lector.onerror = () => reject(lector.error);
    lector.readAsText(blob);
  });
}

async function consultar(usuario, correo = CORREO) {
  await usuario.type(screen.getByLabelText('Correo de la persona'), correo);
  await usuario.click(screen.getByRole('button', { name: 'Consultar qué consta' }));
}

beforeEach(() => {
  for (const clave of Object.keys(api)) {
    if (typeof api[clave]?.mockReset === 'function') api[clave].mockReset();
  }
  api.getCurrentUserRole.mockReturnValue('Sales_Lead');
  api.getCurrentUser.mockReturnValue({ id: 3, email: 'lider@plurione.test', role: 'Sales_Lead' });
  // `buscarTitularPorCorreo` es del módulo simulado: su comportamiento real —la igualdad
  // exacta sobre el resultado del `LIKE`— se prueba en `api.test.js`, contra `fetch`.
  api.buscarTitularPorCorreo.mockResolvedValue(FICHA);
  api.exportarDatosDelTitular.mockResolvedValue(DOCUMENTO);
  api.suprimirTitular.mockResolvedValue(null);

  // `jsdom` no implementa ni los objetos URL de un blob ni la navegación de un enlace de
  // descarga. Se sustituyen las tres cosas para poder comprobar QUÉ se descarga.
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:prueba');
  globalThis.URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

// ---------------------------------------------------------------------------
// Antes de pulsar nada
// ---------------------------------------------------------------------------

describe('antes de consultar', () => {
  it('dice qué hace cada una de las tres acciones', () => {
    montar();

    for (const accion of ['Consultar', 'Descargar', 'Suprimir']) {
      expect(screen.getByText(accion, { selector: 'dt' })).toBeInTheDocument();
    }
    expect(screen.getByText(/queda en la bitácora con quién la pidió y cuándo/)).toBeInTheDocument();
    expect(screen.getByText(/No tiene vuelta atrás/)).toBeInTheDocument();
    expect(screen.getByText(/no borra nada en el CRM/)).toBeInTheDocument();
  });

  it('no ofrece ni descarga ni supresión mientras no se ha consultado a nadie', () => {
    montar();

    expect(screen.queryByRole('button', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Suprimir/ })).not.toBeInTheDocument();
  });

  it('las dos regiones vivas están en el documento desde el principio', () => {
    // Un lector de pantalla anuncia lo que CAMBIA dentro de una región que ya estaba. Una
    // región creada junto a su texto no se lee, y es el fallo que el capítulo 36 encontró
    // en el acuse de la página pública.
    montar();

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// La consulta
// ---------------------------------------------------------------------------

describe('la consulta de una persona que está', () => {
  it('enseña quién es, de dónde llegó y qué guarda el sistema', async () => {
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);

    await screen.findByText('Ana Titular');
    expect(screen.getByText(CORREO, { selector: 'div' })).toBeInTheDocument();
    expect(screen.getByText('WhatsApp')).toBeInTheDocument();
    expect(screen.getByText(/Post · Talento TI septiembre/)).toBeInTheDocument();
    expect(screen.getByText(/Aviso de privacidad aceptado el 2026-09-20/)).toBeInTheDocument();
  });

  it('los recuentos y las secciones salen del documento, no de una lista escrita aquí', async () => {
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);
    await screen.findByText('Ana Titular');

    // Las dos propiedades que importan: están TODAS las secciones de registros del
    // documento, y ninguna más. Una tabla nueva en el mapa de la supresión aparece aquí sin
    // tocar la pantalla; y una sección que la pantalla enseñara y el documento no traiga
    // sería un invento.
    const filas = screen.getAllByRole('row').slice(1);
    expect(filas.map((f) => f.cells[0].textContent)).toEqual(SECCIONES);

    const actividades = filas.find((f) => f.cells[0].textContent === 'actividades');
    expect(actividades.cells[1]).toHaveTextContent('3');
  });

  it('enseña lo que ni la consulta ni la supresión alcanzan, tal como lo dice el servidor', async () => {
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);
    await screen.findByText('Ana Titular');

    for (const linea of DOCUMENTO.fuera_de_la_base) {
      expect(screen.getByText(linea)).toBeInTheDocument();
    }
  });

  it('la consulta ES la entrega: pide la exportación al servidor y queda su asiento', async () => {
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);
    await screen.findByText('Ana Titular');

    // No se espera a que alguien pulse «Descargar» para pedírsela al servidor: enseñar un
    // resumen de los datos de una persona ya es entregárselos a quien mira la pantalla, y
    // el asiento `lead.exportar` tiene que existir desde ese momento.
    expect(api.exportarDatosDelTitular).toHaveBeenCalledWith(FICHA.id);
  });

  it('el correo se busca normalizado, no tal como se escribió', async () => {
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario, '  Ana.Titular@Ejemplo.TEST  ');
    await screen.findByText('Ana Titular');

    expect(api.buscarTitularPorCorreo).toHaveBeenCalledWith(CORREO);
  });
});

describe('la consulta de una persona que no está', () => {
  it('contesta el mismo panel, sin datos y sin decir que no existe', async () => {
    api.buscarTitularPorCorreo.mockResolvedValue(null);
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario, 'nadie@ejemplo.test');

    await screen.findByText('No consta ninguna ficha con esta dirección.');
    expect(screen.getByText(/Lo que consta de/)).toBeInTheDocument();
    // Ni error, ni «no existe», ni «no encontrado».
    expect(screen.getByRole('alert')).toBeEmptyDOMElement();
    expect(screen.queryByText(/no existe/i)).not.toBeInTheDocument();
    // Y no se le pide al servidor la exportación de nada.
    expect(api.exportarDatosDelTitular).not.toHaveBeenCalled();
  });

  it('dice que la respuesta es la misma para quien nunca entró y para quien ya se fue', async () => {
    api.buscarTitularPorCorreo.mockResolvedValue(null);
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario, 'nadie@ejemplo.test');

    expect(
      await screen.findByText(/la misma para una dirección que nunca entró y para una cuya/),
    ).toBeInTheDocument();
  });

  it('tampoco ofrece descargar ni suprimir', async () => {
    api.buscarTitularPorCorreo.mockResolvedValue(null);
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario, 'nadie@ejemplo.test');
    await screen.findByText('No consta ninguna ficha con esta dirección.');

    expect(screen.queryByRole('button', { name: /Descargar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Suprimir/ })).not.toBeInTheDocument();
  });

  it('un fallo del servidor sí se anuncia, y no se confunde con «no consta»', async () => {
    api.buscarTitularPorCorreo.mockRejectedValue(new Error('El servidor no responde.'));
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);

    expect(await screen.findByRole('alert')).toHaveTextContent('El servidor no responde.');
    expect(screen.queryByText('No consta ninguna ficha con esta dirección.')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// La descarga
// ---------------------------------------------------------------------------

describe('la descarga del archivo', () => {
  it('guarda el documento del servidor sin recomponerlo', async () => {
    const usuario = userEvent.setup();
    montar();
    await consultar(usuario);
    await screen.findByText('Ana Titular');

    await usuario.click(screen.getByRole('button', { name: 'Descargar el archivo con sus datos' }));

    expect(globalThis.URL.createObjectURL).toHaveBeenCalledTimes(1);
    const blob = globalThis.URL.createObjectURL.mock.calls[0][0];
    expect(JSON.parse(await textoDelBlob(blob))).toEqual(DOCUMENTO);
  });

  it('el archivo se entrega al navegador y la URL del blob se suelta', async () => {
    const usuario = userEvent.setup();
    montar();
    await consultar(usuario);
    await screen.findByText('Ana Titular');

    await usuario.click(screen.getByRole('button', { name: 'Descargar el archivo con sus datos' }));

    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled();
    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith('blob:prueba');
  });

  it('si el navegador no deja guardar, lo dice en vez de callarse', async () => {
    // Lo peor que puede pasar con una exportación de datos personales es que parezca
    // hecha: la persona se iría creyendo que tiene su copia.
    globalThis.URL.createObjectURL = vi.fn(() => { throw new Error('bloqueado'); });
    const usuario = userEvent.setup();
    montar();
    await consultar(usuario);
    await screen.findByText('Ana Titular');

    await usuario.click(screen.getByRole('button', { name: 'Descargar el archivo con sus datos' }));

    expect(screen.getByRole('alert')).toHaveTextContent(/no dejó guardar el archivo/);
  });
});

// ---------------------------------------------------------------------------
// La supresión
// ---------------------------------------------------------------------------

describe('la supresión', () => {
  async function abrirSupresion(usuario) {
    await consultar(usuario);
    await screen.findByText('Ana Titular');
    await usuario.click(screen.getByRole('button', { name: 'Suprimir estos datos…' }));
  }

  it('los dos botones de suprimir se ven como acciones destructivas, y el blanco deja de significar borrar', async () => {
    // El que abre la supresión era `btn` a secas —sin fondo ni borde, el elemento menos
    // visible de la pantalla— y el que la confirma era `btn-primary`, el mismo blanco que
    // «Buscar». En esta paleta el blanco significa «la acción esperada de esta pantalla»,
    // y borrar los datos de una persona no lo es. Los dos pasan al color de acción
    // destructiva que el capítulo 39 metió en la paleta (§6.4 punto 31).
    const usuario = userEvent.setup();
    montar();

    await consultar(usuario);
    await screen.findByText('Ana Titular');
    const abrir = screen.getByRole('button', { name: 'Suprimir estos datos…' });
    expect(abrir).toHaveClass('btn-danger');

    await usuario.click(abrir);
    const confirmar = screen.getByRole('button', { name: 'Suprimir definitivamente' });
    expect(confirmar).toHaveClass('btn-danger');
    expect(confirmar).not.toHaveClass('btn-primary');
    // Y sigue apagado hasta que se escriba el correo: el color no sustituye a la
    // confirmación escrita, se suma a ella.
    expect(confirmar).toBeDisabled();
  });

  it('dice qué se borra, qué no y que el CRM no se entera', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);

    expect(screen.getByText(/Se borran la ficha y los registros de la lista de arriba/)).toBeInTheDocument();
    expect(screen.getByText(/De la bitácora no se borra ningún asiento/)).toBeInTheDocument();
    expect(screen.getByText(/Suprimir aquí no suprime en el CRM/)).toBeInTheDocument();
    expect(screen.getAllByText(/No se puede deshacer/).length).toBeGreaterThan(0);
  });

  it('no promete un número de registros borrados', async () => {
    // Sumar la tabla daría un total que incluye los asientos de la bitácora, y esos no se
    // borran: se les retiran los datos. Un número que no es el que ocurre es peor que
    // ninguno, porque el que se da acaba en la constancia de la persona.
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);

    expect(screen.queryByText(/\d+ registros/)).not.toBeInTheDocument();
  });

  it('no se puede suprimir sin escribir el correo', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);

    expect(screen.getByRole('button', { name: 'Suprimir definitivamente' })).toBeDisabled();
    await usuario.click(screen.getByRole('button', { name: 'Suprimir definitivamente' }));
    expect(api.suprimirTitular).not.toHaveBeenCalled();
  });

  it('un correo escrito a medias no vale', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), 'ana.titular@ejemplo');

    expect(screen.getByRole('button', { name: 'Suprimir definitivamente' })).toBeDisabled();
  });

  it('con el correo escrito, suprime y deja la constancia', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), CORREO);
    await usuario.click(screen.getByRole('button', { name: 'Suprimir definitivamente' }));

    await waitFor(() => expect(api.suprimirTitular).toHaveBeenCalledWith(FICHA.id));

    // La constancia es el último blob que se descargó.
    const blobs = globalThis.URL.createObjectURL.mock.calls;
    const constancia = JSON.parse(await textoDelBlob(blobs[blobs.length - 1][0]));
    expect(constancia.formato).toBe('plurione.constancia-de-supresion/1');
    expect(constancia.titular).toBe(CORREO);
    expect(constancia.prospecto_id).toBe(42);
    expect(constancia.solicitado_por).toBe('lider@plurione.test');
    expect(constancia.lo_que_habia.actividades).toBe(3);
    expect(constancia.lo_que_no_se_suprime).toEqual(DOCUMENTO.fuera_de_la_base);
    // De dónde salen los recuentos, dicho en el propio archivo.
    expect(constancia.procedencia_de_los_recuentos).toMatch(/lead\.eliminar/);
  });

  it('el aviso posterior recuerda que en el CRM los datos siguen estando', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), CORREO);
    await usuario.click(screen.getByRole('button', { name: 'Suprimir definitivamente' }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/siguen estando/));
  });

  it('después de suprimir, la pantalla contesta lo mismo que si nunca hubiera entrado', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), CORREO);
    await usuario.click(screen.getByRole('button', { name: 'Suprimir definitivamente' }));

    // Esta es la prueba del oráculo. Si algún día la pantalla dijera «suprimida el 1 de
    // octubre», bastaría recorrer una lista de correos para saber quién pidió el borrado,
    // que es precisamente lo que la huella con clave de la bitácora evita.
    await screen.findByText('No consta ninguna ficha con esta dirección.');
    expect(screen.queryByText('Ana Titular')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Suprimir/ })).not.toBeInTheDocument();
  });

  it('un fallo al suprimir se anuncia y no se finge que se borró', async () => {
    api.suprimirTitular.mockRejectedValue(new Error('El prospecto está fuera de su alcance.'));
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), CORREO);
    await usuario.click(screen.getByRole('button', { name: 'Suprimir definitivamente' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('fuera de su alcance');
    expect(screen.getByText('Ana Titular')).toBeInTheDocument();
  });

  it('cancelar cierra el bloque y olvida lo escrito', async () => {
    const usuario = userEvent.setup();
    montar();

    await abrirSupresion(usuario);
    await usuario.type(screen.getByLabelText(/Escriba el correo completo/), CORREO);
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }));
    await usuario.click(screen.getByRole('button', { name: 'Suprimir estos datos…' }));

    expect(screen.getByLabelText(/Escriba el correo completo/)).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Suprimir definitivamente' })).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Quién la ve
// ---------------------------------------------------------------------------

describe('un asesor comercial', () => {
  it('no alcanza la pantalla de derechos', () => {
    api.getCurrentUserRole.mockReturnValue('Commercial_Executive');
    const { container } = montar();

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByLabelText('Correo de la persona')).not.toBeInTheDocument();
  });

  it('y el líder y el administrador sí', () => {
    for (const rol of ['Sales_Lead', 'System_Admin']) {
      api.getCurrentUserRole.mockReturnValue(rol);
      const { unmount } = montar();
      expect(screen.getByLabelText('Correo de la persona'), rol).toBeInTheDocument();
      unmount();
    }
  });

  it('sin sesión tampoco se dibuja', () => {
    api.getCurrentUserRole.mockReturnValue(null);
    const { container } = montar();

    expect(container).toBeEmptyDOMElement();
  });
});
