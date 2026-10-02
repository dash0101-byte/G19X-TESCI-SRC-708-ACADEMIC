// ============================================================================
// La aplicación montada: a qué pantalla lleva cada estado de sesión
// ============================================================================
//
// `App.jsx` no pinta casi nada: decide. Mira si la sesión se pudo restaurar, si hay usuario
// y si ese usuario todavía lleva la contraseña que le fijó otra persona, y de esas tres
// respuestas salen cuatro pantallas distintas. Hasta el capítulo 32 ese razonamiento estaba
// comprobado **por lectura** y por la prueba del componente de cambio de contraseña, que se
// monta solo. Es decir: se sabía que el componente funciona, no que la aplicación lo enseñe.
//
// Lo que se comprueba aquí, y por qué estas dos cosas
// ----------------------------------------------------
// 1. **La redirección.** Una cuenta con `must_change_password` no ve el panel: ve la
//    pantalla de cambio. Si esa condición se cayera —un `&&` de más, un campo renombrado en
//    la respuesta del servidor—, la aplicación enseñaría el panel entero a una cuenta que
//    el servidor rechaza para todo salvo cambiar la contraseña, y cada tarjeta fallaría con
//    un 403. Lo que se vería no es «acceso denegado»: es un panel roto.
//
// 2. **Que en ese estado no se lancen cargas de datos.** Es la parte que ninguna prueba de
//    componente puede ver, porque vive en los efectos de `App` y no en lo que se pinta. Los
//    dos `useEffect` que cargan analíticas, campañas y prospectos llevan
//    `if (!user || user.must_change_password) return;`, y ese `return` es media línea que un
//    cambio razonable se lleva por delante sin romper nada visible: las tres peticiones
//    saldrían, el servidor respondería 403 a las tres, y la consola del navegador se
//    llenaría de errores mientras la pantalla de cambio de contraseña se ve perfecta.
//
// Los componentes del panel van sustituidos por marcadores. Cada uno tiene su propia prueba
// y aquí sobran: lo que se mide es a cuál se llega, no qué pinta. `LoginScreen` y
// `CambioDeContrasenaObligatorio` sí son los de verdad, porque son el destino de la
// decisión y la prueba no diría gran cosa si el destino fuera también un marcador.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// El módulo entero simulado, export por export. Enumerarlos a mano habría dejado fuera
// cualquier función que un componente hijo llame sin que esta prueba lo sepa, y el fallo
// llegaría como «no es una función» desde un archivo que no es el que se está probando.
vi.mock('./services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import App from './App.jsx';
import {
  fetchAnalyticsSummary,
  fetchCampaigns,
  fetchLeads,
  fetchNuevosSinAsesor,
  getCurrentUser,
  getCurrentUserRole,
  logout,
  recalculateAllScores,
  restoreSession,
  setSessionExpiredHandler,
  changeOwnPassword,
} from './services/api';

// El panel, reducido a lo que esta prueba necesita saber de él: si apareció. Cada fábrica
// va escrita entera y no a través de un ayudante: `vi.mock` se eleva a la cabecera del
// archivo, así que una función declarada aquí arriba todavía no existe cuando se ejecuta.
//
// La barra lleva botones desde el capítulo 38, y es el único marcador que los tiene. El
// motivo: a partir de ese capítulo hay dos pestañas cuyo CONTENIDO depende del rol —el
// contador del tablero y los derechos del titular en administración—, y sin poder cambiar
// de pestaña no se puede comprobar ninguna de las dos. Siguen siendo botones pelados: no
// deciden qué se ve, solo piden el cambio, que es lo que hace la barra de verdad.
vi.mock('./components/Navbar', () => ({
  default: ({ setActiveTab }) => (
    <nav data-testid="navbar">
      {['hoy', 'dashboard', 'leads', 'publicaciones', 'admin'].map((pestana) => (
        <button key={pestana} type="button" onClick={() => setActiveTab(pestana)}>
          {pestana}
        </button>
      ))}
    </nav>
  ),
}));
vi.mock('./components/BandejaDeHoy', () => ({ default: () => <div data-testid="bandeja-de-hoy" /> }));
vi.mock('./components/KPICards', () => ({ default: () => <div data-testid="kpis" /> }));
vi.mock('./components/AnalyticsCharts', () => ({ default: () => <div data-testid="graficas" /> }));
vi.mock('./components/LeadsTable', () => ({ default: () => <div data-testid="tabla-de-prospectos" /> }));
vi.mock('./components/LeadDetailModal', () => ({ default: () => <div data-testid="ficha" /> }));
vi.mock('./components/ScoringSimulator', () => ({ default: () => <div data-testid="simulador" /> }));
// El panel de administración, con el único botón que `App` le pasa: el del recálculo
// masivo. Lo que se mide de él no es lo que pinta —tiene su propia prueba— sino lo que
// `App` hace con el resultado, que desde el capítulo 43 es un aviso dentro de la página y
// no un cuadro del navegador.
vi.mock('./components/AdminPanel', () => ({
  default: ({ onBatchRecalculate }) => (
    <div data-testid="administracion">
      <button type="button" onClick={onBatchRecalculate}>recalcular la cartera</button>
    </div>
  ),
}));
vi.mock('./components/BandejaSinAsociar', () => ({ default: () => <div data-testid="sin-asociar" /> }));
vi.mock('./components/Publicaciones', () => ({ default: () => <div data-testid="publicaciones" /> }));
vi.mock('./components/PanelDeDesenlaces', () => ({ default: () => <div data-testid="desenlaces" /> }));
vi.mock('./components/SessionModal', () => ({ default: () => <div data-testid="sesion" /> }));
vi.mock('./components/NewLeadModal', () => ({ default: () => <div data-testid="alta" /> }));
vi.mock('./components/AltaDelSegundoFactor', () => ({ default: () => <div data-testid="alta-del-segundo-factor" /> }));

const ASESOR = {
  id: 7,
  email: 'ana.torres@plurione.test',
  full_name: 'Ana Torres Delgado',
  role: 'Commercial_Executive',
  must_change_password: false,
};

const RECIEN_CREADA = { ...ASESOR, id: 9, full_name: 'Luis Nuevo Paredes', must_change_password: true };

/** Las tres llamadas que los efectos de `App` lanzan en cuanto hay sesión utilizable. */
const CARGAS_DE_DATOS = () => [fetchAnalyticsSummary, fetchCampaigns, fetchLeads];

function conSesion(usuario) {
  restoreSession.mockResolvedValue(usuario);
}

beforeEach(() => {
  vi.clearAllMocks();
  restoreSession.mockResolvedValue(null);
  logout.mockResolvedValue(undefined);
  fetchAnalyticsSummary.mockResolvedValue({ total_leads: 0 });
  fetchCampaigns.mockResolvedValue([]);
  fetchLeads.mockResolvedValue({ items: [], total: 0 });
  fetchNuevosSinAsesor.mockResolvedValue({ total: 4 });
  // `DerechosDelTitular` es el componente de verdad —no un marcador— porque lo que se
  // mide de él es justo lo que un marcador taparía: que a un asesor no se le dibuje.
  // Pregunta el rol al módulo de sesión, que está simulado entero.
  getCurrentUserRole.mockReturnValue(null);
  getCurrentUser.mockReturnValue(null);
});

describe('mientras se comprueba la sesión', () => {
  it('no enseña ni la entrada ni el panel, y no pide datos todavía', async () => {
    // Una promesa que no se resuelve: el estado intermedio dura lo que tarde el servidor,
    // y en ese hueco la aplicación no puede enseñar la pantalla de entrada a quien SÍ tiene
    // sesión. Ese parpadeo es lo que `authChecked` existe para evitar.
    restoreSession.mockReturnValue(new Promise(() => {}));
    render(<App />);

    expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
    expect(screen.queryByLabelText('Correo corporativo')).not.toBeInTheDocument();
    expect(screen.queryByTestId('navbar')).not.toBeInTheDocument();
    for (const carga of CARGAS_DE_DATOS()) expect(carga).not.toHaveBeenCalled();
  });

  it('deja preparado el aviso de sesión caducada antes de pedir nada', () => {
    restoreSession.mockReturnValue(new Promise(() => {}));
    render(<App />);
    // El manejador se registra en el mismo efecto y antes de la primera petición: si se
    // registrara después, un 401 llegado en ese intervalo no tendría quien lo recogiera.
    expect(setSessionExpiredHandler).toHaveBeenCalledTimes(1);
  });
});

describe('sin sesión', () => {
  it('lleva a la entrada y no pide datos', async () => {
    render(<App />);

    expect(await screen.findByRole('button', { name: /Iniciar sesión/i })).toBeInTheDocument();
    expect(screen.queryByTestId('navbar')).not.toBeInTheDocument();
    for (const carga of CARGAS_DE_DATOS()) expect(carga).not.toHaveBeenCalled();
  });
});

describe('con la contraseña que le fijó otra persona', () => {
  it('lleva al cambio obligatorio y no al panel', async () => {
    conSesion(RECIEN_CREADA);
    render(<App />);

    expect(await screen.findByText(/Luis Nuevo Paredes/)).toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña actual')).toBeInTheDocument();
    expect(screen.queryByTestId('navbar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('bandeja-de-hoy')).not.toBeInTheDocument();
  });

  it('NO lanza ninguna de las tres cargas de datos', async () => {
    conSesion(RECIEN_CREADA);
    render(<App />);
    await screen.findByLabelText('Contraseña actual');

    // Se espera a que la aplicación esté quieta antes de afirmar la ausencia: comprobar que
    // algo no ocurrió en el primer render solo demuestra que todavía no había ocurrido.
    await waitFor(() => expect(restoreSession).toHaveBeenCalled());
    for (const carga of CARGAS_DE_DATOS()) expect(carga).not.toHaveBeenCalled();
  });

  it('al cambiarla, cierra la sesión local y vuelve a la entrada diciendo por qué', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockResolvedValue({ mensaje: 'Contraseña actualizada. Entre con la nueva.' });
    conSesion(RECIEN_CREADA);
    render(<App />);

    await usuario.type(await screen.findByLabelText('Contraseña actual'), 'Prestada-Inicial-2026');
    await usuario.type(screen.getByLabelText(/Contraseña nueva/), 'Mi-Frase-Propia-Y-Larga');
    await usuario.type(screen.getByLabelText('Repita la contraseña nueva'), 'Mi-Frase-Propia-Y-Larga');
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    // El servidor ya cerró todas las sesiones: la local tiene que irse detrás, o el cliente
    // se quedaría con un usuario en memoria para el que ningún token vale ya.
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('status')).toHaveTextContent('Entre con la nueva');
    // Y sigue sin pedir datos: se vuelve a la entrada, no al panel.
    for (const carga of CARGAS_DE_DATOS()) expect(carga).not.toHaveBeenCalled();
  });
});

describe('con sesión utilizable', () => {
  it('enseña el panel y lanza las tres cargas', async () => {
    conSesion(ASESOR);
    render(<App />);

    expect(await screen.findByTestId('navbar')).toBeInTheDocument();
    // El contraste que da sentido a las dos pruebas de arriba: si estas llamadas tampoco
    // salieran aquí, «no se lanzan cargas» no estaría comprobando nada.
    await waitFor(() => {
      for (const carga of CARGAS_DE_DATOS()) expect(carga).toHaveBeenCalled();
    });
  });

  it('la bandeja «Hoy» es lo primero que se ve', async () => {
    conSesion(ASESOR);
    render(<App />);
    expect(await screen.findByTestId('bandeja-de-hoy')).toBeInTheDocument();
    expect(screen.queryByTestId('administracion')).not.toBeInTheDocument();
  });
});

// ============================================================================
// Capítulo 35: la misma redirección, para el segundo factor
// ============================================================================
//
// Una cuenta de administración sin segundo factor está en el mismo sitio que una con la
// contraseña prestada: el servidor le rechaza todo menos lo justo para dejar de estarlo.
// Enseñarle el panel para que cada tarjeta falle con un 403 sería peor que no enseñárselo.

const ADMIN_SIN_DOSFA = {
  ...ASESOR,
  id: 11,
  full_name: 'Admin de Pruebas',
  role: 'System_Admin',
  segundo_factor_obligatorio: true,
  totp_activo: false,
};

describe('el segundo factor obligatorio', () => {
  it('lleva al alta en lugar de al panel', async () => {
    conSesion(ADMIN_SIN_DOSFA);
    render(<App />);

    expect(await screen.findByTestId('alta-del-segundo-factor')).toBeInTheDocument();
    expect(screen.queryByTestId('navbar')).not.toBeInTheDocument();
  });

  it('y en ese estado no se lanza ninguna carga de datos', async () => {
    // El mismo motivo que con la contraseña prestada: el servidor las rechazaría todas, y
    // la condición que lo evita es media línea que un cambio distraído borra sin que nada
    // se rompa de forma visible.
    conSesion(ADMIN_SIN_DOSFA);
    render(<App />);
    await screen.findByTestId('alta-del-segundo-factor');

    for (const carga of CARGAS_DE_DATOS()) {
      expect(carga).not.toHaveBeenCalled();
    }
  });

  it('con el segundo factor activo entra al panel con normalidad', async () => {
    conSesion({ ...ADMIN_SIN_DOSFA, totp_activo: true });
    render(<App />);

    expect(await screen.findByTestId('navbar')).toBeInTheDocument();
    expect(screen.queryByTestId('alta-del-segundo-factor')).not.toBeInTheDocument();
  });

  it('a quien no lo tiene obligatorio no se le pide', async () => {
    conSesion({ ...ASESOR, segundo_factor_obligatorio: false, totp_activo: false });
    render(<App />);

    expect(await screen.findByTestId('navbar')).toBeInTheDocument();
  });

  it('la contraseña prestada va primero', async () => {
    // Una cuenta con las dos cosas pendientes cambia primero la credencial que conoce otra
    // persona. Al revés, ataría un teléfono a una cuenta que todavía no es suya. Es el
    // mismo orden que aplica el servidor.
    conSesion({ ...ADMIN_SIN_DOSFA, must_change_password: true });
    render(<App />);

    expect(await screen.findByRole('heading', { name: /contraseña/i })).toBeInTheDocument();
    expect(screen.queryByTestId('alta-del-segundo-factor')).not.toBeInTheDocument();
  });
});

// ============================================================================
// Capítulo 38: lo que el rol decide DENTRO de una pestaña
// ============================================================================
//
// Hasta aquí este archivo medía a qué pantalla lleva cada estado de sesión. Las dos cosas
// que entran en el capítulo 38 son distintas: no cambian de pantalla, cambian qué hay
// dentro de una. El contador del tablero y los derechos del titular en administración los
// ve quien dirige la cartera y no los ve un asesor, y las dos decisiones viven en `App`.

const LIDER = {
  ...ASESOR,
  id: 3,
  email: 'lider@plurione.test',
  full_name: 'Laura Líder',
  role: 'Sales_Lead',
};

/** Deja la sesión abierta con ese usuario, incluido el rol que leen los componentes. */
function conSesionDe(usuario) {
  conSesion(usuario);
  getCurrentUserRole.mockReturnValue(usuario.role);
  getCurrentUser.mockReturnValue(usuario);
}

async function irA(pestana) {
  const usuario = userEvent.setup();
  await usuario.click(within(await screen.findByTestId('navbar')).getByRole('button', { name: pestana }));
  return usuario;
}

describe('el contador de «nuevos sin asesor» en el tablero (§6.2, punto 11)', () => {
  it('el líder lo ve, con el número que da el servidor', async () => {
    conSesionDe(LIDER);
    render(<App />);

    await irA('dashboard');

    expect(await screen.findByText(/Nuevos de publicaciones, sin asesor/)).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('y lleva a la matriz, que es donde se abre la ficha y se asigna', async () => {
    conSesionDe(LIDER);
    render(<App />);

    const usuario = await irA('dashboard');
    await usuario.click(await screen.findByRole('button', { name: 'Ver y repartir' }));

    // El tablero enseña ocho filas; la matriz, la lista entera. Que haya cambiado de
    // pestaña se ve en que el simulador y la bandeja ya no están y la tabla sí.
    expect(screen.getByTestId('tabla-de-prospectos')).toBeInTheDocument();
    expect(screen.queryByTestId('graficas')).not.toBeInTheDocument();
  });

  it('a un asesor no se le enseña ni se le pide al servidor', async () => {
    // Las dos mitades cuentan. Pedirlo y tragarse el 403 llenaría la bitácora de accesos
    // denegados que no provocó nadie, que es el mismo criterio que sigue «Publicaciones».
    conSesionDe(ASESOR);
    render(<App />);

    await irA('dashboard');
    await waitFor(() => expect(fetchLeads).toHaveBeenCalled());

    expect(screen.queryByText(/Nuevos de publicaciones, sin asesor/)).not.toBeInTheDocument();
    expect(fetchNuevosSinAsesor).not.toHaveBeenCalled();
  });

  it('si el servidor no lo contesta, el tablero se dibuja sin el aviso y no inventa un cero', async () => {
    fetchNuevosSinAsesor.mockRejectedValue(new Error('503'));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    conSesionDe(LIDER);
    render(<App />);

    await irA('dashboard');
    await waitFor(() => expect(screen.getByTestId('graficas')).toBeInTheDocument());

    expect(screen.queryByText(/Nuevos de publicaciones, sin asesor/)).not.toBeInTheDocument();
  });
});

describe('la pantalla de derechos del titular (§6.2, punto 16)', () => {
  it('el líder la alcanza desde administración', async () => {
    conSesionDe(LIDER);
    render(<App />);

    await irA('admin');

    expect(await screen.findByRole('heading', { name: 'Derechos del titular' })).toBeInTheDocument();
    expect(screen.getByLabelText('Correo de la persona')).toBeInTheDocument();
  });

  it('un asesor no la alcanza ni forzando la pestaña', async () => {
    // La pestaña no se le ofrece en la barra de verdad, así que esto fuerza la única vía
    // que quedaría: pedir «admin» directamente. `App` lo devuelve a la matriz, y además el
    // propio componente no se dibujaría —el servidor, por su parte, responde 403 a los dos
    // endpoints (`test_un_asesor_no_exporta_ni_suprime`)—.
    conSesionDe(ASESOR);
    render(<App />);

    await irA('admin');

    expect(screen.queryByRole('heading', { name: 'Derechos del titular' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Correo de la persona')).not.toBeInTheDocument();
    expect(screen.queryByTestId('administracion')).not.toBeInTheDocument();
    expect(screen.getByTestId('tabla-de-prospectos')).toBeInTheDocument();
  });
});

// ============================================================================
// Lo que el recálculo masivo contesta, dentro de la página (capítulo 43)
// ============================================================================
//
// Este archivo no probaba el recálculo masivo, y era el único sitio del cliente donde
// quedaban cuadros del navegador: seis `alert()`, todos aquí. §6.4 los contaba como «siete
// errores», y de los seis dos no eran errores —uno anunciaba un éxito y otro que el trabajo
// seguía en curso— y uno no era de ningún recálculo.
//
// Un cuadro del navegador no se puede probar porque no está en el documento: en `jsdom`,
// `window.alert` existe y lanza «not implemented», que `userEvent` se traga. Así que el
// defecto y la razón por la que nadie lo había notado son el mismo: lo que no está en la
// página no lo ve ni una persona con lector de pantalla ni una prueba.
describe('el resultado del recálculo masivo', () => {
  /** Deja la sesión del líder abierta y pulsa el botón del recálculo en administración. */
  async function recalcular() {
    conSesionDe(LIDER);
    render(<App />);
    const usuario = await irA('admin');
    await usuario.click(await screen.findByRole('button', { name: 'recalcular la cartera' }));
    return usuario;
  }

  it('cuando termina, lo dice en la página y como un estado', async () => {
    recalculateAllScores.mockResolvedValue({
      id: 'j-1', status: 'COMPLETED', processed_leads: 312, failed_leads: 0,
    });
    const cuadroDelNavegador = vi.fn();
    vi.stubGlobal('alert', cuadroDelNavegador);

    await recalcular();

    const avisos = await screen.findAllByRole('status');
    const aviso = avisos.find((nodo) => nodo.textContent.includes('recalculados'));
    expect(aviso).toBeDefined();
    expect(aviso.textContent).toContain('312 prospectos recalculados');
    // Un éxito no se anuncia como alerta: `role="status"` espera a que el lector de
    // pantalla termine lo que esté diciendo.
    expect(aviso.closest('[role="alert"]')).toBeNull();
    expect(aviso.querySelector('.alert-ok')).not.toBeNull();
    expect(cuadroDelNavegador).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it('cuando falla, lo dice como alerta y con la variante del error', async () => {
    recalculateAllScores.mockResolvedValue({
      id: 'j-2', status: 'FAILED', error_message: 'el extractor se quedó sin memoria',
    });

    await recalcular();

    // Varias regiones de alerta conviven en el panel —la de `App` y la de la pantalla de
    // derechos, que también vive en administración—, así que se busca la que habla.
    const avisos = await screen.findAllByRole('alert');
    const aviso = avisos.find((nodo) => nodo.textContent.includes('extractor'));
    expect(aviso, 'el fallo del recálculo no salió en ninguna región de alerta').toBeDefined();
    expect(aviso.textContent).toContain('el extractor se quedó sin memoria');
    expect(aviso.querySelector('.alert-error')).not.toBeNull();
  });

  it('con el turno ocupado avisa en ámbar, porque no ha fallado nada', async () => {
    // El 409 trae el trabajo que ocupa el turno y por dónde va. Era un `alert()` con ese
    // texto; ahora es la variante que la hoja tenía escrita desde el capítulo 40 y que no
    // usaba ningún componente.
    recalculateAllScores.mockRejectedValue(Object.assign(
      new Error('Ya hay un recálculo masivo en curso.'),
      { status: 409, detalle: { procesados: 40, total: 120, solicitado_por: 'ana@plurione.test' } },
    ));

    await recalcular();

    const avisos = await screen.findAllByRole('status');
    const aviso = avisos.find((nodo) => nodo.textContent.includes('en curso'));
    expect(aviso.textContent).toContain('Va por 40 de 120');
    expect(aviso.textContent).toContain('Lo lanzó ana@plurione.test');
    expect(aviso.querySelector('.alert-warn')).not.toBeNull();
  });

  it('el aviso se queda hasta que quien lo ha leído lo cierra', async () => {
    // No se va a los cuatro segundos: un error que desaparece mientras se lee no se ha
    // leído. Y no se queda para siempre: lo cierra quien lo ha visto.
    recalculateAllScores.mockResolvedValue({ id: 'j-3', status: 'COMPLETED', processed_leads: 5 });

    const usuario = await recalcular();
    await screen.findByText(/5 prospectos recalculados/);
    await usuario.click(screen.getByRole('button', { name: 'Cerrar' }));

    expect(screen.queryByText(/prospectos recalculados/)).not.toBeInTheDocument();
  });

  it('mientras trabaja, el velo dice que está ocupado y no se queda mudo', async () => {
    // Tapa la página entera durante minutos. Sin `role`, sin `aria-live` y sin `aria-busy`,
    // para quien no ve la pantalla la aplicación se quedaba cubierta y en silencio.
    let soltar;
    recalculateAllScores.mockReturnValue(new Promise((resolve) => { soltar = resolve; }));

    await recalcular();

    const velo = (await screen.findByText('Encolando el recálculo...')).closest('[role="status"]');
    expect(velo).not.toBeNull();
    expect(velo).toHaveAttribute('aria-live', 'polite');
    expect(velo).toHaveAttribute('aria-busy', 'true');

    soltar({ id: 'j-4', status: 'COMPLETED', processed_leads: 1 });
    await waitFor(() => expect(screen.queryByText('Encolando el recálculo...')).not.toBeInTheDocument());
  });
});
