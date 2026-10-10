import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BandejaDeHoy from './BandejaDeHoy';
import { fetchBandejaDeHoy, fetchHotQueSeEnfrian, marcarTareaHecha } from '../services/api';

vi.mock('../services/api', () => ({
  fetchBandejaDeHoy: vi.fn(),
  fetchHotQueSeEnfrian: vi.fn(),
  marcarTareaHecha: vi.fn(),
}));

const EN_DOS_HORAS = new Date(Date.now() + 2 * 3600_000).toISOString();
const HACE_CINCO_HORAS = new Date(Date.now() - 5 * 3600_000).toISOString();

function tarea(extra = {}) {
  return {
    id: 1,
    regla: 'primer_contacto',
    regla_etiqueta: 'Primer contacto',
    motivo: 'Asignado y todavía sin contactar.',
    estado: 'abierta',
    vence_el: EN_DOS_HORAS,
    vencida: false,
    creada_en: HACE_CINCO_HORAS,
    prospecto: { id: 10, nombre: 'Rosa Lima', empresa: 'Lima SA', score: 72, categoria: 'HOT' },
    ...extra,
  };
}

function bandeja(extra = {}) {
  return { asesor_id: 3, tareas: [tarea()], vencidas: 0, para_hoy: 1, mas_adelante: 0, ...extra };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchBandejaDeHoy.mockResolvedValue(bandeja());
  fetchHotQueSeEnfrian.mockResolvedValue({ total: 0, filas: [] });
  marcarTareaHecha.mockResolvedValue({ id: 1, estado: 'hecha', cerrada_en: new Date().toISOString() });
});

describe('La bandeja de hoy', () => {
  it('dice qué hay que hacer, por qué y con quién', async () => {
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);

    expect(await screen.findByText('Llamar por primera vez')).toBeInTheDocument();
    expect(screen.getByText(/Asignado y todavía sin contactar/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Rosa Lima/ })).toBeInTheDocument();
  });

  it('el nombre abre la ficha del prospecto', async () => {
    // Es el camino corto entre «esto hay que hacerlo» y el teléfono, que está en la ficha
    // y no aquí: la bandeja es una lista de trabajo, no un directorio.
    const onSelectLead = vi.fn();
    render(<BandejaDeHoy onSelectLead={onSelectLead} />);

    await userEvent.click(await screen.findByRole('button', { name: /Rosa Lima/ }));

    expect(onSelectLead).toHaveBeenCalledWith(10);
  });

  it('marca lo vencido sin sacarlo de su sitio', async () => {
    fetchBandejaDeHoy.mockResolvedValue(
      bandeja({ tareas: [tarea({ vencida: true, vence_el: HACE_CINCO_HORAS })], vencidas: 1, para_hoy: 0 }),
    );
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);

    expect(await screen.findByText('Vencida')).toBeInTheDocument();
    expect(screen.getByText(/Venció el/)).toBeInTheDocument();
  });

  it('respeta el orden que manda el servidor', async () => {
    // Por score, no por fecha: quien ordenara aquí volvería a poner arriba lo más viejo,
    // que suele ser también lo más frío.
    fetchBandejaDeHoy.mockResolvedValue(
      bandeja({
        tareas: [
          tarea({ id: 1, prospecto: { id: 10, nombre: 'Alta Puntuación', empresa: null, score: 90, categoria: 'HOT' } }),
          tarea({ id: 2, prospecto: { id: 11, nombre: 'Baja Puntuación', empresa: null, score: 12, categoria: 'COLD' } }),
        ],
      }),
    );
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);

    const nombres = (await screen.findAllByRole('button', { name: /Puntuación/ })).map((b) => b.textContent);
    expect(nombres).toEqual(['Alta Puntuación', 'Baja Puntuación']);
  });

  it('cuenta lo de más adelante sin enseñarlo', async () => {
    fetchBandejaDeHoy.mockResolvedValue(bandeja({ tareas: [], para_hoy: 0, mas_adelante: 4 }));
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);

    expect(await screen.findByText(/4 más adelante/)).toBeInTheDocument();
    expect(screen.getByText(/Nada pendiente para hoy/)).toBeInTheDocument();
  });

  it('al cerrar una tarea vuelve a preguntar qué queda', async () => {
    // Y no borra la fila por su cuenta: cerrar una tarea puede hacer que otra deje de
    // tener sentido, y quién sabe eso es el servidor.
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);
    await screen.findByText('Llamar por primera vez');
    fetchBandejaDeHoy.mockResolvedValue(bandeja({ tareas: [], para_hoy: 0 }));

    await userEvent.click(screen.getByRole('button', { name: 'Ya está' }));

    await waitFor(() => expect(marcarTareaHecha).toHaveBeenCalledWith(1));
    // Con su propia espera: volver a preguntar qué queda ocurre DESPUÉS de que el cierre
    // conteste, y el `waitFor` de arriba se cumple en cuanto la llamada sale.
    await waitFor(() => expect(fetchBandejaDeHoy).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('Llamar por primera vez')).not.toBeInTheDocument());
  });

  it('si el cierre falla lo dice y no borra nada', async () => {
    marcarTareaHecha.mockRejectedValue(new Error('No se pudo cerrar'));
    render(<BandejaDeHoy onSelectLead={vi.fn()} />);
    await screen.findByText('Llamar por primera vez');

    await userEvent.click(screen.getByRole('button', { name: 'Ya está' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cerrar');
    expect(screen.getByText('Llamar por primera vez')).toBeInTheDocument();
  });
});

describe('Los HOT que se enfrían', () => {
  it('el asesor ni siquiera los pide', async () => {
    // Su panel no puede depender de una llamada que le va a responder 403.
    render(<BandejaDeHoy onSelectLead={vi.fn()} esDireccion={false} />);
    await screen.findByText('Llamar por primera vez');

    expect(fetchHotQueSeEnfrian).not.toHaveBeenCalled();
    expect(screen.queryByText(/se están enfriando/)).not.toBeInTheDocument();
  });

  it('el líder los ve, y con qué asesor están', async () => {
    fetchHotQueSeEnfrian.mockResolvedValue({
      total: 1,
      filas: [
        {
          prospecto: { id: 20, nombre: 'Elena Soto', empresa: 'Soto SA', score: 88, categoria: 'HOT' },
          asesor_id: 7,
          asesor: 'Carlos Morales',
          horas_sin_contacto: 31,
          avisado_al_asesor: true,
          avisado_al_lider: false,
        },
      ],
    });
    render(<BandejaDeHoy onSelectLead={vi.fn()} esDireccion />);

    expect(await screen.findByText(/se están enfriando/)).toBeInTheDocument();
    expect(screen.getByText(/Elena Soto/)).toBeInTheDocument();
    expect(screen.getByText(/Carlos Morales · 31 h/)).toBeInTheDocument();
  });

  it('si no hay ninguno, la sección no se pinta', async () => {
    render(<BandejaDeHoy onSelectLead={vi.fn()} esDireccion />);
    await screen.findByText('Llamar por primera vez');

    expect(screen.queryByText(/se están enfriando/)).not.toBeInTheDocument();
  });
});
