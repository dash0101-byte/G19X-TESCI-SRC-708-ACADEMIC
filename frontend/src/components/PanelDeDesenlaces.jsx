import React, { useCallback, useEffect, useState } from 'react';
import { fetchPanelDeDesenlaces } from '../services/api';

// Qué se gana, qué se pierde y por qué. La pantalla del líder.
//
// Hasta el capítulo 30 el sistema sabía cuántos prospectos se ganaban y era incapaz de
// decir qué se pierde por precio y qué se pierde por plazo, que es la única de las dos
// preguntas que cambia lo que alguien hace mañana.
//
// Aquí no hay ni una fila con nombre. Todo son totales: por motivo, por publicación, por
// red y por la categoría que tenía el prospecto **al cerrarse**. Quien necesita ver a las
// personas tiene el listado y la ficha, donde ese acceso queda registrado como lo que es.
//
// Cada tasa va acompañada del número de casos que hay detrás, y no por adorno: con doce
// cierres, cualquier conclusión sobre la calidad del modelo es una anécdota con decimales.

const PORCENTAJE = (valor) => (valor === null || valor === undefined ? '—' : `${valor} %`);
const NUMERO = (valor) => (valor === null || valor === undefined ? '—' : valor);

const CELDA = { padding: '7px 10px', verticalAlign: 'top' };

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

function Reentrenamiento({ datos }) {
  // El contador. No es un botón: este capítulo no reentrena nada y no toca el artefacto.
  // Dice cuánto falta, que hasta ahora no se podía saber sin abrir la base a mano.
  const faltan = [
    datos.faltan_casos > 0 ? `${datos.faltan_casos} cierres` : null,
    datos.faltan_ganados > 0 ? `${datos.faltan_ganados} ganados` : null,
    datos.faltan_perdidos > 0 ? `${datos.faltan_perdidos} perdidos` : null,
  ].filter(Boolean);

  return (
    <section
      aria-labelledby="titulo-reentrenamiento"
      style={{ marginTop: '18px', paddingTop: '14px', borderTop: '1px solid var(--border-subtle)' }}
    >
      <h3 id="titulo-reentrenamiento" style={{ fontSize: '0.9rem', fontWeight: '700', marginBottom: '2px' }}>
        Cuánto falta para poder reentrenar
      </h3>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Este contador no se filtra por fechas: el modelo se entrenaría con todo lo que hay.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div
          role="progressbar"
          aria-valuenow={datos.utilizables}
          aria-valuemin={0}
          aria-valuemax={datos.minimo_de_casos}
          aria-label="Cierres utilizables frente al mínimo exigido"
          style={{ flex: '1 1 220px', height: '10px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}
        >
          <div
            style={{
              width: `${Math.min(100, Math.round((datos.utilizables / datos.minimo_de_casos) * 100))}%`,
              height: '100%',
              background: datos.alcanzado ? 'var(--hot-text)' : 'var(--accent-primary)',
            }}
          />
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
          {datos.utilizables} / {datos.minimo_de_casos}
        </span>
      </div>

      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: '8px 0 0' }}>
        {datos.alcanzado ? (
          <>
            Ya hay desenlaces suficientes ({datos.ganados_utilizables} ganados y{' '}
            {datos.perdidos_utilizables} perdidos, mínimo {datos.minimo_por_clase} de cada).
            {' '}Reentrenar sigue siendo una decisión de una persona: el sistema no lo hace solo.
          </>
        ) : (
          <>Faltan {faltan.join(', ')} para alcanzar el mínimo.</>
        )}
      </p>

      {(datos.sin_instantanea > 0 || datos.de_un_vector_anterior > 0) && (
        // La merma, a la vista. Un contador que solo enseñara los utilizables escondería
        // que de trescientos cierres solo sirven ciento veinte.
        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '6px 0 0' }}>
          De los {datos.cerrados} cierres registrados, {datos.sin_instantanea} no tienen
          instantánea de entrada y {datos.de_un_vector_anterior} la tienen de una versión
          anterior del vector (la vigente es la {datos.version_del_vector}). Esos no se
          pueden usar sin inventar lo que no dicen.
        </p>
      )}
    </section>
  );
}

export default function PanelDeDesenlaces() {
  const [panel, setPanel] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [filtros, setFiltros] = useState({ desde: '', hasta: '' });

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      setPanel(await fetchPanelDeDesenlaces(filtros));
    } catch (err) {
      setError(err.message);
      setPanel(null);
    } finally {
      setCargando(false);
    }
  }, [filtros]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const resumen = panel && panel.resumen;

  return (
    <section className="glass-panel" aria-labelledby="titulo-desenlaces" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 id="titulo-desenlaces" style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>
            Desenlaces
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Qué se gana, qué se pierde y por qué. Totales; ninguna fila lleva a una persona.
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={cargar} disabled={cargando}>
          {cargando ? 'Cargando…' : 'Actualizar'}
        </button>
      </div>

      {error && (
        <div role="alert" style={{ padding: '8px 12px', margin: '12px 0', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', color: 'var(--error-text)', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end', margin: '14px 0' }}>
        <div>
          <label htmlFor="desenlaces-desde" className="form-label">Cerrados desde</label>
          <input
            id="desenlaces-desde"
            type="date"
            className="input-field"
            value={filtros.desde}
            onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })}
          />
        </div>
        <div>
          <label htmlFor="desenlaces-hasta" className="form-label">Hasta</label>
          <input
            id="desenlaces-hasta"
            type="date"
            className="input-field"
            value={filtros.hasta}
            onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })}
          />
        </div>
        {(filtros.desde || filtros.hasta) && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setFiltros({ desde: '', hasta: '' })}>
            Quitar filtros
          </button>
        )}
      </div>

      {resumen && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' }}>
          <Dato titulo="Cerrados" valor={resumen.cerrados} pie="Con motivo registrado" />
          <Dato titulo="Ganados" valor={resumen.ganados} />
          <Dato titulo="Perdidos" valor={resumen.perdidos} />
          {/* Sin cierres no hay tasa. Un 0 % diría que no se gana ninguno, y lo que pasa
              es que todavía no ha cerrado ninguno. */}
          <Dato titulo="Tasa de ganados" valor={PORCENTAJE(resumen.tasa_de_ganados)} pie={`sobre ${resumen.cerrados} cierres`} />
          <Dato
            titulo="Score medio"
            valor={`${NUMERO(resumen.score_medio_de_los_ganados)} / ${NUMERO(resumen.score_medio_de_los_perdidos)}`}
            pie="ganados / perdidos, al cerrarse"
          />
        </div>
      )}

      {panel && panel.resumen.cerrados === 0 && !cargando && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Todavía no hay ningún prospecto cerrado con su motivo en este periodo. Los cierres
          anteriores al capítulo 30 no tienen motivo y no aparecen aquí: inventárselo habría
          llenado el panel de una respuesta que nadie dio.
        </p>
      )}

      {panel && panel.por_motivo.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>Por motivo</h3>
          <table className="data-table" aria-label="Cierres por motivo" style={{ fontSize: '0.78rem', width: '100%' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Desenlace</th>
                <th scope="col" style={CELDA}>Motivo</th>
                <th scope="col" style={CELDA}>Casos</th>
                <th scope="col" style={CELDA}>% de su desenlace</th>
                <th scope="col" style={CELDA}>Score medio</th>
              </tr>
            </thead>
            <tbody>
              {panel.por_motivo.map((fila) => (
                <tr key={`${fila.resultado}:${fila.motivo}`} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <td style={CELDA}>{fila.resultado_etiqueta}</td>
                  <th scope="row" style={{ ...CELDA, fontWeight: 600, textAlign: 'left' }}>{fila.motivo_etiqueta}</th>
                  <td style={CELDA}>{fila.casos}</td>
                  <td style={CELDA}>{PORCENTAJE(fila.porcentaje)}</td>
                  <td style={{ ...CELDA, fontFamily: 'var(--font-mono)' }}>{NUMERO(fila.score_medio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            El porcentaje es sobre los de su propio desenlace: «de lo que perdemos, cuánto se
            va por precio». Si «Otro motivo» crece, la lista está mal y hay que discutirla.
          </p>
        </div>
      )}

      {panel && panel.acierto_del_score.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>¿Acertaba el score?</h3>
          <table className="data-table" aria-label="Cierres por categoría de score al cerrarse" style={{ fontSize: '0.78rem', width: '100%' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Categoría al cerrarse</th>
                <th scope="col" style={CELDA}>Casos</th>
                <th scope="col" style={CELDA}>Ganados</th>
                <th scope="col" style={CELDA}>Perdidos</th>
                <th scope="col" style={CELDA}>Tasa de ganados</th>
              </tr>
            </thead>
            <tbody>
              {panel.acierto_del_score.map((fila) => (
                <tr key={fila.categoria} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <th scope="row" style={{ ...CELDA, fontWeight: 600, textAlign: 'left' }}>{fila.categoria}</th>
                  <td style={CELDA}>{fila.casos}</td>
                  <td style={CELDA}>{fila.ganados}</td>
                  <td style={CELDA}>{fila.perdidos}</td>
                  <td style={CELDA}>{PORCENTAJE(fila.tasa_de_ganados)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Si el score acierta, los HOT se ganan más que los COLD. Mire primero la columna
            de casos: con pocos cierres esta tabla no concluye nada.
          </p>
        </div>
      )}

      {panel && panel.por_publicacion.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>Por publicación</h3>
          <table className="data-table" aria-label="Cierres por publicación" style={{ fontSize: '0.78rem', width: '100%' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Publicación</th>
                <th scope="col" style={CELDA}>Ganados</th>
                <th scope="col" style={CELDA}>Perdidos</th>
                <th scope="col" style={CELDA}>Tasa de ganados</th>
                <th scope="col" style={CELDA}>Score medio</th>
              </tr>
            </thead>
            <tbody>
              {panel.por_publicacion.map((fila) => (
                <tr key={fila.publicacion_id ?? 'sin-publicacion'} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <th scope="row" style={{ ...CELDA, fontWeight: 600, textAlign: 'left' }}>{fila.titulo}</th>
                  <td style={CELDA}>{fila.ganados}</td>
                  <td style={CELDA}>{fila.perdidos}</td>
                  <td style={CELDA}>{PORCENTAJE(fila.tasa_de_ganados)}</td>
                  <td style={{ ...CELDA, fontFamily: 'var(--font-mono)' }}>{NUMERO(fila.score_medio_al_cierre)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Cada cierre cuenta una sola vez, en la publicación por la que llegó esa persona.
            El informe de cada publicación cuenta distinto —allí cada post ve a todo el que
            le respondió— porque responde a otra pregunta.
          </p>
        </div>
      )}

      {panel && panel.por_red.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>Por red de difusión</h3>
          <table className="data-table" aria-label="Cierres por red de difusión" style={{ fontSize: '0.78rem', width: '100%' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Red</th>
                <th scope="col" style={CELDA}>Ganados</th>
                <th scope="col" style={CELDA}>Perdidos</th>
                <th scope="col" style={CELDA}>Tasa de ganados</th>
                <th scope="col" style={CELDA}>Score medio</th>
              </tr>
            </thead>
            <tbody>
              {panel.por_red.map((fila) => (
                <tr key={fila.red} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <th scope="row" style={{ ...CELDA, fontWeight: 600, textAlign: 'left' }}>{fila.etiqueta}</th>
                  <td style={CELDA}>{fila.ganados}</td>
                  <td style={CELDA}>{fila.perdidos}</td>
                  <td style={CELDA}>{PORCENTAJE(fila.tasa_de_ganados)}</td>
                  <td style={{ ...CELDA, fontFamily: 'var(--font-mono)' }}>{NUMERO(fila.score_medio_al_cierre)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {panel && panel.por_tramo.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '6px' }}>Tamaño de los ganados</h3>
          <table className="data-table" aria-label="Ganados por tramo del acuerdo" style={{ fontSize: '0.78rem', width: '100%' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={CELDA}>Tramo</th>
                <th scope="col" style={CELDA}>Casos</th>
              </tr>
            </thead>
            <tbody>
              {panel.por_tramo.map((fila) => (
                <tr key={fila.tramo} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <th scope="row" style={{ ...CELDA, fontWeight: 600, textAlign: 'left' }}>{fila.etiqueta}</th>
                  <td style={CELDA}>{fila.casos}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Por tramos y sin cifra exacta: de aquí no sale ninguna previsión de ingresos.
          </p>
        </div>
      )}

      {panel && <Reentrenamiento datos={panel.reentrenamiento} />}
    </section>
  );
}
