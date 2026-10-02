import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchSalesReps,
  fetchUsers,
  createUser,
  changeUserRole,
  deactivateUser,
  activateUser,
  resetUserPassword,
  transferPortfolio,
  getCurrentUserRole,
} from '../services/api';
import MensajeDeCampo from './MensajeDeCampo.jsx';
import {
  comoAviso,
  enfocarPrimerCampoConError,
  erroresDelServidor,
  propiedadesDeCampo,
  resumenDeCampos,
} from './erroresDeFormulario';

// Los campos del alta de una cuenta que el servidor valida uno por uno. El nombre completo
// y el teléfono tienen validador propio —el teléfono es el mismo E.164 del capítulo 32—, y
// el correo repetido contesta 409, no 422: ese sigue yendo al aviso de arriba, porque no es
// un campo mal escrito sino una cuenta que ya existe.
const CAMPOS_DEL_ALTA = ['full_name', 'email', 'password', 'phone', 'capacity'];

const ETIQUETAS_DEL_ALTA = {
  full_name: 'Nombre completo',
  email: 'Correo institucional',
  password: 'Contraseña inicial',
  phone: 'Teléfono',
  capacity: 'Capacidad de cartera',
};

const PROPIOS_DEL_ALTA = { email: 'Escriba un correo con la forma nombre@plurione.com.' };

// Roles del sistema, con el nombre que se enseña. Coinciden uno a uno con `UserRole` del
// backend; no hay etiquetas inventadas como las que tenía antes este componente
// ("Asesor Comercial Senior", "Administrador TI"), que no existían en ninguna parte y
// solo servían para que la pantalla pareciera llena.
const ROLES = [
  { valor: 'Commercial_Executive', etiqueta: 'Asesor Comercial' },
  { valor: 'Sales_Lead', etiqueta: 'Líder Comercial' },
  { valor: 'System_Admin', etiqueta: 'Administrador de Sistemas' },
];

const etiquetaDeRol = (valor) => ROLES.find((r) => r.valor === valor)?.etiqueta || valor;

const ALTA_VACIA = {
  email: '',
  full_name: '',
  role: 'Commercial_Executive',
  password: '',
  is_sales_rep: true,
  phone: '',
  capacity: 50,
};

/**
 * Panel de administración.
 *
 * Antes esta pantalla mostraba un array de tres personas escrito dentro del propio
 * componente —con roles que no existían en el backend— y, para rellenar la columna de
 * "leads activos", lanzaba una petición al listado de prospectos por cada una: tantas
 * consultas como personas en el equipo, cada una trayendo una página entera de prospectos
 * para leer un único número. Y todo ello contra unos identificadores fijos que no tenían
 * por qué corresponder con nadie real.
 *
 * Ahora hay endpoints de verdad. `/sales-reps` devuelve el equipo con su carga ya contada
 * en una sola consulta agregada, y `/users` permite dar de alta, cambiar de rol, dar de
 * baja y restablecer contraseñas sin entrar al servidor.
 */
export default function AdminPanel({ onBatchRecalculate, isRecalculating }) {
  const esAdministrador = getCurrentUserRole() === 'System_Admin';

  const [asesores, setAsesores] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [mostrarInactivos, setMostrarInactivos] = useState(false);
  const [alta, setAlta] = useState(ALTA_VACIA);
  const [creando, setCreando] = useState(false);
  const [ocupado, setOcupado] = useState(null);
  const [enBajas, setEnBajas] = useState(0);
  const [destinoDe, setDestinoDe] = useState({});
  const [erroresDelAlta, setErroresDelAlta] = useState({});
  const formularioDelAltaRef = useRef(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      // Dos llamadas en paralelo, no una por persona. El administrador ve además las
      // cuentas que no atienden cartera; el líder comercial solo el equipo.
      const peticiones = [fetchSalesReps({ incluirInactivos: mostrarInactivos })];
      if (esAdministrador) {
        peticiones.push(fetchUsers({ incluirInactivos: mostrarInactivos }));
      }
      const [equipo, usuarios] = await Promise.all(peticiones);
      setAsesores(equipo?.items || []);
      setEnBajas(equipo?.prospectos_en_cuentas_de_baja || 0);
      setCuentas(usuarios?.items || []);
    } catch (err) {
      // Se muestra el fallo en lugar de sustituirlo por datos inventados. La versión
      // anterior caía en un array fijo cuando la API no respondía, de modo que la pantalla
      // seguía enseñando un equipo plausible aunque el backend estuviera caído.
      setError(err.message || 'No se pudo cargar la administración de cuentas.');
      setAsesores([]);
      setEnBajas(0);
      setCuentas([]);
    } finally {
      setCargando(false);
    }
  }, [mostrarInactivos, esAdministrador]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // `alFallar` deja que quien llama se quede con el error si sabe hacer algo mejor que
  // volcarlo en el aviso de arriba —repartirlo por campos, por ejemplo—. Devuelve `true` si
  // lo ha hecho; si no, el aviso general sigue siendo la salida.
  const conAviso = async (accion, mensajeExito, alFallar = null) => {
    setError(null);
    setAviso(null);
    try {
      await accion();
      setAviso(mensajeExito);
      await cargar();
    } catch (err) {
      if (!(alFallar && alFallar(err))) {
        setError(err.message || 'La operación no se pudo completar.');
      }
    } finally {
      setOcupado(null);
    }
  };

  const conErrorDelAlta = (nombre) => propiedadesDeCampo(nombre, erroresDelAlta, 'alta');
  const mensajeDelAlta = (nombre) => (
    <MensajeDeCampo nombre={nombre} errores={erroresDelAlta} prefijo="alta" />
  );

  // El 422 del alta, repartido por campos. Antes se volcaba entero en el aviso de arriba,
  // que decía «full_name: String should have at least 2 characters»: el nombre de la
  // columna y el idioma de Pydantic, en una pantalla escrita en castellano.
  const repartirErrorDelAlta = (err) => {
    if (err.status !== 422) return false;
    const repartidos = erroresDelServidor(err.detalle, {
      propios: PROPIOS_DEL_ALTA, campos: CAMPOS_DEL_ALTA,
    });
    if (!repartidos || !Object.keys(repartidos.porCampo).length) return false;
    setErroresDelAlta(repartidos.porCampo);
    setError(comoAviso([
      resumenDeCampos(repartidos.porCampo, ETIQUETAS_DEL_ALTA),
      ...repartidos.sueltos,
    ]));
    enfocarPrimerCampoConError(formularioDelAltaRef, repartidos.porCampo, CAMPOS_DEL_ALTA);
    return true;
  };

  const enviarAlta = async (evento) => {
    evento.preventDefault();
    setCreando(true);
    setErroresDelAlta({});
    await conAviso(async () => {
      const datos = {
        email: alta.email.trim(),
        full_name: alta.full_name.trim(),
        role: alta.role,
        password: alta.password,
        is_sales_rep: alta.is_sales_rep,
        phone: alta.phone.trim() || null,
        capacity: alta.is_sales_rep ? Number(alta.capacity) || 50 : null,
      };
      await createUser(datos);
      setAlta(ALTA_VACIA);
    },
    'Cuenta creada. La persona deberá cambiar la contraseña en su primer acceso.',
    repartirErrorDelAlta);
    setCreando(false);
  };

  const cambiarRol = (usuario, rol) =>
    conAviso(
      () => {
        setOcupado(usuario.id);
        return changeUserRole(usuario.id, rol);
      },
      `Rol de ${usuario.full_name} cambiado a ${etiquetaDeRol(rol)}. Sus sesiones se han cerrado.`,
    );

  const alternarActividad = (usuario) =>
    conAviso(
      () => {
        setOcupado(usuario.id);
        return usuario.is_active ? deactivateUser(usuario.id) : activateUser(usuario.id);
      },
      usuario.is_active
        ? `${usuario.full_name} queda dado de baja. Conserva sus prospectos hasta que se repartan desde el equipo comercial.`
        : `${usuario.full_name} vuelve a tener acceso y deberá fijar una contraseña nueva.`,
    );

  const restablecer = (usuario) => {
    const nueva = window.prompt(
      `Contraseña nueva para ${usuario.full_name}.\n\n` +
        'Mínimo 12 caracteres. Una frase larga y fácil de recordar es mejor que una ' +
        'palabra corta con símbolos.\n\n' +
        'Se cerrarán todas sus sesiones y tendrá que cambiarla al entrar.',
    );
    if (!nueva) return;
    conAviso(
      () => {
        setOcupado(usuario.id);
        return resetUserPassword(usuario.id, nueva);
      },
      `Contraseña de ${usuario.full_name} restablecida. Sus sesiones se han cerrado.`,
    );
  };

  // La cartera de una cuenta dada de baja. La baja la conserva a su nombre a propósito
  // —repartirla sola sería decidir sin nadie que decida—, así que alguien tiene que
  // repartirla, y para eso primero tiene que verla. Solo se ofrecen como destino las
  // cuentas activas: traspasar a otra baja movería el problema sin resolverlo.
  const activosQueAtienden = asesores.filter((rep) => rep.is_active);

  const repartir = (rep) => {
    const destinoId = Number(destinoDe[rep.id]);
    const destino = activosQueAtienden.find((a) => a.id === destinoId);
    if (!destino) return;
    conAviso(
      () => {
        setOcupado(rep.id);
        return transferPortfolio(rep.id, destinoId);
      },
      `${rep.leads_asignados} prospectos de ${rep.full_name} pasan a ${destino.full_name}.`,
    );
  };

  const tarjeta = { padding: '24px', background: 'var(--bg-panel, transparent)' };
  const etiqueta = {
    display: 'block',
    fontSize: '0.72rem',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    marginBottom: '4px',
  };
  const campo = {
    width: '100%',
    padding: '8px 10px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border-subtle)',
    background: 'var(--bg-base)',
    color: 'var(--text-primary)',
    fontSize: '0.85rem',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', marginBottom: '32px' }}>

      {/* Encabezado */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '700' }}>Panel de Administración y Control Algorítmico</h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            Cuentas, equipo comercial y mantenimiento del modelo de scoring
          </p>
        </div>
        <span className="badge" style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
          🛡️ Área Restringida (Admin / Líder)
        </span>
      </div>

      {/* `role="alert"` cuando es un fallo y `role="status"` cuando no: un error anunciado
          como estado espera a que el lector de pantalla acabe lo que esté diciendo, y lo
          que avisa de que una operación no se hizo no puede esperar. Y la clase de la hoja
          en vez de seis propiedades en línea, como el resto de los avisos. */}
      {(error || aviso) && (
        <div
          role={error ? 'alert' : 'status'}
          className={`alert ${error ? 'alert-error' : 'alert-ok'}`}
        >
          {error || aviso}
        </div>
      )}

      {/* Mantenimiento del modelo */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px' }}>
        <div className="glass-panel" style={{ ...tarjeta, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <span style={{ fontSize: '1.25rem' }}>⏱️</span>
              <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>Mantenimiento de Decaimiento Temporal</h3>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: '1.5' }}>
              Aplica la función de atenuación continua <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>γ(Δt) = (0.5)^(Δt / 14)</code> a la totalidad de prospectos en base de datos,
              penalizando a los que llevan días sin interactuar.
            </p>
            <div style={{ background: 'var(--bg-base)', padding: '12px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '20px' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Fórmula del Algoritmo Híbrido:</div>
              <div style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: '4px' }}>
                Score = 0.60 × S_ML + 0.40 × S_Heurístico × (0.5)^(Δt / 14)
              </div>
            </div>
          </div>
          <div>
            <button onClick={onBatchRecalculate} disabled={isRecalculating} className="btn btn-primary" style={{ width: '100%', padding: '12px' }}>
              {isRecalculating ? '⏳ Aplicando atenuación a todos los prospectos...' : '🔄 Ejecutar Recálculo de Decaimiento en Lote'}
            </button>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '8px' }}>
              Queda registrado en la bitácora de auditoría con quién lo solicitó.
            </div>
          </div>
        </div>

        <div className="glass-panel" style={tarjeta}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <span style={{ fontSize: '1.25rem' }}>⚖️</span>
            <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>Parámetros de Calibración del Sistema</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {[
              ['Peso ML Supervisado', '60%', 'GradientBoosting Calibrado', 'var(--text-primary)'],
              ['Peso Heurístico ICP', '40%', 'Perfil de Cliente Ideal', 'var(--warm-text)'],
              ['Vida Media (Decaimiento)', '14 días', 'Pérdida del 50% de fuerza', 'var(--text-primary)'],
              ['Umbral Lead HOT', '≥ 75 pts', 'Prioridad crítica de contacto', 'var(--hot-text)'],
            ].map(([titulo, valor, pie, color]) => (
              <div key={titulo} style={{ background: 'var(--bg-base)', padding: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{titulo}</div>
                <div style={{ fontSize: '1.3rem', fontWeight: '800', fontFamily: 'var(--font-mono)', color, marginTop: '2px' }}>{valor}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{pie}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>ℹ️</span>
            <span>Para modificar estos coeficientes, actualice las variables correspondientes en el archivo <code style={{ fontFamily: 'var(--font-mono)' }}>.env</code>.</span>
          </div>
        </div>
      </div>

      {/* Equipo comercial */}
      <div className="glass-panel" style={tarjeta}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: '700' }}>Equipo Comercial y Carga de Trabajo</h3>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <input
              type="checkbox"
              checked={mostrarInactivos}
              onChange={(e) => setMostrarInactivos(e.target.checked)}
            />
            Incluir cuentas dadas de baja
          </label>
        </div>

        {cargando && <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Cargando equipo…</p>}

        {/* Se cuenta siempre, también con las bajas ocultas: es en esa vista por defecto
            donde la cartera de quien se fue dejaba de verse. */}
        {!cargando && enBajas > 0 && (
          <div
            role="alert"
            style={{
              padding: '10px 14px',
              marginBottom: '12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--warm-text)',
              color: 'var(--warm-text)',
              fontSize: '0.8rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '12px',
              flexWrap: 'wrap',
            }}
          >
            <span>
              {enBajas === 1 ? 'Hay 1 prospecto asignado' : `Hay ${enBajas} prospectos asignados`} a
              cuentas dadas de baja. Nadie los está atendiendo hasta que se repartan.
            </span>
            {!mostrarInactivos && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setMostrarInactivos(true)}>
                Ver cuentas de baja
              </button>
            )}
          </div>
        )}

        {!cargando && asesores.length === 0 && !error && (
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            No hay ninguna cuenta marcada como asesora. Los prospectos calientes no se
            podrán asignar automáticamente hasta que exista al menos una.
          </p>
        )}

        {!cargando && asesores.length > 0 && (
          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Asesor</th>
                  <th>Correo</th>
                  <th>Rol</th>
                  <th>Capacidad</th>
                  <th>Prospectos asignados</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {asesores.map((rep) => {
                  const saturado = rep.capacity && rep.leads_asignados > rep.capacity;
                  return (
                    <tr key={rep.id}>
                      <td style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{rep.full_name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{rep.email}</td>
                      <td><span className="badge badge-status">{etiquetaDeRol(rep.role)}</span></td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{rep.capacity ?? '—'}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: saturado ? 'var(--hot-text)' : 'var(--text-primary)' }}>
                        {rep.leads_asignados}
                        {saturado && <span title="Por encima de su capacidad declarada"> ⚠</span>}
                      </td>
                      <td>
                        <span
                          className="badge"
                          style={
                            rep.is_active
                              ? { background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)' }
                              : { background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }
                          }
                        >
                          ● {rep.is_active ? 'Activo' : 'De baja'}
                        </span>
                        {!rep.is_active && rep.leads_asignados > 0 && (
                          <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                            <select
                              aria-label={`Asesor que recibe la cartera de ${rep.full_name}`}
                              style={{ ...campo, padding: '4px 6px', fontSize: '0.75rem' }}
                              value={destinoDe[rep.id] || ''}
                              disabled={ocupado === rep.id}
                              onChange={(e) => setDestinoDe({ ...destinoDe, [rep.id]: e.target.value })}
                            >
                              <option value="">Repartir a…</option>
                              {activosQueAtienden.map((a) => (
                                <option key={a.id} value={a.id}>{a.full_name}</option>
                              ))}
                            </select>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={!destinoDe[rep.id] || ocupado === rep.id}
                              onClick={() => repartir(rep)}
                            >
                              Repartir
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Cuentas: solo el administrador */}
      {esAdministrador && (
        <>
          <div className="glass-panel" style={tarjeta}>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '4px' }}>Alta de cuenta</h3>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
              La persona tendrá que cambiar esta contraseña en su primer acceso: mientras la
              conozca alguien más, la cuenta no identifica a nadie.
            </p>
            <form onSubmit={enviarAlta} ref={formularioDelAltaRef} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', alignItems: 'end' }}>
              <div>
                <label style={etiqueta} htmlFor="alta-nombre">Nombre completo</label>
                <input id="alta-nombre" style={campo} required minLength={2} value={alta.full_name}
                  onChange={(e) => setAlta({ ...alta, full_name: e.target.value })}
                  {...conErrorDelAlta('full_name')} />
                {mensajeDelAlta('full_name')}
              </div>
              <div>
                <label style={etiqueta} htmlFor="alta-email">Correo institucional</label>
                <input id="alta-email" type="email" style={campo} required value={alta.email}
                  onChange={(e) => setAlta({ ...alta, email: e.target.value })}
                  {...conErrorDelAlta('email')} />
                {mensajeDelAlta('email')}
              </div>
              <div>
                <label style={etiqueta} htmlFor="alta-rol">Rol</label>
                <select id="alta-rol" style={campo} value={alta.role}
                  onChange={(e) => setAlta({ ...alta, role: e.target.value })}>
                  {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
                </select>
              </div>
              <div>
                <label style={etiqueta} htmlFor="alta-pass">Contraseña inicial (mín. 12)</label>
                <input id="alta-pass" type="password" style={campo} required minLength={12} value={alta.password}
                  onChange={(e) => setAlta({ ...alta, password: e.target.value })}
                  {...conErrorDelAlta('password')} />
                {mensajeDelAlta('password')}
              </div>
              <div>
                <label style={etiqueta} htmlFor="alta-tel">Teléfono (opcional)</label>
                <input id="alta-tel" style={campo} value={alta.phone}
                  onChange={(e) => setAlta({ ...alta, phone: e.target.value })}
                  {...conErrorDelAlta('phone')} />
                {mensajeDelAlta('phone')}
              </div>
              <div>
                <label style={etiqueta} htmlFor="alta-cap">Capacidad de cartera</label>
                <input id="alta-cap" type="number" min={1} max={1000} style={campo} disabled={!alta.is_sales_rep}
                  value={alta.capacity} onChange={(e) => setAlta({ ...alta, capacity: e.target.value })}
                  {...conErrorDelAlta('capacity')} />
                {mensajeDelAlta('capacity')}
              </div>
              <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input type="checkbox" checked={alta.is_sales_rep}
                  onChange={(e) => setAlta({ ...alta, is_sales_rep: e.target.checked })} />
                Atiende cartera
              </label>
              <button type="submit" className="btn btn-primary" disabled={creando} style={{ padding: '10px' }}>
                {creando ? 'Creando…' : 'Crear cuenta'}
              </button>
            </form>
          </div>

          <div className="glass-panel" style={tarjeta}>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '12px' }}>Cuentas del sistema</h3>
            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Persona</th>
                    <th>Correo</th>
                    <th>Rol</th>
                    <th>Contraseña</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {cuentas.map((usuario) => (
                    <tr key={usuario.id}>
                      <td style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                        {usuario.full_name}
                        {usuario.is_sales_rep && <span title="Atiende cartera"> 💼</span>}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{usuario.email}</td>
                      <td>
                        <select
                          style={{ ...campo, padding: '4px 6px', fontSize: '0.78rem' }}
                          value={usuario.role}
                          disabled={ocupado === usuario.id}
                          onChange={(e) => cambiarRol(usuario, e.target.value)}
                        >
                          {ROLES.map((r) => <option key={r.valor} value={r.valor}>{r.etiqueta}</option>)}
                        </select>
                      </td>
                      <td style={{ fontSize: '0.75rem', color: usuario.must_change_password ? 'var(--warm-text)' : 'var(--text-muted)' }}>
                        {usuario.must_change_password ? 'Pendiente de cambio' : 'Propia'}
                      </td>
                      <td>
                        <span
                          className="badge"
                          style={
                            usuario.is_active
                              ? { background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)' }
                              : { background: 'var(--bg-subtle)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }
                          }
                        >
                          ● {usuario.is_active ? 'Activa' : 'De baja'}
                        </span>
                      </td>
                      <td style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button type="button" className="btn" style={{ fontSize: '0.72rem', padding: '4px 8px' }}
                          disabled={ocupado === usuario.id} onClick={() => restablecer(usuario)}>
                          Restablecer contraseña
                        </button>
                        <button type="button" className="btn" style={{ fontSize: '0.72rem', padding: '4px 8px' }}
                          disabled={ocupado === usuario.id} onClick={() => alternarActividad(usuario)}>
                          {usuario.is_active ? 'Dar de baja' : 'Reactivar'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '12px' }}>
              Dar de baja no borra la cuenta: deja de entrar y de recibir prospectos, pero
              conserva los que atendía y su rastro en la bitácora. Todas estas operaciones
              quedan registradas.
            </p>
          </div>
        </>
      )}

      {/* Estado de servicios */}
      <div className="glass-panel" style={tarjeta}>
        <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '12px' }}>
          Monitoreo de Servicios e Integración CRM
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
          {[
            ['Webhook Ingest API', '/api/v1/crm/webhook'],
            ['Motor de Inferencia ML', 'ROC-AUC 0.9408'],
            ['Base de Datos Relacional', 'SQLAlchemy 2.0'],
          ].map(([titulo, detalle]) => (
            <div key={titulo} style={{ background: 'var(--bg-base)', padding: '14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: '600' }}>{titulo}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                <code style={{ fontFamily: 'var(--font-mono)' }}>{detalle}</code>
              </div>
            </div>
          ))}
        </div>
        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '12px' }}>
          Estos tres bloques describen la configuración desplegada, no comprueban que los
          servicios respondan. El estado real se consulta en <code style={{ fontFamily: 'var(--font-mono)' }}>/health</code>.
        </p>
      </div>

    </div>
  );
}
