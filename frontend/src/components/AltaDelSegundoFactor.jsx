import React, { useEffect, useState } from 'react';
import { activarSegundoFactor, altaDelSegundoFactor } from '../services/api';

/**
 * Alta obligatoria del segundo factor (capítulo 35).
 *
 * Es la hermana de `CambioDeContrasenaObligatorio` y existe por el mismo motivo: una cuenta
 * de administración sin segundo factor no puede operar —el servidor le rechaza todo salvo
 * darlo de alta—, así que enseñarle el panel para que cada tarjeta falle con un 403 sería
 * peor que no enseñárselo.
 *
 * Los dos pasos están separados a propósito. El primero enseña el QR y los códigos; el
 * segundo pide un código del teléfono y **es el que activa**. Sin esa comprobación, quien
 * escanee mal el QR se queda fuera de su propia cuenta sin haber visto nunca un código
 * bueno, que es exactamente el escenario que §3.6 daba como motivo para no hacer nada.
 */
export default function AltaDelSegundoFactor({ user, onActivado, onSalir }) {
  const [alta, setAlta] = useState(null);
  const [codigo, setCodigo] = useState('');
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [guardados, setGuardados] = useState(false);

  useEffect(() => {
    let vigente = true;
    altaDelSegundoFactor()
      .then((datos) => { if (vigente) setAlta(datos); })
      .catch((err) => { if (vigente) setError(err.message); });
    return () => { vigente = false; };
  }, []);

  const activar = async (evento) => {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await activarSegundoFactor(codigo);
      onActivado();
    } catch (err) {
      setError(err.message);
      setCodigo('');
    } finally {
      setEnviando(false);
    }
  };

  const caja = {
    maxWidth: '620px',
    margin: '0 auto',
    padding: '28px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-md)',
  };

  return (
    <div style={{ minHeight: '100vh', padding: '40px 24px', background: 'var(--bg-base)' }}>
      <div style={caja}>
        <h1 style={{ fontSize: '1.15rem', marginBottom: '6px' }}>Active su segundo factor</h1>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
          Las cuentas de administración lo necesitan para entrar. Hasta que lo active, esta
          es la única pantalla disponible para <strong>{user.email}</strong>.
        </p>

        {error && (
          <div role="alert" className="alert alert-error" style={{ marginBottom: '16px' }}>
            {error}
          </div>
        )}

        {!alta ? (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Preparando el alta...</p>
        ) : (
          <>
            <h2 style={{ fontSize: '0.9rem', marginBottom: '8px' }}>1. Escanee este código</h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Con Google Authenticator, Microsoft Authenticator, 1Password o cualquier
              aplicación de códigos de un solo uso.
            </p>
            {/* El SVG viene del servidor ya dibujado. Se inserta como marcado porque es
                geometría, no texto: el contenido lo genera `app/core/codigo_qr.py` a partir
                de la URI que el propio servidor acaba de construir, no de nada que haya
                escrito nadie de fuera. */}
            <div
              aria-label="Código QR para la aplicación de autenticación"
              style={{ background: '#fff', padding: '12px', borderRadius: 'var(--radius-sm)', width: 'fit-content', marginBottom: '14px' }}
              dangerouslySetInnerHTML={{ __html: alta.qr_svg }}
            />
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
              ¿No puede escanear? Escriba esta clave a mano:{' '}
              <code style={{ fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{alta.secreto_en_base32}</code>
            </p>

            <h2 style={{ fontSize: '0.9rem', marginBottom: '8px' }}>2. Guarde sus códigos de recuperación</h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
              Son la forma de entrar si pierde el teléfono. Cada uno sirve <strong>una sola
              vez</strong> y <strong>no se volverán a mostrar</strong>: guárdelos en un sitio
              que no sea este equipo.
            </p>
            <ul style={{ listStyle: 'none', padding: '12px 14px', margin: '0 0 12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
              {alta.codigos_de_recuperacion.map((c) => <li key={c}>{c}</li>)}
            </ul>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', marginBottom: '22px' }}>
              <input type="checkbox" checked={guardados} onChange={(e) => setGuardados(e.target.checked)} />
              Ya los he guardado en un sitio seguro
            </label>

            <h2 style={{ fontSize: '0.9rem', marginBottom: '8px' }}>3. Confirme con un código</h2>
            <form onSubmit={activar}>
              <label htmlFor="alta-codigo" style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Código de seis dígitos que enseña la aplicación
              </label>
              <input
                id="alta-codigo"
                type="text"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                required
                autoComplete="one-time-code"
                inputMode="numeric"
                placeholder="000000"
                className="input-field"
                style={{ width: '100%', marginBottom: '14px', letterSpacing: '0.12em' }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                /* Sin la casilla marcada no se puede activar. Es la única forma de que el
                   paso 2 no se lea como decorado: en cuanto esto se active, esos códigos
                   son lo único que queda si el teléfono se pierde. */
                disabled={enviando || !guardados}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                {enviando ? 'Comprobando...' : 'Activar el segundo factor'}
              </button>
            </form>
          </>
        )}

        <button type="button" className="btn" onClick={onSalir} style={{ width: '100%', justifyContent: 'center', marginTop: '10px' }}>
          Cerrar sesión
        </button>
      </div>
    </div>
  );
}
