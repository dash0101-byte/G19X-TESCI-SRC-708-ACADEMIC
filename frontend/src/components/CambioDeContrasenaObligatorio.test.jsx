// ============================================================================
// El cambio de contraseña obligatorio
// ============================================================================
//
// La pantalla que ve una cuenta con contraseña prestada en lugar de la aplicación. Lo que
// importa de ella es lo mismo que en el menú de la sesión —que la confirmación se compruebe
// antes de mandar nada, que los motivos del servidor lleguen completos y que no se pueda
// enviar dos veces—, más una cosa propia: al terminar tiene que devolver a la entrada con
// el mensaje del servidor, porque las sesiones ya están cerradas.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  changeOwnPassword: vi.fn(),
}));

import { changeOwnPassword } from '../services/api';
import CambioDeContrasenaObligatorio from './CambioDeContrasenaObligatorio.jsx';

const USUARIO = {
  id: 9,
  email: 'luis.nuevo@plurione.test',
  full_name: 'Luis Nuevo Paredes',
  role: 'Commercial_Executive',
  must_change_password: true,
};

const PRESTADA = 'Prestada-Inicial-2026';
const PROPIA = 'Mi-Frase-Propia-Y-Larga';

function montar() {
  const acciones = { onCompletado: vi.fn(), onSalir: vi.fn() };
  render(<CambioDeContrasenaObligatorio user={USUARIO} {...acciones} />);
  return acciones;
}

async function rellenar(usuario, { actual, nueva, repetida }) {
  await usuario.type(screen.getByLabelText('Contraseña actual'), actual);
  await usuario.type(screen.getByLabelText(/Contraseña nueva/), nueva);
  await usuario.type(screen.getByLabelText('Repita la contraseña nueva'), repetida);
}

beforeEach(() => {
  changeOwnPassword.mockReset();
});

describe('lo que se le dice a la persona', () => {
  it('la nombra y explica por qué no la deja pasar', () => {
    montar();
    expect(screen.getByText(/Luis Nuevo Paredes/)).toBeInTheDocument();
    expect(screen.getByText(/la fijó otra persona/)).toBeInTheDocument();
  });

  it('los tres campos se encuentran por su etiqueta y no enseñan lo que se escribe', () => {
    montar();
    for (const nombre of ['Contraseña actual', /Contraseña nueva/, 'Repita la contraseña nueva']) {
      expect(screen.getByLabelText(nombre)).toHaveAttribute('type', 'password');
    }
  });
});

describe('el envío', () => {
  it('no manda nada si la repetición no coincide', async () => {
    const usuario = userEvent.setup();
    const { onCompletado } = montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: `${PROPIA}x` });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('no coinciden');
    expect(changeOwnPassword).not.toHaveBeenCalled();
    expect(onCompletado).not.toHaveBeenCalled();
  });

  it('al cambiarla devuelve a la entrada con el mensaje del servidor', async () => {
    changeOwnPassword.mockResolvedValue({
      mensaje: 'Contraseña actualizada. Se han cerrado todas las sesiones, incluida esta.',
      sesiones_cerradas: 1,
    });
    const usuario = userEvent.setup();
    const { onCompletado } = montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    await waitFor(() => expect(onCompletado).toHaveBeenCalledTimes(1));
    expect(changeOwnPassword).toHaveBeenCalledWith(PRESTADA, PROPIA);
    expect(onCompletado).toHaveBeenCalledWith(
      'Contraseña actualizada. Se han cerrado todas las sesiones, incluida esta.',
    );
  });

  // Este error se construye como lo construye `api.js`, con su `status` y con los motivos ya
  // unidos en el mensaje, y eso tiene su historia (capítulo 43).
  //
  // La versión anterior de esta prueba escribía el mensaje a mano —«no cumple la
  // política\n- es demasiado común»— y comprobaba que la pantalla lo enseñara. Lo enseñaba,
  // claro: se lo había dado la prueba. Lo que nadie comprobaba era el tramo de antes, y en
  // ese tramo estaba el defecto: `parseApiError` se quedaba con el titular del detalle
  // estructurado y **tiraba la lista de motivos**, así que en pantalla no salía ninguno. Una
  // prueba que fabrica la respuesta del servidor una capa por debajo de donde está el fallo
  // no puede verlo. El tramo que faltaba vive ahora en `services/api.test.js`.
  function comoLoDevuelveElServidor({ status, mensaje, motivos = [] }) {
    return Object.assign(new Error([mensaje, ...motivos].join('\n')), {
      status,
      detalle: motivos.length ? { mensaje, motivos } : { mensaje },
    });
  }

  it('si el servidor la rechaza, enseña todos los motivos y deja reintentar', async () => {
    changeOwnPassword.mockRejectedValue(comoLoDevuelveElServidor({
      status: 422,
      mensaje: 'La contraseña no cumple la política del sistema.',
      motivos: ['Debe tener al menos 12 caracteres.', 'Es demasiado común.'],
    }));
    const usuario = userEvent.setup();
    const { onCompletado } = montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const aviso = await screen.findByRole('alert');
    expect(aviso).toHaveTextContent('Debe tener al menos 12 caracteres.');
    expect(aviso).toHaveTextContent('Es demasiado común.');
    expect(screen.getByRole('button', { name: 'Guardar y volver a entrar' })).toBeEnabled();
    expect(onCompletado).not.toHaveBeenCalled();
  });

  it('y el aviso nombra el campo con su etiqueta, no con el nombre de la columna', async () => {
    changeOwnPassword.mockRejectedValue(comoLoDevuelveElServidor({
      status: 422,
      mensaje: 'La contraseña no cumple la política del sistema.',
      motivos: ['Está en la lista de contraseñas filtradas: elija otra.'],
    }));
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const aviso = await screen.findByRole('alert');
    expect(aviso).toHaveTextContent('Revise el campo Contraseña nueva.');
    expect(aviso.textContent).not.toContain('nueva_contrasena');
  });

  it('el rechazo de la política señala la contraseña nueva, y el foco va a ella', async () => {
    changeOwnPassword.mockRejectedValue(comoLoDevuelveElServidor({
      status: 422,
      mensaje: 'La contraseña no cumple la política del sistema.',
      motivos: ['Es demasiado común.'],
    }));
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const nueva = screen.getByLabelText(/Contraseña nueva/);
    await waitFor(() => expect(nueva).toHaveAttribute('aria-invalid', 'true'));
    expect(nueva).toHaveFocus();
    // Y la que no tiene nada que ver no queda marcada.
    expect(screen.getByLabelText('Contraseña actual')).not.toHaveAttribute('aria-invalid');
  });

  it('una contraseña actual incorrecta señala la actual, no la nueva', async () => {
    // El 401 de esa puerta solo puede significar eso: la credencial que se pidió para
    // comprobar que quien cambia la contraseña es quien dice ser no era la correcta.
    changeOwnPassword.mockRejectedValue(comoLoDevuelveElServidor({
      status: 401,
      mensaje: 'La contraseña actual no es correcta.',
    }));
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, { actual: 'la-que-no-es', nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const actual = screen.getByLabelText('Contraseña actual');
    await waitFor(() => expect(actual).toHaveAttribute('aria-invalid', 'true'));
    expect(actual).toHaveFocus();
    expect(screen.getByLabelText(/Contraseña nueva/)).not.toHaveAttribute('aria-invalid');
    expect(await screen.findByRole('alert')).toHaveTextContent('Revise el campo Contraseña actual.');
  });

  it('al corregir el campo señalado se le quita la marca', async () => {
    changeOwnPassword.mockRejectedValue(comoLoDevuelveElServidor({
      status: 422,
      mensaje: 'La contraseña no cumple la política del sistema.',
      motivos: ['Es demasiado común.'],
    }));
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const nueva = screen.getByLabelText(/Contraseña nueva/);
    await waitFor(() => expect(nueva).toHaveAttribute('aria-invalid', 'true'));
    await usuario.type(nueva, 'z');

    expect(nueva).not.toHaveAttribute('aria-invalid');
  });

  it('no se puede enviar dos veces mientras el primer envío está en el aire', async () => {
    changeOwnPassword.mockReturnValue(new Promise(() => {}));
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, { actual: PRESTADA, nueva: PROPIA, repetida: PROPIA });
    await usuario.click(screen.getByRole('button', { name: 'Guardar y volver a entrar' }));

    const boton = await screen.findByRole('button', { name: 'Guardando…' });
    expect(boton).toBeDisabled();
    await usuario.click(boton);
    expect(changeOwnPassword).toHaveBeenCalledTimes(1);
  });

  it('salir no exige cambiarla antes', async () => {
    const usuario = userEvent.setup();
    const { onSalir } = montar();
    await usuario.click(screen.getByRole('button', { name: 'Salir' }));
    expect(onSalir).toHaveBeenCalledTimes(1);
    expect(changeOwnPassword).not.toHaveBeenCalled();
  });
});
