# ==============================================================================
# SISTEMA INTELIGENTE DE LEAD SCORING - IMAGEN DEL BACKEND (FastAPI + ML)
# ==============================================================================
# El contexto de build es la RAÍZ del repositorio, no `backend/`. Es necesario para
# copiar `ml_pipeline/models/`: con el contexto anterior el artefacto .joblib quedaba
# fuera de la imagen y el servicio arrancaba en modo degradado —cayendo al heurístico
# analítico del adaptador— sin que nada lo señalara (A-5).
#
#   docker build -f backend/Dockerfile -t plurione-backend .
#
# La imagen base va fijada por huella (capítulo 22). `python:3.13-slim` sola se resolvía
# por etiqueta: lo que instala pip era reproducible desde la Fase 14, la capa del sistema
# operativo no. La etiqueta queda delante de la huella para que se lea qué es y para que
# `scripts/renovar_imagenes.py` sepa qué seguir; renovar es un acto explícito, con su diff.
# ==============================================================================

# ------------------------------------------------------------------------------
# Etapa 1 — Compilación de dependencias
# ------------------------------------------------------------------------------
# Los compiladores y las cabeceras de desarrollo solo hacen falta para construir las
# ruedas de psycopg2, numpy y scikit-learn. Se quedan en esta etapa y no viajan a la
# imagen final, que es lo que reduce tanto el tamaño como la superficie de ataque.
FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285 AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Con versión exacta desde el capítulo 32. Hasta entonces esta etapa era el último sitio
# del proyecto donde algo se resolvía «lo que haya ese día»: la imagen base iba por huella
# y las ruedas de Python por lock con hash, pero el compilador con el que se construyen
# esas ruedas lo elegía el índice de Debian en el momento del build.
#
# `build-essential` es un METAPAQUETE: fijar su versión fija el metapaquete, no cada gcc y
# cada libc que arrastra. Es una mejora real —esta línea deja de construir cuando Debian lo
# renueva, y la renovación pasa a ser un acto con su diff— y no es fijación total. Fijar el
# árbol completo exigiría `apt-get install` con la lista resuelta entera, que hay que
# regenerar en cada renovación de la base; no compensa para una etapa que no viaja a la
# imagen final.
RUN apt-get update && apt-get install -y --no-install-recommends \
    'build-essential=12.12' \
    'libpq-dev=17.11-0+deb13u1' \
    && rm -rf /var/lib/apt/lists/*

# Entorno virtual aislado: se copia entero a la etapa final de una sola vez.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Desde el lock, no desde los rangos (R-2). `requirements.txt` dice qué versiones son
# aceptables; `requirements.lock` dice cuáles se instalan, con la huella SHA-256 de cada
# fichero. Con `--require-hashes` pip rechaza cualquier paquete —dependencias transitivas
# incluidas— que no esté en el lock o cuyo fichero no coincida byte a byte: dos
# construcciones con meses de diferencia instalan lo mismo, y un paquete sustituido en el
# índice no entra.
#
# Ya no se actualiza pip antes de instalar. Aquel `pip install --upgrade pip` era la única
# descarga sin versión ni huella de toda la etapa, y el pip de la imagen base ya entiende
# `--require-hashes`; además se retira de la imagen final unas líneas más abajo.
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --require-hashes -r /tmp/requirements.lock


# ------------------------------------------------------------------------------
# Etapa 2 — Imagen de ejecución
# ------------------------------------------------------------------------------
FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285 AS runtime

# libpq5 es la biblioteca en tiempo de ejecución de PostgreSQL; libpq-dev (cabeceras y
# compilador) se queda en la etapa de compilación. Desde el capítulo 32 va con su versión
# como los demás: era el único paquete de la imagen FINAL que seguía sin ella, y el que más
# cerca está del proceso que atiende peticiones.
#
# Los otros cuatro son parches de Debian 13 sobre la base fijada (capítulo 22): con la huella
# de hoy, Trivy encontraba doce avisos ALTOS o CRÍTICOS con arreglo publicado en ellos. Van con
# su versión exacta por la misma razón que los de `apk` del cliente: lo que entra lo decide
# este archivo, no el día de la construcción. Cuando Debian publique otra revisión, esta
# línea dejará de construir; se resuelve renovando la base y mirando qué sigue haciendo falta.
RUN apt-get update && apt-get install -y --no-install-recommends \
    'libpq5=17.11-0+deb13u1' \
    'gzip=1.13-1+deb13u1' \
    'libpcre2-8-0=10.46-1~deb13u2' \
    'libsqlite3-0=3.46.1-7+deb13u2' \
    'perl-base=5.40.1-6+deb13u1' \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios. El proceso corría como root: una ejecución remota de código
# dentro del contenedor equivalía a control total sobre él, y cualquier volumen montado
# quedaba escrito con permisos de root en el anfitrión.
RUN groupadd --system --gid 1001 plurione \
    && useradd --system --uid 1001 --gid plurione --create-home --home-dir /home/plurione plurione

# Los puntos de montaje de los volúmenes, creados AQUÍ y con su dueño (capítulo 32).
#
# Docker copia el contenido y los PERMISOS del directorio de la imagen dentro de un volumen
# nombrado vacío la primera vez que lo monta. Si el directorio no existe en la imagen, lo
# crea el demonio y queda como `root:root` — y estos procesos corren como `plurione`
# (uid 1001), así que no pueden escribir en él.
#
# Esto no es una precaución teórica. El volumen `deriva` existe desde el capítulo 22 con un
# comentario en `docker-compose.yml` que explica por qué el estado de las alertas va ahí y no
# en `tmpfs`: para que un reinicio no haga que la misma deriva vuelva a avisar. Nunca
# funcionó: el volumen llevaba desde entonces vacío y propiedad de root. No se había notado
# porque el monitor solo escribe cuando tiene una alerta que recordar, y todavía no ha
# tenido ninguna. La primera habría fallado al guardar el estado, y la segunda habría
# vuelto a avisar de lo mismo, que es exactamente lo que ese volumen existía para evitar.
RUN mkdir -p /var/lib/plurione/deriva /var/lib/plurione/realimentacion \
    && chown -R plurione:plurione /var/lib/plurione

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Fuera el instalador de paquetes de la imagen de ejecucion (N-10).
#
# Esta aplicacion no instala nada en tiempo de ejecucion: las dependencias se resuelven
# en la etapa de compilacion y llegan aqui dentro del venv ya montado. Que `pip` siga en
# la imagen tiene dos costes:
#
#  1. Es una herramienta de descarga y ejecucion de codigo arbitrario al alcance de
#     quien consiga ejecutar algo dentro del contenedor. Con el sistema de ficheros en
#     solo lectura de la Fase 10 no podria escribir en /app, pero /tmp es escribible.
#  2. Arrastra sus propias dependencias VENDORIZADAS, y Trivy las cuenta. Los dos unicos
#     hallazgos ALTOS con arreglo publicado que quedaban en esta imagen —msgpack 1.1.2 y
#     setuptools 70.3.0— no los importa la aplicacion en ningun momento: viven dentro de
#     `pip/_vendor`, para la cache HTTP del propio pip. Actualizarlos habria sido
#     perseguir un sintoma; lo que sobra es el paquete entero.
#
# Se limpian los dos sitios: el venv copiado y el `site-packages` de la imagen base.
RUN rm -rf /opt/venv/lib/python3.13/site-packages/pip            /opt/venv/lib/python3.13/site-packages/pip-*.dist-info            /opt/venv/lib/python3.13/site-packages/setuptools            /opt/venv/lib/python3.13/site-packages/setuptools-*.dist-info            /opt/venv/lib/python3.13/site-packages/pkg_resources            /opt/venv/bin/pip /opt/venv/bin/pip3 /opt/venv/bin/pip3.13            /usr/local/lib/python3.13/site-packages/pip            /usr/local/lib/python3.13/site-packages/pip-*.dist-info            /usr/local/lib/python3.13/site-packages/setuptools            /usr/local/lib/python3.13/site-packages/setuptools-*.dist-info            /usr/local/lib/python3.13/site-packages/pkg_resources            /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13

# Código de la aplicación. Se copian rutas concretas en lugar de `COPY . .`: así el
# `.dockerignore` deja de ser la única defensa contra colar `.env`, la base de datos
# local o el árbol de pruebas dentro de la imagen.
COPY --chown=plurione:plurione backend/app /app/app
COPY --chown=plurione:plurione backend/scripts /app/scripts

# Migraciones de Alembic. En produccion el esquema NO se crea al arrancar: la aplicacion
# se limita a verificar que la base este en la ultima revision y aborta si no lo esta.
# Aplicarlas es un paso explicito del despliegue, desde este mismo contenedor:
#   python devops/pila.py run --rm migrate
# La disposicion replica la del repositorio (alembic.ini junto a backend/alembic) porque
# Alembic resuelve `script_location` relativo al .ini antes de cargar nada.
COPY --chown=plurione:plurione backend/alembic /app/backend/alembic
COPY --chown=plurione:plurione alembic.ini /app/alembic.ini

# Artefacto del modelo entrenado (A-5). `ML_MODEL_PATH` apunta aquí, de modo que el
# adaptador no depende de rutas relativas al árbol del repositorio.
COPY --chown=plurione:plurione ml_pipeline/models /opt/plurione/models

# Herramientas de observabilidad del modelo. Van en la imagen porque es el unico sitio
# desde el que pueden hacer su trabajo: en la pila de compose, PostgreSQL no publica
# puerto y solo un contenedor de esa red alcanza la base. Se ejecutan a demanda:
#   python devops/pila.py exec backend python /app/observabilidad/drift_monitor.py
COPY --chown=plurione:plurione ml_pipeline/src/drift_monitor.py /app/observabilidad/drift_monitor.py
COPY --chown=plurione:plurione ml_pipeline/src/model_registry.py /app/observabilidad/model_registry.py
# El extractor del bucle de realimentacion. Va en la imagen porque necesita hablar con la
# base de PRODUCCION, que es donde estan los desenlaces comerciales; entrenar, en cambio,
# se hace fuera y con el CSV que este guion exporta.
#
# La separacion es deliberada y no es de comodidad: meter el entrenamiento aqui obligaria
# a llevar scikit-learn entero mas el generador sintetico a la imagen que atiende
# peticiones, y a que el proceso que sirve la API tuviera un camino para escribir un
# .joblib nuevo. Extraer es leer; entrenar y publicar son otra cosa y viven fuera.
#
#   python devops/pila.py exec backend python /app/observabilidad/feedback_dataset.py \
#       --salida /tmp/leads_reales.csv
COPY --chown=plurione:plurione ml_pipeline/src/feedback_dataset.py /app/observabilidad/feedback_dataset.py

# Frontend compilado, para la entrega unificada en http://<host>:8000. La ruta no es
# arbitraria: `main.py` resuelve `dist/` como dos niveles por encima del paquete `app`,
# es decir `/frontend/dist` cuando el código vive en `/app/app`.
COPY --chown=plurione:plurione frontend/dist /frontend/dist

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    DEBUG=False \
    ML_MODEL_PATH=/opt/plurione/models/lead_scorer_model.joblib \
    ML_REFERENCE_PROFILE=/opt/plurione/models/reference_profile.json

USER plurione

EXPOSE 8000

# Consulta el endpoint /health, que a su vez ejecuta un SELECT contra la base de datos.
# `start-period` cubre el arranque de uvicorn y la carga del modelo; sin él, Docker
# marcaría el contenedor como enfermo antes de que llegara a estar listo.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
