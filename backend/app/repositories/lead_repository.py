import datetime
from typing import List, Optional, Tuple

from sqlalchemy import desc, false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.autorizacion import AlcanceDeCartera, FueraDeAlcance
from app.models.entities import (
    Lead,
)
from app.schemas.lead import LeadCreate, LeadListFilter, LeadUpdate


class LeadEmailAlreadyExists(Exception):
    """
    El correo solicitado ya pertenece a otro prospecto.

    Existe como excepción de dominio para que el repositorio no dependa de FastAPI:
    la capa HTTP la traduce a 409 Conflict.
    """

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"El correo '{email}' ya está registrado en otro prospecto.")


class LeadRepository:
    """
    Acceso a prospectos, siempre acotado al alcance de quien pregunta.

    `alcance` es obligatorio y no tiene valor por defecto. Es la decisión de diseño de
    esta clase, así que conviene decir por qué: la autorización por objeto se olvida en
    silencio. Nadie ve un error porque una consulta devolvió prospectos ajenos —la
    respuesta es un 200 perfectamente formado—, de modo que un filtro que dependa de que
    cada endpoint se acuerde de aplicarlo dejará de aplicarse en cuanto se añada el
    siguiente endpoint con prisa.

    Al ser un parámetro obligatorio del constructor, olvidarlo produce un `TypeError` en
    la primera línea que se ejecute, y en la suite, no en producción y no en silencio.
    Los procesos sin usuario detrás pasan `AlcanceDeCartera.del_sistema("motivo")`, que
    es igual de explícito pero deja escrito para qué.
    """

    def __init__(self, db: Session, alcance: AlcanceDeCartera):
        self.db = db
        self.alcance = alcance

    # ------------------------------------------------------------------ interno
    def _acotar(self, query):
        """
        Añade el filtro por dueño a cualquier consulta de prospectos.

        Un asesor sin identificador resoluble no ve nada: el `False` explícito evita que
        un `assigned_rep_id == None` se convierta en «los prospectos sin asignar», que es
        lo que devolvería la comparación natural con NULL.
        """
        if self.alcance.toda_la_cartera:
            return query
        if self.alcance.usuario_id is None:
            return query.filter(false())
        return query.filter(Lead.assigned_rep_id == self.alcance.usuario_id)

    def _exigir_alcance(self, lead: Optional[Lead], lead_id: Optional[int] = None) -> None:
        """Comprobación de cierre para las rutas que reciben la entidad ya cargada."""
        if lead is not None and not self.alcance.alcanza(lead.assigned_rep_id):
            raise FueraDeAlcance(lead_id if lead_id is not None else lead.id)

    # ------------------------------------------------------------------ lecturas
    def get_by_id(self, lead_id: int, include_relations: bool = True) -> Optional[Lead]:
        query = self.db.query(Lead)
        if include_relations:
            query = query.options(
                joinedload(Lead.assigned_rep),
                joinedload(Lead.campaign),
                joinedload(Lead.activities),
                joinedload(Lead.score_histories),
            )
        return self._acotar(query).filter(Lead.id == lead_id).first()

    def existe_fuera_del_alcance(self, lead_id: int) -> bool:
        """
        ¿Ese identificador es de un prospecto real que simplemente no es suyo?

        Sirve para una sola cosa: distinguir en la **bitácora** un tanteo de
        identificadores de una petición a un prospecto inexistente. La respuesta HTTP es
        404 en los dos casos —hacia fuera no se confirma nada—, pero hacia dentro
        interesa mucho la diferencia.
        """
        if self.alcance.toda_la_cartera:
            return False
        return self.db.query(Lead.id).filter(Lead.id == lead_id).first() is not None

    def get_by_email(self, email: str) -> Optional[Lead]:
        consulta = self.db.query(Lead).filter(func.lower(Lead.email) == email.lower().strip())
        return self._acotar(consulta).first()

    def email_ya_registrado(self, email: str) -> bool:
        """
        ¿Existe YA un prospecto con ese correo, sea de quien sea?

        Deliberadamente **sin acotar**, y conviene justificarlo porque va a contracorriente
        del resto de la clase. `leads.email` es único en toda la tabla. Si un asesor
        comprobara duplicados solo dentro de su cartera, un correo que ya pertenece a otra
        persona pasaría la comprobación y estallaría en el INSERT: el usuario recibiría un
        500 en vez de un 400, y el registro quedaría a medias.

        Sí, esto permite averiguar si una dirección concreta está en el sistema. Es una
        fuga real y pequeña, y no hay forma de cerrarla mientras la columna sea única:
        ocultarla no elimina la señal, solo la convierte en un error del servidor, que
        revela lo mismo y encima rompe. Se devuelve un booleano, nunca la ficha ajena.
        """
        return (
            self.db.query(Lead.id)
            .filter(func.lower(Lead.email) == email.lower().strip())
            .first()
            is not None
        )

    def list_leads(self, filters: LeadListFilter) -> Tuple[List[Lead], int]:
        query = self._acotar(
            self.db.query(Lead).options(
                joinedload(Lead.assigned_rep),
                joinedload(Lead.campaign)
            )
        )

        if filters.score_category:
            query = query.filter(Lead.score_category == filters.score_category)
        if filters.status:
            query = query.filter(Lead.status == filters.status)
        if filters.industry:
            query = query.filter(func.lower(Lead.industry).like(f"%{filters.industry.lower()}%"))
        if filters.assigned_rep_id:
            query = query.filter(Lead.assigned_rep_id == filters.assigned_rep_id)
        if filters.min_score is not None:
            query = query.filter(Lead.current_score >= filters.min_score)
        if filters.max_score is not None:
            query = query.filter(Lead.current_score <= filters.max_score)
        if filters.search:
            search_pattern = f"%{filters.search.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Lead.first_name).like(search_pattern),
                    func.lower(Lead.last_name).like(search_pattern),
                    func.lower(Lead.email).like(search_pattern),
                    func.lower(Lead.company).like(search_pattern),
                    func.lower(Lead.job_title).like(search_pattern),
                )
            )

        total_count = query.count()
        leads = query.order_by(desc(Lead.current_score), desc(Lead.updated_at)).offset(filters.offset).limit(filters.limit).all()
        return leads, total_count

    def create(self, lead_in: LeadCreate) -> Lead:
        """
        Da de alta un prospecto dentro del alcance de quien lo crea.

        Un asesor no elige dueño: el prospecto queda suyo. Sin esto, un asesor que creara
        un prospecto sin asignar lo perdería de vista en el mismo instante —quedaría
        fuera de su propio alcance—, y si pudiera elegir dueño podría endosárselo a otro.
        Repartir cartera es una decisión de quien la dirige.
        """
        destino = lead_in.assigned_rep_id
        if not self.alcance.puede_reasignar():
            if destino is not None and destino != self.alcance.usuario_id:
                raise FueraDeAlcance(None)
            destino = self.alcance.usuario_id

        lead = Lead(
            first_name=lead_in.first_name,
            last_name=lead_in.last_name,
            email=lead_in.email.lower().strip(),
            phone=lead_in.phone,
            company=lead_in.company,
            job_title=lead_in.job_title,
            industry=lead_in.industry,
            company_size=lead_in.company_size,
            annual_revenue=lead_in.annual_revenue,
            country=lead_in.country,
            city=lead_in.city,
            source=lead_in.source,
            assigned_rep_id=destino,
            campaign_id=lead_in.campaign_id,
            raw_metadata=lead_in.raw_metadata or {},
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def update(self, lead: Lead, lead_in: LeadUpdate) -> Lead:
        """
        Aplica una actualización parcial sobre el prospecto.

        El correo recibe trato aparte: es la clave de deduplicación del sistema (el
        webhook CRM busca prospectos por él) y la columna es ÚNICA. Antes se escribía
        tal cual, de modo que reasignarlo a uno ya existente terminaba en un
        IntegrityError convertido en 500, y guardarlo con mayúsculas rompía la
        deduplicación posterior, que compara contra el correo en minúsculas.
        """
        self._exigir_alcance(lead)

        update_data = lead_in.model_dump(exclude_unset=True)

        # Reasignar es repartir trabajo. Quien solo atiende su cartera no cambia de dueño
        # un prospecto: hacerlo lo sacaría de la vista de quien respondía por él, o se lo
        # traería de la de otro.
        if "assigned_rep_id" in update_data and not self.alcance.puede_reasignar():
            if update_data["assigned_rep_id"] != lead.assigned_rep_id:
                raise FueraDeAlcance(lead.id)

        new_email = update_data.get("email")
        if new_email is not None:
            new_email = str(new_email).lower().strip()
            update_data["email"] = new_email
            if new_email != (lead.email or "").lower().strip():
                existing = self.get_by_email(new_email)
                if existing and existing.id != lead.id:
                    raise LeadEmailAlreadyExists(new_email)

        for field, value in update_data.items():
            if hasattr(lead, field) and value is not None:
                setattr(lead, field, value)
        lead.updated_at = datetime.datetime.now(datetime.timezone.utc)

        try:
            self.db.commit()
        except IntegrityError as exc:
            # Red de seguridad ante dos actualizaciones simultáneas: entre la
            # comprobación anterior y este commit, otra transacción pudo tomar el correo.
            self.db.rollback()
            raise LeadEmailAlreadyExists(new_email or lead.email) from exc

        self.db.refresh(lead)
        return lead

    def delete(self, lead_id: int) -> bool:
        lead = self._acotar(self.db.query(Lead)).filter(Lead.id == lead_id).first()
        if not lead:
            return False
        self.db.delete(lead)
        self.db.commit()
        return True

