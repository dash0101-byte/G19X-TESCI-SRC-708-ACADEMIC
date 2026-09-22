"""
Genera la lista local de contraseñas filtradas que usa la política (capítulo 23).

    python scripts/generar_lista_de_contrasenas.py FUENTE [FUENTE ...]

Las fuentes son listas públicas de contraseñas reales filtradas, una por línea. Las que se
usaron están en el manifiesto con su huella, para que cualquiera pueda regenerar el archivo
y obtener exactamente los mismos bytes:

* `100k-most-used-passwords-NCSC.txt` y `xato-net-10-million-passwords-1000000.txt`, de
  SecLists (https://github.com/danielmiessler/SecLists, licencia MIT), carpeta
  `Passwords/Common-Credentials/`.

Qué se guarda y por qué
-----------------------
* **Solo lo que la política no rechazaría ya por su longitud.** Una contraseña filtrada de
  ocho caracteres ya la rechaza el mínimo de 12; guardarla solo engordaría el archivo. Si
  algún día baja el mínimo, la suite falla hasta que se regenere.
* **Normalizada igual que la compara la política** —minúsculas, sin acentos—, con
  `app.core.passwords._normalizar`, la misma función y no una copia.
* **Sin servicio externo.** El archivo viaja en la imagen: comprobar una contraseña no manda
  nada a nadie, ni siquiera un prefijo de su huella.
* **Determinista.** Ordenada, sin duplicados y comprimida con fecha cero: dos generaciones
  desde las mismas fuentes dan el mismo archivo, y su huella queda en el manifiesto, que la
  aplicación comprueba al cargarlo.
"""
import gzip
import hashlib
import io
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from app.core.passwords import (  # noqa: E402
    ARCHIVO_DE_FILTRADAS,
    LONGITUD_MINIMA,
    MANIFIESTO_DE_FILTRADAS,
    MAX_BYTES,
    _normalizar,
)


def generar(fuentes):
    entradas = set()
    descripcion = []
    for fuente in fuentes:
        ruta = pathlib.Path(fuente)
        crudo = ruta.read_bytes()
        lineas = crudo.decode("utf-8", errors="replace").splitlines()
        descripcion.append({"nombre": ruta.name, "sha256": hashlib.sha256(crudo).hexdigest(), "lineas": len(lineas)})
        for linea in lineas:
            normalizada = _normalizar(linea.strip())
            if len(normalizada) >= LONGITUD_MINIMA and len(normalizada.encode("utf-8")) <= MAX_BYTES:
                entradas.add(normalizada)

    texto = ("\n".join(sorted(entradas)) + "\n").encode("utf-8")
    comprimido = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=comprimido, mtime=0, compresslevel=9) as gz:
        gz.write(texto)
    datos = comprimido.getvalue()

    ARCHIVO_DE_FILTRADAS.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_DE_FILTRADAS.write_bytes(datos)
    MANIFIESTO_DE_FILTRADAS.write_text(
        json.dumps(
            {
                "fuentes": descripcion,
                "origen": "https://github.com/danielmiessler/SecLists (MIT), Passwords/Common-Credentials/",
                "criterio": f"normalizadas (minúsculas, sin acentos), longitud >= {LONGITUD_MINIMA}, <= {MAX_BYTES} bytes",
                "longitud_minima": LONGITUD_MINIMA,
                "entradas": len(entradas),
                "sha256": hashlib.sha256(datos).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(entradas), hashlib.sha256(datos).hexdigest()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    total, huella = generar(sys.argv[1:])
    print(f"{total} contraseñas filtradas en {ARCHIVO_DE_FILTRADAS} (sha256 {huella[:16]}…)")
