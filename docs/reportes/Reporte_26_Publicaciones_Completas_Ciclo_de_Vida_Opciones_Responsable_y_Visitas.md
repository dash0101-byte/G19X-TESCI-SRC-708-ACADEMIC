# Capítulo 26: Publicaciones Completas — Ciclo de Vida, Opciones, Responsable y Visitas

## 26.1. De dónde se parte

El capítulo 25 dejó la historia completa, del post de LinkedIn al prospecto puntuado, pero la
publicación seguía siendo mínima: un texto, a quién va dirigida y un enlace. El líder no
podía:

* ver cómo quedaría el post antes de pegarlo;
* revisar la página antes de que la abriera nadie;
* dejar una publicación a medias;
* pararla sin darla por terminada;
* ponerle fecha de fin;
* decidir qué opciones de «¿Qué necesitas?» ofrecía;
* decir quién atiende lo que llega;
* enlazar el post real;
* reutilizar una publicación que funcionó;
* saber cuánta gente abrió la página sin dejar sus datos.

Este capítulo amplía la sección «Publicaciones» con todo eso. Las reglas del capítulo 25
siguen valiendo: una publicación es una campaña, sin tabla paralela (R-2), y lo que no se sabe
no se inventa (R-4). Editan el líder y el administrador, y el asesor consulta, igual que antes.

| Qué | Dónde se ve | Qué garantiza |
| :--- | :--- | :--- |
| Vista previa del post | Formulario y lista | Corte de «ver más», aviso a 3 000 caracteres |
| Vista previa de la página | Botón «Ver la página» | La página tal cual, en cualquier estado, sin contar visita ni enviar |
| «¿Qué necesitas?» por publicación | Página, ficha 360, informe | De 2 a 5 opciones; solo valen las suyas; siguen sin puntuar |
| Asesor responsable | Formulario, lista, informe | Las fichas nuevas se le asignan; si deja de ser asesor, llegan sin asesor |
| Estados y cierre automático | Lista, página, informe | Solo «activa» sirve la página; la fecha de cierre la cierra sola |
| Dirección del post | Formulario, informe | De linkedin.com por el nombre de la máquina |
| Duplicar | Lista | Borrador con enlace propio; no se lleva lo que trajo el original |
| Visitas y tasa de envío | Informe, comparativa | Un número por día; sin cookies ni datos de nadie |
| Perfiles por día | Informe | Una barra por día, con los días vacíos a cero |

---

## 26.2. El modelo de datos

La migración `d5a8e2f41c73` añade cuatro columnas a `campaigns` y una tabla:

| Columna | Tipo | Al migrar |
| :--- | :--- | :--- |
| `estado` | texto, obligatorio | «activa» si `is_active`; **«cerrada»** si no |
| `necesidades` | JSON | vacío: siguen con las opciones de siempre |
| `responsable_id` | FK a `users`, `SET NULL` | vacío: siguen llegando sin asesor |
| `url_del_post` | texto (300) | vacío |

Una campaña desactivada antes de que hubiera estados pasa a «cerrada» y no a «pausada».
Desactivar era dejar de recibir perfiles; «pausada» prometería que se va a reanudar.

`visitas_de_publicacion` tiene **tres columnas**: publicación, día y número. La clave primaria es
(publicación, día).

La reversión quita la tabla y las cuatro columnas y conserva las campañas y su `is_active`. Lo
que se pierde está escrito en la propia migración: los estados, las opciones propias, el
responsable, la dirección del post y las visitas.

`is_active` no desaparece. Se mantiene igual a «está activa» desde un solo sitio,
`fijar_estado`, porque el listado de campañas y la baja lógica lo leen desde antes de que
hubiera estados. Nada escribe `is_active` por su cuenta. Un `PUT` con `is_active` suelto, que es
como el panel reactivaba antes, se traduce en activa (verdadero) o pausada (falso), y el
`DELETE` cierra.

---

## 26.3. Estados y cierre automático

| Estado | La página | Qué significa |
| :--- | :--- | :--- |
| Borrador | «No disponible» | Se está escribiendo; el enlace existe pero no sirve |
| Activa | Recibe perfiles | La única que sirve la página |
| Pausada | «No disponible» | Se deja de recibir sin darla por terminada |
| Cerrada | «No disponible» | Terminó |

Fuera de «activa», la página responde con **el mismo texto** que un enlace inventado: decir
cuál de los casos es ayudaría a recorrer enlaces ajenos. Sin estado explícito, una
publicación nace activa, como antes. El guion de la demo crea la publicación y copia su enlace
en el mismo minuto, y un borrador por defecto habría sido un atasco nuevo en el paso 3.

La **fecha de cierre** es la `end_date` de siempre. Una publicación activa o pausada cuya fecha
ya pasó se cierra sola. No hay tarea programada que la vigile: se cierra la primera vez que
alguien mira —la página, la lista, el informe, la comparativa— y antes de contestar, con una
sola sentencia (`cerrar_vencidas`) que no toca nada si no hay vencidas. Así no depende de que
un proceso aparte esté vivo, y una página vencida no se sirve nunca, aunque nadie haya abierto
el panel desde que venció. Un borrador no se cierra por fecha, porque nunca se abrió. Activar
algo cuya fecha ya pasó responde 422, porque lo volvería a cerrar en el acto.

En el panel, el formulario pide la fecha por día y cierra al terminar ese día. Cada
publicación ofrece solo lo que se puede hacer desde su estado:

* **borrador:** Activar;
* **activa:** Pausar o Cerrar;
* **pausada:** Reanudar o Cerrar;
* **cerrada:** Reabrir.

---

## 26.4. Las dos vistas previas

**El post.** `VistaPreviaDelPost` pinta el texto como una tarjeta del feed de LinkedIn y lo corta
donde lo corta LinkedIn: a las tres líneas o a unos 210 caracteres, lo que llegue antes, sin
partir palabras, con «…ver más». Cuenta el texto entero, enlace incluido, contra el tope de
3 000 y avisa si pasa («sobran N»). Dice además algo que casi nadie comprueba: **si el enlace
ha quedado detrás de «ver más»**, donde solo lo ve quien despliega el texto. En el formulario
la vista previa se actualiza mientras se escribe, con un enlace del mismo largo que los de
verdad; en la lista, con el texto exacto que se copia.

**La página.** «Ver la página» enseña la página de interés **tal como la verá el interesado**. Es
el mismo componente, no una imitación, dentro de un marco del ancho de un teléfono. Los datos
vienen de `GET /publicaciones/{id}/vista-previa`, que devuelve exactamente lo que sirve la ruta
pública (una prueba compara las dos respuestas). Tiene tres diferencias, y las tres importan:

* funciona en **cualquier estado**, porque un borrador se revisa precisamente antes de activarlo;
* **no cuenta una visita**, porque mirar la propia página desde el panel no es la visita de
  nadie, y si contara, la tasa bajaría cada vez que el líder la revisa;
* **no envía nada**: el botón está desactivado y un aviso lo dice.

---

## 26.5. «¿Qué necesitas?» por publicación

Cada publicación puede tener sus propias opciones, de **2 a 5**:

* con una sola no hay nada que elegir;
* con más de cinco los botones ya no caben en la pantalla del teléfono sin desplazarse, y el
  formulario de treinta segundos del capítulo 25 deja de serlo.

Cada opción tiene de 2 a 40 caracteres, y no se admiten repetidas. El líder escribe las
etiquetas y el servidor deriva la clave: «Ver una demostración» → `ver_una_demostracion`. Sin
opciones propias, la publicación usa las de siempre.

Tres decisiones:

* **Solo valen las de esa publicación.** La página valida el envío contra las opciones de su
  publicación. «vacantes», que es de las de siempre, no vale en una publicación con las suyas.
  El error tiene la forma de los del esquema, así que aparece junto al campo. El esquema solo
  exige forma de clave (`[a-z0-9_]`): una frase sigue siendo un 422 antes de mirar ninguna
  publicación.
* **La etiqueta se guarda con el envío.** La actividad lleva `necesidad` (la clave) y
  `necesidad_etiqueta` (lo que vio la persona). Si el líder cambia después las opciones, lo que
  eligió quien ya escribió no cambia con ellas. La ficha 360 y el informe leen la etiqueta
  guardada; las solicitudes anteriores, que solo tienen clave, caen en las opciones de siempre,
  que eran las únicas.
* **Siguen sin puntuar.** Toda solicitud es `FORM_SUBMIT` y la necesidad no entra en
  `raw_metadata`. Personas iguales que eligen opciones propias distintas obtienen el mismo
  score, el mismo desglose y la misma probabilidad del modelo; lo comprueban una prueba y la
  guarda.

---

## 26.6. El asesor responsable

Una publicación puede tener responsable: un **asesor comercial activo**. Crearla o editarla con
otra persona —el líder, una cuenta de baja, un id que no existe— responde 422. Las fichas
**nuevas** que llegan por su página nacen asignadas a él. Por eso también quedan fuera del
contador de prospectos sin asesor: ya tienen a alguien detrás.

Tres casos que no se asignan, a propósito:

* **Sin responsable**, la ficha llega sin asesor al líder, como en el capítulo 25.
* **Si el responsable dejó de ser asesor activo** después de elegirlo, se comprueba otra vez al
  llegar cada ficha, y llega sin asesor. Asignarla a una cartera que nadie abre sería
  esconderla.
* **Una ficha que ya existía** no se reasigna. La página de interés no toca fichas existentes
  desde el capítulo 25 (`actualiza_prospecto=False`), y cambiar su asesor sería tocarla.

El asesor llega a la ficha por el registro de actividad, como el resto de datos. Lo pone el
código de la página, con el responsable ya comprobado, y `registrar_evento` solo acepta ahí un
entero. Ningún conector lo copia de lo que recibe de fuera. La auto-asignación de las fichas
`HOT` sigue existiendo, pero no pisa una ficha que ya nace con asesor.

---

## 26.7. La dirección del post y duplicar

**La dirección del post** se guarda si es de LinkedIn de verdad, y se comprueba **el nombre de la
máquina**, no que el texto contenga «linkedin.com». `https://linkedin.com.ejemplo.net/…`,
`https://ejemplo.net/?ir=linkedin.com` y `https://milinkedin.com/…` lo contienen y llevan a
otra parte, y este enlace lo abre el líder desde el informe.

Además se exige:

* esquema `https`;
* sin usuario ni contraseña en la dirección;
* sin puerto raro;
* con una ruta.

Se guarda limpia: sin los parámetros de campaña que añade el botón «compartir» y sin fragmento.
El informe y la lista la enlazan en otra pestaña con `rel="noopener noreferrer"`.

**Duplicar** crea otra publicación con el texto, el público, las opciones y el responsable, con
estos cambios:

* sale en **borrador**;
* el nombre lleva «(copia)»;
* tiene **enlace propio**, porque el del original ya está publicado y apunta al original para
  siempre;
* no se lleva la dirección del post, las fechas, las visitas ni los perfiles: es otro post, y
  lo que trajo el original sigue siendo del original.

Solo pueden duplicar el líder y el administrador, y queda en la bitácora
(`campana.duplicar`), con la publicación de la que salió.

---

## 26.8. Visitas, tasa de envío y perfiles por día

**Las visitas** se cuentan en `GET /interes/{slug}`, cuando la publicación está activa: una fila
por publicación y día con un número. No se guarda ni IP, ni navegador, ni hora, ni ninguna
cookie. Quien solo miró no ha aceptado ningún aviso de privacidad, y así no hay nada suyo que
suprimir ni que proteger. La página no disponible no cuenta, y la vista previa del panel
tampoco.

Tres cosas que aparecieron al medir, y cómo se resolvieron:

* **En desarrollo, cada apertura contaba dos visitas.** React monta dos veces cada componente y
  la página se pedía dos veces. El cliente comparte ahora la misma petición cuando dos iguales
  salen a la vez; una apertura posterior sí vuelve a pedir, y cuenta. En producción no había
  doble montaje, pero un recuento que depende de cómo se sirve el panel no es un recuento.
* **La tasa salía del 200 %** en la publicación de ejemplo. Sus envíos eran anteriores a que se
  contaran visitas: el preparador de la demo los mandaba directamente, sin abrir la página. La
  **tasa de envío** —envíos entre visitas, en tanto por ciento— cuenta ahora solo los envíos
  **desde el primer día con visitas contadas**, y el panel lo dice («N envíos desde que se
  cuentan visitas»). Sin visitas no hay tasa: un guion, no un 0 %. Puede pasar de 100, porque
  quien corrige un error y vuelve a enviar no vuelve a abrir la página. El preparador abre ya la
  página antes de cada perfil, y nueve veces más sin enviar.
* **La publicación de ejemplo heredaba las visitas de la anterior.** La resiembra de la demo
  borraba las campañas y no las visitas, y SQLite reutiliza el id: la publicación nueva
  empezaba con las visitas de la borrada. `seed_data.py` vacía ahora la tabla de visitas antes
  que las campañas, y una prueba exige que cualquier tabla que cuelgue de `campaigns` se vacíe
  antes que ella.

**El gráfico de perfiles por día** es un SVG propio, sin librería: una barra por día, con los
días sin perfiles a cero para que un hueco no se lea como un dato que falta. Tiene un
límite de 90 días, los últimos; si el periodo es más largo, lo dice. Lleva una descripción
para quien no ve el dibujo y una tabla desplegable con perfiles y visitas de cada día. Las
barras son solo de perfiles: dos series en la misma escala esconderían la pequeña, que es la
que importa. Los perfiles se acotan como las filas del informe, y un asesor ve en el gráfico
solo los suyos. Las visitas y los envíos son totales sin nombres, iguales para todos.

La comparativa entre publicaciones suma estado, visitas y tasa de envío a cada fila.

---

## 26.9. Que nada de esto sea decorativo

### Pruebas

| Dónde | Qué |
| :--- | :--- |
| `test_publicaciones_completas.py` | 74 casos: estados, cierre por fecha, opciones, responsable, dirección del post, duplicar, visitas, tasa, gráfico, vista previa |
| `test_migracion_publicaciones_completas.py` | Alembic de verdad en un proceso aparte: datos migrados, valor por defecto, clave de visitas, reversión, vuelta adelante y **esquema migrado igual al de los modelos** |
| `test_seed_data_guards.py` | Toda tabla que cuelga de `campaigns` se vacía antes que ella |
| Cliente | `Publicaciones.test.jsx` (25), `VistaPreviaDelPost.test.jsx`, `GraficoPorDia.test.jsx`, y lo añadido a la página, al informe y al catálogo de rutas |

### La guarda del CI

`scripts/guarda_de_la_pagina_publica.py` suma una sexta comprobación, **el ciclo de la
publicación**. Cada punto se prueba ejecutando, no leyendo el código:

* un borrador, una pausada, una cerrada y una activa vencida responden «no disponible» a
  la lectura y al envío;
* el contador guarda solo publicación, día y número, tres aperturas cuentan tres, la página
  no pone cookies y la vista previa no cuenta;
* una publicación con opciones propias sirve las suyas, rechaza una ajena y ninguna mueve la
  puntuación;
* el responsable activo recibe la ficha y uno de baja no;
* las direcciones de post falsas se rechazan.

El límite de lecturas y el de envíos siguen comprobándose como en el capítulo 25.

### Reintroducciones

Con el arnés de siempre —copia, altera, exige el fallo y restaura comprobando la huella—,
26 defectos:

| Defecto | Lo atrapa |
| :--- | :--- |
| La página sirve cualquier estado | Guarda |
| La página no cierra las vencidas antes de servir | Guarda |
| El cierre por fecha no cierra nada | Guarda |
| `is_active` se desacopla del estado | Pruebas |
| Cada visita cuenta dos | Guarda |
| El contador guarda la IP | Guarda |
| La vista previa cuenta una visita | Guarda |
| Se aceptan las opciones de siempre en una publicación con las suyas | Guarda |
| Una opción propia puntúa | Guarda |
| El responsable no recibe la ficha | Guarda |
| Un responsable de baja sigue recibiendo fichas | Guarda |
| La dirección del post se comprueba por contener «linkedin.com» | Guarda |
| La dirección del post admite http | Guarda |
| Duplicar publica la copia | Pruebas |
| Duplicar se lleva la dirección del post | Pruebas |
| El asesor duplica | Pruebas |
| El asesor cambia el estado | Pruebas |
| Hasta ocho opciones | Pruebas |
| Sin visitas, una tasa del 0 % | Pruebas |
| El gráfico enseña al asesor los perfiles ajenos | Pruebas |
| La migración deja las desactivadas como pausadas | Prueba de la migración |
| La reversión deja la tabla de visitas | Prueba de la migración |
| La vista previa del panel envía | Pruebas del cliente |
| Cada apertura en desarrollo cuenta dos visitas | Pruebas del cliente |
| La vista previa del post no corta | Pruebas del cliente |
| Sin aviso al pasar de 3 000 caracteres | Pruebas del cliente |

**26 de 26.** La primera ronda dejó uno sin atrapar, «hasta ocho opciones». La prueba del
máximo construía su caso con la propia constante (`MAX_NECESIDADES + 1`), así que al subir la
constante la prueba se movía con ella. Ahora escribe el seis a mano: el requisito es «de 2 a
5», y si la constante cambia, la prueba tiene que fallar.

---

## 26.10. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend | **1082 pruebas**, 93 % de cobertura (la de la memoria completa, después de regenerarla con este capítulo) |
| Suite del cliente | **267 pruebas**; `eslint .` sin avisos |
| `ruff check .` | Sin avisos |
| Guarda de la página pública | Pasa sobre el árbol correcto |
| Reintroducciones | 26 de 26, cada archivo restaurado con su huella comprobada |
| Migración en SQLite | Prueba propia: ida, vuelta y esquema igual al de los modelos |
| Migración en PostgreSQL 16 (la imagen del CI, en un contenedor local desechable) | `upgrade head`, `alembic check` sin diferencias, `downgrade base`, `upgrade head`, `alembic check`; una campaña activa pasa a «activa» y una desactivada a «cerrada»; la reversión quita la tabla y conserva las campañas |
| Recorrido en el navegador, a 375 × 812, contra la base de la demo migrada | Pausada, la página dice «no disponible». Activa con opciones propias, enseña esas tres opciones y cabe en una pantalla. Un envío llega asignado al responsable y con la etiqueta elegida en la ficha 360 y en el informe. Una apertura de la página en desarrollo cuenta una visita, no dos. La copia duplicada es un borrador cuya página responde 404 y que el asesor puede previsualizar. El asesor recibe 403 al pausar y al duplicar, y una dirección de post falsa, 422 |
| Informe de la publicación de ejemplo tras regenerar la demo | 12 visitas, 3 envíos, tasa del 25 % |

El panel del líder —formulario, lista, botones de estado, vistas previas— no se recorrió en el
navegador. Hace falta iniciar sesión, y eso no se hace en el navegador de esta sesión. Lo
cubren las pruebas de los componentes y el recorrido de su API en proceso, con testigos
acuñados.

---

## 26.11. Lo que este capítulo no hizo

* **No hay A/B.** Una publicación tiene un texto. Probar varios textos de la misma publicación
  queda fuera, y duplicar es la forma honrada de compararlos hoy: dos publicaciones, dos
  enlaces, la comparativa lado a lado.
* **No se publica en LinkedIn automáticamente.** Se copia el texto y se pega; la dirección del
  post se escribe a mano después. Publicar exige una cuenta de la API de LinkedIn.
* **No se reentrena el modelo.** Ni las opciones de «¿Qué necesitas?» ni la tasa de envío llegan
  al modelo o a la regla.
* **Las visitas son aperturas, no personas.** Sin cookies ni IP no se puede saber cuántas
  personas distintas abrieron la página, y es a propósito. Una persona que recarga cuenta dos.
* **La tasa cuenta desde el primer día con visitas**, no desde la primera visita. El día en que
  empezaron a contarse puede incluir envíos anteriores a esa primera visita. Pasado ese día, la
  tasa es la que es.
* **El cierre es por día y en UTC.** «Se cierra el 30» cierra a las 23:59:59 UTC del 30, que en
  México es la tarde de ese día.
* **La sesión con personas sigue sin hacerse** (capítulo 25, §25.6). Lo que este capítulo
  añadió —el ciclo de la publicación, las opciones, el responsable y las visitas— **no llegó
  a las listas de tareas del guion** hasta el capítulo 29, y aun entonces solo en parte: el
  guion recorre ahora la difusión por dos redes y la bandeja «Hoy», pero cerrar una
  publicación, duplicarla o mirar su tasa de envío siguen sin tener a nadie delante. Se dice
  aquí porque es fácil confundir «tiene pruebas» con «se ha probado con alguien».
