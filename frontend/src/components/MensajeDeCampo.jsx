// ============================================================================
// El renglón que va debajo de un campo cuando su valor no vale
// ============================================================================
//
// Está en su propio archivo y no junto al resto del mecanismo
// (`erroresDeFormulario.js`) por una razón de herramienta y no de diseño: un archivo que
// exporta un componente **y** funciones rompe la recarga en caliente de Vite, y el
// `linter` del proyecto no admite avisos.
//
// Lo que no se separa es lo que importa: el `id` de este párrafo y el `aria-describedby`
// del campo salen los dos de `idDelMensaje`. Si se escribieran a mano en los dos sitios, el
// día que uno cambiara el lector de pantalla dejaría de leer el error sin que nada fallara.

import React from 'react';

import { idDelMensaje } from './erroresDeFormulario';

export default function MensajeDeCampo({ nombre, errores, prefijo, clase = 'form-error' }) {
  if (!errores || !errores[nombre]) return null;
  return (
    <p id={idDelMensaje(prefijo, nombre)} className={clase}>{errores[nombre]}</p>
  );
}
