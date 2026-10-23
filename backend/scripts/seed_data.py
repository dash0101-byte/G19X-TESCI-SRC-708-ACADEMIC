import argparse
import datetime
import os
import random
import secrets
import sys

# Asegurar que el path incluya el backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import HARDENED_ENVIRONMENTS, settings
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models.entities import (
    ActivityType,
    Campaign,
    CRMIntegrationLog,
    Lead,
    LeadActivity,
    LeadStatus,
    QualificationStatus,
    ScoreCategory,
    ScoreHistory,
    User,
    VisitaDePublicacion,
)

# Cuentas de operación del sistema. La contraseña de cada una se toma de su variable de
# entorno; nunca se codifica en el repositorio.
SEED_USERS = [
    {
        "email": "admin.ti@plurione.com",
        "full_name": "Mónica Arredondo Vela",
        "role": "System_Admin",
        "env_var": "SEED_ADMIN_PASSWORD",
        # Administra el sistema; no atiende cartera.
        "es_asesor": False,
        "capacidad": None,
    },
    {
        "email": "lider.ventas@plurione.com",
        "full_name": "Ricardo Peñaloza Gómez",
        "role": "Sales_Lead",
        "env_var": "SEED_SALES_LEAD_PASSWORD",
        "es_asesor": True,
        "capacidad": 40,
    },
    {
        "email": "asesor.comercial@plurione.com",
        "full_name": "Alejandro Morales",
        "role": "Commercial_Executive",
        "env_var": "SEED_EXECUTIVE_PASSWORD",
        "es_asesor": True,
        "capacidad": 50,
    },
]

# Resto del equipo comercial de la demostración. Antes eran filas de `sales_reps`, una
# tabla de personas sin cuenta y sin ninguna relación con `users`: el sembrado creaba tres
# cuentas con unos correos y cuatro asesores con otros, y ningún prospecto quedaba asignado
# a alguien capaz de abrirlo. Ahora son cuentas de verdad, y la demostración puede enseñar
# lo que importa: que cada asesor entra y ve exactamente su cartera.
SEED_ASESORES = [
    {
        "email": "carlos.morales@plurione.com",
        "full_name": "Carlos Morales",
        "phone": "+52 55 1234 5678",
        "capacidad": 60,
        "env_var": "SEED_ASESOR_PASSWORD",
    },
    {
        "email": "ana.ruiz@plurione.com",
        "full_name": "Ana Sofía Ruiz",
        "phone": "+52 55 2345 6789",
        "capacidad": 40,
        "env_var": "SEED_ASESOR_PASSWORD",
    },
    {
        "email": "valeria.mendoza@plurione.com",
        "full_name": "Valeria Mendoza",
        "phone": "+52 55 3456 7890",
        "capacidad": 50,
        "env_var": "SEED_ASESOR_PASSWORD",
    },
    {
        "email": "diego.herrera@plurione.com",
        "full_name": "Diego Herrera",
        "phone": "+52 55 4567 8901",
        "capacidad": 80,
        "env_var": "SEED_ASESOR_PASSWORD",
    },
]

# Contraseña de desarrollo, usada solo si no se define la variable de entorno y el
# entorno NO es de producción. Cumple el mínimo de 8 caracteres que exige el login.
DEV_FALLBACK_PASSWORD = "PluriOne2026!"  # noqa: S105  contraseña de demostración; en producción se genera aleatoria


def resolve_seed_password(env_var: str) -> tuple:
    """
    Resuelve la contraseña de una cuenta sembrada.

    Prioridad: variable de entorno > contraseña de desarrollo conocida (solo fuera de
    producción) > contraseña aleatoria irrecuperable. En producción nunca se siembra una
    credencial predecible: si no se inyecta por entorno, se genera al azar y se muestra
    una única vez para que el operador la cambie de inmediato.
    """
    from_env = os.environ.get(env_var)
    if from_env:
        return from_env, "variable de entorno"

    if settings.ENVIRONMENT.strip().lower() in HARDENED_ENVIRONMENTS:
        return secrets.token_urlsafe(18), "ALEATORIA (anótela: no se volverá a mostrar)"

    return DEV_FALLBACK_PASSWORD, "desarrollo (defina %s para cambiarla)" % env_var


def _fijar_cuenta(db, spec: dict) -> None:
    """Crea o restablece una cuenta a partir de su especificación."""
    password, origin = resolve_seed_password(spec["env_var"])
    user = db.query(User).filter(User.email == spec["email"]).first()
    if user is None:
        user = User(
            email=spec["email"],
            full_name=spec["full_name"],
            role=spec["role"],
            hashed_password=hash_password(password),
        )
        db.add(user)
    else:
        user.full_name = spec["full_name"]
        user.role = spec["role"]
        user.hashed_password = hash_password(password)
        # Invalida las sesiones vivas: la contraseña acaba de cambiar
        user.token_version += 1

    user.is_sales_rep = spec.get("es_asesor", False)
    user.capacity = spec.get("capacidad") if user.is_sales_rep else None
    if spec.get("phone"):
        user.phone = spec["phone"]

    marca = " [asesor]" if user.is_sales_rep else ""
    print(f"   -> {spec['email']:<32} rol={spec['role']:<22} contraseña: {origin}{marca}")
    if origin.startswith("ALEATORIA"):
        print(f"      CONTRASEÑA GENERADA: {password}")


def seed_users(db) -> None:
    """
    Crea o actualiza **todas** las cuentas del sistema, asesores incluidos.

    Ya no hay dos poblaciones. Antes este script creaba tres cuentas en `users` y cuatro
    asesores en `sales_reps` con correos distintos, sin relación entre sí: los prospectos
    quedaban asignados a personas que no existían como cuenta y que, por tanto, no podían
    iniciar sesión para atenderlos.
    """
    print("0. Creando cuentas de usuario autenticables...")
    for spec in SEED_USERS:
        _fijar_cuenta(db, spec)
    for spec in SEED_ASESORES:
        _fijar_cuenta(db, dict(spec, role="Commercial_Executive", es_asesor=True))
    db.commit()


# Tablas que la resiembra vacía, en orden de dependencia (hijas antes que padres).
TABLAS_A_VACIAR = [
    ("Logs de sincronización CRM", CRMIntegrationLog),
    ("Historiales de scoring", ScoreHistory),
    ("Actividades de prospectos", LeadActivity),
    ("Prospectos", Lead),
    # Antes que las campañas: las visitas son de una publicación, y una publicación nueva
    # que heredara el id de una borrada heredaría también sus visitas.
    ("Visitas de publicaciones", VisitaDePublicacion),
    ("Campañas", Campaign),
]
# `users` NO se vacía. Las cuentas son identidad, no datos de demostración: borrarlas
# dejaría sin sujeto los asientos de la bitácora que las nombran, y con la fusión de
# `sales_reps` dentro de `users` la resiembra habría pasado a destruir también las
# credenciales de acceso, que es un efecto que nadie espera de "recargar los datos de
# ejemplo".


class SiembraRechazada(RuntimeError):
    """La siembra no procede en este entorno o sin la confirmación explícita."""


def destino_de_la_base() -> str:
    """Descripción del destino sin la contraseña, para poder enseñarla antes de borrar."""
    url = settings.DATABASE_URL
    if "@" in url and "://" in url:
        esquema, resto = url.split("://", 1)
        credenciales, servidor = resto.split("@", 1)
        usuario = credenciales.split(":", 1)[0]
        return f"{esquema}://{usuario}:***@{servidor}"
    return url


def verificar_entorno_permitido() -> None:
    """
    Impide sembrar datos de demostración sobre una base endurecida (A-2).

    Este script no añade: **vacía y regenera**. Apuntado por descuido al `DATABASE_URL`
    de producción —una variable de entorno heredada de otra sesión de terminal basta—
    borraba todos los prospectos, actividades e historiales sin preguntar nada. Y el
    pipeline de CI lo ejecutaba, de modo que el descuido no necesitaba ni una persona
    delante.

    Las cuentas de operación sí son legítimas en producción, así que ese caso se atiende
    aparte con `--solo-usuarios`, que no borra nada.
    """
    if settings.ENVIRONMENT.strip().lower() in HARDENED_ENVIRONMENTS:
        raise SiembraRechazada(
            f"ENVIRONMENT='{settings.ENVIRONMENT}' es un entorno endurecido y este script "
            f"vacía las tablas de negocio antes de sembrar. Destino: {destino_de_la_base()}.\n"
            "Si lo que necesita es crear o restablecer las cuentas de acceso, use:\n"
            "  python backend/scripts/seed_data.py --solo-usuarios"
        )


def _resumen_de_lo_que_se_borraria(db) -> list:
    return [(nombre, db.query(modelo).count()) for nombre, modelo in TABLAS_A_VACIAR]


def seed_database(forzar: bool = False, solo_usuarios: bool = False) -> None:
    """Puebla la base de datos con datos sintéticos realistas para PluriOne."""
    if not solo_usuarios:
        verificar_entorno_permitido()

    print(f"Destino: {destino_de_la_base()}")
    print("Iniciando creación de esquema y población de datos para PluriOne...")
    init_db()
    db = SessionLocal()

    try:
        if solo_usuarios:
            # Camino no destructivo: es el único que tiene sentido sobre datos reales.
            seed_users(db)
            print("\nCuentas de acceso creadas o restablecidas. No se tocó ningún otro dato.")
            return

        # Verificar si ya existen datos
        if db.query(Lead).count() > 0 or db.query(Campaign).count() > 0:
            resumen = _resumen_de_lo_que_se_borraria(db)
            total = sum(cantidad for _, cantidad in resumen)
            if not forzar:
                detalle = "\n".join(f"    {nombre:<32} {cantidad}" for nombre, cantidad in resumen)
                raise SiembraRechazada(
                    "La base ya contiene datos y volver a sembrar los DESTRUYE. Se abortó sin "
                    f"tocar nada.\n  Destino: {destino_de_la_base()}\n"
                    f"  Se borrarían {total} registros:\n{detalle}\n"
                    "  Si es lo que quiere, repita el comando con --force."
                )
            print(f"Vaciando {total} registros existentes (--force):")
            for nombre, modelo in TABLAS_A_VACIAR:
                borrados = db.query(modelo).delete()
                print(f"    {nombre:<32} {borrados}")
            db.commit()

        seed_users(db)

        print("1. Recuperando el equipo comercial (cuentas con is_sales_rep)...")
        # Ya existen: `seed_users` los creó como cuentas. Aquí solo se leen para repartir
        # la cartera de demostración entre ellos.
        sales_reps = (
            db.query(User)
            .filter(User.is_sales_rep.is_(True), User.is_active.is_(True))
            .order_by(User.id)
            .all()
        )
        if not sales_reps:
            raise SiembraRechazada(
                "No hay ninguna cuenta marcada como asesora; los prospectos quedarían sin "
                "asignar y la demostración del filtro por cartera no se podría enseñar."
            )

        print(f"   -> {len(sales_reps)} asesores disponibles para repartir cartera.")

        print("2. Creando Campañas de Marketing...")
        campaigns = [
            Campaign(name="Q3 Tech Talent Summit 2026", channel="LinkedIn Ads", budget=12000.0, utm_source="linkedin", utm_medium="cpc", utm_campaign="talent_summit_26"),
            Campaign(name="Webinar: IA en Procesos de Selección B2B", channel="Webinar", budget=4500.0, utm_source="email", utm_medium="newsletter", utm_campaign="webinar_ia_b2b"),
            Campaign(name="Inbound SEO - Soluciones TI Corporativas", channel="Organic Search", budget=8000.0, utm_source="google", utm_medium="organic", utm_campaign="ti_solutions_seo"),
            Campaign(name="Outbound Email - C-Level Executives", channel="Outbound Cold Email", budget=3000.0, utm_source="outbound", utm_medium="email", utm_campaign="c_level_q3"),
        ]
        db.add_all(campaigns)
        db.commit()
        for camp in campaigns:
            db.refresh(camp)

        print(f"   -> {len(campaigns)} campañas creadas.")

        print("3. Generando Prospectos Comerciales (Leads)...")
        companies = [
            ("FinTech Avanzada S.A.P.I.", "FinTech", "201-1000", 5000000.0, "CDMX"),
            ("Logística y Transporte Global", "Logistics", "51-200", 2500000.0, "Monterrey"),
            ("Soluciones Cloud México", "Software/TI", "11-50", 1200000.0, "Guadalajara"),
            ("Grupo Retail del Norte", "Retail", "1000+", 15000000.0, "Monterrey"),
            ("Salud Digital Innovación", "Healthcare", "51-200", 3000000.0, "Querétaro"),
            ("E-Commerce Logistics Express", "E-Commerce", "11-50", 900000.0, "CDMX"),
            ("Consultoría Estratégica MX", "Consulting", "1-10", 400000.0, "Puebla"),
            ("Banco Regional del Centro", "Banking", "1000+", 25000000.0, "CDMX"),
        ]

        sample_leads_data = [
            ("Mariana", "Castillo", "mariana.c@fintechavanzada.com", "CTO", 0),
            ("Roberto", "Garza", "rgarza@logisticaglobal.mx", "Director de Operaciones", 1),
            ("Lucía", "Fernández", "lfernandez@cloudmex.com", "Head of Engineering", 2),
            ("Fernando", "Salinas", "fsalinas@gruporetailnorte.com", "VP de Recursos Humanos", 3),
            ("Elena", "Torres", "etorres@saluddigital.com", "Gerente de Talento TI", 4),
            ("Javier", "López", "jlopez@ecomexpress.mx", "Director General (CEO)", 5),
            ("Gabriela", "Paz", "gpaz@consultoriamex.com", "Socia Directora", 6),
            ("Alejandro", "Vargas", "avargas@bancocentro.com.mx", "Chief Information Officer (CIO)", 7),
            ("Claudia", "Márquez", "cmarquez@techconsultores.mx", "Gerente de Proyectos", 2),
            ("Mauricio", "Ortiz", "mortiz@inretailmex.com", "Líder de Reclutamiento", 3),
            ("Patricia", "Navarro", "pnavarro@fintechavanzada.com", "Engineering Manager", 0),
            ("Esteban", "Domínguez", "edominguez@saluddigital.com", "Director de Tecnología", 4),
        ]

        created_leads = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for idx, (fname, lname, email, title, comp_idx) in enumerate(sample_leads_data):
            comp_name, industry, c_size, rev, city = companies[comp_idx]
            rep = sales_reps[idx % len(sales_reps)]
            camp = campaigns[idx % len(campaigns)]

            # Simular score realista
            if idx in [0, 3, 7, 10]:  # HOT
                score = round(random.uniform(78.0, 96.5), 1)
                category = ScoreCategory.HOT
                q_status = QualificationStatus.SQL
                status = LeadStatus.QUALIFIED
                conv_prob = round(score / 100.0, 2)
            elif idx in [1, 2, 4, 11]:  # WARM
                score = round(random.uniform(48.0, 72.0), 1)
                category = ScoreCategory.WARM
                q_status = QualificationStatus.MQL
                status = LeadStatus.ENGAGED
                conv_prob = round(score / 100.0, 2)
            else:  # COLD
                score = round(random.uniform(15.0, 42.0), 1)
                category = ScoreCategory.COLD
                q_status = QualificationStatus.INCOMING
                status = LeadStatus.NEW
                conv_prob = round(score / 100.0, 2)

            days_ago = random.randint(1, 20)
            lead_date = now - datetime.timedelta(days=days_ago)

            lead = Lead(
                first_name=fname,
                last_name=lname,
                email=email,
                # E.164, como lo deja la validación al guardar.
                phone=f"+5255{random.randint(1000, 9999)}{random.randint(1000, 9999)}",
                company=comp_name,
                job_title=title,
                industry=industry,
                company_size=c_size,
                annual_revenue=rev,
                country="México",
                city=city,
                source=camp.channel,
                status=status,
                qualification_status=q_status,
                current_score=score,
                score_category=category,
                conversion_probability=conv_prob,
                last_score_update=now - datetime.timedelta(hours=random.randint(1, 12)),
                last_activity_at=now - datetime.timedelta(days=random.randint(0, 5)),
                assigned_rep_id=rep.id,
                campaign_id=camp.id,
                raw_metadata={
                    "source_device": "Desktop Mac/Windows",
                    "preferred_contact_time": "Mañana (9:00 - 13:00)",
                    "budget_allocated": True if score > 70 else False,
                    "estimated_hires": random.randint(5, 50),
                },
                created_at=lead_date,
                updated_at=now,
            )
            db.add(lead)
            created_leads.append(lead)

        db.commit()
        for lead in created_leads:
            db.refresh(lead)

        print(f"   -> {len(created_leads)} prospectos creados y clasificados.")

        print("4. Registrando Historial de Actividades y Eventos...")
        # Historial de demostración como si lo hubiera entregado el CRM: con su procedencia,
        # verificado y con identificador propio. Es lo único que escribe `lead_activities`
        # sin pasar por `registrar_evento`, porque reproduce un pasado con scores ya fijados
        # en lugar de recalcularlos evento a evento.
        activity_types = [
            (ActivityType.PAGE_VIEW, "Web", {"url": "/servicios/staffing-ti", "duration_sec": 140}),
            (ActivityType.FORM_SUBMIT, "Web", {"form_id": "contact_lead_scoring", "fields": 6}),
            (ActivityType.EMAIL_OPEN, "Email", {"campaign": "talent_summit_26", "client": "Outlook"}),
            (ActivityType.EMAIL_CLICK, "Email", {"link": "https://plurione.com/agenda-demo"}),
            (ActivityType.DEMO_REQUEST, "Web", {"requested_topic": "Plataforma de Headhunting TI"}),
            (ActivityType.WEBINAR_ATTEND, "Zoom", {"attendance_rate_percent": 95}),
            (ActivityType.CONTENT_DOWNLOAD, "Web", {"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}),
        ]

        total_activities = 0
        for lead in created_leads:
            # Número de actividades según si es HOT, WARM o COLD
            num_acts = 5 if lead.score_category == ScoreCategory.HOT else (3 if lead.score_category == ScoreCategory.WARM else 1)
            for i in range(num_acts):
                act_choice = random.choice(activity_types)
                act_time = lead.created_at + datetime.timedelta(days=i, hours=random.randint(1, 8))
                activity = LeadActivity(
                    lead_id=lead.id,
                    activity_type=act_choice[0],
                    channel=act_choice[1],
                    source="crm",
                    external_event_id=f"demo:{lead.id}:{i}",
                    verificada=True,
                    activity_data=act_choice[2],
                    occurred_at=act_time,
                    created_at=act_time,
                )
                db.add(activity)
                total_activities += 1

        db.commit()
        print(f"   -> {total_activities} actividades registradas.")

        print("5. Generando Auditoría de Scoring Histórico y Explicabilidad...")
        for lead in created_leads:
            heuristic_part = round(lead.current_score * 0.4, 2)
            score_history = ScoreHistory(
                lead_id=lead.id,
                score=lead.current_score,
                score_category=lead.score_category,
                model_version="v1.0.0-hybrid",
                ml_probability=lead.conversion_probability,
                heuristic_score=heuristic_part,
                decay_factor=0.95,
                rule_breakdown={
                    "industry_fit": 25 if lead.industry in ["FinTech", "Software/TI", "Banking"] else 15,
                    "seniority_fit": 25 if "Director" in lead.job_title or "VP" in lead.job_title or "CTO" in lead.job_title or "CIO" in lead.job_title else 12,
                    "company_size_fit": 20 if lead.company_size in ["201-1000", "1000+"] else 10,
                    "engagement_velocity": 15,
                },
                ai_explanation={
                    "summary": f"Prospecto calificado como {lead.score_category.value} debido a alta correspondencia de perfil (Cargo: {lead.job_title}) y recurrencia de interacciones digitales.",
                    "strengths": [f"Sector de alto valor: {lead.industry}", f"Rol con poder de decisión: {lead.job_title}"],
                    "recommended_action": "Asignar de inmediato a llamada exploratoria de 15 minutos con ejecutivo senior." if lead.score_category == ScoreCategory.HOT else "Nutrir con secuencia de emails de casos de éxito.",
                },
                calculated_at=lead.last_score_update,
            )
            db.add(score_history)

            # CRM Log
            crm_log = CRMIntegrationLog(
                lead_id=lead.id,
                external_crm_id=f"CRM-PLURI-{1000 + lead.id}",
                crm_platform="PluriOne_CRM",
                event_type="INGEST_AND_SCORE",
                sync_status="SUCCESS",
                payload={"lead_id": lead.id, "email": lead.email, "score": lead.current_score},
                response_data={"status": "synchronized", "crm_lead_id": f"CRM-PLURI-{1000 + lead.id}"},
                synced_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(crm_log)

        db.commit()
        print("   -> Historiales de scoring y logs de sincronización CRM generados.")

        # Resumen final de verificación
        print("\n" + "=" * 60)
        print("VERIFICACIÓN DE MODELADO RELACIONAL COMPLETADA CON ÉXITO")
        print("=" * 60)
        print(f"Total Cuentas de Usuario:     {db.query(User).count()}")
        print(f"Total Asesores Comerciales: "
              f"{db.query(User).filter(User.is_sales_rep.is_(True)).count()}")
        print(f"Total Campañas Marketing:     {db.query(Campaign).count()}")
        print(f"Total Prospectos (Leads):     {db.query(Lead).count()}")
        print(f"  - HOT (Alta Prioridad):     {db.query(Lead).filter(Lead.score_category == ScoreCategory.HOT).count()}")
        print(f"  - WARM (Nutrición Activa):  {db.query(Lead).filter(Lead.score_category == ScoreCategory.WARM).count()}")
        print(f"  - COLD (Baja Prioridad):    {db.query(Lead).filter(Lead.score_category == ScoreCategory.COLD).count()}")
        print(f"Total Actividades Registradas:{db.query(LeadActivity).count()}")
        print(f"Total Historiales de Score:   {db.query(ScoreHistory).count()}")
        print(f"Total Logs CRM:               {db.query(CRMIntegrationLog).count()}")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"ERROR durante la siembra de base de datos: {str(e)}")
        raise e
    finally:
        db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Puebla la base con datos sintéticos de demostración. VACÍA las tablas de "
            "negocio antes de regenerarlas."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Confirma el borrado de los datos existentes. Sin esta bandera el script aborta.",
    )
    parser.add_argument(
        "--solo-usuarios",
        action="store_true",
        help="Solo crea o restablece las cuentas de acceso. No borra nada; válido en producción.",
    )
    args = parser.parse_args(argv)

    try:
        seed_database(forzar=args.force, solo_usuarios=args.solo_usuarios)
    except SiembraRechazada as exc:
        print(f"\n[SIEMBRA ABORTADA] {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
