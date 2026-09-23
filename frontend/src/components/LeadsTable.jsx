import React from 'react';

export default function LeadsTable({
  leads,
  loading,
  selectedCategory,
  setSelectedCategory,
  searchQuery,
  setSearchQuery,
  onSelectLead,
  onRefresh,
}) {
  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '32px' }}>
      {/* Header & Filter Controls */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '20px'
      }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: '800' }}>Matriz de Prospectos Comerciales</h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Prospectos ordenados por probabilidad predictiva y scoring dinámico
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', width: '260px' }}>
            <input
              id="input-lead-search"
              type="text"
              className="input-field"
              placeholder="Buscar por nombre, cargo, empresa..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '32px' }}
            />
            <span style={{ position: 'absolute', left: '10px', top: '10px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              🔍
            </span>
          </div>

          {/* Category Filter Pills */}
          <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-base)', padding: '3px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <button
              onClick={() => setSelectedCategory('')}
              className={`btn btn-sm ${!selectedCategory ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px' }}
            >
              Todos
            </button>
            <button
              id="filter-category-hot"
              onClick={() => setSelectedCategory('HOT')}
              className={`btn btn-sm ${selectedCategory === 'HOT' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px' }}
            >
              🔥 HOT
            </button>
            <button
              id="filter-category-warm"
              onClick={() => setSelectedCategory('WARM')}
              className={`btn btn-sm ${selectedCategory === 'WARM' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px' }}
            >
              ⚡ WARM
            </button>
            <button
              id="filter-category-cold"
              onClick={() => setSelectedCategory('COLD')}
              className={`btn btn-sm ${selectedCategory === 'COLD' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none', padding: '5px 12px' }}
            >
              ❄️ COLD
            </button>
          </div>

          <button onClick={onRefresh} className="btn btn-secondary btn-sm" title="Refrescar lista">
            🔄
          </button>
        </div>
      </div>

      {/* Table Component */}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Prospecto / Contacto</th>
              <th>Empresa & Cargo</th>
              <th>Sector</th>
              <th>Canal de Origen</th>
              <th>Score Híbrido</th>
              <th>Probabilidad ML</th>
              <th>Cuadrante</th>
              <th>Estado</th>
              <th style={{ textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  ⏳ Cargando y evaluando prospectos en tiempo real...
                </td>
              </tr>
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No se encontraron prospectos con los filtros seleccionados.
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const badgeClass =
                  lead.score_category === 'HOT'
                    ? 'badge-hot'
                    : lead.score_category === 'WARM'
                    ? 'badge-warm'
                    : 'badge-cold';

                const scoreColor =
                  lead.score_category === 'HOT'
                    ? 'var(--hot-text)'
                    : lead.score_category === 'WARM'
                    ? 'var(--warm-text)'
                    : 'var(--cold-text)';

                return (
                  <tr
                    key={lead.id}
                    id={`lead-row-${lead.id}`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onSelectLead(lead.id)}
                  >
                    {/* Contacto */}
                    <td>
                      <div style={{ fontWeight: '700', color: 'var(--text-primary)' }}>
                        {lead.first_name} {lead.last_name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {lead.email}
                      </div>
                    </td>

                    {/* Empresa & Cargo */}
                    <td>
                      <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                        {lead.company || 'N/A'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {lead.job_title || 'No especificado'}
                      </div>
                    </td>

                    {/* Sector */}
                    <td>
                      <span style={{ fontSize: '0.8rem', background: 'rgba(255,255,255,0.04)', padding: '2px 8px', borderRadius: '4px' }}>
                        {lead.industry || 'General'}
                      </span>
                    </td>

                    {/* Canal */}
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {lead.source}
                      {/* Llegó por una publicación y todavía no lo atiende nadie: es lo
                          que el líder tiene que repartir. Lo decide el servidor
                          (`esperando_asesor`), no esta condición: cuando lo decidía aquí
                          preguntando por «LinkedIn», una ficha llegada por WhatsApp salía
                          sin marca aunque el contador de al lado la estuviera contando, y
                          el líder no tenía manera de saber cuál de los dos mentía. */}
                      {lead.esperando_asesor && (
                        <span className="badge" style={{ marginLeft: '6px', fontSize: '0.6rem' }}>
                          Nuevo, sin asesor
                        </span>
                      )}
                    </td>

                    {/* Score Híbrido */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div
                          style={{
                            minWidth: '34px',
                            height: '28px',
                            padding: '0 6px',
                            borderRadius: 'var(--radius-xs)',
                            background: 'var(--bg-surface-elevated)',
                            border: '1px solid var(--border-subtle)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: '700',
                            fontFamily: 'var(--font-mono)',
                            color: scoreColor,
                            fontSize: '0.85rem'
                          }}
                        >
                          {lead.current_score}
                        </div>
                        <span style={{ fontSize: '0.675rem', color: 'var(--text-muted)' }}>/100</span>
                      </div>
                    </td>

                    {/* Probabilidad ML */}
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: '600', color: 'var(--text-primary)' }}>
                      {/* El esquema del backend declara `conversion_probability: float` no
                          nulo con defecto 0.0, así que hoy este campo siempre llega. El
                          `?? 0` no arregla un fallo alcanzable: evita que, si algún día
                          deja de llegar —un endpoint nuevo, una respuesta parcial—, la
                          columna que más se mira ponga «NaN%» en cada fila sin que nada
                          falle en ninguna parte. */}
                      {Math.round((lead.conversion_probability ?? 0) * 100)}%
                    </td>

                    {/* Cuadrante */}
                    <td>
                      <span className={`badge ${badgeClass}`}>
                        {lead.score_category === 'HOT' && '🔥 '}
                        {lead.score_category === 'WARM' && '⚡ '}
                        {lead.score_category === 'COLD' && '❄️ '}
                        {lead.score_category}
                      </span>
                    </td>

                    {/* Estado */}
                    <td>
                      <span className="badge badge-status">
                        {lead.status}
                      </span>
                    </td>

                    {/* Acciones */}
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        id={`btn-edit-lead-${lead.id}`}
                        className="btn btn-secondary btn-sm"
                        style={{ marginRight: '6px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectLead(lead.id, true);
                        }}
                        title="Editar información del prospecto"
                      >
                        ✏️ Editar
                      </button>
                      <button
                        id={`btn-view-lead-${lead.id}`}
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectLead(lead.id, false);
                        }}
                        title="Ver diagnóstico 360 e historial"
                      >
                        Ficha 360 ➔
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
