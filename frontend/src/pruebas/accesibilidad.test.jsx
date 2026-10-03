// ============================================================================
// Accesibilidad: todas las pantallas, revisadas por un motor y no por una lectura
// ============================================================================
//
// La cabecera decía «las ocho pantallas» y era verdad: ocho, de dieciocho que llevan cajas
// de formulario. **La lista estaba escrita a mano**, y es la misma forma que el capítulo 43
// encontró en `PARES`: lo que la suite mide no es el cliente, es el inventario que alguien
// escribió. Las nueve que faltaban llevaban 39 de las 105 cajas del cliente, y en ellas
// había tres controles sin nombre accesible y dos pantallas enteras fuera de toda región.
//
// La diferencia se ve en una frase que ya estaba escrita: `LoginScreen` abre con
// «`<main>` y no un `<div>`: es la pantalla entera y no estaba dentro de ninguna región».
// Eso lo arregló el capítulo 36 **porque esta auditoría la montaba**. El cambio obligatorio
// de contraseña y el alta del segundo factor son también la pantalla entera, nunca se
// montaron aquí, y seguían siendo un `<div>`. El defecto no estaba repartido al azar:
// seguía la lista.
//
// Desde el capítulo 44 la lista no se escribe, se comprueba: `pantallas.test.js` la deriva
// del código y se pone roja cuando una pantalla con controles no aparece en este archivo.
//
// Hasta este capítulo la accesibilidad del cliente estaba cubierta por **una sola regla**
// del `linter` —`label-has-associated-control`— y el resto del plugin estaba apagado con
// una nota que decía por qué: «el conjunto completo señala además cosas de otras familias
// (roles ARIA, orden de foco, texto alternativo) que no se han revisado todavía». Esa nota
// es la deuda que este archivo paga.
//
// Qué hace: monta cada pantalla con sus datos y le pasa `axe-core` encima, exigiendo el
// nivel **AA** de WCAG 2.1. Una pantalla que deje de cumplirlo pone el pipeline en rojo.
//
// Por qué una por una y no una sola prueba que recorra todo: cuando falla, el nombre de la
// prueba dice qué pantalla es. Una prueba única diría «accesibilidad» y habría que leer el
// volcado entero para saber dónde mirar.
//
// Lo que esto NO comprueba, dicho aquí para que no se le suponga alcance de más:
// * **contraste** —necesita píxeles, y `jsdom` no dibuja—: va en `contraste.test.js`;
// * **el recorrido con el tabulador** —`axe` mira el marcado, no el orden real del foco—:
//   va en `teclado.test.jsx`;
// * **si un lector de pantalla de verdad lo anuncia bien**. Ninguna herramienta automática
//   responde a eso. Lo que sí se comprueba es que el marcado que esos lectores leen esté
//   puesto y bien puesto, que es la parte verificable sin una persona delante.

import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { noDebeTenerInfracciones } from './accesibilidad.js';

// El módulo de servicios entero simulado, export por export, con el mismo criterio que
// `App.test.jsx`: enumerar a mano dejaría fuera cualquier función que un componente hijo
// llame sin que este archivo lo sepa.
vi.mock('../services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import * as api from '../services/api';

import PaginaDeInteres from '../components/PaginaDeInteres.jsx';
import LoginScreen from '../components/LoginScreen.jsx';
import LeadDetailModal from '../components/LeadDetailModal.jsx';
import Publicaciones from '../components/Publicaciones.jsx';
import BandejaDeHoy from '../components/BandejaDeHoy.jsx';
import InformeDePublicacion from '../components/InformeDePublicacion.jsx';
import PanelDeDesenlaces from '../components/PanelDeDesenlaces.jsx';
import DerechosDelTitular from '../components/DerechosDelTitular.jsx';
import NewLeadModal from '../components/NewLeadModal.jsx';
import App from '../App.jsx';

// Las nueve del capítulo 44.
import AdminPanel from '../components/AdminPanel.jsx';
import ScoringSimulator from '../components/ScoringSimulator.jsx';
import SessionModal from '../components/SessionModal.jsx';
import CambioDeContrasenaObligatorio from '../components/CambioDeContrasenaObligatorio.jsx';
import AltaDelSegundoFactor from '../components/AltaDelSegundoFactor.jsx';
import BandejaSinAsociar from '../components/BandejaSinAsociar.jsx';
import CerrarProspecto from '../components/CerrarProspecto.jsx';
import CompartirEnRedes from '../components/CompartirEnRedes.jsx';
import AsignarAsesor from '../components/AsignarAsesor.jsx';
import LeadsTable from '../components/LeadsTable.jsx';

// ---------------------------------------------------------------------------
// Datos. Realistas y no vacíos a propósito: una pantalla sin filas no tiene tabla, y una
// tabla sin cabeceras es justo una de las cosas que esta revisión busca.
// ---------------------------------------------------------------------------

const ENLACE = 'http://localhost:3000/interes/Qm9sYS1kZS1wcnVlYmEtMQ';

const OPCIONES = {
  cargos: ['CTO', 'CIO', 'Gerente de Talento TI'],
  sectores: ['FinTech', 'Software/TI'],
  tamanos: ['1-10', '51-200'],
  necesidades: { vacantes: 'Cubrir vacantes de TI', demo: 'Ver una demostración' },
};

const PUBLICACION_PUBLICA = {
  titulo: 'Post · Talento TI septiembre',
  descripcion: '¿Tu equipo de TI tarda meses en cubrir una vacante? Te contamos cómo lo resolvemos.',
  opciones: OPCIONES,
};

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
  necesidades: [
    { clave: 'vacantes', etiqueta: 'Cubrir vacantes de TI' },
    { clave: 'demo', etiqueta: 'Ver una demostración' },
  ],
  necesidades_propias: false,
  budget: 0,
  created_at: '2026-09-17T10:00:00Z',
};

const INFORME = {
  publicacion: { id: 5, titulo: PUBLICACION.name, enlace: ENLACE, activa: true, estado: 'activa' },
  resumen: {
    perfiles_recibidos: 2, avanzaron_de_etapa: 1, score_medio: 60.0,
    de_otros_asesores: 0, alcance_completo: true, visitas: 40, envios: 5, tasa_de_envio: 12.5,
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
  total: 2, limit: 50, offset: 0, por_dia: [], grafico_recortado: false,
};

const EN_DOS_HORAS = new Date(Date.now() + 2 * 3600_000).toISOString();

const BANDEJA = {
  asesor_id: 3,
  tareas: [{
    id: 1, regla: 'primer_contacto', regla_etiqueta: 'Primer contacto',
    motivo: 'Asignado y todavía sin contactar.', estado: 'abierta',
    vence_el: EN_DOS_HORAS, vencida: false,
    creada_en: '2026-09-25T06:00:00Z',
    prospecto: { id: 10, nombre: 'Rosa Lima', empresa: 'Lima SA', score: 72, categoria: 'HOT' },
  }],
  vencidas: 0, para_hoy: 1, mas_adelante: 0,
};

const DESENLACES = {
  desde: null, hasta: null,
  resumen: {
    cerrados: 10, ganados: 4, perdidos: 6, tasa_de_ganados: 40.0,
    score_medio_de_los_ganados: 78.5, score_medio_de_los_perdidos: 41.2,
  },
  por_motivo: [{
    resultado: 'perdido', resultado_etiqueta: 'Perdido', motivo: 'precio',
    motivo_etiqueta: 'Precio', casos: 4, porcentaje: 66.7, score_medio: 44.0,
  }],
  por_tramo: [{ tramo: 'no_consta', etiqueta: 'Todavía no consta', casos: 2 }],
  por_publicacion: [{
    publicacion_id: 5, titulo: 'Perfiles TI en octubre',
    ganados: 3, perdidos: 2, tasa_de_ganados: 60.0, score_medio_al_cierre: 70.1,
  }],
  por_red: [{
    red: 'whatsapp', etiqueta: 'WhatsApp', ganados: 2, perdidos: 1,
    tasa_de_ganados: 66.7, score_medio_al_cierre: 68.0,
  }],
  acierto_del_score: [
    { categoria: 'HOT', casos: 4, ganados: 3, perdidos: 1, tasa_de_ganados: 75.0 },
    { categoria: 'WARM', casos: 6, ganados: 1, perdidos: 5, tasa_de_ganados: 16.7 },
    { categoria: 'COLD', casos: 0, ganados: 0, perdidos: 0, tasa_de_ganados: null },
  ],
  reentrenamiento: {
    utilizables: 10, faltan: 190, minimo: 200, minimo_por_clase: 50,
    ganados_utilizables: 4, perdidos_utilizables: 6, listo: false,
  },
};

function actividad(campos) {
  return {
    channel: 'Web', direction: null, call_outcome: null, external_event_id: null,
    activity_data: {}, created_at: '2026-09-10T12:00:00Z', ...campos,
  };
}

const PROSPECTO = {
  id: 7,
  first_name: 'Ana', last_name: 'Ruiz', email: 'ana.ruiz@empresa.test',
  phone: '+525512345678', company: 'Empresa de Pruebas', job_title: 'CTO',
  industry: 'FinTech', company_size: '51-200', country: 'México', city: 'Monterrey',
  status: 'PROPOSAL_SENT', score_category: 'WARM', current_score: 47.8,
  conversion_probability: 0.41, raw_metadata: {}, latest_explanation: {},
  activities: [
    actividad({ id: 1, activity_type: 'PROPOSAL_SENT', source: 'pipeline', verificada: false, occurred_at: '2026-09-01T10:00:00Z' }),
    actividad({ id: 2, activity_type: 'MEETING_SCHEDULED', source: 'calendly', verificada: true, occurred_at: '2026-09-02T10:00:00Z' }),
    actividad({ id: 3, activity_type: 'PHONE_CALL', source: 'manual', verificada: false, call_outcome: 'BUZON', occurred_at: '2026-09-03T10:00:00Z' }),
  ],
};

const LIDER = {
  id: 3, email: 'lider@plurione.test', full_name: 'Laura Líder',
  role: 'Sales_Lead', must_change_password: false,
  totp_activo: true, segundo_factor_obligatorio: false,
};

const PROSPECTOS = [
  {
    id: 10, first_name: 'Rosa', last_name: 'Lima', email: 'rosa.lima@lima.test',
    company: 'Lima SA', job_title: 'CTO', current_score: 72.0, score_category: 'HOT',
    status: 'NEW', created_at: '2026-09-20T10:00:00Z', assigned_rep_id: null,
  },
  {
    id: 11, first_name: 'Beto', last_name: 'Muestra', email: 'beto@otra.test',
    company: 'Otra SA', job_title: 'CIO', current_score: 40.0, score_category: 'COLD',
    status: 'CONTACTED', created_at: '2026-09-19T10:00:00Z', assigned_rep_id: 3,
  },
];

// ---------------------------------------------------------------------------

beforeEach(() => {
  for (const clave of Object.keys(api)) {
    if (typeof api[clave]?.mockReset === 'function') api[clave].mockReset();
  }
  // Lo que cada pantalla pide al abrirse. Se deja todo puesto aquí en vez de en cada
  // prueba: lo que se audita es el marcado, y una pantalla a medio cargar no lo enseña.
  api.getCurrentUserRole.mockReturnValue('Sales_Lead');
  api.getCurrentUser.mockReturnValue(LIDER);
  api.isAuthenticated.mockReturnValue(true);
  api.restoreSession.mockResolvedValue(LIDER);
  api.logout.mockResolvedValue(undefined);
  api.fetchPublicacionDeInteres.mockResolvedValue(PUBLICACION_PUBLICA);
  api.enviarInteres.mockResolvedValue({ mensaje: 'Gracias por tu interés.', recibido_en: '2026-09-25T12:00:00Z' });
  api.fetchCampaignList.mockResolvedValue({ total: 1, items: [PUBLICACION] });
  api.fetchSalesReps.mockResolvedValue({ total: 1, items: [{ id: 21, full_name: 'Ana Torres', is_active: true, leads_asignados: 3 }] });
  api.fetchComparativaDePublicaciones.mockResolvedValue({
    items: [{
      publicacion_id: 5, titulo: PUBLICACION.name, activa: true, estado: 'activa',
      perfiles_recibidos: 4, avanzaron_de_etapa: 2, score_medio: 61.5,
      visitas: 40, envios: 5, tasa_de_envio: 12.5,
    }],
  });
  api.fetchNuevosSinAsesor.mockResolvedValue({ total: 3 });
  api.fetchEstadoDeLaDireccionPublica.mockResolvedValue({
    base: 'http://localhost:3000/interes', responde: true,
    comprobada_en: '2026-09-25T10:00:00Z', detalle: 'HTTP 200',
    publicaciones_con_enlace_caducado: 0,
  });
  api.fetchInformeDePublicacion.mockResolvedValue(INFORME);
  api.fetchBandejaDeHoy.mockResolvedValue(BANDEJA);
  api.fetchHotQueSeEnfrian.mockResolvedValue({ total: 0, filas: [] });
  api.fetchPanelDeDesenlaces.mockResolvedValue(DESENLACES);
  api.fetchAvisos.mockResolvedValue({ total: 0, sin_leer: 0, items: [] });
  api.fetchAnalyticsSummary.mockResolvedValue({
    total_leads: 2, hot_leads: 1, warm_leads: 0, cold_leads: 1,
    average_score: 56.0, conversion_rate: 12.5,
    by_category: { HOT: 1, WARM: 0, COLD: 1 },
    by_status: { NEW: 1, CONTACTED: 1 },
  });
  api.fetchCampaigns.mockResolvedValue([PUBLICACION]);
  api.fetchLeads.mockResolvedValue({ items: PROSPECTOS, total: 2 });
  // La forma de este doble estaba mal y no se notaba: los motivos iban en un diccionario
  // de primer nivel y no dentro de cada resultado, y no traía `pide_tramo`. El servidor los
  // manda dentro (`OpcionDeResultado.motivos`), que es de donde los lee el formulario.
  // Mientras ninguna prueba eligiera un desenlace, la diferencia no salía: la pantalla no
  // llegaba a pintar la lista. La del capítulo 44 sí elige, y con la forma vieja reventaba.
  api.fetchOpcionesDeCierre.mockResolvedValue({
    resultados: [
      {
        clave: 'ganado', etiqueta: 'Ganado', pide_tramo: true,
        motivos: [{ clave: 'precio', etiqueta: 'Precio', descripcion: 'Ganado por precio.' }],
      },
      {
        clave: 'perdido', etiqueta: 'Perdido', pide_tramo: false,
        motivos: [{ clave: 'precio', etiqueta: 'Precio', descripcion: 'Perdido por precio.' }],
      },
    ],
    tramos: [{ clave: 'no_consta', etiqueta: 'Todavía no consta' }],
  });
});

describe('la página de interés', () => {
  it('cumple el nivel AA', async () => {
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    await noDebeTenerInfracciones();
  });

  it('también cuando el formulario está enseñando sus errores', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    // Enviar en blanco: el estado con errores es tan real como el otro, y es el que lleva
    // los `aria-invalid`, los `aria-describedby` y el resumen. Auditar solo el estado
    // limpio dejaría sin revisar justo el marcado que existe para el lector de pantalla.
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));
    await screen.findByText('Escribe tu nombre.');

    await noDebeTenerInfracciones();
  });

  it('y cuando el enlace ya no vale', async () => {
    api.fetchPublicacionDeInteres.mockRejectedValue(
      Object.assign(new Error('Publicación no disponible'), { status: 404 }),
    );
    render(<PaginaDeInteres slug="caducado" />);
    await screen.findByRole('heading', { name: /no está disponible/ });

    await noDebeTenerInfracciones();
  });
});

describe('la pantalla de acceso', () => {
  it('cumple el nivel AA', async () => {
    render(<LoginScreen onAuthenticated={vi.fn()} />);
    await screen.findByLabelText(/Correo/);

    await noDebeTenerInfracciones();
  });

  it('y el segundo paso, el del código', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    api.login.mockResolvedValue({ tipo: 'segundo_factor', desafio: 'un-desafio', expira_en: 300 });
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await usuario.type(await screen.findByLabelText(/Correo/), 'lider@plurione.test');
    await usuario.type(screen.getByLabelText(/Contraseña/), 'Una-Contrasena-Larga-1');
    await usuario.click(screen.getByRole('button', { name: 'Iniciar sesión' }));
    await screen.findByLabelText('Código');

    await noDebeTenerInfracciones();
  });
});

describe('el tablero', () => {
  it('cumple el nivel AA con la aplicación entera montada', async () => {
    render(<App />);
    await screen.findByRole('navigation');
    // La bandeja «Hoy» es la pestaña con la que abre la aplicación.
    await screen.findByText(/Rosa Lima/);

    await noDebeTenerInfracciones();
  });

  it('y la pestaña de analíticas con sus tarjetas y su tabla', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(<App />);
    await screen.findByRole('navigation');

    await usuario.click(within(screen.getByRole('navigation')).getByRole('button', { name: /Tablero|Dashboard|Analítica/i }));
    await waitFor(() => expect(api.fetchLeads).toHaveBeenCalled());

    await noDebeTenerInfracciones();
  });
});

describe('la ficha 360', () => {
  it('cumple el nivel AA', async () => {
    render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} />);
    await screen.findByText(/Ana Ruiz/);

    await noDebeTenerInfracciones();
  });

  it('y en modo edición, que es donde están casi todos los campos', async () => {
    render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} startInEditMode />);
    await screen.findByLabelText(/Nombre/);

    await noDebeTenerInfracciones();
  });
});

describe('publicaciones', () => {
  it('cumple el nivel AA', async () => {
    render(<Publicaciones puedeGestionar onSelectLead={vi.fn()} />);
    await screen.findByRole('button', { name: 'Copiar texto para LinkedIn' });

    await noDebeTenerInfracciones();
  });
});

describe('la bandeja «Hoy»', () => {
  it('cumple el nivel AA', async () => {
    render(<BandejaDeHoy onSelectLead={vi.fn()} esDireccion />);
    await screen.findByText(/Rosa Lima/);

    await noDebeTenerInfracciones();
  });
});

describe('el informe de una publicación', () => {
  it('cumple el nivel AA', async () => {
    render(<InformeDePublicacion publicacion={PUBLICACION} onCerrar={vi.fn()} onSelectLead={vi.fn()} />);
    await screen.findByText('Perfiles recibidos');

    await noDebeTenerInfracciones();
  });
});

describe('el panel de desenlaces', () => {
  it('cumple el nivel AA', async () => {
    render(<PanelDeDesenlaces />);
    await screen.findByText(/Precio/);

    await noDebeTenerInfracciones();
  });
});

// La novena pantalla, desde el capítulo 38. Se audita en sus tres estados porque los tres
// llevan marcado distinto: el formulario solo, el resultado con su tabla, y el bloque de
// confirmación del borrado, que es el único con un campo que no está dentro de un `<form>`.
describe('los derechos del titular', () => {
  const DOCUMENTO = {
    formato: 'plurione.titular/1',
    prospecto_id: 42,
    datos_del_prospecto: {
      first_name: 'Ana', last_name: 'Titular', email: 'ana.titular@ejemplo.test',
      phone: '+525512345678', company: 'Conservas Titular', job_title: 'CTO',
      source: 'WhatsApp', privacy_notice_accepted_at: '2026-09-20T09:30:00+00:00',
      privacy_notice_source: 'pagina_de_interes',
    },
    campana: { id: 5, name: 'Post · Talento TI septiembre', channel: 'LinkedIn' },
    actividades: [{ id: 1 }, { id: 2 }],
    historial_de_puntuacion: [{ id: 1 }],
    tareas: [],
    tratamientos_registrados: [{ accion: 'lead.crear' }],
    conservacion: { resto_de_datos: 'Mientras el prospecto exista.' },
    fuera_de_la_base: ['Copias de seguridad: los volcados diarios conservan los datos.'],
  };

  beforeEach(() => {
    api.buscarTitularPorCorreo.mockResolvedValue({ id: 42, email: 'ana.titular@ejemplo.test' });
    api.exportarDatosDelTitular.mockResolvedValue(DOCUMENTO);
  });

  it('cumple el nivel AA con el formulario recién abierto', async () => {
    render(<DerechosDelTitular />);
    await screen.findByLabelText('Correo de la persona');

    await noDebeTenerInfracciones();
  });

  it('y con el resultado de una consulta en pantalla', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(<DerechosDelTitular />);

    await usuario.type(await screen.findByLabelText('Correo de la persona'), 'ana.titular@ejemplo.test');
    await usuario.click(screen.getByRole('button', { name: 'Consultar qué consta' }));
    await screen.findByText('Ana Titular');

    await noDebeTenerInfracciones();
  });

  it('y con el bloque de confirmación del borrado abierto', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(<DerechosDelTitular />);

    await usuario.type(await screen.findByLabelText('Correo de la persona'), 'ana.titular@ejemplo.test');
    await usuario.click(screen.getByRole('button', { name: 'Consultar qué consta' }));
    await screen.findByText('Ana Titular');
    await usuario.click(screen.getByRole('button', { name: 'Suprimir estos datos…' }));
    await screen.findByLabelText(/Escriba el correo completo/);

    await noDebeTenerInfracciones();
  });
});

// ============================================================================
// Un formulario con los campos marcados por el servidor (capítulo 40)
// ============================================================================
//
// Las nueve pantallas de arriba se revisan en su estado de reposo, que es el que tienen al
// abrirlas. Un formulario con errores es **otro estado del marcado** —aparecen
// `aria-invalid`, `aria-describedby` y un `role="alert"`—, y es justo el estado que el
// capítulo 40 añadió a cuatro pantallas.
//
// Lo que esto caza y ninguna otra prueba del capítulo caza: un `aria-describedby` que
// apunte a un `id` que no existe. Es la forma en que este mecanismo se puede romper en
// silencio —el atributo sigue siendo válido, el campo se pinta igual, y el lector de
// pantalla no lee nada—, y `axe` lo marca como infracción.

describe('el alta de un prospecto con el servidor quejándose', () => {
  it('no tiene infracciones con los campos marcados', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    const err = new Error('Error de validación');
    err.status = 422;
    err.detalle = [
      { type: 'missing', loc: ['body', 'company'], msg: 'Field required' },
      {
        type: 'value_error',
        loc: ['body', 'phone'],
        msg: 'Value error, El teléfono no es un número válido: revise la lada y el número de dígitos.',
      },
    ];
    api.createLead.mockRejectedValue(err);
    render(<NewLeadModal onClose={() => {}} onLeadCreated={() => {}} />);

    await usuario.type(screen.getByLabelText('Nombre *'), 'Ana');
    await usuario.type(screen.getByLabelText('Apellido *'), 'Titular');
    await usuario.type(screen.getByLabelText('Correo Electrónico *'), 'ana@ejemplo.test');
    await usuario.click(screen.getByRole('button', { name: /Guardar y Calificar/ }));
    await waitFor(() => expect(screen.getByLabelText('Empresa / Institución'))
      .toHaveAttribute('aria-invalid', 'true'));

    // Y los dos `id` que el marcado promete existen de verdad en el documento.
    for (const campo of ['Empresa / Institución', 'Teléfono']) {
      const nodo = screen.getByLabelText(campo);
      const id = nodo.getAttribute('aria-describedby');
      expect(id, `${campo} quedó marcado sin decir dónde está su explicación`).not.toBeNull();
      expect(document.getElementById(id), `${campo} apunta a un id que no existe`).not.toBeNull();
    }

    await noDebeTenerInfracciones();
  });
});

// ===========================================================================
// Las nueve que faltaban, y la tabla (capítulo 44)
// ===========================================================================
//
// Cada una se monta **como la monta la aplicación**, y esa frase hace trabajo. Un bloque de
// una pestaña del panel vive dentro del `<main>` de `App.jsx`; montarlo suelto produce
// fallos de `region` —«todo el contenido dentro de una marca de región»— que no son suyos.
// La salida fácil sería apagar esa regla, y eso la apagaría también para las nueve
// pantallas que hoy la cumplen, que es cambiar un hueco por otro más grande. Así que lo que
// se escribe aquí es dónde vive cada cosa:
//
// * un bloque de pestaña va en `<main>`, porque ahí lo pone `App.jsx`;
// * un modal se monta solo, porque su `role="dialog"` ya es su región;
// * una pantalla entera —el cambio obligatorio, el alta del segundo factor— se monta sola
//   **y tiene que traer su propia región**, porque `App.jsx` la devuelve en lugar del panel
//   y no hay ningún `<main>` alrededor. Las dos eran un `<div>`; es el arreglo del capítulo.

/** Lo que `App.jsx` pone alrededor de un bloque de pestaña. */
function enElPanel(contenido) {
  return <main>{contenido}</main>;
}

const RECIEN_CREADA = {
  id: 9, email: 'luis.nuevo@plurione.test', full_name: 'Luis Nuevo Paredes',
  role: 'Commercial_Executive', must_change_password: true, totp_activo: false,
};

const ADMINISTRADOR = {
  id: 2, email: 'admin@plurione.test', full_name: 'Admin de Pruebas',
  role: 'System_Admin', must_change_password: false, totp_activo: false,
};

function cuenta(id, nombre, { activo = true, asignados = 0 } = {}) {
  return {
    id, full_name: nombre, email: `${nombre.split(' ')[0].toLowerCase()}@plurione.test`,
    role: 'Commercial_Executive', is_active: activo, is_sales_rep: true,
    capacity: 50, leads_asignados: asignados, must_change_password: false,
  };
}

const ALTA_DEL_SEGUNDO_FACTOR = {
  uri_otpauth: 'otpauth://totp/PluriOne%3Aadmin%40plurione.test?secret=JBSWY3DPEHPK3PXP',
  qr_svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 41 41"><path d="M0 0h1v1h-1z"/></svg>',
  secreto_en_base32: 'JBSWY3DPEHPK3PXP',
  codigos_de_recuperacion: [
    '23AB-CDEF-GHJK', '4MNP-QRST-UVWX', '5YZ2-3456-789A', 'BCDE-FGHJ-KMNP', 'QRST-UVWX-YZ23',
    '4567-89AB-CDEF', 'GHJK-MNPQ-RSTU', 'VWXY-Z234-5678', '9ABC-DEFG-HJKM', 'NPQR-STUV-WXYZ',
  ],
};

const SIN_ASOCIAR = {
  id: 11, source: 'whatsapp', activity_type: 'WHATSAPP_MESSAGE', channel: 'WhatsApp',
  direction: 'ENTRANTE', call_outcome: null, contact_email: null,
  contact_phone: '+525598765432', contact_name: 'Contacto de WhatsApp',
  occurred_at: '2026-09-10T15:00:00Z', received_at: '2026-09-10T15:00:05Z',
};

const RED = (clave, etiqueta, extra = {}) => ({
  clave, etiqueta, activa: true,
  enlace: `${ENLACE}?r=${clave}`,
  texto: `Texto de ${etiqueta}\n\n${ENLACE}?r=${clave}`,
  longitud: 40, maximo: 3000,
  compartir: `https://ejemplo-${clave}.test/compartir`,
  admite_texto: true, aviso: null,
  ...extra,
});

const PARA_DIFUNDIR = {
  ...PUBLICACION,
  difusion: [
    RED('linkedin', 'LinkedIn', {
      admite_texto: false,
      aviso: 'LinkedIn solo recibe el enlace: copia el texto y pégalo en el post.',
    }),
    RED('whatsapp', 'WhatsApp', { maximo: 400, longitud: 120 }),
    RED('x', 'X', { activa: false, maximo: 280 }),
  ],
};

describe('la gestión de cuentas', () => {
  it('cumple el nivel AA con la cartera cargada y el alta de cuenta en pantalla', async () => {
    api.getCurrentUserRole.mockReturnValue('System_Admin');
    api.fetchSalesReps.mockResolvedValue({
      total: 2, items: [cuenta(3, 'Ana Activa Soto', { asignados: 20 }), cuenta(7, 'Marta Baja Ruiz', { activo: false, asignados: 12 })],
      prospectos_en_cuentas_de_baja: 12,
    });
    api.fetchUsers.mockResolvedValue({
      total: 2, items: [cuenta(3, 'Ana Activa Soto', { asignados: 20 }), ADMINISTRADOR],
    });
    render(enElPanel(<AdminPanel onBatchRecalculate={() => {}} isRecalculating={false} />));

    // El alta es donde están ocho de sus doce cajas, y el estado que esta auditoría no
    // había visto nunca: son las ocho que el capítulo 40 marca con `aria-invalid`.
    await screen.findByLabelText('Correo institucional');
    await waitFor(() => expect(screen.getAllByText(/Ana Activa Soto/).length).toBeGreaterThan(0));

    await noDebeTenerInfracciones();
  });

  it('y con el formulario de restablecer la contraseña de otra cuenta abierto', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    api.getCurrentUserRole.mockReturnValue('System_Admin');
    api.fetchSalesReps.mockResolvedValue({ total: 1, items: [cuenta(3, 'Ana Activa Soto')], prospectos_en_cuentas_de_baja: 0 });
    api.fetchUsers.mockResolvedValue({ total: 1, items: [cuenta(3, 'Ana Activa Soto')] });
    render(enElPanel(<AdminPanel onBatchRecalculate={() => {}} isRecalculating={false} />));

    await usuario.click(await screen.findByRole('button', { name: 'Restablecer contraseña' }));
    await screen.findByLabelText(/Contraseña nueva para/);

    await noDebeTenerInfracciones();
  });
});

describe('el simulador de scoring', () => {
  it('cumple el nivel AA', async () => {
    api.predictScoreLive.mockResolvedValue({
      score: 72.5, score_category: 'HOT', conversion_probability: 0.58,
      explicacion: null, desglose: [],
    });
    render(enElPanel(<ScoringSimulator />));
    await waitFor(() => expect(api.predictScoreLive).toHaveBeenCalled());

    // Los tres deslizadores no tenían nombre: ni `<label>`, ni `aria-label`, ni `title`.
    // `axe` lo da como infracción crítica y nadie lo había corrido aquí.
    await noDebeTenerInfracciones();
  });

  it('y sus tres deslizadores dicen de qué son', () => {
    render(enElPanel(<ScoringSimulator />));
    for (const etiqueta of [/Páginas Vistas/, /Clics en Correos/, /Días de Inactividad/]) {
      const control = screen.getByLabelText(etiqueta);
      expect(control.type).toBe('range');
    }
  });
});

describe('el panel de la sesión', () => {
  it('cumple el nivel AA con el cambio de contraseña abierto', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(<SessionModal user={LIDER} onLogout={() => {}} onClose={() => {}} />);
    await usuario.click(screen.getByRole('button', { name: 'Cambiar mi contraseña' }));

    await noDebeTenerInfracciones();
  });
});

describe('el cambio de contraseña obligatorio', () => {
  it('cumple el nivel AA, y es la pantalla entera: trae su propia región', async () => {
    render(<CambioDeContrasenaObligatorio user={RECIEN_CREADA} onCompletado={() => {}} onSalir={() => {}} />);
    await screen.findByLabelText('Contraseña actual');

    // `App.jsx` la devuelve **en lugar** del panel, así que no hay ningún `<main>` arriba.
    // Era un `<div>`: la pantalla por la que pasa toda cuenta nueva estaba entera fuera de
    // cualquier región, y quien navega por regiones no tenía dónde saltar.
    expect(document.querySelector('main')).not.toBeNull();
    await noDebeTenerInfracciones();
  });
});

describe('el alta del segundo factor', () => {
  it('cumple el nivel AA con el QR y los códigos en pantalla', async () => {
    api.altaDelSegundoFactor.mockResolvedValue(ALTA_DEL_SEGUNDO_FACTOR);
    render(<AltaDelSegundoFactor user={ADMINISTRADOR} onActivado={() => {}} onSalir={() => {}} />);
    await screen.findByLabelText(/Código QR/);

    // Lo mismo que la de arriba: pantalla entera, devuelta en lugar del panel, sin región.
    expect(document.querySelector('main')).not.toBeNull();
    await noDebeTenerInfracciones();
  });
});

describe('la bandeja de avisos sin asociar', () => {
  it('cumple el nivel AA con una fila y su formulario de vinculación', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    api.fetchEventosSinAsociar.mockResolvedValue({ items: [SIN_ASOCIAR], total: 1, limit: 50, offset: 0 });
    render(enElPanel(<BandejaSinAsociar />));
    await screen.findByText(/Contacto de WhatsApp/);

    // Y con la confirmación del descarte abierta, que es el bloque que el capítulo 43
    // escribió para quitar el `window.confirm` y que nadie ha auditado.
    await usuario.click(screen.getByRole('button', { name: /Descartar/i }));
    await screen.findByRole('button', { name: /Sí, descartar/i });

    await noDebeTenerInfracciones();
  });
});

describe('el cierre de un prospecto', () => {
  it('cumple el nivel AA con el desenlace elegido y sus tres campos', async () => {
    const { default: userEvent } = await import('@testing-library/user-event');
    const usuario = userEvent.setup();
    render(enElPanel(<CerrarProspecto lead={PROSPECTO} onCerrado={() => {}} onCancelar={() => {}} />));

    await usuario.click(await screen.findByRole('button', { name: 'Ganado' }));
    await screen.findByLabelText('¿Por qué?');

    await noDebeTenerInfracciones();
  });
});

describe('compartir una publicación en redes', () => {
  it('cumple el nivel AA con las redes y el código QR', async () => {
    render(enElPanel(<CompartirEnRedes publicacion={PARA_DIFUNDIR} onCopiar={() => {}} />));
    await screen.findByRole('list', { name: 'Redes activas' });

    await noDebeTenerInfracciones();
  });
});

describe('asignar un asesor a una ficha', () => {
  it('cumple el nivel AA', async () => {
    api.getCurrentUserRole.mockReturnValue('Sales_Lead');
    api.fetchSalesReps.mockResolvedValue({
      total: 1, items: [cuenta(3, 'Ana Activa Soto', { asignados: 20 })],
    });
    render(enElPanel(<AsignarAsesor lead={PROSPECTO} onAsignado={() => {}} />));
    await waitFor(() => expect(api.fetchSalesReps).toHaveBeenCalled());

    await noDebeTenerInfracciones();
  });
});

describe('la tabla de prospectos', () => {
  it('cumple el nivel AA', async () => {
    render(enElPanel(
      <LeadsTable leads={PROSPECTOS} onSelectLead={() => {}} onRefresh={() => {}} />,
    ));
    await screen.findByText(/Rosa/);

    await noDebeTenerInfracciones();
  });
});
