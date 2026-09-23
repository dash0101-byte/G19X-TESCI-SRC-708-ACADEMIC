# Capítulo 28: El Sistema Dice Qué Hacer Hoy — Motor de Reglas, Tareas y Avisos

## 28.1. De dónde se parte

Los capítulos 25 a 27 construyeron el camino completo desde un post hasta un prospecto
puntuado: la publicación, su página, su enlace por red, su informe y su tarjeta al
compartirlo. Al final de ese camino hay una ficha con un número, un asesor asignado y una
persona esperando que alguien la llame.

Y ahí se acababa el sistema. A partir de ese punto todo dependía de que alguien se acordara
de mirar. La prueba con personas (`docs/Prueba_Con_Personas.md`) dejó anotados dos sitios
«para mirar con lupa», y los dos son el mismo hueco dicho de dos maneras:

> **El asesor, buscando lo nuevo.** La marca «Nuevo desde LinkedIn» del listado solo sale
> mientras el prospecto no tiene asesor: en cuanto el líder se lo asigna, desaparece. El
> asesor recibe una ficha más en una lista ordenada por score, y una que llega fría queda
> abajo.
>
> **El líder, buscando el contador.** «Nuevos desde LinkedIn sin asesor» vive en la pestaña
> «Publicaciones». Anote si lo primero que mira es el tablero.

Las dos notas describen a alguien buscando. Un sistema que sabe quién es el prospecto más
valioso de la cartera, cuándo llegó y quién lo atiende, y que aun así obliga a su asesor a
buscarlo en una lista, no está terminado: sabe la respuesta y no la dice.

Este capítulo hace que el sistema la diga. Seis reglas corren solas una vez al día y dejan,
para cada persona, una lista corta de lo que le toca hoy y una campana con lo que tiene que
enterarse. Nada sale del panel: ni correo, ni WhatsApp, ni un servicio externo.

---

## 28.2. Tareas y avisos: por qué son dos cosas

Una **tarea** se hace; un **aviso** se lee.

«Volver a llamar» pide un trabajo concreto y se cierra cuando ese trabajo ocurre. «Este HOT
lleva veinticuatro horas sin que nadie lo toque» no pide un trabajo concreto —puede
resolverse llamando, delegando o decidiendo que no vale la pena—: pide que alguien se
entere. Juntarlos en una tabla habría obligado a inventar un estado «leída pero no hecha» y
a decidir si un aviso sin leer cuenta como trabajo pendiente en la bandeja. Son dos tablas.

Tampoco son una actividad más. `lead_activities` guarda lo que **ya pasó**: una llamada, un
formulario, una reunión agendada. Una tarea es lo contrario, algo que todavía no ha pasado.
Meterla allí habría obligado a que el scoring, el decaimiento temporal y la ficha 360 —que
leen esa tabla entera— aprendieran a ignorar filas que no son hechos. Y hay una razón de
fondo: **una tarea pendiente no puede puntuar**. Nadie se vuelve más interesante porque a su
asesor le quede trabajo por hacer.

| | `tareas` | `avisos` |
| :--- | :--- | :--- |
| De quién | `asesor_id`: de quién es el trabajo | `usuario_id`: quién tiene que enterarse |
| Sobre quién | `lead_id` | `lead_id` |
| Qué la creó | `regla` + `clave` | `regla` + `clave` |
| Cuándo | `vence_el` | `creado_en` |
| Cómo se cierra | `estado`: abierta, hecha, cumplida | `leido_en` |

El `motivo` de una tarea y el `texto` de un aviso se escriben **sin datos de contacto**.
Viajan a la bitácora, a la exportación del titular y a cada respaldo; el nombre y la empresa
salen del prospecto al pintar la pantalla, donde ya estaban.

`leads` gana además una columna, `dormido_desde`. No es un cálculo sobre `last_activity_at`:
el motor necesita saber si **ya avisó**, y una consulta por fecha volvería a avisar cada
mañana mientras el prospecto siguiera quieto.

---

## 28.3. Dónde corre el motor, y por qué ahí

En la **pasada diaria que ya existe**: `backend/scripts/retencion_historial.py`, que resume
el historial de puntuación y aplica los plazos de conservación del capítulo 22. El motor
corre antes que las purgas —una tarea recién creada no se puede encontrar con que su
prospecto ya no está—, en el mismo proceso y con el mismo reloj.

No es un servicio nuevo, y es el mismo argumento del capítulo 22: *un proceso más que
supervisar es un proceso más que puede quedarse parado sin que nadie lo vea*. Sin colas, sin
planificador externo, sin n8n. El servicio `retencion-historial` del compose recibe los seis
plazos nuevos como variables de entorno, igual que ya recibía los de conservación.

---

## 28.4. Por qué todo se resuelve barriendo y no enganchándose

«Al asignar, tarea de primer contacto» invita a poner la creación de la tarea justo donde se
asigna. Es la solución obvia y es la equivocada, por una razón que este proyecto ya había
aprendido en otro sitio.

Asignar ocurre en **cinco** lugares: el alta de una ficha con asesor, la edición de la ficha,
el reparto de cartera de una baja (capítulo 19), la asignación automática de un prospecto
HOT y la ficha que nace con el responsable de su publicación (capítulo 26). Enganchar los
cinco funciona hasta que aparezca el sexto. Y el día que aparezca, **nadie recibirá un
error**: simplemente esas tareas no se crearán, y el asesor tendrá una bandeja que parece
correcta y está incompleta.

Es exactamente el razonamiento que llevó el alcance de cartera al repositorio en vez de a
cada endpoint (`app/core/autorizacion.py`): *el único sitio seguro para una regla es aquel
por el que hay que pasar obligatoriamente*.

Aquí ese sitio no es un suceso sino el estado. El motor no pregunta «¿se acaba de asignar
algo?», pregunta «¿hay algún prospecto asignado al que nadie haya contactado?». Da igual por
dónde se asignara, y una vía de asignación nueva queda cubierta el día que exista.

El precio es la **granularidad**: la tarea aparece en la pasada siguiente, no en el mismo
segundo. Para trabajo que se mide en días es un precio justo, y queda dicho aquí.

La excepción son los cierres, y van al revés (§28.7).

---

## 28.5. Las seis reglas

Todas viven en `app/services/motor_de_reglas.py`; su vocabulario —claves, etiquetas y orden
de ejecución— en `app/core/agenda.py`, para que el motor, el modelo, el esquema, el endpoint
y el cliente no escriban la misma cadena cinco veces.

| Regla | Qué mira | Qué deja | Plazo |
| :--- | :--- | :--- | :--- |
| `primer_contacto` | Prospecto asignado, sin contacto nuestro, de menos de un mes | Tarea a su asesor | `REGLA_PRIMER_CONTACTO_HORAS` (24) |
| `volver_a_llamar` | La **última** llamada acabó sin respuesta | Tarea, desde la llamada | `REGLA_VOLVER_A_LLAMAR_DIAS` (2) |
| `recordatorio_de_reunion` | Reunión agendada con fecha, mañana | Tarea que vence al empezar | `REGLA_RECORDATORIO_DE_REUNION_HORAS` (24) |
| `hot_sin_contacto` | HOT sin contacto durante horas | Aviso a su asesor | `REGLA_HOT_SIN_CONTACTO_HORAS` (24) |
| `hot_sin_contacto_lider` | Lo mismo, más tarde y ya avisado | Aviso a cada líder activo | `REGLA_HOT_LIDER_HORAS` (48) |
| `prospecto_dormido` | Sin ninguna actividad durante días | Marca en la ficha + aviso | `REGLA_DORMIDO_DIAS` (30) |

Cinco decisiones que no se ven en la tabla:

**Un correo abierto no es haberlo contactado.** Abrir un correo o visitar la web lo hace la
persona; contactar lo hacemos nosotros. Cuentan como contacto la llamada, la reunión
agendada, el mensaje de WhatsApp o de LinkedIn y la propuesta enviada. Confundirlos haría
que un prospecto muy interesado y completamente desatendido pareciera atendido, que es el
error más caro que esta regla puede cometer.

**Una llamada que nadie contestó sí cuenta como primer contacto.** El asesor hizo el
trabajo; que no hubiera nadie al otro lado lo recoge «volver a llamar». Lo contrario dejaría
las dos tareas abiertas a la vez sobre el mismo prospecto, que es justo el ruido que una
bandeja de trabajo no se puede permitir.

**Solo cuenta la última llamada.** Diez intentos seguidos sin respuesta son un trabajo
pendiente, no diez. Y la tarea vence **desde la llamada**, no desde hoy: si venciera desde
hoy, la pasada de mañana la aplazaría otra vez y nunca llegaría a estar vencida.

**El recordatorio necesita saber cuándo ES la reunión.** `occurred_at` es cuándo se agendó, y
una reunión agendada el martes puede ser el jueves. Calendly ya mandaba
`inicio_de_la_reunion`; ahora el panel también lo pide al asesor cuando la registra a mano,
con la misma clave. Una reunión sin fecha no se recuerda, y eso es mejor que recordarla el
día equivocado.

**«Primer contacto» tiene un corte por antigüedad**, y no es un número redondo: pasado el
plazo del dormido, de ese prospecto se ocupa la otra regla, y mandar a alguien a estrenar
una relación que lleva un mes muerta no ayuda a nadie. Ese corte es además lo que impide que
la primera pasada tras instalar el capítulo abra una tarea por cada prospecto antiguo de la
base.

### El escalado escala

El aviso al líder solo sube lo que **ya se avisó** al asesor y sigue igual. La comprobación
es explícita y no se deja en manos de que los plazos estén bien ordenados.

Y los plazos tienen un validador de **pareja**, no solo de campo: `REGLA_HOT_LIDER_HORAS`
tiene que superar a `REGLA_HOT_SIN_CONTACTO_HORAS`. Por separado, 24 y 24 son dos valores
perfectamente legales; juntos, hacen que las dos reglas disparen en la misma pasada y que el
líder se entere a la vez que la persona que todavía podía resolverlo. No falla nada, no se
rompe nada: simplemente el escalado deja de ser un escalado, y nadie lo nota hasta que el
líder se queja. Es el tipo de error que ningún validador de un solo campo puede ver.

---

## 28.6. Idempotencia: por qué la base decide y no el código

Ninguna regla comprueba si ya hizo su trabajo. Lo intenta y deja que el **índice único** de
la tabla lo rechace:

```
uq_tareas_regla_lead_clave        (regla, lead_id, clave)
uq_avisos_usuario_regla_lead_clave (usuario_id, regla, lead_id, clave)
```

Un `SELECT` previo seguido de un `INSERT` no da ninguna garantía: entre los dos cabe otra
pasada. Con el índice, la pasada puede repetirse cuantas veces haga falta —la misma mañana,
tras un reintento, después de una caída, dos veces por un despliegue— y dos pasadas
simultáneas tampoco duplican nada. Cada inserción va en un punto de guardado propio, para
que la colisión de una no arrastre a las demás.

El índice cubre también lo **cerrado**, y es deliberado: una tarea que ya se hizo no debe
volver a aparecer mañana por el mismo motivo.

La `clave` es lo que distingue dos episodios de la misma regla sobre el mismo prospecto, y
cada regla elige la suya con cuidado:

* **primer contacto** → el asesor. Si el prospecto se reasigna, la persona nueva estrena su
  propia tarea en vez de heredar una que ya se cerró.
* **volver a llamar** y **recordatorio** → la actividad concreta. Otro intento fallido mañana
  es otra tarea; el mismo intento releído por la pasada del jueves no lo es.
* **HOT sin contacto** y **dormido** → la fecha de la última actividad conocida. Con una
  clave fija, un prospecto que revive y vuelve a quedarse quieto no volvería a avisar jamás;
  con la fecha del día, avisaría cada mañana. La última actividad identifica el silencio.

El índice de los avisos incluye al destinatario porque el mismo hecho **sí** puede avisar a
dos personas distintas —al asesor primero y al líder después—: eso son dos avisos, no uno
repetido.

---

## 28.7. Lo que se cierra solo, se cierra en el momento

Una tarea que deja de tener sentido tiene que cerrarse **cuando pasa lo que esperaba**, no
en la pasada de mañana: hasta entonces el asesor vería en su bandeja una llamada que acaba
de hacer, y una bandeja que enseña trabajo ya hecho deja de creerse en una tarde.

`cerrar_lo_cumplido` la llama `registrar_evento`, que es el único sitio por el que se escribe
una actividad, dentro de su misma transacción y sin confirmar: si la actividad se descarta,
la tarea que cerró vuelve a estar abierta. La pasada diaria vuelve a llamar a **la misma
función** como barrido, para lo que se escribiera por un camino que no pase por ahí o antes
de que este capítulo existiera. Dos criterios de «esto ya está» acabarían discrepando.

Qué cierra cada cosa:

* cualquier contacto nuestro cierra «primer contacto»;
* una llamada **contestada** cierra «volver a llamar»; una que no se contesta, no, que es
  justo lo que esa tarea está esperando;
* pasada la hora de la reunión, su recordatorio deja de ser trabajo pendiente;
* cualquier actividad **despierta** al prospecto: la marca dice «nadie lo toca» y acaban de
  tocarlo.

Lo que cierra el sistema queda en estado `cumplida` y con `cerrada_por_id` nulo. Lo que
cierra una persona queda `hecha` y con su firma. «Lo hice» y «pasó» no son lo mismo, y el
informe del próximo capítulo querrá poder separarlos.

---

## 28.8. La bandeja «Hoy» y la campana

El panel abre en «Hoy». Es la pestaña primera y la que se ve al entrar, porque al llegar por
la mañana lo que se quiere saber es qué toca; el tablero cuenta cómo va todo, que es otra
pregunta y menos urgente.

Cada fila dice tres cosas y ninguna más: **qué** hay que hacer, **por qué** y **con quién**.
El nombre abre la ficha 360, que es donde está el teléfono y donde ese acceso queda
registrado como acceso a la ficha. Aquí no hay correo ni teléfono a propósito: esto es una
lista de trabajo, no un directorio, y repetirlos aquí los sacaría de ese registro.

**Va ordenada por score, no por fecha.** Por fecha pone arriba lo más viejo, que suele ser
también lo más frío, y deja al prospecto que más vale para después de comer. Lo vencido se
marca pero no cambia de sitio.

**«Hoy» son las próximas veinticuatro horas**, no lo que queda del día natural. La primera
versión cortaba por medianoche y tenía un fallo que solo se ve al juntarlo con el motor: la
pasada corre de madrugada y da veinticuatro horas de plazo, así que una tarea creada a las
03:00 del lunes vence a las 03:00 del martes. Con el corte por día natural, el lunes entero
esa tarea contaba como «más adelante» y la bandeja aparecía vacía **justo el día de hacer el
trabajo**; solo se asomaba el martes, ya vencida. Una bandeja que solo enseña lo que llega
tarde no dice qué hacer hoy: dice qué se hizo tarde ayer. Como efecto secundario, ahora a las
nueve de la mañana y a las once de la noche se ve lo mismo.

Lo de más adelante **se cuenta y no se enseña**: saber que hay trabajo después tranquiliza;
verlo hoy convierte la bandeja en otra lista larga que nadie termina.

La **campana** va en la barra y no dentro de una pestaña: un aviso tiene que poder verse se
esté donde se esté, y si hubiera que entrar a buscarlo dejaría de ser un aviso para ser otra
lista más. Abrir un aviso lo da por leído y lleva a la ficha; obligar a marcarlo aparte lo
convertiría en una segunda bandeja que también hay que vaciar a mano. Si el marcado falla, la
ficha se abre igual: lo que se pidió fue abrir al prospecto.

El líder ve además, debajo de su bandeja, **los HOT que se están enfriando y con qué asesor
están**. Es la única vista del capítulo que cruza carteras, y usa la misma consulta que la
regla que avisa, no una copia: si fueran dos, el líder acabaría viendo una lista distinta de
la que generó los avisos que está recibiendo. El asesor ni siquiera la pide, así que su panel
no depende de una llamada que le va a responder 403.

---

## 28.9. El alcance

| Ruta | Quién | Qué ve |
| :--- | :--- | :--- |
| `GET /api/v1/agenda/hoy` | Cualquiera | Lo suyo; el líder puede pedir la bandeja de alguien de su cartera |
| `POST /api/v1/agenda/tareas/{id}/hecha` | Su dueño | Cierra la tarea, con su firma |
| `GET /api/v1/agenda/avisos` | Cualquiera | Solo los suyos, sea cual sea el rol |
| `POST /api/v1/agenda/avisos/leidos` | Cualquiera | Marca los suyos |
| `GET /api/v1/agenda/enfriandose` | Líder y administrador | Los HOT desatendidos de toda la cartera |

Todo lo ajeno responde **404 y no 403**, igual que un prospecto ajeno (capítulo 15):
distinguir «no existe» de «no es tuyo» permitiría contar el trabajo del resto del equipo
recorriendo identificadores, sin ver una sola línea.

**Marcar hecha la cierra su dueño, y solo su dueño, aunque el líder la vea.** Verla y decir
«ya la hice» no son el mismo permiso: lo segundo es una afirmación sobre el trabajo de una
persona concreta. Si cualquiera pudiera vaciar la bandeja de otro, «hecha» dejaría de
significar que alguien lo hizo.

La campana es siempre la propia, incluso para el líder: un aviso tiene destinatario, y leer
el de otro no es una vista, es abrir su correo.

---

## 28.10. Lo que queda escrito, y lo que caduca

Cada regla de cada pasada deja un asiento en la bitácora: qué regla, cuántas tareas, cuántos
avisos, cuántas cerró, cuántos prospectos marcó y si falló. **Sin actor**, como la purga: esa
pasada no la pidió ninguna persona, la disparó el reloj. Sin datos de contacto: la bitácora
cuenta cuántos, nunca quiénes. Cerrar una tarea a mano sí lleva actor, porque eso lo afirmó
alguien.

Una regla que falla **no impide las demás**: cada una va en su transacción y queda con su
`ERROR` en la bitácora. Es el mismo criterio que los plazos de conservación, y por el mismo
motivo: que el recordatorio de las reuniones falle un martes no puede dejar sin avisar a
nadie de los HOT desatendidos de ese martes.

Las dos tablas nacen dentro de la tabla de conservación del capítulo 22 y dentro de los
derechos del titular del capítulo 20 —lo que el sistema mandó hacer sobre una persona y a
quién se lo avisó también es tratamiento de sus datos—. Pero **solo caduca lo cerrado**:

* una tarea **abierta** no se borra por vieja. Sigue siendo trabajo que nadie hizo, y
  borrarla sería hacerla desaparecer en lugar de hacerla: la bandeja quedaría limpia sin que
  hubiera ocurrido nada, que es exactamente lo contrario de lo que este capítulo busca. Si
  una tarea de hace un año molesta, se marca hecha.
* un aviso **sin leer** tampoco: nadie se ha enterado todavía de lo que decía.

Los seis plazos del motor son configurables y tienen mínimo, igual que los de conservación.
Allí el daño de un `0` escrito por error era borrar; aquí es lo contrario, inundar, y el
resultado práctico es el mismo: una bandeja con cuarenta tareas de la misma mañana no se lee,
y el sistema deja de decir qué hacer hoy.

---

## 28.11. Que nada de esto sea decorativo

Además de la suite, una guarda del CI —`scripts/guarda_del_motor_de_reglas.py`— comprueba
**propiedades** y no casos, con paso propio en el CI. Falla, diciendo qué defensa se perdió,
si el motor:

1. **duplica** al repetir la pasada;
2. **deja de escalar**: el líder se entera antes, a la vez, o de algo que el asesor no vio;
3. **sale del panel**: aparece un cliente de correo, de HTTP o de mensajería;
4. **mueve el score**;
5. **pierde el alcance**: un asesor ve o cierra trabajo ajeno, o lo ajeno no responde 404;
6. **convierte la bandeja en un directorio**: vuelve el correo o el teléfono;
7. **crea algo sin plazo**, o empieza a caducar lo que sigue abierto o sin leer;
8. **corre a ciegas**: una regla deja de ejecutarse o deja de anotar qué hizo.

Por qué además de la suite: `test_motor_de_reglas.py` comprueba casos. Una regla nueva que
alguien olvide meter en el orden de ejecución no rompe ninguna prueba —la suya la llama a
mano— y aquí falla en cuanto existe.

Y sobre la guarda, el arnés de siempre: **31 defectos reintroducidos** uno a uno, cada uno
con su comprobación esperada, restaurando el árbol y verificando el hash de cada archivo.
Los 31 se detectan.

---

## 28.12. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Backend | **1282 pruebas**, 93 % de cobertura |
| Cliente | **324 pruebas** en 23 ficheros |
| `ruff` y `eslint` | Sin avisos, sobre todo el repositorio y todo el cliente |
| Guarda del motor de reglas | Ocho comprobaciones; pasa |
| Reintroducción de defectos | **31 de 31** detectados; todos los ficheros restaurados con el hash verificado |
| Migración | Ida y vuelta con Alembic de verdad; sin deriva contra los modelos |
| Idempotencia sobre la base de la demostración | Primera pasada: 12 tareas de primer contacto, 4 avisos al asesor, 4 escalados al líder. Segunda pasada: **cero** |
| Paquete de producción | Sigue saliendo con los nombres fijos que el capítulo 27 necesita (`assets/app.js`, `assets/app.css`) |
| Ensayo del guion | Los cuatro papeles pasan; el del asesor ahora encuentra su prospecto en «Hoy» en vez de buscarlo |

---

## 28.13. Lo que este capítulo no hizo

* **No sale nada del panel.** Ni correo, ni WhatsApp, ni notificación de navegador. Queda
  fuera a propósito: un aviso que sale del sistema necesita una cuenta externa, una dirección
  verificada y una política de qué hacer cuando rebota, y sobre todo saca de la aplicación el
  nombre de una persona que aceptó un aviso de privacidad para otra cosa.
* **El usuario no escribe reglas.** Las seis están en el código, con sus plazos
  configurables. Un editor de reglas es un lenguaje, y un lenguaje es otro capítulo.
* **No se reentrena el modelo.** Ni las tareas ni los avisos llegan al score, y eso es una
  garantía comprobada, no un olvido.
* **La granularidad es de un día.** Una asignación de las diez de la mañana produce su tarea
  en la pasada siguiente, no a las diez y un minuto (§28.4). Los cierres sí son inmediatos.
* **El panel no se ha recorrido con una persona dentro.** Las pantallas están comprobadas por
  la suite del cliente y el ensayo automático del guion, pero entrar al panel exige iniciar
  sesión, y eso no se hace desde aquí. La sesión con personas sigue sin celebrarse
  (capítulo 25, §25.10).
* **Nadie ha vivido una semana con la bandeja.** Si las seis reglas producen la cantidad
  adecuada de trabajo —ni tan poco que sobre, ni tanto que se ignore— es justo lo que solo se
  puede saber usándola varios días seguidos. Los plazos se dejan configurables por eso.
