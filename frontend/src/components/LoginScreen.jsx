import React, { useState } from 'react';
import { completarLoginConSegundoFactor, login } from '../services/api';

export default function LoginScreen({ onAuthenticated, expiredNotice, notice }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // El desafío del segundo factor, cuando el servidor pide el segundo paso (capítulo 35).
  // Mientras vale algo, el formulario deja de pedir correo y contraseña y pide el código.
  const [desafio, setDesafio] = useState(null);
  const [codigo, setCodigo] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const respuesta = await login(email.trim(), password);
      // La contraseña no se conserva en el estado tras un primer paso correcto, haya
      // segundo o no: a partir de aquí no vuelve a hacer falta.
      setPassword('');
      if (respuesta && respuesta.tipo === 'segundo_factor') {
        setDesafio(respuesta);
        return;
      }
      onAuthenticated(respuesta);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSegundoFactor = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const user = await completarLoginConSegundoFactor(desafio.desafio, codigo);
      setCodigo('');
      onAuthenticated(user);
    } catch (err) {
      // Se vuelve al primer paso, porque es lo que hay que hacer: el desafío se gasta o
      // caduca, y dejar el formulario del código en pantalla invitaría a reintentar contra
      // un desafío que ya no vale y a leer «el código no es válido» sin que lo sea.
      setError(err.message);
      setDesafio(null);
      setCodigo('');
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

        {/* Segundo paso (capítulo 35). Es otro formulario y no un campo más del primero:
            mientras el desafío vale, el correo y la contraseña ya no pintan nada, y
            dejarlos en pantalla invita a volver a enviarlos. */}
        {desafio ? (
          <form onSubmit={handleSegundoFactor}>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
              Escriba el código de seis dígitos de su aplicación de autenticación.
              También sirve uno de sus códigos de recuperación.
            </p>

            <label htmlFor="login-codigo" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Código
            </label>
            <input
              id="login-codigo"
              type="text"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              required
              autoFocus
              /* `one-time-code` es lo que hace que el teléfono ofrezca el código del SMS o
                 del llavero sin que haya que ir a buscarlo. `inputMode` saca el teclado
                 numérico, pero NO se usa type="number": un código de recuperación lleva
                 letras y guiones, y el campo acepta los dos. */
              autoComplete="one-time-code"
              inputMode="numeric"
              placeholder="000000"
              style={{ width: '100%', marginBottom: '18px', letterSpacing: '0.12em' }}
              className="input"
            />

            {desafio.codigos_de_recuperacion_restantes === 0 && (
              <div style={{ fontSize: '0.72rem', color: 'var(--warm-text)', marginBottom: '14px' }}>
                No le quedan códigos de recuperación. Si pierde el teléfono, necesitará que
                otra persona con administración le quite el segundo factor.
              </div>
            )}

            {error && (
              <div role="alert" style={{
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
              {submitting ? 'Comprobando el código...' : 'Entrar'}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => { setDesafio(null); setCodigo(''); setError(''); }}
              style={{ width: '100%', justifyContent: 'center', marginTop: '8px' }}
            >
              Volver
            </button>
          </form>
        ) : (
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
        )}

        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '18px', textAlign: 'center' }}>
          El acceso y el rol se determinan en el servidor a partir de sus credenciales.
        </p>
      </div>
    </div>
  );
}
