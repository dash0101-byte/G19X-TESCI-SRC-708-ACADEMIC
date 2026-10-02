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

/**
 * Los renglones de un 422, sin el nombre de la columna (capítulo 43).
 *
 * Esta función escribía `campo: mensaje` con el `campo` tal como viaja, que es el nombre de
 * la columna de la base: `nueva_contrasena`, `assigned_rep_id`, `cerrado_el`. El capítulo
 * 40 se lo quitó a las cuatro pantallas que reparten cada error debajo de su campo —ahí el
 * nombre no hace falta, porque el mensaje ya está al lado del campo del que habla— y lo
 * dejó escrito en §6.4 para las demás, que son las que caen aquí. Era «el mismo arreglo en
 * los sitios donde el 422 es menos probable»; no lo es, porque el nombre no se escribe en
 * esas pantallas sino **en este sitio**, una vez.
 *
 * Quitarlo y no traducirlo: una tabla de nombre de columna a etiqueta aquí sería una
 * segunda verdad sobre cómo se llama cada campo, y la primera es la etiqueta que cada
 * pantalla tiene escrita al lado de su `input` —`first_name` es «Nombre(s)» en la ficha y
 * «Nombre» en el alta—. Donde hace falta decir cuál es el campo se reparte por campos, con
 * `erroresDelServidor`, que para eso recibe las etiquetas de la pantalla.
 *
 * Los repetidos se colapsan: dos campos que fallan por lo mismo producen el mismo renglón
 * —«Falta este campo.» dos veces— y repetirlo no añade información, solo ruido.
 */
function renglonesDelCuerpo(detalle) {
  const vistos = [];
  for (const item of detalle) {
    const mensaje = String(item.msg || '').replace(RUIDO_DE_PYDANTIC, '');
    if (mensaje && !vistos.includes(mensaje)) vistos.push(mensaje);
  }
  return vistos.join('\n');
}

function parseApiError(err, defaultMsg) {
  if (!err) return defaultMsg;
  if (typeof err.detail === 'string') return err.detail;
  if (Array.isArray(err.detail)) return renglonesDelCuerpo(err.detail);
  if (err.detail && typeof err.detail === 'object') {
    // El backend devuelve algunos conflictos con un detalle estructurado —el 409 del
    // recálculo masivo lleva el trabajo que ocupa el turno y por dónde va— para que el
    // cliente pueda hacer algo útil con ellos. Cuando trae un `mensaje`, ese es el texto
    // para la persona; volcar el objeto entero con `JSON.stringify` dejaba en pantalla
    // `{"mensaje":"...","job_id":"...","estado":"RUNNING"}`, que tiene toda la
    // información y no se puede leer.
    if (typeof err.detail.mensaje === 'string') {
      // Y cuando además trae `motivos`, van detrás, un renglón cada uno (capítulo 43).
      //
      // La política de contraseñas devuelve **todos** los motivos por los que una no vale
      // —«Debe tener al menos 12 caracteres», «Está en la lista de contraseñas filtradas»—
      // y lo hace a propósito: su propio código lo explica, «devolver uno solo obliga a
      // descubrir la política a base de intentos». Esta función se quedaba con el
      // `mensaje` y tiraba la lista, así que en pantalla salía «La contraseña no cumple la
      // política del sistema.» y nada más. El comentario del formulario de sesión decía
      // desde el capítulo 23 que los enseñaba todos; no llegaba ninguno.
      const motivos = Array.isArray(err.detail.motivos)
        ? err.detail.motivos.filter((m) => typeof m === 'string' && m)
        : [];
      return [err.detail.mensaje, ...motivos].join('\n');
    }
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
  // Desde el capítulo 35 el login puede contestar dos cosas: una sesión, o un desafío de
  // segundo factor. El discriminador `tipo` es lo que las distingue, y se devuelve tal cual
  // para que quien llama decida: aquí no se abre sesión con un desafío.
  if (data.tipo === 'segundo_factor') {
    return data;
  }
  accessToken = data.access_token;
  currentUser = data.user;
  return currentUser;
}

/**
 * Segundo paso del acceso: el código del teléfono o uno de recuperación (capítulo 35).
 *
 * El desafío es lo único que acredita haber superado el primero, y no vale como
 * `Authorization`: viaja en el cuerpo porque no es una credencial de sesión.
 */
export async function completarLoginConSegundoFactor(desafio, codigo) {
  const res = await fetch(`${API_BASE}/auth/login/segundo-factor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ desafio, codigo: codigo.trim() }),
  });
  if (!res.ok) await throwApiError(res, 'No fue posible completar el acceso');
  const data = await res.json();
  accessToken = data.access_token;
  currentUser = data.user;
  return currentUser;
}

export function fetchEstadoDelSegundoFactor() {
  return apiFetch('/auth/segundo-factor', {}, 'Error al consultar el segundo factor');
}

export function altaDelSegundoFactor() {
  return apiFetch('/auth/segundo-factor/alta', { method: 'POST' }, 'Error al dar de alta el segundo factor');
}

export function activarSegundoFactor(codigo) {
  return apiFetch(
    '/auth/segundo-factor/activar',
    { method: 'POST', body: JSON.stringify({ codigo: codigo.trim() }) },
    'Error al activar el segundo factor',
  );
}

export function bajaDelSegundoFactor(codigo) {
  return apiFetch(
    '/auth/segundo-factor/baja',
    { method: 'POST', body: JSON.stringify({ codigo: codigo.trim() }) },
    'Error al quitar el segundo factor',
  );
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

/**
 * La red viaja como `?r=`, igual que en el enlace que abrió la persona (capítulo 27).
 *
 * No se valida aquí: si no se reconoce, el servidor la cuenta como «sin red» y sirve la
 * página igual. Filtrarla en el navegador solo adelantaría el mismo resultado y añadiría un
 * sitio más donde la lista de redes tendría que estar al día.
 */
function conRed(ruta, red) {
  return red ? `${ruta}?r=${encodeURIComponent(red)}` : ruta;
}

/**
 * La red con la que se abrió el enlace, leída de la dirección (`?r=whatsapp`).
 *
 * Vive aquí, y no suelta en el arranque de la aplicación, para que se pueda probar: el
 * fichero de arranque no lo monta ninguna prueba, así que un fallo ahí —devolver siempre
 * vacío, por ejemplo— no lo veía nadie.
 */
export function redDeLaUrl(busqueda = window.location.search) {
  return new URLSearchParams(busqueda).get('r') || '';
}

export function fetchPublicacionDeInteres(slug, red = '') {
  // La clave incluye la red: dos aperturas con redes distintas son dos visitas distintas y
  // no se pueden compartir; con el mismo enlace, sí (React monta dos veces en desarrollo).
  const clave = `${slug}?${red}`;
  const enCurso = cargasEnCurso.get(clave);
  if (enCurso) return enCurso;
  const carga = publicFetch(
    conRed(`/interes/${encodeURIComponent(slug)}`, red),
    {},
    'No fue posible cargar la publicación',
  ).finally(() => cargasEnCurso.delete(clave));
  cargasEnCurso.set(clave, carga);
  return carga;
}

export function enviarInteres(slug, datos, red = '') {
  return publicFetch(
    conRed(`/interes/${encodeURIComponent(slug)}`, red),
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

/**
 * Si la dirección pública configurada sigue llevando al sistema (capítulo 34).
 *
 * `responde` puede ser `true`, `false` o `null`; el último es «no se ha comprobado», que es
 * lo que contesta un despliegue sin túnel delante. No es lo mismo que «no responde» y la
 * pantalla no debe tratarlos igual.
 */
export function fetchEstadoDeLaDireccionPublica() {
  return apiFetch(
    '/publicaciones/direccion-publica',
    {},
    'Error al comprobar la dirección pública',
  );
}

// ============================================================================
// La agenda del día (capítulo 28)
// ============================================================================
// Solo lee y cierra. Quien decide qué hay que hacer es el motor de reglas, en la
// pasada diaria: ninguna de estas llamadas crea una tarea ni un aviso, así que
// abrir el panel dos veces no cambia lo que hay que hacer hoy.

export function fetchBandejaDeHoy({ asesorId = null } = {}) {
  const ruta = asesorId ? `/agenda/hoy?asesor_id=${asesorId}` : '/agenda/hoy';
  return apiFetch(ruta, {}, 'Error al cargar lo que hay que hacer hoy');
}

export function marcarTareaHecha(tareaId) {
  return apiFetch(`/agenda/tareas/${tareaId}/hecha`, { method: 'POST' }, 'Error al cerrar la tarea');
}

export function fetchAvisos({ soloSinLeer = false } = {}) {
  const ruta = soloSinLeer ? '/agenda/avisos?solo_sin_leer=true' : '/agenda/avisos';
  return apiFetch(ruta, {}, 'Error al cargar los avisos');
}

// Sin `ids`, marca todos los propios. El cuerpo va siempre, aunque sea vacío: el
// endpoint recibe la lista dentro de un objeto y un cuerpo ausente no es lo mismo
// que uno sin lista.
export function marcarAvisosLeidos(ids = null) {
  return apiFetch(
    '/agenda/avisos/leidos',
    { method: 'POST', body: JSON.stringify(ids ? { ids } : {}) },
    'Error al marcar los avisos como leídos',
  );
}

export function fetchHotQueSeEnfrian() {
  return apiFetch('/agenda/enfriandose', {}, 'Error al cargar los prospectos que se enfrían');
}

// ============================================================================
// El desenlace (capítulo 30)
// ============================================================================
// Cerrar un prospecto vive bajo `/leads` porque es algo que se le hace a un
// prospecto y necesita el alcance de cartera; leer las opciones y el panel vive
// bajo `/desenlaces`, que solo lee. Ninguna de las tres reentrena nada.

export function fetchOpcionesDeCierre() {
  return apiFetch('/desenlaces/opciones', {}, 'Error al cargar los motivos de cierre');
}

// `cierre` es {resultado, motivo, cerrado_el, tramo}. El servidor rechaza un motivo que
// no esté en la lista de ese resultado, un tramo en un perdido y un ganado sin tramo: la
// validación no se repite aquí a propósito, porque dos copias de una lista cerrada se
// desincronizan y la que manda es la del servidor.
export function cerrarProspecto(leadId, cierre) {
  return apiFetch(
    `/leads/${leadId}/desenlace`,
    { method: 'POST', body: JSON.stringify(cierre) },
    'Error al registrar el desenlace del prospecto',
  );
}

export function fetchPanelDeDesenlaces({ desde = '', hasta = '' } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set('desde', desde);
  if (hasta) params.set('hasta', hasta);
  const consulta = params.toString();
  return apiFetch(
    consulta ? `/desenlaces/panel?${consulta}` : '/desenlaces/panel',
    {},
    'Error al cargar el panel de desenlaces',
  );
}

// ============================================================================
// Derechos del titular (capítulo 38)
// ============================================================================
// Las tres llamadas que necesita la pantalla de derechos, y ni una más. Los dos
// endpoints que hacen el trabajo —la exportación y la supresión— existen desde la
// Fase 14 y están comprobados tabla por tabla (R-11); aquí no se añade ninguna
// lógica de supresión, solo la forma de pedirla desde el panel.

/**
 * La ficha que corresponde EXACTAMENTE a este correo, o `null`.
 *
 * Se apoya en el listado, que es el único sitio que sabe buscar y el único que aplica el
 * alcance de cartera. Dos cosas que no son adorno:
 *
 * 1. **La igualdad la comprueba esta función, no el servidor.** `search` es un `LIKE`
 *    sobre nombre, apellido, correo, empresa y cargo: buscar «ana@x.com» trae también a
 *    «diana@x.com», y una pantalla de derechos que exporte o suprima por coincidencia
 *    parcial entrega —o borra— los datos de otra persona. Es el mismo cuidado que el
 *    servicio tiene al rastrear el correo dentro de las cargas del CRM.
 * 2. **`null` significa «no consta», y nada más.** No distingue entre un correo que nunca
 *    entró y uno cuya ficha ya se suprimió, porque la pantalla tampoco debe distinguirlos:
 *    si dijera «esta persona fue suprimida», sería el oráculo de pertenencia que
 *    `huella_del_titular` existe para no ser.
 */
export async function buscarTitularPorCorreo(correo) {
  const buscado = (correo || '').trim().toLowerCase();
  if (!buscado) return null;
  // El tope de página del servidor. Un `LIKE` sobre un dominio corriente puede traer
  // muchas filas, y la que interesa no tiene por qué venir primera: se pide el máximo
  // que el endpoint admite y se busca la igualdad dentro.
  const pagina = await fetchLeads({ search: buscado, limit: 200 });
  const fichas = (pagina && pagina.items) || [];
  return fichas.find((ficha) => (ficha.email || '').trim().toLowerCase() === buscado) || null;
}

/**
 * Todo lo que el sistema guarda de una persona, en el documento que define el servidor.
 *
 * Se devuelve tal cual llega. La pantalla enseña un resumen y ofrece el archivo, pero el
 * archivo es este documento sin tocar: recomponerlo en el cliente habría creado una
 * segunda versión de «qué datos tiene el sistema», y la buena es la que el servidor
 * construye recorriendo el mapa de tablas.
 */
export function exportarDatosDelTitular(leadId) {
  return apiFetch(
    `/leads/${leadId}/exportar`,
    {},
    'Error al reunir los datos del titular',
  );
}

/**
 * Suprime a la persona y todo lo que cuelga de ella. No tiene vuelta atrás.
 *
 * Responde 204 sin cuerpo: lo que se fue de cada tabla queda en la bitácora, en el asiento
 * `lead.eliminar`, junto a una huella con clave del correo. Por eso la pantalla pide la
 * exportación ANTES de suprimir: es la única manera de poder decir qué había.
 */
export function suprimirTitular(leadId) {
  return apiFetch(
    `/leads/${leadId}`,
    { method: 'DELETE' },
    'Error al suprimir los datos del titular',
  );
}
