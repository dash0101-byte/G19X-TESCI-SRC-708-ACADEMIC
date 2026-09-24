import React, { useCallback, useEffect, useState } from 'react';
import { cerrarProspecto, fetchOpcionesDeCierre } from '../services/api';

// Cerrar un prospecto: cómo acabó, por qué, cuándo y —si se ganó— de qué tamaño.
//
// Hasta el capítulo 30 esto era una opción más del selector de etapa: se elegía «Ganado»,
// se guardaba, y el sistema se quedaba sabiendo que el trato cerró y sin saber nada más.
// Cada uno de esos cierres era una etiqueta de entrenamiento sin nada que la explicara.
//
// No hay ningún campo de texto. Ni uno. Los motivos y los tramos son listas cerradas que
// **trae el servidor**, no listas escritas aquí: cuando el formulario llevaba sus propias
// opciones —como pasó con «¿Qué necesitas?» hasta el capítulo 26—, añadir un motivo exigía
// tocar dos sitios y olvidarse de uno no rompía nada; la opción simplemente dejaba de
// existir para el panel.
//
// «Otro motivo» está en las dos listas a propósito, y tampoco abre un cuadro de texto: una
// lista cerrada sin salida no produce datos limpios, produce datos falsos, porque quien no
// encuentra su caso elige el más parecido.

function hoyEnLocal() {
  // La fecha de hoy en el huso de quien rellena, en formato `AAAA-MM-DD`. `toISOString()`
  // daría el día en UTC: a las nueve de la noche en México eso ya es mañana, y el valor
  // por defecto del formulario sería una fecha futura que el servidor rechaza.
  const ahora = new Date();
  const desplazado = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000);
  return desplazado.toISOString().slice(0, 10);
}

export default function CerrarProspecto({ lead, onCerrado, onCancelar }) {
  const [opciones, setOpciones] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [resultado, setResultado] = useState('');
  const [motivo, setMotivo] = useState('');
  const [tramo, setTramo] = useState('');
  const [cerradoEl, setCerradoEl] = useState(hoyEnLocal());
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setOpciones(await fetchOpcionesDeCierre());
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const elegido = (opciones?.resultados || []).find((r) => r.clave === resultado) || null;

  const elegirResultado = (clave) => {
    setResultado(clave);
    // El motivo y el tramo se vacían: los motivos de un ganado no son los de un perdido, y
    // conservar el anterior dejaría seleccionada una opción que ya no está en la lista.
    setMotivo('');
    setTramo('');
    setError('');
  };

  const enviar = async (evento) => {
    evento.preventDefault();
    setGuardando(true);
    setError('');
    try {
      const registrado = await cerrarProspecto(lead.id, {
        resultado,
        motivo,
        cerrado_el: cerradoEl,
        // Solo en los ganados. Un perdido con tramo es un 422: un trato perdido no tiene
        // tamaño, y anotar «lo que habríamos facturado» sería una previsión inventada.
        ...(elegido?.pide_tramo ? { tramo } : {}),
      });
      if (onCerrado) onCerrado(registrado);
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  const completo = Boolean(resultado && motivo && cerradoEl && (!elegido?.pide_tramo || tramo));

  return (
    <form
      onSubmit={enviar}
      aria-labelledby="titulo-cerrar-prospecto"
      className="glass-panel"
      style={{ padding: '18px', display: 'grid', gap: '14px' }}
    >
      <div>
        <h4
          id="titulo-cerrar-prospecto"
          style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted)' }}
        >
          🏁 Cerrar el prospecto
        </h4>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
          El motivo del cierre es lo único que convierte «se perdió» en algo que se puede
          corregir. Se elige de una lista: así se puede contar.
        </p>
      </div>

      {error && (
        <div role="alert" style={{ fontSize: '0.78rem', color: 'var(--hot-text)' }}>
          {error}
        </div>
      )}

      {cargando && <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Cargando los motivos…</p>}

      {opciones && (
        <>
          <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
            <legend className="form-label">¿Cómo acabó?</legend>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {opciones.resultados.map((opcion) => (
                <button
                  key={opcion.clave}
                  type="button"
                  aria-pressed={resultado === opcion.clave}
                  className={`btn btn-sm ${resultado === opcion.clave ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => elegirResultado(opcion.clave)}
                >
                  {opcion.etiqueta}
                </button>
              ))}
            </div>
          </fieldset>

          {elegido && (
            <div>
              <label htmlFor="cierre-motivo" className="form-label">¿Por qué?</label>
              <select
                id="cierre-motivo"
                className="input-field"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                required
              >
                <option value="">Elige un motivo</option>
                {elegido.motivos.map((opcion) => (
                  <option key={opcion.clave} value={opcion.clave}>{opcion.etiqueta}</option>
                ))}
              </select>
              {/* La descripción del motivo elegido, para que «Perfil» no signifique dos
                  cosas distintas según quién rellene el formulario. */}
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                {elegido.motivos.find((o) => o.clave === motivo)?.descripcion
                  || 'Ninguno lleva más peso que otro: el motivo no puntúa ni entra en el modelo.'}
              </p>
            </div>
          )}

          {elegido?.pide_tramo && (
            <div>
              <label htmlFor="cierre-tramo" className="form-label">Tamaño del acuerdo</label>
              <select
                id="cierre-tramo"
                className="input-field"
                value={tramo}
                onChange={(e) => setTramo(e.target.value)}
                required
              >
                <option value="">Elige un tramo</option>
                {opciones.tramos.map((opcion) => (
                  <option key={opcion.clave} value={opcion.clave}>{opcion.etiqueta}</option>
                ))}
              </select>
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Por tramos y no por cifra exacta. Si todavía no se sabe, «Todavía no consta»
                es la respuesta correcta: una cifra de memoria no es un dato.
              </p>
            </div>
          )}

          {elegido && (
            <div>
              <label htmlFor="cierre-fecha" className="form-label">¿Qué día se cerró?</label>
              <input
                id="cierre-fecha"
                type="date"
                className="input-field"
                value={cerradoEl}
                max={hoyEnLocal()}
                onChange={(e) => setCerradoEl(e.target.value)}
                required
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                El día del cierre, no el de hoy: un trato firmado el viernes cuenta en su semana.
              </p>
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            {onCancelar && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={onCancelar}>
                Cancelar
              </button>
            )}
            <button type="submit" className="btn btn-primary btn-sm" disabled={!completo || guardando}>
              {guardando ? 'Cerrando…' : 'Cerrar el prospecto'}
            </button>
          </div>

          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0 }}>
            Al cerrarlo sale de la bandeja «Hoy» y deja de recibir tareas y avisos. Su
            puntuación no se recalcula: la que tenga es la que había cuando se decidió.
          </p>
        </>
      )}
    </form>
  );
}
