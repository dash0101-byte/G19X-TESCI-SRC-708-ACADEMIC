// ============================================================================
// El alta obligatoria del segundo factor (capítulo 35)
// ============================================================================
//
// La pantalla que ve una cuenta de administración sin segundo factor, en lugar de la
// aplicación. Lo que importa de ella es que los dos pasos estén separados —el QR y los
// códigos primero, la comprobación después— y que no se pueda activar sin haber tenido
// delante los códigos de recuperación: en cuanto esto se active, son lo único que queda si
// el teléfono se pierde.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  altaDelSegundoFactor: vi.fn(),
  activarSegundoFactor: vi.fn(),
}));

import { activarSegundoFactor, altaDelSegundoFactor } from '../services/api';
import AltaDelSegundoFactor from './AltaDelSegundoFactor.jsx';

const USUARIO = { id: 3, email: 'admin@plurione.test', full_name: 'Admin de Pruebas', role: 'System_Admin' };

const ALTA = {
  uri_otpauth: 'otpauth://totp/PluriOne%3Aadmin%40plurione.test?secret=JBSWY3DPEHPK3PXP&issuer=PluriOne',
  qr_svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 41 41"><path d="M0 0h1v1h-1z"/></svg>',
  secreto_en_base32: 'JBSWY3DPEHPK3PXP',
  codigos_de_recuperacion: [
    '23AB-CDEF-GHJK', '4MNP-QRST-UVWX', '5YZ2-3456-789A', 'BCDE-FGHJ-KMNP', 'QRST-UVWX-YZ23',
    '4567-89AB-CDEF', 'GHJK-MNPQ-RSTU', 'VWXY-Z234-5678', '9ABC-DEFG-HJKM', 'NPQR-STUV-WXYZ',
  ],
};

function montar(props = {}) {
  const onActivado = vi.fn();
  const onSalir = vi.fn();
  render(<AltaDelSegundoFactor user={USUARIO} onActivado={onActivado} onSalir={onSalir} {...props} />);
  return { onActivado, onSalir };
}

beforeEach(() => {
  altaDelSegundoFactor.mockReset().mockResolvedValue(ALTA);
  activarSegundoFactor.mockReset().mockResolvedValue({ activo: true });
});

describe('el alta del segundo factor', () => {
  it('enseña el QR, la clave para teclear y los diez códigos', async () => {
    montar();

    expect(await screen.findByLabelText(/Código QR/)).toBeInTheDocument();
    // La clave a mano tiene que estar: si la cámara no va, es la única salida.
    expect(screen.getByText(ALTA.secreto_en_base32)).toBeInTheDocument();
    for (const codigo of ALTA.codigos_de_recuperacion) {
      expect(screen.getByText(codigo)).toBeInTheDocument();
    }
  });

  it('no deja activar hasta confirmar que los códigos están guardados', async () => {
    const usuario = userEvent.setup();
    montar();
    await screen.findByLabelText(/Código QR/);

    const boton = screen.getByRole('button', { name: /Activar el segundo factor/ });
    expect(boton).toBeDisabled();

    await usuario.click(screen.getByRole('checkbox', { name: /guardado en un sitio seguro/ }));
    expect(boton).toBeEnabled();
  });

  it('activa con el código y avisa a quien la montó', async () => {
    const usuario = userEvent.setup();
    const { onActivado } = montar();
    await screen.findByLabelText(/Código QR/);

    await usuario.click(screen.getByRole('checkbox', { name: /guardado en un sitio seguro/ }));
    await usuario.type(screen.getByLabelText(/Código de seis dígitos/), '123456');
    await usuario.click(screen.getByRole('button', { name: /Activar el segundo factor/ }));

    await waitFor(() => expect(activarSegundoFactor).toHaveBeenCalledWith('123456'));
    expect(onActivado).toHaveBeenCalled();
  });

  it('un código equivocado deja el motivo en pantalla y no activa', async () => {
    const usuario = userEvent.setup();
    activarSegundoFactor.mockRejectedValue(
      new Error('Ese código no coincide. Compruebe que la hora del teléfono sea la correcta.'),
    );
    const { onActivado } = montar();
    await screen.findByLabelText(/Código QR/);

    await usuario.click(screen.getByRole('checkbox', { name: /guardado en un sitio seguro/ }));
    await usuario.type(screen.getByLabelText(/Código de seis dígitos/), '000000');
    await usuario.click(screen.getByRole('button', { name: /Activar el segundo factor/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/la hora del teléfono/);
    expect(onActivado).not.toHaveBeenCalled();
    // El QR sigue ahí: el alta no se pierde por fallar el código.
    expect(screen.getByLabelText(/Código QR/)).toBeInTheDocument();
  });

  it('siempre deja salir, aunque el alta no se pueda preparar', async () => {
    const usuario = userEvent.setup();
    altaDelSegundoFactor.mockRejectedValue(new Error('No fue posible dar de alta'));
    const { onSalir } = montar();

    expect(await screen.findByRole('alert')).toHaveTextContent(/No fue posible/);
    await usuario.click(screen.getByRole('button', { name: /Cerrar sesión/ }));
    expect(onSalir).toHaveBeenCalled();
  });
});
