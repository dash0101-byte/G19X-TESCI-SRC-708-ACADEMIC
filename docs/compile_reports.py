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
    return """# RESUMEN EJECUTIVO INSTITUCIONAL

La presente **Memoria Técnica** documenta el ciclo de vida completo de concepción, desarrollo, validación y despliegue del **Sistema Inteligente de Lead Scoring** desarrollado para **PluriOne S.A. de C.V. (Develop Talent & Technology)**.

### El Desafío Empresarial:
PluriOne experimentaba una alta dispersión del tiempo productivo de sus ejecutivos comerciales, quienes atendían solicitudes de prospección bajo un esquema secuencial no calificado (FIFO), con tiempos de respuesta promedio de 36 horas y una tasa de conversión MQL a SQL del 12%.

### La Solución de Ingeniería Implementada:
Diseñé e implementé una plataforma integral basada en **Clean Architecture (Puertos y Adaptadores)** que opera bajo una premisa estricta de **Desarrollo Local a Costo Cero ($0 USD)** con capacidad de integración transparente hacia servicios en la nube de **Microsoft Azure**:
1. **Pipeline de Machine Learning Supervisado:** Clasificador Gradient Boosting con calibración isotónica de probabilidades ($ROC\text{-}AUC = 0.9524$ sobre datos sintéticos). La cifra verifica la integridad del pipeline, no el rendimiento comercial: el Capítulo 12 la compara contra el heurístico sin modelo (0.9110) y contra una regla trivial (0.9136) para mostrar el aporte real, que es de +0.041.
2. **Algoritmo Híbrido con Decaimiento Temporal Continuo:** Ecuación ponderada $S_{\\text{final}} = 0.60 \\times S_{\\text{ML}} + 0.40 \\times S_{\\text{Heurístico}} \\times \\gamma(\\Delta t)$, donde $\\gamma(\\Delta t) = (0.5)^{\\Delta t / 14}$ modela la pérdida exponencial de interés del prospecto en el tiempo.
3. **Core Backend RESTful en FastAPI:** 13 endpoints para ingesta multicanal de webhooks CRM con firma HMAC, deduplicación de contactos, bitácoras inmutables, auto-asignación comercial de leads `HOT` y recálculo masivo en segundo plano.
4. **Explicabilidad con IA (XAI):** Módulo de generación de resúmenes ejecutivos, fortalezas clave y tácticas comerciales accionables para cada prospecto.
5. **Frontend React.js tipo Power BI:** Tablero analítico en tiempo real, matriz de prospectos interactiva, ficha 360 y simulador interactivo de scoring.
6. **Aseguramiento de Calidad y DevOps:** Suite de 428 pruebas automatizadas en Pytest (100% aprobadas, 91% de cobertura), contenerización multi-etapa con usuario sin privilegios, e integración continua de diez trabajos en GitHub Actions con análisis estático, auditoría de dependencias, detección de secretos, verificación de migraciones, catorce controles de regresión sobre configuración peligrosa y umbrales de precisión y de aporte del modelo.
7. **Auditoría y Endurecimiento de Seguridad:** Autenticación por tokens JWT firmados con `bcrypt`, secretos fuera del árbol del proyecto, limitación de tasa por IP, cabeceras de seguridad en la pasarela y verificación de integridad del artefacto de Machine Learning (Capítulo 11).
8. **Gobierno de Datos y Validez del Modelo:** Migraciones versionadas con Alembic, columnas temporales con zona horaria explícita, y diseño del bucle de realimentación que convierte los desenlaces comerciales reales en dataset de reentrenamiento sin fuga de información (Capítulo 12).
9. **Observabilidad del Modelo en Producción:** Aislamiento de los datos del prospecto respecto del prompt del modelo generativo, registro de auditoría que identifica el motor que produjo cada puntuación, monitoreo de deriva de variables mediante el índice PSI y registro versionado de artefactos entrenados (Capítulo 13).
10. **Trazabilidad de la Sesión y de la Operación:** Rotación verificable de tokens de refresco con detección de reutilización y revocación por familia, ingesta idempotente que distingue un reenvío hostil de un reintento legítimo, y bitácora de auditoría de solo lectura que registra actor, acción, entidad, dirección y resultado —incluidos los intentos denegados— consultable únicamente por el rol administrador (Capítulo 14).
11. **Autorización sobre el Dato y Gestión de Identidades:** Identidad unificada —la tabla de asesores se fusiona dentro de la de usuarios, con migración de datos—, autorización por objeto aplicada en el repositorio y no en cada endpoint (un asesor comercial ve y edita únicamente su propia cartera, y un prospecto ajeno responde 404 indistinguible de uno inexistente), endpoints de alta, baja lógica, cambio de rol y restablecimiento de contraseña restringidos al rol administrador, y política de contraseñas con cambio autogestionado que revoca todas las sesiones (Capítulo 15).

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
