// ============================================================================
// Lo que el formulario dice, ¿llega a quien no ve la pantalla?
// ============================================================================
//
// Un mensaje de error que aparece en pantalla no existe para un lector de pantalla salvo que
// se cumpla una de estas dos cosas, y son distintas:
//
// * **Se anuncia**: vive en una región viva —`role="alert"` o `role="status"`— que ya estaba
//   en el documento antes de que apareciera el texto. El lector lo lee en el momento, sin
//   que la persona tenga que ir a buscarlo. Es lo que hace falta para un error que no
//   pertenece a ningún campo: «correo o contraseña incorrectos», «el servidor no responde».
// * **Se asocia**: el mensaje lleva un `id` y el campo lo señala con `aria-describedby`,
//   más `aria-invalid` para decir que ese campo está mal. El lector lo lee **al llegar el
//   foco al campo**. Es lo que hace falta para un error que sí pertenece a un campo, porque
//   además dice a cuál.
//
// Un formulario bien hecho usa las dos, cada una donde toca. Este archivo comprueba que así
// sea en los tres formularios que una persona de fuera o una cuenta nueva van a usar.
//
// La tercera cosa, que no es un `role` y se olvida siempre
// --------------------------------------------------------
// **Cuando la pantalla se sustituye entera, el foco tiene que ir a algún sitio.** El acuse
// de recibo de la página de interés borraba el formulario y con él el botón que tenía el
// foco, así que este caía al `<body>`. Y la región `aria-live` que anunciaba el mensaje se
// creaba **en el mismo instante** que su contenido, que es justo el caso en que los lectores
// no la leen: una región viva anuncia lo que CAMBIA dentro de ella, y para eso tiene que
// haber estado ahí antes. El recorrido de foco está en `teclado.test.jsx`; aquí se comprueba
// la otra mitad, que el acuse esté dentro de una región anunciable.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import * as api from '../services/api';
import PaginaDeInteres from '../components/PaginaDeInteres.jsx';
import LoginScreen from '../components/LoginScreen.jsx';
import CambioDeContrasenaObligatorio from '../components/CambioDeContrasenaObligatorio.jsx';
import NewLeadModal from '../components/NewLeadModal.jsx';
import LeadDetailModal from '../components/LeadDetailModal.jsx';

const PUBLICACION = {
  titulo: 'Post · Talento TI septiembre',
  descripcion: '¿Tu equipo de TI tarda meses en cubrir una vacante?',
  opciones: {
    cargos: ['CTO'], sectores: ['FinTech'], tamanos: ['51-200'],
    necesidades: { vacantes: 'Cubrir vacantes de TI' },
  },
};

const PROSPECTO = {
  id: 7, first_name: 'Ana', last_name: 'Ruiz', email: 'ana.ruiz@empresa.test',
  phone: '+525512345678', company: 'Empresa de Pruebas', job_title: 'CTO',
  industry: 'FinTech', company_size: '51-200', country: 'México', city: 'Monterrey',
  status: 'PROPOSAL_SENT', score_category: 'WARM', current_score: 47.8,
  conversion_probability: 0.41, raw_metadata: {}, latest_explanation: {}, activities: [],
};

const USUARIO_NUEVO = {
  id: 9, email: 'nuevo@plurione.test', full_name: 'Luis Nuevo',
  role: 'Commercial_Executive', must_change_password: true,
};

beforeEach(() => {
  for (const clave of Object.keys(api)) {
    if (typeof api[clave]?.mockReset === 'function') api[clave].mockReset();
  }
  api.getCurrentUserRole.mockReturnValue('Commercial_Executive');
  api.fetchPublicacionDeInteres.mockResolvedValue(PUBLICACION);
  api.fetchSalesReps.mockResolvedValue({ total: 0, items: [] });
});

/** ¿Está este texto dentro de una región que un lector de pantalla anuncia? */
function seAnuncia(nodo) {
  return Boolean(nodo.closest('[role="alert"], [role="status"], [aria-live]'));
}

// ---------------------------------------------------------------------------
describe('la página de interés', () => {
  async function abrir() {
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');
  }

  it('cada error de campo va atado a su campo, y dice que el campo está mal', async () => {
    const usuario = userEvent.setup();
    await abrir();
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));
    await screen.findByText('Escribe tu nombre.');

    // Los seis obligatorios más el aviso. Se recorren todos y no uno de muestra: el defecto
    // que esto persigue es que UNO se quede sin atar, y comprobar uno solo no lo vería.
    const campos = [
      ['Nombre', 'Escribe tu nombre.'],
      ['Correo de trabajo', 'Escribe un correo válido, como nombre@empresa.com.'],
      ['Empresa', 'Escribe el nombre de tu empresa.'],
      ['Cargo', 'Elige tu cargo.'],
      ['Empleados', 'Elige el tamaño de tu empresa.'],
      ['Sector', 'Elige el sector.'],
      [/Acepto el aviso de privacidad/, 'Hay que aceptar el aviso de privacidad para enviar la solicitud.'],
    ];
    for (const [etiqueta, texto] of campos) {
      const campo = screen.getByLabelText(etiqueta);
      expect(campo, `${etiqueta} no se marca como inválido`).toHaveAttribute('aria-invalid', 'true');
      const id = campo.getAttribute('aria-describedby');
      expect(id, `${etiqueta} no apunta a su mensaje`).toBeTruthy();
      // El `aria-describedby` puede llevar varios ids —el perfil de LinkedIn lleva su ayuda
      // y su error—, así que se busca el texto entre todos los que nombra.
      const dicho = id.split(/\s+/).map((i) => document.getElementById(i)?.textContent).join(' ');
      expect(dicho, `${etiqueta} no describe su error`).toContain(texto);
    }
  });

  it('«¿Qué necesitas?» ata el error al grupo, porque el error es del grupo', async () => {
    // Es un `fieldset` de radios: el error no es de un botón concreto sino de no haber
    // elegido ninguno, así que el `aria-describedby` va en el grupo y no en el primer radio.
    const usuario = userEvent.setup();
    await abrir();
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const grupo = await screen.findByRole('group', { name: '¿Qué necesitas?' });
    const id = grupo.getAttribute('aria-describedby');
    expect(document.getElementById(id)).toHaveTextContent('Elige qué necesitas.');
  });

  it('un error que no es de ningún campo sí se anuncia', async () => {
    // El servidor caído, o un 429. No pertenece a ningún campo, así que nadie va a llegar a
    // él con el foco: si no se anuncia, no existe.
    api.enviarInteres.mockRejectedValue(
      Object.assign(new Error('Ahora mismo no podemos atenderte. Inténtalo en un minuto.'), { status: 503 }),
    );
    const usuario = userEvent.setup();
    await abrir();

    await usuario.type(screen.getByLabelText('Nombre'), 'Ana Prueba');
    await usuario.type(screen.getByLabelText('Correo de trabajo'), 'ana@empresa.test');
    await usuario.type(screen.getByLabelText('Empresa'), 'Ejemplo SA');
    await usuario.selectOptions(screen.getByLabelText('Cargo'), 'CTO');
    await usuario.selectOptions(screen.getByLabelText('Empleados'), '51-200');
    await usuario.selectOptions(screen.getByLabelText('Sector'), 'FinTech');
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    await usuario.click(screen.getByLabelText(/Acepto el aviso de privacidad/));
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const aviso = await screen.findByText(/Ahora mismo no podemos atenderte/);
    expect(seAnuncia(aviso), 'el error general no está en una región viva').toBe(true);
  });

  it('el acuse de recibo también se anuncia', async () => {
    api.enviarInteres.mockResolvedValue({
      mensaje: 'Gracias por tu interés. Un asesor de PluriOne se pondrá en contacto contigo.',
      recibido_en: '2026-09-25T12:00:00Z',
    });
    const usuario = userEvent.setup();
    await abrir();

    await usuario.type(screen.getByLabelText('Nombre'), 'Ana Prueba');
    await usuario.type(screen.getByLabelText('Correo de trabajo'), 'ana@empresa.test');
    await usuario.type(screen.getByLabelText('Empresa'), 'Ejemplo SA');
    await usuario.selectOptions(screen.getByLabelText('Cargo'), 'CTO');
    await usuario.selectOptions(screen.getByLabelText('Empleados'), '51-200');
    await usuario.selectOptions(screen.getByLabelText('Sector'), 'FinTech');
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    await usuario.click(screen.getByLabelText(/Acepto el aviso de privacidad/));
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const gracias = await screen.findByRole('heading', { name: /Gracias por tu interés/ });
    expect(seAnuncia(gracias), 'el acuse no está en una región viva').toBe(true);
  });
});

// ---------------------------------------------------------------------------
describe('la pantalla de acceso', () => {
  it('«correo o contraseña incorrectos» se anuncia', async () => {
    // Era el caso que faltaba, y la asimetría lo delataba: el error del SEGUNDO paso —el del
    // código— ya llevaba `role="alert"` desde el capítulo 35 y el del primero no. Quien
    // escribe mal la contraseña veía el mensaje; quien no ve la pantalla se quedaba
    // esperando a que ocurriera algo.
    api.login.mockRejectedValue(new Error('Correo o contraseña incorrectos.'));
    const usuario = userEvent.setup();
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await usuario.type(screen.getByLabelText(/Correo/), 'quien@plurione.test');
    await usuario.type(screen.getByLabelText(/Contraseña/), 'una-contrasena-larga');
    await usuario.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    const error = await screen.findByText('Correo o contraseña incorrectos.');
    expect(seAnuncia(error), 'el error del primer paso no se anuncia').toBe(true);
  });

  it('y el del código también', async () => {
    api.login.mockResolvedValue({ tipo: 'segundo_factor', desafio: 'un-desafio', expira_en: 300 });
    api.completarLoginConSegundoFactor.mockRejectedValue(new Error('El código no es válido.'));
    const usuario = userEvent.setup();
    render(<LoginScreen onAuthenticated={vi.fn()} />);

    await usuario.type(screen.getByLabelText(/Correo/), 'quien@plurione.test');
    await usuario.type(screen.getByLabelText(/Contraseña/), 'una-contrasena-larga');
    await usuario.click(screen.getByRole('button', { name: 'Iniciar sesión' }));
    await usuario.type(await screen.findByLabelText('Código'), '123456');
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }));

    const error = await screen.findByText('El código no es válido.');
    expect(seAnuncia(error)).toBe(true);
  });

  it('el aviso de que la sesión caducó se anuncia', async () => {
    render(<LoginScreen onAuthenticated={vi.fn()} expiredNotice />);
    const aviso = screen.getByText(/Su sesión expiró por inactividad/);
    expect(seAnuncia(aviso)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
describe('el cambio de contraseña obligatorio', () => {
  it('el motivo del rechazo se anuncia', async () => {
    // Es la pantalla donde el mensaje más importa: el servidor rechaza la contraseña nueva
    // por reglas que la pantalla no repite —longitud, lista de filtradas—, así que sin el
    // anuncio no hay forma de saber por qué no la acepta.
    api.changeOwnPassword.mockRejectedValue(
      new Error('Esa contraseña aparece en listas de contraseñas filtradas.'),
    );
    const usuario = userEvent.setup();
    render(<CambioDeContrasenaObligatorio user={USUARIO_NUEVO} onCompletado={vi.fn()} onSalir={vi.fn()} />);

    const campos = screen.getAllByLabelText(/contraseña/i);
    await usuario.type(campos[0], 'La-Que-Me-Dieron-1');
    await usuario.type(campos[1], 'Una-Contrasena-Larguisima-2');
    await usuario.type(campos[2], 'Una-Contrasena-Larguisima-2');
    await usuario.click(screen.getByRole('button', { name: /Cambiar|Guardar|Continuar/ }));

    const error = await screen.findByText(/listas de contraseñas filtradas/);
    expect(seAnuncia(error)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
describe('los formularios del panel', () => {
  it('el error del alta de prospecto se anuncia', async () => {
    api.createLead.mockRejectedValue(new Error('Ya existe un prospecto con ese correo.'));
    const usuario = userEvent.setup();
    render(<NewLeadModal onClose={vi.fn()} onLeadCreated={vi.fn()} />);

    await usuario.type(screen.getByLabelText('Nombre *'), 'Ana');
    await usuario.type(screen.getByLabelText('Apellido *'), 'Prueba');
    await usuario.type(screen.getByLabelText('Correo Electrónico *'), 'ana@empresa.test');
    await usuario.type(screen.getByLabelText('Empresa / Institución'), 'Ejemplo SA');
    await usuario.click(screen.getByRole('button', { name: /Registrar|Crear|Guardar/ }));

    const error = await screen.findByText(/Ya existe un prospecto con ese correo/);
    expect(seAnuncia(error)).toBe(true);
  });

  it('«Prospecto actualizado» se anuncia', async () => {
    // El mensaje que el capítulo 33 se encargó de que no mintiera —antes decía que había
    // guardado un vaciado que no guardaba—. Que no llegue a quien no ve la pantalla deja
    // aquel trabajo a medias: sigue sin saber si se guardó.
    api.updateLead.mockResolvedValue({ ...PROSPECTO, company: 'Empresa Nueva' });
    const usuario = userEvent.setup();
    render(
      <LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} startInEditMode />,
    );

    await usuario.click(screen.getByRole('button', { name: /Guardar/ }));

    await waitFor(async () => {
      const aviso = await screen.findByText(/actualizado/i);
      expect(seAnuncia(aviso), '«Prospecto actualizado» no se anuncia').toBe(true);
    });
  });
});
