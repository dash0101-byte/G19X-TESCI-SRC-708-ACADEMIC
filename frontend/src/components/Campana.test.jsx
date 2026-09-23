import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Campana from './Campana';
import { fetchAvisos, marcarAvisosLeidos } from '../services/api';

vi.mock('../services/api', () => ({
  fetchAvisos: vi.fn(),
  marcarAvisosLeidos: vi.fn(),
}));

function aviso(extra = {}) {
  return {
    id: 1,
    regla: 'hot_sin_contacto',
    regla_etiqueta: 'HOT sin contactar',
    texto: 'Prospecto HOT sin contactar desde hace 24 h.',
    creado_en: new Date(Date.now() - 3600_000).toISOString(),
    leido_en: null,
    prospecto: { id: 10, nombre: 'Rosa Lima', empresa: 'Lima SA', score: 88, categoria: 'HOT' },
    ...extra,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchAvisos.mockResolvedValue({ sin_leer: 1, avisos: [aviso()] });
  marcarAvisosLeidos.mockResolvedValue({ leidos: 1 });
});

describe('La campana', () => {
  it('enseña cuántos hay sin leer', async () => {
    render(<Campana onSelectLead={vi.fn()} />);

    expect(await screen.findByRole('button', { name: 'Avisos: 1 sin leer' })).toBeInTheDocument();
  });

  it('con muchos, el contador no se desborda', async () => {
    fetchAvisos.mockResolvedValue({ sin_leer: 42, avisos: [] });
    render(<Campana onSelectLead={vi.fn()} />);

    expect(await screen.findByText('9+')).toBeInTheDocument();
  });

  it('sin nada que contar, la campana no lleva número', async () => {
    fetchAvisos.mockResolvedValue({ sin_leer: 0, avisos: [] });
    render(<Campana onSelectLead={vi.fn()} />);

    expect(await screen.findByRole('button', { name: 'Avisos: ninguno sin leer' })).toBeInTheDocument();
  });

  it('al abrirla vuelve a preguntar', async () => {
    // Entre que se pintó el panel y que alguien mira la campana puede haber corrido la
    // pasada diaria.
    render(<Campana onSelectLead={vi.fn()} />);
    await screen.findByRole('button', { name: /Avisos:/ });

    await userEvent.click(screen.getByRole('button', { name: /Avisos:/ }));

    expect(await screen.findByRole('dialog', { name: 'Avisos' })).toBeInTheDocument();
    expect(fetchAvisos).toHaveBeenCalledTimes(2);
  });

  it('cada aviso dice de quién habla y qué pasó', async () => {
    render(<Campana onSelectLead={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    expect(screen.getByText(/Rosa Lima · Lima SA/)).toBeInTheDocument();
    expect(screen.getByText(/sin contactar desde hace 24 h/)).toBeInTheDocument();
  });

  it('abrir un aviso lo da por leído y lleva a la ficha', async () => {
    // Obligar a marcarlo aparte convertiría la campana en una segunda lista de pendientes
    // que también habría que vaciar a mano.
    const onSelectLead = vi.fn();
    render(<Campana onSelectLead={onSelectLead} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    await userEvent.click(screen.getByRole('button', { name: /Rosa Lima/ }));

    await waitFor(() => expect(marcarAvisosLeidos).toHaveBeenCalledWith([1]));
    expect(onSelectLead).toHaveBeenCalledWith(10);
  });

  it('si el marcado falla, la ficha se abre igual', async () => {
    // Lo que se pidió fue abrir al prospecto; que no se pudiera anotar la lectura no
    // puede impedirlo.
    marcarAvisosLeidos.mockRejectedValue(new Error('sin red'));
    const onSelectLead = vi.fn();
    render(<Campana onSelectLead={onSelectLead} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    await userEvent.click(screen.getByRole('button', { name: /Rosa Lima/ }));

    await waitFor(() => expect(onSelectLead).toHaveBeenCalledWith(10));
  });

  it('uno ya leído no se vuelve a marcar al abrirlo', async () => {
    fetchAvisos.mockResolvedValue({ sin_leer: 0, avisos: [aviso({ leido_en: new Date().toISOString() })] });
    render(<Campana onSelectLead={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    await userEvent.click(screen.getByRole('button', { name: /Rosa Lima/ }));

    expect(marcarAvisosLeidos).not.toHaveBeenCalled();
  });

  it('se pueden marcar todos de una vez', async () => {
    render(<Campana onSelectLead={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));
    fetchAvisos.mockResolvedValue({ sin_leer: 0, avisos: [aviso({ leido_en: new Date().toISOString() })] });

    await userEvent.click(screen.getByRole('button', { name: 'Marcar todos como leídos' }));

    await waitFor(() => expect(marcarAvisosLeidos).toHaveBeenCalledWith());
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Marcar todos como leídos' })).not.toBeInTheDocument(),
    );
  });

  it('sin avisos, el panel lo dice en vez de quedarse en blanco', async () => {
    fetchAvisos.mockResolvedValue({ sin_leer: 0, avisos: [] });
    render(<Campana onSelectLead={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    expect(screen.getByText('Nada que contar por ahora.')).toBeInTheDocument();
  });

  it('se cierra al pulsar fuera', async () => {
    // Sin esto se queda abierta tapando la tabla, y hay que volver al icono, que es justo
    // donde nadie mira.
    render(
      <div>
        <Campana onSelectLead={vi.fn()} />
        <button type="button">otra cosa</button>
      </div>,
    );
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));
    expect(screen.getByRole('dialog', { name: 'Avisos' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'otra cosa' }));

    expect(screen.queryByRole('dialog', { name: 'Avisos' })).not.toBeInTheDocument();
  });

  it('si no se pueden cargar, lo dice', async () => {
    fetchAvisos.mockRejectedValue(new Error('Error al cargar los avisos'));
    render(<Campana onSelectLead={vi.fn()} />);
    await userEvent.click(await screen.findByRole('button', { name: /Avisos:/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Error al cargar los avisos');
  });
});
