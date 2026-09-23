# Sistema Inteligente de Lead Scoring (Release v1.0.0 - Versión Entregable)

**Empresa Titular:** PluriOne S.A. de C.V.  
**Representante Legal:** Lic. Xochicuahuitl Gleason Juárez  
**Asesor Empresarial:** Juan Méndez Herrera  
**Líder de Proyecto:** Edgar Loheffelmman  
**Alumno Residente:** Alumno de Ingeniería en Sistemas Computacionales  
**Periodo de Ejecución:** Estadía Profesional (2026)  

---

## 🔒 Aviso de Confidencialidad y Propiedad Intelectual

> **CONVENIO DE CONFIDENCIALIDAD Y CESIÓN DE DERECHOS PATRIMONIALES**  
> La totalidad del código fuente, modelos matemáticos, algoritmos de scoring híbrido, diagramas de arquitectura, componentes de software, reportes técnicos y la memoria técnica consolidada son propiedad intelectual y patrimonial exclusiva de **PLURIONE S.A. DE C.V.**
>
> **Anonimización Estricta:** En cumplimiento riguroso con el Secreto Industrial y el Convenio de Confidencialidad, el 100% de los datos, prospectos, empresas y correos electrónicos utilizados en este repositorio corresponden a **datos sintéticos generados probabilísticamente**. No se expone ningún dato sensible, financiero ni de clientes reales de PluriOne.

---

## 🚀 Arquitectura y Tecnologías Clave (Stack Optimizado de Producción)

El sistema fue diseñado bajo el principio de **parsimonia tecnológica y autosuficiencia operativa**. Se depuraron tecnologías redundantes, costosas o poco útiles (como Azure AI Search, llamadas remotas a endpoints de Azure ML, dependencias externas a Azure OpenAI y licencias privativas de Power BI), consolidando una arquitectura autocontenida, de latencia ultrabaja y costo recurrente $0 USD:

- **Motor de Machine Learning Supervisado Nativo:** Algoritmo `GradientBoostingClassifier` con calibración isotónica de probabilidades (`CalibratedClassifierCV`) e inferencia en memoria en menos de 1 ms. Su **ROC-AUC de 0.9469 (IC 95 % [0.928, 0.964]) se mide sobre datos sintéticos**: verifica que el pipeline está íntegro, no el rendimiento comercial. Sobre ese mismo conjunto el heurístico sin modelo alcanza 0.8950 y ordenar por una sola columna alcanza 0.9053, así que **el aporte real del modelo es de +0.052, con IC 95 % [+0.030, +0.076]** — y esa es la cifra que hay que defender (Capítulos 12 y 24). El modelo no recibe datos inventados: los ingresos que no se declararon llegan como ausentes y se imputan con marca, WhatsApp y LinkedIn son variables distintas y el resultado de cada llamada cuenta.
- **Algoritmo Híbrido con Decaimiento Temporal Continuo:**
  $$S_{\text{final}} = 0.60 \times S_{\text{ML}} + 0.40 \times S_{\text{Heurístico}} \times \gamma(\Delta t)$$
  donde $\gamma(\Delta t) = (0.5)^{\frac{\Delta t}{14}}$ modela la pérdida exponencial del interés del prospecto en una vida media de 14 días.
- **Inteligencia Artificial Explicable (XAI) Nativa:** Motor de interpretabilidad analítica que sintetiza fortalezas clave y genera tácticas comerciales recomendadas en tiempo real sin costos por tokens ni latencias externas.
- **Backend RESTful:** FastAPI con Clean Architecture, Pydantic v2 y SQLAlchemy 2.0. Sirve tanto la API y documentación OpenAPI/Swagger como la aplicación web compilada (SPA).
- **Frontend Analítico Empresarial:** React.js con Vite, diseño Glassmorphism, dashboards analíticos de segmentación y embudo, Ficha 360° y simulador de scoring interactivo.
- **Seguridad RBAC:** Control de acceso empresarial basado en roles (`Líder Comercial`, `Administrador TI`, `Asesor Comercial`).
- **DevOps y Empaquetado:** Dockerfiles multi-etapa y Docker Compose listos para despliegue productivo inmediato.

---

> **Calidad en las dos mitades.** 1158 pruebas en el backend (93 % de cobertura) y 302 en
> el cliente (94,6 %), `ruff` y `eslint` sin avisos, y 10 trabajos de integración continua
> con 34 guardas de regresión de configuración peligrosa.

## ⚡ Guía de Inicio Rápido (Despliegue de la Versión Entregable)

### Opción A: Despliegue Unificado con Docker Compose (Recomendado)

El backend arranca con `ENVIRONMENT=production` y **exige** dos secretos propios. La pila se
arranca siempre de un solo modo: con `devops/pila.py`, que envuelve `docker compose` y le pasa
un archivo de entorno que vive **fuera del repositorio** —`~/.plurione/pila.env`, o el que
indique `PLURIONE_ENTORNO`—. Se niega a arrancar si ese archivo está dentro del árbol, si hay
un `.env` suelto en el repositorio que Compose o la aplicación leerían por su cuenta, o si
faltan `SECRET_KEY` o `POSTGRES_PASSWORD` (capítulo 22).

```bash
# Una sola vez: crea el archivo de entorno, con los dos secretos ya generados
python devops/pila.py iniciar

# Aplica el esquema. Es un servicio de un solo disparo: espera a que PostgreSQL esté sano,
# ejecuta `alembic upgrade head` y termina.
python devops/pila.py run --rm migrate

python devops/pila.py up --build -d
```

Todo lo que sigue a `devops/pila.py` es una orden de `docker compose` y se le pasa tal cual.
`python devops/pila.py --comprobar` hace solo las comprobaciones, sin tocar Docker.

Ese `run --rm migrate` es **opcional**: la pila lo ejecuta sola, porque el
backend depende de él con `service_completed_successfully` y no arranca hasta que sale con
código 0. Se muestra aparte porque un despliegue conviene hacerlo en dos tiempos —migrar
y, si eso fue bien, servir— y porque así queda dicho de dónde sale el esquema.

Nada crea tablas al vuelo: en producción el backend **verifica** que la base esté sellada
en la última revisión de Alembic y aborta el arranque si no lo está. Es lo que evita que
una aplicación nueva se ponga a escribir sobre un esquema viejo.

```bash
# Qué revisión tiene la base ahora mismo
python devops/pila.py run --rm migrate alembic current

# Historial y hacia dónde va
python devops/pila.py run --rm migrate alembic history --indicate-current
```

El sistema queda disponible en [http://localhost:3000](http://localhost:3000). Esa es la
puerta de entrada: nginx sirve la SPA, añade las cabeceras de seguridad y hace de pasarela
hacia la API.

Lo que la pila **no** publica, y antes sí:

| | Antes | Ahora |
| :--- | :--- | :--- |
| PostgreSQL | `0.0.0.0:5432` | Solo dentro de la red de la pila |
| pgAdmin | `0.0.0.0:5050`, con `admin`/`admin` en el YAML | Fuera del stack; overlay aparte con credenciales propias |
| API del backend | `0.0.0.0:8000` | `127.0.0.1:8000` (el acceso público entra por nginx) |
| Redis (contador de tasa) | No existía; la cuenta vivía en la memoria de cada worker | Servicio propio de la pila, sin puerto publicado |
| `/docs`, `/redoc`, OpenAPI | Abiertos | Deshabilitados con `ENVIRONMENT=production` |

Para inspeccionar la base de datos durante el desarrollo:

```bash
# Consola psql dentro del contenedor, sin publicar ningún puerto
python devops/pila.py exec postgres psql -U plurione -d lead_scoring_db

# O levantar pgAdmin y el puerto 5432, ambos limitados a 127.0.0.1.
# Exige PGADMIN_EMAIL y PGADMIN_PASSWORD en el archivo de entorno de la pila.
python devops/pila.py --dev up -d
```

---

### Opción B: Ejecución Inmediata en Producción (Local)

#### 1. Instalar Dependencias
```bash
# Ejecución: exactamente lo que lleva la imagen, con la huella de cada fichero
pip install --require-hashes -r backend/requirements.lock

# Desarrollo y pruebas: lo anterior en las mismas versiones, más pytest, ruff y pip-audit
pip install --require-hashes -r backend/requirements-dev.lock

# ¿Lo instalado es lo fijado? Sale con 1 y dice qué paquete difiere
python scripts/comprobar_instalado.py backend/requirements-dev.lock
```

`requirements.txt` dice qué versiones son **aceptables**; los `.lock` dicen cuáles se
**instalan**, con la huella SHA-256 de cada fichero. La imagen, el CI y el entrenamiento
del modelo instalan desde los locks: dos construcciones separadas por meses llevan lo mismo,
y un paquete sustituido en el índice no entra. Para cambiar una dependencia se edita el
`.txt` y se regeneran los dos, desde `backend/`:

```bash
cd backend
python -m uv pip compile requirements.txt --universal --python-version 3.13 --generate-hashes -o requirements.lock
python -m uv pip compile requirements-dev.txt --universal --python-version 3.13 --generate-hashes -c requirements.lock -o requirements-dev.lock
```

`--universal` resuelve para todas las plataformas a la vez y deja los marcadores escritos:
un lock generado en Windows sin él no llevaría `uvloop`, que la imagen Linux sí instala. El
de desarrollo se compila **con el de producción como restricción**, para que la suite corra
sobre las mismas versiones que la imagen.

#### 2. Crear el Esquema con Alembic

Sin Compose no hay servicio `migrate`, así que las migraciones se aplican a mano **antes**
de sembrar nada. El sembrado escribe en tablas que todavía no existen si se salta este paso.

```bash
# `DATABASE_URL` fuera del árbol: ni el .env ni la base viven en el repositorio.
export DATABASE_URL="sqlite:///C:/Users/<usuario>/Desktop/Resi/_lead_scoring_local/lead_scoring.db"
python -m alembic upgrade head
```

#### 3. Entrenar Modelo y Sembrar Base de Datos
```bash
# Entrenar pipeline supervisado calibrado. Genera lead_scorer_model.joblib, el perfil
# de referencia para el monitoreo de deriva y una entrada en el registro de modelos.
# Falla —y NO sobrescribe el artefacto anterior— si el ROC-AUC cae bajo 0.82 o si el
# modelo deja de aportar sobre el heurístico.
python ml_pipeline/src/train_model.py

# Poblar base de datos con prospectos sintéticos.
# El script VACÍA las tablas de negocio antes de regenerarlas: si la base ya tiene
# datos, aborta y enumera lo que borraría. Añada --force para confirmarlo.
python backend/scripts/seed_data.py

# En producción o staging el sembrado de demostración está prohibido. Para crear o
# restablecer solo las cuentas de acceso, sin tocar ningún dato:
python backend/scripts/seed_data.py --solo-usuarios

# Dejar la pila lista para sentar a alguien delante: siembra lo anterior y añade una
# publicación de ejemplo con perfiles ya recibidos por su enlace público, para que haya
# algo que comparar. Copia la base antes de vaciarla e imprime enlaces y cuentas.
python scripts/preparar_prueba_con_personas.py --force
```

El guion por rol y la hoja para anotar dónde se atasca cada persona están en
[docs/Prueba_Con_Personas.md](docs/Prueba_Con_Personas.md).

#### 4. Observabilidad del Modelo
```bash
# ¿Se siguen pareciendo los prospectos de hoy a los del entrenamiento?
# Compara las instantáneas de variables registradas en producción contra el perfil de
# referencia mediante el índice PSI, e informa además de qué motor puntuó cada caso.
python ml_pipeline/src/drift_monitor.py

# Dataset etiquetado con desenlaces comerciales reales (WON/LOST), para reentrenar.
# Exige un mínimo de ejemplos: por debajo de él, se niega a generarlo y explica por qué.
python ml_pipeline/src/feedback_dataset.py
```

En la pila de Compose, PostgreSQL no publica puerto hacia el host, así que el monitor se
ejecuta desde el propio contenedor, donde viaja incluido:

```bash
python devops/pila.py exec backend python /app/observabilidad/drift_monitor.py
```

Sus umbrales y sus límites —incluido el hecho de que el perfil de referencia se construye
sobre datos sintéticos— están en el Capítulo 13 de la memoria.

### El monitor de deriva corre solo, y avisa

Lo anterior es la consulta manual. Un monitor que hay que acordarse de lanzar detecta la
deriva el día que a alguien se le ocurre mirar, que suele ser el día después de que
importara. El servicio `monitor-deriva` de la pila lo ejecuta en bucle:

| Variable | Por defecto | Qué hace |
| :--- | :--- | :--- |
| `ML_DRIFT_INTERVALO_S` | `21600` (6 h) | Cada cuánto reevaluar |
| `ML_DRIFT_SILENCIO_S` | `21600` (6 h) | Cuánto callar antes de repetir un aviso vigente |
| `ML_DRIFT_WEBHOOK` | *(vacío)* | A dónde entregar la alerta, además de al registro |

La alerta sale como un objeto JSON en una línea, con el mismo formato que el resto del
registro del sistema:

```
[ALERTA-DERIVA] {"evento":"deriva_de_variables","tipo":"deriva","veredicto":"deriva significativa",
                 "columnas_con_deriva":["source_channel"],"psi":{"source_channel":0.41}, ...}
```

Y **se repite lo justo**. La deriva de población dura semanas; avisar en cada ciclo produce
decenas de mensajes idénticos sobre una condición que no ha cambiado, quien los recibe crea
un filtro, y a partir de ahí el sistema tiene monitorización y no tiene aviso —que es peor
que el punto de partida, porque además parece resuelto—. Se reavisa cuando **cambia el
conjunto de columnas afectadas** o cuando pasa el periodo de silencio, y se avisa también
de la vuelta a la normalidad, que si no nadie sabe cuándo terminó. El estado vive en un
volumen y no en `tmpfs`: en `tmpfs`, cada reinicio del contenedor olvidaría que ya avisó.

Corre en la pila y no en integración continua porque lo que hay que comparar contra el
perfil son las instantáneas que produjo **esa** base al puntuar prospectos reales. CI no
las tiene ni debe tenerlas; un trabajo programado en el pipeline daría la sensación de
vigilancia sin ninguna.

### El modelo, atado a los datos que lo produjeron

El registro de modelos guarda una entrada por entrenamiento, y desde N-15 esa entrada
**no puede escribirse sin la huella SHA-256 del conjunto que lo entrenó**:

```bash
python - <<'PY'
import json, sys; sys.path.insert(0, "ml_pipeline/src")
from model_registry import entrada_de_artefacto
sha = json.load(open("ml_pipeline/models/metrics.json", encoding="utf-8"))["model_sha256"]
print(entrada_de_artefacto(sha))
PY
```

El campo existía desde la fase 8 y valía `null` en todas las entradas: el parámetro era
opcional y `train_model.py` llamaba sin él. El registro declaraba una trazabilidad que no
tenía, y la pregunta «¿con qué datos se entrenó el modelo que puntuó a este prospecto?»
seguía sin respuesta, con el agravante de parecer contestada. Ahora la llamada falla sin
huella, el origen se **declara** en vez de deducirse —la deducción anterior, `sinteticos si
no hay huella`, se vuelve falsa justo al hacerla obligatoria— y el pipeline **recalcula** la
huella desde el CSV y exige que coincida: un valor constante también dejaría el campo
distinto de `null`.

### El perfil de referencia sabe de qué modelo es

El monitor mide cuánto se aleja producción de la población con la que se entrenó **el modelo
que está puntuando**. Contra el perfil de otro entrenamiento el PSI sigue saliendo, con el
mismo aspecto, y deja de significar lo que dice. Perfil y `.joblib` viajan juntos en la
imagen y salen del mismo `train_model.py`, pero hasta la Fase 13 nada lo dejaba escrito ni
lo comprobaba.

Ahora el perfil lleva la huella del artefacto (`model_sha256`) y la de los datos, y el
monitor la comprueba **antes de leer una sola instantánea**:

```
[DERIVA] No se evalua. El perfil de referencia salio del artefacto 0a2632a2f496 y el que
         esta desplegado es 7c1e90b3d2aa. Se compararia produccion contra la poblacion de
         otro modelo, y los PSI no significarian lo que dicen.
```

Sale con código **1** —«no se pudo evaluar»—, no con el 2 de la deriva: no es una señal del
negocio, es un despliegue roto. Un perfil sin huella se rechaza también en lugar de darse
por bueno: es exactamente el caso que hay que obligar a regenerar.

### Reentrenar con desenlaces reales

```bash
# 1. Exportar los prospectos que llegaron a WON / LOST / UNQUALIFIED, etiquetados sobre la
#    instantánea de variables del momento en que ENTRARON al embudo.
python devops/pila.py exec backend python /app/observabilidad/feedback_dataset.py \
    --salida /tmp/leads_reales.csv

# 2. Medir contra ellos. NO publica: mide.
python ml_pipeline/src/train_model.py --datos realimentacion --dataset leads_reales.csv

# 3. Pedir la publicación. Solo se publica si el LÍMITE INFERIOR del IC 95 % del ROC-AUC
#    alcanza el umbral y el del APORTE sobre el heurístico alcanza el mínimo; si no, no
#    escribe el artefacto y sale con código 1.
python ml_pipeline/src/train_model.py --datos realimentacion --dataset leads_reales.csv --publicar
```

Medir y publicar están separados a propósito. El primer dataset de realimentación tiene
decenas de filas, no miles, y con un conjunto de prueba pequeño el ROC-AUC sale alto por
azar con facilidad: en el ensayo, 45 desenlaces dieron **0.8889 con un intervalo de
confianza del 95 % de [0.571, 1.000]** —superando los dos umbrales del pipeline—, mientras
260 dieron **0.8917 con [0.800, 0.968]**. Casi la misma estimación puntual y un valor
probatorio completamente distinto. Por eso el intervalo se calcula siempre y por eso
publicar es un acto deliberado.

Y desde la Fase 13 no depende de que quien lo pide haya mirado la tabla: `--publicar` exige
que el **límite inferior** del intervalo alcance el umbral de 0.82. Con ese criterio no se
habría publicado ninguna de las dos cohortes del ensayo, tampoco la de 260, cuyo límite
inferior se queda en 0.800. Con los datos sintéticos queda en 0.928 y la condición no cuesta
nada: solo muerde donde tiene que morder.

Desde el capítulo 24 lo mismo vale para el **aporte sobre el heurístico**, que antes se exigía
con la estimación puntual. Se mide con un bootstrap pareado —las mismas filas para el modelo
y para la regla en cada réplica— y su límite inferior tiene que alcanzar +0.01. Muerde antes
que el del ROC-AUC: una cohorte sintética de 1000 prospectos da un aporte de +0.028 con
intervalo [-0.002, +0.059] y no se publica, aunque su ROC-AUC tenga el límite inferior en
0.91. Y el ensayo del bucle, con 12 ejemplos de prueba, se queda fuera por el aporte
([-0.100, +0.222]) antes de llegar a nada más.

Las instantáneas llevan `version_del_vector`. Las anteriores al capítulo 24 no dicen qué
mensajes eran de LinkedIn ni cuántas llamadas quedaron sin respuesta, así que el dataset
real y el monitor de deriva las **descartan y las cuentan** en lugar de traducirlas.

**Hoy el bucle no tiene datos**: en la base no hay ningún prospecto en estado terminal.
Para que el camino no se pudra hasta que los haya, el pipeline lo recorre entero en cada
ejecución sobre una base desechable:

```bash
python ml_pipeline/src/ensayo_del_bucle.py --tamano 60 --entrenar
```

No mide el negocio —las etiquetas son sintéticas— y no toca nada del despliegue: artefacto,
perfil y registro de producción quedan intactos.

---

## 🔐 Autenticación y Control de Acceso

El sistema exige inicio de sesión: **todos** los endpoints de datos requieren un JWT
firmado por el backend (HS256 con `SECRET_KEY`). Las cabeceras `X-User-Role` /
`X-Entra-User-Role` ya no se leen — cualquiera podía declararse administrador con ellas.

| Pieza | Dónde vive | Vigencia |
| :--- | :--- | :--- |
| **Access token** | Solo en memoria del navegador (nunca en `localStorage`) | 15 minutos |
| **Refresh token** | Cookie `HttpOnly`, `SameSite=Strict`, limitada a `/api/v1/auth` | 7 días |

El frontend renueva el access token de forma transparente. La renovación **rota** el token
de refresco: cada emisión queda registrada con un identificador propio (`jti`) y una
*familia* común a toda la sesión, y refrescar consume el token presentado.

Presentar un token ya consumido solo puede significar que dos partes tienen la misma
cookie. Como no hay forma de saber cuál es la legítima, se revoca **la familia entera** y
ambas vuelven a iniciar sesión; el incidente queda en la bitácora de auditoría. Antes esto
no ocurría: se entregaba una cookie nueva y la anterior seguía valiendo hasta expirar, de
modo que una cookie robada daba siete días de acceso renovable sin dejar rastro.

Dos matices, porque conviene decirlos:

- Hay una **ventana de gracia de 10 segundos** (`REFRESH_ROTATION_GRACE_SECONDS`) para el
  caso honesto de dos pestañas refrescando a la vez. Sin ella, un usuario con varias
  pestañas perdería la sesión sin haber hecho nada.
- Los **access tokens ya emitidos también se revocan al instante** (capítulo 23). Llevan
  `ver`, la `token_version` de la cuenta al emitirse, y la resolución de identidad —que ya
  leía la cuenta en cada petición— la compara sin ninguna consulta más. Antes seguían
  valiendo sus 15 minutos: un token robado sobrevivía al logout de su víctima.

Al cerrar sesión se revocan todas las familias vivas **y** se incrementa `token_version`,
que cierra la sesión en todos los dispositivos a la vez. Lo mismo ocurre al cambiar o
restablecer la contraseña, al cambiar el rol y al desactivar la cuenta.

Los JWT se firman y verifican con **PyJWT**, solo HMAC, exigiendo `exp`, `iat`, `nbf`,
`iss`, `aud`, `sub` y `jti`. python-jose salió del proyecto porque arrastraba `ecdsa`, con un
aviso sin arreglo que `pip-audit` tenía que ignorar; ahora la auditoría no ignora ninguno.

**Contraseñas filtradas.** La política rechaza, además, las que aparecen en filtraciones
públicas, con una lista **local** de 46 825 entradas dentro de la imagen
(`backend/app/core/datos/`). No se consulta ningún servicio externo. Se comprueba en el
alta, en el cambio propio y en el restablecimiento; la huella del archivo está en su
manifiesto, y una lista vaciada o sustituida no se usa en silencio.

### Cuentas sembradas

`seed_data.py` crea tres cuentas, una por rol. Sus contraseñas salen de
`SEED_ADMIN_PASSWORD`, `SEED_SALES_LEAD_PASSWORD` y `SEED_EXECUTIVE_PASSWORD`. Si no
define esas variables **fuera de producción**, se usa la contraseña de desarrollo
`PluriOne2026!`; en `production`/`staging` se genera una aleatoria y se imprime una sola
vez en la salida del script.

`seed_data.py` crea además cuatro cuentas de asesor comercial (`carlos.morales@`,
`ana.ruiz@`, `valeria.mendoza@` y `diego.herrera@`), que antes vivían en una tabla
`sales_reps` aparte y no podían iniciar sesión. Su contraseña sale de
`SEED_ASESOR_PASSWORD`.

| Correo | Rol | Puede |
| :--- | :--- | :--- |
| `admin.ti@plurione.com` | System_Admin | Todo, incluida la gestión de cuentas y la bitácora |
| `lider.ventas@plurione.com` | Sales_Lead | Cartera completa, campañas, borrado y recálculo masivo |
| `asesor.comercial@plurione.com` | Commercial_Executive | **Solo su propia cartera**: consulta, alta, edición y actividades |

### Alcance sobre el dato

El rol decide qué operaciones puede invocar cada persona. **De qué prospectos** lo decide la
asignación:

| | `Commercial_Executive` | `Sales_Lead` y `System_Admin` |
| :--- | :--- | :--- |
| Ver y buscar prospectos | Solo los asignados a él | Toda la cartera |
| `total` del listado y KPIs de `/analytics/summary` | Contados sobre su cartera | Sobre toda |
| Editar un prospecto | Solo los suyos | Cualquiera |
| Reasignar (`assigned_rep_id`) | No (403) | Sí |
| Borrar un prospecto | No (403) | Sí |
| `/analytics/campaigns` | No (403) | Sí |

Un prospecto que existe pero pertenece a otra persona responde **404**, indistinguible de uno
inexistente: un 403 confirmaría que ese identificador está ocupado, y recorrer identificadores
dibujaría el tamaño de la cartera ajena sin ver un solo dato. La diferencia sí queda
registrada en la bitácora, como `acceso.fuera_de_alcance`.

El filtro se aplica **en el repositorio**, no en cada endpoint: `LeadRepository` exige el
alcance como argumento obligatorio, así que un endpoint nuevo que se olvide de pasarlo falla
con un `TypeError` en lugar de devolver datos de más en silencio.

### Gestión de cuentas

| Endpoint | Quién | Qué hace |
| :--- | :--- | :--- |
| `GET/POST /api/v1/users` | `System_Admin` | Listado y alta |
| `PUT /api/v1/users/{id}` | `System_Admin` | Nombre, rol, actividad, marca de asesor, capacidad |
| `POST /api/v1/users/{id}/role` | `System_Admin` | Cambio de rol con asiento propio; cierra sus sesiones |
| `DELETE /api/v1/users/{id}` | `System_Admin` | **Baja lógica**: no borra la fila |
| `POST /api/v1/users/{id}/activate` | `System_Admin` | Reactiva; exige cambiar la contraseña |
| `POST /api/v1/users/{id}/reset-password` | `System_Admin` | Fija contraseña y revoca sesiones |
| `GET /api/v1/sales-reps` | `Sales_Lead`, `System_Admin` | Equipo comercial con su carga, en una consulta; cuenta siempre los prospectos que siguen en cuentas de baja |
| `POST /api/v1/sales-reps/{id}/cartera` | `Sales_Lead`, `System_Admin` | Traspasa todos los prospectos de una cuenta a un asesor activo; avisa si supera su capacidad |
| `GET /api/v1/eventos-sin-asociar` | `Sales_Lead`, `System_Admin` | Bandeja de avisos de integraciones que no pertenecen a ninguna ficha |
| `POST /api/v1/eventos-sin-asociar/{id}/vincular` | `Sales_Lead`, `System_Admin` | Convierte el aviso en actividad del prospecto elegido; conserva su fuente y su verificación |
| `DELETE /api/v1/eventos-sin-asociar/{id}` | `Sales_Lead`, `System_Admin` | Descarta el aviso; en la bitácora quedan su fuente y su tipo |
| `GET /api/v1/campaigns` | Cualquier rol | Campañas de captación; `?canal=LinkedIn` da las publicaciones |
| `POST/PUT/DELETE /api/v1/campaigns` | `Sales_Lead`, `System_Admin` | Alta, edición, estado (`borrador`, `activa`, `pausada`, `cerrada`) y cierre (`DELETE`) |
| `POST /api/v1/campaigns/{id}/duplicar` | `Sales_Lead`, `System_Admin` | Copia en borrador con enlace propio |
| `GET /api/v1/publicaciones/{id}/informe` | Cualquier rol | Perfiles que trajo una publicación; el asesor ve los suyos y **un número** con el resto; visitas, tasa de envío y perfiles por día |
| `GET /api/v1/publicaciones/{id}/vista-previa` | Cualquier rol | La página de interés tal como la verá el interesado, en cualquier estado y sin contar visita |
| `GET /api/v1/publicaciones/comparativa` | `Sales_Lead`, `System_Admin` | Perfiles, score medio y avances de cada publicación |
| `GET /api/v1/publicaciones/nuevos-sin-asesor` | `Sales_Lead`, `System_Admin` | Cuántos prospectos de LinkedIn siguen sin asignar |
| `GET /api/v1/interes/{slug}` | **Sin sesión** | La publicación y las listas del formulario |
| `POST /api/v1/interes/{slug}` | **Sin sesión** | Solicitud de contacto de la página de interés |

**Publicaciones.** Una publicación de LinkedIn es una campaña con canal `LinkedIn`, no una
entidad aparte. Tiene descripción, a quién va dirigida y un enlace público
`<PUBLICACIONES_URL_BASE>/<public_slug>`. El slug lo genera el servidor con 128 bits de azar,
ninguna edición lo cambia y el índice único impide que otra campaña lo lleve. La respuesta
trae `enlace_publico` y `texto_para_linkedin` (descripción + enlace), que es lo que copia el
botón «Copiar texto para LinkedIn» de la pestaña «Publicaciones». El asesor la consulta; el
líder y el administrador la gestionan.

Desde el capítulo 26 una publicación tiene además:

* **estado**: borrador, activa, pausada o cerrada; solo la activa sirve su página;
* **fecha de cierre**, que la cierra sola sin tarea programada, la primera vez que alguien
  mira;
* **asesor responsable**, que recibe solo las fichas nuevas y, si deja de ser asesor activo,
  deja de recibirlas;
* sus propias **opciones de «¿Qué necesitas?»**, de 2 a 5, que siguen sin puntuar;
* la **dirección del post** publicado, comprobada como de linkedin.com por el nombre de la
  máquina.

Se puede **duplicar** (sale en borrador, con enlace propio) y ver en dos **vistas previas**:

* el post como en LinkedIn, con su corte de «ver más» y el aviso a 3 000 caracteres;
* la página tal como la verá el interesado, en cualquier estado y sin contar visita.

La página cuenta **visitas**: un número por día, sin cookies ni datos de quien mira. El
informe da con ellas la tasa de envío y un gráfico de perfiles recibidos por día.

Desde el capítulo 27 la misma publicación se difunde por **varias redes**: LinkedIn,
WhatsApp, Facebook y correo vienen activadas; Instagram y X se activan si se quieren. Cada
red tiene **su propio enlace a la misma página** (`?r=whatsapp`) y su propio texto, recortado
a lo que cabe —X a 280 contando el enlace, WhatsApp y correo más cortos—, sin recortar nunca
el enlace.

Los botones «Compartir en…» abren la **dirección pública de compartir** de cada red: sin
API, sin cuentas y sin claves; publica quien pulsa, con su sesión. Donde la red solo se lleva
el enlace (LinkedIn, Facebook) o no tiene forma de compartir desde la web (Instagram), al
lado va «Copiar texto». Hay además un **código QR** descargable del enlace, generado en el
navegador, para Instagram y para material impreso.

Por dónde llegó cada persona queda registrado: en la actividad, en la ficha 360 («Llegó por
la publicación X, vía WhatsApp») y como **canal** de la ficha. Una red desconocida o
manipulada en el enlace se registra como «sin red» y **nunca** rechaza el envío. Ninguno de
esos canales lo conoce el modelo, así que todos son neutros, igual que «LinkedIn». El informe
añade una **fila por red** con visitas, envíos, tasa, perfiles y score medio.

**Página de interés.** El enlace lleva a `/interes/<slug>`, la única pantalla sin sesión.
Muestra el título y el texto de la publicación y un formulario de listas cerradas: cargo,
sector y tamaño son **las listas del modelo** (`CATEGORIAS_DEL_MODELO`), porque el
preprocesador descarta en silencio las categorías que no vio al entrenar. No hay texto libre,
el aviso de privacidad es obligatorio, teléfono y perfil de LinkedIn son opcionales y la
facturación no se pregunta: `annual_revenue` queda vacío. Es una ruta propia y no un conector firmado: un navegador no puede guardar un
secreto HMAC. Se defiende con límite por IP y por publicación, campo trampa, validación
estricta, «no disponible» cuando la publicación no existe o está desactivada, y **la misma
respuesta exista o no el correo**, para que no sirva para averiguar quién está en la base.
Por dentro usa `registrar_evento`: si el correo ya existe, la solicitud se suma al historial
y **no pisa** los datos de la ficha. El prospecto llega atribuido a su publicación, sin asesor
y con canal `LinkedIn`, que el listado marca como «Nuevo desde LinkedIn».

**Informe por publicación.** `GET /api/v1/publicaciones/{id}/informe` responde con tres
números —perfiles recibidos, cuántos avanzaron de etapa (salieron de `NEW`) y score medio— y
la tabla ordenada por score: nombre, empresa, cargo, qué necesita (de su última solicitud; no
puntúa), score, etapa, asesor y fecha, filtrable
por etapa y por días. Entra en el informe tanto quien está **atribuido** a la campaña
(`leads.campaign_id`) como quien **envió su perfil** por su enlace: `campaign_id` se fija al
crear la ficha y no se vuelve a tocar, así que sin lo segundo una persona que responde a tres
publicaciones contaría solo en la primera. Los números son los de quien pregunta: un asesor
ve sus prospectos y `de_otros_asesores` dice cuántos más hay **sin un solo nombre**; el líder
y el administrador ven la publicación entera. Una campaña de otro canal responde 404, igual
que una inexistente; una publicación desactivada **sí** conserva su informe, porque se
desactiva para dejar de recibir perfiles, no para borrar los que trajo. Cada consulta queda en
la bitácora como `publicacion.informe` con sus filtros y el número de filas, nunca con las
filas. La comparativa (`publicacion.comparativa`) no se acota por cartera —comparar
publicaciones con la cartera de una sola persona ordenaría asesores, no publicaciones— y por
eso es de dirección.

**Ficha 360.** `GET /api/v1/leads/{id}` trae `llego_por` cuando la persona llegó por una
publicación: su perfil de LinkedIn y una fila por solicitud, con la publicación, su enlace, la
fecha, qué necesita y cuándo aceptó el aviso de privacidad. Si no hubo solicitudes el campo es
`null` y la ficha no pinta la tarjeta; el perfil va en la tarjeta y no en cada fila porque es
de la persona y la ficha guarda el primero que llegó.

Ni las cuentas ni las campañas se borran: se desactivan. Borrar una cuenta dejaría sin sujeto
sus asientos de auditoría; borrar una campaña pondría a `NULL` la atribución de cada prospecto
que atrajo. Toda mutación queda en la bitácora.

Un administrador **no puede degradarse ni desactivarse a sí mismo**, ni dejar el sistema sin
ninguna cuenta de administración activa: la comprobación cuenta cuántas quedarían.

### Contraseñas

- Mínimo **12 caracteres**; a partir de 16 no se exige variedad, por debajo hacen falta 3 de
  los 4 tipos (minúscula, mayúscula, dígito, símbolo). Se prefiere una frase larga a una
  palabra corta con símbolos: `Verano2026!` cumple las cuatro reglas clásicas y es de las
  primeras que prueba un diccionario.
- Máximo **72 bytes** (no caracteres): bcrypt trunca ahí en silencio.
- Se rechazan las contraseñas conocidas, el nombre del producto y el propio nombre o correo.
- El rechazo devuelve **todos** los motivos, no el primero.
- `POST /api/v1/auth/change-password` cambia la propia. Exige la contraseña actual aunque la
  sesión esté autenticada —si bastara el token, robar una sesión de 15 minutos bastaría para
  quedarse con la cuenta— y **cierra todas las sesiones, incluida la que hizo el cambio**.
- Una cuenta con **contraseña prestada** —creada, restablecida o reactivada por un
  administrador— no opera hasta cambiarla. El servidor responde `403` con
  `{"codigo": "cambio_de_contrasena_obligatorio"}` a todo salvo `GET /auth/me`,
  `POST /auth/change-password` y `POST /auth/logout`, y el cliente la lleva directamente a
  cambiarla. El bloqueo vive en la dependencia de identidad por defecto: un endpoint nuevo
  nace cerrado para estas cuentas sin que nadie tenga que acordarse.
- No hay caducidad por tiempo: forzar cambios periódicos empuja a rotar un sufijo.

### Webhook CRM

`POST /api/v1/crm/webhook` exige firma HMAC-SHA256 sobre `<timestamp>.<cuerpo crudo>`:

- `X-PluriOne-Signature`: el HMAC en hexadecimal, con `CRM_WEBHOOK_SECRET` como clave.
- `X-PluriOne-Timestamp`: epoch en segundos; se rechaza fuera de ±300 s (anti-replay).
- El cuerpo se limita a 256 KiB.

Si `CRM_WEBHOOK_SECRET` está vacío, el endpoint responde **503** en lugar de aceptar
tráfico anónimo.

La firma autentica el cuerpo, pero **no acredita que la petición sea nueva**: reenviar una
entrega capturada dentro de la ventana de tolerancia volvía a pasar todas las
comprobaciones, porque es la misma petición. Cada entrega atendida queda ahora registrada,
y se distingue un reenvío de un reintento:

| Qué llega | Respuesta |
| :--- | :--- |
| Los mismos bytes con la misma firma | **409** — ningún emisor honesto reenvía con la misma marca de tiempo |
| El mismo evento con firma nueva (reintento del CRM) | **200 con la respuesta original** y la cabecera `X-PluriOne-Idempotent-Replay: true` |

La ventana se controla con `CRM_IDEMPOTENCY_WINDOW_SECONDS` (900 s por defecto). Pasada
esa ventana la marca de tiempo original ya no supera la comprobación anti-replay, así que
las entradas caducadas se purgan solas.

### Registro de actividad e integraciones

Toda actividad —la que declara un asesor desde la ficha, la que registra el cambio de etapa,
la del webhook CRM y la de los conectores— pasa por `registrar_evento()`
(`backend/app/services/registro_de_actividad.py`) y por nada más. Cada fila dice de dónde
viene:

| Campo | Qué dice |
| :--- | :--- |
| `source` | `manual`, `pipeline`, `crm`, `formulario_web`, `linkedin_lead_gen`, `calendly` o `whatsapp` |
| `verificada` | Si lo vio un sistema o lo declaró una persona |
| `external_event_id` | El identificador de origen; `(source, external_event_id)` es único para siempre |
| `occurred_at` / `created_at` | Cuándo ocurrió / cuándo se registró |

Reglas iguales para todas las fuentes:

- Un tipo desconocido o ausente responde **422** con el motivo, nunca un `FORM_SUBMIT` por defecto.
- Una llamada lleva su resultado (`CONECTO`, `NO_CONTESTO`, `BUZON`) y solo la que conectó
  cuenta como conversación. Un mensaje lleva su dirección y no admite notas.
- La propuesta enviada y la reunión agendada no se declaran: las registra el cambio de etapa.
- Los teléfonos se guardan en E.164; lo que no es un número responde 422.
- Un correo desconocido crea ficha solo si la fuente genera prospectos (formularios, LinkedIn
  Lead Gen, CRM). El resto espera en la bandeja **«Sin asociar»**.
- Lo que no llega queda vacío y puntúa neutro: ni industria ni tamaño inventados.
- Del mensaje no se guarda el texto: solo tipo, dirección, fecha e identificador.

Las integraciones entran por `POST /api/v1/integraciones/{nombre}/eventos` (`calendly`,
`whatsapp`, `linkedin-lead-gen`, `formulario-web`), firmadas con el mismo esquema HMAC que el
CRM. Cada una tiene su interruptor, su secreto y su límite, y ninguno se comparte:

```bash
INTEGRACION_CALENDLY_ACTIVA=true
INTEGRACION_CALENDLY_SECRETO=<secreto compartido solo con Calendly>
INTEGRACION_CALENDLY_LIMITE=60/minute
```

Están apagadas por defecto, y una apagada responde 404 igual que una que no existe. Revocar
una —vaciar su secreto o apagarla— no toca a las demás. El CRM conserva `CRM_WEBHOOK_SECRET` y
gana `INTEGRACION_CRM_ACTIVA`. Las formas de carga que aceptan los conectores, y lo que falta
para conectar un proveedor real, están en el capítulo 21.


#### 4. Iniciar Servidor de Producción Entregable (1 solo comando)
Al contar con el frontend previamente compilado en `frontend/dist`, FastAPI sirve tanto la aplicación web como los endpoints:
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
> Ingresa a tu navegador en: **[http://localhost:8000](http://localhost:8000)**. La aplicación pedirá
> credenciales: usa una de las cuentas sembradas (ver *Autenticación y Control de Acceso*).

*(Si deseas ejecutar el frontend en modo hot-reload de desarrollo: `cd frontend && npm run dev` en el puerto 3000).*

---

## 📥 Cómo llegan los prospectos

Un prospecto entra por uno de cinco caminos. Todos terminan en el mismo sitio —
`registrar_evento`, la única pieza que escribe actividades— y se puntúan al llegar; lo que
cambia es quién lo manda, si puede crear la ficha, si puede reescribirla y si queda atribuido
a una campaña.

| Camino | Quién lo manda | ¿Crea la ficha? | Si el correo ya existe | Campaña | Asesor |
| :--- | :--- | :-: | :--- | :-: | :--- |
| **Página de interés** `/interes/<enlace>` | La persona, desde el enlace de una publicación | Sí | Suma la solicitud al historial y **no pisa** la ficha | La publicación | Ninguno: lo reparte el líder |
| **Alta en el panel** | Un asesor o el líder | Sí | Rechaza el alta (el correo es único) | La que se indique | El asesor que la crea; el líder elige |
| **CRM** `POST /api/v1/crm/webhook` | El CRM, con firma HMAC | Sí | Actualiza cargo, empresa, sector, tamaño e ingresos | Ninguna | Automático solo si sale `HOT` |
| **Formulario web y LinkedIn Lead Gen** `POST /api/v1/integraciones/<nombre>/eventos` | Cada sistema, con su propio secreto y su interruptor | Sí | Igual que el CRM | Ninguna | Automático solo si sale `HOT` |
| **Calendly y WhatsApp** (mismas rutas) | Cada sistema, firmado | **No** | Suman reunión o mensaje a la ficha | — | — |

Lo que no se puede atribuir a ninguna ficha —una reunión de Calendly con un correo que no
existe— no se descarta ni crea una ficha a medias: va a la bandeja «Sin asociar», donde el líder
lo vincula o lo descarta.

### La historia que se enseña: del post de LinkedIn al prospecto puntuado

1. **Marketing crea la publicación** en la pestaña «Publicaciones»: una campaña con canal
   `LinkedIn`, su texto y a quién va dirigida. El servidor le da un enlace propio de 128 bits
   que nadie puede elegir, cambiar ni reutilizar.
2. **Copia el texto para LinkedIn**: la descripción y el enlace, ya juntos.
3. **La persona abre el enlace** —en el teléfono, normalmente— y deja sus datos en un
   formulario de unos treinta segundos, sin texto libre. Solo son obligatorios nombre,
   correo, empresa, cargo, tamaño y sector (las listas que conoce el modelo), «¿Qué
   necesitas?» con botones de un toque y el aviso de privacidad. El teléfono y el perfil de
   LinkedIn van plegados bajo «Añadir más datos», y la facturación no se pregunta.
4. **El sistema crea la ficha puntuada**, atribuida a la publicación, sin asesor y marcada
   «Nuevo desde LinkedIn».
5. **El líder la ve** en el contador «Nuevos desde LinkedIn sin asesor», la abre y se la
   asigna a un asesor desde la propia ficha. El asesor la encuentra con la tarjeta «Llegó
   por»: de qué publicación, qué necesita, cuándo aceptó el aviso y su perfil de LinkedIn.
6. **El líder compara publicaciones**: perfiles recibidos, cuántos avanzaron de etapa y score
   medio de cada una, y el informe de cada publicación con sus perfiles por score.

El guion completo, con las reglas que lo gobiernan, está en
[docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md](docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md),
y cómo ensayarlo con personas en [docs/Prueba_Con_Personas.md](docs/Prueba_Con_Personas.md).

### Lo que protege la página pública

Es la única ruta sin sesión que escribe en la base. Tiene límite de envíos por IP (10 por
hora) y por publicación (120), un campo trampa para robots, un esquema que rechaza cualquier
campo de más, «no disponible» igual para una publicación inexistente, desactivada o que no es
de LinkedIn, y **la misma respuesta exista o no el correo**, para que no sirva para averiguar
quién está en la base. El CI lo comprueba en un paso propio, **«La pagina publica conserva
sus defensas»** (`scripts/guarda_de_la_pagina_publica.py`), que falla si la página pierde el
límite, acepta texto libre, sirve listas distintas de las del modelo que puntúa, obliga a más
de lo imprescindible, vuelve a preguntar o escribir la facturación, deja que «¿Qué
necesitas?» mueva la puntuación, o si el heurístico vuelve a suponer lo que falta.

**Nada supuesto.** Lo que la persona no dice queda vacío: ni teléfono, ni perfil, ni
facturación. «¿Qué necesitas?» no puntúa: se guarda en la solicitud y el asesor lo lee en la
ficha 360 y en el informe (antes, «Ver una demostración» se registraba como una demo pedida y
sumaba 25 puntos). Y la regla heurística trata un tamaño, un cargo o un sector que faltan
como **desconocidos**, con el punto medio de su bloque (6, 15 y 10,5 puntos), y no como
«1-10» o como la base de un estudiante.

Dos límites conocidos: el modelo todavía no conoce el canal `LinkedIn` —conoce «LinkedIn
Ads», que es publicidad pagada— y lo trata como desconocido hasta reentrenar con desenlaces
reales; y solo esta página atribuye la ficha a su campaña, las integraciones no.

---

## 🌐 Rutas y Puertos de Validación Funcional

| Servicio / Componente | URL de Acceso | Descripción |
| :--- | :--- | :--- |
| **Plataforma Web (React SPA)** | [http://localhost:3000](http://localhost:3000) | Entrada de la pila Docker: nginx sirve la SPA y hace de pasarela hacia la API. |
| **Plataforma Web (ejecución local)** | [http://localhost:8000](http://localhost:8000) | Entrega unificada de uvicorn fuera de Docker. |
| **Documentación Swagger API** | [http://localhost:8000/docs](http://localhost:8000/docs) | Solo fuera de producción. Con `ENVIRONMENT=production` devuelve 404, igual que `/redoc` y el esquema OpenAPI. |
| **Health Check API** | [http://localhost:8000/health](http://localhost:8000/health) | Ejecuta un `SELECT` real contra la base y responde 503 si no contesta. |
| **pgAdmin 4** | [http://127.0.0.1:5050](http://127.0.0.1:5050) | Solo con el overlay de desarrollo (`python devops/pila.py --dev up -d`) y credenciales propias en el archivo de entorno de la pila. |
| **PostgreSQL 16** | — | Sin puerto publicado. Acceso vía `python devops/pila.py exec postgres psql` o el overlay de desarrollo. |

### Límites de tasa

Cuatro rutas se pueden abusar sin credenciales válidas o con un único token, y llevan tope por IP:

| Endpoint | Límite por defecto | Variable | Motivo |
| :--- | :--- | :--- | :--- |
| `POST /api/v1/auth/login` | 10/minuto | `RATE_LIMIT_LOGIN` | Fuerza bruta de contraseñas |
| `POST /api/v1/scoring/predict` | 60/minuto | `RATE_LIMIT_PREDICT` | Es la ruta más cara: inferencia + generación de texto |
| `POST /api/v1/crm/webhook` | 120/minuto | `RATE_LIMIT_WEBHOOK` | Un secreto filtrado no debe permitir inundar la base |
| `POST /api/v1/integraciones/{nombre}/eventos` | Uno por integración (30–120/minuto) | `INTEGRACION_<NOMBRE>_LIMITE` | La cuenta de una integración no consume la de otra |

Al superarlos se devuelve `429` con las cabeceras `X-RateLimit-*`. `RATE_LIMIT_ENABLED=false`
desactiva el mecanismo cuando el corte lo aplica un balanceador por delante.

Dos ajustes deciden si el tope sirve de algo:

- **`TRUST_PROXY_HEADERS`** (por defecto `false`). `X-Forwarded-For` la escribe el cliente:
  si se le hace caso sin un proxy de confianza delante, basta con rotar un valor inventado
  en cada intento para que el límite no llegue a aplicarse nunca. La pila de compose la
  activa explícitamente, porque allí todo el tráfico entra por nginx.
- **`RATE_LIMIT_STORAGE_URI`**. Con `memory://` cada worker de uvicorn cuenta por su lado y
  el tope real es el declarado *multiplicado* por el número de workers (medido: con 2
  workers y `10/minute` pasaban 11-20 intentos). La pila levanta un Redis propio y apunta
  a él, con lo que la cuenta es exacta y común a todos los procesos.

### Bitácora de auditoría

`GET /api/v1/audit` devuelve quién hizo qué, sobre qué, desde qué dirección y con qué
resultado — incluidos los intentos **denegados**, que son los que interesan cuando alguien
tantea los límites de su rol. Filtra por `actor_email`, `action`, `entity`, `entity_id`,
`outcome`, `desde` y `hasta`.

Es **solo lectura** (no hay endpoint que borre ni edite asientos: lo primero que borraría
quien abusa de sus permisos es el registro de que lo hizo) y **solo `System_Admin`**: la
bitácora concentra ya correlacionado quién trabaja con qué cartera y desde dónde se conecta
cada persona, y eso no es información que un responsable de equipo necesite para su trabajo.
Consultarla queda a su vez registrado.

### Datos de los prospectos: acceso, supresión y retención

Un prospecto es una persona. El sistema guarda su ficha, lo que hizo, cada puntuación con
el vector de variables y la explicación, y lo que llegó del CRM.

| Qué | Cómo | Quién |
| :--- | :--- | :--- |
| Todo lo que el sistema sabe de una persona | `GET /api/v1/leads/{id}/exportar` — JSON adjunto, `Cache-Control: no-store` | `Sales_Lead`, `System_Admin` |
| Suprimirla | `DELETE /api/v1/leads/{id}` | `Sales_Lead`, `System_Admin` |
| Resumir el historial vencido | servicio `retencion-historial` de la pila, una pasada al día | la pila, sin actor |

- **La exportación** trae cada columna de cada tabla que cuelga del prospecto —también las
  que se añadan mañana—, las ingestas del CRM que no llegaron a vincularse, qué se hizo con
  sus datos y cuándo (por rol, sin datos de los empleados), cuánto se conservan y qué copias
  existen fuera de la base.
- **La supresión** borra en una transacción todo lo que cuelga del prospecto, incluidas las
  entregas de webhook y las ingestas revertidas que llevan su correo sin `lead_id`, y retira
  sus datos de los asientos de la bitácora sin borrar los asientos. El asiento del borrado
  guarda cuántas filas salieron de cada tabla y una **huella con clave** del correo: permite
  comprobar si una persona concreta fue suprimida sin que la bitácora se lo diga a nadie más.
- **El historial de puntuación** conserva el detalle de los últimos
  `SCORE_HISTORY_RETENTION_MONTHS` meses completos (12 por defecto, mínimo 3) más el mes en
  curso. Lo anterior se resume por prospecto y mes en `score_history_monthly` y se borra.
  Se conservan **siempre** la instantánea de entrada de cada prospecto —el ejemplo de
  entrenamiento del bucle de realimentación— y su puntuación vigente.
- **Lo demás también tiene plazo** (capítulo 22), y lo aplica la misma pasada diaria, con un
  asiento por plazo en la bitácora. Por debajo del mínimo, el servicio no arranca.

  | Tabla | Plazo por defecto | Mínimo | Cuenta desde |
  | :--- | :--- | :--- | :--- |
  | `refresh_tokens` (sesiones) | `CONSERVACION_SESIONES_DIAS` = 30 | 7 | que la sesión caducó |
  | `scoring_jobs` (recálculos) | `CONSERVACION_TRABAJOS_DIAS` = 90 | 7 | que terminó; los vivos no se tocan |
  | `crm_integration_logs` | `CONSERVACION_REGISTROS_CRM_DIAS` = 90 | 30 | la sincronización |
  | `unmatched_events` (bandeja «Sin asociar») | `CONSERVACION_SIN_ASOCIAR_DIAS` = 90 | 30 | que llegó el aviso |

```bash
# Qué haría la purga hoy, sin escribir nada
python devops/pila.py exec retencion-historial python /app/scripts/retencion_historial.py --simular
```

La política completa —qué se guarda, cuánto tiempo, con qué mecanismo y qué queda fuera del
alcance de una supresión— está en el capítulo 20 de la memoria técnica.

---

## 🛠️ Fiabilidad Operativa

### Recálculo masivo: un turno a la vez, y un estado que caduca

`scoring_jobs.status` decía qué se pretendía hacer, no qué estaba pasando. Un proceso que
moría a mitad del recorrido dejaba su fila en `RUNNING` para siempre.

| | Antes | Ahora |
| :--- | :--- | :--- |
| Trabajo cuyo proceso murió | `RUNNING` indefinidamente | Arriendo vencido → `FAILED` |
| Distinguir «lento» de «muerto» | Imposible | `heartbeat_at` y `lease_until` |
| Dos recálculos simultáneos | Ambos se ejecutaban | El segundo recibe **409** |
| Saber en qué contenedor mirar | — | `worker_id` (host y PID) |

El ejecutor renueva `lease_until` **en cada lote**, junto con el progreso y en el mismo
commit: la señal de vida la produce el avance real, no un temporizador aparte que seguiría
diciendo «vivo» con el bucle bloqueado. Vencido el plazo, el trabajo se cierra como
fallido —al arrancar la aplicación y también antes de aceptar uno nuevo, porque si nadie
reinicia la pila el barrido del arranque no vuelve a ocurrir—.

La exclusión la impone un **índice único** sobre `lease_key`, no una consulta previa.
«Mirar si hay uno activo y, si no, insertar» es una carrera que con dos workers pierde
alguien cada vez que un usuario pulsa dos veces el botón.

```bash
# Un recálculo mientras hay otro vivo
curl -X POST .../api/v1/leads/batch/recalculate-all -H "Authorization: Bearer $TOKEN"
# 409 {"detail": {"job_id": "...", "estado": "RUNNING", "procesados": 340, "total": 5000}}
```

### Registro estructurado y `request_id`

Los registros son **un objeto JSON por línea**. El formato de texto anterior dejaba de
servir con dos workers escribiendo sobre el mismo descriptor: las trazas multilínea se
entremezclaban y no había forma de reunir lo que produjo una misma petición.

Cada petición lleva un `request_id` que viaja por `contextvars`, sale en la cabecera
`X-Request-ID` y aparece en **todos** los renglones que esa petición genere, incluidos los
de las librerías. Antes, el identificador que se devolvía en los 500 se inventaba en el
propio manejador y no constaba en ningún otro sitio: el dato que soporte pedía no llevaba
a ninguna parte.

Si el cliente manda su propio `X-Request-ID`, se respeta —así se encadena con el de un
balanceador— pero solo si encaja en `[A-Za-z0-9._-]{1,64}`. Aceptarlo tal cual sería
inyección en el registro: un salto de línea dentro de la cabecera escribe renglones enteros
en el log, y en un formato de una línea por evento eso es fabricar eventos falsos.

```bash
# Todo lo que produjo una petición concreta
python devops/pila.py logs backend --no-log-prefix | jq -c 'select(.request_id=="a1b2c3...")'

# Las peticiones que tardaron más de medio segundo
python devops/pila.py logs backend --no-log-prefix | jq -c 'select(.duracion_ms > 500)'
```

`LOG_FORMAT` acepta `json`, `text` o `auto`. Con `auto` manda el entorno: JSON en producción
y staging, texto en desarrollo, donde los lee una persona.

### Métricas de Prometheus

`GET /metrics`, **fuera** de `/api/v1`. No es un capricho de rutas: el nginx de la pila solo
hace de pasarela para `/api/`, de modo que la ruta queda inalcanzable desde el puerto
público sin depender de una regla de denegación que alguien pueda borrar.

| Métrica | Origen | Exactitud |
| :--- | :--- | :--- |
| `plurione_http_peticiones_total` | Memoria del proceso | Solo del worker que responde |
| `plurione_http_duracion_segundos` | Memoria del proceso | Solo del worker que responde |
| `plurione_scores_calculados_total` | Memoria del proceso | Solo del worker que responde |
| `plurione_recalculos_en_curso` | Consulta a la base | Exacta |
| `plurione_recalculos_total` | Consulta a la base | Exacta |
| `plurione_prospectos_total` | Consulta a la base | Exacta |

La imagen sirve con `--workers 2`, así que una recogida la atiende uno de los dos y
devuelve **su** mitad de los contadores de proceso. Es el mismo defecto que tenía la
limitación de tasa con `memory://`, y aquí no se resuelve igual: un contador en Redis por
petición costaría más que la petición. Se hace explícito con `plurione_worker_info`, que
dice qué worker respondió. Para números exactos: una réplica por contenedor con
`--workers 1`, y que Prometheus recoja de todas.

Todo lo que puede leerse de la base se lee de la base, y por eso sale exacto venga la
respuesta de donde venga.

**Protección.** Prometheus no sabe iniciar sesión, así que la ruta no puede depender del
JWT del resto de la API: se compara `METRICS_TOKEN` con `compare_digest`. Sin testigo, la
ruta queda **abierta en desarrollo y apagada (404) en producción y staging**. Responde 404
y no 403 porque un 403 confirma que hay algo que pedir.

```bash
curl -H "Authorization: Bearer $METRICS_TOKEN" http://backend:8000/metrics
```

### Endurecimiento de los contenedores

Todos los servicios llevan techo de CPU y memoria, `no-new-privileges`, `cap_drop: ALL`
con solo las capacidades que cada imagen necesita, y rotación de registros.

| Servicio | `read_only` | Capacidades añadidas | Techo por defecto |
| :--- | :--- | :--- | :--- |
| `backend` | Sí (`/tmp` en memoria) | ninguna | 2 CPU / 2 GB |
| `migrate` | Sí | ninguna | 1 CPU / 512 MB |
| `frontend` | Sí | `CHOWN`, `SETGID`, `SETUID`, `NET_BIND_SERVICE` | 0.5 CPU / 128 MB |
| `redis` | Sí | `SETGID`, `SETUID` | 0.5 CPU / 256 MB |
| `postgres` | **No** | `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID` | 1 CPU / 1 GB |

PostgreSQL es el único sin `read_only`: su entrypoint ajusta permisos y escribe fuera del
volumen al inicializar, y una base de datos es por definición un proceso que escribe.

Los techos se ajustan por variable (`LIMITE_MEM_BACKEND`, `LIMITE_CPU_POSTGRES`…). Vienen
holgados a propósito: un techo demasiado justo no da un error legible, da un proceso que el
núcleo mata con código 137 y sin un solo renglón en el registro.

La rotación (`max-size`, `max-file`) importa más ahora que antes: un objeto JSON por
petición llena un disco bastante más rápido que una línea por evento, y el disco que se
llena es el mismo en el que vive la base de datos.

### Fuentes autoalojadas y una CSP que se comprueba

La página traía tres familias de `fonts.googleapis.com`. La `Content-Security-Policy` que
sirve nginx dice `style-src 'self'` y `font-src 'self'`, así que el navegador bloqueaba
esa hoja **en silencio**: en producción la aplicación caía a las fuentes del sistema y el
único síntoma era que se veía distinta que con `npm run dev`. De las tres familias
descargadas, además, dos no se usaban en ningún sitio y la que el CSS pedía de verdad
(`Inter`) no se descargaba nunca.

Ahora los `.woff2` viajan en el bundle con huella en el nombre (`src/fuentes.css`), la
política dice `font-src 'self'` sin `data:`, y **hay quien lo comprueba**: el pipeline
levanta la imagen del frontend, descarga la página, y verifica que todo lo que enlaza lo
sirve ese mismo origen y que cada fuente responde con la firma `wOF2` de un archivo real
—el `try_files` de la SPA devuelve `index.html` con código 200 para cualquier ruta que no
exista, así que mirar solo el código no vale—.

```bash
cd frontend
docker build -t plurione-frontend:local .
# nginx resuelve el upstream al arrancar y se niega si el nombre no existe
docker run --rm -p 8099:80 --add-host backend:127.0.0.1 plurione-frontend:local
curl -sI http://127.0.0.1:8099/ | grep -i content-security-policy
```

### Auditoría de dependencias, escaneo de imágenes e inventario

| Qué | Herramienta | Puerta |
| :--- | :--- | :--- |
| Dependencias de Python | `pip-audit` sobre lo **instalado** desde los locks, también dentro de la imagen | cualquier aviso |
| Dependencias del cliente | `npm audit` | `--audit-level=high` |
| Imágenes de contenedor | Trivy | `HIGH`/`CRITICAL` **con arreglo publicado** |
| Lista de materiales | syft (CycloneDX) | se publica como artefacto |

```bash
npm --prefix frontend audit --audit-level=high

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.74.0 \
    image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
    plurione/leadscoring-backend:local

docker run --rm -v /var/run/docker.sock:/var/run/docker.sock anchore/syft:v1.51.1 \
    -o cyclonedx-json plurione/leadscoring-backend:local > sbom-backend.cdx.json
```

Las dos herramientas, como todas las imágenes de terceros del proyecto, van **fijadas por
huella** en el pipeline, los Dockerfiles y la pila (`nombre:etiqueta@sha256:…`). La etiqueta
dice qué seguir; lo que se descarga lo decide la huella. Renovar es explícito:

```bash
python scripts/renovar_imagenes.py --solo-fijacion   # sin red: todo fijado, sin apk upgrade
python scripts/renovar_imagenes.py                   # pregunta al registro qué quedó atrás
python scripts/renovar_imagenes.py --aplicar         # reescribe las huellas; se revisa el diff
```

`pip-audit` ya no audita los rangos de `requirements.txt`, que resolvía en el momento de
auditar y no tenían por qué coincidir con lo que llevaba la imagen construida una hora
antes. El CI instala cada lock en un entorno limpio, comprueba con
`scripts/comprobar_instalado.py` que lo instalado es exactamente lo fijado —y lo mismo
**dentro de la imagen**, donde los marcadores se evalúan para Linux— y audita esa lista con
`--no-deps --disable-pip`, sin volver a resolver nada.

`--ignore-unfixed` no es una concesión, es lo que hace que la puerta signifique algo. Sin
ella, la imagen del backend salía con 57 hallazgos altos o críticos, de los cuales 55 no
tienen arreglo publicado por Debian: una puerta que está en rojo por causas que nadie de
este proyecto puede resolver se acaba desactivando, y entonces tampoco avisa de los dos
que sí eran accionables.

Los dos accionables eran `msgpack` y `setuptools` **vendorizados dentro de pip**, que la
aplicación no importa nunca. Se cerraron sacando pip entero de la imagen de ejecución
—que además le quita a un atacante la herramienta de descargar y ejecutar código—. Los
siete de la imagen del frontend eran `libuuid` del sistema base de Alpine, ya corregidos
aguas arriba. Se recogían con `apk upgrade`, que subía lo que hubiera ese día; desde el
capítulo 22 se instalan con su versión exacta sobre una base fijada por huella.

### El bundle que se prueba es el que se despliega

`frontend/dist/` no se versiona. El pipeline lo compila **una vez**, en el trabajo del
cliente, después de pasar el `linter`, las pruebas y el suelo de cobertura; lo publica
como artefacto; y la imagen lo consume tal cual con `--target desde-artefacto`, sin
recompilarlo. Un paso posterior compara la huella SHA-256 del artefacto con la del
archivo que sirve la imagen.

El Dockerfile del cliente tiene dos destinos por eso:

```bash
# En un portátil: compila desde el código
docker build -t plurione-frontend:local frontend/

# Como en CI: consume un dist/ ya compilado y verificado
npm --prefix frontend run build
docker build --target desde-artefacto -t plurione-frontend:artefacto frontend/
```

Antes había uno solo, y el pipeline compilaba dos veces: la que se probaba y la que se
publicaba. Dos compilaciones que terminan bien no son la misma compilación, y la
diferencia no da ningún síntoma.

### Copias de seguridad, y su prueba de restauración

```bash
# Volcado con marca UTC en un volumen aparte, verificado y con huella SHA-256
python devops/pila.py --profile respaldo run --rm respaldo

# Lo que convierte «tenemos copias» en «tenemos copias que sirven»
python devops/pila.py --profile respaldo run --rm prueba-de-restauracion
```

La copia no se da por buena porque `pg_dump` terminara: se comprueba que el archivo **se
puede leer** (`pg_restore --list`), que no es sospechosamente pequeño —una base vacía por
error produce un volcado perfectamente válido de unos kilobytes— y se deja su huella al
lado. Se escribe como `.parcial` y se renombra al final, para que un volcado interrumpido
no quede nunca con el nombre de uno bueno.

La prueba de restauración restaura el volcado más reciente en una base **desechable** del
mismo servidor y compara el recuento de filas tabla por tabla contra la base real. Usa
`pg_restore --exit-on-error`: sin esa opción, una restauración a medias informa de los
errores y termina con código 0, de modo que el fallo se leería como un éxito.

Para recuperar de verdad:

```bash
python devops/pila.py stop backend frontend
python devops/pila.py --profile respaldo run --rm \
    -e VOLCADO=/respaldos/lead_scoring_db_20260909T031500Z.dump \
    -e CONFIRMO_SOBRESCRIBIR=si restaurar
python devops/pila.py run --rm migrate alembic current   # ¿coincide con lo que espera el código?
python devops/pila.py start backend frontend
```

Exige el archivo exacto —no coge el más reciente por su cuenta, que puede ser justo el que
ya contiene el borrado del que se quiere volver— y una confirmación explícita. Restaura con
`--single-transaction`: si falla a mitad, la base se queda como estaba en vez de convertirse
en una mezcla de dos versiones.

**Dos límites que conviene tener escritos.** Las copias viven en un volumen del mismo
disco: protegen de un `DROP TABLE` o de una migración que salió mal, **no** de que se muera
el disco; sacarlas de la máquina es un paso de operación que depende de dónde se despliegue.
Y la prueba demuestra que el archivo sirve, no que se podría reconstruir el servicio entero
en otra máquina; ese ensayo es distinto y no lo cubre este script.

---

## 🧪 Ejecución de Pruebas Automatizadas (QA)

### Backend — 1158 pruebas

Ejecuta la suite completa de pruebas automatizadas (matemáticas de decaimiento, paridad
entre las dos rutas de cálculo del heurístico, validación de esquemas, atomicidad de la
ingesta CRM, adaptadores nativos, API y seguridad RBAC):
```bash
python -m pytest backend/tests/ -v
```

### Gobierno del modelo

```bash
python -m pytest backend/tests/test_gobierno_del_modelo.py backend/tests/test_perfil_y_publicacion.py \
    backend/tests/test_ml_honesto.py -v
```

Cubren lo que decide si el modelo se puede explicar dentro de seis meses: que la huella de
los datos sea real y **recalculable por un tercero**, que medir con datos reales no
publique ni ensucie el registro, y que una alerta de deriva se emita cuando toca y —sobre
todo— **se calle cuando no toca**; que el perfil de referencia corresponda al artefacto que
puntúa, y que publicar exija el intervalo de confianza y no solo la estimación puntual.

### Reproducibilidad y ciclo de vida del dato

```bash
python -m pytest backend/tests/test_dependencias_fijadas.py backend/tests/test_retencion_del_historial.py \
    backend/tests/test_derechos_del_titular.py -v
```

Cubren que los locks estén completos y sean coherentes con los rangos y entre sí, que la
imagen y el CI instalen desde ellos y que el modelo versionado se haya entrenado con sus
versiones; que la purga del historial resuma sin perder la instantánea de entrada que usa
el bucle de realimentación, y sin contar dos veces una fila; y que, tras suprimir a una
persona, su correo no aparezca en **ninguna fila de ninguna tabla**.

### Cimientos del registro

```bash
python -m pytest backend/tests/test_registro_de_actividad.py -v
```

Cubren que solo `registrar_evento` escriba actividades; que un tipo desconocido responda 422
en lugar de degradarse; que lo que no llega no se invente; que solo la llamada que conectó
cuente; que WhatsApp y LinkedIn sigan alimentando la variable con la que se entrenó el
modelo; que cada integración firme con su secreto y cuente con su límite; y que el texto de
un mensaje enviado por el CRM, WhatsApp, Calendly o el formulario web no aparezca en
**ninguna columna de ninguna tabla**.

### Del post de LinkedIn al prospecto puntuado

```bash
python -m pytest backend/tests/test_publicaciones.py backend/tests/test_pagina_de_interes.py \
  backend/tests/test_categorias_del_modelo.py backend/tests/test_informe_de_publicaciones.py -v
python scripts/guarda_de_la_pagina_publica.py
```

Cubren el enlace de cada publicación —imposible de adivinar, de cambiar y de reutilizar—; la
página pública con duplicados que suman sin pisar la ficha, publicaciones desactivadas o
inexistentes, los dos límites de envío, el campo trampa, el aviso de privacidad falso u
omitido y la misma respuesta exista o no el correo; que las listas del formulario sean las
del artefacto que puntúa; y el alcance del informe, con el asesor viendo sus prospectos y
un número del resto, sin nombres. La guarda comprueba propiedades en lugar de casos, y es un
paso propio del CI.

### Cliente — 302 pruebas

El navegador tenía la mitad del sistema y ninguna prueba. Ahora tiene las suyas, con
Vitest y Testing Library, y un `linter` propio:

```bash
cd frontend

npm run lint            # eslint + eslint-plugin-react-hooks
npm test                # 302 pruebas
npm run test:coverage   # con suelo de cobertura; falla si baja
npm run test:watch      # mientras se trabaja
```

La prioridad fue el módulo de sesión (`src/services/api.js`), que es donde un fallo no
se ve: un refresco de más solo multiplica peticiones, y una sesión que revive tras
cerrarla tampoco avisa. Se cubren el refresco concurrente, el reintento tras un 401, la
expiración y el cierre de sesión; después, los componentes con lógica —la matriz de
prospectos, el simulador, el menú de la sesión, la pantalla de cambio obligatorio de
contraseña, el reparto de la cartera de las bajas en el panel de administración, la ficha del
prospecto y la bandeja «Sin asociar»—.

El suelo de cobertura vive en `frontend/vite.config.js` y va **justo por debajo de lo
medido** (92 / 86 / 94 / 94 frente a 95 / 88 / 97 / 97), no en un número redondo: un
suelo del 80 % con la cobertura real en el 95 % deja pasar una regresión de quince puntos
sin decir nada.

`react-hooks/exhaustive-deps` está en `error`, no en aviso. Un aviso permanente que nadie
atiende enseña a ignorar la salida del `linter`. Hay una regla apagada a propósito
—`react-hooks/set-state-in-effect`— con el motivo escrito en `eslint.config.js`.

> La suite es autosuficiente: corre sobre SQLite en memoria y crea sus propios datos.
> **No** hace falta sembrar antes, y no debe hacerse: las pruebas no tocan ninguna base
> real. Esta nota decía lo contrario mientras las pruebas dependían del sembrado, que es
> precisamente lo que las volvía dependientes del orden de ejecución.

Las reglas heurísticas del ICP viven en un único módulo, `backend/app/core/scoring_rules.py`,
que consumen tanto el servicio de scoring como el pipeline de entrenamiento. Es
deliberado: cuando cada uno tenía su copia, el modelo se entrenaba con una definición de
"buen prospecto" y luego se evaluaba a los prospectos reales con otra. `test_scoring_parity.py`
compara ambas rutas para que la divergencia no pueda repetirse en silencio.

---

## 🎯 Demostración Técnica Interactiva (CLI)

Ejecuta el script de demostración end-to-end en vivo que simula la ingesta de un webhook CRM, evalúa el algoritmo híbrido y genera el diagnóstico con IA:
```bash
python scripts/demo_e2e.py
```

---

## 📚 Compilación de la Memoria Técnica Institucional

Para compilar los 21 reportes técnicos en el documento formal consolidado con portada e índice:
```bash
python docs/compile_reports.py
```
El archivo consolidado se genera en: `docs/Memoria_Tecnica_Final_Lead_Scoring.md`.

---

## 📑 Suite de 27 Reportes Técnicos de Estadía Profesional

| Reporte | Documento | Enfoque de Ingeniería |
| :-: | :--- | :--- |
| **01** | [Reporte 01](docs/reportes/Reporte_01_Deteccion_de_Necesidades_y_Requerimientos.md) | Detección de Necesidades y Especificación IEEE 830. |
| **02** | [Reporte 02](docs/reportes/Reporte_02_Propuesta_Tecnica_y_Estrategia_de_Lead_Scoring.md) | Formulación Matemática del Scoring Híbrido y Decaimiento Continuo. |
| **03** | [Reporte 03](docs/reportes/Reporte_03_Diseno_de_Arquitectura_Integral_y_Modelo_de_Datos.md) | Clean Architecture, Puertos y Adaptadores y Modelo ERD. |
| **04** | [Reporte 04](docs/reportes/Reporte_04_Planificacion_Operativa_y_Gestion_Scrum_del_Proyecto.md) | Gestión Ágil Scrum, Historias de Usuario y Riesgos. |
| **05** | [Reporte 05](docs/reportes/Reporte_05_Desarrollo_del_Pipeline_de_Machine_Learning_y_Adaptadores_Azure_Local.md) | Pipeline de Machine Learning ($ROC\text{-}AUC=0.9524$) sobre datos sintéticos) y Motores Nativos. |
| **06** | [Reporte 06](docs/reportes/Reporte_06_Core_Backend_FastAPI_Ingesta_CRM_y_Reglas_Dinamicas.md) | Core Backend FastAPI, Ingesta CRM y Deduplicación. |
| **07** | [Reporte 07](docs/reportes/Reporte_07_Interfaz_de_Usuario_React_y_Visualizacion_Analitica.md) | UI en React.js, Analítica Avanzada, Ficha 360° y XAI. |
| **08** | [Reporte 08](docs/reportes/Reporte_08_Suite_de_Pruebas_Automatizadas_y_QA_de_Precision.md) | QA, Pruebas Matemáticas y 100% de Aprobación en Pytest. |
| **09** | [Reporte 09](docs/reportes/Reporte_09_Contenerizacion_CI_CD_y_Simulacion_de_Seguridad_RBAC.md) | Dockerfiles, Docker Compose, CI/CD y RBAC Empresarial. |
| **10** | [Reporte 10](docs/reportes/Reporte_10_Manual_Tecnico_Plan_de_Mantenimiento_y_Cierre_de_Estadia.md) | Manual Técnico, Soporte Multinivel (N1/N2/N3) y Cierre de Estadía. |
| **11** | [Reporte 11](docs/reportes/Reporte_11_Auditoria_Endurecimiento_de_Seguridad_y_Rendimiento.md) | Auditoría Técnica, Endurecimiento de Seguridad y Optimización de Rendimiento. |
| **12** | [Reporte 12](docs/reportes/Reporte_12_Gobierno_de_Datos_Migraciones_y_Validez_del_Modelo.md) | Migraciones con Alembic, Líneas Base del Modelo y Bucle de Realimentación. |
| **13** | [Reporte 13](docs/reportes/Reporte_13_Superficie_de_Ataque_Residual_y_Observabilidad_del_Modelo.md) | CORS, Inyección de Prompt, Monitoreo de Deriva y Registro de Modelos. |
| **14** | [Reporte 14](docs/reportes/Reporte_14_Sesiones_Verificables_Ingesta_Idempotente_y_Bitacora_de_Auditoria.md) | Rotación de sesión con detección de reutilización, idempotencia de la ingesta y bitácora de auditoría. |
| **15** | [Reporte 15](docs/reportes/Reporte_15_Identidad_Unificada_Autorizacion_por_Objeto_y_Gestion_de_Cuentas.md) | Identidad unificada, autorización por objeto en el repositorio, gestión de cuentas y política de contraseñas. |
| **16** | [Reporte 16](docs/reportes/Reporte_16_Fiabilidad_Operativa_Arriendos_Observabilidad_y_Respaldos.md) | Arriendo y turno exclusivo del recálculo, registro estructurado con `request_id`, métricas de Prometheus, endurecimiento de contenedores y copias con prueba de restauración. |
| **17** | [Reporte 17](docs/reportes/Reporte_17_Paridad_de_Calidad_en_el_Cliente_Fuentes_Autoalojadas_y_Cadena_de_Suministro.md) | Pruebas y análisis estático del cliente, fuentes autoalojadas con CSP verificada, auditoría de dependencias, escaneo de imágenes con SBOM y trazabilidad del artefacto desplegado. |
| **18** | [Reporte 18](docs/reportes/Reporte_18_Gobierno_del_Modelo_Procedencia_de_los_Datos_Bucle_de_Realimentacion_y_Alertas_de_Deriva.md) | Procedencia obligatoria del conjunto de entrenamiento, bucle de realimentación ejercitado de punta a punta con intervalos de confianza, y monitoreo de deriva programado con alerta y silencio. |
| **19** | [Reporte 19](docs/reportes/Reporte_19_Lo_Dicho_y_No_Hecho_Contrasena_Prestada_Cartera_de_las_Bajas_y_Condiciones_de_Publicacion.md) | Contraseña prestada impuesta en el servidor, reparto de la cartera de las cuentas de baja, perfil de referencia atado al artefacto y publicación condicionada al intervalo de confianza. |
| **20** | [Reporte 20](docs/reportes/Reporte_20_Reproducibilidad_y_Ciclo_de_Vida_del_Dato_Dependencias_Fijadas_Retencion_del_Historial_y_Derechos_del_Titular.md) | Dependencias fijadas con huellas y auditoría de lo instalado, retención del historial de puntuación, exportación y supresión de los datos de una persona, y política de conservación. |
| **21** | [Reporte 21](docs/reportes/Reporte_21_Cimientos_del_Registro_Procedencia_de_la_Actividad_Integraciones_y_Minimizacion.md) | Procedencia en cada actividad y un solo servicio de registro, bandeja «Sin asociar», teléfonos en E.164, integraciones con secreto y límite propios, minimización de mensajes y una ficha que enseña el cambio real del score. |
| **22** | [Reporte 22](docs/reportes/Reporte_22_Nada_Sin_Plazo_Ni_Sin_Aviso_Caducidad_Alertas_del_Monitor_Imagenes_Fijadas_y_Arranque.md) | Plazo de conservación para todo lo que no lo tenía, alertas del monitor también cuando no evalúa, imágenes fijadas por huella y un solo modo de arrancar. |
| **23** | [Reporte 23](docs/reportes/Reporte_23_Autenticacion_sin_Excepciones_PyJWT_Revocacion_Inmediata_y_Contrasenas_Filtradas.md) | PyJWT en lugar de python-jose, revocación inmediata del access token y contraseñas filtradas con una lista local. |
| **24** | [Reporte 24](docs/reportes/Reporte_24_Modelo_sin_Datos_Inventados_Ingresos_Ausentes_Canales_Separados_y_Aporte_con_Intervalo.md) | Un solo vector del modelo con versión, ingresos ausentes como ausencia, canales y resultados de llamada separados y aporte sobre el heurístico con intervalo. |
| **25** | [Reporte 25](docs/reportes/Reporte_25_Del_Post_de_LinkedIn_al_Prospecto_Puntuado_Publicaciones_Pagina_de_Interes_e_Informe_por_Publicacion.md) | Del post de LinkedIn al prospecto puntuado: publicaciones con enlace propio, página de interés pública y defendida, ficha «Llegó por», informe y comparativa por publicación, y guarda del CI. |
| **26** | [Reporte 26](docs/reportes/Reporte_26_Publicaciones_Completas_Ciclo_de_Vida_Opciones_Responsable_y_Visitas.md) | Publicaciones completas: estados y cierre automático, vistas previas del post y de la página, opciones de «¿Qué necesitas?» por publicación, asesor responsable, post real, duplicar, y visitas sin datos personales con tasa de envío y gráfico por día. |
| **27** | [Reporte 27](docs/reportes/Reporte_27_Una_Publicacion_Varias_Redes_Difusion_Textos_por_Red_y_Atribucion.md) | Una publicación, varias redes: enlace y texto por red, botones oficiales de compartir sin API ni cuentas, código QR generado en local, red de llegada en la ficha y en el informe, y las claves viejas de JWT guardadas por su huella. |
| **DEF** | [Guía de Defensa](docs/GUIA_DEFENSA_ORAL.md) | Guion de 10 minutos y 12 preguntas de sínodo con respuestas modelo. |

---

*Desarrollado para PluriOne S.A. de C.V. - Proyecto de Estadía Profesional en Ingeniería en Sistemas Computacionales.*
