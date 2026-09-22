"""
Imágenes de contenedor fijadas por huella, y su renovación explícita (capítulo 22).

Cada imagen de la que depende el proyecto se escribe como `nombre:etiqueta@sha256:<huella>`.
La huella decide lo que se descarga; la etiqueta dice qué seguir al renovar. Hasta el
capítulo 22 se resolvían por etiqueta, y `python:3.13-slim` o `anchore/syft:latest` podían
apuntar a otra imagen en la siguiente construcción sin que nada cambiara en el repositorio.

Tres usos:

    python scripts/renovar_imagenes.py --solo-fijacion  # sin red: todo fijado y coherente
    python scripts/renovar_imagenes.py                  # pregunta al registro qué quedó atrás
    python scripts/renovar_imagenes.py --aplicar        # reescribe las huellas quedadas atrás

`--solo-fijacion` es la guarda: la corren la suite y el pipeline. Falla si una imagen va sin
huella, si la misma `nombre:etiqueta` aparece con dos huellas distintas, si un Dockerfile
vuelve a `apk upgrade` o si instala un paquete de `apk` sin versión.

`--aplicar` no decide nada por su cuenta: deja un diff para revisar. Después hay que
construir, escanear con Trivy y mirar si los paquetes de `apk` con versión del Dockerfile del
cliente siguen haciendo falta; una base nueva puede traerlos ya, o necesitar otros.

Al registro se pregunta con `docker buildx imagetools inspect`, que usa las credenciales y el
proxy del propio Docker, y se toma la huella del índice multiplataforma: la misma referencia
sirve en el ejecutor x86 del CI y en un portátil ARM.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Callable, Dict, List, Tuple

RAIZ = pathlib.Path(__file__).resolve().parents[1]

DOCKERFILES = ["backend/Dockerfile", "frontend/Dockerfile"]
COMPOSE = ["devops/docker-compose.yml", "devops/docker-compose.dev.yml"]
WORKFLOWS = [".github/workflows/ci.yml"]

HUELLA = r"sha256:[0-9a-f]{64}"
FIJADA = re.compile(
    r"(?P<imagen>[a-z0-9][a-z0-9._/-]*):(?P<etiqueta>[A-Za-z0-9._-]+)@(?P<huella>" + HUELLA + r")"
)

# Una referencia `nombre:etiqueta` en el workflow que NO va seguida de huella. Las oficiales
# de Docker Hub no llevan barra, así que se nombran; el resto se reconoce por la barra. Las
# imágenes que construye el propio pipeline (`plurione-...:ci`) no son de nadie más y no
# se fijan.
_OFICIALES = "postgres|redis|nginx|node|python|alpine|busybox|ubuntu|debian"
SIN_HUELLA_EN_WORKFLOW = re.compile(
    r"(?<![\w./@:-])"
    r"(?P<ref>(?:(?:[a-z0-9-]+\.)+[a-z]{2,}/)?(?:[a-z0-9-]+/[a-z0-9._/-]+|(?:" + _OFICIALES + r"))"
    r":[A-Za-z0-9._-]+)"
    r"(?![A-Za-z0-9._@-])"
)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(linea for linea in texto.splitlines() if not linea.lstrip().startswith("#"))


def _instrucciones_de_dockerfile(texto: str) -> List[str]:
    """Una instrucción por elemento, con las continuaciones `\\` ya unidas."""
    unidas = re.sub(r"\\\s*\n", " ", _sin_comentarios(texto))
    return [linea.strip() for linea in unidas.splitlines() if linea.strip()]


def problemas_de_dockerfile(texto: str) -> List[str]:
    problemas: List[str] = []
    etapas = set()
    for instruccion in _instrucciones_de_dockerfile(texto):
        desde = re.match(r"FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", instruccion, re.IGNORECASE)
        if desde:
            origen, alias = desde.group(1), desde.group(2)
            if origen not in etapas and origen != "scratch" and not FIJADA.fullmatch(origen):
                problemas.append(f"FROM {origen}: la imagen base no va fijada por huella")
            if alias:
                etapas.add(alias)
            continue

        if re.search(r"\bapk\b[^;&|]*\bupgrade\b", instruccion):
            problemas.append("`apk upgrade`: sube lo que haya ese día; nombre los paquetes con su versión")
        for orden in re.finditer(r"\bapk\s+add\b(?P<resto>[^;&|]*)", instruccion):
            for token in orden.group("resto").split():
                paquete = token.strip("'\"")
                if not paquete or paquete.startswith("-"):
                    continue
                if "=" not in paquete:
                    problemas.append(f"`apk add {paquete}`: paquete sin versión")
    return problemas


def servicios_de_compose(texto: str) -> Dict[str, Dict[str, str]]:
    """
    Servicios y sus claves de primer nivel, sin PyYAML.

    La guarda corre también en el trabajo de CI que no instala dependencias de Python, y un
    `import yaml` que falla allí se confundiría con un disparo. Basta con la sangría de dos y
    cuatro espacios que usan los dos archivos de la pila; la suite comprueba que este lector
    y `yaml.safe_load` ven los mismos servicios y las mismas imágenes.
    """
    servicios: Dict[str, Dict[str, str]] = {}
    dentro, actual = False, None
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        if sangria == 0:
            dentro, actual = linea.rstrip() == "services:", None
            continue
        if not dentro:
            continue
        if sangria == 2 and linea.rstrip().endswith(":"):
            actual = linea.strip()[:-1]
            servicios[actual] = {}
        elif sangria == 4 and actual is not None:
            clave, _, valor = linea.strip().partition(":")
            servicios[actual][clave] = valor.strip()
    return servicios


def problemas_de_compose(texto: str) -> List[str]:
    problemas: List[str] = []
    for nombre, servicio in servicios_de_compose(texto).items():
        imagen = servicio.get("image")
        # Con `build`, la imagen la construye la propia pila y su nombre es solo una etiqueta
        # local; lo que hay que fijar es el FROM de su Dockerfile. Los servicios que reutilizan
        # esa imagen sin declarar `build` —el monitor, la purga— la nombran `plurione/…`.
        propia = "build" in servicio or (imagen or "").startswith("plurione/")
        if imagen and not propia and not FIJADA.fullmatch(imagen):
            problemas.append(f"servicio `{nombre}`: {imagen} no va fijada por huella")
    return problemas


def problemas_de_workflow(texto: str) -> List[str]:
    problemas: List[str] = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if linea.lstrip().startswith("#"):
            continue
        for encontrada in SIN_HUELLA_EN_WORKFLOW.finditer(linea):
            if encontrada.group("ref").startswith("plurione"):
                continue
            problemas.append(f"línea {numero}: {encontrada.group('ref')} no va fijada por huella")
    return problemas


def _leer(relativa: str) -> str:
    return (RAIZ / relativa).read_text(encoding="utf-8")


def problemas_de_fijacion() -> List[str]:
    """Todo lo que la guarda rechaza, con el archivo delante. Lista vacía: todo en orden."""
    problemas: List[str] = []
    for ruta in DOCKERFILES:
        problemas += [f"{ruta}: {p}" for p in problemas_de_dockerfile(_leer(ruta))]
    for ruta in COMPOSE:
        problemas += [f"{ruta}: {p}" for p in problemas_de_compose(_leer(ruta))]
    for ruta in WORKFLOWS:
        problemas += [f"{ruta}: {p}" for p in problemas_de_workflow(_leer(ruta))]

    # La misma etiqueta con dos huellas es una renovación a medias: el CI escanearía una
    # imagen y la pila desplegaría otra, las dos con el mismo nombre.
    vistas: Dict[Tuple[str, str], Dict[str, List[str]]] = {}
    for ruta in DOCKERFILES + COMPOSE + WORKFLOWS:
        for ref in FIJADA.finditer(_leer(ruta)):
            clave = (ref.group("imagen"), ref.group("etiqueta"))
            vistas.setdefault(clave, {}).setdefault(ref.group("huella"), []).append(ruta)
    for (imagen, etiqueta), huellas in sorted(vistas.items()):
        if len(huellas) > 1:
            detalle = "; ".join(f"{h[7:19]} en {', '.join(sorted(set(r)))}" for h, r in huellas.items())
            problemas.append(f"{imagen}:{etiqueta} aparece con {len(huellas)} huellas distintas ({detalle})")
    return problemas


def referencias_fijadas() -> Dict[Tuple[str, str], str]:
    referencias: Dict[Tuple[str, str], str] = {}
    for ruta in DOCKERFILES + COMPOSE + WORKFLOWS:
        for ref in FIJADA.finditer(_leer(ruta)):
            referencias[(ref.group("imagen"), ref.group("etiqueta"))] = ref.group("huella")
    return referencias


def huella_en_el_registro(imagen: str, etiqueta: str) -> str:
    # `docker` por PATH, como lo invoca quien renueva a mano; la referencia sale de los
    # archivos del repositorio, ya validada por la expresión `FIJADA`, y va como argumento de
    # una lista, sin shell de por medio.
    salida = subprocess.run(  # noqa: S603
        ["docker", "buildx", "imagetools", "inspect", f"{imagen}:{etiqueta}", "--format", "{{json .Manifest}}"],  # noqa: S607
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(salida)["digest"]


def reescribir(texto: str, nuevas: Dict[Tuple[str, str], str]) -> str:
    def sustituir(ref: re.Match) -> str:
        clave = (ref.group("imagen"), ref.group("etiqueta"))
        return f"{clave[0]}:{clave[1]}@{nuevas.get(clave, ref.group('huella'))}"

    return FIJADA.sub(sustituir, texto)


def main(argv=None, consultar: Callable[[str, str], str] = huella_en_el_registro) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--solo-fijacion", action="store_true", help="Solo comprobar, sin red, que todo va fijado.")
    modo.add_argument("--aplicar", action="store_true", help="Reescribir las huellas que hayan quedado atrás.")
    args = parser.parse_args(argv)

    problemas = problemas_de_fijacion()
    for problema in problemas:
        print(f"FALLO: {problema}")
    if problemas:
        return 1
    if args.solo_fijacion:
        print(f"Imágenes fijadas por huella y sistema base sin `apk upgrade`: {len(referencias_fijadas())} referencias.")
        return 0

    atrasadas: Dict[Tuple[str, str], str] = {}
    for (imagen, etiqueta), huella in sorted(referencias_fijadas().items()):
        actual = consultar(imagen, etiqueta)
        if actual == huella:
            print(f"  al día     {imagen}:{etiqueta}")
        else:
            atrasadas[(imagen, etiqueta)] = actual
            print(f"  ATRASADA   {imagen}:{etiqueta}  {huella[7:19]} -> {actual[7:19]}")

    if not atrasadas:
        print("Todas las huellas coinciden con lo que hoy publica cada etiqueta.")
        return 0
    if not args.aplicar:
        print(f"{len(atrasadas)} imagen(es) atrasada(s). Para renovarlas: --aplicar, y revisar el diff.")
        return 1

    for ruta in DOCKERFILES + COMPOSE + WORKFLOWS:
        original = _leer(ruta)
        renovado = reescribir(original, atrasadas)
        if renovado != original:
            (RAIZ / ruta).write_text(renovado, encoding="utf-8")
            print(f"  reescrito  {ruta}")
    print(
        "Renovadas. Antes de publicar: construir, pasar Trivy y revisar si los paquetes de `apk` "
        "con versión del Dockerfile del cliente siguen haciendo falta."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
