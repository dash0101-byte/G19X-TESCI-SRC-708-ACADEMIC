"""
El único modo de arrancar la pila: con el entorno FUERA del repositorio (capítulo 22).

Lo que había
------------
Tres maneras de arrancar, y en las tres los secretos acababan dentro del árbol de trabajo.
El README mandaba escribir `SECRET_KEY` y `POSTGRES_PASSWORD` con `>> .env` en `devops/`; la
cabecera del compose decía `cd devops && docker compose up`; y la aplicación, fuera de
Docker, lee además `.env` y `../.env` desde donde se lance. Que `.gitignore` excluya esos
archivos evita que se versionen, no que existan: un `.env` dentro del repositorio viaja en
cada copia de la carpeta, en cada comprimido que se manda por correo y en cada respaldo del
portátil. En la Fase 0 de seguridad hubo que sacar uno con la clave ya expuesta.

Lo que hace
-----------
Envuelve `docker compose` y le pasa siempre el mismo archivo de entorno, que vive fuera del
repositorio. Antes de ejecutar nada comprueba cuatro cosas y se niega si falla alguna:

1. el archivo existe;
2. no está dentro del repositorio;
3. no hay un `.env` en el repositorio que Compose o la aplicación leerían por su cuenta
   —`devops/.env` lo carga Compose sin que nadie lo pida—;
4. trae `SECRET_KEY` y `POSTGRES_PASSWORD`.

Uso
---
    python devops/pila.py iniciar              # crea el archivo de entorno con secretos nuevos
    python devops/pila.py up -d --build        # cualquier orden de docker compose
    python devops/pila.py --dev up -d          # con el overlay de desarrollo
    python devops/pila.py --profile respaldo run --rm respaldo
    python devops/pila.py --comprobar          # solo las comprobaciones, sin Docker

El archivo es `~/.plurione/pila.env`, o el que indique `PLURIONE_ENTORNO` o `--entorno RUTA`.
El proyecto de Compose sigue llamándose `devops`, como cuando se arrancaba desde esa
carpeta: los volúmenes existentes (`devops_pgdata`…) se siguen encontrando.
"""
import os
import pathlib
import secrets
import stat
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Sequence

DEVOPS = pathlib.Path(__file__).resolve().parent
RAIZ = DEVOPS.parent
COMPOSE = DEVOPS / "docker-compose.yml"
COMPOSE_DEV = DEVOPS / "docker-compose.dev.yml"
EJEMPLO = DEVOPS / ".env.example"

ENTORNO_POR_DEFECTO = pathlib.Path.home() / ".plurione" / "pila.env"
OBLIGATORIAS = ("SECRET_KEY", "POSTGRES_PASSWORD")

# Los `.env` que alguien leería sin que se lo pidan: Compose carga el del directorio del
# proyecto, y la aplicación busca `.env` y `../.env` desde donde se lance (`config.py`).
ENV_QUE_SE_LEEN_SOLOS = (DEVOPS / ".env", RAIZ / ".env", RAIZ / "backend" / ".env")

# El cliente compilado no viaja en el repositorio —`dist/` está en `.gitignore`— y la imagen
# del backend lo COPIA, para poder servir la SPA ella sola en el 8000. En un clon limpio eso
# hace morir la construcción con `failed to compute cache key: "/frontend/dist": not found`,
# sesenta líneas por debajo de la orden, nombrando una ruta de dentro de la imagen y sin decir
# qué hacer. El 07-10-2026 un ensayo de instalación desde cero murió exactamente ahí.
#
# El compose ya avisa de la otra mitad de este problema —la imagen del cliente sirviendo un
# `dist/` de otro día— en el comentario de su `target` explícito, y esa nota ya decía que «en
# una máquina limpia la construcción falla de golpe». Lo que faltaba era decirlo aquí, antes.
CLIENTE_COMPILADO = RAIZ / "frontend" / "dist" / "index.html"

# `run` incluido a propósito: `run --rm migrate` usa la imagen del backend, así que también
# la construye si no existe.
ORDENES_QUE_CONSTRUYEN = ("up", "build", "create", "run")


def ruta_del_entorno(explicita: Optional[str] = None, entorno: Optional[Dict[str, str]] = None) -> pathlib.Path:
    entorno = os.environ if entorno is None else entorno
    elegida = explicita or entorno.get("PLURIONE_ENTORNO") or str(ENTORNO_POR_DEFECTO)
    return pathlib.Path(elegida).expanduser()


def dentro_del_repositorio(ruta: pathlib.Path) -> bool:
    # `normcase`: en Windows `C:\Users\...` y `c:\users\...` son la misma carpeta.
    raiz = os.path.normcase(str(RAIZ.resolve()))
    candidata = os.path.normcase(str(ruta.resolve()))
    try:
        return os.path.commonpath([raiz, candidata]) == raiz
    except ValueError:  # unidades distintas en Windows: no puede estar dentro
        return False


def leer_variables(ruta: pathlib.Path) -> Dict[str, str]:
    variables: Dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        variables[clave.strip()] = valor.strip().strip("'\"")
    return variables


def problemas_del_entorno(ruta: pathlib.Path) -> List[str]:
    """Por qué no se arranca. Lista vacía: se puede arrancar."""
    problemas: List[str] = []
    for suelto in ENV_QUE_SE_LEEN_SOLOS:
        if suelto.exists():
            problemas.append(
                f"Hay un archivo de entorno dentro del repositorio: {suelto}. Compose o la aplicación "
                f"lo leerían por su cuenta. Muévalo fuera (por ejemplo, a {ENTORNO_POR_DEFECTO}) y bórrelo de ahí."
            )
    if not ruta.is_file():
        problemas.append(
            f"No existe el archivo de entorno {ruta}. Créelo con `python devops/pila.py iniciar`, "
            "o indique otro con PLURIONE_ENTORNO o --entorno."
        )
        return problemas
    if dentro_del_repositorio(ruta):
        problemas.append(f"El archivo de entorno {ruta} está dentro del repositorio ({RAIZ}). Tiene que vivir fuera.")
    variables = leer_variables(ruta)
    for obligatoria in OBLIGATORIAS:
        if not variables.get(obligatoria):
            problemas.append(f"{ruta} no define {obligatoria}.")
    return problemas


def problema_del_cliente_compilado(resto: Sequence[str]) -> Optional[str]:
    """Qué falta para construir, dicho antes de que Docker lo diga de otra manera."""
    if not any(palabra in ORDENES_QUE_CONSTRUYEN for palabra in resto):
        return None
    if CLIENTE_COMPILADO.exists():
        return None
    return (
        f"Falta el cliente compilado: {CLIENTE_COMPILADO}. La imagen del backend lo copia para "
        "la entrega unificada del 8000, así que su construcción falla con "
        '«"/frontend/dist": not found». No está en el repositorio a propósito —se compila—, '
        "y basta con hacerlo una vez:\n"
        "    cd frontend && npm ci && npm run build"
    )


def aviso_de_permisos(ruta: pathlib.Path) -> Optional[str]:
    """En POSIX, un archivo de secretos legible por otros usuarios de la máquina se señala."""
    if os.name == "nt" or not ruta.is_file():
        return None
    if ruta.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        return f"AVISO: {ruta} es legible por otros usuarios de esta máquina. `chmod 600 {ruta}`."
    return None


def orden_de_compose(ruta: pathlib.Path, dev: bool, resto: Sequence[str]) -> List[str]:
    orden = [
        "docker", "compose",
        "--env-file", str(ruta),
        "--project-directory", str(DEVOPS),
        "-f", str(COMPOSE),
    ]
    if dev:
        orden += ["-f", str(COMPOSE_DEV)]
    return orden + list(resto)


def contenido_inicial() -> str:
    """El `.env.example` con los dos secretos obligatorios ya generados."""
    lineas = []
    for linea in EJEMPLO.read_text(encoding="utf-8").splitlines():
        if linea == "SECRET_KEY=":
            linea = f"SECRET_KEY={secrets.token_urlsafe(64)}"
        elif linea == "POSTGRES_PASSWORD=":
            linea = f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}"
        lineas.append(linea)
    return "\n".join(lineas) + "\n"


def iniciar(ruta: pathlib.Path) -> int:
    if dentro_del_repositorio(ruta):
        print(f"No se crea: {ruta} está dentro del repositorio.")
        return 2
    if ruta.exists():
        # Nunca se sobrescribe: POSTGRES_PASSWORD solo se aplica al crear el volumen, y
        # cambiarla aquí sobre una base ya creada deja al backend sin poder conectar.
        print(f"No se crea: {ruta} ya existe. Edítelo a mano si hace falta.")
        return 2
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        archivo.write(contenido_inicial())
    print(f"Creado {ruta} con SECRET_KEY y POSTGRES_PASSWORD nuevas. Revise el resto de variables.")
    return 0


def main(argv: Optional[Sequence[str]] = None, ejecutar: Callable[[List[str]], int] = subprocess.call) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    explicita: Optional[str] = None
    dev = False
    solo_comprobar = False
    # Las opciones propias van delante; lo demás es de Compose y se pasa tal cual.
    while argv and argv[0] in ("--entorno", "--dev", "--comprobar"):
        opcion = argv.pop(0)
        if opcion == "--dev":
            dev = True
        elif opcion == "--comprobar":
            solo_comprobar = True
        else:
            if not argv:
                print("--entorno necesita una ruta.")
                return 2
            explicita = argv.pop(0)

    ruta = ruta_del_entorno(explicita)

    if argv[:1] == ["iniciar"]:
        return iniciar(ruta)

    problemas = problemas_del_entorno(ruta)
    for problema in problemas:
        print(f"FALLO: {problema}")
    if problemas:
        return 2
    aviso = aviso_de_permisos(ruta)
    if aviso:
        print(aviso)

    if solo_comprobar:
        print(f"Entorno fuera del repositorio y sin .env sueltos: {ruta}")
        return 0
    if not argv:
        print("Falta la orden de docker compose (por ejemplo: up -d --build).")
        return 2
    sin_cliente = problema_del_cliente_compilado(argv)
    if sin_cliente:
        print(f"FALLO: {sin_cliente}")
        return 2
    return ejecutar(orden_de_compose(ruta, dev, argv))


if __name__ == "__main__":
    sys.exit(main())
