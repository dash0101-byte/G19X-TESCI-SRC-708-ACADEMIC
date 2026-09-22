import json
import logging
from functools import lru_cache
from typing import Any, Dict, List

import httpx

from app.adapters.base import BaseAIExplanationAdapter
from app.adapters.prompt_safety import (
    INSTRUCCION_DE_AISLAMIENTO,
    construir_bloque_de_datos,
    validar_explicacion,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class NativeXAIExplanationAdapter(BaseAIExplanationAdapter):
    """
    Motor nativo de Inteligencia Artificial Explicable (XAI) para producción.
    Genera diagnósticos ejecutivos, identificación de fortalezas del prospecto
    y recomendaciones tácticas comerciales en lenguaje natural basadas en los
    atributos del ICP y el comportamiento digital, con latencia < 5 ms y alta fiabilidad.
    """

    async def generate_explanation(
        self,
        lead_data: Dict[str, Any],
        score: float,
        score_category: str,
        heuristic_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        first_name = lead_data.get("first_name", "Prospecto")
        company = lead_data.get("company", "Empresa no especificada")
        job_title = lead_data.get("job_title", "Ejecutivo")
        industry = lead_data.get("industry", "Tecnología")
        days_inactive = lead_data.get("days_since_last_activity", 0)
        custom_metadata = lead_data.get("custom_metadata") or {}

        title_upper = (job_title or "").upper()
        ind_upper = (industry or "").upper()

        is_atypical_role = any(k in title_upper for k in ["PSICÓLOGO", "PSICOLOGO", "DOCENTE", "PROFESOR", "ESTUDIANTE", "BECARIO", "ALUMNO", "PRACTICANTE"])
        is_hr_role = any(k in title_upper for k in ["TALENTO", "TALENT", "RECLUTAMIENTO", "RECRUITER", "RRHH", "PEOPLE", "HUMAN"])
        is_academic_sector = any(k in ind_upper for k in ["EDUCACIÓN", "EDUCACION", "UNIVERSIDAD", "ESCUELA", "INSTITUTO"])

        strengths: List[str] = []
        profiles_needed = custom_metadata.get("profiles_needed")
        urgency = custom_metadata.get("urgency")
        budget_range = custom_metadata.get("budget_range")

        if profiles_needed:
            strengths.append(f"Requerimiento activo de perfiles TI definido: {profiles_needed}.")
        if urgency and any(u in str(urgency).upper() for u in ["INMEDIATA", "ALTA", "URGENTE", "<15"]):
            strengths.append(f"Urgencia de contratación prioritaria ({urgency}).")
        if budget_range:
            strengths.append(f"Rango presupuestal informado: {budget_range}.")

        if is_atypical_role:
            strengths.append(f"Rol profesional registrado fuera del núcleo de toma de decisiones TI ({job_title}).")
        elif is_hr_role:
            strengths.append(f"Interlocutor clave en atracción de talento y gestión de capital humano ({job_title}).")
        elif heuristic_breakdown.get("title_fit_score", 0) >= 18:
            strengths.append(f"Cargo con alto poder de decisión técnica en el área ({job_title}).")

        if heuristic_breakdown.get("industry_fit_score", 0) >= 12:
            strengths.append(f"Industria prioritaria de alta demanda para PluriOne ({industry}).")
        elif is_academic_sector:
            strengths.append(f"Sector formativo o académico ({industry}) con potencial para convenios o semilleros de talento.")

        if heuristic_breakdown.get("behavior_raw_total", 0) >= 20:
            strengths.append("Interacción digital activa y consumo recurrente de información.")

        if not strengths:
            strengths.append("Interés inicial capturado a través de canales de prospección.")

        # Diagnóstico y recomendación según coherencia del perfil
        if is_atypical_role:
            summary = (
                f"Prospecto con score {score}/100 registrado como '{job_title}' en '{company}' ({industry}). "
                f"No corresponde al perfil típico de comprador corporativo de staffing TI de PluriOne."
            )
            recommendation = (
                f"Verificar si {first_name} actúa en representación del área de recursos humanos o selección institucional. "
                f"De lo contrario, clasificar como contacto exploratorio o consulta no comercial para no saturar al equipo de ventas."
            )
        elif score_category == "HOT":
            summary = (
                f"Prospecto de prioridad crítica (Score: {score}/100). {first_name} en {company} "
                f"presenta un ajuste óptimo al perfil de cliente ideal (ICP) y requiere contacto comercial inmediato."
            )
            if profiles_needed:
                recommendation = (
                    f"Asignar llamada de diagnóstico en menos de 15 minutos enfocada en el requerimiento de: {profiles_needed}. "
                    f"Presentar disponibilidad inmediata de candidatos evaluados y tiempos de entrega."
                )
            else:
                recommendation = (
                    "Asignar llamada de diagnóstico de 15 minutos en menos de 15 minutos con un Senior Account Executive. "
                    "Foco de la conversación: Retos de contratación de perfiles TI especializados y ahorro de tiempo en selección."
                )
        elif score_category == "WARM":
            summary = (
                f"Prospecto con potencial moderado (Score: {score}/100). Registra interacción en {industry}, "
                f"pero requiere maduración, validación de presupuesto o definición del alcance de contratación."
            )
            if profiles_needed:
                recommendation = (
                    f"Enviar presentación personalizada con casos de éxito en contratación de {profiles_needed} "
                    f"y proponer una breve sesión de sondeo de requerimientos de 15 minutos."
                )
            else:
                recommendation = (
                    "Incluir en flujo de nutrición por correo electrónico con casos de éxito de staffing en su sector "
                    "y enviar invitación al próximo webinar técnico de PluriOne."
                )
        else:
            summary = (
                f"Prospecto de baja prioridad o en etapa exploratoria temprana (Score: {score}/100). "
                f"Actualmente no cumple los criterios clave de decisión inmediata."
            )
            recommendation = (
                "Mantener en campañas generales de branding y newsletters mensuales. "
                "Revaluar automáticamente si se detectan nuevas visitas a páginas de cotización."
            )

        if days_inactive > 10:
            recommendation += f" [Alerta: Registra {days_inactive} días de inactividad; se aplicó factor de atenuación temporal]."

        # El motor nativo es determinista, pero no todo su texto lo escribe PluriOne:
        # `company`, `job_title` y `profiles_needed` salen del formulario del prospecto y
        # se interpolan en el resumen y en la recomendación. Pasar por el mismo validador
        # que la salida del modelo acota su longitud y elimina los caracteres de control,
        # de modo que lo que se persiste y se muestra tiene la misma forma venga de donde
        # venga.
        validado = validar_explicacion(
            {
                "summary": summary,
                "strengths": strengths,
                "recommended_action": recommendation,
            }
        )
        validado["engine"] = "PluriOne_XAI_Engine"
        validado["model_deployment"] = "XAI_Deterministic_Synthesizer_v1"
        return validado


class AzureOpenAIAdapter(BaseAIExplanationAdapter):
    """
    Adaptador de contingencia para Azure OpenAI Service (GPT-4o / GPT-4o-mini).
    """

    def __init__(self):
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_API_KEY
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT_NAME
        self.api_version = settings.AZURE_OPENAI_API_VERSION

    async def generate_explanation(
        self,
        lead_data: Dict[str, Any],
        score: float,
        score_category: str,
        heuristic_breakdown: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        system_prompt = (
            "Eres el asistente analítico de IA de PluriOne S.A. de C.V. Analizas un prospecto comercial (Lead) "
            "y generas un JSON estricto con: 'summary' (resumen de 2 frases), 'strengths' (lista de 2-3 puntos fuertes), "
            "y 'recommended_action' (recomendación táctica para el asesor de ventas).\n"
            + INSTRUCCION_DE_AISLAMIENTO
        )
        # Los datos del prospecto se serializan como JSON saneado en lugar de interpolarse
        # en una frase. `first_name`, `company` y el `custom_metadata` los escribe quien
        # rellena el formulario, no PluriOne: interpolados en el prompt, el prospecto podía
        # redactar la recomendación que después vería el asesor comercial (A-11).
        user_content = construir_bloque_de_datos(
            lead_data, score, score_category, heuristic_breakdown
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content_str = data["choices"][0]["message"]["content"]
                validado = validar_explicacion(json.loads(content_str))
                if validado is None:
                    # El modelo pudo haber sido persuadido pese al aislamiento; lo que no
                    # se le permite es devolver una estructura distinta de la esperada y
                    # que esa estructura acabe persistida y mostrada como propia.
                    raise ValueError("La respuesta del modelo no cumple el esquema esperado.")
                validado["engine"] = "Azure_OpenAI_GPT4o"
                validado["model_deployment"] = self.deployment
                return validado
            except Exception as e:
                logger.error(f"Fallo en Azure OpenAI ({e}). Usando fallback NativeXAIExplanationAdapter.")
                mock = NativeXAIExplanationAdapter()
                return await mock.generate_explanation(lead_data, score, score_category, heuristic_breakdown)


# Alias para retrocompatibilidad
LocalMockOpenAIAdapter = NativeXAIExplanationAdapter


@lru_cache(maxsize=8)
def _construir_adaptador_explicacion(modo: str, endpoint: str, clave_definida: bool) -> BaseAIExplanationAdapter:
    """
    Construye el adaptador una sola vez por combinación de configuración.

    Los argumentos son la clave de la caché, no datos de entrada: así un cambio de
    `AI_MODE` o de credenciales produce una entrada nueva en lugar de devolver el
    adaptador anterior. La clave no lleva la API key en claro, solo si está definida.
    """
    if modo == "azure" and endpoint and clave_definida:
        logger.info("Usando AzureOpenAIAdapter (Producción Azure)")
        return AzureOpenAIAdapter()
    return NativeXAIExplanationAdapter()


def get_ai_explanation_adapter() -> BaseAIExplanationAdapter:
    """Fábrica de adaptadores de explicación: por defecto entrega el motor nativo XAI."""
    return _construir_adaptador_explicacion(
        settings.AI_MODE.lower(),
        settings.AZURE_OPENAI_ENDPOINT or "",
        bool(settings.AZURE_OPENAI_API_KEY),
    )


def reset_explanation_adapter_cache() -> None:
    """Vacía la caché de adaptadores de explicación."""
    _construir_adaptador_explicacion.cache_clear()
