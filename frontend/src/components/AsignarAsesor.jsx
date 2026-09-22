import React, { useEffect, useState } from 'react';
import { fetchSalesReps, getCurrentUserRole, updateLead } from '../services/api';

// Quién atiende esta ficha, y cómo se decide desde la propia ficha.
//
// La página de interés crea los prospectos **sin asesor** a propósito: repartir cartera es
// una decisión del líder, no del formulario. Hasta aquí no había forma de repartirlos desde
// el panel —solo llamando a `PUT /leads/{id}` a mano—, así que una ficha llegada de LinkedIn
// se quedaba fuera de la vista de todo asesor hasta que alguien tocaba la base.
//
// Solo se enseña a quien puede reasignar. Un asesor que viera el selector recibiría un 403
// al usarlo: es mejor no ofrecer lo que el servidor va a rechazar.
const PUEDEN_REPARTIR = ['Sales_Lead', 'System_Admin'];

export default function AsignarAsesor({ lead, onAsignado }) {
  const [asesores, setAsesores] = useState([]);
  const [elegido, setElegido] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  const puedeRepartir = PUEDEN_REPARTIR.includes(getCurrentUserRole());

  useEffect(() => {
    if (!puedeRepartir) return;
    let vigente = true;
    fetchSalesReps()
      .then((datos) => {
        if (vigente) setAsesores((datos && datos.items) || []);
      })
      .catch((err) => {
        if (vigente) setError(err.message);
      });
    return () => { vigente = false; };
  }, [puedeRepartir]);

  if (!puedeRepartir) return null;

  const actual = asesores.find((a) => a.id === lead.assigned_rep_id);

  const asignar = async () => {
    if (!elegido) return;
    setGuardando(true);
    setError('');
    try {
      await updateLead(lead.id, { assigned_rep_id: Number(elegido) });
      setElegido('');
      if (onAsignado) await onAsignado();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div
      className="glass-panel"
      style={{ padding: '12px 14px', marginBottom: '20px', display: 'flex', gap: '10px', alignItems: 'flex-end', flexWrap: 'wrap', fontSize: '0.8rem' }}
    >
      <div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Asesor asignado
        </div>
        <strong>
          {lead.assigned_rep_id
            ? (actual ? actual.full_name : `Asesor ${lead.assigned_rep_id}`)
            : 'Sin asesor'}
        </strong>
      </div>
      <div>
        <label htmlFor="asignar-asesor" className="form-label">
          {lead.assigned_rep_id ? 'Reasignar a' : 'Asignar a'}
        </label>
        <select
          id="asignar-asesor"
          className="input-field"
          value={elegido}
          onChange={(e) => setElegido(e.target.value)}
        >
          <option value="">Elija un asesor</option>
          {asesores.map((asesor) => (
            <option key={asesor.id} value={asesor.id}>
              {asesor.full_name} ({asesor.leads_asignados}
              {asesor.capacity ? ` de ${asesor.capacity}` : ''})
            </option>
          ))}
        </select>
      </div>
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={!elegido || guardando}
        onClick={asignar}
      >
        {guardando ? 'Asignando...' : 'Asignar'}
      </button>
      {error && (
        <span role="alert" style={{ color: 'var(--hot-text)' }}>{error}</span>
      )}
    </div>
  );
}
