// ============================================================================
// Publicaciones
// ============================================================================
//
// Una publicación es una campaña con canal LinkedIn. Se comprueba:
// * que el alta manda el canal LinkedIn y nunca un enlace, con su estado, cierre,
//   responsable, dirección del post y opciones de «¿Qué necesitas?»;
// * que «Copiar texto para LinkedIn» deja en el portapapeles el texto que armó el servidor,
//   con descripción y enlace, y que si el navegador no deja copiar lo enseña para copiarlo
//   a mano;
// * que el ciclo de estados ofrece solo lo que se puede hacer desde cada uno;
// * que se duplica, se previsualiza el post y se ve la página como el interesado;
// * que el asesor consulta, copia y previsualiza, pero no ve nada que gestione.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchCampaignList: vi.fn(),
  createCampaign: vi.fn(),
  updateCampaign: vi.fn(),
  cambiarEstadoDePublicacion: vi.fn(),
  duplicateCampaign: vi.fn(),
  fetchVistaPreviaDePublicacion: vi.fn(),
  fetchSalesReps: vi.fn(),
  fetchComparativaDePublicaciones: vi.fn(),
  fetchNuevosSinAsesor: vi.fn(),
  fetchEstadoDeLaDireccionPublica: vi.fn(),
  fetchInformeDePublicacion: vi.fn(),
  fetchPublicacionDeInteres: vi.fn(),
  enviarInteres: vi.fn(),
}));

import {
  cambiarEstadoDePublicacion,
  createCampaign,
  duplicateCampaign,
  enviarInteres,
  fetchCampaignList,
  fetchComparativaDePublicaciones,
  fetchInformeDePublicacion,
  fetchEstadoDeLaDireccionPublica,
  fetchNuevosSinAsesor,
  fetchPublicacionDeInteres,
  fetchSalesReps,
  fetchVistaPreviaDePublicacion,
  updateCampaign,
} from '../services/api';
import Publicaciones, { CANAL_LINKEDIN, MAX_DESCRIPCION, MAX_NECESIDADES } from './Publicaciones.jsx';

const ENLACE = 'http://localhost:3000/interes/Qm9sYS1kZS1wcnVlYmEtMQ';
const NECESIDADES = [
  { clave: 'vacantes', etiqueta: 'Cubrir vacantes de TI' },
  { clave: 'equipo', etiqueta: 'Formar un equipo completo' },
];
const PUBLICACION = {
  id: 5,
  name: 'Post · Talento TI septiembre',
  channel: 'LinkedIn',
  description: '¿Tu equipo de TI tarda meses en cubrir una vacante?',
  target_audience: 'Directores de TI',
  public_slug: 'Qm9sYS1kZS1wcnVlYmEtMQ',
  enlace_publico: ENLACE,
  texto_para_linkedin: `¿Tu equipo de TI tarda meses en cubrir una vacante?\n\n${ENLACE}`,
  longitud_del_texto: 110,
  max_texto_de_linkedin: 3000,
  is_active: true,
  estado: 'activa',
  end_date: null,
  responsable_id: null,
  responsable: null,
  url_del_post: null,
  necesidades: NECESIDADES,
  necesidades_propias: false,
  budget: 0,
  created_at: '2026-09-17T10:00:00Z',
};
const ASESORES = [
  { id: 21, full_name: 'Ana Torres', is_active: true, leads_asignados: 3 },
  { id: 22, full_name: 'Luis Prado', is_active: true, leads_asignados: 1 },
];
const VISTA_PREVIA = {
  titulo: PUBLICACION.name,
  descripcion: PUBLICACION.description,
  opciones: {
    cargos: ['CTO'], sectores: ['FinTech'], tamanos: ['1-10'],
    necesidades: { vacantes: 'Cubrir vacantes de TI', equipo: 'Formar un equipo completo' },
  },
};

let escribir;

beforeEach(() => {
  fetchCampaignList.mockReset().mockResolvedValue({ total: 1, items: [PUBLICACION] });
  createCampaign.mockReset().mockResolvedValue({ ...PUBLICACION, id: 6 });
  updateCampaign.mockReset().mockResolvedValue(PUBLICACION);
  cambiarEstadoDePublicacion.mockReset().mockResolvedValue(PUBLICACION);
  duplicateCampaign.mockReset().mockResolvedValue({ ...PUBLICACION, id: 7, name: `${PUBLICACION.name} (copia)`, estado: 'borrador' });
  fetchVistaPreviaDePublicacion.mockReset().mockResolvedValue(VISTA_PREVIA);
  fetchSalesReps.mockReset().mockResolvedValue({ total: 2, items: ASESORES });
  fetchPublicacionDeInteres.mockReset();
  enviarInteres.mockReset();
  fetchComparativaDePublicaciones.mockReset().mockResolvedValue({
    items: [
      { publicacion_id: 5, titulo: PUBLICACION.name, activa: true, estado: 'activa', perfiles_recibidos: 4, avanzaron_de_etapa: 2, score_medio: 61.5, visitas: 40, envios: 5, tasa_de_envio: 12.5 },
      { publicacion_id: 9, titulo: 'Post antiguo', activa: false, estado: 'cerrada', perfiles_recibidos: 1, avanzaron_de_etapa: 0, score_medio: 20.0, visitas: 0, envios: 0, tasa_de_envio: null },
    ],
  });
  fetchNuevosSinAsesor.mockReset().mockResolvedValue({ total: 3 });
  // Por defecto, la dirección pública responde y no hay enlaces caducados: es el estado
  // normal, y así cada prueba que quiera el otro caso lo dice explícitamente.
  fetchEstadoDeLaDireccionPublica.mockReset().mockResolvedValue({
    base: 'http://localhost:3000/interes',
    responde: true,
    comprobada_en: '2026-09-25T10:00:00Z',
    detalle: 'HTTP 200',
    publicaciones_con_enlace_caducado: 0,
  });
  fetchInformeDePublicacion.mockReset().mockResolvedValue({
    publicacion: { id: 5, titulo: PUBLICACION.name, enlace: ENLACE, activa: true, estado: 'activa' },
    resumen: { perfiles_recibidos: 1, avanzaron_de_etapa: 0, score_medio: 35.8, de_otros_asesores: 0, alcance_completo: true, visitas: 0, envios: 0, tasa_de_envio: null },
    filas: [{
      lead_id: 13, nombre: 'Ana Prueba', empresa: 'Ejemplo SA', cargo: 'CTO',
      score: 35.8, categoria: 'COLD', etapa: 'NEW', asesor: null,
      recibida_en: '2026-09-17T12:00:00Z',
    }],
    total: 1, limit: 50, offset: 0, por_dia: [], grafico_recortado: false,
  });
  escribir = vi.fn().mockResolvedValue(undefined);
});

// `userEvent.setup()` instala su propio portapapeles simulado en `navigator`; el de la
// prueba se pone después para que sea el que recibe la escritura.
function prepararUsuario() {
  const usuario = userEvent.setup();
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: escribir }, configurable: true });
  return usuario;
}

afterEach(() => {
  vi.restoreAllMocks();
});

// El título de una publicación sale dos veces cuando el líder mira la sección: en su
// ficha de la lista y en la fila de la comparativa. Las búsquedas se acotan a la lista
// para que digan cuál de las dos se está mirando.
function lista() {
  return screen.getByRole('list', { name: 'Publicaciones' });
}

function elemento(nombre) {
  return within(lista()).getByText(nombre).closest('li');
}

async function esperarPublicacion(nombre) {
  const lasPublicaciones = await screen.findByRole('list', { name: 'Publicaciones' });
  return within(lasPublicaciones).findByText(nombre);
}

describe('lo que enseña', () => {
  it('pide solo las campañas de LinkedIn, también las inactivas', async () => {
    render(<Publicaciones puedeGestionar />);
    expect(await esperarPublicacion(PUBLICACION.name)).toBeInTheDocument();
    expect(fetchCampaignList).toHaveBeenCalledWith({ incluirInactivas: true, canal: CANAL_LINKEDIN });
  });

  it('cada publicación con su estado, a quién va, su responsable, su texto y su enlace', async () => {
    fetchCampaignList.mockResolvedValue({
      total: 1,
      items: [{
        ...PUBLICACION, responsable_id: 21, responsable: { id: 21, full_name: 'Ana Torres' },
        end_date: '2026-10-31T23:59:59Z', url_del_post: 'https://www.linkedin.com/posts/algo',
      }],
    });
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);
    const fila = elemento(PUBLICACION.name);

    expect(within(fila).getByText('Activa')).toBeInTheDocument();
    expect(within(fila).getByText('Dirigida a: Directores de TI')).toBeInTheDocument();
    expect(within(fila).getByText(/Responsable: Ana Torres · Se cierra el 2026-10-31/)).toBeInTheDocument();
    expect(within(fila).getByText(PUBLICACION.description)).toBeInTheDocument();
    expect(within(fila).getByText(ENLACE)).toBeInTheDocument();
    const post = within(fila).getByRole('link', { name: 'Ver el post en LinkedIn' });
    expect(post).toHaveAttribute('href', 'https://www.linkedin.com/posts/algo');
    expect(post).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('sin responsable dice que llegan sin asesor', async () => {
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    expect(within(elemento(PUBLICACION.name)).getByText(/ninguno \(llegan sin asesor\)/)).toBeInTheDocument();
  });

  it('dice que no hay nada cuando no hay nada', async () => {
    fetchCampaignList.mockResolvedValue({ total: 0, items: [] });
    render(<Publicaciones puedeGestionar />);
    expect(await screen.findByText('Todavía no hay publicaciones.')).toBeInTheDocument();
  });

  it('un error al cargar se muestra', async () => {
    fetchCampaignList.mockRejectedValue(new Error('Error al cargar las campañas'));
    render(<Publicaciones puedeGestionar />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Error al cargar las campañas');
  });
});

describe('crear una publicación y copiar su texto', () => {
  it('el alta manda el canal LinkedIn y ningún enlace, y después se copia el texto', async () => {
    const usuario = prepararUsuario();
    fetchCampaignList.mockResolvedValueOnce({ total: 0, items: [] });
    render(<Publicaciones puedeGestionar />);
    await screen.findByText('Todavía no hay publicaciones.');

    await usuario.click(screen.getByRole('button', { name: '+ Nueva publicación' }));
    await usuario.type(screen.getByLabelText('Título interno'), PUBLICACION.name);
    await usuario.type(screen.getByLabelText('Texto de la publicación'), PUBLICACION.description);
    await usuario.type(screen.getByLabelText('A quién va dirigida'), 'Directores de TI');
    await usuario.click(screen.getByRole('button', { name: 'Crear publicación' }));

    await waitFor(() => expect(createCampaign).toHaveBeenCalledTimes(1));
    const enviado = createCampaign.mock.calls[0][0];
    expect(enviado).toEqual({
      name: PUBLICACION.name,
      description: PUBLICACION.description,
      target_audience: 'Directores de TI',
      estado: 'activa',
      end_date: null,
      responsable_id: null,
      url_del_post: null,
      necesidades: null,
      // Las de siempre: una publicación nueva sale difundible por las cuatro por defecto.
      redes: ['linkedin', 'whatsapp', 'facebook', 'correo'],
      channel: 'LinkedIn',
    });
    expect(enviado).not.toHaveProperty('public_slug');
    expect(await screen.findByRole('status')).toHaveTextContent('creada');

    await esperarPublicacion(PUBLICACION.name);
    await usuario.click(within(elemento(PUBLICACION.name)).getByRole('button', { name: 'Copiar texto para LinkedIn' }));

    expect(escribir).toHaveBeenCalledWith(PUBLICACION.texto_para_linkedin);
    expect(escribir.mock.calls[0][0]).toContain(ENLACE);
    expect(await screen.findByRole('status')).toHaveTextContent('copiado');
  });

  it('un borrador con cierre, responsable, post y opciones propias viaja completo', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: '+ Nueva publicación' }));
    const estado = screen.getByLabelText('Estado');
    // Al crear solo tiene sentido borrador o activa.
    expect(within(estado).getAllByRole('option').map((o) => o.value)).toEqual(['borrador', 'activa']);
    await usuario.type(screen.getByLabelText('Título interno'), 'Borrador');
    await usuario.type(screen.getByLabelText('Texto de la publicación'), 'Texto');
    await usuario.selectOptions(estado, 'borrador');
    await usuario.type(screen.getByLabelText('Fecha de cierre (opcional)'), '2026-10-31');
    await usuario.selectOptions(screen.getByLabelText('Asesor responsable'), '22');
    expect(screen.getByText('Los prospectos nuevos de esta publicación se le asignan solos.')).toBeInTheDocument();
    await usuario.type(screen.getByLabelText('Dirección del post publicado (opcional)'), 'https://www.linkedin.com/posts/x');
    await usuario.click(screen.getByLabelText(/Usar opciones propias/));
    await usuario.type(screen.getByLabelText('Opción 1'), 'Cubrir una vacante');
    await usuario.type(screen.getByLabelText('Opción 2'), 'Montar un equipo');
    await usuario.click(screen.getByRole('button', { name: '+ Añadir opción' }));
    await usuario.type(screen.getByLabelText('Opción 3'), 'Hablar con alguien');
    await usuario.click(screen.getByRole('button', { name: 'Crear publicación' }));

    await waitFor(() => expect(createCampaign).toHaveBeenCalledTimes(1));
    expect(createCampaign.mock.calls[0][0]).toMatchObject({
      estado: 'borrador',
      end_date: '2026-10-31T23:59:59+00:00',
      responsable_id: 22,
      url_del_post: 'https://www.linkedin.com/posts/x',
      necesidades: ['Cubrir una vacante', 'Montar un equipo', 'Hablar con alguien'],
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Revise su página');
  });

  it('las opciones van de dos a cinco: ni se quitan por debajo ni se añaden por encima', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);
    await usuario.click(screen.getByRole('button', { name: '+ Nueva publicación' }));
    await usuario.click(screen.getByLabelText(/Usar opciones propias/));

    expect(screen.getByRole('button', { name: 'Quitar la opción 1' })).toBeDisabled();
    for (let i = 2; i < MAX_NECESIDADES; i += 1) {
      await usuario.click(screen.getByRole('button', { name: '+ Añadir opción' }));
    }
    expect(screen.getAllByRole('button', { name: /Quitar la opción/ })).toHaveLength(MAX_NECESIDADES);
    expect(screen.queryByRole('button', { name: '+ Añadir opción' })).not.toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Quitar la opción 5' }));
    expect(screen.getAllByRole('button', { name: /Quitar la opción/ })).toHaveLength(MAX_NECESIDADES - 1);
  });

  it('si el navegador no deja copiar, enseña el texto para copiarlo a mano', async () => {
    const usuario = prepararUsuario();
    escribir.mockRejectedValue(new Error('NotAllowedError'));
    render(<Publicaciones />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: 'Copiar texto para LinkedIn' }));

    const manual = await screen.findByLabelText(/cópielo a mano/);
    expect(manual).toHaveValue(PUBLICACION.texto_para_linkedin);
  });

  it('el contador avisa de lo que queda y la vista previa cuenta el texto con el enlace', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);
    await usuario.click(screen.getByRole('button', { name: '+ Nueva publicación' }));

    const texto = screen.getByLabelText('Texto de la publicación');
    expect(texto).toHaveAttribute('maxLength', String(MAX_DESCRIPCION));
    await usuario.type(texto, 'Hola');
    expect(screen.getByText(`Quedan ${MAX_DESCRIPCION - 4} caracteres. El enlace se añade al final al copiar.`)).toBeInTheDocument();
    // «Hola», línea en blanco y un enlace del mismo largo que los de verdad.
    expect(screen.getByTestId('longitud-del-post')).toHaveTextContent(`${4 + 2 + ENLACE.length} / 3000 caracteres`);
  });

  it('un rechazo del servidor se muestra y el formulario sigue abierto', async () => {
    const usuario = prepararUsuario();
    createCampaign.mockRejectedValue(new Error('Error al crear la campaña'));
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: '+ Nueva publicación' }));
    await usuario.type(screen.getByLabelText('Título interno'), 'Otra');
    await usuario.type(screen.getByLabelText('Texto de la publicación'), 'Texto');
    await usuario.click(screen.getByRole('button', { name: 'Crear publicación' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Error al crear la campaña');
    expect(screen.getByRole('form', { name: 'Nueva publicación' })).toBeInTheDocument();
  });
});

describe('editar y el ciclo de estados', () => {
  it('editar carga lo que hay y guarda sin tocar el canal', async () => {
    const usuario = prepararUsuario();
    fetchCampaignList.mockResolvedValue({
      total: 1,
      items: [{
        ...PUBLICACION, responsable_id: 21, end_date: '2026-10-31T23:59:59Z',
        necesidades_propias: true, necesidades: NECESIDADES,
      }],
    });
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: 'Editar' }));
    const publico = screen.getByLabelText('A quién va dirigida');
    expect(publico).toHaveValue('Directores de TI');
    expect(screen.getByLabelText('Asesor responsable')).toHaveValue('21');
    expect(screen.getByLabelText('Fecha de cierre (opcional)')).toHaveValue('2026-10-31');
    expect(screen.getByLabelText('Opción 2')).toHaveValue('Formar un equipo completo');
    await usuario.clear(publico);
    await usuario.type(publico, 'Líderes de talento');
    await usuario.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() =>
      expect(updateCampaign).toHaveBeenCalledWith(5, {
        name: PUBLICACION.name,
        description: PUBLICACION.description,
        target_audience: 'Líderes de talento',
        estado: 'activa',
        end_date: '2026-10-31T23:59:59+00:00',
        responsable_id: 21,
        url_del_post: null,
        necesidades: ['Cubrir vacantes de TI', 'Formar un equipo completo'],
        redes: ['linkedin', 'whatsapp', 'facebook', 'correo'],
      }),
    );
  });

  it.each([
    ['borrador', ['Activar']],
    ['activa', ['Pausar', 'Cerrar']],
    ['pausada', ['Reanudar', 'Cerrar']],
    ['cerrada', ['Reabrir']],
  ])('desde %s se ofrece %j', async (estado, acciones) => {
    fetchCampaignList.mockResolvedValue({ total: 1, items: [{ ...PUBLICACION, estado }] });
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);
    const fila = elemento(PUBLICACION.name);

    for (const accion of ['Activar', 'Pausar', 'Reanudar', 'Cerrar', 'Reabrir']) {
      const boton = within(fila).queryByRole('button', { name: accion });
      if (acciones.includes(accion)) expect(boton).toBeInTheDocument();
      else expect(boton).not.toBeInTheDocument();
    }
  });

  it('pausar y reanudar cambian el estado por su ruta', async () => {
    const usuario = prepararUsuario();
    fetchCampaignList.mockResolvedValue({
      total: 2,
      items: [PUBLICACION, { ...PUBLICACION, id: 9, name: 'Post pausado', estado: 'pausada', is_active: false }],
    });
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion('Post pausado');

    await usuario.click(within(elemento(PUBLICACION.name)).getByRole('button', { name: 'Pausar' }));
    await waitFor(() => expect(cambiarEstadoDePublicacion).toHaveBeenCalledWith(5, 'pausada'));
    await usuario.click(within(elemento('Post pausado')).getByRole('button', { name: 'Reanudar' }));
    await waitFor(() => expect(cambiarEstadoDePublicacion).toHaveBeenCalledWith(9, 'activa'));
    expect(within(elemento('Post pausado')).getByText('Pausada')).toBeInTheDocument();
  });

  it('duplicar crea un borrador y lo dice', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: 'Duplicar publicación' }));

    await waitFor(() => expect(duplicateCampaign).toHaveBeenCalledWith(5));
    expect(await screen.findByRole('status')).toHaveTextContent('Copia creada como borrador');
  });
});

describe('las vistas previas', () => {
  it('el post se ve como en LinkedIn, cortado con «ver más»', async () => {
    const usuario = prepararUsuario();
    const largo = `${'Montamos equipos de TI en treinta días. '.repeat(8)}`;
    fetchCampaignList.mockResolvedValue({
      total: 1,
      items: [{ ...PUBLICACION, description: largo, texto_para_linkedin: `${largo}\n\n${ENLACE}` }],
    });
    render(<Publicaciones />);
    await screen.findByRole('list', { name: 'Publicaciones' });

    await usuario.click(screen.getByRole('button', { name: 'Vista previa del post' }));

    const post = screen.getByRole('figure', { name: 'Vista previa del post en LinkedIn' });
    expect(within(post).getByRole('button', { name: 'ver más' })).toBeInTheDocument();
    expect(within(post).getByText(/El enlace queda después de «ver más»/)).toBeInTheDocument();
    await usuario.click(within(post).getByRole('button', { name: 'ver más' }));
    expect(within(post).getByTestId('texto-del-post')).toHaveTextContent(ENLACE);
  });

  it('«Ver la página» enseña la página del interesado sin enviar nada', async () => {
    const usuario = prepararUsuario();
    fetchCampaignList.mockResolvedValue({ total: 1, items: [{ ...PUBLICACION, estado: 'borrador', is_active: false }] });
    render(<Publicaciones />);
    await screen.findByRole('list', { name: 'Publicaciones' });

    await usuario.click(screen.getByRole('button', { name: 'Ver la página' }));

    expect(fetchVistaPreviaDePublicacion).toHaveBeenCalledWith(5);
    expect(await screen.findByRole('heading', { name: PUBLICACION.name })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Vista previa');
    expect(screen.getByText(/hasta que esté activa/)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Formar un equipo completo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Quiero que me contacten' })).toBeDisabled();
    // Ni la ruta pública —que contaría una visita— ni un envío.
    expect(fetchPublicacionDeInteres).not.toHaveBeenCalled();
    expect(enviarInteres).not.toHaveBeenCalled();

    await usuario.click(screen.getByRole('button', { name: 'Volver a las publicaciones' }));
    expect(await screen.findByRole('list', { name: 'Publicaciones' })).toBeInTheDocument();
  });
});

describe('el asesor solo consulta', () => {
  it('ve, copia y previsualiza, pero no puede crear, editar, duplicar ni cambiar el estado', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones />);
    await esperarPublicacion(PUBLICACION.name);

    for (const nombre of ['+ Nueva publicación', 'Editar', 'Duplicar publicación', 'Pausar', 'Cerrar', 'Activar']) {
      expect(screen.queryByRole('button', { name: nombre })).not.toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: 'Ver la página' })).toBeInTheDocument();
    expect(screen.getByText(/crearlas y editarlas es tarea del líder comercial/)).toBeInTheDocument();
    expect(fetchSalesReps).not.toHaveBeenCalled();

    await usuario.click(screen.getByRole('button', { name: 'Copiar texto para LinkedIn' }));
    expect(escribir).toHaveBeenCalledWith(PUBLICACION.texto_para_linkedin);
  });
});

describe('la comparativa y el contador del líder', () => {
  it('el líder ve cuántos llegaron sin asesor y qué trajo cada publicación', async () => {
    render(<Publicaciones puedeGestionar />);
    await esperarPublicacion(PUBLICACION.name);

    expect(await screen.findByText(/Nuevos de publicaciones, sin asesor/)).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    const comparativa = screen.getByRole('table');
    const fila = within(comparativa).getByRole('row', { name: /Post · Talento TI septiembre/ });
    expect(fila).toHaveTextContent('61.5');
    expect(fila).toHaveTextContent('40');
    expect(fila).toHaveTextContent('12.5 %');
    const antigua = within(comparativa).getByRole('row', { name: /Post antiguo/ });
    expect(within(antigua).getByText('Cerrada')).toBeInTheDocument();
    // Sin visitas no hay tasa: un guion, no un 0 %.
    expect(antigua).toHaveTextContent('—');
  });

  it('al asesor no se le piden: el servidor no se los daría', async () => {
    render(<Publicaciones />);
    await esperarPublicacion(PUBLICACION.name);

    expect(fetchComparativaDePublicaciones).not.toHaveBeenCalled();
    expect(fetchNuevosSinAsesor).not.toHaveBeenCalled();
    expect(screen.queryByText(/Nuevos de publicaciones, sin asesor/)).not.toBeInTheDocument();
  });
});

describe('del listado al informe y a la ficha', () => {
  it('«Ver informe» abre el de esa publicación, y una fila abre su ficha 360', async () => {
    const usuario = prepararUsuario();
    const abrirFicha = vi.fn();
    render(<Publicaciones puedeGestionar onSelectLead={abrirFicha} />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(within(elemento(PUBLICACION.name)).getByRole('button', { name: 'Ver informe' }));

    expect(await screen.findByRole('heading', { name: /Informe de/ })).toBeInTheDocument();
    await waitFor(() => expect(fetchInformeDePublicacion).toHaveBeenCalledWith(5, { etapa: '', desde: '', hasta: '' }));

    await usuario.click(await screen.findByRole('button', { name: 'Ana Prueba' }));
    expect(abrirFicha).toHaveBeenCalledWith(13);

    await usuario.click(screen.getByRole('button', { name: '← Volver a publicaciones' }));
    expect(await esperarPublicacion(PUBLICACION.name)).toBeInTheDocument();
  });

  it('el asesor también puede consultarlo', async () => {
    const usuario = prepararUsuario();
    render(<Publicaciones />);
    await esperarPublicacion(PUBLICACION.name);

    await usuario.click(screen.getByRole('button', { name: 'Ver informe' }));

    expect(await screen.findByRole('heading', { name: /Informe de/ })).toBeInTheDocument();
  });
});

// ============================================================================
// Capítulo 34: la dirección pública que cambia en cada arranque
// ============================================================================
//
// Un túnel de prueba gratuito da otra dirección cada vez que se levanta. Eso no rompe nada
// de forma visible —el post sigue en LinkedIn, la publicación sigue activa— y por eso la
// pantalla tiene que decirlo: es la única señal que habrá.

describe('la dirección pública', () => {
  it('no dibuja nada mientras la dirección responde', async () => {
    render(<Publicaciones puedeGestionar />);
    await screen.findAllByText(PUBLICACION.name);

    // Una franja de advertencia permanente se convierte en parte del decorado en dos días
    // y deja de leerse justo el día que sí pasa algo.
    expect(screen.queryByText(/no responde/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ya no lleva aquí/i)).not.toBeInTheDocument();
  });

  it('avisa cuando la dirección configurada dejó de responder', async () => {
    fetchEstadoDeLaDireccionPublica.mockResolvedValue({
      base: 'https://energy-compare.trycloudflare.com/interes',
      responde: false,
      comprobada_en: '2026-09-25T10:00:00Z',
      detalle: 'HTTP 530',
      publicaciones_con_enlace_caducado: 0,
    });
    render(<Publicaciones puedeGestionar />);

    const aviso = await screen.findByText(/La dirección pública no responde/i);
    expect(aviso).toBeInTheDocument();
    // Dice cuál es la dirección que falla y qué contestó: sin eso, el aviso obliga a ir a
    // buscar el dato a un archivo de configuración para poder hacer algo.
    expect(screen.getByText(/energy-compare\.trycloudflare\.com/)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 530/)).toBeInTheDocument();
  });

  it('no avisa cuando la comprobación está apagada', async () => {
    // `responde: null` es «no se ha preguntado», que es lo que contesta un despliegue sin
    // túnel delante. Tratarlo como una caída encendería una alarma permanente.
    fetchEstadoDeLaDireccionPublica.mockResolvedValue({
      base: 'http://localhost:3000/interes',
      responde: null,
      comprobada_en: null,
      detalle: 'La comprobación está apagada (COMPROBAR_DIRECCION_PUBLICA).',
      publicaciones_con_enlace_caducado: 0,
    });
    render(<Publicaciones puedeGestionar />);
    await screen.findAllByText(PUBLICACION.name);

    expect(screen.queryByText(/no responde/i)).not.toBeInTheDocument();
  });

  it('cuenta las publicaciones cuyo enlace repartido ya no lleva aquí', async () => {
    fetchEstadoDeLaDireccionPublica.mockResolvedValue({
      base: 'https://otra.trycloudflare.com/interes',
      responde: true,
      comprobada_en: '2026-09-25T10:00:00Z',
      detalle: 'HTTP 200',
      publicaciones_con_enlace_caducado: 3,
    });
    render(<Publicaciones puedeGestionar />);

    expect(await screen.findByText(/3 publicaciones repartieron/i)).toBeInTheDocument();
  });

  it('marca la publicación concreta cuyo enlace caducó, sin tapar el enlace bueno', async () => {
    fetchCampaignList.mockResolvedValue({
      total: 1,
      items: [{ ...PUBLICACION, enlace_caducado: true }],
    });
    render(<Publicaciones puedeGestionar />);

    expect(await screen.findByText(/El enlace que se repartió de esta publicación ya no lleva aquí/i))
      .toBeInTheDocument();
    // El enlace de arriba es el de AHORA y se puede copiar: lo que caducó está dentro del
    // post. Si el aviso lo sustituyera, no habría nada que pegar para arreglarlo.
    expect(screen.getByText(ENLACE)).toBeInTheDocument();
  });

  it('un asesor no pide el estado de la dirección', async () => {
    // No tendría ninguna acción disponible con la respuesta: quien reparte los enlaces es
    // quien puede volver a repartirlos.
    render(<Publicaciones />);
    await screen.findAllByText(PUBLICACION.name);

    expect(fetchEstadoDeLaDireccionPublica).not.toHaveBeenCalled();
  });
});
