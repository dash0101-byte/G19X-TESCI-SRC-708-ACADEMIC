import React, { useCallback, useEffect, useState } from 'react';
import {
  descartarEventoSinAsociar,
  fetchEventosSinAsociar,
  fetchLeads,
  vincularEventoSinAsociar,
} from '../services/api';
import {
  DIRECCIONES,
  RESULTADOS_DE_LLAMADA,
  describirCambioDeScore,
  nombreDeActividad,
  nombreDeFuente,
} from '../services/actividades';

// Avisos de las integraciones que llegaron sin ficha a la que pertenecer. Antes, cualquier
// correo desconocido creaba un prospecto con industria y tamaño inventados; ahora solo lo
// crean los formularios, LinkedIn Lead Gen y el CRM, y el resto espera aquí a que alguien
// lo vincule o lo descarte. La atienden quienes dirigen la cartera.
export default function BandejaSinAsociar() {
  const [eventos, setEventos] = useState([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const [enVinculacion, setEnVinculacion] = useState(null);
  const [busqueda, setBusqueda] = useState('');
  const [candidatos, setCandidatos] = useState([]);
  const [prospectoElegido, setProspectoElegido] = useState('');
  const [trabajando, setTrabajando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const datos = await fetchEventosSinAsociar();
      setEventos(datos.items || []);
      setTotal(datos.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrirVinculacion = (evento) => {
    setEnVinculacion(evento.id);
    setBusqueda(evento.contact_email || evento.contact_name || '');
    setCandidatos([]);
    setProspectoElegido('');
    setAviso('');
    setError('');
  };

  const buscar = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const datos = await fetchLeads({ search: busqueda, limit: 10 });
      const encontrados = (datos && datos.items) || [];
      setCandidatos(encontrados);
      setProspectoElegido(encontrados.length ? String(encontrados[0].id) : '');
    } catch (err) {
      setError(err.message);
    }
  };

  const vincular = async (e) => {
    e.preventDefault();
    if (!prospectoElegido) return;
    setTrabajando(true);
    setError('');
    try {
      const registrada = await vincularEventoSinAsociar(enVinculacion, Number(prospectoElegido));
      setAviso(`Aviso vinculado. Score del prospecto: ${describirCambioDeScore(registrada)}`);
      setEnVinculacion(null);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setTrabajando(false);
    }
  };

  const descartar = async (evento) => {
    if (!window.confirm('¿Descartar este aviso? Se borra y no queda nada de él salvo el registro en la bitácora.')) return;
    setTrabajando(true);
    setError('');
    try {
      await descartarEventoSinAsociar(evento.id);
      setAviso('Aviso descartado.');
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setTrabajando(false);
    }
  };

  return (
    <section className="glass-panel" aria-labelledby="titulo-bandeja-sin-asociar" style={{ padding: '20px', marginTop: '20px' }}>
      <h3 id="titulo-bandeja-sin-asociar" style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '4px' }}>
        Bandeja «Sin asociar» ({total})
      </h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
        Avisos de las integraciones que no pertenecen a ninguna ficha. Al vincularlos se registran como actividad del
        prospecto y cuentan para su score; al descartarlos se borran.
      </p>

      {aviso && (
        <div role="status" style={{ padding: '8px 12px', marginBottom: '12px', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 'var(--radius-sm)', color: 'var(--success-text)', fontSize: '0.8rem' }}>
          {aviso}
        </div>
      )}
      {error && (
        <div role="alert" style={{ padding: '8px 12px', marginBottom: '12px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', color: 'var(--hot-text)', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      {cargando ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Cargando la bandeja...</p>
      ) : eventos.length === 0 ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No hay avisos pendientes.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {eventos.map((evento) => (
            <li key={evento.id} style={{ padding: '10px 12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                <div>
                  <strong>{nombreDeActividad(evento.activity_type)}</strong>
                  <span style={{ color: 'var(--text-muted)' }}>
                    {' '}• {nombreDeFuente(evento.source)}
                    {evento.direction && ` • ${DIRECCIONES[evento.direction] || evento.direction}`}
                    {evento.call_outcome && ` • ${RESULTADOS_DE_LLAMADA[evento.call_outcome] || evento.call_outcome}`}
                    {' '}• {new Date(evento.occurred_at).toLocaleString('es-MX')}
                  </span>
                  <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {[evento.contact_name, evento.contact_email, evento.contact_phone].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <button type="button" className="btn btn-primary btn-sm" disabled={trabajando} onClick={() => abrirVinculacion(evento)}>
                    Vincular
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={trabajando} onClick={() => descartar(evento)}>
                    Descartar
                  </button>
                </div>
              </div>

              {enVinculacion === evento.id && (
                <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)' }}>
                  <form onSubmit={buscar} style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '200px' }}>
                      <label htmlFor={`bandeja-busqueda-${evento.id}`} style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                        Buscar prospecto (nombre, correo o empresa):
                      </label>
                      <input
                        id={`bandeja-busqueda-${evento.id}`}
                        type="text"
                        className="input-field"
                        value={busqueda}
                        onChange={(e) => setBusqueda(e.target.value)}
                      />
                    </div>
                    <button type="submit" className="btn btn-secondary btn-sm">Buscar</button>
                  </form>

                  {candidatos.length > 0 && (
                    <form onSubmit={vincular} style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '8px' }}>
                      <div style={{ flex: 1, minWidth: '200px' }}>
                        <label htmlFor={`bandeja-prospecto-${evento.id}`} style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                          Prospecto al que pertenece:
                        </label>
                        <select
                          id={`bandeja-prospecto-${evento.id}`}
                          className="input-field"
                          value={prospectoElegido}
                          onChange={(e) => setProspectoElegido(e.target.value)}
                        >
                          {candidatos.map((lead) => (
                            <option key={lead.id} value={lead.id}>
                              {[`${lead.first_name} ${lead.last_name}`.trim(), lead.email, lead.company].filter(Boolean).join(' · ')}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button type="submit" className="btn btn-primary btn-sm" disabled={trabajando || !prospectoElegido}>
                        Confirmar vinculación
                      </button>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEnVinculacion(null)}>
                        Cancelar
                      </button>
                    </form>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
