"""
La comprobación de contraseñas filtradas contra el servicio público (capítulo 37).

Lo que se comprueba aquí se agrupa en tres preguntas, y la primera es la que importa:

1. **¿Qué sale de esta máquina?** Que sean exactamente cinco caracteres hexadecimales del
   resumen SHA-1 y nada más; que la contraseña no aparezca en la petición de ninguna forma;
   que el resumen completo tampoco; y que la bitácora no los escriba. Esta es la propiedad
   que hace aceptable preguntar a un tercero, y si se rompe, se rompe en silencio: todo
   seguiría funcionando igual de bien mientras las contraseñas salen por el cable.

2. **¿Qué pasa en los cuatro casos del servicio?** Filtrada, no filtrada, caída y lenta. Los
   dos últimos tienen la misma respuesta correcta —no bloquear a nadie— y es la que un
   cambio bienintencionado convierte en «por si acaso, rechazamos».

3. **¿Sigue valiendo todo lo de antes?** Que sin servicio el resultado sea el del capítulo
   23, ni más permisivo ni más estricto.

Ninguna prueba de este archivo abre un socket. El servicio se simula con una sonda
inyectada, que es la misma costumbre de `services/direccion_publica.py` (capítulo 34).
"""
import hashlib
import logging

import pytest
from app.core import filtradas_remotas, passwords
from app.core.config import settings
from app.core.filtradas_remotas import (
    MOTIVO_FILTRADA_FUERA,
    PREFIJO,
    Veredicto,
    consultar,
    huella_partida,
)

# Una contraseña que la política LOCAL acepta: larga, variada, sin fragmentos del producto
# ni de nadie. Tiene que pasar todo lo local para que lo que se mida aquí sea el servicio y
# no otra regla.
ACEPTADA_EN_LOCAL = "tramoya-vistosa-9271"


def _resumen(contrasena: str) -> str:
    return hashlib.sha1(contrasena.encode("utf-8")).hexdigest().upper()  # noqa: S324


def _cuerpo_con(contrasena: str, veces: int = 1234) -> str:
    """La respuesta que el servicio daría si esa contraseña estuviera filtrada."""
    sufijo = _resumen(contrasena)[PREFIJO:]
    return "\r\n".join(
        [
            "0000000000000000000000000000000AAAA:17",
            f"{sufijo}:{veces}",
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:3",
        ]
    )


def _cuerpo_sin(contrasena: str) -> str:
    """La respuesta del servicio cuando el sufijo no está: la lista, sin nuestra línea."""
    sufijo = _resumen(contrasena)[PREFIJO:]
    lineas = [
        "0000000000000000000000000000000AAAA:17",
        "11111111111111111111111111111111111:4",
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:3",
    ]
    assert sufijo not in lineas
    return "\r\n".join(lineas)


@pytest.fixture
def encendida(monkeypatch):
    """Enciende la comprobación para una prueba. Sin sonda sigue sin salir a internet."""
    monkeypatch.setattr(settings, "COMPROBAR_CONTRASENAS_FILTRADAS", True)


# ---------------------------------------------------------------------------
# 1. Qué sale de esta máquina
# ---------------------------------------------------------------------------


def test_solo_salen_cinco_caracteres_del_resumen(encendida):
    """
    La propiedad central: lo que se manda es el prefijo y nada más.

    Se captura el argumento tal cual lo recibe la sonda, que es la única función que abre un
    socket, y se mide. Comprobarlo sobre la URL construida sería comprobar la misma línea
    dos veces; comprobarlo sobre el argumento comprueba el contrato.
    """
    enviados = []

    def sonda(prefijo, timeout):
        enviados.append(prefijo)
        return 200, _cuerpo_sin(ACEPTADA_EN_LOCAL)

    consultar(ACEPTADA_EN_LOCAL, sonda=sonda)

    assert len(enviados) == 1
    (enviado,) = enviados
    assert len(enviado) == PREFIJO == 5
    assert enviado == _resumen(ACEPTADA_EN_LOCAL)[:5]
    assert all(c in "0123456789ABCDEF" for c in enviado)


def test_ni_la_contrasena_ni_el_resumen_completo_salen(encendida):
    """
    Lo que NO sale. Es la otra mitad de la prueba anterior y no es redundante: un cambio
    que añadiera la contraseña como parámetro de consulta «para depurar» dejaría intacta la
    longitud del prefijo y pasaría la prueba de arriba.
    """
    visto = []

    def sonda(prefijo, timeout):
        visto.append(prefijo)
        return 200, _cuerpo_sin(ACEPTADA_EN_LOCAL)

    consultar(ACEPTADA_EN_LOCAL, sonda=sonda)

    todo = "".join(visto)
    assert ACEPTADA_EN_LOCAL not in todo
    assert _resumen(ACEPTADA_EN_LOCAL) not in todo
    assert _resumen(ACEPTADA_EN_LOCAL)[PREFIJO:] not in todo


def test_la_huella_se_devuelve_partida_y_las_dos_mitades_cuadran():
    """
    `huella_partida` existe para que ninguna función tenga el resumen entero a mano. Se
    comprueba que las dos mitades son el resumen real: una partición que no cuadrara
    produciría un prefijo que no es el de esa contraseña y la comprobación miraría en el
    cajón equivocado sin decirlo nunca.
    """
    prefijo, sufijo = huella_partida("una frase larga y tranquila")
    assert len(prefijo) == 5
    assert prefijo + sufijo == _resumen("una frase larga y tranquila")
    assert (prefijo + sufijo).isupper()


def test_la_bitacora_no_escribe_la_contrasena_ni_su_resumen(encendida, caplog):
    """
    Una bitácora que registrara el resumen completo anularía todo lo anterior: el archivo de
    registro sería el diccionario que no se quiso mandar, y encima guardado.
    """
    caplog.set_level(logging.DEBUG)

    def sonda(prefijo, timeout):
        return 200, _cuerpo_con(ACEPTADA_EN_LOCAL)

    consultar(ACEPTADA_EN_LOCAL, sonda=sonda)
    escrito = caplog.text
    assert ACEPTADA_EN_LOCAL not in escrito
    assert _resumen(ACEPTADA_EN_LOCAL) not in escrito
    assert _resumen(ACEPTADA_EN_LOCAL)[PREFIJO:] not in escrito
    # Y sí el prefijo, que es lo que de todas formas ya viajó por el cable: sin él, un
    # incidente no se puede investigar.
    assert _resumen(ACEPTADA_EN_LOCAL)[:PREFIJO] in escrito


def test_la_bitacora_del_fallo_tampoco_lleva_el_mensaje_de_httpx(encendida, caplog):
    """
    El mensaje de una excepción de httpx lleva la URL, y la URL lleva el prefijo. Se guarda
    la CLASE de la excepción, no su texto: un texto libre es por donde se escapa lo que
    nadie decidió registrar.
    """
    caplog.set_level(logging.DEBUG)

    class ErrorConUrlDentro(RuntimeError):
        pass

    def sonda(prefijo, timeout):
        raise ErrorConUrlDentro(f"fallo al pedir https://ejemplo/range/{prefijo}SECRETO")

    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=sonda)
    assert veredicto.filtrada is None
    assert "ErrorConUrlDentro" in caplog.text
    assert "SECRETO" not in caplog.text


# ---------------------------------------------------------------------------
# 2. Los cuatro casos del servicio
# ---------------------------------------------------------------------------


def test_filtrada(encendida):
    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=lambda p, t: (200, _cuerpo_con(ACEPTADA_EN_LOCAL, 4096)))
    assert veredicto.filtrada is True
    assert veredicto.apariciones == 4096
    assert veredicto.se_pudo_preguntar


def test_no_filtrada(encendida):
    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=lambda p, t: (200, _cuerpo_sin(ACEPTADA_EN_LOCAL)))
    assert veredicto.filtrada is False
    assert veredicto.apariciones == 0
    assert veredicto.se_pudo_preguntar


def test_caida(encendida):
    """El servicio no contesta: ni filtrada ni no filtrada. No se puede saber."""

    def sonda(prefijo, timeout):
        raise ConnectionError("sin ruta hasta el host")

    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=sonda)
    assert veredicto.filtrada is None
    assert not veredicto.se_pudo_preguntar
    assert veredicto.detalle == "ConnectionError"


def test_lenta(encendida):
    """
    El servicio tarda más de lo que se le concede. Para este módulo es indistinguible de
    una caída, y está bien que lo sea: lo que se protege es el tiempo de quien espera.
    """

    class Agotado(Exception):
        pass

    esperas = []

    def sonda(prefijo, timeout):
        esperas.append(timeout)
        raise Agotado()

    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=sonda, timeout=0.75)
    assert veredicto.filtrada is None
    assert esperas == [0.75]


def test_no_hay_reintentos(encendida):
    """
    Un reintento con espera multiplica el tope por un número que nadie fijó, y convierte un
    tercero caído en un formulario de alta que parece colgado.
    """
    intentos = []

    def sonda(prefijo, timeout):
        intentos.append(prefijo)
        raise ConnectionError("cae siempre")

    consultar(ACEPTADA_EN_LOCAL, sonda=sonda)
    assert len(intentos) == 1


def test_un_codigo_que_no_es_200_es_no_se_pudo_preguntar(encendida):
    """
    Un 429 o un 503 son «ahora no», no «no está filtrada». Tratarlos como un cuerpo vacío
    convertiría un servicio saturado en una vía libre, que es la degradación silenciosa que
    este capítulo se propuso no tener.
    """
    for codigo in (301, 429, 500, 503):
        veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=lambda p, t, c=codigo: (c, ""))
        assert veredicto.filtrada is None, codigo
        assert veredicto.detalle == f"HTTP {codigo}"


def test_el_relleno_de_recuento_cero_no_cuenta_como_filtrada(encendida):
    """
    `Add-Padding` hace que el servicio devuelva entradas falsas con recuento 0 para que el
    tamaño de la respuesta no delate el prefijo. Contarlas haría que una contraseña pareciera
    filtrada en cuanto el relleno acertara con su sufijo —que es precisamente lo que el
    relleno simula—, y el rechazo sería inexplicable para quien lo sufriera.
    """
    sufijo = _resumen(ACEPTADA_EN_LOCAL)[PREFIJO:]
    cuerpo = f"AAAA:5\r\n{sufijo}:0\r\nBBBB:9"
    veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=lambda p, t: (200, cuerpo))
    assert veredicto.filtrada is False


def test_un_cuerpo_inesperado_no_rompe_el_alta(encendida):
    """
    Si el servicio cambiara de formato, lo que no puede pasar es que el alta de usuario
    devuelva un 500. Un cuerpo que no se entiende es «no se pudo saber».
    """
    sufijo = _resumen(ACEPTADA_EN_LOCAL)[PREFIJO:]
    for cuerpo in ("", "<html>mantenimiento</html>", f"{sufijo}:no-es-un-numero"):
        veredicto = consultar(ACEPTADA_EN_LOCAL, sonda=lambda p, t, c=cuerpo: (200, c))
        assert veredicto.filtrada is False, cuerpo


# ---------------------------------------------------------------------------
# 3. La política de arriba: qué hace el sistema con cada veredicto
# ---------------------------------------------------------------------------


def test_la_politica_rechaza_lo_que_el_servicio_dice_que_esta_filtrado(monkeypatch):
    monkeypatch.setattr(
        passwords.filtradas_remotas,
        "consultar",
        lambda c: Veredicto(filtrada=True, apariciones=9, prefijo="ABCDE"),
    )
    motivos = passwords.evaluar(ACEPTADA_EN_LOCAL, preguntar_fuera=True)
    assert motivos == [MOTIVO_FILTRADA_FUERA]
    with pytest.raises(passwords.ContrasenaDebil):
        passwords.exigir(ACEPTADA_EN_LOCAL)


def test_el_motivo_no_dice_cuantas_veces_aparecio(monkeypatch):
    """
    El recuento no ayuda a quien elige y sí ayuda a quien ataca. Que el veredicto lo lleve
    es para la bitácora; que el mensaje no lo lleve es la decisión.
    """
    monkeypatch.setattr(
        passwords.filtradas_remotas,
        "consultar",
        lambda c: Veredicto(filtrada=True, apariciones=38421, prefijo="ABCDE"),
    )
    (motivo,) = passwords.evaluar(ACEPTADA_EN_LOCAL, preguntar_fuera=True)
    assert "38421" not in motivo
    # Y sí dice que la contraseña no salió de aquí: quien lee «aparece en filtraciones»
    # justo después de teclearla tiene todo el derecho a preguntarse si la mandamos.
    assert "cinco caracteres" in motivo


def test_sin_servicio_el_resultado_es_el_de_antes_del_capitulo_37(monkeypatch):
    """
    La prueba de la no-degradación, y la razón de que el veredicto tenga tres valores.

    Se evalúa la MISMA contraseña dos veces: una con el servicio caído y otra sin preguntar
    siquiera. Las dos listas de motivos tienen que ser idénticas, carácter a carácter.
    """
    monkeypatch.setattr(
        passwords.filtradas_remotas,
        "consultar",
        lambda c: Veredicto(filtrada=None, detalle="ConnectionError"),
    )
    for contrasena in (ACEPTADA_EN_LOCAL, "corta", "password", "Plurione2026!!"):
        con_servicio_caido = passwords.evaluar(contrasena, preguntar_fuera=True)
        como_siempre = passwords.evaluar(contrasena, preguntar_fuera=False)
        assert con_servicio_caido == como_siempre, contrasena


def test_sin_servicio_la_lista_local_sigue_rechazando(monkeypatch):
    """
    «No se degrada a todo vale» dicho de la forma que se podría romper: con el servicio
    caído, una contraseña de la lista LOCAL tiene que seguir cayendo.
    """
    monkeypatch.setattr(
        passwords.filtradas_remotas, "consultar", lambda c: Veredicto(filtrada=None)
    )
    with pytest.raises(passwords.ContrasenaDebil):
        passwords.exigir("password")


def test_no_se_pregunta_fuera_por_lo_que_ya_rechazo_la_lista_local(monkeypatch):
    """
    No hay motivo para mandar ni cinco caracteres de algo ya rechazado, y una salida a
    internet por cada «123456789012» es una salida regalada.
    """
    preguntas = []

    def espia(contrasena):
        preguntas.append(contrasena)
        return Veredicto(filtrada=False)

    monkeypatch.setattr(passwords.filtradas_remotas, "consultar", espia)
    passwords.evaluar("password", preguntar_fuera=True)
    assert preguntas == []

    passwords.evaluar(ACEPTADA_EN_LOCAL, preguntar_fuera=True)
    assert preguntas == [ACEPTADA_EN_LOCAL]


def test_se_pregunta_por_la_contrasena_tal_cual_se_escribio(monkeypatch):
    """
    Sin normalizar. Nuestras listas se generan normalizadas y por eso se comparan así; el
    servicio indexa contraseñas reales, donde `Tramoya` y `tramoya` son dos entradas. Pasarle
    la normalizada preguntaría por una contraseña que nadie escribió nunca, y el resultado
    sería un «no está filtrada» tan tranquilizador como falso.
    """
    preguntas = []
    monkeypatch.setattr(
        passwords.filtradas_remotas,
        "consultar",
        lambda c: preguntas.append(c) or Veredicto(filtrada=False),
    )
    passwords.evaluar("Tramoya-Vistosa-9271", preguntar_fuera=True)
    assert preguntas == ["Tramoya-Vistosa-9271"]


def test_evaluar_no_sale_a_internet_por_defecto(monkeypatch):
    """
    El valor por omisión de `preguntar_fuera` es falso, y de eso depende que el generador de
    la lista local no abra una conexión por cada una de las decenas de miles de contraseñas
    que evalúa.
    """
    monkeypatch.setattr(
        passwords.filtradas_remotas,
        "consultar",
        lambda c: pytest.fail("evaluar() ha salido a internet sin que nadie se lo pidiera"),
    )
    passwords.evaluar(ACEPTADA_EN_LOCAL)


# ---------------------------------------------------------------------------
# Las dos guardas que impiden que esto salga a internet por descuido
# ---------------------------------------------------------------------------


def test_apagada_no_abre_un_socket():
    """Con el interruptor en falso ni se calcula el resumen: se devuelve «no se preguntó»."""
    assert settings.COMPROBAR_CONTRASENAS_FILTRADAS is False  # la fija conftest
    veredicto = consultar(
        ACEPTADA_EN_LOCAL,
        sonda=lambda p, t: pytest.fail("se preguntó con la comprobación apagada"),
    )
    assert veredicto.filtrada is None
    assert veredicto.detalle == filtradas_remotas.NO_SE_PREGUNTO
    assert veredicto.prefijo == ""


def test_la_suite_no_puede_salir_a_internet_aunque_se_encienda(encendida):
    """
    La segunda guarda. Con ENVIRONMENT=test y sin sonda inyectada, `consultar` se niega en
    lugar de abrir el socket. Es lo que separa «esta prueba no sale a internet» de «esta
    prueba no sale a internet mientras nadie toque el fixture».
    """
    assert settings.ENVIRONMENT == "test"
    with pytest.raises(RuntimeError, match="no sale a internet"):
        consultar(ACEPTADA_EN_LOCAL)


def test_el_tope_de_espera_tiene_limites():
    """
    Un tope de sesenta segundos convierte a un tercero caído en un formulario colgado, y la
    persona que lo sufre no tiene forma de saber que la culpa no es suya.
    """
    from app.core.config import Settings

    for malo in (0.1, 0.49, 11, 60):
        with pytest.raises(ValueError):
            Settings(CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS=malo)
    for bueno in (0.5, 2.0, 10):
        assert Settings(CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS=bueno)


def test_el_contexto_tls_es_el_del_sistema_y_verifica():
    """
    La línea del punto 3 del encargo, comprobada y no solo escrita.

    Se mira que el contexto VERIFIQUE —`CERT_REQUIRED` y comprobación del nombre—, porque
    la forma de «arreglar» un certificado que no valida es apagar justamente eso, y el
    resultado se parece mucho a que todo funcione.

    Lo que no se puede comprobar aquí es que el almacén cargado sea el del sistema y no el
    de `certifi`: las dos cosas producen un `SSLContext` idéntico por fuera. De eso se ocupa
    el control 44 del CI, mirando la llamada.
    """
    contexto = filtradas_remotas._contexto_tls()
    import ssl

    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_la_url_es_https_y_el_prefijo_no_es_configurable():
    """
    Dos constantes que no deben moverse. `http` mandaría el prefijo en claro —poco, pero
    gratis para cualquiera en el camino—, y un prefijo más largo estrecharía el conjunto en
    el que la contraseña se esconde hasta hacerlo inútil.
    """
    assert filtradas_remotas.URL_DE_RANGO.startswith("https://")
    assert PREFIJO == 5
