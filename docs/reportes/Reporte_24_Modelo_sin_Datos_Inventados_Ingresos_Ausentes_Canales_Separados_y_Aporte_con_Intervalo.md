# Capítulo 24: Modelo sin Datos Inventados — Ingresos Ausentes, Canales Separados y Aporte con Intervalo

## 24.1. Por qué existe esta fase

El capítulo 21 dejó el registro de la actividad honesto: cada llamada con su resultado, cada
mensaje con su canal. Pero el modelo seguía entrenado con el vector de antes, y §21.12 lo
decía sin rodeos:

* **Los ingresos anuales se inventaban en la inferencia.** Cuando un prospecto no los
  declaraba, el adaptador pasaba 100 000 porque el preprocesador no sabía qué hacer con un
  hueco. El modelo leía una empresa pequeña donde solo faltaba un dato.
* **WhatsApp y LinkedIn eran una sola variable**, `whatsapp_messages`, hasta reentrenar.
* **Las llamadas sin respuesta se perdían.** Solo las conectadas llegaban al modelo.

Y §19.9 tenía otra deuda del mismo gate de publicación: **el aporte sobre el heurístico se
medía con una estimación puntual.** El intervalo se exigía para el ROC-AUC, no para la
diferencia, que es más inestable.

La fase cierra las cuatro sin cuentas externas. Lo que requiere desenlaces reales —la deriva
del rendimiento y la curva de aprendizaje de los mínimos del extractor— queda para cuando
los haya (§24.9).

---

## 24.2. Un solo vector, con versión

`backend/app/core/vector_del_modelo.py` es ahora la única definición de las variables del
modelo. Lo consumen el adaptador, el servicio de scoring, el preprocesador, el entrenamiento
y el extractor del dataset real. En ML-4 esas listas estaban escritas por separado y el
adaptador perdió cuatro señales sin que nada fallara; la suite las comparaba leyendo el
texto de los archivos con expresiones regulares. Ahora compara los objetos que se ejecutan:
la fila que construye el adaptador, las columnas que selecciona el preprocesador y las que
usa el entrenamiento.

| Variable (v1) | Variable (v2) | Qué mide |
| :--- | :--- | :--- |
| `annual_revenue` (100 000 si faltaba) | `annual_revenue` (ausente si falta) | Ingresos declarados; imputados con marca |
| `phone_calls` | `phone_calls_connected` | Llamadas con resultado `CONECTO` |
| — | `phone_calls_unanswered` | Llamadas con `NO_CONTESTO` o `BUZON` |
| `whatsapp_messages` (con LinkedIn) | `whatsapp_messages` | Solo WhatsApp |
| — | `linkedin_messages` | Solo LinkedIn |

Cada instantánea guarda `version_del_vector: 2`. Una de la versión 1 **no se puede
traducir** sin inventar: no dice qué mensajes eran de LinkedIn ni cuántas llamadas quedaron
sin respuesta. Por eso el extractor del dataset real y el monitor de deriva las descartan y
las cuentan (`terminales_con_instantanea_de_un_vector_anterior`,
`instantaneas_de_otro_vector`) en lugar de rellenarlas.

---

## 24.3. Los ingresos que faltan llegan como ausencia

### En el modelo

El preprocesador da a `annual_revenue` su propio tramo: `SimpleImputer(strategy="median",
add_indicator=True)` y después el escalado. La imputación sola no bastaba: un prospecto sin
ingresos sería indistinguible de uno que factura exactamente la mediana, y el modelo volvería
a leer una cifra donde hay un hueco, solo que más verosímil que 100 000. La columna
indicadora dice que faltaba.

El adaptador pasa `NaN`. Cero cuenta también como ausente (`ingresos_o_ausente`): ninguna
empresa a la que se vende este servicio factura cero, y en la base un cero era lo que
escribían los formularios cuando el campo llegaba vacío.

### Los otros sitios que los inventaban

Al buscar de dónde salían los ceros aparecieron cinco sitios más, todos con la misma forma:

| Dónde | Qué escribía | Ahora |
| :--- | :--- | :--- |
| Alta desde el panel (`NewLeadModal`) | **2 000 000 fijos**, sin campo en el formulario | `null` |
| Edición de la ficha (`LeadDetailModal`) | `parseFloat(valor) \|\| 0` y tamaño «11-50» si no había | `null` si está vacío; tamaño «Sin indicar» |
| Esquema de la API (`LeadBase`) | `0.0` por defecto | `None` |
| Ingesta de integraciones | `0.0` por defecto | `None` |
| Extractor del dataset real | `lead.annual_revenue or 0.0` y tamaño «1-10» | ausente y tamaño vacío, como al puntuar |

El último era además una incoherencia: se entrenaba con tamaño «1-10» y se puntuaba con
vacío, dos vectores distintos para el mismo prospecto.

### En el generador sintético

Los datos sintéticos ahora tienen ingresos ausentes, un **24.8 %** del conjunto. La ausencia
no es al azar: las empresas pequeñas y los contactos por correo en frío o búsqueda orgánica
la dejan en blanco más a menudo. Es una suposición sobre el negocio, no una medida, y la
etiqueta sigue sin depender de los ingresos. Sin ausentes en el entrenamiento el indicador
no existiría en el artefacto.

---

## 24.4. Canales y resultados de llamada

El servicio de scoring cuenta cuatro variables donde contaba dos. Una llamada sin resultado
—las anteriores a la Fase 15— no suma en ninguna: suponérselo sería inventarlo.

**La mitad heurística del score no cambia.** La regla sigue puntuando las conversaciones
—llamadas conectadas— y suma WhatsApp y LinkedIn bajo el mismo tope de 10 puntos. Separar las
variables del modelo no puede mover lo que la regla ya decía de cada prospecto, y una prueba
lo comprueba con varias combinaciones.

En el generador sintético cada llamada tiene resultado —conecta más a menudo si hay interés
previo— y cada mensaje su canal. Los intentos sin respuesta restan poco a la probabilidad
latente, WhatsApp suma más que LinkedIn. Como todo el generador, son supuestos: sirven para
que el pipeline tenga algo que aprender en cada variable, no describen el negocio.

---

## 24.5. El aporte sobre el heurístico, con intervalo (§19.9)

### El intervalo

`intervalo_bootstrap_del_aporte` calcula el IC 95 % de ROC-AUC(modelo) − ROC-AUC(heurístico)
por **bootstrap pareado**: en cada réplica se toman las mismas filas para los dos y se resta.
Remuestrear cada ROC-AUC por separado mediría dos incertidumbres como si fueran
independientes, y no lo son: se calculan sobre los mismos prospectos y fallan en los mismos
casos difíciles. Usa la misma semilla y el mismo criterio que el intervalo del ROC-AUC.

### El gate

`motivo_para_no_publicar` recibe `intervalo_aporte` como argumento **obligatorio y sin valor
por defecto**, y no publica si no hay intervalo o si su límite inferior no alcanza el aporte
mínimo (+0.01). Un gate que se pudiera llamar sin él volvería a decidir con la estimación
puntual sin que se notara.

### Lo que mide

| Cohorte (sintética, semilla 7) | Filas de prueba | ROC-AUC e IC 95 % | Aporte e IC 95 % | ¿Publica? |
| :--- | ---: | :--- | :--- | :--- |
| 400 | 80 | 0.976 [0.944, 0.996] | +0.007 [−0.024, +0.040] | No, aporte puntual |
| 800 | 160 | 0.911 [0.860, 0.951] | −0.018 [−0.059, +0.021] | No, aporte puntual |
| **1000** | 200 | 0.942 [0.910, 0.968] | **+0.028 [−0.002, +0.059]** | **No, por el intervalo del aporte** |
| 1500 | 300 | 0.955 [0.933, 0.975] | +0.049 [+0.019, +0.080] | Sí |
| Ensayo del bucle (60 cerrados) | 12 | — | +0.031 [−0.100, +0.222] | No, por el intervalo del aporte |
| **Publicado (3000)** | 600 | **0.947 [0.928, 0.964]** | **+0.052 [+0.030, +0.076]** | **Sí** |

La fila de 1000 es el caso que §19.9 temía: supera los dos umbrales puntuales y el límite
inferior del ROC-AUC, y antes se habría publicado; su aporte es compatible con un modelo que
no mejora la regla. Y el intervalo del aporte muerde **antes** que el del ROC-AUC, que en esa
cohorte queda holgado en 0.91.

La tabla dejó una consecuencia en la suite: las pruebas de publicación usaban una cohorte de
400 filas y daban por hecho que superaba los umbrales. Con el vector nuevo no los supera, y
pasaron a 1500.

---

## 24.6. El artefacto nuevo

| | Antes (`372d843e`) | Ahora (`98ed8bd1`) |
| :--- | :--- | :--- |
| Vector | 16 variables, sin versión | 18 variables, versión 2 |
| ROC-AUC (IC 95 %) | 0.9524 [0.935, 0.968] | 0.9469 [0.928, 0.964] |
| Heurístico ICP | 0.9110 | 0.8950 |
| Mejor regla trivial | 0.9136 (`days_since_last_activity`) | 0.9053 (la misma) |
| Aporte sobre el heurístico | +0.041, sin intervalo | +0.052 [+0.030, +0.076] |
| Ingresos ausentes en el entrenamiento | 0 % | 24.8 % |

Las cifras no son comparables como mejora o empeoramiento: el generador cambió y con él el
problema. Lo que cuenta es que el artefacto pasa el gate con los dos intervalos.

Se publicó por el camino normal (`python ml_pipeline/src/train_model.py`), que escribe
artefacto, métricas, perfil de referencia y entrada en el registro, en ese orden y solo si
pasa. El perfil lleva la huella del artefacto, la de los datos y `version_del_vector`; la
entrada del registro, los dos intervalos, la versión y las columnas. Huella para fijar en el
despliegue:

```
ML_MODEL_SHA256=98ed8bd179414ea724102600fffcc5db4adeb753e15161eea5c3df80e49d2a63
```

---

## 24.7. Que nada de esto sea decorativo

### Las pruebas

32 pruebas nuevas en `test_modelo_sin_datos_inventados.py`: ingresos ausentes o a cero en
el adaptador, la ficha y el alta; el artefacto y el preprocesador imputando con marca; un
artefacto de otro vector rechazado al cargar; llamadas sin resultado que no suman; la regla
heurística igual con los canales separados; instantáneas del vector 1 descartadas y contadas
por el extractor y por el monitor; el intervalo del aporte pareado, sensible y sin intervalo
con una sola clase; el gate con el intervalo del aporte obligatorio; un entrenamiento real de
1000 filas que no se publica por él, y lo publicado cumpliendo los dos intervalos.

Se adaptaron `test_ml_honesto.py` —las tres listas se comparan ejecutando, y las señales
comerciales nombradas pasan de cuatro a seis—, `test_registro_de_actividad.py` —el resultado
de la llamada y los dos canales—, `test_perfil_y_publicacion.py` y
`test_gobierno_del_modelo.py` —cohorte de 1500 e intervalo del aporte— y
`test_scoring_parity.py`. En el cliente, 8 pruebas nuevas de `ingresosDelFormulario`.

### Las guardas del pipeline

| Guarda (trabajo `modelo`) | Qué detecta |
| :--- | :--- |
| El modelo no recibe datos inventados (nueva) | el adaptador pasando una cifra por ingresos ausentes; la fila fuera del vector; el preprocesador sin indicador; el artefacto de otro vector o imputando sin marca; métricas o perfil sin versión; el servicio contando mal llamadas, canales o ingresos de un prospecto construido con actividades de cada clase |
| Publicar exige el intervalo de confianza (modificada) | el gate sin límite inferior del aporte, sin intervalo del aporte, con el intervalo omitible; `entrenar()` sin calcularlo o sin pasarlo; lo publicado sin cumplirlo |

Se comprueban ejecutando, no buscando texto: la guarda construye un prospecto con una llamada
de cada resultado, una sin resultado, un WhatsApp y dos LinkedIn, y compara lo que extrae el
servicio.

### Reintroducciones

Se reintrodujeron **16 defectos** con el arnés de los capítulos anteriores: copia cada
archivo, lo altera, exige que la prueba falle y, si hay guarda, que falle con `FALLO`, y lo
restaura. Sobre el árbol correcto pasan las dos.

| Pieza | Defectos reintroducidos |
| :--- | :--- |
| Ingresos | el adaptador pasando 100 000; el preprocesador sin indicador; la ficha pasando 0.0; el extractor rellenando; el esquema del alta con 0.0 por defecto |
| Llamadas y canales | LinkedIn sumando en WhatsApp; las sin respuesta perdidas; las sin resultado contadas como sin respuesta; la regla sin sumar LinkedIn |
| Versión del vector | la instantánea sin versión; el monitor comparando cualquier vector; el adaptador cargando un artefacto de otro vector |
| Aporte con intervalo | el gate sin límite inferior del aporte; el intervalo omitible; `entrenar()` pasando al gate el intervalo del ROC-AUC; el bootstrap sin parear |

**Resultado: pruebas 16 de 16 y guardas 11 de 11**, sin huecos. La primera ejecución se
detuvo en el defecto 15 por un fallo del propio arnés —su ancla aparecía dos veces en
`lead.py`, en el alta y en la edición— y no llegó a modificar el archivo; corregida el ancla,
se repitió.

Lo que sí dejó la fase fue un defecto encontrado **al escribir el reporte**, no por el arnés:
con el artefacto del vector 1 y el código del 2, `predict_proba` fallaría en cada petición y el
adaptador caería al cálculo de contingencia **anotando `ml:<huella>` como motor**. Ahora el
adaptador compara `feature_names_in_` con el vector vigente al cargar y, si no coinciden, no lo
usa y consta como `heuristico`. Tiene prueba, comprobación en la guarda y es el defecto 16.

---

## 24.8. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend | **849 pruebas**, 92 % de cobertura |
| Suite del cliente | **156 pruebas**, 94.9 % de cobertura; `eslint` sin avisos |
| Reintroducciones | 16 defectos: pruebas 16/16 y guardas 11/11 |
| `ruff` | Sin avisos |
| Artefacto publicado | `98ed8bd1`, vector 2; ROC-AUC 0.9469 [0.928, 0.964], aporte +0.052 [+0.030, +0.076]; perfil y registro con la misma huella |
| Pasos del trabajo `modelo`, con Git Bash | Los seis pasan sobre el árbol correcto, incluido el ensayo del bucle, que no publica por el intervalo del aporte |
| Imagen del backend | Se construye; motor `ml:98ed8bd1`; ingresos ausentes llegan como `NaN` y se puntúan; perfil y artefacto corresponden; `drift_monitor` y `feedback_dataset` importan; 869 MB. Sin cambios de dependencias ni de imagen base, Trivy no se repitió |
| Integración continua | 10 trabajos; una guarda nueva y una modificada en `modelo`; 34 en `configuracion-peligrosa` |

Una lectura que conviene no pasar por alto: dentro de la imagen, el mismo prospecto da **la
misma probabilidad con ingresos ausentes que con 20 millones**. No es un fallo de la
imputación: en los datos sintéticos la etiqueta no depende de los ingresos, y el modelo lo
aprendió. Lo que la fase garantiza es que el modelo no recibe una cifra que nadie dio; que los
ingresos importen o no lo dirán los desenlaces reales.

---

## 24.9. Lo que esta fase no hizo

* **No hay deriva del rendimiento ni curva de aprendizaje de los mínimos del extractor.** Las
  dos necesitan desenlaces reales, y en la base no hay ningún prospecto en estado terminal.
  Quedan como estaban.
* **Las instantáneas anteriores dejan de servir para entrenar.** Es el precio de no
  inventar. Hoy no cuesta nada, porque no hay desenlaces; el manifiesto dice cuántas se
  descartan para que el día que los haya se vea.
* **El monitor de deriva dirá «muestra insuficiente» durante un tiempo.** Solo compara
  instantáneas del vector 2, y hasta que se acumulen cien no dictamina. Es la respuesta
  verdadera; comparar las antiguas daría un PSI con aspecto de deriva que sería un cambio de
  definición.
* **Los ceros que ya hay en la base no se migraron a nulos.** El extractor los lee como
  ausentes, que es lo que importa al modelo. La ficha los sigue mostrando como cero hasta que
  alguien la edite.
* **El alta del panel no pregunta los ingresos.** Deja el campo vacío; se rellena desde la
  ficha. Añadir el campo al alta es una decisión de producto, no de este capítulo.
* **Las suposiciones del generador son suposiciones.** Qué prospectos dejan los ingresos en
  blanco y cuánto pesa un intento sin respuesta están elegidos para que el pipeline tenga algo
  que aprender, no medidos.
* **Código y artefacto viajan juntos.** El artefacto anterior no entiende el vector nuevo ni
  al revés: un despliegue que actualice uno sin el otro puntúa con columnas que faltan. La
  imagen los lleva juntos y el CI entrena en cada ejecución; una pila ya arrancada hay que
  reconstruirla, y `ML_MODEL_SHA256` cambiarse a la huella nueva si estaba fijada.
