import React from 'react';

// De dónde llegó esta persona. El servidor manda `llego_por: null` cuando no llegó por
// ninguna publicación, y entonces aquí no se pinta nada: una tarjeta con guiones diría
// «vino de una publicación que no sabemos cuál», que no es lo mismo que «no vino de ahí».
export default function LlegoPor({ llegoPor }) {
  if (!llegoPor || !llegoPor.solicitudes || llegoPor.solicitudes.length === 0) return null;

  const { perfil_de_linkedin: perfil, solicitudes } = llegoPor;

  return (
    <div
      className="glass-panel"
      aria-labelledby="titulo-llego-por"
      style={{ padding: '18px', marginBottom: '20px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '1.1rem' }} aria-hidden="true">📣</span>
        <h3 id="titulo-llego-por" style={{ fontSize: '0.95rem', fontWeight: '700' }}>
          Llegó por {solicitudes.length > 1 ? `${solicitudes.length} publicaciones` : 'una publicación'}
        </h3>
        {perfil && (
          // En otra pestaña: el perfil está fuera de la aplicación y volver atrás no debe
          // costar perder la ficha abierta.
          <a
            href={perfil}
            target="_blank"
            rel="noopener noreferrer"
            className="badge"
            style={{ marginLeft: 'auto', textDecoration: 'none' }}
          >
            Ver perfil de LinkedIn ↗
          </a>
        )}
      </div>

      <ul
        aria-label="Solicitudes recibidas"
        style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}
      >
        {solicitudes.map((solicitud, indice) => (
          <li
            key={`${solicitud.publicacion_id || 'sin-publicacion'}-${solicitud.recibida_en}-${indice}`}
            style={{
              padding: '10px 12px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
              <strong>
                {solicitud.titulo || 'Publicación retirada'}
                {/* «Llegó por la publicación X, vía WhatsApp». Es de este envío: la misma
                    persona puede volver por otra red, y cada solicitud dice la suya. */}
                {solicitud.red && <span style={{ fontWeight: 400 }}>, vía {solicitud.red}</span>}
              </strong>
              <span style={{ color: 'var(--text-muted)' }}>
                {new Date(solicitud.recibida_en).toLocaleString('es-MX')}
              </span>
            </div>
            {solicitud.necesidad && (
              <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                Qué necesita: {solicitud.necesidad}
              </div>
            )}
            {solicitud.enlace && (
              <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', wordBreak: 'break-all', marginTop: '2px' }}>
                {solicitud.enlace}
              </div>
            )}
            <div style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              {solicitud.aviso_aceptado_en
                ? `Aceptó el aviso de privacidad el ${new Date(solicitud.aviso_aceptado_en).toLocaleString('es-MX')}`
                : 'Sin fecha de aviso registrada'}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
