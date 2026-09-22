import React, { useState } from 'react';
import { login } from '../services/api';

export default function LoginScreen({ onAuthenticated, expiredNotice, notice }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const user = await login(email.trim(), password);
      // La contraseña no se conserva en el estado tras un login correcto
      setPassword('');
      onAuthenticated(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      background: 'var(--bg-base)',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md, 10px)',
        padding: '32px',
      }}>
        <div style={{ marginBottom: '24px', textAlign: 'center' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: 'var(--radius-sm)',
            background: '#ffffff',
            color: '#0b0f19',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: '800',
            margin: '0 auto 14px',
            fontFamily: 'var(--font-mono)',
          }}>
            P1
          </div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: '700', marginBottom: '4px' }}>
            Sistema Inteligente de Lead Scoring
          </h1>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            PluriOne S.A. de C.V. — Acceso corporativo
          </p>
        </div>

        {expiredNotice && (
          <div style={{
            background: 'rgba(234, 179, 8, 0.12)',
            border: '1px solid rgba(234, 179, 8, 0.35)',
            color: '#eab308',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: '0.78rem',
            marginBottom: '16px',
          }}>
            Su sesión expiró por inactividad. Vuelva a iniciar sesión.
          </div>
        )}

        {notice && (
          <div role="status" style={{
            background: 'rgba(34, 197, 94, 0.12)',
            border: '1px solid rgba(34, 197, 94, 0.35)',
            color: '#22c55e',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: '0.78rem',
            marginBottom: '16px',
          }}>
            {notice}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <label htmlFor="login-email" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Correo corporativo
          </label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            autoComplete="username"
            placeholder="nombre@plurione.com"
            style={{ width: '100%', marginBottom: '14px' }}
            className="input"
          />

          <label htmlFor="login-password" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
            Contraseña
          </label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="current-password"
            placeholder="••••••••"
            style={{ width: '100%', marginBottom: '18px' }}
            className="input"
          />

          {error && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              color: '#ef4444',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 12px',
              fontSize: '0.78rem',
              marginBottom: '14px',
              whiteSpace: 'pre-line',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {submitting ? 'Verificando credenciales...' : 'Iniciar sesión'}
          </button>
        </form>

        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '18px', textAlign: 'center' }}>
          El acceso y el rol se determinan en el servidor a partir de sus credenciales.
        </p>
      </div>
    </div>
  );
}
