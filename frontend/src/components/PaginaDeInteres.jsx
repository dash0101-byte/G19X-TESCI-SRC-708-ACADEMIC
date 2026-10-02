import React, { useCallback, useEffect, useRef, useState } from 'react';
import { enviarInteres, fetchPublicacionDeInteres } from '../services/api';
// El reparto de un 422 por campo nació aquí, en el capítulo 34. El 40 lo sacó a un módulo
// para que los cuatro formularios del panel lo usen, y esta página lo importa en vez de
// quedarse con su copia: dos copias de la misma mecánica son dos cosas que se separan.
import MensajeDeCampo from './MensajeDeCampo.jsx';
import {
  comoAviso,
  enfocarPrimerCampoConError,
  erroresDelServidor,
  propiedadesDeCampo,
} from './erroresDeFormulario';

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
  const graciasRef = useRef(null);

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

  // El acuse de recibo, al teclado y al lector de pantalla.
  //
  // Antes el formulario entero se sustituía por la pantalla de gracias y pasaban dos cosas
  // que no se ven mirando: el foco estaba en el botón de enviar, que acababa de desaparecer
  // del documento, así que caía al `<body>`; y la región `aria-live` que anunciaba el
  // mensaje **se creaba en el mismo instante que su contenido**, que es el caso en que los
  // lectores de pantalla no la leen —una región viva anuncia lo que CAMBIA dentro de ella, y
  // para eso tiene que haber estado ahí antes—.
  //
  // Llevar el foco al título resuelve las dos: el lector lo lee porque el foco acaba de
  // llegar, no porque haya cambiado nada, y el teclado queda en el sitio correcto.
  useEffect(() => {
    if (gracias) graciasRef.current?.focus();
  }, [gracias]);

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

  // Si el campo que falla está plegado bajo «Añadir más datos», se despliega antes de
  // buscarlo: un campo que no está en el documento no puede recibir el foco.
  const enfocarPrimerError = (encontrados) => enfocarPrimerCampoConError(
    formularioRef, encontrados, ORDEN, (campo) => { if (OPCIONALES.has(campo)) setMasDatos(true); },
  );

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
      // `propios: FALTA` hace que ganen las frases de esta página sobre las del servidor:
      // están escritas para quien rellena el formulario. `campos: ORDEN` saca aparte lo que
      // esta pantalla no pinta, para que no desaparezca al repartir.
      const repartidos = err.status === 422
        ? erroresDelServidor(err.detalle, { propios: FALTA, campos: ORDEN })
        : null;
      if (repartidos && Object.keys(repartidos.porCampo).length) {
        setErrores(repartidos.porCampo);
        enfocarPrimerError(repartidos.porCampo);
        if (repartidos.sueltos.length) setError(comoAviso(repartidos.sueltos));
      } else if (repartidos && repartidos.sueltos.length) {
        setError(comoAviso(repartidos.sueltos));
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
        <section className="glass-panel" style={panel} role="status">
          {/* `tabIndex={-1}`: no entra en el recorrido del tabulador —no es un control— pero
              sí puede recibir el foco cuando se lo lleva el efecto de arriba. */}
          <h1 style={titulo} ref={graciasRef} tabIndex={-1}>{gracias}</h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Puedes cerrar esta página. Tus datos se tratan conforme al aviso de privacidad que aceptaste.
          </p>
        </section>
      </main>
    );
  }

  const { opciones } = publicacion;
  const esLarga = (publicacion.descripcion || '').length > LARGA;

  // Las propiedades que conectan un campo con su error y el renglón que va debajo. Los dos
  // los construye el mismo módulo, que es lo que garantiza que el `id` del mensaje y el
  // `aria-describedby` del campo digan lo mismo.
  const conError = (nombre, ademasDescritoPor = null) => propiedadesDeCampo(
    nombre, errores, 'interes', ademasDescritoPor,
  );
  const mensaje = (nombre) => (
    <MensajeDeCampo nombre={nombre} errores={errores} prefijo="interes" clase="interes-error" />
  );

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
          {/* El `id` del mensaje no se escribe aquí: sale de la misma función que lo pone
              en el mensaje. El `data-campo` lo lleva el primer radio del grupo, que es
              donde tiene sentido devolver el foco, así que de este juego de propiedades el
              fieldset solo se queda con `aria-describedby`. */}
          <fieldset className="interes-necesidades"
            aria-describedby={conError('necesidad')['aria-describedby']}>
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
                  {...conError('linkedin', 'interes-linkedin-ayuda')}
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

          {/* El motivo, PEGADO al botón y no solo arriba del todo (01-10-2026).
              Hasta aquí la vista previa lo decía en un `role="note"` encima del título, y
              era verdad y no servía: el formulario mide varias pantallas de alto dentro de
              un marco de 375 px, así que quien llega al botón tiene ese aviso cuatrocientos
              píxeles más arriba y fuera de la vista. Pulsó, no pasó nada —el botón está
              desactivado, y un botón desactivado ni siquiera dispara el evento— y no había
              nada cerca que lo explicara.

              Sigue desactivado, que es lo correcto: desde la vista previa no se envía. Lo
              que cambia es que ahora se ve por qué sin tener que subir a buscarlo, y el
              botón lo señala con `aria-describedby` para quien no ve la pantalla. */}
          <button
            type="submit"
            className="btn btn-primary interes-enviar"
            disabled={enviando || Boolean(vistaPrevia)}
            aria-describedby={vistaPrevia ? 'interes-sin-envio' : undefined}
          >
            {enviando ? 'Enviando...' : 'Quiero que me contacten'}
          </button>
          {vistaPrevia && (
            <p id="interes-sin-envio" className="interes-ayuda">
              Este botón está desactivado porque esto es la vista previa: aquí se ve cómo
              queda la página, pero no se envía nada ni se crea ningún prospecto. Para
              probar el envío de verdad, abra el enlace público de la publicación.
            </p>
          )}
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
