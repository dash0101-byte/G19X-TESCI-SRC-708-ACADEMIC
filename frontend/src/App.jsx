import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import LoginScreen from './components/LoginScreen';
import KPICards from './components/KPICards';
import AnalyticsCharts from './components/AnalyticsCharts';
import LeadsTable from './components/LeadsTable';
import LeadDetailModal from './components/LeadDetailModal';
import ScoringSimulator from './components/ScoringSimulator';
import AdminPanel from './components/AdminPanel';
import BandejaSinAsociar from './components/BandejaSinAsociar';
import Publicaciones from './components/Publicaciones';
import SessionModal from './components/SessionModal';
import NewLeadModal from './components/NewLeadModal';
import CambioDeContrasenaObligatorio from './components/CambioDeContrasenaObligatorio';
import {
  fetchAnalyticsSummary,
  fetchCampaigns,
  fetchLeads,
  fetchLeadDetail,
  getRecalculationJob,
  recalculateAllScores,
  restoreSession,
  logout,
  setSessionExpiredHandler,
} from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  // La identidad y el rol vienen del servidor tras autenticarse; el cliente ya no los
  // elige ni los guarda en localStorage, donde eran editables desde la consola.
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  // Lo que la pantalla de entrada tiene que decir al volver a ella cuando no es una
  // caducidad: que la contraseña se acaba de cambiar y hay que entrar con la nueva.
  const [avisoDeAcceso, setAvisoDeAcceso] = useState(null);
  const currentRole = user?.role ?? null;
  const [summary, setSummary] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [leads, setLeads] = useState([]);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [globalLoadingMsg, setGlobalLoadingMsg] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  
  const [selectedLead, setSelectedLead] = useState(null);
  const [isNewLeadOpen, setIsNewLeadOpen] = useState(false);
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setActiveTab('dashboard');
    setSummary(null);
    setCampaigns([]);
    setLeads([]);
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
  }, []);

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
    if (!user || user.must_change_password) return;
    loadData();
  }, [user, loadData]);

  useEffect(() => {
    if (!user || user.must_change_password) return;
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
      alert('Error al cargar detalle del lead: ' + err.message);
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
        alert(`El recálculo no pudo completarse: ${estado.error_message || 'error desconocido'}`);
      } else if (estado.status === 'COMPLETED') {
        const fallidos = estado.failed_leads
          ? ` (${estado.failed_leads} no se pudieron recalcular)`
          : '';
        alert(`✅ ${estado.processed_leads} prospectos recalculados${fallidos}.`);
      } else {
        alert(
          'El recálculo sigue en curso; puede tardar unos minutos más. '
          + 'Los scores se actualizarán solos: vuelva a cargar la vista en un rato.',
        );
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
        alert(`${err.message}${avance}${quien}`);
      } else {
        alert('Error en recálculo masivo: ' + err.message);
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

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Overlay de carga global para operaciones de red significativas */}
      {globalLoading && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
          zIndex: 9999, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '16px',
          backdropFilter: 'blur(4px)',
        }}>
          <div style={{
            width: '48px', height: '48px', border: '4px solid var(--border-subtle)',
            borderTop: '4px solid var(--accent-primary)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ color: '#fff', fontSize: '0.9rem', fontWeight: '500' }}>
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
      />

      <main style={{ maxWidth: '1400px', margin: '0 auto', width: '100%', padding: '24px 20px', flex: 1 }}>
        
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
            puedeGestionar={currentRole === 'Sales_Lead' || currentRole === 'System_Admin'}
            onSelectLead={handleSelectLead}
          />
        )}

        {/* Tab 4: Panel de Administración (Solo Admin y Líder) */}
        {activeTab === 'admin' && (
          <div>
            <AdminPanel
              onBatchRecalculate={handleBatchRecalculate}
              isRecalculating={isRecalculating}
            />
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
