# Guion cronometrado de la demostración

**Ensayado el 24 de septiembre de 2026** sobre la base de demostración, de principio a fin.
**Duración de la parte demostrada: 4 minutos 30 segundos.**

---

## 1. Qué es esto y qué no es

Es el reloj de la demostración: qué se enseña, en qué orden, cuántos segundos dura cada
cosa y **qué frase hay que decir** mientras se carga cada pantalla.

**No es** el guion de la historia —eso es
[Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md](Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md),
que explica las reglas que la gobiernan— ni el guion de la prueba con personas —eso es
[Prueba_Con_Personas.md](Prueba_Con_Personas.md), donde las tareas están escritas **sin**
decir dónde pulsar, precisamente para medir si alguien lo encuentra solo—.

Aquí sí se dice dónde pulsar. Es una exposición, no una prueba de usabilidad.

### De dónde salen los tiempos

Dos relojes distintos, y conviene no confundirlos:

| Reloj | Qué mide | De dónde sale |
| :--- | :--- | :--- |
| **Los segundos de cada paso** | Lo que tarda **quien expone** en enseñarlo y contarlo | Repartidos a mano sobre los 4:30 del hueco de la demostración. Son un presupuesto, no una medición |
| **Los milisegundos de servidor** | Lo que tarda **la API** en contestar | Medidos: `python scripts/ensayo_de_la_demo.py`, que recorre los nueve pasos contra la API de verdad y los cronometra |

El segundo reloj sirve para una sola pregunta: **¿hay algún paso que tarde lo bastante como
para que se note el silencio?** La respuesta, hoy, está en §5.

---

## 2. Paso 0: antes de que entre nadie

**Diez minutos antes.** Ninguno de estos puntos es opcional y todos han fallado alguna vez.

| # | Qué | Por qué |
| :---: | :--- | :--- |
| 1 | **Levantar la pila** con `python devops/pila.py up` | Es el único camino que carga las variables de entorno completas |
| 2 | **Preparar la base**: `python scripts/preparar_prueba_con_personas.py --force` | Deja sembrada la publicación de agosto con perfiles ya recibidos. Sin ella, la comparativa del paso 7 tiene **una sola fila y no compara nada** |
| 3 | **Definir `SECRET_KEY`** antes de levantar | Sin ella el backend firma con una clave nueva en cada arranque: si se reinicia en mitad de la demostración, todo el mundo se queda fuera |
| 4 | **Hacer un envío de prueba en la página pública y borrarlo** | Ver el recuadro de abajo. Es el punto que más fácil se olvida y el que peor se ve |
| 5 | **Abrir las cuatro pestañas** en el orden del guion, ya con sesión iniciada: «Publicaciones», «Prospectos», «Hoy», «Desenlaces» | Iniciar sesión delante del sínodo gasta veinte segundos y no demuestra nada |
| 6 | **Dejar el teléfono con el enlace ya abierto**, si se va a usar uno de verdad | El panel escucha en `localhost`: desde un teléfono no se abre nada sin `PUBLICACIONES_URL_BASE` apuntando a la dirección de la máquina en la red (el preparador lo avisa) |

> ### El calentamiento del modelo
>
> El artefacto de Machine Learning se deserializa **la primera vez que alguien puntúa**, y
> se queda en memoria para el resto de la vida del proceso.
>
> Medido en el ensayo: esa primera carga tarda entre **3 y 4 segundos**, y se paga una
> sola vez.
>
> En una pila recién levantada, ese «primera vez» cae exactamente en el envío del
> interesado, que es el instante de la demostración en el que todo el mundo está mirando la
> pantalla. Con un envío de prueba antes, el paso 3 entero —abrir la página, validar,
> crear la ficha y **puntuarla**— tarda **286 ms**; sin él, más de **tres segundos** de
> pantalla quieta.
>
> No es un defecto y no se arregla cargando el modelo al arrancar: verificar la huella del
> artefacto en el arranque retrasaría la pila entera por algo que la mayoría de los
> despliegues no necesita en el primer segundo. Se arregla con el punto 4 de la lista.
>
> El ensayo lo provoca a propósito antes de empezar y lo cronometra aparte, para que los
> tiempos de §5 sean los de verdad y no los del arranque.

---

## 3. El reloj de la exposición completa (10 minutos)

La demostración no es una sección más: es la **columna vertebral**. Todo lo anterior existe
para explicar lo que se va a ver, y todo lo posterior para explicar lo que se acaba de ver.

| Tiempo | Bloque | En una frase |
| :---: | :--- | :--- |
| **0:00 – 1:00** | Portada y contexto | Quién, dónde, y que todo lo que se va a ver son datos sintéticos |
| **1:00 – 2:00** | El problema | 36 horas de latencia, 12 % de conversión, atención FIFO. Y la restricción: local, a coste cero, con salida a Azure |
| **2:00 – 3:00** | La arquitectura, en una diapositiva | Puertos y adaptadores; el score híbrido 60/40 con decaimiento exponencial de vida media 14 días |
| **3:00 – 7:30** | **LA DEMOSTRACIÓN** — §4 | Del post a la red social hasta el dato de entrenamiento |
| **7:30 – 8:45** | Calidad, seguridad y operación | 2093 + 748 pruebas, 99 % de cobertura con ramas, 10 trabajos de CI, 61 controles y siete guardas de propiedades |
| **8:45 – 10:00** | Lo que se negó a hacer, y cierre | Por qué no se reentrenó, por qué no hay pesos inventados, y qué queda |

---

## 4. La demostración, segundo a segundo

**4 minutos 30.** Los nueve pasos del recorrido; el README los cuenta como ocho porque mete
el del asesor dentro del quinto.

> **La regla de oro:** nunca se pulsa en silencio. Cada paso tiene abajo, en cursiva, lo que
> hay que estar diciendo **mientras** la pantalla carga. Si se acaba la frase y la pantalla
> sigue cargando, hay un problema; los tiempos de §5 dicen que no debería pasar.

---

### Paso 1 — Marketing crea la publicación · 35 s

**Pestaña «Publicaciones» → «Nueva publicación».** Nombre, canal LinkedIn, el texto del post
y a quién va dirigido. Guardar.

**Enseñar:** el **enlace** que aparece solo, ya creado.

> *«Marketing no escribe este enlace: lo da el servidor, con 128 bits de azar. No se puede
> elegir, ni adivinar, ni reutilizar el de otra publicación. Es lo que después permite saber
> de qué post salió cada persona sin preguntárselo a nadie.»*

---

### Paso 2 — Un post, varias redes · 30 s

**En la misma publicación**, abrir la difusión. Copiar el texto de **LinkedIn**. Después
copiar el de **WhatsApp**.

**Enseñar, poniendo los dos textos uno al lado del otro:** que **los enlaces son
distintos**.

> *«El mismo post, dos redes, y cada una con su propio enlace etiquetado. Esto es lo que
> hace que dentro de un rato podamos decir por dónde llegó la persona. Y el texto viene ya
> recortado a lo que cabe en cada red: los 280 caracteres de X los cuenta el servidor, no el
> navegador, porque si se calculara en los dos sitios acabarían dando resultados distintos.»*

**Este es el paso que más se subestima.** Es la única pregunta de la prueba con personas que
el capítulo 27 considera decisiva: si alguien mira los dos enlaces y dice «son el mismo», el
informe por red no se puede explicar por muy exactos que sean sus números.

---

### Paso 3 — El interesado deja sus datos · 45 s

**Desde el teléfono** (o el navegador en modo teléfono), abrir el enlace **de WhatsApp**,
tal cual, sin quitarle nada. Rellenar y enviar.

**Enseñar:** que el formulario **no tiene ni un campo de texto libre**, y que lo obligatorio
cabe en una pantalla.

> *«Todo lo que se pregunta aquí lo sabe leer el modelo: el cargo, el sector y el tamaño son
> exactamente las listas con las que se entrenó, y vienen del servidor para que no puedan
> divergir. El teléfono y el perfil están plegados debajo, porque no son obligatorios. La
> facturación no se pregunta: LinkedIn no la da y el modelo aprendió a tratar su ausencia
> como ausencia, no como un cero.»*

**Cuidado con el enlace:** tiene que ser el de WhatsApp, no el de LinkedIn. El paso 7 enseña
la atribución por red y se queda sin gracia si todo llegó por el canal de siempre.

---

### Paso 4 — La ficha ya está puntuada · 25 s

**Pestaña «Prospectos».** La ficha nueva, arriba.

**Enseñar:** el score, la categoría y que **no tiene asesor**.

> *«Nadie ha tocado nada. La ficha se creó, se puntuó, quedó atribuida a su publicación y
> quedó repartida en el mismo segundo del envío. El reparto no mira el score: mira quién
> tiene menos cartera abierta, y con empate quién lleva más tiempo sin recibir a nadie. Hasta
> el capítulo 46 esta ficha se quedaba sin dueño esperando al líder, y sin dueño el sistema
> no tenía a quién ponerle la tarea del paso 6.»*

---

### Paso 5 — El líder ve a quién le tocó y se la pasa a su asesor · 25 s

**El contador «Nuevos de publicaciones, sin asesor», que dice cero.** Abrir la ficha desde la
matriz, leer a quién se le asignó y pasársela al asesor comercial.

> *«El contador dice cero y la persona sí ha llegado: desde el capítulo 46 cuenta lo que el
> reparto **no pudo** colocar —una publicación cuyo responsable se dio de baja, un día sin
> ninguna asesora activa—. Y lo que yo reasigno aquí se queda: el reparto corre una sola vez,
> en el alta, así que ningún recálculo me va a deshacer esto.»*

> *«El número y la lista los calcula el servidor con la misma condición. Durante dos
> capítulos no fue así: el contador sumaba seis canales y se seguía llamando “desde
> LinkedIn”, mientras la lista solo marcaba los de LinkedIn. El líder veía un número y
> encontraba menos fichas. Está en el reporte, porque la lección no es la etiqueta: es que
> al ampliar un concepto hay que releer las palabras que lo nombran.»*

---

### Paso 6 — El asesor no tiene que buscarla · 40 s

**Cambiar a la sesión del asesor. Pestaña «Hoy».**

**Enseñar, en este orden:** (1) la tarea está ahí sola, con **el motivo escrito**; (2) un
clic abre la ficha 360 y la tarjeta **«Llegó por»**; (3) «Ya está» cierra la tarea.

> *«Hasta el capítulo 28 el asesor tenía que buscar la ficha nueva en una lista ordenada por
> puntuación. Ahora el sistema le dice qué hacer hoy y por qué. Y en la ficha tiene las
> cuatro respuestas sin preguntarle a nadie: de qué publicación salió, por qué red llegó,
> qué pidió y cuándo aceptó el aviso de privacidad.»*

**Es el paso con más contenido de los nueve.** Si hay que recortar, se recorta el cierre de
la tarea, no la tarjeta «Llegó por».

---

### Paso 7 — El líder compara y atribuye · 30 s

**Volver a la sesión del líder. «Publicaciones» → comparativa**, y después el **informe** de
la publicación nueva.

**Enseñar:** la comparativa de las dos publicaciones, y dentro del informe la **fila de
WhatsApp**.

> *«Perfiles recibidos, cuántos avanzaron de etapa y puntuación media de cada publicación. Y
> dentro, por red: la persona que acabamos de ver llegó por WhatsApp, y el sistema lo sabe
> porque el enlace se lo dijo. Con una advertencia honesta: esto dice por dónde se repartió
> el enlace que se abrió, no dónde estaba la persona. Quien recibe por WhatsApp un enlace
> copiado del post de LinkedIn cuenta como WhatsApp. Para decidir dónde volver a publicar es
> exactamente lo correcto; para cualquier otra cosa, no.»*

---

### Paso 8 — Cerrar diciendo por qué · 25 s

**En la ficha, intentar poner «Ganado» en el selector de etapa.** El sistema se niega.
Después, el botón de cierre: motivo de la lista, fecha y tramo.

**Enseñar:** que el selector **no deja**, y que el formulario de cierre **no tiene un cuadro
de texto**.

> *«Cerrar un trato es lo único que produce una etiqueta de entrenamiento, así que no puede
> ser una opción más de un desplegable. Se pide el motivo de una lista cerrada, el día y, si
> se ganó, el tramo. Y la puntuación no se recalcula: la que tiene guardada es la que había
> cuando se decidió, que es lo único con lo que después se puede responder si el score
> acertaba.»*

---

### Paso 9 — El círculo se cierra · 15 s

**Pestaña «Desenlaces».**

**Enseñar:** la tabla por motivo, la columna de **categoría al cerrarse**, y el **contador
del reentrenamiento**.

> *«Ganados y perdidos por motivo, por publicación y por red. Y qué puntuación tenían al
> cerrarse, que es la respuesta a “¿el score acertaba?”. Abajo, cuánto falta para poder
> reentrenar: doscientos casos, cincuenta de cada clase. El sistema avisa cuando se
> alcanza. No reentrena: quien decide es una persona.»*

**Cerrar aquí.** Es el final natural: se empezó en un post y se ha terminado en un dato de
entrenamiento.

---

## 5. Lo que tarda el servidor, medido

Del ensayo del 24-09-2026, sobre la base de demostración, **con el modelo ya cargado**:

| Paso | Qué | Servidor |
| :---: | :--- | ---: |
| 0 | *Calentamiento: el artefacto entra en memoria (una vez por proceso)* | *3 584 ms* |
| 1 | Marketing crea la publicación y el servidor le da su enlace | 399 ms |
| 2 | Los textos de las dos redes, con su enlace cada uno | 40 ms |
| 3 | El interesado abre el enlace de WhatsApp y envía sus datos | 286 ms |
| 4 | La ficha queda creada, puntuada y atribuida | 2 ms |
| 5 | El contador «sin asesor», la reasignación y el contador otra vez | 248 ms |
| 6 | La bandeja «Hoy», la ficha 360 y el cierre de la tarea | 361 ms |
| 7 | La comparativa y el informe por red | 197 ms |
| 8 | El cierre con su motivo | 183 ms |
| 9 | El panel de desenlaces y el contador | 103 ms |
| | **Todo el recorrido** | **1 819 ms** |

**Ningún paso llega al medio segundo.** La demostración entera cuesta al servidor menos de
dos segundos; los 4:30 son de hablar.

Entre ejecuciones los números bailan un 30 % arriba o abajo según lo que esté haciendo la
máquina. Lo que no cambia es el orden de magnitud, que es lo único que decide si un paso se
nota o no. Si algún día uno se va a varios segundos, eso sí es una señal.

**Dos aclaraciones sobre estos números, porque un número sin su letra pequeña engaña:**

* **No incluyen el navegador.** Son el tiempo de la API medido dentro del proceso. Pintar la
  pantalla añade lo suyo, y eso depende de la máquina.
* **Los pasos 6 y 8 no incluyen la pasada del motor de reglas.** El ensayo la lanza a mano
  porque no puede esperar a la tarea programada; en producción corre de madrugada y nadie la
  ve. Sumarla diría que pulsar «Hoy» tarda medio segundo, y no es verdad. Medida sola, la
  pasada tarda **318 ms** de media sobre la base de demostración; el ensayo la imprime
  aparte.

---

## 6. Qué hacer si algo falla

| Si pasa esto | Casi seguro es | Qué hacer delante de la gente |
| :--- | :--- | :--- |
| El envío del interesado tarda varios segundos | El modelo no estaba cargado (§2, punto 4) | Decirlo: *«es la primera puntuación del proceso; carga el artefacto y verifica su huella»*. Es verdad y es una respuesta mejor que el silencio |
| El enlace no abre desde el teléfono | `PUBLICACIONES_URL_BASE` dice `localhost` | Seguir desde el navegador en modo teléfono. El guion no pierde nada |
| La comparativa tiene una sola fila | No se corrió el preparador (§2, punto 2) | Enseñar el **informe** de la publicación nueva en lugar de la comparativa. La atribución por red sigue viéndose |
| La tarea no aparece en «Hoy» | La pasada del motor no ha corrido desde la asignación | Es de granularidad diaria y está documentado. Enseñar la ficha y decirlo |
| Todo el mundo se queda sin sesión | El backend se reinició sin `SECRET_KEY` fija | Volver a entrar. Es el punto 3 de §2 |
| El panel de desenlaces da 403 | Se está en la sesión del asesor | **Correcto.** El panel son totales de toda la casa y solo lo ve la dirección. Merece decirse en voz alta |

---

## 7. Cómo repetir el ensayo

```bash
python scripts/ensayo_de_la_demo.py --base <ruta al .db de demostración>
```

Recorre los nueve pasos contra la API de verdad, comprueba el resultado de cada uno y los
cronometra. **Copia la base antes de tocarla**: la original se queda como estaba, porque la
demostración se enseña sobre ella y un ensayo que deje dentro un prospecto de prueba obliga
a volver a sembrarla justo antes de la defensa.

**No inicia sesión con ninguna contraseña**: firma el token de las dos cuentas que necesita,
como hacen las guardas del CI. Lo que se ensaya es el camino, no el formulario de entrada.

**La base que se le pase tiene que estar al día de las migraciones.** Una guardada hace unos
capítulos no falla a medias: el ensayo muere en el primer paso con `no such column:
users.totp_sal` o la columna que falte, y eso se lee como «el ensayo está roto» y no como «la
base es vieja». El 07-10-2026 la guardada era del 24 de septiembre, catorce capítulos por
detrás. Se pone al día con Alembic, sobre una **copia** y desde la raíz del repositorio —ahí
está `alembic.ini`, y lanzarlo desde `backend/` falla con «No 'script_location' key found»—:

```bash
DATABASE_URL="sqlite:///C:/ruta/a/la/copia.db" python -m alembic upgrade head
```

Si un paso falla, para ahí y dice cuál y por qué. Un guion que se ensaya y no se comprueba
es un guion que se cae delante del sínodo.

---

## 8. Lo que este ensayo no demuestra

* **Que alguien entienda lo que ve.** El ensayo comprueba que el camino funciona; si
  marketing distingue los dos enlaces o si el asesor lee su bandeja en vez de irse a
  «Prospectos» solo lo dice una persona sentada delante. La sesión con personas sigue
  pendiente y su guion está en `Prueba_Con_Personas.md`.
* **Los treinta segundos del formulario.** Están medidos en el navegador con ritmos de
  referencia, no con una persona y un cronómetro. La hoja de observación tiene su columna
  para el dato real.
* **Que la tarjeta se vea bien al pegar el enlace en una red.** El **06-10-2026**, con el
  túnel levantado, se comprobó desde internet lo que una red lee: las nueve etiquetas `og:`
  con la dirección del día y la imagen de 1200×630 servida con su tipo. Lo que sigue sin
  verse es **cómo la compone cada red**, que solo lo enseña cada red con una cuenta dentro.

**Y una que ya no está pendiente.** *Que el código QR se lea* lo estuvo hasta el
**06-10-2026**, y se cerró así: un decodificador de terceros —`jsQR 1.4.0`, nada del
proyecto— leyó el enlace exacto que el panel pinta, con **0 discrepancias entre los 2025
módulos pintados y la geometría del SVG** y 7,11 píxeles por módulo en pantalla; y después un
teléfono lo escaneó de la pantalla, abrió el formulario **por internet** y el envío entró como
prospecto ya repartido —`mas_tiempo_sin_recibir`, entre 6 candidatas, con su asiento— y con su
tarea de primer contacto tras la pasada del motor. Es la vez que más cerca se ha estado de la
prueba con personas sin que la haya.

Las que quedan están en `Congelacion_y_Trabajo_Futuro.md`, con lo que haría falta para
cerrarlas.
