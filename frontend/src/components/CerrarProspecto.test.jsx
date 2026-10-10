import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CerrarProspecto from './CerrarProspecto';
import { cerrarProspecto, fetchOpcionesDeCierre } from '../services/api';

vi.mock('../services/api', () => ({
  fetchOpcionesDeCierre: vi.fn(),
  cerrarProspecto: vi.fn(),
}));

const OPCIONES = {
  resultados: [
    {
      clave: 'ganado',
      etiqueta: 'Ganado',
      pide_tramo: true,
      motivos: [
        { clave: 'precio', etiqueta: 'Precio', descripcion: 'Nuestra propuesta económica fue la que encajó.' },
        { clave: 'otro', etiqueta: 'Otro motivo', descripcion: 'Ninguno de los anteriores.' },
      ],
    },
    {
      clave: 'perdido',
      etiqueta: 'Perdido',
      pide_tramo: false,
      motivos: [
        { clave: 'eligio_a_otro', etiqueta: 'Eligió a otro', descripcion: 'Se decidió por otro proveedor.' },
        { clave: 'no_contesto', etiqueta: 'Dejó de contestar', descripcion: 'Se perdió el contacto.' },
      ],
    },
  ],
  tramos: [
    { clave: 'hasta_100k', etiqueta: 'Hasta 100 000 MXN' },
    { clave: 'no_consta', etiqueta: 'Todavía no consta' },
  ],
};

const LEAD = { id: 7, first_name: 'Rosa', last_name: 'Lima' };

beforeEach(() => {
  vi.clearAllMocks();
  fetchOpcionesDeCierre.mockResolvedValue(OPCIONES);
  cerrarProspecto.mockResolvedValue({
    lead_id: 7,
    resultado: 'perdido',
    resultado_etiqueta: 'Perdido',
    motivo: 'no_contesto',
    motivo_etiqueta: 'Dejó de contestar',
    tareas_descartadas: 2,
  });
});

describe('Cerrar un prospecto', () => {
  it('las listas de motivos vienen del servidor, no escritas en el cliente', async () => {
    // Cuando el formulario llevaba sus propias listas, añadir una opción exigía tocar dos
    // sitios y olvidarse de uno no rompía nada: la opción dejaba de existir para el panel.
    render(<CerrarProspecto lead={LEAD} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));

    expect(fetchOpcionesDeCierre).toHaveBeenCalled();
    expect(screen.getByRole('option', { name: 'Eligió a otro' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Dejó de contestar' })).toBeInTheDocument();
  });

  it('no hay ni un campo de texto donde escribir el motivo', async () => {
    // La regla del capítulo. Un texto libre no se puede contar —«precio», «muy caro» y «no
    // le cuadraba el costo» son tres filas distintas— y acaba llevando lo que una persona
    // dijo por teléfono a la tabla que alimenta al modelo.
    render(<CerrarProspecto lead={LEAD} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Ganado' }));

    expect(screen.queryByRole('textbox')).toBeNull();
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('un ganado pide el tramo del acuerdo y un perdido no', async () => {
    // Un trato perdido no tiene tamaño. Pedirlo invitaría a anotar «lo que habríamos
    // facturado», que es una previsión de ingresos inventada.
    render(<CerrarProspecto lead={LEAD} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Ganado' }));
    expect(screen.getByLabelText('Tamaño del acuerdo')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Perdido' }));
    expect(screen.queryByLabelText('Tamaño del acuerdo')).toBeNull();
  });

  it('cambiar de desenlace no conserva el motivo del anterior', async () => {
    // Los motivos de un ganado no son los de un perdido: conservarlo dejaría seleccionada
    // una opción que ya no está en la lista, y el envío se iría con ella.
    render(<CerrarProspecto lead={LEAD} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));
    await userEvent.selectOptions(screen.getByLabelText('¿Por qué?'), 'no_contesto');
    await userEvent.click(screen.getByRole('button', { name: 'Ganado' }));

    expect(screen.getByLabelText('¿Por qué?')).toHaveValue('');
  });

  it('manda el desenlace con su motivo y su fecha, y avisa de lo que se descartó', async () => {
    const onCerrado = vi.fn();
    render(<CerrarProspecto lead={LEAD} onCerrado={onCerrado} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));
    await userEvent.selectOptions(screen.getByLabelText('¿Por qué?'), 'no_contesto');
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar el prospecto' }));

    await waitFor(() => expect(cerrarProspecto).toHaveBeenCalled());
    const [leadId, cuerpo] = cerrarProspecto.mock.calls[0];
    expect(leadId).toBe(7);
    expect(cuerpo.resultado).toBe('perdido');
    expect(cuerpo.motivo).toBe('no_contesto');
    expect(cuerpo.cerrado_el).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // Un perdido no manda tramo: el servidor lo rechazaría con un 422.
    expect(cuerpo).not.toHaveProperty('tramo');
    // Con su propia espera: la ficha se recarga DESPUÉS de que el cierre conteste, y el
    // `waitFor` de arriba se cumple en cuanto la llamada sale.
    await waitFor(() => expect(onCerrado).toHaveBeenCalled());
  });

  it('no deja cerrar sin elegir motivo', async () => {
    render(<CerrarProspecto lead={LEAD} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));

    expect(screen.getByRole('button', { name: 'Cerrar el prospecto' })).toBeDisabled();
  });

  it('un ganado sin tramo tampoco se puede enviar', async () => {
    render(<CerrarProspecto lead={LEAD} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Ganado' }));
    await userEvent.selectOptions(screen.getByLabelText('¿Por qué?'), 'precio');

    expect(screen.getByRole('button', { name: 'Cerrar el prospecto' })).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText('Tamaño del acuerdo'), 'no_consta');
    expect(screen.getByRole('button', { name: 'Cerrar el prospecto' })).toBeEnabled();
  });

  it('la fecha por defecto es hoy y no admite el futuro', async () => {
    // Una fecha de cierre posterior a hoy no es un caso de negocio, es una errata; el
    // servidor la rechaza y el formulario ni siquiera la ofrece.
    render(<CerrarProspecto lead={LEAD} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));

    const campo = screen.getByLabelText('¿Qué día se cerró?');
    expect(campo).toHaveAttribute('max', campo.value);
  });

  it('el error del servidor se enseña tal cual', async () => {
    cerrarProspecto.mockRejectedValue(new Error('La fecha de cierre es anterior al alta.'));
    render(<CerrarProspecto lead={LEAD} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Perdido' }));
    await userEvent.selectOptions(screen.getByLabelText('¿Por qué?'), 'no_contesto');
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar el prospecto' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('anterior al alta');
  });
});
