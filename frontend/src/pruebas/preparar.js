// ============================================================================
// Preparación común de las pruebas del cliente
// ============================================================================
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, vi } from 'vitest';

beforeEach(() => {
  // `fetch` se sustituye entero en cada prueba. Dejar el real disponible haría que un
  // descuido —una ruta sin simular— saliera a la red de verdad desde la suite: pasaría
  // en el portátil de quien tiene el backend levantado y fallaría en CI, que es la peor
  // clase de prueba. Aquí cualquier petición no prevista falla en el acto y dice cuál.
  globalThis.fetch = vi.fn(async (url) => {
    throw new Error(`Petición no simulada en la prueba: ${url}`);
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
