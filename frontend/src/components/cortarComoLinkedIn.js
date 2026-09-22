// Dónde corta LinkedIn el texto de un post en el feed, y su tope de caracteres.
export const MAX_TEXTO_DE_LINKEDIN = 3000;
export const CORTE_EN_CARACTERES = 210;
export const CORTE_EN_LINEAS = 3;

export function cortarComoLinkedIn(texto) {
  const lineas = texto.split('\n');
  let corte = texto.length;
  if (lineas.length > CORTE_EN_LINEAS) {
    corte = lineas.slice(0, CORTE_EN_LINEAS).join('\n').length;
  }
  corte = Math.min(corte, CORTE_EN_CARACTERES);
  if (corte >= texto.length) return { visible: texto, cortado: false };
  // No se parte una palabra por la mitad, como no la parte LinkedIn.
  const espacio = texto.lastIndexOf(' ', corte);
  const final = espacio > corte * 0.6 ? espacio : corte;
  return { visible: texto.slice(0, final).trimEnd(), cortado: true };
}

