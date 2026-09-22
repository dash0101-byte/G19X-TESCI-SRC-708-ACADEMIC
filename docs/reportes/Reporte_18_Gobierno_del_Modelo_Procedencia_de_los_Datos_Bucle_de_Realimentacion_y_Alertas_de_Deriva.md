# Capítulo 18: Gobierno del Modelo — Procedencia de los Datos, Bucle de Realimentación y Alertas de Deriva

## 18.1. Por qué existe esta fase

Las tres piezas que aborda este capítulo estaban escritas desde hace varias fases. El
registro de modelos, el extractor de desenlaces comerciales y el monitor de deriva
existían, tenían pruebas, aparecían en el README y se citaban en la memoria.

Ninguna de las tres hacía lo que decía.

* El registro guardaba un campo `huella_datos_sha256` que valía `null` en **todas** las
  entradas, porque el parámetro era opcional y `train_model.py` llamaba sin él.
* El extractor producía un dataset etiquetado que **ningún camino de código entrenaba**.
* El monitor calculaba PSI correctamente y no avisaba a nadie, porque nadie lo ejecutaba:
  se documentaba como orden manual.

Es una variante del error que recorre este proyecto entero y que las fases anteriores ya
encontraron cuatro veces en las guardas de integración continua —el comentario que
documenta el arreglo satisface la comprobación del arreglo, la guarda que encuentra la
línea del `import` en vez del uso, la que se conforma con «aparece alguna vez», la que
encuentra su propio patrón en su propia línea `grep`—. Aquí aparece en su forma de
**esquema y de proceso**: un campo previsto vale por el dato que no contiene, y un guion
disponible vale por la vigilancia que nadie ejerce.

Las tres tienen algo en común que las hace peores que una ausencia: el sistema **aparenta**
tener trazabilidad, bucle de mejora y monitorización. Quien lee el README lo cree. Quien
audita el repositorio encuentra los módulos. El hueco solo se nota el día que hace falta,
y ese día es siempre el peor.

---

## 18.2. N-15 — Un campo previsto no es un dato

### El estado de partida

`registrar_modelo` aceptaba la huella del conjunto de entrenamiento como parámetro
opcional:

```python
def registrar_modelo(metricas, filas_entrenamiento, columnas,
                     huella_datos=None, ruta=None):
    ...
    "huella_datos_sha256": huella_datos,
    "origen_de_los_datos": "sinteticos" if huella_datos is None else "realimentacion",
```

Y el único llamador del proyecto pasaba tres argumentos:

```python
entrada = registrar_modelo(
    metricas=metrics,
    filas_entrenamiento=int(len(X_train)),
    columnas=list(feature_cols),
)
```

El resultado, en la única entrada que el registro tenía antes de esta fase:

```json
"huella_datos_sha256": null,
"origen_de_los_datos": "sinteticos"
```

La guarda que el pipeline ya dedicaba a esto comprobaba que la huella **del artefacto**
apareciera en el registro. Eso pasaba. Lo que faltaba era el otro extremo del vínculo: con
qué datos. La pregunta que N-15 planteaba —*«¿con qué se entrenó el modelo que puntuó a
este prospecto en marzo?»*— seguía sin respuesta, con el agravante de parecer contestada.

### Tres decisiones

**La huella es obligatoria.** `registrar_modelo` levanta `ProcedenciaIncompleta` si no la
recibe. Un modelo que no se puede rastrear hasta sus datos no llega a registrarse, igual
que un modelo que no supera el umbral no llega a escribirse en disco. Un aviso lo leería
quien ya sabe que hay que mirar.

**El origen se declara, no se deduce.** Esta es la parte que no era evidente. La regla
`"sinteticos" if huella_datos is None else "realimentacion"` era inofensiva mientras la
huella no se pasaba nunca, y se vuelve **falsa exactamente al arreglar lo anterior**: con
huella obligatoria, todo entrenamiento —incluido el sintético de CI— habría quedado
anotado como «realimentacion», y el registro afirmaría que el modelo desplegado se entrenó
con desenlaces de clientes reales. Una deducción que rellena un hueco deja de ser
inofensiva justo cuando el hueco se llena.

**La huella tiene que poder recalcularla un tercero.** Se serializa en forma canónica
—columnas ordenadas, filas ordenadas— por dos razones distintas:

* Dos extracciones de los mismos desenlaces llegan en distinto orden; la base no garantiza
  ninguno sin `ORDER BY`. Si eso cambiara la huella, cada ejecución daría una distinta y el
  campo solo diría «se entrenó alguna vez».
* Es lo que permite que el pipeline la **recompute desde el CSV** y la contraste. Exigir
  solo que no sea `null` no basta: una constante también cumple.

Y se acota a las columnas que de verdad entran al modelo. `lead_id` y las marcas de tiempo
viajan en el dataset y no entran; incluirlas haría que dos extracciones de los mismos
desenlaces, hechas con un día de diferencia, parecieran conjuntos distintos.

### Verificado

```
huella registrada : cd42cf4f04961d23828b0dde0d42b8b8d898a3bb80c4aab55d9cdb6e6328a410
origen            : sinteticos
recalculada desde el CSV por un tercero: cd42cf4f...6328a410
COINCIDE: True

¿con qué datos se entrenó el .joblib desplegado?
  -> sinteticos cd42cf4f04961d23 | filas: 2400
```

Se añadió también `entrada_de_artefacto`, porque `artefacto_registrado` responde sí o no y
la pregunta de N-15 es otra: saber que un `.joblib` tiene procedencia no es lo mismo que
poder consultarla, y ante una puntuación rara de hace tres meses lo que hace falta es la
segunda.

---

## 18.3. El bucle de realimentación no tiene datos, y eso es un dato

El objetivo del punto 22 era exportar los `WON`/`LOST` como dataset etiquetado real y
reentrenar contra él «aunque el volumen sea pequeño». Al ejecutar el extractor contra la
base de desarrollo:

```
[REALIMENTACION] Ningun desenlace utilizable todavia: 12 prospectos siguen en curso y
                 0 cerrados no tienen instantanea aprovechable.
```

El volumen no es pequeño: **es cero**. No hay ningún prospecto en estado terminal. Decirlo
es parte del trabajo; construir un dataset a partir de nada y presentar sus métricas como
«empezamos a medir de verdad» sería exactamente el engaño contra el que avisa el docstring
del propio módulo.

Ejecutar el extractor destapó, de paso, dos defectos reales.

### `--sin-minimos` reventaba con una traza de pandas

Es la opción a la que se recurre el primer día, para mirar qué hay. Con cero desenlaces:

```
KeyError: "None of [Index(['job_title', 'industry', ...])] are in the [columns]"
```

Escribía un CSV vacío y después indexaba columnas que un `DataFrame` vacío no tiene. La
respuesta correcta —«todavía no ha cerrado ningún prospecto»— llegaba como un fallo del
programa. Ahora se informa y **no se escribe nada**: un CSV vacío se entrena igual de mal
que uno malo, y además sin avisar.

### «No hay cierres» y «esta no es la base» se veían igual

`DATABASE_URL` por defecto es relativa —`sqlite:///./lead_scoring.db`—, así que ejecutar
el extractor desde otro directorio **crea una base vacía** en lugar de fallar. Ocurrió
durante esta misma fase: quedó un archivo de cero bytes en la raíz del repositorio, que se
borró de inmediato porque en este proyecto la base no vive en el árbol de trabajo. El
informe resultante —cero desenlaces, cero en curso— parecía un diagnóstico del negocio
cuando era un error de ruta. El manifiesto lleva ahora `base_sin_prospectos`, y el mensaje
distingue los dos casos.

---

## 18.4. El ensayo del bucle: entrenar lo que no puede entrenarse todavía

Un camino de código que no se ejecuta hasta dentro de un ciclo comercial completo no llega
vivo a ese día. Cuando cierre el primer prospecto, alguien correrá el extractor y se
encontrará con lo que se encuentra siempre: una firma que cambió, una columna que se
renombró, un `import` que dejó de resolver. Y lo encontrará justo cuando por fin hay datos
y ganas de mirarlos.

`ensayo_del_bucle.py` levanta una base **temporal y desechable**, siembra una cohorte
cerrada con instantáneas de entrada coherentes y recorre el bucle entero: extracción,
manifiesto, huella, entrenamiento y registro. Las variables y su etiqueta salen del
generador sintético del proyecto y no de números al azar: contra ruido puro el ROC-AUC
saldría en 0.5 y el ensayo no distinguiría un bucle sano de uno que perdió el vector de
variables por el camino.

### Lo que enseñan dos tamaños de cohorte

| Cohorte cerrada | Conjunto de prueba | ROC-AUC | IC 95 % | ¿Supera el umbral de 0.82? |
| ---: | ---: | ---: | :--- | :--- |
| 45 | 9 | 0.8889 | **[0.571, 1.000]** | sí |
| 60 | 12 | 0.8125 | **[0.355, 1.000]** | no |
| 260 | 52 | 0.8917 | **[0.800, 0.968]** | sí |

Las dos primeras filas son la misma cohorte con quince prospectos más, y el veredicto de la
puerta se invierte. Sus intervalos de confianza se solapan casi por completo: la diferencia
entre «cumple» y «no cumple» no está en el modelo, está en qué doce ejemplos cayeron del
lado del conjunto de prueba.

Con la cohorte de 45, además, el aporte de +0.1111 sobre el heurístico es literalmente **un
ejemplo cambiando de lado**.

Los dos umbrales que protegen el camino sintético —ROC-AUC ≥ 0.82 y aporte ≥ 0.01— se
superan holgadamente en el primer caso y se incumplen en el segundo. **No protegen el
camino real, en ninguna de las dos direcciones.** No porque estén mal calibrados, sino
porque miden una estimación puntual, y el problema del primer dataset de realimentación no
es el valor: es la incertidumbre. Es también la razón por la que el ensayo de integración
continua no exige que el modelo pase la puerta: comprueba que el camino funciona, y con
doce ejemplos de prueba el resultado de la puerta es una moneda.

De ahí las dos decisiones del diseño:

* **El intervalo de confianza se calcula siempre**, por remuestreo con reemplazo, también
  con datos sintéticos. Un intervalo que solo aparece cuando el resultado es incómodo se
  lee como excusa.
* **Medir y publicar están separados.** `--datos realimentacion` mide; publicar exige
  `--publicar`. Si el mismo comando hiciera las dos cosas, ese modelo de 36 filas de
  entrenamiento llegaría a producción por el camino normal, sin que nadie decidiera nada.

---

## 18.5. Un ensayo que ensuciaba justo lo que la fase venía a arreglar

La primera versión del ensayo funcionó a la primera y dejó esto en el registro **de
producción**:

```json
{
  "registrado_en": "2026-09-10T20:24:26...",
  "origen_de_los_datos": "realimentacion",
  "filas_entrenamiento": 36,
  "publicado": false
}
```

Una entrada indistinguible de un entrenamiento real contra desenlaces de clientes. Las
etiquetas eran inventadas y la base había sido borrada al terminar.

`publicar=False` protegía el artefacto y el perfil de referencia, y **no el registro**. Que
es precisamente donde vive la respuesta a «¿con qué datos se entrenó esto?» que N-15 vino a
arreglar: un ensayo que ensucia la procedencia hace daño en el mismo sitio que el defecto
que corrige.

`entrenar()` recibe ahora `directorio_modelos`, y todo lo que el ensayo escribe muere con
su directorio temporal. Hay una prueba dedicada a ello, porque el fallo no era del ensayo
sino del reparto de responsabilidades: cualquier otro llamador habría tropezado igual.

Vale la pena decir cómo apareció: no leyendo el código, sino mirando `registry.json`
después de una ejecución que había terminado bien.

---

## 18.6. El archivo con datos de clientes que nadie había puesto en `.gitignore`

Apareció al final, mirando el árbol de trabajo después de todo lo demás.

`ml_pipeline/data/` contiene `leads_historical.csv`, que es sintético y **se versiona a
propósito**: es el conjunto con el que CI entrena y la referencia que permite recalcular la
huella. El bucle de realimentación deja su salida en ese mismo directorio, con el nombre de
al lado: `leads_reales.csv`.

Y ese archivo es lo contrario. Cargo, sector, facturación, número de llamadas y mensajes,
días desde la última actividad —y el `lead_id`— de prospectos concretos que cerraron o se
perdieron. Es el único archivo del proyecto con datos de clientes.

No estaba en `.gitignore`. Nadie lo había cometido porque hasta esta fase no existía; el
descuido estaba preparado, esperando a la primera exportación. Y la vecindad con el
sintético es justo lo que lo hace probable: dos CSV en la misma carpeta, uno de los cuales
sí debe versionarse.

Se cierran las dos mitades, con la lección que dejó `frontend/dist` en la fase anterior:
que la regla esté, y que **nadie la haya anulado con una negación posterior** —que deja la
regla intacta y la desactiva igual—. Y una tercera que aquellas no tenían: consultar el
índice de Git, porque es lo único que atrapa un `git add -f`.

De paso se borró un `leads_reales.csv` de dos bytes que había dejado la primera ejecución,
la que reventaba con el `KeyError`. Un CSV vacío en la ruta por defecto de
`--datos realimentacion` es un accidente esperando: no habría fallado, habría entrenado con
nada.

---

## 18.7. N-23 — Una alerta que se calla

`drift_monitor.py` existía desde la fase 8 con su índice PSI, sus umbrales y sus dos
cautelas escritas. Lo que no tenía era quién lo ejecutara ni a quién avisar.

### Programado donde están los datos

El servicio `monitor-deriva` de la pila lo corre en bucle. Es un bucle en el propio proceso
y no `cron` porque la imagen del backend no lleva demonio de tareas, y añadirlo significaría
un proceso más que supervisar, un formato de registro distinto del resto del sistema y una
vía de ejecución que nadie mira.

Corre en la pila y **no en integración continua**, y la razón no tiene vuelta: lo que hay
que comparar contra el perfil de referencia son las instantáneas de variables que produjo
*esa* base al puntuar prospectos reales. CI no las tiene ni debe tenerlas. Un trabajo
programado en el pipeline daría la sensación de vigilancia sin ninguna.

### La mitad que importa es el silencio

La deriva de población dura semanas. Con el monitor evaluando cada seis horas, avisar en
cada ciclo produce decenas de mensajes idénticos sobre una condición que no ha cambiado.
Quien los recibe crea un filtro, y a partir de ese momento el sistema tiene monitorización
y no tiene aviso —peor que el punto de partida, porque además parece resuelto—. Es el mismo
razonamiento que llevó a apagar `react-hooks/set-state-in-effect` entera en la fase
anterior en vez de dejarla en aviso permanente.

Las reglas:

* Si deriva y antes no derivaba, se avisa.
* Si sigue derivando pero **cambió el conjunto de columnas**, se avisa: no es la misma
  condición aunque el veredicto se llame igual. Que a `source_channel` se le sume
  `industry` puede ser lo que convierta una campaña rara en un cambio de mercado.
* Si sigue derivando con las mismas columnas, se calla hasta que pase el periodo de
  silencio. Callar no es olvidar.
* Y **la vuelta a la normalidad se avisa una vez**. Sin eso, quien recibió la alerta no
  sabe nunca si la condición sigue viva y acaba abriendo el panel para averiguarlo, que es
  justo lo que la alerta venía a evitar.
* «Muestra insuficiente» no es una alerta. El PSI se infla con pocas observaciones y el
  monitor ya lo dice en el veredicto; convertirlo en aviso llenaría el canal los primeros
  días, que es cuando hay que ganarse que lo lean.

El estado vive en un **volumen** y no en `tmpfs`: en `tmpfs`, cada reinicio del contenedor
olvidaría que ya avisó. Y un estado corrupto no impide evaluar —perderlo cuesta, como
mucho, un aviso repetido; dejar de vigilar por no poder leer un JSON sería cambiar un ruido
por una ceguera—.

### Dos detalles de la entrega

Un webhook caído **no tumba el monitor** —la deriva sigue mereciendo evaluarse aunque el
receptor esté caído— pero **sí se dice**: una alerta que no llega y no dice que no llegó
deja al sistema aparentando vigilancia. Y la URL nunca se imprime: suele llevar un testigo
en la ruta, y un registro que la reproduce convierte el canal de avisos en una credencial
filtrada, precisamente en el momento en que esas líneas se leen, que es durante un
incidente.

---

## 18.8. Que nada de esto sea decorativo

### Las pruebas

Se reintrodujeron **22 defectos**, uno a uno, corriendo la suite entera con cada uno
puesto: **21 hacen fallar alguna prueba**, con 32 fallos en total.

El vigesimosegundo merece explicarse, porque no es un hueco. Se quitó el retorno temprano
de `intervalo_bootstrap` cuando el conjunto tiene una sola clase, y no falló nada. La razón
es que un segundo resguardo sostiene el mismo contrato: sin dos clases, **todos** los
remuestreos se descartan, se queda por debajo del mínimo de réplicas válidas y devuelve
`None` igual. Comprobado ejecutando las dos versiones: ambas devuelven `None`. La inyección
no cambia el comportamiento observable, así que no era un defecto que ninguna prueba
pudiera detectar.

### Las guardas del pipeline

Cuatro guardas nuevas, **once reintroducciones, once disparos**, y las cuatro pasan sobre
el árbol correcto. Todas comprueban
comportamiento y no texto: la del registro *llama* a `registrar_modelo` sin huella y exige
la excepción, en vez de buscar la firma con `grep`. Una guarda que ejecuta la función no
puede satisfacerse a sí misma —que es como fallaron siete de las guardas de la fase
anterior—.

Y aun así, la verificación encontró dos fallos en las guardas nuevas, los dos de la misma
familia:

**La guarda del monitor usaba `jq`.** Los ejecutores de GitHub lo traen; esta máquina no.
Las cuatro reintroducciones «dispararon» —y las cuatro fallaban por `jq: command not
found`—. Cuatro guardas que parecían verificadas y no lo estaban.

**Después usaba `/tmp` como intermediario.** `docker compose config > /tmp/pila.json`
seguido de un Python que lee esa ruta funciona en el ejecutor y no en Git Bash sobre
Windows, donde no son el mismo sitio. Otra vez cuatro disparos por el motivo equivocado.

La lección es la misma en los dos casos y merece decirse aparte: **comprobar que una guarda
dispara no significa nada sin comprobar antes que pasa sobre el árbol correcto.** Un guion
roto dispara con todo. En ambos casos el clean tree salía en rojo, y era lo único que
distinguía una verificación de una ilusión.

Se resolvió quitando las dos dependencias: la guarda invoca a `docker compose` ella misma y
analiza la configuración **resuelta** —no el YAML, porque lo que importa es lo que arranca
`up` y un override puede cambiarlo— con `python3`, disponible tanto en el ejecutor como en
la máquina donde se escribe. Una guarda que no se puede ejecutar donde se escribe no se
puede comprobar.

### Y una reintroducción que reveló un hueco en el ensayo

Quitarle al extractor el filtro de estados terminales —el error clásico de estos bucles:
contar los prospectos en curso como perdidos, que sesga el modelo hacia el pesimismo justo
en los más activos— **no hacía fallar el ensayo**. El ensayo comprobaba que las señales
posteriores al desenlace no se colaran, y no cuántas filas salían. Ahora cuenta.

---

## 18.9. Lo que esta fase no hizo

* **El bucle de realimentación sigue sin datos reales.** Cero prospectos en estado terminal.
  Todo lo que se mide en §18.4 son etiquetas sintéticas sobre una base desechable: verifica
  que el camino funciona, no el rendimiento del modelo en el negocio. La frase «empezamos a
  medir de verdad» describe la instrumentación, no todavía la medición.
* **No hay deriva de rendimiento**, solo de variables de entrada. Lo primero necesita
  conversiones reales y tarda un ciclo comercial completo, igual que el bucle.
* **La alerta no tiene destinatario configurado.** `ML_DRIFT_WEBHOOK` está vacío por
  defecto, así que hoy el aviso vive en la salida del contenedor. Es donde vive todo el
  registro del sistema, y no es mal sitio, pero no despierta a nadie.
* **El perfil de referencia y el artefacto pueden desincronizarse.** Ambos viajan en la
  imagen y salen del mismo entrenamiento, pero nada lo comprueba en el arranque: un perfil
  de un entrenamiento con un modelo de otro compararía producción contra una referencia que
  no corresponde a lo que está puntuando. El registro ya tiene los datos para verificarlo.
  *Cerrado en el Capítulo 19 (§19.4).*
* **Los mínimos del extractor (200 ejemplos, 50 por clase) no están validados** contra nada
  empírico. Son juicio razonable, no una curva de aprendizaje medida.
* **`--publicar` no exige el intervalo de confianza.** Depende de que quien lo escriba haya
  mirado la tabla. Podría ser una condición del código y hoy es una convención.
  *Cerrado en el Capítulo 19 (§19.5).*
