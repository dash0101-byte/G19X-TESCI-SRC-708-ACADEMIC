"""
Ensayo del bucle de realimentación de punta a punta, sobre una base desechable.

## Por qué existe este guion

El bucle está completo —`feedback_dataset.py` extrae los desenlaces, `train_model.py
--datos realimentacion` entrena con ellos— y hoy no tiene nada que procesar: en la base
no hay ningún prospecto en estado `WON` ni `LOST`. Todos siguen en curso.

Un camino de código que no se ejecuta hasta dentro de un ciclo comercial completo no
llega vivo a ese día. Cuando cierre el primer prospecto, alguien correrá el extractor y
se encontrará con lo que se encuentra siempre: una firma que cambió, una columna que se
renombró, un `import` que dejó de resolver. Y lo encontrará justo cuando por fin hay datos
y ganas de mirarlos.

Este guion levanta una base **temporal y desechable**, siembra en ella una cohorte cerrada,
y recorre el bucle entero: extracción, manifiesto, huella, entrenamiento y registro. No
mide el negocio —las etiquetas son sintéticas, y decir lo contrario sería justo el engaño
contra el que avisa el docstring de `feedback_dataset`—. Mide que **el camino funciona**.

## Las dos cohortes

    --tamano 45     lo que hay el primer trimestre: por debajo de los minimos
    --tamano 260    lo que hay cuando el bucle lleva un año andando

Con la primera, el ensayo enseña lo que se quiere enseñar: el modelo puede superar los
umbrales y aun así no debe publicarse, porque el intervalo de confianza del ROC-AUC ocupa
media escala.

Uso:
    python ml_pipeline/src/ensayo_del_bucle.py --tamano 45
    python ml_pipeline/src/ensayo_del_bucle.py --tamano 260 --entrenar
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

# El paquete `app` vive en `backend/`. Se anade aqui y no se exige `PYTHONPATH` fuera:
# un guion que solo funciona si quien lo invoca recuerda una variable de entorno es un
# guion que fallara en el pipeline y en el portatil del siguiente.
_BACKEND = os.path.abspath(os.path.join(_AQUI, "..", "..", "backend"))
if os.path.isdir(_BACKEND) and _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _preparar_base(directorio: str) -> str:
    """
    Fija `DATABASE_URL` a un archivo del directorio temporal, ANTES de importar `app`.

    El orden no es un detalle. `app.core.database` crea el `engine` al importarse, así que
    fijar la variable después no serviría de nada y este guion escribiría en la base de
    desarrollo —que es la que tiene los doce prospectos reales—.
    """
    ruta = os.path.join(directorio, "ensayo.db")
    os.environ["DATABASE_URL"] = "sqlite:///" + ruta.replace("\\", "/")
    os.environ.setdefault("ENVIRONMENT", "development")
    return ruta


def _sembrar(db, tamano: int, en_curso: int, semilla: int):
    """
    Siembra una cohorte cerrada con instantáneas de entrada coherentes.

    Las variables y su etiqueta salen del generador sintético del proyecto, no de números
    al azar: si la etiqueta no guardase ninguna relación con las variables, el ensayo
    entrenaría contra ruido puro, el ROC-AUC saldría en 0.5 y no distinguiría un bucle sano
    de uno que perdió el vector de variables por el camino.

    La instantánea se escribe **con los ceros del momento de entrada** en las señales que
    solo aparecen al avanzar el trato, y el estado actual del prospecto sí las lleva. Así
    el ensayo comprueba de paso lo que comprueban las pruebas: que el extractor lee la
    instantánea y no el estado de hoy.
    """
    import pandas as pd
    from app.core.vector_del_modelo import CLAVE_DE_VERSION, VERSION_DEL_VECTOR
    from app.models.entities import Lead, LeadStatus, ScoreCategory, ScoreHistory
    from synthetic_generator import generate_synthetic_leads_dataset

    df = generate_synthetic_leads_dataset(num_samples=tamano + en_curso, random_seed=semilla)
    ahora = datetime.datetime.now(datetime.timezone.utc)

    # Señales que un prospecto no tiene el día que entra al embudo. Se ponen a cero en la
    # instantánea y se dejan intactas en el prospecto de hoy.
    POSTERIORES = ("proposal_sent", "meeting_scheduled")

    for i, fila in df.iterrows():
        cerrado = i < tamano
        convertido = int(fila["converted"])

        if cerrado:
            estado = LeadStatus.WON if convertido else LeadStatus.LOST
        else:
            estado = LeadStatus.NEGOTIATION

        lead = Lead(
            first_name="Ensayo",
            last_name=f"Numero{i}",
            email=f"ensayo.{i}@cohorte-desechable.invalid",
            company=f"Empresa {i}",
            job_title=str(fila["job_title"]),
            industry=str(fila["industry"]),
            company_size=str(fila["company_size"]),
            annual_revenue=None if pd.isna(fila["annual_revenue"]) else float(fila["annual_revenue"]),
            source=str(fila["source_channel"]),
            status=estado,
            current_score=50.0,
            score_category=ScoreCategory.WARM,
            created_at=ahora - datetime.timedelta(days=120),
            updated_at=ahora - datetime.timedelta(days=int(fila["days_since_last_activity"])),
        )
        db.add(lead)
        db.flush()

        instantanea = {
            "page_views": int(fila["page_views"]),
            "email_opens": int(fila["email_opens"]),
            "email_clicks": int(fila["email_clicks"]),
            "content_downloads": int(fila["content_downloads"]),
            "attended_webinar": int(fila["attended_webinar"]),
            "requested_demo": int(fila["requested_demo"]),
            "meeting_scheduled": 0,
            "proposal_sent": 0,
            "phone_calls_connected": int(fila["phone_calls_connected"]),
            "phone_calls_unanswered": int(fila["phone_calls_unanswered"]),
            "whatsapp_messages": int(fila["whatsapp_messages"]),
            "linkedin_messages": int(fila["linkedin_messages"]),
            "days_since_last_activity": int(fila["days_since_last_activity"]),
            CLAVE_DE_VERSION: VERSION_DEL_VECTOR,
        }
        db.add(
            ScoreHistory(
                lead_id=lead.id,
                score=50.0,
                score_category=ScoreCategory.WARM,
                model_version="v1.0.0-hibrido+modelo",
                ml_probability=0.5,
                heuristic_score=50.0,
                decay_factor=1.0,
                feature_snapshot=instantanea,
                calculated_at=ahora - datetime.timedelta(days=120),
            )
        )

        # El estado de HOY sí lleva las señales posteriores, para los que cerraron.
        if cerrado and convertido:
            db.add(
                ScoreHistory(
                    lead_id=lead.id,
                    score=90.0,
                    score_category=ScoreCategory.HOT,
                    model_version="v1.0.0-hibrido+modelo",
                    ml_probability=0.9,
                    heuristic_score=90.0,
                    decay_factor=1.0,
                    feature_snapshot={**instantanea, **dict.fromkeys(POSTERIORES, 1)},
                    calculated_at=ahora - datetime.timedelta(days=5),
                )
            )

    db.commit()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tamano", type=int, default=45, help="Prospectos cerrados a sembrar.")
    parser.add_argument("--en-curso", type=int, default=30, help="Prospectos aun sin desenlace.")
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--entrenar", action="store_true", help="Entrenar tambien contra la cohorte.")
    parser.add_argument("--conservar", default=None, help="Directorio donde dejar el CSV resultante.")
    args = parser.parse_args(argv)

    directorio = tempfile.mkdtemp(prefix="ensayo-bucle-")
    try:
        _preparar_base(directorio)

        # `Base.metadata` solo conoce las tablas de los modelos que se hayan importado.
        # Sin esta linea `create_all` crea una base sin tablas y el primer INSERT falla
        # con «no such table: leads», que es lo que paso la primera vez.
        import app.models.entities  # noqa: F401
        from app.core.database import Base, SessionLocal, engine

        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            _sembrar(db, args.tamano, args.en_curso, args.semilla)

            from feedback_dataset import COLUMNAS_MODELO, construir_dataset, huella_del_dataset

            print("=" * 72)
            print(f"ENSAYO DEL BUCLE DE REALIMENTACION  ({args.tamano} cerrados, "
                  f"{args.en_curso} en curso)")
            print("=" * 72)
            print("Etiquetas SINTETICAS sobre una base desechable. Esto verifica que el")
            print("camino funciona, no el rendimiento del modelo en el negocio.")
            print()

            df, manifiesto = construir_dataset(db=db, exigir_minimos=False)
            manifiesto["huella_sha256"] = huella_del_dataset(df[COLUMNAS_MODELO + ["converted"]])
            print(json.dumps(manifiesto, indent=2, ensure_ascii=False, default=str))
        finally:
            db.close()

        if df.empty:
            print("El ensayo no extrajo ninguna fila: el bucle esta roto.")
            return 1

        # Los prospectos en curso NO pueden haber entrado. Contar la censura por la
        # derecha como negativo es el error mas comun al montar estos bucles: sesga el
        # modelo hacia el pesimismo justo en los prospectos mas activos, y no da ningun
        # sintoma —el dataset sale mas grande, que parece bueno—.
        #
        # Esta comprobacion faltaba en la primera version del ensayo, y sin ella quitarle
        # al extractor el filtro de estados terminales no hacia fallar nada aqui.
        if len(df) != args.tamano:
            print(f"FALLO: se sembraron {args.tamano} cerrados y {args.en_curso} en curso, "
                  f"y el extractor trajo {len(df)} filas.")
            print("       Los prospectos sin desenlace no son perdidos: son resultados que")
            print("       todavia no se conocen, y contarlos como negativos sesga el modelo.")
            return 1

        # Lo que comprueban las pruebas, comprobado tambien aqui de punta a punta: las
        # senales posteriores al desenlace no pueden haberse colado en las filas ganadas.
        ganados = df[df["converted"] == 1]
        if len(ganados) and (ganados["proposal_sent"].max() or ganados["meeting_scheduled"].max()):
            print("FALLO: el extractor trajo el estado de hoy, no la instantanea de entrada.")
            return 1
        print(f"\nLas {len(ganados)} filas ganadas llevan los ceros del momento de entrada.")

        destino = args.conservar or directorio
        os.makedirs(destino, exist_ok=True)
        csv = os.path.join(destino, "leads_ensayo.csv")
        df.to_csv(csv, index=False)
        with open(os.path.splitext(csv)[0] + "_manifiesto.json", "w", encoding="utf-8") as fh:
            json.dump(manifiesto, fh, indent=2, ensure_ascii=False, default=str)
        print(f"Dataset del ensayo: {csv}")

        if args.entrenar:
            from train_model import cargar_realimentacion, entrenar

            marco, procedencia = cargar_realimentacion(csv)
            # `publicar=False` no es una precaucion del ensayo: es el modo por defecto del
            # camino de realimentacion. Una cohorte de ensayo que sobrescribiera el
            # artefacto desplegado seria peor que no tener ensayo.
            #
            # `directorio_modelos` es lo que faltaba en la primera version: sin el, el
            # ensayo dejaba en el registro de PRODUCCION una entrada de origen
            # «realimentacion» con 36 filas, indistinguible de un entrenamiento real contra
            # desenlaces de clientes. Todo lo que este guion escribe muere con el
            # directorio temporal.
            entrenar(marco, origen="realimentacion", procedencia=procedencia,
                     publicar=False, directorio_modelos=os.path.join(directorio, "models"))

        return 0
    finally:
        shutil.rmtree(directorio, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
