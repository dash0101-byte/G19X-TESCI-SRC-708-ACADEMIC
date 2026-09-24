import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PanelDeDesenlaces from './PanelDeDesenlaces';
import { fetchPanelDeDesenlaces } from '../services/api';

vi.mock('../services/api', () => ({ fetchPanelDeDesenlaces: vi.fn() }));

function panel(extra = {}) {
  return {
    desde: null,
    hasta: null,
    resumen: {
      cerrados: 10,
      ganados: 4,
      perdidos: 6,
      tasa_de_ganados: 40.0,
      score_medio_de_los_ganados: 78.5,
      score_medio_de_los_perdidos: 41.2,
    },
    por_motivo: [
      {
        resultado: 'perdido',
        resultado_etiqueta: 'Perdido',
        motivo: 'precio',
        motivo_etiqueta: 'Precio',
        casos: 4,
        porcentaje: 66.7,
        score_medio: 44.0,
      },
    ],
    por_tramo: [{ tramo: 'no_consta', etiqueta: 'Todavía no consta', casos: 2 }],
    por_publicacion: [
      {
        publicacion_id: 5,
        titulo: 'Perfiles TI en octubre',
        ganados: 3,
        perdidos: 2,
        tasa_de_ganados: 60.0,
        score_medio_al_cierre: 70.1,
      },
      {
        publicacion_id: null,
        titulo: 'Sin publicación',
        ganados: 1,
        perdidos: 4,
        tasa_de_ganados: 20.0,
        score_medio_al_cierre: 40.0,
      },
    ],
    por_red: [
      { red: 'whatsapp', etiqueta: 'WhatsApp', ganados: 2, perdidos: 1, tasa_de_ganados: 66.7, score_medio_al_cierre: 68.0 },
    ],
    acierto_del_score: [
      { categoria: 'HOT', casos: 4, ganados: 3, perdidos: 1, tasa_de_ganados: 75.0 },
      { categoria: 'WARM', casos: 6, ganados: 1, perdidos: 5, tasa_de_ganados: 16.7 },
      { categoria: 'COLD', casos: 0, ganados: 0, perdidos: 0, tasa_de_ganados: null },
    ],
    reentrenamiento: {
      cerrados: 12,
      utilizables: 10,
      ganados_utilizables: 4,
      perdidos_utilizables: 6,
      sin_instantanea: 1,
      de_un_vector_anterior: 1,
      version_del_vector: 2,
      minimo_de_casos: 200,
      minimo_por_clase: 50,
      alcanzado: false,
      faltan_casos: 190,
      faltan_ganados: 46,
      faltan_perdidos: 44,
    },
    ...extra,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchPanelDeDesenlaces.mockResolvedValue(panel());
});

describe('El panel de desenlaces', () => {
  it('responde qué se gana, qué se pierde y por qué', async () => {
    render(<PanelDeDesenlaces />);

    expect(await screen.findByText('40 %')).toBeInTheDocument();
    const porMotivo = screen.getByRole('table', { name: 'Cierres por motivo' });
    expect(within(porMotivo).getByRole('rowheader', { name: 'Precio' })).toBeInTheDocument();
    expect(within(porMotivo).getByText('66.7 %')).toBeInTheDocument();
  });

  it('no lleva ni un nombre de persona', async () => {
    // Es la propiedad del capítulo: el panel son totales. Quien necesita ver a las personas
    // tiene el listado y la ficha, donde ese acceso queda registrado como lo que es.
    const { container } = render(<PanelDeDesenlaces />);
    await screen.findByText('40 %');

    expect(container.textContent).not.toMatch(/@/);
  });

  it('cada tasa viaja con los casos que hay detrás', async () => {
    // Con doce cierres, cualquier conclusión sobre la calidad del modelo es una anécdota
    // con decimales. La columna de casos es lo que impide leerla como otra cosa.
    render(<PanelDeDesenlaces />);

    const acierto = await screen.findByRole('table', { name: /categoría de score/ });
    const fila = within(acierto).getByRole('row', { name: /HOT/ });
    expect(within(fila).getByText('4')).toBeInTheDocument();
    expect(within(fila).getByText('75 %')).toBeInTheDocument();
  });

  it('enseña las tres categorías aunque alguna esté vacía', async () => {
    // Aquí sí se enseñan las filas a cero: la pregunta es si los HOT se ganan más que los
    // COLD, y una tabla a la que le falta la fila de los COLD invita a leer la comparación
    // que precisamente no se puede hacer.
    render(<PanelDeDesenlaces />);

    const acierto = await screen.findByRole('table', { name: /categoría de score/ });
    expect(within(acierto).getByRole('rowheader', { name: 'COLD' })).toBeInTheDocument();
    // Sin casos no hay tasa: un 0 % diría que no se gana ninguno, y lo que pasa es que no
    // ha cerrado ninguno.
    expect(within(acierto).getByRole('row', { name: /COLD/ }).textContent).toContain('—');
  });

  it('el contador dice cuánto falta y no ofrece reentrenar', async () => {
    render(<PanelDeDesenlaces />);

    expect(await screen.findByText(/Faltan 190 cierres/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '10');
    expect(screen.queryByRole('button', { name: /reentrenar/i })).toBeNull();
  });

  it('avisa cuando ya hay desenlaces suficientes, sin reentrenar nada', async () => {
    fetchPanelDeDesenlaces.mockResolvedValue(
      panel({
        reentrenamiento: {
          ...panel().reentrenamiento,
          utilizables: 240,
          ganados_utilizables: 90,
          perdidos_utilizables: 150,
          alcanzado: true,
          faltan_casos: 0,
          faltan_ganados: 0,
          faltan_perdidos: 0,
        },
      }),
    );
    render(<PanelDeDesenlaces />);

    expect(await screen.findByText(/Ya hay desenlaces suficientes/)).toBeInTheDocument();
    expect(screen.getByText(/decisión de una persona/)).toBeInTheDocument();
  });

  it('la merma se ve: cuántos cierres no sirven y por qué', async () => {
    render(<PanelDeDesenlaces />);

    expect(await screen.findByText(/no tienen\s+instantánea de entrada/)).toBeInTheDocument();
  });

  it('el periodo se manda al servidor', async () => {
    render(<PanelDeDesenlaces />);
    await screen.findByText('40 %');

    await userEvent.type(screen.getByLabelText('Cerrados desde'), '2026-01-01');

    await waitFor(() =>
      expect(fetchPanelDeDesenlaces).toHaveBeenLastCalledWith({ desde: '2026-01-01', hasta: '' }),
    );
  });

  it('sin cierres lo dice, en lugar de enseñar tablas vacías', async () => {
    fetchPanelDeDesenlaces.mockResolvedValue(
      panel({
        resumen: { cerrados: 0, ganados: 0, perdidos: 0, tasa_de_ganados: null, score_medio_de_los_ganados: null, score_medio_de_los_perdidos: null },
        por_motivo: [],
        por_tramo: [],
        por_publicacion: [],
        por_red: [],
        acierto_del_score: [],
      }),
    );
    render(<PanelDeDesenlaces />);

    expect(await screen.findByText(/Todavía no hay ningún prospecto cerrado/)).toBeInTheDocument();
  });

  it('el error del servidor se enseña y no deja el panel a medias', async () => {
    fetchPanelDeDesenlaces.mockRejectedValue(new Error('El primer día del periodo es posterior al último.'));
    render(<PanelDeDesenlaces />);

    expect(await screen.findByRole('alert')).toHaveTextContent('posterior al último');
  });
});
