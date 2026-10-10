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

    // Con su propia espera: `altaMinima` espera a que el alta SALGA, y a quien la pidió se
    // le avisa después de que el servidor conteste.
    await waitFor(() => expect(creado).toHaveBeenCalled());
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

// ============================================================================
// El 422 llega al campo que lo causó (capítulo 40)
// ============================================================================
//
// Lo que esta pantalla hacía con un 422 de tres campos era volcarlo entero en el aviso de
// arriba, con el nombre de la columna, en inglés y en un solo renglón, porque el salto de
// línea que `parseApiError` pone no es un salto en HTML:
//
//     first_name: Field required email: value is not a valid email address...
//
// Y el servidor **ya decía** qué campo: el 422 trae `loc`. Lo que faltaba era recogerlo.
describe('un 422 del servidor señala el campo', () => {
  /** El error que lanza `api.js` para un 422: mensaje, código y detalle colgados. */
  function error422(detalle) {
    const err = new Error('Error de validación');
    err.status = 422;
    err.detalle = detalle;
    return err;
  }

  /** Lo mínimo para que el formulario envíe. */
  async function rellenarYEnviar(usuario) {
    await usuario.type(screen.getByLabelText('Nombre *'), 'Ana');
    await usuario.type(screen.getByLabelText('Apellido *'), 'Titular');
    await usuario.type(screen.getByLabelText('Correo Electrónico *'), 'ana@ejemplo.test');
    await usuario.click(screen.getByRole('button', { name: /Guardar y Calificar/ }));
  }

  it('marca el campo, pone el mensaje debajo y los ata', async () => {
    const usuario = userEvent.setup();
    api.createLead.mockRejectedValue(error422([{
      type: 'value_error',
      loc: ['body', 'phone'],
      msg: 'Value error, El teléfono no es un número válido: revise la lada y el número de dígitos.',
    }]));
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await usuario.type(screen.getByLabelText('Teléfono'), '123');
    await rellenarYEnviar(usuario);

    const telefono = screen.getByLabelText('Teléfono');
    await waitFor(() => expect(telefono).toHaveAttribute('aria-invalid', 'true'));

    // El mensaje está donde el campo dice que está: no basta con que exista en la pantalla,
    // tiene que ser el que `aria-describedby` nombra, que es el que el lector lee.
    const explicacion = document.getElementById(telefono.getAttribute('aria-describedby'));
    expect(explicacion).not.toBeNull();
    expect(explicacion.textContent).toMatch(/revise la lada/);
    // Y sin el ruido interno de Pydantic delante.
    expect(explicacion.textContent).not.toMatch(/Value error/);
  });

  it('el aviso de arriba dice qué campos, con la etiqueta de la pantalla', async () => {
    const usuario = userEvent.setup();
    api.createLead.mockRejectedValue(error422([
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
      {
        type: 'value_error',
        loc: ['body', 'email'],
        msg: 'value is not a valid email address: An email address must have an @-sign.',
      },
    ]));
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await rellenarYEnviar(usuario);

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Revise estos campos: Nombre, Correo electrónico/);
    // Ni el nombre de la columna ni el idioma de Pydantic llegan a la pantalla.
    expect(aviso.textContent).not.toMatch(/first_name/);
    expect(aviso.textContent).not.toMatch(/email address/);
    // Y el aviso es la clase de la hoja, no siete propiedades en línea.
    expect(aviso.className).toContain('alert-error');
  });

  it('el foco va al primer campo que falla en el orden de la pantalla', async () => {
    // El 422 nombra el correo primero; en la pantalla, el nombre está encima. Si el foco
    // fuera al orden del servidor, quien navega con teclado acabaría en el campo de abajo
    // con el de arriba todavía mal.
    const usuario = userEvent.setup();
    api.createLead.mockRejectedValue(error422([
      { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
      { type: 'missing', loc: ['body', 'first_name'], msg: 'Field required' },
    ]));
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await rellenarYEnviar(usuario);

    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('Nombre *')));
  });

  it('corregir el campo le quita la marca', async () => {
    // Si no, el borde rojo y el mensaje se quedan puestos mientras se escribe la
    // corrección, diciendo de un campo algo que ya no es verdad.
    const usuario = userEvent.setup();
    api.createLead.mockRejectedValue(error422([
      { type: 'missing', loc: ['body', 'company'], msg: 'Field required' },
    ]));
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await rellenarYEnviar(usuario);

    const empresa = screen.getByLabelText('Empresa / Institución');
    await waitFor(() => expect(empresa).toHaveAttribute('aria-invalid', 'true'));
    expect(screen.getByText('Falta este campo.')).not.toBeNull();

    await usuario.type(empresa, 'PluriOne');
    expect(empresa).not.toHaveAttribute('aria-invalid');
    expect(screen.queryByText('Falta este campo.')).toBeNull();
  });

  it('un error de un campo que esta pantalla no pinta no desaparece', async () => {
    // `raw_metadata` no es un campo de la pantalla: no hay dónde ponerle un renglón. Pero
    // callarlo dejaría a quien rellena el formulario con un botón que no hace nada.
    const usuario = userEvent.setup();
    api.createLead.mockRejectedValue(error422([{
      type: 'extra_forbidden',
      loc: ['body', 'raw_metadata', 'lo_que_sea'],
      msg: 'Extra inputs are not permitted',
    }]));
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await rellenarYEnviar(usuario);

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Este dato no se admite aquí/);
  });

  it('un error que no es un 422 sigue yendo al aviso de arriba', async () => {
    // Un 409 de correo repetido no es un campo mal escrito: es una ficha que ya existe, y
    // su mensaje ya viene escrito para leerse.
    const usuario = userEvent.setup();
    const conflicto = new Error('Ya existe un prospecto con ese correo.');
    conflicto.status = 409;
    api.createLead.mockRejectedValue(conflicto);
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await rellenarYEnviar(usuario);

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Ya existe un prospecto con ese correo/);
    expect(screen.getByLabelText('Correo Electrónico *')).not.toHaveAttribute('aria-invalid');
  });
});
