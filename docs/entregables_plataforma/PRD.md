# PRD — Sistema Inteligente de Lead Scoring

**Producto:** Sistema Inteligente de Lead Scoring
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Residente:** Rosales Castillo Sebastián · No. de control 223107211 · Ingeniería en Sistemas Computacionales · 9° semestre
**Periodo:** 2026-2 (31/08/2026 – 29/01/2027)
**Versión del documento:** 1.0 — octubre de 2026 (producto en congelación definitiva desde el 06-10-2026)

---

## 1. Resumen

PluriOne atendía sus solicitudes de prospección **en orden de llegada y sin calificar**: unas **36 horas** de latencia hasta el primer contacto y una conversión de MQL a SQL del **12 %**. El ejecutivo comercial no sabía a quién llamar primero ni de dónde había salido la persona que tenía delante.

El producto es un sistema web que **puntúa cada prospecto de 0 a 100**, lo clasifica (HOT / WARM / COLD), le dice al asesor **qué hacer hoy y por qué**, y **cierra el círculo**: cuando un trato se gana o se pierde, el sistema guarda el desenlace con su motivo para poder reentrenar el modelo con datos reales.

Restricción de ingeniería: **coste recurrente de 0 USD**, sin cuentas externas nuevas, funcionando en una sola máquina y con salida posible a Azure.

---

## 2. Problema

| Síntoma | Causa raíz |
| :--- | :--- |
| Prospectos de alto valor contactados con horas o días de retraso | No hay priorización: el CRM atiende por orden de llegada (FIFO) |
| Esfuerzo comercial gastado en contactos sin perfil de decisión | No hay un criterio cuantitativo de encaje (cargo, sector, tamaño) |
| El interés de un prospecto se enfría y nadie lo nota | El score no considera el paso del tiempo sin interacción |
| El ejecutivo desconfía de un número sin explicación | Las herramientas comerciales evaluadas son cajas negras |
| No se sabe qué publicación o red trajo a cada persona | Los enlaces no se distinguen entre redes ni entre publicaciones |
| Nadie aprende de los tratos cerrados | El desenlace no se registra con un motivo utilizable |

**Alternativa descartada:** adoptar un SaaS (HubSpot Enterprise, Salesforce Einstein): licencias de 150–300 USD por ejecutivo al mes, algoritmo de caja negra y sin ajuste al mercado de talento TI en México.

---

## 3. Objetivos y métricas de éxito

| Objetivo | Métrica | Estado al cierre |
| :--- | :--- | :--- |
| Priorizar la cartera con un score explicable | Score 0–100 híbrido (60 % ML + 40 % heurístico ICP con decaimiento) | Implementado |
| El modelo debe aportar sobre la línea base | Aporte sobre el heurístico con IC 95 % que **no toque el cero** | **+0,0519**, IC [+0,0296, +0,0761] |
| Calidad de ordenamiento | ROC-AUC del modelo | 0,9469 (IC 95 % [0,9275, 0,9635]) — **sobre datos sintéticos** |
| Respuesta rápida | Inferencia individual < 150 ms | Cumplido (el alta completa del envío público mide 286 ms) |
| Que el asesor no tenga que buscar | Bandeja «Hoy» con tarea y motivo escrito | Implementado |
| Saber de dónde llega cada persona | Atribución por publicación y por red | Implementado |
| Aprender de los cierres | Desenlace con motivo de lista cerrada + contador de reentrenamiento (200 casos, 50 por clase) | Implementado; **sin reentrenar**: faltan desenlaces reales |
| Coste cero | 0 USD recurrentes | Cumplido |

> **Honestidad de las cifras.** El ROC-AUC se mide sobre datos sintéticos cuya etiqueta sale de una fórmula conocida: verifica que el **pipeline está íntegro**, no el rendimiento comercial. La cifra defendible es el **aporte sobre el heurístico (+0,0519)**.

---

## 4. Usuarios

| Persona | Rol en el sistema | Necesita |
| :--- | :--- | :--- |
| **Asesor comercial** | `Commercial_Executive` | Saber a quién contactar hoy y por qué; ver solo **su** cartera |
| **Líder comercial** | `Sales_Lead` | Cartera completa, reasignar, publicaciones, informes, desenlaces |
| **Administrador de TI** | `System_Admin` | Cuentas, bitácora de auditoría, derechos del titular, segundo factor |
| **Marketing** (opera con el rol de líder) | `Sales_Lead` | Crear publicaciones y repartirlas por red con enlace propio |
| **Persona interesada** | Sin cuenta | Dejar sus datos en un formulario público corto |
| **CRM externo** | Actor no humano | Enviar prospectos por webhook firmado |

---

## 5. Requerimientos funcionales

| ID | Requerimiento | Prioridad |
| :--- | :--- | :---: |
| RF-01 | **Ingesta** de prospectos por varios caminos (alta desde el panel, página pública de interés, webhook CRM firmado, integraciones de LinkedIn y formulario web), todos por una sola pieza que escribe actividades | Alta |
| RF-02 | **Score híbrido** 0–100: `0,60·S_ML + 0,40·S_heurístico·γ(Δt)`, con `γ(Δt) = 0,5^(Δt/14)` | Crítica |
| RF-03 | **Decaimiento temporal** continuo (vida media de 14 días) | Alta |
| RF-04 | **Categorías** HOT (≥ 75), WARM ([45, 75)), COLD (< 45) | Crítica |
| RF-05 | **Registro de actividades** ponderadas y trazables a su origen | Alta |
| RF-06 | **Explicación del score** en lenguaje natural, sin costo por token (motor local) | Media |
| RF-07 | **Reparto automático** equitativo al dar de alta una ficha, con asiento de bitácora que dice la regla y los candidatos | Media |
| RF-08 | **Publicaciones**: enlace propio de 128 bits por publicación, un enlace y un texto por red, código QR local, informe por red y comparativa | Alta |
| RF-09 | **Página de interés pública**: formulario sin texto libre, con aviso de privacidad, defendido contra abuso | Alta |
| RF-10 | **Motor de reglas diario**: seis reglas, tareas y avisos, bandeja «Hoy», campana y escalado al líder | Alta |
| RF-11 | **Cierre de trato** con motivo de lista cerrada, fecha y tramo; sin recalcular el score | Alta |
| RF-12 | **Panel de desenlaces** y contador del reentrenamiento | Media |
| RF-13 | **Dashboard analítico**: distribución, embudo MQL→SAL→SQL, KPIs y desempeño de campañas | Alta |
| RF-14 | **Simulador de scoring** interactivo | Baja |
| RF-15 | **Gestión de cuentas** con baja lógica, cambio de rol y restablecimiento de contraseña | Alta |
| RF-16 | **Derechos del titular**: exportación y supresión por tabla, con huella en la bitácora | Media |

## 6. Requerimientos no funcionales

| ID | Categoría | Criterio |
| :--- | :--- | :--- |
| RNF-01 | Rendimiento | Inferencia individual < 150 ms |
| RNF-02 | Coste | 0 USD recurrentes; todo corre en local con Docker Compose |
| RNF-03 | Portabilidad | Configuración por variables de entorno; sin código atado a un proveedor |
| RNF-04 | Seguridad | JWT con revocación inmediata, refresco rotado con detección de reutilización, RBAC, alcance de cartera aplicado en el repositorio, segundo factor TOTP para administración, límites de tasa |
| RNF-05 | Trazabilidad | Bitácora de auditoría de solo lectura, incluidos los intentos denegados; cada puntuación guarda la versión del motor que la calculó |
| RNF-06 | Privacidad | Plazos de conservación en todas las tablas; sin datos reales en el repositorio (todo sintético) |
| RNF-07 | Accesibilidad | Nivel AA de WCAG 2.1 en las nueve pantallas, medido con `axe-core` desde la suite |
| RNF-08 | Calidad | Cobertura del servidor ≥ 99,1 % con ramas; guardas de propiedades en CI |
| RNF-09 | Operación | Un solo modo de arranque; copias de seguridad con prueba de restauración; imágenes fijadas por huella |

---

## 7. Alcance

**Dentro:** todo lo anterior. El MVP (ver [MVP.md](MVP.md)) es el subconjunto mínimo que valida la hipótesis; el resto es el producto entregado.

**Fuera, por decisión escrita** (detalle y motivo en `docs/Congelacion_y_Trabajo_Futuro.md`):

- **Leer LinkedIn, Calendly o WhatsApp:** exige cuentas y API aprobadas que el proyecto no tiene; el sistema recibe lo que *llega desde* esas redes.
- **Reentrenar el modelo:** exige desenlaces reales; un reentrenamiento con etiquetas sintéticas sería circular.
- **Borrar en el CRM externo** al suprimir un prospecto aquí: no hay (ni debe haber) credenciales de borrado ajenas.
- **Dirección pública permanente:** el túnel gratuito cambia de dirección en cada arranque; cerrarlo exige un dominio y un certificado, no código.
- **Instalación en la PC servidora:** no hecha ni ensayada; lo probado es esta instalación con Docker.

---

## 8. Arquitectura (resumen)

- **Backend:** FastAPI, Clean Architecture (puertos y adaptadores), Pydantic v2, SQLAlchemy 2.0, Alembic (17 migraciones). PostgreSQL en la pila; SQLite en pruebas.
- **Modelo:** `GradientBoostingClassifier` con calibración isotónica; motor heurístico ICP compartido entre el servicio y el pipeline de entrenamiento.
- **Frontend:** React + Vite, accesible AA, sin dependencias de fuentes externas.
- **Operación:** Docker Compose (seis servicios), Redis para el contador de tasa, nginx como puerta pública, respaldos con prueba de restauración, CI con 10 trabajos.

## 9. Riesgos

| Riesgo | Mitigación |
| :--- | :--- |
| Métricas sobre datos sintéticos no predicen rendimiento comercial | Se defiende el aporte sobre la línea base, no el ROC-AUC; el sistema recoge ya los desenlaces reales |
| Sin modelo en un clon limpio el sistema puntúa con el heurístico sin avisar | `/health` expone `ml_model_loaded`; cada puntuación guarda `hybrid+ml:<huella>` o `hybrid+heuristico` |
| Enlace público muerto al cambiar el túnel | El sistema marca los enlaces desactualizados y avisa si la dirección configurada no responde |
| Deuda menor acumulada tras la congelación | 60 puntos anotados y numerados; ninguno impide levantar la pila ni enseñar la demostración |
