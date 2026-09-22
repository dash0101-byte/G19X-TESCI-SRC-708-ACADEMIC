"""
Política de contraseñas del sistema.

Vive en un módulo propio porque hay cuatro sitios que fijan contraseñas —el sembrado, el
alta de usuario, el restablecimiento del administrador y el cambio que hace uno mismo— y
una política escrita cuatro veces son cuatro políticas. En cuanto una de ellas se relaja,
la más floja es la que manda: basta con dar de alta la cuenta por la puerta que no
comprueba.

Sobre los criterios, y por qué son estos y no la receta de siempre:

* **Longitud antes que ceremonia.** El mínimo es de 12 caracteres y no se exige mayúscula,
  número y símbolo. Esa exigencia produce `Verano2026!` —que cumple las cuatro reglas y es
  de las primeras que prueba cualquier ataque de diccionario— mientras rechaza
  `caballo grapa batería correcta`, que es incomparablemente más fuerte. Se obliga a algo
  más modesto y más útil: variedad real (al menos tres clases de carácter) o longitud
  suficiente para no necesitarla.
* **Se rechaza lo que ya se sabe que se prueba primero.** Una lista corta de contraseñas
  del contexto de este sistema, el correo de la persona, su nombre y el nombre del producto.
* **Se rechaza lo que ya se filtró (capítulo 23).** Una lista LOCAL de contraseñas reales
  aparecidas en filtraciones públicas —solo las que la longitud mínima no rechazaría ya—,
  dentro de la imagen. Comprobar una contraseña no manda nada a ningún servicio, ni siquiera
  un prefijo de su huella. El archivo lo genera `scripts/generar_lista_de_contrasenas.py`, su
  huella está en el manifiesto y se comprueba al cargarlo: una lista vaciada o sustituida no
  se usa en silencio, falla.
* **El máximo son 72 bytes**, porque bcrypt trunca en silencio a partir de ahí. Una
  contraseña de 100 caracteres de la que solo cuentan 72 es peor que un rechazo: quien la
  eligió cree tener una protección que no tiene.

Lo que esta política NO hace, dicho aquí para que no haya que deducirlo: no caduca
contraseñas por tiempo. Forzar cambios periódicos empuja a la gente a rotar un sufijo, y
lo que se gana en rotación se pierde en calidad. Se registra `password_changed_at` para
poder auditarlo, no para exigirlo.
"""
from __future__ import annotations

import functools
import gzip
import hashlib
import json
import pathlib
import re
import unicodedata
from typing import FrozenSet, List, Optional

# bcrypt opera sobre 72 bytes; más allá trunca sin avisar.
MAX_BYTES = 72
LONGITUD_MINIMA = 12
# A partir de aquí, una contraseña larga no necesita demostrar variedad: la longitud ya
# aporta más entropía que cualquier combinación de clases sobre 12 caracteres.
LONGITUD_QUE_EXIME_DE_VARIEDAD = 16
CLASES_MINIMAS = 3

# Deliberadamente corta y específica del contexto: las que este sistema vería de verdad y
# que ninguna filtración pública tiene por qué contener. Las filtradas van aparte.
CONTRASENAS_PROHIBIDAS = frozenset(
    {
        "password", "passw0rd", "contrasena", "contraseña", "123456", "1234567890",
        "qwerty", "qwertyuiop", "administrador", "administrator", "admin1234",
        "plurione", "plurione2026", "leadscoring", "lead_scoring", "bienvenido",
        "cambiame", "changeme", "iloveyou", "letmein", "welcome", "secret",
    }
)

# Fragmentos que no pueden aparecer dentro de la contraseña por ser adivinables desde
# fuera: el producto y la empresa.
FRAGMENTOS_PROHIBIDOS = ("plurione", "leadscoring", "lead-scoring", "lead_scoring")

# Longitud mínima de una parte del nombre o del correo para considerarla reutilizada. Con
# menos, un "ana" dentro de "cabana" daría un falso positivo constante.
LONGITUD_MINIMA_DE_FRAGMENTO_PERSONAL = 4

DATOS = pathlib.Path(__file__).resolve().parent / "datos"
ARCHIVO_DE_FILTRADAS = DATOS / "contrasenas_filtradas.txt.gz"
MANIFIESTO_DE_FILTRADAS = DATOS / "contrasenas_filtradas.json"


class ContrasenaDebil(ValueError):
    """
    La contraseña no cumple la política. Lleva **todos** los motivos, no el primero.

    Devolver uno solo obliga a descubrir la política a base de intentos, y cada intento
    fallido es una ocasión más para que quien la elige acabe poniendo lo primero que pase.
    """

    def __init__(self, motivos: List[str]):
        self.motivos = motivos
        super().__init__(" ".join(motivos))


class ListaDeFiltradasInvalida(RuntimeError):
    """El archivo de contraseñas filtradas no es el que dice el manifiesto."""


def _normalizar(texto: str) -> str:
    """
    Minúsculas y sin acentos, para comparar `Contraseña` con `contrasena`.

    Primero se descompone y después se pasa a minúsculas. Al revés no es idempotente:
    NFKD convierte algunos signos en letras mayúsculas (`ℌ` → `H`), y la lista de filtradas,
    ya normalizada, no coincidiría con la misma contraseña normalizada otra vez.
    """
    descompuesto = unicodedata.normalize("NFKD", texto).lower()
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


@functools.lru_cache(maxsize=1)
def contrasenas_filtradas() -> FrozenSet[str]:
    """
    La lista local de contraseñas filtradas, verificada contra su manifiesto.

    Se carga una vez por proceso. Si el archivo no está, o su huella o su número de
    entradas no son los del manifiesto, **lanza**: una comprobación de filtradas que
    funcionara con una lista vacía aceptaría todo sin que nada lo dijera, que es peor que
    no tenerla.
    """
    try:
        manifiesto = json.loads(MANIFIESTO_DE_FILTRADAS.read_text(encoding="utf-8"))
        datos = ARCHIVO_DE_FILTRADAS.read_bytes()
    except (OSError, ValueError) as exc:
        raise ListaDeFiltradasInvalida(f"No se puede leer la lista de contraseñas filtradas: {exc}") from exc

    if hashlib.sha256(datos).hexdigest() != manifiesto.get("sha256"):
        raise ListaDeFiltradasInvalida("La lista de contraseñas filtradas no coincide con la huella de su manifiesto.")
    entradas = frozenset(gzip.decompress(datos).decode("utf-8").splitlines())
    if len(entradas) != manifiesto.get("entradas") or not entradas:
        raise ListaDeFiltradasInvalida("La lista de contraseñas filtradas no tiene las entradas que declara su manifiesto.")
    return entradas


def _clases_de_caracter(contrasena: str) -> int:
    clases = 0
    if re.search(r"[a-z]", contrasena):
        clases += 1
    if re.search(r"[A-Z]", contrasena):
        clases += 1
    if re.search(r"[0-9]", contrasena):
        clases += 1
    if re.search(r"[^A-Za-z0-9]", contrasena):
        clases += 1
    return clases


def _fragmentos_personales(email: Optional[str], nombre: Optional[str]) -> List[str]:
    """Trozos del correo y del nombre que no deben aparecer en la contraseña."""
    piezas: List[str] = []
    if email:
        local = _normalizar(email).split("@")[0]
        piezas.extend(p for p in re.split(r"[._\-+0-9]+", local) if p)
    if nombre:
        piezas.extend(p for p in re.split(r"\s+", _normalizar(nombre)) if p)
    return [p for p in piezas if len(p) >= LONGITUD_MINIMA_DE_FRAGMENTO_PERSONAL]


def evaluar(
    contrasena: str,
    *,
    email: Optional[str] = None,
    nombre: Optional[str] = None,
) -> List[str]:
    """
    Devuelve la lista de motivos por los que la contraseña no vale. Vacía si vale.

    Se expone además de `exigir` para que la interfaz pueda enseñar los requisitos que
    faltan mientras se escribe, sin provocar un error.
    """
    motivos: List[str] = []

    if contrasena is None:
        return ["La contraseña es obligatoria."]

    # El máximo se mide en BYTES, no en caracteres: una contraseña con acentos o emoji
    # ocupa más de lo que aparenta, y bcrypt cuenta bytes.
    if len(contrasena.encode("utf-8")) > MAX_BYTES:
        motivos.append(
            f"No puede superar los {MAX_BYTES} bytes: bcrypt descarta en silencio lo que "
            "sobra, y una contraseña recortada sin avisar es más débil de lo que parece."
        )

    if len(contrasena) < LONGITUD_MINIMA:
        motivos.append(f"Debe tener al menos {LONGITUD_MINIMA} caracteres.")

    if contrasena != contrasena.strip():
        motivos.append(
            "No puede empezar ni terminar con espacios: se pierden al copiarla y luego "
            "no coincide."
        )

    if (
        len(contrasena) < LONGITUD_QUE_EXIME_DE_VARIEDAD
        and _clases_de_caracter(contrasena) < CLASES_MINIMAS
    ):
        motivos.append(
            f"Con menos de {LONGITUD_QUE_EXIME_DE_VARIEDAD} caracteres debe combinar al "
            f"menos {CLASES_MINIMAS} de estos cuatro tipos: minúsculas, mayúsculas, "
            "dígitos y símbolos. Una frase larga no necesita cumplirlo."
        )

    normalizada = _normalizar(contrasena)
    sin_espacios = normalizada.replace(" ", "")

    if normalizada in CONTRASENAS_PROHIBIDAS or sin_espacios in CONTRASENAS_PROHIBIDAS:
        motivos.append("Esa contraseña está entre las primeras que prueba cualquier ataque.")
    elif normalizada in contrasenas_filtradas() or sin_espacios in contrasenas_filtradas():
        # Sin decir de qué filtración ni desde cuándo: a quien la elige le basta saber que
        # ya circula, y el detalle no le sirve para elegir otra.
        motivos.append(
            "Esa contraseña aparece en filtraciones públicas: está en las listas que se "
            "prueban antes que cualquier otra. Elija una que no haya usado en otro sitio."
        )

    for fragmento in FRAGMENTOS_PROHIBIDOS:
        if fragmento in sin_espacios:
            motivos.append(
                "No puede contener el nombre del producto ni de la empresa: es lo primero "
                "que prueba quien sabe dónde está entrando."
            )
            break

    for pieza in _fragmentos_personales(email, nombre):
        if pieza in sin_espacios:
            motivos.append(
                "No puede contener su propio nombre ni parte de su dirección de correo."
            )
            break

    # Un solo carácter repetido, o una secuencia evidente.
    if len(set(contrasena)) <= 3 and len(contrasena) >= LONGITUD_MINIMA:
        motivos.append("Repite demasiado los mismos caracteres.")

    return motivos


def exigir(
    contrasena: str,
    *,
    email: Optional[str] = None,
    nombre: Optional[str] = None,
) -> None:
    """Lanza `ContrasenaDebil` con todos los motivos si la contraseña no cumple."""
    motivos = evaluar(contrasena, email=email, nombre=nombre)
    if motivos:
        raise ContrasenaDebil(motivos)
