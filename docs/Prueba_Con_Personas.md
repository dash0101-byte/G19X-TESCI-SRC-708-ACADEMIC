# Prueba con personas — «Del post de LinkedIn al prospecto puntuado»

Fase 4 del guion de la demo. Cuatro personas recorren la historia entera delante de quien
conduce la prueba. **No se explica nada antes de empezar**: lo que haya que explicar es
justo lo que hay que arreglar.

Quien conduce no ayuda salvo que la persona se quede parada más de un minuto. Entonces
anota *qué* tuvo que decir, porque esa frase es el defecto.

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

### Tres cosas que parecen fallos y no lo son

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
4. Pega ese texto en cualquier sitio donde se pueda leer (un bloc de notas) y pásale el
   enlace a quien hace de interesado.

### B. Interesado — **desde el teléfono**, sin cuenta

1. Abre el enlace que te acaban de pasar.
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

1. Averigua cuántas personas han llegado por LinkedIn y **todavía no tienen asesor**.
2. Mira qué ha traído la publicación nueva y compárala con la de agosto: cuál trajo más
   perfiles, cuál los trajo mejores.
3. Entra en la ficha de la persona que acaba de escribir y averigua **por qué publicación**
   llegó y qué necesita.
4. Asígnasela al asesor comercial (Alejandro Morales).

### D. Asesor — entra como `asesor.comercial@plurione.com`

1. Entra al panel y averigua si tienes algo nuevo que atender.
2. Abre la ficha de la persona que acaba de llegar de LinkedIn.
3. Responde, sin preguntarle a nadie: ¿de dónde salió?, ¿qué pidió?, ¿aceptó que le
   escribamos y cuándo?, ¿dónde está su perfil de LinkedIn?
4. Llámala (de mentira) y deja constancia de que la llamaste y de que no contestó.
5. Di qué harías mañana con ella.

---

## 2. Hoja de observación

Una hoja **por persona**. Quien conduce escribe; la persona no escribe nada.

**Persona:** ______________________  **Rol:** ____________  **Fecha:** __________
**Aparato:** teléfono / portátil  **Navegador:** ____________

| # | Tarea | ¿Sola? | Segundos | Dónde dudó (palabras suyas) | Qué hubo que decirle |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | | S / N | | | |
| 2 | | S / N | | | |
| 3 | | S / N | | | |
| 4 | | S / N | | | |
| 5 | | S / N | | | |

**«¿Sola?»** es «sí» solo si nadie le dijo nada. Una pista pequeña ya es un «no».

### Lo que hay que cazar

- **Atasco**: no consigue terminar la tarea sin ayuda. → se corrige en esta fase.
- **Duda**: lo consigue, pero se para, vuelve atrás o pregunta «¿esto es lo que quería?».
  → se corrige en esta fase si la palabra que falta está en pantalla.
- **Falta**: quiere hacer algo que el sistema no hace. → **no se toca ahora**; se anota
  abajo y se decide después.

> **Cerrado en el capítulo 28 (23-09-2026).** Los dos sitios de abajo se corrigieron sin
> esperar a la sesión: los dos describían a alguien **buscando**, y un sistema que sabe la
> respuesta y obliga a buscarla no está terminado. El panel abre ahora en «Hoy» con lo que
> le toca a cada uno, y el líder ve los HOT que se enfrían debajo de su propia bandeja. Se
> dejan escritos tal cual porque siguen siendo lo que hay que observar cuando la sesión se
> celebre: lo que se arregló fue el síntoma que se había anotado, no la prueba de que ya
> nadie tenga que buscar nada.

### Dos sitios donde mirar con lupa

Salieron del ensayo previo. No se han tocado porque no llegaron a impedir la tarea, y esta
fase corrige con notas de personas, no con sospechas:

- **El asesor, buscando lo nuevo.** La marca «Nuevo desde LinkedIn» del listado solo sale
  mientras el prospecto no tiene asesor: en cuanto el líder se lo asigna, desaparece. El
  asesor recibe una ficha más en una lista ordenada por score, y una que llega fría queda
  abajo. Anote cuánto tarda en encontrarla y si la busca por el nombre.
- **El líder, buscando el contador.** «Nuevos desde LinkedIn sin asesor» vive en la pestaña
  «Publicaciones». Anote si lo primero que mira es el tablero.

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
