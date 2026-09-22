// Datos de la ficha del prospecto tal como se envían a la API.

/**
 * Ingresos escritos en el formulario, o `null` si se dejó vacío o no son una cifra positiva.
 *
 * Antes se enviaba `parseFloat(valor) || 0`: guardar la ficha sin tocar el campo escribía un
 * cero, y el modelo lo leía como una empresa que no factura (capítulo 24). Un campo vacío es
 * un dato que falta, y así tiene que llegar.
 */
export function ingresosDelFormulario(valor) {
  const numero = Number.parseFloat(valor);
  return Number.isFinite(numero) && numero > 0 ? numero : null;
}
