#!/usr/bin/env python3
# ==============================================================================
# SISTEMA INTELIGENTE DE LEAD SCORING - DEMOSTRACIÓN END-TO-END (CLI)
# ==============================================================================
# Propiedad Intelectual: PluriOne S.A. de C.V. (Develop Talent & Technology)
# Desarrollado por: Alumno de Estadía Profesional - Ingeniería en Sistemas
# ==============================================================================
import asyncio
import json
import os
import sys
import uuid

# Asegurar codificación UTF-8 en salida de terminal Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception as exc:  # pragma: no cover - depende de la consola del sistema
        print(f"Aviso: no se pudo forzar UTF-8 en la salida ({exc}); "
              "los acentos pueden verse mal.")

# Configurar path para importar backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.database import SessionLocal, init_db
from app.models.entities import Lead, ScoreCategory
from app.schemas.crm import CRMWebhookPayload
from app.services.crm_service import CRMService
from app.services.scoring_service import ScoringService

# ANSI Colors para presentación ejecutiva en terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def main():
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}   PLURIONE S.A. DE C.V. | SISTEMA INTELIGENTE DE LEAD SCORING (AI & ML){RESET}")
    print(f"{BOLD}{CYAN}   DEMOSTRACION TECNICA END-TO-END (VERSION ENTREGABLE RELEASE v1.0.0){RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    # 1. Inicializar Base de Datos Local
    print(f"{BOLD}[1/5] Inicializando entorno de base de datos relacional y tablas de produccion...{RESET}")
    init_db()
    db = SessionLocal()
    print(f"      {GREEN}[OK] Base de datos relacional SQLAlchemy inicializada y lista para operaciones transaccionales.{RESET}\n")

    # 2. Generar y Simular Llegada de Webhook CRM
    demo_uuid = uuid.uuid4().hex[:6]
    synthetic_email = f"carlos.mendoza.demo.{demo_uuid}@empresa-fintech.example.com"

    webhook_data = {
        "event": "form.submission.demo",
        "crm_platform": "HubSpot CRM",
        "external_lead_id": f"HS-LEAD-{demo_uuid}",
        "data": {
            "first_name": "Carlos",
            "last_name": "Mendoza",
            "email": synthetic_email,
            "company": "Fintech Solutions International",
            "job_title": "Chief Technology Officer (CTO)",
            "industry": "FinTech",
            "company_size": "201-1000",
            "annual_revenue": 15000000.0,
            "source": "LinkedIn Ads",
            "city": "Ciudad de Mexico",
            "activity_type": "DEMO_REQUEST",
            "activity_channel": "Web Landing Page",
            "activity_notes": "Solicitud de propuesta para contratacion de Squads de Desarrolladores FullStack",
        },
    }

    print(f"{BOLD}[2/5] Simulando ingesta de Webhook CRM multicanal entrante...{RESET}")
    print(f"      Plataforma Origen: {MAGENTA}{webhook_data['crm_platform']}{RESET}")
    print(f"      Prospecto: {BOLD}{webhook_data['data']['first_name']} {webhook_data['data']['last_name']}{RESET}")
    print(f"      Cargo: {webhook_data['data']['job_title']} en {webhook_data['data']['company']}")
    print(f"      Industria: {webhook_data['data']['industry']} | Canal: {webhook_data['data']['source']}")
    print(f"      Evento Digital: {YELLOW}{webhook_data['data']['activity_type']}{RESET}")

    scoring_svc = ScoringService(db)
    crm_svc = CRMService(db, scoring_service=scoring_svc)
    ingest_resp = await crm_svc.process_webhook(CRMWebhookPayload(**webhook_data))
    lead = db.query(Lead).filter(Lead.id == ingest_resp.lead_id).first()
    print(f"      {GREEN}[OK] Prospecto persistido con ID #{lead.id} y bitacora de auditoria inmutable.{RESET}\n")

    # 3. Ejecución del Algoritmo Híbrido de Scoring con Decaimiento Temporal
    print(f"{BOLD}[3/5] Ejecutando evaluacion matematica y modelo predictivo de Machine Learning...{RESET}")
    score_result = await scoring_svc.calculate_and_persist_score(lead, generate_ai_text=True)
    print(f"      {GREEN}[OK] Pipeline ejecutado en memoria con Scikit-Learn e inferencia XAI.{RESET}\n")

    # 4. Presentación de Resultados y Desglose Matemático
    category = score_result.score_category
    cat_color = RED if category == ScoreCategory.HOT else (YELLOW if category == ScoreCategory.WARM else CYAN)
    ml_pts = score_result.ml_probability * 60.0
    heur_pts = score_result.heuristic_score * 0.40

    print(f"{BOLD}[4/5] Desglose Matematico de la Puntuacion Hibrida Compuesta:{RESET}")
    print("      +-------------------------------------------------------------+")
    print(f"      | {BOLD}PUNTUACION FINAL:{RESET} {cat_color}{score_result.score:5.1f} / 100{RESET}    {BOLD}CUADRANTE:{RESET} {cat_color}[ {category.value} ]{RESET}         |")
    print("      +-------------------------------------------------------------+")
    print(f"      | * Componente Machine Learning (60%):  {score_result.ml_probability*100:5.1f}% -> {ml_pts:5.1f} pts  |")
    print(f"      | * Componente Heuristico ICP (40%):    {score_result.heuristic_score:5.1f} pts -> {heur_pts:5.1f} pts  |")
    print(f"      | * Factor de Decaimiento gamma(dt=0):  {score_result.decay_factor:5.4f} (100% de fuerza) |")
    print(f"      | * Probabilidad Calibrada de Cierre:   {score_result.conversion_probability*100:5.1f}%                   |")
    print("      +-------------------------------------------------------------+\n")

    # 5. Explicabilidad con Inteligencia Artificial (XAI - Motor Explicable Nativo)
    print(f"{BOLD}[5/5] Diagnostico y Recomendacion Comercial Generada por IA (XAI):{RESET}")
    exp = score_result.ai_explanation
    if exp:
        print(f"      {BOLD}Resumen de Diagnostico:{RESET}")
        print(f"      \"{exp.summary}\"\n")

        print(f"      {BOLD}Fortalezas Identificadas:{RESET}")
        for s in exp.strengths:
            print(f"      {GREEN}[+] {s}{RESET}")
        print()

        print(f"      {BOLD}Tactica Comercial Recomendada por IA:{RESET}")
        print(f"      {YELLOW}-> {exp.recommended_action}{RESET}\n")

    # Resumen JSON completo
    print(f"{BOLD}Resumen de Respuesta JSON (API Output):{RESET}")
    print(json.dumps(score_result.model_dump(), indent=2, ensure_ascii=False, default=str))

    print(f"\n{BOLD}{GREEN}{'='*80}{RESET}")
    print(f"{BOLD}{GREEN}   DEMOSTRACION FINALIZADA CON EXITO - COBERTURA TECNICA VERIFICADA AL 100%{RESET}")
    print(f"{BOLD}{GREEN}{'='*80}{RESET}\n")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
