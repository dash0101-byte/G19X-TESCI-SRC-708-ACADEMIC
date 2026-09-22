import React, { useState } from 'react';
import { changeOwnPassword } from '../services/api';

// Descripción de cada rol, solo para mostrar al usuario qué puede hacer.
// Los permisos reales los aplica el backend a partir del token; esto es informativo.
const ROLE_INFO = {
  System_Admin: {
    badge: '🛡️ Administrador TI',
    description: 'Acceso total: calibración de parámetros, recálculo por lotes, gestión de base de datos y auditoría.',
  },
  Sales_Lead: {
    badge: '🎖️ Líder Comercial',
    description: 'Supervisión gerencial: dashboards analíticos de conversión, campañas de marketing, edición y recálculo masivo.',
  },
  Commercial_Executive: {
    badge: '👔 Asesor Comercial',
    description: 'Operación diaria: consulta de prospectos, priorización de leads HOT y registro de actividades.',
  },
};

function initials(fullName) {
  return (fullName || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

export default function SessionModal({ user, onLogout, onClose }) {
  const info = ROLE_INFO[user?.role] || {
    badge: user?.role || 'Sin rol',
    description: 'Permisos determinados por el servidor.',
  };

  // Cambio de contraseña propio. Vive aquí, en el menú de la sesión, porque es el sitio
  // donde alguien busca "mi cuenta". Antes no existía en ninguna parte: cambiar la
  // contraseña exigía que un administrador entrara al servidor a ejecutar un script.
  const [abriendoCambio, setAbriendoCambio] = useState(false);
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [repetida, setRepetida] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [hecho, setHecho] = useState(null);

  const cambiar = async (evento) => {
    evento.preventDefault();
    setError(null);
    if (nueva !== repetida) {
      setError('La contraseña nueva y su repetición no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      const resultado = await changeOwnPassword(actual, nueva);
      setHecho(resultado?.mensaje || 'Contraseña actualizada.');
      setActual('');
      setNueva('');
      setRepetida('');
    } catch (err) {
      // El backend devuelve la lista completa de motivos cuando la política la rechaza;
      // enseñarlos todos evita que la persona tenga que descubrirla a base de intentos.
      setError(err.message || 'No se pudo cambiar la contraseña.');
    } finally {
      setEnviando(false);
    }
  };

  const campo = {
    width: '100%',
    padding: '8px 10px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    background: 'var(--bg-base)',
    color: 'var(--text-primary)',
    fontSize: '0.85rem',
    marginBottom: '10px',
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '460px', padding: '24px' }} onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700' }}>Sesión activa</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Identidad verificada por el servidor
            </p>
          </div>
          <button onClick={onClose} className="btn btn-secondary btn-sm" style={{ border: 'none', fontSize: '1rem', padding: '4px 8px' }}>
            ✕
          </button>
        </div>

        {/* Identidad autenticada */}
        <div style={{
          padding: '16px',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--color-primary)',
          background: 'var(--color-primary-subtle)',
          display: 'flex',
          gap: '14px',
          alignItems: 'center',
          marginBottom: '18px',
        }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: 'var(--radius-full)',
            // --color-primary es #ffffff en este tema oscuro: el texto va en el color del fondo base
            background: 'var(--color-primary)',
            color: '#0b0f19',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: '700',
            fontSize: '0.9rem',
            fontFamily: 'var(--font-mono)',
          }}>
            {initials(user?.full_name)}
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: '700', fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                {user?.full_name}
              </span>
              <span className="badge" style={{ fontSize: '0.65rem' }}>{info.badge}</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{user?.email}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
              {info.description}
            </div>
          </div>
        </div>

        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '18px', lineHeight: 1.5 }}>
          Para operar con otro rol, cierre la sesión e inicie con las credenciales
          correspondientes. El rol no se puede cambiar desde el navegador.
        </p>

        {/* Cambio de contraseña propio */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px', marginBottom: '14px' }}>
          {!abriendoCambio && !hecho && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setAbriendoCambio(true)}>
              Cambiar mi contraseña
            </button>
          )}

          {hecho && (
            <p style={{ fontSize: '0.78rem', color: 'var(--success-text)', lineHeight: 1.5 }}>
              {hecho}
            </p>
          )}

          {abriendoCambio && !hecho && (
            <form onSubmit={cambiar}>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: 1.5 }}>
                Se pide la contraseña actual aunque ya haya iniciado sesión: es lo que impide
                que quien se haga con una sesión abierta se quede con la cuenta cambiándola.
                Al terminar se cerrarán <strong>todas</strong> sus sesiones, incluida esta.
              </p>
              <input type="password" style={campo} placeholder="Contraseña actual" required autoComplete="current-password"
                value={actual} onChange={(e) => setActual(e.target.value)} />
              <input type="password" style={campo} placeholder="Contraseña nueva (mínimo 12 caracteres)" required minLength={12}
                autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} />
              <input type="password" style={campo} placeholder="Repítala" required minLength={12}
                autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} />
              <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: 1.5 }}>
                Una frase larga y fácil de recordar es más segura que una palabra corta con
                símbolos.
              </p>
              {error && (
                <p style={{ fontSize: '0.75rem', color: 'var(--hot-text, #b42318)', marginBottom: '10px', whiteSpace: 'pre-line' }}>
                  {error}
                </p>
              )}
              <div style={{ display: 'flex', gap: '8px' }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={enviando}>
                  {enviando ? 'Guardando…' : 'Guardar'}
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setAbriendoCambio(false); setError(null); }}>
                  Cancelar
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
          <button onClick={onLogout} className="btn btn-danger btn-sm">
            Cerrar sesión
          </button>
          <button onClick={onClose} className="btn btn-secondary btn-sm">
            Cerrar
          </button>
        </div>

      </div>
    </div>
  );
}
