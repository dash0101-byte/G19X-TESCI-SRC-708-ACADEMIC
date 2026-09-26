// ============================================================================
// Recorrer la página de interés y la ficha 360 solo con el teclado
// ============================================================================
//
// `axe` mira el marcado. Esto mira el **recorrido**: qué pasa al pulsar `Tab` una vez tras
// otra, que es una cosa distinta y la que de verdad usa quien no puede usar el ratón.
//
// Son las dos pantallas que pide el capítulo, y son las dos que importan por motivos
// opuestos:
//
// * **La página de interés** es la única pública. Quien la abre no tiene cuenta, llega desde
//   un enlace y puede estar usando cualquier cosa. Si el formulario no se puede rellenar con
//   el teclado, esa persona no entra al sistema y nadie se enteraría nunca.
// * **La ficha 360** es una ventana modal, y una ventana modal es el sitio donde el foco se
//   pierde. Hasta el capítulo 36 se perdía: ver `ventanaModal.js` para la lista de las cinco
//   cosas que le faltaban.
//
// Lo que estas pruebas NO pueden comprobar, y dónde se comprueba
// --------------------------------------------------------------
// **Si el aro de foco se VE.** Eso son píxeles y `jsdom` no los tiene. Se comprueba de otras
// dos formas, las dos aquí abajo: que la hoja no quite el aro del navegador sin poner otro
// en su lugar (`el aro de foco`), y que el color de ese otro llega al mínimo de la norma
// (`contraste.test.js`, par `--border-focus`).

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { HOJA } from './contraste.js';

vi.mock('../services/api', async (importOriginal) => {
  const real = await importOriginal();
  return Object.fromEntries(Object.keys(real).map((clave) => [clave, vi.fn()]));
});

import * as api from '../services/api';
import PaginaDeInteres from '../components/PaginaDeInteres.jsx';
import LeadDetailModal from '../components/LeadDetailModal.jsx';
import KPICards from '../components/KPICards.jsx';
import Navbar from '../components/Navbar.jsx';

const OPCIONES = {
  cargos: ['CTO', 'CIO'],
  sectores: ['FinTech', 'Software/TI'],
  tamanos: ['1-10', '51-200'],
  necesidades: { vacantes: 'Cubrir vacantes de TI', demo: 'Ver una demostración' },
};

const PUBLICACION = {
  titulo: 'Post · Talento TI septiembre',
  descripcion: '¿Tu equipo de TI tarda meses en cubrir una vacante?',
  opciones: OPCIONES,
};

const PROSPECTO = {
  id: 7,
  first_name: 'Ana', last_name: 'Ruiz', email: 'ana.ruiz@empresa.test',
  phone: '+525512345678', company: 'Empresa de Pruebas', job_title: 'CTO',
  industry: 'FinTech', company_size: '51-200', country: 'México', city: 'Monterrey',
  status: 'PROPOSAL_SENT', score_category: 'WARM', current_score: 47.8,
  conversion_probability: 0.41, raw_metadata: {}, latest_explanation: {}, activities: [],
};

beforeEach(() => {
  for (const clave of Object.keys(api)) {
    if (typeof api[clave]?.mockReset === 'function') api[clave].mockReset();
  }
  api.getCurrentUserRole.mockReturnValue('Commercial_Executive');
  api.fetchPublicacionDeInteres.mockResolvedValue(PUBLICACION);
  api.enviarInteres.mockResolvedValue({
    mensaje: 'Gracias por tu interés. Un asesor de PluriOne se pondrá en contacto contigo.',
    recibido_en: '2026-09-25T12:00:00Z',
  });
  api.fetchSalesReps.mockResolvedValue({ total: 0, items: [] });
});

/** Cómo se anuncia lo que tiene el foco ahora mismo, para leer un fallo sin adivinar. */
function foco() {
  const nodo = document.activeElement;
  if (!nodo || nodo === document.body) return '(el body: el foco se perdió)';
  const etiqueta = nodo.labels?.[0]?.textContent?.trim();
  return [
    nodo.tagName.toLowerCase(),
    nodo.id && `#${nodo.id}`,
    etiqueta && `«${etiqueta}»`,
    !etiqueta && nodo.textContent?.trim().slice(0, 30),
  ].filter(Boolean).join(' ');
}

/**
 * Pulsa `Tab` hasta que el foco cumpla la condición, o falla diciendo dónde se quedó.
 *
 * Por qué no se cuentan las pulsaciones a mano: `jsdom` **no oculta el contenido de un
 * `<details>` cerrado**. En un navegador, el teléfono y el perfil de LinkedIn están fuera del
 * recorrido mientras «Añadir más datos» esté plegado; aquí se visitan igual. Contar
 * pulsaciones ataría la prueba a esa diferencia del entorno en vez de a lo que se comprueba,
 * que es que se llega con el teclado y en el orden correcto.
 */
async function tabHasta(usuario, condicion, limite = 20) {
  for (let i = 0; i < limite; i += 1) {
    await usuario.tab();
    if (condicion(document.activeElement)) return document.activeElement;
  }
  throw new Error(`No se llegó con el tabulador; el foco quedó en ${foco()}`);
}

/** Pulsa `Tab` hasta `limite` veces y devuelve por dónde fue pasando el foco. */
async function recorrer(usuario, limite = 40) {
  const visitados = [];
  for (let i = 0; i < limite; i += 1) {
    await usuario.tab();
    const nodo = document.activeElement;
    if (!nodo || nodo === document.body) break;
    if (visitados.includes(nodo)) break; // dio la vuelta
    visitados.push(nodo);
  }
  return visitados;
}

// ---------------------------------------------------------------------------
describe('la página de interés, solo con el teclado', () => {
  it('el recorrido va en el orden en que se lee la pantalla', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    const visitados = await recorrer(usuario);
    const ids = visitados.map((n) => n.id || n.tagName.toLowerCase());

    // Los campos en el orden en que están escritos. Si alguien añadiera un `tabindex`
    // positivo para «arreglar» algo, este orden se rompería sin que nada más fallara: la
    // pantalla se vería igual y el formulario se rellenaría a saltos.
    //
    // El teléfono y el perfil de LinkedIn aparecen aquí porque `jsdom` no oculta el
    // contenido de un `<details>` cerrado. En un navegador solo se visitan tras desplegar
    // «Añadir más datos», y entonces el orden es exactamente este. Se deja la lista entera y
    // no una parte: lo que esta prueba defiende es la SECUENCIA, y recortarla dejaría sin
    // comprobar que los dos opcionales van después de los obligatorios y antes del aviso.
    expect(ids.filter((id) => id.startsWith('interes-'))).toEqual([
      'interes-nombre',
      'interes-correo',
      'interes-empresa',
      'interes-cargo',
      'interes-tamano',
      'interes-sector',
      // «¿Qué necesitas?» son radios y no llevan `id`: el tabulador entra en el grupo una
      // vez y dentro se mueve con las flechas, que es el comportamiento nativo y el correcto.
      'interes-telefono',
      'interes-linkedin',
      'interes-aviso',
    ]);
  });

  it('todo lo que hay que rellenar se alcanza sin tocar el ratón', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    const visitados = await recorrer(usuario);

    // Cada control que la persona necesita para enviar la solicitud tiene que estar en el
    // recorrido. Se comprueba por su etiqueta y no por su `id`: es lo que la persona ve.
    const imprescindibles = [
      screen.getByLabelText('Nombre'),
      screen.getByLabelText('Correo de trabajo'),
      screen.getByLabelText('Empresa'),
      screen.getByLabelText('Cargo'),
      screen.getByLabelText('Empleados'),
      screen.getByLabelText('Sector'),
      screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }),
      screen.getByLabelText(/Acepto el aviso de privacidad/),
      screen.getByRole('button', { name: 'Quiero que me contacten' }),
    ];
    for (const control of imprescindibles) {
      expect(visitados, `no se llega con el tabulador a: ${control.id || control.textContent}`)
        .toContain(control);
    }
  });

  it('el campo trampa queda fuera del recorrido', async () => {
    // Está oculto para la vista y para el lector, y con `tabIndex={-1}`. Si entrara en el
    // recorrido, quien navega con el teclado lo rellenaría sin saberlo y el servidor le
    // descartaría la solicitud por parecer un robot. Es el fallo más cruel posible: la
    // persona hace todo bien y el sistema no le dice nada.
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    const visitados = await recorrer(usuario);
    expect(visitados).not.toContain(document.getElementById('interes-sitio-web'));
  });

  it('se rellena y se envía entera con el teclado, sin un solo clic', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    // Nada de `usuario.click` en toda la prueba: solo `tab`, `keyboard` y `selectOptions`
    // sobre el elemento que ya tiene el foco.
    await usuario.tab();
    await usuario.keyboard('Ana Prueba');
    await usuario.tab();
    await usuario.keyboard('ana.prueba@empresa.test');
    await usuario.tab();
    await usuario.keyboard('Ejemplo SA');
    await usuario.tab();
    await usuario.selectOptions(document.activeElement, 'CTO');
    await usuario.tab();
    await usuario.selectOptions(document.activeElement, '51-200');
    await usuario.tab();
    await usuario.selectOptions(document.activeElement, 'FinTech');
    // El grupo de radios: se entra con `Tab` y se elige con la barra espaciadora.
    await tabHasta(usuario, (n) => n.type === 'radio');
    await usuario.keyboard(' ');
    // La casilla del aviso.
    await tabHasta(usuario, (n) => n.type === 'checkbox');
    await usuario.keyboard(' ');
    // Y el botón de enviar, con Enter.
    await tabHasta(usuario, (n) => n.tagName === 'BUTTON' && n.type === 'submit');
    expect(document.activeElement).toHaveAccessibleName('Quiero que me contacten');
    await usuario.keyboard('{Enter}');

    await waitFor(() => expect(api.enviarInteres).toHaveBeenCalled());
    const [, enviado] = api.enviarInteres.mock.calls[0];
    expect(enviado.nombre).toBe('Ana Prueba');
    expect(enviado.aviso_de_privacidad).toBe(true);
    expect(enviado.sitio_web).toBe('');
  });

  it('al enviar, el foco va al acuse de recibo y no al vacío', async () => {
    // El formulario entero desaparece al enviar. Sin llevar el foco a algún sitio, queda en
    // el `<body>`: para quien navega con el teclado, la página se queda muda y el siguiente
    // `Tab` empieza desde arriba, y no hay forma de saber si se envió.
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    await usuario.type(screen.getByLabelText('Nombre'), 'Ana Prueba');
    await usuario.type(screen.getByLabelText('Correo de trabajo'), 'ana.prueba@empresa.test');
    await usuario.type(screen.getByLabelText('Empresa'), 'Ejemplo SA');
    await usuario.selectOptions(screen.getByLabelText('Cargo'), 'CTO');
    await usuario.selectOptions(screen.getByLabelText('Empleados'), '51-200');
    await usuario.selectOptions(screen.getByLabelText('Sector'), 'FinTech');
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    await usuario.click(screen.getByLabelText(/Acepto el aviso de privacidad/));
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const acuse = await screen.findByRole('heading', { name: /Gracias por tu interés/ });
    await waitFor(() => expect(document.activeElement, foco()).toBe(acuse));
    // Y está dentro de una región que el lector anuncia.
    expect(acuse.closest('[role="status"]')).not.toBeNull();
  });

  it('al enviar en blanco, el foco va al primer campo que falta y lleva su error atado', async () => {
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const nombre = screen.getByLabelText('Nombre');
    await waitFor(() => expect(document.activeElement, foco()).toBe(nombre));
    expect(nombre).toHaveAttribute('aria-invalid', 'true');
    // El mensaje no está solo al lado: está atado al campo, así que el lector lo dice al
    // llegar el foco. Esto es lo que hace que el error se «anuncie» sin una región viva.
    const descrito = nombre.getAttribute('aria-describedby');
    expect(document.getElementById(descrito)).toHaveTextContent('Escribe tu nombre.');
  });

  it('un campo plegado se despliega antes de mandarle el foco', async () => {
    // Si el servidor devuelve un 422 sobre el teléfono o el perfil de LinkedIn —que viven
    // dentro de «Añadir más datos»—, mandar el foco a un campo que está dentro de un
    // `<details>` cerrado lo mandaría a la nada.
    api.enviarInteres.mockRejectedValue(Object.assign(new Error('no vale'), {
      status: 422,
      detalle: [{ loc: ['body', 'linkedin'], msg: 'Value error, el perfil no tiene la forma esperada' }],
    }));
    const usuario = userEvent.setup();
    render(<PaginaDeInteres slug="Qm9sYS1kZS1wcnVlYmEtMQ" />);
    await screen.findByLabelText('Cargo');

    await usuario.type(screen.getByLabelText('Nombre'), 'Ana Prueba');
    await usuario.type(screen.getByLabelText('Correo de trabajo'), 'ana.prueba@empresa.test');
    await usuario.type(screen.getByLabelText('Empresa'), 'Ejemplo SA');
    await usuario.selectOptions(screen.getByLabelText('Cargo'), 'CTO');
    await usuario.selectOptions(screen.getByLabelText('Empleados'), '51-200');
    await usuario.selectOptions(screen.getByLabelText('Sector'), 'FinTech');
    await usuario.click(screen.getByRole('radio', { name: 'Cubrir vacantes de TI' }));
    await usuario.click(screen.getByLabelText(/Acepto el aviso de privacidad/));
    await usuario.click(screen.getByRole('button', { name: 'Quiero que me contacten' }));

    const linkedin = await screen.findByLabelText('Tu perfil de LinkedIn');
    await waitFor(() => expect(document.activeElement, foco()).toBe(linkedin));
    expect(linkedin.closest('details')).toHaveAttribute('open');
  });
});

// ---------------------------------------------------------------------------
describe('la ficha 360, solo con el teclado', () => {
  /** Monta un botón que abre la ficha, para poder comprobar a dónde vuelve el foco. */
  function conAbridor() {
    function Pantalla() {
      const [abierta, setAbierta] = useState(false);
      return (
        <div>
          <button type="button" onClick={() => setAbierta(true)}>Abrir la ficha</button>
          {abierta && (
            <LeadDetailModal
              lead={PROSPECTO}
              onClose={() => setAbierta(false)}
              onLeadUpdated={vi.fn()}
            />
          )}
        </div>
      );
    }
    render(<Pantalla />);
  }

  it('es una ventana con nombre, y lo dice', async () => {
    render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} />);

    const ventana = await screen.findByRole('dialog');
    expect(ventana).toHaveAttribute('aria-modal', 'true');
    // El nombre es el del prospecto, no «diálogo». Es la diferencia entre que el lector
    // diga «se abrió algo» y que diga «ficha de Ana Ruiz».
    expect(ventana).toHaveAccessibleName('Ana Ruiz');
  });

  it('al abrirse, el foco entra dentro', async () => {
    const usuario = userEvent.setup();
    conAbridor();

    await usuario.click(screen.getByRole('button', { name: 'Abrir la ficha' }));
    const ventana = await screen.findByRole('dialog');

    // Sin esto, el foco se quedaba en el botón de la fila de la tabla: quien navega con el
    // tabulador tenía que recorrer la tabla, el menú y el pie para llegar a una ventana que
    // visualmente estaba delante de todo.
    await waitFor(() => expect(ventana.contains(document.activeElement), foco()).toBe(true));
  });

  it('el tabulador no se sale de la ventana: da la vuelta', async () => {
    const usuario = userEvent.setup();
    render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} />);
    const ventana = await screen.findByRole('dialog');

    // Sesenta pulsaciones, muchas más que los controles que hay: si el ciclo estuviera roto,
    // en alguna se saldría. Antes se salía en la primera vuelta, a una página tapada por el
    // velo donde el foco es invisible.
    for (let i = 0; i < 60; i += 1) {
      await usuario.tab();
      expect(ventana.contains(document.activeElement), `vuelta ${i}: ${foco()}`).toBe(true);
    }
  });

  it('y hacia atrás tampoco', async () => {
    const usuario = userEvent.setup();
    render(<LeadDetailModal lead={PROSPECTO} onClose={vi.fn()} onLeadUpdated={vi.fn()} />);
    const ventana = await screen.findByRole('dialog');

    for (let i = 0; i < 20; i += 1) {
      await usuario.tab({ shift: true });
      expect(ventana.contains(document.activeElement), `vuelta ${i}: ${foco()}`).toBe(true);
    }
  });

  it('`Escape` la cierra', async () => {
    const usuario = userEvent.setup();
    const onClose = vi.fn();
    render(<LeadDetailModal lead={PROSPECTO} onClose={onClose} onLeadUpdated={vi.fn()} />);
    await screen.findByRole('dialog');

    await usuario.keyboard('{Escape}');

    // Con el ratón se cierra pulsando en el velo. Sin ratón no había ninguna forma de
    // cerrarla salvo encontrar la «×» a base de tabulador.
    expect(onClose).toHaveBeenCalled();
  });

  it('al cerrarse, el foco vuelve a donde estaba', async () => {
    const usuario = userEvent.setup();
    conAbridor();
    const abridor = screen.getByRole('button', { name: 'Abrir la ficha' });

    await usuario.click(abridor);
    await screen.findByRole('dialog');
    await usuario.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    // Si no vuelve, cae al `<body>` y el siguiente `Tab` empieza a recorrer la página desde
    // arriba: para quien no ve la pantalla, es perder el sitio.
    await waitFor(() => expect(document.activeElement, foco()).toBe(abridor));
  });
});

// ---------------------------------------------------------------------------
describe('el aro de foco', () => {
  it('la hoja no quita el aro del navegador sin poner otro en su lugar', async () => {
    // Que el aro se VEA son píxeles, y aquí no hay. Lo que sí se puede comprobar es la causa
    // de casi todos los casos en que no se ve: un `outline: none` suelto. La hoja tiene uno
    // —en `.input-field`— y a su lado un `:focus` que pone un borde en su lugar, cuyo color
    // se mide en `contraste.test.js`. La regla es: quien quite el aro, pone otro.
    const sinAro = [...HOJA.matchAll(/([^{}]+)\{([^}]*outline\s*:\s*(?:none|0)[^}]*)\}/g)]
      .map((m) => m[1].trim().split('\n').pop().trim())
      .filter((selector) => !selector.startsWith('@'));

    expect(sinAro.length, 'ninguna regla quita el aro; si eso cambia, hay que revisar esto')
      .toBeGreaterThan(0);

    for (const selector of sinAro) {
      const base = selector.split(',')[0].trim();
      const reemplazo = new RegExp(
        `${base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:(focus|focus-visible)`,
      );
      expect(
        HOJA,
        `«${base}» hace outline: none y no tiene ninguna regla :focus que ponga otro aro. `
        + 'Quien navega con el teclado no sabría dónde está.',
      ).toMatch(reemplazo);
    }
  });

  it('no hay ningún `tabindex` positivo en ningún componente', () => {
    // Un `tabindex` mayor que cero saca a ese elemento de su sitio y lo pone ANTES de todo
    // lo que no lo lleve, en toda la página. Es la forma más habitual de romper un orden de
    // foco que estaba bien, y no se nota mirando la pantalla.
    const rutas = recorrerJsx('src');
    // Sin esto, un recorrido que no encontrara nada —una ruta mal resuelta— pasaría la
    // comprobación sin haber mirado un solo archivo.
    expect(rutas.length).toBeGreaterThan(20);

    for (const ruta of rutas) {
      const codigo = readFileSync(ruta, 'utf8');
      const positivos = [...codigo.matchAll(/tabIndex=\{?["']?(\d+)/g)]
        .map((m) => Number(m[1]))
        .filter((n) => n > 0);
      expect(positivos, `${ruta} usa tabIndex positivo: ${positivos.join(', ')}`).toEqual([]);
    }
  });
});

function recorrerJsx(directorio) {
  const encontrados = [];
  for (const entrada of readdirSync(directorio)) {
    const ruta = join(directorio, entrada);
    if (statSync(ruta).isDirectory()) encontrados.push(...recorrerJsx(ruta));
    else if (ruta.endsWith('.jsx')) encontrados.push(ruta);
  }
  return encontrados;
}

// ---------------------------------------------------------------------------
// Lo que hasta este capítulo solo se podía pulsar con el ratón
// ---------------------------------------------------------------------------
//
// Cuatro controles del panel se dibujaban con `<div onClick>`. Un `<div>` con un manejador
// de clic **no está en el recorrido del tabulador y no responde a Enter**: se ve pulsable
// —llevan `cursor: pointer`— y con el teclado no se puede pulsar.
//
// Los cuatro son ahora `<button>`, y estas pruebas lo fijan. No es una comprobación de
// estilo: la pastilla de la sesión era la única puerta al menú donde se cierra sesión y se
// cambia la contraseña, así que sin ratón no se podía hacer ninguna de las dos cosas.
describe('los controles que eran divs', () => {
  it('las tres tarjetas de categoría son botones y filtran con Enter', async () => {
    const usuario = userEvent.setup();
    const filtrar = vi.fn();
    render(
      <KPICards
        summary={{
          total_leads: 10, hot_leads_count: 3, warm_leads_count: 4, cold_leads_count: 3,
        }}
        onFilterCategory={filtrar}
      />,
    );

    // La cuarta tarjeta —«Total Prospectos»— NO filtra, y por eso no es un botón: anunciarla
    // como control diría que se puede pulsar algo que no hace nada.
    const botones = screen.getAllByRole('button');
    expect(botones).toHaveLength(3);

    await usuario.tab();
    expect(document.activeElement, foco()).toBe(botones[0]);
    await usuario.keyboard('{Enter}');
    expect(filtrar).toHaveBeenCalledWith('HOT');

    await usuario.tab();
    await usuario.keyboard('{Enter}');
    expect(filtrar).toHaveBeenCalledWith('WARM');

    await usuario.tab();
    await usuario.keyboard(' ');
    expect(filtrar).toHaveBeenCalledWith('COLD');
  });

  it('la pastilla de la sesión se alcanza con el tabulador y se abre con Enter', async () => {
    const usuario = userEvent.setup();
    const abrirSesion = vi.fn();
    api.fetchAvisos.mockResolvedValue({ total: 0, sin_leer: 0, items: [] });
    render(
      <Navbar
        activeTab="hoy"
        setActiveTab={vi.fn()}
        onOpenNewLead={vi.fn()}
        currentRole="Sales_Lead"
        user={{ name: 'Laura Líder', badge: 'Líder Comercial', avatar: 'LL' }}
        onOpenSessionModal={abrirSesion}
        onSelectLead={vi.fn()}
      />,
    );

    const pastilla = await tabHasta(
      usuario,
      (n) => n.getAttribute?.('title') === 'Ver perfil o cambiar usuario',
      30,
    );
    await usuario.keyboard('{Enter}');

    // Sin esto no hay forma de cerrar sesión sin ratón.
    expect(abrirSesion).toHaveBeenCalled();
    expect(pastilla.tagName).toBe('BUTTON');
  });
});
