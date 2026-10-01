/**
 * Los botones de compartir, las casillas de redes y el código QR (capítulo 27).
 *
 * Lo que se comprueba aquí es lo del navegador: que se pinta lo que manda el servidor, que
 * cada botón lleva al enlace oficial de esa red, que «Copiar texto» copia el texto de **esa**
 * red y no otro, y que el QR se arma en local y se descarga sin pasar por ningún servicio.
 *
 * Los textos y sus recortes no se comprueban aquí: los calcula el servidor y se prueban en
 * `test_una_publicacion_varias_redes.py`. Repetir la regla en dos lenguajes sería tener dos
 * versiones de la misma regla esperando a separarse.
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import CompartirEnRedes, { RedesDelFormulario } from './CompartirEnRedes';

const ENLACE = 'http://localhost:3000/interes/Qm9sYS1kZS1wcnVlYmEtMQ';

const RED = (clave, etiqueta, extra = {}) => ({
  clave,
  etiqueta,
  activa: true,
  enlace: `${ENLACE}?r=${clave}`,
  texto: `Texto de ${etiqueta}\n\n${ENLACE}?r=${clave}`,
  longitud: 40,
  maximo: 3000,
  compartir: `https://ejemplo-${clave}.test/compartir`,
  admite_texto: true,
  aviso: null,
  ...extra,
});

const PUBLICACION = {
  id: 7,
  name: 'Post · Talento TI',
  enlace_publico: ENLACE,
  difusion: [
    RED('linkedin', 'LinkedIn', {
      compartir: 'https://www.linkedin.com/sharing/share-offsite/?url=x',
      admite_texto: false,
      aviso: 'LinkedIn solo recibe el enlace: copia el texto y pégalo en el post.',
    }),
    RED('whatsapp', 'WhatsApp', { compartir: 'https://wa.me/?text=x', maximo: 400, longitud: 120 }),
    RED('instagram', 'Instagram', {
      compartir: null,
      admite_texto: false,
      aviso: 'Instagram no deja enlaces en el pie de una publicación: pon el enlace en la biografía.',
    }),
    RED('x', 'X', { activa: false, compartir: 'https://x.com/intent/post?text=x', maximo: 280 }),
  ],
};

const DISPONIBLES = [
  { clave: 'linkedin', etiqueta: 'LinkedIn' },
  { clave: 'whatsapp', etiqueta: 'WhatsApp' },
  { clave: 'instagram', etiqueta: 'Instagram' },
  { clave: 'x', etiqueta: 'X' },
];

function pintar(props = {}) {
  const onCopiar = vi.fn();
  render(<CompartirEnRedes publicacion={PUBLICACION} onCopiar={onCopiar} {...props} />);
  return { onCopiar };
}

/** La fila de una red. Se busca dentro de la lista: el selector del QR repite los nombres. */
function fila(etiqueta) {
  return within(screen.getByRole('list', { name: 'Redes activas' }))
    .getByText(etiqueta)
    .closest('li');
}

describe('los botones de compartir', () => {
  it('solo enseña las redes activas', () => {
    pintar();

    expect(screen.getByRole('link', { name: 'Compartir en LinkedIn' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Compartir en WhatsApp' })).toBeInTheDocument();
    // X está desactivada en esta publicación: no se ofrece.
    expect(screen.queryByRole('link', { name: 'Compartir en X' })).not.toBeInTheDocument();
  });

  it('cada botón lleva al enlace oficial de su red', () => {
    pintar();

    expect(screen.getByRole('link', { name: 'Compartir en LinkedIn' })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/sharing/share-offsite/?url=x',
    );
    expect(screen.getByRole('link', { name: 'Compartir en WhatsApp' })).toHaveAttribute(
      'href',
      'https://wa.me/?text=x',
    );
  });

  it('abre en otra pestaña sin dejarle tocar esta', () => {
    pintar();

    const boton = screen.getByRole('link', { name: 'Compartir en LinkedIn' });
    expect(boton).toHaveAttribute('target', '_blank');
    // Sin `noopener`, la página que se abre puede manipular la que la abrió.
    expect(boton.getAttribute('rel')).toContain('noopener');
  });

  it('copia el texto de la red en la que se pulsa, no el de otra', async () => {
    const usuario = userEvent.setup();
    const { onCopiar } = pintar();

    await usuario.click(within(fila('WhatsApp')).getByRole('button', { name: 'Copiar texto' }));

    expect(onCopiar).toHaveBeenCalledTimes(1);
    expect(onCopiar.mock.calls[0][0]).toContain('Texto de WhatsApp');
    expect(onCopiar.mock.calls[0][0]).toContain('?r=whatsapp');
  });

  it('a Instagram le ofrece copiar y le dice dónde va el enlace', () => {
    pintar();

    const instagram = fila('Instagram');
    expect(within(instagram).queryByRole('link')).not.toBeInTheDocument();
    expect(within(instagram).getByRole('button', { name: 'Copiar texto' })).toBeInTheDocument();
    expect(within(instagram).getByText(/biografía/)).toBeInTheDocument();
  });

  it('avisa donde la red no se lleva el texto', () => {
    pintar();

    expect(within(fila('LinkedIn')).getByText(/copia el texto/i)).toBeInTheDocument();
  });

  it('enseña cuánto ocupa el texto frente al tope de cada red', () => {
    pintar();

    expect(within(fila('WhatsApp')).getByText('120 / 400')).toBeInTheDocument();
  });
});

describe('el código QR', () => {
  it('se dibuja en local, sin pedirle la imagen a nadie', () => {
    pintar();

    const dibujo = screen.getByRole('img', { name: `Código QR de ${ENLACE}` });
    expect(dibujo.querySelector('svg')).toBeTruthy();
    // Ni `img src`, ni `fetch`: el SVG está aquí dentro.
    expect(dibujo.querySelector('image')).toBeNull();
  });

  it('por defecto apunta al enlace sin red, que es el de material impreso', () => {
    pintar();

    expect(screen.getByLabelText('Enlace del código')).toHaveValue('');
    expect(screen.getByRole('img', { name: `Código QR de ${ENLACE}` })).toBeInTheDocument();
  });

  it('cambia de enlace al elegir una red', async () => {
    const usuario = userEvent.setup();
    pintar();

    await usuario.selectOptions(screen.getByLabelText('Enlace del código'), 'whatsapp');

    expect(
      screen.getByRole('img', { name: `Código QR de ${ENLACE}?r=whatsapp` }),
    ).toBeInTheDocument();
  });

  it('solo ofrece las redes activas para el código', () => {
    pintar();

    const opciones = within(screen.getByLabelText('Enlace del código'))
      .getAllByRole('option')
      .map((o) => o.textContent);
    expect(opciones).toEqual(['Material impreso (sin red)', 'LinkedIn', 'WhatsApp', 'Instagram']);
  });

  it('descarga el SVG con un nombre que dice de qué publicación es', async () => {
    const usuario = userEvent.setup();
    const crear = vi.fn(() => 'blob:qr');
    const revocar = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL: crear, revokeObjectURL: revocar });
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function espia() {
      expect(this.download).toBe('qr-post-talento-ti-impreso.svg');
    });

    pintar();
    await usuario.click(screen.getByRole('button', { name: 'Descargar código QR' }));

    expect(clic).toHaveBeenCalledTimes(1);
    expect(crear).toHaveBeenCalledTimes(1);
    // Se suelta el objeto: si no, el navegador se queda con el blob hasta recargar.
    expect(revocar).toHaveBeenCalledTimes(1);
    clic.mockRestore();
    vi.unstubAllGlobals();
  });
});

describe('cuando la dirección pública no contesta', () => {
  // Encontrado usándolo (01-10-2026). Este panel es donde alguien actúa sobre el enlace
  // —lo copia, lo comparte, lo imprime—, y el aviso de arriba de «Publicaciones» se queda
  // fuera de la vista en cuanto se despliega una publicación. Un código QR de una
  // dirección muerta se ve exactamente igual que uno bueno: el único momento en que se
  // descubre es con el teléfono delante del papel ya impreso.
  it('lo dice aquí, donde está el enlace y el código', () => {
    pintar({ direccionCaida: true });

    const aviso = screen.getByRole('alert');
    expect(aviso).toHaveTextContent(/La dirección pública no contesta/i);
    expect(aviso).toHaveTextContent(/no llega a ninguna parte/i);
  });

  it('y dice que el código no está mal, que lo que falla es el otro extremo', () => {
    // Si no, el aviso parecería decir que el QR está roto y alguien lo volvería a generar.
    pintar({ direccionCaida: true });

    expect(screen.getByRole('alert')).toHaveTextContent(/el enlace es correcto/i);
    expect(screen.getByRole('img', { name: `Código QR de ${ENLACE}` })).toBeInTheDocument();
  });

  it('con la dirección viva, no hay aviso', () => {
    pintar({ direccionCaida: false });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('y sin saber si contesta, tampoco: «no se ha comprobado» no es una avería', () => {
    pintar();

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('las casillas de redes del formulario', () => {
  function pintarFormulario(activas = ['linkedin', 'whatsapp']) {
    const onChange = vi.fn();
    render(
      <RedesDelFormulario activas={activas} disponibles={DISPONIBLES} onChange={onChange} />,
    );
    return { onChange };
  }

  it('marca las activas y deja sin marcar las demás', () => {
    pintarFormulario();

    expect(screen.getByRole('checkbox', { name: 'LinkedIn' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'X' })).not.toBeChecked();
  });

  it('activar una red la añade en el orden fijo, no al final', async () => {
    const usuario = userEvent.setup();
    const { onChange } = pintarFormulario(['whatsapp']);

    await usuario.click(screen.getByRole('checkbox', { name: 'LinkedIn' }));

    expect(onChange).toHaveBeenCalledWith(['linkedin', 'whatsapp']);
  });

  it('desactivar una red la quita', async () => {
    const usuario = userEvent.setup();
    const { onChange } = pintarFormulario(['linkedin', 'whatsapp']);

    await usuario.click(screen.getByRole('checkbox', { name: 'WhatsApp' }));

    expect(onChange).toHaveBeenCalledWith(['linkedin']);
  });

  it('avisa si se quedan todas apagadas', () => {
    pintarFormulario([]);

    expect(screen.getByText('Hace falta al menos una red de difusión.')).toBeInTheDocument();
  });
});
