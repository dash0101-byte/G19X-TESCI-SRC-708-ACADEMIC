# Capítulo 30: Cerrar el Bucle — El Desenlace con su Motivo, Panel de Desenlaces y Contador del Reentrenamiento

> **Sobre la numeración.** Este es el **Reporte 29** y el **capítulo 30**. Los dos números
> dejaron de coincidir en el capítulo 29, «Lo que dijeron las personas», que no escribió un
> reporte propio: lo que produjo —el guion de demostración, las hojas de observación y su
> lector— se incorporó como actualización fechada dentro de los reportes 25 a 28. Se deja
> dicho aquí en lugar de renumerar nada: un reporte que cambia de número rompe todas las
> referencias cruzadas de los anteriores, y el desajuste es más barato explicado que
> disimulado. Los apartados se numeran **30.x**, por el capítulo: es lo que se lee en el
> índice de la memoria técnica y lo que citarán los reportes siguientes.

## 30.1. De dónde se parte

El bucle de realimentación existe desde el capítulo 18. `ml_pipeline/src/feedback_dataset.py`
sabe leer, de cada prospecto cerrado, la instantánea de variables del momento en que entró
al embudo, etiquetarla con su desenlace y producir un dataset con su manifiesto de
procedencia. El capítulo 24 le puso versión al vector para que una instantánea vieja no se
tradujera inventando. El capítulo 20 prohibió a la purga del historial borrar la instantánea
de entrada, que es justo la fila que ese extractor necesita.

Toda esa maquinaria estaba **vacía por un extremo**. La etiqueta salía de una sola cosa: el
estado del prospecto. Alguien elegía «Ganado» en el selector de etapa de la ficha, guardaba,
y el sistema pasaba a saber exactamente una cosa más sobre ese trato: que había acabado
bien. No sabía por qué, no sabía cuándo —`updated_at` es la última vez que alguien tocó la
ficha por cualquier motivo— y no sabía de qué tamaño.

Las consecuencias eran dos, y la segunda es la grave:

* **Para el negocio.** El sistema podía decir *cuántos* se ganaban y era incapaz de decir
  *qué se pierde por precio y qué se pierde por plazo*. De esas dos preguntas, solo la
  segunda cambia lo que alguien hace mañana.
* **Para el modelo.** Cada uno de esos cierres es una **etiqueta de entrenamiento**. Una
  etiqueta sin nada que la explique no se puede interpretar seis meses después: el día que
  una métrica sorprenda, la primera pregunta será de dónde salieron las etiquetas, y la
  respuesta habría sido «alguien cambió un selector, no consta quién ni por qué».

Este capítulo cierra ese extremo. Pasar un prospecto a ganado o perdido deja de ser una
opción de un desplegable y pasa a exigir tres datos de listas cerradas, sin una sola línea
de texto libre.

---

## 30.2. Qué se pregunta al cerrar, y por qué esas tres cosas

| Dato | Forma | Por qué |
| :--- | :--- | :--- |
| **Cómo acabó** | `ganado` / `perdido` | Es la etiqueta. Lo único que ya existía. |
| **Por qué** | clave de una lista cerrada, distinta para cada desenlace | Es lo que convierte «se perdió» en algo sobre lo que se puede hacer algo. |
| **Qué día se cerró** | una fecha, no la de hoy | Un trato firmado el viernes y anotado el lunes tiene que contar en su semana. |
| **De qué tamaño** | un tramo, solo si se ganó | Permite ver si los ganados por recomendación son los de arriba. Sin inventar cifras. |

Las listas viven en un solo sitio, `backend/app/core/desenlaces.py`, y el servidor las sirve
por `GET /api/v1/desenlaces/opciones`. El formulario **no** las lleva escritas: cuando el
cliente llevaba sus propias listas —como pasó con «¿Qué necesitas?» hasta el capítulo 26—,
añadir una opción exigía tocar dos sitios, y olvidarse de uno no rompía nada; la opción
simplemente dejaba de existir para quien leyera el informe.

**Motivos de un ganado:** precio, plazo, perfil, recomendación, acompañamiento, otro.
**Motivos de un perdido:** precio, plazo, perfil, no era el momento, eligió a otro, dejó de
contestar, sin presupuesto, lo resolvió por dentro, otro.

Tres claves —`precio`, `plazo`, `perfil`— son **las mismas** en las dos listas, y eso es
deliberado: son el mismo eje. Compartirlas es lo que permite poner las dos columnas una al
lado de la otra —«doce ganados por precio, treinta perdidos por precio»— y esa comparación
es la que dice algo. Con dos claves distintas para lo mismo habría sido imposible de cruzar.

---

## 30.3. Por qué una lista cerrada y no un campo de notas

Un cuadro de texto es lo más fácil de programar y lo único que después no se puede contar.
«Precio», «muy caro», «presupuesto» y «no le cuadraba el costo» son cuatro filas distintas
en cualquier agrupación y el mismo motivo para cualquier persona. Con treinta cierres, el
panel enseñaría veintiocho motivos de uno.

Hay además una razón que no es de comodidad. Un texto libre **sobre una persona** acaba
llevando datos de esa persona —su nombre, el de su jefe, lo que dijo por teléfono— a una
tabla que viaja a los respaldos, a la exportación del titular y, el día que se reentrene, a
un CSV. Este proyecto lleva desde el capítulo 21 quitando texto libre de donde no hace
falta: de los mensajes se guarda el tipo y la dirección, nunca el contenido. Reintroducirlo
justo en el registro que existe para alimentar al modelo habría sido raro.

### «Otro motivo» está en las dos listas, y no abre un cuadro de texto

Una lista cerrada sin salida no produce datos limpios: produce datos **falsos**. Quien no
encuentra su caso elige el más parecido, y a partir de ahí «precio» significa «precio o
cualquier otra cosa». Con una salida explícita, lo que no encaja se ve, y el panel lo cuenta
aparte: **si «otro» crece, la lista está mal y hay que discutirla**, que es exactamente la
conversación que un cuadro de texto libre impide tener.

Lo que se gana con «otro» es saber cuántas veces la lista no sirvió, no una explicación caso
por caso. Por eso no abre un campo donde escribir.

---

## 30.4. Por qué el tamaño va por tramos

Una cifra exacta necesita moneda, impuestos, duración del contrato y una definición de qué
cuenta como «el acuerdo» para significar algo. Sin todo eso es un número que alguien escribió
de memoria y que después se suma como si fuera contabilidad. Un tramo es algo que una persona
puede contestar con honestidad el día del cierre.

Los tramos son cuatro, en pesos, más uno: **«Todavía no consta»**. Existe por el mismo
motivo que los ingresos anuales dejaron de ser cero en el capítulo 24: obligar a elegir un
tramo cuando todavía no se sabe fabricaría exactamente la cifra que este diseño evita.

Y el límite del capítulo, dicho en el código y aquí: **de esto no sale ninguna previsión de
ingresos**. El tramo está para poder mirar de dónde salen los tratos grandes, no para
multiplicarlo por una tasa de conversión y enseñar un pronóstico.

### Lo que el motivo NO es

El motivo **no pesa**. Ninguno vale más que otro, ninguno suma ni resta score, y ninguno
entra al modelo como variable. Es una etiqueta para leer el panel. Inventar que «eligió a
otro» vale el doble que «no era el momento» habría sido justo la clase de número que este
proyecto lleva veinticuatro capítulos quitando.

Tampoco entra en el dataset como *feature*, y la razón es de fondo: el motivo se conoce **al
cerrar**, y el modelo tiene que servir el día que hay que decidir a quién llamar, que es
mucho antes. Viaja en el CSV como columna de contexto, fuera de `COLUMNAS_DEL_MODELO` y
fuera de la huella del dataset, para poder segmentar un análisis después.

---

## 30.5. La tabla `desenlaces`, y lo que copia

Una fila por prospecto (`uq_desenlaces_lead`). No cuatro columnas en `leads`: `leads`
describe a una persona y su situación **actual** —su teléfono, su empresa, su score, su
etapa—, y el desenlace es un hecho fechado que ocurrió una vez y no cambia porque la ficha
cambie. Separarlo tiene tres consecuencias prácticas: las fichas en curso no arrastran
cuatro columnas vacías; la exportación y la supresión del titular lo recogen por el mismo
camino que todo lo demás que cuelga de `leads`; y el extractor puede preguntar «¿cuáles
están cerrados con motivo?» con un `JOIN` en vez de recorrer la cartera entera.

Dos cosas se **copian** en el momento del cierre, y las dos por el mismo motivo:

* **`score_al_cierre` y `categoria_al_cierre`.** El score se mueve con cada actividad y con
  cada recálculo masivo. Preguntado seis meses después diría lo que el prospecto vale hoy
  —cerrado y sin que ninguna regla lo toque—, no lo que valía el día en que se decidió. La
  pregunta del panel es «¿el score acertaba?», y solo se puede responder con el valor que
  había al decidir.
* **`version_del_vector`.** Se copia de la instantánea de entrada, no de la constante de
  hoy. Es lo que permite que una instantánea de la versión 1 siga diciendo que lo es cuando
  la vigente sea la 3, y que el extractor la descarte en lugar de traducirla inventando.

`score_history_id` ata el desenlace a la instantánea que etiqueta, con `SET NULL`: si algún
día esa fila desapareciera, el desenlace tiene que seguir existiendo —sigue siendo cierto— y
el contador dejará de considerarlo utilizable, que es la verdad.

**Corregir un cierre reescribe la fila.** Guardar el historial de correcciones sonaba más
completo y habría obligado a decidir cuál de las filas es «el» desenlace cada vez que el
panel o el extractor preguntan, que es la clase de ambigüedad que produce dos números
distintos para la misma pregunta. Quién corrigió qué y cuándo ya queda en la bitácora.

---

## 30.6. Una sola puerta

`PUT /api/v1/leads/{id}` con `status` en `WON` o `LOST` responde **422** y no mueve nada. El
mensaje dice adónde ir: `POST /api/v1/leads/{id}/desenlace`.

Es el mismo razonamiento que llevó el alcance de cartera al repositorio en el capítulo 15 y
las reglas a un barrido en el 28: *una obligación que se comprueba en cuatro sitios es una
obligación que el quinto camino se salta sin que nadie reciba un error*. Y la comprobación
está en el endpoint, no en la pantalla: una pantalla que esconde el botón deja el camino
abierto para cualquiera que llame a la API.

La guarda mira la etapa que **llega**, no la que el prospecto tiene. Si mirara la suya, un
cliente ganado quedaría congelado y no se le podría corregir ni el teléfono.

**Quién cierra: quien atiende.** El permiso es el mismo que editar la ficha. Reservarlo al
líder habría convertido el cierre en un trámite que se pide por chat y se hace el viernes de
todos a la vez, y los motivos de un cierre los sabe quien estuvo en la conversación.

### Lo que el cierre hace, en una transacción

1. mueve la etapa a `WON` o `LOST` y **quita la marca de dormido** —un prospecto cerrado no
   está dormido: la marca dice «nadie lo toca» y a partir de ahora nadie debe tocarlo—;
2. guarda el desenlace con su motivo, su fecha y su tramo;
3. copia el score y la categoría del momento;
4. ata el desenlace a la instantánea de entrada con su versión;
5. **descarta** las tareas abiertas de ese prospecto.

### Lo que el cierre NO hace

**No recalcula el score.** Sería lo natural —cualquier otro cambio de la ficha lo hace— y
aquí está mal: recalcular en ese instante sobrescribiría, con un número que ya incorpora el
desenlace, justo el valor que el panel pregunta. **No reentrena nada**, no escribe en el
registro de modelos y no toca el artefacto.

Deja asiento con actor, a diferencia de lo que cierra el sistema solo. Se anota el motivo
—una clave— y nunca el nombre ni la empresa de nadie.

---

## 30.7. Lo cerrado sale del trabajo

Un prospecto cerrado no recibe más tareas ni más avisos. Hay **dos** defensas, y cada una
cubre lo que la otra no:

* **el filtro está en la consulta de cada regla** (`motor_de_reglas.en_seguimiento`). No
  solo en la bandeja: filtrar al pintar habría dejado el motor creando cada madrugada tareas
  invisibles sobre tratos cerrados, ocupando el índice único para siempre y reapareciendo
  todas con la fecha equivocada el día que alguien reabriera un prospecto;
* **el descarte es inmediato**, en la misma transacción del cierre. La barata —filtrar al
  leer— no limpia; la que limpia no cubre lo que no pasó por ahí.

`UNQUALIFIED` entra en el filtro de las reglas y **no** en las etapas que exigen desenlace.
Nadie debe recibir la tarea de llamar a alguien a quien ya se descartó, pero descartar no es
cerrar un trato: no tiene lista de motivos propia, y exigirle uno obligaría a inventar el de
todos los descartes anteriores a que la lista existiera. El extractor lo sigue contando como
negativo, como desde el capítulo 18.

### Un tercer estado de tarea: `descartada`

No es `hecha` —nadie la hizo— ni `cumplida` —no ocurrió lo que la tarea esperaba—. El trato
terminó y el trabajo dejó de tener sentido, que es una tercera cosa. Juntarla con «hecha»
habría inflado con los tratos que se cerraron solos la primera métrica de cumplimiento que
alguien calcule. Caduca con el mismo plazo que las demás cerradas.

La campana lleva el mismo filtro, y su contador de «sin leer» **el mismo que la lista**: que
el número dijera tres y la campana enseñara uno es exactamente el defecto que costó un
capítulo corregir en el contador de prospectos sin asesor.

---

## 30.8. El panel de desenlaces

`GET /api/v1/desenlaces/panel`, de dirección —como la comparativa de publicaciones y por la
misma razón: los cierres de un solo asesor comparados entre publicaciones dan un orden que
no es el real—. Cinco agrupaciones y un contador:

| Agrupación | Responde a |
| :--- | :--- |
| **Por motivo** | De lo que perdemos, cuánto se va por precio. |
| **Por categoría al cerrarse** | ¿El score acertaba? |
| **Por publicación** | De dónde salen los tratos que se ganan. |
| **Por red** | Por dónde llegaron. |
| **Por tramo** | El tamaño de lo ganado. Sin previsión de ingresos. |

**Ni una fila lleva a una persona.** Todo son totales. Quien necesita ver a las personas
tiene el listado y la ficha, donde ese acceso queda registrado como lo que es.

Tres decisiones sostienen los números:

* **Cada tasa viaja con su base.** Con doce cierres, cualquier conclusión sobre la calidad
  del modelo es una anécdota con decimales, y la columna de casos es lo que impide leerla
  como otra cosa. Sin base no hay tasa: se devuelve `—`, no un 0 %, porque «ninguno de cero»
  y «ninguno de cuarenta» no son lo mismo.
* **El porcentaje por motivo es sobre su propio desenlace.** La pregunta es «de lo que
  perdemos, cuánto se va por precio»; dividir entre ganados y perdidos juntos daría un número
  que no responde a nada.
* **Cada cierre cuenta una sola vez por publicación**, en la de su **primera** solicitud. El
  informe de una publicación cuenta al revés —allí cada post ve a todo el que le respondió, y
  allí es correcto— porque responde a otra pregunta. Lo que no podía ser es que las dos
  respuestas se llamaran igual: aquí, si un cierre contara dos veces, las filas no sumarían
  el total y el panel tendría dos números distintos para lo mismo.

La tabla de «¿acertaba el score?» enseña **las tres categorías, aunque alguna esté vacía**,
al revés que la de motivos. No es una incoherencia: la pregunta es si los HOT se ganan más
que los COLD, y una tabla a la que le falta la fila de los COLD invita a leer precisamente la
comparación que no se puede hacer. En los motivos, en cambio, nueve filas a cero enseñan la
lista y no los datos.

---

## 30.9. El contador del reentrenamiento, y su aviso

Un contador, **no un botón**. Este capítulo no reentrena: no toca el artefacto, no escribe
en el registro de modelos y no genera el CSV. Lo único que hace es dejar de ser imposible
saber cuánto falta.

Cuenta los cierres **utilizables**: los que tienen instantánea de entrada de la versión
vigente del vector **y completa**. Los mínimos —200 ejemplos, 50 por clase— viven en
`app/core/desenlaces.py` y el extractor del pipeline los **importa** desde ahí. No es una
elegancia: con dos copias del número, el día que alguien subiera una, el panel diría «ya se
puede reentrenar» mientras el extractor se niega.

El criterio de «utilizable» también es uno solo: `vector_del_modelo.instantanea_utilizable`,
que consumen el contador y el extractor. Este detalle lo encontró la guarda del CI, no una
prueba: la primera versión del contador miraba solo la columna `version_del_vector` copiada
al cerrar, y una instantánea puede declarar la versión vigente y estar **incompleta** —una
fila escrita a mano, una migración a medias—. El contador prometía un ejemplo y el extractor
traía cero.

El contador **no se filtra por fechas**, a diferencia del resto del panel: filtrar un
trimestre responde «cómo fue este trimestre», y el modelo se entrenaría con todo lo que hay.

### El aviso

Una regla más del motor (`desenlaces_suficientes`), que corre en la misma pasada diaria y
avisa a los líderes cuando se alcanza el mínimo. Es la única regla que no habla de un
prospecto sino del conjunto.

Avisa **una vez**, y eso lo consigue la clave, que son los mínimos exigidos y no la cuenta
del día: con la cuenta, cada cierre nuevo dispararía otro aviso a partir del doscientos. El
aviso cuelga del **cierre que inclinó la balanza** —el que hizo número doscientos entre los
utilizables, por orden de registro— y no del último cerrado: un aviso necesita un prospecto
del que hablar, y el último cambia con cada cierre nuevo, de modo que la pasada de mañana
habría escrito otro aviso idéntico sobre otra persona. El texto lo dice explícitamente: *no
se ha reentrenado nada*.

---

## 30.10. El bucle, con la etiqueta leída y no deducida

`feedback_dataset.py` toma ahora la etiqueta de la tabla `desenlaces` cuando existe:
`converted` sale de `resultado`, y el CSV gana cuatro columnas de contexto —resultado,
motivo, etiqueta del motivo, fecha real de cierre y tramo— que **no** son variables del
modelo ni entran en la huella del dataset.

Los prospectos cerrados **antes** de que existiera el desenlace siguen entrando, con su
etiqueta deducida del estado, y el manifiesto los cuenta aparte
(`etiquetados_solo_por_su_estado`). Inventarles un motivo habría sido peor que no tenerlo: el
análisis por motivo describiría una respuesta que nadie dio. Mientras esa cifra sea grande,
el panel por motivo describe una minoría de los cierres, y el manifiesto lo dice.

El ensayo del bucle (`ml_pipeline/src/ensayo_del_bucle.py`, capítulo 18) siembra ahora
desenlaces en su cohorte desechable y comprueba tres cosas nuevas: que ninguna fila llega sin
motivo, que ninguna etiqueta discrepa de su desenlace y que el motivo no se coló entre las
variables del modelo. Sin eso, el camino nuevo podía romperse y el ensayo seguir pasando, que
es justo el silencio que ese guion existe para romper.

---

## 30.11. Migración, conservación y derechos del titular

**La migración (`c1d9f4b72a08`) no rellena nada.** Los prospectos que ya estén en `WON` o
`LOST` se quedan sin desenlace, y es lo correcto: el motivo de un cierre anterior a que la
lista existiera no está en ninguna parte, y escribir «otro motivo» en todos ellos llenaría el
panel de una respuesta que nadie dio. Lo mismo con la fecha: `updated_at` es la última vez
que alguien tocó la ficha, y usarla habría producido un panel por meses con fechas plausibles
y falsas, que es peor que un panel con menos filas.

**La reversión** quita la tabla. Se pierden los motivos, las fechas y los tramos; **no** se
pierde qué prospectos estaban ganados o perdidos, porque eso vive en `leads.status` y esta
migración no lo toca. Al revertir, el sistema vuelve a saber cuántos se ganaron y vuelve a no
saber por qué: exactamente el estado anterior a este capítulo.

**Conservación.** El desenlace no tiene plazo propio, y es una decisión y no un olvido: es un
hecho sobre el prospecto —como su score—, no trabajo nuestro que se acumule, y purgarlo por
antiguo destruiría los ejemplos de entrenamiento que el sistema tardó un ciclo comercial
entero en reunir. Vive y muere con la ficha, y la exportación del titular lo dice.

**Derechos del titular.** `desenlaces` entra en `TABLAS_DEL_PROSPECTO`: sale en la
exportación —con su sección propia— y se va con la supresión, por `CASCADE`. La prueba que
compara ese mapa con las claves foráneas reales del esquema lo habría exigido igualmente: una
tabla nueva que apunte a `leads` rompe la suite hasta que alguien decida qué hacer con ella.
La nota de «fuera de la base» se actualizó para decir que, desde este capítulo, lo que puede
haber salido a un CSV de entrenamiento incluye el motivo y la fecha del cierre.

---

## 30.12. Que nada de esto sea decorativo

Además de la suite, una guarda del CI —`scripts/guarda_de_los_desenlaces.py`— comprueba
**propiedades** y no casos, con paso propio en el CI. Falla, diciendo qué defensa se perdió,
si el sistema:

1. **cierra sin decir nada**: la edición de la ficha vuelve a aceptar «Ganado» o «Perdido», o
   el cierre admite un motivo que no está en la lista de su desenlace, un ganado sin tramo, un
   perdido con tramo, una fecha futura o una anterior al alta;
2. **abre la puerta al texto libre**: el esquema del cierre gana un campo, o el cliente
   escribe su propia copia de las listas;
3. **reentrena por su cuenta**: el camino del cierre toca el artefacto, el registro o una
   biblioteca de entrenamiento —y las huellas de los dos archivos se comparan antes y después
   de cerrar y de abrir el panel—;
4. **mueve el score al cerrar**;
5. **sigue mandando trabajo sobre lo cerrado**: la pasada del día siguiente crea tareas, o la
   bandeja enseña una tarea abierta sobre un prospecto cerrado por otro camino;
6. **promete ejemplos que no existen**: el contador y el extractor dejan de contar lo mismo o
   de exigir los mismos mínimos;
7. **convierte el panel en un directorio**: vuelve el correo, el teléfono o la empresa, o la
   vista de dirección se abre a un asesor;
8. **se salta los derechos del titular**: el desenlace deja de exportarse o de borrarse.

Por qué además de la suite: `test_desenlaces.py` comprueba casos. Un campo `comentario` nuevo
en el esquema del cierre no rompe ninguna prueba existente —nadie lo envía— y aquí falla en
cuanto existe.

Y sobre la guarda, el arnés de siempre: **18 defectos reintroducidos** uno a uno, cada uno
con la comprobación que debía atraparlo, restaurando el árbol y verificando el hash de cada
archivo. Los 18 se detectan. Dos de ellos merecen mención porque cambiaron el código y no
solo la guarda:

* «un ganado puede cerrarse sin tramo» **no** era un defecto al desactivar solo la primera
  comprobación: el tramo vacío sigue cayendo por la segunda. El defecto real —quitar la rama
  entera— sí se detecta;
* los mínimos del reentrenamiento **ya no se pueden desincronizar** desde el núcleo, porque
  el extractor los importa. El defecto que queda es volver a escribirlos a mano allí, y es el
  que la guarda atrapa.

---

## 30.13. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Backend | **1326 pruebas** (39 de este capítulo), 93 % de cobertura; los cuatro módulos nuevos entre el 98 % y el 100 % |
| Cliente | **350 pruebas** en 25 ficheros; suelos de cobertura del cliente superados (94,5 / 86,3 / 97,3 / 97,4) |
| `ruff` y `eslint` | Sin avisos, sobre todo el repositorio y todo el cliente |
| Guarda del desenlace | Ocho comprobaciones; pasa |
| Reintroducción de defectos | **18 de 18** detectados; todos los ficheros restaurados con el hash verificado |
| Guarda del motor de reglas | Sigue pasando sus ocho comprobaciones con el filtro nuevo dentro |
| Migración | Ida y vuelta con Alembic de verdad; sin deriva contra los modelos |
| Ensayo del bucle | 60 cerrados y 20 en curso: 60 filas, todas con motivo, ninguna con la etiqueta cambiada |

---

## 30.14. Lo que este capítulo no hizo

* **No se reentrena el modelo.** Ni aquí ni en ninguna parte de este capítulo. El contador
  dice cuánto falta; quien decide es una persona, y el artefacto que sirve en producción es
  el mismo antes y después, comprobado por huella.
* **No se inventa el peso de los motivos.** Ninguno suma, resta ni entra al modelo. Si algún
  día se quiere saber si el motivo predice algo, eso es un análisis sobre los datos ya
  recogidos, no una constante escrita a ojo.
* **Ninguna previsión de ingresos.** El tramo agrupa lo ganado y no se multiplica por nada.
* **El panel no concluye nada sobre la calidad del modelo.** Enseña la tabla y el número de
  casos; con los cierres que habrá el primer trimestre, cualquier lectura de esas tasas es
  una anécdota, y el capítulo prefiere decirlo a redondearlo.
* **Los cierres anteriores siguen sin motivo.** La migración no los rellena, el panel no los
  cuenta y el manifiesto del dataset dice cuántos son. Es la merma que cuesta no inventar.
* **El guion de demostración todavía no recorre el cierre.** El capítulo 29 dejó el guion y
  sus hojas de observación puestos al día hasta la bandeja «Hoy»; cerrar un prospecto con su
  motivo es un paso más que nadie ha ensayado con una persona delante. Queda anotado, no dado
  por hecho.
* **Nadie ha rellenado este formulario varias veces seguidas.** Si nueve motivos de pérdida
  son demasiados o se quedan cortos —y sobre todo, cuánto crece «Otro motivo»— es justo lo
  que solo se sabe usándolo. El panel cuenta «otro» aparte precisamente para poder tener esa
  conversación con datos.
* **Reabrir un prospecto cerrado no es una operación del sistema.** Corregir un cierre
  equivocado sí: se vuelve a cerrar y la fila se reescribe. Devolver un trato a «En
  negociación» exigiría decidir qué pasa con su desenlace, y esa decisión no se ha tomado.
