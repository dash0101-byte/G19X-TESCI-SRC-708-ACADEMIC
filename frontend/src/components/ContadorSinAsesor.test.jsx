// ============================================================================
// «N nuevos de publicaciones, sin asesor»
// ============================================================================
//
// El bloque vivía dentro de `Publicaciones` y el capítulo 38 lo saca para que el tablero
// pueda enseñar el mismo (§6.2, punto 11). Lo que se comprueba es lo que un componente
// compartido entre dos pantallas puede romper sin que se note:
//
// * que `null` y `0` no digan lo mismo. «No se ha preguntado» y «no hay nadie esperando»
//   son respuestas distintas, y la segunda es una afirmación: un contador que enseña «0»
//   cuando el servidor no contestó le dice al líder que no tiene nada que repartir.
// * que el enlace a repartir aparezca donde hace falta y no donde estorba.

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ContadorSinAsesor from './ContadorSinAsesor.jsx';

describe('el contador de «nuevos sin asesor»', () => {
  it('enseña el número y dice que están esperando', () => {
    render(<ContadorSinAsesor total={3} />);

    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText(/Nuevos de publicaciones, sin asesor/)).toBeInTheDocument();
    expect(screen.getByText(/Están esperando/)).toBeInTheDocument();
  });

  it('con cero, no dice que nadie esté esperando', () => {
    render(<ContadorSinAsesor total={0} />);

    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.queryByText(/Están esperando/)).not.toBeInTheDocument();
  });

  it('sin respuesta del servidor no se dibuja, y no finge un cero', () => {
    const { container } = render(<ContadorSinAsesor total={null} />);
    expect(container).toBeEmptyDOMElement();

    const sinProp = render(<ContadorSinAsesor />);
    expect(sinProp.container).toBeEmptyDOMElement();
  });

  it('lleva a repartir cuando se le da a dónde', async () => {
    const usuario = userEvent.setup();
    const ir = vi.fn();
    render(<ContadorSinAsesor total={3} onIrARepartir={ir} />);

    await usuario.click(screen.getByRole('button', { name: 'Ver y repartir' }));

    expect(ir).toHaveBeenCalledTimes(1);
  });

  it('sin dónde ir, no ofrece un botón que no lleva a ninguna parte', () => {
    render(<ContadorSinAsesor total={3} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('con cero no ofrece repartir aunque se le diga a dónde', () => {
    // No hay nada que repartir: el botón llevaría a una lista en la que no hay ninguna
    // ficha marcada, y el viaje en balde es peor que no ofrecerlo.
    render(<ContadorSinAsesor total={0} onIrARepartir={vi.fn()} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
