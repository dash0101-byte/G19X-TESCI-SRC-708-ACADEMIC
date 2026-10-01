// ============================================================================
// El alta de prospecto y la casilla del aviso de privacidad
// ============================================================================
//
// La API admite `privacy_notice_accepted` desde la Fase 15 y esta pantalla no lo ofrecía:
// el punto 14 de §6.2. El efecto no era un error visible, que es lo que lo dejó ahí dos
// docenas de capítulos: **toda** ficha dada de alta a mano nacía sin constancia de que la
// persona hubiera aceptado nada, y la ficha se guardaba, se puntuaba y se leía igual.
// Donde se notaba era en la respuesta de acceso del titular, que decía «no consta que haya
// aceptado el aviso de privacidad» de gente que a lo mejor lo aceptó por teléfono.
//
// Las tres propiedades que se fijan aquí, y por qué son tres y no una:
//
// 1. **La casilla nace sin marcar.** Marcada por omisión guardaría una aceptación que
//    nadie dio, con la fecha de ahora al lado, y esa fecha la volvería indistinguible de
//    las de verdad. Es el mismo criterio del país que ya no se supone y de los ingresos
//    que no son cero.
// 2. **Sin marcar se envía `false`, no se omite el campo.** Omitirlo funcionaría —el
//    esquema tiene `False` por omisión— y sería peor: el cliente dejaría de decir lo que
//    quiere, y el día que el servidor cambiara ese valor por omisión el alta cambiaría de
//    comportamiento sin que nadie tocara esta pantalla.
// 3. **No es obligatoria para guardar.** La página pública sí la exige, y la diferencia es
//    deliberada: allí la marca la persona y aquí la marcaría el asesor por ella. Obligarla
//    garantizaría que se marque siempre, que es justo lo contrario de que signifique algo
//    (§5.2 de la congelación).

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import * as api from '../services/api';
import NewLeadModal from './NewLeadModal.jsx';

const CASILLA = /La persona aceptó el aviso de privacidad/;

beforeEach(() => {
  for (const clave of Object.keys(api)) {
    if (typeof api[clave]?.mockReset === 'function') api[clave].mockReset();
  }
  api.createLead.mockResolvedValue({ id: 99 });
});

/** Rellena lo mínimo que el formulario exige y envía. */
async function altaMinima(usuario) {
  await usuario.type(screen.getByLabelText('Nombre *'), 'Ana');
  await usuario.type(screen.getByLabelText('Apellido *'), 'Titular');
  await usuario.type(screen.getByLabelText('Correo Electrónico *'), 'ana@ejemplo.test');
  await usuario.click(screen.getByRole('button', { name: /Guardar y Calificar/ }));
  await waitFor(() => expect(api.createLead).toHaveBeenCalled());
  return api.createLead.mock.calls[0][0];
}

describe('la casilla del aviso de privacidad', () => {
  it('se ofrece, y nace sin marcar', () => {
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    expect(screen.getByLabelText(CASILLA)).not.toBeChecked();
  });

  it('dice qué pasa al marcarla y qué pasa al no marcarla', () => {
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    expect(screen.getByText(/queda registrada la fecha y la hora de ahora/)).toBeInTheDocument();
    expect(screen.getByText(/el campo se queda vacío/)).toBeInTheDocument();
  });

  it('marcada, el alta la envía', async () => {
    const usuario = userEvent.setup();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await usuario.click(screen.getByLabelText(CASILLA));
    const enviado = await altaMinima(usuario);

    expect(enviado.privacy_notice_accepted).toBe(true);
  });

  it('sin marcar, el alta envía `false` y no omite el campo', async () => {
    const usuario = userEvent.setup();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    const enviado = await altaMinima(usuario);

    expect(enviado).toHaveProperty('privacy_notice_accepted');
    expect(enviado.privacy_notice_accepted).toBe(false);
  });

  it('sin marcar se puede guardar la ficha igual', async () => {
    // No es un olvido: es §5.2. Aceptar el aviso no es condición para que la ficha exista,
    // y la decisión de que lo sea no es técnica.
    const usuario = userEvent.setup();
    const creado = vi.fn();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={creado} />);

    await altaMinima(usuario);

    expect(creado).toHaveBeenCalled();
  });

  it('la casilla no viaja dentro de los campos personalizados', async () => {
    // `raw_metadata` es un JSON libre que el modelo no lee. Una constancia de
    // consentimiento ahí dentro no se podría consultar ni suprimir como un campo.
    const usuario = userEvent.setup();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await usuario.click(screen.getByLabelText(CASILLA));
    const enviado = await altaMinima(usuario);

    expect(JSON.stringify(enviado.raw_metadata)).not.toContain('privacy');
  });
});

describe('lo que el alta sigue sin inventar', () => {
  it('no manda unos ingresos que nadie escribió', async () => {
    // Capítulo 24: enviaba 2 000 000 fijos y cada ficha creada desde el panel llegaba al
    // modelo con una facturación inventada. Se comprueba aquí para que el arreglo no se
    // deshaga al tocar el formulario por otro motivo, que es lo que este capítulo hizo.
    const usuario = userEvent.setup();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    const enviado = await altaMinima(usuario);

    expect(enviado.annual_revenue).toBeNull();
  });
});
