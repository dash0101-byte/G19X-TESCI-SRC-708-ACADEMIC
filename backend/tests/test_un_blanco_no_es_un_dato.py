"""
Capítulo 41: un blanco no es un dato, y el mínimo tiene que medir lo que se guarda.

El defecto
----------
`UsuarioCreate.full_name` declaraba `min_length=2` y recortaba en un `field_validator`. En
ese orden —y es el orden que Pydantic impone: las restricciones del campo se aplican a lo que
llega, el validador corre después— el mínimo mide una cadena y la base recibe otra. Dos
espacios pasaban el mínimo de dos caracteres y se guardaban como `''`; `' A '` se guardaba
como una letra. La columna es `NOT NULL` porque una cuenta sin nombre no identifica a nadie.

Lo mismo, sin recorte ninguno, en el alta de una ficha: `first_name='   '` entraba tal cual
en otra columna `NOT NULL`, y los otros nueve campos de texto del alta guardaban el blanco
que la **edición** normalizaba desde el capítulo 33. La misma ficha decía dos cosas distintas
en la base según por qué puerta hubiera entrado.

Lo que se midió antes de tocar nada: de los 61 campos de texto de las entradas, **34
guardaban el blanco**, 15 lo normalizaban y 12 lo rechazaban. Los 12 eran el formulario
público y tres listas cerradas, y el formulario público lo rechazaba con una línea de
configuración —`str_strip_whitespace=True`— que no tenía ninguna otra entrada del sistema. El
arreglo llevaba siete capítulos escrito en una sola puerta.

Por qué esta prueba y no una por campo
---------------------------------------
Porque el fallo no es de un campo, es de los campos que nadie miró. Una prueba por campo
habría cubierto los diez del alta y habría dejado fuera el siguiente que alguien añadiera, que
es exactamente lo que pasó entre el 33 y el 41: el 33 escribió la regla para la edición, dejó
dicho en su propio docstring que el alta quedaba sin hacer, y el alta siguió sin hacerse
mientras se añadían campos.

Así que la lista **sale del código** —de las rutas, igual que `tokens.test.js` y
`colores.test.js` sacan la suya de los fuentes del cliente— y lo que está escrito a mano es
solo el inventario de excepciones, cada una con su motivo. Un cuerpo de petición nuevo nace en
rojo: o normaliza el blanco, o alguien escribe por qué no.
"""
import inspect
import re
from pathlib import Path

import pytest
from app.core.texto import ENTRADA_DE_TEXTO, columnas_de_texto, en_blanco
from app.main import app
from app.models.entities import Campaign, Lead, User
from app.schemas.lead import TEXTOS_QUE_ADMITEN_VACIO, LeadUpdate
from app.schemas.user import UsuarioCreate
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError

BLANCO = "   "

# ==============================================================================
# De dónde sale la lista de entradas
# ==============================================================================

ENDPOINTS = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints"

# Un esquema de cuerpo que no aparece en la firma del endpoint porque el endpoint lo valida a
# mano. Se busca por **uso** y no por nombre (la lección del capítulo 40): lo que se localiza
# es la llamada `X.model_validate(` sobre el cuerpo de la petición, que es lo que de verdad
# convierte un cuerpo en un esquema. Hoy encuentra uno, `CRMWebhookPayload`: el webhook del CRM
# toma el cuerpo en crudo porque el HMAC se calcula sobre los bytes exactos del emisor, así que
# Pydantic no puede haberlo tocado antes de comprobar la firma.
#
# El argumento tiene que venir del cuerpo, y eso también se mira: `model_validate` se usa
# cuatro veces más en los endpoints para construir **respuestas** a partir de un objeto de la
# base, y una entrada que en realidad es una salida metería en esta prueba esquemas que nadie
# puede enviar.
_VALIDACION_A_MANO = re.compile(
    r"\b([A-Z][A-Za-z0-9]*)\.model_validate\([^)]*(?:raw_body|body|cuerpo)"
)


def _rutas(rutas):
    """Las rutas de verdad, atravesando los enrutadores incluidos."""
    for ruta in rutas:
        original = getattr(ruta, "original_router", None)
        if original is not None:
            yield from _rutas(original.routes)
        elif getattr(ruta, "routes", None):
            yield from _rutas(ruta.routes)
        else:
            yield ruta


def _de_las_firmas():
    encontrados = {}
    for ruta in _rutas(app.routes):
        if not isinstance(ruta, APIRoute):
            continue
        for parametro in ruta.dependant.body_params:
            anotacion = parametro.field_info.annotation
            candidatos = [anotacion, *getattr(anotacion, "__args__", ())]
            for candidato in candidatos:
                if inspect.isclass(candidato) and issubclass(candidato, BaseModel):
                    encontrados[candidato.__name__] = candidato
                    break
    return encontrados


def _de_la_validacion_a_mano():
    import app.schemas as paquete

    modulos = {}
    for nombre in dir(paquete):
        objeto = getattr(paquete, nombre)
        if inspect.isclass(objeto) and issubclass(objeto, BaseModel):
            modulos[nombre] = objeto

    encontrados = {}
    for fuente in ENDPOINTS.glob("*.py"):
        for nombre in _VALIDACION_A_MANO.findall(fuente.read_text(encoding="utf-8")):
            if nombre in modulos:
                encontrados[nombre] = modulos[nombre]
    return encontrados


def esquemas_de_entrada():
    """Todo cuerpo de petición de la API, por las dos vías por las que puede llegar."""
    encontrados = dict(_de_las_firmas())
    encontrados.update(_de_la_validacion_a_mano())
    return encontrados


# ==============================================================================
# Un cuerpo válido por entrada, para poder dejar un solo campo en blanco
# ==============================================================================
#
# Esto sí está escrito a mano, y no puede no estarlo: un cuerpo válido depende de qué significa
# cada campo. Lo que no está escrito a mano es la **lista**, y hay una prueba que exige que
# esta tabla cubra todas las entradas que las rutas declaran. Una entrada nueva sin cuerpo de
# ejemplo pone la prueba en rojo con su nombre, que es el momento en que alguien está mirando.
CLAVE_LARGA = "Mu3y-L4rga-Clave!x"

CUERPOS = {
    "ActivityCreate": {"activity_type": "EMAIL_OPEN"},
    "CRMWebhookPayload": {"data": {"email": "ana@example.com"}},
    "CambiarContrasenaPropia": {"contrasena_actual": CLAVE_LARGA, "nueva_contrasena": CLAVE_LARGA},
    "CampanaCreate": {"name": "Vacantes de TI", "channel": "LinkedIn"},
    "CampanaUpdate": {},
    "CierreDelProspecto": {
        "resultado": "ganado",
        "motivo": "precio",
        "cerrado_el": "2026-09-01",
        "tramo": "hasta_100k",
    },
    "CodigoDelSegundoFactor": {"codigo": "123456"},
    "LeadCreate": {"first_name": "Ana", "last_name": "Pérez", "email": "ana@example.com"},
    "LeadUpdate": {},
    "LoginRequest": {"email": "ana@example.com", "password": CLAVE_LARGA},
    "RecalculationJobRequest": {},
    "RepartoDeCartera": {"destino_id": 1},
    "RestablecerContrasena": {"nueva_contrasena": CLAVE_LARGA},
    "ScorePredictRequest": {"job_title": "CTO", "industry": "FinTech"},
    "SegundoFactorDelLogin": {"desafio": "un-desafio", "codigo": "123456"},
    "SolicitudDeInteres": {
        "nombre": "Ana Pérez",
        "correo": "ana@example.com",
        "empresa": "ACME",
        "cargo": "CTO",
        "sector": "FinTech",
        "tamano_de_empresa": "11-50",
        "necesidad": "contratar",
        "aviso_de_privacidad": True,
    },
    "UsuarioCreate": {
        "email": "ana@example.com",
        "full_name": "Ana Pérez",
        "role": "Commercial_Executive",
        "password": CLAVE_LARGA,
    },
    "UsuarioUpdate": {},
    "VinculacionRequest": {"lead_id": 1},
}

# ==============================================================================
# Lo que puede quedarse con un blanco, y por qué
# ==============================================================================
#
# Cada excepción lleva su motivo escrito, como el inventario de colores del capítulo 40. Sin el
# motivo, un inventario es una lista de cosas que alguien decidió no mirar.
ACEPTADOS = {
    ("UsuarioCreate", "password"): (
        "Una contraseña no se recorta: un espacio en los bordes es parte del secreto, y "
        "recortarla vaciaría de sentido la regla de la política que rechaza exactamente eso. "
        "Aquí no hay mínimo declarado a propósito —lo explica MAX_PASSWORD_LENGTH en "
        "app.schemas.user—, así que la que contesta es la política, con la lista entera de "
        "motivos en vez de un 422 de longitud. Una contraseña de espacios se rechaza allí."
    ),
    ("RestablecerContrasena", "nueva_contrasena"): "Igual que la del alta, y por la misma política.",
    ("CambiarContrasenaPropia", "contrasena_actual"): (
        "Es la contraseña que esa persona ya tiene: no se recorta, y si está en blanco no "
        "coincide con ninguna, que es la respuesta correcta y la misma que para cualquier otra "
        "contraseña equivocada."
    ),
    ("CambiarContrasenaPropia", "nueva_contrasena"): "Igual que la del alta, y por la misma política.",
    ("SolicitudDeInteres", "sitio_web"): (
        "Es el campo trampa del formulario público, oculto en la página: lo que importa es si "
        "viene relleno, y `es_robot` ya lo mira con un `strip`. No es un dato que se guarde."
    ),
    ("SegundoFactorDelLogin", "codigo"): (
        "No tiene mínimo a propósito —un TOTP son 6 dígitos y uno de recuperación 12 "
        "caracteres—, y un código vacío es un código incorrecto: la respuesta es la misma que "
        "para cualquier otro, y distinguirla diría si el formato era plausible."
    ),
    ("SegundoFactorDelLogin", "desafio"): (
        "Un desafío vacío no existe en la tabla de desafíos, así que se rechaza al buscarlo. "
        "Decirlo aquí antes sería una respuesta distinta para un desafío inválido y para uno "
        "caducado."
    ),
    ("CodigoDelSegundoFactor", "codigo"): "Igual que el del login.",
    ("ActivityCreate", "channel"): (
        "No llega a una columna desde el esquema: pasa por `registrar_evento`, que desde el "
        "capítulo 24 hace `(evento.canal or '').strip() or CANAL_POR_TIPO[tipo]`. Ese es el "
        "borde común del panel, del webhook y de las dos integraciones, así que la regla está "
        "más compartida ahí que aquí. Se comprobó quitando el validador que sí se escribió "
        "primero: ninguna prueba se puso roja, porque no hacía nada."
    ),
    ("ActivityCreate", "notes"): (
        "Lo mismo, con `(evento.notas or '').strip() or None` en la misma función."
    ),
    # Una excepción de esquema entero, con `*`, y es la única que lo necesita.
    ("ScorePredictRequest", "*"): (
        "El simulador no escribe en ninguna columna: `predict_standalone` puntúa y contesta, "
        "y por eso la regla no le aplica —lo que esta prueba evita es que la base tenga dos "
        "formas de decir lo mismo, y aquí no hay base—. Un firmográfico en blanco es un "
        "firmográfico desconocido, que es lo que `_desconocido` ya lee en `scoring_rules`, "
        "así que el recorte basta y anular sobraría. Y `industry` es entrada libre en la "
        "pantalla: rechazar su blanco impediría probar justo el caso que el capítulo 25 vino "
        "a arreglar, un prospecto sin industria declarada."
    ),
}


# ==============================================================================
# 1. La lista de entradas está completa
# ==============================================================================

def test_hay_un_cuerpo_de_ejemplo_para_cada_entrada():
    """
    La mitad que impide que esta prueba se quede atrás.

    Las entradas se descubren recorriendo las rutas; los cuerpos de ejemplo están escritos. Si
    alguien añade un endpoint con un cuerpo nuevo, esto se pone rojo con su nombre antes de que
    nadie haya tenido que acordarse de esta prueba.
    """
    encontradas = set(esquemas_de_entrada())
    assert encontradas, "no se ha encontrado ningún cuerpo de petición: el recorrido de rutas falla"

    sin_ejemplo = sorted(encontradas - set(CUERPOS))
    assert not sin_ejemplo, (
        "entradas nuevas sin cuerpo de ejemplo en CUERPOS: " + ", ".join(sin_ejemplo)
    )

    sobran = sorted(set(CUERPOS) - encontradas)
    assert not sobran, "CUERPOS tiene entradas que ya no existen: " + ", ".join(sobran)


def test_el_webhook_del_crm_entra_por_la_segunda_via():
    """
    La vía que una lista escrita a mano habría olvidado.

    `CRMWebhookPayload` no está en la firma de su endpoint: el webhook lee el cuerpo en crudo
    para comprobar el HMAC sobre los bytes exactos del emisor, y lo valida después. Es la
    entrada con menos vigilancia humana del sistema —nadie mira lo que manda un CRM— y es la
    que se habría quedado fuera.
    """
    assert "CRMWebhookPayload" in _de_la_validacion_a_mano()
    assert "CRMWebhookPayload" not in _de_las_firmas()


# ==============================================================================
# 2. Toda entrada con texto recorta antes de medir
# ==============================================================================

def _campos_de_texto(esquema):
    for nombre, info in esquema.model_fields.items():
        anotacion = info.annotation
        if anotacion is str or str in getattr(anotacion, "__args__", ()):
            yield nombre, info


@pytest.mark.parametrize("nombre", sorted(CUERPOS))
def test_toda_entrada_con_texto_recorta_antes_de_medir(nombre):
    """
    `str_strip_whitespace=True` en la configuración, que es la única forma que ocurre antes.

    Se comprueba la configuración y no «que haya un recorte» porque un recorte en un validador
    es precisamente el defecto: existe, parece lo mismo, y corre después de la comprobación que
    debería proteger.
    """
    esquema = esquemas_de_entrada()[nombre]
    if not list(_campos_de_texto(esquema)):
        return
    assert esquema.model_config.get("str_strip_whitespace") is True, (
        f"{nombre} tiene campos de texto y no recorta antes de medir; "
        "la configuración está en app.core.texto.ENTRADA_DE_TEXTO"
    )


def test_el_recorte_de_la_configuracion_ocurre_antes_del_minimo():
    """
    El mecanismo, comprobado sobre el campo donde vivía el defecto.

    Si el recorte volviera a un validador, estas tres líneas seguirían pasando por sí solas y
    esta no: `'  '` volvería a cumplir un mínimo de dos y a guardarse vacío.
    """
    with pytest.raises(ValidationError) as error:
        UsuarioCreate(
            email="ana@example.com", full_name="  ", role="Commercial_Executive",
            password=CLAVE_LARGA,
        )
    assert error.value.errors()[0]["type"] == "string_too_short"

    # Y una letra entre espacios tampoco: el mínimo mide la letra, no los espacios.
    with pytest.raises(ValidationError):
        UsuarioCreate(
            email="ana@example.com", full_name=" A ", role="Commercial_Executive",
            password=CLAVE_LARGA,
        )

    cuenta = UsuarioCreate(
        email="ana@example.com", full_name="  Ana Pérez  ", role="Commercial_Executive",
        password=CLAVE_LARGA,
    )
    assert cuenta.full_name == "Ana Pérez"


def test_la_contrasena_es_la_excepcion_y_no_se_recorta():
    """
    Lo que el recorte general **no** puede alcanzar.

    Si lo alcanzara, la regla de la política que prohíbe una contraseña con espacios en los
    bordes —porque «se pierden al copiarla y luego no coincide»— no tendría nunca nada que
    rechazar: llegaría ya recortada y aprobaría en silencio lo que dice prohibir.
    """
    cuenta = UsuarioCreate(
        email="ana@example.com", full_name="Ana Pérez", role="Commercial_Executive",
        password="  " + CLAVE_LARGA + "  ",
    )
    assert cuenta.password == "  " + CLAVE_LARGA + "  "


# ==============================================================================
# 3. Ningún campo de texto guarda un blanco sin estar inventariado
# ==============================================================================

def _resultado_del_blanco(esquema, nombre_del_esquema, campo):
    """Qué hace una entrada con un blanco en uno de sus campos: lo rechaza, lo anula o lo guarda."""
    cuerpo = dict(CUERPOS[nombre_del_esquema])
    cuerpo[campo] = BLANCO
    try:
        instancia = esquema(**cuerpo)
    except ValidationError as error:
        propios = [e for e in error.errors() if e["loc"] and e["loc"][0] == campo]
        if propios:
            return "rechaza"
        # Un error de modelo también cuenta como rechazo, pero no es tan bueno: no lleva el
        # campo, así que la pantalla no puede ponerlo rojo (capítulo 40).
        return "rechaza el cuerpo"
    valor = getattr(instancia, campo, None)
    return "anula" if valor is None else ("guarda" if en_blanco(valor) else "cambia")


def test_ningun_campo_de_texto_guarda_un_blanco():
    """
    El barrido. Es la prueba que el capítulo 41 existe para escribir.

    Un blanco puede acabar en tres sitios y dos son correctos: rechazado con un 422 que nombra
    el campo —cuando hay alguien delante que puede corregirlo— o convertido en `None` —cuando
    la columna admite vacío y vacío es lo que hay—. El tercero, guardarlo tal cual, es el
    defecto: deja en la base dos formas de decir lo mismo y un `NOT NULL` cumplido por una
    cadena de espacios.
    """
    guardan = []
    for nombre, esquema in sorted(esquemas_de_entrada().items()):
        if (nombre, "*") in ACEPTADOS:
            continue
        for campo, _info in _campos_de_texto(esquema):
            if (nombre, campo) in ACEPTADOS:
                continue
            if _resultado_del_blanco(esquema, nombre, campo) == "guarda":
                guardan.append(f"{nombre}.{campo}")
    assert not guardan, (
        "guardan un blanco tal cual y no están inventariados: " + ", ".join(guardan)
    )


def test_el_inventario_no_tiene_entradas_de_sobra():
    """
    Un inventario que no caduca.

    Si un campo inventariado deja de guardar el blanco —porque alguien lo arregló, o porque el
    campo desapareció—, su excepción sobra, y una excepción que sobra es una vigilancia apagada
    que nadie recuerda haber apagado. Es la misma comprobación que el inventario de colores del
    capítulo 40 lleva para los suyos.
    """
    entradas = esquemas_de_entrada()
    inservibles = []
    for (nombre, campo), motivo in sorted(ACEPTADOS.items()):
        assert motivo.strip(), f"{nombre}.{campo} está inventariado sin motivo"
        esquema = entradas.get(nombre)
        if esquema is None:
            inservibles.append(f"{nombre} (ya no es una entrada)")
            continue
        if campo == "*":
            # La excepción de esquema entero caduca si el esquema deja de tener texto: ya no
            # hay nada que eximir, y la línea se quedaría ahí pareciendo que sí.
            if not list(_campos_de_texto(esquema)):
                inservibles.append(f"{nombre}.* (ya no tiene campos de texto)")
            continue
        if campo not in esquema.model_fields:
            inservibles.append(f"{nombre}.{campo} (ya no existe)")
            continue
        if _resultado_del_blanco(esquema, nombre, campo) != "guarda":
            inservibles.append(f"{nombre}.{campo} (ya no guarda el blanco)")
    assert not inservibles, "sobran en ACEPTADOS: " + ", ".join(inservibles)


def test_los_blancos_admitidos_son_contrasenas_y_tres_casos_nombrados():
    """
    El tamaño del inventario, para que crecer tenga que ser una decisión.

    Cuatro contraseñas, el campo trampa, los tres valores del segundo factor, los dos de una
    actividad y el simulador. Nada más, y nada que se guarde en una columna **desde aquí**: es
    la diferencia entre «este texto no se normaliza» y «este texto se guarda sin normalizar».

    La del login no está, y merece la pena decir por qué: declara `min_length=8`, así que tres
    espacios no llegan a ninguna parte. Estaba en el inventario cuando se escribió y la prueba
    de más arriba la echó.
    """
    assert len(ACEPTADOS) == 11
    contrasenas = [c for (_e, c) in ACEPTADOS if "contrasena" in c or c == "password"]
    assert len(contrasenas) == 4
    # Una sola excepción de esquema entero. Si hubiera dos, lo que habría dejado de valer es
    # la regla, no el esquema.
    assert [e for (e, c) in ACEPTADOS if c == "*"] == ["ScorePredictRequest"]


# ==============================================================================
# 4. Qué se rechaza y qué se anula lo dice la tabla, no una copia
# ==============================================================================

def test_los_textos_de_la_ficha_que_se_anulan_son_los_que_la_tabla_deja_vacios():
    """
    La lista de campos que se normalizan a `None` contra las columnas que admiten nulo.

    Las dos excepciones van nombradas aquí y no en una variable, para que añadir una tercera
    obligue a escribirla en una prueba: `phone`, que pasa por E.164 y ya devuelve nada cuando
    no hay número, y `privacy_notice_source`, que no está en ningún esquema de entrada porque
    la escribe el servidor al anotar el consentimiento.
    """
    de_la_tabla = set(columnas_de_texto(Lead, obligatorias=False))
    assert set(TEXTOS_QUE_ADMITEN_VACIO) == de_la_tabla - {"phone", "privacy_notice_source"}


def test_lo_que_la_ficha_no_admite_vaciar_se_rechaza_con_el_campo_delante():
    """
    Un blanco sobre una columna obligatoria responde 422 **y nombra el campo**.

    Que nombre el campo no es un detalle de cortesía: es lo que hace que el mecanismo del
    capítulo 40 lo pinte debajo del campo en vez de en el aviso de arriba. `source` llegó a
    este capítulo sin mínimo declarado, así que su blanco se habría ido al aviso general.
    """
    for campo in ("first_name", "last_name", "source"):
        with pytest.raises(ValidationError) as error:
            LeadUpdate(**{campo: BLANCO})
        locs = [e["loc"] for e in error.value.errors()]
        assert (campo,) in locs, f"{campo}: el 422 no lleva el campo, llega {locs}"


def test_las_columnas_obligatorias_de_texto_de_las_tres_tablas_estan_contadas():
    """
    Cuántas columnas de texto no admiten vacío en las tablas que una entrada escribe.

    Es una prueba de fijación, y sirve para lo que sirvió la del capítulo 33: la columna
    `NOT NULL` que alguien añada mañana a una de estas tres tablas aparece aquí, y quien la
    añada tendrá que decidir si su blanco se rechaza o se admite en vez de descubrirlo por un
    500 meses después.
    """
    assert columnas_de_texto(Lead, obligatorias=True) == [
        "first_name", "last_name", "email", "source", "status",
        "qualification_status", "score_category",
    ]
    assert columnas_de_texto(User, obligatorias=True) == [
        "email", "hashed_password", "full_name", "role",
    ]
    assert columnas_de_texto(Campaign, obligatorias=True) == [
        "name", "channel", "public_slug", "estado",
    ]


def test_un_cero_y_un_falso_no_son_blancos():
    """
    `en_blanco` no puede ser un `not valor`, y es la clase de función en que lo parece.

    Un presupuesto de cero es una cifra y una cuenta desactivada es un estado, y los dos son
    falsos para un `if`. Con `not valor`, desactivar una cuenta —`is_active: false` sobre una
    columna `NOT NULL`— respondería «este campo no puede quedar vacío», y el mensaje sería
    además convincente.
    """
    assert en_blanco(None) is True
    assert en_blanco("") is True
    assert en_blanco("   ") is True
    assert en_blanco(False) is False
    assert en_blanco(0) is False
    assert en_blanco(0.0) is False
    assert en_blanco("0") is False


def test_la_red_de_la_tabla_ve_un_blanco_y_no_solo_un_nulo():
    """
    El validador de modelo, comprobado directamente, y hay que decir por qué así.

    Con el recorte delante, ningún campo **de hoy** llega a este validador en blanco: los que
    tienen `min_length` se rechazan antes y `source` tiene el suyo. Así que su parte de
    «blanco» no se puede provocar desde una petición, y probarla por ahí sería escribir una
    prueba que pasa por otro motivo. Se comprueba la función.

    Que exista igualmente no es adorno: es la red para la columna obligatoria que alguien añada
    sin declararle un mínimo, que es el descuido más probable de todos —el mínimo es opcional y
    la columna no—. El capítulo 33 escribió esta red mirando solo `None`; aquí mira las dos
    formas del vacío.
    """
    from app.core.texto import vacios_prohibidos

    class Falso:
        model_fields_set = {"first_name", "city"}
        first_name = "   "
        city = ""

    assert vacios_prohibidos(Falso(), frozenset({"first_name"})) == ["first_name"]
    # `city` no está en la lista de obligatorios, así que su vacío es legítimo y no se nombra.
    assert vacios_prohibidos(Falso(), frozenset({"city", "first_name"})) == ["city", "first_name"]

    class Correcto:
        model_fields_set = {"first_name"}
        first_name = "Ana"

    assert vacios_prohibidos(Correcto(), frozenset({"first_name"})) == []


def test_la_configuracion_compartida_es_solo_el_recorte():
    """
    `ENTRADA_DE_TEXTO` no lleva nada más, y conviene que se vea.

    Si llevara `extra="forbid"`, ponerla en una entrada cambiaría cómo responde a un campo
    desconocido, y este capítulo la pone en dieciséis a la vez. Las dos entradas que sí son
    estrictas lo declaran ellas, junto a su motivo.
    """
    assert dict(ENTRADA_DE_TEXTO) == {"str_strip_whitespace": True}
