"""
¿Lo que está instalado es exactamente lo que fija el lock? (R-2)

    python scripts/comprobar_instalado.py backend/requirements-dev.lock
    python scripts/comprobar_instalado.py backend/requirements.lock --ignorar pip
    python scripts/comprobar_instalado.py backend/requirements.lock --listar > instalado.txt

Compara el entorno de Python que lo ejecuta con el lock: cada paquete del lock cuyo
marcador aplica a esta plataforma tiene que estar instalado en esa versión exacta, y no
puede haber nada instalado que el lock no mencione. Lo segundo importa tanto como lo
primero: un paquete que entró por otro camino —una capa de la imagen base, un `pip install`
suelto en un paso de CI— es código que nadie fijó ni auditó.

Los marcadores se evalúan donde corre el guion. Por eso, para comprobar la imagen del
backend, el CI lo ejecuta DENTRO de la imagen: evaluarlo en el runner diría qué le tocaría
a Ubuntu, no qué tiene el contenedor.

`--listar` escribe lo instalado como `nombre==versión`, que es lo que `pip-audit
--requirement ... --no-deps --disable-pip` audita sin volver a resolver nada: se audita lo
que hay, no lo que se resolvería hoy a partir de unos rangos.

Solo usa la biblioteca estándar y `packaging`, que está en los dos locks. Salida 0 si
coincide, 1 si no.
"""
import argparse
import importlib.metadata
import re
import sys
from typing import Dict, List, NamedTuple, Optional

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")


class Fijado(NamedTuple):
    nombre: str
    version: str
    marcador: Optional[str]
    hashes: List[str]


def leer_lock(texto: str) -> Dict[str, Fijado]:
    """
    Entradas del lock por nombre canónico.

    Une las líneas de continuación (terminadas en barra invertida) y separa requisito,
    marcador y huellas. Una entrada sin `==` exacto no es un lock y se rechaza.
    """
    logicas: List[str] = []
    acumulada = ""
    for cruda in texto.splitlines():
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        continua = linea.endswith("\\")
        acumulada += " " + linea.rstrip("\\").strip()
        if not continua:
            logicas.append(acumulada.strip())
            acumulada = ""
    if acumulada.strip():
        logicas.append(acumulada.strip())

    entradas: Dict[str, Fijado] = {}
    for logica in logicas:
        requisito = logica.split(" --hash", 1)[0].strip()
        req = Requirement(requisito)
        exactas = [e for e in req.specifier if e.operator == "=="]
        if len(exactas) != 1 or len(req.specifier) != 1:
            raise ValueError(f"Entrada sin versión exacta en el lock: {requisito!r}")
        entradas[canonicalize_name(req.name)] = Fijado(
            nombre=canonicalize_name(req.name),
            version=exactas[0].version,
            marcador=str(req.marker) if req.marker else None,
            hashes=_HASH.findall(logica),
        )
    return entradas


def aplicables(entradas: Dict[str, Fijado]) -> Dict[str, str]:
    """Nombre → versión de lo que el lock pide EN ESTA plataforma."""
    return {
        nombre: fijado.version
        for nombre, fijado in entradas.items()
        if fijado.marcador is None or Requirement(f"x; {fijado.marcador}").marker.evaluate()
    }


def instalado() -> Dict[str, str]:
    return {
        canonicalize_name(dist.metadata["Name"]): dist.version
        for dist in importlib.metadata.distributions()
        if dist.metadata["Name"]
    }


def comparar(esperado: Dict[str, str], presente: Dict[str, str], ignorar=()) -> List[str]:
    ignorados = {canonicalize_name(n) for n in ignorar}
    problemas = []
    for nombre, version in sorted(esperado.items()):
        if nombre in ignorados:
            continue
        if nombre not in presente:
            problemas.append(f"falta     {nombre}=={version}")
        elif presente[nombre] != version:
            problemas.append(f"distinto  {nombre}: lock {version}, instalado {presente[nombre]}")
    for nombre, version in sorted(presente.items()):
        if nombre not in esperado and nombre not in ignorados:
            problemas.append(f"sobra     {nombre}=={version} (no está en el lock)")
    return problemas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lock", help="Fichero de requisitos fijados con huellas.")
    parser.add_argument(
        "--ignorar",
        action="append",
        default=[],
        help="Paquete del propio entorno que no forma parte de lo desplegado (p. ej. pip en un venv).",
    )
    parser.add_argument("--listar", action="store_true", help="Escribir lo instalado como nombre==versión.")
    args = parser.parse_args(argv)

    with open(args.lock, encoding="utf-8") as fh:
        entradas = leer_lock(fh.read())

    presente = instalado()
    if args.listar:
        ignorados = {canonicalize_name(n) for n in args.ignorar}
        for nombre, version in sorted(presente.items()):
            if nombre not in ignorados:
                print(f"{nombre}=={version}")
        return 0

    sin_huella = sorted(n for n, f in entradas.items() if not f.hashes)
    if sin_huella:
        print(f"[LOCK] Entradas sin huella en {args.lock}: {', '.join(sin_huella)}")
        return 1

    esperado = aplicables(entradas)
    problemas = comparar(esperado, presente, args.ignorar)
    if problemas:
        print(f"[LOCK] Lo instalado NO corresponde a {args.lock}:")
        for problema in problemas:
            print(f"  {problema}")
        return 1
    print(f"[LOCK] Lo instalado corresponde a {args.lock}: {len(esperado)} paquetes, versiones exactas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
