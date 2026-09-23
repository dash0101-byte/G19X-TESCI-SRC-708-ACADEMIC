# Capítulo 27: Una Publicación, Varias Redes — Difusión, Textos por Red y Atribución

## 27.1. De dónde se parte

El capítulo 25 le dio a cada publicación un enlace público, y el 26 le dio estados,
responsable, opciones propias y un contador de visitas. Con eso, el líder escribe un post,
copia su texto, lo pega en LinkedIn y ve en el informe qué trajo.

El problema apareció en cuanto la demo salió de LinkedIn. El enlace es un enlace: se
reenvía por WhatsApp, se pega en un grupo de Facebook, se manda por correo. Y el sistema
guardaba **«LinkedIn»** en todas esas fichas, porque era el único canal que sabía escribir.
Era verdad el primer día y dejó de serlo el segundo. Un informe que dice «LinkedIn trajo
quince perfiles» cuando nueve llegaron por WhatsApp no es un informe con un error de
etiqueta: es un número que lleva a repetir el canal equivocado.

Este capítulo hace que **una publicación se difunda por varias redes** sin dejar de ser una
sola publicación con una sola página: cada red tiene su enlace, su texto y su botón de
compartir, y por dónde llegó cada persona queda registrado.

Dos cosas que **no** cambian, y conviene decirlo antes:

* **No se publica nada en nombre de nadie.** No hay API de ninguna red, ni cuentas, ni
  claves. Los botones abren la dirección pública de compartir de cada red, en el navegador
  de quien pulsa y con su sesión; publica esa persona, a mano.
* **El modelo no cambia.** Ninguno de los canales nuevos lo conoce, así que todos cuentan
  como desconocidos y neutros, exactamente como ya pasaba con «LinkedIn».

---

## 27.2. Las redes y cómo viaja la red de llegada

Seis redes, en `backend/app/core/redes.py`:

| Red | Activada por defecto | Se lleva el texto | Tope del texto |
|---|---|---|---|
| LinkedIn | sí | no (solo el enlace) | 3 000 |
| WhatsApp | sí | sí | 400 |
| Facebook | sí | no (solo el enlace) | 3 000 |
| Correo | sí | sí | 600 |
| Instagram | no | no tiene enlace de compartir | 3 000 |
| X | no | sí | 280 |

La red viaja en un parámetro de la dirección: `…/interes/<slug>?r=whatsapp`. No en el
`slug` —un identificador por red multiplicaría los enlaces que hay que mantener y rompería
la promesa del capítulo 25 de que un enlace publicado apunta siempre a lo mismo— ni en una
cookie, que es precisamente lo que esta página no pone.

### Ese parámetro lo puede editar cualquiera, y por eso no decide nada

Quien abre el enlace puede borrar el `?r=`, cambiarlo por `?r=tiktok` o por cualquier otra
cosa. Es una etiqueta de analítica, no una credencial. La regla es corta:

> Una red desconocida, inventada o manipulada se registra como **«sin red»** y **nunca**
> rechaza el envío.

Si rechazara, bastaría con tocar la dirección para dejar la página sin recibir a nadie:
habríamos convertido un adorno de analítica en una puerta que se cierra desde fuera. Y
quien copia el enlace a mano y se come un carácter perdería el formulario sin entender por
qué. El valor se recorta a veinte caracteres antes de mirarlo, para que una dirección con
basura larga no se pasee por el resto del sistema.

### Una red desactivada sigue contando lo que trae

El líder activa y desactiva redes para decidir **qué botones y qué textos quiere**, no para
invalidar enlaces. Si desactiva WhatsApp después de haberlo difundido, lo que ya está
compartido sigue llegando y sigue contándose como WhatsApp. Lo contrario reescribiría el
origen de gente que llegó de verdad por ahí, y las filas del informe dejarían de sumar el
total de la publicación.

---

## 27.3. El canal del prospecto y por qué sigue siendo neutro

La ficha se guarda con el canal de la red de llegada: «WhatsApp», «Facebook», «Correo»,
«Instagram», «X», «LinkedIn». Cuando no consta la red, el canal es **«Publicación»**, y no
«LinkedIn»: el enlace se pudo compartir desde cualquier sitio, y escribir una red que no
consta sería inventarla.

Esto no mueve ninguna puntuación, y no por casualidad. Las categorías que el modelo aprendió
para `source_channel` son «LinkedIn Ads», «Webinar», «Demo Request Form», «Organic Search»,
«Outbound Cold Email» y «Referral». Ninguno de los siete canales de la página está en esa
lista, así que el preprocesador —`OneHotEncoder(handle_unknown="ignore")`— los descarta en
silencio y el prospecto puntúa como si no se supiera por dónde vino: **neutro**. Es lo mismo
que ya ocurría con «LinkedIn» desde el capítulo 25.

La tentación evidente era escribir «LinkedIn Ads» para que sumara. Eso habría sido declarar
publicidad pagada donde hubo un post orgánico: un dato falso a cambio de unos puntos.
Reentrenar el modelo con estos canales es una decisión de negocio que queda fuera de esta
fase.

Hay dos pruebas que lo sostienen: una comprueba que ninguno de los canales está entre las
categorías del modelo, y otra manda el mismo perfil por cuatro redes distintas y exige que
salga **el mismo score**. La guarda del CI repite la primera, porque un canal renombrado
sin querer bastaría para que la red empezara a mover el score sin que nadie lo decidiera.

---

## 27.4. El texto de cada red

El texto de la publicación es uno. Lo que cambia es cuánto cabe:

* **X**: 280 caracteres **contando el enlace**. X acorta las direcciones a 23 caracteres con
  `t.co`, pero aquí se cuentan los caracteres de verdad: si se contaran 23 y X cambiara esa
  regla, el texto se pasaría de largo sin que nada avisara. Contando de más, el recorte es
  conservador y nunca se pasa.
* **WhatsApp (400) y correo (600)**: se leen en una notificación o en una vista previa de
  bandeja, no en un muro. Lo que no entra en las primeras líneas no lo lee nadie.
* **Instagram**: el texto entero, con un aviso de que el enlace va en la biografía o en una
  historia, porque Instagram no deja enlaces en el pie de una publicación.

Cuando no cabe todo, **lo que cede es la descripción, nunca el enlace**: un texto cortado
sigue diciendo algo y un enlace cortado no lleva a ninguna parte. El recorte respeta las
palabras y remata con «…»; cortar a mitad de palabra deja textos que parecen un error de
programa y no un resumen.

Los textos se calculan **en el servidor**. El navegador solo los pinta. La alternativa
—recortarlos en el cliente— habría puesto la misma regla en dos lenguajes, esperando a que
uno de los dos cambiara.

El botón de siempre, «Copiar texto para LinkedIn», ahora copia el texto de la red LinkedIn,
cuyo enlace lleva `?r=linkedin`. Sin eso, la vía principal se habría contado entera como
«sin red» y la tabla por red diría que LinkedIn no trajo a nadie.

---

## 27.5. Compartir sin API ni cuentas

Cada red activa tiene su botón, y cada botón es una **dirección pública de compartir**:

| Red | Dirección |
|---|---|
| LinkedIn | `https://www.linkedin.com/sharing/share-offsite/?url=…` |
| Facebook | `https://www.facebook.com/sharer/sharer.php?u=…` |
| X | `https://x.com/intent/post?text=…` |
| WhatsApp | `https://wa.me/?text=…` |
| Correo | `mailto:?subject=…&body=…` |

Ninguna necesita clave, aplicación registrada ni sesión iniciada por el sistema. Abren la
red en una pestaña nueva —con `noopener`, para que la página que se abre no pueda tocar la
que la abrió— y publica quien pulsa, con su propia cuenta.

LinkedIn y Facebook solo se llevan el enlace, no el texto. Por eso al lado va **«Copiar
texto»**, que está en todas las filas: también se quiere pegar el texto a mano en una
historia o en un mensaje. Instagram no ofrece ninguna dirección pública de compartir desde
la web, así que su fila lleva «Copiar texto», el aviso y el código QR.

En el enlace de X el enlace de la página va **dentro** del texto y no como parámetro `url`
aparte: mandarlo las dos veces lo pondría dos veces y el recorte a 280 dejaría de cuadrar.

---

## 27.6. El código QR, generado aquí

Para Instagram y para material impreso hace falta un código QR del enlace. Se genera **en
el navegador**, sin pedirle la imagen a nadie.

Los generadores de QR que se usan de una línea son servicios: se les manda la dirección y
devuelven la imagen. Eso significa mandar a un tercero cada enlace de cada publicación, que
es justo lo que esta parte del sistema evita. Y una dependencia nueva de npm entra en la
cadena de suministro del cliente, que el proyecto mantiene corta a propósito. Así que el
codificador está escrito: modo binario UTF-8, corrección de errores nivel M y versiones 1 a
10, que llegan a 213 bytes —de sobra para un enlace—. Un texto más largo da un error visible
en lugar de un código a medias.

El panel deja elegir el enlace del código: «material impreso (sin red)» o cualquiera de las
redes activas. Se descarga como SVG, que se imprime a cualquier tamaño sin perder nitidez.

**Cómo está comprobado, y hasta dónde.** No hay ningún lector de códigos disponible en este
entorno: `BarcodeDetector` no existe en el navegador de Windows que se usó, y traer una
biblioteca solo para la prueba habría metido en la cadena de suministro justo lo que se
evitó. Lo que sí se comprueba son las propiedades que la norma exige y que se verifican por
sí solas:

* la palabra de Reed-Solomon (datos + corrección) **vale cero** al evaluarla en α⁰…α⁹, que
  es la definición del código: con la aritmética de Galois o el polinomio generador mal, no
  daría cero;
* las 32 combinaciones de la información de formato difieren **al menos en 7 bits** entre sí,
  y las de versión en 8, que son las distancias mínimas conocidas de esos códigos BCH;
* la estructura de la matriz: tamaño según la versión, los tres localizadores con su
  separador, los patrones de sincronismo alternados, el módulo oscuro fijo y la zona
  tranquila.

**Queda pendiente escanear un código impreso con un teléfono.** Es lo único que prueba que
una cámara real lo lee, y no se ha hecho. Está en los límites del capítulo.

---

## 27.7. Visitas y envíos por red

La tabla de visitas pasa de (publicación, día) a **(publicación, día, red)**. Sigue sin
guardar nada de quien visita: ni IP, ni navegador, ni cookie, ni hora. La red no es un dato
de la persona, es por dónde se repartió el enlace.

El informe gana una **fila por red** con visitas, envíos, tasa de envío, perfiles y score
medio, más una fila «Sin red» para lo que llegó con el enlace sin etiquetar. Esa tabla es la
comparativa entre redes de la publicación: cuál trajo visitas y cuál trajo perfiles, que no
siempre son la misma.

Tres decisiones que se ven en los números:

* **Sin visitas no hay tasa, no un 0 %.** Un 0 % diría que nadie escribió de los que
  miraron; lo que pasa es que no miró nadie.
* **Las visitas son de la publicación; los perfiles y el score medio son de quien pregunta.**
  Un contador agregado no sabe de carteras, pero un total y una media de la cartera ajena
  describen el trabajo de otro sin abrir una sola ficha, que es lo que cerró el alcance de
  cartera. Un asesor ve sus perfiles por red; el resumen dice que está viendo los suyos.
* **El gráfico por día suma todas las redes.** Sin sumar, enseñaría solo la última red de
  cada día, y el error no se habría notado: las barras seguirían dibujándose.

El contador de «prospectos sin asesor» del líder buscaba `source == "LinkedIn"`. Con seis
canales posibles habría dejado de ver a casi todos los que están esperando, justo cuando
empezaron a llegar por más sitios. Ahora busca por todos los canales de la página.

---

## 27.8. La migración

`campaigns` gana `redes` (JSON), vacío en todas las que ya existen: ninguna publicación
cambia de comportamiento al migrar, porque vacío significa «las de siempre».

`visitas_de_publicacion` gana `red` **dentro de la clave primaria**. Las visitas ya contadas
no saben por dónde llegaron —se contaron antes de que hubiera redes—, así que se quedan en
`sin_red`, que es exactamente lo que significan. Inventarles «linkedin» habría dado una
tabla por red con una primera fila falsa.

Cambiar una clave primaria no se escribe igual en SQLite que en PostgreSQL, y
`batch_alter_table` resuelve el caso de SQLite y deja el de PostgreSQL a medias. Se hace con
**tabla nueva, copia, borrado y renombrado**, que es la misma secuencia en los dos motores y
la que se prueba en los dos.

La reversión vuelve a (publicación, día) **sumando** las filas de las distintas redes del
mismo día: el total diario se conserva y lo único que se pierde es el reparto. Sin el `SUM`
la copia chocaría con la clave primaria en cuanto una publicación tuviera visitas de dos
redes el mismo día. Los prospectos, sus canales y sus solicitudes no se tocan: una ficha que
llegó por WhatsApp sigue diciendo «WhatsApp» después de revertir.

Los permisos no cambian: editan el líder comercial y el administrador; el asesor consulta,
copia textos y comparte.

---

## 27.9. Las claves viejas de JWT

Aparte del trabajo de redes, este capítulo cierra un asunto pendiente del capítulo 11.

La clave de firma que se filtró entonces se rotó el mismo día y quedó en una lista de
bloqueo para que nadie pudiera volver a usarla. La lista guardaba **el texto literal de la
clave**, en `config.py` y en dos documentos. Funcionaba —la prohibía—, pero dejaba la clave
escrita en el repositorio, y en cuanto el proyecto se subió a GitHub, también en su
historial para siempre. Prohibir una clave no sirve de mucho si la clave sigue escrita al
lado de la prohibición.

Ahora la lista guarda **la huella SHA-256** de cada clave prohibida. Comparar huellas
reconoce la clave sin escribirla en ninguna parte, porque la operación va en un solo
sentido. Los marcadores de relleno (`changeme`, `secret`, `CAMBIAR_ESTA_CLAVE`) se quedan en
claro: no son secretos de nadie, son más útiles legibles, y los tres son más cortos que el
mínimo de 32 caracteres, que ya los rechazaría por su cuenta.

Y una prueba recorre todo el código y toda la documentación, calcula la huella de cada
palabra que pudiera ser una clave y falla si alguna encaja con la lista
(`test_claves_comprometidas.py`). Si alguien vuelve a pegar la clave vieja en un fichero
—aunque sea en un comentario o en un reporte—, la prueba lo dice.

---

## 27.10. Que nada de esto sea decorativo

### Pruebas

* `test_una_publicacion_varias_redes.py` (66): las redes de una publicación y su catálogo;
  la red de llegada en la actividad, en el canal de la ficha y en la ficha 360; la red
  desconocida que nunca rechaza; las visitas por red; los textos y sus topes; los botones
  oficiales; la neutralidad ante el modelo; las filas del informe con su alcance; y los
  permisos.
* `test_migracion_una_publicacion_varias_redes.py`: Alembic de verdad, en un proceso aparte
  y sobre una SQLite temporal. Ida, vuelta y otra vez ida, comprobando que no se pierde ni
  una visita y que al final el esquema es el que declaran los modelos.
* `test_claves_comprometidas.py` (9): la lista son huellas, el mecanismo sigue prohibiendo y
  ninguna clave prohibida ha vuelto al árbol del proyecto.
* `qr.test.js` (17) y `CompartirEnRedes.test.jsx` (16) en el cliente.
* `test_vista_previa_en_redes.py` (32): las etiquetas en el HTML servido, el escape con
  cinco títulos hostiles, lo que no filtran las publicaciones que no están activas, la
  imagen y que nada de esto cuenta una visita.

### La guarda del CI

`scripts/guarda_de_la_pagina_publica.py` gana su **séptima** comprobación. Falla si una red
desconocida o manipulada rechaza el envío en lugar de contarse como «sin red»; si la red de
llegada deja de marcar el canal de la ficha o las visitas dejan de repartirse por red; si
alguno de esos canales pasa a ser una categoría que el modelo conoce; si el texto de una red
se pasa de su tope o se come el enlace; o si un botón de compartir lleva credenciales en la
dirección.

La guarda comprueba **propiedades**, no casos: una red nueva mal configurada no rompe
ninguna prueba existente —nadie la usa— y aquí falla en cuanto existe.

### Reintroducciones

Se volvieron a meter **38 defectos**, uno a uno, para comprobar que algo falla de verdad y
no solo sobre el papel: los 38 los cazó la guarda o una prueba. Cada fichero se respalda
antes y se restaura después, con el hash verificado.

El ejercicio encontró cuatro cosas que había que arreglar, y esa es la razón de hacerlo:

* **Una prueba que no podía fallar.** La del recorte por palabras usaba un texto de palabras
  cortas y asertaba algo que se cumplía igual con el recorte roto. Ahora usa palabras largas
  y comprueba que lo que sigue en el original es un espacio.
* **Otra que se comprobaba a sí misma.** La de la zona tranquila del código QR calculaba el
  tamaño esperado **desde la propia constante**: ponerla a cero habría seguido pasando, y un
  código pegado al borde no lo lee ninguna cámara. Ahora el 4 está escrito en la prueba.
* **Un módulo sin ninguna prueba.** La lectura de `?r=` vivía suelta en el fichero de
  arranque, que no monta ningún test: si devolvía siempre vacío, todo el mundo llegaba «sin
  red» y nada lo decía. Se movió a `services/api.js` y se probó.
* **La guarda reventaba en lugar de explicar.** Con una red que lanzaba excepción, el paso
  del CI moría con un rastro de pila en vez de decir qué defensa se había perdido. Ahora lo
  nombra.

### PostgreSQL encontró un fallo que SQLite no podía ver

La migración pasaba en SQLite y fallaba en PostgreSQL:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable)
relation "pk_visitas_de_publicacion" already exists
```

En PostgreSQL el nombre de una restricción es único **en todo el esquema**, no dentro de su
tabla: crear la tabla provisional con el nombre definitivo choca con la restricción que
todavía tiene la original. En SQLite el nombre vive dentro del `CREATE TABLE` y no choca con
nada. La tabla provisional se crea ahora con las restricciones **con sufijo**, y el sufijo se
quita al final con un `RENAME CONSTRAINT` que solo hace falta en PostgreSQL.

Es exactamente el fallo que el paso de migraciones del CI —que corre sobre PostgreSQL 16 y
hace `upgrade`, `check`, `downgrade base`, `upgrade` y `check`— habría detenido. Se
reprodujo en local contra la misma imagen, en un contenedor de usar y tirar atado a
`127.0.0.1`.

---

## 27.11. Evidencia

| Comprobación | Resultado |
|---|---|
| Backend | **1190 pruebas**, 93 % de cobertura |
| Cliente | **302 pruebas** en 21 ficheros, 94,6 % |
| `ruff` y `eslint` | Sin avisos |
| Guarda del CI | Comprobaciones séptima y octava añadidas; pasa |
| Reintroducción de defectos | **48 de 48** detectados; todos los ficheros restaurados con el hash verificado |
| Migración en SQLite | Ida, vuelta y otra vez ida; ninguna visita perdida |
| Migración en PostgreSQL 16 (imagen del CI) | `upgrade`, `check` sin diferencias, reversión sumando visitas, `upgrade` otra vez |
| Navegador, 375 px, datos de la demo | Se abre `?r=whatsapp`, se envía el formulario y la ficha queda con canal **WhatsApp**; la ficha 360 dice «vía WhatsApp»; el informe reparte 3 visitas y 1 envío a WhatsApp y 13 y 3 a «Sin red» |
| Permisos | Asesor 403 al cambiar redes; líder 200; red inventada 422 |
| Imagen de producción | `docker build` del backend con el lock nuevo (`--require-hashes`); dentro, Pillow 12.3.0, la fuente Inter y una tarjeta de 1200×630 dibujada con acentos |
| Tarjeta social | HTML pedido con un `GET` y analizado como lo hace un rastreador: etiquetas de la publicación; un borrador da el mismo documento genérico |

---

## 27.12. La vista previa del enlace en las redes

Con los botones de compartir ya funcionando apareció el problema siguiente: el enlace se
pegaba y salía **como una tarjeta vacía**. Un rectángulo gris, el nombre del sistema y
ninguna descripción. El enlace funcionaba, pero nadie lo pulsaba, porque no decía nada.

La causa es sencilla y no se ve desde el navegador. Cuando alguien pega una dirección,
LinkedIn, WhatsApp, Facebook o X la piden **como un programa**: descargan el HTML, leen sus
etiquetas y se van. **No ejecutan JavaScript.** Y `/interes/{slug}` la servía el cliente:
lo que el rastreador leía era el `index.html` genérico del panel, el mismo para todas las
publicaciones. Poner las etiquetas al montar la aplicación no habría arreglado nada, porque
el rastreador ya se fue.

### Quién sirve ahora esa página

El servidor. `GET /interes/{slug}` devuelve el documento **con las etiquetas dentro**, y
después carga la aplicación igual que antes. En un despliegue, nginx manda `/interes/` al
backend (`frontend/nginx.conf`); en desarrollo el servidor de Vite sigue sirviendo la ruta,
y las etiquetas se comprueban pidiéndoselas directamente al backend, que es exactamente lo
que ve un rastreador.

Eso obligó a un detalle de construcción: el HTML tiene que **nombrar** el archivo con el que
arranca la aplicación, y el servidor no puede conocer la huella que el compilador le pone.
Así que la entrada y su hoja de estilos salen con nombre fijo —`assets/app.js` y
`assets/app.css`—, y esos dos, y solo esos dos, se revalidan en lugar de cachearse un año.
El resto de los archivos conserva su huella y su caché. Una prueba compara el nombre que
escribe el servidor con el que declara `vite.config.js`: son dos archivos distintos del
proyecto, y si uno cambia y el otro no, la página pública se queda sin aplicación y eso solo
se ve al desplegar.

### Qué se dice, y de quién

Solo de una publicación **activa** se dicen su título y su texto. Un borrador, una pausada,
una cerrada y un enlace inventado dan las **mismas** etiquetas genéricas, la misma imagen de
marca y el mismo **200**.

Lo del 200 es deliberado. Si el HTML respondiera 404 para unos y 200 para otros, el código
de respuesta diría desde fuera qué enlaces existen —y el capítulo 26 cerró exactamente ese
hueco al hacer que «no disponible» fuera idéntico en los cuatro casos—. Una prueba compara
los dos documentos carácter a carácter, salvo el propio enlace, y exige que sean el mismo.

Estas dos rutas tampoco **cuentan visitas**. La visita la cuenta la petición que hace la
aplicación al montarse, que es cuando alguien abrió la página de verdad; contarla aquí
sumaría una por cada vez que el enlace se pega en un chat y el recuento dejaría de medir lo
que dice medir.

### El escape

Todo lo que viene de la base pasa por `html.escape(..., quote=True)`. El título lo escribe
una persona y admite cualquier carácter desde el capítulo 25: unas comillas cierran el
atributo `content="…"` y lo que venga detrás deja de ser texto para pasar a ser marcado.

Las pruebas no buscan cadenas, **analizan el HTML** con un analizador —que es lo que hace el
rastreador— y comprueban, para cinco títulos hostiles, que el valor llega entero al atributo,
que el documento sigue teniendo una sola etiqueta `og:title` y que no ha aparecido ninguna
etiqueta que no pusiéramos nosotros. Uno de esos títulos lo intenta a propósito:

```
Post "/><meta property="og:title" content="secuestrado
```

Sin escape, el documento tendría dos `og:title` y la red leería el segundo.

### La imagen

1 200 × 630, dibujada en el servidor al pedirla, sin mandarle el título a ningún servicio de
tarjetas. Lleva la marca, el título repartido en tres líneas como mucho y el nombre del
sistema abajo.

Se dibuja con **Pillow**, que es la dependencia nueva de este capítulo. Entra fijada por su
huella en `requirements.lock`, y la regeneración del lock no movió ninguna otra versión:
cincuenta y tres paquetes antes, cincuenta y cuatro ahora. Se usa **solo para escribir**: no
se abre aquí ninguna imagen que venga de fuera, que es donde está históricamente la
superficie de esa biblioteca.

La tipografía es la **Inter que ya usa el cliente**, el mismo archivo `.woff2` que viaja en
el bundle del navegador, copiado a `backend/app/recursos/` con su licencia OFL al lado. No
es una fuente nueva en el proyecto. La que trae Pillow por defecto se descartó al probarla:
no tiene acentos, y «días» salía «d☐as». Hay una prueba que lo fija, y que además comprueba
que la comprobación sirve de algo, enseñando que con la fuente por defecto **sí** sale el
recuadro.

No se guarda en ninguna parte: cuesta unas decenas de milisegundos y así nunca enseña un
título que ya se cambió. Lleva `ETag`, así que quien la pida otra vez no la vuelve a
descargar, y cinco minutos de caché, para que corregir un título no obligue a volver a
compartir el enlace.

### Cómo está comprobado

* **Como lo lee un rastreador**: un `GET` al HTML servido y un analizador, sin montar la
  aplicación. Una prueba borra además todo lo que hay dentro de `<script>` y exige que las
  etiquetas sigan ahí.
* **En el navegador**, contra la base de la demo: se pidió `/interes/{slug}` con `fetch` y
  se analizó el HTML recibido —`og:title`, `og:description`, `og:url`, `og:image` y
  `twitter:card` con los valores de la publicación—; la página siguió montando su formulario
  de catorce campos desde ese mismo HTML; y la imagen se abrió directamente, con el propio
  navegador rotulando la pestaña «tarjeta.png (1200×630)».
* **La guarda del CI** gana su **octava** comprobación, con las propiedades: que las
  etiquetas están en el HTML servido, que un título con marcado no rompe nada, que lo que no
  está activo no filtra su título y que la imagen es un PNG de 1 200 × 630.

Lo que **no** se ha hecho: pegar el enlace en LinkedIn, en WhatsApp o en X y mirar la tarjeta
de verdad. Para eso hace falta que la dirección sea pública, y la de la demo es `localhost`.
Las etiquetas son las que esas redes documentan y el HTML se comprueba como ellas lo leen,
pero el último paso queda pendiente y está en los límites del capítulo.

---

## 27.13. Lo que este capítulo no hizo

* **No publica en ninguna red automáticamente.** No hay API, ni cuentas, ni claves. Los
  botones abren la dirección pública de compartir y publica quien pulsa. Estaba fuera del
  alcance y sigue fuera.
* **No hay TikTok.** Estaba fuera del alcance.
* **No se reentrenó el modelo.** Los seis canales nuevos son desconocidos para él y por
  tanto neutros. Darles peso exige reentrenar con datos reales de cada canal, que todavía no
  existen.
* **La tarjeta no se ha visto en una red de verdad.** El HTML se comprueba como lo lee
  un rastreador, y las etiquetas son las que LinkedIn, WhatsApp, Facebook y X
  documentan, pero pegar el enlace y mirar la tarjeta exige una dirección pública, y la
  de la demo es `localhost`.
* **El código QR no se ha escaneado con un teléfono.** Se comprueban las propiedades
  matemáticas y estructurales que exige la norma, que es lo verificable sin un lector, pero
  nadie ha impreso uno y lo ha leído con una cámara. Es lo primero que habría que hacer
  antes de repartir material impreso.
* **La red es una etiqueta, no una medición.** Dice por dónde se repartió el enlace que se
  abrió, no dónde estaba la persona. Quien recibe por WhatsApp un enlace que alguien copió
  del post de LinkedIn cuenta como WhatsApp, que es lo correcto para decidir dónde volver a
  publicar, pero no es «vino de WhatsApp» en ningún sentido más profundo.
* **Las visitas siguen siendo aperturas, no personas.** Como en el capítulo 26.
* **La sesión con personas reales sigue sin celebrarse.** Arrastrado desde el capítulo 24.
