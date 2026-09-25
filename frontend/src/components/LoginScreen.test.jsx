// ============================================================================
// La entrada, con y sin segundo factor (capítulo 35)
// ============================================================================
//
// Lo que importa aquí es que el segundo paso sea un paso y no un campo más: mientras el
// desafío vale, el correo y la contraseña ya no pintan nada, y dejarlos en pantalla invita
// a volver a enviarlos. Y que la contraseña no se quede en el estado del componente una vez
// que el primer paso salió bien.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  login: vi.fn(),
  completarLoginConSegundoFactor: vi.fn(),
}));

import { completarLoginConSegundoFactor, login } from '../services/api';
import LoginScreen from './LoginScreen.jsx';

const USUARIO = { id: 3, email: 'admin@plurione.test', full_name: 'Admin', role: 'System_Admin' };
const DESAFIO = {
  tipo: 'segundo_factor',
  desafio: 'un.token.de.desafio',
  expira_en: 300,
  codigos_de_recuperacion_restantes: 7,
};

function montar() {
  const onAuthenticated = vi.fn();
  render(<LoginScreen onAuthenticated={onAuthenticated} />);
  return { onAuthenticated };
}

async function primerPaso(usuario) {
  await usuario.type(screen.getByLabelText(/Correo corporativo/), 'admin@plurione.test');
  await usuario.type(screen.getByLabelText(/^Contraseña/), 'PruebaSegura2026!');
  await usuario.click(screen.getByRole('button', { name: /Iniciar sesión/ }));
}

beforeEach(() => {
  login.mockReset();
  completarLoginConSegundoFactor.mockReset();
});

describe('la entrada', () => {
  it('una cuenta sin segundo factor entra de una vez', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue(USUARIO);
    const { onAuthenticated } = montar();

    await primerPaso(usuario);

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(USUARIO));
    expect(completarLoginConSegundoFactor).not.toHaveBeenCalled();
  });

  it('con segundo factor pide el código y deja de pedir la contraseña', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue(DESAFIO);
    const { onAuthenticated } = montar();

    await primerPaso(usuario);

    expect(await screen.findByLabelText(/^Código/)).toBeInTheDocument();
    // El primer formulario desaparece: no hay nada que volver a enviar.
    expect(screen.queryByLabelText(/Correo corporativo/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Contraseña/)).not.toBeInTheDocument();
    // Y todavía no hay sesión.
    expect(onAuthenticated).not.toHaveBeenCalled();
  });

  it('el código correcto completa la entrada', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue(DESAFIO);
    completarLoginConSegundoFactor.mockResolvedValue(USUARIO);
    const { onAuthenticated } = montar();
    await primerPaso(usuario);

    await usuario.type(await screen.findByLabelText(/^Código/), '123456');
    await usuario.click(screen.getByRole('button', { name: /^Entrar/ }));

    await waitFor(() =>
      expect(completarLoginConSegundoFactor).toHaveBeenCalledWith('un.token.de.desafio', '123456'),
    );
    expect(onAuthenticated).toHaveBeenCalledWith(USUARIO);
  });

  it('un código equivocado devuelve al primer paso con el motivo', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue(DESAFIO);
    completarLoginConSegundoFactor.mockRejectedValue(
      new Error('El código no es válido o el acceso ha caducado. Vuelva a iniciar sesión.'),
    );
    montar();
    await primerPaso(usuario);

    await usuario.type(await screen.findByLabelText(/^Código/), '000000');
    await usuario.click(screen.getByRole('button', { name: /^Entrar/ }));

    // Vuelve al primer paso: el desafío se gasta o caduca, y dejar el campo del código
    // invitaría a reintentar contra uno que ya no vale y a leer «código no válido» sin
    // que lo sea.
    expect(await screen.findByLabelText(/Correo corporativo/)).toBeInTheDocument();
    expect(screen.getByText(/no es válido o el acceso ha caducado/)).toBeInTheDocument();
  });

  it('avisa a quien se quedó sin códigos de recuperación', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue({ ...DESAFIO, codigos_de_recuperacion_restantes: 0 });
    montar();

    await primerPaso(usuario);

    expect(await screen.findByText(/No le quedan códigos de recuperación/)).toBeInTheDocument();
  });

  it('se puede volver atrás desde el segundo paso', async () => {
    const usuario = userEvent.setup();
    login.mockResolvedValue(DESAFIO);
    montar();
    await primerPaso(usuario);

    await usuario.click(await screen.findByRole('button', { name: /Volver/ }));

    expect(screen.getByLabelText(/Correo corporativo/)).toBeInTheDocument();
    // La contraseña no se conserva tras un primer paso correcto: hay que volver a escribirla.
    expect(screen.getByLabelText(/^Contraseña/)).toHaveValue('');
  });
});
