import React, { useState } from 'react';
import { changeOwnPassword } from '../services/api';

/**
 * Cambio de contraseña obligatorio.
 *
 * Una cuenta recién creada, restablecida o reactivada entra con una contraseña que fijó
 * otra persona. Hasta la Fase 13 la marca `must_change_password` se guardaba y el panel de
 * administración la enseñaba, pero nada obligaba a cambiarla: se podía trabajar meses con
 * la contraseña que conoce el administrador. Ahora el servidor rechaza todo salvo cambiarla
 * (§19.2), y esta pantalla es la que la persona ve en lugar de una aplicación que le fallaría
 * tarjeta a tarjeta.
 *
 * Se pide la contraseña actual igual que en el menú de la sesión: quien se haga con estas
 * credenciales prestadas no debe poder fijar una propia sin conocerlas.
 */
export default function CambioDeContrasenaObligatorio({ user, onCompletado, onSalir }) {
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [repetida, setRepetida] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const enviar = async (evento) => {
    evento.preventDefault();
    setError(null);
    if (nueva !== repetida) {
      setError('La contraseña nueva y su repetición no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      const resultado = await changeOwnPassword(actual, nueva);
      setActual('');
      setNueva('');
      setRepetida('');
      // El servidor cierra todas las sesiones al cambiarla, esta incluida: quien llama
      // vuelve a la pantalla de entrada. `enviando` no se suelta, porque esta pantalla
      // desaparece y un botón que se reactiva un instante invita a un segundo envío.
      await onCompletado(resultado?.mensaje || 'Contraseña actualizada. Entre con la nueva.');
    } catch (err) {
      setError(err.message || 'No se pudo cambiar la contraseña.');
      setEnviando(false);
    }
  };

  const etiqueta = {
    display: 'block',
    fontSize: '0.75rem',
    color: 'var(--text-secondary)',
    marginBottom: '6px',
  };
  const campo = { width: '100%', marginBottom: '14px' };

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
        maxWidth: '440px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md, 10px)',
        padding: '32px',
      }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '8px' }}>
          Cambie su contraseña para continuar
        </h1>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: '8px' }}>
          {user?.full_name}, la contraseña con la que ha entrado la fijó otra persona al crear,
          restablecer o reactivar su cuenta.
        </p>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.55, marginBottom: '20px' }}>
          Mientras siga siendo esa, la cuenta no le identifica solo a usted, así que el
          sistema no le deja operar hasta que la cambie. Al guardarla se cerrarán todas sus
          sesiones y volverá a entrar con la nueva.
        </p>

        <form onSubmit={enviar}>
          <label htmlFor="cambio-actual" style={etiqueta}>Contraseña actual</label>
          <input id="cambio-actual" type="password" className="input-field" style={campo} required
            autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} />

          <label htmlFor="cambio-nueva" style={etiqueta}>Contraseña nueva (mínimo 12 caracteres)</label>
          <input id="cambio-nueva" type="password" className="input-field" style={campo} required minLength={12}
            autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} />

          <label htmlFor="cambio-repetida" style={etiqueta}>Repita la contraseña nueva</label>
          <input id="cambio-repetida" type="password" className="input-field" style={campo} required minLength={12}
            autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} />

          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '14px', lineHeight: 1.5 }}>
            Una frase larga y fácil de recordar es más segura que una palabra corta con símbolos.
          </p>

          {error && (
            <div role="alert" className="alert alert-error" style={{ marginBottom: '14px' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px' }}>
            <button type="submit" className="btn btn-primary" disabled={enviando} style={{ flex: 1, justifyContent: 'center' }}>
              {enviando ? 'Guardando…' : 'Guardar y volver a entrar'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onSalir}>
              Salir
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
