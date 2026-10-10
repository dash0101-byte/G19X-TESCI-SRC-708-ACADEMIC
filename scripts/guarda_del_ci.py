"""
Guarda del CI mismo: que haya veredicto, que sea verde, y que los diez trabajos hayan corrido.

    python scripts/guarda_del_ci.py                 # el veredicto de la última ejecución de HEAD
    python scripts/guarda_del_ci.py --sin-red       # solo lo que se comprueba leyendo el árbol
    python scripts/guarda_del_ci.py --ejecucion ID  # una ejecución concreta, por su número
    python scripts/guarda_del_ci.py --rama          # la última de la rama, sea de qué commit sea

Punto 68 de §6.4, el que la abrió: **el CI llevaba rojo desde antes de aquel trabajo y nada
lo decía.** Las guardas de este repositorio vigilan la aplicación; ninguna vigilaba el
pipeline. Un trabajo que falla se ve en GitHub y en ningún otro sitio, y quien trabaja en
local con la suite verde no tiene cómo enterarse: de los nueve defectos de aquella tanda,
**ninguno lo trajo un cambio del árbol**. Esta guarda es el sitio donde mirar, en una orden.

Falla —nombrando qué falta— si:

1. **no hay veredicto, o no es verde**: no existe ejecución de este flujo para el commit;
   existe y terminó en rojo; o terminó en algo que no es un veredicto —cancelada, en vuelo—,
   que no es lo mismo que estar bien y aquí no se cuenta como tal;
2. **algún trabajo declarado no corrió**: el inventario se saca de `ci.yml`, no de una lista
   escrita a mano, y cada trabajo tiene que aparecer en la respuesta de GitHub **y** estar en
   verde. Un trabajo que no aparece, o que aparece `skipped`, es la segunda mitad del punto
   68: un trabajo en rojo deja sin correr a los que dependen de él, y entonces no se sabe
   cuántos defectos hay detrás. Aquel día los cuatro rojos anotados resultaron ser nueve;
3. **algún paso quedó tapado**: `ci.yml` no declara ninguna condición de paso que no sea
   `always()`, así que un paso `skipped` **solo** puede significar que algo delante se rompió.
   Esa premisa se comprueba aquí mismo contra el archivo: si aparece una condición que no sea
   `always()`, la guarda avisa de que ya no puede afirmarlo y pide venir a revisarla, en
   lugar de seguir midiendo menos de lo que dice;
4. **los documentos y el flujo discrepan en cuántos trabajos hay**: la cifra está escrita a
   mano en siete sitios vivos —este repositorio ya aprendió tres veces que medir bien sobre
   una lista escrita a mano es medir la lista—, y se coteja con la derivada del archivo.

Tres salidas, y la tercera es el motivo de que esta guarda exista:

    0  verde
    1  hay algo roto, con el motivo escrito
    2  **no se pudo establecer el veredicto** —no está `gh`, no hay sesión, no hay red, el
       commit no está empujado, la ejecución sigue en vuelo—. Nunca se calla en verde: una
       guarda que da por bueno lo que no ha podido mirar es justo lo que se está arreglando.

No corre dentro del CI, y es a propósito: el veredicto de una ejecución no se puede pedir
desde dentro de ella. La mitad que no necesita red —`--sin-red`, los puntos 3 y 4— la
comprueba la suite, en `backend/tests/test_guarda_del_ci.py`.

A GitHub se le pregunta con `gh`, que ya trae la sesión de quien trabaja aquí, y **filtrando
por el archivo del flujo**: `Dependabot Updates` deja ejecuciones de un solo trabajo y
verdes, y «la última ejecución» sin filtrar es, cada pocos días, la de otro flujo dando por
bueno lo que nadie ha comprobado.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Callable, Dict, List, Tuple

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FLUJO = ".github/workflows/ci.yml"

# Los documentos vivos que dan cifras del sistema. Se derivan por glob y no se enumeran: la
# lista escrita a mano es el defecto que esta guarda vigila en los demás. Fuera quedan tres,
# cada uno por su motivo: `docs/reportes/` y la memoria son el registro de lo que se midió
# cada capítulo —se compila, y reescribir el pasado sería falsearlo—, y `docs_residencias`
# no lo mantiene este repositorio.
COMPILADA = "Memoria_Tecnica_Final_Lead_Scoring.md"

PALABRAS = {
    "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
}

CIFRA_DE_TRABAJOS = re.compile(
    r"(?<![\w-])(\d{1,3}|" + "|".join(PALABRAS) + r")\*{0,2} trabajos(?![\w-])",
    re.IGNORECASE,
)

# Una fila de §6.4: `| 73 | ... |`. Son registros con fecha —«la ejecución 38003136533 sale
# verde entera, diez de diez trabajos»—, y un trabajo nuevo no las vuelve falsas.
FILA_DE_OBSERVACION = re.compile(r"^\| \d+ \|")

VERDE = "success"
SIN_VEREDICTO = ("skipped", "cancelled", None, "")


class SinVeredicto(Exception):
    """No se pudo mirar. Distinto de «está roto», y la diferencia es el punto 68 entero."""


# --------------------------------------------------------------------- leer el flujo
def _escalar(valor: str) -> str:
    """Un valor de una línea `clave: valor`, sin el comentario de al lado ni las comillas."""
    valor = valor.strip()
    if valor[:1] in ("'", '"'):
        return valor[1:].partition(valor[0])[0]
    return valor.partition(" #")[0].strip()


def trabajos_declarados(texto: str) -> Dict[str, Dict[str, object]]:
    """
    Clave de cada trabajo -> su `name:` y sus `needs:`, sin PyYAML.

    Mismo motivo que en `renovar_imagenes.py`: la guarda tiene que correr donde no hay
    dependencias instaladas, y un `import yaml` que falla allí se confundiría con un
    disparo. Basta con la sangría de dos y cuatro espacios; la suite comprueba que este
    lector y `yaml.safe_load` ven los mismos trabajos, los mismos nombres y las mismas
    dependencias.
    """
    trabajos: Dict[str, Dict[str, object]] = {}
    dentro, actual = False, None
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        if sangria == 0:
            dentro, actual = linea.rstrip() == "jobs:", None
            continue
        if not dentro:
            continue
        if sangria == 2 and linea.rstrip().endswith(":"):
            actual = linea.strip()[:-1]
            trabajos[actual] = {"nombre": actual, "necesita": []}
        elif sangria == 4 and actual is not None:
            clave, _, valor = linea.strip().partition(":")
            valor = valor.strip()
            if clave == "name" and valor:
                trabajos[actual]["nombre"] = _escalar(valor)
            elif clave == "needs" and valor:
                trabajos[actual]["necesita"] = [
                    uno.strip() for uno in valor.strip("[] ").split(",") if uno.strip()
                ]
    return trabajos


def pasos_declarados(texto: str) -> List[Tuple[str, str, str]]:
    """
    Cada paso, con el trabajo al que pertenece y su condición si la tiene.

    Un paso se abre con cualquier `- ` y no solo con `- name:`: hay doce declarados como
    `- uses: actions/...` sin nombre, y la primera versión de este lector los saltaba. Una
    condición escrita en uno de ellos se habría atribuido al paso anterior —o se habría
    perdido, si era el primero del trabajo—, que es la forma de medir bien sobre el
    inventario equivocado. Al que no tiene nombre se le llama por su acción.
    """
    pasos: List[List[str]] = []
    dentro, trabajo = False, None
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        if sangria == 0:
            dentro, trabajo = linea.rstrip() == "jobs:", None
            continue
        if not dentro:
            continue
        if sangria == 2 and linea.rstrip().endswith(":"):
            trabajo = linea.strip()[:-1]
        elif sangria == 6 and linea.strip().startswith("- ") and trabajo:
            clave, _, valor = linea.strip()[2:].partition(":")
            nombre = _escalar(valor) if clave in ("name", "uses") else ""
            pasos.append([trabajo, nombre, ""])
        elif sangria == 8 and pasos and trabajo == pasos[-1][0]:
            clave, _, valor = linea.strip().partition(":")
            if clave == "name" and valor.strip():
                pasos[-1][1] = _escalar(valor)
            elif clave == "if" and valor.strip():
                pasos[-1][2] = _escalar(valor)
    return [(trabajo, nombre, condicion) for trabajo, nombre, condicion in pasos]


def documentos_vivos() -> List[pathlib.Path]:
    return sorted(
        ruta
        for ruta in list(RAIZ.glob("*.md")) + list(RAIZ.glob("docs/*.md")) + [RAIZ / "docs/compile_reports.py"]
        if ruta.name != COMPILADA and ruta.exists()
    )


def cifras_documentadas() -> List[Tuple[str, int, int]]:
    """Cada sitio vivo que dice cuántos trabajos tiene el CI: ruta, línea y cifra."""
    encontradas: List[Tuple[str, int, int]] = []
    for ruta in documentos_vivos():
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
            if FILA_DE_OBSERVACION.match(linea):
                continue
            for escrita in CIFRA_DE_TRABAJOS.findall(linea):
                cifra = PALABRAS.get(escrita.lower()) if not escrita.isdigit() else int(escrita)
                if cifra is not None:
                    encontradas.append((ruta.relative_to(RAIZ).as_posix(), numero, cifra))
    return encontradas


def problemas_del_flujo(texto: str, cifras: List[Tuple[str, int, int]]) -> List[str]:
    """
    Lo que se comprueba sin red: la premisa de esta guarda y la cifra que dan los documentos.

    Recibe el texto y las cifras en lugar de leerlos: así el arnés puede volver a escribir
    cada defecto —un flujo sin trabajos, un `needs` a un trabajo que no existe, un paso que
    puede saltarse por su cuenta— sin tocar el árbol.
    """
    problemas: List[str] = []
    trabajos = trabajos_declarados(texto)

    if not trabajos:
        problemas.append(
            f"`{FLUJO}` no declara ningún trabajo. Es el síntoma de un flujo roto —una "
            "interpolación de Actions escrita dentro de un comentario ya lo dejó así una vez—, "
            "y GitHub lo presenta como una ejecución de cero trabajos."
        )
        return problemas

    for clave, trabajo in trabajos.items():
        for necesita in trabajo["necesita"]:
            if necesita not in trabajos:
                problemas.append(
                    f"el trabajo `{clave}` depende de `{necesita}`, que no existe: no correría nunca."
                )
    nombres = [str(trabajo["nombre"]) for trabajo in trabajos.values()]
    repetidos = {nombre for nombre in nombres if nombres.count(nombre) > 1}
    if repetidos:
        problemas.append(
            f"dos trabajos comparten nombre ({', '.join(sorted(repetidos))}): la respuesta de "
            "GitHub viene por nombre, y con uno repetido no se puede saber cuál corrió."
        )

    condicionales = [
        (trabajo, paso, condicion)
        for trabajo, paso, condicion in pasos_declarados(texto)
        if condicion and condicion != "always()"
    ]
    for trabajo, paso, condicion in condicionales:
        problemas.append(
            f"`{trabajo}` declara el paso «{paso}» con la condición `{condicion}`. Esta guarda "
            "da por hecho que un paso saltado es un paso tapado por el anterior, y con una "
            "condición que no es `always()` eso deja de ser cierto: hay que venir a decidir "
            "aquí si ese paso puede saltarse."
        )

    for ruta, linea, cifra in [uno for uno in cifras if uno[2] != len(trabajos)]:
        problemas.append(
            f"{ruta}:{linea} dice {cifra} trabajos y `{FLUJO}` declara {len(trabajos)}."
        )
    if not cifras:
        problemas.append(
            "ningún documento vivo dice cuántos trabajos tiene el CI: la cifra dejó de estar "
            "escrita y esta comprobación se quedó sin nada que cotejar."
        )
    return problemas


# --------------------------------------------------------------------- preguntar a GitHub
def preguntar_a_github(argumentos: List[str]) -> object:
    orden = ["gh"] + argumentos
    # La orden la escribe esta guarda, va como lista y sin shell de por medio; lo único que
    # viene de fuera es el número de ejecución, y `gh` lo rechaza si no es uno.
    try:
        hecho = subprocess.run(  # noqa: S603
            orden, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        raise SinVeredicto(
            "no está instalado `gh` (GitHub CLI), que es con lo que se pregunta el veredicto. "
            "Sin él esta guarda no puede mirar, y no mirar no es estar verde."
        ) from None
    if hecho.returncode != 0:
        detalle = (hecho.stderr or hecho.stdout or "").strip().splitlines()
        raise SinVeredicto(
            f"`{' '.join(orden)}` salió con {hecho.returncode}: "
            f"{detalle[0] if detalle else 'sin mensaje'}"
        )
    try:
        return json.loads(hecho.stdout)
    except json.JSONDecodeError as exc:
        raise SinVeredicto(f"`{' '.join(orden)}` no contestó JSON: {exc}") from exc


def _git(*argumentos: str) -> str:
    hecho = subprocess.run(  # noqa: S603
        ["git", *argumentos],  # noqa: S607
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return hecho.stdout.strip() if hecho.returncode == 0 else ""


def elegir_ejecucion(preguntar: Callable[[List[str]], object], de_la_rama: bool) -> object:
    """
    La última ejecución **de este flujo**, y la de HEAD salvo que se pida la de la rama.

    El filtro por archivo no es un detalle: sin él «la última ejecución» puede ser una de
    `Dependabot Updates`, que tiene un trabajo y sale verde.
    """
    ejecuciones = preguntar([
        "run", "list", "--workflow", FLUJO, "--limit", "30",
        "--json", "databaseId,headSha,status,conclusion,event",
    ])
    if not isinstance(ejecuciones, list) or not ejecuciones:
        raise SinVeredicto(f"GitHub no tiene ninguna ejecución de `{FLUJO}`.")
    if de_la_rama:
        return ejecuciones[0]

    cabeza = _git("rev-parse", "HEAD")
    if not cabeza:
        raise SinVeredicto("no se pudo leer el commit de HEAD con `git rev-parse`.")
    for ejecucion in ejecuciones:
        if ejecucion.get("headSha") == cabeza:
            return ejecucion

    por_delante = _git("rev-list", "--count", "@{u}..HEAD")
    if por_delante and por_delante != "0":
        raise SinVeredicto(
            f"HEAD ({cabeza[:7]}) no está empujado: va {por_delante} confirmación(es) por "
            "delante del remoto, así que todavía no hay nada que vigilar. Súbelo y vuelve."
        )
    return {"sinEjecucion": cabeza}


def problemas_de_la_ejecucion(trabajos: Dict[str, Dict[str, object]], ejecucion: dict) -> List[str]:
    """Lo que tiene que cumplir una ejecución terminada: verde, completa y sin pasos tapados."""
    problemas: List[str] = []
    esperados = {str(trabajo["nombre"]) for trabajo in trabajos.values()}
    presentes = {str(uno.get("name")): uno for uno in (ejecucion.get("jobs") or [])}

    if ejecucion.get("conclusion") != VERDE:
        problemas.append(
            f"la ejecución {ejecucion.get('databaseId')} terminó en "
            f"«{ejecucion.get('conclusion')}», no en verde."
        )

    for nombre in sorted(esperados):
        trabajo = presentes.get(nombre)
        if trabajo is None:
            problemas.append(
                f"el trabajo «{nombre}» está declarado en `{FLUJO}` y no aparece en la "
                "ejecución: no corrió, y lo que fuera a comprobar sigue sin comprobarse."
            )
            continue
        veredicto = trabajo.get("conclusion")
        if veredicto in SIN_VEREDICTO:
            problemas.append(
                f"«{nombre}» quedó en «{veredicto or 'sin nada'}»: sin veredicto. Es lo que "
                "pasa cuando algo de lo que depende se pone en rojo, y es la mitad del punto "
                "68 que cuesta ver —el trabajo no sale rojo, sale como si no existiera—."
            )
        elif veredicto != VERDE:
            problemas.append(f"«{nombre}» terminó en «{veredicto}».")

    for nombre in sorted(set(presentes) - esperados):
        problemas.append(
            f"la ejecución trae el trabajo «{nombre}», que `{FLUJO}` no declara: el flujo que "
            "corrió no es el del árbol."
        )

    for nombre, trabajo in sorted(presentes.items()):
        for paso in trabajo.get("steps") or []:
            if paso.get("conclusion") in SIN_VEREDICTO:
                problemas.append(
                    f"«{nombre}» dejó el paso «{paso.get('name')}» en "
                    f"«{paso.get('conclusion') or 'sin nada'}»: un paso en rojo deja sin "
                    "correr a los de detrás, y hasta que no queda uno no se sabe cuántos son."
                )
            elif paso.get("conclusion") != VERDE:
                problemas.append(f"«{nombre}», paso «{paso.get('name')}»: {paso.get('conclusion')}.")
    return problemas


# --------------------------------------------------------------------- orden
def main(argv=None, preguntar: Callable[[List[str]], object] = preguntar_a_github) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sin-red", action="store_true", help="Solo lo que se lee en el árbol.")
    parser.add_argument("--rama", action="store_true", help="La última de la rama, no la de HEAD.")
    parser.add_argument("--ejecucion", metavar="ID", help="El número de una ejecución concreta.")
    args = parser.parse_args(argv)

    texto = (RAIZ / FLUJO).read_text(encoding="utf-8")
    cifras = cifras_documentadas()
    trabajos = trabajos_declarados(texto)
    problemas = problemas_del_flujo(texto, cifras)
    print(f"`{FLUJO}` declara {len(trabajos)} trabajo(s), y {len(cifras)} sitio(s) vivo(s) lo repiten.")

    if args.sin_red:
        for problema in problemas:
            print(f"FALLO: {problema}")
        if problemas:
            return 1
        print("Flujo coherente: cada dependencia existe, ningún paso puede saltarse por su cuenta y los documentos dan la misma cifra.")
        return 0

    try:
        elegida = (
            {"databaseId": int(args.ejecucion)} if args.ejecucion
            else elegir_ejecucion(preguntar, args.rama)
        )
        if "sinEjecucion" in elegida:
            problemas.append(
                f"el commit {elegida['sinEjecucion'][:7]} está en el remoto y no tiene ninguna "
                f"ejecución de `{FLUJO}`: el flujo no disparó."
            )
        else:
            numero = elegida["databaseId"]
            ejecucion = preguntar([
                "run", "view", str(numero),
                "--json", "databaseId,headSha,status,conclusion,url,workflowName,jobs",
            ])
            print(f"Ejecución {numero} sobre {str(ejecucion.get('headSha'))[:7]}: {ejecucion.get('url')}")
            if ejecucion.get("status") != "completed":
                en_vuelo = [
                    str(uno.get("name")) for uno in (ejecucion.get("jobs") or [])
                    if uno.get("status") != "completed"
                ]
                raise SinVeredicto(
                    f"la ejecución {numero} sigue en «{ejecucion.get('status')}»"
                    + (f"; falta(n): {', '.join(en_vuelo)}" if en_vuelo else "")
                )
            if ejecucion.get("conclusion") == "cancelled":
                raise SinVeredicto(
                    f"la ejecución {numero} está cancelada, que no es un veredicto: la paró "
                    "alguien, o la relevó otra del mismo `concurrency`. No dice que el árbol "
                    "esté bien ni que esté mal."
                )
            problemas += problemas_de_la_ejecucion(trabajos, ejecucion)
    except SinVeredicto as motivo:
        for problema in problemas:
            print(f"FALLO: {problema}")
        print(f"SIN VEREDICTO: {motivo}")
        return 2

    for problema in problemas:
        print(f"FALLO: {problema}")
    if problemas:
        print(f"\nEl CI no está verde, y ahora está escrito aquí: {len(problemas)} cosa(s).")
        return 1
    print(f"Los {len(trabajos)} trabajos corrieron y los {len(trabajos)} están en verde, con todos sus pasos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
