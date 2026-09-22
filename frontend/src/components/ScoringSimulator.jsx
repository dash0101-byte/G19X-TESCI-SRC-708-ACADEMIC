import React, { useState, useEffect, useRef, useCallback } from 'react';
import { predictScoreLive } from '../services/api';

export default function ScoringSimulator() {
  const [formData, setFormData] = useState({
    job_title: 'CTO',
    industry: 'FinTech',
    company_size: '201-1000',
    annual_revenue: 5000000,
    source: 'LinkedIn Ads',
    page_views: 6,
    email_opens: 3,
    email_clicks: 2,
    content_downloads: 1,
    attended_webinar: true,
    requested_demo: true,
    proposal_sent: false,
    meeting_scheduled: false,
    urgency: 'INMEDIATA',
    days_since_last_activity: 0,
  });

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Número de la última inferencia pedida. El intervalo de 250 ms evita disparar una
  // petición por cada píxel del deslizador, pero NO ordena las respuestas: cancela el
  // temporizador, no la petición que ya salió. Dos inferencias en vuelo tardan cosas
  // distintas —una genera la explicación por IA y la otra no— y la vieja puede contestar
  // después que la nueva. Cuando eso pasaba, en pantalla quedaba la puntuación de una
  // entrada que ya nadie tenía delante, sin ningún síntoma. Se comprobó reproduciéndolo.
  const ultimaPeticion = useRef(0);

  const runPrediction = useCallback(async () => {
    const miTurno = ultimaPeticion.current + 1;
    ultimaPeticion.current = miTurno;
    setLoading(true);
    try {
      const data = await predictScoreLive(formData);
      // Si mientras tanto salió otra, esta respuesta describe una entrada anterior.
      if (ultimaPeticion.current !== miTurno) return;
      setResult(data);
      setError(null);
    } catch (err) {
      if (ultimaPeticion.current !== miTurno) return;
      // Antes esto era `console.error(err)` y nada más: el panel seguía enseñando el
      // resultado ANTERIOR, indistinguible de una evaluación recién hecha con los
      // controles actuales. Un simulador que miente en silencio es peor que uno roto.
      setError(err?.message || 'No se pudo evaluar la puntuación.');
    } finally {
      if (ultimaPeticion.current === miTurno) setLoading(false);
    }
  }, [formData]);

  useEffect(() => {
    const timer = setTimeout(() => {
      runPrediction();
    }, 250);
    return () => clearTimeout(timer);
  }, [runPrediction]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const scoreColor =
    result?.score_category === 'HOT'
      ? 'var(--hot-text)'
      : result?.score_category === 'WARM'
      ? 'var(--warm-text)'
      : 'var(--cold-text)';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '24px', marginBottom: '32px' }}>
      
      {/* Simulation Controls Panel */}
      <div className="glass-panel" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <span style={{ fontSize: '1.4rem' }}>🎛️</span>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '800' }}>Simulador de Lead Scoring</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Ajusta los parámetros para evaluar la respuesta algorítmica, campos dinámicos y el decaimiento temporal
            </p>
          </div>
        </div>

        {/* Firmographic Inputs */}
        {/* Cada `label` lleva `htmlFor` y cada control su `id`. Antes eran cuatro
            etiquetas sueltas: se leían bien con los ojos, pero no estaban asociadas a
            nada. Un lector de pantalla anunciaba «lista desplegable» sin decir de qué, y
            pulsar sobre el texto no llevaba el foco al campo. Las casillas de más abajo
            no lo necesitan porque el `input` va DENTRO de su propia `label`. */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
          <div>
            <label htmlFor="sim-job-title" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Cargo del Prospecto:</label>
            <input
              id="sim-job-title"
              type="text"
              className="input-field"
              value={formData.job_title}
              onChange={(e) => handleChange('job_title', e.target.value)}
              placeholder="Ej. CTO, Gerente de Talento, Psicólogo"
              style={{ marginTop: '4px' }}
            />
          </div>
          <div>
            <label htmlFor="sim-industry" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Industria (Entrada Libre) ✏️:</label>
            <input
              id="sim-industry"
              list="sim-industries"
              className="input-field"
              value={formData.industry}
              onChange={(e) => handleChange('industry', e.target.value)}
              placeholder="Escribe o selecciona industria..."
              style={{ marginTop: '4px' }}
            />
            <datalist id="sim-industries">
              <option value="FinTech" />
              <option value="Software/TI" />
              <option value="Banca y Finanzas" />
              <option value="Educación / Universidades" />
              <option value="Salud / HealthTech" />
              <option value="Logistics" />
              <option value="Retail & E-Commerce" />
              <option value="Manufactura" />
              <option value="Gobierno / Sector Público" />
              <option value="Telecomunicaciones" />
            </datalist>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '18px' }}>
          <div>
            <label htmlFor="sim-company-size" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Tamaño de Empresa:</label>
            <select
              id="sim-company-size"
              className="input-field"
              value={formData.company_size}
              onChange={(e) => handleChange('company_size', e.target.value)}
              style={{ marginTop: '4px' }}
            >
              <option value="1000+">Corporativo (1000+ empl)</option>
              <option value="201-1000">Mediana Grande (201-1000)</option>
              <option value="51-200">Mediana (51-200)</option>
              <option value="11-50">Pequeña (11-50)</option>
              <option value="1-10">Microempresa (1-10)</option>
            </select>
          </div>
          <div>
            <label htmlFor="sim-urgency" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>Urgencia de Contratación:</label>
            <select
              id="sim-urgency"
              className="input-field"
              value={formData.urgency}
              onChange={(e) => handleChange('urgency', e.target.value)}
              style={{ marginTop: '4px' }}
            >
              <option value="INMEDIATA">Inmediata (&lt; 15 días) [+10 pts]</option>
              <option value="MEDIA">1 a 3 meses [+5 pts]</option>
              <option value="EXPLORATORIA">Exploratoria / Sondeo</option>
            </select>
          </div>
        </div>

        {/* Behavioral Sliders */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', marginBottom: '18px' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            Comportamiento e Interacción Digital
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span>Páginas Vistas:</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{formData.page_views}</strong>
            </div>
            <input
              type="range"
              min="0"
              max="25"
              value={formData.page_views}
              onChange={(e) => handleChange('page_views', parseInt(e.target.value))}
              style={{ width: '100%', marginTop: '4px' }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span>Clics en Correos:</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{formData.email_clicks}</strong>
            </div>
            <input
              type="range"
              min="0"
              max="10"
              value={formData.email_clicks}
              onChange={(e) => handleChange('email_clicks', parseInt(e.target.value))}
              style={{ width: '100%', marginTop: '4px' }}
            />
          </div>

          {/* Temporal Decay Slider */}
          <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: formData.days_since_last_activity > 14 ? 'var(--warm-text)' : 'var(--text-primary)' }}>
              <span>⏱️ Días de Inactividad (Decaimiento):</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{formData.days_since_last_activity} días</strong>
            </div>
            <input
              type="range"
              min="0"
              max="45"
              value={formData.days_since_last_activity}
              onChange={(e) => handleChange('days_since_last_activity', parseFloat(e.target.value))}
              style={{ width: '100%', marginTop: '6px' }}
            />
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Vida media de interés: 14 días (Atenuación: {(Math.pow(0.5, formData.days_since_last_activity / 14) * 100).toFixed(1)}%)
            </div>
          </div>
        </div>

        {/* Commercial Intent Checkboxes */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.8125rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={formData.requested_demo}
              onChange={(e) => handleChange('requested_demo', e.target.checked)}
            />
            <span>Solicitó Demo (+25)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={formData.proposal_sent}
              onChange={(e) => handleChange('proposal_sent', e.target.checked)}
            />
            <span>📄 Propuesta / Cotización (+25)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={formData.meeting_scheduled}
              onChange={(e) => handleChange('meeting_scheduled', e.target.checked)}
            />
            <span>🤝 Reunión Agendada (+20)</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={formData.attended_webinar}
              onChange={(e) => handleChange('attended_webinar', e.target.checked)}
            />
            <span>Asistió a Webinar (+15)</span>
          </label>
        </div>
      </div>

      {/* Real-Time Prediction Output */}
      <div className="glass-panel" style={{ padding: '28px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700' }}>Inferencia Predictiva en Tiempo Real</h3>
            {loading && <span style={{ fontSize: '0.8rem', color: 'var(--color-primary-light)' }}>⏳ Evaluando...</span>}
          </div>

          {error && (
            <div
              role="alert"
              style={{
                background: 'var(--hot-bg)',
                border: '1px solid var(--hot-border)',
                color: 'var(--hot-text)',
                borderRadius: 'var(--radius-sm)',
                padding: '10px 12px',
                marginBottom: '14px',
                fontSize: '0.8rem',
                lineHeight: 1.4,
              }}
            >
              {error}
              <div style={{ color: 'var(--text-muted)', marginTop: '4px', fontSize: '0.72rem' }}>
                La puntuación de abajo es la de la última evaluación que sí funcionó.
              </div>
            </div>
          )}

          {/* Minimalist Score Gauge Card */}
          <div style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '24px',
            textAlign: 'center',
            marginBottom: '18px',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>
              Puntuación Híbrida Compuesta
            </div>
            <div style={{ fontSize: '3.6rem', fontWeight: '800', fontFamily: 'var(--font-mono)', color: scoreColor, margin: '6px 0', lineHeight: 1.1 }}>
              {result?.score ?? '--'}
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
              <span className={`badge ${result?.score_category === 'HOT' ? 'badge-hot' : (result?.score_category === 'WARM' ? 'badge-warm' : 'badge-cold')}`}>
                {result?.score_category}
              </span>
              <span className="badge badge-status">
                Prob. ML: {Math.round((result?.conversion_probability || 0) * 100)}%
              </span>
            </div>
          </div>

          {/* Mathematical Breakdown Details */}
          <div style={{ background: 'var(--bg-base)', padding: '16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '16px', fontSize: '0.8rem' }}>
            <div style={{ fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', fontSize: '0.725rem', letterSpacing: '0.04em' }}>
              Desglose de la Ecuación Híbrida:
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span>60% Machine Learning (Supervisado):</span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {((result?.ml_probability || 0) * 60).toFixed(1)} pts
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span>40% Heurístico ICP (Atenuado):</span>
              <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--warm-text)' }}>
                {((result?.heuristic_score || 0) * 0.4).toFixed(1)} pts
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
              <span>Factor de Decaimiento γ(Δt):</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {result?.decay_factor}
              </strong>
            </div>
          </div>

          {/* AI Tactical Advice */}
          {result?.ai_explanation && (
            <div style={{ background: 'var(--bg-surface-elevated)', padding: '14px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.725rem', fontWeight: '700', color: 'var(--text-primary)', textTransform: 'uppercase', marginBottom: '4px', letterSpacing: '0.03em' }}>
                💡 Sugerencia Táctica Comercial:
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                {result.ai_explanation.recommended_action}
              </p>
            </div>
          )}
        </div>

        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '16px' }}>
          Motor de Inferencia Predictiva en Tiempo Real • Pipeline Calibrado de Machine Learning v1.0
        </div>
      </div>

    </div>
  );
}
