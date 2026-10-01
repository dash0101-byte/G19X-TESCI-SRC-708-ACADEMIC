# Congelación de funcionalidades y trabajo futuro

**Fecha de congelación:** 24 de septiembre de 2026
**Alcance:** todo el repositorio `Sistema_Inteligente_Lead_Scoring`
**Sustituye a:** las secciones «Lo que esta fase no hizo» dispersas en los reportes 19 a 29
**Última revisión:** 1 de octubre de 2026 (apéndice del capítulo 38)

> **Revisión del capítulo 38.** La congelación se mantiene, y este capítulo la abrió **para
> tres puntos de §6.2 y para ninguno más**: el 16, el 14 y el 11.
>
> Los tres eran el mismo fallo con tres caras —**una capacidad que existe, está probada y no
> se puede usar desde donde hay que usarla**— y los tres pasan el criterio del §1: la frase
> ya estaba escrita y el código no la cumplía. El README promete desde el capítulo 20
> «exportación y supresión del titular comprobadas tabla por tabla», y lo que no decía era
> **quién** podía usarlas: hasta este capítulo, un derecho de acceso y supresión que solo se
> ejerce construyendo una petición HTTP con un token de líder comercial no era un derecho de
> la persona, era un derecho de quien sabe usar `curl`.
>
> No se añadió ni un endpoint, ni una tabla, ni una migración, ni un campo de esquema: **el
> servidor del capítulo 38 es el del 37 más un archivo de pruebas**. Lo que entró fue el
> alrededor que faltaba, y es donde están todas las decisiones (R36).
>
> §6.2 pasa de **siete entradas abiertas de ocho a cinco de nueve**: se cierran la 11, la 14
> y la 16, y entra la **35**, que el propio capítulo encontró al enlazar el contador del
> tablero con la matriz. De las cinco que quedan, cuatro —9, 10, 12 y 15— piden que el
> servidor haga algo que hoy no hace, y eso es funcionalidad: es la misma distinción que
> dejó entrar a estos tres.
>
> **Lo que el capítulo encontró por ejecutar y no por leer, esta vez dentro de su propio
> trabajo**, y son dos:
>
> * Un **recuento que habría mentido**. El bloque de confirmación del borrado decía «se
>   borran la ficha y los N registros», sumando la tabla de secciones. Entre esas secciones
>   están los asientos de la bitácora, que **no se borran**: se les retiran los datos
>   personales y se quedan. El número se quitó, porque un total que no es el que ocurre acaba
>   en la constancia de la persona (R36 §38.5).
> * Una **fila que no era una sección**. `fuera_de_la_base` también es una lista del documento
>   de exportación, y lleva dentro tres párrafos de texto: salió en la pantalla como «fuera de
>   la base — 3», que no dice que haya tres registros de nadie. Arreglado por la forma del
>   contenido y no por una excepción con nombre.
>
> **Y lo que apareció con un teléfono en la mano, que es lo más grave de todo el capítulo.**
> §6.3 punto 17 decía «el código QR no se ha escaneado con un teléfono… es lo primero que
> habría que hacer antes de repartir material impreso». Se escaneó. **No lo detectaba
> ningún lector, y llevaba así desde el capítulo 27.** La información de formato —los quince
> bits que dicen con qué máscara está hecho el código, y sin los cuales no se puede leer un
> solo dato— iba escrita con la fila y la columna cambiadas de sitio. El dibujo, los datos,
> la corrección Reed-Solomon y el zigzag estaban bien.
>
> Lo que lo hace una lección y no un descuido: **las diecinueve pruebas del QR son todas
> simétricas respecto de la diagonal** —localizadores en esquinas simétricas, dos patrones
> de sincronismo que son uno el reflejo del otro, dos bandas de formato reservadas a la
> vez—, así que transponer no rompía ninguna. Y la única que podría haberlo visto —el módulo
> siempre oscuro, que el bucle pisaba— **pasaba por casualidad**. Una familia entera de
> pruebas puede estar ciega a un error concreto sin que nada lo señale; lo que faltaba era
> **leer el código**, y ahora la suite lo lee. §6.3 pasa de cuatro comprobaciones a mano a
> tres: el punto 17 queda cerrado (R36 §38.10a).
>
> Con el mismo teléfono salieron otras dos, menores y de la misma familia —lo que el sistema
> **no dice**—: el botón desactivado de la vista previa no explicaba por qué a quien llegaba
> hasta él, y el panel de compartir no avisaba de que la dirección pública estaba caída justo
> donde alguien copia e imprime ese enlace. Las dos corregidas (R36 §38.10b y §38.10c).
>
> Y una tercera, sobre el método: **la primera pasada del arnés de reintroducción dijo 13 de
> 13 y era mentira**. Lanzaba el control con una ruta relativa desde otro directorio, Python
> salía con código 1 por no encontrar el archivo, y el arnés leía ese 1 como «el control
> disparó». Un arnés que verifica guardas es código sin verificar; lo destapó mirar **qué
> mensaje** daba cada disparo en vez de contar los que disparaban (R36 §38.9).

> **Revisión del capítulo 37.** La congelación se mantiene, y esta revisión corrige el
> **documento** además del código, que es la primera vez que pasa.
>
> El capítulo 37 cerró **§3.7** y **§3.8**, y los cerró demostrando que su premisa era falsa:
> ninguno de los dos necesitaba una cuenta externa. El servicio de comprobación de
> contraseñas filtradas por rango —*k-anonymity*, el modelo que la propia entrada nombraba—
> es una petición anónima sin registro ni clave, y Dependabot es parte de GitHub, donde el
> repositorio vive desde el capítulo 11. §3 pasa de **nueve entradas abiertas a siete**: de
> las diez que tiene, tres están ya cerradas —§3.6 en el capítulo 35, y estas dos—.
>
> Las siete que quedan sí necesitan lo que dicen necesitar, y conviene decirlo para que esta
> revisión no se lea como una sospecha general sobre §3: LinkedIn, Calendly, WhatsApp y la
> publicación automática piden credenciales de una plataforma; la tarjeta de vista previa
> pide un dominio público; las copias fuera de la máquina piden almacenamiento; y el
> `event_id` lo tiene que mandar un CRM que todavía no existe. El error no estaba en el
> criterio de §3, estaba en dos entradas que nadie volvió a comprobar.
>
> **La diferencia entre los dos errores importa.** §3.8 fue correcto el día que se escribió:
> en el capítulo 22 no estaba decidido dónde viviría el repositorio, y dejó de ser cierto sin
> que nadie volviera a mirarlo. §3.7 **nunca** lo fue: el capítulo 23 escribió «haría falta
> una cuenta» por analogía con el resto de §3 y no fue a comprobarlo, y así estuvo catorce
> capítulos.
>
> Es la cuarta vez que algo aparece por **ejecutar y no por leer** —el volumen `deriva` del
> capítulo 32, el suelo de cobertura del 36, el `target` ausente del Compose— y la primera en
> que lo que falla no es el código sino **el inventario de lo que falta**. Una lista de
> trabajo futuro es también código que envejece, y nadie le corre pruebas. De aquí sale una
> costumbre nueva: **una entrada de §3 no se da por buena sin haber comprobado que la cuenta
> hace falta de verdad**, porque «depende de alguien» es la clasificación que nadie revisa.
>
> §6.3 pasa de dos comprobaciones a mano a **cuatro** y §6.4 de quince restos a **dieciséis**.
> Las dos nuevas de §6.3 son del mismo tipo y conviene leerlas: lo que el capítulo 37 añadió
> solo se puede ver funcionando **fuera** de la suite, a propósito, porque meter un tercero
> dentro de la suite la pondría roja los días que ese tercero tenga un mal día.

> **Revisión del capítulo 36.** La congelación se mantiene. El capítulo 36 fue calidad del
> cliente, no funcionalidad: ninguna pantalla nueva, ningún campo nuevo, ninguna frase nueva
> en el README. Lo que hizo fue **comprobar** lo que el sistema ya afirmaba —que se puede
> usar con teclado, que el texto se lee, que los errores llegan a quien no ve la pantalla— y
> corregir los seis sitios donde no era cierto (R36).
>
> Encontró además dos cosas que no estaban en ninguna lista, y las dos son de la clase que
> este documento no puede prever:
>
> * **El suelo de cobertura del cliente estaba roto en `main`.** El capítulo 35 añadió al
>   módulo de sesión las cinco funciones del segundo factor sin una sola prueba; la suite
>   pasaba y la cobertura no, y la cobertura es lo que el CI ejecuta. Corregido en el 36
>   (R36 §36.9), que es donde entra por §1: «una guarda del CI en rojo».
> * **La bandeja «Hoy» hacía una consulta por tarea.** No se veía con seis prospectos: con
>   seis filas, una consulta por fila y una para todas tardan lo mismo. Se vio al medir con
>   300 prospectos y 5 000 actividades (R36 §36.7).
>
> §6.4 pasa de cinco restos menores a nueve: los cuatro nuevos son deuda **visual** que el
> capítulo encontró y no pagó porque pagarla es diseñar, y eso estaba fuera de su alcance.
>
> **Añadido el 29-09-2026, y es la tercera de esa clase.** Al levantar la pila para mirar el
> trabajo del capítulo 36, el panel seguía enseñando el defecto que ese capítulo había
> corregido: servía un bundle de cinco días antes. El servicio del cliente no declaraba
> `target` en Compose, así que Docker construía la **última** etapa del Dockerfile —la del
> pipeline, que no compila y copia el `dist/` del contexto— mientras la cabecera de ese
> mismo Dockerfile afirmaba que la que se construía era la que compila. Ninguna prueba podía
> verlo: todas miden el código fuente, y lo que fallaba era el empaquetado. Corregido, con
> el control **43** del CI (R36 §36.13).
>
> Las tres —el volumen `deriva` del capítulo 32, el suelo de cobertura roto y esta— tienen
> la misma forma: **no estaban en ninguna lista, y ninguna apareció leyendo código**.
> Aparecieron al ejecutar el sistema de verdad. Es lo que este documento no puede prever y
> la razón de que «verificar levantando la pila» sea una costumbre escrita.

> **Revisión del capítulo 32.** La congelación se mantiene tal cual: solo entran
> correcciones de fallos, con el criterio de §1. Lo que cambia es el inventario. §6.1 —«lo
> que puede morder»— tenía ocho puntos y ahora tiene **dos**, y los dos esperan a un
> sistema externo, no a más trabajo de este equipo. Se cerraron además el 13 y el 22. El
> capítulo 32 fue deuda, no funcionalidad: cada punto reparaba algo que el sistema ya
> prometía por escrito —una política de conservación sin filas sin plazo, una ficha que no
> supone, una guarda que exige versión— y ninguno añadió una frase nueva al README.
>
> Ese capítulo encontró además, al levantar la pila para comprobar el trabajo, **un defecto
> que no estaba en ninguna lista**: el volumen `deriva` del capítulo 22 nunca fue escribible
> por el proceso que lo usa, así que el monitor de deriva no habría podido recordar que ya
> avisó. Corregido, con un control nuevo en el CI. Se anota aquí porque es la clase de cosa
> que este documento no puede prever: las listas recogen lo que se sabe que falta, no lo que
> se cree terminado y no lo está.

---

## 0. Por qué existe este documento

Desde el capítulo 19, cada reporte termina con una lista de lo que esa fase **no** hizo.
Son once listas, cada una en su contexto, y cada una es correcta el día que se escribió.

El problema es doble. Primero, **una docena larga de esas entradas ya no son ciertas**: se
cerraron en un capítulo posterior, y el reporte lo dice en cursiva debajo de la entrada
original —que es lo honrado, porque tachar la línea borraría que estuvo abierta—. Segundo,
quien hoy quiera saber «qué falta» tiene que abrir once archivos y llevar la cuenta a mano
de cuáles se tacharon.

Este documento hace dos cosas, y ninguna más:

1. **Declara la congelación.** A partir de la fecha de arriba, el criterio de qué entra al
   repositorio cambia. §1.
2. **Reúne en un solo sitio lo que queda abierto**, agrupado por **de qué depende**, que es
   lo único que decide si algo se puede hacer o no. §3 a §6.

No decide prioridades ni promete fechas. Ninguna de las dos cosas corresponde a quien
escribe el código: la primera es de PluriOne y la segunda depende de cuándo lleguen cuentas
y datos que hoy no existen.

---

## 1. Qué significa «congelado»

**A partir de aquí solo se corrigen fallos.** Un cambio entra si y solo si repara algo que
está roto respecto de lo ya documentado.

| Entra | No entra |
| :--- | :--- |
| Un comportamiento que contradice lo que dice su reporte, el README o una prueba | Una funcionalidad nueva, por pequeña que parezca |
| Un fallo de seguridad | Un campo más en un formulario existente |
| Una prueba que falla, o una guarda del CI en rojo | Una pantalla, un endpoint o una tabla nuevos |
| Una dependencia con aviso de seguridad publicado | Una biblioteca nueva |
| Documentación que describe algo que el código no hace | Reescribir algo que funciona porque se le ocurrió una forma mejor |

**El criterio para distinguirlos** es el que el proyecto ya venía usando y no cambia aquí:
si para explicarlo hay que añadir una frase nueva al README, es funcionalidad; si la frase
del README ya está escrita y el código no la cumple, es un fallo.

**Tres casos frontera**, decididos de antemano para no tener que discutirlos con el reloj en
contra:

* **Reentrenar el modelo con desenlaces reales no es una funcionalidad nueva**: el camino
  está construido, comprobado en cada ejecución del CI (`ensayo_del_bucle.py`) y lo único
  que falta son las filas. Ejecutarlo el día que existan es operación, no desarrollo. Lo que
  sí sería funcionalidad nueva es cambiar el pipeline para que acepte menos datos.
* **Rellenar una lista cerrada** —un motivo de pérdida más, un sector más— es cambiar una
  constante del vocabulario y sus etiquetas. Cuenta como corrección si el panel demuestra
  que «Otro motivo» está creciendo (§4.7); como funcionalidad si sale de una intuición.
* **Los plazos de conservación** son configurables por variable de entorno a propósito
  (capítulos 20 y 22). Cambiarlos es configuración, no código, y no toca la congelación.

---

## 2. Cómo está clasificado lo que sigue

Cada entrada dice **de qué depende**, porque es lo que separa «no se hizo» de «no se puede
hacer todavía»:

| Grupo | Significa | Qué haría falta |
| :---: | :--- | :--- |
| **§3. Cuentas externas** | El código no se puede escribir de forma honrada sin una cuenta, una clave o un dominio público que el proyecto no tiene | Que PluriOne abra la cuenta |
| **§4. Datos reales** | El código se podría escribir, pero cualquier número que produjera sería inventado | Que el bucle acumule desenlaces |
| **§5. Decisiones que no son técnicas** | Está construido lo necesario; falta que alguien decida qué debe pasar | Una decisión de negocio, de producto o de quien responde del tratamiento de datos |
| **§6. Deuda de ingeniería** | No depende de nadie. Se puede hacer hoy | Tiempo |

**§7** recoge aparte lo que **no se va a hacer**, con el motivo. Una lista de trabajo futuro
que no dice qué descartó obliga a volver a plantear cada año las mismas discusiones ya
zanjadas.

Cada entrada lleva su origen entre paréntesis: `R25 §25.10` remite al **capítulo** 25,
apartado 25.10.

**Ojo con la numeración, que se ha desfasado dos veces.** Hasta el capítulo 28, el número
del reporte y el del capítulo coincidían. El capítulo 29 no escribió reporte propio, así que
a partir de ahí el reporte va **uno** por detrás; el capítulo 31 tampoco, y desde el capítulo
32 va **dos**. Hoy: el capítulo 36 está en el `Reporte_34`, y sus apartados se numeran `36.x`.

Por eso las referencias de este documento van por **capítulo** y no por reporte: es lo único
que no vuelve a moverse. `R36 §36.8` es el capítulo 36, apartado 36.8, que vive en el
archivo `Reporte_34_...`.

---

## 3. Depende de cuentas externas

Nada de esto se puede terminar dentro del proyecto. Lo que sí está hecho en todos los casos
es el lado de acá: el conector, el esquema, la firma o el botón.

### 3.1. LinkedIn no se lee

**(R25 §25.10, R21 §21.12 — H-5)**

Ni **Lead Sync** (recoger los formularios de captación de LinkedIn) ni **Sign In with
LinkedIn**. Las dos exigen una aplicación aprobada en LinkedIn Developer con su producto
concedido. El conector `linkedin-lead-gen` existe y acepta una forma **simplificada** de la
carga, no la de `leadFormResponses`: hoy sirve para probar el camino, no para recibir a
LinkedIn de verdad.

**Consecuencia hoy:** los perfiles entran por la página de interés del proyecto, que es lo
que la demostración enseña. Es un camino completo y real; simplemente no es el de LinkedIn.

**Qué haría falta:** la cuenta, y después contrastar el esquema completo y la firma de
LinkedIn contra lo que el conector acepta —o poner delante un traductor.

### 3.2. Calendly y WhatsApp Business, lo mismo

**(R21 §21.12)**

Los tres conectores se firman con el **esquema HMAC propio** del proyecto, no con el de cada
proveedor. Aceptan una forma reducida de sus cargas.

### 3.3. No se publica en ninguna red automáticamente

**(R26 §26.11, R27 §27.13)**

Los botones de difusión abren la **dirección pública de compartir** de cada red y publica
quien pulsa. El texto se copia y se pega; la dirección del post se escribe a mano después.
Publicar desde el panel exige una API y una cuenta por red.

**Estaba fuera del alcance desde el principio y sigue fuera.**

### 3.4. La tarjeta de vista previa no se ha visto en una red de verdad

**(R27 §27.13 · desbloqueado a medias en el capítulo 34)**

El HTML se comprueba como lo lee un rastreador, y las etiquetas Open Graph y Twitter Card
son las que LinkedIn, WhatsApp, Facebook y X documentan. Pero pegar el enlace y **mirar** la
tarjeta exige una dirección pública, y la de la demostración era `localhost`.

**Ya no lo es.** El capítulo 34 dejó la página alcanzable desde internet por un túnel
gratuito, con HTTPS y sin abrir puertos (R32). Se comprobó desde fuera de la red que el HTML
llega con `og:title`, `og:description`, `og:url`, `og:image` y `twitter:card` correctos, y
que la imagen de 1 200 × 630 se sirve.

**Lo que sigue abierto es la última mitad, y es la que no puede hacer una máquina:** pegar el
enlace en LinkedIn y **mirar** la tarjeta que compone. Eso exige una cuenta y una persona.
La guía lo pone como tarea del primer día (`docs/Guia_del_Tunel_Publico.md` §4).

**Qué haría falta para cerrarlo del todo:** alguien con cuenta de LinkedIn, diez minutos, y
el túnel encendido.

### 3.5. Nada sale del panel

**(R28 §28.13)**

Ni correo, ni WhatsApp, ni notificación de navegador. Las tareas y los avisos del motor de
reglas viven dentro del panel y se ven al entrar.

**Esto no es solo una cuenta que falta.** Un aviso que sale del sistema necesita una
dirección verificada, una política de qué hacer cuando rebota y, sobre todo, saca de la
aplicación el nombre de una persona que aceptó un aviso de privacidad para otra cosa. La
cuenta es el requisito más barato de los tres.

### 3.6. ~~No hay segundo factor~~ — **cerrado en el capítulo 35**

**(R23 §23.7, R19 §19.9 · cerrado en R33)**

Decía esto, y era un diagnóstico exacto: «Un TOTP para `System_Admin` exige alta con código
de verificación, códigos de recuperación, un paso más en el login del cliente y una
respuesta para quien pierde el teléfono siendo el único administrador —que es justo la
cuenta que no puede quedarse fuera. Añadir la verificación sin eso produce una cuenta de
administración que se bloquea sola.»

**Las cuatro cosas están hechas** (R33 §35.3), y la cuarta mandó sobre las otras tres: hay
tres salidas para quien se queda fuera, y la última cuenta de administración con segundo
factor **no se lo puede quitar**, porque hacerlo dejaría el sistema sin administración
utilizable.

Resultó que **no dependía de ninguna cuenta externa**, que es lo que lo tenía clasificado
aquí. Los códigos de recuperación se entregan en pantalla al darse de alta —no hacía falta
un canal para mandarlos— y el rescate del último caso se resuelve con acceso al servidor,
que es la respuesta correcta y no una carencia: cualquier canal usable desde fuera sería una
segunda puerta a la cuenta más poderosa del sistema.

Tampoco hizo falta una biblioteca de criptografía. El secreto **no se guarda**: se deriva de
`SECRET_KEY` y de una sal por alta, así que la base no contiene nada que cifrar. El precio
está escrito: rotar esa clave invalida todas las altas
(`docs/Guia_del_Segundo_Factor.md` §5).

### 3.7. ~~La lista de contraseñas filtradas no se actualiza sola ni es exhaustiva~~ — **cerrado en el capítulo 37**

**(R23 §23.7 · cerrado en R37 §37.2)**

~~Es una foto de dos listas públicas, con manifiesto de cuáles salió. Cubre las filtradas
más frecuentes de 12 caracteres o más. Comprobar contra cientos de millones de huellas sin
un servicio externo pediría un archivo de decenas de gigabytes dentro de la imagen.~~

~~**Qué haría falta:** una cuenta en un servicio de comprobación de contraseñas
comprometidas —con el modelo de *k-anonymity*, que no envía la contraseña— o aceptar el
tamaño.~~

**Lo que hacía falta no era una cuenta, y por eso esta entrada estaba mal clasificada desde
el día que se escribió.** El servicio de rango que implementa *k-anonymity* —el modelo que
esta misma entrada nombraba— es una petición `GET` anónima: sin registro, sin clave de API,
sin identificarse. El capítulo 23 escribió «haría falta una cuenta» por analogía con el
resto de §3, donde sí hace falta, y nadie volvió a comprobarlo en catorce capítulos.

Desde el capítulo 37, al alta de usuario y al cambio de contraseña se les pregunta por
rango: **salen los cinco primeros caracteres del resumen SHA-1 y nada más**, nunca la
contraseña ni el resumen completo. Si el servicio no contesta, no se bloquea a nadie y el
resultado es idéntico al de antes del capítulo 37 —hay una prueba que compara las dos
listas de motivos carácter a carácter—, porque la lista local sigue decidiendo primero.

**Lo que sigue abierto, y es la mitad que no se cerró:** la lista **local** sigue sin
actualizarse sola. Se regenera a mano con `scripts/generar_lista_de_contrasenas.py`, y
sigue importando porque es exactamente lo que queda cuando no hay internet. No depende de
ninguna cuenta: depende de que alguien la corra, así que su sitio ya no es §3 sino §6. Está
anotada como resto **34** en §6.4.

### 3.8. ~~Nadie avisa de que una huella de imagen se quedó atrás~~ — **cerrado en el capítulo 37**

**(R22 §22.9 · cerrado en R37 §37.7)**

~~Todas las imágenes de terceros van fijadas por huella y se renuevan con
`scripts/renovar_imagenes.py`. Que alguien **tenga que correr el guion** es deliberado.
Automatizarlo con un servicio que abra solicitudes de cambio exige una cuenta.~~

**Tampoco exigía una cuenta.** Dependabot es parte de GitHub y el repositorio está en
GitHub desde el capítulo 11; lo único que faltaba era `.github/dependabot.yml`. Esta
entrada sí fue correcta el día que se escribió —en el capítulo 22 no estaba decidido dónde
viviría el repositorio— y dejó de serlo sin que nadie volviera a mirarla.

Desde el capítulo 37 hay seis ecosistemas vigilados: las acciones del CI, las dependencias
de Python y de npm, las dos imágenes base de los Dockerfile y las imágenes de la pila.

**Lo que NO cambia, y está escrito en la cabecera del propio archivo:** Dependabot
**avisa**; `scripts/renovar_imagenes.py` sigue siendo la fuente de verdad. El guion es quien
conoce las reglas de este proyecto —una etiqueta no puede llevar dos huellas, nada de
`apt-get upgrade`, paquetes con versión, acciones por huella de commit— y una solicitud
automática puede dejar el repositorio en un estado que su guarda `--solo-fijacion` rechaza.
Y al revés: que no haya solicitudes abiertas no significa que todo esté al día, significa
que Dependabot no ha visto nada.

El archivo documenta además qué se acepta con el CI verde y qué exige repetir la
comprobación de la imagen entera —construir, Trivy, syft y los paquetes con versión fijada
de los dos Dockerfile—, y el control **45** del CI comprueba que esa cobertura y ese
criterio sigan ahí.

### 3.9. Las copias de seguridad no salen de la máquina

**(R19 §19.9)**

Hay copias, con prueba de restauración comprobada (capítulo 16). Sacarlas de la máquina
exige almacenamiento externo.

---

### 3.10. Sin `event_id`, el CRM se deduplica por contenido

**(R21 §21.12 · reclasificado desde §6.1 en el capítulo 32)**

Estuvo en «deuda de ingeniería» hasta el capítulo 32, y estaba mal colocado: aquí no hay
nada que escribir. La clave de deduplicación es `(source, external_event_id)`, y cuando el
sistema de origen **no manda** identificador la única huella disponible es el contenido.

Lo que eso cuesta: dos eventos reales idénticos byte a byte —incluido el instante— entran
como uno. Lo que costaría la alternativa: aceptar los dos y dejar que el operador decida,
es decir, cambiar un caso raro y sin daño por uno frecuente y con daño, porque cada
reentrega del CRM duplicaría la actividad. La corrección de verdad es que el CRM mande
`event_id`, y eso lo decide quien opera ese CRM.

Lo mismo, en menor grado, vale para la entrega de WhatsApp con varios mensajes (§6.1,
punto 6): el arreglo es escribible, pero **no comprobable** hasta que haya una cuenta al
otro lado, porque depende de si el proveedor reentrega la tanda entera o solo lo que
faltaba, y de esa respuesta depende si la transacción única es la corrección o el problema.

---

## 4. Depende de datos reales

Este grupo es el corazón del trabajo futuro, y todo él cuelga del mismo hecho:

> **Hoy la base no tiene ni un solo prospecto en estado terminal.** El bucle de
> realimentación está construido, comprobado y vacío.

El capítulo 30 construyó lo que faltaba para llenarlo: cerrar un trato exige decir cómo
acabó, por qué motivo —de una lista cerrada— y qué día. El contador del panel de desenlaces
dice cuánto falta: **200 ejemplos utilizables, 50 de cada clase**.

### 4.1. El modelo no se reentrena, y por eso no conoce los canales nuevos

**(R25 §25.10, R26 §26.11, R27 §27.13, R28 §28.13, R29 §30.14)**

El artefacto en producción conoce **«LinkedIn Ads»**, que es publicidad pagada. Un post
orgánico no lo es. Los seis canales de difusión del capítulo 27 tampoco los conoce.

**Qué hace hoy con ellos:** los trata como **canal desconocido**, es decir, **neutro**. No
los penaliza ni los premia. Esa es la respuesta honrada: no hay ninguna evidencia sobre la
que asignarles un peso.

**Tampoco llegan al modelo** ni las opciones de «¿Qué necesitas?», ni la tasa de envío de la
página, ni las tareas, ni los avisos, ni el motivo del desenlace. En los tres últimos casos
**es una garantía comprobada por el CI**, no un olvido: el motivo se conoce al cerrar, y el
día que hay que decidir a quién llamar todavía no existe.

### 4.2. No hay deriva del rendimiento ni curva de aprendizaje de los mínimos

**(R24 §24.9)**

Las dos necesitan desenlaces reales. El monitor vigila deriva de **variables** (PSI), que sí
se puede medir sin etiquetas; el rendimiento del modelo, no.

### 4.3. El monitor dirá «muestra insuficiente» durante un tiempo

**(R24 §24.9)**

Solo compara instantáneas del **vector 2**, y hasta que se acumulen cien no dictamina. Es la
respuesta verdadera: comparar con las antiguas daría un PSI con aspecto de deriva que sería
en realidad un cambio de definición.

### 4.4. Las instantáneas anteriores al capítulo 24 no sirven para entrenar

**(R24 §24.9)**

Es el precio de no inventar: no dicen qué mensajes eran de LinkedIn ni cuántas llamadas
quedaron sin respuesta. El dataset real y el monitor las **descartan y las cuentan** en
lugar de traducirlas, y el manifiesto dice cuántas son.

### 4.5. Los cierres anteriores al capítulo 30 no tienen motivo

**(R29 §30.14)**

La migración no los rellenó. El panel no los cuenta y el manifiesto del dataset los cuenta
aparte, con la etiqueta deducida del estado. Es la merma que cuesta no inventar.

### 4.6. El criterio del límite inferior es juicio, no medida

**(R19 §19.9)**

Publicar un modelo exige que el **límite inferior** del IC 95 % del ROC-AUC alcance 0.82 y
el del aporte sobre el heurístico alcance +0.01. Con esos umbrales, 260 desenlaces reales no
publicarían. Puede resultar demasiado exigente, y no hay curva de aprendizaje que diga
cuánto hasta que haya datos.

### 4.7. Nadie ha rellenado el formulario de cierre varias veces seguidas

**(R29 §30.14)**

Si **nueve motivos de pérdida** son demasiados o se quedan cortos —y sobre todo cuánto crece
«Otro motivo»— solo se sabe usándolo. El panel cuenta «otro» aparte precisamente para poder
tener esa conversación con datos en vez de con opiniones.

### 4.8. Nadie ha vivido una semana con la bandeja «Hoy»

**(R28 §28.13)**

Si las seis reglas producen la cantidad adecuada de trabajo —ni tan poco que sobre, ni tanto
que se ignore— es justo lo que solo se puede saber usándola varios días seguidos. **Los
plazos se dejaron configurables por eso.**

### 4.9. Las suposiciones del generador sintético son suposiciones

**(R24 §24.9)**

Qué prospectos dejan los ingresos en blanco, y cuánto pesa un intento de llamada sin
respuesta, están **elegidos para que el pipeline tenga algo que aprender**, no medidos. El
ROC-AUC de 0.9469 mide la integridad del pipeline, no el negocio.

### 4.10. La sesión con personas sigue sin celebrarse

**(R25 §25.10, R26 §26.11, R27 §27.13, R28 §28.13, R29 §30.14)**

Es la entrada más arrastrada del proyecto y merece decirse con precisión, porque es fácil
confundir «tiene pruebas» con «se ha probado con alguien».

**Lo que sí está:** la pila, el guion por papel (`docs/Prueba_Con_Personas.md`), las cuatro
hojas de observación, el preparador de la base y el ensayo automático del guion —que desde
este capítulo recorre los nueve pasos contra la API de verdad y los cronometra
(`scripts/ensayo_de_la_demo.py`, y su reloj en `docs/Guion_Cronometrado_de_la_Demo.md`)—.

**Lo que no puede decir ninguna prueba automática:**

| Rol | Lo que hay que observar | De qué capítulo viene |
| :--- | :--- | :---: |
| Marketing | Si al pedirle el texto de WhatsApp contesta que los dos enlaces **son el mismo**. Si lo dice, el informe por red es inexplicable por muy exactos que sean sus números | 27 |
| Interesado | Si el formulario se rellena de verdad en **treinta segundos** desde un teléfono, y en qué campo se para si no | 25 |
| Líder | Si lo primero que mira para contar los prospectos sin asesor es el **tablero** —el contador vive en «Publicaciones»— | 25 · 28 |
| Asesor | Si al entrar **lee** la bandeja «Hoy» o se va a «Prospectos» por costumbre, y si encuentra «Ya está» sin que nadie se lo nombre | 28 |
| Todos | Cerrar un prospecto con su motivo: **nadie lo ha ensayado con una persona delante** | 30 |

**Nota sobre una nota:** el capítulo 28 dio por cerradas dos observaciones y solo una lo
estaba. Al líder se le dio ver los `HOT` que se enfrían, que es **otra pregunta distinta** de
cuántos esperan a que los repartan. Queda escrito porque el error no fue de código: fue dar
por resuelto un síntoma parecido al anotado.

---

## 5. Decisiones que no son técnicas

Aquí está construido lo necesario. Lo que falta es que alguien decida.

### 5.1. Los plazos de conservación no tienen valoración jurídica

**(R20 §20.8, R22 §22.9)**

Son **técnicos y provisionales**. Fijarlos corresponde a quien responda del tratamiento de
datos. La **oposición al tratamiento** no está modelada.

### 5.2. Aceptar el aviso de privacidad no es condición para crear la ficha

**(R21 §21.12)**

Se registra si llega. Qué hacer cuando no llega —rechazar la ficha, crearla marcada, crearla
y no contactar— es una decisión de quien responde del tratamiento, no del código.

**Sigue abierta tras el capítulo 38**, y conviene decirlo porque ese capítulo tocó justo al
lado. El punto 14 de §6.2 cerró que el alta del panel **ofreciera** la casilla; esta entrada
es si **exigirla**, y ahí no se tocó nada: la casilla no es obligatoria. La diferencia con la
página pública, donde sí lo es, es deliberada —allí la marca la persona, aquí la marcaría el
asesor por ella—, y obligarla garantizaría que se marque siempre, que es lo contrario de que
signifique algo (R36 §38.7).

### 5.3. Suprimir aquí no suprime en el CRM

**(R20 §20.8)**

Una entrega posterior del CRM vuelve a crear a la persona. La huella con clave permitiría
reconocerla y **rechazar la ingesta**, pero bloquear una entrada de negocio es una decisión
que nadie ha tomado. Las copias de seguridad conservan a la persona suprimida hasta 14 días;
no se editan volcados, y está dicho en la propia exportación.

**Tras el capítulo 38 la advertencia está donde se ve, que es todo lo que puede hacer el
software.** Hasta entonces vivía en este documento y en el campo `fuera_de_la_base` del JSON
de exportación, y ninguno de los dos lo lee quien atiende una petición de borrado. La
pantalla de derechos lo dice dos veces —en el bloque de confirmación y en el mensaje de
éxito— y dice además la mitad que no es obvia y que cambia lo que hay que hacer: no es solo
que los datos sigan allí, es que **volverán** con la siguiente entrega. Lo que falta es un
procedimiento para el otro lado, y eso sigue sin decidirse aquí.

### 5.4. «¿Qué necesitas?» no tiene peso

**(R25 §25.10)**

Informa y nada más. Darle peso —que una demostración pedida en la página cuente como
interés— es una decisión de negocio. Antes lo tenía y sumaba 25 puntos; el capítulo 25 se lo
quitó porque nadie había decidido que lo tuviera.

### 5.5. Reabrir un prospecto cerrado no es una operación del sistema

**(R29 §30.14)**

**Corregir** un cierre equivocado sí: se vuelve a cerrar y la fila se reescribe. Devolver un
trato a «En negociación» exigiría decidir qué pasa con su desenlace —si se borra, si se
conserva como histórico, si el dataset lo sigue usando—, y esa decisión no se ha tomado.

### 5.6. El peso de los motivos y la previsión de ingresos

**(R29 §30.14)**

Ningún motivo suma ni resta. El tramo del acuerdo agrupa lo ganado y **no se multiplica por
nada**. Si algún día se quiere saber si el motivo predice algo, eso es un análisis sobre los
datos ya recogidos, no una constante escrita a ojo.

### 5.7. El alta del panel no pregunta los ingresos

**(R24 §24.9)**

Deja el campo vacío y se rellena desde la ficha. Añadir el campo al alta es producto.

### 5.8. No hay A/B de textos

**(R26 §26.11)**

Una publicación tiene un texto. Duplicarla es la forma honrada de comparar dos hoy: dos
publicaciones, dos enlaces, la comparativa lado a lado.

### 5.9. No hay candidatos

**(R25 §25.10)**

La historia es de **prospectos comerciales**. Los perfiles que PluriOne coloca en sus
clientes son otra historia y otro sistema.

---

## 6. Deuda de ingeniería

No depende de nadie. Se puede hacer hoy. Ordenada por lo que cuesta si nadie la toca.

### 6.1. Lo que puede morder

> **Estado tras el capítulo 32 (cerrado el 24-09-2026).** De los ocho puntos, **seis
> cerrados**: 1, 2, 3, 4, 5 y 8. Quedan abiertos el **6** y el **7**, y los dos por el
> mismo motivo, que está escrito debajo de la tabla. La lista se conserva entera, tachada,
> porque un backlog del que se borran las filas resueltas deja de servir para saber qué se
> decidió y cuándo.
>
> Entra además un punto nuevo, el **24**, que el propio capítulo 32 encontró al comprobar si
> un país escrito por error se podía corregir desde el panel. No se cerró porque el arreglo
> afecta a **todos** los campos de la ficha a la vez y eso es una decisión de diseño con su
> propia discusión, no una corrección.

> **Estado tras el capítulo 33 (cerrado el 24-09-2026).** El punto **24** queda cerrado: la
> decisión que el capítulo 32 dejó por tomar se tomó, y la corrección completa está en el
> Reporte 31 (§33.2–§33.5). Vuelve a ser cierto lo que decía el capítulo 32: **§6.1 no tiene
> ningún punto que este equipo pueda cerrar por su cuenta**. Quedan el 6 y el 7, los dos
> esperando a un sistema externo.
>
> El 24 duró un capítulo, y conviene decir cómo se encontró porque no fue por donde se
> suelen encontrar estas cosas. No lo vio una prueba, ni el CI, ni una revisión: lo vio
> alguien preguntándose si el arreglo que acababa de escribir se podía usar. El capítulo 32
> quitó el país supuesto de cuatro sitios y escribió una migración que solo podía tocar
> parte de las fichas; las demás quedaban «a que un asesor las corrigiera», y nadie había
> comprobado que eso fuera posible. No lo era.

| # | Qué | Por qué importa | Origen | Estado |
| :---: | :--- | :--- | :---: | :---: |
| 1 | ~~**El CSV de realimentación no caduca**~~ | Vive fuera de la base y fuera del control de versiones. Es la última fila de la política de conservación sin plazo, y lleva datos de personas | R20 §20.8 · R22 §22.9 | **Cerrado** (R32 §32.2) |
| 2 | ~~**La bitácora de auditoría no tiene plazo en la aplicación**~~ | Es una decisión de operación desde el capítulo 14 y crece sin techo | R22 §22.9 | **Cerrado** (R32 §32.3) |
| 3 | ~~**`App.jsx` sigue sin pruebas**~~ | La redirección al cambio obligatorio de contraseña y el que no se lancen cargas de datos en ese estado están comprobados por lectura y por la prueba del componente, no por la aplicación montada. Arrastra desde el capítulo 17 y el 19 le añadió dos comportamientos más | R19 §19.9 | **Cerrado** (R32 §32.5) |
| 4 | ~~**La guarda no mira `apt-get`**~~ | Los cuatro paquetes de seguridad del backend van con versión; `libpq5` y las herramientas de compilación de la primera etapa, no. La guarda solo exige versión a `apk`: la misma indeterminación que se quitó en Alpine, a medias | R22 §22.9 | **Cerrado** (R32 §32.6) |
| 5 | ~~**Las acciones de GitHub van por etiqueta**~~ | `actions/checkout@v4`, no por el SHA del commit. Todo lo demás del CI va por huella | R22 §22.9 | **Cerrado** (R32 §32.6) |
| 6 | **Una entrega de WhatsApp con varios mensajes no es atómica** | Se validan todos antes de escribir, pero si el tercero falla al registrarse los dos primeros quedan. Un reintento los encuentra como duplicados, así que no corrompe; deja trabajo a medias | R21 §21.12 | **Abierto** |
| 7 | **Sin `event_id`, el CRM se deduplica por contenido** | Dos eventos reales idénticos byte a byte entran como uno | R21 §21.12 | **Abierto** → §3.10 |
| 24 | ~~**Ningún campo de la ficha se puede vaciar una vez escrito**~~ | La actualización parcial aplicaba `if value is not None`, así que un `null` explícito se ignoraba. Se podía cambiar un valor por otro; no borrarlo. Y no respondía que no: respondía **200 con la ficha entera**, de modo que la pantalla decía «Prospecto actualizado» y el dato seguía ahí | R32 §32.9 | **Cerrado** (R33 §33.2–§33.5) |
| 8 | ~~**El país sigue supuesto**~~ | La ficha escribe «México» cuando no llega. No puntúa en ninguna de las dos mitades del score, y quitarlo exige una migración de la columna | R25 §25.10 · H-7 | **Cerrado** (R32 §32.4) |

**Por qué 6 y 7 siguen abiertos, uno por uno.**

**6 — La entrega de WhatsApp con varios mensajes.** Arreglarlo es escribible: envolver el
registro de los mensajes de una entrega en una transacción y deshacerla entera si uno falla.
No se hizo porque **no se puede comprobar que esté arreglado**. Nadie ha conectado nunca una
cuenta de WhatsApp Business a este sistema (§3.2), así que la única forma de ejercitar el
caso es una prueba que simule el fallo del tercer mensaje, y eso comprueba el código que se
acaba de escribir, no el comportamiento con el proveedor real: no se sabe si WhatsApp
reentrega la tanda entera o solo lo que faltaba, y de esa respuesta depende si la
transacción única es la corrección o el problema. El daño mientras tanto está acotado y
medido: no corrompe nada —el reintento encuentra los dos primeros como duplicados por
`(source, external_event_id)`— y lo que deja es trabajo a medias, visible en la bandeja.
Pertenece a §3, «depende de cuentas externas», más que a la deuda de ingeniería.

**7 — La deduplicación por contenido del CRM.** Aquí no hay nada que escribir: la clave de
deduplicación es `(source, external_event_id)`, y cuando el sistema de origen **no manda**
identificador, la única huella disponible es el contenido. La alternativa —aceptar los dos
eventos y dejar que el operador decida— cambia un caso raro y sin daño (dos eventos reales
idénticos byte a byte, incluido el instante, entran como uno) por uno frecuente y con daño
(cada reentrega del CRM duplica la actividad). La corrección de verdad es que el CRM mande
`event_id`, y eso no se decide aquí. **Queda reclasificado a §3**, con lo demás que depende
de que alguien del otro lado haga algo.

Es decir: cerrado el punto 24 en el capítulo 33, **§6.1 no tiene ningún punto que este
equipo pueda cerrar por su cuenta**. Los dos que quedan esperan a un sistema externo, no a
más trabajo.

**24 — Vaciar un campo.** Cerrado en el capítulo 33. La decisión que el 32 dejó pendiente
—qué pasa cuando el vacío llega a un campo que la ficha no puede no tener— se resolvió con
un 422 que nombra el campo, y con la lista de campos obligatorios **derivada de la tabla**
en vez de escrita a mano, que es lo que evita que el arreglo caduque en la primera migración
que toque un `nullable`. La bitácora distingue desde entonces los campos vaciados de los
cambiados, sin copiar valores.

### 6.2. Huecos de la historia que se enseña

> **Estado tras el capítulo 38 (cerrado el 01-10-2026).** De los ocho puntos, **cuatro
> cerrados**: 11, 13, 14 y 16. Quedan abiertos el **9**, el **10**, el **12** y el **15**, y
> los cuatro por el mismo motivo, escrito debajo de la tabla: exigen decidir comportamiento
> **nuevo** del servidor, y eso es funcionalidad, no corrección.
>
> El capítulo 38 abrió la congelación para los tres que eran lo mismo con tres caras —una
> capacidad que existe, está probada y **no se puede usar desde donde hay que usarla**— y
> para ninguno más. No añadió ni un endpoint, ni una tabla, ni una migración: el servidor
> del capítulo 38 es el del 37 más un archivo de pruebas.
>
> Entra además un punto nuevo, el **35**, que el propio capítulo encontró al enlazar el
> contador del tablero con la matriz. No se cerró porque el arreglo honrado exige un
> parámetro nuevo en el listado, y hacerlo en el cliente sobre una página de cincuenta
> habría reproducido la discrepancia del capítulo 27.

| # | Qué | Estado | Origen |
| :---: | :--- | :--- | :---: |
| 9 | **Las integraciones no atribuyen la ficha a una campaña** | `formulario_web`, `linkedin_lead_gen`, Calendly y WhatsApp no leen el UTM. **Solo la página de interés atribuye.** H-4 está cerrado para ese camino y abierto para los demás | R25 §25.10 |
| 10 | **La asignación automática es solo para las fichas `HOT`** | H-6, a medias: hay dónde repartir, pero nada reparte solo. Una ficha `WARM` o `COLD` espera a que el líder la asigne | R25 §25.10 |
| 11 | ~~**El contador de «sin asesor» vive en «Publicaciones»**~~ | No en el tablero, que es donde el líder mira primero. Es la nota de usabilidad que el capítulo 28 dio por cerrada sin estarlo. **Cerrado** en el capítulo 38: el bloque se sacó a `ContadorSinAsesor` y se monta en los dos sitios —el mismo componente, no una copia del texto—, con enlace a la matriz, pedido solo a quien dirige la cartera y distinguiendo «no se preguntó» de cero (R36 §38.8) | R25 §25.10 · R28 §28.13 |
| 12 | **El reparto de la cartera de una baja es todo o nada** | A un solo destino. Repartir entre varias personas exige hacerlo prospecto a prospecto, y no hay aviso fuera del panel de administración | R19 §19.9 |
| 13 | ~~**El teléfono de los asesores no se normaliza**~~ | `users.phone`. El capítulo 21 se ocupó del de los prospectos. **Cerrado** en el capítulo 32: mismo E.164 y mismo módulo (`app.core.telefono`), con migración de los que ya estaban escritos de otra forma (R32 §32.4) | R21 §21.12 |
| 14 | ~~**El alta del panel no ofrece la casilla del aviso de privacidad**~~ | La API la admite (`privacy_notice_accepted`); la pantalla, no. **Cerrado** en el capítulo 38, y lo delicado no era que existiera: nace **sin marcar** —una aceptación por omisión es una suposición con fecha, indistinguible de las de verdad—, se envía siempre y **no** es obligatoria, que sigue siendo el §5.2 (R36 §38.7) | R21 §21.12 |
| 15 | **No hay pantalla para configurar integraciones** | Se encienden y se revocan por variables de entorno | R21 §21.12 |
| 16 | ~~**No hay interfaz para exportar ni para explicar la supresión**~~ | Los derechos del titular son API. Funcionan y están comprobados; no tienen pantalla. **Cerrado** en el capítulo 38: pantalla en administración que busca por correo, enseña qué consta y de dónde llegó, exporta el documento del servidor y suprime exigiendo que el correo se **escriba**, con su constancia. Sin lógica de supresión nueva (R36 §38.2–§38.6) | R20 §20.8 |
| 35 | **El listado no se puede filtrar por «sin asesor»** | El contador del tablero lleva a la matriz, donde las fichas que esperan llevan su marca, pero la lista no se acota a ellas. Filtrarla exige un parámetro nuevo en el servidor; hacerlo en el cliente sobre una página de cincuenta reproduciría la discrepancia del capítulo 27 —un número que dice siete y una lista con dos marcas— | R36 §38.10 |

**Por qué 9, 10, 12 y 15 siguen abiertos.** Los cuatro piden que el servidor **haga algo que
hoy no hace**: leer el UTM en cuatro conectores y decidir qué gana cuando hay dos
atribuciones posibles; repartir sin que nadie decida; partir una cartera entre varias
personas; y encender integraciones desde una pantalla, lo que significa guardar y rotar sus
secretos en la base en vez de en el entorno. Ninguno es «la frase ya está escrita y el
código no la cumple»; los cuatro son frases nuevas. Es la distinción del §1, y es la que
dejó entrar a los tres de este capítulo y detuvo a estos cuatro.

**16, 14 y 11 — qué se cerró exactamente.** Lo que faltaba no era la capacidad, era el
alrededor. En el 16: encontrar a la persona por su correo comparando la **igualdad** y no la
coincidencia parcial del buscador —quedarse con la primera fila del `LIKE` entrega o
destruye los datos de otra persona—; decir qué hace cada acción **antes** de ofrecerla;
contestar **lo mismo** para una dirección que nunca entró y para una cuya ficha ya no está,
para no ser el oráculo de pertenencia que la huella con clave de la bitácora evita; y avisar
de que suprimir aquí no suprime en el CRM (§5.3), dos veces y donde se ve. En el 14 y el 11,
lo que está en la tabla. Los tres quedan vigilados por los controles 46 y 47 del CI, con 22
defectos reintroducidos y 22 detectados.

### 6.3. Comprobaciones que nadie ha hecho a mano

| # | Qué | Por qué no se hizo | Origen |
| :---: | :--- | :--- | :---: |
| 17 | ~~**El código QR no se ha escaneado con un teléfono**~~ | Se comprueban las propiedades matemáticas y estructurales que exige la norma, que es lo verificable sin lector. **Es lo primero que habría que hacer antes de repartir material impreso**. **Hecho el 01-10-2026, y no lo leyó**: la información de formato iba transpuesta desde el capítulo 27, así que ningún lector podía empezar a decodificar. Las diecinueve pruebas del QR estaban verdes porque todas miden propiedades **simétricas respecto de la diagonal**. Corregido, con un lector escrito dentro de la suite y el control 48 del CI (R36 §38.10a) | R27 §27.13 · R36 §38.10 |
| 18 | **El panel no se ha recorrido con una persona dentro** | Entrar exige iniciar sesión. La suite del cliente y el ensayo automático cubren las pantallas; una persona, no. **El capítulo 36 acercó la mitad verificable**: las ocho pantallas pasan WCAG 2.1 AA medido por `axe`, se recorren con teclado y sus errores llegan a un lector de pantalla (R36). Lo que sigue sin responder es si **lo que ese lector dice se entiende**, y eso no lo contesta ninguna herramienta | R28 §28.13 · R36 §36.8 |
| 19 | **Nadie ha visto una solicitud de Dependabot en este repositorio** | `.github/dependabot.yml` está bien formado y el control 45 comprueba que cubre los seis ecosistemas y que la renovación a mano sigue mandando. Lo que ninguna prueba sustituye es el **primer lunes** que abra solicitudes de verdad: qué propone, si el CI las deja verdes y si alguna choca con la guarda `--solo-fijacion` | R37 §37.10 |
| 20 | **La comprobación de contraseñas filtradas no se ha ejecutado nunca contra el servicio real** | La suite usa una sonda simulada a propósito: una suite que depende de un tercero se pone roja los días que ese tercero tiene un mal día. Lo que falta por saber es si el contexto TLS del sistema basta desde la máquina del despliegue — y si no bastara, **el síntoma sería silencioso**: la política ante «no se pudo preguntar» es seguir adelante, así que la comprobación estaría apagada de hecho mientras el código afirma tenerla. **Es lo primero que hay que mirar en la bitácora el día del despliegue**, buscando el `WARNING` de `app.core.filtradas_remotas` | R37 §37.4 · §37.10 |

### 6.4. Restos menores

| # | Qué | Origen |
| :---: | :--- | :---: |
| 19 | `socat` y `pgAdmin` van fijados por huella, pero su etiqueta dice `latest` y no la versión | R22 §22.9 |
| 20 | Fuera de Docker la aplicación lee `.env` y `../.env` desde donde se lance; el lanzador cubre la pila, `uvicorn` directo depende de quien lo lanza | R22 §22.9 |
| 21 | En el entorno de desarrollo de **esta máquina** quedan `cffi`, `cryptography` y `pycparser`: un proceso ajeno tenía abierto `_cffi_backend.pyd` y no se detuvo. El código no los importa, el CI instala desde cero y la imagen no los lleva | R23 §23.7 |
| 22 | ~~Los ceros de ingresos que ya hay en la base no se migraron a nulos. El extractor los lee como ausentes, que es lo que importa al modelo; la ficha los muestra como cero hasta que alguien la edite~~ — **cerrado** en el capítulo 32: la migración `a4c8d1e70f39` los pasa a vacío y la base dice ya lo que el modelo leía (R32 §32.4) | R24 §24.9 |
| 23 | Un aviso purgado puede volver a entrar si el sistema de origen lo reentrega pasado el plazo; y **descartar no bloquea** | R21 §21.12 · R22 §22.9 |
| 25 | El **alta** no normaliza los textos en blanco: `LeadCreate` guarda `''` donde la edición guarda `NULL` desde el capítulo 33. Es el mismo arreglo en otro camino, y afecta también a las integraciones que dan de alta fichas, así que tiene su propia discusión | R33 §33.8 |
| 26 | El `except IntegrityError` de la edición traduce **cualquier** violación de integridad a «el correo ya existe», que es lo único que podía producirla. Con el 422 del esquema delante, un nulo sobre una columna `NOT NULL` no llega a ese commit; si llegara, el mensaje sería equivocado. Distinguir qué restricción falló obliga a leer el error del motor, específico de PostgreSQL y de SQLite por separado | R33 §33.8 |
| 27 | El **bundle de la SPA es descargable** desde la puerta pública: la página de interés lo necesita para dibujarse y es un solo archivo. Es código de cliente sin secretos y no puede llamar a nada —las rutas de gestión no existen en esa puerta—; evitarlo exigiría compilar un segundo bundle solo para esa página | R34 §34.8 |
| 28 | El **túnel no arranca con la pila**: hay que abrir una ventana y dejarla abierta, y la dirección hay que copiarla a mano en `pila.env` en cada arranque. Es deliberado mientras la dirección sea efímera —cerrar la ventana apaga la exposición al instante—, y es lo primero que se automatiza cuando haya dominio | R34 §34.8 |
| 29 | Un administrador **no puede quitarle el segundo factor a otro** desde el panel: la salida (b) de la guía existe en el diseño pero no tiene botón, porque la gestión de cuentas no ganó esa operación. Hoy se resuelve por la vía (c), que es la misma sentencia SQL | R35 §35.9 |
| 30 | **`CompartirEnRedes` se dibuja sin ningún estilo.** El componente no usa ni un estilo en línea: se apoya entero en **catorce clases que la hoja no define**, así que el panel de difusión y el del QR salen con el estilo por omisión del navegador. Escribirlas no es corregir un nombre —eso fue el caso de `input`, ya arreglado—, es **diseñar** el panel: colores, espaciados y estados. Está inventariado en `frontend/src/pruebas/clases.test.js`, que además impide que la lista crezca. **Sigue abierto tras el capítulo 38**, con una excepción de una línea: el aviso de «la dirección pública no contesta» que entró ahí lleva estilo en línea, porque un aviso que se ve igual que el cuerpo del texto no lo lee nadie, y darle borde y color a uno no es diseñar el panel (R36 §38.10c) | R36 §36.6 |
| 31 | **`btn-danger` no existe.** «Cerrar sesión» pide un aspecto de acción destructiva que la paleta no tiene, así que se dibuja como un `.btn` a secas —borde transparente, sin fondo— y no parece un botón. Darle uno exige un color nuevo en la paleta | R36 §36.6 |
| 32 | **El borde de un campo sin foco tiene 1.12:1** contra lo que lo rodea: el contorno es prácticamente invisible hasta que se le pone el foco. WCAG §1.4.11 pide 3.0 para lo que identifica un control. Subirlo es una decisión de paleta con efecto en todas las pantallas, no una corrección puntual | R36 §36.8 |
| 33 | **`var(--accent-primary)` no existe** en la paleta —el token se llama `--color-primary`—, así que el borde superior del girador de carga de `App.jsx` se queda sin color. Cosmético, y en un elemento que dura lo que una petición | R36 §36.8 |
| 34 | **La lista LOCAL de contraseñas filtradas no se actualiza sola.** Viene de §3.7, que el capítulo 37 cerró a medias: la comprobación contra el servicio público por rango añade cientos de millones de huellas, pero la lista de la imagen —la que decide cuando no hay internet— sigue siendo la foto del capítulo 23. Se regenera con `scripts/generar_lista_de_contrasenas.py`. No depende de ninguna cuenta; depende de que alguien lo corra, y por eso ya no vive en §3 | R23 §23.7 · R37 §37.10 |

---

## 7. Lo que no se va a hacer, y por qué

Distinto de todo lo anterior: esto no está pendiente, está **decidido**.

| Qué | Por qué |
| :--- | :--- |
| **Inventar un peso para los motivos del desenlace** | Una constante escrita a ojo que entra al modelo es indistinguible de una medición para quien lee el resultado seis meses después |
| **Cualquier previsión de ingresos** | El tramo del acuerdo agrupa lo ganado y no se multiplica por nada. Multiplicarlo por una tasa supuesta produce un número con dos decimales y ningún respaldo |
| **Contar personas en lugar de aperturas** | Las visitas de la página son aperturas. Contar personas exige cookies o dirección IP. Es a propósito |
| **Tratar la red de llegada como una medición** | La etiqueta dice por dónde se repartió el enlace que se abrió, no dónde estaba la persona. Quien recibe por WhatsApp un enlace copiado del post de LinkedIn cuenta como WhatsApp: correcto para decidir dónde volver a publicar, y nada más |
| **Un editor de reglas para el usuario** | Un editor de reglas es un lenguaje, y un lenguaje es otro proyecto. Las seis reglas están en el código con sus plazos configurables |
| **Bajar los mínimos del reentrenamiento para poder reentrenar antes** | El pipeline se negaría con razón. Los mínimos son 200 casos y 50 por clase, y publicar exige además que el límite inferior del intervalo alcance el umbral |
| **Automatizar el recálculo del score al cerrar** | El score guardado en el desenlace es el que había **cuando se decidió**. Recalcularlo destruiría la única respuesta posible a «¿el score acertaba?» |
| **TikTok** | Estaba fuera del alcance |
| **Granularidad menor de un día en el motor de reglas** | Una asignación de las diez de la mañana produce su tarea en la pasada siguiente. Los cierres sí son inmediatos. Bajar de un día convierte una pasada diaria en un servicio |
| **Regenerar el lock automáticamente** | Cuando se publique un aviso sobre una versión fijada, `pip-audit --strict` pondrá el pipeline en rojo y habrá que regenerar a mano. **Es el comportamiento buscado**: la alternativa es que el arreglo entre sin que nadie lo decida |
| **Avisar cuando no hay instantáneas** | En una instalación nueva es el estado normal durante días. Avisar de él sería ruido |
| **Conservar la huella de un aviso purgado para que no vuelva** | Sería guardar sin plazo un rastro de lo que se decidió no guardar |

---

## 8. Qué mirar el primer día que haya datos

Un orden sugerido, no un plan. Cada paso está construido y solo hay que ejecutarlo.

1. **Abrir el panel de «Desenlaces».** El contador dice cuántos casos utilizables hay y
   cuántos faltan para 200 con 50 de cada clase. Mientras no llegue, todo lo demás es
   prematuro.
2. **Mirar cuánto pesa «Otro motivo».** Si es el motivo más frecuente, la lista cerrada está
   mal y ampliarla es corrección, no funcionalidad (§1).
3. **Mirar la columna de categoría al cierre.** Es la respuesta a «¿el score acertaba?».
   Con los cierres del primer trimestre cualquier lectura es una anécdota, y el panel lo
   dice en vez de redondearlo.
4. **Extraer el dataset y medirlo sin publicar.** `feedback_dataset.py` y
   `train_model.py --datos realimentacion`. Medir y publicar están separados a propósito.
5. **Comprobar el manifiesto** antes de mirar ninguna métrica: cuántas filas se descartaron
   por vector antiguo, cuántas se etiquetaron solo por su estado y cuántas llevan motivo.
   Una cohorte con mitad de filas heredadas no dice lo mismo que una entera.
6. **Solo entonces, pedir la publicación.** Y aceptar que se niegue.

---

## 9. Dónde está cada cosa

| Qué | Dónde |
| :--- | :--- |
| El estado completo del sistema | `README.md` |
| Los capítulos con su detalle | `docs/reportes/` |
| Todo compilado, con portada e índice | `docs/Memoria_Tecnica_Final_Lead_Scoring.md` |
| La historia que se enseña, con sus reglas | `docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md` |
| El guion cronometrado y su ensayo | `docs/Guion_Cronometrado_de_la_Demo.md` |
| Cómo sentar a cuatro personas delante | `docs/Prueba_Con_Personas.md` |
| La defensa oral y las preguntas difíciles | `docs/GUIA_DEFENSA_ORAL.md` |
| Qué actualiza un tercero y qué sigue decidiendo una persona | `.github/dependabot.yml` |
| **Lo que queda por hacer** | **este documento** |
