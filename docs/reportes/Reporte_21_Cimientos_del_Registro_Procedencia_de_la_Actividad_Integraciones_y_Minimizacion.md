# Capítulo 21: Cimientos del Registro — Procedencia de la Actividad, Integraciones y Minimización

## 21.1. Por qué existe esta fase

El score de un prospecto se alimenta de lo que el sistema anota que ha pasado con él: qué
formulario envió, cuántas llamadas hubo, si se le mandó una propuesta. Los capítulos
anteriores se ocuparon de cómo se calcula el score, de quién puede verlo y de cuánto tiempo
se guarda. Esta fase mira un paso antes: **cómo entra en el sistema lo que el score cuenta**.

Al leer ese camino de punta a punta aparecieron defectos que no eran de ningún módulo
concreto:

* **Tres caminos para escribir una actividad, cada uno con sus reglas.** El panel escribía
  lo que mandara el cliente. El webhook del CRM traducía el tipo por su nombre y, si no lo
  conocía, registraba un `FORM_SUBMIT` y lo anotaba en el registro de texto. El alta de un
  prospecto por webhook rellenaba lo que faltaba.
* **Datos inventados que puntuaban.** Un alta del CRM sin industria entraba como
  «Tecnología», que son 15 puntos de ajuste; sin tamaño, como «1-10»; sin empresa, como
  «Empresa no identificada»; sin nombre, como «Prospecto Sin Apellido».
* **Nada decía de dónde venía cada actividad.** Una reunión confirmada por un sistema y una
  que el asesor declaró eran la misma fila. Un mismo aviso del CRM reentregado fuera de la
  ventana de idempotencia de 15 minutos entraba dos veces.
* **Un «peso» sin efecto.** Cada actividad guardaba `activity_weight`, que mandaba el cliente
  y que el scoring no leyó nunca. El panel lo enseñaba en el historial («Peso: 25 pts») y lo
  prometía en el selector («Envío de propuesta, +25 pts»).
* **Tipos que mezclaban cosas distintas.** «Mensaje de WhatsApp / LinkedIn» era un solo tipo,
  y una llamada a buzón contaba como una conversación.
* **La propuesta se declaraba dos veces.** El asesor pasaba el prospecto a «Propuesta
  enviada» y además registraba la actividad «Envío de propuesta».

La fase se organizó en dos bloques. El de **datos**: procedencia, un solo camino, nada
inventado, tipos correctos, teléfonos normalizados, integraciones con secreto propio y
minimización. El de **la ficha**: lo que el asesor ve y registra.

---

## 21.2. Procedencia en cada actividad

### Columnas

| Columna | Qué dice | Antes |
| :--- | :--- | :--- |
| `source` | `manual`, `pipeline`, `crm`, `formulario_web`, `linkedin_lead_gen`, `calendly` o `whatsapp` | No existía |
| `external_event_id` | El identificador que le dio el sistema de origen; nulo en lo que registra una persona | No existía |
| `verificada` | Verdadero si lo vio un sistema; falso si lo declaró una persona | No existía |
| `occurred_at` | Cuándo ocurrió | `timestamp`, que valía también para cuándo se registró |
| `created_at` | Cuándo se registró | Igual |
| `direction` | En los mensajes: `ENTRANTE` o `SALIENTE` | No existía |
| `call_outcome` | En las llamadas: `CONECTO`, `NO_CONTESTO` o `BUZON` | No existía |
| `activity_weight` | — | Retirada |

`source` es texto y no un tipo enumerado de la base. Añadir una integración no debe exigir
una migración con `ALTER TYPE`. La lista válida vive en el código, en un único sitio.

### Índice único permanente

`(source, external_event_id)` es único en la base. La deduplicación del webhook del
capítulo 14 dura quince minutos: protege de una repetición, pero un aviso que el CRM
reentrega al día siguiente volvía a entrar. El índice lo impide para siempre. Los nulos de
lo registrado a mano no chocan entre sí, ni en PostgreSQL ni en SQLite.

El servicio comprueba antes de escribir y devuelve «duplicada» con la actividad original,
sin volver a puntuar. El índice cubre la carrera entre dos entregas simultáneas: la segunda
falla al confirmar y se resuelve como duplicado.

### La migración de lo existente

`e3a9c41d7b25` no puede saber de dónde vino cada fila antigua. Usa lo único que lo dice:
la ingesta del CRM escribía la actividad con la plataforma como canal y dejaba un registro
de integración del mismo prospecto. Cuando las dos cosas coinciden, la fila se marca como
`crm` verificada. Todo lo demás se marca como `manual` declarada, que es lo prudente: no
afirma que un sistema viera algo que quizá declaró una persona.

La reversión conserva los datos, pero pierde la procedencia. Los mensajes de LinkedIn vuelven
a `WHATSAPP_MESSAGE`, que es como se registraban. En PostgreSQL el valor
`LINKEDIN_MESSAGE` se queda en el tipo enumerado: un tipo no admite retirar valores sin
recrearlo.

---

## 21.3. Un solo camino: `registrar_evento()`

El panel, el cambio de etapa, el webhook del CRM, los conectores y la vinculación desde la
bandeja construyen un `Evento` y lo entregan a
`app/services/registro_de_actividad.registrar_evento`. Es la única función que construye
filas de `lead_activities`.

| Decisión | Regla |
| :--- | :--- |
| ¿Es válido? | Tipo conocido y admitido para su fuente; resultado en las llamadas; dirección en los mensajes; fecha no futura (5 min de tolerancia); teléfono en E.164. Si no, `EventoInvalido` con motivo y campo, que los endpoints dan como **422** |
| ¿Ya estaba? | Por `(source, external_event_id)`, en las actividades y en la bandeja |
| ¿De quién es? | Por correo; si no hay correo, por teléfono |
| ¿Crea ficha? | Solo si la fuente genera prospectos: formularios, LinkedIn Lead Gen y CRM |
| ¿Qué se guarda? | Los datos pasan por `minimizar` antes de escribir nada |
| Después | Recalcula el score y devuelve el anterior y el nuevo |

| Fuente | Crea ficha | Verificada | Tipos |
| :--- | :---: | :---: | :--- |
| `manual` | No | No | Todos salvo propuesta y reunión |
| `pipeline` | No | No | Propuesta enviada y reunión agendada |
| `crm` | Sí | Sí | Todos |
| `formulario_web` | Sí | Sí | Formulario, solicitud de demo, descarga |
| `linkedin_lead_gen` | Sí | Sí | Formulario |
| `calendly` | No | Sí | Reunión agendada |
| `whatsapp` | No | Sí | Mensaje de WhatsApp |

Que no haya un segundo camino no es una convención: una prueba recorre `backend/app` y exige
que el único fichero que construye `LeadActivity(` sea el servicio, y una guarda del CI
comprueba lo mismo. El repositorio de actividades queda de solo lectura. Un endpoint que
escribiera actividades por su cuenta se saltaría la validación, la deduplicación y la
minimización, y ninguna prueba de ese endpoint lo notaría.

---

## 21.4. Lo que no llega no se inventa

### El alta desde el CRM

Lo que no viene queda vacío: sin industria, sin tamaño, sin empresa, sin cargo, y con el
nombre vacío si no llegó. Vacío puntúa neutro:

| Variable | Vacía | Antes, inventada |
| :--- | :--- | :--- |
| Industria (regla) | 7 puntos, la base de las industrias no listadas | 15 puntos («Tecnología») |
| Tamaño (regla) | 2 puntos, la base | 2 puntos («1-10», por casualidad el mismo valor) |
| Tamaño (modelo) | Categoría desconocida: el codificador la ignora | La categoría «1-10», que sí aprendió |

El extractor de variables también suponía «1-10» para cualquier ficha sin tamaño, no solo
para las del CRM. Ahora pasa la cadena vacía. La respuesta de la API admite nombre vacío:
con el mínimo de longitud heredado de la entrada, una sola ficha así habría convertido el
listado entero en un error.

### Tipo desconocido o ausente

`LEAD_MAGICO` responde **422** con los tipos admitidos, y nada se escribe. Una carga sin
`activity_type` también responde 422, con el motivo «Falta el tipo de actividad». Antes el
primer caso se registraba como `FORM_SUBMIT`, y el segundo como `FORM_SUBMIT` si el
prospecto era nuevo o `PAGE_VIEW` si no lo era.

### Correos desconocidos: la bandeja «Sin asociar»

Un mensaje de WhatsApp de un número que no está en ninguna ficha, o una reunión de Calendly
con un correo desconocido, ya no crean prospecto. Van a `unmatched_events`, con lo mínimo
para reconocer a la persona: correo, teléfono y nombre si llegaron.

| Ruta | Quién | Qué hace |
| :--- | :--- | :--- |
| `GET /api/v1/eventos-sin-asociar` | `Sales_Lead`, `System_Admin` | Lista, lo más reciente primero |
| `POST /api/v1/eventos-sin-asociar/{id}/vincular` | Ídem | Lo convierte en actividad del prospecto elegido, conserva fuente y verificación, y lo retira |
| `DELETE /api/v1/eventos-sin-asociar/{id}` | Ídem | Lo borra; en la bitácora queda la fuente y el tipo |

Un asesor no la atiende: enseña datos de personas que todavía no son cartera de nadie, y
vincular es decidir de quién es un dato. Vincular conserva `verificada`: lo decide una
persona, pero lo vio WhatsApp. Lo que decide la persona es a quién pertenece, no si ocurrió.

La bandeja no tiene clave foránea a `leads`, así que el mapa de tablas del capítulo 20 no la
alcanza. La exportación y la supresión la buscan por correo y teléfono; la prueba de
supresión lo comprueba.

---

## 21.5. Tipos, llamadas y el modelo registrado

### LinkedIn separado de WhatsApp

`LINKEDIN_MESSAGE` es un tipo propio. El modelo registrado, sin embargo, se entrenó con una
sola variable, `whatsapp_messages`, que en la práctica medía «WhatsApp o LinkedIn», porque
así se declaraba. Si la variable pasara a contar solo WhatsApp, el modelo recibiría una
distribución distinta de la que aprendió sin que ningún gate lo detectara.

Hasta el siguiente reentrenamiento, `whatsapp_messages` se alimenta con **mensajes
directos**: WhatsApp y LinkedIn. El nombre de la variable no cambia y el artefacto sigue
siendo válido. Separarlas en el modelo exige reentrenar, y ese reentrenamiento tiene que
pasar el gate de métricas y la condición de publicación del capítulo 19.

### Resultado de llamada

Solo `CONECTO` es una conversación. Un `NO_CONTESTO` o un `BUZON` quedan en el historial y
no suman. Antes, dos intentos a buzón alcanzaban el tope de la regla (16 puntos).

**Consecuencia sobre lo existente:** las llamadas anteriores a la fase no tienen resultado y
**dejan de contar** en el siguiente recálculo. Contarlas como conectadas habría supuesto un
dato que nadie registró. La migración informa de cuántas hay.

### El pipeline registra por sí mismo

Pasar a «Propuesta enviada» o «Reunión agendada» registra la actividad con fuente `pipeline`
y la marca de declarada. Guardar otra vez la ficha en esa misma etapa no la duplica. El
asesor ya no puede declarar esos dos tipos a mano: responde 422 con el motivo. La reunión
verificada llega por Calendly; la del pipeline es la declaración de quien cambió la etapa.

---

## 21.6. Teléfonos en E.164

El teléfono se valida y normaliza con `phonenumbers` al guardar: en el alta, en la edición,
en el CRM y en los conectores. «55 1234 5678», «+52 (55) 1234-5678» y «5512345678» se
guardan como `+525512345678`. Lo que no es un número se rechaza con 422, y el mensaje de error
no repite el número, porque puede acabar en el registro del servidor. Sin prefijo se asume
México.

### Hallazgo: el «1» de WhatsApp

WhatsApp identifica a los móviles mexicanos con el «1» que México retiró en 2019:
`5215512345678`. `phonenumbers` lo da por inválido, y con razón. Sin corregirlo, **cada
mensaje de WhatsApp de un móvil mexicano se habría rechazado** y nunca habría casado con la
ficha que guarda `+525512345678`. Se vio al contrastar la biblioteca con los formatos reales
antes de escribir el conector. Ahora se retira ese «1» antes de validar.

### Lo existente

La migración normaliza los teléfonos de `leads`: los vacíos pasan a nulo y los que no tienen
forma de número **se dejan como estaban**, contados en la salida de la migración. Borrarlos
sería perder un dato que alguien escribió. Por eso la validación está en la entrada y no en la
respuesta: si estuviera en la respuesta, abrir esa ficha daría un error.

---

## 21.7. Integraciones

`POST /api/v1/integraciones/{nombre}/eventos`, con un conector por integración:
`calendly`, `whatsapp`, `linkedin-lead-gen` y `formulario-web`. El conector solo traduce la
carga a eventos: no escribe, no valida ni decide a quién pertenece cada uno.

| Paso | Qué pasa |
| :--- | :--- |
| 1. ¿Existe y está activa? | Si no, **404**, igual en los dos casos |
| 2. Límite propio | **429** al superarlo; la cuenta de una no consume la de otra |
| 3. Firma con su secreto | HMAC sobre `<marca de tiempo>.<cuerpo>`; **401** con otro secreto; **503** si no tiene |
| 4. Traducir y validar todos los eventos | Uno inválido rechaza la entrega entera con su motivo (**422**) antes de escribir nada |
| 5. Registrar cada evento | `registrar_evento`; la deduplicación es la permanente |
| 6. Bitácora | `integracion.entrega`: cuántos eventos y en qué estado quedaron, sin datos de contacto |

Cada integración tiene `INTEGRACION_<NOMBRE>_ACTIVA`, `_SECRETO` y `_LIMITE`. Están apagadas
por defecto: una integración se enciende cuando hay alguien al otro lado. Un límite mal
escrito falla al arrancar, no en la primera entrega. El CRM conserva su secreto y su límite
(`CRM_WEBHOOK_SECRET`, `RATE_LIMIT_WEBHOOK`) y gana su interruptor
(`INTEGRACION_CRM_ACTIVA`, encendido porque ya lo estaba).

**Revocar una no toca a las demás**, y está probado en los tres sentidos:

* con el secreto de Calendly vacío, Calendly responde 503 y WhatsApp sigue entrando;
* una entrega de WhatsApp firmada con el secreto de Calendly da 401;
* con Calendly a una entrega por minuto, la segunda da 429 y WhatsApp sigue entrando.

### Lo que los conectores no pretenden

Las cargas que se aceptan se parecen a las de origen —el `invitee.created` de Calendly, el
`entry[].changes[].value` de la API de WhatsApp Business—, pero son la forma reducida que
entregaría un conector, no los esquemas completos de cada proveedor. La firma tampoco es la
de cada proveedor: todas usan el esquema HMAC del webhook CRM, cada una con su secreto. En
esta fase no hay cuentas en esos sistemas contra las que contrastarlo (§21.12).

---

## 21.8. Minimización y aviso de privacidad

### Nunca el texto de un mensaje

De un mensaje se guardan el tipo, la dirección, la fecha y el identificador. Tres barreras:

1. **Los conectores no leen el contenido.** El de WhatsApp no toca `text.body`, el de
   Calendly no toca las respuestas de la reserva y el del formulario web no copia
   `campos.mensaje`.
2. **`minimizar` retira las claves de contenido** (`text`, `body`, `message`, `mensaje`,
   `content`, `subject`, `caption`…) a cualquier profundidad antes de escribir: en los datos
   de la actividad, en lo que se conserva del CRM dentro de `raw_metadata` y en la carga que
   guarda `crm_integration_logs`. Esta última guardaba antes la entrega completa, que es donde
   el texto de un mensaje del CRM se quedaba para siempre.
3. **Los mensajes no admiten notas.** Una nota del asesor sobre un WhatsApp era el sitio
   natural para pegar el mensaje; la API la rechaza y la ficha no ofrece el campo.

La prueba no mira un campo concreto. Envía una frase centinela dentro del mensaje por el
CRM, WhatsApp, Calendly y el formulario web, y **recorre todas las columnas de todas las
tablas** buscándola.

### Aviso de privacidad

`leads.privacy_notice_accepted_at` y `privacy_notice_source` guardan cuándo y por qué vía se
aceptó el aviso. Se guarda la primera aceptación: una entrega posterior del mismo CRM no la
mueve, porque lo que hay que poder demostrar es desde cuándo había consentimiento. LinkedIn
Lead Gen la toma de su casilla de consentimiento, el formulario web de
`aviso_de_privacidad.aceptado`, el CRM de `privacy_notice_accepted_at` y el alta manual del campo
`privacy_notice_accepted`, con el que el asesor deja constancia. Sin aceptación, el campo queda vacío: no se
supone.

Esto da soporte técnico a lo que pide la LFPDPPP de 2025 sobre el aviso de privacidad: poder
decir cuándo y por qué medio se puso a disposición y se aceptó. No es una valoración jurídica,
y **aceptar el aviso no es condición para crear la ficha** (§21.12).

---

## 21.9. La ficha

| Antes | Ahora |
| :--- | :--- |
| Desplegable de diez tipos con «+25 pts», «+8 pts»… | Cuadrícula de tres casillas —llamada, WhatsApp, LinkedIn—, sin puntos. Resultado y dirección, también en casillas. Demo, descarga, webinar y «otro evento» salen de la ficha: los registra la integración que los ve |
| Tras registrar, nada | «Score: 47,8 → 58,6», el cambio real devuelto por el servidor |
| Historial con `PROPOSAL_SENT` y «Peso: 25 pts» | «Propuesta enviada», marca **verificada** o **declarada**, fuente, resultado o dirección |
| Llamada sin resultado | Resultado obligatorio: conectó, no contestó o buzón de voz |
| «Mensaje de WhatsApp / LinkedIn» | Dos tipos, con su dirección y sin notas |
| Propuesta y reunión en el selector | Fuera: se registran al cambiar la etapa, y la ficha lo dice |
| Error en un `alert` genérico | El motivo del servidor, bajo el formulario |

El número del selector nunca pudo ser cierto. La parte conductual tiene tope de 50 puntos,
decae con el tiempo y pesa el 40 % frente al modelo. Una propuesta no suma 25 al score: suma
lo que suma en ese prospecto, ese día. La respuesta del registro trae ahora `score_anterior`
y `score`, calculados por el mismo recálculo que ya se hacía.

### Defectos que aparecieron al tocar la ficha

* **El selector de etapa cambiaba la etapa al guardar.** Solo ofrecía ocho de las diez
  etapas: faltaban «En conversación» (`ENGAGED`) y «No calificado» (`UNQUALIFIED`); la
  primera es la de los prospectos templados del sembrado. En un prospecto así, el selector enseñaba otra etapa, y
  cualquier cambio en el formulario podía guardar la equivocada sin que nadie lo pidiera.
  Ahora se ofrecen todas.
* **La urgencia prometía puntos falsos.** «ALTA, +5 pts», cuando la regla suma 10 por «ALTA».
  Se retiró el número, como en el selector de actividades.

---

## 21.10. Que nada de esto sea decorativo

### Las pruebas

Se reintrodujeron **28 defectos**, uno a uno, ejecutando con cada uno solo las pruebas de
su pieza, en backend y cliente: **28 los detectan**, con 68 fallos en total.

| Pieza | Defectos reintroducidos |
| :--- | :--- |
| Registro | tipo desconocido del CRM como `FORM_SUBMIT`; la ficha nueva inventa industria y tamaño; cualquier fuente crea ficha; llamada sin resultado; buzón como conversación; LinkedIn fuera de mensajes directos; propuesta declarable a mano; el cambio de etapa no registra; el cambio de etapa registra en cada guardado; sin índice único; fecha futura aceptada; un evento tardío rejuvenece al prospecto; WhatsApp deja de ser verificada |
| Teléfonos | el móvil mexicano con «1» no se normaliza; el alta no valida |
| Minimización | el registro del CRM guarda la carga completa; los datos de la actividad sin minimizar; el formulario copia el mensaje libre |
| Integraciones | un solo secreto para todas; una apagada se delata con 403; límite común |
| Derechos del titular | la supresión no alcanza la bandeja; la exportación la omite |
| Cliente | el selector vuelve a prometer puntos; el historial enseña el identificador en inglés; el cambio de score no se enseña; un mensaje manda notas; descartar sin confirmar |

### Las guardas del pipeline

Tres guardas nuevas, **15 reintroducciones, 15 disparos**, y las tres
pasan sobre el árbol correcto. El arnés exige la palabra `FALLO` en la salida y guarda en
disco la copia de cada archivo antes de tocarlo.

La primera ejecución dio también quince disparos, pero **la guarda de lo inventado fallaba
ya sobre el árbol correcto**, así que sus cinco disparos no demostraban nada: buscaba
«Tecnología» y «Empresa no identificada» en `crm_service.py` y los encontraba en la
documentación del propio módulo, que los nombra para contar que ya no se usan. Ahora busca
esos valores como literales de código, entre comillas. El arnés lo señaló porque exige las
dos cosas: pasar sobre el árbol y disparar con el defecto. Mirar solo los disparos lo habría
dado por buena.

| Guarda | Reintroducciones |
| :--- | :--- |
| Las actividades se registran por un solo camino | un endpoint construye actividades; el repositorio vuelve a escribir; la ficha o el CRM dejan de pasar por el registro |
| El registro no inventa ni supone | el CRM inventa la industria; tipo desconocido como `FORM_SUBMIT`; cualquier fuente crea ficha; buzón como conversación; tamaño «1-10» supuesto |
| El texto de los mensajes no se guarda y las integraciones no comparten secreto | carga completa del CRM guardada; datos sin minimizar; integraciones con el secreto del CRM; sin límite propio; Calendly encendida por defecto; WhatsApp sin secreto propio |

---

## 21.11. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend, en el entorno instalado desde el lock | **728 pruebas**, 92 % de cobertura |
| Suite del cliente | **148 pruebas** |
| `ruff` / `eslint` | Sin avisos |
| Locks | 59 paquetes en producción y 92 en desarrollo; entra `phonenumbers` y ninguna otra versión cambia |
| Migración en SQLite | Subida, `alembic check` limpio, reversión de un paso y ciclo completo de 8 migraciones |
| PostgreSQL 16 | Verificado después del cierre (§21.12). Datos con la forma anterior migrados y marcados: 1 actividad CRM, 3 manuales; 2 teléfonos normalizados, 1 vacío pasado a nulo y 1 sin forma de número conservado. Recorrido completo por el servicio, índice único rechazado por la base, texto del mensaje en ninguna columna |

---

## 21.12. Lo que esta fase no hizo

* **La verificación en PostgreSQL llegó después del cierre.** Durante la fase Docker Desktop no
  arrancaba, y el cierre se hizo con el ciclo completo en SQLite y los guiones de PostgreSQL
  preparados. Se ejecutaron en cuanto Docker volvió a funcionar, con los resultados de §21.11. Al
  recrear la base de la pila apareció un defecto de entorno ajeno a la fase: el volumen se había
  inicializado con el usuario `postgres`, el compose conectaba como `plurione` y el chequeo de
  salud dejaba un `FATAL` cada diez segundos sin marcar el contenedor como enfermo.
* **No hay cuentas en Calendly, WhatsApp Business ni LinkedIn.** Los conectores aceptan una
  forma reducida de sus cargas y se firman con el esquema HMAC propio, no con el de cada
  proveedor. Conectar uno de verdad exige contrastar su esquema completo y su firma, o poner
  delante un conector que traduzca.
* **Los ingresos anuales siguen inventándose en la inferencia.** Si faltan, el adaptador del
  modelo pasa 100 000, porque el preprocesador no imputa valores ausentes y fallaría con uno
  vacío. Arreglarlo exige reentrenar con imputación.
  *Cerrado en el capítulo 24: el adaptador pasa la ausencia como ausencia y el artefacto
  imputa con la mediana y una columna que marca que faltaba. El alta del panel, que enviaba
  2 000 000 fijos, y el esquema de la API, que ponía cero, tampoco los inventan ya.*
* **Las llamadas anteriores dejaron de contar.** Es la consecuencia honesta de no suponer su
  resultado, pero mueve el score de los prospectos que las tenían en el siguiente recálculo.
  *Desde el capítulo 24 el resultado de la llamada es una variable del modelo —conectadas y
  sin respuesta por separado—; las llamadas sin resultado siguen sin contar en ninguna, por la
  misma razón.*
* **WhatsApp y LinkedIn siguen siendo una sola variable del modelo** hasta reentrenar.
  *Cerrado en el capítulo 24: `whatsapp_messages` y `linkedin_messages` son dos variables del
  artefacto nuevo; la regla heurística los sigue sumando bajo el mismo tope.*
* **La bandeja no tiene caducidad.** Un aviso que nadie vincula ni descarta se queda. Es una
  fila más para la política de conservación del capítulo 20.
  *Cerrado en el capítulo 22: 90 días desde que llegó el aviso (`CONSERVACION_SIN_ASOCIAR_DIAS`,
  mínimo 30), en la pasada diaria y con asiento en la bitácora.*
* **Aceptar el aviso de privacidad no es condición para crear la ficha.** Se registra si
  llega; qué hacer cuando no llega es una decisión de quien responde del tratamiento.
* **Una entrega de WhatsApp con varios mensajes no es atómica.** Se validan todos antes de
  escribir, pero si el tercero falla al registrarse los dos primeros quedan. Un reintento los
  encuentra como duplicados.
* **Sin `event_id`, el CRM se deduplica por contenido.** Dos eventos reales idénticos byte a
  byte entran como uno.
* **Descartar no bloquea.** Si el sistema de origen reentrega un aviso descartado, vuelve a la
  bandeja.
* **El teléfono de los asesores (`users.phone`) no se normaliza.** Esta fase se ocupó del de
  los prospectos.
* **El formulario de alta del panel no ofrece la casilla del aviso de privacidad.** La API
  la admite (`privacy_notice_accepted`); la pantalla, todavía no.
* **No hay pantalla para configurar integraciones.** Se encienden y se revocan por variables
  de entorno.
