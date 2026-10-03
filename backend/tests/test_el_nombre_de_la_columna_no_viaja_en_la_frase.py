"""
Capítulo 45: lo que un validador que no puede señalar un campo dice del campo.

El defecto
----------
`PUT /users/{id}` con `{"full_name": null}` respondía, en una frase en castellano:

    La cuenta no existe sin estos campos, así que no se pueden dejar vacíos: full_name.
    Envíe un valor, o no envíe el campo si no quiere cambiarlo.

`full_name` es el nombre de la columna de la base. Es lo que el capítulo 43 le quitó a
`parseApiError` del cliente —con su motivo escrito: «quitarlo y no traducirlo»— y lo quitó
**del prefijo**, que es donde una expresión regular lo alcanza. Dentro de la frase no lo
alcanza nada, y con `loc: ['body']` el cliente no puede repartir el renglón por campos: cae
en el aviso de arriba tal cual, con la columna dentro.

Por qué estaba ahí
------------------
Porque la regla estaba escrita y no se podía cumplir. `exigir_texto`, tres líneas más arriba
en el mismo archivo, la dice desde el capítulo 41: «el mensaje no dice qué campo es: lo dice
el `loc` del 422». Lo que nadie escribió es qué hacer **cuando no hay `loc`**. Un validador de
modelo ve el cuerpo entero y responde `loc: ['body']`, así que su autor hizo lo único que
quedaba —decirlo en el texto—, y las dos mitades no son evitables por separado.

El inventario del punto 46
--------------------------
§6.4 decía: «el cierre de un prospecto y el registro de una actividad… **los dos** validan con
`model_validator`». En los esquemas hay **cinco**, y los tres que el punto no contaba son los
de las ediciones parciales: nacieron en el capítulo 33, se repartieron en el 41 y son los
únicos cuyo mensaje escribía un nombre de columna. Es la tercera vez seguida —43 en la tabla
de pares de colores, 44 en la lista de pantallas de la auditoría— que una observación correcta
descansa sobre un inventario escrito a mano, y la tercera vez que el defecto sigue a la lista.

Por qué estas pruebas y no una por mensaje
------------------------------------------
Porque lo que falló no fue un mensaje, fueron los mensajes que nadie leyó: la suite entera
—1677 pruebas— pasa igual con la columna dentro de la frase y sin ella. Ninguna mira lo que
esas tres puertas contestan. Así que la lista de validadores **sale de Pydantic** —de los
decoradores que va a ejecutar, no de un `grep` sobre el código—, los campos que alcanzan cada
uno salen de cruzar el esquema con su tabla, y la prueba se comprueba a sí misma antes de
contestar que no falta nada: si encuentra menos de cinco validadores o menos de catorce campos
alcanzables, es que dejó de mirar donde miraba.
"""
import inspect
import pathlib
import re

import pytest
from app.core.texto import campos_sin_los_que_no_existe
from app.models import entities
from app.schemas.lead import LeadUpdate
from app.schemas.user import CampanaUpdate, UsuarioUpdate
from pydantic import BaseModel

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ESQUEMAS = pathlib.Path(__file__).resolve().parents[1] / "app" / "schemas"

# El tipo del rechazo de los tres validadores de las ediciones parciales. Un tipo y no una
# frase: es lo que el cliente mira, y es parte del contrato de la API.
TIPO = "campos_vacios_prohibidos"

# Las tres puertas y su tabla. Se escriben el esquema y el modelo; los campos no, que salen
# de cruzarlos.
PUERTAS = [
    ("LeadUpdate", LeadUpdate, entities.Lead),
    ("UsuarioUpdate", UsuarioUpdate, entities.User),
    ("CampanaUpdate", CampanaUpdate, entities.Campaign),
]


def _clases_de_los_esquemas():
    """Todas las clases de Pydantic de `app.schemas`, importando cada módulo."""
    import importlib

    clases = {}
    for ruta in sorted(ESQUEMAS.glob("*.py")):
        if ruta.name == "__init__.py":
            continue
        modulo = importlib.import_module(f"app.schemas.{ruta.stem}")
        for nombre, obj in vars(modulo).items():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj.__module__ == modulo.__name__
            ):
                clases[f"{ruta.stem}.{nombre}"] = obj
    return clases


def _validadores_de_modelo():
    """
    Los validadores de modelo que Pydantic va a ejecutar, por función y no por clase.

    Se le pregunta a Pydantic y no al texto del archivo, que es la diferencia entre contar lo
    que está escrito y contar lo que corre: `_CamposDePublicacion` declara el suyo una vez y
    lo heredan tres clases —el alta de una publicación incluida—, así que un recuento por
    clase daría siete donde hay cinco, y un `grep` por el decorador daría cinco sin ver que
    uno de ellos vigila tres entradas.
    """
    por_funcion = {}
    for nombre, clase in _clases_de_los_esquemas().items():
        for decorador in clase.__pydantic_decorators__.model_validators.values():
            funcion = decorador.func
            clave = f"{funcion.__module__}.{funcion.__qualname__}"
            por_funcion.setdefault(clave, {"funcion": funcion, "clases": []})
            por_funcion[clave]["clases"].append(nombre)
    return por_funcion


def _nombres_de_columna():
    """
    Todo nombre de columna de todas las tablas, que es lo que no puede salir en una frase.
    """
    nombres = set()
    for tabla in entities.Base.metadata.tables.values():
        nombres.update(columna.name for columna in tabla.columns)
    return nombres


def _campos_alcanzables(esquema, modelo):
    """Los campos que el esquema admite y la tabla no deja vacíos: los que llegan a la red."""
    return sorted(set(esquema.model_fields) & campos_sin_los_que_no_existe(modelo))


# Las columnas que además son una palabra del castellano o una palabra sola demasiado
# frecuente para buscarla dentro de una frase. Se nombran con su motivo, y el inventario de
# excepciones es lo único escrito a mano aquí.
COLUMNAS_QUE_SON_PALABRAS = {
    "id",  # «…del id» no existiría, pero aparece dentro de cualquier otra palabra
    "estado",  # castellano
    "motivo",  # castellano
    "notas",  # castellano
    "tramo",  # castellano
    "resultado",  # castellano
    "ingresos",  # castellano
    "necesidades",  # castellano
    "redes",  # castellano
    "cerrado_el",  # castellano
    "inicio_de_la_reunion",  # castellano
    "categoria_al_cierre",  # castellano
    "fecha",  # castellano
}


def _columnas_en(texto):
    """Qué nombres de columna aparecen en un texto, como palabra entera."""
    encontradas = set()
    for nombre in _nombres_de_columna() - COLUMNAS_QUE_SON_PALABRAS:
        if re.search(rf"\b{re.escape(nombre)}\b", texto):
            encontradas.add(nombre)
    return encontradas


# ============================================================================
# El inventario, derivado, y su propia comprobación
# ============================================================================


def test_los_validadores_de_modelo_de_los_esquemas_son_cinco():
    """
    La cifra que el punto 46 de §6.4 daba por dos.

    Es una prueba de fijación y el motivo de que el capítulo exista: el sexto validador de
    modelo que alguien escriba aparece aquí, y quien lo escriba tendrá que decidir qué dice su
    mensaje cuando no pueda señalar el campo, en vez de resolverlo escribiendo la columna.
    """
    validadores = _validadores_de_modelo()
    assert sorted(validadores) == [
        "app.schemas.activity.ActivityCreate._la_fecha_es_de_la_reunion",
        "app.schemas.desenlaces.CierreDelProspecto._comprobar",
        "app.schemas.lead.LeadUpdate._vaciar_solo_lo_que_la_ficha_admite_vaciar",
        "app.schemas.user.UsuarioUpdate._vaciar_solo_lo_que_la_cuenta_admite_vaciar",
        "app.schemas.user._CamposDePublicacion._vaciar_solo_lo_que_la_publicacion_admite_vaciar",
    ]


def test_el_validador_de_la_publicacion_corre_en_cuatro_clases_y_no_en_una():
    """
    Por qué el recuento se hace por función y no por clase.

    `_CamposDePublicacion` existe desde el capítulo 41 para que el alta y la edición de una
    publicación compartan las reglas, así que su validador lo heredan cuatro clases: la base
    donde se declara, la base de las campañas y las dos que son cuerpo de una petición. Contar
    por clase daría ocho validadores donde hay cinco; contar los decoradores escritos daría
    cinco sin ver que uno vigila dos puertas.

    En el alta no puede saltar —`name` y `channel` son obligatorios ahí y un `null` lo rechaza
    el campo antes, nombrándolo en su `loc`—, y eso es una consecuencia de cómo están
    declarados hoy, no una decisión: el día que alguien los haga opcionales en el alta, ese
    mensaje sale por una puerta más.
    """
    validadores = _validadores_de_modelo()
    publicacion = validadores[
        "app.schemas.user._CamposDePublicacion._vaciar_solo_lo_que_la_publicacion_admite_vaciar"
    ]
    assert sorted(publicacion["clases"]) == [
        "user.CampanaBase",
        "user.CampanaCreate",
        "user.CampanaUpdate",
        "user._CamposDePublicacion",
    ]
    # Y el recuento por clase, que es el que no sirve.
    por_clase = sum(len(d["clases"]) for d in validadores.values())
    assert (por_clase, len(validadores)) == (8, 5)


def test_los_tres_de_las_ediciones_parciales_son_los_que_usan_la_red_compartida():
    """
    Cuáles de los cinco son los del punto 46 y cuáles los que el punto no contaba.

    Se distingue por lo que el validador **usa** y no por su nombre: los tres que llaman a
    `vacios_prohibidos` son los que comprueban una lista de campos derivada de la tabla, y por
    eso son los únicos que tenían algo que nombrar.
    """
    con_la_red = sorted(
        clave
        for clave, dato in _validadores_de_modelo().items()
        if "vacios_prohibidos(" in inspect.getsource(dato["funcion"])
    )
    assert con_la_red == [
        "app.schemas.lead.LeadUpdate._vaciar_solo_lo_que_la_ficha_admite_vaciar",
        "app.schemas.user.UsuarioUpdate._vaciar_solo_lo_que_la_cuenta_admite_vaciar",
        "app.schemas.user._CamposDePublicacion._vaciar_solo_lo_que_la_publicacion_admite_vaciar",
    ]


def test_la_comprobacion_encontro_algo_y_de_un_tamano_plausible():
    """
    La guarda se comprueba a sí misma antes de contestar que no falta nada.

    Es la lección del capítulo 44, donde una comprobación correcta sobre una lista de ocho
    pantallas de dieciocho pasaba en verde: una lista que se quedó corta no se distingue de una
    completa mirando el verde. Aquí hay tres cifras que pueden quedarse a cero sin que ninguna
    afirmación falle —los validadores, los campos que los alcanzan y las columnas contra las
    que se comparan—, y las tres se exigen.
    """
    assert len(_validadores_de_modelo()) >= 5
    assert len(_nombres_de_columna()) > 100
    alcanzables = sum(len(_campos_alcanzables(e, m)) for _, e, m in PUERTAS)
    assert alcanzables >= 14, f"solo {alcanzables} campos alcanzan la red; eran quince"


# ============================================================================
# Lo que contesta cada puerta, pedido de verdad
# ============================================================================


@pytest.mark.parametrize("nombre,esquema,modelo", PUERTAS, ids=[p[0] for p in PUERTAS])
def test_ningun_campo_vaciado_saca_el_nombre_de_su_columna_en_la_frase(nombre, esquema, modelo):
    """
    Los quince campos, uno por uno, con el `null` que llega a la red.

    No se comprueba un mensaje: se comprueban todos los que esa puerta puede dar. Y se mira el
    `msg` que **viaja**, no el texto del `ValueError`, porque lo que la pantalla enseña es lo
    primero.
    """
    alcanzables = _campos_alcanzables(esquema, modelo)
    assert alcanzables, f"{nombre}: ningún campo alcanza la red"
    vistos = 0
    for campo in alcanzables:
        with pytest.raises(Exception) as fallo:
            esquema.model_validate({campo: None})
        errores = fallo.value.errors()
        delaRed = [e for e in errores if e["type"] == TIPO]
        if not delaRed:
            # Un campo con su propio validador se rechaza antes y **nombra el campo en el
            # `loc`**, que es mejor: `source` es el caso, y por eso no se exige que todos
            # lleguen aquí.
            assert all(list(e["loc"]) == [campo] for e in errores), (
                f"{nombre}.{campo}: rechazado sin red y sin campo: {errores}"
            )
            continue
        vistos += 1
        item = delaRed[0]
        assert campo in item["ctx"]["campos"], (
            f"{nombre}.{campo}: la red no lo nombra en el contexto: {item['ctx']}"
        )
        colado = _columnas_en(item["msg"])
        assert not colado, f"{nombre}.{campo}: la frase nombra columnas {sorted(colado)}"
    assert vistos, f"{nombre}: la red no saltó en ningún campo"


def test_la_frase_de_la_red_se_lee_sola_y_el_campo_viaja_aparte():
    """
    Las dos mitades de lo que ese mensaje mezclaba, cada una en su sitio.

    La frase no termina en dos puntos: se lee entera en el aviso de arriba de una pantalla que
    no reparta, y ahí no hay nada que la complete. Los campos van en `ctx`, que es dato y no
    prosa, y son **nombres del esquema**: `vacios_prohibidos` recorre `model_fields_set`, así
    que lo que vuelve es lo que el cliente envió. Esa es la razón de que se le puedan dar sin
    contarle la forma de la base.
    """
    with pytest.raises(Exception) as fallo:
        UsuarioUpdate.model_validate({"full_name": None, "role": None})
    item = fallo.value.errors()[0]
    assert item["type"] == TIPO
    assert list(item["loc"]) == []  # `['body']` cuando llega por una ruta de FastAPI
    assert item["ctx"]["campos"] == ["full_name", "role"]
    assert item["msg"] == (
        "La cuenta no existe sin alguno de los campos que llegaron vacíos. "
        "Envíe un valor, o no envíe el campo si no quiere cambiarlo."
    )
    assert not item["msg"].rstrip().endswith(":")


def test_la_peticion_de_verdad_contesta_lo_mismo_que_el_esquema(
    client, admin_headers, sample_lead
):
    """
    Lo mismo, por la puerta: 422, el tipo, el contexto y ni una columna en la frase.

    Por la puerta porque el `loc` solo lleva `body` cuando pasa por FastAPI, y porque el `ctx`
    tiene que sobrevivir a la serialización: una lista en el contexto de un error no tiene por
    qué llegar al cable, y si no llegara, el cliente no podría repartir nada.
    """
    r = client.put(
        f"/api/v1/leads/{sample_lead.id}",
        json={"last_name": None},
        headers=admin_headers,
    )
    assert r.status_code == 422
    item = r.json()["detail"][0]
    assert item["type"] == TIPO
    assert item["loc"] == ["body"]
    assert item["ctx"] == {"campos": ["last_name"]}
    assert "last_name" not in item["msg"]
    assert item["msg"].startswith("La ficha no existe sin alguno de los campos")


def test_los_otros_dos_validadores_tampoco_nombran_una_columna(
    client, admin_headers, sample_lead
):
    """
    Los dos que el punto 46 sí contaba, que nunca tuvieron el defecto.

    Nombran su campo **en castellano y entre comillas** —«inicio_de_la_reunion» es el único, y
    es el nombre que el propio formulario usa— o no lo nombran porque hablan del cuerpo entero.
    Se comprueban aquí para que la regla valga para los cinco y no para los tres que se
    tocaron: el que escriba el sexto encontrará esta prueba antes que el problema.
    """
    r = client.post(
        f"/api/v1/leads/{sample_lead.id}/activities",
        json={
            "activity_type": "PHONE_CALL",
            "channel": "phone",
            "inicio_de_la_reunion": "2099-01-01T10:00:00Z",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422
    frase = r.json()["detail"][0]["msg"]
    assert "solo tiene sentido en una reunión agendada" in frase
    # `inicio_de_la_reunion` es columna y aparece en la frase, entre comillas españolas: es
    # el nombre que el formulario de la ficha 360 tiene escrito al lado del campo.
    assert "«inicio_de_la_reunion»" in frase
    assert not _columnas_en(frase)
