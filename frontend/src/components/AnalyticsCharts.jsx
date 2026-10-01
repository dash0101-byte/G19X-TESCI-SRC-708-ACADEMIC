import React from 'react';

export default function AnalyticsCharts({ summary, campaigns }) {
  if (!summary) return null;

  const total = summary.total_leads || 1;
  const hotWidth = (summary.hot_leads_count / total) * 100;
  const warmWidth = (summary.warm_leads_count / total) * 100;
  const coldWidth = (summary.cold_leads_count / total) * 100;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px', marginBottom: '32px' }}>
      
      {/* 1. Distribución de Cuadrantes de Lead Scoring */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700' }}>Segmentación de Calidad de Leads</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Proporción por umbrales algorítmicos dinámicos</p>
          </div>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)', padding: '4px 8px', borderRadius: '6px' }}>
            Analítica Avanzada
          </span>
        </div>

        {/* Stacked Progress Bar */}
        <div style={{ height: '24px', width: '100%', display: 'flex', borderRadius: '8px', overflow: 'hidden', marginBottom: '20px', border: '1px solid var(--border-subtle)' }}>
          {/* Los tres degradados no existían en la paleta hasta el capítulo 39, así que
              `var()` era inválido, la declaración entera se caía al valor inicial y esta
              barra —el gráfico que dice cómo se reparte la cartera— se dibujaba
              **vacía**. Estaba anotado como «cosmético» en §6.4; no lo era.

              La línea oscura entre segmentos es necesaria por lo mismo que la barra: una
              vez que pinta, hay que poder decir dónde acaba uno y empieza el otro, y los
              rojos y ámbares vecinos solo se separan 1.75:1 entre sí. La línea da de 5.26
              a 9.21 contra los colores que separa. */}
          <div style={{ width: `${hotWidth}%`, background: 'var(--hot-gradient)', boxShadow: 'inset -1px 0 0 var(--bg-base)' }} title={`HOT: ${summary.hot_leads_count}`} />
          <div style={{ width: `${warmWidth}%`, background: 'var(--warm-gradient)', boxShadow: 'inset -1px 0 0 var(--bg-base)' }} title={`WARM: ${summary.warm_leads_count}`} />
          <div style={{ width: `${coldWidth}%`, background: 'var(--cold-gradient)' }} title={`COLD: ${summary.cold_leads_count}`} />
        </div>

        {/* Breakdown Items */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'var(--hot-text)' }}></span>
            <div>
              <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>HOT ({summary.hot_leads_count})</span>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{Math.round(hotWidth)}% del total</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'var(--warm-text)' }}></span>
            <div>
              <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>WARM ({summary.warm_leads_count})</span>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{Math.round(warmWidth)}% del total</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'var(--cold-text)' }}></span>
            <div>
              <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>COLD ({summary.cold_leads_count})</span>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{Math.round(coldWidth)}% del total</div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Pipeline Comercial por Estados */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700' }}>Embudo de Conversión de Ventas</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Flujo desde nuevo prospecto hasta cierre exitoso</p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {Object.entries(summary.pipeline_distribution || {}).map(([stage, count]) => {
            const pct = Math.round((count / total) * 100);
            return (
              <div key={stage}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: '500' }}>{stage}</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: '700', fontFamily: 'var(--font-mono)' }}>{count} leads ({pct}%)</span>
                </div>
                <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${pct}%`,
                      background: stage === 'WON' ? '#10b981' : (stage === 'QUALIFIED' ? '#6366f1' : '#f59e0b'),
                      borderRadius: '4px',
                      transition: 'width 0.5s ease-out'
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Calidad de Prospectos por Sector Económico */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>Score Promedio por Industria</h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>Sectores con mayor propensión a contratación TI</p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {(summary.top_industries || []).map((ind) => (
            <div key={ind.industry} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ width: '140px', fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {ind.industry}
              </div>
              <div style={{ flex: 1, margin: '0 16px', height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${ind.avg_score}%`,
                    background: ind.avg_score >= 75 ? 'var(--hot-gradient)' : 'var(--warm-gradient)',
                    borderRadius: '4px'
                  }}
                />
              </div>
              <div style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: ind.avg_score >= 75 ? 'var(--hot-text)' : 'var(--warm-text)' }}>
                {ind.avg_score} <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>({ind.count} leads)</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Rendimiento por Campaña de Marketing */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>Rendimiento de Campañas de Adquisición</h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>Atribución multicanal y efectividad de canales</p>

        <div className="data-table-container">
          <table className="data-table" style={{ fontSize: '0.8rem' }}>
            <thead>
              <tr>
                <th>Campaña</th>
                <th>Canal</th>
                <th>Leads</th>
                <th>Score</th>
                <th>Conv.</th>
              </tr>
            </thead>
            <tbody>
              {(campaigns || []).map((c) => (
                <tr key={c.campaign_id}>
                  <td style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{c.campaign_name}</td>
                  <td>{c.channel}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{c.total_leads} ({c.hot_leads} 🔥)</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: c.avg_score >= 70 ? 'var(--hot-text)' : 'var(--text-secondary)' }}>
                    {c.avg_score}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: '#34d399', fontWeight: '700' }}>
                    {c.conversion_rate}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
