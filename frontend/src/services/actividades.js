// Nombres legibles de lo que el servidor guarda con identificadores en inglés.
//
// El historial de la ficha enseñaba `PROPOSAL_SENT` y `WHATSAPP_MESSAGE` tal cual, junto a un
// «Peso: 25 pts» que el scoring nunca leyó. Esta tabla es la única traducción: la ficha, la
// bandeja «Sin asociar» y sus pruebas leen de aquí.

export const NOMBRES_DE_ACTIVIDAD = {
  PAGE_VIEW: 'Visita a la web',
  FORM_SUBMIT: 'Formulario enviado',
  EMAIL_OPEN: 'Correo abierto',
  EMAIL_CLICK: 'Clic en un correo',
  DEMO_REQUEST: 'Solicitud de demo',
  WEBINAR_ATTEND: 'Asistencia a webinar',
  CONTENT_DOWNLOAD: 'Descarga de contenido',
  CHAT_INTERACTION: 'Conversación por chat',
  PHONE_CALL: 'Llamada',
  MEETING_SCHEDULED: 'Reunión agendada',
  WHATSAPP_MESSAGE: 'Mensaje de WhatsApp',
  LINKEDIN_MESSAGE: 'Mensaje de LinkedIn',
  PROPOSAL_SENT: 'Propuesta enviada',
  CUSTOM: 'Otro evento',
};

export const NOMBRES_DE_ETAPA = {
  NEW: 'Nuevo',
  CONTACTED: 'Contactado',
  ENGAGED: 'En conversación',
  QUALIFIED: 'Calificado',
  MEETING_SCHEDULED: 'Reunión agendada',
  PROPOSAL_SENT: 'Propuesta enviada',
  NEGOTIATION: 'En negociación',
  UNQUALIFIED: 'No calificado',
  WON: 'Ganado',
  LOST: 'Perdido',
};

// Las etapas que se cierran con un desenlace (capítulo 30). El servidor responde 422 si
// alguna llega por la edición de la ficha: cerrar exige motivo, fecha y —si se ganó— el
// tramo del acuerdo, y eso lo pide `POST /leads/{id}/desenlace`.
export const ETAPAS_DE_CIERRE = ['WON', 'LOST'];

// Lo que el selector de etapa de la ficha puede ofrecer. Se calcula desde la tabla de
// arriba en lugar de escribirse a mano: una etapa nueva aparece en el selector el día que
// se crea, y el día que otra pase a cerrarse con motivo desaparece de él sin que haya que
// acordarse de este archivo.
export const ETAPAS_EDITABLES = Object.keys(NOMBRES_DE_ETAPA).filter(
  (etapa) => !ETAPAS_DE_CIERRE.includes(etapa),
);

export function esEtapaDeCierre(etapa) {
  return ETAPAS_DE_CIERRE.includes(etapa);
}

export const RESULTADOS_DE_LLAMADA = {
  CONECTO: 'Conectó',
  NO_CONTESTO: 'No contestó',
  BUZON: 'Buzón de voz',
};

export const DIRECCIONES = {
  SALIENTE: 'Enviado',
  ENTRANTE: 'Recibido',
};

export const NOMBRES_DE_FUENTE = {
  manual: 'Registro manual',
  pipeline: 'Cambio de etapa',
  crm: 'CRM',
  formulario_web: 'Formulario web',
  linkedin_lead_gen: 'LinkedIn Lead Gen',
  pagina_de_interes: 'Página de interés',
  calendly: 'Calendly',
  whatsapp: 'WhatsApp',
};

// Lo que un asesor registra desde la ficha: sus propias conversaciones con la persona.
//
// La propuesta y la reunión no están: las registra el pipeline al cambiar la etapa. Tampoco
// la solicitud de demo, la descarga de contenido, la asistencia a un webinar ni el «otro
// evento»: los tres primeros son formularios o plataformas que registran lo que ven —el
// formulario web, LinkedIn Lead Gen, el CRM—, y declarados a mano sumaban puntos por algo
// que nadie envió desde el panel. «Otro evento» sumaba sin decir qué había pasado.
export const TIPOS_DECLARABLES = ['PHONE_CALL', 'WHATSAPP_MESSAGE', 'LINKEDIN_MESSAGE'];

export const AYUDA_DE_TIPO = {
  PHONE_CALL: 'Con su resultado: conectó, no contestó o buzón.',
  WHATSAPP_MESSAGE: 'Enviado o recibido. No se guarda el texto.',
  LINKEDIN_MESSAGE: 'Enviado o recibido. No se guarda el texto.',
};

export const TIPOS_DE_MENSAJE = ['WHATSAPP_MESSAGE', 'LINKEDIN_MESSAGE'];

export function nombreDeActividad(tipo) {
  return NOMBRES_DE_ACTIVIDAD[tipo] || tipo;
}

export function nombreDeEtapa(etapa) {
  return NOMBRES_DE_ETAPA[etapa] || etapa;
}

// Los sectores que conoce el modelo, escritos como se leen. El valor que viaja es el de la
// izquierda —es vocabulario del modelo y no se toca—; lo que cambia es lo que se lee.
//
// Se encontró recorriendo la página pública desde el teléfono, que es donde la ve quien no
// trabaja aquí: una página entera en castellano y, en «Sector», siete de las diez opciones
// en inglés. No es jerga del oficio como «CTO»: son palabras corrientes —banca, salud,
// logística— que nadie elige en otro idioma para decir a qué se dedica.
//
// `NOMBRES_DE_SECTOR` no cubre lo que se escribe a mano en el panel, donde el campo es
// libre: `nombreDeSector` devuelve tal cual lo que no esté en la tabla.
export const NOMBRES_DE_SECTOR = {
  Banking: 'Banca',
  'E-Commerce': 'Comercio electrónico',
  Healthcare: 'Salud',
  Logistics: 'Logística',
  Retail: 'Comercio minorista',
  Consulting: 'Consultoría',
  Manufacturing: 'Manufactura',
  Education: 'Educación',
};

export function nombreDeSector(sector) {
  return NOMBRES_DE_SECTOR[sector] || sector;
}

export function nombreDeFuente(fuente) {
  return NOMBRES_DE_FUENTE[fuente] || fuente;
}

// «47,8»: una cifra decimal, con coma, como se escribe el cambio de score en la ficha.
export function formatearScore(valor) {
  if (typeof valor !== 'number' || Number.isNaN(valor)) return '—';
  return valor.toFixed(1).replace('.', ',');
}

// Lo que se enseña al registrar: «47,8 → 58,6». Sin score anterior (la ficha se acaba de
// crear) se enseña solo el nuevo.
export function describirCambioDeScore({ score_anterior: anterior, score }) {
  if (typeof anterior !== 'number') return formatearScore(score);
  return `${formatearScore(anterior)} → ${formatearScore(score)}`;
}
