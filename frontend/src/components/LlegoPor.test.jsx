// ============================================================================
// Tarjeta «Llegó por» de la ficha 360
// ============================================================================
//
// Se comprueba:
// * que sin solicitudes no se pinta nada —una tarjeta vacía diría «vino de una publicación
//   que no sabemos cuál», que no es lo que pasó—;
// * que cada solicitud trae su publicación, su enlace, su fecha, qué necesita y cuándo se
//   aceptó el aviso;
// * que si la persona respondió a dos publicaciones se ven las dos;
// * que el perfil de LinkedIn abre en otra pestaña y con `rel` seguro.

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import LlegoPor from './LlegoPor.jsx';

const SOLICITUD = {
  publicacion_id: 5,
  titulo: 'Post · Talento TI septiembre',
  enlace: 'http://localhost:3000/p/Qm9sYS1kZS1wcnVlYmEtMQ',
  recibida_en: '2026-09-17T12:00:00Z',
  necesidad: 'Cubrir vacantes de TI',
  aviso_aceptado_en: '2026-09-17T12:00:00Z',
};

const TARJETA = {
  perfil_de_linkedin: 'https://www.linkedin.com/in/ana-prueba',
  solicitudes: [SOLICITUD],
};

describe('cuándo aparece', () => {
  it('sin tarjeta, no se pinta nada', () => {
    const { container } = render(<LlegoPor llegoPor={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('con la tarjeta pero sin solicitudes, tampoco', () => {
    const { container } = render(<LlegoPor llegoPor={{ perfil_de_linkedin: null, solicitudes: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('lo que enseña', () => {
  it('la publicación con su enlace, la fecha, qué necesita y el consentimiento', () => {
    render(<LlegoPor llegoPor={TARJETA} />);

    const solicitud = screen.getByRole('listitem');
    expect(within(solicitud).getByText(SOLICITUD.titulo)).toBeInTheDocument();
    expect(within(solicitud).getByText(SOLICITUD.enlace)).toBeInTheDocument();
    expect(within(solicitud).getByText(/Cubrir vacantes de TI/)).toBeInTheDocument();
    expect(within(solicitud).getByText(/Aceptó el aviso de privacidad el/)).toBeInTheDocument();
  });

  it('el perfil de LinkedIn se abre en otra pestaña', () => {
    render(<LlegoPor llegoPor={TARJETA} />);

    const enlace = screen.getByRole('link', { name: /Ver perfil de LinkedIn/ });
    expect(enlace).toHaveAttribute('href', TARJETA.perfil_de_linkedin);
    expect(enlace).toHaveAttribute('target', '_blank');
    // Sin `noopener`, la pestaña nueva puede redirigir la del panel desde el otro sitio.
    expect(enlace).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('sin perfil no hay enlace que enseñar', () => {
    render(<LlegoPor llegoPor={{ ...TARJETA, perfil_de_linkedin: null }} />);

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByRole('listitem')).toBeInTheDocument();
  });

  it('quien respondió a dos publicaciones las ve las dos', () => {
    render(<LlegoPor llegoPor={{
      ...TARJETA,
      solicitudes: [
        SOLICITUD,
        { ...SOLICITUD, publicacion_id: 9, titulo: 'Post · Equipos completos octubre', recibida_en: '2026-09-10T09:00:00Z' },
      ],
    }} />);

    expect(screen.getByRole('heading')).toHaveTextContent('Llegó por 2 publicaciones');
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('una publicación retirada no deja la fila muda', () => {
    render(<LlegoPor llegoPor={{
      ...TARJETA,
      solicitudes: [{ ...SOLICITUD, publicacion_id: null, titulo: null, enlace: null }],
    }} />);

    expect(screen.getByText('Publicación retirada')).toBeInTheDocument();
  });
});
