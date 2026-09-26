import React from 'react';

// Las tres tarjetas de categoría FILTRAN la tabla al pulsarlas, así que son botones. Se
// dibujaban con un `<div onClick>`, y eso las dejaba fuera del alcance del teclado: quien
// no usa ratón veía tres tarjetas con el cursor de mano y no podía pulsar ninguna. La
// cuarta —«Total Prospectos»— no filtra nada y sigue siendo un `<div>`, que es lo correcto:
// convertirla en botón anunciaría al lector de pantalla un control que no hace nada.
//
// Un `<button>` trae su propia tipografía, su color y su alineación al centro. Esto los
// devuelve a los del panel para que la tarjeta se vea exactamente igual que antes.
const TARJETA_PULSABLE = {
  padding: '16px 18px',
  cursor: 'pointer',
  font: 'inherit',
  color: 'inherit',
  textAlign: 'left',
  width: '100%',
  display: 'block',
};

export default function KPICards({ summary, onFilterCategory }) {
  if (!summary) return null;

  const hotPct = summary.total_leads ? Math.round((summary.hot_leads_count / summary.total_leads) * 100) : 0;
  const warmPct = summary.total_leads ? Math.round((summary.warm_leads_count / summary.total_leads) * 100) : 0;
  const coldPct = summary.total_leads ? Math.round((summary.cold_leads_count / summary.total_leads) * 100) : 0;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
      gap: '12px',
      marginBottom: '24px'
    }}>
      {/* Total Leads */}
      <div className="glass-panel" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Prospectos
          </span>
          <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>📁</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
          {summary.total_leads}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Pipeline activo registrado
        </div>
      </div>

      {/* HOT Leads */}
      <button
        type="button"
        className="glass-panel"
        style={TARJETA_PULSABLE}
        onClick={() => onFilterCategory('HOT')}
        title="Filtrar prospectos HOT (Score >= 75)"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--hot-text)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            🔥 HOT (≥ 75)
          </span>
          <span className="badge badge-hot" style={{ fontSize: '0.65rem' }}>{hotPct}%</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--hot-text)' }}>
          {summary.hot_leads_count}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Atención comercial &lt; 15m
        </div>
      </button>

      {/* WARM Leads */}
      <button
        type="button"
        className="glass-panel"
        style={TARJETA_PULSABLE}
        onClick={() => onFilterCategory('WARM')}
        title="Filtrar prospectos WARM (Score 45 - 74.9)"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--warm-text)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            ⚡ WARM (45-74)
          </span>
          <span className="badge badge-warm" style={{ fontSize: '0.65rem' }}>{warmPct}%</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--warm-text)' }}>
          {summary.warm_leads_count}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Nutrición y seguimiento
        </div>
      </button>

      {/* COLD Leads */}
      <button
        type="button"
        className="glass-panel"
        style={TARJETA_PULSABLE}
        onClick={() => onFilterCategory('COLD')}
        title="Filtrar prospectos COLD (Score < 45)"
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--cold-text)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            ❄️ COLD (&lt; 45)
          </span>
          <span className="badge badge-cold" style={{ fontSize: '0.65rem' }}>{coldPct}%</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--cold-text)' }}>
          {summary.cold_leads_count}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Campañas de branding
        </div>
      </button>

      {/* Average Score */}
      <div className="glass-panel" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Score Promedio
          </span>
          <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>🎯</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
          {summary.average_score} <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '400' }}>/100</span>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Calificación compuesta
        </div>
      </div>

      {/* Conversion Rate */}
      <div className="glass-panel" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Conversión MQL
          </span>
          <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>📈</span>
        </div>
        <div style={{ fontSize: '1.75rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: 'var(--success-text)' }}>
          {summary.mql_to_sql_conversion_rate}%
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Tasa MQL a SQL
        </div>
      </div>
    </div>
  );
}
