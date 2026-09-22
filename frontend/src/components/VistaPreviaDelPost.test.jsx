// La vista previa del post: corta donde corta LinkedIn, dice si el enlace quedó escondido y
// avisa al pasar de 3 000 caracteres.

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { CORTE_EN_CARACTERES, MAX_TEXTO_DE_LINKEDIN, cortarComoLinkedIn } from './cortarComoLinkedIn';
import VistaPreviaDelPost from './VistaPreviaDelPost.jsx';

const ENLACE = 'http://localhost:3000/interes/abcdefghijklmnopqrstuv';

describe('dónde corta', () => {
  it('un texto corto no se corta', () => {
    expect(cortarComoLinkedIn('Hola')).toEqual({ visible: 'Hola', cortado: false });
  });

  it('a los 210 caracteres, sin partir una palabra', () => {
    const texto = 'palabra '.repeat(60);
    const { visible, cortado } = cortarComoLinkedIn(texto);

    expect(cortado).toBe(true);
    expect(visible.length).toBeLessThanOrEqual(CORTE_EN_CARACTERES);
    expect(visible.endsWith('palabra')).toBe(true);
  });

  it('a las tres líneas aunque sean cortas', () => {
    const { visible, cortado } = cortarComoLinkedIn('uno\ndos\ntres\ncuatro\ncinco');

    expect(cortado).toBe(true);
    expect(visible).toBe('uno\ndos\ntres');
  });
});

describe('lo que enseña', () => {
  it('un post corto se ve entero, sin «ver más», con el enlace', () => {
    render(<VistaPreviaDelPost texto={`Hola\n\n${ENLACE}`} enlace={ENLACE} />);

    expect(screen.queryByRole('button', { name: 'ver más' })).not.toBeInTheDocument();
    expect(screen.getByTestId('texto-del-post')).toHaveTextContent(ENLACE);
    expect(screen.queryByText(/queda después de «ver más»/)).not.toBeInTheDocument();
  });

  it('uno largo se corta, avisa de que el enlace queda escondido y se despliega', async () => {
    const usuario = userEvent.setup();
    render(<VistaPreviaDelPost texto={`${'Texto largo del post. '.repeat(20)}\n\n${ENLACE}`} enlace={ENLACE} />);

    expect(screen.getByTestId('texto-del-post')).not.toHaveTextContent(ENLACE);
    expect(screen.getByText(/queda después de «ver más»/)).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'ver más' }));
    expect(screen.getByTestId('texto-del-post')).toHaveTextContent(ENLACE);
  });

  it('cuenta los caracteres contra el tope y avisa al pasarlo', () => {
    const { rerender } = render(<VistaPreviaDelPost texto={'a'.repeat(MAX_TEXTO_DE_LINKEDIN)} enlace="" />);
    expect(screen.getByTestId('longitud-del-post')).toHaveTextContent('3000 / 3000 caracteres');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    rerender(<VistaPreviaDelPost texto={'a'.repeat(MAX_TEXTO_DE_LINKEDIN + 12)} enlace="" />);
    expect(screen.getByRole('alert')).toHaveTextContent('LinkedIn no admite más de 3000 caracteres: sobran 12.');
  });
});
