# Reporte Técnico 08: Suite de Pruebas Automatizadas y QA de Precisión

**Proyecto:** Sistema Inteligente de Lead Scoring basado en Inteligencia Artificial y Machine Learning  
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)  
**Autor:** Alumno de Estadía Profesional - Ingeniería en Sistemas Computacionales  
**Fecha:** Septiembre 2026  
**Fase de Estadía:** 8. Aseguramiento de Calidad (QA), Pruebas Automatizadas y Validación de Precisión  

---

## 1. Objetivo de la Fase
El objetivo principal de esta fase fue diseñar, implementar y ejecutar el **Plan Integral de Aseguramiento de Calidad (QA - Quality Assurance)** para el Sistema Inteligente de Lead Scoring de **PluriOne S.A. de C.V.**. Me propuse construir una suite exhaustiva de pruebas automatizadas en **Pytest** y **FastAPI TestClient**, que abarcara pruebas unitarias de formulación matemática y decaimiento temporal, pruebas de adaptadores de infraestructura (*Ports & Adapters*), pruebas de integración de endpoints RESTful y validación de la robustez de ingesta multicanal de webhooks con deduplicación de datos.

---

## 2. Qué se Realizó (Pirámide de Pruebas y Suites Automatizadas)

### 2.1. Estructura del Plan de Pruebas (Pirámide de QA)
Estructuré el aseguramiento de calidad en cuatro niveles de prueba automatizada:

```mermaid
pyramid
    title Pirámide de Pruebas del Sistema de Lead Scoring
    "Pruebas End-to-End & UI (Flujo Comercial)" : 10
    "Pruebas de Integración REST & CRM Webhooks (test_api.py & test_crm_integration.py)" : 30
    "Pruebas de Adaptadores y Puertos IA (test_adapters.py)" : 25
    "Pruebas Unitarias Matemáticas & Decaimiento (test_scoring_math.py)" : 35
```

---

### 2.2. Módulos de Prueba Desarrollados en `backend/tests/`

#### A. Pruebas Unitarias Matemáticas ([test_scoring_math.py](file:///c:/Users/lllllllllllllllllll/Desktop/Resi/Sistema_Inteligente_Lead_Scoring/backend/tests/test_scoring_math.py)):
Validé la exactitud de la ecuación de atenuación exponencial $\gamma(\Delta t) = (0.5)^{\frac{\Delta t}{14}}$ y las cotas de ajuste heurístico:
- En $\Delta t = 0 \text{ días} \rightarrow \gamma = 1.0000$ (Sin penalización).
- En $\Delta t = 7 \text{ días} \rightarrow \gamma \approx 0.7071$ ($70.7\%$ de fuerza conductual).
- En $\Delta t = 14 \text{ días} \rightarrow \gamma = 0.5000$ (Vida media exacta).
- En $\Delta t = 28 \text{ días} \rightarrow \gamma = 0.2500$ (Dos vidas medias).
- Validación de cotas de frontera: El puntaje compuesto nunca excede el rango cerrado $[0, 100]$.

#### B. Pruebas de Adaptadores de Infraestructura ([test_adapters.py](file:///c:/Users/lllllllllllllllllll/Desktop/Resi/Sistema_Inteligente_Lead_Scoring/backend/tests/test_adapters.py)):
- Inferencia determinística de `LocalMLScoringAdapter` a costo cero ($0 USD) con salida probabilística calibrada en $[0.0, 1.0]$.
- Generación de explicaciones ejecutivas y recomendaciones tácticas estructuradas con `LocalMockOpenAIAdapter`.
- Recuperación semántica de prospectos convertidos con `LocalMockSearchAdapter`.
- Verificación de fábricas abstractas (`get_ml_scoring_adapter`, `get_ai_explanation_adapter`).

#### C. Pruebas de Integración CRM y Deduplicación ([test_crm_integration.py](file:///c:/Users/lllllllllllllllllll/Desktop/Resi/Sistema_Inteligente_Lead_Scoring/backend/tests/test_crm_integration.py)):
- Manejo de cargas útiles incompletas (HTTP 400 por omisión de correo obligatorio).
- Ingesta sucesiva de múltiples webhooks (Zoho $\rightarrow$ HubSpot) con el mismo email, comprobando la actualización atómica de atributos, el recálculo dinámico del score y el registro inmutable en `crm_integration_logs`.

#### D. Pruebas de Controladores RESTful ([test_api.py](file:///c:/Users/lllllllllllllllllll/Desktop/Resi/Sistema_Inteligente_Lead_Scoring/backend/tests/test_api.py)):
- Health check y estado del servicio (`GET /` y `GET /health`).
- Consulta paginada y filtrado multidimensional de leads (`GET /api/v1/leads`).
- Creación de prospecto con actividad inicial y auto-scoring (`POST /api/v1/leads`).
- Registro reactivo de interacción digital (`POST /api/v1/leads/{id}/activities`).
- Inferencia en tiempo real *stateless* (`POST /api/v1/scoring/predict`).
- Resumen analítico para gráficos ejecutivos (`GET /api/v1/analytics/summary`).
- Encolado del recálculo masivo y consulta de su avance (`POST /api/v1/leads/batch/recalculate-all` → `202`, `GET /api/v1/leads/batch/jobs/{id}`).

---

### 2.3. Resumen de Resultados de Ejecución en Pytest

La suite creció de las 16 pruebas iniciales a **428**, repartidas en 30 módulos. El
crecimiento no es decorativo: la mayor parte corresponde a las fases de endurecimiento
descritas en el **Capítulo 11**, donde cada corrección de seguridad o de rendimiento se
acompañó de la prueba que la fija.

| Módulo | Pruebas | Qué asegura |
| :--- | :---: | :--- |
| `test_security_rbac.py` | 41 | Separación de roles y respuestas 401/403 en cada endpoint protegido. |
| `test_schema_validation.py` | 38 | Cotas, tipos y longitudes máximas de todos los esquemas de entrada. |
| `test_security_path_traversal.py` | 23 | La entrega de la SPA no sirve ficheros fuera de `dist/`. |
| `test_recalculation_jobs.py` | 18 | Ciclo de vida del recálculo masivo: `202`, lotes, avance y tolerancia a fallos. |
| `test_crm_webhook_signature.py` | 16 | Firma HMAC, ventana temporal y rechazo de reenvíos. |
| `test_model_integrity.py` | 13 | Huella SHA-256 del artefacto de ML y caché de las fábricas de adaptadores. |
| `test_scoring_parity.py` | 12 | El heurístico compartido da lo mismo por sus dos rutas de cálculo. |
| `test_api.py` | 12 | Contratos REST: paginación, filtrado, alta y consulta de prospectos. |
| `test_config_validation.py` | 10 | La configuración inválida aborta el arranque en lugar de degradarse. |
| `test_production_hardening.py` | 9 | Documentación cerrada y validaciones exigidas en entorno productivo. |
| `test_rate_limiting.py` | 8 | El corte por tasa existe de verdad en login, scoring y webhook. |
| `test_analytics_aggregation.py` | 7 | El informe de campañas se resuelve en una sola consulta. |
| `test_security_identity_lifecycle.py` | 6 | Un cambio de rol surte efecto sobre los tokens ya emitidos. |
| `test_crm_transaction.py` | 4 | La ingesta CRM confirma todo o no confirma nada. |
| `test_adapters.py` | 4 | Adaptadores locales de ML, explicabilidad y búsqueda. |
| `test_scoring_math.py` | 2 | Precisión del decaimiento temporal y cotas del heurístico. |
| `test_crm_integration.py` | 2 | Deduplicación por correo y registro de auditoría. |
| `test_ml_honesto.py` | 15 | Alineación del vector de variables y bucle de realimentación sin fuga. |
| `test_cors_policy.py` | 15 | Que ningún origen no declarado pueda leer respuestas autenticadas. |
| `test_prompt_injection.py` | 15 | Aislamiento de los datos del prospecto respecto del prompt y validación de la salida. |
| `test_deriva_y_registro.py` | 14 | Que el índice de deriva detecte un desplazamiento y no marque lo que no cambió. |
| `test_seed_data_guards.py` | 9 | Que el script de siembra no borre sin confirmación explícita. |
| `test_proxy_y_auditoria.py` | 21 | Que la cabecera de proxy no esquive el tope y que cada operación sensible deje asiento. |
| `test_sesiones_rotativas.py` | 13 | Que un token de refresco consumido no vuelva a servir y que su reutilización cierre la sesión. |
| `test_ingesta_idempotente.py` | 11 | Que una entrega de webhook reenviada no se ingiera dos veces. |
| `test_autorizacion_por_objeto.py` | 28 | Que un asesor comercial vea y edite únicamente su propia cartera. |
| `test_gestion_de_identidades.py` | 24 | Alta, baja lógica y cambio de rol de cuentas, sin poder dejar el sistema sin administrador. |
| `test_politica_de_contrasenas.py` | 22 | La política de contraseñas y que el cambio propio exija la actual y cierre las sesiones. |
| `test_campanas.py` | 12 | Permisos sobre campañas y que desactivarlas no destruya la atribución. |
| `test_pila_de_despliegue.py` | 4 | Que la pila aplique las migraciones antes de servir. |

```
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\...\Sistema_Inteligente_Lead_Scoring
configfile: pyproject.toml
testpaths: backend/tests

...........................................................................
...........................................................................
...........................................................................
........................................................................

====================== 428 passed, 8 warnings in 154.67s ======================
```

**Cobertura del paquete de aplicación: 91 %**, medida con `pytest-cov`. El pipeline de
integración continua la exige por encima del 85 % y falla por debajo.

#### Aislamiento: la suite nunca toca una base de datos real
El `conftest.py` fija `DATABASE_URL=sqlite://` **antes** de importar la aplicación y
sustituye la dependencia `get_db`, de modo que toda la suite corre sobre una base en
memoria. Es una garantía comprobada, no una intención: tras cada ejecución se verifica que
no haya quedado ningún fichero `.db` en el árbol del proyecto.

---

---

## 3. Justificación Técnica
1. **Pytest con FastAPI TestClient (ASGI):**
   - *Velocidad y Aislamiento:* `TestClient` ejecuta las peticiones directamente a través de la pila ASGI en memoria sin levantar sockets TCP reales, lo que permite ejecutar las 428 pruebas completas con base de datos en unos tres minutos a costo $0 USD.
2. **Idempotencia de Pruebas Mediante UUIDs:**
   - *Confiabilidad:* Los tests de integración generan correos y entidades únicas mediante `uuid.uuid4().hex`, evitando colisiones o fallos por datos remanentes de ejecuciones previas.

---

## 4. Metodología y Arquitectura Aplicada
- **Test-Driven Development (TDD) & BDD:** Especificación de escenarios de prueba con precondiciones (*Given*), acciones (*When*) y resultados esperados (*Then*).
- **Aislamiento de Sesiones de Base de Datos:** Uso de `expire_all()` y transaccionalidad limpia para garantizar que las relaciones de SQLAlchemy no dependan del estado en memoria residual.

---

## 5. Retos Técnicos Superados y Evidencia Funcional

### Reto 1: Verificación de la Calibración de Probabilidades del Modelo ML
**Problema:** Un modelo que clasifica bien pero asigna probabilidades irreales distorsiona la ponderación híbrida ($0.60 \times P_{\text{ML}} \times 100$).  
**Solución:** Validé que el `Brier Score` se mantuviera en $0.0875$ y que el `ROC-AUC` alcanzara $0.9524$, garantizando que la salida del clasificador se traduzca de forma confiable a la puntuación del lead.

### Reto 2: Compatibilidad de Expresiones Condicionales SQL en SQLAlchemy 2.0
**Problema:** La función `func.case(...)` generaba errores de sintaxis en SQLAlchemy 2.0 al procesar argumentos `else_`.  
**Solución:** Migré la consulta al constructor nativo `case((Lead.score_category == ScoreCategory.HOT, 1), else_=0)` en `analytics_service.py`, asegurando compatibilidad multiplataforma entre SQLite y PostgreSQL.

### Evidencia de Calidad del Software
La suite completa de 428 pruebas automatizadas fue aprobada con un **100% de tasa de éxito**, certificando que el sistema es matemáticamente exacto, seguro contra inyecciones y errores de tipado, y listo para operación comercial.
