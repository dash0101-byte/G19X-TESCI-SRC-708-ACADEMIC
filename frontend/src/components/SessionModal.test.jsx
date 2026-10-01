// ============================================================================
// El menú de la sesión
// ============================================================================
//
// Aquí se cambia la contraseña propia, así que sus reglas importan más que su aspecto:
// que la confirmación se compruebe antes de mandar nada, que los motivos de rechazo del
// servidor lleguen completos a la persona, y que el formulario no se pueda enviar dos
// veces mientras el primer envío está en el aire.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  changeOwnPassword: vi.fn(),
}));

import { changeOwnPassword } from '../services/api';
import SessionModal from './SessionModal.jsx';

const USUARIO = {
  id: 4,
  email: 'ana.ruiz@plurione.test',
  full_name: 'Ana Ruiz Delgado',
  role: 'Sales_Lead',
};

function montar(props = {}) {
  const acciones = { onLogout: vi.fn(), onClose: vi.fn() };
  render(<SessionModal user={USUARIO} {...acciones} {...props} />);
  return acciones;
}

/** Abre el formulario y rellena los tres campos. */
async function rellenar(usuario, { actual, nueva, repetida }) {
  await usuario.click(screen.getByRole('button', { name: 'Cambiar mi contraseña' }));
  await usuario.type(screen.getByPlaceholderText('Contraseña actual'), actual);
  await usuario.type(screen.getByPlaceholderText(/Contraseña nueva/), nueva);
  await usuario.type(screen.getByPlaceholderText('Repítala'), repetida);
}

beforeEach(() => {
  changeOwnPassword.mockReset();
});

describe('la identidad que se enseña', () => {
  it('muestra nombre, correo y el rol traducido a lo que esa persona puede hacer', () => {
    montar();
    expect(screen.getByText('Ana Ruiz Delgado')).toBeInTheDocument();
    expect(screen.getByText('ana.ruiz@plurione.test')).toBeInTheDocument();
    expect(screen.getByText(/Líder Comercial/)).toBeInTheDocument();
    expect(screen.getByText(/Supervisión gerencial/)).toBeInTheDocument();
  });

  it('las iniciales son las dos primeras palabras del nombre', () => {
    montar();
    expect(screen.getByText('AR')).toBeInTheDocument();
  });

  it('un nombre con espacios de más no produce iniciales con huecos', () => {
    montar({ user: { ...USUARIO, full_name: '  Ana   Ruiz  ' } });
    expect(screen.getByText('AR')).toBeInTheDocument();
  });

  it('sin nombre no revienta ni pinta basura', () => {
    montar({ user: { ...USUARIO, full_name: null } });
    expect(screen.getByText('ana.ruiz@plurione.test')).toBeInTheDocument();
  });

  it('un rol que el cliente no conoce se muestra tal cual, sin inventarse permisos', () => {
    montar({ user: { ...USUARIO, role: 'Auditor_Externo' } });
    expect(screen.getByText('Auditor_Externo')).toBeInTheDocument();
    // El texto de reserva no promete nada concreto: quien manda es el servidor.
    expect(screen.getByText(/Permisos determinados por el servidor/)).toBeInTheDocument();
  });

  it('deja claro que el rol no se cambia desde el navegador', () => {
    montar();
    expect(screen.getByText(/El rol no se puede cambiar desde el navegador/)).toBeInTheDocument();
  });
});

describe('cerrar el modal', () => {
  it('pulsar fuera lo cierra', async () => {
    const usuario = userEvent.setup();
    const { onClose } = montar();
    await usuario.click(document.querySelector('.modal-overlay'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('pulsar DENTRO no lo cierra: si no, cualquier clic en el formulario lo tiraría abajo', async () => {
    const usuario = userEvent.setup();
    const { onClose } = montar();
    await usuario.click(screen.getByText('Sesión activa'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('«Cerrar sesión» avisa hacia arriba; no cierra sesión por su cuenta', async () => {
    const usuario = userEvent.setup();
    const { onLogout, onClose } = montar();
    await usuario.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(onLogout).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('y se ve como lo que es: un botón de acción destructiva', () => {
    // `btn-danger` estuvo escrito aquí desde el capítulo 29 y **no existía en la hoja**
    // hasta el 39 (§6.4 punto 31), así que este botón se dibujaba como un `.btn` a secas:
    // sin fondo y con el borde transparente. El único que cierra la sesión era el que menos
    // se veía de los dos del pie.
    montar();
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toHaveClass('btn-danger');
  });
});

describe('cambio de la contraseña propia', () => {
  it('si la repetición no coincide, no se manda nada al servidor', async () => {
    const usuario = userEvent.setup();
    montar();
    await rellenar(usuario, {
      actual: 'la-de-siempre',
      nueva: 'una-frase-larga-y-nueva',
      repetida: 'una-frase-larga-distinta',
    });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText(/no coinciden/)).toBeInTheDocument();
    // Comprobarlo aquí evita un viaje inútil y, sobre todo, evita gastar un intento
    // contra el límite de tasa del backend por un dedazo al repetir.
    expect(changeOwnPassword).not.toHaveBeenCalled();
  });

  it('con todo correcto manda la actual y la nueva, en ese orden', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockResolvedValue({ mensaje: 'Contraseña actualizada.' });
    montar();
    await rellenar(usuario, {
      actual: 'la-de-siempre',
      nueva: 'una-frase-larga-y-nueva',
      repetida: 'una-frase-larga-y-nueva',
    });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(changeOwnPassword).toHaveBeenCalledWith('la-de-siempre', 'una-frase-larga-y-nueva'),
    );
  });

  it('al terminar enseña la confirmación y retira el formulario', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockResolvedValue({
      mensaje: 'Contraseña actualizada. Todas sus sesiones se han cerrado.',
    });
    montar();
    await rellenar(usuario, {
      actual: 'la-de-siempre',
      nueva: 'una-frase-larga-y-nueva',
      repetida: 'una-frase-larga-y-nueva',
    });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText(/Todas sus sesiones se han cerrado/)).toBeInTheDocument();
    // El formulario desaparece: dejarlo con los campos vacíos invita a repetir la
    // operación sobre una contraseña que ya no es la actual.
    expect(screen.queryByPlaceholderText('Contraseña actual')).not.toBeInTheDocument();
  });

  it('los motivos que devuelve la política de contraseñas se enseñan enteros', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockRejectedValue(
      new Error(
        'La contraseña no cumple la política:\n- Debe tener al menos 12 caracteres\n- No puede ser una contraseña conocida',
      ),
    );
    montar();
    await rellenar(usuario, { actual: 'x', nueva: 'corta', repetida: 'corta' });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    // Los dos motivos, no solo el primero: si no, la persona los descubre a base de
    // intentos y cada intento cuenta contra el límite de tasa.
    expect(await screen.findByText(/al menos 12 caracteres/)).toBeInTheDocument();
    expect(screen.getByText(/contraseña conocida/)).toBeInTheDocument();
    // El formulario sigue ahí para corregir, con lo escrito intacto.
    expect(screen.getByPlaceholderText('Contraseña actual')).toBeInTheDocument();
  });

  it('un fallo sin mensaje no deja el aviso en blanco', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockRejectedValue(new Error(''));
    montar();
    await rellenar(usuario, { actual: 'x', nueva: 'y', repetida: 'y' });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText(/No se pudo cambiar la contraseña/)).toBeInTheDocument();
  });

  it('mientras se guarda, el botón queda inhabilitado y no se puede enviar dos veces', async () => {
    const usuario = userEvent.setup();
    let terminar;
    changeOwnPassword.mockImplementation(
      () => new Promise((r) => { terminar = () => r({ mensaje: 'Hecho.' }); }),
    );
    montar();
    await rellenar(usuario, {
      actual: 'la-de-siempre',
      nueva: 'una-frase-larga-y-nueva',
      repetida: 'una-frase-larga-y-nueva',
    });

    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));

    const boton = await screen.findByRole('button', { name: 'Guardando…' });
    expect(boton).toBeDisabled();
    await usuario.click(boton);
    expect(changeOwnPassword).toHaveBeenCalledTimes(1);

    terminar();
    expect(await screen.findByText('Hecho.')).toBeInTheDocument();
  });

  it('cancelar cierra el formulario y borra el aviso de error anterior', async () => {
    const usuario = userEvent.setup();
    changeOwnPassword.mockRejectedValue(new Error('Contraseña actual incorrecta.'));
    montar();
    await rellenar(usuario, { actual: 'mal', nueva: 'aaaaaaaaaaaa', repetida: 'aaaaaaaaaaaa' });
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText(/actual incorrecta/)).toBeInTheDocument();

    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByText(/actual incorrecta/)).not.toBeInTheDocument();

    // Y al volver a abrirlo, no reaparece el error de la vez anterior.
    await usuario.click(screen.getByRole('button', { name: 'Cambiar mi contraseña' }));
    expect(screen.queryByText(/actual incorrecta/)).not.toBeInTheDocument();
  });

  it('los tres campos son de tipo contraseña y no se autocompletan entre sí', async () => {
    const usuario = userEvent.setup();
    montar();
    await usuario.click(screen.getByRole('button', { name: 'Cambiar mi contraseña' }));

    const actual = screen.getByPlaceholderText('Contraseña actual');
    const nueva = screen.getByPlaceholderText(/Contraseña nueva/);
    expect(actual).toHaveAttribute('type', 'password');
    expect(actual).toHaveAttribute('autoComplete', 'current-password');
    // `new-password` es lo que impide que el gestor rellene la nueva con la vieja.
    expect(nueva).toHaveAttribute('autoComplete', 'new-password');
    expect(nueva).toHaveAttribute('minLength', '12');
  });

  it('avisa de que el cambio cierra todas las sesiones, incluida la actual', async () => {
    const usuario = userEvent.setup();
    montar();
    await usuario.click(screen.getByRole('button', { name: 'Cambiar mi contraseña' }));
    expect(screen.getByText(/incluida esta/)).toBeInTheDocument();
  });
});
