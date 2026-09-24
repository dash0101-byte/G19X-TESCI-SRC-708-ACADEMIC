# Congelación de funcionalidades y trabajo futuro

**Fecha de congelación:** 24 de septiembre de 2026
**Alcance:** todo el repositorio `Sistema_Inteligente_Lead_Scoring`
**Sustituye a:** las secciones «Lo que esta fase no hizo» dispersas en los reportes 19 a 29

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

Cada entrada lleva su origen entre paréntesis: `R25 §25.10` es el reporte 25, apartado
25.10. **Ojo con la numeración**: desde el Reporte 29 el número del reporte va uno por
detrás del capítulo (el capítulo 29 no escribió reporte propio), así que el Reporte 29
contiene el capítulo 30 y sus apartados se numeran `30.x`.

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

**(R27 §27.13)**

El HTML se comprueba como lo lee un rastreador, y las etiquetas Open Graph y Twitter Card
son las que LinkedIn, WhatsApp, Facebook y X documentan. Pero pegar el enlace y **mirar** la
tarjeta exige una dirección pública, y la de la demostración es `localhost`.

**Qué haría falta:** un dominio con certificado, aunque sea de pruebas.

### 3.5. Nada sale del panel

**(R28 §28.13)**

Ni correo, ni WhatsApp, ni notificación de navegador. Las tareas y los avisos del motor de
reglas viven dentro del panel y se ven al entrar.

**Esto no es solo una cuenta que falta.** Un aviso que sale del sistema necesita una
dirección verificada, una política de qué hacer cuando rebota y, sobre todo, saca de la
aplicación el nombre de una persona que aceptó un aviso de privacidad para otra cosa. La
cuenta es el requisito más barato de los tres.

### 3.6. No hay segundo factor

**(R23 §23.7, R19 §19.9)**

Era opcional en el alcance y **no se hizo a medias a propósito**. Un TOTP para
`System_Admin` exige alta con código de verificación, códigos de recuperación, un paso más
en el login del cliente y una respuesta para quien pierde el teléfono siendo el único
administrador —que es justo la cuenta que no puede quedarse fuera. Añadir la verificación
sin eso produce una cuenta de administración que se bloquea sola.

Depende de cuenta externa solo en parte: la entrega de los códigos de recuperación y
cualquier canal de rescate sí la necesitan.

### 3.7. La lista de contraseñas filtradas no se actualiza sola ni es exhaustiva

**(R23 §23.7)**

Es una foto de dos listas públicas, con manifiesto de cuáles salió. Cubre las filtradas más
frecuentes de 12 caracteres o más. Comprobar contra cientos de millones de huellas sin un
servicio externo pediría un archivo de decenas de gigabytes dentro de la imagen.

**Qué haría falta:** una cuenta en un servicio de comprobación de contraseñas
comprometidas —con el modelo de *k-anonymity*, que no envía la contraseña— o aceptar el
tamaño.

### 3.8. Nadie avisa de que una huella de imagen se quedó atrás

**(R22 §22.9)**

Todas las imágenes de terceros van fijadas por huella y se renuevan con
`scripts/renovar_imagenes.py`. Que alguien **tenga que correr el guion** es deliberado.
Automatizarlo con un servicio que abra solicitudes de cambio exige una cuenta.

### 3.9. Las copias de seguridad no salen de la máquina

**(R19 §19.9)**

Hay copias, con prueba de restauración comprobada (capítulo 16). Sacarlas de la máquina
exige almacenamiento externo.

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

### 5.3. Suprimir aquí no suprime en el CRM

**(R20 §20.8)**

Una entrega posterior del CRM vuelve a crear a la persona. La huella con clave permitiría
reconocerla y **rechazar la ingesta**, pero bloquear una entrada de negocio es una decisión
que nadie ha tomado. Las copias de seguridad conservan a la persona suprimida hasta 14 días;
no se editan volcados, y está dicho en la propia exportación.

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

| # | Qué | Por qué importa | Origen |
| :---: | :--- | :--- | :---: |
| 1 | **El CSV de realimentación no caduca** | Vive fuera de la base y fuera del control de versiones. Es la última fila de la política de conservación sin plazo, y lleva datos de personas | R20 §20.8 · R22 §22.9 |
| 2 | **La bitácora de auditoría no tiene plazo en la aplicación** | Es una decisión de operación desde el capítulo 14 y crece sin techo | R22 §22.9 |
| 3 | **`App.jsx` sigue sin pruebas** | La redirección al cambio obligatorio de contraseña y el que no se lancen cargas de datos en ese estado están comprobados por lectura y por la prueba del componente, no por la aplicación montada. Arrastra desde el capítulo 17 y el 19 le añadió dos comportamientos más | R19 §19.9 |
| 4 | **La guarda no mira `apt-get`** | Los cuatro paquetes de seguridad del backend van con versión; `libpq5` y las herramientas de compilación de la primera etapa, no. La guarda solo exige versión a `apk`: la misma indeterminación que se quitó en Alpine, a medias | R22 §22.9 |
| 5 | **Las acciones de GitHub van por etiqueta** | `actions/checkout@v4`, no por el SHA del commit. Todo lo demás del CI va por huella | R22 §22.9 |
| 6 | **Una entrega de WhatsApp con varios mensajes no es atómica** | Se validan todos antes de escribir, pero si el tercero falla al registrarse los dos primeros quedan. Un reintento los encuentra como duplicados, así que no corrompe; deja trabajo a medias | R21 §21.12 |
| 7 | **Sin `event_id`, el CRM se deduplica por contenido** | Dos eventos reales idénticos byte a byte entran como uno | R21 §21.12 |
| 8 | **El país sigue supuesto** | La ficha escribe «México» cuando no llega. No puntúa en ninguna de las dos mitades del score, y quitarlo exige una migración de la columna | R25 §25.10 · H-7 |

### 6.2. Huecos de la historia que se enseña

| # | Qué | Estado | Origen |
| :---: | :--- | :--- | :---: |
| 9 | **Las integraciones no atribuyen la ficha a una campaña** | `formulario_web`, `linkedin_lead_gen`, Calendly y WhatsApp no leen el UTM. **Solo la página de interés atribuye.** H-4 está cerrado para ese camino y abierto para los demás | R25 §25.10 |
| 10 | **La asignación automática es solo para las fichas `HOT`** | H-6, a medias: hay dónde repartir, pero nada reparte solo. Una ficha `WARM` o `COLD` espera a que el líder la asigne | R25 §25.10 |
| 11 | **El contador de «sin asesor» vive en «Publicaciones»** | No en el tablero, que es donde el líder mira primero. Es la nota de usabilidad que el capítulo 28 dio por cerrada sin estarlo | R25 §25.10 · R28 §28.13 |
| 12 | **El reparto de la cartera de una baja es todo o nada** | A un solo destino. Repartir entre varias personas exige hacerlo prospecto a prospecto, y no hay aviso fuera del panel de administración | R19 §19.9 |
| 13 | **El teléfono de los asesores no se normaliza** | `users.phone`. El capítulo 21 se ocupó del de los prospectos | R21 §21.12 |
| 14 | **El alta del panel no ofrece la casilla del aviso de privacidad** | La API la admite (`privacy_notice_accepted`); la pantalla, no | R21 §21.12 |
| 15 | **No hay pantalla para configurar integraciones** | Se encienden y se revocan por variables de entorno | R21 §21.12 |
| 16 | **No hay interfaz para exportar ni para explicar la supresión** | Los derechos del titular son API. Funcionan y están comprobados; no tienen pantalla | R20 §20.8 |

### 6.3. Comprobaciones que nadie ha hecho a mano

| # | Qué | Por qué no se hizo | Origen |
| :---: | :--- | :--- | :---: |
| 17 | **El código QR no se ha escaneado con un teléfono** | Se comprueban las propiedades matemáticas y estructurales que exige la norma, que es lo verificable sin lector. **Es lo primero que habría que hacer antes de repartir material impreso** | R27 §27.13 |
| 18 | **El panel no se ha recorrido con una persona dentro** | Entrar exige iniciar sesión. La suite del cliente y el ensayo automático cubren las pantallas; una persona, no | R28 §28.13 |

### 6.4. Restos menores

| # | Qué | Origen |
| :---: | :--- | :---: |
| 19 | `socat` y `pgAdmin` van fijados por huella, pero su etiqueta dice `latest` y no la versión | R22 §22.9 |
| 20 | Fuera de Docker la aplicación lee `.env` y `../.env` desde donde se lance; el lanzador cubre la pila, `uvicorn` directo depende de quien lo lanza | R22 §22.9 |
| 21 | En el entorno de desarrollo de **esta máquina** quedan `cffi`, `cryptography` y `pycparser`: un proceso ajeno tenía abierto `_cffi_backend.pyd` y no se detuvo. El código no los importa, el CI instala desde cero y la imagen no los lleva | R23 §23.7 |
| 22 | Los ceros de ingresos que ya hay en la base no se migraron a nulos. El extractor los lee como ausentes, que es lo que importa al modelo; la ficha los muestra como cero hasta que alguien la edite | R24 §24.9 |
| 23 | Un aviso purgado puede volver a entrar si el sistema de origen lo reentrega pasado el plazo; y **descartar no bloquea** | R21 §21.12 · R22 §22.9 |

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
| Los treinta capítulos con su detalle | `docs/reportes/` |
| Todo compilado, con portada e índice | `docs/Memoria_Tecnica_Final_Lead_Scoring.md` |
| La historia que se enseña, con sus reglas | `docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md` |
| El guion cronometrado y su ensayo | `docs/Guion_Cronometrado_de_la_Demo.md` |
| Cómo sentar a cuatro personas delante | `docs/Prueba_Con_Personas.md` |
| La defensa oral y las preguntas difíciles | `docs/GUIA_DEFENSA_ORAL.md` |
| **Lo que queda por hacer** | **este documento** |
