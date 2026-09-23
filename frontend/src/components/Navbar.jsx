import React from 'react';
import Campana from './Campana';

export default function Navbar({
  activeTab,
  setActiveTab,
  onOpenNewLead,
  currentRole,
  user: authUser,
  onOpenSessionModal,
  onSelectLead,
}) {
  // Etiquetas de presentación por rol. El nombre y el correo ya no se deducen del rol:
  // vienen de la cuenta autenticada que devolvió el servidor.
  const roleDisplay = {
    System_Admin: { roleTitle: 'Admin TI', badge: '🛡️ Admin TI' },
    Sales_Lead: { roleTitle: 'Líder Comercial', badge: '🎖️ Líder Comercial' },
    Commercial_Executive: { roleTitle: 'Asesor Comercial', badge: '👔 Asesor' },
  };

  const display = roleDisplay[currentRole] || { roleTitle: currentRole || 'Sin rol', badge: currentRole || '—' };
  const fullName = authUser?.full_name || 'Usuario';
  const avatar = fullName.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('');
  const user = { ...display, name: fullName, avatar };
  const canAccessAdmin = currentRole === 'System_Admin' || currentRole === 'Sales_Lead';

  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(11, 15, 25, 0.95)',
      backdropFilter: 'blur(8px)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      padding: '12px 28px'
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '30px',
            height: '30px',
            borderRadius: 'var(--radius-sm)',
            background: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.9rem',
            fontWeight: '900',
            color: '#090a0f',
            boxShadow: '0 1px 3px rgba(0,0,0,0.5)'
          }}>
            ⚡
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.1rem', fontWeight: '800', letterSpacing: '-0.02em' }}>
                PluriOne
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>/</span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Lead Scoring Enterprise
              </span>
              <span className="badge" style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)', fontSize: '0.65rem' }}>
                v1.0.0
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '4px', background: 'var(--bg-surface)', padding: '3px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          {/* Primera, y a propósito: al entrar, lo que se quiere saber es qué toca hoy.
              El tablero cuenta cómo va todo, que es otra pregunta y menos urgente. */}
          <button
            id="tab-hoy"
            onClick={() => setActiveTab('hoy')}
            className={`btn btn-sm ${activeTab === 'hoy' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ border: 'none' }}
          >
            ☀️ Hoy
          </button>
          <button
            id="tab-dashboard"
            onClick={() => setActiveTab('dashboard')}
            className={`btn btn-sm ${activeTab === 'dashboard' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ border: 'none' }}
          >
            📊 Dashboard
          </button>
          <button
            id="tab-leads"
            onClick={() => setActiveTab('leads')}
            className={`btn btn-sm ${activeTab === 'leads' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ border: 'none' }}
          >
            👥 Prospectos
          </button>
          <button
            id="tab-simulator"
            onClick={() => setActiveTab('simulator')}
            className={`btn btn-sm ${activeTab === 'simulator' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ border: 'none' }}
          >
            🎯 Simulador
          </button>
          {/* Todos los roles la ven: el asesor consulta y copia, el líder además gestiona. */}
          <button
            id="tab-publicaciones"
            onClick={() => setActiveTab('publicaciones')}
            className={`btn btn-sm ${activeTab === 'publicaciones' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ border: 'none' }}
          >
            📣 Publicaciones
          </button>
          {canAccessAdmin && (
            <button
              id="tab-admin"
              onClick={() => setActiveTab('admin')}
              className={`btn btn-sm ${activeTab === 'admin' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ border: 'none' }}
            >
              ⚙️ Administración
            </button>
          )}
        </nav>

        {/* Action Buttons & User Profile Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          
          {/* La campana va aquí y no dentro de una pestaña: un aviso tiene que poder
              verse se esté donde se esté, y si hubiera que entrar a buscarlo dejaría de
              ser un aviso para ser otra lista más. */}
          <Campana onSelectLead={onSelectLead} />

          <button
            id="btn-new-lead"
            onClick={onOpenNewLead}
            className="btn btn-primary btn-sm"
          >
            + Nuevo Prospecto
          </button>

          {/* User Profile Pill */}
          <div
            onClick={onOpenSessionModal}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 10px 4px 6px',
              borderRadius: 'var(--radius-full)',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
            title="Ver perfil o cambiar usuario"
          >
            <div style={{
              width: '24px',
              height: '24px',
              borderRadius: 'var(--radius-full)',
              background: 'var(--bg-surface-hover)',
              border: '1px solid var(--border-medium)',
              color: 'var(--text-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.65rem',
              fontWeight: '700',
              fontFamily: 'var(--font-mono)'
            }}>
              {user.avatar}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-primary)', lineHeight: '1.2' }}>
                {user.name}
              </span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', lineHeight: '1' }}>
                {user.badge}
              </span>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '2px' }}>▾</span>
          </div>

        </div>
      </div>
    </header>
  );
}
