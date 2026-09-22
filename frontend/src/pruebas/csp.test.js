// ============================================================================
// Que la política de seguridad y lo que la página pide digan lo mismo (N-7)
// ============================================================================
//
// El problema que cierra esta prueba no era que faltara la CSP: la CSP estaba, y era
// estricta. Era que la página pedía cosas que la CSP prohibía —tres familias de
// `fonts.googleapis.com` con `style-src 'self'`— y NADA fallaba: el navegador bloqueaba
// la hoja, la aplicación caía a las fuentes del sistema y el único síntoma era que en
// producción se veía distinta que en `npm run dev`. Ni el build, ni las pruebas, ni el
// pipeline decían una palabra.
//
// Así que lo que se comprueba no es que exista la política, sino que la política y el
// contenido servido no se contradigan. Esto es la mitad estática; la otra mitad la hace
// el pipeline, que levanta el nginx de verdad, descarga la página y comprueba que cada
// recurso que pide llega con 200 (paso «La CSP admite todo lo que la página pide»).

import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const RAIZ = path.resolve(import.meta.dirname, '../..');
const leer = (relativa) => fs.readFileSync(path.join(RAIZ, relativa), 'utf8');

/** Extrae la CSP del fragmento de cabeceras de nginx como {directiva: [orígenes]}. */
function politica() {
  const conf = leer('security-headers.conf');
  // Solo las directivas: la cabecera del archivo explica la política nombrando cada
  // origen, así que leer el texto completo daría una comprobación que su propio
  // comentario satisface. Es el mismo error que apareció tres veces en fases
  // anteriores; aquí se descarta la prosa antes de mirar.
  const directivas = conf
    .split('\n')
    .filter((linea) => !linea.trimStart().startsWith('#'))
    .join('\n');

  const encontrada = directivas.match(/add_header Content-Security-Policy\s+"([^"]+)"/);
  expect(encontrada, 'no hay Content-Security-Policy en las directivas').not.toBeNull();

  return Object.fromEntries(
    encontrada[1]
      .split(';')
      .map((trozo) => trozo.trim())
      .filter(Boolean)
      .map((trozo) => {
        const [nombre, ...origenes] = trozo.split(/\s+/);
        return [nombre, origenes];
      }),
  );
}

/** Todas las URL absolutas que aparecen en un texto y de las que el navegador descarga algo. */
function origenesExternos(texto) {
  // Se descartan primero los `data:` —el favicon es un SVG en línea— porque dentro
  // llevan `xmlns='http://www.w3.org/2000/svg'`, que es un identificador de espacio de
  // nombres XML y no una descarga: el navegador nunca pide esa dirección. Contarla como
  // origen externo haría fallar la prueba sobre un árbol correcto, y una prueba que
  // siempre falla acaba desactivada.
  const sinDatos = texto.replace(/data:[^"')\s]+/g, '');
  const encontrados = sinDatos.match(/https?:\/\/[^\s"'()<>]+/g) || [];
  return [...new Set(encontrados.map((u) => new URL(u).origin))].filter(
    (origen) => origen !== 'http://www.w3.org',
  );
}

describe('la página no pide nada a terceros', () => {
  it('index.html no enlaza hojas de estilo ni scripts de otro origen', () => {
    const html = leer('index.html');
    // Los comentarios explican que ANTES había enlaces a Google, y nombran el dominio.
    const marcado = html.replace(/<!--[\s\S]*?-->/g, '');

    expect(origenesExternos(marcado)).toEqual([]);
    expect(marcado).not.toMatch(/rel=["']preconnect["']/);
  });

  it('el CSS no importa nada de fuera', () => {
    for (const archivo of ['src/index.css', 'src/fuentes.css']) {
      const css = leer(archivo).replace(/\/\*[\s\S]*?\*\//g, '');
      expect(origenesExternos(css), `${archivo} enlaza a un tercero`).toEqual([]);
    }
  });

  it('las fuentes se declaran contra archivos del paquete, no contra una URL', () => {
    const css = leer('src/fuentes.css');
    const caras = css.match(/@font-face/g) || [];
    expect(caras.length).toBeGreaterThanOrEqual(2);
    // `.woff2` locales: el empaquetador los copia a /assets con huella en el nombre.
    expect(css).toMatch(/url\('@fontsource-variable\/[^']+\.woff2'\)/);
  });

  it('las familias que el CSS pide son las que se declaran', () => {
    const variables = leer('src/index.css');
    const fuentes = leer('src/fuentes.css');

    const pedidas = [...variables.matchAll(/--font-(?:sans|mono):\s*'([^']+)'/g)].map((m) => m[1]);
    expect(pedidas.length).toBe(2);

    for (const familia of pedidas) {
      // Antes, `--font-sans` pedía 'Inter' y no se descargaba en ningún sitio: la
      // primera familia de la lista no existía y el navegador pasaba a la de reserva
      // sin decir nada. Descargar tres familias y usar cero es el mismo descuido.
      expect(fuentes, `nadie declara la familia ${familia}`).toContain(`font-family: '${familia}'`);
    }
  });

  it('no queda ninguna familia declarada que nadie use', () => {
    const variables = leer('src/index.css');
    const declaradas = [
      ...new Set([...leer('src/fuentes.css').matchAll(/font-family: '([^']+)'/g)].map((m) => m[1])),
    ];

    for (const familia of declaradas) {
      expect(variables, `se descarga ${familia} y no la usa nadie`).toContain(`'${familia}'`);
    }
  });
});

describe('la política que sirve nginx', () => {
  it('no admite ningún origen externo en ninguna directiva', () => {
    for (const [directiva, origenes] of Object.entries(politica())) {
      for (const origen of origenes) {
        expect(
          origen.startsWith('http'),
          `${directiva} admite el origen externo ${origen}`,
        ).toBe(false);
      }
    }
  });

  it('las fuentes solo pueden venir del propio origen', () => {
    // Con las fuentes autoalojadas ya no hay ninguna incrustada, así que `data:` sobra.
    // Dejarlo abierto no rompe nada, pero una política que permite más de lo que hace
    // falta deja de servir para detectar que algo cambió.
    expect(politica()['font-src']).toEqual(["'self'"]);
  });

  it('los scripts solo pueden venir del propio origen, sin inline ni eval', () => {
    const script = politica()['script-src'];
    expect(script).toEqual(["'self'"]);
    expect(script).not.toContain("'unsafe-inline'");
    expect(script).not.toContain("'unsafe-eval'");
  });

  it('sigue prohibiendo que la aplicación se embeba en un iframe ajeno', () => {
    expect(politica()['frame-ancestors']).toEqual(["'none'"]);
  });

  it('las conexiones de la aplicación no pueden salir a otro servidor', () => {
    // `connect-src 'self'` es lo que impide que un XSS mande la cartera de prospectos
    // a un servidor de fuera con un solo `fetch`.
    expect(politica()['connect-src']).toEqual(["'self'"]);
  });
});
