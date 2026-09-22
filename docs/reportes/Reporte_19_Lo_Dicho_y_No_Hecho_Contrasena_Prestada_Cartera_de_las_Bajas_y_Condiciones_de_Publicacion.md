# Capítulo 19: Lo Dicho y No Hecho — Contraseña Prestada, Cartera de las Bajas y Condiciones de Publicación del Modelo

## 19.1. Por qué existe esta fase

El plan de mejora que ordenó los capítulos 14 a 18 terminaba en la Fase 12. No había una
Fase 13 escrita en ninguna parte.

Lo que sí había eran cuatro listas. Desde el capítulo 14, cada capítulo cierra con una
sección que enumera lo que **no** hizo, escrita para que no se lea como resuelto. Juntas,
esas listas son la deuda que el propio proyecto se reconoce, con su motivo al lado. Esta
fase se construye leyéndolas y separando dos clases de entradas:

* las que son **defectos que el código puede cerrar**, y
* las que son decisiones de operación, trabajo que solo el tiempo puede hacer, o piezas
  demasiado grandes para una fase.

| Origen | Entrada | Decisión |
| :--- | :--- | :--- |
| §15.8.3 | `must_change_password` se registra pero no se impone | **N-24**, §19.2 |
| §15.8.4 | La cartera de quien se va no se reparte ni se avisa | **N-25**, §19.3 |
| §18.9 | El perfil de referencia y el artefacto pueden desincronizarse | **N-26**, §19.4 |
| §18.9 | `--publicar` no exige el intervalo de confianza | **N-27**, §19.5 |
| §17.9 | Unas 43 etiquetas de formulario sin asociar | Ya estaba hecho; el texto no, §19.6 |
| §15.8.1–2 | Lista de contraseñas filtradas; segundo factor | Fuera: servicio externo o pieza grande |
| §16.9 | Copias fuera de la máquina, planificador, alertas operativas | Fuera: decisiones de quien opera |
| §17.9 | Pruebas de extremo a extremo; rediseño de la carga de datos | Fuera: pieza grande |
| §18.9 | Bucle sin datos reales; deriva de rendimiento; mínimos del extractor | Fuera: solo el tiempo |

Las cuatro entradas que se cierran tienen algo en común, y es el mismo defecto que abrió el
capítulo 18 con otra ropa: **una condición que el sistema anota, enseña o documenta, y no
impone**. Una marca que la base guarda y el servidor ignora. Un aviso que solo aparece si
se piden las cuentas de baja. Un perfil que sale del mismo entrenamiento que el modelo
«por construcción», sin que nada lo compruebe. Un intervalo de confianza que se imprime al
lado de la cifra que decide, y que no decide nada.

---

## 19.2. N-24 — La contraseña que conoce otra persona

### El estado de partida

Una cuenta recibe una contraseña ajena en tres momentos: cuando el administrador la da de
alta, cuando la restablece y cuando la reactiva. Los tres ponían `must_change_password` a
verdadero desde la Fase 9. El panel de administración mostraba «Pendiente de cambio» en
color de advertencia.

Y el servidor dejaba operar igual. Se podía trabajar indefinidamente —leer la cartera,
editar prospectos, lanzar un recálculo si el rol lo permitía— con la contraseña que
conoce el administrador. Mientras siga siendo esa, la cuenta no identifica a quien la usa,
y todo lo que este sistema protege por identidad cuelga de eso: la autorización por objeto
del capítulo 15, la bitácora del 14.

Había un detalle más, que convertía el hueco en invisible desde el cliente: la respuesta
del login **no incluía la marca**. `UserResponse` enumeraba sus campos uno a uno —por una
buena razón, la de no publicar nunca el hash— y `must_change_password` no estaba entre
ellos. Aunque alguien hubiera querido llevar a la persona a cambiarla, el navegador no tenía
forma de saber que debía.

### Dónde se impone

La tentación es una lista de rutas bloqueadas. Tiene el defecto de siempre: el endpoint que
se añada mañana nace abierto, y cerrarlo depende de que alguien se acuerde.

Se hizo al revés. La comprobación vive en la resolución de identidad que usan **todas** las
rutas autenticadas —directamente, o a través de `require_roles`, `auditar` y
`alcance_actual`—, y la excepción hay que pedirla por su nombre:

```python
def get_current_user(...):                         # la de siempre, ahora estricta
    return _resolver_identidad(credentials, db, admitir_contrasena_prestada=False)

def get_current_user_con_contrasena_prestada(...):  # la excepción, con nombre largo
    return _resolver_identidad(credentials, db, admitir_contrasena_prestada=True)
```

Solo tres rutas piden la excepción: consultar el propio perfil, cambiar la contraseña y
cerrar la sesión. Lo imprescindible para dejar de estar en ese estado.

La respuesta es un **403**, no un 401. El cliente interpreta un 401 como sesión caducada:
intenta renovar, vuelve a recibir 401 y expulsa a la persona a la pantalla de entrada, que
es un bucle sin explicación. Un 403 dice lo que pasa —la identidad es válida y la operación
no se permite todavía— y lleva en el cuerpo un código, `cambio_de_contrasena_obligatorio`,
para que el cliente lo distinga de «su rol no llega» sin comparar cadenas.

El cliente, por su parte, recibe ahora la marca en el login y en cada refresco, y en lugar
de la aplicación enseña una pantalla que explica por qué no la deja pasar y pide la
contraseña actual y la nueva. Las cargas de datos del panel no se lanzan en ese estado: si
se lanzaran, cada tarjeta fallaría con un 403. Al cambiarla, el servidor cierra todas las
sesiones —esa incluida, como ya hacía— y la persona vuelve a la entrada con el mensaje del
servidor, para que no parezca una caducidad.

### La prueba que salía verde sin comprobar nada

La prueba central no enumera rutas a mano, por la misma razón por la que el bloqueo no es
una lista: recorre las rutas registradas en la aplicación, se queda con las que dependen de
`get_current_user` y exige que **todas** rechacen a la cuenta marcada. Un endpoint nuevo
queda cubierto sin tocar la prueba.

La primera ejecución dio seis pruebas verdes, dos rojas y **una omitida**. La omitida era la
paramétrica: se había quedado sin casos. La versión de FastAPI instalada (0.141) ya no copia
las rutas de un router incluido a `app.routes` con el prefijo puesto, como hacían las
anteriores; las deja dentro de un objeto `_IncludedRouter` que guarda el router original y
el prefijo aparte. Recorrer `app.routes` devolvía una lista vacía, y pytest convierte una
paramétrica vacía en un aviso de omisión que en una ejecución larga no lee nadie.

Lo que lo delató fueron las dos rojas: la que exige que la lista **no esté vacía** y la que
exige que la excepción la pidan exactamente tres rutas. La primera se escribió pensando en
un cambio futuro que desenganchara las rutas, y atrapó el presente.

El recorrido se corrigió descendiendo por esos objetos, y como sus atributos son internos,
se contrasta con una fuente pública: el conjunto de rutas recorridas tiene que ser **el
mismo** que el del esquema OpenAPI. Si FastAPI vuelve a cambiar su estructura, la prueba que
falla es esa, con un mensaje que dice qué rutas faltan, y no una paramétrica que se vacía en
silencio. Hoy recorre 28 rutas, y las 28 rechazan.

### Una consecuencia que no se buscaba

El capítulo 14 dejó dicho (§14.7) que un access token robado sigue valiendo hasta expirar,
quince minutos, porque revocarlo exigiría consultar la base en cada petición. Pero la
resolución de identidad **ya consulta la base en cada petición** —recarga el rol, para que
una degradación surta efecto de inmediato—, y ahora también lee la marca.

Restablecer la contraseña de una cuenta la marca. A partir de ese instante, los tokens que
ya circulaban solo sirven para ver el perfil, salir, o cambiar una contraseña que exige
conocer la que acaba de fijar el administrador. El restablecimiento, que es justo lo que se
hace cuando se sospecha de una cuenta, corta ahora los tokens ya emitidos. No cierra el
caso general de §14.7 —un token robado a una cuenta que nadie restablece sigue valiendo sus
quince minutos—, pero cubre el que más importa.

---

## 19.3. N-25 — La cartera de quien se va

### El estado de partida

La baja de una cuenta conserva sus prospectos a su nombre, y esa decisión del capítulo 15
sigue siendo correcta: repartirlos automáticamente sería decidir sin nadie que decida.

Lo que no existía era la segunda mitad. No había forma de repartir esa cartera salvo
editando prospecto a prospecto. La vista por defecto del equipo comercial oculta las
cuentas de baja, así que la cartera de quien se fue **desaparecía de la pantalla justo donde
había que verla**. Y la autoasignación no la rescataba: solo reparte los prospectos
calientes que no tienen dueño, y estos lo tienen.

Un prospecto caliente asignado a una cuenta que ya no puede entrar no lo atiende nadie, y
nada lo dice.

### Verla

`GET /sales-reps` devuelve ahora, **siempre**, cuántos prospectos siguen asignados a
cuentas de baja, también cuando el listado las oculta. Se cuentan sin filtrar por la marca
de asesor: quien dejó de atender cartera y después fue dado de baja puede conservar
prospectos igual, y esos son los que menos se ven.

El panel lo convierte en un aviso en la vista por defecto, con un botón que muestra las
cuentas de baja. Un aviso que solo aparece al pedir las bajas no avisa.

### Repartirla

`POST /sales-reps/{id}/cartera` traspasa todos los prospectos de una cuenta a otra. Lo
puede hacer el líder comercial, no solo el administrador: repartir trabajo es una decisión
comercial. Las condiciones son las que impiden mover el problema en vez de resolverlo:

* el destino tiene que estar **activo** —traspasar a otra baja no arregla nada—;
* tiene que **atender cartera** —si no, los prospectos quedan fuera de toda vista de
  asesor—;
* no puede ser la misma cuenta.

Superar la capacidad declarada del destino **no se bloquea**: cargar de más a alguien
durante una semana puede ser la decisión correcta. Se devuelve `supera_capacidad` y se
anota en la bitácora, para que sea una decisión y no un descuido.

El panel ofrece, en la fila de cada baja con cartera, un selector que solo lista cuentas
activas.

---

## 19.4. N-26 — El perfil que no sabía de qué modelo era

### El estado de partida

El monitor de deriva mide cuánto se aleja producción de la población con la que se entrenó
el modelo. Para eso compara contra un perfil de referencia que escribe `train_model.py` en
el mismo momento en que escribe el `.joblib`. Los dos viajan juntos en la imagen.

«En el mismo momento» era la única garantía, y era una garantía de construcción, no de
comprobación. Una imagen construida con un `.joblib` de un entrenamiento y un perfil de
otro —un artefacto copiado a mano, una construcción a medias, un reentrenamiento que falló
entre las dos escrituras— no produce ningún error. El PSI sigue saliendo, con el mismo
aspecto y los mismos dictámenes, y deja de significar lo que dice. Es la clase de fallo que
nadie ve, porque su síntoma es un número plausible.

### El vínculo

Al publicar, el perfil guarda ahora la huella del artefacto y la de los datos:

```json
{
  "generado_en": "2026-09-10T23:00:33+00:00",
  "filas_de_referencia": 2400,
  "model_sha256": "0a2632a2f496fd188e610aecf3f6452154916a1bed7781b65370d2d9401925fd",
  "huella_datos_sha256": "cd42cf4f04961d23828b0dde0d42b8b8d898a3bb80c4aab55d9cdb6e6328a410",
  "columnas": { ... }
}
```

Y el monitor lo comprueba **antes de leer una sola instantánea**. Si no corresponden, no
evalúa y sale con código 1 —«no se pudo evaluar»—, no con el 2 de la deriva: no es una
señal del negocio, es un despliegue roto, y un supervisor que confunda las dos cosas
reacciona igual a ambas. En modo servicio se comprueba una vez, al arrancar; el contenedor
sale, `restart: unless-stopped` lo vuelve a lanzar, y el bucle de reinicios queda a la vista.

Un perfil **sin** huella se rechaza también, en lugar de darse por bueno por no poder
comprobarlo. Es exactamente el caso que hay que obligar a regenerar: todo perfil anterior a
esta fase.

### Regenerarlo

El perfil versionado era anterior a esta fase y el monitor lo habría rechazado. Se
reentrenó. La huella del `.joblib` resultante es **idéntica** a la del artefacto que ya se
servía (`0a2632a2…`): con la semilla fija, el entrenamiento es determinista byte a byte. El
perfil nuevo queda así atado al mismo modelo que estaba desplegado, sin cambiar el modelo.

El registro tiene por eso dos publicaciones del mismo artefacto, la de la fase anterior y
la de esta. Es verdad: se entrenó dos veces y salió lo mismo. Borrar una para que el
registro «se vea limpio» sería reescribir la historia del archivo que existe para poder
creerla.

Una prueba y una guarda comprueban además el estado del repositorio, no solo el del código:
que el perfil versionado nombra al `.joblib` versionado, y que el registro tiene esa
publicación con la misma huella de datos.

---

## 19.5. N-27 — El intervalo, de convención a condición

### El estado de partida

El capítulo 18 añadió el intervalo de confianza bootstrap del ROC-AUC y lo imprimió siempre,
al lado de la estimación puntual. Separó medir de publicar: con datos reales hay que pedir
`--publicar` explícitamente. Y dejó escrito, en su lista final, que pedirlo no exigía mirar
el intervalo. Dependía de que quien lo escribiera hubiera leído la tabla.

### La regla

Se publica solo si, además de los dos umbrales de siempre, el **límite inferior** del
intervalo alcanza el umbral de 0.82. Sin intervalo calculable —una sola clase en la
partición de prueba, o muy pocos ejemplos— tampoco.

La regla es una función pura, `motivo_para_no_publicar`, que devuelve el motivo o `None`.
Las métricas distinguen ahora tres cosas que antes eran una:

| Campo | Qué dice |
| :--- | :--- |
| `passed` | Supera los umbrales con la estimación puntual |
| `publicable` | Además, el intervalo no contradice al umbral |
| `publicado` | Se pidió publicar, era publicable y se escribió el artefacto |

Y la orden sale con código 1 cuando se pidió publicar y no se publicó. Antes salía con 0
ante cualquier modelo que pasara los umbrales puntuales, de modo que un guion que la
automatizara daba por publicado lo que no lo estaba.

### Qué habría pasado

Las cohortes del ensayo del capítulo 18, releídas con la regla:

| Cohorte | ROC-AUC | IC 95 % | Antes | Ahora |
| :--- | ---: | :--- | :--- | :--- |
| 45 desenlaces | 0.8889 | [0.571, 1.000] | Pasa los umbrales | No publicable |
| 60 desenlaces | 0.8125 | [0.355, 1.000] | No pasa | No publicable |
| 260 desenlaces | 0.8917 | [0.800, 0.968] | Pasa los umbrales | **No publicable** |
| Sintéticos (3000) | 0.9524 | [0.935, 0.968] | Pasa | Publicable |

La tercera fila es la que conviene leer despacio. Con 260 desenlaces reales, 52 de ellos en
la partición de prueba, la regla **tampoco publica**: el límite inferior se queda en 0.800.
Es una afirmación sobre cuántos datos hacen falta, no solo sobre la regla. Con un umbral de
0.82 y la variabilidad de un conjunto de prueba de medio centenar, la estimación todavía es
compatible con un modelo por debajo de lo exigido. Si eso resulta demasiado conservador
cuando lleguen datos reales, la conversación correcta es sobre el umbral o sobre el tamaño
del conjunto de prueba, y tiene que ocurrir con los datos delante; bajar la exigencia antes
sería decidirla sin ellos.

Con los datos sintéticos la condición no cuesta nada. Solo muerde donde tiene que morder.

La regla se aplica a los dos orígenes por el mismo camino. Un criterio que solo existiera
para los datos reales se leería como excusa el día que un modelo real no pasara.

---

## 19.6. Lo que ya estaba hecho: las 43 etiquetas

La primera entrada de §17.9 decía que unas 43 etiquetas de formulario seguían sin asociar
a su control en cuatro componentes. Al planificar esta fase se contaron:

| Componente | Etiquetas | Con `htmlFor` |
| :--- | ---: | ---: |
| `LeadDetailModal` | 20 | 20 |
| `NewLeadModal` | 15 | 15 |
| `AdminPanel` | 8 | 6 (las otras 2 envuelven su casilla) |
| `LoginScreen` | 2 | 2 |

Estaban asociadas. Se arreglaron después del cierre del capítulo 17, en otra sesión de
trabajo del mismo día, y el texto no se actualizó. La regla
`jsx-a11y/label-has-associated-control` está en `error` y el `linter` pasa; para no dar por
buena una regla por su configuración, se comprobó que dispara con un archivo de sonda que
contenía una etiqueta suelta, y se retiró la sonda.

Es el error de siempre en su dirección menos habitual: la documentación afirmaba **menos**
de lo que el código hacía. Sigue siendo un error, porque la memoria es lo que lee quien
evalúa el proyecto. Se corrigió anotando la entrada, sin borrarla —que estuvo pendiente es
parte de lo que la memoria cuenta—, y lo mismo se hizo con las cuatro entradas de §15.8 y
§18.9 que esta fase cierra. Sin esas notas, la memoria compilada se contradiría a sí misma
entre un capítulo y el siguiente.

---

## 19.7. Que nada de esto sea decorativo

### Las pruebas

Se reintrodujeron **22 defectos**, uno a uno, ejecutando con cada uno las pruebas de
su pieza —backend y cliente—: **22 los detectan**, con 64 fallos en total.

### Las guardas del pipeline

Tres guardas nuevas, **ocho reintroducciones, ocho disparos**, y las tres pasan sobre el
árbol correcto. El arnés exige además que el fallo sea el correcto —la palabra `FALLO` en
la salida de la guarda—, porque la lección del capítulo 18 fue que una guarda rota dispara
con todo.

| Guarda | Reintroducciones |
| :--- | :--- |
| La contraseña prestada no opera | quitar la comprobación; pedir la excepción desde un endpoint de negocio; abrir una cuarta ruta en `/auth` |
| El perfil de referencia corresponde al artefacto | dejar de escribir la huella (reentrenando); que el monitor no compruebe; que la comprobación acepte cualquier artefacto |
| Publicar exige el intervalo de confianza | quitar la condición del límite inferior; que `entrenar` vuelva a decidir con los umbrales puntuales |

La guarda del perfil no se limita a leer archivos: construye un perfil ajeno, lanza el
monitor contra él y exige que se niegue. Es lo que atrapa quitar la comprobación dejando la
huella escrita, que es la reintroducción más verosímil.

La guarda de la publicación tuvo un hueco que se vio al diseñar sus reintroducciones, antes
de ejecutarlas: en su primera versión solo preguntaba a `motivo_para_no_publicar` con las
cifras del ensayo. Si `entrenar` dejara de llamarla, la función seguiría respondiendo bien y
la guarda seguiría en verde. Ahora comprueba también que el entrenamiento decide con ella, y
esa es precisamente la segunda reintroducción.

El arnés de las guardas desvía `DATABASE_URL` a una base desechable. Si una reintroducción
dejara pasar al monitor, este intentaría leer instantáneas por la ruta relativa por defecto
y crearía un `lead_scoring.db` vacío en la raíz del proyecto, que es lo que pasó en la fase
anterior. Al terminar se comprobó que no apareció, y que los cuatro archivos del modelo
volvieron byte a byte a su estado.

---

## 19.8. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend | **673 pruebas** (eran 563), 92 % de cobertura |
| Suite del cliente | **126 pruebas** (eran 113), cobertura 95.6 / 87.8 / 97.7 / 97.7 |
| `ruff` / `eslint` | Sin avisos |
| Rutas autenticadas que rechazan la contraseña prestada | 28 de 28, contrastadas con OpenAPI |
| Integración continua | 10 trabajos, 101 pasos, 23 guardas en `configuracion-peligrosa` |
| Guardas nuevas | 3 guardas, 8 reintroducciones, 8 disparos |
| Artefacto del modelo | `0a2632a2…`, idéntico antes y después del reentrenamiento |
| Perfil desplegado | Atado al artefacto y a su publicación en el registro |
| Ensayo del bucle (60 desenlaces) | «No sería publicable», código 0 |

> **Nota sobre la cifra del backend.** La suite no se midió por separado al cerrar esta
> fase: la de la tabla es la del cierre de la Fase 14 (capítulo 20), que ya incluye sus
> pruebas propias. Por la misma razón, las rutas autenticadas son hoy 29 —se sumó la
> exportación de los datos del prospecto— y la integración continua ha crecido; las 28
> rutas y los 101 pasos son los de este capítulo.

---

## 19.9. Lo que esta fase no hizo

* **`App.jsx` sigue sin pruebas.** La redirección a la pantalla de cambio obligatorio y el
  que las cargas de datos no se lancen en ese estado están comprobados por lectura y por la
  prueba del componente, no por una prueba de la aplicación montada. Es la entrada de §17.9
  que sigue abierta, y esta fase le añadió dos comportamientos más.
* **El caso general de §14.7 sigue abierto.** Un access token robado a una cuenta que nadie
  restablece vale sus quince minutos. Esta fase cubre el restablecimiento, no la revocación.
  *Cerrado en el capítulo 23: el access token lleva `token_version` y se rechaza en cuanto
  no coincide con la de la cuenta.*
* **El criterio del límite inferior es juicio, no medida.** Con él, 260 desenlaces reales no
  publican. Puede resultar demasiado exigente; no hay curva de aprendizaje con datos reales
  que diga cuánto, y no la habrá hasta que el bucle tenga datos.
* **El aporte sobre el heurístico se sigue midiendo con una estimación puntual.** El
  intervalo se exige para el ROC-AUC, no para el delta. Con pocos datos, el delta es aún más
  inestable que el ROC-AUC.
  *Cerrado en el capítulo 24: el aporte lleva su IC 95 % por bootstrap pareado y publicar exige
  que su límite inferior alcance el mínimo; una cohorte de 1000 filas con aporte +0.028 e
  intervalo [-0.002, +0.059] ya no se publica.*
* **El reparto es todo o nada, a un solo destino.** Repartir la cartera de una baja entre
  varias personas exige hacerlo en varios pasos o prospecto a prospecto, y no hay aviso
  fuera del panel: quien no abre la administración no se entera.
* **Cuando el monitor se niega, solo lo dice en su salida.** No usa `ML_DRIFT_WEBHOOK` para
  avisar de que no está evaluando. Un monitor que no vigila y no lo comunica por el mismo
  canal que sus alertas es un hueco de la misma familia que este capítulo cierra.
  *Cerrado en el capítulo 22: la negativa —y una evaluación fallida dentro del bucle— sale
  por `ML_DRIFT_WEBHOOK`, con silencio entre avisos y aviso de vuelta al evaluar otra vez.*
* **Lo que quedó fuera en §19.1** sigue fuera: segundo factor, lista de contraseñas
  filtradas, copias fuera de la máquina, pruebas de extremo a extremo y, sobre todo, datos
  reales.
