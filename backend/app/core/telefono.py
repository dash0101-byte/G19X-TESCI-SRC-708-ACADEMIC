"""
Teléfonos en E.164.

El teléfono de un prospecto era texto libre de hasta 50 caracteres. «55 1234 5678»,
«+52 (55) 1234-5678» y «5512345678» eran tres prospectos distintos para cualquier
comparación, y un aviso de WhatsApp —que identifica a la persona solo por su número— no
tenía contra qué casar. Ahora se guarda una sola forma, `+525512345678`, y lo que no es un
número se rechaza al guardarlo en lugar de descubrirse el día que se intenta marcar.

La región por defecto es México: un número sin prefijo internacional se interpreta como
mexicano, que es lo que escribe quien da de alta un prospecto aquí. Con prefijo, vale el
del número.

El mensaje de error no repite el número. Llega en la respuesta a quien lo envió, pero
también puede acabar en un registro del servidor, y un teléfono es un dato personal (R-11).

Desde el capítulo 32 se aplica también al teléfono de los **asesores** (`users.phone`), que
se había quedado como texto libre. Aquí vive `validador_de_telefono`, el envoltorio que
usan los dos esquemas: mientras cada uno tuvo su copia privada, mantener una sola forma del
número dependía de que quien tocara una se acordara de la otra.
"""
from typing import Optional

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

REGION_POR_DEFECTO = "MX"


class TelefonoInvalido(ValueError):
    """El valor no es un número de teléfono válido."""


def _sin_uno_movil_mexicano(numero: phonenumbers.PhoneNumber) -> phonenumbers.PhoneNumber:
    """
    Retira el «1» de móvil que México dejó de usar en 2019: +52 1 55 1234 5678.

    WhatsApp sigue identificando así a los móviles mexicanos (`5215512345678`), y muchas
    agendas también. `phonenumbers` lo da por inválido, con razón; sin esta corrección, cada
    mensaje de WhatsApp de un móvil de México se rechazaría y nunca casaría con la ficha que
    guarda +525512345678.
    """
    if numero.country_code == 52:
        nacional = str(numero.national_number)
        if len(nacional) == 11 and nacional.startswith("1"):
            return phonenumbers.parse("+52" + nacional[1:], None)
    return numero


def normalizar_telefono(valor: Optional[str], region: str = REGION_POR_DEFECTO) -> Optional[str]:
    """
    Devuelve el número en E.164, `None` si no hay número, o lanza `TelefonoInvalido`.

    Una cadena vacía o de espacios es «sin teléfono», no un teléfono inválido: es lo que
    envía un formulario con el campo en blanco.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        numero = _sin_uno_movil_mexicano(phonenumbers.parse(texto, region))
    except NumberParseException as exc:
        raise TelefonoInvalido("El teléfono no tiene forma de número de teléfono.") from exc
    if not phonenumbers.is_valid_number(numero):
        raise TelefonoInvalido(
            "El teléfono no es un número válido: revise la lada y el número de dígitos."
        )
    return phonenumbers.format_number(numero, PhoneNumberFormat.E164)


def validador_de_telefono(valor: Optional[str]) -> Optional[str]:
    """
    Valida y normaliza desde un esquema de Pydantic. Uno solo para prospectos y asesores.

    Vuelve a lanzar como `ValueError` llano, con el mismo mensaje y `from None`: lo que
    llega a quien envió el formulario es la explicación —«revise la lada y el número de
    dígitos»— con el campo delante, y no una traza encadenada con el nombre de la clase.

    No se aplica a las respuestas, solo a la entrada —alta y edición—: un teléfono anterior
    a la Fase 15 que la migración no pudo normalizar convertiría la lectura de su ficha en
    un error, y leer una ficha no es el momento de descubrir que su teléfono está mal.
    """
    try:
        return normalizar_telefono(valor)
    except TelefonoInvalido as exc:
        raise ValueError(str(exc)) from None
