import React, { useRef, useState } from 'react';
import { changeOwnPassword } from '../services/api';
import MensajeDeCampo from './MensajeDeCampo';
import {
  comoAviso,
  enfocarPrimerCampoConError,
  erroresDeLaContrasena,
  propiedadesDeCampo,
  resumenDeCampos,
  sinElCampo,
} from './erroresDeFormulario';
import { useVentanaModal } from './ventanaModal';

// Las dos de la petición, con el nombre que este formulario les da. Desde el capítulo 44
// ese nombre está además en una `<label>` de verdad al lado del campo, así que esta tabla y
// la pantalla dicen lo mismo; antes el nombre vivía solo en el `placeholder` y esto era la
// única forma de que el resumen de arriba dijera «Contraseña actual» y no
// `contrasena_actual`.
const ETIQUETAS_DE_LA_CONTRASENA = {
  contrasena_actual: 'Contraseña actual',
  nueva_contrasena: 'Contraseña nueva',
};
const CAMPOS_DE_LA_CONTRASENA = ['contrasena_actual', 'nueva_contrasena'];

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
  // Nombre, atrapado del foco, `Escape` y devolución del foco al cerrar (capítulo 36).
  const ventana = useVentanaModal({ alCerrar: onClose, etiquetadoPor: 'sesion-activa-titulo' });

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
  const [errores, setErrores] = useState({});
  const [hecho, setHecho] = useState(null);
  const formularioDeLaContrasena = useRef(null);

  const cambiar = async (evento) => {
    evento.preventDefault();
    setError(null);
    setErrores({});
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
      // El backend devuelve la lista completa de motivos cuando la política la rechaza, y
      // este comentario decía desde el capítulo 23 que se enseñaban todos. No llegaba
      // ninguno: `parseApiError` se quedaba con el titular del detalle estructurado y
      // tiraba la lista (capítulo 43). Ahora llegan, y además cada respuesta va al campo
      // del que habla: la actual con un 401, la nueva con un 422.
      const repartidos = erroresDeLaContrasena(err);
      if (repartidos) {
        setErrores(repartidos.porCampo);
        setError(comoAviso([
          resumenDeCampos(repartidos.porCampo, ETIQUETAS_DE_LA_CONTRASENA),
          ...repartidos.sueltos,
        ]));
        enfocarPrimerCampoConError(
          formularioDeLaContrasena, repartidos.porCampo, CAMPOS_DE_LA_CONTRASENA,
        );
      } else {
        setError(err.message || 'No se pudo cambiar la contraseña.');
      }
    } finally {
      setEnviando(false);
    }
  };

  // Las tres cajas de contraseña eran `className="input-field" style={{ marginBottom: '10px' }}` y no `.input-field` (capítulo 43), con
  // el mismo precio que en el panel de administración: el borde de 1.12:1 que el capítulo 39
  // retiró de los controles, ningún aro de foco propio y, desde que este formulario reparte
  // su error por campos, un `aria-invalid` que no se ve. Lo único que no estaba en la hoja
  // era el margen de abajo, y eso es lo que queda escrito aquí.

  // Velo con `role="presentation"` y cierre según dónde se pulsó; `Escape` para el teclado.
  // El detalle está explicado en LeadDetailModal.jsx.
  return (
    <div className="modal-overlay" role="presentation"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div {...ventana} className="modal-content" style={{ maxWidth: '460px', padding: '24px' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
          <div>
            <h3 id="sesion-activa-titulo" style={{ fontSize: '1.1rem', fontWeight: '700' }}>Sesión activa</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Identidad verificada por el servidor
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar la ventana de sesión"
            className="btn btn-secondary btn-sm" style={{ border: 'none', fontSize: '1rem', padding: '4px 8px' }}>
            <span aria-hidden="true">✕</span>
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
            color: 'var(--color-primary-text)',
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
            <form onSubmit={cambiar} ref={formularioDeLaContrasena}>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: 1.5 }}>
                Se pide la contraseña actual aunque ya haya iniciado sesión: es lo que impide
                que quien se haga con una sesión abierta se quede con la cuenta cambiándola.
                Al terminar se cerrarán <strong>todas</strong> sus sesiones, incluida esta.
              </p>
              {/* Las tres se nombraban con el `placeholder` y nada más —§6.4 punto 44—.
                  `axe` no se queja de eso: un marcador sí da nombre accesible al control,
                  así que la auditoría daba cero infracciones aquí. Lo que no hace es
                  quedarse: desaparece en cuanto se teclea, de modo que quien vuelve al
                  segundo campo ya no sabe si es la nueva o la repetición, y con tres cajas
                  idénticas de puntos eso no es un detalle. El marcador se queda donde dice
                  algo que la etiqueta no dice —el mínimo de doce—. */}
              <label htmlFor="sesion-actual" className="form-label">Contraseña actual</label>
              <input id="sesion-actual" type="password" className="input-field" style={{ marginBottom: '10px' }} required autoComplete="current-password"
                value={actual}
                onChange={(e) => { setActual(e.target.value); setErrores(sinElCampo(errores, 'contrasena_actual')); }}
                {...propiedadesDeCampo('contrasena_actual', errores, 'sesion')} />
              <MensajeDeCampo nombre="contrasena_actual" errores={errores} prefijo="sesion" />
              <label htmlFor="sesion-nueva" className="form-label">Contraseña nueva</label>
              <input id="sesion-nueva" type="password" className="input-field" style={{ marginBottom: '10px' }} placeholder="Mínimo 12 caracteres" required minLength={12}
                autoComplete="new-password" value={nueva}
                onChange={(e) => { setNueva(e.target.value); setErrores(sinElCampo(errores, 'nueva_contrasena')); }}
                {...propiedadesDeCampo('nueva_contrasena', errores, 'sesion')} />
              <MensajeDeCampo nombre="nueva_contrasena" errores={errores} prefijo="sesion" />
              <label htmlFor="sesion-repetida" className="form-label">Repita la contraseña nueva</label>
              <input id="sesion-repetida" type="password" className="input-field" style={{ marginBottom: '10px' }} required minLength={12}
                autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} />
              <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '10px', lineHeight: 1.5 }}>
                Una frase larga y fácil de recordar es más segura que una palabra corta con
                símbolos.
              </p>
              {/* `role="alert"` no lo tenía: era el único aviso del panel que no lo
                  llevaba, así que un lector de pantalla no decía nada al fallar el cambio
                  de contraseña. Y `white-space: pre-line` sale ahora de `.alert`, que lo
                  lleva por el mismo motivo por el que estaba aquí. */}
              {error && (
                <p role="alert" className="alert alert-error" style={{ marginBottom: '10px' }}>
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
