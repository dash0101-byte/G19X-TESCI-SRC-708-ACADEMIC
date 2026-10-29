# Evidencia del trabajo — Sistema Inteligente de Lead Scoring

**Residente:** Rosales Castillo Sebastián · **No. de control:** 223107211 · **Empresa:** PluriOne S.A. de C.V. · **Corte:** 29/10/2026

Este documento reúne **la evidencia que se puede comprobar**: cada afirmación trae el comando o el archivo que la respalda. Las **doce capturas** de la demostración están en [`capturas/`](capturas/), tomadas sobre un clon limpio con la pila levantada (ver §5), y los **dos videos** —la instalación desde cero y el recorrido de la demostración— ya están grabados y entregados (§5).

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
| Historial de trabajo | 101 confirmaciones del 22-09 al 23-10-2026, **las 101 con línea de coautoría** (`git log`) |

## 5. Capturas y video de la demostración

**Las doce capturas que pedía este apartado ya están**, en
[`capturas/`](capturas/). Se tomaron por primera vez el **19 de octubre de 2026** sobre un
**clon limpio** del repositorio en la confirmación `5b28cde`, levantado siguiendo los cinco
pasos de «Cómo ejecutarlo desde cero» del README —sin un solo atajo— y recorriendo después
el [guion cronometrado](../Guion_Cronometrado_de_la_Demo.md).

**Y se rehicieron el 23 de octubre de 2026**, sobre el árbol de esta misma confirmación y
con las imágenes reconstruidas, por un motivo que no es cosmético: dos de las siete cuentas
de demostración llevaban el **nombre de personas reales del proyecto** —el líder de proyecto
y el asesor empresarial—, y ese nombre salía en la barra superior de casi todas las
pantallas. Una cosa es acreditar a alguien, que es lo correcto y se sigue haciendo en la
portada de este entregable, y otra darle de alta una cuenta inventada con su rol y su hash
de contraseña. Las cuentas pasaron a nombres inventados y las capturas se tomaron otra vez.

| # | Captura | Qué se ve | Archivo | Tamaño |
| :-: | :--- | :--- | :--- | :--- |
| 1 | Inicio de sesión | Pantalla de entrada | [`01_inicio_de_sesion.png`](capturas/01_inicio_de_sesion.png) | 2880×1800 |
| 2 | Pestaña «Hoy» | Tareas con su motivo | [`02_pestana_hoy.png`](capturas/02_pestana_hoy.png) | 2880×1800 |
| 3 | Dashboard | KPIs, embudo y contador «sin asesor» | [`03_tablero_kpis_embudo.png`](capturas/03_tablero_kpis_embudo.png) | 2880×4404 |
| 4 | Prospectos | Matriz con categorías HOT/WARM/COLD | [`04_prospectos_hot_warm_cold.png`](capturas/04_prospectos_hot_warm_cold.png) | 2880×3098 |
| 5 | Ficha 360° | Puntuación, explicación y tarjeta «Llegó por» | [`05_ficha_360_puntuacion_y_llego_por.png`](capturas/05_ficha_360_puntuacion_y_llego_por.png) | 2880×3262 |
| 6 | Simulador | Deslizadores y resultado | [`06_simulador.png`](capturas/06_simulador.png) | 2880×1800 |
| 7 | Publicaciones | Enlace propio, textos por red y código QR | [`07_publicacion_redes_y_qr.png`](capturas/07_publicacion_redes_y_qr.png) | 2880×2774 |
| 8 | Informe de publicación | Fila por red (WhatsApp / LinkedIn) | [`08_informe_de_publicacion_por_red.png`](capturas/08_informe_de_publicacion_por_red.png) | 2880×2242 |
| 9 | Página pública de interés | Formulario sin texto libre | [`09_pagina_publica_de_interes.png`](capturas/09_pagina_publica_de_interes.png) | 2880×1800 |
| 10 | Cierre de trato | Formulario con motivo de lista cerrada | [`10_cierre_de_trato.png`](capturas/10_cierre_de_trato.png) | 2880×3262 |
| 11 | Desenlaces | Tabla por motivo y contador de reentrenamiento | [`11_desenlaces_por_motivo.png`](capturas/11_desenlaces_por_motivo.png) | 2880×2622 |
| 12 | `/health` en el navegador | `"ml_model_loaded": true` | [`12_health_ml_model_loaded.png`](capturas/12_health_ml_model_loaded.png) | 2880×1800 |

**Cinco de las doce no existían al sembrar la base.** Las pantallas de publicaciones,
informe, página pública, cierre y desenlaces están vacías hasta que alguien crea una
publicación, la reparte, un interesado deja sus datos y el trato se cierra. Así que las
capturas no son una sesión de pantallazos sobre datos sembrados: son el recorrido de la
demostración, en este orden —crear la publicación, repartirla por WhatsApp y LinkedIn,
llegar por el enlace público, puntuar la ficha recién creada, cerrar el trato con un motivo
de la lista cerrada y mirar el desenlace—.

**Cada captura espera una condición antes de dispararse**, y si no se cumple no se toma
ninguna: la 5 exige que la ficha enseñe «Llegó por», la 12 exige que `/health` conteste
literalmente `"ml_model_loaded": true`. Una captura de una pantalla a medio dibujar parece
una prueba y no lo es.

**Lo que estas capturas prueban y lo que no.** Prueban que el sistema arranca desde un clon
limpio y que las doce pantallas hacen lo que la documentación dice. **No** prueban quién
levantó la pila: eso lo comprueba quien evalúa repitiendo los cinco pasos del README, que es
para lo que están escritos y cronometrados.

> **Datos de la demostración:** todos sintéticos, generados por `backend/scripts/seed_data.py`
> y por el propio recorrido. No hay datos reales de PluriOne ni credenciales a la vista.

### Los dos videos

**Están grabados y entregados**, con la voz del residente, y responden a las dos cosas
que las capturas no pueden probar: que la pila se levanta desde un clon limpio siguiendo
el README, y que la demostración se recorre entera de principio a fin.

| Video | Qué enseña | Dura | Pesa | Dónde está |
| :--- | :--- | :---: | :---: | :--- |
| **Instalación limpia** | Los cinco pasos de «Cómo ejecutarlo desde cero» sobre un clon recién hecho, cronometrados con `Get-Date` al principio y al final, y el `"ml_model_loaded": true` del cierre | 18:12 | 35,4 MB | [Plataforma, documento 372](https://todoacademy.net/documentos/version/372) |
| **Funcionamiento** | El recorrido de la demostración: crear la publicación, repartirla por LinkedIn y WhatsApp, llegar por el enlace público, la ficha puntuada, el reparto, el cierre con motivo y los desenlaces | 7:06 | 36,2 MB | [Plataforma, documento 378](https://todoacademy.net/documentos/version/378) |

**Lo único que se les hizo después de grabar** fue subir el volumen —el micrófono grabó a −58,8 dB de media, unos treinta y cinco por debajo de lo normal— y, en el de la demostración, acelerarlo a **1,25×** para acercarlo al tiempo pedido. Ni un corte, ni un montaje, ni una toma pegada a otra: lo que se ve es lo que pasó, en el orden en que pasó.

Los dos enlaces son de la plataforma de seguimiento y piden sesión. Los archivos viven además en `media/` del árbol de trabajo, que está en `.gitignore`: GitHub rechaza archivos de más de 100 MB y un repositorio no es sitio para dos videos de 36 MB.
