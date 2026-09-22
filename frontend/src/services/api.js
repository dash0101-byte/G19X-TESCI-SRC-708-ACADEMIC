const API_BASE = '/api/v1';

// ============================================================================
// Sesión
// ============================================================================
// El access token vive SOLO en esta variable de módulo. No se guarda en
// localStorage ni sessionStorage: cualquier XSS puede leer ese almacenamiento, y
// un token allí sobrevive al cierre de la pestaña. El refresh token ni siquiera
// llega hasta aquí — viaja en una cookie HttpOnly que JavaScript no puede leer.

let accessToken = null;
let currentUser = null;
let onSessionExpired = null;

// Contador de sesiones. Sube cada vez que la sesión se cierra —al salir o al caducar—.
// Sirve para que una renovación lanzada ANTES del cierre no escriba su resultado
// DESPUÉS: sin esto, cerrar sesión mientras había un refresco en el aire dejaba la
// pestaña dentro otra vez, con un token recién emitido y sin que nadie hubiera vuelto a
// entrar. Se descubrió con la prueba `un refresco en vuelo no puede resucitar una sesión
// ya cerrada`, que al principio pasaba por casualidad porque el reintento posterior
// devolvía otro 401 y volvía a limpiarlo todo.
let epocaDeSesion = 0;

// Una sola promesa de refresco compartida: si varias peticiones reciben 401 a la vez,
// todas esperan al mismo refresco en lugar de disparar una tormenta de renovaciones.
let refreshPromise = null;

export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

export function getCurrentUser() {
  return currentUser;
}

export function getCurrentUserRole() {
  return currentUser?.role ?? null;
}

export function isAuthenticated() {
  return Boolean(accessToken);
}

function clearSession() {
  accessToken = null;
  currentUser = null;
  epocaDeSesion += 1;
  // La renovación en curso, si la hay, ya no sirve para nada: pertenece a la sesión que
  // se acaba de cerrar. Se descarta para que la siguiente no la reutilice.
  refreshPromise = null;
}

// Pydantic antepone «Value error, » a lo que dice el validador: es el nombre interno de su
// excepción y no significa nada para quien lo lee. En la página pública dejaba en pantalla
// «linkedin: Value error, El perfil tiene que ser...» delante de una frase que ya estaba
// escrita para leerse. Se quita el prefijo, no el mensaje.
const RUIDO_DE_PYDANTIC = /^(Value error|Assertion failed),\s*/;

function parseApiError(err, defaultMsg) {
  if (!err) return defaultMsg;
  if (typeof err.detail === 'string') return err.detail;
  if (Array.isArray(err.detail)) {
    return err.detail
      .map((item) => {
        const field = item.loc ? item.loc.filter((x) => x !== 'body').join('.') : '';
        const mensaje = String(item.msg || '').replace(RUIDO_DE_PYDANTIC, '');
        return field ? `${field}: ${mensaje}` : mensaje;
      })
      .join('\n');
  }
  if (err.detail && typeof err.detail === 'object') {
    // El backend devuelve algunos conflictos con un detalle estructurado —el 409 del
    // recálculo masivo lleva el trabajo que ocupa el turno y por dónde va— para que el
    // cliente pueda hacer algo útil con ellos. Cuando trae un `mensaje`, ese es el texto
    // para la persona; volcar el objeto entero con `JSON.stringify` dejaba en pantalla
    // `{"mensaje":"...","job_id":"...","estado":"RUNNING"}`, que tiene toda la
    // información y no se puede leer.
    if (typeof err.detail.mensaje === 'string') return err.detail.mensaje;
    // Un evento que el registro de actividad rechaza (422) trae `motivo`: qué falta o qué
    // no se admite —una llamada sin resultado, una propuesta declarada a mano—.
    if (typeof err.detail.motivo === 'string') return err.detail.motivo;
    return JSON.stringify(err.detail);
  }
  return err.message || defaultMsg;
}

async function throwApiError(res, defaultMsg) {
  const err = await res.json().catch(() => ({}));
  const error = new Error(parseApiError(err, defaultMsg));
  // Se cuelgan el código y el detalle del propio Error para que quien llama pueda
  // distinguir un conflicto de un fallo. Sin esto, la única forma de saber que un 409 es
  // un 409 sería comparar la cadena del mensaje, que se rompe al reescribir el texto.
  error.status = res.status;
  error.detalle = err && err.detail;
  throw error;
}

// ============================================================================
// Autenticación
// ============================================================================

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // `credentials: same-origin` permite que el navegador guarde la cookie de refresco
    credentials: 'same-origin',
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Email o contraseña incorrectos.');
    await throwApiError(res, 'No fue posible iniciar sesión');
  }
  const data = await res.json();
  accessToken = data.access_token;
  currentUser = data.user;
  return currentUser;
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    const epoca = epocaDeSesion;
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        if (!res.ok) return false;
        const data = await res.json();
        // Si la sesión cambió mientras esta petición estaba en vuelo, el token que
        // acaba de llegar es de una sesión que ya no existe. Se descarta.
        if (epoca !== epocaDeSesion) return false;
        accessToken = data.access_token;
        currentUser = data.user;
        return true;
      } catch {
        return false;
      } finally {
        // Se libera en el siguiente tick para que las peticiones que ya estaban
        // esperando lean el token nuevo antes de que se permita otro refresco.
        setTimeout(() => {
          // Solo si sigue siendo ESTA promesa: `clearSession` puede haberla puesto ya a
          // null y haber empezado otra distinta mientras tanto.
          if (epoca === epocaDeSesion) refreshPromise = null;
        }, 0);
      }
    })();
  }
  return refreshPromise;
}

/**
 * Restaura la sesión al cargar la página.
 *
 * El access token se pierde al recargar (vive en memoria), pero la cookie de refresco
 * sobrevive: si sigue siendo válida, se recupera la sesión sin volver a pedir la contraseña.
 */
export async function restoreSession() {
  const ok = await refreshAccessToken();
  return ok ? currentUser : null;
}

export async function logout() {
  try {
    if (accessToken) {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'same-origin',
      });
    }
  } catch {
    // Cerrar sesión NO puede fallar hacia fuera. Antes esto era un `finally` a secas: la
    // sesión local se limpiaba, sí, pero la excepción de red seguía subiendo y en
    // `App.jsx` reventaba el `await logout()` antes del `setUser(null)`. Resultado con el
    // servidor caído: el token desaparecía por dentro y la pantalla se quedaba dentro de
    // la aplicación, con cada acción posterior fallando. Quien pulsa «salir» ha salido.
  } finally {
    clearSession();
  }
}

// ============================================================================
// Cliente HTTP autenticado
// ============================================================================

/**
 * Realiza una llamada autenticada a la API.
 *
 * Ante un 401 intenta renovar el access token una única vez y reintenta la petición;
 * si el refresco también falla, la sesión ha caducado de verdad y se notifica a la app.
 */
async function apiFetch(path, options = {}, defaultMsg = 'Error de comunicación con el servidor') {
  const buildRequest = () => {
    const headers = { ...(options.headers || {}) };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (options.body) headers['Content-Type'] = 'application/json';
    return { ...options, headers, credentials: 'same-origin' };
  };

  let res = await fetch(`${API_BASE}${path}`, buildRequest());

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      res = await fetch(`${API_BASE}${path}`, buildRequest());
    }
    if (res.status === 401) {
      clearSession();
      if (onSessionExpired) onSessionExpired();
      throw new Error('Su sesión ha expirado. Vuelva a iniciar sesión.');
    }
  }

  if (!res.ok) await throwApiError(res, defaultMsg);
  if (res.status === 204) return null;
  return res.json();
}

// ============================================================================
// Endpoints de negocio
// ============================================================================

export function fetchAnalyticsSummary() {
  return apiFetch('/analytics/summary', {}, 'Error al cargar métricas analíticas');
}

export function fetchCampaigns() {
  return apiFetch('/analytics/campaigns', {}, 'Error al cargar rendimiento de campañas');
}

export function fetchLeads(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.category) searchParams.append('score_category', params.category);
  if (params.status) searchParams.append('status', params.status);
  if (params.search) searchParams.append('search', params.search);
  if (params.assignedRepId) searchParams.append('assigned_rep_id', params.assignedRepId);
  if (params.limit) searchParams.append('limit', params.limit);
  if (params.offset) searchParams.append('offset', params.offset);

  return apiFetch(`/leads?${searchParams.toString()}`, {}, 'Error al cargar prospectos');
}

export function fetchLeadDetail(leadId) {
  return apiFetch(`/leads/${leadId}`, {}, 'Error al obtener ficha de prospecto');
}

export function createLead(leadData) {
  return apiFetch(
    '/leads',
    { method: 'POST', body: JSON.stringify(leadData) },
    'Error al registrar prospecto',
  );
}

export function updateLead(leadId, leadData) {
  return apiFetch(
    `/leads/${leadId}`,
    { method: 'PUT', body: JSON.stringify(leadData) },
    'Error al actualizar información del prospecto',
  );
}

export function addLeadActivity(leadId, activityData) {
  return apiFetch(
    `/leads/${leadId}/activities`,
    { method: 'POST', body: JSON.stringify(activityData) },
    'Error al registrar actividad',
  );
}

export function recalculateLeadScore(leadId) {
  return apiFetch(
    `/leads/${leadId}/recalculate-score`,
    { method: 'POST' },
    'Error al recalcular puntuación',
  );
}

// Bandeja «Sin asociar»: avisos de las integraciones —un WhatsApp de un número desconocido,
// una reunión de Calendly con un correo que no está en ninguna ficha— que esperan a que
// alguien diga a quién pertenecen.
export function fetchEventosSinAsociar({ limit = 50, offset = 0 } = {}) {
  return apiFetch(
    `/eventos-sin-asociar?limit=${limit}&offset=${offset}`,
    {},
    'Error al cargar la bandeja «Sin asociar»',
  );
}

export function vincularEventoSinAsociar(eventoId, leadId) {
  return apiFetch(
    `/eventos-sin-asociar/${eventoId}/vincular`,
    { method: 'POST', body: JSON.stringify({ lead_id: leadId }) },
    'Error al vincular el aviso',
  );
}

export function descartarEventoSinAsociar(eventoId) {
  return apiFetch(
    `/eventos-sin-asociar/${eventoId}`,
    { method: 'DELETE' },
    'Error al descartar el aviso',
  );
}

// El recálculo masivo ya no devuelve el resultado: responde 202 con el trabajo encolado.
// El recorrido puede tardar minutos con una cartera grande, mucho más de lo que aguantan
// el navegador y el `proxy_read_timeout` de nginx, así que el avance se consulta aparte.
export function recalculateAllScores(batchSize) {
  return apiFetch(
    '/leads/batch/recalculate-all',
    {
      method: 'POST',
      body: JSON.stringify(batchSize ? { batch_size: batchSize } : {}),
    },
    'Error en recálculo por lotes',
  );
}

export function getRecalculationJob(jobId) {
  return apiFetch(
    `/leads/batch/jobs/${jobId}`,
    { method: 'GET' },
    'Error al consultar el trabajo de recálculo',
  );
}

export function predictScoreLive(predictData) {
  return apiFetch(
    '/scoring/predict',
    { method: 'POST', body: JSON.stringify(predictData) },
    'Error en inferencia de scoring',
  );
}

// ============================================================================
// Gestión de identidades y campañas
//
// El panel de administración consumía datos escritos a mano en el propio componente y
// pedía la carga de cada asesor con una llamada al listado de prospectos por persona.
// Estas funciones lo sustituyen por los endpoints reales.
// ============================================================================

export function fetchSalesReps({ incluirInactivos = false } = {}) {
  // Una sola llamada: el backend trae cada asesor con su número de prospectos ya contado.
  const query = incluirInactivos ? '?incluir_inactivos=true' : '';
  return apiFetch(`/sales-reps${query}`, {}, 'Error al cargar el equipo comercial');
}

export function fetchUsers({ incluirInactivos = false, rol = null } = {}) {
  const params = new URLSearchParams();
  if (incluirInactivos) params.append('incluir_inactivos', 'true');
  if (rol) params.append('rol', rol);
  return apiFetch(`/users?${params.toString()}`, {}, 'Error al cargar las cuentas');
}

export function createUser(datos) {
  return apiFetch(
    '/users',
    { method: 'POST', body: JSON.stringify(datos) },
    'Error al crear la cuenta',
  );
}

export function updateUser(userId, cambios) {
  return apiFetch(
    `/users/${userId}`,
    { method: 'PUT', body: JSON.stringify(cambios) },
    'Error al modificar la cuenta',
  );
}

export function changeUserRole(userId, rol) {
  return apiFetch(
    `/users/${userId}/role?rol=${encodeURIComponent(rol)}`,
    { method: 'POST' },
    'Error al cambiar el rol',
  );
}

export function deactivateUser(userId) {
  return apiFetch(`/users/${userId}`, { method: 'DELETE' }, 'Error al desactivar la cuenta');
}

export function activateUser(userId) {
  return apiFetch(`/users/${userId}/activate`, { method: 'POST' }, 'Error al reactivar la cuenta');
}

export function resetUserPassword(userId, nuevaContrasena) {
  return apiFetch(
    `/users/${userId}/reset-password`,
    { method: 'POST', body: JSON.stringify({ nueva_contrasena: nuevaContrasena }) },
    'Error al restablecer la contraseña',
  );
}

export function transferPortfolio(origenId, destinoId) {
  return apiFetch(
    `/sales-reps/${origenId}/cartera`,
    { method: 'POST', body: JSON.stringify({ destino_id: destinoId }) },
    'Error al repartir la cartera',
  );
}

export function changeOwnPassword(contrasenaActual, nuevaContrasena) {
  return apiFetch(
    '/auth/change-password',
    {
      method: 'POST',
      body: JSON.stringify({
        contrasena_actual: contrasenaActual,
        nueva_contrasena: nuevaContrasena,
      }),
    },
    'Error al cambiar la contraseña',
  );
}

// ----------------------------------------------------------------- página pública
// Sin sesión y sin token: es la página a la que lleva el enlace de una publicación, y
// quien la abre no tiene cuenta. Por eso no pasa por `apiFetch`, que añadiría la
// cabecera de autorización y trataría un 401 como una sesión caducada.
async function publicFetch(path, options, defaultMsg) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(options && options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  if (!res.ok) await throwApiError(res, defaultMsg);
  return res.json();
}

// Abrir la página suma una visita en el servidor. En desarrollo, React monta dos veces cada
// componente y la página se pedía dos veces por cada apertura: el recuento salía doblado. Dos
// peticiones iguales a la vez comparten la misma respuesta; una apertura posterior sí vuelve
// a pedir, y cuenta, como debe.
const cargasEnCurso = new Map();

export function fetchPublicacionDeInteres(slug) {
  const enCurso = cargasEnCurso.get(slug);
  if (enCurso) return enCurso;
  const carga = publicFetch(`/interes/${encodeURIComponent(slug)}`, {}, 'No fue posible cargar la publicación')
    .finally(() => cargasEnCurso.delete(slug));
  cargasEnCurso.set(slug, carga);
  return carga;
}

export function enviarInteres(slug, datos) {
  return publicFetch(
    `/interes/${encodeURIComponent(slug)}`,
    { method: 'POST', body: JSON.stringify(datos) },
    'No fue posible enviar la solicitud',
  );
}

export function fetchCampaignList({ incluirInactivas = false, canal = '' } = {}) {
  const params = new URLSearchParams();
  if (incluirInactivas) params.set('incluir_inactivas', 'true');
  if (canal) params.set('canal', canal);
  const query = params.toString() ? `?${params}` : '';
  return apiFetch(`/campaigns${query}`, {}, 'Error al cargar las campañas');
}

export function createCampaign(datos) {
  return apiFetch(
    '/campaigns',
    { method: 'POST', body: JSON.stringify(datos) },
    'Error al crear la campaña',
  );
}

export function updateCampaign(campaignId, cambios) {
  return apiFetch(
    `/campaigns/${campaignId}`,
    { method: 'PUT', body: JSON.stringify(cambios) },
    'Error al modificar la campaña',
  );
}

export function deactivateCampaign(campaignId) {
  return apiFetch(
    `/campaigns/${campaignId}`,
    { method: 'DELETE' },
    'Error al desactivar la campaña',
  );
}

// Reactivar no tiene ruta propia: es una edición del estado, y queda en la bitácora como tal.
export function activateCampaign(campaignId) {
  return updateCampaign(campaignId, { is_active: true });
}

// borrador, activa, pausada o cerrada (capítulo 26).
export function cambiarEstadoDePublicacion(campaignId, estado) {
  return updateCampaign(campaignId, { estado });
}

export function duplicateCampaign(campaignId) {
  return apiFetch(
    `/campaigns/${campaignId}/duplicar`,
    { method: 'POST' },
    'Error al duplicar la publicación',
  );
}

// La página de interés tal como la verá el interesado, en cualquier estado y sin contar
// una visita: mirar la propia página desde el panel no es una visita de nadie.
export function fetchVistaPreviaDePublicacion(campaignId) {
  return apiFetch(
    `/publicaciones/${campaignId}/vista-previa`,
    {},
    'Error al cargar la vista previa de la página',
  );
}

// Los informes viven bajo `/publicaciones` y el alta y la edición bajo `/campaigns`: una
// publicación es una campaña con canal LinkedIn, y lo que cambia es la pregunta, no la
// entidad.
export function fetchInformeDePublicacion(campaignId, { etapa = '', desde = '', hasta = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (etapa) params.set('etapa', etapa);
  if (desde) params.set('desde', desde);
  if (hasta) params.set('hasta', hasta);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  return apiFetch(
    `/publicaciones/${campaignId}/informe?${params}`,
    {},
    'Error al cargar el informe de la publicación',
  );
}

export function fetchComparativaDePublicaciones() {
  return apiFetch('/publicaciones/comparativa', {}, 'Error al cargar la comparativa');
}

export function fetchNuevosSinAsesor() {
  return apiFetch('/publicaciones/nuevos-sin-asesor', {}, 'Error al contar los nuevos sin asesor');
}
