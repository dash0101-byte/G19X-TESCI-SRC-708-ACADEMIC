# Prueba con personas — «Del post de LinkedIn al prospecto puntuado»

Fase 4 del guion de la demo. Cuatro personas recorren la historia entera delante de quien
conduce la prueba. **No se explica nada antes de empezar**: lo que haya que explicar es
justo lo que hay que arreglar.

Quien conduce no ayuda salvo que la persona se quede parada más de un minuto. Entonces
anota *qué* tuvo que decir, porque esa frase es el defecto.

> **Esto no es el guion de la exposición.** Aquí las tareas se escriben **sin decir dónde
> pulsar**, porque lo que se mide es si la persona lo encuentra sola. Para enseñar la
> demostración —donde sí se dice dónde pulsar, y cada paso lleva su frase— está el
> [guion cronometrado](Guion_Cronometrado_de_la_Demo.md).

---

---

## 0. Preparar la pila (quien conduce, 10 minutos antes)

```bash
python scripts/preparar_prueba_con_personas.py --force
```

Vacía y regenera los datos de demostración, **copiando antes la base** (deja el fichero
`…antes-de-la-prueba-<fecha>` junto a ella). Al terminar imprime el enlace de la publicación
de ejemplo y las cuentas con su contraseña.

Después, levantar la pila:

- **Backend**: `http://localhost:8000` — sin reiniciarlo durante la prueba. Si no hay una
  `SECRET_KEY` definida, el backend firma con una clave nueva en cada arranque y **todos
  tendrán que volver a entrar**; el preparador avisa cuando es el caso.
- **Panel**: `http://localhost:3000`.
- **El teléfono del «interesado»**. Con el navegador del portátil en modo teléfono no hay
  nada que preparar. Con un teléfono de verdad hacen falta dos cosas, y las dos **antes** de
  levantar la pila, porque si no el interesado se queda mirando una página que no carga:

  ```bash
  # 1. servir el panel en la red, no solo en localhost
  npm run dev:lan --prefix frontend

  # 2. que el enlace que copia marketing lleve la dirección de la máquina, no «localhost»
  #    (el preparador imprime la suya; vuelva a lanzarlo después de definirla)
  PUBLICACIONES_URL_BASE=http://192.168.x.x:3000/interes
  ```

  El panel queda accesible para cualquiera en esa red: hágalo solo en una de confianza y
  apague el servidor al terminar. El backend sigue escuchando en `localhost`; el teléfono
  llega a la API por el proxy del propio panel.

Lo que queda preparado:

| | |
| :--- | :--- |
| Publicación de ejemplo | «Post · Equipos de TI en 30 días (agosto)», con 3 perfiles ya recibidos |
| Prospectos | 12 de cartera repartida + 3 de la publicación de ejemplo, **sin asesor** |
| Cuentas | líder (marketing y dirección), asesor, administración |

### Cuatro cosas que parecen fallos y no lo son

Para quien conduce. Si pasa alguna de estas, **no** se apunta como atasco de la persona:

- **El panel no se actualiza solo.** Cuando el interesado envía su perfil, el líder tiene
  que recargar la pestaña para verlo. No hay sondeo, y es a propósito.
- **Un correo repetido no crea ficha nueva.** Si el interesado usa un correo que ya está en
  la base —por ejemplo porque se repite el ejercicio—, la solicitud se suma al historial de
  esa ficha y no aparece nadie nuevo. La página responde lo mismo en los dos casos, a
  propósito: así no sirve para averiguar quién está registrado. Cambie el correo en cada
  vuelta.
- **Diez envíos por hora y por IP.** Si varias personas hacen de interesado desde la misma
  red, el undécimo envío recibe «Hemos recibido demasiadas solicitudes». Para una sesión
  larga, levante el backend con `INTERES_LIMITE_POR_IP=60/hour`. Abrir la página no gasta
  esos diez: las lecturas tienen su propia cuenta (120 por hora).
- **La bandeja «Hoy» del asesor no estrena tarea con el prospecto que acaban de asignarle.**
  Las tareas no las crea la pantalla: las crea el motor de reglas, que pasa **una vez al
  día** y sin nadie delante (`services/agenda_del_dia.py` explica por qué: si las creara
  quien mira, «cuántas tareas hay» dependería de cuánta gente hubiera entrado esa mañana).
  Así que durante la sesión el asesor encuentra al prospecto en su cartera y en la ficha,
  con la tarjeta «Llegó por», pero no en «Hoy». Lo que sí se apunta es si **busca** la tarea
  ahí y no entiende por qué no está: eso es un atasco de verdad y hay que anotarlo.

---

## 1. Tareas por rol

Cada persona recibe **solo su lista**, sin las demás. Las tareas están escritas como lo que
quiere conseguir, no como los clics que hay que dar: si la tarea dice dónde pulsar, la
prueba ya no mide nada.

El orden importa: la tarea 4 del líder ocurre **antes** de que el asesor empiece, porque un
prospecto que llega de LinkedIn no tiene asesor hasta que alguien se lo asigna.

### A. Marketing — entra como `lider.ventas@plurione.com`

1. Entra al panel.
2. Crea una publicación para anunciar en LinkedIn que PluriOne monta equipos de TI en 30
   días. Ponle el texto que publicarías de verdad y di a quién va dirigida.
3. Consigue el texto listo para pegar en LinkedIn, **con su enlace**, sin escribirlo a mano.
4. La misma publicación va también por **WhatsApp**. Consigue el texto de WhatsApp, y
   después di en voz alta si crees que los dos enlaces son el mismo o son distintos.
5. Pega el texto de WhatsApp en cualquier sitio donde se pueda leer (un bloc de notas) y
   pásale **ese** enlace a quien hace de interesado.

> La tarea 4 trae el capítulo 27. Lo que se observa no es si encuentra el botón, sino qué
> contesta: si dice «el mismo», el panel no le ha explicado para qué sirven las redes, y
> todo el informe por red de la tarea 3 del líder se vuelve inexplicable.

### B. Interesado — **desde el teléfono**, sin cuenta

1. Abre el enlace que te acaban de pasar. **Tal cual**, sin quitarle nada.
2. Decide si lo que ofrece te interesa: lee lo que dice la página.
3. Pide que te contacten. Eres **Lucía Prado**, *Head of Engineering* en *Fábrica de
   Software Norte* (unos 80 empleados, software). Necesitas cubrir vacantes de TI.
   Usa un correo que te inventes con el dominio `@ejemplo-demo.mx`.
4. Si quieres dejar tu perfil de LinkedIn, usa `linkedin.com/in/lucia-prado-demo`. No es
   obligatorio.
5. Al terminar, di en voz alta qué crees que va a pasar ahora.

> Quien conduce **cronometra la tarea 3**, desde que la persona empieza a escribir hasta que
> pulsa «Quiero que me contacten», y lo anota en la columna «Segundos». El formulario está
> pensado para unos treinta segundos; si pasa del minuto, anotar en qué campo se paró.

### C. Líder — entra como `lider.ventas@plurione.com`

1. Averigua cuántas personas han llegado por una publicación y **todavía no tienen asesor**.
2. Mira qué ha traído la publicación nueva y compárala con la de agosto: cuál trajo más
   perfiles, cuál los trajo mejores.
3. Averigua **por qué red** llegó la persona que acaba de escribir: se repartió por dos.
4. Entra en su ficha y averigua **por qué publicación** llegó y qué necesita.
5. Asígnasela al asesor comercial (Alejandro Morales).
6. Antes de salir, di si hay algún prospecto **caliente que se esté enfriando** y con quién
   está.

> Las tareas 3 y 6 son de los capítulos 27 y 28. En la 1, apunte si lo primero que mira es
> el tablero: el contador vive en «Publicaciones». En la 6, si busca en algún sitio antes
> de mirar su propia bandeja.

### D. Asesor — entra como `asesor.comercial@plurione.com`

1. Entra al panel y averigua si tienes algo que hacer hoy. **Antes de tocar nada**, di en
   voz alta qué crees que te está pidiendo el sistema y por qué.
2. Abre la ficha de la persona que acaba de llegar.
3. Responde, sin preguntarle a nadie: ¿de dónde salió?, ¿qué pidió?, ¿aceptó que le
   escribamos y cuándo?, ¿dónde está su perfil de LinkedIn?
4. Llámala (de mentira) y deja constancia de que la llamaste y de que no contestó.
5. Deja el trabajo de hoy como lo dejarías de verdad al terminar con ella.
6. Di qué esperas encontrarte mañana al entrar.

> Las tareas 1, 5 y 6 son del capítulo 28. La 1 es la que más importa: hasta el capítulo 28
> el asesor tenía que **buscar** la ficha nueva en una lista ordenada por score. Si ahora
> sigue yéndose a «Prospectos» en lugar de leer lo que tiene delante, la bandeja no ha
> resuelto nada y hay que anotarlo tal cual.
>
> En la 5, **no** se le dice que existe «Ya está». Si cierra la tarea, la bandeja le está
> hablando; si no, apunte qué hizo en su lugar —recargar, salir, dejarlo abierto—.

---

## 2. Hoja de observación

Una hoja **por persona**. Quien conduce escribe; la persona no escribe nada.

> **Rellénela en fichero, no aquí.** La tabla de abajo describe qué se anota; para anotarlo
> de verdad:
>
> ```bash
> python scripts/hojas_de_observacion.py crear
> ```
>
> Deja una hoja por papel en `docs/hojas_de_observacion/`, con las tareas ya escritas —las
> saca de este mismo documento— y un hueco por campo. Al terminar la sesión:
>
> ```bash
> python scripts/hojas_de_observacion.py leer
> ```
>
> arma la tabla de vaciado de §3 y dice si el criterio «nadie se atasca» se cumple. Con las
> hojas en blanco responde «SIN DATOS», que es la respuesta correcta hasta que alguien se
> siente delante.

**Persona:** ______________________  **Rol:** ____________  **Fecha:** __________
**Aparato:** teléfono / portátil  **Navegador:** ____________

| # | Tarea | ¿Sola? | Segundos | Dónde dudó (palabras suyas) | Qué hubo que decirle |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | | S / N | | | |
| 2 | | S / N | | | |
| 3 | | S / N | | | |
| 4 | | S / N | | | |
| 5 | | S / N | | | |
| 6 | | S / N | | | |

Seis filas porque las listas más largas —líder y asesor— tienen seis tareas desde los
capítulos 27 y 28. Las que tengan menos dejan las últimas en blanco.

**«¿Sola?»** es «sí» solo si nadie le dijo nada. Una pista pequeña ya es un «no».

### Lo que hay que cazar

- **Atasco**: no consigue terminar la tarea sin ayuda. → se corrige en esta fase.
- **Duda**: lo consigue, pero se para, vuelve atrás o pregunta «¿esto es lo que quería?».
  → se corrige en esta fase si la palabra que falta está en pantalla.
- **Falta**: quiere hacer algo que el sistema no hace. → **no se toca ahora**; se anota
  abajo y se decide después.

> **Estado a 23-09-2026 (capítulos 28 y 29).** De los dos sitios de abajo, **uno se cerró y
> el otro sigue abierto**. La nota que había aquí decía que los dos, y no era verdad: lo que
> el capítulo 28 le dio al líder son los HOT que se enfrían, que es otra pregunta distinta
> de cuántos están esperando a que los repartan. Se corrige aquí porque una hoja de
> observación que se da la razón a sí misma no sirve para observar nada.
>
> - **El asesor, buscando lo nuevo: cerrado.** El panel abre en «Hoy» y dice qué toca. La
>   marca del listado, además, dejó de preguntar por «LinkedIn» en el capítulo 29.
> - **El líder, buscando el contador: abierto.** Sigue en la pestaña «Publicaciones». Es la
>   tarea 1 de su lista, y es lo que hay que mirar en la sesión.
>
> Los dos se dejan escritos tal cual. Lo que se arregló del primero fue el síntoma que se
> había anotado, no la prueba de que ya nadie tenga que buscar nada.

### Dos sitios donde mirar con lupa

Salieron del ensayo previo. Se escriben como estaban, porque lo que hay que observar es lo
mismo aunque una de las dos ya se haya tocado:

- **El asesor, buscando lo nuevo.** La marca del listado solo sale mientras el prospecto no
  tiene asesor: en cuanto el líder se lo asigna, desaparece. El asesor recibía una ficha más
  en una lista ordenada por score, y una que llega fría queda abajo. Anote cuánto tarda en
  encontrarla, si la busca por el nombre, y —desde el capítulo 28— si llega a mirar «Hoy» o
  se va derecho a «Prospectos» por costumbre.
- **El líder, buscando el contador.** El contador de los que esperan asesor vive en la
  pestaña «Publicaciones». Anote si lo primero que mira es el tablero.

### Frases que hay que apuntar tal cual

Cuando alguien diga algo de este estilo, se copia literal: es la etiqueta que falta.

- «¿y esto dónde se ve?»
- «¿esto lo ve el cliente?»
- «pensé que ya estaba guardado»
- «¿cuál de los dos es?»
- «esto no es lo que yo llamo …»

### Al terminar cada persona (dos minutos)

1. ¿Qué pensaste que iba a pasar y no pasó?
2. ¿Qué palabra de la pantalla no significaba lo que tú creías?
3. Si esto fuera tu trabajo de mañana, ¿qué te faltaría?

---

## 3. Vaciado y decisión

| Nº | Rol | Qué pasó | Tipo | Qué se cambia |
| :-: | :--- | :--- | :--- | :--- |
| 1 | | | atasco / duda / falta | |
| 2 | | | | |
| 3 | | | | |

Regla de la fase: **solo se corrige lo que bloquea o confunde**. Lo que aparezca y sea
funcionalidad nueva se anota en la última columna como «para después» y se lleva al
documento del guion (`Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md`, sección 4),
que es donde viven los huecos.

### Estado de esta hoja, a 23-09-2026

**La tabla de arriba está vacía y es correcto que lo esté: la sesión con personas todavía no
se ha celebrado.** Se deja en blanco a propósito. Rellenarla con lo que se supone que dirá
alguien convertiría este documento en lo contrario de lo que es.

Lo que sí hay son notas de **ensayo**, de recorrer el guion sin nadie delante. Valen para
arreglar lo que está roto; no valen para decir que alguien entendió una pantalla. Van
clasificadas con los mismos tres tipos, y con su origen dicho:

| Nº | Origen | Qué pasaba | Tipo | Qué se hizo |
| :-: | :--- | :--- | :--- | :--- |
| E-1 | Ensayo, fase 4 | El enlace copiado llevaba a la pantalla de acceso | bloquea | Corregido (§4) |
| E-2 | Ensayo, fase 4 | El perfil de LinkedIn se rechazaba pegado tal cual | bloquea | Corregido (§4) |
| E-3 | Ensayo, fase 4 | El panel solo se servía en `localhost` | bloquea | Corregido (§4) |
| E-4 | Ensayo, fase 4 | El error empezaba por «Value error,» | confunde | Corregido (§4) |
| E-5 | Ensayo, fase 4 | El asesor tenía que buscar la ficha nueva en una lista por score | confunde | Corregido en el capítulo 28: bandeja «Hoy» |
| E-6 | Ensayo, fase 4 | El contador de sin asignar vive en «Publicaciones», no en el tablero | confunde | **No corregido.** Sigue ahí; es lo que mide la tarea 1 del líder |
| E-7 | Ensayo, capítulo 29 | El contador decía «Nuevos desde LinkedIn» y contaba seis redes, mientras el listado solo marcaba las de LinkedIn: el número y la lista no cuadraban | confunde | Corregido (§5) |
| E-8 | Ensayo, capítulo 29 | El ensayo automático tiraba la parte de la consulta, así que no podía notar que se perdiera la red de llegada | bloquea (la prueba, no el panel) | Corregido (§5) |
| I-1 | Guion, hueco H-6 | Un prospecto de publicación llega sin asesor salvo que salga `HOT` | idea para después | Sin tocar; sigue en el guion |
| I-2 | Capítulo 28 | Las reglas las escribe el sistema, no el usuario | idea para después | Fuera de alcance, escrito en el Reporte 28 |

**E-6 se deja a propósito.** Es exactamente la clase de nota que esta fase existe para
resolver *con personas*: mover un contador de pestaña porque a uno le parece es cambiar una
pantalla por una corazonada. Si en la sesión el líder mira el tablero primero, se mueve.

### El criterio «nadie se atasca»: **no cumplido**

No por haber fallado, sino por no haberse medido. Un criterio que habla de personas solo lo
cumplen personas. Lo que hay hasta ahora es:

- las cuatro listas de tareas recorridas **automáticamente** en cada ejecución del CI
  (`frontend/src/EnsayoDelGuion.test.jsx`), incluidas las tareas nuevas de los capítulos 27
  y 28;
- ocho notas de ensayo, siete de ellas corregidas;
- cuatro hojas listas para rellenar, y **cero rellenadas**.

El veredicto ya no lo da nadie de palabra: `hojas_de_observacion.py leer` lo calcula de las
hojas y hoy responde «SIN DATOS». Cuando se celebre la sesión, esa misma orden dirá
«CUMPLIDO» o nombrará los atascos, y esta sección se reescribe con lo que diga.

Lo que un ensayo automático no puede decir, y por lo que la sesión sigue pendiente: si la
palabra que hay en pantalla significa para la persona lo que significa para quien la
escribió. Una prueba que busca «Llamar por primera vez» lo encuentra siempre; un asesor que
no sepa qué se espera de él al leerlo se queda parado, y eso no lo detecta ninguna prueba.

---

## 4. Lo que ya se corrigió antes de sentar a nadie

Ensayo previo de esta misma fase, recorriendo el guion con los cuatro papeles. Tres cosas
paraban a una persona de verdad y están arregladas:

| Qué pasaba | Por qué importaba | Qué se cambió |
| :--- | :--- | :--- |
| El enlace copiado llevaba a `/p/<enlace>`, y el panel solo atiende `/interes/<enlace>` | Quien seguía el enlace ya publicado veía la **pantalla de acceso**. Escribiendo la dirección a mano no se notaba | `PUBLICACIONES_URL_BASE` apunta a `/interes`, y una prueba compara ese valor con la ruta de verdad del panel |
| El perfil de LinkedIn se rechazaba si se pegaba tal cual | El botón «compartir» de LinkedIn añade `?utm_source=share&utm_medium=member_ios`, y quien lo escribe a mano no pone `https://`. Las dos formas daban error | El servidor completa el esquema y quita los parámetros antes de comprobarlo; el campo dejó de ser `type="url"`, que lo bloqueaba en el propio navegador |
| El panel solo se servía en `localhost` | La tarea del interesado dice «desde el teléfono», y desde un teléfono no cargaba nada: la prueba no se podía ni empezar | `npm run dev:lan`, y el preparador imprime la dirección de la máquina y recuerda que el enlace tiene que llevarla |
| El error decía «linkedin: **Value error**, El perfil tiene que ser…» | «Value error» es el nombre interno de una excepción de Pydantic delante de una frase ya escrita para leerse | El panel quita ese prefijo en todos los mensajes de validación |

Las cuatro listas de tareas de la sección 1 están además **ensayadas automáticamente** en
`frontend/src/EnsayoDelGuion.test.jsx`: recorre las mismas tareas, en el mismo orden, sobre
la aplicación entera y contra un servidor simulado con las respuestas que da el backend de
verdad. Si una tarea deja de poderse terminar —una ruta que cambia, un botón que
desaparece, una ficha que ya no dice de dónde vino—, esa prueba falla antes de que nadie se
siente delante. Lo que no puede decir es si la persona **entiende** lo que ve: para eso es
la hoja.

Conocido y **no** corregido aquí, porque es funcionalidad y no un atasco del guion: un
prospecto de LinkedIn llega sin asesor y solo se asigna solo si sale `HOT` (hueco **H-6**
del guion). Por eso el líder reparte antes de que el asesor empiece.

---

## 5. Lo que se corrigió al añadir las tareas nuevas (23-09-2026)

Añadir al guion lo que trajeron los capítulos 26, 27 y 28 —repartir por dos redes, y el
asesor atendiendo desde «Hoy»— destapó dos cosas. Las dos se corrigieron, porque las dos
entran en «bloquea o confunde»; ninguna es funcionalidad nueva.

| Qué pasaba | Por qué importaba | Qué se cambió |
| :--- | :--- | :--- |
| El contador del líder decía **«Nuevos desde LinkedIn sin asesor»** y contaba los seis canales de publicación; el listado, en cambio, solo marcaba `source === 'LinkedIn'` | El líder leía «3 esperando» e iba a la lista a repartirlos: encontraba **una** marca. Dos números que no cuadran y ninguna manera de saber cuál miente. Con una sola red nunca se notó; con seis, dos de cada tres fichas quedaban invisibles | La condición pasa al servidor, que ya la tenía para el contador: `LeadResponse.esperando_asesor` la calcula con la misma `es_de_publicacion`, y el listado solo la dibuja. La marca pasa a decir **«Nuevo, sin asesor»**, sin nombrar red —la red ya está en esa misma celda— y el contador, «Nuevos de publicaciones, sin asesor» |
| El ensayo automático **tiraba la parte de la consulta** de cada petición | La red por la que se repartió el enlace viaja ahí (`?r=whatsapp`). El ensayo no podía ver la atribución, así que habría dado por bueno un panel que la perdiera entera: justo lo que el capítulo 27 añadió | El servidor simulado guarda la consulta aparte. El interesado entra ahora por el enlace de WhatsApp y el ensayo comprueba que la etiqueta viaja **en la apertura y en el envío** |

Las dos llevan prueba: `tests/test_una_publicacion_varias_redes.py` compara el contador con
las fichas marcadas y falla si vuelven a separarse, y el ensayo del guion cubre las tareas
nuevas de los dos papeles.
