# ==============================================================================
# SISTEMA INTELIGENTE DE LEAD SCORING - DOCKERFILE FRONTEND (REACT + NGINX)
# ==============================================================================
#
# Dos destinos, y conviene entender por qué (N-17):
#
#   production-stage  — compila la SPA aquí dentro. Es lo que usa
#                     `docker compose up --build` en un portátil: basta el código.
#
#   desde-artefacto   — NO compila: copia el `dist/` que ya viene en el contexto.
#                     Es lo que usa el pipeline, que compila una vez en el trabajo
#                     `frontend`, corre allí las pruebas y el `linter` sobre ese
#                     código, publica el resultado como artefacto y lo mete tal cual
#                     en la imagen.
#
# NINGUNA DE LAS DOS ES «LA DE POR DEFECTO», Y ESTA LÍNEA DECÍA QUE SÍ (29-09-2026).
#
# Decía «production-stage (por defecto)», y no lo era: cuando un servicio de Compose no
# declara `target`, Docker construye la **última** etapa del archivo, que es la de abajo del
# todo. `desde-artefacto` se añadió después de `production-stage`, así que pasó a ser la que
# se construía sin que nadie lo decidiera, y `docker compose up --build` dejó de compilar
# nada: servía el `dist/` que hubiera quedado en la carpeta del portátil.
#
# Se encontró al levantar la pila para mirar el trabajo del capítulo 36 y ver que el panel
# servía el bundle de cinco días antes. `devops/docker-compose.yml` declara ahora
# `target: production-stage`, y un control del CI exige que cualquier Dockerfile de tres
# etapas o más diga cuál quiere: con dos, la última es la de ejecución y no hay ambigüedad;
# a partir de tres, cuál es la buena no se deduce del orden, y el orden es lo único que
# Docker mira.
#
# La distinción no es cosmética. Con un solo destino, el pipeline compilaba dos veces:
# una en el trabajo `frontend` —la que se probaba— y otra dentro de este Dockerfile
# —la que se publicaba—. Dos compilaciones no son la misma compilación: basta que
# `npm ci` resuelva algo distinto, o que el contexto de build excluya un archivo que
# el otro sí veía, para que lo verificado y lo desplegado dejen de coincidir. Y no
# habría ningún síntoma: las dos terminan con éxito.
#
# IMÁGENES BASE FIJADAS POR HUELLA (capítulo 22)
#
# Una etiqueta como `nginx:alpine` apunta hoy a una imagen y mañana a otra: dos
# construcciones del mismo Dockerfile podían llevar sistemas base distintos sin que nada
# en el repositorio cambiara. La huella `@sha256:` fija la imagen exacta. La etiqueta se
# conserva delante solo para que se lea qué es y para que el guion de renovación sepa qué
# seguir; lo que se descarga lo decide la huella.
#
# Renovar es un acto explícito, con su diff:
#   python scripts/renovar_imagenes.py            # dice qué huellas han quedado atrás
#   python scripts/renovar_imagenes.py --aplicar  # las reescribe en todos los archivos

# ------------------------------------------------------------------ etapa de build
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build-stage
WORKDIR /app

COPY package.json package-lock.json ./
# `npm ci` y no `npm install`: instala exactamente lo que fija el lockfile y falla si
# este no concuerda con package.json, en vez de resolver versiones nuevas en silencio.
# Dos builds de la misma revision producen asi el mismo bundle.
RUN npm ci

COPY . .
# El `dist/` del anfitrión ya no se excluye del contexto —el destino `desde-artefacto`
# lo necesita—, así que aquí se borra antes de compilar. Sin esta línea, un `dist/`
# viejo del portátil podría acabar en la imagen si la compilación no lo sobrescribiera
# entero, y eso es exactamente el fallo silencioso que N-17 quería cerrar.
RUN rm -rf dist && npm run build

# ------------------------------------------------- base común del servidor web
FROM nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3 AS servidor

# Parches del sistema base, con versión (N-10, capítulo 22).
#
# Hasta el capítulo 22 esto era `apk --no-cache upgrade`. Recogía el parche de `libuuid`
# —siete ALTAS en Trivy que Alpine ya había corregido—, pero a cambio dos construcciones en
# fechas distintas daban imágenes distintas, y lo que entraba en cada una no lo decidía
# nadie: lo decidía el día.
#
# Ahora la base va fijada por huella y los paquetes que hay que subir por encima de ella se
# nombran con su versión exacta. Son los que `apk version -l '<'` señala en la base fijada
# y afectan a lo que la imagen ejecuta; `apk-tools` también aparece y no se sube, porque la
# imagen no instala nada después de construirse.
#
# Alpine solo publica la última revisión de cada paquete en una rama. El día que salga otra,
# esta línea deja de construir con «unable to select packages». Es lo buscado: el aviso
# llega como un fallo de construcción y no como una imagen distinta en silencio. Se resuelve
# renovando la base y mirando qué sigue haciendo falta:
#   docker run --rm <imagen base> sh -c "apk update -q && apk version -l '<'"
RUN apk add --no-cache 'libuuid=2.42.3-r1' 'xz-libs=5.8.4-r0'

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Fragmento con las cabeceras de seguridad, incluido desde cada `location`.
COPY security-headers.conf /etc/nginx/conf.d/security-headers.conf
# Fragmento con las directivas de proxy de la puerta estrecha (capítulo 34), incluido desde
# cada `location` del servidor del 8080.
COPY puerta-publica.conf /etc/nginx/conf.d/puerta-publica.conf
# El 80 es el panel, en la red local. El 8080 es la puerta estrecha, y es el único puerto
# que mira el túnel; se publica solo en 127.0.0.1 (véase `devops/docker-compose.yml`).
EXPOSE 80 8080
CMD ["nginx", "-g", "daemon off;"]

# ---------------------------------------- destino por defecto: compilar aquí dentro
FROM servidor AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# ------------------------------ destino del pipeline: consumir el artefacto probado
FROM servidor AS desde-artefacto
COPY dist/ /usr/share/nginx/html/
# Que el artefacto llegue vacío o a medias es un fallo posible: `download-artifact` no
# se queja si el nombre no existe. Sin esta comprobación, la imagen se construiría con
# un directorio vacío y nginx serviría un 404 por cada ruta, sin que nada fallara antes.
RUN test -f /usr/share/nginx/html/index.html \
  && test -d /usr/share/nginx/html/assets \
  || (echo "El artefacto del frontend no trae index.html ni assets/" && exit 1)
