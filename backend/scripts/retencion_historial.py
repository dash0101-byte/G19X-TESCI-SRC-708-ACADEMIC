"""
Purga programada: historial de puntuación (R-3) y demás plazos de conservación (capítulo 22).

Resume por prospecto y mes el detalle de `score_histories` que ha superado su plazo de
retención y lo borra. Las reglas —qué se conserva siempre y por qué— están en
`app/services/retencion_service.py`.

En la misma pasada aplica los plazos de `app/services/caducidad_service.py`: sesiones
caducadas, trabajos de recálculo terminados, registros del CRM y avisos de la bandeja «Sin
asociar». Hasta el capítulo 22 esas tablas no tenían plazo, y la de sesiones tenía incluso su
función de purga, que nada llamaba. Es la misma pasada y no un servicio nuevo a propósito: un
proceso más que supervisar es un proceso más que puede quedarse parado sin que nadie lo vea.

Y desde el capítulo 28, el **motor de reglas** (`app/services/motor_de_reglas.py`): lo que
cada asesor tiene que hacer hoy. Por el mismo argumento de arriba, y porque el motor y la
purga miran la misma clase de cosa —qué ha pasado con cada prospecto desde la última vez—,
no hacía falta un segundo reloj para preguntarlo. El motor corre **antes** de las purgas:
una tarea recién creada no se puede encontrar con que su prospecto ya no está.

Este guion solo ejecuta las reglas y deja constancia: cada pieza tiene su asiento en la
bitácora, y un fallo en una no impide las demás.

Uso:
    python backend/scripts/retencion_historial.py --simular     # cuenta, no escribe
    python backend/scripts/retencion_historial.py               # una pasada
    python backend/scripts/retencion_historial.py --cada 86400  # servicio

En la pila de despliegue corre como el servicio `retencion-historial`, con `--cada`.

Códigos de salida: 0 pasada correcta; 1 alguna pieza falló; 2 configuración inválida (un
plazo por debajo del mínimo). En modo servicio, un fallo de la pasada se informa y se
reintenta en el ciclo siguiente —una caída momentánea de la base no puede dejar la purga
parada hasta el próximo despliegue—, pero una configuración inválida termina el proceso:
repetirla cada día no la arregla, y un contenedor reiniciándose en bucle se ve.
"""
import argparse
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.abspath(os.path.join(_AQUI, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.audit import ACCION_HISTORIAL_RETENCION, ENTIDAD_HISTORIAL, registrar_evento  # noqa: E402
from app.core.config import RETENCION_MINIMA_DEL_HISTORIAL_MESES, settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.caducidad_service import aplicar_caducidad  # noqa: E402
from app.services.motor_de_reglas import ejecutar as ejecutar_reglas  # noqa: E402
from app.services.retencion_service import LOTE_POR_DEFECTO, aplicar_retencion  # noqa: E402

INTERVALO_SUGERIDO = 86400


def _resumir_historial(db, meses: int, lote: int, simular: bool) -> None:
    resultado = aplicar_retencion(db, meses=meses, lote=lote, simular=simular)
    verbo = "Simulacion" if simular else "Retencion aplicada"
    print(
        f"[RETENCION] {verbo}: se conserva el detalle desde {resultado.limite.date().isoformat()} "
        f"({meses} meses). {resultado.filas_resumidas} filas resumidas de {resultado.prospectos} "
        f"prospectos ({resultado.resumenes_nuevos} meses nuevos, {resultado.resumenes_fusionados} "
        f"fusionados); {resultado.filas_protegidas} filas vencidas conservadas por ser la entrada "
        f"o la vigente; {resultado.lotes_descartados} lotes descartados."
    )
    # La simulación no borra nada y no se anota: la bitácora dice lo que pasó, no lo
    # que se consultó que pasaría.
    if not simular:
        registrar_evento(
            db,
            accion=ACCION_HISTORIAL_RETENCION,
            entidad=ENTIDAD_HISTORIAL,
            metadatos=resultado.como_dict(),
        )


def _ejecutar_reglas(db, simular: bool) -> int:
    """
    El motor de reglas. Devuelve cuántas reglas fallaron.

    Simular no ejecuta nada. Una simulación que creara tareas no sería una simulación, y
    contar «cuántas crearía» exigiría escribir la mitad del motor otra vez solo para
    responder a una pregunta que nadie ha hecho todavía.
    """
    if simular:
        print("[REGLAS] Simulacion: el motor no se ejecuta.")
        return 0
    fallos = 0
    for resultado in ejecutar_reglas(db):
        if resultado.error:
            fallos += 1
            print(
                f"[REGLAS] {resultado.regla}: fallo ({resultado.error}). "
                "Queda anotado en la bitacora; las demas reglas se aplicaron."
            )
            continue
        print(
            f"[REGLAS] {resultado.regla}: {resultado.tareas} tareas, {resultado.avisos} avisos, "
            f"{resultado.cerradas} cerradas, {resultado.marcados} marcados."
        )
    return fallos


def una_pasada(meses: int, lote: int, simular: bool) -> int:
    """Historial, reglas y plazos, cada pieza por su lado. Devuelve 1 si alguna falló."""
    fallos = 0
    db = SessionLocal()
    try:
        try:
            _resumir_historial(db, meses, lote, simular)
        except Exception as exc:  # noqa: BLE001  (se informa y siguen los plazos)
            db.rollback()
            fallos += 1
            print(f"[RETENCION] El historial no se pudo resumir ({exc.__class__.__name__}: {exc}).")

        try:
            fallos += _ejecutar_reglas(db, simular)
        except Exception as exc:  # noqa: BLE001  (se informa y siguen los plazos)
            db.rollback()
            fallos += 1
            print(f"[REGLAS] El motor no se pudo ejecutar ({exc.__class__.__name__}: {exc}).")

        verbo = "se borrarian" if simular else "borradas"
        for resultado in aplicar_caducidad(db, simular=simular):
            if resultado.error:
                fallos += 1
                print(
                    f"[CADUCIDAD] {resultado.tabla}: la purga fallo ({resultado.error}). "
                    "Queda anotado en la bitacora; los demas plazos se aplicaron."
                )
                continue
            print(
                f"[CADUCIDAD] {resultado.tabla}: {resultado.filas} filas {verbo} "
                f"(plazo {resultado.dias} dias, corte {resultado.corte.date().isoformat()})."
            )
        return 1 if fallos else 0
    finally:
        db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--meses",
        type=int,
        default=settings.SCORE_HISTORY_RETENTION_MONTHS,
        help="Meses completos de detalle a conservar (por defecto, SCORE_HISTORY_RETENTION_MONTHS).",
    )
    parser.add_argument("--lote", type=int, default=LOTE_POR_DEFECTO, help="Prospectos por transacción.")
    parser.add_argument("--simular", action="store_true", help="Contar lo que se haría, sin escribir.")
    parser.add_argument(
        "--cada",
        type=int,
        default=0,
        help=f"Repetir cada N segundos en vez de una sola vez (sugerido: {INTERVALO_SUGERIDO}).",
    )
    args = parser.parse_args(argv)

    if args.meses < RETENCION_MINIMA_DEL_HISTORIAL_MESES:
        print(
            f"[RETENCION] No se purga: {args.meses} meses está por debajo del mínimo de "
            f"{RETENCION_MINIMA_DEL_HISTORIAL_MESES}."
        )
        return 2
    if args.lote < 1:
        print("[RETENCION] No se purga: el lote tiene que ser de al menos un prospecto.")
        return 2

    if args.cada <= 0:
        try:
            return una_pasada(args.meses, args.lote, args.simular)
        except Exception as exc:  # noqa: BLE001
            print(f"[RETENCION] La pasada fallo ({exc.__class__.__name__}: {exc}).")
            return 1

    print(f"[RETENCION] Purgando cada {args.cada} s; se conservan {args.meses} meses de detalle.")
    while True:
        try:
            una_pasada(args.meses, args.lote, args.simular)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[RETENCION] La pasada fallo ({exc.__class__.__name__}: {exc}). "
                "Se reintenta en el proximo ciclo."
            )
        time.sleep(args.cada)


if __name__ == "__main__":
    sys.exit(main())
