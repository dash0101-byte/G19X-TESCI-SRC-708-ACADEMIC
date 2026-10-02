import datetime
from typing import List, Optional, Tuple

from sqlalchemy import desc, false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core import integridad
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

        # Las dos columnas de la ficha que apuntan a otra tabla —la publicación que la trajo
        # y el asesor que la atiende— son también las dos únicas claves ajenas del esquema
        # que salen de un cuerpo de petición: las otras dieciséis se escriben desde una fila
        # ya cargada. Hasta el capítulo 42 nadie comprobaba que existieran, así que un
        # `campaign_id` que no existe llegaba al `INSERT` y salía como **500**, sin decir qué
        # campo era. La comprobación ya estaba escrita en este repositorio y dos veces, para
        # la columna hermana: `ciclo.comprobar_responsable` y `ciclo.asesor_para`.
        enviados = {"assigned_rep_id": destino, "campaign_id": lead_in.campaign_id}
        sin_destino = integridad.claves_que_no_apuntan_a_nada(self.db, Lead, enviados)
        if sin_destino:
            raise integridad.LaBaseRechaza(sin_destino[0])

        # Lo que se intenta escribir, copiado ANTES del `commit`: un `rollback` caduca los
        # objetos de la sesión, y después de él `lead.campaign_id` ya no dice lo que se
        # intentó sino lo que la base tiene.
        valores = {
            columna.name: getattr(lead, columna.name, None) for columna in Lead.__table__.columns
        }

        self.db.add(lead)
        try:
            self.db.commit()
        except IntegrityError as exc:
            # La red que la edición lleva desde el capítulo 33 y el alta no tenía (punto 40
            # de §6.4). Cubre dos cosas: la carrera del correo —entre la comprobación del
            # endpoint y este `commit` cabe otra transacción que lo tome— y la de las claves
            # de arriba, que puede perder su destino en el mismo hueco.
            self.db.rollback()
            raise self._lo_que_la_base_rechazo(valores) from exc
        self.db.refresh(lead)
        return lead

    def _lo_que_la_base_rechazo(self, valores: dict, *, id_propio: Optional[int] = None) -> Exception:
        """
        Qué excepción corresponde a un `IntegrityError`, preguntándoselo a la base.

        El conflicto del correo sigue contestándose con la frase que el capítulo 33 escribió
        para él —es el caso para el que se puso la red, y la pantalla ya la enseña—, y todo
        lo demás deja de contestarse con esa frase, que era el punto 26 de §6.4: una clave
        ajena sin destino salía como «El correo … ya está registrado en otro prospecto», con
        el correo de la propia ficha dentro de una frase sobre un conflicto que no ocurrió.
        """
        rechazo = integridad.motivo_del_rechazo(self.db, Lead, valores, id_propio=id_propio)
        if rechazo.clase == integridad.REPETIDO and rechazo.campo == "email":
            return LeadEmailAlreadyExists(valores.get("email") or "")
        return integridad.LaBaseRechaza(rechazo)

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

        # La misma comprobación que el alta, por el mismo motivo y en la misma función: un
        # asesor que no existe salía de aquí como un 409 sobre el correo de la propia ficha.
        sin_destino = integridad.claves_que_no_apuntan_a_nada(self.db, Lead, update_data)
        if sin_destino:
            raise integridad.LaBaseRechaza(sin_destino[0])

        # Se aplica TODO lo que vino en el cuerpo, incluido lo que vino vacío. Hasta el
        # capítulo 33 la condición era `and value is not None`, y esa línea convertía el
        # `exclude_unset=True` de arriba en decoración: el dump ya distinguía «no lo mandó»
        # de «lo mandó vacío», y el bucle volvía a mezclarlos tirando los dos.
        #
        # La consecuencia no era que no se pudiera vaciar un campo, sino que vaciarlo
        # respondía 200. Un dato escrito por error —un país supuesto, una empresa mal
        # tecleada— se podía cambiar por otro, pero no retirar, y la pantalla decía que sí.
        #
        # Que un `None` no llegue aquí sobre una columna `NOT NULL` lo garantiza `LeadUpdate`,
        # que lo rechaza con 422 nombrando el campo. Se comprueba allí y no aquí para que la
        # lista de campos obligatorios tenga UN dueño: la tabla. Y si alguna vez se colara,
        # no sería en silencio —la base lo rechaza, que es el modo de fallo que sí se ve—.
        for field, value in update_data.items():
            if hasattr(lead, field):
                setattr(lead, field, value)
        lead.updated_at = datetime.datetime.now(datetime.timezone.utc)

        # Lo que se intenta escribir, antes del `rollback` que lo haría ilegible: la fila ya
        # tiene los valores nuevos encima y el `dump` dice cuáles vinieron en el cuerpo.
        intentado = {"email": lead.email, **update_data}

        try:
            self.db.commit()
        except IntegrityError as exc:
            # Red de seguridad ante dos actualizaciones simultáneas: entre la
            # comprobación anterior y este commit, otra transacción pudo tomar el correo.
            # Desde el capítulo 42 no lo supone: lo pregunta, porque el correo es una de las
            # seis reglas que esta tabla puede hacer cumplir y era la única que esta línea
            # sabía nombrar.
            self.db.rollback()
            raise self._lo_que_la_base_rechazo(intentado, id_propio=lead.id) from exc

        self.db.refresh(lead)
        return lead

    def delete(self, lead_id: int) -> bool:
        """
        Suprime un prospecto con todo lo que el sistema guarda de él, o dice que no estaba.

        Borra por el mapa de `derechos_del_titular` y no con un `db.delete(lead)`, y eso es
        lo que este método arrastraba corregido a medias. La Fase 14 ya había descubierto que
        fiarse de las cascadas dejaba atrás las entregas de webhook, los registros de ingesta
        revertida y el correo de la persona dentro de la bitácora, y cambió el **endpoint**
        para que recorriera ese mapa; este método se quedó con el borrado que esa decisión
        había retirado, sin que lo llamara nadie y pareciendo la forma de borrar un
        prospecto. El día que alguien lo llamara, la supresión volvería a ser incompleta.

        Y era además el único borrado del sistema que dependía de las cláusulas `ondelete`
        del esquema: con `PRAGMA foreign_keys` apagado —el motor de la suite y del desarrollo
        hasta el capítulo 42— las tareas y los avisos del prospecto se quedaban apuntando a
        una fila que ya no estaba, y la bandeja «Hoy» de su asesor reventaba al pintarlas.
        """
        from app.services.derechos_del_titular import suprimir_prospecto

        lead = self._acotar(self.db.query(Lead)).filter(Lead.id == lead_id).first()
        if not lead:
            return False
        suprimir_prospecto(self.db, lead)
        return True

