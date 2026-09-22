// ============================================================================
// ESLint — configuración plana (ESLint 9)
// ============================================================================
//
// El backend tiene `ruff` desde la Fase 1 y el cliente no tenía nada: los mismos
// descuidos que allí fallan el pipeline aquí no los veía nadie. Esto lo iguala.
//
// La regla que justifica por sí sola instalar esto es `react-hooks/exhaustive-deps`.
// Un efecto con la lista de dependencias incompleta no rompe la pantalla: se queda
// leyendo un valor viejo y nadie se entera hasta que un dato no cuadra. Es
// exactamente la familia del defecto que la Fase 11 encontró en el simulador —una
// petición vieja pisando a la nueva—, y un `linter` la ve sin ejecutar nada.

import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [
  {
    // Lo generado no se revisa: `dist/` es salida del compilador y `coverage/` del
    // medidor. Analizarlos solo produce ruido sobre código que nadie escribió.
    ignores: ['dist/**', 'coverage/**', 'node_modules/**'],
  },

  js.configs.recommended,

  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    plugins: {
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...reactHooks.configs.flat.recommended.rules,

      // Con el JSX transform automático de Vite, `React` no hace falta en el ámbito y
      // los componentes no tienen que declarar `propTypes` en un proyecto de este
      // tamaño: exigirlo aquí solo produciría ruido sin encontrar defectos.
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',

      // Las tres que sí encuentran cosas:
      //  - `exhaustive-deps` como ERROR, no aviso. Como aviso se acumula y se ignora.
      'react-hooks/exhaustive-deps': 'error',
      //  - una variable que se asigna y no se usa suele ser una línea que se quedó a
      //    medias. Se admite el prefijo `_` para lo deliberado.
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      //  - `console.log` olvidado en producción. `warn` y `error` sí se dejan pasar.
      'no-console': ['error', { allow: ['warn', 'error'] }],

      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      // Accesibilidad: una etiqueta que no está asociada a su control.
      //
      // Se entra con una sola regla del plugin, no con su `recommended` entero. El
      // conjunto completo señala además cosas de otras familias (roles ARIA, orden de
      // foco, texto alternativo) que no se han revisado todavía; meterlas de golpe
      // llenaría la salida de errores ajenos a lo que aquí se arregló, y eso es
      // exactamente cómo se aprende a ignorar al `linter`.
      //
      // Esta sí se acaba de pagar a mano: sin ella, un lector de pantalla anunciaba
      // «cuadro de texto» sin decir de qué campo, y pulsar sobre el texto de la
      // etiqueta no llevaba el foco al campo. `nesting` cubre las casillas que ya
      // envuelven su `input`; `htmlFor` cubre el resto.
      'jsx-a11y/label-has-associated-control': ['error', {
        assert: 'either',
      }],

      // APAGADA A PROPÓSITO, y conviene saber por qué.
      //
      // `set-state-in-effect` viene con el plugin 7 y persigue el patrón «cargar datos en
      // un efecto y guardarlos en el estado». Señala cinco sitios: los tres cargadores de
      // `App.jsx`, el de `AdminPanel` y la sincronización de `lead` en `LeadDetailModal`.
      // Ninguno es un error: son la forma en que esta aplicación entera obtiene sus
      // datos. Cumplirla de verdad significa mover la carga fuera del render —una
      // biblioteca de datos, o estado derivado en vez de copiado—, que es un rediseño del
      // flujo, no un arreglo de estilo, y no es lo que esta fase se comprometió a hacer.
      //
      // Se apaga entera en vez de bajarla a `warn` porque un aviso permanente que nadie
      // va a atender acaba enseñando a ignorar la salida del `linter`, y entonces
      // tampoco se ven los avisos que sí importan. Cuando se aborde ese rediseño, lo
      // primero es volver a poner esta línea en 'error' y dejar que enumere el trabajo.
      'react-hooks/set-state-in-effect': 'off',
    },
  },

  {
    // Las pruebas viven en el navegador simulado pero usan las globales de Vitest.
    files: ['**/*.test.{js,jsx}', 'src/pruebas/**'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
      },
    },
    rules: {
      // Una prueba puede querer imprimir mientras se depura un fallo.
      'no-console': 'off',
    },
  },

  {
    // Los archivos de configuración corren en Node, no en el navegador.
    files: ['*.config.js'],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
];
