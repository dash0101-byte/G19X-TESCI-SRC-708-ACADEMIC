// Cómo se lee un rechazo del servidor, en un sitio.
//
// Esto no es código nuevo: son dos constantes que estaban escritas **dos veces**, una en
// `services/api.js` y otra en `components/erroresDeFormulario.js`, con el mismo nombre y el
// mismo valor. Dos copias de la misma decisión es la forma que este repositorio ya conoce de
// cerca: `texto_o_nada` vivía dos veces en el servidor hasta el capítulo 41, y mientras cada
// puerta tuvo su definición de «vacío», mantenerlas de acuerdo dependía de que quien tocara
// una se acordara de la otra.
//
// Y aquí ya se habían separado. La tabla `POR_TIPO` la escribió el capítulo 40 para las
// pantallas que reparten su 422 por campos, y la función que ve **todas** las demás
// —`renglonesDelCuerpo`, en `api.js`— no la tenía: entregaba el `msg` de Pydantic tal cual.
// Medido en los dos formularios del panel que no reparten, **seis de nueve rechazos llegaban
// en inglés** —«Field required», «Input should be a valid date or datetime»— y cinco de los
// seis eran de un tipo que esta tabla ya traducía. No faltaba la traducción: faltaba que la
// viera quien la necesitaba (capítulo 45).

/**
 * Pydantic antepone «Value error, » a lo que dice un validador propio.
 *
 * Es el nombre interno de su excepción y no significa nada para quien lo lee, pero sirve
 * para algo mejor que quitarlo: **distingue nuestros mensajes de los suyos**. Un
 * `value_error` con este prefijo lo escribió alguien de este repositorio, en castellano y
 * para leerse —«El teléfono no es un número válido: revise la lada…»—. Uno sin prefijo
 * viene de una biblioteca y está en inglés —«value is not a valid email address»—.
 */
export const RUIDO_DE_PYDANTIC = /^(Value error|Assertion failed),\s*/;

/**
 * Lo que se dice de cada clase de error, por el `type` que manda Pydantic y no por su
 * texto en inglés.
 *
 * Por el tipo y no por el texto porque el texto es de ellos: cambia entre versiones, y una
 * tabla que compare cadenas en inglés se queda muda en la primera actualización sin que
 * ninguna prueba lo note. El tipo es parte del contrato de la API.
 *
 * Las frases están escritas para caber **debajo de un campo**, que es donde el capítulo 40
 * las puso: no dicen de qué campo hablan, porque eso lo dice el sitio donde salen. Cuando la
 * pantalla no puede repartirlas, lo que se enseña es la frase del servidor y no estas.
 */
export const POR_TIPO = {
  missing: () => 'Falta este campo.',
  string_too_short: (item) => (item.ctx && item.ctx.min_length
    ? `Tiene que tener al menos ${item.ctx.min_length} caracteres.`
    : 'Es demasiado corto.'),
  string_too_long: (item) => (item.ctx && item.ctx.max_length
    ? `No puede pasar de ${item.ctx.max_length} caracteres.`
    : 'Es demasiado largo.'),
  string_pattern_mismatch: () => 'No tiene la forma que se espera.',
  greater_than_equal: (item) => `Tiene que ser ${item.ctx.ge} o más.`,
  less_than_equal: (item) => `Tiene que ser ${item.ctx.le} o menos.`,
  int_parsing: () => 'Escriba un número entero.',
  float_parsing: () => 'Escriba un número.',
  bool_parsing: () => 'Tiene que ser sí o no.',
  enum: () => 'Elija una de las opciones de la lista.',
  literal_error: () => 'Elija una de las opciones de la lista.',
  date_from_datetime_parsing: () => 'Escriba una fecha válida.',
  datetime_parsing: () => 'Escriba una fecha válida.',
  // El tercer nombre de la misma familia, que faltaba. Pydantic tiene uno por cada dirección
  // de la conversión —`date_from_datetime_parsing` cuando el campo es una fecha y
  // `datetime_from_date_parsing` cuando es un instante— y la tabla solo tenía dos de los
  // tres, así que la fecha de una reunión mal escrita contestaba «Input should be a valid
  // datetime or date, input is too short» mientras la de un cierre contestaba en castellano.
  // Es el mismo error, en dos campos del mismo panel, con dos idiomas.
  datetime_from_date_parsing: () => 'Escriba una fecha válida.',
  url_parsing: () => 'Escriba una dirección web completa, con https://.',
  extra_forbidden: () => 'Este dato no se admite aquí.',
  // La familia `*_type`: lo que llegó no es de la clase del campo —una lista donde va un
  // texto, un texto donde va un objeto—. Un formulario no puede provocarla, porque un
  // `<input>` manda siempre una cadena; un cliente de la API, sí, y es la mitad de los tipos
  // que estas puertas pueden contestar. Ocho frases que faltaban, y la razón de que faltaran
  // es que la tabla se escribió mirando lo que un formulario rompe (capítulo 45).
  string_type: () => 'Tiene que ser un texto.',
  int_type: () => 'Tiene que ser un número entero.',
  float_type: () => 'Tiene que ser un número.',
  bool_type: () => 'Tiene que ser sí o no.',
  date_type: () => 'Tiene que ser una fecha.',
  datetime_type: () => 'Tiene que ser una fecha con hora.',
  dict_type: () => 'Tiene que ser un objeto con sus campos.',
  // Y una fecha con hora donde se espera un día: Pydantic lo admite si la hora es cero y lo
  // rechaza si no, porque recortarla sería decidir en qué zona horaria cae ese día.
  date_from_datetime_inexact: () => 'Escriba un día, sin hora.',
  // Los campos sin los que la fila no existe, enviados vacíos (capítulo 45). El renglón
  // llega con `loc: ['body']` —lo escribe un validador de modelo, que no puede señalar un
  // campo— y con la lista en `ctx.campos`, así que aquí no hace falta que diga cuál es: ya
  // se está poniendo debajo del campo del que habla. La frase larga que trae el servidor es
  // para la pantalla que no pueda repartirlo.
  campos_vacios_prohibidos: () => 'No puede quedar vacío.',
};

/**
 * Los tipos de rechazo que escribió este repositorio, y no Pydantic.
 *
 * Un validador propio que levanta un `ValueError` se reconoce por el prefijo de arriba. Uno
 * que levanta un `PydanticCustomError` **no lleva prefijo** —y es lo que hacen los tres
 * validadores de modelo del capítulo 45— así que hace falta decir cuáles son por su tipo.
 * Son nuestros por construcción: el nombre lo elige quien escribe el error.
 *
 * Importa porque sus frases están escritas para leerse **enteras y solas**, en el aviso de
 * arriba de una pantalla que no reparte: «La ficha no existe sin alguno de los campos que
 * llegaron vacíos». La tabla de arriba tiene para ese mismo tipo una frase corta —«No puede
 * quedar vacío»— que solo dice algo debajo de un campo. Las dos son correctas en su sitio, y
 * ponerlas al revés deja al aviso de arriba diciendo que algo no puede quedar vacío sin
 * decir qué.
 */
export const TIPOS_PROPIOS = ['campos_vacios_prohibidos'];

/**
 * El texto de un renglón del 422 para un aviso que **no** va debajo de ningún campo.
 *
 * Es lo que `renglonesDelCuerpo` de `api.js` necesitaba y no tenía. El orden:
 *
 * 1. Si lo escribió un validador propio —por el prefijo o por el tipo—, su frase. Está en
 *    castellano, explica el caso concreto y se lee sola.
 * 2. Si no, la tabla por tipo.
 * 3. Y si el tipo no está en la tabla, una frase genérica. **No** el texto en inglés: un
 *    mensaje que no se entiende no es mejor que uno vago. Es la misma decisión que el
 *    capítulo 40 tomó para el reparto por campos, aplicada al aviso de arriba; lo que la
 *    hace sostenible es que `pruebas/rechazos.test.js` saca de los esquemas del servidor los
 *    tipos que esas puertas pueden contestar y exige que la tabla los cubra, así que el hueco
 *    del punto 3 no se llena en silencio.
 */
export function textoDelRenglon(item) {
  const crudo = String((item && item.msg) || '');
  if (RUIDO_DE_PYDANTIC.test(crudo)) return crudo.replace(RUIDO_DE_PYDANTIC, '');
  if (item && TIPOS_PROPIOS.includes(item.type)) return crudo;
  const deLaTabla = POR_TIPO[item && item.type];
  if (deLaTabla) {
    try {
      return deLaTabla(item);
    } catch {
      // Un `ctx` que no trae lo que su tipo promete no puede dejar la pantalla sin aviso: el
      // objetivo era explicar un error, no provocar otro.
      return 'No se admite este valor.';
    }
  }
  return 'No se admite este valor.';
}
