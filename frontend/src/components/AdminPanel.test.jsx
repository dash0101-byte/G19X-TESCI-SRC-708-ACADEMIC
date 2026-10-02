// ============================================================================
// Panel de administración: la cartera de las cuentas dadas de baja
// ============================================================================
//
// Dar de baja una cuenta conserva sus prospectos a su nombre, a propósito. Lo que faltaba
// era la otra mitad: verlos y repartirlos. Estas pruebas no cubren el panel entero —eso lo
// dice §17.9 y sigue siendo cierto—, sino lo que la Fase 13 le añadió: que el aviso aparezca
// en la vista por defecto, que es donde la cartera de quien se fue dejaba de verse, y que el
// reparto solo ofrezca destinos que puedan atenderla.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchSalesReps: vi.fn(),
  fetchUsers: vi.fn(),
  createUser: vi.fn(),
  changeUserRole: vi.fn(),
  deactivateUser: vi.fn(),
  activateUser: vi.fn(),
  resetUserPassword: vi.fn(),
  transferPortfolio: vi.fn(),
  getCurrentUserRole: vi.fn(),
}));

import {
  createUser, fetchSalesReps, fetchUsers, getCurrentUserRole, resetUserPassword, transferPortfolio,
} from '../services/api';
import AdminPanel from './AdminPanel.jsx';

function asesor(id, nombre, { activo = true, asignados = 0 } = {}) {
  return {
    id,
    full_name: nombre,
    email: `${nombre.split(' ')[0].toLowerCase()}@plurione.test`,
    role: 'Commercial_Executive',
    is_active: activo,
    is_sales_rep: true,
    capacity: 50,
    leads_asignados: asignados,
    must_change_password: false,
  };
}

const MARTA = asesor(7, 'Marta Baja Ruiz', { activo: false, asignados: 12 });
const ANA = asesor(3, 'Ana Activa Soto', { asignados: 20 });
const PEDRO = asesor(4, 'Pedro Activo Luna', { asignados: 5 });

function montar() {
  render(<AdminPanel onBatchRecalculate={vi.fn()} isRecalculating={false} />);
}

beforeEach(() => {
  vi.clearAllMocks();
  getCurrentUserRole.mockReturnValue('Sales_Lead');
});

describe('la cartera de las cuentas dadas de baja', () => {
  it('sin prospectos en cuentas de baja no avisa de nada', async () => {
    fetchSalesReps.mockResolvedValue({ total: 2, items: [ANA, PEDRO], prospectos_en_cuentas_de_baja: 0 });
    montar();
    expect(await screen.findByText('Ana Activa Soto')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('avisa aunque el listado oculte las bajas, y lleva a verlas', async () => {
    fetchSalesReps.mockResolvedValue({ total: 2, items: [ANA, PEDRO], prospectos_en_cuentas_de_baja: 12 });
    const usuario = userEvent.setup();
    montar();

    const aviso = await screen.findByRole('alert');
    expect(aviso).toHaveTextContent('Hay 12 prospectos asignados a cuentas dadas de baja');
    await usuario.click(within(aviso).getByRole('button', { name: 'Ver cuentas de baja' }));

    await waitFor(() => expect(fetchSalesReps).toHaveBeenLastCalledWith({ incluirInactivos: true }));
  });

  it('reparte la cartera de una baja a un asesor activo', async () => {
    fetchSalesReps.mockResolvedValue({ total: 3, items: [MARTA, ANA, PEDRO], prospectos_en_cuentas_de_baja: 12 });
    transferPortfolio.mockResolvedValue({
      origen_id: 7, destino_id: 4, movidos: 12, carga_del_destino: 17, supera_capacidad: false,
    });
    const usuario = userEvent.setup();
    montar();

    const destino = await screen.findByLabelText('Asesor que recibe la cartera de Marta Baja Ruiz');
    const boton = screen.getByRole('button', { name: 'Repartir' });
    expect(boton).toBeDisabled();

    await usuario.selectOptions(destino, 'Pedro Activo Luna');
    await usuario.click(boton);

    await waitFor(() => expect(transferPortfolio).toHaveBeenCalledWith(7, 4));
    expect(
      await screen.findByText('12 prospectos de Marta Baja Ruiz pasan a Pedro Activo Luna.'),
    ).toBeInTheDocument();
  });

  it('no ofrece como destino a otra cuenta de baja', async () => {
    const OLGA = asesor(8, 'Olga También Baja', { activo: false, asignados: 2 });
    fetchSalesReps.mockResolvedValue({ total: 3, items: [MARTA, OLGA, ANA], prospectos_en_cuentas_de_baja: 14 });
    montar();

    const destino = await screen.findByLabelText('Asesor que recibe la cartera de Marta Baja Ruiz');
    const opciones = within(destino).getAllByRole('option').map((o) => o.textContent);
    expect(opciones).toEqual(['Repartir a…', 'Ana Activa Soto']);
  });

  it('una baja sin prospectos no enseña el control de reparto', async () => {
    const VACIA = asesor(9, 'Vicente Sin Cartera', { activo: false, asignados: 0 });
    fetchSalesReps.mockResolvedValue({ total: 2, items: [VACIA, ANA], prospectos_en_cuentas_de_baja: 0 });
    montar();

    expect(await screen.findByText('Vicente Sin Cartera')).toBeInTheDocument();
    expect(screen.queryByLabelText(/recibe la cartera de Vicente/)).not.toBeInTheDocument();
  });
});

// ============================================================================
// Capítulo 40: el 422 del alta de una cuenta
// ============================================================================

describe('un 422 al dar de alta una cuenta', () => {
  async function altaQueFalla(detalle) {
    const usuario = userEvent.setup();
    getCurrentUserRole.mockReturnValue('System_Admin');
    fetchSalesReps.mockResolvedValue({ items: [ANA], prospectos_en_cuentas_de_baja: 0 });
    fetchUsers.mockResolvedValue({ items: [ANA] });
    const err = new Error('Error de validación');
    err.status = 422;
    err.detalle = detalle;
    createUser.mockRejectedValue(err);

    montar();
    await screen.findByRole('heading', { name: 'Alta de cuenta' });
    await usuario.type(screen.getByLabelText('Nombre completo'), 'A');
    await usuario.type(screen.getByLabelText('Correo institucional'), 'nueva@plurione.test');
    await usuario.type(screen.getByLabelText('Contraseña inicial (mín. 12)'), 'unafraselargaybuena');
    await usuario.click(screen.getByRole('button', { name: 'Crear cuenta' }));
    await waitFor(() => expect(createUser).toHaveBeenCalled());
    return usuario;
  }

  it('señala el campo y lo explica en castellano', async () => {
    await altaQueFalla([{
      type: 'string_too_short',
      loc: ['body', 'full_name'],
      msg: 'String should have at least 2 characters',
      ctx: { min_length: 2 },
    }]);

    const nombre = screen.getByLabelText('Nombre completo');
    await waitFor(() => expect(nombre).toHaveAttribute('aria-invalid', 'true'));
    const explicacion = document.getElementById(nombre.getAttribute('aria-describedby'));
    expect(explicacion.textContent).toBe('Tiene que tener al menos 2 caracteres.');
    // Ni el nombre de la columna ni el inglés de Pydantic.
    expect(document.body.textContent).not.toMatch(/full_name/);
    expect(document.body.textContent).not.toMatch(/String should have/);
  });

  it('el aviso de un fallo se anuncia como alerta y no como estado', async () => {
    // Este aviso servía para las dos cosas con `role="status"`. Un error anunciado como
    // estado espera a que el lector de pantalla acabe lo que esté diciendo, y lo que avisa
    // de que una operación no se hizo no puede esperar.
    await altaQueFalla([{ type: 'missing', loc: ['body', 'email'], msg: 'Field required' }]);

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Revise el campo Correo institucional/);
    expect(aviso.className).toContain('alert-error');
  });

  it('un error que no es de un campo sigue yendo al aviso general', async () => {
    const usuario = userEvent.setup();
    getCurrentUserRole.mockReturnValue('System_Admin');
    fetchSalesReps.mockResolvedValue({ items: [ANA], prospectos_en_cuentas_de_baja: 0 });
    fetchUsers.mockResolvedValue({ items: [ANA] });
    const conflicto = new Error('Ese correo ya tiene cuenta.');
    conflicto.status = 409;
    createUser.mockRejectedValue(conflicto);

    montar();
    await screen.findByRole('heading', { name: 'Alta de cuenta' });
    await usuario.type(screen.getByLabelText('Nombre completo'), 'Ana Nueva');
    await usuario.type(screen.getByLabelText('Correo institucional'), 'ana@plurione.test');
    await usuario.type(screen.getByLabelText('Contraseña inicial (mín. 12)'), 'unafraselargaybuena');
    await usuario.click(screen.getByRole('button', { name: 'Crear cuenta' }));

    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toMatch(/Ese correo ya tiene cuenta/);
    expect(screen.getByLabelText('Correo institucional')).not.toHaveAttribute('aria-invalid');
  });
});

// ============================================================================
// La contraseña de otra cuenta ya no se teclea en un cuadro del navegador
// ============================================================================
//
// Hasta el capítulo 43 esto era un `window.prompt`, y de los tres cuadros del navegador que
// quedaban en el cliente era el peor: **un `prompt` escribe en claro**. Fijar la contraseña
// de una cuenta ajena obligaba a teclearla a la vista de cualquiera, sin repetición que
// comprobara la errata, sin los requisitos delante y sin que el 422 de la política pudiera
// señalar nada —cuando llegaba, el cuadro ya se había cerrado con la contraseña dentro—.
//
// §6.4 contaba los `alert()` y no mencionaba este. Tampoco había prueba: un cuadro del
// navegador no está en el documento, así que no hay nada que consultar.
describe('restablecer la contraseña de otra cuenta', () => {
  const ADMIN_Y_UNA_CUENTA = () => {
    getCurrentUserRole.mockReturnValue('System_Admin');
    fetchSalesReps.mockResolvedValue({ items: [ANA], prospectos_en_cuentas_de_baja: 0 });
    fetchUsers.mockResolvedValue({ items: [ANA] });
  };

  /** Abre el formulario de restablecimiento de la única cuenta de la tabla. */
  async function abrir() {
    const usuario = userEvent.setup();
    ADMIN_Y_UNA_CUENTA();
    montar();
    await usuario.click(await screen.findByRole('button', { name: 'Restablecer contraseña' }));
    return usuario;
  }

  it('pide la contraseña en la página, oculta y con repetición', async () => {
    const cuadroDelNavegador = vi.fn(() => 'la-que-sea');
    vi.stubGlobal('prompt', cuadroDelNavegador);

    await abrir();

    const nueva = screen.getByLabelText(/Contraseña nueva para Ana Activa Soto/);
    const repetida = screen.getByLabelText('Repítala');
    expect(nueva).toHaveAttribute('type', 'password');
    expect(repetida).toHaveAttribute('type', 'password');
    expect(nueva.className).toContain('input-field');
    // Y el foco está donde estaba al abrirse el cuadro, que era lo único que hacía bien.
    expect(nueva).toHaveFocus();
    expect(cuadroDelNavegador).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it('los requisitos están a la vista antes de escribir nada', async () => {
    await abrir();
    expect(screen.getByText(/Mínimo 12 caracteres/)).toBeInTheDocument();
    expect(screen.getByText(/Se cerrarán todas sus sesiones/)).toBeInTheDocument();
  });

  it('una errata al repetirla no gasta una llamada al servidor', async () => {
    // El servidor no puede comprobar esto: solo le llega una contraseña. Con el `prompt` no
    // había repetición que comprobar, así que la errata se descubría al no poder entrar.
    const usuario = await abrir();
    await usuario.type(screen.getByLabelText(/Contraseña nueva para/), 'una-frase-larga-y-buena');
    await usuario.type(screen.getByLabelText('Repítala'), 'una-frase-larga-y-otra');
    await usuario.click(screen.getByRole('button', { name: 'Fijar contraseña' }));

    expect(screen.getByText('No coincide con la contraseña de arriba.')).toBeInTheDocument();
    expect(resetUserPassword).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Repítala')).toHaveAttribute('aria-invalid', 'true');
  });

  it('con las dos iguales la fija y cierra el formulario', async () => {
    resetUserPassword.mockResolvedValue({ id: 3 });
    const usuario = await abrir();
    await usuario.type(screen.getByLabelText(/Contraseña nueva para/), 'una-frase-larga-y-buena');
    await usuario.type(screen.getByLabelText('Repítala'), 'una-frase-larga-y-buena');
    await usuario.click(screen.getByRole('button', { name: 'Fijar contraseña' }));

    await waitFor(() => expect(resetUserPassword).toHaveBeenCalledWith(3, 'una-frase-larga-y-buena'));
    await waitFor(() => expect(screen.queryByLabelText('Repítala')).not.toBeInTheDocument());
    expect(await screen.findByRole('status')).toHaveTextContent(/restablecida/);
  });

  it('si la política la rechaza, los motivos van debajo del campo y lo escrito se queda', async () => {
    const rechazo = new Error('La contraseña no cumple la política del sistema.\nEs demasiado común.');
    rechazo.status = 422;
    rechazo.detalle = {
      mensaje: 'La contraseña no cumple la política del sistema.',
      motivos: ['Es demasiado común.'],
    };
    resetUserPassword.mockRejectedValue(rechazo);

    const usuario = await abrir();
    await usuario.type(screen.getByLabelText(/Contraseña nueva para/), 'plurione-plurione');
    await usuario.type(screen.getByLabelText('Repítala'), 'plurione-plurione');
    await usuario.click(screen.getByRole('button', { name: 'Fijar contraseña' }));

    const nueva = screen.getByLabelText(/Contraseña nueva para/);
    await waitFor(() => expect(nueva).toHaveAttribute('aria-invalid', 'true'));
    const explicacion = document.getElementById(nueva.getAttribute('aria-describedby'));
    expect(explicacion.textContent).toContain('no cumple la política');
    const aviso = await screen.findByRole('alert');
    expect(aviso.textContent).toContain('Revise el campo Contraseña nueva.');
    expect(aviso.textContent).toContain('Es demasiado común.');
    // El formulario sigue abierto y con lo escrito: cerrarlo obligaría a teclear otra vez
    // doce caracteres por un motivo que ya está en pantalla.
    expect(nueva).toHaveValue('plurione-plurione');
  });

  it('cancelar lo cierra sin llamar a nadie', async () => {
    const usuario = await abrir();
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.queryByLabelText('Repítala')).not.toBeInTheDocument();
    expect(resetUserPassword).not.toHaveBeenCalled();
  });
});
