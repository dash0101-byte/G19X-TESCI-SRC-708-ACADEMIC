#!/bin/sh
# ==============================================================================
# PRUEBA DE RESTAURACIÓN — una copia que nadie ha restaurado nunca no es una copia
# ==============================================================================
#   cd devops && docker compose --profile respaldo run --rm prueba-de-restauracion
#
# Toma el volcado más reciente, lo restaura en una base DESECHABLE del mismo servidor y
# compara el recuento de filas de cada tabla con el de la base real. Si algo no cuadra,
# sale con código distinto de cero.
#
# Por qué así y no «restaurando en un servidor aparte»: lo que se está comprobando es que
# el ARCHIVO sirve —que se lee entero, que el esquema se reconstruye, que las claves ajenas
# se satisfacen y que no falta la mitad de las filas—. Eso se demuestra igual de bien en
# una base temporal del mismo motor, y se puede ejecutar en cualquier momento sin montar
# nada. Lo que esta prueba NO demuestra es que sobreviviría a la pérdida del servidor
# entero; para eso hace falta un ensayo en otra máquina, y queda dicho en el README.
#
# La base temporal se llama siempre igual y se borra al empezar y al terminar. Nunca toca
# la base real: la comparación se hace con dos conexiones distintas y todo lo que escribe
# va a la desechable.
# ==============================================================================
set -eu

PGHOST="${PGHOST:-postgres}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-plurione}"
PGDATABASE="${PGDATABASE:-lead_scoring_db}"
export PGHOST PGPORT PGUSER

DIRECTORIO="${DIRECTORIO_DE_RESPALDOS:-/respaldos}"
BASE_DE_PRUEBA="${BASE_DE_PRUEBA:-lead_scoring_prueba_de_restauracion}"

if [ -z "${PGPASSWORD:-}" ]; then
    echo "FALLO: PGPASSWORD no está definida." >&2
    exit 2
fi

# Guarda de seguridad. El nombre de la base desechable es configurable, y una errata que
# lo hiciera coincidir con la base real haría que esta prueba BORRARA los datos de
# producción antes de restaurar. La comprobación cuesta tres líneas.
if [ "$BASE_DE_PRUEBA" = "$PGDATABASE" ]; then
    echo "FALLO: BASE_DE_PRUEBA ('$BASE_DE_PRUEBA') es la base real. Esta prueba la" >&2
    echo "       borraría antes de restaurar. Elija otro nombre." >&2
    exit 2
fi

VOLCADO="${VOLCADO:-}"
if [ -z "$VOLCADO" ]; then
    VOLCADO="$(ls -1t "$DIRECTORIO"/*.dump 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$VOLCADO" ] || [ ! -f "$VOLCADO" ]; then
    echo "FALLO: no hay ningún volcado en $DIRECTORIO. Ejecute antes 'respaldo'." >&2
    exit 1
fi

echo "== Volcado a probar: $VOLCADO =="

if [ -f "$VOLCADO.sha256" ]; then
    echo "== Comprobando la huella =="
    # Se comprueba antes de restaurar: si el archivo se corrompió en el disco, conviene
    # saber que el fallo es del archivo y no de la restauración.
    ( cd "$(dirname "$VOLCADO")" && sha256sum -c "$(basename "$VOLCADO").sha256" )
fi

retirar_base_desechable() {
    psql --dbname=postgres --quiet --no-psqlrc \
         --command="DROP DATABASE IF EXISTS \"$BASE_DE_PRUEBA\";" >/dev/null 2>&1 || true
}

# La retirada va en un `trap` y no solo al final.
#
# Con `set -e`, un `pg_restore` que falla aborta el guion antes de llegar al DROP, y la
# base desechable se queda en el servidor con la restauracion a medias dentro. Es
# precisamente el caso que mas se repite —el que se reintenta mientras se investiga—, de
# modo que cada intento dejaba otra base huerfana en el servidor de produccion.
trap retirar_base_desechable EXIT

echo "== Preparando la base desechable '$BASE_DE_PRUEBA' =="
retirar_base_desechable
psql --dbname=postgres --quiet --no-psqlrc --set=ON_ERROR_STOP=1 \
     --command="CREATE DATABASE \"$BASE_DE_PRUEBA\";"

echo "== Restaurando =="
# `--exit-on-error`: sin esto, `pg_restore` informa de los errores y termina con código 0,
# de modo que una restauración a medias se leería como un éxito. Es la opción que
# convierte esta prueba en una prueba.
pg_restore --dbname="$BASE_DE_PRUEBA" --no-owner --no-privileges --exit-on-error "$VOLCADO"

echo "== Comparando recuentos por tabla =="

listar_recuentos() {
    # Recorre las tablas del esquema público y emite «tabla<TAB>filas». `--tuples-only` y
    # `--no-align` para que la salida sea comparable sin recortar espacios.
    psql --dbname="$1" --quiet --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
         --command="
            SELECT relname || E'\t' || n_live_tup
            FROM (
                SELECT c.relname,
                       (xpath('/row/c/text()',
                              query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
                                                  n.nspname, c.relname),
                                           false, true, '')))[1]::text::bigint AS n_live_tup
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'r' AND n.nspname = 'public'
            ) t
            ORDER BY relname;"
}

ORIGEN="$(mktemp)"
COPIA="$(mktemp)"
listar_recuentos "$PGDATABASE"    > "$ORIGEN"
listar_recuentos "$BASE_DE_PRUEBA" > "$COPIA"

echo "--- original ($PGDATABASE) ---"
cat "$ORIGEN"
echo "--- restaurado ($BASE_DE_PRUEBA) ---"
cat "$COPIA"

RESULTADO=0
if diff -u "$ORIGEN" "$COPIA" > /dev/null; then
    echo ""
    echo "== La restauración reproduce el original tabla por tabla =="
else
    echo ""
    echo "FALLO: el contenido restaurado NO coincide con el original:" >&2
    diff -u "$ORIGEN" "$COPIA" >&2 || true
    echo "" >&2
    echo "Una diferencia aquí puede ser legítima —si alguien escribió en la base entre el" >&2
    echo "volcado y esta comprobación—, pero NO debe darse por buena sin mirarla: es" >&2
    echo "exactamente la forma que tiene una copia incompleta de pasar desapercibida." >&2
    RESULTADO=1
fi

rm -f "$ORIGEN" "$COPIA"

# La retirada la hace el `trap` al salir, pase lo que pase.
echo "== Retirando la base desechable =="

exit "$RESULTADO"
