import hashlib
import logging
import math
import os
from functools import lru_cache
from typing import Any, Dict, Optional

import httpx
import joblib
import pandas as pd
from starlette.concurrency import run_in_threadpool

from app.adapters.base import BaseMLScoringAdapter
from app.core.config import settings
from app.core.vector_del_modelo import COLUMNAS_DEL_MODELO, ingresos_o_ausente

logger = logging.getLogger(__name__)


class NativeMLScoringAdapter(BaseMLScoringAdapter):
    """
    Adaptador nativo de inferencia de Machine Learning para producción.
    Carga y ejecuta el artefacto Scikit-Learn calibrado en memoria local con latencia ultrabaja (< 1 ms).
    """

    def __init__(self, model_path: Optional[str] = None, expected_sha256: Optional[str] = None):
        if model_path is None:
            # `ML_MODEL_PATH` manda cuando está definida. La búsqueda relativa de abajo
            # asume el árbol del repositorio, y dentro del contenedor eso no se cumple: la
            # imagen coloca el artefacto en una ruta fija. Es la raíz de A-5 —el modelo no
            # llegaba a la imagen y el servicio arrancaba degradado sin advertirlo—.
            model_path = settings.ML_MODEL_PATH.strip()
        if not model_path:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            model_path = os.path.join(base_dir, "ml_pipeline", "models", "lead_scorer_model.joblib")

        self.model_path = model_path
        self.expected_sha256 = (
            expected_sha256 if expected_sha256 is not None else settings.ML_MODEL_SHA256
        ).strip().lower()
        self.model_sha256: Optional[str] = None
        self.model = None
        self._load_model()

    @staticmethod
    def _digest(path: str) -> str:
        """SHA-256 del artefacto, leído por bloques para no cargarlo entero en memoria."""
        sha = hashlib.sha256()
        with open(path, "rb") as fh:
            for bloque in iter(lambda: fh.read(1024 * 1024), b""):
                sha.update(bloque)
        return sha.hexdigest()

    def _load_model(self) -> None:
        """
        Carga el artefacto, verificando antes su huella cuando hay una fijada.

        `joblib.load` deserializa con pickle, y pickle ejecuta código durante la carga: quien
        pueda sustituir el .joblib ejecuta lo que quiera dentro del proceso del backend, con
        sus credenciales y su acceso a la base (A-10). La ruta viene de configuración, así que
        basta con apuntarla a otro fichero. Fijar `ML_MODEL_SHA256` convierte eso en un fallo
        ruidoso: si la huella no cuadra, NO se deserializa nada.

        Sin huella fijada el comportamiento no cambia —se carga igual—, pero se registra la
        que tiene el fichero para que pueda anclarse, y en producción se avisa de que va sin
        anclar. Se prefiere eso a exigirla: negarse a arrancar rompería los despliegues que ya
        están en marcha, y degradar en silencio al heurístico es justo el fallo que costó A-5.
        """
        if not os.path.exists(self.model_path):
            logger.info(
                f"Artefacto de modelo no encontrado en {self.model_path}. "
                "Se usará inferencia heurística calibrada."
            )
            return

        try:
            self.model_sha256 = self._digest(self.model_path)
        except OSError as exc:
            logger.error(f"No se pudo leer el artefacto {self.model_path} para verificarlo: {exc}")
            return

        if self.expected_sha256:
            if self.model_sha256 != self.expected_sha256:
                logger.error(
                    "HUELLA DEL MODELO NO COINCIDE — el artefacto NO se ha cargado. "
                    f"Ruta: {self.model_path}. Esperada: {self.expected_sha256}. "
                    f"Encontrada: {self.model_sha256}. El sistema opera con el heurístico "
                    "hasta que se resuelva; si el cambio es legítimo, actualice ML_MODEL_SHA256."
                )
                return
            logger.info(f"Huella del modelo verificada correctamente ({self.model_sha256}).")
        elif settings.is_hardened_environment:
            logger.warning(
                "El artefacto del modelo se carga SIN huella fijada. `joblib.load` deserializa "
                f"con pickle: defina ML_MODEL_SHA256={self.model_sha256} para que una "
                "sustitución del fichero se detecte en lugar de ejecutarse."
            )
        else:
            logger.info(f"Huella del artefacto (sin fijar): {self.model_sha256}")

        try:
            self.model = joblib.load(self.model_path)
        except Exception as e:
            logger.warning(f"No se pudo deserializar el modelo local ({e}). Usando fallback heurístico calibrado.")
            self.model = None
            return

        # Código y artefacto tienen que hablar del mismo vector (capítulo 24). Un artefacto del
        # vector 1 con el código del 2 no recibe `phone_calls`: `predict_proba` fallaría en
        # cada petición, la inferencia caería al cálculo de contingencia y el historial seguiría
        # anotando `ml:<huella>` como motor. Mejor no cargarlo y que conste como `heuristico`.
        columnas = getattr(self.model, "feature_names_in_", None)
        if columnas is not None and list(columnas) != COLUMNAS_DEL_MODELO:
            logger.error(
                "EL ARTEFACTO ES DE OTRO VECTOR DE VARIABLES — NO se usa. "
                f"Ruta: {self.model_path}. Espera {len(COLUMNAS_DEL_MODELO)} columnas del vector "
                f"vigente y el artefacto se entrenó con {len(columnas)}. Reentrene o despliegue el "
                "artefacto que corresponde a este código."
            )
            self.model = None
            return
        logger.info(f"Modelo ML de producción cargado exitosamente desde: {self.model_path}")

    def is_healthy(self) -> bool:
        return True

    def version_del_motor(self) -> str:
        """
        `ml:<8 primeros del sha>` si el artefacto se cargó; `heuristico` si no.

        La huella corta ata cada puntuación a un artefacto concreto: si un día los scores
        cambian sin explicación, el historial dice con qué fichero se calcularon los de
        antes y con cuál los de después.
        """
        if self.model is None:
            return "heuristico"
        if self.model_sha256:
            return f"ml:{self.model_sha256[:8]}"
        return "ml:sin-huella"

    def _predict_sync(self, row_dict: Dict[str, Any]) -> float:
        """Parte bloqueante de la inferencia; se invoca desde un hilo aparte."""
        df = pd.DataFrame([row_dict], columns=COLUMNAS_DEL_MODELO)
        return float(self.model.predict_proba(df)[0, 1])

    @staticmethod
    def construir_fila(features: Dict[str, Any]) -> Dict[str, Any]:
        """
        El vector que recibe el modelo, en el orden y con los tipos del entrenamiento.

        Los ingresos ausentes viajan como `NaN`. Hasta el capítulo 24 viajaban como 100 000,
        porque el preprocesador no imputaba y un hueco lo habría hecho fallar: el modelo
        veía una empresa pequeña donde solo faltaba un dato. Ahora el artefacto imputa con la
        mediana del entrenamiento y añade la columna que dice que faltaba.

        Las claves se comprueban contra `COLUMNAS_DEL_MODELO` en la suite: la lista escrita
        aquí a mano es la que divergió en ML-4.
        """
        ingresos = ingresos_o_ausente(features.get("annual_revenue"))
        return {
            "job_title": str(features.get("job_title") or ""),
            "industry": str(features.get("industry") or ""),
            # Vacío y no «1-10»: para el codificador es una categoría desconocida.
            "company_size": str(features.get("company_size") or ""),
            "annual_revenue": math.nan if ingresos is None else ingresos,
            "source_channel": str(features.get("source", features.get("source_channel", "Website"))),
            "page_views": int(features.get("page_views", 0)),
            "email_opens": int(features.get("email_opens", 0)),
            "email_clicks": int(features.get("email_clicks", 0)),
            "content_downloads": int(features.get("content_downloads", 0)),
            "attended_webinar": int(features.get("attended_webinar", 0)),
            "requested_demo": int(features.get("requested_demo", 0)),
            # Estas cuatro las calculaba `extract_features_from_lead` desde hace tiempo,
            # pero no se pasaban aquí: el modelo nunca vio si se había enviado una propuesta
            # o agendado una reunión, que son las señales más fuertes del embudo (ML-4).
            "meeting_scheduled": int(features.get("meeting_scheduled", 0)),
            "proposal_sent": int(features.get("proposal_sent", 0)),
            # Vector 2: el resultado de la llamada y el canal del mensaje son variables.
            "phone_calls_connected": int(features.get("phone_calls_connected", 0)),
            "phone_calls_unanswered": int(features.get("phone_calls_unanswered", 0)),
            "whatsapp_messages": int(features.get("whatsapp_messages", 0)),
            "linkedin_messages": int(features.get("linkedin_messages", 0)),
            "days_since_last_activity": float(features.get("days_since_last_activity", 0.0)),
        }

    async def predict_conversion_probability(self, features: Dict[str, Any]) -> float:
        """
        Ejecuta la inferencia probabilística sobre el vector de características.
        """
        row_dict = self.construir_fila(features)

        if self.model is not None:
            try:
                # `predict_proba` es CPU pura y síncrona: ejecutada aquí dentro bloquearía el
                # bucle de eventos, y con ello TODAS las peticiones en vuelo, no solo esta.
                # Se nota poco pidiendo un prospecto y muchísimo en el recálculo por lotes.
                prob = await run_in_threadpool(self._predict_sync, row_dict)
                return round(prob, 4)
            except Exception as e:
                logger.error(f"Error durante inferencia con modelo Scikit-Learn: {e}")

        # Fallback analítico calibrado si el modelo en disco no está presente
        score_est = 0.20
        title = row_dict["job_title"].upper()
        if any(k in title for k in ["CTO", "CIO", "CHIEF", "VP", "DIRECTOR"]):
            score_est += 0.35
        elif any(k in title for k in ["GERENTE", "MANAGER", "LEAD"]):
            score_est += 0.20

        if row_dict["requested_demo"]:
            score_est += 0.30
        if row_dict["attended_webinar"]:
            score_est += 0.15

        score_est += min(0.15, row_dict["page_views"] * 0.02 + row_dict["email_clicks"] * 0.03)
        return min(0.99, max(0.01, round(score_est, 4)))


class AzureMLScoringAdapter(BaseMLScoringAdapter):
    """
    Adaptador de producción para Azure Machine Learning Managed Online Endpoints.
    """

    def __init__(self):
        self.endpoint = settings.AZURE_ML_ENDPOINT
        self.api_key = settings.AZURE_ML_API_KEY
        self.timeout = 5.0

    def is_healthy(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def version_del_motor(self) -> str:
        return "azure-endpoint"

    async def predict_conversion_probability(self, features: Dict[str, Any]) -> float:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {"data": [features]}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                # Azure ML estándar retorna lista de probabilidades
                return float(result.get("predictions", [0.5])[0])
            except Exception as e:
                logger.error(f"Error conectando con Azure ML Endpoint ({self.endpoint}): {e}")
                # Fallback de seguridad
                return 0.50


# Alias para retrocompatibilidad
LocalMLScoringAdapter = NativeMLScoringAdapter


@lru_cache(maxsize=8)
def _construir_adaptador_ml(
    modo: str, endpoint: str, ruta_modelo: str, huella: str
) -> BaseMLScoringAdapter:
    """
    Construye el adaptador una sola vez por combinación de configuración.

    Los parámetros no se usan dentro: son la CLAVE de la caché. Cachear una función sin
    argumentos habría devuelto siempre el primer adaptador construido, aunque después se
    cambiara `AI_MODE` o la ruta del modelo —y las pruebas hacen justamente eso—. Al
    entrar como argumentos todo lo que decide qué adaptador toca, un cambio de
    configuración produce una entrada nueva y la respuesta sigue siendo correcta.
    """
    if modo == "azure" and endpoint:
        logger.info("Usando AzureMLScoringAdapter (Endpoint Nube Azure)")
        return AzureMLScoringAdapter()
    return NativeMLScoringAdapter()


def get_ml_scoring_adapter() -> BaseMLScoringAdapter:
    """
    Fábrica de adaptadores de ML: por defecto entrega el motor nativo Scikit-Learn.

    El resultado se cachea. `ScoringService` se instancia en cada petición y construía aquí
    un adaptador nuevo, de modo que el artefacto de ~890 KiB se deserializaba con
    `joblib.load` en CADA petición de scoring: decenas de milisegundos y basura en el
    montón por algo que no cambia en toda la vida del proceso.
    """
    return _construir_adaptador_ml(
        settings.AI_MODE.lower(),
        settings.AZURE_ML_ENDPOINT or "",
        settings.ML_MODEL_PATH or "",
        settings.ML_MODEL_SHA256 or "",
    )


def reset_ml_adapter_cache() -> None:
    """Vacía la caché de adaptadores. Para pruebas y para recargar tras cambiar el modelo."""
    _construir_adaptador_ml.cache_clear()
