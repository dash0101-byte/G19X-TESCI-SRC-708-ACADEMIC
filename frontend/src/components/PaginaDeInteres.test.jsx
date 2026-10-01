// ============================================================================
// La página de interés (pública)
// ============================================================================
//
// Es la única pantalla sin sesión, y un formulario de treinta segundos. Se comprueba:
// * que enseña el título y el texto de la publicación;
// * que las listas son las que manda el servidor y no unas escritas aquí;
// * que obligatorio es solo lo imprescindible, y que teléfono y LinkedIn van plegados;
// * que no se pregunta la facturación ni se envía nada sobre ella;
// * que «¿Qué necesitas?» se elige con un toque;
// * que cada error aparece junto a su campo, también los que devuelve el servidor;
// * que sin aceptar el aviso no se envía nada;
// * que el campo trampa está oculto y fuera del tabulador;
// * que un enlace que ya no vale dice «no disponible» y no enseña formulario.

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchPublicacionDeInteres: vi.fn(),
  enviarInteres: vi.fn(),
}));

import { enviarInteres, fetchPublicacionDeInteres } from '../services/api';
import PaginaDeInteres from './PaginaDeInteres.jsx';

const SLUG = 'Qm9sYS1kZS1wcnVlYmEtMQ';
const GRACIAS = 'Gracias por tu interés. Un asesor de PluriOne se pondrá en contacto contigo.';
const ENVIAR = { name: 'Quiero que me contacten' };

const PUBLICACION = {
  titulo: 'Post · Talento TI septiembre',
  descripcion: '¿Tu equipo de TI tarda meses en cubrir una vacante?',
  opciones: {
    cargos: ['CTO', 'CIO', 'Gerente de Talento TI'],
    sectores: ['FinTech', 'Software/TI', 'Education'],
    tamanos: ['1-10', '51-200', '201-1000'],
    necesidades: { vacantes: 'Cubrir vacantes de TI', demo: 'Ver una demostración' },
  },
};

beforeEach(() => {
  fetchPublicacionDeInteres.mockReset().mockResolvedValue(PUBLICACION);
  enviarInteres.mockReset().mockResolvedValue({ mensaje: GRACIAS, recibido_en: '2026-09-17T12:00:00Z' });
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function abrir() {
  render(<PaginaDeInteres slug={SLUG} />);
  await screen.findByLabelText('Cargo');
}

async function rellenar(usuario, { aviso = true } = {}) {
  await usuario.type(screen.getByLabelText('Nombre'), 'Ana Prueba');
  await usuario.type(screen.getByLabelText('Correo de trabajo'), 'ana.prueba@empresa.test');
  await usuario.type(screen.getByLabelText('Empresa'), 'Ejemplo SA');
  await usuario.selectOptions(screen.getByLabelText('Cargo'), 'CTO');
  await usuario.selectOptions(screen.getByLabelText('Empleados'), '201-1000');
  await usuario.selectOptions(screen.getByLabelText('Sector'), 'FinTech');
  await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
  if (aviso) await usuario.click(screen.getByLabelText(/Acepto el aviso de privacidad/));
}

describe('lo que enseña', () => {
  it('el título y el texto de la publicación', async () => {
    render(<PaginaDeInteres slug={SLUG} />);

    expect(await screen.findByRole('heading', { name: PUBLICACION.titulo })).toBeInTheDocument();
    expect(screen.getByText(PUBLICACION.descripcion)).toBeInTheDocument();
    // Sin `?r=` en la dirección, la red viaja vacía y el servidor la cuenta como «sin red».
    expect(fetchPublicacionDeInteres).toHaveBeenCalledWith(SLUG, '');
  });

  it('las listas que manda el servidor, y ninguna escrita aquí', async () => {
    await abrir();

    const opciones = (etiqueta) =>
      within(screen.getByLabelText(etiqueta))
        .getAllByRole('option')
        .map((o) => o.value)
        .filter(Boolean);

    expect(opciones('Cargo')).toEqual(PUBLICACION.opciones.cargos);
    expect(opciones('Sector')).toEqual(PUBLICACION.opciones.sectores);
    expect(opciones('Empleados')).toEqual(PUBLICACION.opciones.tamanos);
    const botones = within(screen.getByRole('group', { name: '¿Qué necesitas?' })).getAllByRole('radio');
    expect(botones.map((b) => b.value)).toEqual(Object.keys(PUBLICACION.opciones.necesidades));
  });

  it('obligatorio solo lo imprescindible; teléfono y LinkedIn, plegados', async () => {
    await abrir();

    for (const etiqueta of ['Nombre', 'Correo de trabajo', 'Empresa', 'Cargo', 'Empleados', 'Sector']) {
      expect(screen.getByLabelText(etiqueta)).toBeRequired();
    }
    const mas = screen.getByText('Añadir más datos (opcional)').closest('details');
    expect(mas).not.toHaveAttribute('open');
    expect(within(mas).getByLabelText('Teléfono')).not.toBeRequired();
    expect(within(mas).getByLabelText('Tu perfil de LinkedIn')).not.toBeRequired();
  });

  it('un texto largo se recorta y se despliega con «Leer más»', async () => {
    const usuario = userEvent.setup();
    const largo = 'Montar un equipo de TI completo tarda meses. '.repeat(5);
    fetchPublicacionDeInteres.mockResolvedValue({ ...PUBLICACION, descripcion: largo });
    await abrir();

    const texto = document.getElementById('interes-descripcion');
    expect(texto).toHaveClass('recortada');
    await usuario.click(screen.getByRole('button', { name: 'Leer más' }));
    expect(texto).not.toHaveClass('recortada');
    expect(screen.getByRole('button', { name: 'Leer menos' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('un texto corto no lleva «Leer más»', async () => {
    await abrir();

    expect(screen.queryByRole('button', { name: 'Leer más' })).not.toBeInTheDocument();
  });

  it('no pregunta la facturación', async () => {
    await abrir();

    expect(screen.queryByText(/facturación|ingresos/i)).not.toBeInTheDocument();
  });

  it('demasiadas visitas desde la misma conexión no se confunden con un enlace roto', async () => {
    const limite = new Error('Hemos recibido demasiadas solicitudes. Inténtalo más tarde.');
    limite.status = 429;
    fetchPublicacionDeInteres.mockRejectedValue(limite);
    render(<PaginaDeInteres slug={SLUG} />);

    expect(await screen.findByRole('heading', { name: 'Ahora mismo no podemos atenderte' })).toBeInTheDocument();
    expect(screen.getByText(/demasiadas solicitudes/)).toBeInTheDocument();
    expect(screen.queryByText(/no está disponible/)).not.toBeInTheDocument();
  });

  it('un enlace que ya no vale dice que no está disponible y no pide nada', async () => {
    fetchPublicacionDeInteres.mockRejectedValue(new Error('Esta publicación no está disponible.'));
    render(<PaginaDeInteres slug={SLUG} />);

    expect(await screen.findByRole('heading', { name: /no está disponible/ })).toBeInTheDocument();
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
  });
});

describe('el envío', () => {
  it('manda lo indicado, `null` lo opcional vacío y nada sobre ingresos', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await rellenar(usuario);
    await usuario.click(screen.getByRole('button', ENVIAR));

    await waitFor(() => expect(enviarInteres).toHaveBeenCalledTimes(1));
    const [slug, datos] = enviarInteres.mock.calls[0];
    expect(slug).toBe(SLUG);
    expect(datos).toEqual({
      nombre: 'Ana Prueba',
      correo: 'ana.prueba@empresa.test',
      empresa: 'Ejemplo SA',
      cargo: 'CTO',
      tamano_de_empresa: '201-1000',
      sector: 'FinTech',
      necesidad: 'vacantes',
      aviso_de_privacidad: true,
      telefono: null,
      linkedin: null,
      sitio_web: '',
    });
  });

  it('los opcionales viajan cuando se despliegan y se rellenan', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await rellenar(usuario);
    await usuario.click(screen.getByText('Añadir más datos (opcional)'));
    await usuario.type(screen.getByLabelText('Teléfono'), '+52 55 1234 5678');
    await usuario.type(screen.getByLabelText('Tu perfil de LinkedIn'), 'linkedin.com/in/ana-prueba');
    await usuario.click(screen.getByRole('button', ENVIAR));

    await waitFor(() => expect(enviarInteres).toHaveBeenCalled());
    const datos = enviarInteres.mock.calls[0][1];
    expect(datos.telefono).toBe('+52 55 1234 5678');
    expect(datos.linkedin).toBe('linkedin.com/in/ana-prueba');
  });

  it('«¿Qué necesitas?» se elige con un toque y se puede cambiar', async () => {
    const usuario = userEvent.setup();
    await abrir();

    const demo = screen.getByRole('radio', { name: 'Ver una demostración' });
    await usuario.click(demo);
    expect(demo).toBeChecked();
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    expect(demo).not.toBeChecked();
  });

  it('después de enviar agradece y ya no pide nada más', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await rellenar(usuario);
    await usuario.click(screen.getByRole('button', ENVIAR));

    expect(await screen.findByRole('heading', { name: GRACIAS })).toBeInTheDocument();
    expect(screen.queryByLabelText('Cargo')).not.toBeInTheDocument();
  });
});

describe('los errores, junto a su campo', () => {
  it('vacío, cada campo dice lo suyo al lado y el foco va al primero', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await usuario.click(screen.getByRole('button', ENVIAR));

    expect(enviarInteres).not.toHaveBeenCalled();
    const nombre = screen.getByLabelText('Nombre');
    expect(nombre).toHaveAttribute('aria-invalid', 'true');
    expect(nombre).toHaveAccessibleDescription('Escribe tu nombre.');
    expect(screen.getByLabelText('Correo de trabajo')).toHaveAccessibleDescription(/correo válido/);
    expect(screen.getByLabelText('Empleados')).toHaveAccessibleDescription('Elige el tamaño de tu empresa.');
    expect(screen.getByRole('group', { name: '¿Qué necesitas?' })).toHaveAccessibleDescription('Elige qué necesitas.');
    expect(screen.getByRole('checkbox')).toHaveAccessibleDescription(/aceptar el aviso de privacidad/);
    // Ningún bloque de errores arriba: cada uno está donde hay que corregirlo.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await waitFor(() => expect(nombre).toHaveFocus());
  });

  it('el error de un campo se va en cuanto se corrige', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await usuario.click(screen.getByRole('button', ENVIAR));
    await usuario.type(screen.getByLabelText('Nombre'), 'Ana');

    expect(screen.getByLabelText('Nombre')).not.toHaveAttribute('aria-invalid');
    expect(screen.queryByText('Escribe tu nombre.')).not.toBeInTheDocument();
    expect(screen.getByText('Escribe el nombre de tu empresa.')).toBeInTheDocument();
  });

  it('sin aceptar el aviso no se envía nada', async () => {
    const usuario = userEvent.setup();
    await abrir();

    await rellenar(usuario, { aviso: false });
    await usuario.click(screen.getByRole('button', ENVIAR));

    expect(screen.getByRole('checkbox')).toHaveAccessibleDescription(/aviso de privacidad/);
    expect(enviarInteres).not.toHaveBeenCalled();
  });

  it('un 422 del servidor se reparte por campo y despliega el opcional que falló', async () => {
    const usuario = userEvent.setup();
    const rechazo = new Error('linkedin: El perfil tiene que ser una dirección de LinkedIn');
    rechazo.status = 422;
    rechazo.detalle = [{
      loc: ['body', 'linkedin'],
      msg: 'Value error, El perfil tiene que ser una dirección de LinkedIn como https://www.linkedin.com/in/tu-perfil',
    }];
    enviarInteres.mockRejectedValue(rechazo);
    await abrir();

    await rellenar(usuario);
    await usuario.click(screen.getByText('Añadir más datos (opcional)'));
    await usuario.type(screen.getByLabelText('Tu perfil de LinkedIn'), 'facebook.com/ana');
    // Se pliega otra vez: el error tiene que volver a abrirlo.
    await usuario.click(screen.getByText('Añadir más datos (opcional)'));
    await usuario.click(screen.getByRole('button', ENVIAR));

    const perfil = await screen.findByLabelText('Tu perfil de LinkedIn');
    await waitFor(() => expect(perfil).toHaveAttribute('aria-invalid', 'true'));
    expect(perfil).toHaveAccessibleDescription(/El perfil tiene que ser una dirección de LinkedIn/);
    expect(perfil.closest('details')).toHaveAttribute('open');
    expect(screen.queryByText(/Value error/)).not.toBeInTheDocument();
  });

  it('un rechazo que no es de un campo se explica arriba y el formulario sigue en pantalla', async () => {
    const usuario = userEvent.setup();
    const limite = new Error('Hemos recibido demasiadas solicitudes. Inténtalo más tarde.');
    limite.status = 429;
    enviarInteres.mockRejectedValue(limite);
    await abrir();

    await rellenar(usuario);
    await usuario.click(screen.getByRole('button', ENVIAR));

    expect(await screen.findByRole('alert')).toHaveTextContent('demasiadas solicitudes');
    expect(screen.getByLabelText('Cargo')).toBeInTheDocument();
  });
});

describe('el campo trampa', () => {
  it('está oculto, fuera del tabulador y se envía vacío', async () => {
    const usuario = userEvent.setup();
    await abrir();

    const trampa = document.getElementById('interes-sitio-web');
    expect(trampa).toHaveAttribute('tabindex', '-1');
    expect(trampa.closest('[aria-hidden="true"]')).not.toBeNull();
    // `aria-hidden` lo saca del árbol de accesibilidad: no existe como campo para quien
    // usa un lector de pantalla, aunque siga en el documento.
    expect(screen.queryByRole('textbox', { name: 'No rellene este campo' })).not.toBeInTheDocument();

    await rellenar(usuario);
    await usuario.click(screen.getByRole('button', ENVIAR));

    await waitFor(() => expect(enviarInteres).toHaveBeenCalled());
    expect(enviarInteres.mock.calls[0][1].sitio_web).toBe('');
  });
});

describe('el perfil de LinkedIn', () => {
  it('no lo bloquea el navegador: se puede pegar tal como lo da la aplicación', async () => {
    await abrir();
    const campo = screen.getByLabelText('Tu perfil de LinkedIn');

    // Con `type="url"` el navegador rechaza «linkedin.com/in/perfil» antes de enviar nada,
    // con un aviso suyo que no dice qué falta. El servidor completa el esquema y quita los
    // parámetros que añade LinkedIn al compartir.
    expect(campo).toHaveAttribute('type', 'text');
    expect(campo).toHaveAttribute('inputMode', 'url');
    expect(screen.getByText(/pegarlo tal como te lo dé la aplicación/i)).toBeInTheDocument();
  });
});

describe('la vista previa desde el panel', () => {
  it('se pinta igual, sin pedir nada al servidor público y sin poder enviar', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug={SLUG} vistaPrevia={PUBLICACION} />);

    expect(screen.getByRole('heading', { name: PUBLICACION.titulo })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Vista previa');
    expect(screen.getByLabelText('Cargo')).toBeInTheDocument();
    expect(fetchPublicacionDeInteres).not.toHaveBeenCalled();

    const boton = screen.getByRole('button', { name: 'Quiero que me contacten' });
    expect(boton).toBeDisabled();
    await usuario.click(boton);
    expect(enviarInteres).not.toHaveBeenCalled();
  });

  it('el motivo está junto al botón, no solo arriba del todo', async () => {
    // Encontrado usándolo (01-10-2026): el aviso de «vista previa» estaba encima del
    // título y el botón, varias pantallas más abajo dentro de un marco de 375 px. Quien
    // llegaba al botón lo pulsaba, no pasaba nada —un botón desactivado ni siquiera
    // dispara el evento— y no había nada cerca que lo explicara.
    render(<PaginaDeInteres slug={SLUG} vistaPrevia={PUBLICACION} />);

    const boton = screen.getByRole('button', { name: 'Quiero que me contacten' });
    const explicacion = document.getElementById(boton.getAttribute('aria-describedby'));

    expect(explicacion, 'el botón desactivado debe decir por qué').not.toBeNull();
    expect(explicacion).toHaveTextContent(/desactivado porque esto es la vista previa/i);
    expect(explicacion).toHaveTextContent(/no se envía nada/i);
    // Y pegado: el aviso de arriba sigue estando, pero no es el que resuelve esto.
    expect(boton.parentElement).toContainElement(explicacion);
  });

  it('fuera de la vista previa, ni el botón está desactivado ni sobra la explicación', () => {
    render(<PaginaDeInteres slug={SLUG} />);

    return screen.findByLabelText('Cargo').then(() => {
      const boton = screen.getByRole('button', { name: 'Quiero que me contacten' });
      expect(boton).toBeEnabled();
      expect(boton).not.toHaveAttribute('aria-describedby');
      expect(screen.queryByText(/desactivado porque esto es la vista previa/i)).not.toBeInTheDocument();
    });
  });

  it('enseña las opciones de «¿Qué necesitas?» de esa publicación', () => {
    const propias = { ...PUBLICACION, opciones: { ...PUBLICACION.opciones, necesidades: { hablar: 'Hablar con alguien', equipo: 'Montar un equipo' } } };
    render(<PaginaDeInteres slug={SLUG} vistaPrevia={propias} />);

    const botones = within(screen.getByRole('group', { name: '¿Qué necesitas?' })).getAllByRole('radio');
    expect(botones.map((b) => b.value)).toEqual(['hablar', 'equipo']);
  });
});
