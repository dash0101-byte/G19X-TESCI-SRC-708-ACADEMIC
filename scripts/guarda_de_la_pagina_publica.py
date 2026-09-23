"""
Guarda del CI para la página de interés: la única ruta sin sesión que escribe en la base.

    python scripts/guarda_de_la_pagina_publica.py

Falla —con un mensaje que dice qué se perdió— si la página:

1. **pierde el límite de envíos**: los límites por defecto dejan de existir o se vuelven
   decorativos, o la ruta deja de aplicarlos (se comprueba enviando de verdad hasta que
   corte, uno por IP y otro por publicación); o abrir la página vuelve a gastar el cupo de
   enviar, o la lectura se queda sin límite propio;
2. **acepta texto libre**: el esquema deja de rechazar campos de más, aparece un campo que
   admite cualquier cosa, o algo escrito por la persona acaba guardado en la actividad;
3. **se desalinea del modelo**: las listas de cargo, sector y tamaño que sirve la página dejan
   de ser las categorías que conoce el artefacto que puntúa;
4. **deja de ser un formulario de treinta segundos sin datos supuestos**: obliga a algo más
   que nombre, correo, empresa, cargo, tamaño, sector, necesidad y aviso; vuelve a preguntar
   o a escribir la facturación; «¿Qué necesitas?» mueve la puntuación; el campo trampa deja
   de descartar; o la respuesta cambia según el correo ya exista;
5. **el heurístico supone lo que falta**: un tamaño, cargo o sector que no llegó puntúa como
   un valor concreto —«1-10», la base de un estudiante— en lugar del punto medio del bloque,
   en la regla o en el servicio que la llama;
6. **deja de respetar el ciclo de la publicación** (capítulo 26): sirve una publicación que
   no está activa —un borrador, una pausada, una cerrada o una vencida sin que nadie la
   cerrara—; cuenta visitas con algo más que un número por día, pone cookies o cuenta la
   vista previa del panel; acepta una necesidad que no es de las opciones de esa
   publicación o deja que alguna puntúe; no asigna el responsable, o asigna uno que ya no es
   asesor activo; o guarda como dirección del post algo que no es de linkedin.com;
7. **deja de aguantar cualquier red en el enlace** (capítulo 27): una red desconocida o
   manipulada en `?r=` rechaza el envío en lugar de contarse como «sin red»; la red de
   llegada deja de marcar el canal de la ficha o las visitas dejan de repartirse por red;
   alguno de esos canales pasa a ser una categoría que el modelo conoce, con lo que la red
   empezaría a mover el score; el texto de una red se pasa de su tope o se come el enlace;
   o un botón de compartir lleva credenciales en la dirección;
8. **pierde la tarjeta de las redes** (capítulo 27): el HTML servido deja de traer las
   etiquetas Open Graph y de X —que es lo único que lee un rastreador, porque no ejecuta
   JavaScript—; un título con comillas o con marcado consigue romperlas o meter etiquetas
   de más; una publicación que no está activa filtra su título; o la imagen de vista previa
   deja de ser un PNG de 1 200 x 630 dibujado aquí.

Por qué además de la suite: las pruebas de `test_pagina_de_interes.py` comprueban casos; esta
guarda comprueba **propiedades**. Un campo nuevo `comentarios: str` no rompe ninguna prueba
existente —nadie lo envía—, y aquí falla en cuanto existe. Se ejecuta contra el artefacto
validado del CI y una base SQLite temporal, como paso con nombre propio: si falla, el
motivo se lee en el título del paso y no enterrado entre novecientas pruebas.
"""
import os
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BASE_TEMPORAL = os.path.join(tempfile.mkdtemp(prefix="guarda-interes-"), "guarda.db")
# Antes de importar la aplicación: la configuración lee la base al cargarse.
os.environ["DATABASE_URL"] = f"sqlite:///{_BASE_TEMPORAL}"
os.environ.setdefault("ENVIRONMENT", "development")
sys.path.insert(0, os.path.join(RAIZ, "backend"))

import joblib  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.publicaciones import CANAL_LINKEDIN  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.scoring_rules import (  # noqa: E402
    DEFAULT_TITLE_POINTS,
    SIZE_POINTS,
    UNKNOWN_INDUSTRY_POINTS,
    UNKNOWN_SIZE_POINTS,
    UNKNOWN_TITLE_POINTS,
    calculate_heuristic_score,
)
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO  # noqa: E402
from app.models.entities import Campaign, Lead, LeadActivity, ScoreHistory  # noqa: E402
from app.schemas.interes import NECESIDADES, SolicitudDeInteres  # noqa: E402
from limits import parse  # noqa: E402
from pydantic import ValidationError  # noqa: E402

ARTEFACTO = os.path.join(RAIZ, "ml_pipeline", "models", "lead_scorer_model.joblib")

# Techos de los límites por defecto. No son los valores de hoy (10 y 120 por hora): son el
# punto a partir del cual el límite ya no frena nada. Subir un límite por debajo del techo
# es una decisión; pasarlo, o quitarlo, es perderlo.
TECHO_POR_IP_A_LA_HORA = 60
TECHO_POR_PUBLICACION_A_LA_HORA = 600
# Abrir la página no escribe nada y tiene su propia cuenta; aun así, sin techo, recorrer
# enlaces en bucle sería gratis.
TECHO_DE_LECTURAS_A_LA_HORA = 600

# Los únicos campos que la persona escribe: sus datos de contacto, su empresa y su perfil,
# cada uno con su tope. Todo lo demás tiene que ser una lista cerrada. El campo trampa está
# aquí porque lo rellenan los robots, y lo que traiga se descarta sin guardarse.
ESCRITOS_POR_LA_PERSONA = {
    "nombre": 100, "correo": 150, "telefono": 50,
    "empresa": 150, "linkedin": 200, "sitio_web": 200,
}

# Lo único que la actividad guarda de una solicitud. Ni el correo, ni la empresa, ni ningún
# texto de la persona: eso vive en la ficha, con su propio criterio de acceso y supresión.
#
# `necesidad_etiqueta` es la etiqueta de la opción elegida, que escribió el líder al configurar
# la publicación (capítulo 26), no la persona: se guarda para que cambiar después las opciones
# no cambie lo que eligió quien ya escribió.
#
# `red` y `red_etiqueta` son la red de difusión por la que llegó (capítulo 27). Tampoco las
# escribe la persona: la clave sale del catálogo cerrado del servidor —lo que no está en él
# se guarda como `sin_red`— y la etiqueta es la de ese mismo catálogo. No dicen nada de
# quien visita, solo por dónde se repartió el enlace.
DATOS_DE_LA_ACTIVIDAD = {
    "publicacion", "necesidad", "necesidad_etiqueta", "aviso_aceptado_en", "red", "red_etiqueta",
}

# La solicitud de referencia toma cargo, sector y tamaño de las listas del modelo y no de
# valores escritos aquí: si esas listas cambian, la referencia sigue siendo válida y cada
# comprobación falla por lo que mide, no porque la referencia dejó de pasar.
VALIDA = {
    "nombre": "Guarda Del CI", "correo": "guarda.ci@ejemplo-demo.mx",
    "telefono": "5511223344", "empresa": "Empresa de la Guarda",
    "cargo": CATEGORIAS_DEL_MODELO["job_title"][0],
    "sector": CATEGORIAS_DEL_MODELO["industry"][0],
    "tamano_de_empresa": CATEGORIAS_DEL_MODELO["company_size"][0],
    "linkedin": "https://www.linkedin.com/in/guarda-del-ci", "necesidad": "vacantes",
    "aviso_de_privacidad": True, "sitio_web": "",
}

# Lo único obligatorio. Añadir un campo obligatorio alarga los treinta segundos; volver
# opcional uno de estos deja al asesor sin a quién llamar o al modelo sin qué puntuar.
OBLIGATORIOS = {
    "nombre", "correo", "empresa", "cargo", "tamano_de_empresa", "sector", "necesidad",
    "aviso_de_privacidad",
}

# Cualquier forma de preguntar o de escribir la facturación. La página no la pide, y la
# ficha que crea la deja vacía: `annual_revenue` es «no lo sabemos», no una cifra.
PALABRAS_DE_INGRESOS = ("ingreso", "revenue", "factura", "tramo")

fallos: list[str] = []


def fallo(mensaje: str) -> None:
    fallos.append(mensaje)
    print(f"  FALLO: {mensaje}")


def por_hora(limite: str) -> float:
    item = parse(limite)
    return item.amount * 3600 / item.get_expiry()


# ----------------------------------------------------------------------------- 1. límites
def comprobar_limites(cliente, slug: str) -> None:
    print("1. Límite de envíos")
    for nombre, techo in (
        ("INTERES_LIMITE_POR_IP", TECHO_POR_IP_A_LA_HORA),
        ("INTERES_LIMITE_POR_PUBLICACION", TECHO_POR_PUBLICACION_A_LA_HORA),
        ("INTERES_LIMITE_DE_LECTURAS_POR_IP", TECHO_DE_LECTURAS_A_LA_HORA),
    ):
        valor = getattr(settings, nombre, None)
        if not valor:
            fallo(f"{nombre} ya no existe o está vacío.")
            continue
        if por_hora(valor) > techo:
            fallo(f"{nombre}={valor!r} deja pasar más de {techo} peticiones por hora.")

    ruta = f"/api/v1/interes/{slug}"
    originales = (
        settings.INTERES_LIMITE_POR_IP, settings.INTERES_LIMITE_POR_PUBLICACION,
        settings.INTERES_LIMITE_DE_LECTURAS_POR_IP, limiter.enabled,
    )
    try:
        limiter.enabled = True
        settings.INTERES_LIMITE_DE_LECTURAS_POR_IP = "1000/hour"
        for ambito, por_ip, por_publicacion in (("IP", "2/hour", "1000/hour"), ("publicación", "1000/hour", "2/hour")):
            settings.INTERES_LIMITE_POR_IP = por_ip
            settings.INTERES_LIMITE_POR_PUBLICACION = por_publicacion
            limiter.reset()
            # Antes de enviar, se abre la página unas cuantas veces: ver no puede gastar
            # el cupo de enviar.
            for _ in range(3):
                cliente.get(ruta)
            codigos = [
                cliente.post(ruta, json={**VALIDA, "correo": f"limite{ambito[:2]}{i}@ejemplo-demo.mx"}).status_code
                for i in range(3)
            ]
            if codigos[:2] != [202, 202] or codigos[2] != 429:
                fallo(
                    f"con un límite de 2 por {ambito} y tres visitas previas, tres envíos respondieron "
                    f"{codigos}: la ruta no lo aplica, o abrir la página gasta el cupo de enviar."
                )

        settings.INTERES_LIMITE_POR_IP = settings.INTERES_LIMITE_POR_PUBLICACION = "1000/hour"
        settings.INTERES_LIMITE_DE_LECTURAS_POR_IP = "2/hour"
        limiter.reset()
        lecturas = [cliente.get(ruta).status_code for _ in range(3)]
        if lecturas != [200, 200, 429]:
            fallo(f"con un límite de 2 lecturas, tres visitas respondieron {lecturas}: la lectura no tiene límite.")
    finally:
        (
            settings.INTERES_LIMITE_POR_IP, settings.INTERES_LIMITE_POR_PUBLICACION,
            settings.INTERES_LIMITE_DE_LECTURAS_POR_IP, limiter.enabled,
        ) = originales
        limiter.reset()


# -------------------------------------------------------------------------- 2. texto libre
def comprobar_texto_libre(cliente, slug: str) -> None:
    print("2. Sin texto libre")
    try:
        SolicitudDeInteres(**VALIDA)
    except ValidationError as exc:
        # Sin una referencia válida, «rechaza una frase cualquiera» se cumpliría siempre.
        fallo(f"la solicitud de referencia no pasa el esquema; la comprobación no mediría nada: {exc}")
        return
    if SolicitudDeInteres.model_config.get("extra") != "forbid":
        fallo("el esquema ya no rechaza campos de más (extra != 'forbid').")

    campos = SolicitudDeInteres.model_fields
    for nombre, campo in campos.items():
        if nombre in ESCRITOS_POR_LA_PERSONA:
            tope = next((m.max_length for m in campo.metadata if getattr(m, "max_length", None)), None)
            if tope is None or tope > ESCRITOS_POR_LA_PERSONA[nombre]:
                fallo(f"«{nombre}» no tiene tope de longitud o lo tiene por encima de {ESCRITOS_POR_LA_PERSONA[nombre]}.")
            continue
        if nombre == "aviso_de_privacidad":
            continue
        # Cualquier otro campo tiene que rechazar una frase cualquiera: si la admite, es texto libre.
        try:
            SolicitudDeInteres(**{**VALIDA, nombre: "Cuéntenos su caso con sus propias palabras"})
            fallo(f"«{nombre}» admite texto libre: no es una lista cerrada ni un dato de contacto.")
        except ValidationError:
            pass

    respuesta = cliente.post(f"/api/v1/interes/{slug}", json={**VALIDA, "comentarios": "texto libre"})
    if respuesta.status_code != 422:
        fallo(f"un envío con un campo de más respondió {respuesta.status_code}, no 422.")

    db = SessionLocal()
    try:
        cliente.post(f"/api/v1/interes/{slug}", json={**VALIDA, "correo": "almacen.ci@ejemplo-demo.mx"})
        lead = db.query(Lead).filter(Lead.email == "almacen.ci@ejemplo-demo.mx").first()
        if lead is None:
            fallo("un envío válido no creó la ficha: no se puede comprobar qué se guarda.")
            return
        for actividad in db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id):
            sobrantes = set(actividad.activity_data or {}) - DATOS_DE_LA_ACTIVIDAD
            if sobrantes:
                fallo(f"la actividad guarda {sorted(sobrantes)} además de {sorted(DATOS_DE_LA_ACTIVIDAD)}.")
    finally:
        db.close()


# ------------------------------------------------------------------ 3. alineación con el modelo
def comprobar_alineacion(cliente, slug: str) -> None:
    print("3. Listas del modelo")
    if not os.path.exists(ARTEFACTO):
        fallo(f"no está el artefacto que puntúa ({ARTEFACTO}); sin él no hay contra qué comparar.")
        return
    preprocesador = joblib.load(ARTEFACTO).named_steps["preprocessor"]
    codificador = preprocesador.named_transformers_["cat"]
    columnas = preprocesador.transformers_[0][2]
    conocidas = {c: set(v) for c, v in zip(columnas, codificador.categories_, strict=True)}

    opciones = cliente.get(f"/api/v1/interes/{slug}").json()["opciones"]
    for lista, variable in (("cargos", "job_title"), ("sectores", "industry"), ("tamanos", "company_size")):
        servidas = set(opciones.get(lista, []))
        if servidas != conocidas.get(variable, set()):
            fallo(
                f"la página sirve «{lista}» distinta de lo que conoce el modelo en {variable}: "
                f"sobran {sorted(servidas - conocidas.get(variable, set()))}, "
                f"faltan {sorted(conocidas.get(variable, set()) - servidas)}."
            )
        for valor in servidas:
            campo = {"cargos": "cargo", "sectores": "sector", "tamanos": "tamano_de_empresa"}[lista]
            try:
                SolicitudDeInteres(**{**VALIDA, campo: valor})
            except ValidationError:
                fallo(f"la página ofrece «{valor}» en {lista} y el esquema lo rechaza.")


# --------------------------------------------------------- 4. treinta segundos, nada supuesto
def _ficha(db, correo: str):
    db.expire_all()
    return db.query(Lead).filter(Lead.email == correo).first()


def _sin_hora(respuesta):
    """Código y cuerpo, sin la hora: lo único que puede cambiar de un envío a otro."""
    datos = dict(respuesta.json())
    datos.pop("recibido_en", None)
    return respuesta.status_code, datos


def comprobar_formulario(cliente, slug: str) -> None:
    print("4. Formulario de treinta segundos sin datos supuestos")
    ruta = f"/api/v1/interes/{slug}"
    campos = SolicitudDeInteres.model_fields
    obligatorios = {nombre for nombre, campo in campos.items() if campo.is_required()}
    if obligatorios != OBLIGATORIOS:
        fallo(
            f"los obligatorios ya no son los imprescindibles: sobran {sorted(obligatorios - OBLIGATORIOS)}, "
            f"faltan {sorted(OBLIGATORIOS - obligatorios)}."
        )
    de_ingresos = [n for n in campos if any(p in n.lower() for p in PALABRAS_DE_INGRESOS)]
    if de_ingresos:
        fallo(f"el formulario vuelve a preguntar la facturación: {de_ingresos}.")
    opciones = cliente.get(ruta).json().get("opciones", {})
    listas_de_ingresos = [n for n in opciones if any(p in n.lower() for p in PALABRAS_DE_INGRESOS)]
    if listas_de_ingresos:
        fallo(f"la página sirve una lista de facturación: {listas_de_ingresos}.")

    db = SessionLocal()
    try:
        # Lo mínimo: solo lo obligatorio. Tiene que entrar, y lo que no se dijo, quedar vacío.
        minima = {k: v for k, v in VALIDA.items() if k in OBLIGATORIOS}
        minima["correo"] = "minima.ci@ejemplo-demo.mx"
        codigo = cliente.post(ruta, json=minima).status_code
        lead = _ficha(db, minima["correo"])
        if codigo != 202 or lead is None:
            fallo(f"un envío con solo lo obligatorio respondió {codigo} y no creó la ficha.")
        else:
            inventados = {
                campo: valor
                for campo, valor in (("phone", lead.phone), ("annual_revenue", lead.annual_revenue))
                if valor is not None
            }
            if inventados:
                fallo(f"la ficha rellena lo que la persona no dijo: {inventados}.")

        # «¿Qué necesitas?» informa y no puntúa: cuatro personas iguales salvo en eso.
        resultados = {}
        for necesidad in sorted(NECESIDADES):
            correo = f"necesita.{necesidad}@ejemplo-demo.mx"
            cliente.post(ruta, json={**minima, "correo": correo, "necesidad": necesidad})
            lead = _ficha(db, correo)
            if lead is None:
                fallo(f"el envío con necesidad «{necesidad}» no creó la ficha.")
                continue
            historial = db.query(ScoreHistory).filter(ScoreHistory.lead_id == lead.id).first()
            resultados[necesidad] = (
                lead.current_score,
                historial.ml_probability if historial else None,
                tuple(sorted((historial.rule_breakdown or {}).items())) if historial else None,
                tuple(sorted({a.activity_type.value for a in lead.activities})),
            )
        if len(set(resultados.values())) > 1:
            fallo(f"«¿Qué necesitas?» mueve la puntuación o el tipo de actividad: {resultados}.")

        # La misma respuesta para una ficha nueva, un correo que ya existe y el campo trampa;
        # y el campo trampa, además, no deja nada escrito.
        sin_contacto = {**VALIDA, "telefono": None, "linkedin": None}
        nueva = _sin_hora(cliente.post(ruta, json={**sin_contacto, "correo": "repetido.ci@ejemplo-demo.mx"}))
        repetida = _sin_hora(cliente.post(ruta, json={**sin_contacto, "correo": "repetido.ci@ejemplo-demo.mx"}))
        trampa = _sin_hora(
            cliente.post(ruta, json={**sin_contacto, "correo": "robot.ci@ejemplo-demo.mx", "sitio_web": "https://spam.example"})
        )
        if not (nueva == repetida == trampa):
            fallo(f"la respuesta distingue casos: nueva={nueva}, repetida={repetida}, trampa={trampa}.")
        if _ficha(db, "robot.ci@ejemplo-demo.mx") is not None:
            fallo("un envío con el campo trampa relleno creó una ficha.")
    finally:
        db.close()


# ---------------------------------------------------------------- 5. heurístico sin suponer
def comprobar_heuristico() -> None:
    print("5. Heurístico sin suposiciones")
    base = {"job_title": "CTO", "industry": "FinTech", "company_size": "1000+"}
    casos = (
        ("company_size", "company_size_fit_score", UNKNOWN_SIZE_POINTS),
        ("job_title", "title_fit_score", UNKNOWN_TITLE_POINTS),
        ("industry", "industry_fit_score", UNKNOWN_INDUSTRY_POINTS),
    )
    for variable, clave, desconocido in casos:
        for falta in (None, "", "  "):
            puntos = calculate_heuristic_score(**{**base, variable: falta})[1][clave]
            if puntos != desconocido:
                fallo(f"sin {variable} ({falta!r}) la regla da {puntos} y no el punto medio {desconocido}.")
    if UNKNOWN_SIZE_POINTS == SIZE_POINTS.get("1-10") or UNKNOWN_TITLE_POINTS == DEFAULT_TITLE_POINTS:
        fallo("lo desconocido puntúa igual que «1-10» o que un cargo sin poder de decisión.")

    # El servicio que llama a la regla tampoco puede rellenar el hueco antes de llamarla.
    import asyncio

    from app.services.scoring_service import ScoringService

    db = SessionLocal()
    try:
        lead = Lead(
            first_name="Sin datos", last_name="", email="sin.datos.ci@ejemplo-demo.mx",
            job_title=None, industry=None, company_size=None, source="Website",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        resultado = asyncio.run(ScoringService(db).calculate_and_persist_score(lead, generate_ai_text=False))
        for clave, desconocido in (
            ("company_size_fit_score", UNKNOWN_SIZE_POINTS),
            ("title_fit_score", UNKNOWN_TITLE_POINTS),
            ("industry_fit_score", UNKNOWN_INDUSTRY_POINTS),
        ):
            obtenido = resultado.rule_breakdown.get(clave)
            if obtenido != desconocido:
                fallo(f"el servicio puntúa una ficha sin datos con {clave}={obtenido}, no {desconocido}.")
    finally:
        db.close()


# ------------------------------------------------------ 6. el ciclo de la publicación
# Un «hash» que ningún bcrypt produce: las cuentas de la guarda no inician sesión nunca.
CUENTA_SIN_ACCESO = "!sin-contrasena:guarda"

DIRECCIONES_FALSAS = (
    "http://www.linkedin.com/posts/x",
    "https://linkedin.com.ejemplo.net/posts/x",
    "https://ejemplo.net/?ir=linkedin.com",
    "https://milinkedin.com/posts/x",
    "https://usuario@www.linkedin.com/posts/x",
    "javascript:alert(1)//linkedin.com/x",
)


def _publicacion(db, **campos) -> Campaign:
    from app.services.ciclo_de_publicaciones import fijar_estado

    estado = campos.pop("estado", "activa")
    campana = Campaign(name=campos.pop("name", "Guarda · ciclo"), channel=CANAL_LINKEDIN, **campos)
    fijar_estado(campana, estado)
    db.add(campana)
    db.commit()
    db.refresh(campana)
    return campana


def comprobar_ciclo(cliente) -> None:
    import datetime

    from app.core.publicaciones import normalizar_necesidades, normalizar_url_del_post
    from app.models.entities import User, VisitaDePublicacion
    from app.schemas.user import CampanaCreate

    print("6. El ciclo de la publicación")
    minima = {k: v for k, v in VALIDA.items() if k in OBLIGATORIOS}
    db = SessionLocal()
    try:
        # Solo «activa» sirve la página; y una activa vencida se cierra antes de servirla.
        ayer = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        casos = {estado: _publicacion(db, estado=estado) for estado in ("borrador", "pausada", "cerrada")}
        casos["vencida"] = _publicacion(db, estado="activa", end_date=ayer)
        for nombre, campana in casos.items():
            ruta = f"/api/v1/interes/{campana.public_slug}"
            codigos = (
                cliente.get(ruta).status_code,
                cliente.post(ruta, json={**minima, "correo": f"ciclo.{nombre}@ejemplo-demo.mx"}).status_code,
            )
            if codigos != (404, 404):
                fallo(f"una publicación {nombre} responde {codigos} en su página, no «no disponible».")

        # Visitas: un número por día, sin cookie, y la vista previa del panel no cuenta.
        columnas = {c.name for c in VisitaDePublicacion.__table__.columns}
        if columnas != {"campaign_id", "dia", "red", "visitas"}:
            fallo(f"el contador de visitas guarda más que un número por día y red: {sorted(columnas)}.")
        activa = _publicacion(db, estado="activa")
        ruta = f"/api/v1/interes/{activa.public_slug}"
        respuestas = [cliente.get(ruta) for _ in range(3)]
        if any("set-cookie" in {k.lower() for k in r.headers} for r in respuestas):
            fallo("abrir la página pone una cookie.")
        db.expire_all()
        contadas = sum(
            v.visitas for v in db.query(VisitaDePublicacion).filter(VisitaDePublicacion.campaign_id == activa.id)
        )
        if contadas != 3:
            fallo(f"tres aperturas de la página contaron {contadas} visitas.")
        from app.api.v1.endpoints.publicaciones import vista_previa_de_la_pagina

        vista_previa_de_la_pagina(activa.id, db=db, current_user=None)
        db.expire_all()
        tras_la_previa = sum(
            v.visitas for v in db.query(VisitaDePublicacion).filter(VisitaDePublicacion.campaign_id == activa.id)
        )
        if tras_la_previa != contadas:
            fallo("la vista previa desde el panel cuenta como una visita.")

        # Opciones propias: solo esas valen, y ninguna puntúa.
        opciones = normalizar_necesidades(["Cubrir una vacante", "Montar un equipo", "Solo mirar"])
        propia = _publicacion(db, estado="activa", necesidades=opciones)
        ruta = f"/api/v1/interes/{propia.public_slug}"
        servidas = cliente.get(ruta).json().get("opciones", {}).get("necesidades", {})
        if list(servidas) != [o["clave"] for o in opciones]:
            fallo(f"la página no sirve las opciones de su publicación: {servidas}.")
        ajena = cliente.post(ruta, json={**minima, "correo": "ajena.ci@ejemplo-demo.mx", "necesidad": "vacantes"})
        if ajena.status_code != 422:
            fallo(f"una necesidad que no es de esta publicación respondió {ajena.status_code}, no 422.")
        puntuaciones = set()
        for i, opcion in enumerate(opciones):
            correo = f"propia{i}.ci@ejemplo-demo.mx"
            cliente.post(ruta, json={**minima, "correo": correo, "necesidad": opcion["clave"]})
            lead = _ficha(db, correo)
            if lead is None:
                fallo(f"el envío con la opción «{opcion['etiqueta']}» no creó la ficha.")
                continue
            historial = db.query(ScoreHistory).filter(ScoreHistory.lead_id == lead.id).first()
            puntuaciones.add((lead.current_score, tuple(sorted((historial.rule_breakdown or {}).items()))))
        if len(puntuaciones) > 1:
            fallo(f"las opciones propias de «¿Qué necesitas?» mueven la puntuación: {puntuaciones}.")

        # Responsable: se asigna si es asesor activo; si no, la ficha llega sin asesor.
        asesor = User(
            email="responsable.ci@ejemplo-demo.mx", full_name="Responsable CI", role="Commercial_Executive",
            hashed_password=CUENTA_SIN_ACCESO, is_sales_rep=True, is_active=True,
        )
        baja = User(
            email="baja.ci@ejemplo-demo.mx", full_name="Baja CI", role="Commercial_Executive",
            hashed_password=CUENTA_SIN_ACCESO, is_sales_rep=True, is_active=False,
        )
        db.add_all([asesor, baja])
        db.commit()
        for usuario, esperado in ((asesor, asesor.id), (baja, None)):
            con_responsable = _publicacion(db, estado="activa", responsable_id=usuario.id)
            correo = f"asignada.{usuario.id}.ci@ejemplo-demo.mx"
            cliente.post(
                f"/api/v1/interes/{con_responsable.public_slug}", json={**minima, "correo": correo}
            )
            lead = _ficha(db, correo)
            asignado = lead.assigned_rep_id if lead else "sin ficha"
            if asignado != esperado:
                fallo(f"con responsable {usuario.full_name} la ficha llegó asignada a {asignado}, no a {esperado}.")
    finally:
        db.close()

    # La dirección del post: de linkedin.com por el nombre de la máquina.
    if normalizar_url_del_post("www.linkedin.com/posts/x?utm_source=share") != "https://www.linkedin.com/posts/x":
        fallo("una dirección de post válida no se guarda limpia.")
    for falsa in DIRECCIONES_FALSAS:
        try:
            CampanaCreate(name="Guarda", channel=CANAL_LINKEDIN, url_del_post=falsa)
            fallo(f"se acepta como dirección del post «{falsa}».")
        except ValidationError:
            pass


def comprobar_redes(cliente) -> None:
    """
    Una publicación, varias redes (capítulo 27).

    Las propiedades que no pueden perderse, en este orden:

    * **Ninguna red rechaza a nadie.** El parámetro `?r=` lo edita cualquiera: una red
      inventada, manipulada o borrada tiene que dejar pasar el envío y contarse «sin red».
      Lo contrario convierte una etiqueta de analítica en una puerta que se cierra desde
      fuera editando la dirección.
    * **El modelo no conoce estos canales.** Si alguno coincidiera con una categoría que el
      modelo aprendió, la red de llegada empezaría a mover el score sin que nadie lo
      decidiera.
    * **El enlace nunca se recorta.** En X el texto cabe en 280 contando el enlace, y lo que
      cede es la descripción.
    * **Sin API ni cuentas.** Los botones son direcciones públicas de compartir: ninguna
      lleva clave, token ni identificador de aplicación.
    """
    from app.core import redes as r
    from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO
    from app.models.entities import Lead, VisitaDePublicacion
    from app.schemas.user import CampanaResponse

    print("7. Una publicación, varias redes")
    minima = {k: v for k, v in VALIDA.items() if k in OBLIGATORIOS}
    db = SessionLocal()
    try:
        publicacion = _publicacion(db, name="Guarda · redes", description="Texto de la guarda. " * 40)
        ruta = f"/api/v1/interes/{publicacion.public_slug}"

        # Ninguna red rechaza a nadie.
        #
        # Se captura la excepción además de mirar el código: `TestClient` vuelve a lanzar lo
        # que reviente dentro de la aplicación, y un rastro de pila enterraría el motivo en
        # un paso del CI que solo se lee por su título. Que la página explote con una red
        # inventada es exactamente el fallo que esta comprobación busca, así que se nombra.
        for etiqueta in ("tiktok", "../../etc/passwd", "x" * 300, "", "whatsapp'; DROP TABLE x"):
            correo = f"red.{abs(hash(etiqueta)) % 10**8}@ejemplo-demo.mx"
            try:
                codigos = (
                    cliente.get(ruta, params={"r": etiqueta}).status_code,
                    cliente.post(f"{ruta}?r={etiqueta}", json={**minima, "correo": correo}).status_code,
                )
            except Exception as error:  # noqa: BLE001  cualquier excepción aquí es el fallo
                fallo(
                    f"una red que no se reconoce («{etiqueta[:20]}») revienta la página: "
                    f"{type(error).__name__}: {error}."
                )
                continue
            if codigos != (200, 202):
                fallo(
                    f"una red que no se reconoce («{etiqueta[:20]}») deja la página en "
                    f"{codigos[0]}/{codigos[1]} en lugar de dejar pasar."
                )

        # Y una que sí se reconoce marca el canal de la ficha.
        cliente.post(f"{ruta}?r=whatsapp", json={**minima, "correo": "red.whatsapp@ejemplo-demo.mx"})
        db.expire_all()
        ficha = db.query(Lead).filter(Lead.email == "red.whatsapp@ejemplo-demo.mx").first()
        if ficha is None or ficha.source != "WhatsApp":
            fallo(f"llegar por WhatsApp no deja el canal de la ficha: {ficha and ficha.source}.")

        # El modelo no conoce ninguno de estos canales: todos neutros.
        conocidas = set(CATEGORIAS_DEL_MODELO["source_channel"])
        intrusas = [c for c in r.CANALES_DE_PUBLICACION if c in conocidas]
        if intrusas:
            fallo(f"el modelo conoce canales de la página y dejarían de ser neutros: {intrusas}.")

        # Las visitas se reparten por red y siguen sin decir nada de quien visita.
        cliente.get(ruta, params={"r": "facebook"})
        db.expire_all()
        por_red = {
            v.red: v.visitas
            for v in db.query(VisitaDePublicacion).filter(
                VisitaDePublicacion.campaign_id == publicacion.id
            )
        }
        if "facebook" not in por_red or "sin_red" not in por_red:
            fallo(f"las visitas no se reparten por red: {por_red}.")

        # El enlace no se recorta, y cada red apunta a la misma página.
        difusion = {f.clave: f for f in CampanaResponse.model_validate(publicacion).difusion}
        for clave, fila in difusion.items():
            if publicacion.public_slug not in fila.enlace:
                fallo(f"el enlace de {clave} no lleva a esta publicación: «{fila.enlace}».")
            if not fila.texto.rstrip().endswith(fila.enlace):
                fallo(f"el texto de {clave} no termina en su enlace entero: «{fila.texto[-60:]}».")
            if fila.maximo is not None and fila.longitud > fila.maximo:
                fallo(f"el texto de {clave} se pasa de su tope: {fila.longitud} > {fila.maximo}.")
        if difusion["x"].maximo != 280:
            fallo(f"X dejó de contar 280 caracteres: {difusion['x'].maximo}.")

        # Sin API ni cuentas.
        for clave, fila in difusion.items():
            if not fila.compartir:
                continue
            sospechosas = [p for p in ("api_key", "client_id", "access_token", "oauth") if p in fila.compartir.lower()]
            if sospechosas:
                fallo(f"el botón de {clave} lleva credenciales en la dirección: {sospechosas}.")
    finally:
        db.close()


def comprobar_vista_previa(cliente) -> None:
    """
    La tarjeta que enseñan las redes al pegar el enlace (capítulo 27).

    Las propiedades que no pueden perderse:

    * **Las etiquetas están en el HTML servido.** Quien las lee no ejecuta JavaScript: si
      dejaran de estar, el enlace volvería a salir como una tarjeta vacía y nadie se
      enteraría hasta compartirlo.
    * **Lo que no está activo no filtra nada.** Un borrador, una pausada, una cerrada y un
      enlace inventado dan las mismas etiquetas genéricas y el mismo código de respuesta.
    * **Todo va escapado.** Un título con comillas o con `<script>` entra como texto; se
      comprueba analizando el HTML, que es lo que hace el rastreador.
    * **La imagen es un PNG de 1 200 × 630** dibujado aquí, no pedido a ningún servicio.
    """
    import re
    import struct
    from html.parser import HTMLParser

    from app.core.etiquetas_sociales import TITULO_GENERICO

    # El tamaño va escrito aquí, no leído de `tarjeta.py`. Es lo que piden LinkedIn y X
    # para la imagen ancha, no una preferencia nuestra: leerlo del módulo que se comprueba
    # haría una comprobación que pasa siempre, porque cambiaría con él.
    ANCHO_DE_LA_TARJETA, ALTO_DE_LA_TARJETA = 1200, 630

    print("8. La tarjeta de las redes")

    class Lector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.meta, self.etiquetas = {}, []

        def handle_starttag(self, tag, attrs):
            self.etiquetas.append(tag)
            d = dict(attrs)
            clave = d.get("property") or d.get("name")
            if tag == "meta" and clave:
                self.meta[clave] = d.get("content", "")

    def leer(texto):
        lector = Lector()
        lector.feed(texto)
        return lector

    db = SessionLocal()
    try:
        titulo = 'Guarda " con <script>alert(1)</script> y & TI'
        activa = _publicacion(db, name=titulo, estado="activa", description="Texto de la guarda.")
        borrador = _publicacion(db, name=titulo, estado="borrador")

        # Se captura la excepción además de mirar el código: que la página reviente con una
        # publicación que no está activa es uno de los fallos que esto busca, y un rastro de
        # pila lo enterraría en un paso del CI que solo se lee por su título.
        try:
            respuesta = cliente.get(f"/interes/{activa.public_slug}")
        except Exception as error:  # noqa: BLE001  cualquier excepción aquí es el fallo
            fallo(f"la página pública revienta al servirse: {type(error).__name__}: {error}.")
            return
        if respuesta.status_code != 200 or not respuesta.headers.get("content-type", "").startswith("text/html"):
            fallo(f"la página pública ya no sirve HTML: {respuesta.status_code} {respuesta.headers.get('content-type')}.")
            return

        # Sin lo que hay dentro de los <script>: es lo único que ve un rastreador.
        sin_js = re.sub(r"<script[ >].*?</script>", "", respuesta.text, flags=re.S)
        leido = leer(sin_js)
        faltan = [e for e in ("og:title", "og:description", "og:url", "og:image", "twitter:card") if e not in leido.meta]
        if faltan:
            fallo(f"el HTML servido ya no trae las etiquetas de la tarjeta: faltan {faltan}.")
        if leido.meta.get("twitter:card") != "summary_large_image":
            fallo(f"X dejaría de enseñar la imagen ancha: twitter:card={leido.meta.get('twitter:card')!r}.")

        # El escape: el título entra entero y no aparece ninguna etiqueta de más.
        if leido.meta.get("og:title") != titulo:
            fallo(f"el título no llega entero a la etiqueta: {leido.meta.get('og:title')!r}.")
        # Dos problemas distintos, dos mensajes: meter una etiqueta en el documento y
        # duplicar una etiqueta de la tarjeta no se arreglan igual.
        if "script" in leido.etiquetas:
            fallo(f"un título con marcado mete etiquetas en el documento: {leido.etiquetas}.")
        veces = respuesta.text.count('property="og:title"')
        if veces != 1:
            fallo(f"el documento trae {veces} etiquetas og:title; la red leería la que no es.")

        # Lo que no está activo no dice nada de sí mismo.
        try:
            del_borrador = cliente.get(f"/interes/{borrador.public_slug}")
            inventado = cliente.get("/interes/estoMeLoInvento00000x")
        except Exception as error:  # noqa: BLE001
            fallo(f"una publicación que no está activa revienta la página: {type(error).__name__}: {error}.")
            return
        if del_borrador.status_code != inventado.status_code:
            fallo("el código de respuesta distingue un borrador de un enlace inventado.")
        if leer(del_borrador.text).meta.get("og:title") != TITULO_GENERICO:
            fallo("un borrador filtra su título en las etiquetas de la tarjeta.")
        if titulo.split('"')[0] in del_borrador.text:
            fallo("un borrador filtra su título en el cuerpo del documento.")

        # La imagen, dibujada aquí.
        try:
            png = cliente.get(f"/interes/{activa.public_slug}/tarjeta.png")
        except Exception as error:  # noqa: BLE001
            fallo(f"la imagen de la tarjeta revienta al dibujarse: {type(error).__name__}: {error}.")
            return
        if png.status_code != 200 or png.headers.get("content-type") != "image/png":
            fallo(f"la imagen de la tarjeta ya no es un PNG: {png.status_code} {png.headers.get('content-type')}.")
        elif png.content[:8] != b"\x89PNG\r\n\x1a\n":
            fallo("la imagen de la tarjeta no empieza por la firma de un PNG.")
        else:
            ancho, alto = struct.unpack(">II", png.content[16:24])
            if (ancho, alto) != (ANCHO_DE_LA_TARJETA, ALTO_DE_LA_TARJETA):
                fallo(
                    f"la imagen de la tarjeta mide {ancho}x{alto} y no "
                    f"{ANCHO_DE_LA_TARJETA}x{ALTO_DE_LA_TARJETA}, que es lo que piden las redes."
                )
    finally:
        db.close()


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        publicacion = Campaign(name="Guarda del CI", channel=CANAL_LINKEDIN, description="Guarda")
        db.add(publicacion)
        db.commit()
        db.refresh(publicacion)
        slug = publicacion.public_slug
    finally:
        db.close()

    from app.main import app
    from fastapi.testclient import TestClient

    cliente = TestClient(app)
    limiter.enabled = False
    comprobar_alineacion(cliente, slug)
    comprobar_texto_libre(cliente, slug)
    comprobar_formulario(cliente, slug)
    comprobar_heuristico()
    comprobar_ciclo(cliente)
    comprobar_redes(cliente)
    comprobar_vista_previa(cliente)
    comprobar_limites(cliente, slug)

    if fallos:
        print(f"\nLa página pública perdió {len(fallos)} defensa(s).")
        return 1
    print(
        "\nLímite de envíos, sin texto libre, listas del modelo, treinta segundos sin datos "
        "supuestos, heurístico sin suposiciones, ciclo de la publicación, redes de difusión y "
        "tarjeta de las redes: la página pública conserva sus defensas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
