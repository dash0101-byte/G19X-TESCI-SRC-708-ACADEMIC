import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import BandejaDeHoy from './components/BandejaDeHoy';
import LoginScreen from './components/LoginScreen';
import KPICards from './components/KPICards';
import AnalyticsCharts from './components/AnalyticsCharts';
import LeadsTable from './components/LeadsTable';
import LeadDetailModal from './components/LeadDetailModal';
import ScoringSimulator from './components/ScoringSimulator';
import AdminPanel from './components/AdminPanel';
import BandejaSinAsociar from './components/BandejaSinAsociar';
import ContadorSinAsesor from './components/ContadorSinAsesor';
import DerechosDelTitular from './components/DerechosDelTitular';
import Publicaciones from './components/Publicaciones';
import PanelDeDesenlaces from './components/PanelDeDesenlaces';
import SessionModal from './components/SessionModal';
import NewLeadModal from './components/NewLeadModal';
import AltaDelSegundoFactor from './components/AltaDelSegundoFactor';
import CambioDeContrasenaObligatorio from './components/CambioDeContrasenaObligatorio';
import {
  fetchAnalyticsSummary,
  fetchCampaigns,
  fetchLeads,
  fetchLeadDetail,
  fetchNuevosSinAsesor,
  getRecalculationJob,
  recalculateAllScores,
  restoreSession,
  logout,
  setSessionExpiredHandler,
} from './services/api';

/**
 * ¿A esta cuenta le falta el segundo factor que tiene obligatorio? (capítulo 35)
 *
 * Los dos datos vienen del servidor y ninguno se deduce aquí del rol. Deducirlo en el
 * cliente crearía una segunda definición de «quién está obligado», y el día que alguien
 * cambiara la del servidor —`ROLES_OBLIGADOS_A_SEGUNDO_FACTOR`— esta se quedaría atrás sin
 * que nada fallara: el panel enseñaría la aplicación a una cuenta a la que el servidor le
 * va a rechazar todo, o al revés.
 */
function faltaElSegundoFactor(user) {
  return Boolean(user.segundo_factor_obligatorio && !user.totp_activo);
}

/**
 * El aviso de una operación que no vive en ninguna pantalla (capítulo 43).
 *
 * La caja la dibuja `.alert` con su variante, que es lo que la hoja tiene escrito desde el
 * capítulo 40 para esto; aquí solo se elige la variante y se añade el botón de cerrar.
 *
 * El botón existe porque este aviso no desaparece solo. Un error que se va a los cuatro
 * segundos se va justo mientras se lee, y uno que no se puede quitar se queda en pantalla
 * para siempre: lo cierra quien lo ha leído. Va dentro de la región viva, así que el lector
 * de pantalla lo anuncia como parte del aviso y no como un botón suelto.
 *
 * No se exporta a propósito: un archivo que exporta dos componentes rompe la recarga en
 * caliente de Vite, y el `linter` lo dice.
 */
/**
 * La variante de `.alert` de cada clase de aviso, escrita y no compuesta.
 *
 * `alert-${aviso.tipo}` habría valido igual en el navegador y lo dijo `clases.test.js` en
 * cuanto se escribió: una clase que el código **compone** no la puede leer la guarda que
 * saca del marcado los nombres de clase, así que un día cualquiera `alert-aviso` sin
 * definir se dibujaría con el estilo por omisión del navegador y nada lo diría. Las tres
 * están aquí escritas enteras por eso, no por estilo.
 */
const VARIANTE_DEL_AVISO = {
  error: 'alert-error',
  ok: 'alert-ok',
  warn: 'alert-warn',
};

function AvisoDelPanel({ aviso, onCerrar }) {
  return (
    <div
      className={`alert ${VARIANTE_DEL_AVISO[aviso.tipo]}`}
      style={{
        marginBottom: '16px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'flex-start', gap: '12px',
      }}
    >
      <span>{aviso.texto}</span>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onCerrar}>
        Cerrar
      </button>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('hoy');
  // La identidad y el rol vienen del servidor tras autenticarse; el cliente ya no los
  // elige ni los guarda en localStorage, donde eran editables desde la consola.
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  // Lo que la pantalla de entrada tiene que decir al volver a ella cuando no es una
  // caducidad: que la contraseña se acaba de cambiar y hay que entrar con la nueva.
  const [avisoDeAcceso, setAvisoDeAcceso] = useState(null);
  const currentRole = user?.role ?? null;
  // Quién dirige la cartera completa, escrito una vez. Era la misma comparación repetida
  // en tres sitios de este archivo y ahora en cuatro, y de las cuatro cuelga qué se pide
  // al servidor: una que se quedara atrás pediría datos que el servidor niega con un 403.
  const esDireccion = currentRole === 'Sales_Lead' || currentRole === 'System_Admin';
  const [summary, setSummary] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  // Cuántos prospectos de publicaciones esperan a que alguien los reparta. `null` es «no
  // se ha preguntado», que es lo que vale para un asesor: no se le pide, porque el
  // servidor se lo negaría y el intento llenaría la bitácora de accesos denegados que no
  // provocó nadie. Es el mismo criterio que sigue «Publicaciones».
  const [sinAsesor, setSinAsesor] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [globalLoadingMsg, setGlobalLoadingMsg] = useState('');
  // Lo que este archivo tiene que decir cuando acaba algo que no vive en ninguna pantalla
  // (capítulo 43). `{ tipo, texto }`, con el tipo de las tres variantes de `.alert`.
  //
  // Hasta aquí lo decía un `alert()` del navegador, seis veces. Un cuadro del navegador no
  // forma parte de la página: ningún lector de pantalla lo anuncia como contenido, no se
  // puede señalar junto a nada, tapa lo que hay que mirar y se va al pulsar «Aceptar» sin
  // dejar rastro de lo que decía. Y no era solo para errores: dos de los seis daban una
  // buena noticia —«✅ 312 prospectos recalculados»— con el mismo cuadro con el que el
  // navegador avisa de un fallo.
  const [aviso, setAviso] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  
  const [selectedLead, setSelectedLead] = useState(null);
  const [isNewLeadOpen, setIsNewLeadOpen] = useState(false);
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  // Salir deja la pantalla como la encontró quien entre después. La lista de
  // abajo se escribió a mano el día que nació y se quedó corta: el buscador y el
  // cuadrante son estado de la vista igual que los datos, y nadie volvió a leerla
  // cuando se añadieron. Se vio recorriendo la demostración: el líder había buscado
  // a una persona, cerró sesión, entró la asesora y su cartera —tres prospectos—
  // salía con uno, filtrada por un nombre que ella no había escrito y que no era
  // suyo. No hay nada en la pantalla que explique por qué faltan los otros dos.
  //
  // `selectedLead` entra por lo mismo aunque hoy no se pueda salir con la ficha
  // abierta —el modal tapa la barra—: es la ficha de otra persona, guardada en la
  // memoria del navegador para la sesión siguiente.
  const handleLogout = async () => {
    await logout();
    setUser(null);
    setActiveTab('hoy');
    setSummary(null);
    setCampaigns([]);
    setLeads([]);
    setSinAsesor(null);
    setSelectedCategory('');
    setSearchQuery('');
    setSelectedLead(null);
  };

  // `useCallback` no está aquí por rendimiento: sin él, estas funciones se recrean en
  // cada render y no se pueden declarar como dependencia del efecto que las usa. La
  // lista quedaba incompleta y el `linter` lo señalaba. Una dependencia que falta no
  // rompe nada visible: el efecto se queda leyendo el valor que había cuando se creó.
  const loadData = useCallback(async () => {
    try {
      const [sumData, campData] = await Promise.all([
        fetchAnalyticsSummary(),
        fetchCampaigns(),
      ]);
      setSummary(sumData);
      setCampaigns(campData);
    } catch (err) {
      console.error('Error cargando analíticas:', err);
    }
    // Aparte y con su propio `catch`: el contador es un aviso, no el tablero. Si el
    // servidor no lo contesta, el tablero se dibuja igual y el aviso no aparece —lo que
    // deja un contador ausente, no un cero, que diría que no hay nada esperando—.
    if (!esDireccion) return;
    try {
      const pendientes = await fetchNuevosSinAsesor();
      setSinAsesor(pendientes ? pendientes.total : null);
    } catch (err) {
      console.error('Error contando los nuevos sin asesor:', err);
    }
  }, [esDireccion]);

  const loadLeads = useCallback(async () => {
    setLoadingLeads(true);
    try {
      const data = await fetchLeads({
        category: selectedCategory,
        search: searchQuery,
        limit: 50,
      });
      // Soporte para la nueva respuesta paginada { items, total } y fallback a array plano
      if (data && Array.isArray(data.items)) {
        setLeads(data.items);
      } else if (Array.isArray(data)) {
        setLeads(data);
      }
    } catch (err) {
      console.error('Error cargando leads:', err);
    } finally {
      setLoadingLeads(false);
    }
  }, [selectedCategory, searchQuery]);

  // Al cargar la página el access token se ha perdido (vivía en memoria), pero la
  // cookie de refresco puede seguir viva: se intenta recuperar la sesión en silencio.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setSessionExpired(true);
    });
    restoreSession()
      .then((restored) => setUser(restored))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!user || user.must_change_password || faltaElSegundoFactor(user)) return;
    loadData();
  }, [user, loadData]);

  useEffect(() => {
    if (!user || user.must_change_password || faltaElSegundoFactor(user)) return;
    // `loadLeads` cambia exactamente cuando cambian el cuadrante o la búsqueda, así que
    // depender de la función equivale a la lista anterior —y no se puede quedar corta.
    loadLeads();
  }, [user, loadLeads]);

  // Un asesor no debe quedarse en la pestaña de administración si llega a ella
  useEffect(() => {
    if (currentRole === 'Commercial_Executive' && activeTab === 'admin') {
      setActiveTab('leads');
    }
  }, [currentRole, activeTab]);

  const [modalStartEdit, setModalStartEdit] = useState(false);

  const handleSelectLead = async (leadId, startEdit = false) => {
    try {
      const fullLead = await fetchLeadDetail(leadId);
      setSelectedLead(fullLead);
      setModalStartEdit(startEdit);
    } catch (err) {
      setAviso({ tipo: 'error', texto: `No se pudo abrir la ficha: ${err.message}` });
    }
  };

  const handleLeadUpdated = async () => {
    if (selectedLead) {
      await handleSelectLead(selectedLead.id, false);
    }
    loadLeads();
    loadData();
  };

  // Intervalo entre consultas de avance y número máximo de ellas. El tope existe para no
  // dejar el sondeo girando indefinidamente si el trabajo muriera sin marcarse como
  // fallido: a los cinco minutos se suelta la interfaz y se le dice al usuario dónde mirar.
  const SONDEO_MS = 1500;
  const SONDEOS_MAXIMOS = 200;

  const handleBatchRecalculate = async () => {
    setIsRecalculating(true);
    setGlobalLoading(true);
    setGlobalLoadingMsg('Encolando el recálculo...');
    // El resultado de la vez anterior no puede seguir en pantalla mientras corre esta: un
    // «312 prospectos recalculados» de hace cinco minutos, al lado del velo, dice que ya
    // terminó algo que está empezando.
    setAviso(null);
    try {
      // 202: el servidor acepta el trabajo y devuelve su identificador. El recorrido
      // ocurre después, así que hay que esperar a que termine antes de recargar; si no,
      // se recargarían los scores viejos y parecería que el recálculo no hizo nada.
      const trabajo = await recalculateAllScores();

      let estado = trabajo;
      for (let intento = 0; intento < SONDEOS_MAXIMOS; intento += 1) {
        if (estado.status === 'COMPLETED' || estado.status === 'FAILED') break;
        setGlobalLoadingMsg(
          `Recalculando ${estado.processed_leads}/${estado.total_leads} prospectos `
          + `(${estado.progress_percentage}%)...`,
        );
        await new Promise((resolve) => setTimeout(resolve, SONDEO_MS));
        estado = await getRecalculationJob(trabajo.id);
      }

      if (estado.status === 'FAILED') {
        setAviso({
          tipo: 'error',
          texto: `El recálculo no pudo completarse: ${estado.error_message || 'error desconocido'}`,
        });
      } else if (estado.status === 'COMPLETED') {
        const fallidos = estado.failed_leads
          ? ` (${estado.failed_leads} no se pudieron recalcular)`
          : '';
        setAviso({
          tipo: 'ok',
          texto: `${estado.processed_leads} prospectos recalculados${fallidos}.`,
        });
      } else {
        // Ni un fallo ni un final: el sondeo se agotó y el trabajo sigue. Es la variante
        // ámbar, que hasta el capítulo 43 no tenía dónde salir —`.alert-warn` estaba
        // escrita en la hoja desde el 40 y no la usaba ningún componente—.
        setAviso({
          tipo: 'warn',
          texto: 'El recálculo sigue en curso; puede tardar unos minutos más. '
            + 'Los scores se actualizarán solos: vuelva a cargar la vista en un rato.',
        });
      }

      loadLeads();
      loadData();
    } catch (err) {
      // 409: el turno está ocupado. No es un error del que informar en abstracto —hay un
      // recálculo concreto en marcha y el servidor dice cuál y por dónde va—, así que se
      // enseña eso en lugar de «error en recálculo masivo».
      if (err.status === 409 && err.detalle) {
        const { procesados, total, solicitado_por: solicitadoPor } = err.detalle;
        const avance = (typeof procesados === 'number' && typeof total === 'number')
          ? ` Va por ${procesados} de ${total}.`
          : '';
        const quien = solicitadoPor ? ` Lo lanzó ${solicitadoPor}.` : '';
        // Ámbar y no rojo: no ha fallado nada. Hay un recálculo en marcha y el servidor
        // dice cuál y por dónde va, que es justo lo contrario de un error.
        setAviso({ tipo: 'warn', texto: `${err.message}${avance}${quien}` });
      } else {
        setAviso({ tipo: 'error', texto: `El recálculo masivo no se pudo lanzar: ${err.message}` });
      }
    } finally {
      setIsRecalculating(false);
      setGlobalLoading(false);
      setGlobalLoadingMsg('');
    }
  };

  if (!authChecked) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem',
      }}>
        Verificando sesión...
      </div>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        expiredNotice={sessionExpired}
        notice={avisoDeAcceso}
        onAuthenticated={(authenticatedUser) => {
          setSessionExpired(false);
          setAvisoDeAcceso(null);
          setUser(authenticatedUser);
        }}
      />
    );
  }

  // Una cuenta con la contraseña que le fijó otra persona no entra a la aplicación: el
  // servidor le rechazaría todo salvo cambiarla. Enseñarle el panel para que cada tarjeta
  // falle con un 403 sería peor que no enseñárselo. Las cargas de datos de arriba tampoco
  // se lanzan en este estado, por la misma razón.
  if (user.must_change_password) {
    return (
      <CambioDeContrasenaObligatorio
        user={user}
        onCompletado={async (mensaje) => {
          // El servidor ya cerró todas las sesiones, esta incluida. Se limpia la local y se
          // vuelve a la entrada diciendo por qué, para que no parezca una caducidad.
          await logout();
          setAvisoDeAcceso(mensaje);
          setUser(null);
        }}
        onSalir={handleLogout}
      />
    );
  }

  // Y lo mismo con el segundo factor (capítulo 35). Va DESPUÉS del cambio de contraseña
  // porque ese es el orden que aplica el servidor: una cuenta con las dos cosas pendientes
  // tiene que cambiar primero la credencial que conoce otra persona. Al revés, ataría un
  // teléfono a una cuenta que todavía no es suya.
  if (faltaElSegundoFactor(user)) {
    return (
      <AltaDelSegundoFactor
        user={user}
        onActivado={async () => {
          // Se vuelve a la entrada en lugar de seguir con la sesión actual. El segundo
          // factor acaba de cambiar lo que hace falta para entrar, y que la primera vez que
          // se usa sea inmediatamente después de activarlo es la única forma de comprobar
          // en el momento que el teléfono quedó bien atado.
          await logout();
          setAvisoDeAcceso('Segundo factor activado. Vuelva a entrar usando el código de su aplicación.');
          setUser(null);
        }}
        onSalir={handleLogout}
      />
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* El velo de una operación larga (capítulo 43 le puso lo que le faltaba)
          ----------------------------------------------------------------------
          Tapa la página entera —`position: fixed`, `inset: 0`— y escribe el avance del
          recálculo masivo, que recorre la cartera completa y puede durar minutos. No
          llevaba `role`, ni `aria-live`, ni `aria-busy`: para quien no ve la pantalla, la
          aplicación se quedaba cubierta y muda, sin forma de saber si estaba trabajando o
          colgada. El barrido de `axe` del capítulo 36 no lo encontró porque el velo es
          condicional y ninguna prueba lo montaba encendido.

          `aria-busy` va en el velo y no en `<main>` porque es el velo lo que aparece, y
          `aria-live="polite"` en lugar de `assertive`: el avance cambia cada vez que el
          sondeo contesta —cada segundo y medio—, y un anuncio que interrumpe a esa
          cadencia no deja oír nada más. */}
      {globalLoading && (
        <div role="status" aria-live="polite" aria-busy="true" style={{
          position: 'fixed', inset: 0, background: 'var(--overlay-loading)',
          zIndex: 9999, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '16px',
          backdropFilter: 'blur(4px)',
        }}>
          <div style={{
            width: '48px', height: '48px', border: '4px solid var(--border-subtle)',
            borderTop: '4px solid var(--accent-primary)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ color: 'var(--text-primary)', fontSize: '0.9rem', fontWeight: '500' }}>
            {globalLoadingMsg || 'Procesando...'}
          </span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenNewLead={() => setIsNewLeadOpen(true)}
        currentRole={currentRole}
        user={user}
        onOpenSessionModal={() => setIsSessionModalOpen(true)}
        onSelectLead={handleSelectLead}
      />

      <main style={{ maxWidth: '1400px', margin: '0 auto', width: '100%', padding: '24px 20px', flex: 1 }}>

        {/* Dos regiones vivas, siempre en el documento y vacías mientras no hay nada que
            decir, con el mismo reparto que la pantalla de derechos: `role="alert"` para lo
            que falló, `role="status"` para lo que no. Un error anunciado como estado espera
            a que el lector de pantalla acabe lo que esté diciendo; un éxito anunciado como
            alerta interrumpe para dar una buena noticia.

            Son dos y no una con el `role` cambiante porque un lector de pantalla registra
            la región cuando entra en el documento: cambiarle el papel la convierte en otra
            región, y lo que aparece dentro de una región recién nacida no se anuncia. Por
            eso también están aquí vacías en vez de montarse con el aviso dentro.

            Y están en `<main>`, encima de la pestaña que sea: el botón del recálculo vive
            en administración, pero el resultado llega minutos después y quien lo lanzó
            puede estar mirando cualquier otra cosa. */}
        <div role="alert">
          {aviso && aviso.tipo === 'error' && <AvisoDelPanel aviso={aviso} onCerrar={() => setAviso(null)} />}
        </div>
        <div role="status">
          {aviso && aviso.tipo !== 'error' && <AvisoDelPanel aviso={aviso} onCerrar={() => setAviso(null)} />}
        </div>


        {/* Lo que hay que hacer hoy (capítulo 28). El líder ve además los HOT que se
            enfrían y con qué asesor están. */}
        {activeTab === 'hoy' && (
          <BandejaDeHoy
            onSelectLead={handleSelectLead}
            esDireccion={esDireccion}
          />
        )}

        {/* KPI Top Cards (Visible on Dashboard and Leads tab) */}
        {(activeTab === 'dashboard' || activeTab === 'leads') && (
          <KPICards
            summary={summary}
            onFilterCategory={(cat) => {
              setSelectedCategory(cat);
              setActiveTab('leads');
            }}
          />
        )}

        {/* Tab 1: Dashboard Analítico */}
        {activeTab === 'dashboard' && (
          <div>
            {/* Lo que hay sin repartir, antes de las gráficas (§6.2, punto 11). El mismo
                componente y el mismo número que en «Publicaciones», donde sigue estando;
                aquí además lleva a la matriz, que es donde se abre la ficha y se asigna. */}
            {esDireccion && (
              <ContadorSinAsesor total={sinAsesor} onIrARepartir={() => setActiveTab('leads')} />
            )}
            <AnalyticsCharts summary={summary} campaigns={campaigns} />
            <LeadsTable
              leads={leads.slice(0, 8)}
              loading={loadingLeads}
              selectedCategory={selectedCategory}
              setSelectedCategory={setSelectedCategory}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onSelectLead={handleSelectLead}
              onRefresh={loadLeads}
            />
          </div>
        )}

        {/* Tab 2: Matriz Completa de Prospectos */}
        {activeTab === 'leads' && (
          <div>
            <LeadsTable
              leads={leads}
              loading={loadingLeads}
              selectedCategory={selectedCategory}
              setSelectedCategory={setSelectedCategory}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onSelectLead={handleSelectLead}
              onRefresh={loadLeads}
            />
          </div>
        )}

        {/* Tab 3: Simulador de Scoring */}
        {activeTab === 'simulator' && (
          <div>
            <ScoringSimulator />
          </div>
        )}

        {/* Publicaciones de LinkedIn: gestionan el líder y el administrador, el asesor consulta */}
        {activeTab === 'publicaciones' && (
          <Publicaciones
            puedeGestionar={esDireccion}
            onSelectLead={handleSelectLead}
          />
        )}

        {/* Qué se gana, qué se pierde y por qué (capítulo 30). Solo dirección: el
            servidor responde 403 a un asesor, así que la pestaña tampoco se le ofrece. */}
        {activeTab === 'desenlaces' && <PanelDeDesenlaces />}

        {/* Tab 4: Panel de Administración (Solo Admin y Líder) */}
        {activeTab === 'admin' && (
          <div>
            <AdminPanel
              onBatchRecalculate={handleBatchRecalculate}
              isRecalculating={isRecalculating}
            />
            {/* Los derechos de la persona cuyos datos guarda el sistema (§6.2, punto 16).
                Va en administración y no en la ficha de un prospecto a propósito: la
                petición la trae alguien de fuera por su correo, y quien la atiende no tiene
                por qué saber si esa persona está en la base ni en qué ficha. */}
            <DerechosDelTitular />
            <BandejaSinAsociar />
          </div>
        )}

      </main>

      {/* Footer Minimalista */}
      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-base)',
        padding: '16px 24px',
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
        textAlign: 'center',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <span>PluriOne S.A. de C.V. • Sistema Inteligente de Lead Scoring v1.0</span>
        <span style={{ fontFamily: 'var(--font-mono)' }}>Entorno: Producción Calibrada</span>
      </footer>

      {/* Modals */}
      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => {
            setSelectedLead(null);
            setModalStartEdit(false);
          }}
          onLeadUpdated={handleLeadUpdated}
          startInEditMode={modalStartEdit}
        />
      )}

      {isNewLeadOpen && (
        <NewLeadModal
          onClose={() => setIsNewLeadOpen(false)}
          onLeadCreated={() => {
            loadLeads();
            loadData();
          }}
        />
      )}

      {isSessionModalOpen && (
        <SessionModal
          user={user}
          onLogout={async () => {
            setIsSessionModalOpen(false);
            await handleLogout();
          }}
          onClose={() => setIsSessionModalOpen(false)}
        />
      )}
    </div>
  );
}
