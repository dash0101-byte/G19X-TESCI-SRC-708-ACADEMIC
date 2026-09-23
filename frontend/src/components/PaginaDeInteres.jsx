import React, { useCallback, useEffect, useRef, useState } from 'react';
import { enviarInteres, fetchPublicacionDeInteres } from '../services/api';

// La página a la que lleva el enlace de una publicación de LinkedIn. Es la única pantalla
// sin sesión: quien la abre no tiene cuenta ni la va a tener.
//
// Un formulario de treinta segundos. Obligatorio solo lo que el asesor necesita para llamar
// y el modelo para puntuar; el teléfono y el perfil de LinkedIn van plegados bajo «Añadir
// más datos», y la facturación ya no se pregunta. Una sola columna pensada para un teléfono
// de 375 px, porque es desde donde se abre un enlace de LinkedIn.
//
// Las listas de cargo, sector y tamaño NO se escriben aquí: las manda el servidor, que las
// toma de las del modelo. Escritas en el cliente acabarían diciendo algo parecido pero
// distinto —«Tecnología» en vez de «Software/TI»—, y el modelo descarta en silencio lo que
// no reconoce.
const VACIO = {
  nombre: '',
  correo: '',
  empresa: '',
  cargo: '',
  tamano_de_empresa: '',
  sector: '',
  necesidad: '',
  aviso_de_privacidad: false,
  telefono: '',
  linkedin: '',
  // Campo trampa: oculto para las personas, irresistible para un robot que rellena todo.
  sitio_web: '',
};

// Lo que se dice junto a cada campo cuando falta o no vale. El servidor valida lo mismo;
// aquí se adelanta para que el error aparezca al lado del campo y no en un bloque arriba.
const FALTA = {
  nombre: 'Escribe tu nombre.',
  correo: 'Escribe un correo válido, como nombre@empresa.com.',
  empresa: 'Escribe el nombre de tu empresa.',
  cargo: 'Elige tu cargo.',
  tamano_de_empresa: 'Elige el tamaño de tu empresa.',
  sector: 'Elige el sector.',
  necesidad: 'Elige qué necesitas.',
  aviso_de_privacidad: 'Hay que aceptar el aviso de privacidad para enviar la solicitud.',
};

// Los campos en el orden en que aparecen: el foco va al primero que tenga un error.
const ORDEN = [
  'nombre', 'correo', 'empresa', 'cargo', 'tamano_de_empresa', 'sector', 'necesidad',
  'aviso_de_privacidad', 'telefono', 'linkedin',
];
const OPCIONALES = new Set(['telefono', 'linkedin']);
const CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// A partir de aquí el texto del post se recorta a tres líneas en un teléfono.
const LARGA = 140;

function validar(formulario) {
  const errores = {};
  for (const campo of ['nombre', 'empresa', 'cargo', 'tamano_de_empresa', 'sector', 'necesidad']) {
    if (!String(formulario[campo]).trim()) errores[campo] = FALTA[campo];
  }
  if (!CORREO.test(formulario.correo.trim())) errores.correo = FALTA.correo;
  if (!formulario.aviso_de_privacidad) errores.aviso_de_privacidad = FALTA.aviso_de_privacidad;
  return errores;
}

// Un 422 del servidor trae, por campo, qué no valió. Se reparte junto a cada campo. Para
// los campos que la página ya comprueba se usa su propio texto —el del validador de correo
// llega en inglés—; para el perfil de LinkedIn y el teléfono, el del servidor, que ya
// explica qué forma espera.
function erroresDelServidor(detalle) {
  if (!Array.isArray(detalle)) return null;
  const errores = {};
  for (const item of detalle) {
    const campo = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
    if (!ORDEN.includes(campo) || errores[campo]) continue;
    errores[campo] = FALTA[campo] || String(item.msg || '').replace(/^(Value error|Assertion failed),\s*/, '');
  }
  return Object.keys(errores).length ? errores : null;
}

// `red`: por dónde llegó quien abre la página (`?r=whatsapp`). Solo viaja al servidor, que
// decide si la reconoce; la página no la enseña ni la usa para nada más.
//
// `vistaPrevia`: lo que devuelve `/publicaciones/{id}/vista-previa`. Con él, la página se
// pinta **igual** que la verá el interesado —el mismo componente, no una imitación— pero no
// pide nada al servidor público ni envía: el botón queda desactivado y un aviso lo dice.
export default function PaginaDeInteres({ slug, red = '', vistaPrevia = null }) {
  const [publicacion, setPublicacion] = useState(vistaPrevia);
  const [cargando, setCargando] = useState(!vistaPrevia);
  const [noDisponible, setNoDisponible] = useState(null);
  const [formulario, setFormulario] = useState(VACIO);
  const [errores, setErrores] = useState({});
  const [error, setError] = useState('');
  const [masDatos, setMasDatos] = useState(false);
  const [descripcionCompleta, setDescripcionCompleta] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [gracias, setGracias] = useState('');
  const formularioRef = useRef(null);

  const cargar = useCallback(async () => {
    if (vistaPrevia) {
      setPublicacion(vistaPrevia);
      return;
    }
    setCargando(true);
    try {
      setPublicacion(await fetchPublicacionDeInteres(slug, red));
    } catch (err) {
      // Un 429 no es «no disponible»: la publicación existe y se podrá abrir en un rato.
      // Decir lo contrario manda a la persona a buscar otro enlace que tampoco funcionará.
      setNoDisponible(err.status === 429 ? { espera: err.message } : { mensaje: err.message });
    } finally {
      setCargando(false);
    }
  }, [slug, red, vistaPrevia]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cambiar = (nombre, valor) => {
    setFormulario((previo) => ({ ...previo, [nombre]: valor }));
    // El error de un campo se va en cuanto se corrige, sin esperar a volver a enviar.
    setErrores((previo) => {
      if (!previo[nombre]) return previo;
      const resto = { ...previo };
      delete resto[nombre];
      return resto;
    });
  };

  const enfocarPrimerError = (encontrados) => {
    const primero = ORDEN.find((campo) => encontrados[campo]);
    if (!primero) return;
    if (OPCIONALES.has(primero)) setMasDatos(true);
    // Tras el render: si el campo estaba plegado, aún no está en el documento.
    setTimeout(() => {
      const nodo = formularioRef.current?.querySelector(`[data-campo="${primero}"]`);
      nodo?.focus();
    }, 0);
  };

  const enviar = async (e) => {
    e.preventDefault();
    if (vistaPrevia) return;
    setError('');
    const encontrados = validar(formulario);
    setErrores(encontrados);
    if (Object.keys(encontrados).length) {
      enfocarPrimerError(encontrados);
      return;
    }
    setEnviando(true);
    try {
      const respuesta = await enviarInteres(
        slug,
        {
          ...formulario,
          telefono: formulario.telefono.trim() || null,
          linkedin: formulario.linkedin.trim() || null,
        },
        // La misma red con la que se abrió la página: así el envío cuenta donde contó la
        // visita, aunque la persona tarde un rato en rellenar el formulario.
        red,
      );
      setGracias(respuesta.mensaje);
    } catch (err) {
      const porCampo = err.status === 422 ? erroresDelServidor(err.detalle) : null;
      if (porCampo) {
        setErrores(porCampo);
        enfocarPrimerError(porCampo);
      } else {
        setError(err.message);
      }
    } finally {
      setEnviando(false);
    }
  };

  if (cargando) {
    return <main style={envoltorio}><p style={{ color: 'var(--text-muted)' }}>Cargando...</p></main>;
  }

  if (noDisponible) {
    return (
      <main style={envoltorio}>
        <section className="glass-panel" style={panel}>
          {noDisponible.espera ? (
            <>
              <h1 style={titulo}>Ahora mismo no podemos atenderte</h1>
              <p style={{ color: 'var(--text-secondary)' }}>{noDisponible.espera}</p>
            </>
          ) : (
            <>
              <h1 style={titulo}>Esta publicación no está disponible</h1>
              <p style={{ color: 'var(--text-secondary)' }}>
                Puede que el enlace haya cambiado o que la publicación ya no esté activa.
              </p>
            </>
          )}
        </section>
      </main>
    );
  }

  if (gracias) {
    return (
      <main style={envoltorio}>
        <section className="glass-panel" style={panel} aria-live="polite">
          <h1 style={titulo}>{gracias}</h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Puedes cerrar esta página. Tus datos se tratan conforme al aviso de privacidad que aceptaste.
          </p>
        </section>
      </main>
    );
  }

  const { opciones } = publicacion;
  const esLarga = (publicacion.descripcion || '').length > LARGA;

  // Las propiedades que conectan un campo con su error: el lector de pantalla lo anuncia
  // al llegar al campo, y `data-campo` es por donde se le devuelve el foco.
  const conError = (nombre) => ({
    'data-campo': nombre,
    'aria-invalid': errores[nombre] ? 'true' : undefined,
    'aria-describedby': errores[nombre] ? `interes-${nombre}-error` : undefined,
  });
  const mensaje = (nombre) =>
    errores[nombre] ? (
      <div id={`interes-${nombre}-error`} className="interes-error">{errores[nombre]}</div>
    ) : null;

  return (
    <main style={envoltorio}>
      <section className="glass-panel" style={panel}>
        {vistaPrevia && (
          <div role="note" className="interes-aviso" style={{ color: 'var(--text-secondary)' }}>
            Vista previa: así verá la página el interesado. Desde aquí no se envía nada.
          </div>
        )}
        <h1 style={titulo}>{publicacion.titulo}</h1>
        {publicacion.descripcion && (
          <>
            {/* Tres líneas y «Leer más»: el texto del post completo empujaba el botón de
                enviar fuera de la pantalla del teléfono. */}
            <p id="interes-descripcion"
              className={`interes-descripcion${descripcionCompleta || !esLarga ? '' : ' recortada'}`}>
              {publicacion.descripcion}
            </p>
            {esLarga && (
              <button type="button" className="interes-leer-mas"
                aria-expanded={descripcionCompleta} aria-controls="interes-descripcion"
                onClick={() => setDescripcionCompleta((v) => !v)}>
                {descripcionCompleta ? 'Leer menos' : 'Leer más'}
              </button>
            )}
          </>
        )}

        {error && (
          <div role="alert" className="interes-aviso">{error}</div>
        )}

        <form ref={formularioRef} onSubmit={enviar} aria-label="Solicitud de contacto" noValidate className="interes-formulario">
          <div>
            <label htmlFor="interes-nombre" className="form-label">Nombre</label>
            <input id="interes-nombre" className="input-field" required maxLength={100} autoComplete="name"
              {...conError('nombre')}
              value={formulario.nombre} onChange={(e) => cambiar('nombre', e.target.value)} />
            {mensaje('nombre')}
          </div>

          <div>
            <label htmlFor="interes-correo" className="form-label">Correo de trabajo</label>
            <input id="interes-correo" type="email" inputMode="email" className="input-field" required maxLength={150}
              autoComplete="email" {...conError('correo')}
              value={formulario.correo} onChange={(e) => cambiar('correo', e.target.value)} />
            {mensaje('correo')}
          </div>

          <div>
            <label htmlFor="interes-empresa" className="form-label">Empresa</label>
            <input id="interes-empresa" className="input-field" required maxLength={150} autoComplete="organization"
              {...conError('empresa')}
              value={formulario.empresa} onChange={(e) => cambiar('empresa', e.target.value)} />
            {mensaje('empresa')}
          </div>

          <div>
            <label htmlFor="interes-cargo" className="form-label">Cargo</label>
            <select id="interes-cargo" className="input-field" required {...conError('cargo')}
              value={formulario.cargo} onChange={(e) => cambiar('cargo', e.target.value)}>
              <option value="">Elige una opción</option>
              {opciones.cargos.map((valor) => <option key={valor} value={valor}>{valor}</option>)}
            </select>
            {mensaje('cargo')}
          </div>

          {/* Tamaño y sector comparten fila: son listas cortas y caben en 375 px. */}
          <div className="interes-pareja">
            <div>
              <label htmlFor="interes-tamano" className="form-label">Empleados</label>
              <select id="interes-tamano" className="input-field" required {...conError('tamano_de_empresa')}
                value={formulario.tamano_de_empresa} onChange={(e) => cambiar('tamano_de_empresa', e.target.value)}>
                <option value="">Elige</option>
                {opciones.tamanos.map((valor) => <option key={valor} value={valor}>{valor}</option>)}
              </select>
              {mensaje('tamano_de_empresa')}
            </div>
            <div>
              <label htmlFor="interes-sector" className="form-label">Sector</label>
              <select id="interes-sector" className="input-field" required {...conError('sector')}
                value={formulario.sector} onChange={(e) => cambiar('sector', e.target.value)}>
                <option value="">Elige</option>
                {opciones.sectores.map((valor) => <option key={valor} value={valor}>{valor}</option>)}
              </select>
              {mensaje('sector')}
            </div>
          </div>

          {/* Botones de un clic: radios nativos con aspecto de botón. Se eligen con un
              toque, con las flechas del teclado, y el lector de pantalla los anuncia como
              un grupo de opciones. */}
          <fieldset className="interes-necesidades"
            aria-describedby={errores.necesidad ? 'interes-necesidad-error' : undefined}>
            <legend className="form-label">¿Qué necesitas?</legend>
            <div className="interes-botones">
              {Object.entries(opciones.necesidades).map(([clave, etiqueta], indice) => (
                <label key={clave} className={`interes-boton${formulario.necesidad === clave ? ' elegido' : ''}`}>
                  <input type="radio" name="necesidad" value={clave}
                    data-campo={indice === 0 ? 'necesidad' : undefined}
                    checked={formulario.necesidad === clave}
                    onChange={() => cambiar('necesidad', clave)} />
                  <span>{etiqueta}</span>
                </label>
              ))}
            </div>
            {mensaje('necesidad')}
          </fieldset>

          <details className="interes-mas" open={masDatos}
            onToggle={(e) => setMasDatos(e.currentTarget.open)}>
            <summary>Añadir más datos (opcional)</summary>
            <div className="interes-formulario" style={{ marginTop: '10px' }}>
              <div>
                <label htmlFor="interes-telefono" className="form-label">Teléfono</label>
                <input id="interes-telefono" type="tel" inputMode="tel" className="input-field" maxLength={50}
                  autoComplete="tel" {...conError('telefono')}
                  value={formulario.telefono} onChange={(e) => cambiar('telefono', e.target.value)} />
                {mensaje('telefono')}
              </div>
              {/* `type="text"` y no `type="url"`: el navegador rechaza «linkedin.com/in/perfil»
                  antes de enviar nada, con un aviso suyo que no explica qué falta. El servidor
                  completa el «https://» y quita los parámetros que añade la aplicación de
                  LinkedIn al compartir, así que lo que se pegue tal cual vale. */}
              <div>
                <label htmlFor="interes-linkedin" className="form-label">Tu perfil de LinkedIn</label>
                <input id="interes-linkedin" type="text" inputMode="url" className="input-field" maxLength={200}
                  placeholder="linkedin.com/in/tu-perfil"
                  data-campo="linkedin"
                  aria-invalid={errores.linkedin ? 'true' : undefined}
                  aria-describedby={errores.linkedin ? 'interes-linkedin-ayuda interes-linkedin-error' : 'interes-linkedin-ayuda'}
                  value={formulario.linkedin} onChange={(e) => cambiar('linkedin', e.target.value)} />
                <div id="interes-linkedin-ayuda" className="interes-ayuda">
                  Puedes pegarlo tal como te lo dé la aplicación de LinkedIn.
                </div>
                {mensaje('linkedin')}
              </div>
            </div>
          </details>

          {/* Campo trampa. Oculto a la vista y al lector de pantalla, y fuera del recorrido
              del tabulador: una persona no puede rellenarlo sin proponérselo. */}
          <div aria-hidden="true" style={{ position: 'absolute', left: '-10000px', width: '1px', height: '1px', overflow: 'hidden' }}>
            <label htmlFor="interes-sitio-web">No rellene este campo</label>
            <input id="interes-sitio-web" type="text" tabIndex={-1} autoComplete="off"
              value={formulario.sitio_web} onChange={(e) => cambiar('sitio_web', e.target.value)} />
          </div>

          <div>
            <div className="interes-aviso-privacidad">
              <input id="interes-aviso" type="checkbox" {...conError('aviso_de_privacidad')}
                checked={formulario.aviso_de_privacidad}
                onChange={(e) => cambiar('aviso_de_privacidad', e.target.checked)} />
              <label htmlFor="interes-aviso">
                Acepto el aviso de privacidad y que PluriOne me contacte por esta solicitud.
              </label>
            </div>
            {mensaje('aviso_de_privacidad')}
          </div>

          <button type="submit" className="btn btn-primary interes-enviar" disabled={enviando || Boolean(vistaPrevia)}>
            {enviando ? 'Enviando...' : 'Quiero que me contacten'}
          </button>
        </form>
      </section>
    </main>
  );
}

const envoltorio = {
  maxWidth: '560px',
  margin: '0 auto',
  width: '100%',
  padding: '8px',
};

const panel = { padding: '14px' };

const titulo = { fontSize: '1.15rem', fontWeight: '700', marginBottom: '6px', lineHeight: 1.3 };
