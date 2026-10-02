// ============================================================================
// Ningún color se escribe a mano: todos salen de la paleta, donde se miden
// ============================================================================
//
// El hueco que cierra esta comprobación
// --------------------------------------
// El cliente tiene dos guardas de contraste y las dos están bien escritas:
//
// * `accesibilidad.test.jsx` pasa `axe` por las nueve pantallas, y dice en su cabecera que
//   **no mide contraste** —«necesita píxeles, y jsdom no dibuja»— y que eso va en
//   `contraste.test.js`.
// * `contraste.test.js` aplica la fórmula de WCAG a los colores de la paleta, y dice en su
//   cabecera que los lee del `:root` de `index.css` y que nadie los copia.
//
// Las dos frases son verdad, y entre las dos queda un sitio: **un color escrito en un
// `style` del JSX no está en ninguna de las dos**. No lo mide la primera porque no dibuja,
// y no lo mide la segunda porque no está en la paleta. Trece archivos del cliente tenían
// colores ahí, y cuatro de ellos no llegaban al mínimo de §1.4.3: #ef4444 como texto de un
// aviso da 4.43:1 sobre el panel y 4.17:1 sobre el elevado. El color no estaba mal
// elegido; estaba elegido donde no se mide.
//
// Qué hace, y por qué así
// ------------------------
// Saca la lista **del código**, igual que `clases.test.js` con las clases y
// `tokens.test.js` con los tokens: recorre el cliente y exige que todo color viva en el
// `:root` o esté inventariado con su motivo escrito. No comprueba que el color esté bien
// elegido —eso es `contraste.test.js`—: comprueba que **pase por donde se mide**.
//
// El inventario no es una lista de excepciones cómodas: las cuatro entradas que tiene son
// colores que **no deben** seguir esta paleta, y eso es distinto de que no la sigan por
// descuido. Un QR tiene que ser negro sobre blanco para que una cámara lo lea, y la
// tarjeta de vista previa imita la de LinkedIn: tematizar cualquiera de los dos sería el
// defecto, no el arreglo.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

import { fuentes, lineaDe, sinComentarios } from './codigo.js';
import { HOJA, MINIMO_TEXTO, componer, razon, variablesDe } from './contraste.js';

/**
 * Un color escrito a mano: `#abc`, `#aabbcc`, `#aabbccdd`, `rgb(...)` o `rgba(...)`.
 *
 * Los nombres de CSS (`white`, `red`) no se buscan: el cliente no usa ninguno, y una
 * expresión que cazara palabras daría por color cualquier texto que diga «white».
 */
const COLOR = /#[0-9a-fA-F]{3,8}\b|rgba?\([0-9.,\s]+\)/g;

/**
 * El cuerpo del `:root` se recorta antes de buscar.
 *
 * Es el único sitio de la aplicación donde un color literal está en su casa: la paleta es
 * precisamente la lista de los colores escritos una vez. Lo que esta guarda persigue es el
 * color escrito **en otro sitio**, donde nadie lo mide.
 */
function sinLaPaleta(css) {
  const raiz = /:root\s*\{[\s\S]*?\n\}/.exec(css);
  if (!raiz) throw new Error('No se encontró el bloque :root en index.css');
  return css.slice(0, raiz.index) + css.slice(raiz.index + raiz[0].length);
}

/** Los colores escritos a mano de un archivo, con la línea en la que están. */
function coloresDe(ruta) {
  const bruto = readFileSync(ruta, 'utf8');
  const limpio = sinComentarios(ruta.endsWith('index.css') ? sinLaPaleta(bruto) : bruto);
  const encontrados = [];
  for (const coincidencia of limpio.matchAll(COLOR)) {
    encontrados.push({ valor: coincidencia[0], linea: lineaDe(limpio, coincidencia.index) });
  }
  return encontrados;
}

/**
 * Los colores que NO salen de la paleta a propósito, por archivo y con su motivo.
 *
 * Cada entrada responde a una pregunta: «¿por qué este color no puede ser un token?». Si
 * la respuesta es «porque nadie lo ha movido todavía», no va aquí: va a la paleta.
 */
const ACEPTADOS = {
  'src/components/VistaPreviaDelPost.jsx': {
    porque: 'son los colores de LinkedIn, no los nuestros. La tarjeta imita la que se verá '
      + 'en la red para que quien publica vea de verdad lo que va a salir (§3.4), así que '
      + 'tematizarla con esta paleta sería el defecto: enseñaría una tarjeta que no existe',
    valores: ['#191919', '#666', '#555', '#b42318', '#7a4b00', '#ffffff', '#e0dfdc', '#0a66c2', '#fff'],
  },
  'src/components/qr.js': {
    porque: 'el negro y el blanco de un código QR son parte del código, no del tema. Un QR '
      + 'con los colores de la paleta no lo lee ninguna cámara, y el capítulo 38 ya pagó '
      + 'una vez el precio de un código impecable que ningún lector podía decodificar',
    valores: ['#ffffff', '#000000'],
  },
  'src/components/AltaDelSegundoFactor.jsx': {
    porque: 'el papel blanco de debajo del QR del segundo factor, por el mismo motivo: el '
      + 'SVG lo dibuja el servidor y necesita un fondo claro detrás para que se escanee',
    valores: ['#fff'],
  },
  'src/index.css': {
    porque: 'el mismo papel blanco, el de debajo del QR de la página de interés '
      + '(.interes-qr-dibujo). No es un token para que nadie lo tematice por error',
    valores: ['#ffffff'],
  },
};

describe('ningún color se escribe a mano', () => {
  const archivos = fuentes('src');
  const porArchivo = new Map(archivos.map((ruta) => [ruta, coloresDe(ruta)]));

  it('se leen de verdad los archivos, y la expresión encuentra colores', () => {
    // Sin esto, una ruta mal resuelta o una expresión rota dejarían las listas vacías y la
    // comprobación de abajo pasaría sin haber mirado nada. Es el mismo cuidado que en
    // `tokens.test.js` y en `clases.test.js`: la peor prueba no es la que falla, es la que
    // se aprueba a sí misma quedándose sin datos.
    expect(archivos.length).toBeGreaterThan(30);
    expect(archivos).toContain('src/index.css');
    const total = [...porArchivo.values()].reduce((suma, lista) => suma + lista.length, 0);
    expect(total).toBeGreaterThanOrEqual(12);
    // Y la paleta se recorta de verdad: si `sinLaPaleta` no funcionara, los cincuenta y
    // pico colores del `:root` aparecerían aquí y el inventario tendría que crecer.
    expect(porArchivo.get('src/index.css').length).toBeLessThan(5);
  });

  it('todos los que quedan están inventariados, con su motivo', () => {
    const sueltos = [];
    for (const [ruta, colores] of porArchivo) {
      const permitidos = ACEPTADOS[ruta] ? ACEPTADOS[ruta].valores : [];
      for (const { valor, linea } of colores) {
        if (permitidos.includes(valor)) continue;
        sueltos.push(`  ${ruta}:${linea} — ${valor}`);
      }
    }
    expect(
      sueltos,
      'Estos colores están escritos a mano y no pasan por la paleta, que es el único sitio '
      + 'donde el contraste se mide:\n'
      + `${sueltos.join('\n')}\n`
      + 'Si el color ya existe con un nombre, use ese nombre. Si hace falta uno nuevo, '
      + 'escríbalo en el :root y métalo en PARES. Y si de verdad no debe seguir esta paleta '
      + '—un QR, una tarjeta que imita otra red—, apúntelo en ACEPTADOS diciendo por qué.',
    ).toEqual([]);
  });

  it('el inventario no guarda colores que ya no están en el archivo', () => {
    // Un inventario que crece y nunca se poda deja de ser un inventario: pasa a ser una
    // lista de permisos. Si un color inventariado desaparece del archivo, la entrada sobra
    // y hay que borrarla.
    const fantasmas = [];
    for (const [ruta, { valores }] of Object.entries(ACEPTADOS)) {
      if (!porArchivo.has(ruta)) {
        fantasmas.push(`  ${ruta} — el archivo ya no existe o ya no se recorre`);
        continue;
      }
      const presentes = porArchivo.get(ruta).map((c) => c.valor);
      for (const valor of valores) {
        if (!presentes.includes(valor)) fantasmas.push(`  ${ruta} — ${valor} ya no está`);
      }
    }
    expect(fantasmas, `Sobran del inventario:\n${fantasmas.join('\n')}`).toEqual([]);
  });

  it('ni escondido en el respaldo de un var()', () => {
    // El caso que ninguna guarda miraba: tres sitios decían `var(--hot-text, #b42318)`. El
    // token existe, así que el respaldo no se aplica nunca y `tokens.test.js` no lo mira
    // —solo inventaría los respaldos de tokens que faltan—, de modo que ahí vivía el rojo
    // de un tema claro que nunca se escribió, invisible para todo.
    const escondidos = [];
    for (const ruta of archivos) {
      const limpio = sinComentarios(readFileSync(ruta, 'utf8'));
      for (const c of limpio.matchAll(/var\(\s*--[\w-]+\s*,\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))/g)) {
        escondidos.push(`  ${ruta}:${lineaDe(limpio, c.index)} — ${c[0]})`);
      }
    }
    expect(
      escondidos,
      'Un color dentro del respaldo de un var() no lo mide nadie: si el token existe no se '
      + 'aplica nunca, y si no existe se aplica sin haber pasado por la paleta.\n'
      + `${escondidos.join('\n')}`,
    ).toEqual([]);
  });
});

describe('el estado de error, que la hoja no dibujaba', () => {
  const variables = variablesDe(HOJA);

  it('un campo inválido se distingue de uno correcto', () => {
    // §6.4 punto 36. Y se dibuja sobre el atributo, no sobre una clase: así la hoja pinta
    // exactamente lo que el lector de pantalla anuncia, y no hay dos verdades sobre el
    // mismo campo. Con una clase habría que mantener las dos a mano, y se separarían el
    // primer día —de hecho ya estaban separadas: el atributo llevaba puesto en la página
    // pública desde el capítulo 34 y la hoja no lo miraba—.
    expect(HOJA).toMatch(/\.input-field\[aria-invalid='true'\]\s*\{/);
    const regla = /\.input-field\[aria-invalid='true'\]\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(regla).toContain('var(--border-error)');
  });

  it('y sigue distinguiéndose cuando se escribe en él', () => {
    // El borde rojo no cambia con el foco —el error no se va porque se esté escribiendo— y
    // el foco se señala con un aro añadido. Por qué tiene que ser añadido y no un cambio
    // de color está medido en contraste.test.js: ningún rojo llega a 3.0 por encima de este.
    const regla = /\.input-field\[aria-invalid='true'\]:focus\s*\{([\s\S]*?)\}/.exec(HOJA);
    expect(regla, 'desapareció la regla del campo inválido con foco').not.toBeNull();
    expect(regla[1]).toContain('var(--border-error)');
    expect(regla[1]).toMatch(/box-shadow:[^;]*var\(--border-focus\)/);
  });

  it('el aviso de una pantalla es una clase, no siete propiedades copiadas', () => {
    for (const clase of ['.alert', '.alert-error', '.alert-warn', '.alert-ok']) {
      expect(HOJA, `falta la regla de ${clase}`).toContain(`${clase} {`);
    }
    const error = /\.alert-error\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(error).toContain('var(--error-bg)');
    expect(error).toContain('var(--error-border)');
    expect(error).toContain('var(--error-text)');
  });

  it('y la usan las pantallas que tenían el aviso escrito en línea', () => {
    // Esto ata la clase a su uso. Sin esta prueba, alguien podría dejar la regla escrita y
    // volver a poner el estilo en línea en un componente, y las dos cosas estarían verdes.
    for (const archivo of [
      'LoginScreen', 'CambioDeContrasenaObligatorio', 'AltaDelSegundoFactor', 'NewLeadModal',
      'LeadDetailModal', 'Publicaciones',
    ]) {
      const codigo = readFileSync(`src/components/${archivo}.jsx`, 'utf8');
      expect(codigo, `${archivo} ya no usa la clase del aviso`).toContain('alert alert-error');
    }
    // El panel de administración usa el mismo aviso para el fallo y para el acierto, así que
    // elige la variante al pintar. Lo que no puede es volver a elegir `role="status"` para
    // un fallo: un error anunciado como estado espera su turno.
    const admin = readFileSync('src/components/AdminPanel.jsx', 'utf8');
    expect(admin).toContain("alert-error' : 'alert-ok'");
    expect(admin).toContain("role={error ? 'alert' : 'status'}");
  });

  it('el aviso respeta los saltos de línea que el mensaje trae', () => {
    // Los dos extremos de la misma cuerda, comprobados juntos: el servidor manda un 422 con
    // un renglón por campo, `parseApiError` los une con saltos de línea, y un salto de
    // línea en HTML no es un salto. Sin `white-space`, un 422 de tres campos salía en una
    // sola línea con los tres pegados. Si alguien quita el `join`, esta prueba lo dice; si
    // alguien quita el `white-space`, también.
    const regla = /\.alert\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(regla).toMatch(/white-space:\s*pre-line/);
    expect(readFileSync('src/services/api.js', 'utf8')).toMatch(/\.join\('\\n'\)/);
  });

  it('el rojo del aviso llega a 4.5, y el que había no llegaba', () => {
    // La medida que justifica el token nuevo, recalculada de la paleta. La segunda mitad es
    // la que importa dentro de un año: si alguien «simplifica» --error-text a
    // --danger-border —son dos rojos muy parecidos—, la pantalla vuelve a incumplir
    // §1.4.3, y esto lo dice en vez de dejarlo pasar.
    const peorFondo = componer(variables['--error-bg'], variables['--bg-surface-elevated']);
    expect(razon(variables['--error-text'], peorFondo)).toBeGreaterThanOrEqual(MINIMO_TEXTO);
    expect(razon(variables['--danger-border'], peorFondo)).toBeLessThan(MINIMO_TEXTO);
  });

  it('el rojo de una temperatura ya no pinta errores', () => {
    // --hot-text tenía dos oficios: el rojo de un prospecto caliente y el de un mensaje de
    // error. Eran dos, y solo uno tenía nombre. Las insignias y los scores siguen siendo
    // suyos; los avisos, no.
    const hot = /\.badge-hot\s*\{([\s\S]*?)\}/.exec(HOJA)[1];
    expect(hot).toContain('var(--hot-text)');
    for (const clase of ['form-error', 'interes-error']) {
      const regla = new RegExp(`\\.${clase}\\s*\\{([\\s\\S]*?)\\}`).exec(HOJA)[1];
      expect(regla, `.${clase} se pinta con la temperatura de un prospecto`).toContain('var(--error-text)');
      expect(regla).not.toContain('var(--hot-text)');
    }
  });
});
