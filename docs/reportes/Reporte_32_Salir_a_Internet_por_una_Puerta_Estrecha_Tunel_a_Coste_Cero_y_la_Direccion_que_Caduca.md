# Capítulo 34: Salir a Internet por una Puerta Estrecha — Túnel a Coste Cero y la Dirección que Caduca

> **Sobre la numeración.** Este es el **Reporte 32** y el **capítulo 34**. El desfase de dos
> viene de los capítulos 29 y 31, que no escribieron reporte propio; está explicado al
> principio del Reporte 30. Los apartados se numeran **34.x**, por el capítulo.

> **Sobre la congelación.** El proyecto sigue congelado. Este capítulo **no añade
> funcionalidad**: desbloquea §3.4 del documento de congelación, que decía literalmente
> «pegar el enlace y **mirar** la tarjeta exige una dirección pública, y la de la
> demostración es `localhost`», y cuyo «qué haría falta» era «un dominio con certificado,
> **aunque sea de pruebas**». Un túnel gratuito es exactamente eso. La página de interés, su
> formulario, su tarjeta de vista previa y sus límites ya estaban escritos desde el capítulo
> 25; lo único que no existía era una dirección desde la que alcanzarlos.
>
> Lo que sí entra nuevo es la **puerta**, y entra porque sin ella lo anterior no se puede
> hacer sin publicar el sistema entero.

## 34.1. De dónde se parte, y cuál es el riesgo real

La página de interés lleva nueve capítulos funcionando contra `localhost`. Tiene formulario
sin texto libre, campo trampa, límites por IP y por publicación, aviso de privacidad,
atribución por red y una tarjeta de vista previa con sus etiquetas Open Graph. Todo
comprobado. Nada de eso lo ha visto nunca alguien de fuera de esta red, porque no hay por
dónde.

La forma obvia de arreglarlo —abrir un puerto en el router— es la que no se va a hacer, y no
por pereza: abrir el 3000 publica **el panel entero**, con su pantalla de acceso, su API de
gestión, su documentación interactiva y sus métricas. La página de interés sería una ruta más
dentro de un sistema completo puesto en internet, protegido solo por que nadie adivine una
contraseña.

Así que el problema de este capítulo no es «salir a internet». Es **salir por un sitio del
que se pueda demostrar qué cabe**.

## 34.2. La puerta estrecha

La decisión central cabe en una frase: **el túnel no mira al servidor del panel, mira a otro
servidor**.

`frontend/nginx.conf` declara ahora dos bloques. El del puerto 80 es el de siempre: la SPA,
la API completa, la red local. El del **8080** es nuevo, y su contenido entero es esto:

```
GET  /interes/<slug>                 el HTML con las etiquetas de la tarjeta
GET  /interes/<slug>/tarjeta.png     la imagen 1200x630 de la vista previa
GET  /api/v1/interes/<slug>          la publicación y las listas del formulario
POST /api/v1/interes/<slug>          el envío del interesado
GET  /assets/…                       el bundle que la página necesita para dibujarse

location / { return 404; }           todo lo demás
```

### Por qué lista blanca y no lista negra

Es la única parte de este capítulo que hay que defender con cuidado, porque las dos formas
parecen equivalentes y no lo son.

Una lista negra —publicar todo y prohibir `/api/v1/leads`, `/docs`, `/metrics`…— **funciona
el día que se escribe**. Y falla el día que alguien añade un endpoint, porque lo que no está
en la lista queda publicado por omisión. El fallo no rompe nada: el panel sigue funcionando
igual de bien, ninguna prueba se pone roja, y lo único que cambia es que la cartera de
prospectos pasó a ser alcanzable desde internet. Nadie se entera hasta que alguien la
encuentra.

Con la lista blanca, un endpoint nuevo **nace fuera**. Para publicarlo hay que escribir su
`location`, que es un acto deliberado y visible en la revisión. El coste es simétrico y es
el correcto: si mañana la página necesita un endpoint más, hay que nombrarlo. Ese roce es la
defensa.

Por eso la guarda del CI (§34.6) no comprueba «`/api/v1/leads` no está publicada» —eso
seguiría pasando con `/api/v1/nomina` dentro—, sino que **ninguna `location` nombra algo que
no sea de la página** y que la negativa por defecto sigue ahí.

### El 404, y no el 403

Todo lo no publicado responde 404. Un 403 diría «esto existe y no te lo doy», que es
información gratuita sobre la forma del sistema. Desde fuera, el panel y la API de gestión
**no existen**.

### De quién es cada petición

Este es el detalle que se habría escapado fácilmente. Detrás del túnel, `$remote_addr` es
siempre el proceso `cloudflared` que corre en esta misma máquina: los mil visitantes de un
post compartirían un solo contador y el tope por IP —la única defensa contra un envío en
bucle— dejaría de existir **sin que nada fallara**.

La IP real llega en `CF-Connecting-IP`. Creer una cabecera es justo lo que
`app/core/proxy.py` lleva desde el capítulo 11 advirtiendo que no se haga, así que la
licencia hay que ganársela: **el puerto de la puerta se publica solo en `127.0.0.1`**. Nadie
de la red local puede conectarse a él para falsear la cabecera; el único que llega es el
túnel del propio anfitrión. Las dos decisiones —el `map` en nginx y el `127.0.0.1:` en
compose— son una sola cosa escrita en dos archivos, y la guarda comprueba las dos.

Se midió, porque «debería funcionar» no basta: con dos `CF-Connecting-IP` distintos, cada
visitante recibió su propia cuenta de cinco envíos, mientras la IP pública real ya tenía la
suya agotada (§34.5).

## 34.3. Una sola opción de configuración, ya desde antes

El encargo pedía que la dirección pública fuera «una sola opción de configuración, nunca
código». Resultó que **ya lo era**: `PUBLICACIONES_URL_BASE` existe desde el capítulo 26 y
todo lo que se reparte —el enlace del panel, el texto que se copia para cada red, `og:url`,
`og:image`— sale de `enlace_publico()`, que lo lee.

Lo que había que hacer no era construirlo, era **impedir que se rompa**, porque a partir de
ahora ese valor se cambia a mano cada vez que arranca el túnel:

* `base_publica()` es el único sitio que lee el ajuste, y tiene nombre propio para que nadie
  tenga que escribir `settings.PUBLICACIONES_URL_BASE` fuera de ahí.
* Una prueba recorre `backend/app/` buscando direcciones escritas a mano; la guarda del CI
  hace lo mismo.
* Otra prueba mueve el ajuste y comprueba que **las cuatro cosas** que se reparten se mueven
  con él.

Se verificó en vivo: con el ajuste apuntando al túnel, `og:url` y `og:image` salieron con la
dirección del túnel sin tocar una línea de código.

## 34.4. La dirección que caduca, que es el precio de que sea gratis

Un túnel de prueba gratuito da una dirección **distinta en cada arranque**. Esa es la
propiedad que lo hace gratis y la que lo hace peligroso para lo que este sistema produce: un
enlace de publicación no se queda en el panel, se pega en un post de LinkedIn.

Cuando la dirección cambia, el post sigue publicado, la publicación sigue activa, el informe
sigue contando sus visitas —cero— y quien pulsa no llega a ninguna parte. **Nada falla.**
Simplemente deja de funcionar, que es la avería más cara de descubrir.

Son dos preguntas distintas y se responden con dos mecanismos, a propósito:

**¿La dirección configurada responde?** Una sonda sale a internet y **vuelve a entrar por el
túnel**, porque es el camino que hace un visitante; desde dentro el backend siempre se
responde a sí mismo y no comprobaría nada. Pide un slug inventado, aprovechando que la ruta
pública devuelve 200 con etiquetas genéricas para cualquier slug desconocido (capítulo 27):
así se comprueba el camino entero sin necesidad de que haya ninguna publicación activa.

Tres detalles que decidió la realidad y no el diseño:

* **Un 429 cuenta como que funciona.** Lo que se comprueba es que la dirección lleva hasta
  aquí, no que deje pasar. Tratarlo como caída habría encendido el aviso justo durante una
  oleada, que es cuando la pantalla tiene que decir la verdad.
* **Un 530 cuenta como caída.** Al parar `cloudflared` se midió qué pasa: el borde de
  Cloudflare **sigue contestando** por ese nombre y devuelve 530. No es un error de conexión,
  así que una sonda que solo mirara si hubo respuesta daría por viva una dirección muerta.
* **`responde` tiene tres valores.** `True`, `False` y **`None`** = «no se ha preguntado»,
  que es lo que contesta un despliegue sin túnel delante. Colapsarlo en `False` pondría una
  alarma permanente en la pantalla de publicaciones, y una alarma siempre encendida deja de
  leerse en dos días, justo el día que sí pasa algo.

**¿Los enlaces ya repartidos siguen apuntando a la dirección de ahora?** Esa no necesita
salir a ningún sitio. `campaigns.url_base_publicada` guarda bajo qué dirección se **activó**
la publicación —el instante en que su enlace se vuelve repartible— y se compara con la de
ahora.

Se escribe **una sola vez**. Reactivar una publicación pausada bajo otra dirección no lo
reescribe, y esa es la decisión que hace útil el dato: lo que hay que poder contestar es «¿el
enlace que la gente ya tiene lleva aquí?», y quien lo tiene lo copió la primera vez.
Sobrescribir borraría justo la prueba de que caducó.

Las publicaciones anteriores a este capítulo quedan a `NULL` y **no se marcan**. Rellenarlas
con la dirección de hoy sería una línea de SQL y afirmaría que sus enlaces están vigentes,
que es lo contrario de lo que la columna existe para detectar. Es el criterio del capítulo 32
con el país supuesto: se prefiere una advertencia que falta a una advertencia inventada,
porque la segunda enseña a ignorar la primera.

En el panel, el aviso general dice cuántas caducaron y el de cada publicación va **debajo del
enlace, sin taparlo**: el enlace de arriba es el de ahora y hay que copiarlo; lo que caducó
está dentro del post.

## 34.5. Lo que se comprobó de verdad, desde fuera de la red

No hay forma honrada de escribir este capítulo sin levantar el túnel, así que se levantó, se
comprobó y se apagó. La dirección de la prueba fue
`https://energy-compare-clearing-excerpt.trycloudflare.com` y ya no existe.

**La puerta, ruta por ruta, desde internet** (`scripts/comprobar_puerta_publica.py`):

| | Resultado |
| :--- | :--- |
| Rutas que la página necesita | **5 de 5** responden |
| Rutas de gestión, documentación y métricas | **25 de 25** responden 404 |

Las veinticinco incluyen `/`, `/index.html`, la cartera, una ficha concreta, el login, las
cuentas, la bitácora, los indicadores, el alta de publicaciones, la comparativa, el recálculo
masivo, el webhook del CRM, las integraciones, `/docs`, `/redoc`, `/openapi.json`,
`/metrics`, `/health` y un intento de salirse del directorio de recursos.

**La página, de punta a punta:**

* `og:title`, `og:description`, `og:url` y `og:image` con la dirección del túnel dentro, y
  `twitter:card: summary_large_image`. Cabeceras `Strict-Transport-Security` y
  `X-Frame-Options: DENY`.
* La tarjeta: **23 268 bytes** de PNG, dibujada al pedirla.
* Un envío real desde internet: **202**, y en la base **un** prospecto, puntuado (30, COLD),
  con `source: LinkedIn` y la actividad atribuida a `red: linkedin` por el `?r=linkedin`.
  Sin país —el capítulo 32 aguanta— y sin apellidos, que es lo que ese formulario no pregunta.
* Un envío con el **campo trampa** relleno: **202**, el mismo texto, y en la base **nada**.
  Desde fuera los dos son indistinguibles, que es el punto.
* El límite endurecido: envíos 1 a 5 aceptados, **el sexto 429**.
* Dos visitantes con `CF-Connecting-IP` distinta: **cinco envíos cada uno** con la IP real ya
  agotada. El contador por visitante es real.
* Con el túnel vivo, la sonda dijo `responde: True / HTTP 200`. Al pararlo,
  `responde: False / HTTP 530`, con su renglón en el registro.
* Cambiando el ajuste a otra dirección: `enlace_caducado: True` y el contador a 1.

**Un tropiezo que merece quedar escrito.** La primera comprobación desde fuera falló entera:
treinta rutas con «no se pudo conectar» sobre un túnel que funcionaba —`curl` daba 200—.
La causa es la salida TLS interceptada de esta máquina: el certificado lo firma una autoridad
que solo está en el almacén del sistema, y el paquete `certifi` que trae `httpx` la rechaza.
El guion pasa ahora a usar el almacén del sistema. Se cuenta porque el modo de fallo era el
peor posible: **una herramienta rota que se parece mucho a un sistema comprobado**, y la
primera lectura del resultado fue «el túnel no llega».

Y por eso mismo el guion trata el fallo de conexión como un **tercer estado**. Antes lo
contaba como «no dio 404» y escribía «ESTÁ PUBLICADA» sobre rutas que ni se habían llegado a
mirar. Ahora dice «no se pudo comprobar», que es lo único cierto: dar por cerrada una puerta
que no se miró sería peor que cualquiera de los dos errores anteriores.

## 34.6. Que nada de esto sea decorativo

**Las pruebas.** `backend/tests/test_puerta_estrecha.py`, **41 casos**: la puerta leída como
la lee nginx (catorce rutas de gestión que no casan, siete que sí), la negativa por defecto,
el puerto en loopback, la dirección con un solo dueño, el ciclo completo de
`url_base_publicada` y los siete casos de la sonda. Y seis más en el panel.

**La guarda del CI.** Un paso nuevo; `configuracion-peligrosa` pasa de 38 a **39 controles**.
Vigila la forma de la lista blanca, no una lista de prohibiciones: la negativa por defecto,
que ninguna `location` nombre algo que no sea de la página, que el único prefijo sea
`/assets/`, el `127.0.0.1:` del puerto, el dueño único de la dirección y que los límites
públicos sigan declarados.

**La reintroducción de defectos.** Diez defectos, de uno en uno: **10 de 10 detectados**. La
primera pasada dejó escapar uno —que la sonda dejara de tratar un 5xx como caída— y era
justamente el caso medido con el túnel apagado: se añadió la prueba del 530 y la segunda
pasada salió completa.

## 34.7. Qué haría falta para el dominio, y qué costaría

El camino está dejado listo a propósito: lo de hoy es la versión de prueba del **mismo
mecanismo**, no un apaño que haya que tirar.

| Qué | Coste |
| :--- | :--- |
| Un dominio (`.com`, `.mx`) | **10–15 USD al año** |
| Cuenta de Cloudflare, plan gratuito | **0** |
| Certificado TLS | **0**, lo emite y renueva Cloudflare |
| Túnel con nombre | **0**, mismo binario |
| Trabajo | Una tarde |

Qué cambia, y ninguna de las tres es código:

1. El túnel pasa a ser **con nombre**: se crea una vez, se le asigna el dominio y la
   dirección deja de cambiar. Arranca solo, como servicio de Windows.
2. `PUBLICACIONES_URL_BASE` se escribe **una vez**. Los pasos 2, 3 y 4 de la guía
   desaparecen.
3. Los enlaces de los posts dejan de caducar, y con eso §34.4 entero deja de hacer falta —el
   mecanismo se queda puesto, pero no vuelve a avisar de nada—.

Lo que **no** cambia: la puerta estrecha sigue siendo necesaria, y sigue siendo lista blanca.
Un dominio propio no publica menos cosas que un túnel de prueba.

## 34.8. Lo que esta fase no hizo, y por qué

**El panel sigue sin salir de la oficina, y así se queda.** Estaba fuera del encargo y es la
decisión correcta: publicar el panel exige segundo factor (§3.6), y sin él la única defensa
de la cartera entera sería una contraseña.

**No se publicó ningún post de verdad.** La dirección caduca al reiniciar, así que un post
con ella tiene fecha de caducidad desconocida. La difusión en redes espera al dominio, y eso
está dicho en la guía en el primer recuadro, antes que nada.

**La tarjeta sigue sin verse en LinkedIn.** Se comprobó que el HTML llega con las etiquetas
correctas desde una dirección pública con HTTPS, que es todo lo que puede comprobar una
máquina. Pegar el enlace y **mirar** la tarjeta lo tiene que hacer una persona con una cuenta
—§3.4 se queda abierto en esa última mitad, y ahora por fin es posible—: la guía lo pone como
tarea del primer día.

**El túnel no arranca con la pila.** Es deliberado. Mientras haya que abrir una ventana y
dejarla abierta, no hay forma de que la máquina quede expuesta sin que alguien lo haya hecho
a propósito, y cerrarla apaga la exposición al instante. Automatizarlo es lo primero que hay
que hacer **cuando haya dominio**, no antes.

**El bundle de la SPA es descargable desde fuera.** La página pública lo necesita para
dibujarse y es un solo archivo. Es código de cliente sin secretos, y no puede llamar a nada
porque las rutas de gestión no existen en esa puerta; evitarlo exigiría compilar un segundo
bundle solo para esta página. Queda dicho en §6.4.
