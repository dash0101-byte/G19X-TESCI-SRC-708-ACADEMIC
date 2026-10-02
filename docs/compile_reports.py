#!/usr/bin/env python3
# ==============================================================================
# COMPILADOR DE MEMORIA TÉCNICA INSTITUCIONAL - PLURIONE S.A. DE C.V.
# ==============================================================================
# Consolida los Reportes Técnicos de Estadía Profesional con Portada Formal,
# Aviso Legal de Confidencialidad e Índice General Numerado.
# ==============================================================================
import os
import re
import sys

# Asegurar codificación UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

REPORTES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "reportes"))
OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "Memoria_Tecnica_Final_Lead_Scoring.md"))

REPORT_FILES = [
    ("Reporte_01_Deteccion_de_Necesidades_y_Requerimientos.md", "Capítulo 1: Detección de Necesidades y Especificación de Requerimientos"),
    ("Reporte_02_Propuesta_Tecnica_y_Estrategia_de_Lead_Scoring.md", "Capítulo 2: Propuesta Técnica y Estrategia de Lead Scoring Híbrido"),
    ("Reporte_03_Diseno_de_Arquitectura_Integral_y_Modelo_de_Datos.md", "Capítulo 3: Diseño de Arquitectura Integral, Clean Architecture y Modelo de Datos"),
    ("Reporte_04_Planificacion_Operativa_y_Gestion_Scrum_del_Proyecto.md", "Capítulo 4: Planificación Operativa y Gestión Ágil (Scrum) del Proyecto"),
    ("Reporte_05_Desarrollo_del_Pipeline_de_Machine_Learning_y_Adaptadores_Azure_Local.md", "Capítulo 5: Pipeline de Machine Learning y Adaptadores Azure/Local"),
    ("Reporte_06_Core_Backend_FastAPI_Ingesta_CRM_y_Reglas_Dinamicas.md", "Capítulo 6: Core Backend FastAPI, Ingesta CRM y Reglas Dinámicas de Scoring"),
    ("Reporte_07_Interfaz_de_Usuario_React_y_Visualizacion_Analitica.md", "Capítulo 7: Interfaz de Usuario React.js, Dashboards y Visualización Analítica"),
    ("Reporte_08_Suite_de_Pruebas_Automatizadas_y_QA_de_Precision.md", "Capítulo 8: Suite de Pruebas Automatizadas y Aseguramiento de Calidad (QA)"),
    ("Reporte_09_Contenerizacion_CI_CD_y_Simulacion_de_Seguridad_RBAC.md", "Capítulo 9: Contenerización Docker, CI/CD y Simulación de Seguridad RBAC"),
    ("Reporte_10_Manual_Tecnico_Plan_de_Mantenimiento_y_Cierre_de_Estadia.md", "Capítulo 10: Manual Técnico, Plan de Soporte Multinivel y Cierre de Estadía"),
    ("Reporte_11_Auditoria_Endurecimiento_de_Seguridad_y_Rendimiento.md", "Capítulo 11: Auditoría Técnica, Endurecimiento de Seguridad y Optimización de Rendimiento"),
    ("Reporte_12_Gobierno_de_Datos_Migraciones_y_Validez_del_Modelo.md", "Capítulo 12: Gobierno de Datos, Migraciones de Esquema y Validez del Modelo"),
    ("Reporte_13_Superficie_de_Ataque_Residual_y_Observabilidad_del_Modelo.md", "Capítulo 13: Superficie de Ataque Residual y Observabilidad del Modelo"),
    ("Reporte_14_Sesiones_Verificables_Ingesta_Idempotente_y_Bitacora_de_Auditoria.md", "Capítulo 14: Sesiones Verificables, Ingesta Idempotente y Bitácora de Auditoría"),
    ("Reporte_15_Identidad_Unificada_Autorizacion_por_Objeto_y_Gestion_de_Cuentas.md", "Capítulo 15: Identidad Unificada, Autorización por Objeto y Gestión de Cuentas"),
    ("Reporte_16_Fiabilidad_Operativa_Arriendos_Observabilidad_y_Respaldos.md", "Capítulo 16: Fiabilidad Operativa — Arriendos, Observabilidad y Respaldos"),
    ("Reporte_17_Paridad_de_Calidad_en_el_Cliente_Fuentes_Autoalojadas_y_Cadena_de_Suministro.md", "Capítulo 17: Paridad de Calidad en el Cliente — Fuentes Autoalojadas y Cadena de Suministro"),
    ("Reporte_18_Gobierno_del_Modelo_Procedencia_de_los_Datos_Bucle_de_Realimentacion_y_Alertas_de_Deriva.md", "Capítulo 18: Gobierno del Modelo — Procedencia de los Datos, Bucle de Realimentación y Alertas de Deriva"),
    ("Reporte_19_Lo_Dicho_y_No_Hecho_Contrasena_Prestada_Cartera_de_las_Bajas_y_Condiciones_de_Publicacion.md", "Capítulo 19: Lo Dicho y No Hecho — Contraseña Prestada, Cartera de las Bajas y Condiciones de Publicación del Modelo"),
    ("Reporte_20_Reproducibilidad_y_Ciclo_de_Vida_del_Dato_Dependencias_Fijadas_Retencion_del_Historial_y_Derechos_del_Titular.md", "Capítulo 20: Reproducibilidad y Ciclo de Vida del Dato — Dependencias Fijadas, Retención del Historial y Derechos del Titular"),
    ("Reporte_21_Cimientos_del_Registro_Procedencia_de_la_Actividad_Integraciones_y_Minimizacion.md", "Capítulo 21: Cimientos del Registro — Procedencia de la Actividad, Integraciones y Minimización"),
    # Del 22 al 24 se pegaron a mano en la memoria sin pasar por aquí, y salieron sin su ancla:
    # sus entradas del índice no llevaban a ninguna parte. Todo capítulo entra por esta lista.
    ("Reporte_22_Nada_Sin_Plazo_Ni_Sin_Aviso_Caducidad_Alertas_del_Monitor_Imagenes_Fijadas_y_Arranque.md", "Capítulo 22: Nada sin Plazo ni sin Aviso — Caducidad de los Datos, Alertas del Monitor, Imágenes Fijadas y Arranque"),
    ("Reporte_23_Autenticacion_sin_Excepciones_PyJWT_Revocacion_Inmediata_y_Contrasenas_Filtradas.md", "Capítulo 23: Autenticación sin Excepciones — PyJWT, Revocación Inmediata y Contraseñas Filtradas"),
    ("Reporte_24_Modelo_sin_Datos_Inventados_Ingresos_Ausentes_Canales_Separados_y_Aporte_con_Intervalo.md", "Capítulo 24: Modelo sin Datos Inventados — Ingresos Ausentes, Canales Separados y Aporte con Intervalo"),
    ("Reporte_25_Del_Post_de_LinkedIn_al_Prospecto_Puntuado_Publicaciones_Pagina_de_Interes_e_Informe_por_Publicacion.md", "Capítulo 25: Del Post de LinkedIn al Prospecto Puntuado — Publicaciones, Página de Interés e Informe por Publicación"),
    ("Reporte_26_Publicaciones_Completas_Ciclo_de_Vida_Opciones_Responsable_y_Visitas.md", "Capítulo 26: Publicaciones Completas — Ciclo de Vida, Opciones, Responsable y Visitas"),
    ("Reporte_27_Una_Publicacion_Varias_Redes_Difusion_Textos_por_Red_y_Atribucion.md", "Capítulo 27: Una Publicación, Varias Redes — Difusión, Textos por Red y Atribución"),
    ("Reporte_28_El_Sistema_Dice_Que_Hacer_Hoy_Motor_de_Reglas_Tareas_y_Avisos.md", "Capítulo 28: El Sistema Dice Qué Hacer Hoy — Motor de Reglas, Tareas y Avisos"),
    # A partir de aquí el número del reporte y el del capítulo dejan de coincidir. El
    # capítulo 29 («Lo que dijeron las personas») no escribió un reporte propio: lo que
    # produjo se incorporó como actualización fechada dentro de los reportes 25 a 28. Se
    # deja el desajuste en vez de renumerar, porque un reporte que cambia de número rompe
    # las referencias cruzadas de todos los anteriores. El propio Reporte 29 lo explica en
    # su primera línea.
    ("Reporte_29_Cerrar_el_Bucle_El_Desenlace_con_su_Motivo_Panel_y_Contador_del_Reentrenamiento.md", "Capítulo 30: Cerrar el Bucle — El Desenlace con su Motivo, Panel de Desenlaces y Contador del Reentrenamiento"),
    # El desfase crece a DOS: el capítulo 31 («Congelar y entregar») tampoco escribió reporte
    # propio. Sus cinco entregables fueron el documento de congelación, el guion cronometrado
    # de la demostración, su ensayo, la guía de defensa y este mismo resumen ejecutivo, y
    # ninguno era un reporte. Igual que con el 29: se explica, no se renumera.
    ("Reporte_30_La_Deuda_Que_Muerde_Plazos_Para_lo_Ultimo_sin_Plazo_El_Pais_Que_Ya_No_Se_Supone_y_Todo_Fijado.md", "Capítulo 32: La Deuda que Muerde — Plazos para lo Último sin Plazo, el País que ya no se Supone y Todo Fijado por Versión"),
    # El desfase se queda en dos y ya no crece: el capítulo 33 sí escribe reporte. Cierra el
    # único punto de §6.1 que el capítulo 32 abrió, y que el propio 32 encontró comprobando
    # si su arreglo del país se podía usar de verdad.
    ("Reporte_31_Vaciar_un_Campo_es_un_Cambio_El_Nulo_que_se_Ignoraba_y_la_Lista_que_la_Tabla_Dicta.md", "Capítulo 33: Vaciar un Campo es un Cambio — El Nulo que se Ignoraba y la Lista que Dicta la Tabla"),
    # El capítulo que por fin pone la página de interés a disposición de alguien de fuera,
    # y el primero que publica algo de este sistema en internet. Desbloquea §3.4 de la
    # congelación, que llevaba abierto desde el capítulo 27 esperando «un dominio con
    # certificado, aunque sea de pruebas».
    ("Reporte_32_Salir_a_Internet_por_una_Puerta_Estrecha_Tunel_a_Coste_Cero_y_la_Direccion_que_Caduca.md", "Capítulo 34: Salir a Internet por una Puerta Estrecha — Túnel a Coste Cero y la Dirección que Caduca"),
    # Cierra §3.6, el punto más antiguo que quedaba abierto: llevaba desde el capítulo 19
    # esperando, y no por falta de tiempo sino porque hacerlo a medias produce una cuenta
    # de administración que se bloquea sola.
    ("Reporte_33_Segundo_Factor_para_Administracion_El_Secreto_que_no_se_Guarda_y_la_Cuenta_que_no_se_Bloquea_Sola.md", "Capítulo 35: Segundo Factor para Administración — El Secreto que no se Guarda y la Cuenta que no se Bloquea Sola"),
    # Paga la deuda que el propio `eslint.config.js` se dejó anotada en el capítulo 17: el
    # conjunto de reglas de accesibilidad entra entero porque las familias que decía no
    # haber revisado, ya están revisadas.
    ("Reporte_34_Accesibilidad_Comprobada_La_Ventana_que_no_Era_Ventana_el_Color_que_no_Llegaba_y_la_Consulta_por_Fila.md", "Capítulo 36: Accesibilidad Comprobada — La Ventana que no Era Ventana, el Color que no Llegaba y la Consulta por Fila"),
    # Cierra §3.7 y §3.8 de la congelación demostrando que la premisa de las dos era falsa:
    # ninguna necesitaba la cuenta externa que decían necesitar. Es el primer capítulo que
    # corrige el documento de trabajo futuro y no solo el código.
    ("Reporte_35_La_Cadena_de_Suministro_se_Mantiene_Sola_Cinco_Caracteres_que_Salen_el_Tercero_que_no_Puede_Bloquear_y_el_Aviso_que_no_Decide.md", "Capítulo 37: La Cadena de Suministro se Mantiene Sola — Cinco Caracteres que Salen, el Tercero que no Puede Bloquear y el Aviso que no Decide"),
    # Abre la congelación para tres puntos de §6.2 y para ninguno más: los tres eran una
    # capacidad que existe, está probada y no se puede usar desde donde hay que usarla. Y,
    # usando el panel con un teléfono en la mano, encuentra que el código QR no lo leía
    # ningún lector desde el capítulo 27.
    ("Reporte_36_Un_Derecho_sin_Pantalla_La_Respuesta_que_no_Distingue_el_Borrado_que_se_Escribe_y_el_Numero_que_Llego_al_Tablero.md", "Capítulo 38: Un Derecho sin Pantalla — La Respuesta que no Distingue, el Borrado que se Escribe y el Número que Llegó al Tablero"),
    # Abre la congelación para cuatro puntos de §6.4 y para ninguno más. Uno de ellos estaba
    # mal medido: lo anotado como «cosmético» dejaba la barra del tablero sin pintar y la
    # opción elegida de la ficha 360 sin contorno. Y el hallazgo no es el defecto sino lo que
    # apareció al corregirlo: subir el contorno de un control a lo que pide §1.4.11 dejaba el
    # aro de foco a 1.11:1 de él, es decir, cumplía un criterio rompiendo otro.
    ("Reporte_37_Lo_que_el_Marcado_Pedia_y_la_Hoja_no_Tenia_La_Barra_que_no_Pintaba_el_Contorno_que_no_se_Veia_y_el_Criterio_que_Casi_Rompe_el_Otro.md", "Capítulo 39: Lo que el Marcado Pedía y la Hoja no Tenía — La Barra que no Pintaba, el Contorno que no se Veía y el Criterio que Casi Rompe el Otro"),
    ("Reporte_38_El_Error_que_el_Servidor_ya_Explicaba_El_Color_que_Nadie_Media_el_Campo_que_no_se_Senalaba_y_el_Aro_que_Tuvo_que_ser_Geometrico.md", "Capítulo 40: El Error que el Servidor ya Explicaba — El Color que Nadie Medía, el Campo que no se Señalaba y el Aro que Tuvo que ser Geométrico"),
    # El capítulo 41 abre el punto 25 de §6.4 —el alta guardaba el texto en blanco que la
    # edición normalizaba— y encuentra que el defecto es de orden: una comprobación de
    # longitud y un recorte puestos de manera que el mínimo mide una cadena y la base recibe
    # otra. Y que la regla derivada de la tabla, lo mejor del capítulo 33, se escribió para
    # una tabla de tres.
    ("Reporte_39_El_Minimo_que_no_Media_Nada_Un_Blanco_en_Cinco_Puertas_la_Regla_que_Solo_Tenia_una_Tabla_y_el_Espacio_que_Duplicaba_un_Evento.md", "Capítulo 41: El Mínimo que no Medía Nada — Un Blanco en Cinco Puertas, la Regla que Solo Tenía una Tabla y el Espacio que Duplicaba un Evento"),
]


def build_cover_page() -> str:
    return """<!-- PORTADA INSTITUCIONAL FORMAL -->
<div align="center">

# MEMORIA TÉCNICA DE ESTADÍA PROFESIONAL

## SISTEMA INTELIGENTE DE LEAD SCORING BASADO EN INTELIGENCIA ARTIFICIAL Y MACHINE LEARNING

---

### **EMPRESA RECEPTORA:**
**PLURIONE S.A. DE C.V. (DEVELOP TALENT & TECHNOLOGY)**  
*Consultoría Especializada en Atracción de Talento y Soluciones de TI*

---

### **PARTICIPANTES INSTITUCIONALES:**

| Rol Institucional | Nombre y Cargo |
| :--- | :--- |
| **Representante Legal** | Lic. Xochicuahuitl Gleason Juárez |
| **Asesor Empresarial** | Juan Méndez Herrera |
| **Líder de Proyecto** | Edgar Loheffelmman |
| **Alumno Residente** | Alumno de Ingeniería en Sistemas Computacionales |

---

**Programa Académico:** Ingeniería en Sistemas Computacionales  
**Periodo de Ejecución:** Estadía Profesional (2026)  
**Lugar y Fecha:** Ciudad de México, Septiembre de 2026  

</div>

<div style="page-break-after: always;"></div>

---

# AVISO DE CONFIDENCIALIDAD Y PROPIEDAD INTELECTUAL

> **CONVENIO DE CONFIDENCIALIDAD Y CESIÓN DE DERECHOS PATRIMONIALES**  
> **EMPRESA TITULAR: PLURIONE S.A. DE C.V. (DEVELOP TALENT & TECHNOLOGY)**

1. **TITULARIDAD EXCLUSIVA DE DERECHOS:**  
   Se hace constar expresamente que la totalidad del código fuente, modelos matemáticos, algoritmos híbridos de ponderación, diagramas de arquitectura, componentes de software, documentación y la presente memoria técnica son propiedad patrimonial e intelectual exclusiva de **PLURIONE S.A. DE C.V. (Develop Talent & Technology)**. Queda estrictamente prohibida su reproducción, divulgación, ingeniería inversa o uso comercial no autorizado sin el consentimiento previo por escrito de su Representante Legal, **Lic. Xochicuahuitl Gleason Juárez**.

2. **PROTECCIÓN DE SECRETOS INDUSTRIALES Y ANOMINIZACIÓN ESTRICTA:**  
   En cumplimiento riguroso con el Convenio de Confidencialidad y Secreto Industrial suscrito entre la institución educativa, el alumno residente y la empresa receptora, se certifica que:
   - **No se divulga ningún dato sensible, base de datos real de clientes, registros de nómina ni montos contractuales reales de PluriOne S.A. de C.V.**
   - Todos los ejemplos, capturas, bitácoras de auditoría y conjuntos de datos utilizados en este documento y en el repositorio corresponden al **100% a datos sintéticos, probabilísticos y anonimizados** generados mediante algoritmos locales controlados.
   - Las referencias a canales de captación, roles de venta y plataformas externas (CRM) son utilizadas únicamente con fines ilustrativos y de validación de arquitectura de software.

3. **FINALIDAD ACADÉMICA Y DEFENSA DE ESTADÍA:**  
   El presente documento ha sido elaborado exclusivamente para sustentar la evaluación de la Estadía Profesional del programa de **Ingeniería en Sistemas Computacionales**, acreditando las competencias profesionales de análisis, diseño, ingeniería de software, inteligencia artificial y aseguramiento de calidad del alumno residente.

---

<div style="page-break-after: always;"></div>

"""


def build_table_of_contents() -> str:
    toc = "# ÍNDICE GENERAL\n\n"
    toc += "- [Aviso de Confidencialidad y Propiedad Intelectual](#aviso-de-confidencialidad-y-propiedad-intelectual)\n"
    toc += "- [Resumen Ejecutivo Institucional](#resumen-ejecutivo-institucional)\n"
    for i, (_, title) in enumerate(REPORT_FILES, 1):
        anchor = f"capitulo-{i}-{title.lower().split(': ')[1].replace(' ', '-').replace('(', '').replace(')', '').replace('/', '').replace(',', '')}"
        toc += f"- [{title}](#{anchor})\n"
    toc += "\n---\n\n<div style=\"page-break-after: always;\"></div>\n\n"
    return toc


def build_executive_summary() -> str:
    """
    El resumen ejecutivo: la historia, lo construido y las cifras finales.

    Se reescribió entero en el capítulo 31, cuando el proyecto se congeló. Hasta entonces
    enumeraba los capítulos 1 a 15 y se había quedado ahí: las cifras del modelo eran las
    del vector 1 —retirado en el capítulo 24— y las de la suite, las de la fase 8. Un
    resumen que envejece calladamente es peor que no tenerlo, porque el sínodo lo lee
    primero y los capítulos, después.

    Lleva las cifras a mano y no calculadas al compilar a propósito: la memoria tiene que
    salir igual dentro de un año, con el repositorio congelado, sin depender de que haya
    un entorno capaz de correr la suite.
    """
    return """# RESUMEN EJECUTIVO INSTITUCIONAL

La presente **Memoria Técnica** documenta el ciclo de vida completo de concepción, desarrollo, validación y congelación del **Sistema Inteligente de Lead Scoring** desarrollado para **PluriOne S.A. de C.V. (Develop Talent & Technology)**.

### El desafío empresarial

PluriOne atendía sus solicitudes de prospección bajo un esquema secuencial no calificado (FIFO), con un tiempo de primer contacto de **36 horas** y una conversión de MQL a SQL del **12%**. El ejecutivo comercial no tenía forma de saber a quién llamar primero, ni de dónde había salido la persona que tenía delante.

### La historia que el sistema resuelve, de principio a fin

El proyecto no es un tablero de métricas: es un camino completo que empieza en una publicación y termina en un dato de entrenamiento. Son los ocho pasos que recorre la demostración, cada uno construido, probado y verificable:

1. **Marketing crea la publicación** y el servidor le devuelve un enlace propio de 128 bits que nadie puede elegir, adivinar ni reutilizar.
2. **El texto sale listo para pegar**, ya recortado a lo que cabe en cada red, y **cada red lleva su propio enlace etiquetado**: el que se reparte por WhatsApp no es el mismo que el de LinkedIn, y por eso después se puede saber por dónde llegó cada persona.
3. **La persona abre el enlace** —normalmente desde el teléfono— y deja sus datos en un formulario de unos treinta segundos, **sin un solo campo de texto libre**. Solo se le pide lo que el modelo sabe leer.
4. **El sistema crea la ficha ya puntuada**, atribuida a su publicación y a su red, y sin asesor.
5. **El líder la ve en el contador de prospectos sin asesor** y se la asigna desde la propia ficha.
6. **El asesor no tiene que buscarla**: aparece en su bandeja «Hoy» con el motivo escrito, y la ficha 360 le dice de qué publicación salió, qué pidió, cuándo aceptó el aviso de privacidad y dónde está su perfil. Cierra la tarea cuando termina.
7. **El trato se cierra diciendo por qué**: pasar a «Ganado» o «Perdido» no es una opción del selector de etapa. Pide un motivo **de una lista cerrada**, el día del cierre y, si se ganó, el tramo del acuerdo. La puntuación **no se recalcula**, porque el número que importa es el que había cuando se decidió.
8. **Ese cierre es un dato de entrenamiento.** Queda en la instantánea del bucle de realimentación junto con la versión del vector de variables, y el panel de desenlaces dice cuánto falta para poder reentrenar: 200 casos utilizables, 50 de cada clase.

El paso 8 es el que cierra el círculo: el sistema no solo decide a quién llamar, sino que **recoge la prueba de si acertó**, sin que nadie tenga que transcribir nada.

### La solución de ingeniería implementada

Una plataforma integral bajo **Clean Architecture (Puertos y Adaptadores)**, operando con **desarrollo local a costo cero ($0 USD)** y capacidad de integración transparente hacia **Microsoft Azure**:

1. **Pipeline de Machine Learning supervisado.** Clasificador Gradient Boosting con calibración isotónica de probabilidades. El artefacto en producción da **ROC-AUC = 0.9469** con **IC 95 % [0.9275, 0.9635]** sobre datos sintéticos. La cifra verifica la integridad del pipeline, **no el rendimiento comercial**: lo que se exige para publicar es el **aporte sobre el heurístico**, hoy de **+0.0519 con IC 95 % [0.0296, 0.0761]** por bootstrap pareado.
2. **Algoritmo híbrido con decaimiento temporal continuo.** $S_{\\text{final}} = 0.60 \\times S_{\\text{ML}} + 0.40 \\times S_{\\text{Heurístico}} \\times \\gamma(\\Delta t)$, con $\\gamma(\\Delta t) = (0.5)^{\\Delta t / 14}$.
3. **Un modelo que no inventa lo que no sabe.** El vector de variables va versionado: los ingresos ausentes se imputan con la mediana y una columna que marca que faltaban, las llamadas conectadas y las que nadie contestó son variables distintas, y WhatsApp y LinkedIn dejaron de ser una sola. Un canal que el modelo no conoce se trata como **desconocido, es decir, neutro**, y no como un cero.
4. **Core backend RESTful en FastAPI** con ingesta multicanal de webhooks firmados con HMAC, deduplicación idempotente que distingue un reenvío hostil de un reintento legítimo, recálculo masivo en segundo plano con un turno a la vez, y una página pública de captación que es la única ruta sin sesión que escribe en la base —con límite por IP y por publicación, campo trampa y la misma respuesta exista o no el correo—.
5. **Explicabilidad (XAI) con aislamiento del prompt.** Los datos que escribe el prospecto nunca entran como instrucciones al modelo generativo, y la bitácora identifica qué motor produjo cada puntuación.
6. **Frontend React.js** con tablero analítico, matriz de prospectos, ficha 360, simulador de scoring, informe por publicación y por red, bandeja «Hoy» y panel de desenlaces.
7. **Autenticación sin excepciones y autorización sobre el dato.** JWT firmado con PyJWT y contraseñas con `bcrypt`; rotación verificable de tokens de refresco con detección de reutilización y revocación por familia; revocación inmediata por `token_version`; contraseñas contrastadas contra una lista local de filtradas **y contra el servicio público por rango**, del que solo salen cinco caracteres del resumen y que, si no contesta, no bloquea a nadie; y un asesor que ve y edita **únicamente su propia cartera** —un prospecto ajeno responde 404, indistinguible de uno inexistente—, aplicado en el repositorio y no endpoint por endpoint.
8. **Gobierno del dato y derechos del titular.** Migraciones versionadas con Alembic y reversión probada, columnas temporales con zona horaria explícita, exportación y supresión del titular comprobadas tabla por tabla, y bitácora de auditoría de solo lectura que registra actor, acción, entidad y resultado —incluidos los intentos denegados— sin datos personales. La política de conservación **no deja ninguna fila sin plazo**: cada tabla tiene el suyo en días con un mínimo que se valida al arrancar, incluida la propia bitácora —con el mínimo más alto, un año, porque ahí borrar destruye la prueba de quién hizo qué—, y también el conjunto de realimentación, que vive fuera de la base y se purga por directorio. Los aplica una sola pasada diaria, con un asiento por plazo.
9. **Una ficha que no afirma lo que nadie dijo.** El tamaño de empresa que no llegó no es «1-10», unos ingresos que no se indicaron no son cero, y un país que nadie escribió no es «México»: la columna admite vacío y la pantalla dice «sin registrar». Las migraciones que corrigieron los datos ya escritos tocan **solo las filas de las que consta que nadie eligió el valor**, y dejan las demás como estaban explicando por qué no se pueden distinguir.
10. **Bucle de realimentación sin fuga de información.** Cada puntuación guarda una **instantánea del vector tal como estaba al puntuar**, y el dataset se etiqueta sobre esa instantánea: un prospecto ganado lleva propuesta enviada y reunión agendada, y entrenar sobre su estado actual enseñaría que enviar propuestas causa cierres. Los prospectos aún en el embudo se **excluyen**, no se cuentan como perdidos.
11. **Observabilidad del modelo.** Monitor de deriva por índice PSI con perfil de referencia atado por huella a su artefacto, registro versionado de modelos con procedencia de los datos, y verificación de la huella SHA-256 del artefacto antes de deserializarlo —si no coincide, el artefacto **no se carga** y el sistema sigue con el heurístico en lugar de ejecutar un `pickle` sustituido—.
12. **Fiabilidad operativa.** Registro estructurado con `request_id`, métricas de Prometheus, copias de seguridad con **prueba de restauración**, imágenes de terceros fijadas por huella con renovación explícita —y actualizaciones automáticas que **avisan** de lo que se quedó atrás sin decidir nada—, y un lanzador único para toda la pila.
13. **Aseguramiento de calidad.** **1530 pruebas** de backend en Pytest con **93 % de cobertura** y **636 pruebas** de cliente en Vitest con suelos de cobertura que fallan si bajan; **10 trabajos** de integración continua con análisis estático, auditoría de dependencias, detección de secretos, verificación de migraciones en PostgreSQL, umbrales de precisión y de aporte del modelo, **54 controles de regresión** sobre configuración peligrosa y **seis guardas de propiedades** que fallan en cuanto el sistema pierde una defensa, aunque ninguna prueba existente se rompa. Las **nueve pantallas** del cliente se revisan además contra el nivel **AA de WCAG 2.1** desde la propia suite, se recorren con teclado y miden su contraste sobre la paleta declarada. Y el código QR **se lee**: desde el capítulo 38 la suite lo decodifica como lo haría una cámara, que es lo único que distingue un código correcto de uno que solo lo parece; desde el 39 tiene además un tamaño con suelo medido en píxeles por módulo. Todo lo que el marcado nombra —cada clase y cada variable de la paleta— se comprueba que existe, y desde el capítulo 40 **ningún color puede escribirse fuera de la paleta**, que es el único sitio donde el contraste se mide: las tres listas se sacan del código, no se escriben a mano. Cuando el servidor rechaza un campo, la pantalla lo señala, lo explica en castellano y lleva el foco hasta él, con el mismo mecanismo en las cinco pantallas que tienen formulario.

### Lo que este trabajo se negó a hacer

Es parte del resultado y no una omisión. El sistema **no reentrena el modelo** con los canales nuevos, porque todavía no existen desenlaces reales con los que hacerlo; **no asigna peso a los motivos** de pérdida; **no proyecta ingresos** a partir del tramo del acuerdo; y **no publica un modelo** cuyo intervalo de confianza no alcance el umbral, aunque su estimación puntual lo supere. El trabajo futuro que estas decisiones dejan abierto está recogido, con lo que depende cada punto, en `docs/Congelacion_y_Trabajo_Futuro.md`.

---

<div style="page-break-after: always;"></div>

"""


def compile_all():
    print(f"[1/3] Leyendo {len(REPORT_FILES)} reportes técnicos de estadía...")
    compiled_body = ""

    for i, (filename, title) in enumerate(REPORT_FILES, 1):
        filepath = os.path.join(REPORTES_DIR, filename)
        if not os.path.exists(filepath):
            print(f"Error: Archivo no encontrado: {filepath}")
            sys.exit(1)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Ajustar título principal para la memoria
        anchor_id = f"capitulo-{i}-{title.lower().split(': ')[1].replace(' ', '-').replace('(', '').replace(')', '').replace('/', '').replace(',', '')}"
        chapter_header = f"<a id=\"{anchor_id}\"></a>\n\n# {title.upper()}\n\n"

        # Reemplazar el primer h1 del reporte
        content_clean = re.sub(r"^# Reporte Técnico \d+: .*", "", content, flags=re.MULTILINE).strip()

        compiled_body += chapter_header + content_clean + "\n\n---\n\n<div style=\"page-break-after: always;\"></div>\n\n"
        print(f"      ✓ Integrado: {filename}")

    print("[2/3] Ensamblando Portada, Avisos Legales, Índice y Resumen Ejecutivo...")
    full_document = (
        build_cover_page()
        + build_table_of_contents()
        + build_executive_summary()
        + compiled_body
    )

    print(f"[3/3] Escribiendo memoria consolidada en: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_document)

    print(f"\n[OK] ¡Memoria Técnica consolidada exitosamente! Tamaño: {len(full_document):,} caracteres.")


if __name__ == "__main__":
    compile_all()
