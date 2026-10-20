# Evidencia del trabajo — Sistema Inteligente de Lead Scoring

**Residente:** Rosales Castillo Sebastián · **No. de control:** 223107211 · **Empresa:** PluriOne S.A. de C.V. · **Corte:** 13/10/2026

Este documento reúne **la evidencia que se puede comprobar**: cada afirmación trae el comando o el archivo que la respalda. Las capturas y el video de la demostración **no están incluidos aquí** porque requieren la pila en ejecución (ver §5).

---

## 1. Calidad del código

| Evidencia | Cifra | Cómo comprobarla |
| :--- | :--- | :--- |
| Pruebas del servidor | 2093 pasan, 2 omitidas | `python -m pytest backend/tests -q` |
| Cobertura del servidor | 99,11 % con ramas (99,37 % sentencias · 97,88 % ramas) | `python -m pytest backend/tests -q --cov=backend/app --cov-fail-under=99.1` |
| Pruebas del cliente | 748 en 45 archivos; cobertura 96,65 / 91,75 / 98,52 / 98,68 % | `cd frontend && npx vitest run` |
| Análisis estático | `ruff`, `eslint` (34 reglas de accesibilidad) y `npm run build` sin avisos | `ruff check backend/ scripts/` |
| Integración continua | 10 trabajos, 61 controles de configuración peligrosa, 7 guardas de propiedades; **verde entero desde el 09-10-2026** | `python scripts/guarda_del_ci.py` |
| Accesibilidad | WCAG 2.1 AA en las nueve pantallas, medido con `axe-core` | Suite del cliente |

## 2. Modelo de Machine Learning

Fuente: `ml_pipeline/models/metrics.json` (datos **sintéticos**, 3000 filas, semilla 42).

| Métrica | Valor |
| :--- | :--- |
| ROC-AUC | 0,9469 · IC 95 % [0,9275, 0,9635] (2000 remuestreos) |
| Línea base: azar | 0,5000 |
| Línea base: una sola columna (`days_since_last_activity`) | 0,9053 |
| Línea base: heurístico ICP | 0,8950 |
| **Aporte sobre el heurístico** | **+0,0519** · IC 95 % [+0,0296, +0,0761] |
| F1 · exactitud · Brier | 0,8405 · 0,8767 · 0,0872 |
| Reproducibilidad | Artefacto idéntico byte a byte entre el entrenamiento del 16-09 y el del 07-10 (SHA-256 `98ed8bd1…9d2a63`) |

El ROC-AUC verifica que el pipeline está íntegro, no el rendimiento comercial; la cifra defendible es el aporte sobre el heurístico.

## 3. Funcionamiento de la demostración

Fuente: `docs/Guion_Cronometrado_de_la_Demo.md` y `scripts/ensayo_de_la_demo.py` (recorre los nueve pasos contra la API real y los cronometra).

| Paso | Qué ocurre | Servidor |
| :-: | :--- | ---: |
| 1 | Marketing crea una publicación y el servidor le da su enlace | 399 ms |
| 2 | Texto y enlace propio por red | 40 ms |
| 3 | La persona abre el enlace de WhatsApp y envía sus datos | 286 ms |
| 4 | Ficha creada, puntuada y atribuida | 2 ms |
| 5 | Contador «sin asesor» y reasignación | 248 ms |
| 6 | Bandeja «Hoy», ficha 360° y cierre de tarea | 361 ms |
| 7 | Comparativa e informe por red | 197 ms |
| 8 | Cierre del trato con su motivo | 183 ms |
| 9 | Panel de desenlaces y contador | 103 ms |
| | **Todo el recorrido** | **1 819 ms** |

Además, el **06-10-2026** se comprobó de extremo a extremo con un teléfono real: un decodificador independiente (`jsQR 1.4.0`) leyó el QR del panel sin discrepancias entre los 2025 módulos pintados y la geometría del SVG; el teléfono lo escaneó, abrió el formulario por internet y el envío entró como prospecto ya repartido, con su tarea de primer contacto.

## 4. Documentación entregada

| Documento | Ubicación |
| :--- | :--- |
| PRD · MVP | `docs/entregables_plataforma/PRD.md` · `MVP.md` |
| Manual de usuario · Manual técnico · Guía de instalación | `docs/entregables_plataforma/` |
| Documento técnico · Bitácora | `docs/entregables_plataforma/Documento_Tecnico.md` · `Bitacora.md` |
| 44 reportes técnicos y memoria compilada | `docs/reportes/` · `docs/Memoria_Tecnica_Final_Lead_Scoring.md` |
| Guía de defensa (28 preguntas con respuesta) | `docs/GUIA_DEFENSA_ORAL.md` |
| Historial de trabajo | 87 confirmaciones del 22-09 al 13-10-2026 (`git log`) |

## 5. Capturas y video: qué falta y cómo obtenerlo

Docker Desktop no estaba en ejecución al generar este documento, por lo que **no hay capturas ni video**. Para producirlos:

1. Levante la pila (ver [Guía de instalación](Guia_de_Instalacion.md)).
2. Siga el [guion cronometrado](../Guion_Cronometrado_de_la_Demo.md) y capture estas pantallas, ya con sesión iniciada:

| # | Captura | Qué debe verse |
| :-: | :--- | :--- |
| 1 | Inicio de sesión | Pantalla de entrada |
| 2 | Pestaña «Hoy» | Tareas con su motivo |
| 3 | Dashboard | KPIs, embudo y contador «sin asesor» en cero |
| 4 | Prospectos | Matriz con categorías HOT/WARM/COLD |
| 5 | Ficha 360° | Puntuación, explicación y tarjeta «Llegó por» |
| 6 | Simulador | Deslizadores y resultado |
| 7 | Publicaciones | Enlace propio, textos por red y código QR |
| 8 | Informe de publicación | Fila por red (WhatsApp / LinkedIn) |
| 9 | Página pública de interés | Formulario sin texto libre |
| 10 | Cierre de trato | Formulario con motivo de lista cerrada |
| 11 | Desenlaces | Tabla por motivo y contador de reentrenamiento |
| 12 | `/health` en el navegador | `"ml_model_loaded": true` |

3. Para el video, grabe el recorrido de 4 min 30 s de la demostración (nueve pasos).

> **Datos de la demostración:** todos sintéticos. No capture pantallas con datos reales de PluriOne ni con credenciales visibles.
