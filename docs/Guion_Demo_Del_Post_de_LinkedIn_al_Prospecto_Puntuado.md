# Del post de LinkedIn al prospecto puntuado

**Guion de la demo y reglas del proyecto**

Fecha: 16 de septiembre de 2026 · Estado del código: tras la Fase 24 (capítulo 24 de la memoria).

Este documento es el punto de partida de lo que viene. Hace tres cosas:

1. Dice dónde quedó el respaldo del proyecto tal como estaba al escribirlo.
2. Cuenta la historia que tiene que poder enseñarse de principio a fin, paso a paso, y separa en cada paso **lo que ya existe** de **lo que falta**. Lo que existe se ensayó; lo que falta está escrito como hueco, no como promesa.
3. Fija las reglas del proyecto a partir de aquí. Cada regla dice por qué existe y dónde choca hoy con el código.

No cambia código. Los huecos que describe se cierran en fases posteriores, con su propio `/goal`.

---

## 0. Punto de partida: el respaldo

| Qué | Dónde |
| :--- | :--- |
| Copia completa del proyecto | `C:\Users\lllllllllllllllllll\Desktop\Resi\_respaldos\Sistema_Inteligente_Lead_Scoring_2026-09-16_punto_de_partida\` |
| Cómo se hizo | `robocopy /E /COPY:DAT /DCOPY:DAT`. Solo copia, nunca borra en el origen. |
| Qué contiene | Los 16 290 ficheros y 1 432 carpetas del árbol (141,6 MB), `frontend/node_modules` incluido |
| Comprobación | Los 16 290 ficheros están en la copia con el mismo tamaño. Fuera de `node_modules`, el SHA-256 de cada fichero coincide con el del original: 0 diferencias. |

La copia está fuera del árbol y no es un repositorio Git: el proyecto sigue sin Git. Los secretos y las bases de datos (`_lead_scoring_local\`) no están dentro del árbol, así que tampoco entran en la copia. Siguen en su sitio.

Para volver a este punto, se copia esa carpeta en lugar del árbol. No hace falta borrar nada antes: el árbol actual puede renombrarse.

---

## 1. La historia en una frase

> Marketing publica en LinkedIn un enlace de una campaña. Alguien interesado deja sus datos de perfil. El sistema crea su ficha y la puntúa sin inventar nada. El asesor la abre en la ficha 360. El líder ve qué publicación trae mejores prospectos.

### Quién es quién

| En la historia | En el sistema | Rol que usa |
| :--- | :--- | :--- |
| Marketing | Quien gestiona campañas | `Sales_Lead`. No existe un rol de marketing: crear una campaña es hoy una decisión de quien dirige la cartera (`endpoints/campaigns.py`). |
| La publicación | Una `Campaign` (tabla `campaigns`) | — |
| El interesado | Un `Lead` | — |
| Lo que hizo el interesado | Una `LeadActivity` creada por `registrar_evento` | — |
| El asesor | Un `User` con `is_sales_rep` | `Commercial_Executive`, que solo ve su cartera |
| El líder | Quien ve el rendimiento por campaña | `Sales_Lead` |

---

## 2. El guion, paso a paso

Cada paso tiene cuatro partes:

- **Se enseña:** lo que ve el público.
- **Existe hoy:** la pieza de código que ya lo hace.
- **Falta:** el hueco, con número (H-n), para la tabla de la sección 4.
- **Cómo se ensaya hoy:** qué se puede mostrar sin cuentas externas.

### Paso 1. Marketing crea la publicación

**Se enseña:** en la pantalla de campañas, marketing da de alta «Post LinkedIn · Talento TI septiembre», con canal LinkedIn y su identificador de campaña (`utm_campaign`).

**Existe hoy:**
- `POST /api/v1/campaigns` crea la campaña con `name`, `channel`, `budget`, `utm_source`, `utm_medium`, `utm_campaign` y fechas. Solo pueden `Sales_Lead` y `System_Admin`, y queda en la bitácora de auditoría.
- Una campaña no se borra, se desactiva, para no perder la atribución.
- `frontend/src/services/api.js` ya tiene `createCampaign`, `updateCampaign`, `deactivateCampaign` y `fetchCampaignList`.

**Falta:**
- **H-1:** ningún componente usa esas funciones. No hay pantalla para crear campañas: hoy solo se crean por la API o sembrando la base.

**Cómo se ensaya hoy:**
- La base demo ya trae cuatro campañas sembradas; la primera es «Q3 Tech Talent Summit 2026», canal `LinkedIn Ads`, `utm_campaign=talent_summit_26`.
- También se puede crear una con `POST /api/v1/campaigns` desde la documentación interactiva (`/docs`), con sesión de `Sales_Lead`.

### Paso 2. Copia el enlace para LinkedIn

**Se enseña:** junto a la campaña, un botón «Copiar enlace para LinkedIn». Copia la dirección del formulario con los parámetros de esa campaña, lista para pegar en el post.

**Existe hoy:** los tres campos UTM de la campaña. Con ellos se forma el enlace: `…/formulario?utm_source=linkedin&utm_medium=social&utm_campaign=<utm_campaign>`.

**Falta:**
- **H-2:** nada construye ese enlace ni lo ofrece para copiar.
- **H-3:** no hay página de formulario propia. La integración `formulario-web` recibe entregas firmadas de un sitio externo, pero ese sitio no forma parte del proyecto.

**Cómo se ensaya hoy:** se escribe el enlace a mano a partir de los UTM de la campaña y se muestra como texto. No lleva a ninguna página.

> Si se usa un formulario Lead Gen nativo de LinkedIn en lugar de un enlace, este paso no hay que construirlo: LinkedIn asocia la respuesta a su campaña y a su anuncio. Además, el formulario admite campos ocultos con valores de seguimiento del estilo UTM. Eso exige cuenta publicitaria o página de empresa, y queda fuera de esta fase.

### Paso 3. El interesado envía su perfil

**Se enseña:** el interesado abre el enlace y rellena un formulario corto. Solo pide lo que LinkedIn sabe de su perfil (regla R-1): nombre, apellidos, correo, empresa, cargo, sector, tamaño de empresa y ciudad. Acepta el aviso de privacidad y lo envía.

**Existe hoy:**
- `POST /api/v1/integraciones/formulario-web/eventos`, que comprueba en este orden: integración activa, límite de entregas, firma HMAC-SHA256 con su propio secreto, validación, registro. Todo en `services/integraciones.py` y `endpoints/integraciones.py`.
- El conector lee `campos.email`, `nombre`, `apellidos`, `empresa`, `cargo`, `industria`, `tamano_empresa`, `ciudad` y `telefono`. La caja de texto libre (`campos.mensaje`) no se copia a ninguna parte.
- Si `aviso_de_privacidad.aceptado` es `true`, la ficha guarda cuándo se aceptó y por qué vía.
- Hay un conector equivalente para LinkedIn Lead Gen (`linkedin-lead-gen`).

**Falta:**
- **H-4:** el conector no lee el UTM. En el ensayo, la dirección de la página traía `utm_campaign=post_ensayo` y la ficha quedó con `campaign_id = NULL`. El UTM sobrevive solo como texto dentro de `activity_data.pagina`, sin vínculo con la campaña. Sin esto no se puede cumplir el paso 6.
- **H-5:** el conector `linkedin-lead-gen` acepta una forma simplificada (`answers.emailAddress`, `consent.privacyPolicy`) que **no es la de la API real**. La respuesta real de `leadFormResponses`:
  - identifica cada respuesta por `questionId`, no por nombre de campo;
  - trae el consentimiento en `formResponse.consentResponses[]`;
  - trae la campaña en `leadMetadata.sponsoredLeadMetadata.campaign`;
  - trae el anuncio en `associatedEntity`, y en `associatedEntityInfo` la referencia a la publicación.

  Cuando haya cuenta, hay que reescribir el conector contra esa forma. Nada de lo demás cambia, porque solo el conector toca la carga.

**Cómo se ensaya hoy:** simulando la entrega del formulario con una petición firmada. La integración viene apagada. Para el ensayo se enciende **solo en el entorno del backend local**, con un secreto generado para la ocasión que nunca se escribe en el árbol:

```text
INTEGRACION_FORMULARIO_WEB_ACTIVA=true
INTEGRACION_FORMULARIO_WEB_SECRETO=<secreto aleatorio del ensayo>
```

La carga del ensayo:

```json
{
  "formulario": "contacto",
  "envio_id": "ensayo-guion-001",
  "enviado_en": "<ahora, ISO 8601>",
  "pagina": "/talento-ti?utm_source=linkedin&utm_medium=social&utm_campaign=post_ensayo",
  "campos": {
    "email": "ana.ensayo@example.com", "nombre": "Ana", "apellidos": "Prueba",
    "empresa": "Ejemplo SA", "cargo": "CTO", "industria": "FinTech",
    "tamano_empresa": "201-1000", "ciudad": "Monterrey"
  },
  "aviso_de_privacidad": { "aceptado": true, "version": "2026-09" }
}
```

La firma va en dos cabeceras:
- `X-PluriOne-Timestamp`: segundos desde 1970, dentro de la ventana de tolerancia.
- `X-PluriOne-Signature`: el HMAC-SHA256 en hexadecimal de `<timestamp>.<cuerpo crudo>`. Es lo que calcula `build_webhook_signature` en `app/core/security.py`.

**Resultado del ensayo** (16-09-2026, sobre una copia desechable de la base demo):

| Comprobación | Resultado |
| :--- | :--- |
| Primera entrega | `200`, `estado: registrada`, `prospecto_creado: true` |
| La misma entrega otra vez | `200`, `estado: duplicada`: no hay segunda actividad ni segunda ficha |
| Actividad | `FORM_SUBMIT`, fuente `formulario_web`, `verificada = true` |
| Texto libre (`mensaje`) | No está en ninguna columna |
| Aviso de privacidad | `privacy_notice_source = formulario_web` |
| `source` de la ficha | `Formulario web` |
| `country` de la ficha | `México` **sin que nadie lo enviara** (H-7) |
| `campaign_id` | `NULL` (H-4) |
| Score | 35,8, `COLD` |
| Asesor asignado | Ninguno (H-6) |

### Paso 4. El sistema crea y puntúa el prospecto

**Se enseña:** sin que nadie toque nada, aparece una ficha nueva con su score, su categoría y la explicación de por qué puntúa así.

**Existe hoy:**
- `registrar_evento` (`services/registro_de_actividad.py`) valida, deduplica por `(source, external_event_id)`, busca la ficha por correo y luego por teléfono, y si no existe la crea **solo con lo que llegó**.
- Lo que no llega queda vacío y puntúa neutro.
- Después calcula y guarda el score (`ScoringService.calculate_and_persist_score`) y su explicación.

**Falta:**
- **H-6:** solo se asigna asesor de forma automática a las fichas `HOT` (`scoring_service.py`). Una ficha `WARM` o `COLD`, como la del ensayo, queda sin dueño hasta que el líder la asigna.
- Tampoco hay pantalla para asignarla: el campo `assigned_rep_id` solo se cambia con `PUT /api/v1/leads/{id}`, y el repositorio lo reserva a quien puede reasignar cartera.

**Cómo se ensaya hoy:** tras el paso 3, la ficha aparece en el listado del líder con su score.

### Paso 5. El asesor la ve en la ficha 360

**Se enseña:** el asesor entra con su cuenta, ve el prospecto en su cartera y abre «Ficha 360». La ficha muestra:
- el score;
- la explicación;
- la procedencia: «Formulario enviado · verificada · Formulario web»;
- el aviso de privacidad aceptado.

**Existe hoy:**
- La ficha 360 (`LeadDetailModal.jsx`) con el historial legible: nombres en español, verificada o declarada, fuente, fecha del hecho.
- La autorización por objeto: un `Commercial_Executive` solo ve fichas asignadas a él.

**Falta:** depende de H-6. Si la ficha no es `HOT`, el asesor no la ve hasta que se le asigna.

**Cómo se ensaya hoy:** hay dos formas.
- El líder asigna la ficha con `PUT /api/v1/leads/{id}` y `{"assigned_rep_id": <id del asesor>}` desde `/docs`, y el asesor la abre con su sesión.
- Para ahorrarse la asignación, se usa en el paso 3 un perfil que salga `HOT`: se asigna solo, al asesor activo de mayor capacidad.

### Paso 6. El líder compara publicaciones

**Se enseña:** en el panel de analítica, una tabla con una fila por publicación. Cada fila muestra prospectos captados, cuántos son `HOT`, el score medio y la conversión, junto al presupuesto.

**Existe hoy:**
- `GET /api/v1/analytics/campaigns`, solo para `Sales_Lead` y `System_Admin`, calculado en una sola consulta. Las campañas sin captación siguen apareciendo, con ceros.
- La tabla en `AnalyticsCharts.jsx`.

**Falta:**
- **H-4** otra vez: el informe cuenta prospectos por `Lead.campaign_id`, y ninguna integración lo rellena. Una publicación de LinkedIn con cien respuestas aparece con **cero** prospectos. Es el hueco que rompe la historia.
- **H-8:** el informe mide «campaña», no «publicación». Si una campaña tiene varios posts, no se pueden comparar entre sí (ver R-2).

**Cómo se ensaya hoy:** solo con las campañas sembradas, cuyos prospectos se asignaron a campaña al sembrar. No se puede enseñar que el prospecto del paso 3 sume en su publicación.

---

## 3. Reglas del proyecto

Rigen desde este documento. Si una propuesta choca con una regla, se cambia la propuesta. Si lo que hay que cambiar es la regla, se cambia aquí, por escrito y con el motivo.

### R-1. No pedir nada que LinkedIn no dé

**La regla:** el formulario de captación solo pide datos que LinkedIn puede entregar a partir del perfil. No se añaden preguntas que obliguen al interesado a escribir lo que su perfil ya sabe, ni datos que su perfil no sabe.

**Por qué:**
- Cada pregunta extra reduce las respuestas.
- Un dato que el interesado teclea a mano es menos fiable que el de su perfil.
- El mismo formulario tiene que poder pasar a Lead Gen nativo (paso 2) sin rediseñarse.

**Qué da LinkedIn** (documentación de Lead Sync, versión 2026-09):

| Mecanismo | Qué entrega | Requisito |
| :--- | :--- | :--- |
| Formulario Lead Gen, campos predefinidos (`PredefinedField`) | **Contacto:** `FIRST_NAME`, `LAST_NAME`, `EMAIL`, `PHONE_NUMBER`, `CITY`, `STATE`, `COUNTRY`, `ZIP_CODE`.<br>**Trabajo:** `JOB_TITLE`, `JOB_FUNCTION`, `SENIORITY`, `COMPANY_NAME`, `COMPANY_SIZE`, `INDUSTRY`, `WORK_EMAIL`, `WORK_PHONE_NUMBER`, `LINKEDIN_PROFILE_LINK`.<br>**Estudios:** `DEGREE`, `FIELD_OF_STUDY`, `SCHOOL`, `START_DATE`, `GRADUATION_DATE`.<br>**Otros:** `GENDER`.<br>Además, casillas de consentimiento y campos ocultos de seguimiento. | Cuenta publicitaria o página de empresa, y acceso a la API de Lead Sync |
| «Iniciar sesión con LinkedIn» (OpenID Connect) | Identificador, nombre, foto y correo. **Nada de cargo, empresa, sector ni tamaño.** | Una aplicación de LinkedIn |

**Cómo se aplica:**
- Los campos del formulario del paso 3 son un subconjunto de la primera fila.
- **Ingresos anuales no está**: LinkedIn no lo da, así que no se pide. El modelo ya trata su ausencia como ausencia desde el capítulo 24.
- «Iniciar sesión con LinkedIn» no sirve para rellenar el perfil comercial, y no se propone como si sirviera.
- El género y los estudios, aunque LinkedIn los da, no se piden: el modelo no los usa, y pedirlos iría contra la minimización de la Fase 15.

**Dónde choca hoy:**
- El alta manual (`NewLeadModal.jsx`) ya no pide ingresos, pero sí un nivel de urgencia como campo personalizado, y LinkedIn no lo da. Es el formulario del asesor, no el de captación, y la regla no lo alcanza, pero ese campo no debe copiarse al de captación.
- Los valores exactos con que LinkedIn rellena `COMPANY_SIZE` e `INDUSTRY` no están en la documentación pública. Se conocerán con la primera respuesta de prueba (`testLead`) y se traducirán en el conector (R-3).

### R-2. No crear conceptos paralelos

**La regla:** antes de añadir una tabla, un campo o una palabra nueva, se busca el concepto que ya existe y se usa ese. Un concepto nuevo solo entra si lo que se quiere guardar no cabe en ninguno de los que hay, y se escribe por qué.

**Por qué:**
- Dos tablas de personas (`sales_reps` y `users`) hicieron imposible comprobar de quién era un prospecto hasta que se unificaron (capítulo 15).
- Un único «tipo» para WhatsApp y LinkedIn hizo que el historial afirmara el canal equivocado (capítulo 21).
- Cada duplicado acaba en un informe que no cuadra.

**Cómo se aplica a esta historia:**

| En la historia | Se usa | No se crea |
| :--- | :--- | :--- |
| Publicación | `Campaign` | Una tabla `Publicacion` o `Post` |
| Enlace de la publicación | `Campaign.utm_source`, `utm_medium` y `utm_campaign` | Un campo «enlace» o «código de post» |
| Interesado | `Lead` | Un «contacto de LinkedIn» aparte |
| Lo que hizo | `LeadActivity`, creada solo por `registrar_evento` | Un registro de «respuestas de formulario» |
| De dónde vino | `Lead.campaign_id` (qué campaña) y `LeadActivity.source` (qué sistema lo entregó) | Un cuarto campo de origen |
| Evento sin ficha | La bandeja «Sin asociar» (`unmatched_events`) | Otra cola |

**Dónde choca hoy:**
- Ya hay tres nociones de origen que se solapan:
  - `Lead.source`, texto libre («Formulario web», «LinkedIn Ads»…);
  - `Campaign.channel`, texto libre;
  - `LeadActivity.source`, la fuente registrada.

  No se añade una cuarta. Qué hacer con `Lead.source` se decide cuando se cierre H-4.
- **H-8:** si un día una campaña tiene varios posts que haya que comparar, la primera opción es «un post, una campaña». Una entidad nueva solo entra si eso no basta, y con su justificación escrita aquí.

### R-3. Las listas del formulario, iguales a las del modelo

**La regla:** todo campo de lista que llegue al modelo como variable categórica (`job_title`, `industry`, `company_size`, `source_channel`) ofrece en el formulario **exactamente** los valores con los que se entrenó el modelo. Esas listas se definen en un único sitio, que leen el formulario, el conector, las reglas del heurístico y el entrenamiento. Lo que llega de fuera con otro vocabulario (LinkedIn, un CRM) se traduce **en el conector**, nunca en el modelo.

**Por qué:**
- El preprocesador descarta las categorías que no vio al entrenar (`OneHotEncoder(handle_unknown="ignore")`). Un sector escrito de otra forma no produce un error: el modelo deja de verlo, sin avisar.
- Ya pasó con las columnas del vector (ML-4) y por eso existe `core/vector_del_modelo.py`. Con los valores de las listas todavía no se ha hecho.

**Dónde choca hoy** (revisado el 16-09-2026):

| Campo | Modelo (`synthetic_generator.py`) | Alta (`NewLeadModal.jsx`) | Ficha 360 (`LeadDetailModal.jsx`) | Conectores |
| :--- | :--- | :--- | :--- | :--- |
| `industry` | 10 valores en inglés: `FinTech`, `Software/TI`, `Banking`, `E-Commerce`, `Healthcare`, `Logistics`, `Retail`, `Consulting`, `Manufacturing`, `Education` | 11 valores, texto libre; solo `FinTech` y `Software/TI` coinciden | 10 valores distintos de los otros dos; coinciden `FinTech`, `Software/TI` y `Logistics` | Lo que envíe el sistema de origen |
| `company_size` | `1-10`, `11-50`, `51-200`, `201-1000`, `1000+` | Los mismos cinco | Los mismos cinco, más «Sin indicar» | Lo que envíe el sistema de origen. Las reglas del heurístico aceptan además `201-500`, `501-1000` y `1000 o más` |
| `source_channel` | `LinkedIn Ads`, `Webinar`, `Demo Request Form`, `Organic Search`, `Outbound Cold Email`, `Referral` | 7 valores; solo `LinkedIn Ads` y `Webinar` coinciden | — | `Formulario web` y `LinkedIn Lead Gen`, que el modelo nunca vio |
| `job_title` | 13 cargos | Texto libre | Texto libre | Texto libre |

El cargo es texto libre en todas partes, y en LinkedIn también. Para él la regla se aplica al revés: no se convierte en lista, y lo que se alinea es su tratamiento (las palabras clave del heurístico y cómo lo agrupa el modelo).

### R-4. No sobrescribir ni inventar datos

**La regla:**
- Un dato ausente se guarda como ausente: ni un valor por defecto que parezca real, ni el de otra ficha.
- Un dato que ya está en una ficha no lo pisa una entrega automática. Si lo nuevo difiere, se conserva lo que había y la diferencia queda visible para que una persona decida.
- Lo que escribe una persona a mano no lo cambia ninguna integración.

**Por qué:**
- Un cero en ingresos se leía como «factura poco», y un «Tecnología» inventado sumaba 15 puntos (capítulos 21 y 24).
- Un score construido sobre datos supuestos no se puede defender ante el asesor ni ante el titular de los datos.

**Lo que ya la cumple:**
- `_crear_prospecto` no inventa sector, tamaño, ingresos ni nombres.
- El aviso de privacidad conserva la primera aceptación.
- Un evento tardío no mueve la última actividad hacia atrás.
- La guarda de CI «El registro no inventa ni supone» impide reintroducir los valores inventados conocidos.

**Dónde choca hoy:**
- **H-7, país inventado:** `_crear_prospecto` escribe `country = "México"` cuando no llega país, y `LeadBase.country` tiene el mismo valor por defecto. El ensayo lo confirmó.
- **H-7, canal inventado:** `LeadBase.source` vale `"Website"` por defecto, y `scoring_service.py` usa `"Website"` como canal cuando la ficha no tiene fuente.
- **H-9, sobrescritura:** si la persona vuelve a enviar un formulario, `_actualizar_prospecto` reemplaza `job_title`, `company`, `industry`, `company_size` y `annual_revenue` de la ficha existente con lo que llegue no vacío. Pisa también lo que el asesor corrigió a mano.

### R-5. No más endurecimiento salvo fallos reales

**La regla:** a partir de aquí no se añaden defensas, guardas de CI, validaciones ni restricciones de seguridad **por anticipación**. Se añaden cuando hay un fallo real:
- se reproduce con una prueba que falla;
- o lo reporta una auditoría de dependencias (`pip-audit`, `npm audit`) sobre algo que se instala;
- o ocurrió en un entorno en uso.

El esfuerzo va a que la historia de la sección 2 funcione de punta a punta.

**Por qué:**
- Las Fases 11 a 23 dejaron el sistema con 34 pasos en el trabajo de CI «Configuración peligrosa», sesiones verificables, revocación inmediata, minimización y retención.
- Mientras tanto, la historia que justifica el sistema (sección 2) tiene un paso que no se puede enseñar (H-4).
- Seguir endureciendo sin un fallo delante es trabajo que no acerca el producto a quien lo va a usar.

**Cómo se aplica:**
- Una propuesta de endurecimiento tiene que citar el fallo: la prueba que falla, el aviso de auditoría o el incidente. Sin eso, no entra.
- **Lo que ya existe se mantiene.** La regla no autoriza a retirar guardas, a relajar las restricciones de seguridad de fases anteriores ni a saltarse las que ya están. Las reglas de secretos, sesiones y datos personales siguen vigentes.
- Si una pieza nueva de la historia (una pantalla, un conector) necesita autenticación, autorización o firma, usa los mecanismos que ya existen. Eso es construir la pieza, no endurecer.

---

## 4. Huecos detectados

> **Actualización, fase 1 «Publicaciones» (17-09-2026).**
> - La publicación es una `Campaign` con `channel = "LinkedIn"`, tal como fija R-2.
> - La campaña gana `description`, `target_audience` y `public_slug`, con la migración `b7e41c9d2f60` y su reversión.
> - El slug es aleatorio (128 bits), lo genera el servidor, ninguna edición lo cambia y tiene índice único.
> - La pestaña «Publicaciones» permite crear, editar, activar, desactivar y copiar el texto con el enlace.
> - Crean y editan `Sales_Lead` y `System_Admin`; el asesor consulta y copia.
> - Siguen abiertos H-3 (la página a la que lleva el enlace) y H-4 (enlazar la ficha con su publicación). H-4 tendrá ya el slug para resolver la campaña.

> **Actualización, fase 2 «Página de interés» (17-09-2026).**
> - `/interes/{slug}` es la única pantalla sin sesión: enseña el título y el texto de la publicación y funciona en un teléfono.
> - El formulario es de listas cerradas y sin texto libre. Cargo, sector y tamaño son **las listas del modelo**, declaradas en `CATEGORIAS_DEL_MODELO` y comparadas por `tests/test_categorias_del_modelo.py` contra el artefacto servido y contra el generador del dataset: es la prueba que pedía R-3.
> - Ruta propia, no conector firmado: límite por IP y por publicación, campo trampa, validación estricta, «no disponible» y la misma respuesta exista o no el correo.
> - Por dentro usa `registrar_evento` con la fuente `pagina_de_interes`, que **no actualiza** una ficha que ya existe: la solicitud se suma al historial y no pisa lo que escribió el asesor (H-9 sigue abierto para el resto de fuentes).
> - **H-3 cerrado** y **H-4 cerrado para este camino**: la ficha nace atribuida a su publicación (`campaign_id`). Las integraciones (`formulario_web`, `linkedin_lead_gen`, Calendly, WhatsApp) siguen sin atribuir.
> - Queda una tensión con R-1 que decide el negocio: el formulario pide **tramo de facturación**, y LinkedIn no da ese dato, así que nunca se podrá rellenar solo. Es opcional, y el tramo se guarda como tramo: `annual_revenue` queda vacío.
> - El canal de la ficha es `LinkedIn`, que es la verdad, pero el modelo aún no lo conoce (conoce `LinkedIn Ads`, que es publicidad pagada): hasta el próximo reentrenamiento cuenta como canal desconocido, es decir, neutro.

> **Actualización, fase 3 «Ficha 360 e informe por publicación» (17-09-2026).**
> - La ficha 360 trae la tarjeta **«Llegó por»**: la publicación con su enlace, la fecha, qué necesita, el perfil de LinkedIn en otra pestaña y el consentimiento con su fecha. Sin solicitudes no se pinta (`llego_por` viaja como `null`).
> - Quien respondió a varias publicaciones las ve todas: la tarjeta se arma con las **solicitudes** (`lead_activities` de la fuente `pagina_de_interes`), no con `campaign_id`, que se fija al crear la ficha y no se vuelve a tocar.
> - Cada publicación tiene su **informe**: perfiles recibidos, cuántos avanzaron de etapa —salieron de `NEW`— y score medio; debajo, la tabla ordenada por score con nombre, empresa, cargo, score, etapa, asesor y fecha, filtrable por etapa y por días, y cada nombre abre su ficha 360.
> - En el informe entra tanto quien está atribuido a la campaña como quien envió su perfil por su enlace, por lo mismo que la tarjeta.
> - **Alcance:** el asesor ve los suyos y un número con el resto (`de_otros_asesores`), sin un solo nombre; el líder y el administrador, la publicación entera. Una campaña que no es publicación responde 404. Una publicación desactivada **sí** conserva su informe: se desactiva para dejar de recibir perfiles, no para borrar los que trajo.
> - La consulta queda en la bitácora (`publicacion.informe`) con sus filtros y el número de filas, **nunca con las filas**: la bitácora se lee con otro criterio de acceso que la cartera.
> - La **comparativa** entre publicaciones y el contador **«Nuevos desde LinkedIn sin asesor»** son de dirección. La comparativa no se acota por cartera —hacerlo ordenaría asesores, no publicaciones— y `tests/test_informe_de_publicaciones.py` comprueba que sus números coinciden con los del informe, que se calculan por otro camino.
> - **H-6 a medias:** ya hay dónde repartir. La ficha 360 ofrece «Asignar asesor» a quien puede reasignar, que es lo que faltaba para recorrer la demo sin tocar la base a mano. La asignación **automática** sigue siendo solo para las fichas `HOT`.
> - **H-8 cerrado**: la comparativa compara publicaciones, que es lo que R-2 decidió que fueran las campañas de LinkedIn.

> **Actualización, fase 4 «Probar con personas» (17-09-2026).**
> - El guion por rol, la hoja de observación y cómo dejar la pila lista están en `docs/Prueba_Con_Personas.md`; `scripts/preparar_prueba_con_personas.py --force` regenera los datos y añade una publicación de ejemplo con perfiles ya recibidos.
> - Del ensayo previo salieron tres atascos, y los tres están corregidos: **el enlace copiado no llevaba a la página** (`PUBLICACIONES_URL_BASE` apuntaba a `/p` y la ruta es `/interes`, ahora con una prueba que compara las dos), **el perfil de LinkedIn se rechazaba pegado tal cual** (se completa el esquema y se quitan los parámetros de compartir; el campo ya no es `type="url"`) y **el error enseñaba «Value error,»** delante del mensaje.
> - Queda anotado para mirar con personas, sin tocarlo todavía: la marca «Nuevo desde LinkedIn» desaparece en cuanto el prospecto tiene asesor, que es justo cuando el asesor va a buscarlo, y el contador de sin asignar vive en «Publicaciones» y no en el tablero.

> **Actualización, «Formulario de 30 segundos sin datos supuestos» (21-09-2026).**
> - Obligatorio solo nombre (un campo), correo, empresa, cargo, tamaño y sector —las listas del modelo—, «¿Qué necesitas?» con botones de un toque y el aviso. Teléfono y perfil de LinkedIn, opcionales y plegados bajo «Añadir más datos».
> - **Se resuelve la tensión con R-1** de la fase 2: la facturación sale del formulario. `annual_revenue` queda vacío y un cliente que la siga mandando recibe 422.
> - «¿Qué necesitas?» **no puntúa**. Toda solicitud se registra como `FORM_SUBMIT`; antes «Ver una demostración» era `DEMO_REQUEST` y sumaba 25 puntos en la regla y `requested_demo` en el modelo. La necesidad se guarda en la solicitud y se lee en la tarjeta «Llegó por» y en la columna «Necesita» del informe.
> - El heurístico deja de suponer: un tamaño, cargo o sector que faltan puntúan el punto medio de su bloque (6, 15 y 10,5), no «1-10» ni la base de un estudiante. Lo mismo en el servicio, el simulador y la línea base del pipeline.
> - Queda escrito el país: la columna `country` sigue rellenándose con «México» (H-7). No puntúa en ninguna de las dos mitades del score; quitarlo exige una migración.

> **Actualización, capítulo 26 «Publicaciones completas» (22-09-2026).**
> - Paso 1: la publicación puede nacer en **borrador**, con fecha de cierre, asesor responsable, sus propias opciones de «¿Qué necesitas?» (de 2 a 5) y la dirección del post ya publicado. Sin decir nada nace activa, como antes, para que el guion no cambie.
> - Paso 2: antes de copiar, **«Vista previa del post»** enseña el corte de «ver más» y avisa si el enlace queda escondido detrás o si el texto pasa de 3 000 caracteres; **«Ver la página»** enseña la página tal como la verá el interesado, en cualquier estado y sin contar visita.
> - Paso 3: fuera de «activa» —borrador, pausada, cerrada o vencida— la página responde «no disponible». La página se abre y se cuentan visitas: un número por día, sin cookies ni datos.
> - Paso 5: con responsable, la ficha nueva ya llega asignada y no pasa por el contador del líder. **H-6 avanza**: se reparte solo por publicación, además de las `HOT`.
> - Paso 6: el informe suma estado, responsable, enlace al post, visitas, tasa de envío y el gráfico de perfiles por día; la comparativa, visitas y tasa. **«Duplicar publicación»** da un borrador con enlace propio.
> - Detalle en el capítulo 26 de la Memoria (`docs/reportes/Reporte_26_...`).

> **Actualización, capítulo 27 «Una publicación, varias redes» (22-09-2026).**
> - Paso 1: la publicación se difunde por varias **redes**. Vienen activadas LinkedIn, WhatsApp, Facebook y correo; Instagram y X se activan si se quieren. Sin tocar nada, el guion no cambia.
> - Paso 2: además de «Copiar texto para LinkedIn», **«Compartir en redes»** da el enlace y el texto de cada red —X recortado a 280 contando el enlace—, su botón oficial de compartir, «Copiar texto» donde la red no se lleva el texto, y un **código QR** descargable para Instagram y material impreso. No se publica nada por nosotros: abre la red con la sesión de quien pulsa.
> - Paso 3: el enlace de cada red lleva a la **misma** página, con `?r=whatsapp` al final. Una red inventada o manipulada no rechaza a nadie: se cuenta como «sin red».
> - Paso 5: la ficha guarda el **canal de la red de llegada** («WhatsApp», «Facebook»…) y la ficha 360 dice «Llegó por la publicación X, vía WhatsApp». Ninguno de esos canales lo conoce el modelo, así que el score no se mueve.
> - Paso 6: el informe añade una **fila por red** con visitas, envíos, tasa, perfiles y score medio.
> - Detalle en el capítulo 27 de la Memoria (`docs/reportes/Reporte_27_...`).

> **Actualización, capítulo 28 «El sistema dice qué hacer hoy» (23-09-2026).**
> - Cierra las **dos notas** que la prueba con personas había dejado «para mirar con lupa»: el asesor ya no busca lo nuevo en una lista ordenada por score, y el líder ya no busca un contador escondido en otra pestaña. El panel abre en **«Hoy»** y dice qué toca.
> - Seis reglas corren en la pasada diaria que ya existía: primer contacto al asignar, volver a llamar cuando nadie contesta, recordatorio la víspera de una reunión, aviso al asesor cuando un HOT lleva horas sin contacto, escalado al líder cuando ese aviso no bastó, y marca de dormido tras un mes de silencio.
> - Nada sale del panel: ni correo, ni WhatsApp, ni servicios externos. Los avisos viven en una **campana** en la barra.
> - Una llamada contestada cierra «volver a llamar» en el momento de registrarla, no al día siguiente. Marcar una tarea hecha solo puede hacerlo su dueño, aunque el líder la vea.
> - El paso 5 del guion cambia: después de asignar, el asesor **no busca la ficha**; la encuentra en «Hoy», con el motivo escrito y un clic hasta la ficha 360. El ensayo automático recorre ese camino.
> - Detalle en el capítulo 28 de la Memoria (`docs/reportes/Reporte_28_...`).

Ninguno se corrige en este documento. Van en orden de dependencia para la demo.

| Id | Hueco | Paso afectado | Regla |
| :--- | :--- | :---: | :---: |
| **H-4** | **Parcial.** La página de interés ya atribuye la ficha a su publicación; las integraciones (`formulario_web`, `linkedin_lead_gen`, Calendly, WhatsApp) siguen sin rellenar `Lead.campaign_id` | 3, 6 | R-2 |
| ~~H-1~~ | ~~No hay pantalla para crear o editar campañas~~. **Cerrado en la fase 1 «Publicaciones»**: pestaña «Publicaciones» | 1 | — |
| ~~H-3~~ | ~~No hay página de formulario propia~~. **Cerrada en la fase 2**: `/interes/{slug}` | 2, 3 | R-1 |
| ~~H-2~~ | ~~Nada construye ni ofrece el enlace~~. **Cerrado en la fase 1**: enlace público con slug y botón «Copiar texto para LinkedIn». No usa UTM, porque el slug ya identifica la campaña | 2 | R-2 |
| H-7 | País `México` y canal `Website` escritos por defecto cuando no llegan | 3, 4 | R-4 |
| H-9 | Una segunda entrega reemplaza cinco campos de la ficha existente. La página de interés ya no lo hace; `formulario_web`, `linkedin_lead_gen` y el CRM sí | 4 | R-4 |
| H-6 | **Parcial.** Ya se asigna desde la ficha 360 y el líder ve cuántos esperan («Nuevos desde LinkedIn sin asesor»); la asignación automática sigue siendo solo para las `HOT` | 4, 5 | — |
| — | Los vocabularios de industria, tamaño y canal no coinciden entre modelo, formularios y conectores | 3, 4 | R-3 |
| H-5 | El conector `linkedin-lead-gen` no acepta la forma real de `leadFormResponses` (necesita cuenta) | 3 | R-1 |
| ~~H-8~~ | ~~El informe compara campañas, no publicaciones~~. **Cerrado en la fase 3**: comparativa por publicación, con su informe y su tarjeta en la ficha | 6 | R-2 |

---

## 5. Fuentes

- Documentación de LinkedIn, Lead Sync:
  - [Lead Syncing](https://learn.microsoft.com/en-us/linkedin/marketing/lead-sync/leadsync?view=li-lms-2026-09): permisos, forma de `leadFormResponses`, campaña y anuncio asociados.
  - [Lead Syncing Schema](https://learn.microsoft.com/en-us/linkedin/marketing/lead-sync/lead-sync-schema?view=li-lms-2026-09): `PredefinedField`, campos ocultos, consentimientos, `LeadType`.
- Documentación de LinkedIn: [Sign In with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), con los alcances `openid`, `profile` y `email`.
- Código revisado: `services/integraciones.py`, `services/registro_de_actividad.py`, `services/scoring_service.py`, `services/analytics_service.py`, `api/v1/endpoints/campaigns.py`, `api/v1/endpoints/analytics.py`, `core/vector_del_modelo.py`, `core/scoring_rules.py`, `schemas/lead.py`, `ml_pipeline/src/synthetic_generator.py`, `ml_pipeline/src/feature_engineering.py`, `frontend/src/components/NewLeadModal.jsx`, `LeadDetailModal.jsx`, `AnalyticsCharts.jsx` y `frontend/src/services/api.js`.
