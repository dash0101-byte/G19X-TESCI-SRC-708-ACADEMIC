import React, { useState } from 'react';
import { MAX_TEXTO_DE_LINKEDIN, cortarComoLinkedIn } from './cortarComoLinkedIn';

// Cómo se verá el post en el feed de LinkedIn, antes de pegarlo.
//
// LinkedIn corta el texto en el feed y añade «…ver más»: lo que va antes del corte es lo que
// casi todo el mundo lee, y el enlace, al final del texto, casi nunca queda antes. Por eso
// esta vista previa corta donde corta LinkedIn —a las tres líneas o a unos 210 caracteres, lo
// que llegue antes—, y dice si el enlace ha quedado escondido.
//
// El tope de LinkedIn son 3 000 caracteres. El servidor ya limita la descripción para que el
// texto copiado quepa; aquí se cuenta el texto entero, enlace incluido, y se avisa si pasa.
export default function VistaPreviaDelPost({ texto, enlace, autor = 'PluriOne' }) {
  const [completo, setCompleto] = useState(false);
  const { visible, cortado } = cortarComoLinkedIn(texto);
  const longitud = texto.length;
  const sobran = longitud - MAX_TEXTO_DE_LINKEDIN;
  const enlaceEscondido = cortado && enlace && !visible.includes(enlace);

  return (
    <figure aria-label="Vista previa del post en LinkedIn" style={tarjeta}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <div aria-hidden="true" style={avatar}>P1</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#191919' }}>{autor}</div>
          <div style={{ fontSize: '0.7rem', color: '#666' }}>Ahora · 🌐</div>
        </div>
      </div>
      <p data-testid="texto-del-post" style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: '#191919', margin: 0, wordBreak: 'break-word' }}>
        {completo || !cortado ? texto : visible}
        {cortado && !completo && (
          <>
            {'…'}
            <button type="button" onClick={() => setCompleto(true)} style={verMas}>ver más</button>
          </>
        )}
      </p>
      <figcaption style={{ marginTop: '8px', fontSize: '0.72rem', color: sobran > 0 ? '#b42318' : '#555' }}>
        <span data-testid="longitud-del-post">{longitud} / {MAX_TEXTO_DE_LINKEDIN} caracteres</span>
        {sobran > 0 && (
          <strong role="alert" style={{ display: 'block' }}>
            LinkedIn no admite más de {MAX_TEXTO_DE_LINKEDIN} caracteres: sobran {sobran}.
          </strong>
        )}
        {enlaceEscondido && (
          <span style={{ display: 'block', color: '#7a4b00' }}>
            El enlace queda después de «ver más»: solo lo verá quien despliegue el texto.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

// Colores de LinkedIn y no del panel: la vista previa enseña el post como se verá allí.
const tarjeta = {
  margin: 0,
  padding: '12px 14px',
  background: '#ffffff',
  border: '1px solid #e0dfdc',
  borderRadius: '8px',
  maxWidth: '555px',
};

const avatar = {
  width: '36px',
  height: '36px',
  borderRadius: '50%',
  background: '#0a66c2',
  color: '#fff',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontWeight: 700,
  fontSize: '0.75rem',
};

const verMas = {
  background: 'none',
  border: 0,
  padding: 0,
  marginLeft: '2px',
  color: '#666',
  fontWeight: 600,
  cursor: 'pointer',
  fontSize: '0.85rem',
};
