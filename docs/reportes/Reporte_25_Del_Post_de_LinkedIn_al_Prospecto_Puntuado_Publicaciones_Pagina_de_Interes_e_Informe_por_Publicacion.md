# Capítulo 25: Del Post de LinkedIn al Prospecto Puntuado — Publicaciones, Página de Interés e Informe por Publicación

## 25.1. La historia

Marketing escribe un post en LinkedIn. Alguien lo lee, le interesa y deja sus datos. Esa
persona aparece en el sistema como un prospecto ya puntuado, con la publicación que la trajo
escrita en su ficha. Un asesor la atiende sabiendo de dónde vino y qué pidió. Y el líder
compara publicaciones entre sí para saber cuál trajo más perfiles y cuál mejores.

Eso es todo lo que hace este capítulo, y hasta él no se podía enseñar ni un paso sin tocar la
base a mano. El ensayo del 16 de septiembre lo dejó escrito en el guion
(`docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md`): no había pantalla para
crear campañas (H-1), nada construía un enlace que copiar (H-2), no había página a la que
llevara ese enlace (H-3), y la ficha que llegaba por un formulario quedaba con
`campaign_id = NULL` (H-4). **Una publicación con cien respuestas aparecía en el informe de
campañas con cero prospectos.** El resto del sistema —el modelo, la autorización por objeto, el
registro de actividad— estaba; faltaba el camino por el que un prospecto de verdad llega.

Quién hace qué en la historia:

| Papel | Cuenta | Qué hace |
| :--- | :--- | :--- |
| Marketing | Líder comercial o administración | Crea la publicación y copia su texto para LinkedIn |
| Interesado | Ninguna | Abre el enlace desde el teléfono y deja sus datos |
| Líder | `Sales_Lead` | Ve lo que llegó sin asesor, lo reparte y compara publicaciones |
| Asesor | `Commercial_Executive` | Encuentra la ficha nueva, entiende de dónde vino y la atiende |

---

## 25.2. El guion de la demo

Seis pasos, en el orden en que se enseñan. Cada uno dice qué se ve y qué pieza lo hace.

| Paso | Se enseña | Lo hace |
| :-: | :--- | :--- |
| 1 | Marketing crea la publicación | Pestaña «Publicaciones»: una campaña con canal `LinkedIn`, descripción, a quién va dirigida y enlace propio |
| 2 | Copia el texto para LinkedIn | Botón «Copiar texto para LinkedIn»: descripción y enlace, ya armados por el servidor |
| 3 | El interesado envía su perfil | `/interes/<enlace>`: la única pantalla sin sesión, pensada para un teléfono |
| 4 | El sistema crea y puntúa el prospecto | `registrar_evento`: ficha nueva, atribuida a su publicación, sin asesor, puntuada |
| 5 | El asesor la ve en la ficha 360 | El líder la asigna desde la propia ficha; el asesor ve la tarjeta «Llegó por» |
| 6 | El líder compara publicaciones | Informe de cada publicación y comparativa entre ellas |

Para ensayarlo sin tocar la base: `python scripts/preparar_prueba_con_personas.py --force`
deja la pila con datos limpios y una publicación de ejemplo con tres perfiles ya recibidos
por su enlace, para que en el paso 6 haya dos que comparar (§25.6).

### Las reglas del proyecto

El guion fijó cinco reglas antes de escribir código, y las fases las respetaron:

* **R-1. No pedir nada que LinkedIn no dé.** El formulario pide lo que un formulario de
  LinkedIn entrega (`PredefinedField`: nombre, correo, teléfono, empresa, cargo, sector,
  tamaño, perfil). Hubo una excepción consciente, el **tramo de facturación**, que LinkedIn
  no da; la simplificación del formulario la quitó (§25.8).
* **R-2. No crear conceptos paralelos.** Una publicación **es** una campaña con canal
  `LinkedIn`. No hay tabla de publicaciones: el informe de campañas, la atribución y la
  bitácora ya existían y valen tal cual.
* **R-3. Las listas del formulario, iguales a las del modelo.** El preprocesador usa
  `OneHotEncoder(handle_unknown="ignore")`: un sector escrito de otra forma no da error, se
  descarta en silencio y el prospecto puntúa como si no hubiera dicho a qué se dedica.
* **R-4. No sobrescribir ni inventar datos.** Una segunda solicitud se suma al historial y no
  pisa la ficha; lo no indicado queda vacío.
* **R-5. No más endurecimiento salvo fallos reales.** Las defensas de la página pública son
  las que exige una ruta abierta que escribe en la base, no una ronda más de auditoría.

---

## 25.3. Publicaciones (pasos 1 y 2)

La campaña gana tres columnas: `description`, `target_audience` y `public_slug`. La migración
`b7e41c9d2f60` las añade, rellena el enlace de las campañas que ya existían fila a fila y
crea el índice único `uq_campaigns_public_slug`; su reversión las quita. El ciclo
`upgrade → insertar → upgrade → rechazar duplicado y nulo → downgrade → upgrade` tiene prueba
propia contra una base real.

El enlace lo genera **el servidor**: `secrets.token_urlsafe(16)`, 22 caracteres, 128 bits.
No viaja en ningún esquema de entrada, ninguna edición lo cambia, el índice impide que otra
campaña lo lleve y una campaña no se borra: se desactiva. Un enlace publicado en LinkedIn no
se puede retirar, así que no puede quedar libre para que otra campaña lo herede.

Crean y editan el líder y el administrador; el asesor consulta y copia. El texto que se
copia es la descripción más el enlace y cabe en un post: la descripción tiene un tope de
2 800 caracteres para que el conjunto no pase de los 3 000 que admite LinkedIn.

---

## 25.4. La página de interés (pasos 3 y 4)

`/interes/<enlace>` enseña el título y el texto de la publicación —nunca el presupuesto, a
quién va dirigida ni el identificador interno— y un formulario **sin texto libre**. Desde la
simplificación de §25.8 obliga solo a nombre, correo, empresa, cargo, tamaño, sector, «¿Qué
necesitas?» y el aviso de privacidad; teléfono y perfil de LinkedIn van plegados y son
opcionales, y la facturación ya no se pregunta. Cargo, sector y tamaño son
`CATEGORIAS_DEL_MODELO`, las mismas que conoce el artefacto; la página no las escribe, se las
pide al servidor.

### Por qué una ruta propia

Las integraciones firman sus entregas con un secreto HMAC. Un navegador no puede firmar: el
secreto viajaría dentro de la página y sería público. La ruta es abierta a propósito y se
defiende con lo que sí sirve en público:

| Defensa | Qué evita |
| :--- | :--- |
| Límite por IP (10/hora) | Que alguien envíe en bucle desde un sitio |
| Límite por publicación (120/hora) | El mismo envío repartido entre muchas IP: un enlace difundido llenando la base |
| Límite de lecturas por IP (120/hora), aparte | Recorrer enlaces en bucle, sin que abrir la página gaste el cupo de enviarla (§25.8) |
| Campo trampa | El robot que rellena todos los campos: se descarta sin decirlo |
| Esquema estricto (`extra="forbid"`) | Un campo que el servidor no espera: es un error, no algo que se ignora |
| «No disponible» único | Distinguir «no existe», «desactivada» y «no es de LinkedIn»: ayuda a recorrer enlaces |
| La misma respuesta siempre | Averiguar qué correos hay en la base enviando el formulario |

### Por dentro

La ruta no escribe actividades ni fichas: arma un `Evento` y se lo da a `registrar_evento`,
como cualquier otra fuente. Hereda así la deduplicación, la minimización y el aviso de
privacidad. La fuente nueva, `pagina_de_interes`, se registró con
`actualiza_prospecto=False`: si el correo ya existe, la solicitud se suma al historial **sin
pisar** lo que el asesor corrigió a mano (H-9 queda cerrado para este camino). La ficha nace
atribuida a su publicación, sin asesor y con canal `LinkedIn`, que el listado marca como
«Nuevo, sin asesor» (entonces «Nuevo desde LinkedIn»; la etiqueta cambió en el capítulo 29,
cuando el canal dejó de ser siempre LinkedIn). `annual_revenue` queda vacío, que es la verdad (capítulo 24): al
principio la página pedía un tramo de facturación opcional y lo guardaba como tramo; desde
§25.8 no lo pregunta.

---

## 25.5. La ficha 360 y el informe por publicación (pasos 5 y 6)

### La tarjeta «Llegó por»

La ficha trae `llego_por` cuando la persona llegó por una publicación: su perfil de LinkedIn,
que abre en otra pestaña, y una fila por solicitud con la publicación, su enlace, la fecha,
qué necesita y cuándo aceptó el aviso. **Sin solicitudes el campo es `null` y la tarjeta no se
pinta**: una tarjeta vacía diría «vino de una publicación que no sabemos cuál».

La tarjeta se arma con las **solicitudes**, no con `campaign_id`. La atribución se fija al
crear la ficha y no se vuelve a tocar, así que quien responde a tres publicaciones seguiría
apareciendo solo en la primera. El aviso se guarda en cada envío: la ficha conserva el primero,
y quien va a llamar necesita saber cuándo consintió esta persona esta publicación en concreto.

### El informe

`GET /publicaciones/{id}/informe`: perfiles recibidos, cuántos avanzaron de etapa —salieron de
«Nuevo»; una ficha perdida también avanzó, alguien la trabajó— y score medio; debajo, la tabla
ordenada por score con nombre, empresa, cargo, qué necesita (la de su última solicitud a esa
publicación; §25.8), score, etapa, asesor y fecha, filtrable por
etapa y por días. Cada nombre abre la ficha 360. Entra quien está atribuido a la campaña y
quien envió su perfil por su enlace, por la misma razón que la tarjeta.

### El alcance

| | Asesor | Líder y administración |
| :--- | :--- | :--- |
| Filas del informe | Solo las suyas | Todas |
| Cabecera | Sus números, y aparte **cuántos más hay**, sin un nombre | La publicación entera |
| Comparativa entre publicaciones | 403 | Sí |
| «Nuevos de publicaciones, sin asesor» | 403 | Sí |

Un total y una media describen la cartera ajena sin abrir una ficha; el criterio es el del
tablero desde el capítulo 15. Una campaña que no es publicación responde 404, igual que una
inexistente. Una publicación desactivada **sí** conserva su informe: se desactiva para dejar de
recibir perfiles, no para borrar los que trajo.

Cada consulta del informe queda en la bitácora (`publicacion.informe`) con sus filtros y el
número de filas, **nunca con las filas**: la bitácora se lee con otro criterio de acceso que la
cartera, y copiar ahí nombres y empresas los expondría dos veces. La comparativa tiene su
propia acción (`publicacion.comparativa`).

### Repartir desde la ficha

El paso 5 no se podía recorrer: las fichas de LinkedIn llegan sin asesor y no había pantalla
para asignarlas (H-6); había que llamar a `PUT /leads/{id}` a mano. La ficha 360 ofrece ahora
«Asignar asesor» a quien puede reasignar, y solo a él: al asesor el servidor le respondería
403, y ofrecer lo que va a ser rechazado es peor que no ofrecerlo. El contador «Nuevos desde
LinkedIn sin asesor» avisa al líder de que hay trabajo sin repartir.

---

## 25.6. Probar con personas

La cuarta fase preparó una prueba con cuatro personas, una por papel. Dejó tres cosas:

* **La pila con un comando.** `scripts/preparar_prueba_con_personas.py --force` copia la base,
  siembra con `seed_data.py` —sin duplicar su lógica ni sus guardas— y crea la publicación de
  ejemplo con tres perfiles enviados **por la ruta pública de verdad**, no insertados a mano.
  Imprime el enlace, las cuentas y lo necesario para usar un teléfono de verdad.
* **El guion por papel y la hoja de observación** (`docs/Prueba_Con_Personas.md`). *Este
  punto decía también «y una versión rellenable con cronómetro por tarea que Claude puede
  leer de vuelta». **Esa versión no existía**: se anunció y no se construyó, y nadie lo
  notó en cuatro capítulos porque lo que no se usa no falla. Se construyó en el capítulo 29
  (§25.6), que es cuando se fue a usar.*
* **El ensayo automático** (`frontend/src/EnsayoDelGuion.test.jsx`): las cuatro listas de
  tareas, en orden, sobre la aplicación entera y contra un servidor simulado con las
  respuestas del backend de verdad. Si una tarea deja de poderse terminar, falla.

### Cuatro atascos encontrados antes de sentar a nadie

Recorriendo el guion con los cuatro papeles aparecieron cuatro cosas que habrían parado a una
persona real. Ninguna la detectaba la suite, porque todas estaban **entre** dos piezas:

| Qué pasaba | Por qué no se había visto | Qué se cambió |
| :--- | :--- | :--- |
| El enlace copiado apuntaba a `/p/<enlace>` y el panel solo atiende `/interes/<enlace>` | Escribiendo la dirección a mano todo funcionaba; solo siguiendo el enlace ya pegado se llegaba a la pantalla de acceso | `PUBLICACIONES_URL_BASE` apunta a `/interes`, y una prueba compara ese valor con la ruta de verdad leída de `main.jsx` |
| El perfil de LinkedIn se rechazaba pegado tal cual | El botón «compartir» añade `?utm_source=share…` y quien lo teclea no pone `https://`; además `type="url"` lo bloqueaba en el propio navegador | El servidor completa el esquema y quita los parámetros antes de validar, y guarda la forma limpia; el campo pasó a texto con ayuda visible |
| El error decía «linkedin: **Value error**, El perfil…» | Es el nombre interno de una excepción de Pydantic | El cliente quita ese prefijo en toda la validación |
| El panel no se abría desde un teléfono | El servidor de desarrollo solo escucha en `localhost` | `npm run dev:lan`, y el preparador imprime la dirección de la máquina que tiene que llevar el enlace |

**La sesión con personas no se ha hecho.** La hoja está preparada y vacía. El criterio de esa
fase —«nadie se atasca»— solo lo contesta una sesión real, y no se da por cumplido (§25.10).

### El guion, puesto al día (capítulo 29, 23-09-2026)

Entre la fase 4 y hoy el sistema creció tres capítulos y el guion se quedó donde estaba. Un
guion que no recorre lo que el sistema hace deja de medir el sistema que hay, así que las
listas de tareas incorporan lo que trajeron el 26, el 27 y el 28:

* **Marketing** se lleva el texto de **dos** redes, no de una, y tiene que decir en voz alta
  si cree que los dos enlaces son el mismo. Si dice que sí, el panel no ha explicado para qué
  sirven las redes y el informe por red del líder se vuelve inexplicable.
* **El interesado** entra por el enlace de WhatsApp, que es por donde le llegó.
* **El líder** averigua **por qué red** llegó la persona, y antes de salir dice si hay algún
  HOT enfriándose y con quién está.
* **El asesor** empieza por «Hoy» —y antes de tocar nada dice qué cree que le está pidiendo
  el sistema— y al terminar deja el trabajo como lo dejaría de verdad. No se le dice que
  existe «Ya está»: si lo encuentra, la bandeja le está hablando; si no, se apunta qué hizo
  en su lugar.

Todas están además en el ensayo automático, que pasó de cuatro recorridos a cinco.

### Dos defectos que salieron de añadirlas

Ninguno es funcionalidad: los dos son de los que esta fase corrige.

| Qué pasaba | Por qué importaba | Qué se cambió |
| :--- | :--- | :--- |
| El contador del líder decía «Nuevos desde LinkedIn sin asesor» y contaba los **seis** canales de publicación; el listado solo marcaba `source === 'LinkedIn'` | El líder leía «3 esperando», iba a la lista a repartirlos y encontraba **una** marca. Dos números que no cuadran, y ninguna manera de saber cuál miente. Con una sola red nunca se notó; desde el capítulo 27 dos de cada tres fichas quedaban invisibles | La condición pasa al servidor, que ya la tenía para el contador: `LeadResponse.esperando_asesor` la calcula con la misma `es_de_publicacion` y el listado solo la dibuja. La marca pasa a «Nuevo, sin asesor», sin nombrar red —ya está en esa celda—, y el contador a «Nuevos de publicaciones, sin asesor» |
| El ensayo automático **tiraba la parte de la consulta** de cada petición | La red por la que se repartió el enlace viaja ahí (`?r=whatsapp`). El ensayo habría dado por bueno un panel que perdiera entera la atribución del capítulo 27 | El servidor simulado la guarda aparte, y el ensayo comprueba que la etiqueta viaja en la apertura **y** en el envío |

`tests/test_una_publicacion_varias_redes.py` compara ahora el contador con las fichas
marcadas y falla si vuelven a separarse. El primero venía de **no releer una etiqueta al
añadir un concepto**: cuando la única red era LinkedIn, «Nuevos desde LinkedIn» era exacto,
y nada avisa el día que deja de serlo.

### Y una nota de la hoja que decía de más

El capítulo 28 escribió en la hoja que los dos sitios «para mirar con lupa» quedaban
cerrados. Solo uno lo estaba. Al líder se le dio ver los **HOT que se enfrían**, que es otra
pregunta distinta de cuántos esperan a que los repartan; ese contador sigue viviendo en la
pestaña «Publicaciones». La hoja se corrige y la nota queda abierta, porque es exactamente lo
que la sesión tiene que medir: mover un contador de pestaña porque a uno le parece es cambiar
una pantalla por una corazonada.

### El instrumento que faltaba

Al ir a usar la hoja apareció que **lo anunciado en esta misma sección no existía**. Había
una tabla dentro de un documento largo: se lee bien, no se rellena mientras miras a alguien
—hay que buscar la fila, contar columnas, no perder el sitio— y no se vuelve a leer después
sin transcribirla a mano. Una hoja que no se puede rellenar en caliente acaba rellenándose
de memoria al final del día, y lo que se anota de memoria es lo que uno recuerda.

`scripts/hojas_de_observacion.py` lo resuelve con dos órdenes:

* **`crear`** deja una hoja por papel en `docs/hojas_de_observacion/`, con las tareas ya
  escritas y un hueco por campo. Las tareas **se leen del guion**, no de una copia: el guion
  acaba de cambiar con los capítulos 27 y 28, y dos listas que tienen que decir lo mismo
  acaban diciendo cosas distintas sin que nadie se entere. Una hoja ya rellenada no se pisa
  salvo que se pida a gritos (`--forzar`).
* **`leer`** recoge las hojas, arma la tabla de vaciado y **dicta el veredicto**.

El tipo de cada nota —atasco, duda o idea— lo escribe quien conduce, no lo adivina el
programa: un «no» en «¿Sola?» puede ser un atasco o una pista pequeña, y eso solo lo sabe
quien estaba delante. El programa suma; no interpreta.

Lo que sí decide es el veredicto, y por eso lleva sus propias pruebas
(`scripts/test_hojas_de_observacion.py`, 14): un atasco lo tumba, una duda no, tres papeles
de cuatro no bastan —los cuatro se recorren entre todos, y el atasco de uno para a los que
vienen detrás— y una plantilla recién creada no cuenta como observación. Un lector
equivocado diría «cumplido» sin que nadie lo notara.

### El criterio, hoy: **no cumplido**

No por haber fallado, sino por no haberse medido. Lo dice ahora el propio sistema: con la
carpeta de hojas en blanco, `hojas_de_observacion.py leer` responde «SIN DATOS» y termina en
código 2. El criterio dejó de ser algo que alguien afirma en un documento y pasó a salir de
los datos de la sesión, que es lo que había que arreglar: mientras lo afirmara una persona,
un «sí» descuidado y un «sí» medido se escribían igual.

Lo que hay es un guion al día, cinco recorridos automáticos en cada ejecución del CI, ocho
notas de ensayo —siete corregidas—, cuatro hojas listas para rellenar y **cero rellenadas**. Lo que ningún ensayo puede decir es si la palabra
que hay en pantalla significa para quien la lee lo que significaba para quien la escribió:
una prueba que busca «Llamar por primera vez» lo encuentra siempre, y un asesor que no sepa
qué se espera de él al leerlo se queda parado sin que falle nada.

---

## 25.7. Que nada de esto sea decorativo

### Lo que puede romperse, y qué lo prueba

La quinta fase repasó, uno por uno, los puntos por los que la historia se puede romper:

| Punto frágil | Pruebas |
| :--- | :--- |
| Duplicados | La segunda solicitud suma al historial sin pisar la ficha y la puntúa con los datos del asesor; no cambia la campaña de la ficha; la respuesta es idéntica exista o no el correo |
| Publicación desactivada o inexistente | «No disponible» en la página y en el envío, sin crear ficha; una campaña que no es de LinkedIn no tiene página; en el informe, 404 para lo que no es publicación y conservación del informe de una desactivada |
| Límite de envíos | Por IP; por publicación aunque cambie la IP; un límite mal escrito no arranca |
| Campo trampa | Se descarta con la misma respuesta y sin ficha |
| Aviso no aceptado | En falso, 422 y sin ficha; **omitido**, 422 y sin ficha (añadida en esta fase: un valor por defecto en el esquema habría registrado como consentido a quien simplemente no lo envía) |
| Listas alineadas con el modelo | Contra el artefacto que puntúa y contra el generador del dataset, leído sin ejecutarlo; la página sirve exactamente esas listas |
| Alcance del informe | El asesor ve los suyos y un número sin nombres; el líder, todo; comparativa y contador de dirección; bitácora sin datos de contacto; la comparativa y el informe dan lo mismo por dos caminos distintos |

80 funciones de prueba nuevas en el backend —`test_publicaciones.py` (20),
`test_migracion_publicaciones.py` (1), `test_pagina_de_interes.py` (27),
`test_categorias_del_modelo.py` (4), `test_informe_de_publicaciones.py` (24),
`test_guarda_de_la_pagina_publica.py` (2) y `test_memoria_completa.py` (2)—, varias
parametrizadas. La última exige que cada reporte del disco esté en el compilador y que la
memoria tenga cada capítulo con su ancla; con la memoria anterior a esta fase habría fallado
en los capítulos 22 a 25. En el cliente, 55 casos en
los componentes nuevos y el ensayo del guion, más los añadidos a la ficha, al listado y al
catálogo de rutas.

### La guarda del CI

`scripts/guarda_de_la_pagina_publica.py` es un paso con nombre propio del trabajo `pruebas`,
**«La pagina publica conserva sus defensas»**, entre la descarga del artefacto validado y la
suite. Las pruebas comprueban casos; la guarda comprueba propiedades. Un campo `comentarios`
nuevo no rompe ninguna prueba existente, porque nadie lo envía; la guarda falla en cuanto
existe. Mide tres cosas ejecutando, sobre una base SQLite temporal:

1. **El límite de envíos.** Los valores por defecto existen y no pasan de un techo (60 por IP
   y 600 por publicación a la hora; subir por debajo es una decisión, pasarlo es perderlo), y
   la ruta los aplica: con un límite de 2, el tercer envío tiene que recibir 429, una vez por
   IP y otra por publicación.
2. **Sin texto libre.** El esquema rechaza campos de más; cada campo es un dato de contacto
   con tope de longitud o rechaza una frase cualquiera; y la actividad guardada no lleva nada
   más que la publicación, la necesidad y la fecha del aviso.
3. **Alineación con el modelo.** Las listas que sirve la página son las categorías del
   `OneHotEncoder` del artefacto, y el esquema acepta cada valor que la página ofrece.

La solicitud de referencia de la guarda toma cargo, sector y tamaño de las listas del modelo,
no de valores escritos a mano, y se comprueba válida antes de usarla. La primera versión los
llevaba fijos: al cambiar una lista, la referencia dejaba de pasar y la comprobación de texto
libre se habría cumplido sola —«todo campo rechaza una frase» es cierto si todo se rechaza—.
Una prueba de la suite exige que el paso siga en el CI, en ese orden, y que la guarda pase con
el código de hoy.

### Reintroducciones

Con el arnés de los capítulos anteriores —copia el archivo, lo altera, exige el fallo y lo
restaura comprobando su huella—:

| Fase | Defectos | Detectados |
| :--- | :--- | :-: |
| Publicaciones | enlace sin índice único, enlace predecible, el asesor gestionando, la edición cambiando el enlace, la migración sin rellenar enlaces únicos, la reversión sin quitar el índice | 6 / 6 |
| Página de interés | campo trampa ignorado, respuesta distinta con correo conocido, la solicitud pisando la ficha, publicación desactivada aceptando, sin límites, sin atribución, aviso opcional, una lista apartada del modelo | 8 / 8 |
| Ficha e informe | alcance del asesor ignorado, el resto sin contar, solo atribución por campaña, otro canal con informe, «avanzaron» contando las nuevas, «hasta» perdiendo el día, una sola publicación en la tarjeta, la bitácora con nombres, comparativa abierta, contador contando asignados, tarjeta vacía pintada, el asesor repartiendo, filtrado en el navegador | 13 / 13 |
| Guarda del CI | la ruta sin límite, el límite apagado por dentro, el límite decorativo, un campo de texto libre, campos de más aceptados, una lista cerrada abierta, la actividad guardando la empresa, la página con una lista propia, la lista del modelo apartada del artefacto | 9 / 9 |

**36 de 36.** Cada defecto de la guarda falló con un mensaje que dice qué se perdió; el último,
por ejemplo: «la página sirve "sectores" distinta de lo que conoce el modelo en industry:
sobran ['Fintech'], faltan ['FinTech']».

---

## 25.8. Un formulario de treinta segundos sin datos supuestos

El paso 3 es donde la historia pierde a la gente: alguien que acaba de leer un post en el
teléfono no rellena doce campos. Y el formulario pedía cosas que después se suponían o se
puntuaban sin motivo. Esta fase lo simplificó y quitó los supuestos que había detrás.

### Lo que se pide

| | Antes | Ahora |
| :--- | :--- | :--- |
| Obligatorio | Nombre, apellidos, correo, empresa, cargo, sector, tamaño, perfil de LinkedIn, necesidad, aviso | Nombre (un solo campo), correo, empresa, cargo, tamaño, sector, «¿Qué necesitas?», aviso |
| Opcional | Teléfono, tramo de facturación | Teléfono y perfil de LinkedIn, plegados bajo «Añadir más datos» |
| No se pregunta | — | La facturación: `annual_revenue` queda vacío y un envío que la traiga recibe 422 |
| «¿Qué necesitas?» | Una lista desplegable | Cuatro botones de un toque |

El nombre es un solo campo: partir «María José García» en nombre y apellidos sería adivinar
dónde acaba uno y empieza el otro. La ficha lo guarda entero en `first_name` con `last_name`
vacío. Esto destapó un fallo: la ficha 360 exigía apellidos para guardar cualquier cambio, así
que una ficha de la página no se habría podido editar. Ahora se pueden dejar vacíos.

Cargo, tamaño y sector siguen saliendo de `CATEGORIAS_DEL_MODELO`, y lo garantizan tres
comprobaciones: `test_categorias_del_modelo.py` contra el artefacto y el generador, la prueba de
la página que compara lo servido, y la guarda del CI.

### En el teléfono

Una sola columna a 375 px. Los campos tienen letra de 16 px, que es la medida a partir de la
cual Safari deja de ampliar la página al tocarlos, y 44 px de alto. El botón mide 52 px. El texto
del post se recorta a tres líneas con «Leer más». Medido en el navegador a 375 × 812, todo cabe:
el documento mide 812 px, sin desplazamiento lateral, con el aviso y el botón a la vista.

Cada error aparece **bajo su campo**, unido a él con `aria-describedby` y `aria-invalid`, y el
foco va al primero. Un 422 del servidor se reparte igual por campo, y si el campo con error
estaba plegado se despliega. Solo un error que no es de un campo, como el límite de envíos, va
arriba.

### Lo que dejó de suponerse

* **«¿Qué necesitas?» puntuaba.** «Ver una demostración» se registraba como `DEMO_REQUEST`,
  que suma 25 puntos en la regla y enciende `requested_demo` en el modelo: un toque valía
  como una demo pedida. Ahora toda solicitud es `FORM_SUBMIT`. La necesidad va en los datos de
  la actividad, y no en `raw_metadata`, que la regla sí lee. El asesor la ve en la tarjeta
  «Llegó por» y en la nueva columna «Necesita» del informe. Cuatro personas iguales salvo en
  la necesidad puntúan igual: en el total, en el desglose y en la probabilidad del modelo.
* **El heurístico suponía lo que faltaba.** Un tamaño que no llegaba se leía como «1-10», el
  tramo más bajo, y en tres sitios distintos: la regla, el servicio que la llama y la línea
  base del pipeline. Un cargo que faltaba recibía la base de los cargos no listados, la misma
  que un estudiante. Ahora lo que falta (`None`, vacío o solo espacios) puntúa **el punto medio
  de su bloque**, calculado desde las propias tablas: 6 en tamaño (entre 2 y 10), 15 en cargo
  (entre 5 y 25) y 10,5 en sector (entre 6 y 15). Un cargo o un sector escritos que no
  coinciden con ninguna regla sí son un dato y conservan su base. Una etiqueta de tamaño que
  no se reconoce no dice cuántas personas hay y cuenta como desconocida. `1-10` sigue
  valiendo 2.
* **El simulador rellenaba lo que no se le mandaba.** Ponía «51-200», cuatro visitas, dos
  aperturas, un clic, una descarga, un webinar y una demo, y el cálculo sin persistencia
  suponía una visita. Ahora lo que no se envía vale cero o es desconocido.
* **El resto de variables se revisó una por una**, cada caso con su prueba: los recuentos y
  las marcas de comportamiento valen cero cuando no hay evento, que es lo que dice el registro,
  no una suposición. La urgencia no declarada no suma, tampoco `{"urgency": None}`, que se leía
  como la cadena «NONE». Los días sin actividad solo atenúan comportamiento, así que sin él no
  mueven nada.

### Un atasco que apareció al medir

Midiendo en el navegador, a la cuarta carga la página respondió «Esta publicación no está
disponible». Abrirla gastaba la misma cuenta de diez por hora que enviarla, y en desarrollo
cada carga cuenta dos veces. Desde una oficina detrás de una sola IP, unas pocas visitas de
compañeros dejaban al siguiente sin poder ni ver el formulario, con un mensaje falso. Ahora la
lectura tiene su propio límite (`INTERES_LIMITE_DE_LECTURAS_POR_IP`, 120 por hora) y no gasta
el de envíos. Un 429 al abrir dice «Ahora mismo no podemos atenderte», no «no disponible».

### Cuánto se tarda

Medido en el navegador a 375 × 812, con marcas de tiempo en la propia página desde el primer
toque hasta el envío y hasta el «Gracias». Un script no teclea como una persona, así que el
ritmo se fijó con tiempos de referencia:

* 0,33 s por carácter, es decir, 36 palabras por minuto: la media en el teléfono del estudio
  con 37 000 voluntarios de Palin y colegas (MobileHCI 2019);
* 1,1 s por toque;
* 2,5 s por elección en una lista nativa;
* 1,2 a 1,5 s para decidir entre los botones.

| Recorrido | Hasta enviar | Hasta el «Gracias» |
| :--- | :-: | :-: |
| Tecleando nombre, correo y empresa (63 caracteres) | 34,9 s | 35,1 s |
| Con el autocompletado del teléfono para esos tres campos (`autocomplete="name"`, `email` y `organization`) | 13,6 s | 13,8 s |

Las dos vueltas son de lo obligatorio. Casi todo el tiempo es teclear. Los treinta segundos
dependen de si el teléfono ofrece rellenar esos tres campos, y **esto no es una medida con
personas**: la columna «Segundos» de la hoja de observación es la que lo contestará.

### La guarda y las reintroducciones

La guarda del CI suma dos comprobaciones a las tres de §25.7:

4. **Treinta segundos sin datos supuestos.**
   * Los obligatorios son exactamente los ocho; sobra o falta alguno, falla.
   * Ningún campo ni lista de la página tiene que ver con la facturación.
   * Un envío con solo lo obligatorio entra, y deja teléfono y facturación vacíos.
   * Cuatro envíos que solo difieren en la necesidad dan la misma puntuación, el mismo
     desglose, la misma probabilidad y el mismo tipo de actividad.
   * Una ficha nueva, un correo repetido y el campo trampa reciben la misma respuesta.
   * El campo trampa no deja ficha.
5. **El heurístico sin suposiciones.** Sin tamaño, cargo o sector, cada uno en sus tres formas,
   la regla da el punto medio. Y el servicio, puntuando una ficha real sin esos datos, también.

El límite comprueba además que tres visitas previas no gastan los envíos y que la lectura tiene
su propio límite.

| Defecto reintroducido | Detectado por |
| :--- | :--- |
| Sin tamaño se lee como «1-10» en la regla | Guarda |
| El servicio rellena el tamaño con «1-10» antes de llamar a la regla | Guarda |
| Sin cargo, la base de un estudiante | Guarda |
| Sin sector, la base de los no listados | Guarda |
| «Ver una demostración» vuelve a ser `DEMO_REQUEST` | Guarda |
| La necesidad se cuela como urgencia en la ficha | Guarda |
| Vuelve a preguntarse la facturación | Guarda |
| La ficha inventa una facturación | Guarda |
| El teléfono vuelve a ser obligatorio | Guarda |
| La empresa deja de ser obligatoria | Guarda |
| El campo trampa deja de descartar | Guarda |
| La respuesta delata un correo conocido | Guarda |
| La respuesta al campo trampa es distinta | Guarda |
| La ruta deja de aplicar el límite de envíos | Guarda |
| Aparece un campo de texto libre | Guarda |
| Abrir la página vuelve a gastar el cupo de enviar | Guarda |
| La lectura se queda sin límite | Guarda |
| El simulador vuelve a suponer «51-200» | `test_heuristico_sin_suposiciones.py` |
| El cálculo sin persistencia vuelve a suponer una visita | `test_heuristico_sin_suposiciones.py` |

**19 de 19**, y cada archivo restaurado con su huella comprobada. Las dos últimas no las mira
la guarda, porque el simulador necesita sesión; las atrapan las pruebas. La primera ronda dejó
una sin atrapar: el valor por defecto del cálculo sin persistencia no se alcanza por la API,
porque el esquema rellena antes. Se añadió una prueba que llama al servicio directamente.

---

## 25.9. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend | **956 pruebas**, 92 % de cobertura |
| Suite del cliente | **224 pruebas**, 94,3 % de cobertura de sentencias; suelo de cobertura cumplido |
| `ruff` y `eslint` | Sin avisos, sobre todo el repositorio (`ruff check .`) y todo el cliente (`eslint .`) |
| Guarda de la página pública | Pasa sobre el árbol correcto; 9 de 9 defectos reintroducidos la hacen fallar |
| Reintroducciones de las cuatro fases | 36 de 36 |
| Recorrido en el navegador, a 375 × 812 | El enlace copiado abre la página; un perfil pegado con parámetros de compartir se acepta y se guarda limpio; la ficha nace puntuada, atribuida, sin asesor y con `annual_revenue` vacío; un segundo envío con otros datos deja una ficha, dos actividades y los datos del asesor intactos |
| Recorrido del informe contra la base de la demo | El líder ve la publicación entera; el asesor, cero filas y «1 más»; comparativa y contador 403 para el asesor; una campaña «LinkedIn Ads» responde 404; tras asignar, el asesor ve su fila y el contador baja a 0 |
| Memoria | Regenerada con `compile_reports.py`, que ahora lista los capítulos 1 a 25 (§25.10) |
| Suites tras el formulario de treinta segundos (§25.8) | Backend **1004 pruebas**, 93 % de cobertura; cliente **235 pruebas**, cobertura del núcleo medido sin cambios (94,3 %); `ruff check .` y `eslint .` sin avisos |
| Guarda tras la simplificación | Pasa sobre el árbol correcto; 19 de 19 defectos reintroducidos atrapados (17 por la guarda, 2 por las pruebas) |
| Recorrido del formulario en el navegador, a 375 × 812 | Cabe en una pantalla (812 px de documento, sin desplazamiento lateral); vacío, ocho errores bajo sus campos y el foco en el primero; 35,1 s tecleando y 13,8 s con autocompletado hasta el «Gracias»; tres fichas iguales con necesidades distintas, las tres `FORM_SUBMIT` con 27,8 puntos, apellidos, teléfono y facturación vacíos |

Las cifras de las suites de la primera fila son las de la quinta fase; la fila del formulario
recoge las de después de la simplificación.

---

## 25.10. Lo que esta fase no hizo

* **No se hizo la sesión con personas.** La pila, el guion por papel, la hoja y el ensayo
  automático están; nadie se ha sentado todavía. Los cuatro atascos corregidos salieron de un
  ensayo propio, no de observar a nadie. Dos cosas quedaron anotadas para mirar con lupa y sin
  tocar, porque no impidieron ninguna tarea: la marca del listado desaparece en cuanto el
  prospecto tiene asesor —justo cuando el asesor va a buscarlo— y el contador de sin asignar
  vive en «Publicaciones», no en el tablero. *La primera la resolvió el capítulo 28 con la
  bandeja «Hoy»; la segunda sigue abierta, y es lo que hay que mirar en la sesión (§25.6).*
* **No se lee LinkedIn.** Ni Lead Sync ni Sign In with LinkedIn: las dos necesitan cuentas
  externas. El conector `linkedin-lead-gen` sigue aceptando una forma simplificada que no es
  la de `leadFormResponses` (H-5).
* **El canal `LinkedIn` no lo conoce el modelo.** El artefacto conoce «LinkedIn Ads», que es
  publicidad pagada; un post orgánico no lo es. Hasta reentrenar con desenlaces reales, estos
  prospectos puntúan con el canal como desconocido, es decir, neutro. No se reentrena sin esos
  desenlaces.
* **La tensión del tramo de facturación con R-1 se resolvió quitándolo** (§25.8): LinkedIn no
  lo da y el modelo no lo usaba.
* **«¿Qué necesitas?» no tiene peso.** Informa y nada más. Darle peso —que una demo pedida en
  la página cuente como interés— es una decisión de negocio que queda fuera, igual que
  reentrenar el modelo para que la lea.
* **Los treinta segundos no están medidos con personas.** Se midieron en el navegador con
  ritmos de referencia (§25.8); la hoja de observación tiene su columna para el dato real.
* **El país sigue supuesto.** La ficha escribe «México» cuando no llega (H-7). No puntúa en
  ninguna de las dos mitades del score, y quitarlo exige una migración de la columna.
* **H-4 está cerrado solo para este camino.** Las integraciones (`formulario_web`,
  `linkedin_lead_gen`, Calendly, WhatsApp) siguen sin atribuir la ficha a una campaña.
* **La asignación automática sigue siendo solo para las fichas `HOT`** (H-6, a medias): ahora
  hay dónde repartir, pero nada reparte solo.
* **No hay candidatos.** La historia es de prospectos comerciales; los perfiles que PluriOne
  coloca en sus clientes son otra historia.
* **La memoria tenía los capítulos 22 a 24 pegados a mano**, sin sus anclas: sus enlaces del
  índice no llevaban a ninguna parte. Se añadieron al compilador y la memoria se regeneró con
  él; el único cambio sobre esos capítulos son las anclas que les faltaban.
