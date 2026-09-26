"""
Cuánto tarda el panel con un volumen realista, y cuántas consultas cuesta.

Toda la suite trabaja con seis prospectos y un puñado de actividades. Eso es lo correcto
para comprobar reglas —un caso por regla, escrito a mano y legible—, y es exactamente lo que
**no** detecta un problema de rendimiento: con seis filas, una consulta por fila y una
consulta para todas tardan lo mismo.

Aquí se siembran **300 prospectos y 5 000 actividades** y se miden las cuatro pantallas que
más datos mueven: la lista de prospectos, la ficha 360, la bandeja «Hoy» y el informe de una
publicación.

Las dos cosas que se miden, y por qué las dos
---------------------------------------------
**El tiempo** es el número que interesa a quien usa el panel, y es el que no se puede
convertir en una condición estricta: depende de la máquina, y el CI corre en un ejecutor
compartido cuya velocidad varía. Los topes de tiempo van por tanto holgados —buscan la
diferencia entre «rápido» y «se quedó colgado», no entre 40 ms y 60 ms— y el número medido se
imprime para que quede en el reporte.

**El número de consultas SQL** es lo contrario: no depende de la máquina en absoluto. Si un
endpoint hace una consulta por prospecto en vez de una para todos —el defecto llamado N+1—,
el contador lo dice con exactitud y lo dice igual en cualquier ordenador. Ahí los topes van
apretados, y son los que de verdad guardan la puerta.

Lo que este archivo NO mide
---------------------------
**No mide PostgreSQL.** La suite corre sobre SQLite en memoria, que es más rápido en lecturas
pequeñas y no tiene latencia de red. Los milisegundos de aquí no son los de producción, y el
reporte lo dice al pie de la tabla. Lo que sí se traslada tal cual es el número de consultas
y la forma de la curva: un N+1 lo es en los dos motores, y un endpoint que crece con el
número de filas crece en los dos.
"""
import datetime
import statistics
import time

import pytest
from app.core.agenda import ABIERTA
from app.core.database import engine
from app.models.entities import (
    ActivityType,
    Campaign,
    Lead,
    LeadActivity,
    LeadStatus,
    QualificationStatus,
    ScoreCategory,
    Tarea,
    User,
)
from sqlalchemy import event
from tests.conftest import TEST_ACCOUNTS

# El volumen que pide el capítulo. No es una cifra redonda por casualidad: 300 prospectos son
# más de los que PluriOne espera del primer año de la página de interés, y 5 000 actividades
# son unas dieciséis por prospecto, que es lo que deja una cartera trabajada de verdad
# —llamadas, mensajes, reuniones— en vez de una recién importada.
PROSPECTOS = 300
ACTIVIDADES = 5_000

# Cuántas veces se mide cada ruta. La primera medida de cualquier cosa incluye el arranque
# del `TestClient`, la compilación de la consulta por SQLAlchemy y el primer llenado de las
# cachés; tomarla como resultado daría un número que no se repite. Se descarta y se usa la
# **mediana** de las demás, que es lo que aguanta que el sistema operativo robe una pausa.
REPETICIONES = 7

SECTORES = ["FinTech", "Software/TI", "Banking", "Retail", "Logistics", "Educación"]
TAMANOS = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
CARGOS = ["CTO", "CIO", "Gerente de Talento TI", "Director de Operaciones", "Analista"]
TIPOS = [
    ActivityType.PHONE_CALL,
    ActivityType.EMAIL_OPEN,
    ActivityType.MEETING_SCHEDULED,
    ActivityType.DEMO_REQUEST,
    ActivityType.PAGE_VIEW,
]


class ContadorDeConsultas:
    """
    Cuenta las sentencias SQL que se ejecutan mientras está encendido.

    Se cuelga del motor y no de la sesión: así ve también lo que hace el `TestClient` por su
    cuenta —la carga del usuario en cada petición, por ejemplo—, que es parte del coste real
    de la pantalla y no un detalle interno.
    """

    def __init__(self):
        self.sentencias = []

    def __enter__(self):
        event.listen(engine, "before_cursor_execute", self._anotar)
        return self

    def __exit__(self, *_):
        event.remove(engine, "before_cursor_execute", self._anotar)
        return False

    def _anotar(self, conn, cursor, statement, parameters, context, executemany):
        self.sentencias.append(statement)

    def __len__(self):
        return len(self.sentencias)

    def resumen(self, cuantas=3):
        """Las sentencias que más se repiten: si hay un N+1, la primera lo delata."""
        from collections import Counter
        cuenta = Counter(" ".join(s.split())[:110] for s in self.sentencias)
        return cuenta.most_common(cuantas)


@pytest.fixture(scope="module")
def volumen(request):
    """
    Siembra el volumen una sola vez para todo el módulo.

    `scope="module"` va contra el fixture `clean_business_tables`, que vacía las tablas
    después de CADA prueba. Por eso se siembra dentro de cada medición a través de
    `con_volumen`, que comprueba si hace falta. Sembrar 5 300 filas siete veces por ruta
    multiplicaría por cien la duración de la suite sin medir nada nuevo.
    """
    return None


def _sembrar(db, asesor_id, campana_id):
    """300 prospectos, 5 000 actividades y 40 tareas abiertas."""
    ahora = datetime.datetime.now(datetime.timezone.utc)

    prospectos = []
    for i in range(PROSPECTOS):
        score = (i * 7919) % 1000 / 10.0  # repartidos por todo el rango, sin azar
        categoria = (
            ScoreCategory.HOT if score >= 75
            else ScoreCategory.WARM if score >= 45
            else ScoreCategory.COLD
        )
        prospectos.append(Lead(
            first_name=f"Nombre{i:03d}", last_name=f"Apellido{i:03d}",
            email=f"prospecto{i:03d}@volumen-de-pruebas.com",
            company=f"Empresa {i:03d}", job_title=CARGOS[i % len(CARGOS)],
            industry=SECTORES[i % len(SECTORES)], company_size=TAMANOS[i % len(TAMANOS)],
            source="LinkedIn Ads", country="México", city="CDMX",
            annual_revenue=None if i % 4 == 0 else 1_000_000.0 + i,
            current_score=score, score_category=categoria,
            status=LeadStatus.NEW if i % 3 else LeadStatus.CONTACTED,
            qualification_status=QualificationStatus.INCOMING,
            conversion_probability=score / 100.0,
            # La mitad con asesor y la mitad sin: la lista y la bandeja se comportan distinto
            # según el alcance de cartera de quien pregunta.
            assigned_rep_id=asesor_id if i % 2 == 0 else None,
            # Un tercio atribuidos a la publicación, que es lo que mide el informe.
            campaign_id=campana_id if i % 3 == 0 else None,
            last_score_update=ahora, last_activity_at=ahora,
            created_at=ahora - datetime.timedelta(days=i % 60),
            updated_at=ahora, raw_metadata={},
        ))
    db.add_all(prospectos)
    db.commit()

    identificadores = [p.id for p in prospectos]

    # Las actividades se reparten desigualmente a propósito: unos pocos prospectos concentran
    # muchas. Repartirlas a razón de dieciséis por cabeza mediría una ficha promedio y
    # ninguna cara, y el caso que hay que vigilar es justamente la ficha del prospecto más
    # trabajado de la cartera.
    actividades = []
    for n in range(ACTIVIDADES):
        # Distribución sesgada: el índice se eleva al cuadrado sobre el total, así que los
        # primeros prospectos se llevan la mayoría.
        posicion = int(((n / ACTIVIDADES) ** 2) * len(identificadores))
        actividades.append(LeadActivity(
            lead_id=identificadores[posicion],
            activity_type=TIPOS[n % len(TIPOS)],
            channel="Web", source="pipeline", verificada=False,
            activity_data={},
            occurred_at=ahora - datetime.timedelta(hours=n % 2000),
            created_at=ahora,
        ))
    db.add_all(actividades)
    db.commit()

    # Tareas abiertas para que la bandeja «Hoy» tenga trabajo que enseñar.
    db.add_all([
        Tarea(
            lead_id=identificadores[i], asesor_id=asesor_id,
            regla="primer_contacto", clave=f"v{i}", estado=ABIERTA,
            vence_el=ahora + datetime.timedelta(hours=2),
            motivo="Asignado y todavía sin contactar.", datos={},
            creada_en=ahora,
        )
        # Solo los pares: son los que tienen asesor.
        for i in range(0, 80, 2)
    ])
    db.commit()

    # El prospecto con MÁS actividades: es el que hace caro el detalle de la ficha.
    from collections import Counter
    por_prospecto = Counter(a.lead_id for a in actividades)
    el_mas_cargado, cuantas = por_prospecto.most_common(1)[0]
    return {
        "ids": identificadores,
        "mas_cargado": el_mas_cargado,
        "actividades_del_mas_cargado": cuantas,
    }


@pytest.fixture
def con_volumen(db_session):
    """
    La base con 300 prospectos, 5 000 actividades, 40 tareas y una publicación.

    El asesor y el líder de la suite existen ya; lo que se siembra aquí se cuelga de ellos.
    """
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    asesor = db_session.query(User).filter(User.email == email).one()

    campana = Campaign(
        name="Volumen · Talento TI", channel="LinkedIn", budget=0.0,
        description="Publicación con la que se mide el informe.",
    )
    db_session.add(campana)
    db_session.commit()
    db_session.refresh(campana)

    datos = _sembrar(db_session, asesor.id, campana.id)
    datos["asesor_id"] = asesor.id
    datos["campana_id"] = campana.id
    return datos


def medir(cliente, ruta, headers):
    """
    Mediana del tiempo de respuesta y número de consultas de una petición.

    El contador se enciende para UNA sola petición, la última: contarlas todas daría la suma
    de las siete y habría que dividir, y dividir un entero por siete produce un número que ya
    no es «cuántas consultas hace esta pantalla».
    """
    tiempos = []
    for _ in range(REPETICIONES):
        comienzo = time.perf_counter()
        respuesta = cliente.get(ruta, headers=headers)
        tiempos.append((time.perf_counter() - comienzo) * 1000)
        assert respuesta.status_code == 200, f"{ruta} respondió {respuesta.status_code}"

    with ContadorDeConsultas() as contador:
        respuesta = cliente.get(ruta, headers=headers)

    # Se descarta la primera medida, que lleva dentro el arranque y la compilación.
    return {
        "ms": statistics.median(tiempos[1:]),
        "min_ms": min(tiempos[1:]),
        "max_ms": max(tiempos[1:]),
        "consultas": len(contador),
        "resumen": contador.resumen(),
        "cuerpo": respuesta.json(),
    }


def informar(nombre, medida, tope_ms, tope_consultas):
    """Imprime la fila de la tabla y comprueba los dos topes."""
    print(
        f"\n  {nombre:<34} {medida['ms']:7.1f} ms  "
        f"(min {medida['min_ms']:.1f} / max {medida['max_ms']:.1f})  "
        f"{medida['consultas']:3d} consultas"
    )
    assert medida["consultas"] <= tope_consultas, (
        f"{nombre} hace {medida['consultas']} consultas y el tope es {tope_consultas}. "
        f"Las que más se repiten: {medida['resumen']}"
    )
    assert medida["ms"] < tope_ms, (
        f"{nombre} tardó {medida['ms']:.0f} ms y el tope es {tope_ms} ms"
    )


# ---------------------------------------------------------------------------
# Las cuatro pantallas
# ---------------------------------------------------------------------------

def test_el_volumen_es_el_que_dice_ser(client, con_volumen, admin_headers):
    """
    Antes de medir nada: comprobar que de verdad hay 300 y 5 000.

    Sin esto, un fallo del sembrado —una restricción que rechace filas en silencio, un
    `commit` que no se ejecute— dejaría todas las mediciones de abajo hechas sobre una base
    casi vacía, y las cuatro pasarían con tiempos excelentes sin haber medido nada.
    """
    respuesta = client.get("/api/v1/leads?limit=1", headers=admin_headers)
    assert respuesta.json()["total"] == PROSPECTOS

    detalle = client.get(
        f"/api/v1/leads/{con_volumen['mas_cargado']}", headers=admin_headers,
    ).json()
    assert len(detalle["activities"]) == con_volumen["actividades_del_mas_cargado"]
    # El sesgo de la distribución tiene que haber producido de verdad un prospecto cargado.
    assert con_volumen["actividades_del_mas_cargado"] > 100


def test_la_lista_de_prospectos(client, con_volumen, admin_headers):
    """
    Una página de 50 prospectos sobre una tabla de 300.

    El tope de consultas es lo que guarda la puerta: la lista devuelve el asesor de cada
    prospecto, y leerlo fila a fila —300 consultas en vez de dos— es el defecto clásico de un
    listado con relación. Aquí no ocurre, y este número es el que lo dice.
    """
    medida = medir(client, "/api/v1/leads?limit=50", admin_headers)
    assert len(medida["cuerpo"]["items"]) == 50
    informar("Lista de prospectos (50 de 300)", medida, tope_ms=600, tope_consultas=12)


def test_la_lista_filtrada_y_buscada(client, con_volumen, admin_headers):
    """
    La misma lista con filtro de categoría y búsqueda por texto.

    Es como la usa el líder: filtrar HOT y buscar una empresa. La búsqueda es un `LIKE` sin
    índice —lo correcto para 300 filas— y esto mide lo que cuesta.
    """
    medida = medir(
        client, "/api/v1/leads?score_category=HOT&search=Empresa%201&limit=50", admin_headers,
    )
    informar("Lista filtrada HOT + búsqueda", medida, tope_ms=600, tope_consultas=12)


def test_la_ficha_360_del_prospecto_mas_cargado(client, con_volumen, admin_headers):
    """
    La ficha del prospecto con más actividades de toda la base.

    Se mide el peor caso y no uno promedio: la ficha trae el historial **entero** de
    actividades, así que su coste crece con el prospecto más trabajado de la cartera, no con
    la media. Si algún día hay que paginar el historial, este número es el que lo dirá.
    """
    medida = medir(
        client, f"/api/v1/leads/{con_volumen['mas_cargado']}", admin_headers,
    )
    actividades = len(medida["cuerpo"]["activities"])
    print(f"\n  (la ficha medida trae {actividades} actividades)")
    informar("Ficha 360, el peor caso", medida, tope_ms=900, tope_consultas=12)


def test_la_bandeja_de_hoy(client, con_volumen, executive_headers):
    """
    La bandeja del asesor, con 40 tareas abiertas.

    Cada tarea enseña nombre, empresa, score y categoría del prospecto. Leer el prospecto
    tarea a tarea serían 40 consultas; el tope de abajo obliga a que no sea así.
    """
    medida = medir(client, "/api/v1/agenda/hoy", executive_headers)
    assert medida["cuerpo"]["para_hoy"] + medida["cuerpo"]["vencidas"] > 0
    informar("Bandeja «Hoy» (40 tareas)", medida, tope_ms=600, tope_consultas=12)


def test_el_informe_de_la_publicacion(client, con_volumen, admin_headers):
    """
    El informe de una publicación con 100 prospectos atribuidos.

    Es la pantalla que más agrega: tres números de resumen, la tabla y la serie por día.
    """
    medida = medir(
        client, f"/api/v1/publicaciones/{con_volumen['campana_id']}/informe", admin_headers,
    )
    assert medida["cuerpo"]["resumen"]["perfiles_recibidos"] == 100
    informar("Informe de publicación (100)", medida, tope_ms=900, tope_consultas=16)


def test_ninguna_pantalla_crece_con_el_numero_de_filas(client, con_volumen, admin_headers):
    """
    La comprobación que de verdad importa, y la única que no depende de la máquina.

    Pedir 10 prospectos y pedir 200 tiene que costar **el mismo número de consultas**. Si
    costara más, sería porque hay una consulta por fila, y entonces el panel funciona hoy con
    300 prospectos y deja de funcionar con 3 000 sin que nada cambie en el código.
    """
    with ContadorDeConsultas() as pocas:
        client.get("/api/v1/leads?limit=10", headers=admin_headers)
    with ContadorDeConsultas() as muchas:
        client.get("/api/v1/leads?limit=200", headers=admin_headers)

    print(f"\n  10 filas: {len(pocas)} consultas · 200 filas: {len(muchas)} consultas")
    assert len(pocas) == len(muchas), (
        f"Pedir 200 filas cuesta {len(muchas)} consultas y pedir 10 cuesta {len(pocas)}: "
        f"hay una consulta por fila. Las más repetidas: {muchas.resumen()}"
    )


def test_la_bandeja_no_crece_con_el_numero_de_tareas(client, db_session, executive_headers):
    """
    El defecto que esta suite encontró, escrito como propiedad y no como caso.

    Medir «cuarenta tareas cuestan cuarenta consultas» sirve para encontrarlo una vez. Lo que
    impide que vuelva es esto: **dos tareas y veinte tareas tienen que costar lo mismo**. Da
    igual el número que salga y da igual la máquina; si crece, hay una consulta por fila.

    No usa el fixture de volumen: no hace falta sembrar 5 300 filas para comparar dos
    tamaños, y así esta comprobación cuesta menos de un segundo y se puede leer entera.
    """
    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    asesor = db_session.query(User).filter(User.email == email).one()
    ahora = datetime.datetime.now(datetime.timezone.utc)

    def sembrar_tareas(cuantas, desde):
        prospectos = [
            Lead(
                first_name=f"P{i}", last_name=f"A{i}",
                email=f"crece{i}@volumen-de-pruebas.com", company=f"C{i}",
                current_score=50.0, score_category=ScoreCategory.WARM,
                status=LeadStatus.NEW, qualification_status=QualificationStatus.INCOMING,
                assigned_rep_id=asesor.id, created_at=ahora, updated_at=ahora,
                raw_metadata={},
            )
            for i in range(desde, desde + cuantas)
        ]
        db_session.add_all(prospectos)
        db_session.commit()
        db_session.add_all([
            Tarea(
                lead_id=p.id, asesor_id=asesor.id, regla="primer_contacto",
                clave=f"c{p.id}", estado=ABIERTA,
                vence_el=ahora + datetime.timedelta(hours=1),
                motivo="Asignado y todavía sin contactar.", datos={}, creada_en=ahora,
            )
            for p in prospectos
        ])
        db_session.commit()

    sembrar_tareas(2, 0)
    with ContadorDeConsultas() as con_dos:
        respuesta = client.get("/api/v1/agenda/hoy", headers=executive_headers)
    assert len(respuesta.json()["tareas"]) == 2

    sembrar_tareas(18, 100)
    with ContadorDeConsultas() as con_veinte:
        respuesta = client.get("/api/v1/agenda/hoy", headers=executive_headers)
    assert len(respuesta.json()["tareas"]) == 20

    assert len(con_dos) == len(con_veinte), (
        f"Con 2 tareas cuesta {len(con_dos)} consultas y con 20 cuesta {len(con_veinte)}: "
        f"se está leyendo el prospecto tarea a tarea. Las más repetidas: {con_veinte.resumen()}"
    )


def test_la_campana_tampoco_crece_con_el_numero_de_avisos(client, db_session, executive_headers):
    """
    La misma propiedad en la campana, que tenía el mismo defecto.

    Ahí el daño estaba acotado por `MAX_AVISOS` —treinta—, así que eran treinta consultas de
    más y no cuarenta. Se arregla igual porque es el mismo defecto, y la campana se dibuja en
    **todas** las pantallas del panel, no solo en una.
    """
    from app.models.entities import Aviso

    email, _ = TEST_ACCOUNTS["Commercial_Executive"]
    asesor = db_session.query(User).filter(User.email == email).one()
    ahora = datetime.datetime.now(datetime.timezone.utc)

    def sembrar_avisos(cuantos, desde):
        prospectos = [
            Lead(
                first_name=f"V{i}", last_name=f"B{i}",
                email=f"aviso{i}@volumen-de-pruebas.com", company=f"D{i}",
                current_score=80.0, score_category=ScoreCategory.HOT,
                status=LeadStatus.NEW, qualification_status=QualificationStatus.INCOMING,
                assigned_rep_id=asesor.id, created_at=ahora, updated_at=ahora,
                raw_metadata={},
            )
            for i in range(desde, desde + cuantos)
        ]
        db_session.add_all(prospectos)
        db_session.commit()
        db_session.add_all([
            Aviso(
                lead_id=p.id, usuario_id=asesor.id, regla="hot_sin_contacto",
                clave=f"a{p.id}", texto="Un prospecto HOT sigue sin contactar.",
                creado_en=ahora,
            )
            for p in prospectos
        ])
        db_session.commit()

    sembrar_avisos(2, 200)
    with ContadorDeConsultas() as con_dos:
        client.get("/api/v1/agenda/avisos", headers=executive_headers)

    sembrar_avisos(18, 300)
    with ContadorDeConsultas() as con_veinte:
        respuesta = client.get("/api/v1/agenda/avisos", headers=executive_headers)
    assert respuesta.json()["sin_leer"] == 20

    assert len(con_dos) == len(con_veinte), (
        f"Con 2 avisos cuesta {len(con_dos)} consultas y con 20 cuesta {len(con_veinte)}. "
        f"Las más repetidas: {con_veinte.resumen()}"
    )
