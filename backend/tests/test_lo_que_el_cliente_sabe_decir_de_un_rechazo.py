"""
Capítulo 45: los tipos de rechazo que el servidor puede contestar y el cliente sabe traducir.

El defecto
----------
El capítulo 40 escribió en el cliente una tabla que dice qué significa cada clase de error de
Pydantic —«Falta este campo», «Escriba un número entero»— y la indexó por el `type` del 422 y
no por su texto en inglés, que es la decisión correcta: el texto es de la biblioteca y cambia
entre versiones. La tabla la usan las cuatro pantallas que reparten su 422 por campos. La
función que ve **todas las demás**, `renglonesDelCuerpo` en `services/api.js`, no la tenía:
entregaba el `msg` de Pydantic tal cual, en inglés.

Medido en los dos formularios del panel que no reparten —el de actividad de la ficha 360 y el
de cierre—, **seis de nueve rechazos llegaban en inglés**: «Field required» al no elegir el
tipo de una actividad, «Input should be a valid datetime or date, input is too short» en la
fecha de una reunión, y la lista de las catorce claves del `enum` al mandar un tipo que no
existe. Cinco de los seis eran de un tipo que la tabla ya traducía.

Por qué esta prueba está en el servidor
---------------------------------------
Porque la lista de tipos la decide el servidor y solo él puede derivarla: sale de sus 17
esquemas de cuerpo, y esos salen de sus rutas. El cliente no puede saber qué le van a
contestar; lo único que puede hacer es tener una frase para cada cosa. Así que la tabla se
**lee** del archivo del cliente —como `test_publicaciones.py` lee la ruta pública de
`main.jsx`— y lo que se compara es cobertura.

Que un tipo nuevo nazca en rojo es lo que sostiene la otra mitad del arreglo: con la tabla
delante, un tipo que no esté en ella sale como «No se admite este valor», que no dice nada. Es
mejor que el inglés y peor que una frase, y la única forma de que el hueco no se llene en
silencio es que esta prueba exista.
"""
import pathlib
import re

import pydantic
import pytest
from app.main import app
from fastapi.routing import APIRoute

RECHAZOS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "frontend" / "src" / "services" / "rechazos.js"
)

# `value_error` es el de nuestros propios validadores: llega con el prefijo «Value error, » de
# Pydantic, y el cliente lo reconoce por ahí y enseña la frase tal cual, que está en
# castellano y dice más que cualquier entrada de la tabla. No necesita traducción; necesita
# que no se le ponga una por delante.
PROPIOS = {"value_error"}

# Lo que se le manda a cada campo para ver qué contesta. No es una lista de casos de negocio:
# es una lista de cosas que no son lo que el campo pide, para que el rechazo lo elija el
# esquema y no quien escribe la prueba.
RAROS = [{"x": 1}, [1], "x" * 6000, -1, "   "]


def _rutas(cosa, vistos=None):
    """
    Todas las rutas de la aplicación, incluidas las de los enrutadores incluidos.

    Hay que bajar por `original_router` porque esta versión de FastAPI envuelve cada
    `include_router` en un objeto que no es una ruta y no expone las suyas por `routes`.
    """
    vistos = vistos if vistos is not None else set()
    for r in getattr(cosa, "routes", []):
        if isinstance(r, APIRoute):
            yield r
        else:
            yield from _rutas(r, vistos)
            otro = getattr(r, "original_router", None)
            if otro is not None and id(otro) not in vistos:
                vistos.add(id(otro))
                yield from _rutas(otro, vistos)


def _esquemas_de_cuerpo():
    """
    Los esquemas que son cuerpo de una petición, por la función que atiende la puerta.

    La clave es la función y no `(método, ruta)`, y ese detalle costó un esquema: las rutas
    que un enrutador incluye llevan su camino **sin el prefijo**, así que `POST /leads` y
    `POST /campaigns` son las dos `POST ''`, y una pisaba a la otra. El recuento daba 15 en
    vez de 17 sin que nada fallara, que es el fallo que este capítulo entero estudia.
    """
    esquemas = {}
    for ruta in _rutas(app):
        for parametro in ruta.dependant.body_params:
            tipo = parametro.field_info.annotation
            if isinstance(tipo, type) and issubclass(tipo, pydantic.BaseModel):
                esquemas.setdefault(tipo.__name__, tipo)
    return esquemas


def _provocar():
    """
    Qué contesta cada esquema de cuerpo cuando se le manda algo que no es lo que pide.

    Devuelve dos cosas: los `type` de los 422, y los esquemas que levantaron **otra cosa**. La
    segunda no se descarta en silencio porque no es un detalle: un validador que levanta algo
    que Pydantic no sabe convertir en un error de validación no produce un 422, produce un
    **500**, y entonces no hay ningún renglón que traducir.
    """
    tipos = {}
    otra_cosa = {}
    for nombre, esquema in _esquemas_de_cuerpo().items():
        casos = [{}]
        for campo in esquema.model_fields:
            casos.extend({campo: raro} for raro in RAROS)
        for caso in casos:
            try:
                esquema.model_validate(caso)
            except pydantic.ValidationError as fallo:
                for item in fallo.errors():
                    tipos.setdefault(item["type"], set()).add(nombre)
            except Exception as fallo:  # noqa: BLE001 - se cuenta, no se traga
                otra_cosa.setdefault(nombre, set()).add(type(fallo).__name__)
    return tipos, otra_cosa


def _tipos_alcanzables():
    """Qué `type` de 422 puede contestar cada esquema de cuerpo, provocándolos."""
    return _provocar()[0]


def test_ningun_esquema_de_cuerpo_levanta_algo_que_no_sea_un_422():
    """
    Lo que se contaba al pasar, y sale gratis: ninguna de las 17 puertas revienta.

    Un validador que levanta un `KeyError` o un `TypeError` sobre un valor del cuerpo no
    contesta 422: contesta 500, se anota como fallo del servidor y en la pantalla sale «algo ha
    ido mal». Es el mismo síntoma que el capítulo 41 encontró en las tres ediciones parciales,
    por otro camino.
    """
    _, otra_cosa = _provocar()
    assert not otra_cosa, f"estas puertas no contestan un 422: {otra_cosa}"


def _tabla_del_cliente():
    """Las claves de `POR_TIPO`, leídas del archivo del cliente."""
    fuente = RECHAZOS.read_text(encoding="utf-8")
    bloque = fuente[fuente.index("export const POR_TIPO") :]
    bloque = bloque[: bloque.index("\n};")]
    return set(re.findall(r"^\s{2}([a-z_]+):", bloque, re.M))


def test_la_tabla_del_cliente_se_puede_leer():
    """
    Lo primero que esta prueba tiene que demostrar es que encontró la tabla.

    Si el archivo se renombra, si `POR_TIPO` deja de exportarse o si el formato de sus claves
    cambia, la expresión regular devuelve un conjunto vacío y **todas** las comprobaciones de
    cobertura pasarían: un conjunto vacío no contiene ningún tipo sin traducir porque no
    contiene nada. Es el modo de fallar de las guardas de los capítulos 43 y 44.
    """
    assert RECHAZOS.exists(), f"no está {RECHAZOS}"
    tabla = _tabla_del_cliente()
    assert len(tabla) >= 19, f"la tabla del cliente trae {len(tabla)} tipos; eran 24"
    assert "missing" in tabla and "enum" in tabla


def test_las_puertas_con_cuerpo_son_diecisiete():
    """
    Cuántos esquemas puede rechazar el servidor, derivado de las rutas.

    Prueba de fijación: la puerta número dieciocho aparece aquí, y con ella los tipos que
    sepa contestar. Y la cifra importa por sí misma —15 era el número que salía con las
    rutas mal desduplicadas—.
    """
    esquemas = _esquemas_de_cuerpo()
    assert len(esquemas) == 17, sorted(esquemas)
    assert "LeadCreate" in esquemas and "CampanaCreate" in esquemas


def test_todo_tipo_que_el_servidor_puede_contestar_tiene_frase_en_el_cliente():
    """
    El cruce: 19 tipos alcanzables, y una frase para cada uno.

    Antes del capítulo 45 la tabla cubría once. Los ocho que faltaban eran siete de la familia
    `*_type` —lo que llegó no es de la clase del campo— y uno de las fechas, y faltaban por un
    motivo con forma: la tabla se escribió mirando lo que un formulario rompe, y un formulario
    manda siempre una cadena. Lo que un cliente de la API rompe es otra lista.
    """
    tipos = _tipos_alcanzables()
    assert len(tipos) >= 19, f"solo se provocaron {len(tipos)} tipos; eran 19"
    tabla = _tabla_del_cliente()
    sin_frase = sorted(set(tipos) - tabla - PROPIOS)
    assert not sin_frase, (
        "el cliente no sabe qué decir de estos rechazos, y los enseñaría en inglés: "
        + ", ".join(f"{t} (p.ej. {sorted(tipos[t])[0]})" for t in sin_frase)
    )


def test_la_tabla_no_tiene_entradas_de_sobra_sin_motivo():
    """
    Lo contrario también se cuenta, y no se exige.

    Siete entradas de la tabla no las provoca ninguna de estas pruebas: unas porque el tipo
    sale de una restricción que hoy no tiene ningún campo de cuerpo —`url_parsing`,
    `string_pattern_mismatch`—, otras porque las provoca un `Literal` que solo está en una
    respuesta, y `campos_vacios_prohibidos` porque lo escribe un validador de modelo y esta
    prueba manda valores raros campo a campo. No sobran: lo que no se puede es confundir
    «nadie la ha provocado aquí» con «nadie la puede recibir». Se cuentan para que la
    diferencia esté a la vista.
    """
    de_sobra = sorted(_tabla_del_cliente() - set(_tipos_alcanzables()))
    assert de_sobra == [
        "campos_vacios_prohibidos",
        "datetime_parsing",
        "extra_forbidden",
        "less_than_equal",
        "literal_error",
        "string_pattern_mismatch",
        "url_parsing",
    ]


@pytest.mark.parametrize(
    "cuerpo,tipo",
    [
        ({"channel": "phone"}, "missing"),
        ({"activity_type": "CALL_MADE", "channel": "phone"}, "enum"),
        (
            {
                "activity_type": "MEETING_SCHEDULED",
                "channel": "phone",
                "inicio_de_la_reunion": "el martes",
            },
            "datetime_from_date_parsing",
        ),
    ],
)
def test_los_tres_rechazos_en_ingles_del_formulario_de_actividad(
    client, admin_headers, sample_lead, cuerpo, tipo
):
    """
    Los que se veían en inglés, pedidos por la puerta.

    Se comprueba el `type` que viaja y no el texto, porque el texto es el que va a cambiar: lo
    que esta prueba sostiene es que el cliente tiene con qué traducirlo. La frase está en su
    tabla y su propia suite comprueba que se usa.

    `datetime_from_date_parsing` es el que no estaba en la tabla, y la razón de que no
    estuviera se lee aquí: Pydantic tiene un nombre por cada dirección de la conversión
    —`date_from_datetime_parsing` cuando el campo es un día, este cuando es un instante— y la
    tabla tenía dos de los tres. La misma errata de teclado contestaba en castellano en la
    fecha de un cierre y en inglés en la de una reunión, en el mismo panel.
    """
    r = client.post(
        f"/api/v1/leads/{sample_lead.id}/activities",
        json=cuerpo,
        headers=admin_headers,
    )
    assert r.status_code == 422
    tipos = [item["type"] for item in r.json()["detail"]]
    assert tipo in tipos, tipos
    assert tipo in _tabla_del_cliente()
