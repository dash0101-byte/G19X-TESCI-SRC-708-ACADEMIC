#!/bin/sh
# ==============================================================================
# RESTAURACIÓN REAL — recuperar la base de producción desde una copia
# ==============================================================================
#   cd devops
#   docker compose --profile respaldo run --rm \
#       -e VOLCADO=/respaldos/lead_scoring_db_20260909T031500Z.dump \
#       -e CONFIRMO_SOBRESCRIBIR=si \
#       restaurar
#
# Esta es la operación destructiva del conjunto: BORRA el contenido actual de la base y lo
# sustituye por el del volcado. Por eso exige dos cosas que no se pueden teclear por
# inercia: el archivo exacto —no se coge el último por su cuenta— y `CONFIRMO_SOBRESCRIBIR=si`.
#
# La otra guarda importante es detener el backend antes. Restaurar con la aplicación en
# marcha deja a los workers escribiendo sobre un esquema que se está reconstruyendo:
#
#   docker compose stop backend frontend
#   ...restaurar...
#   docker compose start backend frontend
#
# El script lo recuerda pero no lo hace: parar servicios desde dentro de un contenedor
# exigiría darle acceso al socket de Docker, que es acceso de root al anfitrión. Un aviso
# es preferible a esa concesión.
# ==============================================================================
set -eu

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-plurione}"
PGDATABASE="${PGDATABASE:-lead_scoring_db}"
export PGHOST PGPORT PGUSER

if [ -z "${PGPASSWORD:-}" ]; then
    echo "FALLO: PGPASSWORD no está definida." >&2
    exit 2
fi

VOLCADO="${VOLCADO:-}"
if [ -z "$VOLCADO" ]; then
    echo "FALLO: indique el volcado con -e VOLCADO=/respaldos/<archivo>.dump" >&2
    echo "" >&2
    echo "No se elige el más reciente automáticamente a propósito: el más reciente puede" >&2
    echo "ser justo el que ya contiene el borrado del que se quiere volver." >&2
    echo "" >&2
    echo "Disponibles:" >&2
    # El orden de las redirecciones importa: `>&2` primero —el listado va al canal de
    # error, junto al resto del mensaje— y `2>/dev/null` después, para callar el "no such
    # file" cuando no hay ninguno. Al revés, stderr acaba en /dev/null ANTES de que stdout
    # se apunte a él, y el listado desaparece entero.
    ls -1t "${DIRECTORIO_DE_RESPALDOS:-/respaldos}"/*.dump >&2 2>/dev/null || echo "  (ninguno)" >&2
    exit 2
fi

if [ ! -f "$VOLCADO" ]; then
    echo "FALLO: no existe '$VOLCADO'." >&2
    exit 2
fi

if [ "${CONFIRMO_SOBRESCRIBIR:-}" != "si" ]; then
    echo "FALLO: esto BORRA el contenido actual de '$PGDATABASE' en $PGHOST." >&2
    echo "       Para continuar: -e CONFIRMO_SOBRESCRIBIR=si" >&2
    exit 2
fi

if [ -f "$VOLCADO.sha256" ]; then
    echo "== Comprobando la huella del volcado =="
    ( cd "$(dirname "$VOLCADO")" && sha256sum -c "$(basename "$VOLCADO").sha256" )
fi

echo "== Restaurando '$VOLCADO' sobre '$PGDATABASE' =="
echo "   Si el backend sigue en marcha, deténgalo AHORA (Ctrl-C) y vuelva:"
echo "     docker compose stop backend frontend"

# `--clean --if-exists` borra cada objeto antes de recrearlo, dentro de la propia
# restauración. Es preferible a un DROP DATABASE porque no exige desconectar a todo el
# mundo del servidor, y `--if-exists` evita el ruido de errores por objetos que no estaban.
#
# `--single-transaction` hace que la restauración sea todo o nada: si falla a mitad, la
# base se queda como estaba en lugar de convertirse en una mezcla de las dos versiones,
# que es el estado más difícil de arreglar de todos.
pg_restore \
    --dbname="$PGDATABASE" \
    --clean --if-exists \
    --no-owner --no-privileges \
    --single-transaction \
    --exit-on-error \
    "$VOLCADO"

echo "== Restauración terminada =="
echo "   Compruebe el esquema antes de volver a servir:"
echo "     docker compose run --rm migrate alembic current"
echo "   Debe coincidir con la revisión que espera el código; si el volcado es más viejo"
echo "   que el despliegue, aplique lo que falte con 'alembic upgrade head'."
