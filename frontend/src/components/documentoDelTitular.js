// ============================================================================
// Leer el documento de acceso del titular, y levantar acta de su supresión
// ============================================================================
//
// Las dos funciones que `DerechosDelTitular.jsx` necesita y que no pintan nada. Viven en
// su propio archivo por la misma razón que `cortarComoLinkedIn.js` y `ventanaModal.js`:
// un `.jsx` que exporta además funciones pierde la recarga en caliente, y el `linter` lo
// dice. Que sean dos funciones puras tiene de paso la ventaja de que se prueban sin montar
// la pantalla.
//
// Lo que NO hay aquí es una lista de secciones escrita a mano. El documento que entrega el
// servidor nombra sus propias secciones —las deriva del mapa de tablas de
// `derechos_del_titular`—, y aquí se recorren. Una tabla nueva que entre en ese mapa
// aparece en la pantalla el mismo día, sin tocar ni esta función ni la otra.

/**
 * Las secciones del documento que son listas de registros, con su recuento.
 *
 * Parte del mismo criterio que el asiento `lead.exportar` de la bitácora, que anota qué se
 * entregó con `{clave: len(valor) for ... if isinstance(valor, list)}`, y le añade una
 * condición: que los elementos sean **registros** y no frases.
 *
 * La condición hace falta porque `fuera_de_la_base` también es una lista, y es una lista de
 * tres párrafos que explican qué copias existen donde el sistema no llega. Contarla como
 * una sección más dejaba en la pantalla la fila «fuera de la base — 3», que no dice que
 * haya tres registros de la persona en ninguna parte: dice que hay tres avisos escritos. La
 * primera versión de esta función no la distinguía y la fila salió en la tabla.
 *
 * Se decide mirando los elementos, no por una lista de claves escrita a mano: una sección
 * nueva de registros entra sola, y una nueva de texto se queda fuera sola. Las vacías
 * entran, que es lo correcto —«cero actividades» es un dato— y de paso lo único que se
 * puede hacer sin elementos que mirar.
 */
export function recuentoDeSecciones(documento) {
  return Object.entries(documento || {})
    .filter(([, valor]) => Array.isArray(valor) && valor.every((e) => e && typeof e === 'object'))
    .map(([clave, filas]) => ({
      clave,
      etiqueta: clave.replace(/_/g, ' '),
      filas: filas.length,
    }));
}

export const FORMATO_CONSTANCIA = 'plurione.constancia-de-supresion/1';

/**
 * La constancia del borrado, armada con lo que consta y sin inventar nada.
 *
 * Los recuentos salen del documento de acceso que el servidor construyó segundos antes, no
 * de la supresión: `DELETE /leads/{id}` responde 204 sin cuerpo y lo que se fue de cada
 * tabla queda en el asiento `lead.eliminar`. Esto podría haberse disimulado —nadie iba a
 * notar la diferencia leyendo el archivo—, y es justo lo que no se hace: la constancia dice
 * de dónde salen sus números y nombra el asiento donde está el registro del servidor, que
 * es el que vale.
 *
 * Tampoco se calcula aquí la huella con clave del correo que ese asiento guarda: hace falta
 * `SECRET_KEY`, que no sale del servidor y no tiene por qué salir. Quien necesite comprobar
 * «¿se suprimió a esta persona?» lo pregunta a la bitácora con el correo en la mano.
 */
export function constanciaDeSupresion({ documento, correo, actor, suprimidoEn }) {
  return {
    formato: FORMATO_CONSTANCIA,
    suprimido_en: suprimidoEn,
    titular: correo,
    prospecto_id: documento.prospecto_id,
    solicitado_por: actor,
    lo_que_habia: Object.fromEntries(
      recuentoDeSecciones(documento).map(({ clave, filas }) => [clave, filas]),
    ),
    procedencia_de_los_recuentos:
      'Del documento de acceso generado inmediatamente antes de suprimir, no de la propia '
      + 'supresión: el servidor responde al borrado sin cuerpo. El registro de lo que salió '
      + 'de cada tabla está en la bitácora, en el asiento «lead.eliminar» de esta fecha, con '
      + 'una huella con clave del correo en lugar del correo.',
    lo_que_no_se_suprime: documento.fuera_de_la_base,
  };
}
