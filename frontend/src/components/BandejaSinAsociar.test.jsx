// ============================================================================
// La bandeja «Sin asociar»
// ============================================================================
//
// Avisos de las integraciones que no pertenecen a ninguna ficha. Se comprueba que se
// entienden sin conocer los identificadores del servidor, que vincular pide elegir el
// prospecto y enseña lo que le hizo al score, y que descartar —que borra— pide confirmación.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchEventosSinAsociar: vi.fn(),
  vincularEventoSinAsociar: vi.fn(),
  descartarEventoSinAsociar: vi.fn(),
  fetchLeads: vi.fn(),
}));

import {
  descartarEventoSinAsociar,
  fetchEventosSinAsociar,
  fetchLeads,
  vincularEventoSinAsociar,
} from '../services/api';
import BandejaSinAsociar from './BandejaSinAsociar.jsx';

const AVISO = {
  id: 11,
  source: 'whatsapp',
  activity_type: 'WHATSAPP_MESSAGE',
  channel: 'WhatsApp',
  direction: 'ENTRANTE',
  call_outcome: null,
  contact_email: null,
  contact_phone: '+525598765432',
  contact_name: 'Contacto de WhatsApp',
  occurred_at: '2026-09-10T15:00:00Z',
  received_at: '2026-09-10T15:00:05Z',
};

beforeEach(() => {
  fetchEventosSinAsociar.mockReset().mockResolvedValue({ items: [AVISO], total: 1, limit: 50, offset: 0 });
  vincularEventoSinAsociar.mockReset();
  descartarEventoSinAsociar.mockReset().mockResolvedValue(null);
  fetchLeads.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('lo que enseña', () => {
  it('cada aviso con su tipo, su fuente y cómo reconocer a la persona', async () => {
    render(<BandejaSinAsociar />);

    expect(await screen.findByText('Mensaje de WhatsApp')).toBeInTheDocument();
    expect(screen.getByText(/Recibido/)).toBeInTheDocument();
    expect(screen.getByText(/\+525598765432/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Sin asociar.*\(1\)/ })).toBeInTheDocument();
    expect(screen.queryByText('WHATSAPP_MESSAGE')).not.toBeInTheDocument();
  });

  it('dice que no hay nada cuando no hay nada', async () => {
    fetchEventosSinAsociar.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    render(<BandejaSinAsociar />);

    expect(await screen.findByText('No hay avisos pendientes.')).toBeInTheDocument();
  });
});

describe('vincular', () => {
  it('pide elegir el prospecto y enseña lo que el aviso le hizo al score', async () => {
    const usuario = userEvent.setup();
    fetchLeads.mockResolvedValue({
      items: [{ id: 7, first_name: 'Ana', last_name: 'Ruiz', email: 'ana.ruiz@empresa.test', company: 'Empresa' }],
      total: 1,
    });
    vincularEventoSinAsociar.mockResolvedValue({ id: 30, score_anterior: 47.8, score: 51.2, score_category: 'WARM' });
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Vincular' }));
    const busqueda = screen.getByLabelText(/Buscar prospecto/);
    await usuario.clear(busqueda);
    await usuario.type(busqueda, 'Ana');
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }));

    expect(fetchLeads).toHaveBeenCalledWith({ search: 'Ana', limit: 10 });
    await usuario.selectOptions(await screen.findByLabelText('Prospecto al que pertenece:'), '7');
    await usuario.click(screen.getByRole('button', { name: 'Confirmar vinculación' }));

    expect(vincularEventoSinAsociar).toHaveBeenCalledWith(11, 7);
    expect(await screen.findByRole('status')).toHaveTextContent('47,8 → 51,2');
    expect(fetchEventosSinAsociar).toHaveBeenCalledTimes(2);
  });
});

// La confirmación de un borrado, dentro de la página (capítulo 43)
// ----------------------------------------------------------------
// Era un `window.confirm`, y lo que se comprobaba con él era que el `confirm` devolvía
// `false` o `true`: un cuadro del navegador no se puede consultar, así que la prueba
// hablaba con el doble en vez de con la pantalla. Ahora la pregunta está en el documento y
// estas pruebas la leen y pulsan sus botones como lo haría cualquiera.
describe('descartar', () => {
  it('pregunta antes de borrar, y no ha borrado nada mientras pregunta', async () => {
    const usuario = userEvent.setup();
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Descartar' }));

    expect(screen.getByText(/¿Descartar este aviso\?/)).toBeInTheDocument();
    expect(descartarEventoSinAsociar).not.toHaveBeenCalled();
  });

  it('no borra nada si se cancela, y la pregunta se va', async () => {
    const usuario = userEvent.setup();
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Descartar' }));
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByText(/¿Descartar este aviso\?/)).not.toBeInTheDocument();
    expect(descartarEventoSinAsociar).not.toHaveBeenCalled();
  });

  it('borra el aviso confirmado y vuelve a cargar la bandeja', async () => {
    const usuario = userEvent.setup();
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Descartar' }));
    await usuario.click(screen.getByRole('button', { name: 'Sí, descartar' }));

    expect(descartarEventoSinAsociar).toHaveBeenCalledWith(11);
    await waitFor(() => expect(fetchEventosSinAsociar).toHaveBeenCalledTimes(2));
  });

  it('el foco acaba en el botón que confirma, que es lo que hacía el cuadro del navegador', async () => {
    const usuario = userEvent.setup();
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Descartar' }));

    expect(screen.getByRole('button', { name: 'Sí, descartar' })).toHaveFocus();
  });

  it('nada de esta pantalla llama a un cuadro del navegador', async () => {
    const usuario = userEvent.setup();
    // En jsdom `window.confirm` existe y lanza «not implemented», que `userEvent` se come
    // sin que nadie lo vea. El doble lo deja contado.
    const cuadroDelNavegador = vi.fn(() => true);
    vi.stubGlobal('confirm', cuadroDelNavegador);
    vi.stubGlobal('alert', cuadroDelNavegador);
    render(<BandejaSinAsociar />);

    await usuario.click(await screen.findByRole('button', { name: 'Descartar' }));
    await usuario.click(screen.getByRole('button', { name: 'Sí, descartar' }));

    expect(cuadroDelNavegador).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
