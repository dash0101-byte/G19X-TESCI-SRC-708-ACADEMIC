"""procedencia de actividades, bandeja «Sin asociar» y aviso de privacidad

Fase 15 — Cimientos del registro.

* `lead_activities`: `timestamp` pasa a llamarse `occurred_at` —cuándo ocurrió, que no es
  cuándo se registró— y se añaden `source`, `external_event_id`, `verificada`, `direction`
  y `call_outcome`. Se retira `activity_weight`, que mandaba el cliente y nadie leía. Índice
  único permanente sobre `(source, external_event_id)`.
* Lo existente se marca como `crm` (verificada) si hay un registro de integración del mismo
  prospecto con la plataforma como canal, y como `manual` (declarada) en otro caso.
* `activitytype` gana `LINKEDIN_MESSAGE`.
* `leads`: cuándo y por qué vía se aceptó el aviso de privacidad. Los teléfonos existentes
  se normalizan a E.164; los que no tienen forma de número se dejan como estaban y se cuentan.
* `unmatched_events`: la bandeja «Sin asociar».

Revision ID: e3a9c41d7b25
Revises: 904503b049f7
Create Date: 2026-09-11 09:00:00.000000

"""
from typing import Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e3a9c41d7b25"
down_revision: Union[str, None] = "904503b049f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS = (
    "PAGE_VIEW", "FORM_SUBMIT", "EMAIL_OPEN", "EMAIL_CLICK", "DEMO_REQUEST", "WEBINAR_ATTEND",
    "CONTENT_DOWNLOAD", "CHAT_INTERACTION", "PHONE_CALL", "MEETING_SCHEDULED", "WHATSAPP_MESSAGE",
    "LINKEDIN_MESSAGE", "PROPOSAL_SENT", "CUSTOM",
)
# En PostgreSQL el tipo ya existe —lo creó la migración inicial— y aquí solo se amplía: la
# tabla nueva lo reutiliza sin intentar crearlo otra vez.
TIPO_DE_ACTIVIDAD = sa.Enum(*TIPOS, name="activitytype").with_variant(
    postgresql.ENUM(*TIPOS, name="activitytype", create_type=False), "postgresql"
)


def _e164(texto: str) -> Optional[str]:
    """
    Copia de `app.core.telefono.normalizar_telefono` tal como es en esta fase. Una migración
    no importa código de la aplicación: ese código puede cambiar después, y la migración
    tiene que seguir haciendo lo mismo que hizo el día que se escribió.
    """
    import phonenumbers

    try:
        numero = phonenumbers.parse(texto, "MX")
    except phonenumbers.NumberParseException:
        return None
    if numero.country_code == 52:
        nacional = str(numero.national_number)
        if len(nacional) == 11 and nacional.startswith("1"):
            numero = phonenumbers.parse("+52" + nacional[1:], None)
    if not phonenumbers.is_valid_number(numero):
        return None
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def _normalizar_telefonos(bind) -> None:
    filas = bind.execute(sa.text("SELECT id, phone FROM leads WHERE phone IS NOT NULL")).fetchall()
    normalizados = vaciados = sin_forma = 0
    for lead_id, telefono in filas:
        texto = (telefono or "").strip()
        if not texto:
            bind.execute(sa.text("UPDATE leads SET phone = NULL WHERE id = :id"), {"id": lead_id})
            vaciados += 1
            continue
        e164 = _e164(texto)
        if e164 is None:
            sin_forma += 1
            continue
        if e164 != telefono:
            bind.execute(sa.text("UPDATE leads SET phone = :telefono WHERE id = :id"), {"telefono": e164, "id": lead_id})
            normalizados += 1
    print(
        f"[migracion e3a9c41d7b25] Teléfonos: {normalizados} normalizados a E.164, {vaciados} vacíos "
        f"pasados a NULL, {sin_forma} sin forma de número (se dejan como estaban)."
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. El tipo nuevo. `ALTER TYPE ... ADD VALUE` no puede usarse en la misma transacción
    #    que después lo emplea, de ahí el bloque en autocommit.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE activitytype ADD VALUE IF NOT EXISTS 'LINKEDIN_MESSAGE' AFTER 'WHATSAPP_MESSAGE'"
            )

    # 2. Procedencia de las actividades.
    op.drop_index("idx_activity_lead_time", table_name="lead_activities")
    op.drop_index("ix_lead_activities_timestamp", table_name="lead_activities")
    with op.batch_alter_table("lead_activities", schema=None) as batch_op:
        batch_op.alter_column(
            "timestamp",
            new_column_name="occurred_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("source", sa.String(length=40), server_default="manual", nullable=False))
        batch_op.add_column(sa.Column("external_event_id", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("verificada", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("direction", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("call_outcome", sa.String(length=20), nullable=True))
        batch_op.drop_column("activity_weight")
    op.create_index("ix_lead_activities_occurred_at", "lead_activities", ["occurred_at"], unique=False)
    op.create_index("idx_activity_lead_time", "lead_activities", ["lead_id", "occurred_at"], unique=False)

    # 3. Lo existente: CRM si hay un registro de integración del mismo prospecto con esa
    #    plataforma como canal —así las escribía la ingesta—; manual en otro caso.
    op.execute(
        sa.text(
            "UPDATE lead_activities SET source = 'crm', verificada = :verdadero "
            "WHERE EXISTS (SELECT 1 FROM crm_integration_logs AS registro "
            "WHERE registro.lead_id = lead_activities.lead_id "
            "AND registro.crm_platform = lead_activities.channel)"
        ).bindparams(verdadero=True)
    )
    crm = bind.execute(sa.text("SELECT COUNT(*) FROM lead_activities WHERE source = 'crm'")).scalar()
    manual = bind.execute(sa.text("SELECT COUNT(*) FROM lead_activities WHERE source = 'manual'")).scalar()
    llamadas = bind.execute(
        sa.text("SELECT COUNT(*) FROM lead_activities WHERE activity_type = 'PHONE_CALL'")
    ).scalar()
    print(
        f"[migracion e3a9c41d7b25] Actividades existentes: {crm} marcadas como CRM (verificadas), "
        f"{manual} como manuales (declaradas). {llamadas} llamadas sin resultado registrado: "
        "desde esta fase no cuentan como conversación."
    )
    op.create_index(
        "uq_lead_activities_source_external_event",
        "lead_activities",
        ["source", "external_event_id"],
        unique=True,
    )

    # 4. Aviso de privacidad y teléfonos.
    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("privacy_notice_accepted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("privacy_notice_source", sa.String(length=40), nullable=True))
    _normalizar_telefonos(bind)

    # 5. La bandeja «Sin asociar».
    op.create_table(
        "unmatched_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("external_event_id", sa.String(length=200), nullable=False),
        sa.Column("activity_type", TIPO_DE_ACTIVIDAD, nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("call_outcome", sa.String(length=20), nullable=True),
        sa.Column("contact_email", sa.String(length=150), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("contact_name", sa.String(length=150), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_unmatched_events_id", "unmatched_events", ["id"], unique=False)
    op.create_index("ix_unmatched_events_contact_email", "unmatched_events", ["contact_email"], unique=False)
    op.create_index("ix_unmatched_events_contact_phone", "unmatched_events", ["contact_phone"], unique=False)
    op.create_index("ix_unmatched_events_received_at", "unmatched_events", ["received_at"], unique=False)
    op.create_index(
        "uq_unmatched_events_source_external_event",
        "unmatched_events",
        ["source", "external_event_id"],
        unique=True,
    )


def downgrade() -> None:
    """
    Se pierde la procedencia, la bandeja y el aviso de privacidad. Los teléfonos se quedan
    en E.164: siguen siendo el mismo número. `LINKEDIN_MESSAGE` vuelve a `WHATSAPP_MESSAGE`,
    que es como se registraba antes; en PostgreSQL el valor se queda en el tipo, porque un
    tipo enumerado no admite retirar valores sin recrearlo.
    """
    op.drop_index("uq_unmatched_events_source_external_event", table_name="unmatched_events")
    op.drop_index("ix_unmatched_events_received_at", table_name="unmatched_events")
    op.drop_index("ix_unmatched_events_contact_phone", table_name="unmatched_events")
    op.drop_index("ix_unmatched_events_contact_email", table_name="unmatched_events")
    op.drop_index("ix_unmatched_events_id", table_name="unmatched_events")
    op.drop_table("unmatched_events")

    with op.batch_alter_table("leads", schema=None) as batch_op:
        batch_op.drop_column("privacy_notice_source")
        batch_op.drop_column("privacy_notice_accepted_at")

    op.drop_index("uq_lead_activities_source_external_event", table_name="lead_activities")
    op.drop_index("idx_activity_lead_time", table_name="lead_activities")
    op.drop_index("ix_lead_activities_occurred_at", table_name="lead_activities")
    op.execute(
        "UPDATE lead_activities SET activity_type = 'WHATSAPP_MESSAGE' WHERE activity_type = 'LINKEDIN_MESSAGE'"
    )
    with op.batch_alter_table("lead_activities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("activity_weight", sa.Float(), server_default="1.0", nullable=False))
        batch_op.drop_column("call_outcome")
        batch_op.drop_column("direction")
        batch_op.drop_column("verificada")
        batch_op.drop_column("external_event_id")
        batch_op.drop_column("source")
        batch_op.alter_column(
            "occurred_at",
            new_column_name="timestamp",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
    with op.batch_alter_table("lead_activities", schema=None) as batch_op:
        batch_op.alter_column("activity_weight", server_default=None, existing_type=sa.Float(), existing_nullable=False)
    op.create_index("ix_lead_activities_timestamp", "lead_activities", ["timestamp"], unique=False)
    op.create_index("idx_activity_lead_time", "lead_activities", ["lead_id", "timestamp"], unique=False)
