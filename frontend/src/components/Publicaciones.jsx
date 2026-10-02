import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  cambiarEstadoDePublicacion,
  createCampaign,
  duplicateCampaign,
  fetchCampaignList,
  fetchComparativaDePublicaciones,
  fetchEstadoDeLaDireccionPublica,
  fetchNuevosSinAsesor,
  fetchSalesReps,
  fetchVistaPreviaDePublicacion,
  updateCampaign,
} from '../services/api';
import CompartirEnRedes, { RedesDelFormulario } from './CompartirEnRedes';
import ContadorSinAsesor from './ContadorSinAsesor';
import InformeDePublicacion from './InformeDePublicacion';
import PaginaDeInteres from './PaginaDeInteres';
import VistaPreviaDelPost from './VistaPreviaDelPost';
import MensajeDeCampo from './MensajeDeCampo.jsx';
import {
  comoAviso,
  enfocarPrimerCampoConError,
  erroresDelServidor,
  propiedadesDeCampo,
  resumenDeCampos,
  sinElCampo,
} from './erroresDeFormulario';

// Una publicación es una campaña con canal LinkedIn, no una entidad aparte: se crea, se
// lee y se edita por las mismas rutas que cualquier campaña. El enlace público y el texto
// que se copia los arma el servidor, que es quien genera el identificador del enlace; aquí
// solo se enseñan y se copian.
export const CANAL_LINKEDIN = 'LinkedIn';

// Los campos de este formulario que el servidor valida uno por uno.
const CAMPOS_DEL_FORMULARIO = [
  'name', 'description', 'target_audience', 'fecha_de_cierre', 'url_del_post',
];

// El nombre que viaja no es siempre el que la pantalla usa: la «fecha de cierre» del
// formulario es `end_date` para el servidor. Sin esta traducción, el error de esa fecha no
// encontraría su campo y acabaría en el aviso de arriba.
const RENOMBRES = { end_date: 'fecha_de_cierre' };

const ETIQUETAS_DEL_FORMULARIO = {
  name: 'Título interno',
  description: 'Texto de la publicación',
  target_audience: 'A quién va dirigida',
  fecha_de_cierre: 'Fecha de cierre',
  url_del_post: 'Dirección del post publicado',
};
// Mismo tope que el servidor (`MAX_DESCRIPCION`): con él, descripción y enlace caben en un
// post de LinkedIn, que admite 3 000 caracteres.
export const MAX_DESCRIPCION = 2800;
// De 2 a 5 opciones de «¿Qué necesitas?», de hasta 40 caracteres: botones de un toque que
// caben, dos por fila, en la pantalla de un teléfono.
export const MIN_NECESIDADES = 2;
export const MAX_NECESIDADES = 5;
export const MAX_ETIQUETA = 40;

const NOMBRE_DEL_ESTADO = {
  borrador: 'Borrador',
  activa: 'Activa',
  pausada: 'Pausada',
  cerrada: 'Cerrada',
};

// Qué se puede hacer desde cada estado, en el orden en que se ofrece. Solo «activa» recibe
// perfiles; el resto responde «no disponible» en la página.
const TRANSICIONES = {
  borrador: [['activa', 'Activar']],
  activa: [['pausada', 'Pausar'], ['cerrada', 'Cerrar']],
  pausada: [['activa', 'Reanudar'], ['cerrada', 'Cerrar']],
  cerrada: [['activa', 'Reabrir']],
};

const FORMULARIO_VACIO = {
  name: '',
  description: '',
  target_audience: '',
  estado: 'activa',
  fecha_de_cierre: '',
  responsable_id: '',
  url_del_post: '',
  necesidades_propias: false,
  necesidades: ['', ''],
  // Las de siempre, que es lo que trae una publicación nueva sin tocar nada.
  redes: ['linkedin', 'whatsapp', 'facebook', 'correo'],
};

async function copiarAlPortapapeles(texto) {
  if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
    throw new Error('Portapapeles no disponible');
  }
  await navigator.clipboard.writeText(texto);
}

// La fecha de cierre se elige por día y cierra al terminar ese día (UTC): quien pone «30 de
// septiembre» espera poder recibir perfiles el 30.
function finDelDia(fecha) {
  return fecha ? `${fecha}T23:59:59+00:00` : null;
}

function soloElDia(momento) {
  return momento ? String(momento).slice(0, 10) : '';
}

export default function Publicaciones({ puedeGestionar = false, onSelectLead }) {
  const [publicaciones, setPublicaciones] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [trabajando, setTrabajando] = useState(false);

  // `null`: formulario cerrado. `'nueva'`: alta. Un número: edición de esa publicación.
  const [enEdicion, setEnEdicion] = useState(null);
  const [formulario, setFormulario] = useState(FORMULARIO_VACIO);
  // Si el navegador no deja escribir en el portapapeles, el texto se enseña seleccionable
  // para copiarlo a mano en lugar de fallar en silencio.
  const [textoManual, setTextoManual] = useState(null);
  // La publicación cuyo informe se está mirando, o `null` para la lista.
  const [informeDe, setInformeDe] = useState(null);
  // Vista previa del post (id de la publicación) y de la página ({ publicacion, datos }).
  const [postDe, setPostDe] = useState(null);
  const [paginaDe, setPaginaDe] = useState(null);
  // Comparativa y contador: los pide el servidor solo a quien dirige la cartera, así que
  // ni se piden desde la cuenta de un asesor. Pedirlos y tragarse el 403 llenaría la
  // bitácora de accesos denegados que no los provocó nadie.
  const [comparativa, setComparativa] = useState([]);
  const [sinAsesor, setSinAsesor] = useState(null);
  const [asesores, setAsesores] = useState([]);
  // Todas las redes que se pueden activar, tal como las declara el servidor.
  const [redesDisponibles, setRedesDisponibles] = useState([]);
  // La publicación cuyos botones de compartir están abiertos, o `null`.
  const [compartiendo, setCompartiendo] = useState(null);
  // Si la dirección pública sigue llevando aquí (capítulo 34). `null` mientras no se sabe.
  const [direccion, setDireccion] = useState(null);
  // Lo que el servidor dijo de cada campo del formulario de la publicación.
  const [erroresDelFormulario, setErroresDelFormulario] = useState({});
  const formularioRef = useRef(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const datos = await fetchCampaignList({ incluirInactivas: true, canal: CANAL_LINKEDIN });
      setPublicaciones((datos && datos.items) || []);
      // El catálogo de redes viene con la lista: una sola fuente, la del servidor.
      if (datos && datos.redes_disponibles) setRedesDisponibles(datos.redes_disponibles);
      if (puedeGestionar) {
        const [comparadas, pendientes, equipo, publica] = await Promise.all([
          fetchComparativaDePublicaciones(),
          fetchNuevosSinAsesor(),
          fetchSalesReps(),
          // Si el túnel está caído, esta es justamente la llamada que puede tardar. Va en
          // el `Promise.all` y no antes para que su espera no retrase la lista: el tope lo
          // pone el servidor (`DIRECCION_PUBLICA_TIMEOUT_SEGUNDOS`).
          fetchEstadoDeLaDireccionPublica().catch(() => null),
        ]);
        setComparativa((comparadas && comparadas.items) || []);
        setSinAsesor(pendientes ? pendientes.total : null);
        setAsesores((equipo && equipo.items) || []);
        setDireccion(publica);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }, [puedeGestionar]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrirAlta = () => {
    setEnEdicion('nueva');
    setFormulario(FORMULARIO_VACIO);
    setAviso('');
    setError('');
  };

  const abrirEdicion = (publicacion) => {
    setEnEdicion(publicacion.id);
    setFormulario({
      name: publicacion.name || '',
      description: publicacion.description || '',
      target_audience: publicacion.target_audience || '',
      estado: publicacion.estado || 'activa',
      fecha_de_cierre: soloElDia(publicacion.end_date),
      responsable_id: publicacion.responsable_id ? String(publicacion.responsable_id) : '',
      url_del_post: publicacion.url_del_post || '',
      necesidades_propias: Boolean(publicacion.necesidades_propias),
      necesidades: (publicacion.necesidades || []).map((o) => o.etiqueta),
      redes: publicacion.redes || FORMULARIO_VACIO.redes,
    });
    setAviso('');
    setError('');
  };

  const cambiar = (campo, valor) => {
    setFormulario((previo) => ({ ...previo, [campo]: valor }));
    // Al corregir el campo se le quita la marca.
    setErroresDelFormulario((previo) => sinElCampo(previo, campo));
  };

  const conError = (nombre, ademasDescritoPor = null) => propiedadesDeCampo(
    nombre, erroresDelFormulario, 'publicacion', ademasDescritoPor,
  );
  const mensaje = (nombre) => (
    <MensajeDeCampo nombre={nombre} errores={erroresDelFormulario} prefijo="publicacion" />
  );

  const cambiarNecesidad = (indice, valor) =>
    setFormulario((previo) => ({
      ...previo,
      necesidades: previo.necesidades.map((n, i) => (i === indice ? valor : n)),
    }));

  const guardar = async (e) => {
    e.preventDefault();
    setTrabajando(true);
    setError('');
    setErroresDelFormulario({});
    // Sin `trim()` en lo que viaja: lo recorta el servidor desde el capítulo 41, y el vacío
    // lo convierte en nulo él, que es donde tiene que decidirse —el `|| null` de aquí era la
    // mitad de la regla escrita en el sitio por el que no pasan las integraciones—. El
    // recorte de la vista previa de más abajo se queda: ese es trabajo del cliente, porque es
    // el texto que se enseña.
    const datos = {
      name: formulario.name,
      description: formulario.description,
      target_audience: formulario.target_audience,
      estado: formulario.estado,
      end_date: finDelDia(formulario.fecha_de_cierre),
      responsable_id: formulario.responsable_id ? Number(formulario.responsable_id) : null,
      url_del_post: formulario.url_del_post,
      // Sin opciones propias viaja `null`: la publicación usa las de siempre.
      necesidades: formulario.necesidades_propias ? formulario.necesidades : null,
      redes: formulario.redes,
    };
    try {
      // El nombre del aviso sale de lo que el servidor guardó, no de lo que se escribió en
      // el formulario: son la misma cosa salvo los espacios, y decir «Publicación «  X  »
      // creada» enseñaría un nombre que la publicación no tiene.
      if (enEdicion === 'nueva') {
        const creada = await createCampaign({ ...datos, channel: CANAL_LINKEDIN });
        setAviso(
          datos.estado === 'borrador'
            ? `Borrador «${creada.name}» guardado. Revise su página con «Ver la página» antes de activarlo.`
            : `Publicación «${creada.name}» creada. Ya puede copiar su texto para LinkedIn.`,
        );
      } else {
        const guardada = await updateCampaign(enEdicion, datos);
        setAviso(`Publicación «${guardada.name}» guardada.`);
      }
      setEnEdicion(null);
      await cargar();
    } catch (err) {
      const repartidos = err.status === 422
        ? erroresDelServidor(err.detalle, {
          campos: CAMPOS_DEL_FORMULARIO, renombres: RENOMBRES,
        })
        : null;
      if (repartidos && Object.keys(repartidos.porCampo).length) {
        setErroresDelFormulario(repartidos.porCampo);
        setError(comoAviso([
          resumenDeCampos(repartidos.porCampo, ETIQUETAS_DEL_FORMULARIO),
          ...repartidos.sueltos,
        ]));
        enfocarPrimerCampoConError(formularioRef, repartidos.porCampo, CAMPOS_DEL_FORMULARIO);
      } else if (repartidos && repartidos.sueltos.length) {
        setError(comoAviso(repartidos.sueltos));
      } else {
        setError(err.message);
      }
    } finally {
      setTrabajando(false);
    }
  };

  const pasarA = async (publicacion, estado) => {
    setTrabajando(true);
    setError('');
    try {
      await cambiarEstadoDePublicacion(publicacion.id, estado);
      setAviso(`Publicación «${publicacion.name}»: ${NOMBRE_DEL_ESTADO[estado].toLowerCase()}.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setTrabajando(false);
    }
  };

  const duplicar = async (publicacion) => {
    setTrabajando(true);
    setError('');
    try {
      const copia = await duplicateCampaign(publicacion.id);
      setAviso(`Copia creada como borrador: «${copia.name}». Tiene su propio enlace.`);
      await cargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setTrabajando(false);
    }
  };

  const verPagina = async (publicacion) => {
    setError('');
    try {
      const datos = await fetchVistaPreviaDePublicacion(publicacion.id);
      setPaginaDe({ publicacion, datos });
    } catch (err) {
      setError(err.message);
    }
  };

  /**
   * Copia un texto al portapapeles y, si el navegador no deja, lo enseña seleccionable.
   *
   * Es el mismo camino para el texto de LinkedIn de siempre y para el de cada red: quien no
   * puede copiar con un clic tampoco puede en WhatsApp, y una de las dos vías acabaría
   * fallando en silencio si se escribieran por separado.
   */
  const copiarTextoSuelto = async (publicacion, texto, destino) => {
    setError('');
    setTextoManual(null);
    try {
      await copiarAlPortapapeles(texto);
      setAviso(`Texto de «${destino}» copiado. Ya puede pegarlo.`);
    } catch {
      setAviso('');
      setTextoManual({ id: publicacion.id, texto });
    }
  };

  const copiarTexto = (publicacion) =>
    copiarTextoSuelto(publicacion, publicacion.texto_para_linkedin, `${publicacion.name} · LinkedIn`);

  if (informeDe) {
    return (
      <InformeDePublicacion
        publicacion={informeDe}
        onSelectLead={onSelectLead}
        onCerrar={() => setInformeDe(null)}
      />
    );
  }

  if (paginaDe) {
    return (
      <section aria-label={`Vista previa de la página de «${paginaDe.publicacion.name}»`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Estado: {NOMBRE_DEL_ESTADO[paginaDe.publicacion.estado] || paginaDe.publicacion.estado}
            {paginaDe.publicacion.estado !== 'activa' && ' — hasta que esté activa, quien abra el enlace verá «no disponible».'}
          </span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPaginaDe(null)}>
            Volver a las publicaciones
          </button>
        </div>
        {/* El ancho de un teléfono: es desde donde se abre un enlace de LinkedIn. */}
        <div style={{ maxWidth: '375px', margin: '0 auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md, 12px)' }}>
          <PaginaDeInteres slug={paginaDe.publicacion.public_slug} vistaPrevia={paginaDe.datos} />
        </div>
      </section>
    );
  }

  const restantes = MAX_DESCRIPCION - formulario.description.length;
  const enlaceDeEjemplo =
    (enEdicion !== 'nueva' && publicaciones.find((p) => p.id === enEdicion)?.enlace_publico) ||
    (publicaciones[0] ? publicaciones[0].enlace_publico.replace(/[^/]+$/, 'xxxxxxxxxxxxxxxxxxxxxx') : '');
  const textoDelFormulario = [formulario.description.trim(), enlaceDeEjemplo].filter(Boolean).join('\n\n');

  return (
    <section className="glass-panel" aria-labelledby="titulo-publicaciones" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 id="titulo-publicaciones" style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>
            Publicaciones
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '720px' }}>
            Posts de LinkedIn con su enlace propio. Cada publicación es una campaña con canal LinkedIn: los prospectos
            que lleguen por su enlace se podrán comparar por publicación.
            {!puedeGestionar && ' Puede consultarlas y copiar su texto; crearlas y editarlas es tarea del líder comercial.'}
          </p>
        </div>
        {puedeGestionar && enEdicion === null && (
          <button type="button" className="btn btn-primary btn-sm" onClick={abrirAlta}>
            + Nueva publicación
          </button>
        )}
      </div>

      {aviso && (
        <div role="status" className="alert alert-ok" style={{ margin: '12px 0' }}>
          {aviso}
        </div>
      )}
      {error && (
        <div role="alert" className="alert alert-error" style={{ margin: '12px 0' }}>
          {error}
        </div>
      )}

      {/* La dirección pública, cuando hay algo que decir (capítulo 34).
          Se dibuja solo con `responde === false` o con enlaces ya caducados: mientras la
          dirección funciona, esta franja no existe. Una advertencia permanente —«el túnel
          puede caerse»— se convierte en parte del decorado en dos días y deja de leerse
          justo el día que sí pasa algo. */}
      {puedeGestionar && direccion && direccion.responde === false && (
        <div role="alert" className="alert alert-error" style={{ margin: '14px 0' }}>
          <strong>La dirección pública no responde.</strong>{' '}
          Quien abra un enlace de estas publicaciones no llega a ninguna parte. Si el túnel
          se reinició, su dirección es otra: hay que ponerla en{' '}
          <code>PUBLICACIONES_URL_BASE</code> y volver a levantar la pila.
          {/* --text-secondary y no --text-muted: dentro de un aviso el fondo lleva el rojo
              translúcido encima del panel, y el apagado se queda en 3.78 (§1.4.3). */}
          <div style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginTop: '4px', wordBreak: 'break-all' }}>
            {direccion.base}{direccion.detalle ? ` · ${direccion.detalle}` : ''}
          </div>
        </div>
      )}

      {puedeGestionar && direccion && direccion.publicaciones_con_enlace_caducado > 0 && (
        <div role="alert" className="alert alert-warn" style={{ margin: '14px 0' }}>
          <strong>
            {direccion.publicaciones_con_enlace_caducado}{' '}
            {direccion.publicaciones_con_enlace_caducado === 1 ? 'publicación repartió' : 'publicaciones repartieron'}{' '}
            un enlace que ya no lleva aquí.
          </strong>{' '}
          La dirección pública cambió después de activarlas. El enlace que está dentro de
          esos posts está muerto: hay que volver a copiarlo y editar el post, o publicarlo
          de nuevo. Están marcadas abajo.
        </div>
      )}

      {/* El contador y la comparativa son del líder: uno avisa de que hay trabajo sin
          repartir, la otra dice qué post lo trajo. Un asesor no los ve, y tampoco se piden.

          El bloque del contador se fue a `ContadorSinAsesor` en el capítulo 38, cuando el
          tablero ganó el mismo aviso (§6.2, punto 11). Aquí sigue estando y dice lo mismo
          porque es el mismo componente, no una copia del texto. */}
      {puedeGestionar && <ContadorSinAsesor total={sinAsesor} />}

      {puedeGestionar && comparativa.length > 0 && (
        <div style={{ margin: '14px 0', overflowX: 'auto' }}>
          <h3 style={{ fontSize: '0.85rem', fontWeight: '700', marginBottom: '6px' }}>
            Comparativa entre publicaciones
          </h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                <th scope="col" style={{ padding: '6px 8px' }}>Publicación</th>
                <th scope="col" style={{ padding: '6px 8px' }}>Visitas</th>
                <th scope="col" style={{ padding: '6px 8px' }}>Tasa de envío</th>
                <th scope="col" style={{ padding: '6px 8px' }}>Perfiles recibidos</th>
                <th scope="col" style={{ padding: '6px 8px' }}>Avanzaron de etapa</th>
                <th scope="col" style={{ padding: '6px 8px' }}>Score medio</th>
              </tr>
            </thead>
            <tbody>
              {comparativa.map((fila) => (
                <tr key={fila.publicacion_id} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <th scope="row" style={{ padding: '6px 8px', textAlign: 'left', fontWeight: '600' }}>
                    {fila.titulo}
                    {fila.estado !== 'activa' && (
                      <span className="badge" style={{ marginLeft: '6px', fontSize: '0.6rem' }}>
                        {NOMBRE_DEL_ESTADO[fila.estado] || fila.estado}
                      </span>
                    )}
                  </th>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{fila.visitas}</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                    {fila.tasa_de_envio === null || fila.tasa_de_envio === undefined ? '—' : `${fila.tasa_de_envio} %`}
                  </td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{fila.perfiles_recibidos}</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{fila.avanzaron_de_etapa}</td>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{fila.score_medio}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {puedeGestionar && enEdicion !== null && (
        <form
          onSubmit={guardar}
          ref={formularioRef}
          aria-label={enEdicion === 'nueva' ? 'Nueva publicación' : 'Editar publicación'}
          style={{ margin: '14px 0', padding: '14px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', display: 'flex', flexDirection: 'column', gap: '10px' }}
        >
          <div>
            <label htmlFor="publicacion-nombre" className="form-label">Título interno</label>
            <input
              id="publicacion-nombre"
              className="input-field"
              required
              minLength={2}
              maxLength={200}
              value={formulario.name}
              onChange={(e) => cambiar('name', e.target.value)}
              placeholder="Ej. Post · Talento TI septiembre"
              {...conError('name')}
            />
            {mensaje('name')}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' }}>
            <div>
              <label htmlFor="publicacion-descripcion" className="form-label">Texto de la publicación</label>
              <textarea
                id="publicacion-descripcion"
                className="input-field"
                required
                rows={8}
                maxLength={MAX_DESCRIPCION}
                value={formulario.description}
                onChange={(e) => cambiar('description', e.target.value)}
                {...conError('description', 'publicacion-descripcion-restantes')}
              />
              {mensaje('description')}
              <div id="publicacion-descripcion-restantes" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                Quedan {restantes} caracteres. El enlace se añade al final al copiar.
              </div>
            </div>
            <div>
              <span className="form-label">Así se verá en LinkedIn</span>
              <VistaPreviaDelPost texto={textoDelFormulario} enlace={enlaceDeEjemplo} />
            </div>
          </div>
          <div>
            <label htmlFor="publicacion-publico" className="form-label">A quién va dirigida</label>
            <input
              id="publicacion-publico"
              className="input-field"
              maxLength={300}
              value={formulario.target_audience}
              onChange={(e) => cambiar('target_audience', e.target.value)}
              placeholder="Ej. Directores de TI de empresas de 200 a 1000 empleados"
              {...conError('target_audience')}
            />
            {mensaje('target_audience')}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            <div>
              <label htmlFor="publicacion-estado" className="form-label">Estado</label>
              <select
                id="publicacion-estado"
                className="input-field"
                value={formulario.estado}
                onChange={(e) => cambiar('estado', e.target.value)}
              >
                {(enEdicion === 'nueva' ? ['borrador', 'activa'] : Object.keys(NOMBRE_DEL_ESTADO)).map((estado) => (
                  <option key={estado} value={estado}>{NOMBRE_DEL_ESTADO[estado]}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="publicacion-cierre" className="form-label">Fecha de cierre (opcional)</label>
              <input
                id="publicacion-cierre"
                type="date"
                className="input-field"
                value={formulario.fecha_de_cierre}
                onChange={(e) => cambiar('fecha_de_cierre', e.target.value)}
                {...conError('fecha_de_cierre', 'publicacion-cierre-ayuda')}
              />
              {mensaje('fecha_de_cierre')}
              <div id="publicacion-cierre-ayuda" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                Al terminar ese día se cierra sola y la página deja de recibir perfiles.
              </div>
            </div>
            <div>
              <label htmlFor="publicacion-responsable" className="form-label">Asesor responsable</label>
              <select
                id="publicacion-responsable"
                className="input-field"
                aria-describedby="publicacion-responsable-ayuda"
                value={formulario.responsable_id}
                onChange={(e) => cambiar('responsable_id', e.target.value)}
              >
                <option value="">Sin responsable</option>
                {asesores.filter((a) => a.is_active !== false).map((asesor) => (
                  <option key={asesor.id} value={String(asesor.id)}>{asesor.full_name}</option>
                ))}
              </select>
              <div id="publicacion-responsable-ayuda" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {formulario.responsable_id
                  ? 'Los prospectos nuevos de esta publicación se le asignan solos.'
                  : 'Los prospectos llegarán sin asesor y los repartirá el líder.'}
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="publicacion-url" className="form-label">Dirección del post publicado (opcional)</label>
            <input
              id="publicacion-url"
              className="input-field"
              type="text"
              inputMode="url"
              maxLength={300}
              value={formulario.url_del_post}
              onChange={(e) => cambiar('url_del_post', e.target.value)}
              placeholder="https://www.linkedin.com/posts/..."
              {...conError('url_del_post')}
            />
            {mensaje('url_del_post')}
          </div>

          <RedesDelFormulario
            activas={formulario.redes}
            disponibles={redesDisponibles}
            onChange={(redes) => cambiar('redes', redes)}
          />

          <fieldset style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '10px' }}>
            <legend className="form-label" style={{ padding: '0 4px' }}>Opciones de «¿Qué necesitas?»</legend>
            <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.8rem' }}>
              <input
                type="checkbox"
                checked={formulario.necesidades_propias}
                onChange={(e) => cambiar('necesidades_propias', e.target.checked)}
              />
              Usar opciones propias en esta publicación (de {MIN_NECESIDADES} a {MAX_NECESIDADES})
            </label>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '4px 0 8px' }}>
              Informan al asesor en la ficha y en el informe. No cambian el score.
            </p>
            {formulario.necesidades_propias && (
              <ol style={{ margin: 0, paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {formulario.necesidades.map((necesidad, indice) => (
                  // La posición es la identidad de cada opción mientras se escribe.
                  <li key={indice} style={{ display: 'flex', gap: '6px' }}>
                    <label htmlFor={`publicacion-necesidad-${indice}`} className="sr-only">Opción {indice + 1}</label>
                    <input
                      id={`publicacion-necesidad-${indice}`}
                      className="input-field"
                      required
                      minLength={2}
                      maxLength={MAX_ETIQUETA}
                      value={necesidad}
                      onChange={(e) => cambiarNecesidad(indice, e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      aria-label={`Quitar la opción ${indice + 1}`}
                      disabled={formulario.necesidades.length <= MIN_NECESIDADES}
                      onClick={() => cambiar('necesidades', formulario.necesidades.filter((_, i) => i !== indice))}
                    >
                      Quitar
                    </button>
                  </li>
                ))}
              </ol>
            )}
            {formulario.necesidades_propias && formulario.necesidades.length < MAX_NECESIDADES && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ marginTop: '6px' }}
                onClick={() => cambiar('necesidades', [...formulario.necesidades, ''])}
              >
                + Añadir opción
              </button>
            )}
          </fieldset>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" className="btn btn-primary btn-sm" disabled={trabajando}>
              {enEdicion === 'nueva' ? 'Crear publicación' : 'Guardar cambios'}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEnEdicion(null)}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {cargando ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '12px' }}>Cargando publicaciones...</p>
      ) : publicaciones.length === 0 ? (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '12px' }}>Todavía no hay publicaciones.</p>
      ) : (
        <ul aria-label="Publicaciones" style={{ listStyle: 'none', padding: 0, margin: '14px 0 0', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {publicaciones.map((publicacion) => (
            <li key={publicacion.id} style={{ padding: '12px 14px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', opacity: publicacion.estado === 'activa' ? 1 : 0.8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '240px' }}>
                  <strong style={{ fontSize: '0.9rem' }}>{publicacion.name}</strong>{' '}
                  <span className="badge" style={{ fontSize: '0.65rem' }}>
                    {NOMBRE_DEL_ESTADO[publicacion.estado] || publicacion.estado}
                  </span>
                  {publicacion.target_audience && (
                    <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Dirigida a: {publicacion.target_audience}
                    </div>
                  )}
                  <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>
                    Responsable: {publicacion.responsable ? publicacion.responsable.full_name : 'ninguno (llegan sin asesor)'}
                    {publicacion.end_date && ` · Se cierra el ${soloElDia(publicacion.end_date)}`}
                  </div>
                  {publicacion.description && (
                    <p style={{ margin: '6px 0', whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>{publicacion.description}</p>
                  )}
                  <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                    {publicacion.enlace_publico}
                  </div>
                  {/* El enlace de arriba es el de AHORA y se puede copiar sin problema. Lo
                      que caducó es el que ya está dentro del post, que se copió cuando la
                      dirección era otra. Por eso el aviso va debajo del enlace y no lo
                      sustituye: no hay nada que arreglar aquí, hay que editar el post. */}
                  {publicacion.enlace_caducado && (
                    <div style={{ color: 'var(--warn-text)', marginTop: '2px' }}>
                      ⚠ El enlace que se repartió de esta publicación ya no lleva aquí: la
                      dirección pública cambió después de activarla. El de arriba es el
                      bueno; hay que volver a pegarlo en el post.
                    </div>
                  )}
                  {publicacion.url_del_post && (
                    <a href={publicacion.url_del_post} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)' }}>
                      Ver el post en LinkedIn
                    </a>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', flexWrap: 'wrap', maxWidth: '460px' }}>
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => copiarTexto(publicacion)}>
                    Copiar texto para LinkedIn
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-expanded={compartiendo === publicacion.id}
                    onClick={() => setCompartiendo(compartiendo === publicacion.id ? null : publicacion.id)}
                  >
                    Compartir en redes
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-expanded={postDe === publicacion.id}
                    onClick={() => setPostDe(postDe === publicacion.id ? null : publicacion.id)}
                  >
                    Vista previa del post
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => verPagina(publicacion)}>
                    Ver la página
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setInformeDe(publicacion)}>
                    Ver informe
                  </button>
                  {puedeGestionar && (
                    <>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={trabajando} onClick={() => abrirEdicion(publicacion)}>
                        Editar
                      </button>
                      <button type="button" className="btn btn-secondary btn-sm" disabled={trabajando} onClick={() => duplicar(publicacion)}>
                        Duplicar publicación
                      </button>
                      {(TRANSICIONES[publicacion.estado] || []).map(([estado, accion]) => (
                        <button key={estado} type="button" className="btn btn-secondary btn-sm" disabled={trabajando} onClick={() => pasarA(publicacion, estado)}>
                          {accion}
                        </button>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {compartiendo === publicacion.id && (
                <div style={{ marginTop: '10px' }}>
                  <CompartirEnRedes
                    publicacion={publicacion}
                    onCopiar={(texto, etiqueta) => copiarTextoSuelto(publicacion, texto, etiqueta)}
                    // `responde === false` y no `!responde`: `null` es «no se ha
                    // comprobado», que es lo que contesta un despliegue sin túnel delante,
                    // y avisar entonces sería inventar una avería.
                    direccionCaida={direccion ? direccion.responde === false : false}
                  />
                </div>
              )}

              {postDe === publicacion.id && (
                <div style={{ marginTop: '10px' }}>
                  <VistaPreviaDelPost texto={publicacion.texto_para_linkedin} enlace={publicacion.enlace_publico} />
                </div>
              )}

              {textoManual && textoManual.id === publicacion.id && (
                <div style={{ marginTop: '10px' }}>
                  <label htmlFor={`publicacion-texto-${publicacion.id}`} className="form-label">
                    El navegador no dejó copiar. Seleccione el texto y cópielo a mano:
                  </label>
                  <textarea
                    id={`publicacion-texto-${publicacion.id}`}
                    className="input-field"
                    readOnly
                    rows={5}
                    value={textoManual.texto}
                    onFocus={(e) => e.target.select()}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
