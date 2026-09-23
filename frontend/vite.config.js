import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Nombres FIJOS para la entrada de la aplicación y su hoja de estilos.
        //
        // Desde el capítulo 27 el HTML de `/interes/{slug}` lo sirve el backend, con las
        // etiquetas de la tarjeta social dentro. Ese HTML tiene que nombrar estos dos
        // archivos, y el backend no puede conocer la huella que el compilador les pondría.
        // El resto —los trozos que se cargan bajo demanda, las fuentes, las imágenes—
        // conserva su huella y su caché de un año.
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: (info) =>
          info.names?.some((n) => n.endsWith('.css'))
            ? 'assets/app.css'
            : 'assets/[name]-[hash][extname]',
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    // `jsdom` da un DOM real: los componentes se montan y se consultan como los ve una
    // persona. `happy-dom` es más rápido pero no implementa lo suficiente de
    // `HTMLFormElement` ni de los eventos de teclado para lo que hace el simulador.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/pruebas/preparar.js'],
    // Sin esto, un `expect` dentro de un `waitFor` que nunca se cumple deja la suite
    // colgada hasta el tope global en vez de señalar la prueba concreta.
    testTimeout: 10000,
    include: ['src/**/*.test.{js,jsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: './coverage',
      // Se mide lo que esta fase se compromete a cubrir. Incluir aquí los componentes
      // sin lógica —tarjetas de KPI, barra de navegación— rebajaría el suelo hasta
      // volverlo decorativo: un número que sube al añadir archivos triviales no dice
      // nada sobre si el código que decide cosas está probado.
      include: [
        'src/services/api.js',
        'src/components/LeadsTable.jsx',
        'src/components/ScoringSimulator.jsx',
        'src/components/SessionModal.jsx',
        'src/components/CambioDeContrasenaObligatorio.jsx',
      ],
      // El suelo va justo por debajo de lo medido (95 / 88 / 97 / 97), no en un número
      // redondo y cómodo: un suelo del 80 % con la cobertura real en el 95 % deja pasar
      // una regresión de quince puntos sin decir nada, que es tanto como no tenerlo.
      // Cuando la cobertura suba de verdad, este suelo sube con ella.
      thresholds: {
        statements: 92,
        branches: 86,
        functions: 94,
        lines: 94,
      },
    },
  },
});
