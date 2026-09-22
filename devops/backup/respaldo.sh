#!/bin/sh
# ==============================================================================
# COPIA DE SEGURIDAD DE LA BASE DE LEAD SCORING
# ==============================================================================
# Se ejecuta desde un contenedor con la MISMA imagen que el servidor:
#
#   cd devops && docker compose --profile respaldo run --rm respaldo
#
# Que la imagen sea la misma no es comodidad: `pg_dump` se niega a volcar un servidor
# más nuevo que él, y esa negativa aparece el día que alguien actualiza PostgreSQL y no
# el cliente. Compartir imagen hace imposible esa discrepancia.
#
# Qué hace, en orden:
#   1. Vuelca la base en formato personalizado (`-Fc`), comprimido y restaurable por
#      partes con `pg_restore`.
#   2. Comprueba que el archivo se puede LEER (`pg_restore --list`). Un volcado que se
#      escribió a medias —disco lleno, contenedor detenido— pesa lo suyo y parece bueno
#      hasta el día que hace falta.
#   3. Comprueba que no sea sospechosamente pequeño. Una base vacía por accidente produce
#      un volcado válido de unos pocos kilobytes: pasaría el paso 2 sin problema.
#   4. Deja su huella SHA-256 al lado, para detectar corrupción posterior en el disco.
#   5. Retira los volcados que ya superan la retención.
#
# Lo que NO hace, y conviene saberlo: no copia el volcado fuera de esta máquina. Una copia
# en el mismo disco que el original protege de un `DROP TABLE`, no de que se muera el
# disco. Llevarla a otro sitio es un paso de operación que depende de dónde se despliegue.
# ==============================================================================
set -eu

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-plurione}"
PGDATABASE="${PGDATABASE:-lead_scoring_db}"
export PGHOST PGPORT PGUSER PGDATABASE

DIRECTORIO="${DIRECTORIO_DE_RESPALDOS:-/respaldos}"
RETENCION_DIAS="${RETENCION_DIAS:-14}"
# Por debajo de esto se considera que algo salió mal. El esquema solo, sin una fila,
# ronda los 15 KB comprimidos.
TAMANO_MINIMO_BYTES="${TAMANO_MINIMO_BYTES:-10240}"

if [ -z "${PGPASSWORD:-}" ]; then
    echo "FALLO: PGPASSWORD no está definida. Se toma del entorno y NUNCA de la línea de" >&2
    echo "       órdenes: los argumentos de un proceso los lee cualquiera con 'ps'." >&2
    exit 2
fi

mkdir -p "$DIRECTORIO"

# Marca en UTC y con segundos. Con la hora local, dos volcados de la madrugada del cambio
# de horario reciben el mismo nombre y el segundo pisa al primero.
MARCA="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINO="$DIRECTORIO/${PGDATABASE}_${MARCA}.dump"
PARCIAL="$DESTINO.parcial"

echo "== Volcando $PGDATABASE desde $PGHOST:$PGPORT =="
# Se escribe con extensión `.parcial` y se renombra al final. Así un volcado interrumpido
# nunca queda con el nombre de uno bueno, y la retención no lo confunde con una copia
# válida cuando toque borrar las viejas.
pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$PARCIAL"

echo "== Comprobando que el volcado se puede leer =="
if ! pg_restore --list "$PARCIAL" > /dev/null 2>&1; then
    echo "FALLO: el volcado no es legible por pg_restore. Se descarta." >&2
    rm -f "$PARCIAL"
    exit 1
fi

TAMANO="$(wc -c < "$PARCIAL" | tr -d ' ')"
if [ "$TAMANO" -lt "$TAMANO_MINIMO_BYTES" ]; then
    echo "FALLO: el volcado ocupa $TAMANO bytes, por debajo del mínimo" >&2
    echo "       ($TAMANO_MINIMO_BYTES). Suele significar que se volcó la base equivocada" >&2
    echo "       o que está vacía. Se descarta." >&2
    rm -f "$PARCIAL"
    exit 1
fi

mv "$PARCIAL" "$DESTINO"
sha256sum "$DESTINO" > "$DESTINO.sha256"

echo "== Copia terminada =="
echo "   archivo: $DESTINO"
echo "   tamaño : $TAMANO bytes"
echo "   huella : $(cut -d' ' -f1 "$DESTINO.sha256")"

echo "== Retirando copias de más de $RETENCION_DIAS días =="
# `-mtime +N` es «modificado hace más de N días completos». Se listan antes de borrar para
# que el registro diga qué desapareció: un borrado silencioso de copias es indistinguible
# de una copia que nunca se hizo.
find "$DIRECTORIO" -maxdepth 1 -name "${PGDATABASE}_*.dump" -type f -mtime "+$RETENCION_DIAS" -print
find "$DIRECTORIO" -maxdepth 1 -name "${PGDATABASE}_*.dump" -type f -mtime "+$RETENCION_DIAS" -exec rm -f {} \; -exec rm -f {}.sha256 \;

echo "== Copias disponibles =="
ls -la "$DIRECTORIO" | grep -F ".dump" || echo "   (ninguna)"
