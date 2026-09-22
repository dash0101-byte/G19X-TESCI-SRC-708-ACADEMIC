# Reporte Técnico 12: Gobierno de Datos, Migraciones y Validez del Modelo

---

## 1. Objetivo de la Fase

Las fases anteriores dejaron el sistema seguro y rápido. Esta se ocupa de tres cuestiones
que no son de seguridad ni de rendimiento, sino **de honestidad técnica**: cómo evoluciona
el esquema de datos sin romper lo que ya está desplegado, qué significa exactamente el
número que el modelo publica como precisión, y cómo se sustituirían los datos sintéticos
por resultados comerciales reales.

La sección 2.4 es la más importante de todo el documento para la defensa oral, porque
responde a la primera pregunta razonable que cabe hacerle a un ROC-AUC de 0.94: **¿comparado
con qué?**

---

## 2. Qué se Realizó

### 2.1. Migraciones de Esquema con Alembic

El esquema se creaba con `Base.metadata.create_all()` en cada arranque de la aplicación.
Parecía inofensivo —`create_all` no borra ni altera nada— y ahí estaba el problema: **es
incapaz de evacuar un cambio**. Renombrar una columna, cambiar un tipo o añadir un índice
sobre datos ya escritos no lo ve. Daba la falsa impresión de que el esquema se mantenía
solo, mientras la base se quedaba con la forma que tuvo el primer día.

Se incorporó Alembic con tres migraciones:

| Revisión | Contenido |
| :--- | :--- |
| `675112244474` | Línea base: el esquema completo tal como estaba. |
| `eb529f0113d6` | Zona horaria en las 19 columnas temporales; retirada de `tenant_id`. |
| `1458e30e2ea2` | `score_histories.feature_snapshot`, para el bucle de realimentación. |

**En producción y staging la aplicación ya no crea nada.** Verifica que la base esté en la
última revisión y **aborta el arranque si no lo está**:

```
Esquema de base de datos desactualizado: la base está en la revisión 675112244474
y el código espera 1458e30e2ea2. Ejecute `alembic upgrade head` antes de desplegar.
```

Desplegar código nuevo contra una base sin migrar es una de las formas más comunes de
caída: el servicio arranca, sirve tráfico y falla con `UndefinedColumn` en la primera
petición que toque la columna que falta —a veces horas después, y solo en un endpoint
concreto—. Comprobarlo al arrancar convierte ese fallo difuso en un mensaje accionable.

Migrar **no** se hace automáticamente: la imagen levanta varios *workers* y todos
ejecutarían la migración a la vez. Es un paso explícito del despliegue.

La URL de conexión no se escribe en `alembic.ini`: se toma de `settings`, la misma variable
que usa la aplicación. Ponerla en el `.ini` habría dejado una credencial de producción
versionada en el repositorio.

---

### 2.2. Zona Horaria en las Columnas Temporales

La aplicación siempre escribió instantes en UTC, pero las columnas eran
`TIMESTAMP WITHOUT TIME ZONE` y **descartaban la zona al persistir**. Lo que entraba como
«14:03 UTC» se leía después como «14:03 sin zona», y el consumidor tenía que adivinar. El
cálculo de inactividad —del que depende el decaimiento temporal del score— acababa restando
un instante con zona de otro sin ella.

La conversión tiene una trampa que merece detallarse, porque es la razón por la que esta
migración se escribió a mano en lugar de dejar la que generó Alembic:

```sql
-- Lo que genera Alembic por defecto:
ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ;

-- Lo que hace esta migración:
ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ
    USING "created_at" AT TIME ZONE 'UTC';
```

Sin el `USING`, PostgreSQL interpreta cada valor sin zona **según el huso de la sesión que
ejecuta la migración**. Comprobado sobre un valor real de las 14:03:

| | Resultado leído en UTC |
| :--- | :--- |
| Con `USING ... AT TIME ZONE 'UTC'` | `2026-03-01 14:03:00+00` ✔ |
| Sin `USING`, sesión en `America/Mexico_City` | `2026-03-01 20:03:00+00` ✘ |

Seis horas de desplazamiento en cada fecha de la base, silenciosas, y con el decaimiento
temporal calculando sobre datos falseados a partir de ese momento.

---

### 2.3. Retirada de la Multi-Tenencia Decorativa

El sistema declaraba un `tenant_id`, lo guardaba en la tabla de usuarios y lo incluía en
cada token emitido. **Ninguna consulta filtraba por él.** Las tablas de negocio —`leads`,
`campaigns`, `sales_reps`— no tenían esa columna, de modo que cualquier usuario veía la
cartera completa con independencia de su valor.

Se retiró. La decisión merece justificarse porque lo cómodo habría sido dejarlo:

> Un identificador de inquilino que no aísla nada **es peor que no tenerlo**. Su presencia
> en el token y en el modelo de datos induce a creer que la separación existe, y es
> exactamente el tipo de suposición sobre la que alguien construye después una integración
> multi-cliente sin volver a comprobarla.

Implementar multi-tenencia de verdad exigiría añadir la columna a las tres tablas de
negocio, filtrar en cada consulta del repositorio y probar el aislamiento con usuarios de
inquilinos distintos. Es un proyecto en sí mismo y excede el alcance actual, en el que
PluriOne es el único ocupante del sistema.

Un paso del pipeline comprueba que la columna no reaparezca por descuido.

---

### 2.4. Qué Significa Realmente el ROC-AUC de 0.95

Esta es la sección que sostiene la defensa del proyecto.

#### El dato de partida

El modelo se entrena con datos sintéticos generados por `synthetic_generator.py`. La
etiqueta `converted` **no procede de resultados comerciales observados**: se calcula ahí
mismo, como una función suave de las propias variables más un término de ruido gaussiano.

```python
latent_prob = (0.40 * firmografico) + (0.50 * comportamiento_atenuado) + (0.10 * canal)
converted   = 1 if (latent_prob + ruido) >= 0.55 else 0
```

Un modelo entrenado sobre esto está aprendiendo a **recuperar la fórmula de arriba**, no a
predecir el comportamiento de un comprador. Que lo consiga con un ROC-AUC alto verifica que
el pipeline está íntegro —que las variables llegan, que el preprocesado no las corrompe,
que la calibración funciona— y no dice nada sobre el rendimiento en producción.

#### La comparación contra líneas base

Un ROC-AUC no significa nada sin saber contra qué compite. El entrenamiento calcula ahora
tres referencias sobre el mismo conjunto de prueba:

| Referencia | ROC-AUC |
| :--- | :---: |
| Azar | 0.5000 |
| **Regla trivial** (ordenar por `days_since_last_activity`) | **0.9136** |
| Heurístico ICP, sin ninguna componente aprendida | 0.9110 |
| Modelo entrenado | **0.9524** |

El número que hay que mirar no es el 0.95: es que **ordenar la lista por una sola columna
ya alcanza 0.91**. Todo el pipeline de machine learning aporta **+0.041** sobre el
heurístico que el sistema ejecutaría igualmente si se retirase el modelo.

Ese resultado es esperable y no es un defecto: el dataset es sintético y su etiqueta se
genera con una fórmula emparentada con la del propio heurístico. Pero decirlo es más
defendible que exhibir un 0.95 aislado, porque un 0.95 aislado no sobrevive a la pregunta
«¿y sin el modelo, cuánto sale?».

#### El umbral pasó a medir el aporte, no solo la precisión

El pipeline exigía `ROC-AUC ≥ 0.82`. Ese umbral, por sí solo, no distingue un modelo útil
de uno inútil: la regla trivial ya da 0.91, muy por encima. Un clasificador roto que hubiera
aprendido solo esa variable pasaría el gate sin problema.

Se añadió un segundo umbral sobre el **aporte respecto del heurístico** (mínimo +0.01,
medido +0.041). Es además la red que atrapa una regresión como ML-4: la precisión absoluta
apenas se movería, pero el aporte se desplomaría.

#### Fuga de información retirada del dataset publicado

El CSV incluía la columna `latent_prob`: la probabilidad con la que se fabrica la etiqueta.
No entraba en el conjunto de variables del entrenamiento actual, pero estaba publicada, y
quien reentrenara desde ese archivo sin conocer su origen obtendría un modelo con precisión
aparente casi perfecta y valor nulo. Se retiró.

---

### 2.5. Alineación del Vector de Variables (ML-4)

El backend contabilizaba `proposal_sent`, `meeting_scheduled`, `phone_calls` y
`whatsapp_messages` desde las actividades registradas de cada prospecto. **No se los pasaba
al clasificador.** Las señales más informativas del embudo —una propuesta enviada, una
reunión agendada— solo movían la mitad heurística del score; el modelo estaba ciego a ellas.

Era una divergencia silenciosa entre tres listas que nadie comparaba: la del adaptador de
inferencia, la del preprocesador y la del entrenamiento. Scikit-learn no protesta cuando el
vector de entrada no coincide con el de entrenamiento: ignora columnas de más y falla o
imputa las de menos, de modo que el sistema seguía puntuando con un modelo que veía menos de
lo que parecía ver.

Tras alinear las tres listas (16 variables) y reentrenar, el ROC-AUC pasó de 0.9408 a
0.9524. Hay ahora una prueba que compara las tres listas y nombra la variable que se pierda.

---

### 2.6. Diseño del Bucle de Realimentación

Cada prospecto que llega a `WON` o `LOST` es una etiqueta real que el sistema ya posee. El
módulo `feedback_dataset.py` convierte esos desenlaces en un dataset entrenable. Tres
decisiones lo sostienen, y las tres existen para evitar errores que producen modelos con
métricas excelentes y valor nulo:

**1. Se etiqueta sobre la instantánea, nunca sobre el estado actual.**

Un prospecto ganado lleva, por definición, propuesta enviada y reunión agendada. Construir
el dataset leyendo los prospectos tal como están hoy enseñaría al modelo que **enviar
propuestas causa cierres**: la relación invertida, y además inútil, porque en el momento en
que hay que decidir a quién llamar todavía no se ha enviado ninguna propuesta.

Por eso se añadió `score_histories.feature_snapshot`, que guarda el vector de variables tal
como estaba **al puntuar**, es decir cuando aún no se conocía el desenlace. El extractor usa
la instantánea más antigua de cada prospecto: la de su entrada al embudo.

**2. Los prospectos sin desenlace se excluyen, no se cuentan como fracasos.**

Un prospecto en `NEGOTIATION` no es un `LOST`: es un caso cuyo resultado aún no se conoce.
Tratar esa censura por la derecha como negativo es el error más común al montar estos bucles
y sesga el modelo hacia el pesimismo precisamente en los prospectos más activos.

**3. Se exige volumen mínimo antes de reentrenar.**

200 ejemplos y 50 por clase. Con menos, el modelo memoriza los clientes concretos que
cerraron ese trimestre en lugar de generalizar. El extractor prefiere no producir dataset a
producir uno que invite a reentrenar mal.

Cada dataset se acompaña de un **manifiesto**: ventana temporal, balance de clases, cuántos
prospectos se excluyeron por seguir en curso, cuántos terminales se descartaron por no tener
instantánea utilizable, y una huella SHA-256 del contenido. Sin esos datos, una métrica
calculada sobre el dataset no es interpretable; con la huella, un modelo queda ligado a los
datos exactos con que se entrenó.

#### Cadencia operativa propuesta

| Cuándo | Qué |
| :--- | :--- |
| Continuo | El scoring persiste la instantánea de variables en cada puntuación. |
| Mensual | Extraer el dataset y revisar el manifiesto: volumen, balance, ventana. |
| Al superar los mínimos | Reentrenar contra datos reales y comparar contra el heurístico **sobre esos mismos datos**. |
| Antes de publicar | El modelo nuevo debe superar al heurístico y al modelo en producción. Si no, no se publica. |

Conviene ser explícito sobre el plazo: entre puntuar un prospecto y conocer su desenlace
pasan semanas o meses. El primer reentrenamiento con datos propios no es una tarea de la
siguiente iteración, sino de la siguiente campaña comercial completa.

---

## 3. Justificación Técnica

1. **Verificar en lugar de asumir.** Tanto la comprobación de revisión al arrancar como el
   gate de aporte mínimo del modelo comparten la misma idea: convertir una suposición
   —«la base estará migrada», «el modelo aporta algo»— en una comprobación que falla ruidosa.

2. **El dato correcto por encima del dato conveniente.** Retirar `latent_prob`, excluir los
   prospectos en curso y etiquetar sobre la instantánea empeoran las métricas aparentes. Es
   el sentido de hacerlo: una métrica que mejora al eliminar una fuga de información nunca
   fue una métrica.

3. **Retirar antes que simular.** `tenant_id` podría haberse dejado como está, sin coste
   aparente. Se retiró porque una capacidad declarada y no implementada es una trampa para
   quien lea el código después.

---

## 4. Retos Técnicos Superados

### Reto 1: Las migraciones no eran reversibles en PostgreSQL
**Problema:** Un `downgrade base` seguido de `upgrade head` fallaba con
`type "leadstatus" already exists`. PostgreSQL **no borra los tipos ENUM al borrar las
tablas que los usan**: sobreviven como objetos sueltos del esquema, y Alembic no genera esos
`DROP TYPE`. Una migración que no se puede revertir no es una migración: es un viaje de ida,
y se descubre en el peor momento posible —cuando hay que echar atrás un despliegue—.

**Solución:** Borrado explícito de los cuatro tipos en el `downgrade` de la línea base,
condicionado al dialecto porque en SQLite los enums son restricciones `CHECK` y desaparecen
con la tabla. El pipeline ejecuta ahora **dos ciclos completos** de ida y vuelta, porque el
fallo solo aparece al volver a subir.

### Reto 2: SQLite no sabe alterar columnas
**Problema:** La migración de zona horaria funcionaba en PostgreSQL y fallaba en la suite de
pruebas con `near "ALTER": syntax error`. La opción `render_as_batch` de Alembic solo afecta
a cómo se *genera* la migración, no a cómo se *ejecuta*.

**Solución:** `op.batch_alter_table`, que reconstruye la tabla. El cambio es un no-operativo
en SQLite —no distingue ambos tipos—, pero se recorre igualmente para que el historial de
revisiones sea idéntico en pruebas y en producción.

---

## 5. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Migraciones aplicadas y revertidas, dos ciclos completos | PostgreSQL y SQLite |
| `alembic check` (modelos ≡ migraciones) | Sin desviación |
| Fecha de las 14:03 tras migrar desde una sesión en `America/Mexico_City` | 14:03 UTC, sin desplazamiento |
| Arranque en producción contra base sin migrar | Abortado con mensaje accionable |
| Columnas temporales sin zona tras migrar | 0 |
| Listas de variables (adaptador ≡ preprocesador ≡ entrenamiento) | 16 = 16 = 16 |
| Aporte del modelo sobre el heurístico | +0.0414 |
| Gate de aporte mínimo con umbral inalcanzable | Sale con código 1 y no sobrescribe el artefacto |
| Dataset de realimentación con prospecto ganado | `proposal_sent = 0` (estado de entrada, sin fuga) |
| Suite de pruebas al cerrar esta fase | 239 aprobadas |
