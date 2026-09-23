import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchAvisos, marcarAvisosLeidos } from '../services/api';

// La campana: lo que alguien tiene que enterarse de que pasó.
//
// Un aviso no es una tarea. Una tarea se hace y se cierra cuando el trabajo ocurre; un
// aviso se lee. «Este HOT lleva 24 horas sin que nadie lo toque» no pide un trabajo
// concreto —puede resolverse llamando, delegando o decidiendo que no vale la pena—: pide
// que alguien se entere. Por eso vive aquí y no en la bandeja.
//
// Y no sale del panel: ni correo ni WhatsApp. Un aviso que sale del sistema necesita una
// cuenta externa y saca de la aplicación el nombre de una persona que aceptó un aviso de
// privacidad para otra cosa.

function cuando(iso) {
  const minutos = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutos < 60) return `hace ${Math.max(minutos, 1)} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  return `hace ${Math.round(horas / 24)} d`;
}

export default function Campana({ onSelectLead }) {
  const [abierta, setAbierta] = useState(false);
  const [campana, setCampana] = useState({ sin_leer: 0, avisos: [] });
  const [error, setError] = useState('');
  const contenedor = useRef(null);

  const cargar = useCallback(async () => {
    try {
      setCampana(await fetchAvisos());
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Cerrar al pulsar fuera. Sin esto, el panel se queda abierto tapando la tabla y hay que
  // volver a dar al icono, que es justo donde la gente no mira.
  useEffect(() => {
    if (!abierta) return undefined;
    const fuera = (evento) => {
      if (contenedor.current && !contenedor.current.contains(evento.target)) setAbierta(false);
    };
    document.addEventListener('mousedown', fuera);
    return () => document.removeEventListener('mousedown', fuera);
  }, [abierta]);

  const abrir = async () => {
    const siguiente = !abierta;
    setAbierta(siguiente);
    // Al abrir se recarga: entre que se pintó el panel y que alguien mira la campana puede
    // haber corrido la pasada diaria.
    if (siguiente) await cargar();
  };

  const leerTodos = async () => {
    try {
      await marcarAvisosLeidos();
      await cargar();
    } catch (err) {
      setError(err.message);
    }
  };

  const abrirFicha = async (aviso) => {
    setAbierta(false);
    // Abrirlo cuenta como haberse enterado: obligar a marcarlo aparte convierte la campana
    // en una segunda lista de pendientes que también hay que vaciar a mano.
    if (!aviso.leido_en) {
      try {
        await marcarAvisosLeidos([aviso.id]);
        await cargar();
      } catch {
        // Que falle el marcado no puede impedir abrir la ficha, que es lo que se pidió.
      }
    }
    onSelectLead(aviso.prospecto.id);
  };

  return (
    <div ref={contenedor} style={{ position: 'relative' }}>
      <button
        type="button"
        id="btn-campana"
        onClick={abrir}
        className="btn btn-secondary btn-sm"
        aria-expanded={abierta}
        aria-label={
          campana.sin_leer > 0 ? `Avisos: ${campana.sin_leer} sin leer` : 'Avisos: ninguno sin leer'
        }
        style={{ position: 'relative' }}
      >
        🔔
        {campana.sin_leer > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '-6px',
              right: '-6px',
              minWidth: '16px',
              height: '16px',
              padding: '0 4px',
              borderRadius: 'var(--radius-full)',
              background: 'var(--hot-bg)',
              color: 'var(--hot-text)',
              fontSize: '0.6rem',
              fontWeight: '700',
              lineHeight: '16px',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {campana.sin_leer > 9 ? '9+' : campana.sin_leer}
          </span>
        )}
      </button>

      {abierta && (
        <div
          role="dialog"
          aria-label="Avisos"
          className="glass-panel"
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 8px)',
            width: 'min(360px, 90vw)',
            maxHeight: '60vh',
            overflowY: 'auto',
            padding: '12px',
            zIndex: 200,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
            <strong style={{ fontSize: '0.85rem' }}>Avisos</strong>
            {campana.sin_leer > 0 && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={leerTodos}>
                Marcar todos como leídos
              </button>
            )}
          </div>

          {error && (
            <p role="alert" style={{ fontSize: '0.75rem', color: 'var(--hot-text)', margin: '8px 0 0' }}>
              {error}
            </p>
          )}

          {campana.avisos.length === 0 && !error && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '10px 0 0' }}>
              Nada que contar por ahora.
            </p>
          )}

          <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0' }}>
            {campana.avisos.map((aviso) => (
              <li key={aviso.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <button
                  type="button"
                  onClick={() => abrirFicha(aviso)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    padding: '10px 0',
                    cursor: 'pointer',
                    color: 'var(--text-primary)',
                    // Lo no leído pesa más, literalmente.
                    fontWeight: aviso.leido_en ? '400' : '600',
                  }}
                >
                  <span style={{ fontSize: '0.8rem', display: 'block' }}>
                    {aviso.prospecto.nombre}
                    {aviso.prospecto.empresa ? ` · ${aviso.prospecto.empresa}` : ''}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>
                    {aviso.texto} · {cuando(aviso.creado_en)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
