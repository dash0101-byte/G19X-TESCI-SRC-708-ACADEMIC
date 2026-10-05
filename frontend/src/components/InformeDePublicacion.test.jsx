// ============================================================================
// Informe de una publicación
// ============================================================================
//
// Se comprueba:
// * que arriba salen los tres números y abajo la tabla con lo que la fase pide;
// * que las filas van del score más alto al más bajo, tal como las manda el servidor;
// * que los filtros de etapa y fecha viajan en la consulta, y no se filtra en el navegador
//   (filtrar aquí solo escondería filas de una página, no las traería);
// * que una fila abre la ficha 360;
// * que a un asesor se le dice cuántos prospectos más hay sin decirle quiénes.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({ fetchInformeDePublicacion: vi.fn() }));

import { fetchInformeDePublicacion } from '../services/api';
import InformeDePublicacion from './InformeDePublicacion.jsx';

const PUBLICACION = { id: 5, name: 'Post · Talento TI septiembre' };

const INFORME = {
  publicacion: { id: 5, titulo: PUBLICACION.name, enlace: 'http://localhost:3000/p/abc', activa: true },
  resumen: {
    perfiles_recibidos: 2,
    avanzaron_de_etapa: 1,
    score_medio: 60.0,
    de_otros_asesores: 0,
    alcance_completo: true,
  },
  filas: [
    {
      lead_id: 13, nombre: 'Ana Prueba', empresa: 'Ejemplo SA', cargo: 'CTO',
      score: 80.0, categoria: 'HOT', etapa: 'QUALIFIED', asesor: 'Asesor de Pruebas',
      recibida_en: '2026-09-17T12:00:00Z', necesidad: 'Ver una demostración',
    },
    {
      lead_id: 14, nombre: 'Beto Muestra', empresa: 'Otra SA', cargo: 'CIO',
      score: 40.0, categoria: 'COLD', etapa: 'NEW', asesor: null,
      recibida_en: '2026-09-16T12:00:00Z', necesidad: null,
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  fetchInformeDePublicacion.mockReset().mockResolvedValue(INFORME);
});

function pintar(props = {}) {
  return render(
    <InformeDePublicacion publicacion={PUBLICACION} onCerrar={() => {}} {...props} />,
  );
}

describe('lo que enseña', () => {
  it('arriba, perfiles recibidos, avances y score medio', async () => {
    pintar();
    await screen.findByText('Perfiles recibidos');

    expect(screen.getByText('Perfiles recibidos').parentElement).toHaveTextContent('2');
    expect(screen.getByText('Avanzaron de etapa').parentElement).toHaveTextContent('1');
    expect(screen.getByText('Score medio').parentElement).toHaveTextContent('60');
  });

  it('y sin perfiles recibidos no hay score medio: un guion, no un cero', async () => {
    // Lo que se vio en la demostración, en la pantalla de al lado y por el mismo
    // motivo. Aquí se comprueba además el reparto por red, donde la publicación de
    // ejemplo tenía tres redes a cero y las tres decían «Score medio 0».
    fetchInformeDePublicacion.mockResolvedValueOnce({
      ...INFORME,
      resumen: {
        ...INFORME.resumen,
        perfiles_recibidos: 0,
        avanzaron_de_etapa: 0,
        score_medio: null,
        visitas: 0,
        envios: 0,
        tasa_de_envio: null,
      },
      filas: [],
      total: 0,
      por_red: [
        { red: 'linkedin', etiqueta: 'LinkedIn', visitas: 0, envios: 0, tasa_de_envio: null, perfiles: 0, score_medio: null },
        { red: 'whatsapp', etiqueta: 'WhatsApp', visitas: 3, envios: 1, tasa_de_envio: 33.3, perfiles: 1, score_medio: 34.3 },
      ],
    });
    pintar();
    await screen.findByText('Perfiles recibidos');

    // El primero de cada uno es el dato de la cabecera; el otro es la cabecera de
    // columna de la tabla por red, que se comprueba abajo.
    expect(screen.getAllByText('Score medio')[0].parentElement).toHaveTextContent('—');
    expect(screen.getAllByText('Tasa de envío')[0].parentElement).toHaveTextContent('—');

    const sinNadie = await screen.findByRole('row', { name: /LinkedIn/ });
    expect(within(sinNadie).getAllByRole('cell').map((c) => c.textContent.trim()))
      .toEqual(['0', '0', '—', '0', '—']);
    // Y la red por la que sí llegó alguien conserva su número.
    const conAlguien = screen.getByRole('row', { name: /WhatsApp/ });
    expect(conAlguien).toHaveTextContent('34.3');
  });

  it('abajo, la tabla con nombre, empresa, cargo, score, etapa, asesor y fecha', async () => {
    pintar();
    const fila = await screen.findByRole('row', { name: /Ana Prueba/ });

    expect(within(fila).getByText('Ejemplo SA')).toBeInTheDocument();
    expect(within(fila).getByText('CTO')).toBeInTheDocument();
    expect(within(fila).getByText('80')).toBeInTheDocument();
    expect(within(fila).getByText('Calificado')).toBeInTheDocument();
    expect(within(fila).getByText('Asesor de Pruebas')).toBeInTheDocument();
  });

  it('el orden por score es el que manda el servidor', async () => {
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });

    const nombres = screen.getAllByRole('row').slice(1).map((fila) => within(fila).getAllByRole('cell')[0]);
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('Ana Prueba');
    expect(screen.getAllByRole('row')[2]).toHaveTextContent('Beto Muestra');
    expect(nombres).toHaveLength(2);
  });

  it('qué dijo necesitar, al lado del cargo; sin necesidad, un guion', async () => {
    pintar();
    const ana = await screen.findByRole('row', { name: /Ana Prueba/ });

    expect(screen.getByRole('columnheader', { name: 'Necesita' })).toBeInTheDocument();
    expect(within(ana).getByText('Ver una demostración')).toBeInTheDocument();
    expect(within(screen.getByRole('row', { name: /Beto Muestra/ })).getByText('—')).toBeInTheDocument();
  });

  it('un prospecto sin asesor se dice, no se deja en blanco', async () => {
    pintar();
    const fila = await screen.findByRole('row', { name: /Beto Muestra/ });

    expect(within(fila).getByText('Sin asesor')).toBeInTheDocument();
  });

  it('sin perfiles, lo dice', async () => {
    fetchInformeDePublicacion.mockResolvedValue({ ...INFORME, filas: [], total: 0 });
    pintar();

    expect(await screen.findByText(/todavía no ha traído perfiles/)).toBeInTheDocument();
  });

  it('un error al cargar se enseña', async () => {
    fetchInformeDePublicacion.mockRejectedValue(new Error('Error al cargar el informe de la publicación'));
    pintar();

    expect(await screen.findByRole('alert')).toHaveTextContent('Error al cargar el informe');
  });
});

describe('los filtros', () => {
  it('la etapa se pide al servidor, no se filtra aquí', async () => {
    const usuario = userEvent.setup();
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });

    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'WON');

    await waitFor(() => expect(fetchInformeDePublicacion).toHaveBeenLastCalledWith(
      5, { etapa: 'WON', desde: '', hasta: '' },
    ));
  });

  it('las fechas viajan como días', async () => {
    const usuario = userEvent.setup();
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });

    await usuario.type(screen.getByLabelText('Desde'), '2026-09-01');

    await waitFor(() => expect(fetchInformeDePublicacion).toHaveBeenLastCalledWith(
      5, { etapa: '', desde: '2026-09-01', hasta: '' },
    ));
  });

  it('se pueden quitar de golpe', async () => {
    const usuario = userEvent.setup();
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });
    await usuario.selectOptions(screen.getByLabelText('Etapa'), 'WON');

    await usuario.click(await screen.findByRole('button', { name: 'Quitar filtros' }));

    await waitFor(() => expect(fetchInformeDePublicacion).toHaveBeenLastCalledWith(
      5, { etapa: '', desde: '', hasta: '' },
    ));
  });
});

describe('de una fila a la ficha 360', () => {
  it('el nombre es un botón que abre la ficha de esa persona', async () => {
    const usuario = userEvent.setup();
    const abrirFicha = vi.fn();
    pintar({ onSelectLead: abrirFicha });

    await usuario.click(await screen.findByRole('button', { name: 'Ana Prueba' }));

    expect(abrirFicha).toHaveBeenCalledWith(13);
  });
});

describe('el alcance del asesor', () => {
  it('le dice cuántos más hay, sin decirle quiénes', async () => {
    fetchInformeDePublicacion.mockResolvedValue({
      ...INFORME,
      resumen: { ...INFORME.resumen, perfiles_recibidos: 1, de_otros_asesores: 4, alcance_completo: false },
      filas: [INFORME.filas[0]],
      total: 1,
    });
    pintar();

    expect(await screen.findByRole('status')).toHaveTextContent('trajo 4 más');
    expect(screen.queryByText('Beto Muestra')).not.toBeInTheDocument();
  });

  it('a quien ve la cartera completa no se le dice nada de eso', async () => {
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('publicaciones completas', () => {
  const COMPLETO = {
    ...INFORME,
    publicacion: {
      ...INFORME.publicacion, estado: 'pausada', responsable: 'Ana Torres',
      url_del_post: 'https://www.linkedin.com/posts/algo',
    },
    resumen: { ...INFORME.resumen, visitas: 40, envios: 5, tasa_de_envio: 12.5 },
    por_dia: [
      { dia: '2026-09-16', perfiles: 1, visitas: 20 },
      { dia: '2026-09-17', perfiles: 1, visitas: 20 },
    ],
  };

  it('dice el estado y el responsable, y enlaza el post en otra pestaña', async () => {
    fetchInformeDePublicacion.mockResolvedValue(COMPLETO);
    pintar();

    expect(await screen.findByText('Pausada')).toBeInTheDocument();
    expect(screen.getByText('Responsable: Ana Torres')).toBeInTheDocument();
    const post = screen.getByRole('link', { name: 'Ver el post en LinkedIn' });
    expect(post).toHaveAttribute('href', 'https://www.linkedin.com/posts/algo');
    expect(post).toHaveAttribute('target', '_blank');
    expect(post).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('visitas, tasa de visitas a envíos y el gráfico de perfiles por día', async () => {
    fetchInformeDePublicacion.mockResolvedValue(COMPLETO);
    pintar();

    const visitas = await screen.findByText('Visitas a la página');
    expect(visitas.parentElement).toHaveTextContent('40');
    expect(screen.getByText('12.5 %')).toBeInTheDocument();
    expect(screen.getByText('5 envíos desde que se cuentan visitas')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /2 perfiles entre el 16\/9 y el 17\/9/ })).toBeInTheDocument();
  });

  it('sin visitas no inventa una tasa', async () => {
    fetchInformeDePublicacion.mockResolvedValue({ ...COMPLETO, resumen: { ...COMPLETO.resumen, visitas: 0, envios: 0, tasa_de_envio: null } });
    pintar();

    expect(await screen.findByText('Tasa de envío')).toBeInTheDocument();
    expect(screen.queryByText(/ %$/)).not.toBeInTheDocument();
  });

  it('sin dirección de post no pinta un enlace vacío', async () => {
    pintar();
    await screen.findByRole('row', { name: /Ana Prueba/ });
    expect(screen.queryByRole('link', { name: 'Ver el post en LinkedIn' })).not.toBeInTheDocument();
  });
});
