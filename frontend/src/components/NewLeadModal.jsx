import React, { useState } from 'react';
import { createLead } from '../services/api';
import { useVentanaModal } from './ventanaModal';

export default function NewLeadModal({ onClose, onLeadCreated }) {
  // Nombre, atrapado del foco, `Escape` y devolución del foco al cerrar (capítulo 36).
  const ventana = useVentanaModal({ alCerrar: onClose, etiquetadoPor: 'alta-de-prospecto-titulo' });
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    company: '',
    job_title: '',
    industry: 'FinTech',
    company_size: '51-200',
    source: 'LinkedIn Ads',
    initial_activity_type: 'DEMO_REQUEST',
    initial_notes: 'Alta directa desde la plataforma comercial',
    // Custom Fields
    profiles_needed: '',
    urgency: 'INMEDIATA',
    budget_range: '',
    work_modality: 'Remoto 100%',
    tags: '',
    // Si la persona aceptó el aviso de privacidad. Nace SIN marcar, y es lo único que
    // puede nacer: marcada por omisión guardaría una aceptación que nadie dio, y la fecha
    // que se anota junto a ella la volvería indistinguible de las de verdad.
    privacy_notice_accepted: false,
  });

  const [showCustomFields, setShowCustomFields] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const customMetadata = {};
      if (formData.profiles_needed) customMetadata.profiles_needed = formData.profiles_needed;
      if (formData.urgency) customMetadata.urgency = formData.urgency;
      if (formData.budget_range) customMetadata.budget_range = formData.budget_range;
      if (formData.work_modality) customMetadata.work_modality = formData.work_modality;
      if (formData.tags) customMetadata.tags = formData.tags;

      await createLead({
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email,
        phone: formData.phone,
        company: formData.company,
        job_title: formData.job_title,
        industry: formData.industry,
        company_size: formData.company_size,
        // El alta no pregunta los ingresos. Antes enviaba 2 000 000 fijos, y cada prospecto
        // creado desde el panel llegaba al modelo con una facturación inventada.
        annual_revenue: null,
        source: formData.source,
        initial_activity_type: formData.initial_activity_type,
        initial_notes: formData.initial_notes,
        raw_metadata: customMetadata,
        // La casilla, tal cual. El servidor anota la fecha y la fuente «manual» solo si
        // viene `true`; si viene `false`, los dos campos se quedan vacíos y no se supone
        // nada, que es lo mismo que hace la página de interés con quien no la marca.
        privacy_notice_accepted: formData.privacy_notice_accepted,
      });
      onLeadCreated();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field, val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
  };

  // Velo con `role="presentation"` y cierre según dónde se pulsó; `Escape` para el teclado.
  // El detalle está explicado en LeadDetailModal.jsx.
  return (
    <div className="modal-overlay" role="presentation"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div {...ventana} className="modal-content" style={{ padding: '28px', maxWidth: '680px', maxHeight: '90vh', overflowY: 'auto' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '14px' }}>
          <div>
            <h2 id="alta-de-prospecto-titulo" style={{ fontSize: '1.25rem', fontWeight: '800' }}>Registrar Nuevo Prospecto</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              El sistema ejecutará el modelo predictivo e inferencia con IA adaptativa de inmediato.
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar el alta de prospecto"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>
            <span aria-hidden="true">×</span>
          </button>
        </div>

        {/* `role="alert"`, como en el resto de los formularios del panel. */}
        {error && (
          <div role="alert" style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid var(--hot-border)', padding: '10px 14px', borderRadius: '8px', color: 'var(--hot-text)', fontSize: '0.85rem', marginBottom: '16px' }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Nombre y Apellido */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label htmlFor="new-lead-first-name" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Nombre *</label>
              <input
                id="new-lead-first-name"
                type="text"
                required
                className="input-field"
                placeholder="Nombre"
                value={formData.first_name}
                onChange={(e) => handleChange('first_name', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
            <div>
              <label htmlFor="new-lead-last-name" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Apellido *</label>
              <input
                id="new-lead-last-name"
                type="text"
                required
                className="input-field"
                placeholder="Apellido"
                value={formData.last_name}
                onChange={(e) => handleChange('last_name', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
          </div>

          {/* Email y Teléfono */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label htmlFor="new-lead-email" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Correo Electrónico *</label>
              <input
                id="new-lead-email"
                type="email"
                required
                className="input-field"
                placeholder="contacto@empresa.com"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
            <div>
              <label htmlFor="new-lead-phone" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Teléfono</label>
              <input
                id="new-lead-phone"
                type="text"
                className="input-field"
                placeholder="+52 55 1234 5678"
                value={formData.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
          </div>

          {/* Empresa y Cargo */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label htmlFor="new-lead-company" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Empresa / Institución</label>
              <input
                id="new-lead-company"
                type="text"
                className="input-field"
                placeholder="Ej. TESCI, Banco Azteca, Startup"
                value={formData.company}
                onChange={(e) => handleChange('company', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
            <div>
              <label htmlFor="new-lead-job-title" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Cargo / Rol</label>
              <input
                id="new-lead-job-title"
                type="text"
                className="input-field"
                placeholder="Ej. CTO, Gerente de Talento, Psicólogo"
                value={formData.job_title}
                onChange={(e) => handleChange('job_title', e.target.value)}
                style={{ marginTop: '4px' }}
              />
            </div>
          </div>

          {/* Industria Abierta y Canal */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label htmlFor="new-lead-industry" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                Industria / Sector (Entrada Libre) ✏️
              </label>
              <input
                id="new-lead-industry"
                list="industries-list"
                className="input-field"
                placeholder="Selecciona o escribe cualquier industria..."
                value={formData.industry}
                onChange={(e) => handleChange('industry', e.target.value)}
                style={{ marginTop: '4px' }}
              />
              <datalist id="industries-list">
                <option value="FinTech" />
                <option value="Software/TI" />
                <option value="Banking / Banca" />
                <option value="Educación / Universidades" />
                <option value="Salud / HealthTech" />
                <option value="Logistics & Transporte" />
                <option value="Retail & E-Commerce" />
                <option value="Manufactura & Automotriz" />
                <option value="Gobierno & Sector Público" />
                <option value="Telecomunicaciones" />
                <option value="Consultoría Profesional" />
              </datalist>
            </div>
            <div>
              <label htmlFor="new-lead-source-channel" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Canal de Captación</label>
              <select
                id="new-lead-source-channel"
                className="input-field"
                value={formData.source}
                onChange={(e) => handleChange('source', e.target.value)}
                style={{ marginTop: '4px' }}
              >
                <option value="LinkedIn Ads">LinkedIn Ads</option>
                <option value="Formulario Demo">Formulario Demo</option>
                <option value="WhatsApp Business">WhatsApp Business</option>
                <option value="Llamada Directa">Llamada Directa</option>
                <option value="Recomendación / Referral">Recomendación / Referral</option>
                <option value="Webinar">Webinar</option>
                <option value="Búsqueda Orgánica">Búsqueda Orgánica</option>
              </select>
            </div>
          </div>

          {/* Evento Inicial y Tamaño */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            <div>
              <label htmlFor="new-lead-initial-event" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Evento Inicial Registrado</label>
              <select
                id="new-lead-initial-event"
                className="input-field"
                value={formData.initial_activity_type}
                onChange={(e) => handleChange('initial_activity_type', e.target.value)}
                style={{ marginTop: '4px' }}
              >
                {/* Cómo llegó la persona. La propuesta y la reunión no están: se registran al
                    cambiar la etapa. La llamada y el mensaje tampoco: necesitan su resultado o
                    su dirección, y se registran desde la ficha. */}
                <option value="DEMO_REQUEST">Solicitud de demo</option>
                <option value="FORM_SUBMIT">Formulario enviado</option>
                <option value="WEBINAR_ATTEND">Asistencia a webinar</option>
                <option value="CONTENT_DOWNLOAD">Descarga de contenido</option>
              </select>
            </div>
            <div>
              <label htmlFor="new-lead-company-size" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Tamaño de Empresa</label>
              <select
                id="new-lead-company-size"
                className="input-field"
                value={formData.company_size}
                onChange={(e) => handleChange('company_size', e.target.value)}
                style={{ marginTop: '4px' }}
              >
                <option value="1-10">1 a 10 empleados</option>
                <option value="11-50">11 a 50 empleados</option>
                <option value="51-200">51 a 200 empleados</option>
                <option value="201-1000">201 a 1000 empleados</option>
                <option value="1000+">Más de 1000 empleados</option>
              </select>
            </div>
          </div>

          {/* Botón para desplegar Campos Personalizados */}
          <div style={{ marginBottom: '16px' }}>
            <button
              type="button"
              onClick={() => setShowCustomFields(!showCustomFields)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-primary)',
                fontSize: '0.8rem',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: 0
              }}
            >
              <span>{showCustomFields ? '▼ Ocultar' : '▶ Configurar'}</span>
              <span>Requerimientos y Campos Personalizados (Opcional)</span>
            </button>
          </div>

          {/* Sección de Campos Personalizados */}
          {showCustomFields && (
            <div style={{
              background: 'var(--bg-base)',
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-medium)',
              marginBottom: '16px'
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '12px' }}>
                Atributos Dinámicos de la Oportunidad
              </div>

              <div style={{ marginBottom: '10px' }}>
                <label htmlFor="new-lead-requested-profiles" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Perfiles TI Requeridos:</label>
                <input
                  id="new-lead-requested-profiles"
                  type="text"
                  className="input-field"
                  placeholder="Ej. 2 Desarrolladores Python / AWS, 1 DevOps"
                  value={formData.profiles_needed}
                  onChange={(e) => handleChange('profiles_needed', e.target.value)}
                  style={{ marginTop: '4px' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '10px' }}>
                <div>
                  <label htmlFor="new-lead-urgency" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Nivel de Urgencia:</label>
                  <select
                    id="new-lead-urgency"
                    className="input-field"
                    value={formData.urgency}
                    onChange={(e) => handleChange('urgency', e.target.value)}
                    style={{ marginTop: '4px' }}
                  >
                    <option value="INMEDIATA">Inmediata (&lt; 15 días)</option>
                    <option value="MEDIA">1 a 3 meses</option>
                    <option value="EXPLORATORIA">Exploratoria / Sondeo</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="new-lead-work-mode" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Modalidad de Trabajo:</label>
                  <select
                    id="new-lead-work-mode"
                    className="input-field"
                    value={formData.work_modality}
                    onChange={(e) => handleChange('work_modality', e.target.value)}
                    style={{ marginTop: '4px' }}
                  >
                    <option value="Remoto 100%">Remoto 100%</option>
                    <option value="Híbrido">Híbrido</option>
                    <option value="Presencial">Presencial</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label htmlFor="new-lead-budget-range" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Presupuesto Estimado:</label>
                  <input
                    id="new-lead-budget-range"
                    type="text"
                    className="input-field"
                    placeholder="Ej. $40,000 USD / $800,000 MXN"
                    value={formData.budget_range}
                    onChange={(e) => handleChange('budget_range', e.target.value)}
                    style={{ marginTop: '4px' }}
                  />
                </div>
                <div>
                  <label htmlFor="new-lead-tags" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Etiquetas Libres (Tags):</label>
                  <input
                    id="new-lead-tags"
                    type="text"
                    className="input-field"
                    placeholder="Ej. #universidad, #convenio, #urgente"
                    value={formData.tags}
                    onChange={(e) => handleChange('tags', e.target.value)}
                    style={{ marginTop: '4px' }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* El aviso de privacidad (§6.2, punto 14).
              La API lo admitía desde la Fase 15 —`privacy_notice_accepted`— y esta pantalla
              no lo ofrecía, así que toda ficha dada de alta a mano nacía sin constancia de
              que la persona hubiera aceptado nada. La página pública sí lo pide, y lo pide
              como requisito; aquí **no** es requisito, y la diferencia es deliberada: en la
              página la marca la persona, y aquí la marcaría el asesor por ella. Obligar a
              marcarla para poder guardar la ficha garantizaría que se marque siempre, que
              es justo lo contrario de que signifique algo (§5.2 de la congelación). */}
          <div style={{
            background: 'var(--bg-base)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 14px',
            marginBottom: '16px',
          }}>
            <label htmlFor="new-lead-privacy-notice" style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '0.82rem' }}>
              <input
                id="new-lead-privacy-notice"
                type="checkbox"
                checked={formData.privacy_notice_accepted}
                onChange={(e) => handleChange('privacy_notice_accepted', e.target.checked)}
                style={{ marginTop: '2px' }}
              />
              <span>
                La persona aceptó el aviso de privacidad y que PluriOne la contacte.
              </span>
            </label>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px', lineHeight: '1.5' }}>
              Al marcarla queda registrada la fecha y la hora de ahora, con origen
              «manual». Sin marcarla el campo se queda vacío: «no consta» y «no aceptó» no
              son lo mismo, y la ficha no supone ninguno de los dos.
            </p>
          </div>

          {/* Botones de Acción */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancelar
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Evaluando y Creando...' : 'Guardar y Calificar Lead'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
