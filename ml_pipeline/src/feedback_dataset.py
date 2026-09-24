"""
Bucle de realimentación: de los resultados comerciales reales a un dataset etiquetado.

El modelo que hoy sirve en producción se entrenó con datos sintéticos, y por tanto sus
métricas verifican la integridad del pipeline pero no predicen nada del negocio. Este
módulo es el camino para sustituir esos datos por los propios: cada prospecto que llega a
un estado terminal —`WON` o `LOST`— es una etiqueta real que el sistema ya posee.

Tres decisiones sostienen el diseño, y las tres existen para evitar errores que producen
modelos con métricas excelentes y valor nulo:

**1. Se etiqueta sobre la instantánea, nunca sobre el estado actual.**
   Un prospecto ganado lleva, por definición, propuesta enviada y reunión agendada. Si se
   construyera el dataset leyendo los prospectos tal como están hoy, el modelo aprendería
   que enviar propuestas causa cierres: la relación invertida, y además inútil, porque en
   el momento en que hay que decidir a quién llamar todavía no se ha enviado ninguna
   propuesta. Por eso se usa `ScoreHistory.feature_snapshot`, que guarda lo que se sabía
   cuando aún no se sabía el desenlace.

**2. Los prospectos sin desenlace se excluyen, no se cuentan como fracasos.**
   Un prospecto en `NEGOTIATION` no es un `LOST`: es un caso cuyo resultado aún no se
   conoce. Tratar la censura por la derecha como negativo es el error más común al montar
   estos bucles, y sesga el modelo hacia el pesimismo justo en los prospectos más activos.

**3. Solo cuenta la instantánea anterior al desenlace.**
   Se toma la puntuación más antigua de cada prospecto, que corresponde al momento en que
   entró al embudo. Las posteriores ya están contaminadas por el avance comercial.

## El desenlace registrado (capítulo 30)

Desde el capítulo 30 la etiqueta no se deduce del estado: se **lee**. Cerrar un prospecto
exige decir cómo acabó, por qué motivo —de una lista cerrada— y en qué fecha, y eso queda
en la tabla `desenlaces` junto con el score que tenía al cerrarse y la versión del vector
con que se tomó su instantánea de entrada. El dataset usa esa fila tal cual.

La diferencia no es cosmética. Antes, «cerrado» significaba «alguien dejó la etapa en WON
en algún momento» y la fecha de la etiqueta era `updated_at`, es decir, la última vez que
alguien tocó la ficha por cualquier motivo. Ahora hay fecha de cierre de verdad, y el
motivo viaja como columna de contexto: **no es una variable del modelo** —no entra en
`COLUMNAS_DEL_MODELO` ni en la huella— porque el motivo se conoce al cerrar y no el día que
hay que decidir a quién llamar, que es cuando el modelo tiene que servir para algo. Está
para poder segmentar un análisis después.

Los prospectos que se cerraron **antes** de que existiera el desenlace siguen entrando, con
su etiqueta deducida del estado, y el manifiesto los cuenta aparte. Inventarles un motivo
habría sido peor que no tenerlo.

Uso:
    python ml_pipeline/src/feedback_dataset.py --salida ml_pipeline/data/leads_reales.csv
"""
import argparse
import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

_BACKEND = os.path.abspath(os.path.join(_AQUI, "..", "..", "backend"))
if os.path.isdir(_BACKEND) and _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.database import SessionLocal  # noqa: E402
from app.core.desenlaces import (  # noqa: E402
    GANADO,
    MINIMO_DE_CASOS,
    MINIMO_POR_CLASE,
    etiqueta_de_motivo,
)
from app.core.vector_del_modelo import (  # noqa: E402
    COLUMNAS_DEL_MODELO,
    VERSION_DEL_VECTOR,
    es_instantanea_vigente,
    ingresos_o_ausente,
    instantanea_utilizable,
)
from app.models.entities import Desenlace, Lead, LeadStatus, ScoreHistory  # noqa: E402
from app.services.retencion_service import consulta_instantanea_de_entrada  # noqa: E402
from model_registry import huella_de_datos  # noqa: E402

# Estados que constituyen un desenlace conocido. `UNQUALIFIED` cuenta como negativo: el
# prospecto fue evaluado y descartado, que es una decisión, no una ausencia de decisión.
ESTADOS_GANADOS = {LeadStatus.WON}
ESTADOS_PERDIDOS = {LeadStatus.LOST, LeadStatus.UNQUALIFIED}

# Mínimos por debajo de los cuales reentrenar es contraproducente. Con pocas decenas de
# ejemplos el modelo memoriza a los clientes concretos que cerraron ese trimestre.
#
# Viven en `app.core.desenlaces` desde el capítulo 30, no aquí, y el motivo es el mismo que
# llevó el vector del modelo a `app.core.vector_del_modelo`: el contador que enseña el panel
# del líder tiene que exigir EXACTAMENTE estos números. Dos copias se habrían desincronizado
# el día que alguien subiera una, y el panel diría «ya se puede reentrenar» mientras este
# extractor se niega. El nombre local se conserva porque es el que usan las pruebas y el
# guion de línea de órdenes.
MINIMO_EJEMPLOS = MINIMO_DE_CASOS

# Columnas de contexto: acompañan a cada fila y NO son variables del modelo. No entran en
# `COLUMNAS_MODELO` ni en la huella del dataset a propósito —el motivo de un cierre se
# conoce al cerrar, no el día que hay que decidir a quién llamar—, pero sin ellas no se
# podría segmentar un análisis por motivo ni acotar una cohorte por fecha real de cierre.
COLUMNAS_DE_CONTEXTO = ["resultado", "motivo", "motivo_etiqueta", "cerrado_el", "tramo"]

# Variables que consume el modelo, en el mismo orden que `train_model.FEATURE_COLS`: las dos
# salen de `app.core.vector_del_modelo`.
COLUMNAS_MODELO = list(COLUMNAS_DEL_MODELO)


class DatasetInsuficiente(RuntimeError):
    """No hay suficientes desenlaces reales para reentrenar con sentido."""


def _instantanea_de_entrada(db, lead_id: int) -> Optional[ScoreHistory]:
    """
    Primera puntuación registrada del prospecto: la de su entrada al embudo.

    Se ordena por `calculated_at` y no por `id` porque una reindexación o una migración
    podrían no preservar la correspondencia entre ambos.

    El criterio lo define `retencion_service`, no este módulo: la purga del historial tiene
    que conservar exactamente esta fila, y dos copias del mismo criterio acaban
    discrepando. Si la purga borrara la entrada, aquí no fallaría nada —se tomaría la
    siguiente instantánea, ya contaminada por el avance comercial—.
    """
    return consulta_instantanea_de_entrada(db, lead_id).first()


def _fila_desde_instantanea(instantanea: Dict[str, Any], lead: Lead) -> Optional[Dict[str, Any]]:
    """Traduce la instantánea al vector que espera el modelo, o None si está incompleta."""
    if not instantanea:
        return None
    if not instantanea_utilizable(instantanea):
        # Una instantánea de la versión 1 no dice qué mensajes eran de LinkedIn ni cuántas
        # llamadas quedaron sin respuesta: traducirla exigiría inventar las dos cosas. Una
        # incompleta tampoco sirve, porque rellenarla con ceros le diría al modelo «no hubo
        # actividad» donde lo que hay es un hueco.
        #
        # El criterio es el de `vector_del_modelo` y no uno propio: el contador del panel
        # (capítulo 30) promete cuántos ejemplos hay, y con dos criterios prometería más de
        # los que este extractor después encuentra.
        return None

    fila: Dict[str, Any] = {
        # Los firmográficos no se guardan en la instantánea porque no cambian con el
        # avance comercial: un CTO de FinTech lo seguía siendo el día que entró.
        "job_title": lead.job_title or "",
        "industry": lead.industry or "",
        # Vacío, como al puntuar: un tamaño no indicado no es «1-10». Aquí se entrenaba con
        # «1-10» y en producción se puntuaba con vacío, dos vectores para el mismo prospecto.
        "company_size": lead.company_size or "",
        # Ausente, no cero ni 100 000: el modelo imputa y sabe que faltaba (capítulo 24).
        "annual_revenue": ingresos_o_ausente(lead.annual_revenue),
        "source_channel": lead.source or "Website",
    }

    conductuales = [c for c in COLUMNAS_MODELO if c not in fila]
    for columna in conductuales:
        if columna not in instantanea:
            # Instantánea de una versión anterior del vector: descartarla es preferible a
            # imputar un cero, que el modelo leería como «no hubo actividad».
            return None
        fila[columna] = instantanea[columna]

    return fila


def construir_dataset(
    db=None, exigir_minimos: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Extrae el dataset etiquetado con desenlaces reales y su manifiesto de procedencia.

    Devuelve `(dataframe, manifiesto)`. El manifiesto acompaña siempre al dataset: sin
    saber de qué ventana temporal salió y con qué balance de clases, una métrica calculada
    sobre él no es interpretable.
    """
    propia = db is None
    db = db or SessionLocal()
    try:
        estados_terminales = list(ESTADOS_GANADOS | ESTADOS_PERDIDOS)
        leads = (
            db.query(Lead)
            .filter(Lead.status.in_(estados_terminales))
            .order_by(Lead.id)
            .all()
        )

        # Los desenlaces registrados, de una consulta y no de una por prospecto. Desde el
        # capítulo 30 la etiqueta se LEE de aquí en lugar de deducirse del estado.
        desenlaces: Dict[int, Desenlace] = {
            d.lead_id: d
            for d in db.query(Desenlace)
            .filter(Desenlace.lead_id.in_([lead.id for lead in leads]))
            .all()
        } if leads else {}

        filas: List[Dict[str, Any]] = []
        sin_instantanea = 0
        de_un_vector_anterior = 0
        con_motivo = 0
        motivos: Dict[str, int] = {}

        for lead in leads:
            historial = _instantanea_de_entrada(db, lead.id)
            if historial is None:
                sin_instantanea += 1
                continue

            instantanea = historial.feature_snapshot or {}
            fila = _fila_desde_instantanea(instantanea, lead)
            if fila is None:
                sin_instantanea += 1
                if instantanea and not es_instantanea_vigente(instantanea):
                    de_un_vector_anterior += 1
                continue

            desenlace = desenlaces.get(lead.id)
            if desenlace is not None:
                # La etiqueta que una persona registró, con su motivo y su fecha real de
                # cierre. No se comprueba que cuadre con `lead.status` y se corrige en
                # silencio: si algún día discreparan, lo que hay que saber es cuál de los
                # dos mintió, y eso se responde mirando la bitácora del cierre.
                fila["converted"] = 1 if desenlace.resultado == GANADO else 0
                fila["resultado"] = desenlace.resultado
                fila["motivo"] = desenlace.motivo
                fila["motivo_etiqueta"] = etiqueta_de_motivo(desenlace.resultado, desenlace.motivo)
                fila["cerrado_el"] = desenlace.cerrado_el
                fila["tramo"] = desenlace.tramo
                con_motivo += 1
                clave = f"{desenlace.resultado}:{desenlace.motivo}"
                motivos[clave] = motivos.get(clave, 0) + 1
            else:
                # Cerrado antes de que existiera el desenlace, o descartado
                # (`UNQUALIFIED`), que no tiene lista de motivos propia. Entra igual: la
                # etiqueta se deduce del estado, como desde el capítulo 18. Inventarle un
                # motivo habría llenado el análisis de una respuesta que nadie dio.
                fila["converted"] = 1 if lead.status in ESTADOS_GANADOS else 0
                for columna in COLUMNAS_DE_CONTEXTO:
                    fila[columna] = None

            fila["lead_id"] = lead.id
            fila["etiquetado_en"] = lead.updated_at
            fila["puntuado_en"] = historial.calculated_at
            filas.append(fila)

        # Prospectos aún en el embudo: se cuentan para el manifiesto pero NO entran. Su
        # resultado es desconocido, no negativo.
        en_curso = (
            db.query(Lead)
            .filter(~Lead.status.in_(estados_terminales))
            .count()
        )

        # «Ningún prospecto ha cerrado todavía» y «esta no es la base que usted cree» se
        # ven exactamente igual desde aquí: cero filas. La distinción importa porque
        # `DATABASE_URL` por defecto es relativa (`sqlite:///./lead_scoring.db`), así que
        # ejecutar esto desde otro directorio CREA una base vacía en vez de fallar, y el
        # informe resultante —cero desenlaces, cero en curso— parece un diagnóstico del
        # negocio cuando es un error de ruta.
        base_vacia = en_curso == 0 and not filas

        df = pd.DataFrame(filas)
        positivos = int(df["converted"].sum()) if not df.empty else 0
        negativos = len(df) - positivos

        manifiesto = {
            "generado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ejemplos": len(df),
            "positivos_won": positivos,
            "negativos_lost_o_descartados": negativos,
            "tasa_de_conversion": round(positivos / len(df), 4) if len(df) else 0.0,
            "prospectos_en_curso_excluidos": en_curso,
            "terminales_sin_instantanea_utilizable": sin_instantanea,
            # Parte de los anteriores: se puntuaron con un vector de otra versión. Se cuentan
            # aparte porque no son un defecto de los datos, sino el precio de no inventar al
            # cambiar el vector, y conviene ver cuánto cuesta.
            "terminales_con_instantanea_de_un_vector_anterior": de_un_vector_anterior,
            # Capítulo 30. De las filas del dataset, cuántas llevan un desenlace registrado
            # con motivo y cuántas heredan la etiqueta del estado porque se cerraron antes.
            # Se cuentan aparte para que la proporción se vea: mientras la segunda cifra
            # sea grande, un análisis por motivo describe una minoría de los cierres.
            "con_desenlace_registrado": con_motivo,
            "etiquetados_solo_por_su_estado": len(filas) - con_motivo,
            "motivos": dict(sorted(motivos.items())),
            "version_del_vector": VERSION_DEL_VECTOR,
            "base_sin_prospectos": base_vacia,
            "ventana": {
                "desde": df["puntuado_en"].min().isoformat() if len(df) else None,
                "hasta": df["puntuado_en"].max().isoformat() if len(df) else None,
            },
            "advertencia": (
                "Etiquetas tomadas del desenlace registrado del prospecto —o, en los que se "
                "cerraron antes de que existiera, de su estado terminal— sobre la "
                "instantánea de variables del momento de su entrada al embudo. El motivo y "
                "el tramo son contexto y NO variables del modelo: se conocen al cerrar, no "
                "el día que hay que decidir a quién llamar. Los prospectos sin desenlace "
                "conocido se excluyen; contarlos como negativos sesgaría el modelo hacia el "
                "pesimismo."
            ),
        }

        if exigir_minimos:
            if len(df) < MINIMO_EJEMPLOS:
                raise DatasetInsuficiente(
                    f"Solo hay {len(df)} desenlaces utilizables y se exigen {MINIMO_EJEMPLOS}. "
                    "Reentrenar con menos produce un modelo que memoriza los clientes "
                    "concretos de este periodo en lugar de generalizar."
                )
            if min(positivos, negativos) < MINIMO_POR_CLASE:
                raise DatasetInsuficiente(
                    f"Clases desbalanceadas: {positivos} ganados y {negativos} perdidos; se "
                    f"exigen {MINIMO_POR_CLASE} de cada. Con menos, la clase minoritaria no "
                    "aporta señal suficiente."
                )

        return df, manifiesto
    finally:
        if propia:
            db.close()


def huella_del_dataset(df: pd.DataFrame) -> str:
    """
    SHA-256 del contenido, para poder decir con qué datos exactos se entrenó un modelo.

    La implementación vive ahora en `model_registry.huella_de_datos`, junto al registro que
    la consume, y no aquí. El motivo es concreto: `train_model.py` necesita calcular la
    huella y este módulo importa `app.core.database`, así que importarlo desde el
    entrenamiento habría exigido una base de datos viva para entrenar con datos sintéticos.
    Se conserva el nombre porque es el que usan las pruebas y el guion de línea de órdenes.
    """
    return huella_de_datos(df)


def main(argv=None) -> int:
    # `argv` explicito, como en `drift_monitor.main`: sin el, la unica forma de probar
    # este camino seria lanzar un subproceso, y el camino que no se prueba es justo el que
    # reventaba con un KeyError.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--salida",
        default=os.path.join(_AQUI, "..", "data", "leads_reales.csv"),
        help="Ruta del CSV etiquetado a generar.",
    )
    parser.add_argument(
        "--sin-minimos",
        action="store_true",
        help="Genera el dataset aunque no alcance el tamaño mínimo (solo para inspección).",
    )
    args = parser.parse_args(argv)

    try:
        df, manifiesto = construir_dataset(exigir_minimos=not args.sin_minimos)
    except DatasetInsuficiente as exc:
        print(f"[REALIMENTACIÓN] No se genera el dataset: {exc}")
        return 1

    if df.empty:
        # `--sin-minimos` es justo la opcion a la que se recurre el primer dia, para mirar
        # que hay. Con cero desenlaces terminaba en un KeyError contra columnas que un
        # DataFrame vacio no tiene: una traza de pandas en lugar de la respuesta, que es
        # «todavia no ha cerrado ningun prospecto».
        if manifiesto.get("base_sin_prospectos"):
            print("[REALIMENTACION] La base no tiene NINGUN prospecto, ni cerrado ni en curso.")
            print("                 Compruebe DATABASE_URL: la ruta por defecto es relativa,")
            print("                 y ejecutar esto desde otro directorio CREA una base vacia")
            print("                 en vez de fallar. Un informe de cero desenlaces sobre una")
            print("                 base recien creada parece un diagnostico del negocio.")
        else:
            print("[REALIMENTACION] Ningun desenlace utilizable todavia: "
                  f"{manifiesto['prospectos_en_curso_excluidos']} prospectos siguen en curso y "
                  f"{manifiesto['terminales_sin_instantanea_utilizable']} cerrados no tienen "
                  "instantanea aprovechable.")
            print("                 No se escribe dataset. Un CSV vacio se entrena igual de mal")
            print("                 que uno malo, y ademas sin avisar.")
        print(json.dumps(manifiesto, indent=2, ensure_ascii=False, default=str))
        return 1

    salida = os.path.abspath(args.salida)
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    df.to_csv(salida, index=False)

    manifiesto["huella_sha256"] = huella_del_dataset(df[COLUMNAS_MODELO + ["converted"]])
    ruta_manifiesto = os.path.splitext(salida)[0] + "_manifiesto.json"
    with open(ruta_manifiesto, "w", encoding="utf-8") as fh:
        json.dump(manifiesto, fh, indent=2, ensure_ascii=False, default=str)

    print(f"Dataset etiquetado: {salida}")
    print(f"Manifiesto:         {ruta_manifiesto}")
    print(json.dumps(manifiesto, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
