// ============================================================================
// Lo que le faltaba a las tres ventanas modales del panel
// ============================================================================
//
// La ficha 360, el alta de prospecto y la de sesión se dibujaban con un `<div>` encima de
// la pantalla. Se veían bien y se cerraban con el ratón, y eso bastaba para no notar que
// para el teclado y para un lector de pantalla **no eran una ventana**: eran un trozo más
// del documento, dibujado por casualidad delante del resto.
//
// Lo que eso significaba, punto por punto:
//
// * **El lector de pantalla no decía que se hubiera abierto nada.** Sin `role="dialog"` no
//   hay ventana que anunciar; aparecía contenido nuevo en medio del documento y ya.
// * **El foco se quedaba detrás.** Al abrir la ficha, el foco seguía en el botón de la fila
//   de la tabla. Quien navega con el tabulador tenía que recorrer la tabla entera —y el
//   menú, y el pie— para llegar a una ventana que visualmente estaba delante de todo.
// * **El tabulador salía de la ventana sin avisar.** Al llegar al último botón, el
//   siguiente `Tab` llevaba a la página de debajo: una página tapada por el velo, donde
//   el foco es invisible. A partir de ahí no se sabe dónde se está.
// * **`Escape` no cerraba.** Con el ratón se cierra pulsando fuera; sin ratón no había
//   forma de cerrarla salvo encontrar la «×».
// * **Al cerrar, el foco se perdía.** Volvía al `<body>`, así que el siguiente `Tab`
//   empezaba desde el principio de la página en vez de desde donde se abrió la ventana.
//
// `Campana` ya lo hacía a medias —tiene `role="dialog"` y su nombre— desde el capítulo 28,
// así que el patrón estaba en el proyecto y solo se había aplicado en un sitio. Esto lo
// escribe una vez y lo usan las tres.
//
// Por qué un hook y no un componente que envuelva
// -----------------------------------------------
// Un componente `<Modal>` obligaría a mover el marcado de las tres ventanas dentro de él, y
// las tres tienen su propio `.modal-content` con sus estilos y su cabecera. El hook da las
// propiedades y no toca la estructura: cada ventana sigue siendo la suya y solo gana lo que
// le faltaba.

import { useCallback, useEffect, useRef } from 'react';

// Lo que el navegador considera enfocable, en el orden del documento. `:not([disabled])`
// importa: un botón deshabilitado sigue estando en el DOM y meterlo en el ciclo dejaría el
// foco atrapado en algo que no responde.
const ENFOCABLES = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'details > summary',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

function enfocablesDe(contenedor) {
  if (!contenedor) return [];
  // `offsetParent` es nulo para lo que está oculto con `display: none`, pero en `jsdom` es
  // nulo SIEMPRE, porque no hay maquetación. Filtrar por él dejaría la lista vacía en las
  // pruebas y el ciclo no se podría comprobar. Se filtra por lo que sí es fiable en los
  // dos sitios: `hidden`, `aria-hidden` y el campo trampa, que lleva `tabindex="-1"` y ya
  // queda fuera por el selector.
  return Array.from(contenedor.querySelectorAll(ENFOCABLES)).filter(
    (nodo) => !nodo.hidden && nodo.closest('[aria-hidden="true"]') === null,
  );
}

/**
 * Convierte un `<div>` flotante en una ventana modal de verdad.
 *
 * @param {() => void} alCerrar  Lo que hay que hacer con `Escape`. Es la misma función que
 *                               ya usaba el clic en el velo: cerrar es cerrar.
 * @param {string} etiquetadoPor `id` del encabezado que da nombre a la ventana. El lector
 *                               de pantalla lo lee al abrirla, y es lo que distingue «se
 *                               abrió algo» de «se abrió la ficha de Ana Ruiz».
 * @returns Las propiedades que hay que extender sobre el `.modal-content`.
 */
export function useVentanaModal({ alCerrar, etiquetadoPor }) {
  const contenedor = useRef(null);
  // Dónde estaba el foco cuando se abrió. Se guarda en un `ref` y no en el estado porque
  // cambiarlo no tiene que repintar nada.
  const focoPrevio = useRef(null);

  useEffect(() => {
    focoPrevio.current = document.activeElement;
    // Al primer elemento enfocable de la ventana, y si no hay ninguno, a la ventana misma
    // —que lleva `tabIndex={-1}` justo para poder recibirlo—. Así el lector de pantalla
    // anuncia el nombre del diálogo y el siguiente `Tab` sale de dentro, no del principio
    // de la página.
    const dentro = enfocablesDe(contenedor.current);
    (dentro[0] || contenedor.current)?.focus();

    return () => {
      // Al cerrar, el foco vuelve exactamente a donde estaba. Sin esto se queda en el
      // `<body>` y el siguiente `Tab` empieza a recorrer la página desde arriba, que para
      // quien no ve la pantalla equivale a perder el sitio.
      const anterior = focoPrevio.current;
      if (anterior && typeof anterior.focus === 'function' && document.contains(anterior)) {
        anterior.focus();
      }
    };
  }, []);

  const alPulsarTecla = useCallback(
    (evento) => {
      if (evento.key === 'Escape') {
        evento.stopPropagation();
        alCerrar();
        return;
      }
      if (evento.key !== 'Tab') return;

      const dentro = enfocablesDe(contenedor.current);
      if (!dentro.length) {
        // Una ventana sin nada enfocable: el `Tab` no tiene a dónde ir dentro, y dejarlo
        // salir llevaría el foco a una página tapada. Se queda donde está.
        evento.preventDefault();
        return;
      }
      const primero = dentro[0];
      const ultimo = dentro[dentro.length - 1];
      const activo = document.activeElement;

      // El ciclo. Solo se interviene en los dos extremos: en medio, el tabulador del
      // navegador ya hace lo correcto y adelantarse a él rompería el orden del documento.
      if (evento.shiftKey && (activo === primero || activo === contenedor.current)) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && activo === ultimo) {
        evento.preventDefault();
        primero.focus();
      }
    },
    [alCerrar],
  );

  return {
    ref: contenedor,
    role: 'dialog',
    // Le dice al lector de pantalla que mientras esto esté abierto, lo de debajo no existe.
    // Es la mitad que falta del atrapado del foco: una cosa cierra el paso al tabulador y
    // la otra, a la navegación por encabezados y por regiones del propio lector.
    'aria-modal': true,
    'aria-labelledby': etiquetadoPor,
    // Sin esto, una ventana cuyo primer elemento enfocable todavía no existe —porque está
    // cargando— no podría recibir el foco, y el anuncio de apertura se perdería.
    tabIndex: -1,
    onKeyDown: alPulsarTecla,
  };
}
