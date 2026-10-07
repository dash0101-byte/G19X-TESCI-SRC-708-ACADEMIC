"""
Lo que el embudo del registro de actividad rechaza, y con qué motivo.

`registrar_evento()` es el único camino por el que algo llega a `lead_activities`: el panel,
el cambio de etapa, el webhook del CRM y los cuatro conectores construyen un `Evento` y lo
entregan ahí. `validar_evento()` es su puerta, y lo que decide no es si algo se guarda bien
sino qué se devuelve a quien lo manda: un 422 con el campo y el motivo.

La suite probaba lo que entra. De los catorce rechazos escritos en esa función no se
ejercitaba casi ninguno, y un rechazo sin probar falla hacia el lado peor: deja pasar. Un
tipo que la fuente no registra, una fecha en el futuro, un identificador externo de una
fuente que no lo tiene, unas notas que manda una integración —las notas son del asesor— o
unos ingresos negativos entran en la tabla y de ahí al score, que es lo que se enseña.

Se comprueba el campo además del motivo porque el campo es lo que el cliente usa para
pintar el error junto al dato equivocado: un motivo correcto con el campo de otro manda al
usuario a mirar donde no es.
"""
import datetime

import pytest
from app.models.entities import ActivityType, utc_now
from app.services.registro_de_actividad import (
    MAX_CANAL,
    MAX_IDENTIFICADOR_EXTERNO,
    MAX_NOTAS,
    Contacto,
    Evento,
    EventoInvalido,
    nombres_de_fuentes,
    validar_evento,
)


def _manual(**cambios) -> Evento:
    """Un evento válido de registro manual, al que cada caso le estropea una cosa."""
    base = {
        "fuente": "manual",
        "tipo": ActivityType.EMAIL_OPEN,
        "contacto": Contacto(email="ana@ejemplo.mx"),
    }
    base.update(cambios)
    return Evento(**base)


def _externo(**cambios) -> Evento:
    """Lo mismo para una fuente que trae identificador y fecha propios."""
    base = {
        "fuente": "crm",
        "tipo": ActivityType.EMAIL_OPEN,
        "ocurrido_en": utc_now() - datetime.timedelta(minutes=1),
        "identificador_externo": "evt-1",
        "contacto": Contacto(email="ana@ejemplo.mx"),
    }
    base.update(cambios)
    return Evento(**base)


RECHAZOS = [
    (
        "una fuente que no existe",
        _manual(fuente="telepatia"),
        "source",
        "Fuente desconocida",
    ),
    (
        "un tipo que esa fuente no registra",
        Evento(
            fuente="calendly",
            tipo=ActivityType.PHONE_CALL,
            ocurrido_en=utc_now() - datetime.timedelta(minutes=1),
            identificador_externo="evt-2",
        ),
        "activity_type",
        "no registra actividades de tipo",
    ),
    (
        "un resultado de llamada en algo que no es una llamada",
        _manual(resultado_de_llamada="CONECTO"),
        "call_outcome",
        "solo se registra en las llamadas",
    ),
    (
        "un resultado de llamada que no está en la lista",
        _manual(tipo=ActivityType.PHONE_CALL, resultado_de_llamada="QUIZA"),
        "call_outcome",
        "desconocido",
    ),
    (
        "una dirección en algo que no es un mensaje",
        _manual(direccion="ENTRANTE"),
        "direction",
        "solo se registra en los mensajes",
    ),
    (
        "una fuente externa sin su identificador",
        _externo(identificador_externo=None),
        "external_event_id",
        "necesitan el identificador",
    ),
    (
        "un registro manual con identificador externo",
        _manual(identificador_externo="evt-9"),
        "external_event_id",
        "no lleva identificador externo",
    ),
    (
        "un identificador externo más largo que su columna",
        _externo(identificador_externo="e" * (MAX_IDENTIFICADOR_EXTERNO + 1)),
        "external_event_id",
        f"excede {MAX_IDENTIFICADOR_EXTERNO}",
    ),
    (
        "una fuente externa sin la fecha en que ocurrió",
        _externo(ocurrido_en=None),
        "occurred_at",
        "necesitan la fecha",
    ),
    (
        "una fecha por delante del reloj",
        _manual(ocurrido_en=utc_now() + datetime.timedelta(hours=1)),
        "occurred_at",
        "futuro",
    ),
    (
        "un canal más largo que su columna",
        _manual(canal="c" * (MAX_CANAL + 1)),
        "channel",
        f"canal excede {MAX_CANAL}",
    ),
    (
        "notas que manda una integración",
        _externo(notas="Llamé y quedó en pensarlo."),
        "notes",
        "Las notas son del asesor",
    ),
    (
        "notas más largas que su columna",
        _manual(notas="n" * (MAX_NOTAS + 1)),
        "notes",
        f"exceden {MAX_NOTAS}",
    ),
    (
        "una campaña que no es un identificador",
        _manual(campana_id=0),
        "campaign_id",
        "identificador válido",
    ),
    (
        "una campaña escrita como texto",
        _manual(campana_id="3"),
        "campaign_id",
        "identificador válido",
    ),
    (
        "una campaña que es un booleano",
        _manual(campana_id=True),
        "campaign_id",
        "identificador válido",
    ),
    (
        "un atributo del prospecto más largo que su columna",
        _manual(prospecto={"first_name": "a" * 101}),
        "first_name",
        "excede el máximo",
    ),
    (
        "un teléfono del prospecto que no es un teléfono",
        _manual(prospecto={"phone": "123"}),
        "phone",
        "número",
    ),
    (
        "unos ingresos que no son un número",
        _manual(prospecto={"annual_revenue": "muchos"}),
        "annual_revenue",
        "tiene que ser un número",
    ),
    (
        "unos ingresos negativos",
        _manual(prospecto={"annual_revenue": -1}),
        "annual_revenue",
        "no puede ser negativo",
    ),
]


@pytest.mark.parametrize(
    "evento, campo, fragmento",
    [caso[1:] for caso in RECHAZOS],
    ids=[caso[0] for caso in RECHAZOS],
)
def test_el_registro_rechaza_con_el_campo_y_el_motivo(evento, campo, fragmento):
    """Veinte formas de mandar algo que no se puede registrar, y lo que se contesta a cada una."""
    with pytest.raises(EventoInvalido) as fallo:
        validar_evento(evento)

    assert fallo.value.campo == campo
    assert fragmento in fallo.value.motivo
    # El detalle es lo que el endpoint entrega tal cual en el 422.
    assert fallo.value.como_detalle() == {"motivo": fallo.value.motivo, "campo": campo}


def test_el_texto_de_un_mensaje_se_retira_tambien_dentro_de_una_lista():
    """
    La minimización baja por los diccionarios y también por las listas.

    Lo que llega de un conector no tiene una forma fija: Calendly manda sus preguntas y
    respuestas como una lista de objetos, y ahí dentro va escrito lo que la persona
    respondió. Si la retirada de contenido solo recorriera diccionarios, ese texto llegaría
    a la columna de datos de la actividad —y de ahí a cualquier exportación— sin que nada
    fallara: la fila se escribe igual de bien con el texto dentro.
    """
    validado = validar_evento(
        _manual(
            datos={
                "adjuntos": [
                    {"nombre": "propuesta.pdf", "text": "no debería guardarse"},
                    {"nombre": "acta.pdf", "mensaje": "tampoco esto"},
                ],
                "origen": "panel",
            }
        )
    )

    assert validado.datos["origen"] == "panel"
    assert [a["nombre"] for a in validado.datos["adjuntos"]] == ["propuesta.pdf", "acta.pdf"]
    assert "no debería guardarse" not in str(validado.datos)
    assert "tampoco esto" not in str(validado.datos)


def test_las_etiquetas_de_las_fuentes_salen_solo_para_las_que_existen():
    """
    Lo que la API devuelve para pintar el nombre de la fuente en la ficha.

    El filtro no es decoración: los nombres llegan de las filas ya escritas, y una fila
    vieja puede nombrar una fuente que ya no está en la tabla. Sin él, pedir el historial
    de ese prospecto revienta con un KeyError en vez de enseñar el historial.
    """
    assert nombres_de_fuentes(["crm", "pagina_de_interes"]) == {
        "crm": "CRM",
        "pagina_de_interes": "Página de interés",
    }
    assert nombres_de_fuentes(["crm", "una_fuente_retirada"]) == {"crm": "CRM"}
    assert nombres_de_fuentes([]) == {}


def test_unos_ingresos_validos_entran_normalizados_a_numero():
    """
    La otra salida de la comprobacion de ingresos, y la que recorre el camino bueno.

    Llegan como texto desde un formulario y como numero desde el CRM; el modelo los lee
    como una variable continua, asi que lo que se guarda tiene que ser un `float` en los dos
    casos. Un «500000» guardado como cadena no lo detecta ninguna pantalla: el score sale
    igual, calculado sobre un dato que el preprocesador trata como categoria desconocida.
    """
    desde_un_formulario = validar_evento(_manual(prospecto={"annual_revenue": "500000"}))
    desde_una_integracion = validar_evento(_manual(prospecto={"annual_revenue": 500000}))

    for validado in (desde_un_formulario, desde_una_integracion):
        assert validado.prospecto["annual_revenue"] == 500000.0
        assert isinstance(validado.prospecto["annual_revenue"], float)
