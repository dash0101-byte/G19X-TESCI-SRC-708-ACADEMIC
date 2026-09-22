// El gráfico de perfiles por día: una barra por día, alturas proporcionales, sus datos
// legibles sin ver el dibujo, y un aviso cuando se recorta el periodo.

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import GraficoPorDia from './GraficoPorDia.jsx';

const DIAS = [
  { dia: '2026-09-18', perfiles: 0, visitas: 3 },
  { dia: '2026-09-19', perfiles: 2, visitas: 10 },
  { dia: '2026-09-20', perfiles: 4, visitas: 12 },
];

describe('GraficoPorDia', () => {
  it('una barra por día, la más alta para el día con más perfiles', () => {
    render(<GraficoPorDia dias={DIAS} />);

    const barras = screen.getAllByTestId('barra');
    expect(barras).toHaveLength(3);
    const altos = barras.map((b) => Number(b.getAttribute('height')));
    expect(altos[0]).toBe(0);
    expect(altos[2]).toBeGreaterThan(altos[1]);
    expect(altos[2]).toBe(2 * altos[1]);
  });

  it('se describe para quien no ve el dibujo', () => {
    render(<GraficoPorDia dias={DIAS} />);

    expect(screen.getByRole('img')).toHaveAccessibleName('6 perfiles entre el 18/9 y el 20/9; el día con más recibió 4.');
    const tabla = screen.getByRole('table');
    expect(within(tabla).getByRole('row', { name: /2026-09-19/ })).toHaveTextContent('210');
  });

  it('dice cuándo enseña solo los últimos días', () => {
    render(<GraficoPorDia dias={DIAS} recortado />);
    expect(screen.getByText(/los últimos 3 días/)).toBeInTheDocument();
  });

  it('sin datos no dibuja un gráfico vacío', () => {
    render(<GraficoPorDia dias={[]} />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText(/Todavía no hay visitas ni perfiles/)).toBeInTheDocument();
  });
});
