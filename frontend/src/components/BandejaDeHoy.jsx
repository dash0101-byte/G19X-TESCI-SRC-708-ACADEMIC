import React, { useCallback, useEffect, useState } from 'react';
import { fetchBandejaDeHoy, fetchHotQueSeEnfrian, marcarTareaHecha } from '../services/api';

// Lo que hay que hacer hoy, de arriba abajo y por score.
//
// La pantalla que faltaba. El sistema sabía puntuar y no sabía decir a quién llamar: el
// prospecto llegaba, se puntuaba, se asignaba, y a partir de ahí dependía de que alguien
// se acordara de mirarlo. De la prueba con personas salieron dos notas sobre exactamente
// eso —el asesor buscando lo nuevo y el líder buscando el contador—, y las dos son el
// mismo hueco.
//
// Cada fila dice tres cosas y nada más: qué hay que hacer, por qué, y a quién. El nombre
// abre la ficha 360, que es donde está el teléfono y donde ese acceso queda registrado.
// Aquí no hay datos de contacto a propósito: esto es una lista de trabajo, no un
// directorio.

const VERBO = {
  primer_contacto: 'Llamar por primera vez',
  volver_a_llamar: 'Volver a llamar',
  recordatorio_de_reunion: 'Preparar la reunión',
};

function cuando(iso, vencida) {
  const fecha = new Date(iso);
  const texto = fecha.toLocaleString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  return vencida ? `Venció el ${texto}` : `Para el ${texto}`;
}

function Tarea({ tarea, onSelectLead, onHecha, cerrando }) {
  return (
    <li
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '12px',
        padding: '12px 0',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: '700', fontSize: '0.9rem' }}>
            {VERBO[tarea.regla] || tarea.regla_etiqueta}
          </span>
          {/* Lo vencido se marca, pero no se saca de su sitio: la lista sigue ordenada por
              score, y un prospecto frío que lleva tres días esperando no sube por eso. */}
          {tarea.vencida && (
            <span className="badge" style={{ background: 'var(--hot-bg)', color: 'var(--hot-text)', fontSize: '0.6rem' }}>
              Vencida
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => onSelectLead(tarea.prospecto.id)}
          style={{
            background: 'none',
            border: 'none',
            padding: 0,
            marginTop: '2px',
            color: 'var(--text-primary)',
            fontSize: '0.85rem',
            cursor: 'pointer',
            textDecoration: 'underline',
          }}
        >
          {tarea.prospecto.nombre}
          {tarea.prospecto.empresa ? ` · ${tarea.prospecto.empresa}` : ''}
        </button>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '4px 0 0' }}>
          {tarea.motivo} · {cuando(tarea.vence_el, tarea.vencida)}
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
        <span
          className="badge"
          title="Score del prospecto"
          style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}
        >
          {Math.round(tarea.prospecto.score)}
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={cerrando}
          onClick={() => onHecha(tarea.id)}
        >
          {cerrando ? 'Cerrando…' : 'Ya está'}
        </button>
      </div>
    </li>
  );
}

function HotQueSeEnfrian({ filas }) {
  if (!filas.length) return null;
  return (
    <section
      aria-labelledby="titulo-enfriandose"
      style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}
    >
      <h3 id="titulo-enfriandose" style={{ fontSize: '0.9rem', fontWeight: '700', marginBottom: '2px' }}>
        HOT que se están enfriando
      </h3>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0 0 10px' }}>
        Nadie los ha contactado todavía. El trabajo es de cada asesor; un prospecto caliente
        enfriándose es del equipo.
      </p>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {filas.map((fila) => (
          <li
            key={fila.prospecto.id}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '8px 0',
              borderBottom: '1px solid var(--border-subtle)',
              fontSize: '0.8rem',
            }}
          >
            <span>
              {fila.prospecto.nombre}
              {fila.prospecto.empresa ? ` · ${fila.prospecto.empresa}` : ''}
            </span>
            <span style={{ color: 'var(--text-muted)', textAlign: 'right' }}>
              {fila.asesor || 'sin asesor'} · {fila.horas_sin_contacto} h
              {fila.avisado_al_lider ? ' · escalado' : ''}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function BandejaDeHoy({ onSelectLead, esDireccion = false }) {
  const [bandeja, setBandeja] = useState(null);
  const [enfriandose, setEnfriandose] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [cerrando, setCerrando] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const [hoy, hot] = await Promise.all([
        fetchBandejaDeHoy(),
        // La lista del líder es de dirección: para un asesor ni siquiera se pide, así que
        // su panel no depende de una llamada que le va a responder 403.
        esDireccion ? fetchHotQueSeEnfrian() : Promise.resolve({ filas: [] }),
      ]);
      setBandeja(hoy);
      setEnfriandose(hot.filas || []);
    } catch (err) {
      setError(err.message);
      setBandeja(null);
    } finally {
      setCargando(false);
    }
  }, [esDireccion]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const marcar = async (tareaId) => {
    setCerrando(tareaId);
    try {
      await marcarTareaHecha(tareaId);
      // Se recarga en vez de quitar la fila a mano: cerrar una tarea puede hacer que otra
      // deje de tener sentido, y la verdad de qué queda pendiente la tiene el servidor.
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setCerrando(null);
    }
  };

  const tareas = bandeja ? bandeja.tareas : [];

  return (
    <section className="glass-panel" aria-labelledby="titulo-hoy" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 id="titulo-hoy" style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>
            Hoy
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Lo que toca, del prospecto que más vale al que menos.
          </p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={cargar} disabled={cargando}>
          {cargando ? 'Cargando…' : 'Actualizar'}
        </button>
      </div>

      {error && (
        <div
          role="alert"
          style={{
            padding: '8px 12px',
            margin: '12px 0',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--error-text)',
            fontSize: '0.8rem',
          }}
        >
          {error}
        </div>
      )}

      {bandeja && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '12px 0 0' }}>
          {bandeja.vencidas > 0 && <strong>{bandeja.vencidas} vencidas</strong>}
          {bandeja.vencidas > 0 && ' · '}
          {bandeja.para_hoy} para hoy
          {/* Lo de más adelante se cuenta y no se enseña: saber que hay trabajo después
              tranquiliza; verlo hoy convierte esto en otra lista larga que nadie termina. */}
          {bandeja.mas_adelante > 0 && ` · ${bandeja.mas_adelante} más adelante`}
        </p>
      )}

      {!cargando && bandeja && tareas.length === 0 && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '16px 0 0' }}>
          Nada pendiente para hoy. {bandeja.mas_adelante > 0 ? 'Lo siguiente vence más adelante.' : ''}
        </p>
      )}

      {tareas.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0' }}>
          {tareas.map((tarea) => (
            <Tarea
              key={tarea.id}
              tarea={tarea}
              onSelectLead={onSelectLead}
              onHecha={marcar}
              cerrando={cerrando === tarea.id}
            />
          ))}
        </ul>
      )}

      {esDireccion && <HotQueSeEnfrian filas={enfriandose} />}
    </section>
  );
}
