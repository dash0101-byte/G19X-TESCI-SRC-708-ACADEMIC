import React, { useState } from 'react';
import {
  buscarTitularPorCorreo,
  exportarDatosDelTitular,
  getCurrentUser,
  getCurrentUserRole,
  suprimirTitular,
} from '../services/api';
import { constanciaDeSupresion, recuentoDeSecciones } from './documentoDelTitular';

/**
 * Derechos de la persona cuyos datos guarda el sistema, con pantalla (capítulo 38).
 *
 * Lo que había y por qué no bastaba
 * ---------------------------------
 * Desde la Fase 14 el sistema sabe responder «¿qué datos tenéis de mí?» y «borradlos»:
 * `GET /leads/{id}/exportar` recorre el mapa de tablas de `derechos_del_titular` y
 * `DELETE /leads/{id}` suprime a la persona y todo lo que cuelga de ella, con la suite
 * comprobando que el correo no queda en **ninguna** fila de **ninguna** tabla. Funcionaba y
 * estaba probado. No tenía pantalla, y eso dejaba el derecho en manos de quien supiera
 * construir una petición HTTP con un token de líder comercial: el punto 16 de §6.2.
 *
 * Aquí no se escribe ni una línea de lógica de supresión. Esta pantalla **pide** las dos
 * cosas que ya existen y añade lo que faltaba alrededor: encontrar a la persona por su
 * correo, decir con palabras qué hace cada botón antes de pulsarlo, exigir que el borrado
 * se escriba y no solo se confirme, y dejar en la mano de quien atiende la petición un
 * archivo con lo que se entregó y otro con lo que se suprimió.
 *
 * La respuesta es la misma exista la persona o no
 * ----------------------------------------------
 * La consulta tiene **una sola forma de contestar**. Cuando no hay ficha, no responde un
 * error ni dice «esa persona no está»: responde el mismo panel, con el mismo encabezado y
 * la misma frase sobre lo que hay fuera de la base, y sin nada dentro.
 *
 * No es cortesía, es lo mismo que decidió el 404 de la cartera ajena y la huella con clave
 * de la bitácora. Una pantalla que distinguiera «nunca entró» de «ya se suprimió» sería el
 * oráculo de pertenencia que `huella_del_titular` existe para no ser: se escribiría una
 * lista de correos, se consultarían uno a uno, y la pantalla de los derechos acabaría
 * diciendo quién pidió que lo borraran.
 *
 * La consulta que no encuentra nada tampoco deja asiento, y también es a propósito: el
 * único dato personal que habría que anotar para dejarlo es el correo de alguien de quien
 * el sistema no guarda nada. La bitácora recoge lo que se entregó (`lead.exportar`) y lo
 * que se suprimió (`lead.eliminar`), que es el tratamiento; una búsqueda en vacío no lo es.
 */

// El rol decide qué se dibuja, igual que en el panel de administración. El servidor
// responde 403 a un asesor en los dos endpoints —lo comprueba
// `test_un_asesor_no_exporta_ni_suprime`—, así que esto no es la defensa: es no ofrecer un
// formulario cuyos botones van a fallar.
const DIRECCION = ['Sales_Lead', 'System_Admin'];

/**
 * Deja un archivo en el disco de quien lo pidió.
 *
 * Nada de esto sale a la red: el documento ya está en memoria y el navegador lo escribe.
 * Si no deja —algunos lo impiden cuando el gesto no viene de un clic—, se lanza y quien
 * llama lo cuenta; no se falla en silencio, que con una exportación de datos personales
 * sería lo peor: la persona se iría creyendo que tiene su copia.
 */
function descargar(nombre, texto) {
  const url = URL.createObjectURL(new Blob([texto], { type: 'application/json' }));
  try {
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function DerechosDelTitular() {
  const rol = getCurrentUserRole();
  const [correo, setCorreo] = useState('');
  // `null` mientras no se ha consultado nada. Consultado, es `{ correo, ficha, documento }`
  // con `ficha` y `documento` a `null` cuando no consta: el panel se dibuja igual.
  const [consulta, setConsulta] = useState(null);
  const [consultando, setConsultando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  // El texto que hay que escribir para suprimir, y si el bloque está abierto.
  const [escrito, setEscrito] = useState('');
  const [pidiendoSupresion, setPidiendoSupresion] = useState(false);
  const [suprimiendo, setSuprimiendo] = useState(false);

  if (!DIRECCION.includes(rol)) return null;

  const limpiar = () => {
    setError('');
    setAviso('');
  };

  const consultar = async (evento) => {
    evento.preventDefault();
    limpiar();
    setConsulta(null);
    setEscrito('');
    setPidiendoSupresion(false);
    setConsultando(true);
    try {
      const buscado = correo.trim().toLowerCase();
      const ficha = await buscarTitularPorCorreo(buscado);
      // Se pide la exportación aquí, en la consulta, y no al pulsar «Descargar». Es lo que
      // hace que «ver qué datos tiene el sistema» y «entregárselos» sean la misma cosa y
      // dejen el mismo asiento: la pantalla no puede enseñar un resumen que el servidor no
      // haya registrado que entregó.
      const documento = ficha ? await exportarDatosDelTitular(ficha.id) : null;
      setConsulta({ correo: buscado, ficha, documento });
    } catch (err) {
      setError(err.message || 'No se pudo completar la consulta.');
    } finally {
      setConsultando(false);
    }
  };

  const descargarExportacion = () => {
    limpiar();
    try {
      descargar(
        `datos-de-${consulta.correo}.json`,
        JSON.stringify(consulta.documento, null, 2),
      );
      setAviso('Archivo descargado. La entrega quedó registrada en la bitácora.');
    } catch {
      setError(
        'El navegador no dejó guardar el archivo. Vuelva a pulsar el botón; si sigue sin '
        + 'bajar, la entrega no se ha hecho.',
      );
    }
  };

  const suprimir = async () => {
    limpiar();
    setSuprimiendo(true);
    try {
      const { documento, correo: suprimido } = consulta;
      await suprimirTitular(consulta.ficha.id);
      const constancia = constanciaDeSupresion({
        documento,
        correo: suprimido,
        actor: getCurrentUser()?.email || null,
        suprimidoEn: new Date().toISOString(),
      });
      // La ficha ya no está: la consulta se deja en su forma vacía, que es la misma que
      // habría contestado si esta dirección no hubiera entrado nunca.
      setConsulta({ correo: suprimido, ficha: null, documento: null });
      setPidiendoSupresion(false);
      setEscrito('');
      try {
        descargar(`constancia-de-supresion-${suprimido}.json`, JSON.stringify(constancia, null, 2));
        setAviso(
          'Suprimido. Se descargó la constancia. En el CRM y en los demás sistemas de '
          + 'origen los datos siguen estando: hay que pedirlo allí aparte.',
        );
      } catch {
        setAviso(
          'Suprimido, pero el navegador no dejó guardar la constancia. Lo que salió de cada '
          + 'tabla está en la bitácora, en el asiento «lead.eliminar» de hoy. En el CRM y en '
          + 'los demás sistemas de origen los datos siguen estando.',
        );
      }
    } catch (err) {
      setError(err.message || 'No se pudo suprimir.');
    } finally {
      setSuprimiendo(false);
    }
  };

  const etiqueta = {
    display: 'block',
    fontSize: '0.72rem',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    marginBottom: '4px',
  };
  const dato = { fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-primary)' };
  const bloque = {
    background: 'var(--bg-base)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px 14px',
  };

  const documento = consulta?.documento;
  const ficha = consulta?.ficha;
  const secciones = documento ? recuentoDeSecciones(documento) : [];
  // El centinela evita que un campo vacío case con una consulta sin correo: comparar con
  // `''` haría que el botón naciera habilitado.
  const puedeSuprimir = escrito.trim().toLowerCase() === (consulta?.correo || '\u0000');

  return (
    <section className="glass-panel" aria-labelledby="titulo-derechos" style={{ padding: '24px', marginBottom: '32px' }}>
      <h2 id="titulo-derechos" style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '4px' }}>
        Derechos del titular
      </h2>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '760px', marginBottom: '16px' }}>
        Para atender a una persona que pregunta qué datos guarda el sistema sobre ella, que
        pide una copia o que pide que se borren. Se busca por su correo, que es la única
        forma en que el sistema la identifica.
      </p>

      {/* Qué hace cada acción, dicho ANTES de ofrecerla y no en el momento de pulsarla.
          Un «¿seguro?» delante de un borrado irreversible llega tarde: quien lo lee ya
          decidió. Esto se lee mientras se escribe el correo. */}
      <dl style={{ ...bloque, fontSize: '0.8rem', lineHeight: '1.55', marginBottom: '16px' }}>
        <dt style={{ fontWeight: '700' }}>Consultar</dt>
        <dd style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>
          Reúne todo lo que el sistema guarda de esa persona y lo enseña resumido. Cuenta
          como entrega de sus datos y queda en la bitácora con quién la pidió y cuándo.
        </dd>
        <dt style={{ fontWeight: '700' }}>Descargar</dt>
        <dd style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>
          Guarda ese mismo documento en un archivo, tal como lo construyó el servidor, para
          enviárselo a la persona. No se vuelve a pedir nada ni sale nada a la red.
        </dd>
        <dt style={{ fontWeight: '700' }}>Suprimir</dt>
        <dd style={{ margin: 0, color: 'var(--text-secondary)' }}>
          Borra a la persona y todo lo que cuelga de ella: actividades, puntuaciones con su
          explicación, tareas, avisos, desenlace, registros del CRM y avisos sin asociar.
          <strong> No tiene vuelta atrás</strong> y <strong>no borra nada en el CRM</strong>
          {' '}ni en los demás sistemas de origen. La bitácora se conserva: sigue diciendo
          quién hizo qué y cuándo, con los datos personales retirados de sus asientos.
        </dd>
      </dl>

      <form onSubmit={consultar} style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div style={{ flex: '1 1 280px' }}>
          <label style={etiqueta} htmlFor="derechos-correo">Correo de la persona</label>
          <input
            id="derechos-correo"
            type="email"
            required
            className="input-field"
            placeholder="persona@empresa.com"
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={consultando}>
          {consultando ? 'Consultando…' : 'Consultar qué consta'}
        </button>
      </form>

      {/* Las dos regiones vivas están SIEMPRE en el documento, vacías mientras no hay nada
          que decir. Una región que nace con su texto dentro no la anuncia ningún lector:
          anuncian lo que cambia dentro de una región que ya estaba. */}
      <div role="alert" style={{ marginBottom: error ? '12px' : 0 }}>
        {error && (
          <div style={{ ...bloque, borderColor: 'var(--error-text)', color: 'var(--error-text)', fontSize: '0.82rem' }}>
            ⚠️ {error}
          </div>
        )}
      </div>
      <div role="status" style={{ marginBottom: aviso ? '12px' : 0 }}>
        {aviso && (
          <div style={{ ...bloque, borderColor: 'var(--success-border)', background: 'var(--success-bg)', color: 'var(--success-text)', fontSize: '0.82rem' }}>
            {aviso}
          </div>
        )}
      </div>

      {consulta && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '700' }}>
            Lo que consta de <span style={dato}>{consulta.correo}</span>
          </h3>

          {!ficha && (
            <div style={bloque}>
              <p style={{ fontSize: '0.85rem', marginBottom: '8px' }}>
                No consta ninguna ficha con esta dirección.
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.55' }}>
                Esta respuesta es la misma para una dirección que nunca entró y para una cuya
                ficha ya no está, y lo es a propósito: distinguirlas convertiría esta pantalla
                en una forma de averiguar quién figura en la base consultando correos uno a
                uno. Tampoco habla por el CRM, por los formularios ni por las copias de
                seguridad, que son sistemas distintos con sus propios plazos.
              </p>
            </div>
          )}

          {ficha && documento && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                <div style={bloque}>
                  <span style={etiqueta}>Persona</span>
                  <div style={{ fontSize: '0.85rem', fontWeight: '600' }}>
                    {documento.datos_del_prospecto.first_name} {documento.datos_del_prospecto.last_name}
                  </div>
                  <div style={dato}>{documento.datos_del_prospecto.email}</div>
                  {documento.datos_del_prospecto.phone && (
                    <div style={dato}>{documento.datos_del_prospecto.phone}</div>
                  )}
                  {documento.datos_del_prospecto.company && (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {documento.datos_del_prospecto.company}
                      {documento.datos_del_prospecto.job_title ? ` · ${documento.datos_del_prospecto.job_title}` : ''}
                    </div>
                  )}
                </div>

                {/* De dónde llegaron. El canal y la publicación los guarda la ficha; los
                    sistemas que pudieron mandarla y que esta pantalla no alcanza los dice
                    el propio documento, que es quien sabe lo que hay fuera de la base. */}
                <div style={bloque}>
                  <span style={etiqueta}>De dónde llegaron</span>
                  <div style={{ fontSize: '0.85rem' }}>
                    Canal: <strong>{documento.datos_del_prospecto.source || 'sin registrar'}</strong>
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {documento.campana
                      ? `Publicación: ${documento.campana.name}`
                      : 'Sin publicación asociada'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {documento.datos_del_prospecto.privacy_notice_accepted_at
                      ? 'Aviso de privacidad aceptado el '
                        + `${documento.datos_del_prospecto.privacy_notice_accepted_at.slice(0, 10)}`
                        + ` (${documento.datos_del_prospecto.privacy_notice_source})`
                      : 'No consta que haya aceptado el aviso de privacidad'}
                  </div>
                </div>
              </div>

              <div>
                <h4 style={{ fontSize: '0.8rem', fontWeight: '700', marginBottom: '6px' }}>
                  Qué guarda el sistema
                </h4>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Sección</th>
                        <th scope="col">Registros</th>
                      </tr>
                    </thead>
                    <tbody>
                      {secciones.map(({ clave, etiqueta: nombre, filas }) => (
                        <tr key={clave}>
                          <td>{nombre}</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{filas}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Las secciones y sus recuentos son los del documento que entrega el
                  servidor; no se enumeran aquí. Una tabla nueva aparece en esta lista el día
                  que entra en el mapa de la supresión, sin tocar esta pantalla.
                </p>
              </div>

              <div style={bloque}>
                <span style={etiqueta}>Lo que no alcanza ni esta consulta ni la supresión</span>
                <ul style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55', margin: '4px 0 0 0', paddingLeft: '18px' }}>
                  {(documento.fuera_de_la_base || []).map((linea) => (
                    <li key={linea}>{linea}</li>
                  ))}
                </ul>
              </div>

              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-secondary" onClick={descargarExportacion}>
                  Descargar el archivo con sus datos
                </button>
                {!pidiendoSupresion && (
                  // `btn` a secas no dibujaba nada —ni fondo ni borde— porque la paleta no
                  // tenía color de acción destructiva (§6.4 punto 31). El botón que abre el
                  // borrado de los datos de una persona no puede ser el elemento menos
                  // visible de la pantalla.
                  <button type="button" className="btn btn-danger" onClick={() => { limpiar(); setPidiendoSupresion(true); }}>
                    Suprimir estos datos…
                  </button>
                )}
              </div>

              {pidiendoSupresion && (
                <div style={{ ...bloque, borderColor: 'var(--hot-text)' }}>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--hot-text)', marginBottom: '8px' }}>
                    Suprimir los datos de {documento.datos_del_prospecto.first_name}{' '}
                    {documento.datos_del_prospecto.last_name}
                  </h4>
                  {/* Aquí NO va un total. Sumar los recuentos de la tabla daría un número
                      que incluye los asientos de la bitácora, y esos no se borran: se les
                      retiran los datos personales y se quedan. Un «se borrarán 23
                      registros» que en realidad borra 18 y limpia 5 es peor que no dar
                      número, porque el que da no es el que ocurre. */}
                  <p style={{ fontSize: '0.8rem', lineHeight: '1.55', marginBottom: '8px' }}>
                    Se borran la ficha y los registros de la lista de arriba.{' '}
                    <strong>No se puede deshacer</strong> y no queda copia dentro del
                    sistema. De la bitácora no se borra ningún asiento: se le retiran los
                    datos personales de esta persona y sigue diciendo quién hizo qué y
                    cuándo.
                  </p>
                  <p style={{ fontSize: '0.8rem', lineHeight: '1.55', marginBottom: '10px' }}>
                    <strong>Suprimir aquí no suprime en el CRM</strong> ni en LinkedIn, Calendly
                    o WhatsApp. Si la persona pidió el borrado completo, hay que pedirlo
                    también allí; y mientras exista allí, una nueva entrega volvería a crear
                    la ficha aquí.
                  </p>
                  {/* Escribir el correo y no marcar una casilla ni pulsar «Sí». Una
                      confirmación que se resuelve con un clic en el mismo sitio donde estaba
                      el ratón no es una confirmación: es un segundo botón. Escribir la
                      dirección obliga a leer de quién se está hablando. */}
                  <label style={etiqueta} htmlFor="derechos-confirmar">
                    Escriba el correo completo para confirmar
                  </label>
                  <input
                    id="derechos-confirmar"
                    className="input-field"
                    autoComplete="off"
                    placeholder={consulta.correo}
                    value={escrito}
                    onChange={(e) => setEscrito(e.target.value)}
                    style={{ maxWidth: '360px' }}
                  />
                  <div style={{ display: 'flex', gap: '10px', marginTop: '10px', flexWrap: 'wrap' }}>
                    {/* Era `btn-primary`, es decir, el mismo blanco que «Buscar». El
                        blanco de esta paleta significa «la acción esperada de esta
                        pantalla», y borrar los datos de una persona no lo es. Apagado
                        hasta que el correo esté escrito, y apagado se ve apagado desde el
                        capítulo 39: antes no había ningún `:disabled` en la hoja. */}
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={!puedeSuprimir || suprimiendo}
                      onClick={suprimir}
                    >
                      {suprimiendo ? 'Suprimiendo…' : 'Suprimir definitivamente'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={suprimiendo}
                      onClick={() => { setPidiendoSupresion(false); setEscrito(''); }}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
