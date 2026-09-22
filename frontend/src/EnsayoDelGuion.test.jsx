// ============================================================================
// Ensayo del guion de la demo, papel por papel
// ============================================================================
//
// Las demás pruebas comprueban piezas. Esta recorre **las cuatro listas de tareas** de
// `docs/Prueba_Con_Personas.md` sobre la aplicación entera, en el orden en que las va a
// hacer una persona, y falla si alguna tarea deja de poderse terminar.
//
// Por qué así: los atascos de la fase 4 no aparecen dentro de un componente, sino entre
// dos —el texto que se copia y la ruta que lo atiende, la ficha que no se ve porque nadie
// la asignó—. Aquí no se simula `services/api`: se simula el **servidor**, con las mismas
// formas de respuesta que devuelve el backend de verdad, y se deja que corra el cliente
// HTTP real. Un cambio de ruta o de nombre de campo rompe esta prueba, que es lo que se
// quiere.
//
// Lo que NO cubre: que la persona *entienda* la pantalla. Eso solo lo dice sentarla
// delante; para eso está la hoja de observación.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App.jsx';
import PaginaDeInteres from './components/PaginaDeInteres.jsx';

// El cliente llama a rutas relativas bajo `/api/v1`; el ensayo se queda con lo que va
// detrás, que es lo que identifica al endpoint.
const PREFIJO = /^.*\/api\/v1/;
const ENLACE_BASE = 'http://localhost:3000/interes';

const CUENTAS = {
  lider: {
    id: 2, email: 'lider.ventas@plurione.com', full_name: 'Juan Méndez Herrera',
    role: 'Sales_Lead', is_active: true, must_change_password: false,
  },
  asesor: {
    id: 3, email: 'asesor.comercial@plurione.com', full_name: 'Alejandro Morales',
    role: 'Commercial_Executive', is_active: true, must_change_password: false,
  },
};

const PUBLICACION_DE_AGOSTO = {
  id: 5,
  name: 'Post · Equipos de TI en 30 días (agosto)',
  channel: 'LinkedIn',
  description: 'Montar un equipo de TI completo tarda meses. Nosotros lo hacemos en 30 días.',
  target_audience: 'Directores y gerentes de TI',
  public_slug: 'av6_RW2x45Ip_PqJQUWMeA',
  enlace_publico: `${ENLACE_BASE}/av6_RW2x45Ip_PqJQUWMeA`,
  texto_para_linkedin: `Montar un equipo de TI completo tarda meses.\n\n${ENLACE_BASE}/av6_RW2x45Ip_PqJQUWMeA`,
  is_active: true, budget: 3500, created_at: '2026-08-20T10:00:00Z',
};

// La persona que llega por el post durante la prueba.
const LUCIA = {
  id: 16,
  first_name: 'Lucía', last_name: 'Prado',
  email: 'lucia.prado@ejemplo-demo.mx', phone: '+525511223344',
  company: 'Fábrica de Software Norte', job_title: 'Head of Engineering',
  industry: 'Software/TI', company_size: '51-200', annual_revenue: null,
  country: 'México', city: null, source: 'LinkedIn',
  status: 'NEW', qualification_status: 'INCOMING',
  current_score: 41.3, score_category: 'WARM', conversion_probability: 0.41,
  last_score_update: '2026-09-17T22:10:00Z', last_activity_at: '2026-09-17T22:10:00Z',
  privacy_notice_accepted_at: '2026-09-17T22:10:00Z', privacy_notice_source: 'pagina_de_interes',
  created_at: '2026-09-17T22:10:00Z', updated_at: '2026-09-17T22:10:00Z',
  assigned_rep_id: null, campaign_id: 6,
  raw_metadata: { perfil_de_linkedin: 'https://linkedin.com/in/lucia-prado-demo', necesidad: 'vacantes' },
};

const TARJETA_DE_LUCIA = {
  perfil_de_linkedin: 'https://linkedin.com/in/lucia-prado-demo',
  solicitudes: [{
    publicacion_id: 6,
    titulo: 'Post · Equipos de TI en 30 días (septiembre)',
    enlace: `${ENLACE_BASE}/nuevoSlugDeLaPrueba01`,
    recibida_en: '2026-09-17T22:10:00Z',
    necesidad: 'Cubrir vacantes de TI',
    aviso_aceptado_en: '2026-09-17T22:10:00Z',
  }],
};

const RESUMEN = {
  total_leads: 1, hot_leads_count: 0, warm_leads_count: 1, cold_leads_count: 0,
  average_score: 41.3, mql_to_sql_conversion_rate: 0.0,
  pipeline_distribution: { NEW: 1 }, top_industries: [], leads_by_source: [],
};

let servidor;
let escribirEnPortapapeles;

/** Servidor de mentira con las respuestas que da el backend de verdad. */
function crearServidor(cuenta) {
  const estado = {
    usuario: cuenta,
    publicaciones: [{ ...PUBLICACION_DE_AGOSTO }],
    prospecto: { ...LUCIA },
    peticiones: [],
  };

  const responder = (body, status = 200) => Promise.resolve({
    ok: status < 400,
    status,
    headers: new Map(),
    json: async () => body,
  });

  const fetchSimulado = vi.fn(async (url, opciones = {}) => {
    const metodo = (opciones.method || 'GET').toUpperCase();
    const ruta = String(url).split('?')[0].replace(PREFIJO, '');
    const cuerpo = opciones.body ? JSON.parse(opciones.body) : null;
    estado.peticiones.push({ metodo, ruta, cuerpo });

    if (ruta === '/auth/refresh') {
      return responder({ access_token: 'token-de-ensayo', token_type: 'bearer', expires_in: 900, user: estado.usuario });
    }
    if (ruta === '/analytics/summary') return responder(RESUMEN);
    if (ruta === '/analytics/campaigns') return responder([]);
    if (ruta === '/sales-reps') {
      return responder({ total: 1, items: [{ ...CUENTAS.asesor, is_sales_rep: true, capacity: 50, leads_asignados: 4 }] });
    }

    if (ruta === '/leads' && metodo === 'GET') {
      // El asesor solo ve lo suyo, igual que el repositorio del servidor.
      const suyo = estado.usuario.role !== 'Commercial_Executive'
        || estado.prospecto.assigned_rep_id === estado.usuario.id;
      const items = suyo ? [estado.prospecto] : [];
      return responder({ items, total: items.length, limit: 50, offset: 0 });
    }
    if (ruta === `/leads/${estado.prospecto.id}` && metodo === 'GET') {
      return responder({ ...estado.prospecto, activities: [], score_histories: [], latest_explanation: null, llego_por: TARJETA_DE_LUCIA });
    }
    if (ruta === `/leads/${estado.prospecto.id}` && metodo === 'PUT') {
      Object.assign(estado.prospecto, cuerpo);
      return responder({ ...estado.prospecto, activities: [], score_histories: [], latest_explanation: null, llego_por: TARJETA_DE_LUCIA });
    }
    if (ruta === `/leads/${estado.prospecto.id}/activities` && metodo === 'POST') {
      return responder({
        id: 99, lead_id: estado.prospecto.id, activity_type: cuerpo.activity_type,
        channel: 'Teléfono', source: 'manual', external_event_id: null, verificada: false,
        direction: null, call_outcome: cuerpo.call_outcome, activity_data: {},
        occurred_at: '2026-09-17T23:00:00Z', created_at: '2026-09-17T23:00:00Z',
        score_anterior: 41.3, score: 44.0, score_category: 'WARM',
      }, 201);
    }

    if (ruta === '/campaigns' && metodo === 'GET') {
      return responder({ total: estado.publicaciones.length, items: estado.publicaciones });
    }
    if (ruta === '/campaigns' && metodo === 'POST') {
      const slug = 'nuevoSlugDeLaPrueba01';
      const nueva = {
        ...cuerpo, id: 6, public_slug: slug, is_active: true, budget: 0,
        created_at: '2026-09-17T21:00:00Z',
        enlace_publico: `${ENLACE_BASE}/${slug}`,
        texto_para_linkedin: `${cuerpo.description}\n\n${ENLACE_BASE}/${slug}`,
      };
      estado.publicaciones = [...estado.publicaciones, nueva];
      return responder(nueva, 201);
    }

    if (ruta === '/publicaciones/nuevos-sin-asesor') {
      return responder({ total: estado.prospecto.assigned_rep_id ? 0 : 1 });
    }
    if (ruta === '/publicaciones/comparativa') {
      return responder({
        items: estado.publicaciones.map((p) => ({
          publicacion_id: p.id, titulo: p.name, activa: p.is_active,
          perfiles_recibidos: p.id === 5 ? 3 : 1,
          avanzaron_de_etapa: 0,
          score_medio: p.id === 5 ? 32.8 : 41.3,
        })),
      });
    }
    if (/^\/publicaciones\/\d+\/informe$/.test(ruta)) {
      const id = Number(ruta.split('/')[2]);
      const publicacion = estado.publicaciones.find((p) => p.id === id);
      const filas = id === 6 ? [{
        lead_id: estado.prospecto.id,
        nombre: `${estado.prospecto.first_name} ${estado.prospecto.last_name}`,
        empresa: estado.prospecto.company, cargo: estado.prospecto.job_title,
        score: estado.prospecto.current_score, categoria: estado.prospecto.score_category,
        etapa: estado.prospecto.status,
        asesor: estado.prospecto.assigned_rep_id ? CUENTAS.asesor.full_name : null,
        recibida_en: '2026-09-17T22:10:00Z',
      }] : [];
      return responder({
        publicacion: { id, titulo: publicacion.name, enlace: publicacion.enlace_publico, activa: true },
        resumen: {
          perfiles_recibidos: filas.length, avanzaron_de_etapa: 0,
          score_medio: filas.length ? filas[0].score : 0,
          de_otros_asesores: 0, alcance_completo: true,
        },
        filas, total: filas.length, limit: 50, offset: 0,
      });
    }

    // La página pública no lleva sesión y tiene su propio cliente.
    if (/^\/interes\//.test(ruta) && metodo === 'GET') {
      return responder({
        titulo: PUBLICACION_DE_AGOSTO.name,
        descripcion: PUBLICACION_DE_AGOSTO.description,
        opciones: {
          cargos: ['CTO', 'Head of Engineering'],
          sectores: ['FinTech', 'Software/TI'],
          tamanos: ['11-50', '51-200'],
          necesidades: { vacantes: 'Cubrir vacantes de TI', demo: 'Ver una demostración' },
        },
      });
    }
    if (/^\/interes\//.test(ruta) && metodo === 'POST') {
      return responder({
        mensaje: 'Gracias por tu interés. Un asesor de PluriOne se pondrá en contacto contigo.',
        recibido_en: '2026-09-17T22:10:00Z',
      }, 202);
    }

    return responder({ detail: `Ruta no prevista en el ensayo: ${metodo} ${ruta}` }, 404);
  });

  globalThis.fetch = fetchSimulado;
  return estado;
}

/** `userEvent.setup()` instala su propio portapapeles; el de la prueba va después. */
function prepararUsuario() {
  const usuario = userEvent.setup();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: escribirEnPortapapeles }, configurable: true,
  });
  return usuario;
}

beforeEach(() => {
  escribirEnPortapapeles = vi.fn().mockResolvedValue(undefined);
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ============================================================================
// A. Marketing: crear la publicación y copiar su texto
// ============================================================================

describe('A. Marketing', () => {
  beforeEach(() => {
    servidor = crearServidor(CUENTAS.lider);
  });

  it('entra, crea la publicación y se lleva el texto con su enlace', async () => {
    const usuario = prepararUsuario();
    render(<App />);
    await screen.findByText(/Juan Méndez/);

    // Tarea 2: crear la publicación.
    await usuario.click(screen.getByRole('button', { name: /Publicaciones/ }));
    await usuario.click(await screen.findByRole('button', { name: '+ Nueva publicación' }));
    await usuario.type(screen.getByLabelText('Título interno'), 'Post · Equipos de TI en 30 días (septiembre)');
    await usuario.type(screen.getByLabelText('Texto de la publicación'), 'Montamos tu equipo de TI en 30 días.');
    await usuario.type(screen.getByLabelText('A quién va dirigida'), 'Directores de TI');
    await usuario.click(screen.getByRole('button', { name: 'Crear publicación' }));

    expect(await screen.findByRole('status')).toHaveTextContent('creada');

    // Tarea 3: llevarse el texto listo, sin escribir el enlace a mano.
    const lista = await screen.findByRole('list', { name: 'Publicaciones' });
    const fila = within(lista).getByText('Post · Equipos de TI en 30 días (septiembre)').closest('li');
    await usuario.click(within(fila).getByRole('button', { name: 'Copiar texto para LinkedIn' }));

    expect(escribirEnPortapapeles).toHaveBeenCalledTimes(1);
    const copiado = escribirEnPortapapeles.mock.calls[0][0];
    expect(copiado).toContain('Montamos tu equipo de TI en 30 días.');
    // El enlace copiado tiene que ser el de la página pública. Con `/p` llevaba a la
    // pantalla de acceso, y eso solo se descubre siguiéndolo.
    expect(copiado).toContain(`${ENLACE_BASE}/nuevoSlugDeLaPrueba01`);
  });
});

// ============================================================================
// B. Interesado: enviar su perfil desde el teléfono
// ============================================================================

describe('B. Interesado', () => {
  beforeEach(() => {
    servidor = crearServidor(CUENTAS.lider);
  });

  it('abre el enlace, lee de qué va y pide que le contacten', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="nuevoSlugDeLaPrueba01" />);

    // Tarea 2: lo primero que ve es de qué va, no un formulario a secas.
    expect(await screen.findByRole('heading', { name: PUBLICACION_DE_AGOSTO.name })).toBeInTheDocument();

    await usuario.type(screen.getByLabelText('Nombre'), 'Lucía Prado');
    await usuario.type(screen.getByLabelText('Correo de trabajo'), 'lucia.prado@ejemplo-demo.mx');
    await usuario.type(screen.getByLabelText('Empresa'), 'Fábrica de Software Norte');
    await usuario.selectOptions(screen.getByLabelText('Cargo'), 'Head of Engineering');
    await usuario.selectOptions(screen.getByLabelText('Empleados'), '51-200');
    await usuario.selectOptions(screen.getByLabelText('Sector'), 'Software/TI');
    // Un toque, no una lista desplegable.
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    // Tarea 4: opcional y plegado; pegado tal cual, como lo entrega la aplicación de LinkedIn.
    await usuario.click(screen.getByText('Añadir más datos (opcional)'));
    await usuario.type(
      screen.getByLabelText('Tu perfil de LinkedIn'),
      'linkedin.com/in/lucia-prado-demo?utm_source=share&utm_medium=member_ios',
    );
    await usuario.click(screen.getByRole('checkbox'));
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    expect(await screen.findByText(/Gracias por tu interés/)).toBeInTheDocument();
    const envio = servidor.peticiones.find((p) => p.metodo === 'POST' && p.ruta.startsWith('/interes/'));
    expect(envio.cuerpo.linkedin).toBe('linkedin.com/in/lucia-prado-demo?utm_source=share&utm_medium=member_ios');
    expect(envio.cuerpo.aviso_de_privacidad).toBe(true);
  });
});

// ============================================================================
// C. Líder: ver lo que llegó, entenderlo y repartirlo
// ============================================================================

describe('C. Líder', () => {
  beforeEach(() => {
    servidor = crearServidor(CUENTAS.lider);
    servidor.publicaciones = [
      { ...PUBLICACION_DE_AGOSTO },
      {
        ...PUBLICACION_DE_AGOSTO, id: 6, name: 'Post · Equipos de TI en 30 días (septiembre)',
        public_slug: 'nuevoSlugDeLaPrueba01', enlace_publico: `${ENLACE_BASE}/nuevoSlugDeLaPrueba01`,
      },
    ];
  });

  it('cuenta los que llegaron sin asesor, compara publicaciones y reparte', async () => {
    const usuario = prepararUsuario();
    render(<App />);
    await screen.findByText(/Juan Méndez/);
    await usuario.click(screen.getByRole('button', { name: /Publicaciones/ }));

    // Tarea 1: cuántos han llegado por LinkedIn y siguen sin asesor.
    expect(await screen.findByText(/Nuevos desde LinkedIn sin asesor/)).toBeInTheDocument();

    // Tarea 2: las dos publicaciones, uno al lado de otra.
    const comparativa = screen.getByRole('table');
    expect(within(comparativa).getByRole('row', { name: /septiembre/ })).toHaveTextContent('41.3');
    expect(within(comparativa).getByRole('row', { name: /agosto/ })).toHaveTextContent('32.8');

    // Tarea 3: de la publicación nueva a la ficha de quien respondió.
    const lista = await screen.findByRole('list', { name: 'Publicaciones' });
    const fila = within(lista).getByText('Post · Equipos de TI en 30 días (septiembre)').closest('li');
    await usuario.click(within(fila).getByRole('button', { name: 'Ver informe' }));
    await usuario.click(await screen.findByRole('button', { name: 'Lucía Prado' }));

    // La ficha dice por dónde llegó y qué pidió, sin preguntárselo a nadie.
    expect(await screen.findByRole('heading', { name: /Llegó por/ })).toBeInTheDocument();
    expect(screen.getByText(/Cubrir vacantes de TI/)).toBeInTheDocument();
    expect(screen.getByText(/Aceptó el aviso de privacidad el/)).toBeInTheDocument();

    // Tarea 4: asignársela al asesor.
    await usuario.selectOptions(await screen.findByLabelText('Asignar a'), String(CUENTAS.asesor.id));
    await usuario.click(screen.getByRole('button', { name: 'Asignar' }));

    await waitFor(() => {
      const asignacion = servidor.peticiones.find((p) => p.metodo === 'PUT' && p.ruta === '/leads/16');
      expect(asignacion.cuerpo).toEqual({ assigned_rep_id: CUENTAS.asesor.id });
    });
  });
});

// ============================================================================
// D. Asesor: encontrarla, entenderla y atenderla
// ============================================================================

describe('D. Asesor', () => {
  beforeEach(() => {
    servidor = crearServidor(CUENTAS.asesor);
  });

  it('sin asignar no la ve; asignada, la abre, la entiende y registra la llamada', async () => {
    const usuario = prepararUsuario();
    const { unmount } = render(<App />);
    await screen.findByText(/Alejandro Morales/);

    // Lo que la hoja avisa que hay que mirar: hasta que el líder no reparte, no hay nada.
    await waitFor(() => expect(servidor.peticiones.some((p) => p.ruta === '/leads')).toBe(true));
    expect(screen.queryByText('Lucía Prado')).not.toBeInTheDocument();
    unmount();

    servidor.prospecto.assigned_rep_id = CUENTAS.asesor.id;
    render(<App />);
    await screen.findByText(/Alejandro Morales/);

    // Tarea 2: abrir su ficha.
    await usuario.click(await screen.findByText('Lucía Prado'));

    // Tarea 3: las cuatro preguntas se responden en la propia ficha.
    expect(await screen.findByRole('heading', { name: /Llegó por/ })).toBeInTheDocument();
    expect(screen.getByText('Post · Equipos de TI en 30 días (septiembre)')).toBeInTheDocument();
    expect(screen.getByText(/Cubrir vacantes de TI/)).toBeInTheDocument();
    expect(screen.getByText(/Aceptó el aviso de privacidad el/)).toBeInTheDocument();
    const perfil = screen.getByRole('link', { name: /Ver perfil de LinkedIn/ });
    expect(perfil).toHaveAttribute('href', 'https://linkedin.com/in/lucia-prado-demo');
    expect(perfil).toHaveAttribute('target', '_blank');

    // Tarea 4: dejar constancia de la llamada que no contestó.
    const registro = screen.getByRole('radiogroup', { name: 'Tipo de interacción' });
    await usuario.click(within(registro).getByRole('radio', { name: /^Llamada/ }));
    await usuario.click(within(screen.getByRole('radiogroup', { name: 'Resultado de la llamada' })).getByRole('radio', { name: 'No contestó' }));
    await usuario.click(screen.getByRole('button', { name: /Registrar y Recalcular/ }));

    await waitFor(() => {
      const actividad = servidor.peticiones.find((p) => p.ruta === '/leads/16/activities');
      expect(actividad.cuerpo.activity_type).toBe('PHONE_CALL');
      expect(actividad.cuerpo.call_outcome).toBe('NO_CONTESTO');
    });
  });
});
