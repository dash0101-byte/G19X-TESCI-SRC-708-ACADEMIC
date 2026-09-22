# Reporte Técnico 11: Auditoría, Endurecimiento de Seguridad y Optimización de Rendimiento

---

## 1. Objetivo de la Fase

Con el sistema ya funcional y validado en los capítulos anteriores, sometí el proyecto a una
**auditoría técnica completa** antes de considerarlo apto para operación real. El objetivo
no era añadir funcionalidad, sino responder a una pregunta distinta: *¿qué pasa si esto se
despliega de verdad y alguien intenta abusarlo, o la cartera de prospectos crece un orden
de magnitud?*

La auditoría produjo un inventario de hallazgos clasificados en dos familias —los de
**seguridad y arquitectura** (`A-n`) y los de **corrección funcional y calidad**
(`M-n`)— que resolví en seis fases sucesivas. Este capítulo documenta ese trabajo.

Conviene decirlo con claridad porque es la lección más útil de la fase: **varios de los
hallazgos eran defectos reales que la suite de pruebas existente no detectaba**, no
sugerencias de estilo. Un sistema puede pasar el 100 % de sus pruebas y seguir siendo
inseguro si las pruebas nunca preguntaron por la seguridad.

---

## 2. Qué se Realizó

### 2.1. Fase 0-1: Identidad, Secretos y Superficie de Ataque

#### El hallazgo más grave: una clave de firma publicada en el repositorio

La clave con la que se firmaban los tokens de sesión estaba escrita en el código y en el
archivo `.env` versionado. Cualquiera con acceso al repositorio podía **fabricar un token
válido para cualquier usuario y cualquier rol**, sin necesidad de contraseña. El control de
acceso completo del Capítulo 9 quedaba anulado por esa única línea.

Rotarla no bastaba: una clave filtrada sigue existiendo en el historial. La solución tiene
tres partes:

1. Los secretos y la base de datos local salieron del árbol del proyecto.
2. La clave comprometida quedó **en una lista de bloqueo explícita**, de modo que
   reintroducirla por descuido impide el arranque:

```python
COMPROMISED_SECRET_KEYS = {
    "CLAVE_ROTADA_RETIRADA_DEL_HISTORIAL",
    "changeme",
    "secret",
    "CAMBIAR_ESTA_CLAVE",
}
```

3. En entorno productivo, una `SECRET_KEY` ausente, corta o comprometida **aborta el
   arranque**. Antes se generaba una temporal en silencio, lo que en la práctica significaba
   que cada reinicio invalidaba todas las sesiones sin que nadie supiera por qué.

#### Las cabeceras de identidad no eran identidad

El sistema aceptaba las cabeceras `X-User-Email`, `X-User-Role` y `X-Entra-*` como prueba de
identidad. Eso convertía la «simulación de RBAC alineada a Entra ID» del Capítulo 9 en algo
que cualquier cliente podía suplantar con una línea de `curl`:

```bash
curl -H "X-User-Role: System_Admin" http://.../api/v1/leads/1 -X DELETE
```

La identidad pasó a derivarse **exclusivamente** de un token JWT firmado (HS256) emitido tras
verificar la contraseña con `bcrypt`. Nginx, además, borra esas cabeceras en la pasarela: si
alguien reintrodujera esa confianza en el futuro, no llegarían con valores puestos por el
cliente.

#### Almacenamiento de sesión en el navegador

El token de acceso vive **solo en una variable de módulo** del frontend. No se guarda en
`localStorage` ni en `sessionStorage`: cualquier XSS puede leer ese almacenamiento, y un
token allí sobrevive al cierre de la pestaña. El token de refresco ni siquiera llega hasta
JavaScript — viaja en una cookie `HttpOnly` con `SameSite=Strict`.

#### Otros hallazgos de esta fase

| Hallazgo | Riesgo | Corrección |
| :--- | :--- | :--- |
| Entrega de la SPA sin normalizar rutas | *Path traversal*: lectura de ficheros fuera de `dist/` | Resolución real de la ruta y verificación de que sigue contenida en la raíz |
| Webhook CRM sin autenticación | Cualquiera podía inyectar prospectos | Firma HMAC-SHA256 con ventana temporal y comparación en tiempo constante |
| Sin límite de tamaño de cuerpo | Agotamiento de memoria con una sola petición | Tope de 256 KiB, aplicado también en Nginx |

---

### 2.2. Fase 2: Corrección Funcional y Calidad de Datos

Esta fase resolvió defectos que no comprometían la seguridad pero sí la corrección del
producto. El más ilustrativo:

**El simulador enviaba datos que el backend descartaba en silencio.** El esquema
`ScorePredictRequest` no declaraba los campos `proposal_sent`, `meeting_scheduled` ni
`urgency`. Pydantic los ignoraba sin error, de modo que marcar «Propuesta enviada» en la
interfaz no alteraba la puntuación. El usuario veía un formulario que aparentaba funcionar.

Tras completar el esquema, verifiqué el efecto de extremo a extremo en el navegador: con el
mismo prospecto, marcar «Propuesta / Cotización» movió la puntuación de **74.6 (WARM) a 83.8
(HOT)** — exactamente el incremento que predice la fórmula.

Otras correcciones de la fase:

- **Un solo módulo de reglas.** El heurístico estaba duplicado entre el backend y el pipeline
  de ML, con posibilidad de divergir. Ahora vive en `app/core/scoring_rules.py`,
  parametrizado por la configuración, y hay una prueba que compara ambas rutas de cálculo.
- **Los pesos deben sumar 1.** Un validador Pydantic exige
  `SCORE_WEIGHT_ML + SCORE_WEIGHT_HEURISTIC == 1.0`. Sin él, una configuración mal escrita
  producía puntuaciones fuera de la escala 0-100 sin avisar.
- **Una sola transacción en la ingesta CRM.** El webhook confirmaba el prospecto antes de
  puntuarlo; si el scoring fallaba, quedaba un prospecto huérfano con puntuación cero. Lo
  comprobé reintroduciendo a propósito el `commit` prematuro: la prueba de atomicidad falló
  con el prospecto huérfano exacto que describe el hallazgo.

---

### 2.3. Fase 3: Pruebas y Pipeline Confiables

**La suite tocaba la base de datos real.** Los tests abrían sesiones contra el motor
configurado —en desarrollo, el SQLite del proyecto— y dependían en silencio de la salida de
`seed_data.py`. Un test podía pasar solo porque otro había dejado datos antes.

El nuevo `conftest.py` fija `DATABASE_URL=sqlite://` **antes** de importar la aplicación y
sustituye la dependencia `get_db`. Cada prueba declara los datos que necesita mediante
*fixtures*. La garantía se verifica, no se asume: tras cada ejecución se comprueba que no
quede ningún fichero `.db` en el árbol.

El detalle del crecimiento de la suite (16 → 428 pruebas) está en el Capítulo 8; el del
pipeline de diez trabajos, en el Capítulo 9.

---

### 2.4. Fase 4: Endurecimiento del Despliegue

Además de lo descrito en el Capítulo 9, esta fase corrigió dos defectos que **solo
aparecieron al construir y arrancar las imágenes de verdad**, no al revisarlas:

#### El *healthcheck* mentía

`/health` devolvía `{"status": "healthy", "database": "connected"}` como constante. Seguía
diciendo que el servicio estaba sano con la base de datos caída, de modo que Docker y
cualquier balanceador mantenían la instancia en rotación. Ahora ejecuta una consulta real y
responde 503 si falla, sin filtrar la cadena de conexión en el mensaje.

#### Nginx dejaba la SPA sin política de seguridad de contenido

Nginx **deja de heredar las directivas `add_header` del bloque padre en cuanto un bloque
hijo declara una propia**. Al añadir `Cache-Control` en `location = /index.html` —el
documento principal de la aplicación—, este quedó sirviéndose sin CSP ni
`X-Frame-Options`. La corrección fue extraer las cabeceras a un fragmento incluido desde
cada bloque.

Es un fallo que ninguna revisión del archivo por separado detecta: cada bloque parecía
correcto por sí mismo.

---

### 2.5. Fase 5: Escalabilidad y Rendimiento

#### El modelo se deserializaba en cada petición

`ScoringService` se construye una vez por petición y pedía a la fábrica un adaptador nuevo,
lo que significaba ejecutar `joblib.load` sobre el artefacto completo **en cada llamada de
scoring**. Medido en el mismo contenedor y contra la misma base:

| | Antes | Después |
| :--- | :---: | :---: |
| Primera llamada a `/scoring/predict` | 501 ms | 238 ms |
| Latencia estabilizada | ~145 ms | **~60 ms** |

Las fábricas se cachean, pero la clave de la caché son los ajustes que deciden qué adaptador
corresponde. Cachear una función sin argumentos habría congelado el primer adaptador
construido y el sistema habría ignorado su propia configuración hasta el siguiente reinicio.

Además, `predict_proba` es cómputo síncrono: llamarlo desde la corrutina retenía el hilo del
bucle de eventos y con él **todas** las peticiones en vuelo, no solo la que estaba
puntuando. Ahora se ejecuta en un hilo aparte.

#### El recálculo masivo no resistía el crecimiento

El endpoint recorría toda la cartera dentro de la petición. Con unos pocos miles de
prospectos, el navegador y el `proxy_read_timeout` de Nginx (60 s) cortaban antes de
terminar, y el trabajo quedaba a medias sin rastro. Se reescribió como tarea en segundo
plano: responde `202 Accepted` con un identificador y el avance se consulta aparte.

El estado del trabajo se guarda **en una tabla**, no en memoria del proceso. La imagen
arranca varios *workers* de Uvicorn: un trabajo iniciado por uno de ellos sería invisible
para el que atendiera después la consulta, y el cliente recibiría un 404 por un trabajo que
sí fue aceptado.

La paginación es por clave (`id > último`) y no por `OFFSET`: con desplazamiento el motor
recorre y descarta las filas anteriores en cada lote —coste cuadrático— y, si alguien
inserta o borra mientras tanto, se saltan o repiten registros.

#### El informe de campañas era un N+1

`get_campaigns_performance` consultaba las campañas y después, al acceder a sus prospectos,
emitía **una consulta adicional por campaña**, materializando cada prospecto entero en
memoria solo para contarlo. Reescrito como agregación SQL única con `LEFT JOIN` —el join
externo es deliberado: una campaña sin captación debe seguir apareciendo con ceros, que es
justo cuando más interesa verla—.

La prueba cuenta las sentencias emitidas. Reintroduciendo el bucle anterior de forma
temporal, la prueba falla con **4 consultas** para 3 campañas y **14** tras añadir 10 más.

#### Verificación de integridad del artefacto de ML

`joblib.load` deserializa con *pickle*, y *pickle* **ejecuta código durante la carga**. La
ruta del artefacto viene de configuración, de modo que quien pueda escribir ahí ejecuta lo
que quiera dentro del proceso del backend, con sus credenciales y su acceso a la base de
datos. Fijando `ML_MODEL_SHA256`, una huella distinta impide la deserialización:

```
HUELLA DEL MODELO NO COINCIDE — el artefacto NO se ha cargado.
Esperada: 000...  Encontrada: 159b2b3a...
```

El sistema continúa operando con el heurístico en lugar de caer. `train_model.py` imprime la
huella al terminar y el pipeline verifica que el artefacto dentro de la imagen sea
exactamente el que validó.

---

## 3. Justificación Técnica

1. **Corregir la causa, no el síntoma.** El artefacto de ML no llegaba a la imagen de
   Docker y el servicio arrancaba en modo degradado sin advertirlo. La corrección no fue
   copiar el archivo, sino cambiar el contexto de construcción y dejar de depender de
   aritmética de rutas relativas al árbol del repositorio.

2. **Fallar de forma ruidosa antes que degradarse en silencio.** Es el criterio que recorre
   toda la fase: una `SECRET_KEY` débil aborta el arranque; un artefacto con huella
   incorrecta no se carga; un modelo por debajo del umbral no sobrescribe al anterior; el
   webhook sin secreto configurado responde 503 en lugar de aceptar cualquier cosa.

3. **Una prueba que no puede fallar no prueba nada.** Cada corrección relevante se validó
   reintroduciendo temporalmente el defecto para confirmar que la prueba lo detecta. Sin ese
   paso, una prueba mal escrita da una falsa sensación de cobertura indefinidamente.

---

## 4. Metodología Aplicada

- **Auditoría por inventario clasificado**, con cada hallazgo identificado y priorizado por
  impacto antes de tocar código.
- **Fases acotadas y verificables**, cada una cerrada con la suite completa en verde antes de
  pasar a la siguiente.
- **Verificación en el entorno real de ejecución.** Los dos defectos de la Fase 4 y los dos
  de la Fase 5 solo se manifestaron al construir las imágenes y arrancar la pila; la revisión
  estática de los archivos no los habría encontrado.

---

## 5. Retos Técnicos Superados

### Reto 1: El arranque multi-*worker* rompía la creación del esquema
**Problema:** La imagen arranca Uvicorn con varios *workers* y cada uno ejecuta la
inicialización. Los dos entraban a la vez, ambos veían la base vacía y el segundo fallaba al
crear un tipo `ENUM` que el primero acababa de crear:
`duplicate key value violates unique constraint "pg_type_typname_nsp_index"`. Uvicorn mataba
entonces al proceso padre y el contenedor entraba en bucle de reinicio: **la pila no llegaba
a levantar**.

**Solución:** Serialicé la sección mediante un *advisory lock* de PostgreSQL. El segundo
*worker* espera, entra cuando el primero termina y su comprobación previa ya encuentra el
esquema hecho. El defecto no era visible en las pruebas —SQLite, un solo proceso— ni en la
construcción de la imagen.

### Reto 2: El límite de tasa no era el declarado
**Problema:** Configurado a 10 intentos por minuto, el corte llegaba al intento 14. La
biblioteca de limitación lleva la cuenta **en memoria de cada proceso**, de modo que con N
*workers* el tope efectivo es N veces el declarado.

**Solución:** Documenté el comportamiento y expuse `RATE_LIMIT_STORAGE_URI` para delegar la
cuenta en un almacén compartido. Es una mitigación con salida, no un arreglo completo: sin
ese almacén el tope sigue frenando la fuerza bruta, pero no es exacto. Prefiero dejarlo
dicho a que alguien confíe en una cifra que el sistema no cumple.

---

## 6. Evidencia y Cierre

| Indicador | Antes de la auditoría | Después |
| :--- | :---: | :---: |
| Pruebas automatizadas | 16 | **335** |
| Cobertura del paquete de aplicación | No medida | **91 %** |
| Trabajos de verificación en CI | 1 | **10** |
| Latencia estabilizada de `/scoring/predict` | ~145 ms | **~60 ms** |
| Consultas del informe de campañas | 1 + N campañas | **1** |
| Servicios en la pila de producción | 4 | **3** |
| Puertos publicados hacia toda la red | 4 | **1** (solo la SPA) |

El sistema se entrega con la identidad derivada de tokens firmados, los secretos fuera del
árbol del proyecto, la documentación de la API cerrada en producción, la imagen ejecutándose
sin privilegios de administrador y un pipeline que se niega a publicar un modelo peor que el
anterior.
