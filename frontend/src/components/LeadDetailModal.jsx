import React, { useState, useEffect } from 'react';
import { addLeadActivity, recalculateLeadScore, updateLead } from '../services/api';
import AsignarAsesor from './AsignarAsesor';
import CerrarProspecto from './CerrarProspecto';
import LlegoPor from './LlegoPor';
import { ingresosDelFormulario } from '../services/prospecto';
import { useVentanaModal } from './ventanaModal';
import {
  AYUDA_DE_TIPO,
  DIRECCIONES,
  ETAPAS_EDITABLES,
  NOMBRES_DE_ETAPA,
  RESULTADOS_DE_LLAMADA,
  TIPOS_DECLARABLES,
  TIPOS_DE_MENSAJE,
  describirCambioDeScore,
  esEtapaDeCierre,
  nombreDeActividad,
  nombreDeEtapa,
  nombreDeFuente,
} from '../services/actividades';

export default function LeadDetailModal({ lead: initialLead, onClose, onLeadUpdated, startInEditMode = false }) {
  // La guarda contra `lead` ausente estaba AQUÍ, antes de los hooks. Hoy no se dispara
  // —`App.jsx` monta el modal con `{selectedLead && ...}`, así que nunca llega nulo—,
  // pero es un cartucho puesto: en el momento en que algún camino renderizara este
  // componente con `lead={null}` estando ya montado, React contaría menos hooks que en
  // el render anterior, lanzaría durante el render y, sin ninguna frontera de error por
  // encima, la aplicación entera se quedaría en blanco. La comprobación baja después de
  // los hooks y el valor inicial se toma con `?.`, que es lo que la hace innecesaria.
  const datos = initialLead || {};

  const [lead, setLead] = useState(initialLead);
  const [isEditing, setIsEditing] = useState(startInEditMode);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState('');

  // Registro de actividad. Sin canal ni peso: el canal lo deduce el servidor del tipo, y el
  // peso lo mandaba este formulario sin que el scoring lo leyera nunca.
  const [newActivityType, setNewActivityType] = useState('PHONE_CALL');
  const [callOutcome, setCallOutcome] = useState('');
  const [direction, setDirection] = useState('SALIENTE');
  const [activityNotes, setActivityNotes] = useState('');
  const [isSubmittingAct, setIsSubmittingAct] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);
  // El formulario de cierre (capitulo 30). Empieza plegado: cerrar un prospecto no es una
  // accion que se haga a diario, y tenerla siempre abierta la pone a la altura de registrar
  // una llamada, que si lo es.
  const [cerrando, setCerrando] = useState(false);
  // Lo que pasó al registrar: el cambio real del score («47,8 → 58,6») o el motivo del
  // rechazo. El selector prometía «+25 pts», que no era lo que el score se movía.
  const [cambioDeScore, setCambioDeScore] = useState(null);
  const [errorDeActividad, setErrorDeActividad] = useState('');

  // Form edit state
  const [editForm, setEditForm] = useState({
    first_name: datos.first_name || '',
    last_name: datos.last_name || '',
    email: datos.email || '',
    phone: datos.phone || '',
    // Vacío y no «México» (capítulo 32). Precargarlo hacía que guardar una ficha sin país
    // —las de la página de interés, que no lo pregunta— le escribiera uno sin que nadie
    // lo hubiera elegido, y por el camino más difícil de detectar: el asesor entraba a
    // corregir un teléfono y salía habiendo declarado un país.
    country: datos.country || '',
    city: datos.city || '',
    company: datos.company || '',
    job_title: datos.job_title || '',
    industry: datos.industry || '',
    // Vacíos y no «11-50» ni 0: guardar la ficha sin tocarlos escribía un tamaño y unos
    // ingresos que nadie había dado, y el modelo los leía como datos (capítulo 24).
    company_size: datos.company_size || '',
    annual_revenue: datos.annual_revenue ?? '',
    status: datos.status || 'NEW',
    source: datos.source || 'Directo',
    profiles_needed: datos.raw_metadata?.profiles_needed || '',
    urgency: datos.raw_metadata?.urgency || 'MEDIA',
    budget_range: datos.raw_metadata?.budget_range || '',
    work_modality: datos.raw_metadata?.work_modality || 'Híbrido',
    tags: datos.raw_metadata?.tags || '',
  });

  useEffect(() => {
    if (!initialLead) return;
    setLead(initialLead);
    setEditForm({
      first_name: initialLead.first_name || '',
      last_name: initialLead.last_name || '',
      email: initialLead.email || '',
      phone: initialLead.phone || '',
      country: initialLead.country || '',
      city: initialLead.city || '',
      company: initialLead.company || '',
      job_title: initialLead.job_title || '',
      industry: initialLead.industry || '',
      company_size: initialLead.company_size || '',
      annual_revenue: initialLead.annual_revenue ?? '',
      status: initialLead.status || 'NEW',
      source: initialLead.source || 'Directo',
      profiles_needed: initialLead.raw_metadata?.profiles_needed || '',
      urgency: initialLead.raw_metadata?.urgency || 'MEDIA',
      budget_range: initialLead.raw_metadata?.budget_range || '',
      work_modality: initialLead.raw_metadata?.work_modality || 'Híbrido',
      tags: initialLead.raw_metadata?.tags || '',
    });
  }, [initialLead]);

  // Lo que convierte este `<div>` flotante en una ventana para el teclado y para un lector
  // de pantalla: nombre, atrapado del foco, `Escape` y devolución del foco al cerrar
  // (capítulo 36). Va aquí arriba, con los demás hooks, por lo que dice el comentario de
  // abajo: el número de hooks no puede depender del prop.
  const ventana = useVentanaModal({ alCerrar: onClose, etiquetadoPor: 'ficha-360-titulo' });

  // Después de TODOS los hooks: así el número de hooks no depende del prop.
  if (!initialLead) return null;

  const exp = lead.latest_explanation || {};
  const scoreColor =
    lead.score_category === 'HOT'
      ? 'var(--hot-text)'
      : lead.score_category === 'WARM'
      ? 'var(--warm-text)'
      : 'var(--cold-text)';

  const handleEditChange = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  // Qué hacer con un campo que la ficha NO admite vacío cuando el usuario lo deja en blanco.
  //
  // Antes se omitía siempre que estuviera vacío, y eso tapaba dos casos muy distintos con la
  // misma solución. El que había que tapar es real: las fichas de la página de interés
  // guardan el nombre entero y los apellidos en blanco, así que mandar `""` haría que la
  // edición de cualquier otro campo de esas fichas respondiera 422 y no se pudieran tocar.
  // El que no hay que tapar es el asesor que **borra a propósito** un apellido que estaba
  // escrito: omitirlo hacía que la pantalla dijera «Prospecto actualizado» y el apellido
  // siguiera ahí al reabrir la ficha, que es la mentira que el capítulo 33 vino a quitar.
  //
  // Se distinguen mirando lo que la ficha tenía: si había contenido y ahora no, el vacío
  // viaja y el servidor contesta 422 nombrando el campo.
  const obligatorio = (valor, original) =>
    (valor || '').trim() || (original || '').trim() ? valor : undefined;

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveSuccessMsg('');
    try {
      const payload = {
        first_name: obligatorio(editForm.first_name, datos.first_name),
        last_name: obligatorio(editForm.last_name, datos.last_name),
        email: editForm.email,
        phone: editForm.phone,
        country: editForm.country || null,
        city: editForm.city,
        company: editForm.company,
        job_title: editForm.job_title,
        industry: editForm.industry,
        company_size: editForm.company_size || null,
        annual_revenue: ingresosDelFormulario(editForm.annual_revenue),
        // La etapa solo viaja si no es de cierre. Un prospecto ya ganado o perdido se
        // edita sin tocarla: el servidor responderia 422 —cerrar exige motivo, fecha y
        // tramo— y el asesor no podria corregirle el telefono a un cliente ganado.
        ...(esEtapaDeCierre(editForm.status) ? {} : { status: editForm.status }),
        source: editForm.source,
        raw_metadata: {
          ...(lead.raw_metadata || {}),
          profiles_needed: editForm.profiles_needed,
          urgency: editForm.urgency,
          budget_range: editForm.budget_range,
          work_modality: editForm.work_modality,
          tags: editForm.tags,
        },
      };

      const updated = await updateLead(lead.id, payload);
      setLead(updated);
      setSaveSuccessMsg('Prospecto actualizado y rescoreado dinámicamente.');
      setIsEditing(false);
      if (onLeadUpdated) onLeadUpdated();
      setTimeout(() => setSaveSuccessMsg(''), 4000);
    } catch (err) {
      alert('Error al actualizar prospecto: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // Una casilla elegida se distingue por el borde y el sombreado, y además lo dice
  // `aria-checked`: el color solo no basta para quien no lo ve.
  const estiloDeCasilla = (elegida) => ({
    textAlign: 'left',
    padding: '8px 10px',
    borderRadius: 'var(--radius-sm)',
    border: `1px solid ${elegida ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
    boxShadow: elegida ? '0 0 0 1px var(--accent-primary)' : 'none',
    background: elegida ? 'var(--bg-surface)' : 'var(--bg-surface-elevated)',
    color: 'var(--text-primary)',
    fontSize: '0.8rem',
    cursor: 'pointer',
  });

  const esLlamada = newActivityType === 'PHONE_CALL';
  const esMensaje = TIPOS_DE_MENSAJE.includes(newActivityType);

  const handleAddActivity = async (e) => {
    e.preventDefault();
    setErrorDeActividad('');
    setCambioDeScore(null);
    setIsSubmittingAct(true);
    try {
      const actividad = { activity_type: newActivityType };
      if (esLlamada) actividad.call_outcome = callOutcome;
      if (esMensaje) actividad.direction = direction;
      if (!esMensaje && activityNotes.trim()) actividad.notes = activityNotes.trim();
      const registrada = await addLeadActivity(lead.id, actividad);
      setCambioDeScore(describirCambioDeScore(registrada));
      setActivityNotes('');
      setCallOutcome('');
      if (onLeadUpdated) onLeadUpdated();
    } catch (err) {
      setErrorDeActividad(err.message);
    } finally {
      setIsSubmittingAct(false);
    }
  };

  const handleRecalculate = async () => {
    setIsRecalculating(true);
    try {
      await recalculateLeadScore(lead.id);
      if (onLeadUpdated) onLeadUpdated();
    } catch (err) {
      alert('Error al recalcular: ' + err.message);
    } finally {
      setIsRecalculating(false);
    }
  };

  // El velo cierra al pulsarlo, y eso ya no necesita dos manejadores.
  //
  // Antes había uno aquí y otro dentro que solo hacía `stopPropagation`, para que un clic en
  // la ventana no la cerrara. Lo mismo se consigue mirando DÓNDE se pulsó: si el objetivo es
  // el velo y no algo de dentro, se cierra. Un manejador menos, y el de dentro desaparece:
  // era un `onClick` sobre contenido que no es pulsable, que es lo que `jsx-a11y` señala con
  // razón desde que este capítulo encendió el conjunto entero.
  //
  // `role="presentation"`: el velo no es un control ni tiene contenido propio, es un cristal
  // ahumado. Quien usa el teclado lo cierra con `Escape` —ver `ventanaModal.js`—, que es el
  // equivalente correcto y no un `onKeyDown` colgado de un `<div>`.
  return (
    <div className="modal-overlay" role="presentation"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div
        {...ventana}
        className="modal-content"
        style={{ padding: '28px 32px', maxWidth: '820px' }}
      >
        {/* Header with Title & Action Controls */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            borderBottom: '1px solid var(--border-subtle)',
            paddingBottom: '18px',
            marginBottom: '20px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <h2 id="ficha-360-titulo" style={{ fontSize: '1.4rem', fontWeight: '700', letterSpacing: '-0.02em' }}>
                {lead.first_name} {lead.last_name}
              </h2>
              <span className={`badge ${lead.score_category === 'HOT' ? 'badge-hot' : (lead.score_category === 'WARM' ? 'badge-warm' : 'badge-cold')}`}>
                {lead.score_category}
              </span>
              <span className="badge badge-status">{nombreDeEtapa(lead.status)}</span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              {/* Desde el capítulo 33 estos dos campos se pueden vaciar, así que la cabecera
                  tiene que saber enseñarlos vacíos. Sin los rótulos quedaba « • (General)»,
                  que parece la ficha rota y no una ficha sin esos datos. */}
              {lead.job_title || 'Sin cargo'} •{' '}
              <strong style={{ color: 'var(--text-primary)' }}>{lead.company || 'Sin empresa'}</strong>{' '}
              ({lead.industry || 'General'})
            </p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.775rem', marginTop: '2px' }}>
              {/* «Sin registrar» y no «México»: la cabecera era el último sitio donde la
                  suposición seguía leyéndose como dato, y el único que mira una persona. */}
              ✉️ {lead.email} | 📞 {lead.phone || 'Sin registrar'} | 📍 {[lead.city, lead.country].filter(Boolean).join(', ') || 'Sin registrar'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              id="btn-edit-lead-toggle"
              type="button"
              className={isEditing ? 'btn btn-secondary btn-sm' : 'btn btn-primary btn-sm'}
              onClick={() => {
                setIsEditing(!isEditing);
                setSaveSuccessMsg('');
              }}
            >
              {isEditing ? '✕ Cancelar Edición' : '✏️ Editar Prospecto'}
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '1.25rem',
                cursor: 'pointer',
                lineHeight: 1,
                padding: '4px 6px',
              }}
              title="Cerrar modal"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Feedback Alert if updated */}
        {/* `role="status"`: sin él, «Prospecto actualizado» aparecía en pantalla y no lo
            anunciaba nadie. Es justo el mensaje que el capítulo 33 se encargó de que no
            mintiera —antes decía que había guardado un vaciado que no guardaba—, así que
            que no llegue a quien no ve la pantalla deja ese trabajo a medias. */}
        {saveSuccessMsg && (
          <div
            role="status"
            style={{
              padding: '10px 14px',
              background: 'var(--success-bg)',
              border: '1px solid var(--success-border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--success-text)',
              fontSize: '0.825rem',
              fontWeight: '600',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>✓</span> {saveSuccessMsg}
          </div>
        )}

        {/* ========================================================================= */}
        {/* EDIT MODE FORM                                                            */}
        {/* ========================================================================= */}
        {isEditing ? (
          <form onSubmit={handleSaveEdit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '24px' }}>
              
              {/* Sección: Contacto */}
              <div className="glass-panel" style={{ padding: '18px' }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  👤 Información de Contacto
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label htmlFor="lead-first-name" className="form-label">Nombre(s) *</label>
                    <input
                      id="lead-first-name"
                      type="text"
                      required
                      className="input-field"
                      value={editForm.first_name}
                      onChange={(e) => handleEditChange('first_name', e.target.value)}
                    />
                  </div>
                  <div>
                    {/* Sin asterisco: la página de interés guarda el nombre entero en un solo
                        campo, y exigir apellidos impedía guardar cualquier cambio en esa ficha. */}
                    <label htmlFor="lead-last-name" className="form-label">Apellidos</label>
                    <input
                      id="lead-last-name"
                      type="text"
                      className="input-field"
                      value={editForm.last_name}
                      onChange={(e) => handleEditChange('last_name', e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-email" className="form-label">Correo Corporativo *</label>
                    <input
                      id="lead-email"
                      type="email"
                      required
                      className="input-field"
                      value={editForm.email}
                      onChange={(e) => handleEditChange('email', e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-phone" className="form-label">Teléfono / WhatsApp</label>
                    <input
                      id="lead-phone"
                      type="text"
                      className="input-field"
                      value={editForm.phone}
                      onChange={(e) => handleEditChange('phone', e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-country" className="form-label">País</label>
                    <input
                      id="lead-country"
                      type="text"
                      className="input-field"
                      value={editForm.country}
                      onChange={(e) => handleEditChange('country', e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-city" className="form-label">Ciudad</label>
                    <input
                      id="lead-city"
                      type="text"
                      className="input-field"
                      value={editForm.city}
                      onChange={(e) => handleEditChange('city', e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Sección: Empresa y Cargo */}
              <div className="glass-panel" style={{ padding: '18px' }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  🏢 Empresa, Cargo y Sector
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  {/* Sin `required` ni asterisco desde el capítulo 33, y no es un descuido.
                      La tabla declara las dos columnas `nullable`, así que el servidor
                      acepta retirarlas; mientras el formulario las exigiera, el panel era
                      MÁS estricto que la API sin decirlo, y la corrección de una empresa
                      mal tecleada no tenía dónde hacerse. El alta sí las sigue pidiendo:
                      preguntar por un dato al capturarlo y poder retirarlo después cuando
                      se comprueba que era falso son dos decisiones distintas.

                      Los que llevan asterisco —nombre y correo— lo llevan porque la tabla
                      los declara `NOT NULL`, no por costumbre del formulario. */}
                  <div>
                    <label htmlFor="lead-company" className="form-label">Empresa</label>
                    <input
                      id="lead-company"
                      type="text"
                      className="input-field"
                      value={editForm.company}
                      onChange={(e) => handleEditChange('company', e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-job-title" className="form-label">Cargo / Puesto de Decisión</label>
                    <input
                      id="lead-job-title"
                      type="text"
                      className="input-field"
                      value={editForm.job_title}
                      onChange={(e) => handleEditChange('job_title', e.target.value)}
                      placeholder="Ej. CTO, Director de Talento, Psicólogo..."
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-industry" className="form-label">Industria / Sector (Abierto) ✏️</label>
                    <input
                      id="lead-industry"
                      list="edit-industry-list"
                      className="input-field"
                      value={editForm.industry}
                      onChange={(e) => handleEditChange('industry', e.target.value)}
                      placeholder="Selecciona o escribe sector libre..."
                    />
                    <datalist id="edit-industry-list">
                      <option value="FinTech" />
                      <option value="Software/TI" />
                      <option value="Banca y Finanzas" />
                      <option value="Educación / Universidades" />
                      <option value="Salud / HealthTech" />
                      <option value="Logistics" />
                      <option value="Manufactura" />
                      <option value="Retail / E-Commerce" />
                      <option value="Recursos Humanos / Headhunting" />
                      <option value="Consultoría Empresarial" />
                    </datalist>
                  </div>
                  <div>
                    <label htmlFor="lead-company-size" className="form-label">Tamaño de Empresa</label>
                    <select
                      id="lead-company-size"
                      className="input-field"
                      value={editForm.company_size}
                      onChange={(e) => handleEditChange('company_size', e.target.value)}
                    >
                      <option value="">Sin indicar</option>
                      <option value="1-10">1-10 colaboradores (Startup temprana)</option>
                      <option value="11-50">11-50 colaboradores (Pequeña)</option>
                      <option value="51-200">51-200 colaboradores (Mediana)</option>
                      <option value="201-1000">201-1000 colaboradores (Corporativo mediano)</option>
                      <option value="1000+">1000+ colaboradores (Enterprise corporativo)</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="lead-status" className="form-label">Estado del Prospecto en Pipeline</label>
                    <select
                      id="lead-status"
                      className="input-field"
                      value={editForm.status}
                      onChange={(e) => handleEditChange('status', e.target.value)}
                    >
                      {/* Todas las etapas menos las de cierre: si faltara la del prospecto
                          —«En conversación» y «No calificado» no estaban—, el selector
                          enseñaría otra y guardar la cambiaría sin que nadie lo pidiera.
                          «Ganado» y «Perdido» salieron de aquí en el capítulo 30: cerrar
                          exige un motivo, y el botón de abajo es el único camino. */}
                      {ETAPAS_EDITABLES.map((etapa) => (
                        <option key={etapa} value={etapa}>{NOMBRES_DE_ETAPA[etapa]}</option>
                      ))}
                      {/* La del prospecto, si ya está cerrado: deshabilitada, para que el
                          selector no enseñe una etapa que no es la suya. */}
                      {esEtapaDeCierre(editForm.status) && (
                        <option value={editForm.status} disabled>
                          {NOMBRES_DE_ETAPA[editForm.status]} (cerrado)
                        </option>
                      )}
                    </select>
                    <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Pasar a «Propuesta enviada» o «Reunión agendada» deja la actividad registrada en el historial.
                      Para darlo por ganado o perdido, use «Cerrar el prospecto»: hace falta el motivo.
                    </p>
                  </div>
                  <div>
                    <label htmlFor="lead-annual-revenue" className="form-label">Ingresos Anuales Estimados (USD)</label>
                    <input
                      id="lead-annual-revenue"
                      type="number"
                      className="input-field"
                      value={editForm.annual_revenue}
                      onChange={(e) => handleEditChange('annual_revenue', e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Sección: Atributos Personalizados / Metadata */}
              <div className="glass-panel" style={{ padding: '18px' }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)', marginBottom: '14px' }}>
                  ⚙️ Requerimientos Específicos y Metadatos Dinámicos
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div style={{ gridColumn: 'span 2' }}>
                    <label htmlFor="lead-requested-profiles" className="form-label">Perfiles o Solicitud Específica</label>
                    <input
                      id="lead-requested-profiles"
                      type="text"
                      className="input-field"
                      value={editForm.profiles_needed}
                      onChange={(e) => handleEditChange('profiles_needed', e.target.value)}
                      placeholder="Ej. 2 Psicólogos Organizacionales, 3 Devs Fullstack, Consultor de Procesos..."
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-urgency" className="form-label">Nivel de Urgencia Comercial</label>
                    <select
                      id="lead-urgency"
                      className="input-field"
                      value={editForm.urgency}
                      onChange={(e) => handleEditChange('urgency', e.target.value)}
                    >
                      <option value="INMEDIATA">🚨 INMEDIATA (Cierre en &lt; 7 días)</option>
                      <option value="ALTA">🔥 ALTA (Cierre en el mes en curso)</option>
                      <option value="MEDIA">⚡ MEDIA (En exploración trimestral)</option>
                      <option value="BAJA">❄️ BAJA (Planificación a largo plazo)</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="lead-budget-range" className="form-label">Rango de Presupuesto Estimado</label>
                    <input
                      id="lead-budget-range"
                      type="text"
                      className="input-field"
                      value={editForm.budget_range}
                      onChange={(e) => handleEditChange('budget_range', e.target.value)}
                      placeholder="Ej. $15,000 - $30,000 USD"
                    />
                  </div>
                  <div>
                    <label htmlFor="lead-work-mode" className="form-label">Modalidad de Trabajo</label>
                    <select
                      id="lead-work-mode"
                      className="input-field"
                      value={editForm.work_modality}
                      onChange={(e) => handleEditChange('work_modality', e.target.value)}
                    >
                      <option value="Remoto">Remoto (100% WFH)</option>
                      <option value="Híbrido">Híbrido (2-3 días oficina)</option>
                      <option value="Presencial">Presencial (En sede corporativa)</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="lead-tags" className="form-label">Etiquetas / Tags de Segmentación</label>
                    <input
                      id="lead-tags"
                      type="text"
                      className="input-field"
                      value={editForm.tags}
                      onChange={(e) => handleEditChange('tags', e.target.value)}
                      placeholder="Ej. Lead Cualificado, Interés HR, Prioridad 1"
                    />
                  </div>
                </div>
              </div>

            </div>

            {/* Edit Form Buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setIsEditing(false)}
                disabled={isSaving}
              >
                Cancelar
              </button>
              <button
                id="btn-save-lead-edits"
                type="submit"
                className="btn btn-primary"
                disabled={isSaving}
              >
                {isSaving ? 'Guardando y Recalculando...' : '💾 Guardar y Recalcular Score'}
              </button>
            </div>
          </form>
        ) : (
          /* ========================================================================= */
          /* VIEW MODE                                                                 */
          /* ========================================================================= */
          <>
            {/* Upper Overview Grid: Attributes & Score Gauge */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', gap: '16px' }}>
              
              {/* Badges de Atributos Personalizados */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                  Atributos y Requerimientos de la Oportunidad:
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {lead.raw_metadata?.profiles_needed ? (
                    <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.04)', color: 'var(--text-primary)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      💼 Requerimiento: <strong style={{ color: '#ffffff' }}>{lead.raw_metadata.profiles_needed}</strong>
                    </span>
                  ) : (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sin perfiles específicos configurados.</span>
                  )}
                  {lead.raw_metadata?.urgency && (
                    <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      ⏱️ Urgencia: {lead.raw_metadata.urgency}
                    </span>
                  )}
                  {lead.raw_metadata?.budget_range && (
                    <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      💵 Presupuesto: {lead.raw_metadata.budget_range}
                    </span>
                  )}
                  {lead.raw_metadata?.work_modality && (
                    <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      🏢 {lead.raw_metadata.work_modality}
                    </span>
                  )}
                  {lead.raw_metadata?.tags && (
                    <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      🏷️ {lead.raw_metadata.tags}
                    </span>
                  )}
                </div>
              </div>

              {/* Minimalist Executive Score Card */}
              <div
                style={{
                  minWidth: '150px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  background: 'var(--bg-surface)',
                  padding: '12px 18px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-medium)',
                }}
              >
                <span style={{ fontSize: '0.675rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>
                  Score Inteligente
                </span>
                <div style={{ fontSize: '2.2rem', fontWeight: '800', fontFamily: 'var(--font-mono)', color: scoreColor, lineHeight: 1.1, margin: '4px 0' }}>
                  {lead.current_score}
                </div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                  Prob. ML: <strong>{Math.round(lead.conversion_probability * 100)}%</strong>
                </span>
              </div>
            </div>

            {/* De qué publicación llegó. Va antes del diagnóstico porque es lo primero
                que pregunta quien va a llamar: de dónde salió esta persona y qué pidió. */}
            {/* Quién la atiende. Las fichas de LinkedIn llegan sin asesor: sin esto,
                repartirlas obligaba a llamar a la API a mano. */}
            <AsignarAsesor lead={lead} onAsignado={onLeadUpdated} />

            <LlegoPor llegoPor={lead.llego_por} />

            {/* Como acabo, si acabo (capitulo 30). La tarjeta solo se pinta cuando hay
                desenlace registrado: un cierre anterior a este capitulo no tiene motivo, y
                una tarjeta vacia sugeriria un dato perdido en lugar de uno que nunca hubo. */}
            {lead.desenlace && (
              <div
                className="glass-panel"
                style={{ padding: '16px', marginBottom: '20px', border: '1px solid var(--border-medium)' }}
              >
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700', marginBottom: '6px' }}>
                  🏁 {lead.desenlace.resultado_etiqueta} · {lead.desenlace.motivo_etiqueta}
                </h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
                  Cerrado el {new Date(`${lead.desenlace.cerrado_el}T00:00:00`).toLocaleDateString('es-MX')}
                  {lead.desenlace.tramo_etiqueta ? ` · ${lead.desenlace.tramo_etiqueta}` : ''}
                </p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                  Tenía {Math.round(lead.desenlace.score_al_cierre)} puntos
                  ({lead.desenlace.categoria_al_cierre}) al cerrarse. Ese es el número que el
                  panel usa para saber si el score acertaba; no se recalcula.
                </p>
              </div>
            )}

            {/* Cerrar, o corregir un cierre. El asesor que atiende al prospecto es quien
                sabe por que acabo asi, de modo que es quien lo cierra. */}
            {cerrando ? (
              <div style={{ marginBottom: '20px' }}>
                <CerrarProspecto
                  lead={lead}
                  onCancelar={() => setCerrando(false)}
                  onCerrado={(registrado) => {
                    setCerrando(false);
                    setSaveSuccessMsg(
                      `Prospecto ${registrado.resultado_etiqueta.toLowerCase()} por «${registrado.motivo_etiqueta}».`
                      + (registrado.tareas_descartadas
                        ? ` Se descartaron ${registrado.tareas_descartadas} tarea(s) pendiente(s).`
                        : ''),
                    );
                    // La verdad de como quedo la ficha la tiene el servidor: se recarga en
                    // vez de remendar el objeto local, que es como el score y la etapa
                    // acaban diciendo cosas distintas en dos sitios de la misma pantalla.
                    if (onLeadUpdated) onLeadUpdated();
                  }}
                />
              </div>
            ) : (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ marginBottom: '20px' }}
                onClick={() => setCerrando(true)}
              >
                {lead.desenlace ? '🏁 Corregir el desenlace' : '🏁 Cerrar el prospecto'}
              </button>
            )}

            {/* AI Explanation & Recommendations (XAI) */}
            <div
              className="glass-panel"
              style={{
                padding: '20px',
                marginBottom: '20px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <span style={{ fontSize: '1.1rem' }}>🤖</span>
                <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Diagnóstico y Explicabilidad con IA (XAI)
                </h3>
                <span className="badge" style={{ marginLeft: 'auto', background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
                  {exp.engine === 'PluriOne_XAI_Engine' ? 'Motor XAI Institucional' : (exp.engine || 'Motor XAI Institucional')}
                </span>
              </div>

              <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginBottom: '12px', lineHeight: '1.5' }}>
                {exp.summary || 'El prospecto fue evaluado combinando atributos de decisión de cargo y comportamiento digital.'}
              </p>

              {exp.strengths && exp.strengths.length > 0 && (
                <div style={{ marginBottom: '14px' }}>
                  <div style={{ fontSize: '0.725rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Diagnóstico de Idoneidad y Fortalezas:
                  </div>
                  <ul style={{ paddingLeft: '18px', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                    {exp.strengths.map((str, idx) => (
                      <li key={idx} style={{ marginBottom: '3px' }}>{str}</li>
                    ))}
                  </ul>
                </div>
              )}

              {exp.recommended_action && (
                <div
                  style={{
                    background: 'var(--bg-surface-elevated)',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ fontSize: '0.725rem', fontWeight: '700', color: 'var(--text-primary)', textTransform: 'uppercase', marginBottom: '4px', letterSpacing: '0.03em' }}>
                    🎯 Táctica Comercial Recomendada:
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                    {exp.recommended_action}
                  </div>
                </div>
              )}
            </div>

            {/* Interaction Timeline & Quick Logger */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              
              {/* Historial legible: nombre en español, si lo vio un sistema o lo declaró una
                  persona, y de dónde vino. Sin el peso en puntos: nunca fue lo que movía el score. */}
              <div className="glass-panel" style={{ padding: '18px' }}>
                <h4 style={{ fontSize: '0.875rem', fontWeight: '700', marginBottom: '10px' }}>
                  Historial de Eventos ({lead.activities?.length || 0})
                </h4>
                <ul
                  aria-label="Historial de eventos"
                  style={{ maxHeight: '190px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', listStyle: 'none', padding: 0, margin: 0 }}
                >
                  {lead.activities && lead.activities.length > 0 ? (
                    [...lead.activities]
                      .sort((a, b) => new Date(b.occurred_at) - new Date(a.occurred_at))
                      .map((act) => (
                        <li
                          key={act.id}
                          style={{
                            padding: '8px 10px',
                            background: 'var(--bg-surface-elevated)',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-subtle)',
                            fontSize: '0.775rem',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: '600', color: 'var(--text-primary)' }}>
                            <span>{nombreDeActividad(act.activity_type)}</span>
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                              {new Date(act.occurred_at).toLocaleDateString('es-MX')}
                            </span>
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.725rem', marginTop: '3px' }}>
                            <span
                              className="badge"
                              title={act.verificada ? 'La registró un sistema al ocurrir.' : 'La declaró una persona.'}
                              style={{
                                fontSize: '0.65rem',
                                padding: '1px 6px',
                                background: act.verificada ? 'var(--success-bg)' : 'var(--bg-subtle)',
                                color: act.verificada ? 'var(--success-text)' : 'var(--text-secondary)',
                                border: `1px solid ${act.verificada ? 'var(--success-border)' : 'var(--border-subtle)'}`,
                              }}
                            >
                              {act.verificada ? 'verificada' : 'declarada'}
                            </span>
                            <span>{nombreDeFuente(act.source)}</span>
                            {act.call_outcome && <span>• {RESULTADOS_DE_LLAMADA[act.call_outcome] || act.call_outcome}</span>}
                            {act.direction && <span>• {DIRECCIONES[act.direction] || act.direction}</span>}
                            {act.activity_data?.notes && (
                              <span style={{ color: 'var(--text-secondary)' }}>• {act.activity_data.notes}</span>
                            )}
                          </div>
                        </li>
                      ))
                  ) : (
                    <li style={{ color: 'var(--text-muted)', fontSize: '0.775rem' }}>Sin actividades previas registradas.</li>
                  )}
                </ul>
              </div>

              {/* Registrar una interacción */}
              <div className="glass-panel" style={{ padding: '18px' }}>
                <h4 style={{ fontSize: '0.875rem', fontWeight: '700', marginBottom: '10px' }}>
                  Registrar Interacción Comercial
                </h4>
                <form onSubmit={handleAddActivity}>
                  {/* Cuadrícula en lugar de desplegable: las opciones se ven todas a la vez y
                      se eligen con un clic. Solo las conversaciones del asesor; lo demás lo
                      registra quien lo ve ocurrir. */}
                  <div
                    role="radiogroup"
                    aria-label="Tipo de interacción"
                    style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', marginBottom: '6px' }}
                  >
                    {TIPOS_DECLARABLES.map((tipo) => (
                      <button
                        key={tipo}
                        type="button"
                        role="radio"
                        aria-checked={newActivityType === tipo}
                        onClick={() => {
                          setNewActivityType(tipo);
                          setErrorDeActividad('');
                        }}
                        style={estiloDeCasilla(newActivityType === tipo)}
                      >
                        <span style={{ display: 'block', fontWeight: '600' }}>{nombreDeActividad(tipo)}</span>
                        <span style={{ display: 'block', fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          {AYUDA_DE_TIPO[tipo]}
                        </span>
                      </button>
                    ))}
                  </div>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
                    La propuesta y la reunión se registran al cambiar la etapa; formularios, demos y webinars, desde su integración.
                  </p>

                  {esLlamada && (
                    <div style={{ marginBottom: '8px' }}>
                      <div
                        role="radiogroup"
                        aria-label="Resultado de la llamada"
                        style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}
                      >
                        {Object.entries(RESULTADOS_DE_LLAMADA).map(([valor, nombre]) => (
                          <button
                            key={valor}
                            type="button"
                            role="radio"
                            aria-checked={callOutcome === valor}
                            onClick={() => setCallOutcome(valor)}
                            style={{ ...estiloDeCasilla(callOutcome === valor), textAlign: 'center' }}
                          >
                            {nombre}
                          </button>
                        ))}
                      </div>
                      <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Solo la llamada que conectó cuenta como conversación.
                      </p>
                    </div>
                  )}

                  {esMensaje && (
                    <div style={{ marginBottom: '8px' }}>
                      <div
                        role="radiogroup"
                        aria-label="Dirección del mensaje"
                        style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px' }}
                      >
                        {Object.entries(DIRECCIONES).map(([valor, nombre]) => (
                          <button
                            key={valor}
                            type="button"
                            role="radio"
                            aria-checked={direction === valor}
                            onClick={() => setDirection(valor)}
                            style={{ ...estiloDeCasilla(direction === valor), textAlign: 'center' }}
                          >
                            {nombre}
                          </button>
                        ))}
                      </div>
                      <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                        Del mensaje se guarda el tipo, la dirección y la fecha; nunca su texto.
                      </p>
                    </div>
                  )}

                  {!esMensaje && (
                    <div style={{ marginBottom: '8px' }}>
                      <label htmlFor="lead-event-notes" style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Notas:</label>
                      <input
                        id="lead-event-notes"
                        type="text"
                        className="input-field"
                        maxLength={500}
                        placeholder="Ej. Se acordó llamada técnica"
                        value={activityNotes}
                        onChange={(e) => setActivityNotes(e.target.value)}
                        style={{ marginTop: '2px' }}
                      />
                    </div>
                  )}

                  {cambioDeScore && (
                    <div
                      role="status"
                      style={{
                        padding: '8px 10px',
                        marginBottom: '8px',
                        background: 'var(--success-bg)',
                        border: '1px solid var(--success-border)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--success-text)',
                        fontSize: '0.8rem',
                      }}
                    >
                      Score: <strong style={{ fontFamily: 'var(--font-mono)' }}>{cambioDeScore}</strong>
                    </div>
                  )}
                  {errorDeActividad && (
                    <div
                      role="alert"
                      style={{
                        padding: '8px 10px',
                        marginBottom: '8px',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--hot-text)',
                        fontSize: '0.8rem',
                      }}
                    >
                      {errorDeActividad}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button type="submit" disabled={isSubmittingAct || (esLlamada && !callOutcome)} className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                      {isSubmittingAct ? 'Registrando...' : '➕ Registrar y Recalcular'}
                    </button>
                    <button
                      type="button"
                      onClick={handleRecalculate}
                      disabled={isRecalculating}
                      className="btn btn-secondary btn-sm"
                      title="Aplica decaimiento temporal sobre días de inactividad"
                    >
                      {isRecalculating ? '⏳' : '🔄 Decaimiento'}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
              <button onClick={onClose} className="btn btn-secondary">
                Cerrar Ficha
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
