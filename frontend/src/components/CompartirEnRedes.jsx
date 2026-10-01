import { useMemo, useState } from 'react';

import { svgQR } from './qr';

/**
 * Difusión de una publicación por varias redes (capítulo 27).
 *
 * Dos piezas, porque son dos momentos distintos:
 *
 * * `RedesDelFormulario`: qué redes se activan, al crear o editar.
 * * `CompartirEnRedes`: los botones de compartir, el texto de cada red y el código QR, en
 *   la lista, cuando la publicación ya existe.
 *
 * Los enlaces, los textos y sus recortes vienen calculados del servidor (`difusion`). No se
 * rehacen aquí: el recorte de X a 280 caracteres contando el enlace es una regla que ya se
 * prueba en el backend, y calcularla dos veces en dos lenguajes es tener dos versiones de
 * la misma regla esperando a separarse.
 *
 * Nada de esto publica por nadie. Los botones abren el enlace oficial de compartir de cada
 * red en una pestaña nueva, con la sesión de quien pulsa; publica esa persona, a mano.
 */

// Ni `noopener` ni `noreferrer` son adorno: sin el primero, la página que se abre puede
// tocar la que la abrió a través de `window.opener`.
const DESTINO = { target: '_blank', rel: 'noopener noreferrer' };

const SIN_RED = '';

export function RedesDelFormulario({ activas, onChange, disponibles }) {
  const alternar = (clave, marcada) => {
    const siguiente = disponibles
      .map((r) => r.clave)
      .filter((c) => (c === clave ? marcada : activas.includes(c)));
    onChange(siguiente);
  };

  return (
    <fieldset className="interes-redes">
      <legend>Redes de difusión</legend>
      <p className="form-hint">
        Cada red tiene su propio enlace a la misma página. Desactivar una no invalida lo que
        ya se compartió con ella: lo que llegue por ahí se sigue contando.
      </p>
      <div className="interes-redes-lista">
        {disponibles.map((red) => (
          <label key={red.clave} className="interes-red-casilla">
            <input
              type="checkbox"
              checked={activas.includes(red.clave)}
              onChange={(e) => alternar(red.clave, e.target.checked)}
            />
            <span>{red.etiqueta}</span>
          </label>
        ))}
      </div>
      {activas.length === 0 && (
        <p className="form-error">Hace falta al menos una red de difusión.</p>
      )}
    </fieldset>
  );
}


/** Descarga el SVG sin pasar por ningún servidor: se arma en memoria y se suelta. */
function descargarSVG(contenido, nombre) {
  if (typeof URL.createObjectURL !== 'function') return false;
  const blob = new Blob([contenido], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const ancla = document.createElement('a');
  ancla.href = url;
  ancla.download = nombre;
  document.body.appendChild(ancla);
  ancla.click();
  ancla.remove();
  URL.revokeObjectURL(url);
  return true;
}

function nombreDeArchivo(titulo, etiqueta) {
  const limpio = String(titulo)
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .toLowerCase();
  return `qr-${limpio || 'publicacion'}-${etiqueta}.svg`;
}

/**
 * `direccionCaida`: la dirección pública configurada no contesta (capítulo 34).
 *
 * Se pasa desde `Publicaciones`, que ya la consulta para el aviso de arriba. Aquí hace
 * falta por un motivo concreto y encontrado usándolo (01-10-2026): este panel es donde
 * alguien **actúa** sobre el enlace —lo comparte, lo imprime, lo escanea—, y el aviso de
 * arriba se queda fuera de la vista en cuanto se despliega una publicación. Un código QR
 * impecable de una dirección muerta se ve exactamente igual que uno bueno, y el único
 * momento en que se descubre es con el teléfono en la mano delante del papel ya impreso.
 */
export default function CompartirEnRedes({ publicacion, onCopiar, direccionCaida = false }) {
  // Envuelto porque `|| []` crea una lista nueva en cada render, y eso rehacía el código
  // QR —lo más caro de esta pantalla— cada vez que se repintara cualquier otra cosa.
  const difusion = useMemo(() => publicacion.difusion || [], [publicacion.difusion]);
  const activas = useMemo(() => difusion.filter((r) => r.activa), [difusion]);
  const [paraElQR, setParaElQR] = useState(SIN_RED);

  const enlaceDelQR = useMemo(() => {
    if (paraElQR === SIN_RED) return publicacion.enlace_publico;
    return (difusion.find((r) => r.clave === paraElQR) || {}).enlace || publicacion.enlace_publico;
  }, [paraElQR, difusion, publicacion.enlace_publico]);

  // Si el enlace no cupiera en un código, se dice en lugar de dibujar uno roto.
  const { svg, fallo } = useMemo(() => {
    try {
      return { svg: svgQR(enlaceDelQR, { escala: 4 }), fallo: '' };
    } catch (err) {
      return { svg: '', fallo: err.message };
    }
  }, [enlaceDelQR]);

  const etiquetaDelQR =
    paraElQR === SIN_RED ? 'impreso' : (difusion.find((r) => r.clave === paraElQR) || {}).clave;

  return (
    <div className="interes-compartir">
      {direccionCaida && (
        // El único estilo en línea del componente, y va aquí a propósito. El resto se
        // apoya en catorce clases que la hoja no define (§6.4, punto 30), así que sale sin
        // formato; para un texto de ayuda eso es feo y para un **aviso** es inútil, porque
        // un aviso que se ve igual que el cuerpo no lo lee nadie. Escribir las catorce
        // clases es diseñar el panel entero y sigue fuera de alcance; darle borde y color a
        // esta no lo es.
        <div
          role="alert"
          className="interes-compartir-aviso"
          style={{
            padding: '10px 12px',
            marginBottom: '12px',
            border: '1px solid var(--warm-text)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--warm-text)',
            fontSize: '0.8rem',
            lineHeight: '1.5',
          }}
        >
          <strong>La dirección pública no contesta ahora mismo.</strong> Lo que se copie,
          se comparta o se imprima desde aquí —el enlace y el código QR— lleva a esa
          dirección, así que hoy no llega a ninguna parte. El código se dibuja igual porque
          el enlace es correcto; lo que no responde es el otro extremo.
        </div>
      )}
      <h5>Compartir en…</h5>
      <ul className="interes-compartir-lista" aria-label="Redes activas">
        {activas.map((red) => (
          <li key={red.clave}>
            <div className="interes-compartir-red">
              <strong>{red.etiqueta}</strong>
              {red.maximo && (
                <span className="interes-compartir-cuenta">
                  {red.longitud} / {red.maximo}
                </span>
              )}
            </div>
            <div className="interes-compartir-acciones">
              {red.compartir ? (
                <a className="btn btn-sm" href={red.compartir} {...DESTINO}>
                  Compartir en {red.etiqueta}
                </a>
              ) : (
                <span className="interes-compartir-sin-boton">
                  {red.etiqueta} no tiene enlace para compartir desde la web.
                </span>
              )}
              {/* «Copiar texto» está siempre, no solo donde la red no lo admite: también
                  se quiere pegar el texto a mano en una historia o en un mensaje. */}
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => onCopiar(red.texto, `${publicacion.name} · ${red.etiqueta}`)}
              >
                Copiar texto
              </button>
            </div>
            {red.aviso && <p className="interes-compartir-aviso">{red.aviso}</p>}
          </li>
        ))}
      </ul>

      <div className="interes-qr">
        <h5>Código QR</h5>
        <label htmlFor={`qr-red-${publicacion.id}`}>Enlace del código</label>
        <select
          id={`qr-red-${publicacion.id}`}
          value={paraElQR}
          onChange={(e) => setParaElQR(e.target.value)}
        >
          <option value={SIN_RED}>Material impreso (sin red)</option>
          {activas.map((red) => (
            <option key={red.clave} value={red.clave}>
              {red.etiqueta}
            </option>
          ))}
        </select>
        {fallo ? (
          <p className="form-error">{fallo}</p>
        ) : (
          <>
            {/* El SVG se genera aquí, en el navegador: el enlace no sale a ningún servicio
                de códigos QR. */}
            <div
              className="interes-qr-dibujo"
              role="img"
              aria-label={`Código QR de ${enlaceDelQR}`}
              // El SVG lo arma `svgQR` con números que salen de su propia matriz: no hay
              // ningún texto de fuera dentro del dibujo, así que no hay nada que escapar.
              dangerouslySetInnerHTML={{ __html: svg }}
            />
            <button
              type="button"
              className="btn btn-sm btn-secondary"
              onClick={() => descargarSVG(svg, nombreDeArchivo(publicacion.name, etiquetaDelQR))}
            >
              Descargar código QR
            </button>
          </>
        )}
      </div>
    </div>
  );
}

