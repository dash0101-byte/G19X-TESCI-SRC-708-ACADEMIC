"""identidad unificada: sales_reps se fusiona en users

Revision ID: a23deac578cf
Revises: 130b990d78d7
Create Date: 2026-09-09 16:01:40.084043

Esta migración **mueve personas, no solo columnas**, y por eso está escrita a mano.

El sistema tenía dos tablas de personas sin ninguna relación entre sí: `users`, con quien
puede iniciar sesión, y `sales_reps`, con quien atiende prospectos. `leads.assigned_rep_id`
apuntaba a la segunda. La consecuencia práctica era que «de quién es este prospecto» y
«quién está pidiendo verlo» eran preguntas sobre universos distintos, así que la
comparación en la que se apoya toda la autorización por objeto no se podía escribir.

Lo que hace, en orden, y el orden importa:

 1. Añade a `users` los atributos de asesor y los del ciclo de vida de la contraseña.
 2. Traslada cada fila de `sales_reps` a `users`, emparejando por correo. Quien ya tenía
    cuenta conserva la suya y gana la marca de asesor; quien no la tenía recibe una cuenta
    **sin contraseña utilizable** (ver `HASH_INUTILIZABLE`).
 3. Reescribe `leads.assigned_rep_id` con el identificador del usuario correspondiente.
    Se lee TODO el mapa antes de escribir nada: los identificadores de `sales_reps` y los
    de `users` viven en espacios distintos y pueden coincidir, así que actualizar sobre la
    marcha corrompería las asignaciones que aún no se han traducido.
 4. Cambia la clave ajena para que apunte a `users` y añade el índice del filtro por dueño.
 5. Retira `sales_reps`.

ATENCIÓN al desplegar: las cuentas creadas en el paso 2 quedan activas —siguen recibiendo
prospectos— pero **no pueden iniciar sesión** hasta que un administrador les asigne
contraseña desde `/api/v1/users/{id}/reset-password`. Es deliberado: inventar una
contraseña conocida para completar la migración habría creado cuentas con credencial
compartida, que es exactamente la clase de puerta trasera que estas fases persiguen.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a23deac578cf'
down_revision: Union[str, Sequence[str], None] = '130b990d78d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Marcador de "esta cuenta no tiene contraseña". No es un hash bcrypt válido y no puede
# serlo: `verify_password` intenta comprobarlo, bcrypt lanza `ValueError` ante un salt
# malformado y la función devuelve False. Ninguna contraseña coincide nunca con esto.
#
# La alternativa —generar una contraseña real y anotarla en algún sitio— crea una
# credencial que alguien conoce y que probablemente sobreviva al despliegue.
HASH_INUTILIZABLE = "!sin-contrasena:migracion-a23deac578cf"  # noqa: S105

# Roles que atienden cartera. `System_Admin` no: administra el sistema, no vende.
ROLES_QUE_ATIENDEN = ("Commercial_Executive", "Sales_Lead")

CAPACIDAD_POR_DEFECTO = 50

# Convención de nombres para poder referirse, en SQLite, a una clave ajena que allí no
# tiene nombre. Es la receta documentada de Alembic para modificar una FK en modo lote.
CONVENCION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _nombre_de_la_fk(bind, tabla: str, columna: str):
    """Nombre real de la clave ajena de esa columna, o None si el motor no la nombra."""
    for fk in sa.inspect(bind).get_foreign_keys(tabla):
        if fk.get("constrained_columns") == [columna]:
            return fk.get("name")
    return None


# ==============================================================================
# Subida
# ==============================================================================

def upgrade() -> None:
    bind = op.get_bind()
    es_sqlite = bind.dialect.name == "sqlite"

    # --- 1. Columnas nuevas en `users` -------------------------------------
    # Las NOT NULL entran con `server_default` porque la tabla ya tiene filas; el
    # `server_default` se retira después para que el esquema coincida con el modelo, que
    # fija los valores desde Python.
    with op.batch_alter_table("users", schema=None) as lote:
        lote.add_column(
            sa.Column("is_sales_rep", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        lote.add_column(sa.Column("phone", sa.String(length=50), nullable=True))
        lote.add_column(sa.Column("capacity", sa.Integer(), nullable=True))
        lote.add_column(
            sa.Column(
                "password_changed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        lote.add_column(
            sa.Column(
                "must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        lote.create_index(lote.f("ix_users_is_sales_rep"), ["is_sales_rep"], unique=False)

    # --- 2. Trasladar las personas -----------------------------------------
    asesores = bind.execute(
        sa.text(
            "SELECT id, name, email, phone, capacity, is_active FROM sales_reps ORDER BY id"
        )
    ).fetchall()

    # old_sales_rep_id -> users.id
    equivalencias: dict = {}

    for asesor in asesores:
        viejo_id, nombre, correo, telefono, capacidad, activo = asesor
        correo_normalizado = (correo or "").strip().lower()
        if not correo_normalizado:
            # Un asesor sin correo no se puede emparejar ni convertir en cuenta. Sus
            # prospectos quedarán sin asignar, que es visible, en lugar de apuntando a un
            # identificador que ya no significa nada.
            continue

        existente = bind.execute(
            sa.text("SELECT id FROM users WHERE lower(email) = :correo"),
            {"correo": correo_normalizado},
        ).fetchone()

        if existente is not None:
            usuario_id = existente[0]
            # La cuenta manda sobre la ficha de asesor: su nombre y su rol son los que la
            # persona usa para entrar. De `sales_reps` solo se traen los atributos que
            # `users` no tenía.
            bind.execute(
                sa.text(
                    "UPDATE users SET is_sales_rep = :cierto, "
                    "phone = COALESCE(phone, :telefono), "
                    "capacity = COALESCE(capacity, :capacidad) "
                    "WHERE id = :id"
                ),
                {
                    "cierto": True,
                    "telefono": telefono,
                    "capacidad": capacidad or CAPACIDAD_POR_DEFECTO,
                    "id": usuario_id,
                },
            )
        else:
            bind.execute(
                sa.text(
                    "INSERT INTO users "
                    "(email, hashed_password, full_name, role, is_active, token_version, "
                    " is_sales_rep, phone, capacity, password_changed_at, must_change_password, "
                    " created_at, updated_at) "
                    "VALUES (:email, :hash, :nombre, :rol, :activo, 0, :cierto, :telefono, "
                    "        :capacidad, CURRENT_TIMESTAMP, :cierto, CURRENT_TIMESTAMP, "
                    "        CURRENT_TIMESTAMP)"
                ),
                {
                    "email": correo_normalizado,
                    "hash": HASH_INUTILIZABLE,
                    "nombre": nombre or correo_normalizado,
                    "rol": "Commercial_Executive",
                    "activo": bool(activo),
                    "cierto": True,
                    "telefono": telefono,
                    "capacidad": capacidad or CAPACIDAD_POR_DEFECTO,
                },
            )
            creado = bind.execute(
                sa.text("SELECT id FROM users WHERE lower(email) = :correo"),
                {"correo": correo_normalizado},
            ).fetchone()
            usuario_id = creado[0]

        equivalencias[viejo_id] = usuario_id

    # Quien ya tenía cuenta con un rol comercial atiende cartera aunque no estuviera en
    # `sales_reps`. Sin esto, un asesor con cuenta pero sin ficha quedaría marcado como no
    # asesor: entraría al sistema y no podría recibir ni ver un solo prospecto.
    bind.execute(
        sa.text(
            "UPDATE users SET is_sales_rep = :cierto, capacity = COALESCE(capacity, :capacidad) "
            "WHERE role IN :roles AND is_sales_rep = :falso"
        ).bindparams(sa.bindparam("roles", expanding=True)),
        {
            "cierto": True,
            "falso": False,
            "capacidad": CAPACIDAD_POR_DEFECTO,
            "roles": list(ROLES_QUE_ATIENDEN),
        },
    )

    # --- 3. Reescribir las asignaciones ------------------------------------
    # Se lee el mapa entero ANTES de escribir. Los identificadores de `sales_reps` y los de
    # `users` son espacios distintos y pueden solaparse: actualizar fila a fila leyendo el
    # valor actual traduciría dos veces el que ya se hubiera traducido.
    asignaciones = bind.execute(
        sa.text("SELECT id, assigned_rep_id FROM leads WHERE assigned_rep_id IS NOT NULL")
    ).fetchall()

    for lead_id, viejo_rep in asignaciones:
        nuevo = equivalencias.get(viejo_rep)
        bind.execute(
            sa.text("UPDATE leads SET assigned_rep_id = :nuevo WHERE id = :id"),
            {"nuevo": nuevo, "id": lead_id},
        )

    # --- 4. La clave ajena pasa a apuntar a `users` -------------------------
    if es_sqlite:
        with op.batch_alter_table("leads", schema=None, naming_convention=CONVENCION) as lote:
            lote.drop_constraint("fk_leads_assigned_rep_id_sales_reps", type_="foreignkey")
            lote.create_foreign_key(
                "fk_leads_assigned_rep_id_users",
                "users",
                ["assigned_rep_id"],
                ["id"],
                ondelete="SET NULL",
            )
            lote.create_index("idx_leads_rep_score", ["assigned_rep_id", "current_score"])
    else:
        anterior = _nombre_de_la_fk(bind, "leads", "assigned_rep_id")
        if anterior:
            op.drop_constraint(anterior, "leads", type_="foreignkey")
        op.create_foreign_key(
            "fk_leads_assigned_rep_id_users",
            "leads",
            "users",
            ["assigned_rep_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("idx_leads_rep_score", "leads", ["assigned_rep_id", "current_score"])

    # --- 5. Retirar la tabla duplicada -------------------------------------
    with op.batch_alter_table("sales_reps", schema=None) as lote:
        lote.drop_index(lote.f("ix_sales_reps_email"))
        lote.drop_index(lote.f("ix_sales_reps_id"))
    op.drop_table("sales_reps")

    # --- 6. Retirar los `server_default` provisionales ----------------------
    with op.batch_alter_table("users", schema=None) as lote:
        lote.alter_column("is_sales_rep", server_default=None)
        lote.alter_column("password_changed_at", server_default=None)
        lote.alter_column("must_change_password", server_default=None)


# ==============================================================================
# Bajada
# ==============================================================================

def downgrade() -> None:
    """
    Rehace `sales_reps` a partir de los usuarios marcados como asesores.

    **No borra cuentas.** Las que esta migración creó al subir se quedan, y conviene
    decirlo claro: una bajada que eliminara cuentas destruiría los asientos de auditoría
    que las referencian y cualquier sesión abierta, para deshacer un cambio de esquema. Un
    `downgrade` está para revertir estructura, no para borrar personas. Quedan con la
    marca de asesor retirada y sin contraseña utilizable, exactamente como llegaron.
    """
    bind = op.get_bind()
    es_sqlite = bind.dialect.name == "sqlite"

    # `DateTime(timezone=True)` y no `sa.DATETIME()`, que es el tipo de SQLite con el que
    # se autogenero: en PostgreSQL no existe y la reversion fallaba con «type datetime
    # does not exist» (detectado en la Fase 14 al revertir contra PostgreSQL real). Es
    # ademas el tipo que tenia la tabla en la revision a la que se vuelve, posterior a
    # eb529f0113d6.
    op.create_table(
        "sales_reps",
        sa.Column("id", sa.INTEGER(), nullable=False),
        sa.Column("name", sa.VARCHAR(length=150), nullable=False),
        sa.Column("email", sa.VARCHAR(length=150), nullable=False),
        sa.Column("phone", sa.VARCHAR(length=50), nullable=True),
        sa.Column("role", sa.VARCHAR(length=50), nullable=False),
        sa.Column("capacity", sa.INTEGER(), nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("sales_reps", schema=None) as lote:
        lote.create_index(lote.f("ix_sales_reps_id"), ["id"], unique=False)
        lote.create_index(lote.f("ix_sales_reps_email"), ["email"], unique=True)

    asesores = bind.execute(
        sa.text(
            "SELECT id, full_name, email, phone, role, capacity, is_active "
            "FROM users WHERE is_sales_rep = :cierto ORDER BY id"
        ),
        {"cierto": True},
    ).fetchall()

    equivalencias: dict = {}
    for usuario_id, nombre, correo, telefono, rol, capacidad, activo in asesores:
        bind.execute(
            sa.text(
                "INSERT INTO sales_reps (name, email, phone, role, capacity, is_active, "
                "                        created_at, updated_at) "
                "VALUES (:nombre, :correo, :telefono, :rol, :capacidad, :activo, "
                "        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "nombre": nombre,
                "correo": correo,
                "telefono": telefono,
                "rol": rol,
                "capacidad": capacidad if capacidad is not None else 50,
                "activo": bool(activo),
            },
        )
        nuevo = bind.execute(
            sa.text("SELECT id FROM sales_reps WHERE email = :correo"), {"correo": correo}
        ).fetchone()
        equivalencias[usuario_id] = nuevo[0]

    asignaciones = bind.execute(
        sa.text("SELECT id, assigned_rep_id FROM leads WHERE assigned_rep_id IS NOT NULL")
    ).fetchall()
    for lead_id, usuario_id in asignaciones:
        bind.execute(
            sa.text("UPDATE leads SET assigned_rep_id = :nuevo WHERE id = :id"),
            {"nuevo": equivalencias.get(usuario_id), "id": lead_id},
        )

    if es_sqlite:
        with op.batch_alter_table("leads", schema=None, naming_convention=CONVENCION) as lote:
            lote.drop_index("idx_leads_rep_score")
            lote.drop_constraint("fk_leads_assigned_rep_id_users", type_="foreignkey")
            lote.create_foreign_key(
                "fk_leads_assigned_rep_id_sales_reps",
                "sales_reps",
                ["assigned_rep_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.drop_index("idx_leads_rep_score", table_name="leads")
        anterior = _nombre_de_la_fk(bind, "leads", "assigned_rep_id")
        if anterior:
            op.drop_constraint(anterior, "leads", type_="foreignkey")
        op.create_foreign_key(
            "fk_leads_assigned_rep_id_sales_reps",
            "leads",
            "sales_reps",
            ["assigned_rep_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("users", schema=None) as lote:
        lote.drop_index(lote.f("ix_users_is_sales_rep"))
        lote.drop_column("must_change_password")
        lote.drop_column("password_changed_at")
        lote.drop_column("capacity")
        lote.drop_column("phone")
        lote.drop_column("is_sales_rep")
