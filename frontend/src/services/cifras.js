/**
 * Cómo se enseña una cifra que puede no existir.
 *
 * El servidor distingue «cero» de «no hay» —`tasa_de_envio` es `null` sin visitas,
 * `score_medio` es `null` sin perfiles—, y la pantalla tiene que distinguirlo también: un
 * 0 % dice «nadie escribió de los que miraron» y un «—» dice «no miró nadie». Son dos
 * frases distintas y la tabla las pone en la misma casilla.
 *
 * Vive aquí y no dentro de un componente porque ya estaba escrito tres veces: el panel de
 * desenlaces lo tenía resuelto desde el capítulo 30 con estas dos funciones, y las dos
 * pantallas de publicaciones —anteriores— repetían la comparación a mano en cada celda y se
 * les quedó fuera la columna del score. Recorriendo la demostración se veía el resultado en
 * una sola fila: «Tasa de envío —» y «Score medio 0», juntas, contando lo mismo.
 */

export const NUMERO = (valor) => (valor === null || valor === undefined ? '—' : valor);

export const PORCENTAJE = (valor) => (valor === null || valor === undefined ? '—' : `${valor} %`);
