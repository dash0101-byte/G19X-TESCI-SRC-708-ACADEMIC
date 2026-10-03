// ============================================================================
// La ficha del prospecto: registrar y leer lo que pasó
// ============================================================================
//
// Lo que se comprueba aquí:
//
// * el tipo de interacción se elige en una cuadrícula, sin desplegable, y solo ofrece las
//   conversaciones del asesor: llamada, WhatsApp y LinkedIn;
// * no promete puntos: al registrar se enseña el cambio real del score;
// * una llamada pide su resultado y un mensaje su dirección, también en cuadrícula, y un
//   mensaje no lleva notas;
// * el historial está en español, dice si cada actividad la vio un sistema o la declaró una
//   persona, y ya no enseña un «Peso» que el scoring nunca leyó.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  addLeadActivity: vi.fn(),
  recalculateLeadScore: vi.fn(),
  updateLead: vi.fn(),
  fetchSalesReps: vi.fn(),
  // El reparto de cartera solo se ofrece a quien puede repartir; por defecto, un asesor.
  getCurrentUserRole: vi.fn(() => 'Commercial_Executive'),
}));

import { addLeadActivity, fetchSalesReps, updateLead } from '../services/api';
import LeadDetailModal from './LeadDetailModal.jsx';

function actividad(campos) {
  return {
    channel: 'Web',
    direction: null,
    call_outcome: null,
    external_event_id: null,
    activity_data: {},
    created_at: '2026-09-10T12:00:00Z',
    ...campos,
  };
}

const PROSPECTO = {
  id: 7,
  first_name: 'Ana',
  last_name: 'Ruiz',
  email: 'ana.ruiz@empresa.test',
  phone: '+525512345678',
  company: 'Empresa de Pruebas',
  job_title: 'CTO',
  industry: 'FinTech',
  company_size: '51-200',
  country: 'México',
  status: 'PROPOSAL_SENT',
  score_category: 'WARM',
  current_score: 47.8,
  conversion_probability: 0.41,
  raw_metadata: {},
  latest_explanation: {},
  activities: [
    actividad({ id: 1, activity_type: 'PROPOSAL_SENT', source: 'pipeline', verificada: false, occurred_at: '2026-09-01T10:00:00Z' }),
    actividad({ id: 2, activity_type: 'MEETING_SCHEDULED', source: 'calendly', verificada: true, occurred_at: '2026-09-02T10:00:00Z' }),
    actividad({ id: 3, activity_type: 'PHONE_CALL', source: 'manual', verificada: false, call_outcome: 'BUZON', occurred_at: '2026-09-03T10:00:00Z' }),
  ],
};

function montar(props = {}) {
  const onLeadUpdated = vi.fn();
  render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={onLeadUpdated} {...props} />);
  return { onLeadUpdated };
}

function casilla(grupo, nombre) {
  return within(screen.getByRole('radiogroup', { name: grupo })).getByRole('radio', { name: nombre });
}

const REGISTRAR = { name: /Registrar y Recalcular/ };

beforeEach(() => {
  addLeadActivity.mockReset();
  fetchSalesReps.mockReset().mockResolvedValue({ total: 0, items: [] });
});

describe('la cuadrícula de interacciones', () => {
  it('sustituye al desplegable y ofrece solo las conversaciones del asesor', () => {
    montar();
    const opciones = within(screen.getByRole('radiogroup', { name: 'Tipo de interacción' })).getAllByRole('radio');
    const textos = opciones.map((opcion) => opcion.textContent);

    expect(screen.queryAllByRole('combobox')).toHaveLength(0);
    expect(opciones).toHaveLength(3);
    expect(textos[0]).toMatch(/^Llamada/);
    expect(textos[1]).toMatch(/^Mensaje de WhatsApp/);
    expect(textos[2]).toMatch(/^Mensaje de LinkedIn/);
    expect(textos.some((texto) => /pts?\b|Formulario|demo|webinar|Descarga|Otro evento|Propuesta|Reunión/i.test(texto))).toBe(false);
  });

  it('marca la casilla elegida y solo esa', async () => {
    const usuario = userEvent.setup();
    montar();

    expect(casilla('Tipo de interacción', /^Llamada/)).toHaveAttribute('aria-checked', 'true');
    await usuario.click(casilla('Tipo de interacción', /^Mensaje de WhatsApp/));

    expect(casilla('Tipo de interacción', /^Mensaje de WhatsApp/)).toHaveAttribute('aria-checked', 'true');
    expect(casilla('Tipo de interacción', /^Llamada/)).toHaveAttribute('aria-checked', 'false');
  });
});

describe('registrar', () => {
  it('una llamada no se registra sin su resultado, y al registrarla se enseña el cambio real del score', async () => {
    const usuario = userEvent.setup();
    addLeadActivity.mockResolvedValue({ id: 9, score_anterior: 47.8, score: 58.6, score_category: 'WARM' });
    const { onLeadUpdated } = montar();

    expect(screen.getByRole('button', REGISTRAR)).toBeDisabled();
    await usuario.click(casilla('Resultado de la llamada', 'Conectó'));
    expect(screen.getByRole('button', REGISTRAR)).toBeEnabled();
    await usuario.click(screen.getByRole('button', REGISTRAR));

    expect(addLeadActivity).toHaveBeenCalledWith(7, { activity_type: 'PHONE_CALL', call_outcome: 'CONECTO' });
    expect(await screen.findByRole('status')).toHaveTextContent('47,8 → 58,6');
    expect(onLeadUpdated).toHaveBeenCalled();
  });

  it('un mensaje pide su dirección y no ofrece notas', async () => {
    const usuario = userEvent.setup();
    addLeadActivity.mockResolvedValue({ id: 10, score_anterior: 47.8, score: 49.1, score_category: 'WARM' });
    montar();

    await usuario.click(casilla('Tipo de interacción', /^Mensaje de LinkedIn/));
    expect(screen.queryByLabelText('Notas:')).not.toBeInTheDocument();
    expect(screen.queryByRole('radiogroup', { name: 'Resultado de la llamada' })).not.toBeInTheDocument();
    await usuario.click(casilla('Dirección del mensaje', 'Recibido'));
    await usuario.click(screen.getByRole('button', REGISTRAR));

    expect(addLeadActivity).toHaveBeenCalledWith(7, { activity_type: 'LINKEDIN_MESSAGE', direction: 'ENTRANTE' });
  });

  it('el motivo del rechazo llega a la persona', async () => {
    const usuario = userEvent.setup();
    addLeadActivity.mockRejectedValue(new Error('La fecha del evento está en el futuro.'));
    montar();

    await usuario.click(casilla('Tipo de interacción', /^Mensaje de WhatsApp/));
    await usuario.click(screen.getByRole('button', REGISTRAR));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('La fecha del evento está en el futuro.'));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('el historial', () => {
  it('está en español, marca verificada o declarada y no enseña peso', () => {
    montar();
    const historial = screen.getByRole('list', { name: 'Historial de eventos' });

    expect(within(historial).getByText('Propuesta enviada')).toBeInTheDocument();
    expect(within(historial).getByText('Reunión agendada')).toBeInTheDocument();
    expect(within(historial).getByText('Llamada')).toBeInTheDocument();
    expect(within(historial).getAllByText('verificada')).toHaveLength(1);
    expect(within(historial).getAllByText('declarada')).toHaveLength(2);
    expect(within(historial).getByText(/Buzón de voz/)).toBeInTheDocument();
    expect(within(historial).getByText('Calendly')).toBeInTheDocument();

    expect(screen.queryByText(/PROPOSAL_SENT|MEETING_SCHEDULED|PHONE_CALL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Peso/)).not.toBeInTheDocument();
  });

  it('pone primero lo más reciente', () => {
    montar();
    const elementos = within(screen.getByRole('list', { name: 'Historial de eventos' })).getAllByRole('listitem');
    expect(elementos[0]).toHaveTextContent('Llamada');
    expect(elementos[2]).toHaveTextContent('Propuesta enviada');
  });
});

describe('la etapa', () => {
  it('avisa de que cambiarla registra la actividad y ofrece todas las etapas', () => {
    montar({ startInEditMode: true });

    expect(screen.getByText(/deja la actividad registrada en el historial/)).toBeInTheDocument();
    const etapas = within(screen.getByLabelText('Estado del Prospecto en Pipeline')).getAllByRole('option');
    expect(etapas.map((opcion) => opcion.value)).toEqual(
      expect.arrayContaining(['ENGAGED', 'UNQUALIFIED', 'PROPOSAL_SENT', 'MEETING_SCHEDULED']),
    );
  });
});

describe('la tarjeta «Llegó por»', () => {
  it('no se pinta en una ficha que no llegó por una publicación', () => {
    montar();

    expect(screen.queryByRole('heading', { name: /Llegó por/ })).not.toBeInTheDocument();
  });

  it('con solicitudes, la ficha enseña la publicación y el perfil de LinkedIn', () => {
    montar({
      lead: {
        ...PROSPECTO,
        llego_por: {
          perfil_de_linkedin: 'https://www.linkedin.com/in/ana-ruiz',
          solicitudes: [{
            publicacion_id: 5,
            titulo: 'Post · Talento TI septiembre',
            enlace: 'http://localhost:3000/p/abc',
            recibida_en: '2026-09-17T12:00:00Z',
            necesidad: 'Cubrir vacantes de TI',
            aviso_aceptado_en: '2026-09-17T12:00:00Z',
          }],
        },
      },
    });

    expect(screen.getByRole('heading', { name: /Llegó por/ })).toBeInTheDocument();
    expect(screen.getByText('Post · Talento TI septiembre')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Ver perfil de LinkedIn/ }))
      .toHaveAttribute('href', 'https://www.linkedin.com/in/ana-ruiz');
  });
});

describe('editar una ficha de la página de interés', () => {
  it('sin apellidos escritos no manda un apellido vacío que el servidor rechazaría', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue({ ...PROSPECTO, first_name: 'Ana Ruiz', last_name: '' });
    montar({ lead: { ...PROSPECTO, first_name: 'Ana Ruiz', last_name: '' } });

    await usuario.click(screen.getByRole('button', { name: /Editar Prospecto/ }));
    await usuario.click(screen.getByRole('button', { name: /Guardar/ }));

    await waitFor(() => expect(updateLead).toHaveBeenCalledTimes(1));
    const cambios = updateLead.mock.calls[0][1];
    expect(cambios.first_name).toBe('Ana Ruiz');
    expect(cambios).not.toHaveProperty('last_name', '');
    expect(JSON.parse(JSON.stringify(cambios))).not.toHaveProperty('last_name');
  });
});

// ============================================================================
// Capítulo 33: vaciar un campo es un cambio
// ============================================================================
//
// El servidor ya distingue «no lo mandó» de «lo mandó vacío». Lo que se comprueba aquí es
// la mitad del cliente, que tenía su propia forma de tapar el vacío: omitir el campo.

describe('vaciar un campo desde la ficha', () => {
  const rellena = { ...PROSPECTO, city: 'Monterrey', annual_revenue: 4500000 };

  async function editarYGuardar(usuario, cambios) {
    await usuario.click(screen.getByRole('button', { name: /Editar Prospecto/ }));
    for (const [etiqueta, valor] of cambios) {
      const campo = screen.getByLabelText(etiqueta);
      await usuario.clear(campo);
      if (valor) await usuario.type(campo, valor);
    }
    await usuario.click(screen.getByRole('button', { name: /Guardar/ }));
    await waitFor(() => expect(updateLead).toHaveBeenCalledTimes(1));
    return updateLead.mock.calls[0][1];
  }

  it('manda el vacío de los campos que la ficha admite vaciar', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue({ ...rellena, city: null, company: null });
    montar({ lead: rellena });

    const cambios = await editarYGuardar(usuario, [['Ciudad', ''], ['Empresa', '']]);

    // El país y el tamaño ya viajaban como `null`; la ciudad y la empresa viajan como `""`.
    // Las dos formas son el mismo vacío para el servidor desde este capítulo, y lo que
    // importa es que el campo VIAJE: omitirlo es lo que hacía que no se pudiera borrar.
    expect(cambios.city).toBe('');
    expect(cambios.company).toBe('');
  });

  it('no permite exigir en el formulario lo que la tabla admite vacío', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue(rellena);
    montar({ lead: rellena });
    await usuario.click(screen.getByRole('button', { name: /Editar Prospecto/ }));

    // Mientras «Empresa» y «Cargo» llevaran `required`, el navegador bloqueaba el envío y
    // el panel era más estricto que la API sin decirlo.
    expect(screen.getByLabelText('Empresa')).not.toBeRequired();
    expect(screen.getByLabelText(/Cargo \/ Puesto de Decisión/)).not.toBeRequired();
    // Los que la tabla sí declara obligatorios siguen marcados.
    expect(screen.getByLabelText(/Nombre\(s\)/)).toBeRequired();
    expect(screen.getByLabelText(/Correo Corporativo/)).toBeRequired();
  });

  it('manda el apellido vacío cuando estaba escrito y el asesor lo borra', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue(rellena);
    montar({ lead: rellena });

    const cambios = await editarYGuardar(usuario, [['Apellidos', '']]);

    // Viaja para que el servidor conteste 422 nombrándolo. Omitirlo —lo que se hacía— dejaba
    // la pantalla diciendo «Prospecto actualizado» con el apellido intacto: no es que no
    // obedeciera, es que contestaba que sí.
    expect(cambios.last_name).toBe('');
  });

  it('vacía los ingresos por el mismo camino del capítulo 24, no con un cero', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue({ ...rellena, annual_revenue: null });
    montar({ lead: rellena });

    const cambios = await editarYGuardar(usuario, [[/Ingresos/, '']]);

    // Cero es una cifra: diría que la empresa factura cero y el modelo lo leería como tal.
    expect(cambios.annual_revenue).toBeNull();
    expect(cambios.annual_revenue).not.toBe(0);
  });

  it('tras vaciar no vuelve a enseñar el valor anterior', async () => {
    const usuario = userEvent.setup();
    updateLead.mockReset().mockResolvedValue({
      ...rellena, city: null, company: null, job_title: null, country: null,
    });
    montar({ lead: rellena });

    await editarYGuardar(usuario, [['Ciudad', ''], ['Empresa', '']]);

    await waitFor(() => expect(screen.queryByText(/Empresa de Pruebas/)).not.toBeInTheDocument());
    expect(screen.queryByText(/Monterrey/)).not.toBeInTheDocument();
    // Y la cabecera dice que no hay dato, en vez de quedarse con los separadores sueltos.
    expect(screen.getByText(/Sin empresa/)).toBeInTheDocument();
    expect(screen.getByText(/Sin cargo/)).toBeInTheDocument();
  });
});

// ============================================================================
// Capítulo 40: el 422 de la edición deja de ser un cuadro del navegador
// ============================================================================
//
// Este formulario es el que más razones tiene para recibir un 422: tiene trece campos y es
// el que el capítulo 33 se encargó de que contestara 422 **nombrando el campo** cuando se
// vacía algo que la ficha no puede no tener, en vez del 200 mentiroso que había antes.
//
// Lo que hacía con esa respuesta era `alert('Error al actualizar prospecto: ' +
// err.message)`. Un cuadro del navegador: no se puede poner junto a un campo, no forma
// parte de la página —ningún lector de pantalla lo anuncia como contenido—, tapa
// justamente el formulario que hay que corregir y enseña el nombre de la columna. El
// trabajo del capítulo 33 llegaba hasta el servidor y se perdía en la última pulgada.

describe('un 422 al guardar la ficha', () => {
  function error422(detalle) {
    const err = new Error('Error de validación');
    err.status = 422;
    err.detalle = detalle;
    return err;
  }

  async function guardarYFallar(usuario, detalle) {
    updateLead.mockReset().mockRejectedValue(error422(detalle));
    montar();
    await usuario.click(screen.getByRole('button', { name: /Editar Prospecto/ }));
    await usuario.click(screen.getByRole('button', { name: /Guardar/ }));
    await waitFor(() => expect(updateLead).toHaveBeenCalledTimes(1));
  }

  it('se anuncia en la página y no en un cuadro del navegador', async () => {
    const usuario = userEvent.setup();
    // Si algo volviera a llamar a `alert`, esta prueba lo dice en vez de dejarlo pasar: en
    // jsdom `window.alert` no existe y llamarlo sería un error que nadie vería.
    const cuadroDelNavegador = vi.fn();
    vi.stubGlobal('alert', cuadroDelNavegador);

    await guardarYFallar(usuario, [
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
    ]);

    const aviso = await screen.findByRole('alert');
    expect(aviso.className).toContain('alert-error');
    expect(cuadroDelNavegador).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it('cada queja va debajo de su campo, atada por aria-describedby', async () => {
    const usuario = userEvent.setup();
    await guardarYFallar(usuario, [
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
    ]);

    const nombre = screen.getByLabelText('Nombre(s) *');
    await waitFor(() => expect(nombre).toHaveAttribute('aria-invalid', 'true'));
    const explicacion = document.getElementById(nombre.getAttribute('aria-describedby'));
    expect(explicacion.textContent).toBe('Falta este campo.');
    expect(explicacion.className).toContain('form-error');
  });

  it('el resumen de arriba usa la etiqueta de la pantalla, no la columna', async () => {
    const usuario = userEvent.setup();
    await guardarYFallar(usuario, [
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
      {
        type: 'value_error',
        loc: ['body', 'phone'],
        msg: 'Value error, El teléfono no es un número válido: revise la lada y el número de dígitos.',
      },
    ]);

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Revise estos campos: Nombre\(s\), Teléfono \/ WhatsApp/);
    expect(aviso.textContent).not.toMatch(/first_name/);
  });

  // Capítulo 45: el renglón que no trae el campo en el `loc` acaba igualmente debajo del campo
  // ------------------------------------------------------------------------------------------
  // Este es el 422 que `PUT /leads/{id}` contesta al vaciar un apellido, y hasta el capítulo
  // 45 llegaba con `last_name` escrito **dentro de la frase**: un validador de modelo responde
  // `loc: ['body']`, así que el reparto lo mandaba entero al aviso de arriba, con el nombre de
  // la columna de la base en una pantalla en castellano. El trabajo del 43 —quitar ese nombre—
  // llegaba hasta el prefijo y no hasta aquí.
  it('vaciar un apellido se dice debajo del apellido, y sin nombrar la columna', async () => {
    const usuario = userEvent.setup();
    await guardarYFallar(usuario, [
      {
        type: 'campos_vacios_prohibidos',
        loc: ['body'],
        msg: 'La ficha no existe sin alguno de los campos que llegaron vacíos. '
          + 'Envíe un valor, o no envíe el campo si no quiere cambiarlo.',
        ctx: { campos: ['last_name'] },
      },
    ]);

    const apellidos = screen.getByLabelText('Apellidos');
    await waitFor(() => expect(apellidos).toHaveAttribute('aria-invalid', 'true'));
    const explicacion = document.getElementById(apellidos.getAttribute('aria-describedby'));
    expect(explicacion.textContent).toBe('No puede quedar vacío.');

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Revise el campo Apellidos./);
    expect(aviso.textContent).not.toMatch(/last_name/);
    expect(document.body.textContent).not.toMatch(/last_name/);
  });

  it('y la pantalla se queda en modo edición, con los datos escritos', async () => {
    // Un formulario que se cierra al fallar obliga a volver a escribirlo todo. Antes no se
    // cerraba —el `alert` no cambiaba el modo—, así que esto es una propiedad que había que
    // conservar al cambiar el manejo del error, no una que este capítulo añade.
    const usuario = userEvent.setup();
    await guardarYFallar(usuario, [
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
    ]);

    expect(screen.getByLabelText('Nombre(s) *')).toHaveValue('Ana');
    expect(screen.getByRole('button', { name: /Guardar/ })).not.toBeNull();
  });
});
