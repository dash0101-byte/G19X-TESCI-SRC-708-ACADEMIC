import React, { useCallback, useEffect, useState } from 'react';
import { fetchInformeDePublicacion } from '../services/api';
import { NOMBRES_DE_ETAPA, nombreDeEtapa } from '../services/actividades';
import GraficoPorDia from './GraficoPorDia';

const NOMBRE_DEL_ESTADO = { borrador: 'Borrador', activa: 'Activa', pausada: 'Pausada', cerrada: 'Cerrada' };

// Qué trajo una publicación. Arriba los tres números, debajo la tabla ordenada por score.
// Cada fila abre la ficha 360 de esa persona: el informe es el camino corto entre «este
// post funcionó» y «a quién llamo primero».
//
// Los números de arriba son los de quien pregunta, no los de la publicación: un asesor ve
// los suyos y, aparte, cuántos más hay. Los nombres del resto no llegan al navegador.
export default function InformeDePublicacion({ publicacion, onSelectLead, onCerrar }) {
  const [informe, setInforme] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [filtros, setFiltros] = useState({ etapa: '', desde: '', hasta: '' });

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      setInforme(await fetchInformeDePublicacion(publicacion.id, filtros));
    } catch (err) {
      setError(err.message);
      setInforme(null);
    } finally {
      setCargando(false);
    }
  }, [publicacion.id, filtros]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const resumen = informe && informe.resumen;
  const datos = informe && informe.publicacion;

  return (
    <section className="glass-panel" aria-labelledby="titulo-informe" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 id="titulo-informe" style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>
            Informe de «{publicacion.name}»
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Perfiles recibidos por esta publicación, del score más alto al más bajo.
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onCerrar}>
          ← Volver a publicaciones
        </button>
      </div>

      {error && (
        <div role="alert" className="alert alert-error" style={{ margin: '12px 0' }}>
          {error}
        </div>
      )}

      {datos && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '8px 0 0', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="badge" style={{ fontSize: '0.65rem' }}>{NOMBRE_DEL_ESTADO[datos.estado] || datos.estado}</span>
          <span>Responsable: {datos.responsable || 'ninguno'}</span>
          {datos.url_del_post && (
            // El enlace lo comprobó el servidor al guardarlo: es de linkedin.com por su nombre
            // de máquina. Abre en otra pestaña y sin darle a LinkedIn acceso a esta.
            <a href={datos.url_del_post} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)' }}>
              Ver el post en LinkedIn
            </a>
          )}
        </p>
      )}

      {resumen && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', margin: '16px 0' }}>
          <Dato titulo="Visitas a la página" valor={resumen.visitas} pie="Aperturas; sin datos de nadie" />
          <Dato
            titulo="Tasa de envío"
            valor={resumen.tasa_de_envio === null || resumen.tasa_de_envio === undefined ? '—' : `${resumen.tasa_de_envio} %`}
            pie={`${resumen.envios} envíos desde que se cuentan visitas`}
          />
          <Dato titulo="Perfiles recibidos" valor={resumen.perfiles_recibidos} />
          <Dato titulo="Avanzaron de etapa" valor={resumen.avanzaron_de_etapa} pie="Salieron de «Nuevo»" />
          <Dato titulo="Score medio" valor={resumen.score_medio} />
        </div>
      )}

      {informe && <GraficoPorDia dias={informe.por_dia} recortado={informe.grafico_recortado} />}

      {informe && informe.por_red && informe.por_red.length > 0 && (
        <div style={{ marginBottom: '14px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px' }}>Por red de difusión</h4>
          <table className="data-table" aria-label="Resultados por red de difusión" style={{ fontSize: '0.78rem' }}>
            <thead>
              <tr>
                <th scope="col">Red</th>
                <th scope="col">Visitas</th>
                <th scope="col">Envíos</th>
                <th scope="col">Tasa de envío</th>
                <th scope="col">Perfiles</th>
                <th scope="col">Score medio</th>
              </tr>
            </thead>
            <tbody>
              {informe.por_red.map((fila) => (
                <tr key={fila.red}>
                  <th scope="row" style={{ fontWeight: 600 }}>{fila.etiqueta}</th>
                  <td>{fila.visitas}</td>
                  <td>{fila.envios}</td>
                  {/* Sin visitas no hay tasa. Un 0 % diría que nadie escribió de los que
                      miraron, y lo que pasa es que no miró nadie. */}
                  <td>{fila.tasa_de_envio === null || fila.tasa_de_envio === undefined ? '—' : `${fila.tasa_de_envio} %`}</td>
                  <td>{fila.perfiles}</td>
                  <td>{fila.score_medio}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            «Sin red» son las aperturas y los envíos que llegaron con el enlace sin etiquetar,
            o con una etiqueta que no se reconoce.
          </p>
        </div>
      )}

      {resumen && !resumen.alcance_completo && (
        <p role="status" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
          Está viendo sus prospectos. Esta publicación trajo {resumen.de_otros_asesores} más
          {' '}que atienden otras personas.
        </p>
      )}

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '12px' }}>
        <div>
          <label htmlFor="informe-etapa" className="form-label">Etapa</label>
          <select
            id="informe-etapa"
            className="input-field"
            value={filtros.etapa}
            onChange={(e) => setFiltros({ ...filtros, etapa: e.target.value })}
          >
            <option value="">Todas</option>
            {Object.entries(NOMBRES_DE_ETAPA).map(([valor, nombre]) => (
              <option key={valor} value={valor}>{nombre}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="informe-desde" className="form-label">Desde</label>
          <input
            id="informe-desde"
            type="date"
            className="input-field"
            value={filtros.desde}
            onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })}
          />
        </div>
        <div>
          <label htmlFor="informe-hasta" className="form-label">Hasta</label>
          <input
            id="informe-hasta"
            type="date"
            className="input-field"
            value={filtros.hasta}
            onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })}
          />
        </div>
        {(filtros.etapa || filtros.desde || filtros.hasta) && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setFiltros({ etapa: '', desde: '', hasta: '' })}
          >
            Quitar filtros
          </button>
        )}
      </div>

      {cargando ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Cargando el informe...</p>
      ) : informe && informe.filas.length === 0 ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Esta publicación todavía no ha traído perfiles que usted pueda ver.
        </p>
      ) : informe ? (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <caption style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap' }}>
              Perfiles recibidos por la publicación
            </caption>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Nombre</th>
                <th scope="col" style={CELDA}>Empresa</th>
                <th scope="col" style={CELDA}>Cargo</th>
                {/* Lo que dijo necesitar. Informa al asesor; no entra en el score. */}
                <th scope="col" style={CELDA}>Necesita</th>
                <th scope="col" style={CELDA}>Score</th>
                <th scope="col" style={CELDA}>Etapa</th>
                <th scope="col" style={CELDA}>Asesor</th>
                <th scope="col" style={CELDA}>Recibido</th>
              </tr>
            </thead>
            <tbody>
              {informe.filas.map((fila) => (
                <tr
                  key={fila.lead_id}
                  style={{ borderTop: '1px solid var(--border-subtle)' }}
                >
                  <th scope="row" style={{ ...CELDA, fontWeight: '600', textAlign: 'left' }}>
                    {/* Un botón y no una fila «clicable»: así se llega con el teclado y el
                        lector de pantalla dice que abre algo. */}
                    <button
                      type="button"
                      onClick={() => onSelectLead && onSelectLead(fila.lead_id)}
                      style={{ background: 'none', border: 'none', padding: 0, color: 'var(--accent-primary)', cursor: 'pointer', font: 'inherit' }}
                    >
                      {fila.nombre}
                    </button>
                  </th>
                  <td style={CELDA}>{fila.empresa || '—'}</td>
                  <td style={CELDA}>{fila.cargo || '—'}</td>
                  <td style={CELDA}>{fila.necesidad || '—'}</td>
                  <td style={{ ...CELDA, fontFamily: 'var(--font-mono)' }}>{fila.score}</td>
                  <td style={CELDA}>{nombreDeEtapa(fila.etapa)}</td>
                  <td style={CELDA}>{fila.asesor || 'Sin asesor'}</td>
                  <td style={CELDA}>{new Date(fila.recibida_en).toLocaleDateString('es-MX')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

const CELDA = { padding: '8px 10px', verticalAlign: 'top' };

function Dato({ titulo, valor, pie }) {
  return (
    <div style={{ padding: '12px 14px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {titulo}
      </div>
      <div style={{ fontSize: '1.6rem', fontWeight: '800', fontFamily: 'var(--font-mono)' }}>{valor}</div>
      {pie && <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{pie}</div>}
    </div>
  );
}
