# Guía de instalación — Sistema Inteligente de Lead Scoring

Probada sobre un **clon limpio el 07-10-2026**. Si algo falla, ver [Si algo falla](../Si_Algo_Falla.md).

---

## 1. Requisitos

| Requisito | Versión de referencia |
| :--- | :--- |
| Sistema operativo | Windows 11 (también Linux/macOS) |
| Docker Desktop (con Compose) | Abierto y con el motor iniciado |
| Python | 3.13 |
| Node.js y npm | LTS reciente |
| Git | Con `core.longpaths=true` en Windows |
| Disco / RAM | ~5 GB libres · 8 GB de RAM recomendados |

No se necesita ninguna cuenta externa ni conexión a servicios de pago.

---

## 2. Obtener el código

La ruta relativa más larga del repositorio mide 169 caracteres. En Windows, clone en una carpeta **corta** (menos de 90 caracteres de ruta) y con rutas largas habilitadas, o el índice queda vacío:

```bash
git clone -c core.longpaths=true <url-del-repositorio> Sistema_Inteligente_Lead_Scoring
cd Sistema_Inteligente_Lead_Scoring
```

---

## 3. Primer arranque (cuatro pasos, en este orden)

### Paso 1 — Entrenar el modelo (≈ 2 min)

El archivo del modelo **no viaja en el repositorio** (un binario serializado ejecuta código al cargarse). Sin este paso el sistema arranca igual, **pero puntúa solo con el heurístico y sin avisar**.

```bash
pip install --require-hashes -r backend/requirements.lock
python ml_pipeline/src/train_model.py
```

El entrenamiento usa el conjunto sintético incluido (`ml_pipeline/data/leads_historical.csv`, 3000 filas, semilla 42) y reproduce el mismo artefacto byte a byte.

### Paso 2 — Compilar el cliente

```bash
cd frontend
npm ci
npm run build
cd ..
```

La imagen del backend copia `frontend/dist`; sin él la construcción falla con `"/frontend/dist": not found`.

### Paso 3 — Levantar la pila

```bash
python devops/pila.py iniciar        # una sola vez: crea ~/.plurione/pila.env con los secretos
python devops/pila.py up --build -d
python devops/pila.py ps             # seis servicios; backend, db y redis en (healthy)
```

- **Siempre** con `devops/pila.py`, nunca con `docker compose` a secas.
- **Con `--build`**: una imagen vieja arranca igual de bien que la nueva.
- Los secretos viven **fuera del repositorio**, en `~/.plurione/pila.env`. El lanzador se niega a arrancar si encuentra un `.env` dentro del árbol.

### Paso 4 — Crear las cuentas y los datos de demostración

Una base recién migrada **no tiene ninguna cuenta**. El sembrado completo vacía las tablas de negocio, así que se niega en entornos endurecidos; se le pasa el entorno **solo a ese proceso**:

```bash
python devops/pila.py exec -e ENVIRONMENT=development -e SEED_ADMIN_PASSWORD=PluriOne2026! -e SEED_SALES_LEAD_PASSWORD=PluriOne2026! -e SEED_EXECUTIVE_PASSWORD=PluriOne2026! -e SEED_ASESOR_PASSWORD=PluriOne2026! backend python /app/scripts/seed_data.py
```

Crea siete cuentas, cuatro publicaciones y doce prospectos sintéticos. En **Git Bash** anteponga `MSYS_NO_PATHCONV=1` a la orden (de lo contrario traduce `/app/...` a una ruta de Windows).

> `PluriOne2026!` es la contraseña de **desarrollo** de la demostración. Para un despliegue real use `--solo-usuarios` (crea cuentas sin tocar datos) y contraseñas propias; en entornos endurecidos el sembrado genera una aleatoria.

---

## 4. Verificar

```bash
curl -s http://127.0.0.1:8000/health
```

Debe responder `"status": "healthy"`, `"database": "connected"` y **`"ml_model_loaded": true`**. Si es `false`, está puntuando el heurístico: vuelva al Paso 1.

| Servicio | Dirección |
| :--- | :--- |
| Panel | <http://localhost:3000> |
| Puerta pública (página de interés) | `http://127.0.0.1:8080/interes/<enlace-de-la-publicación>` |
| API | `http://127.0.0.1:8000` |
| PostgreSQL | No se publica (solo con el overlay `--dev`) |

Cuentas de demostración (contraseña `PluriOne2026!`): `admin.ti@`, `lider.ventas@` y `asesor.comercial@plurione.com`, más cuatro asesores.

---

## 5. Operación diaria

| Acción | Orden |
| :--- | :--- |
| Encender | `python devops/pila.py up -d` |
| Apagar (conserva los datos) | `python devops/pila.py down` |
| Pausar y reanudar | `python devops/pila.py stop` / `start` |
| Estado | `python devops/pila.py ps` |
| Copia de seguridad | `cd devops && docker compose --profile respaldo run --rm respaldo` |
| Prueba de restauración | `cd devops && docker compose --profile respaldo run --rm prueba-de-restauracion` |

> **Nunca `down -v`**: borra la base de datos entera.

---

## 6. Variables importantes (en `~/.plurione/pila.env`)

| Variable | Para qué |
| :--- | :--- |
| `SECRET_KEY` | Firma de los JWT. Debe ser fija: si cambia, todos pierden la sesión |
| `POSTGRES_PASSWORD` | Contraseña de la base |
| `PUBLICACIONES_URL_BASE` | Dirección pública de los enlaces; cámbiela al dominio o túnel vigente |
| `ML_MODEL_SHA256` | Opcional: fija la huella del modelo; si no cuadra, el modelo no se carga |
| `CRM_WEBHOOK_SECRET` | Clave HMAC del webhook; vacía, el endpoint contesta 503 |
| `COMPROBAR_DIRECCION_PUBLICA` | `false` en redes con proxy que intercepta TLS |

---

## 7. Problemas conocidos de la instalación

| Síntoma | Causa y solución |
| :--- | :--- |
| `No matching distribution found for aiosqlite==0.22.1` al construir | No es el lock: dos líneas arriba hay un `CERTIFICATE_VERIFY_FAILED`. Es una red con TLS interceptado (proxy corporativo); use otra red |
| `docker` no conecta con el motor | Abra Docker Desktop y espere a que termine de iniciar; su ahorro de recursos puede apagarlo solo tras 5 min sin contenedores |
| `git status` muestra todos los archivos borrados tras clonar | Falta `core.longpaths=true` o la ruta es demasiado larga |
| `can't open file '/app/C:/Program Files/Git/...'` | Git Bash traduce rutas; use `MSYS_NO_PATHCONV=1` o PowerShell |
| El panel pide credenciales que no existen | Falta el Paso 4 |
| El sistema puntúa pero `ml_model_loaded` es `false` | Falta el Paso 1 |

**Alcance probado:** esta instalación, en este equipo, con Docker. La instalación en otra PC servidora **no está ensayada**.
