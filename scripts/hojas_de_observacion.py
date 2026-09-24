"""
Las hojas de observación de la prueba con personas: crearlas, y leerlas de vuelta.

    python scripts/hojas_de_observacion.py crear          # antes de la sesión
    python scripts/hojas_de_observacion.py leer           # después

Por qué existe
--------------
El Reporte 25 prometía «una versión rellenable con cronómetro por tarea que Claude puede
leer de vuelta» y esa versión **nunca se construyó**: lo único que había era la tabla de
`docs/Prueba_Con_Personas.md`, que se lee bien pero no se rellena mientras miras a alguien
ni se vuelve a leer después sin transcribirla a mano. Una hoja que no se puede rellenar en
caliente acaba rellenándose de memoria al final del día, y lo que se anota de memoria es lo
que uno recuerda, no lo que pasó.

`crear` deja una hoja por papel en `docs/hojas_de_observacion/`, con **las tareas de verdad
ya escritas** —salen de `Prueba_Con_Personas.md`, no de una copia que se desincroniza— y un
hueco por campo. `leer` las recoge, arma la tabla de vaciado y dice si el criterio «nadie se
atasca» se cumple.

Quién decide el tipo
--------------------
Lo decide **quien conduce**, en el campo `Tipo` de cada tarea. Este programa no lo adivina a
partir de los segundos ni de las palabras: un «no» de la columna «¿Sola?» puede ser un
atasco o una pista pequeña, y la diferencia solo la sabe quien estaba delante. Aquí se
suman, no se interpretan.

El veredicto
------------
«Nadie se atasca» se cumple cuando hay hojas de los cuatro papeles y ninguna tarea quedó
marcada como `atasco`. Sin hojas **no hay veredicto**, y eso no es un fallo del programa: es
la respuesta correcta a una pregunta que nadie ha medido todavía.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GUION = RAIZ / "docs" / "Prueba_Con_Personas.md"
CARPETA = RAIZ / "docs" / "hojas_de_observacion"

# Los cuatro papeles, con el encabezado con el que aparecen en el guion.
PAPELES = {
    "marketing": "### A. Marketing",
    "interesado": "### B. Interesado",
    "lider": "### C. Líder",
    "asesor": "### D. Asesor",
}

TIPOS = ("atasco", "duda", "falta")
SIN_RELLENAR = ""

# Los campos de cada tarea, en el orden en que se rellenan mirando a alguien: primero lo que
# se ve (¿lo hizo sola?, cuánto tardó) y después lo que hay que escribir con palabras.
CAMPOS = ("Sola", "Segundos", "Dónde dudó", "Qué hubo que decirle", "Tipo")


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    ).lower()


def tareas_del_guion(papel: str) -> list:
    """
    Las tareas de un papel, leídas del guion.

    Se leen de ahí y no de una lista escrita aquí porque el guion cambia —acaba de cambiar
    con los capítulos 27 y 28— y dos listas que tienen que decir lo mismo acaban diciendo
    cosas distintas sin que nadie se entere.
    """
    texto = GUION.read_text(encoding="utf-8")
    encabezado = PAPELES[papel]
    if encabezado not in texto:
        raise SystemExit(f"No encuentro «{encabezado}» en {GUION.name}.")

    desde = texto.index(encabezado)
    # Hasta el siguiente encabezado del mismo nivel, o hasta el final de la sección.
    resto = texto[desde + len(encabezado):]
    corte = min(
        (resto.index(m) for m in ("\n### ", "\n---") if m in resto),
        default=len(resto),
    )
    bloque = resto[:corte]

    tareas = []
    for linea in bloque.splitlines():
        m = re.match(r"^(\d+)\.\s+(.*)$", linea)
        if m:
            tareas.append(m.group(2))
        elif tareas and linea.startswith("   ") and linea.strip():
            # Continuación de la tarea anterior. Sin esto, una tarea de tres renglones
            # —y las hay desde el capítulo 28— llegaba a la hoja cortada por la mitad,
            # que es peor que no llevarla: quien conduce leería media instrucción.
            tareas[-1] += " " + linea.strip()
        elif not linea.strip():
            continue
        elif linea.startswith(">"):
            # Las notas para quien conduce no son tareas de nadie.
            continue

    # El texto se guarda en una línea: la hoja se lee en papel o en pantalla estrecha.
    tareas = [re.sub(r"\s+", " ", t).strip() for t in tareas]
    if not tareas:
        raise SystemExit(f"El papel «{papel}» no tiene tareas numeradas en el guion.")
    return tareas


def plantilla(papel: str) -> str:
    tareas = tareas_del_guion(papel)
    lineas = [
        f"# Hoja de observación — {papel.capitalize()}",
        "",
        "Rellenar **durante** la sesión, no al final. Quien conduce escribe; la persona no.",
        "",
        "«Sola» es `S` solo si nadie le dijo nada: una pista pequeña ya es `N`.",
        "«Tipo» lo decide quien conduce, y solo si hubo algo que anotar:",
        "`atasco` (no lo consigue sin ayuda), `duda` (lo consigue pero se para),",
        "`falta` (quiere algo que el sistema no hace). Si fue bien, se deja vacío.",
        "",
        f"Persona: {SIN_RELLENAR}",
        f"Papel: {papel}",
        f"Fecha: {SIN_RELLENAR}",
        f"Aparato: {SIN_RELLENAR}",
        f"Navegador: {SIN_RELLENAR}",
        "",
    ]
    for i, tarea in enumerate(tareas, 1):
        lineas += [f"## Tarea {i}. {tarea}", ""]
        lineas += [f"{campo}: {SIN_RELLENAR}" for campo in CAMPOS]
        lineas.append("")
    lineas += [
        "## Al terminar",
        "",
        "¿Qué pensaste que iba a pasar y no pasó?: ",
        "¿Qué palabra de la pantalla no significaba lo que creías?: ",
        "Si esto fuera tu trabajo de mañana, ¿qué te faltaría?: ",
        "",
    ]
    return "\n".join(lineas)


def crear(forzar: bool) -> int:
    CARPETA.mkdir(parents=True, exist_ok=True)
    escritas, saltadas = 0, 0
    for papel in PAPELES:
        destino = CARPETA / f"{papel}.md"
        # Una hoja ya rellenada no se pisa nunca sin decirlo: son datos que no se repiten.
        if destino.exists() and not forzar:
            print(f"  ya existe, no la toco: {destino.name}")
            saltadas += 1
            continue
        destino.write_text(plantilla(papel), encoding="utf-8")
        print(f"  escrita: {destino.name}")
        escritas += 1
    print(f"\n{escritas} hojas escritas, {saltadas} respetadas, en {CARPETA}.")
    if saltadas and not forzar:
        print("Use --forzar para rehacerlas (se pierde lo que tengan escrito).")
    return 0


# --------------------------------------------------------------------------- leer
def _campos(bloque: str) -> dict:
    datos = {}
    for linea in bloque.splitlines():
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        datos[_sin_acentos(clave.strip().lstrip("#").strip())] = valor.strip()
    return datos


def leer_hoja(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    partes = re.split(r"^## ", texto, flags=re.M)
    cabecera = _campos(partes[0])

    tareas = []
    for parte in partes[1:]:
        m = re.match(r"Tarea (\d+)\.\s*(.*)", parte)
        if not m:
            continue
        datos = _campos(parte)
        tareas.append({
            "numero": int(m.group(1)),
            "texto": m.group(2).strip(),
            "sola": datos.get("sola", ""),
            "segundos": datos.get("segundos", ""),
            "dudo": datos.get("donde dudo", ""),
            "dijo": datos.get("que hubo que decirle", ""),
            "tipo": _sin_acentos(datos.get("tipo", "")),
        })
    return {
        "fichero": ruta.name,
        "papel": cabecera.get("papel", ruta.stem),
        "persona": cabecera.get("persona", ""),
        "fecha": cabecera.get("fecha", ""),
        "tareas": tareas,
    }


def esta_rellenada(hoja: dict) -> bool:
    """
    Una hoja cuenta si tiene persona y al menos una tarea contestada.

    Sin nombre no se sabe de quién es ni si dos hojas son de la misma persona; sin ninguna
    tarea contestada es la plantilla, no una observación.
    """
    if not hoja["persona"]:
        return False
    return any(t["sola"] for t in hoja["tareas"])


def leer() -> int:
    if not CARPETA.exists():
        print(f"No existe {CARPETA}.")
        print("La sesión con personas no se ha celebrado, o las hojas están en otro sitio.")
        print("Cree las hojas con:  python scripts/hojas_de_observacion.py crear")
        return 2

    hojas = [leer_hoja(p) for p in sorted(CARPETA.glob("*.md"))]
    rellenadas = [h for h in hojas if esta_rellenada(h)]

    print(f"Hojas encontradas: {len(hojas)}. Rellenadas: {len(rellenadas)}.\n")

    if not rellenadas:
        print("=" * 70)
        print("SIN DATOS. El criterio «nadie se atasca» NO se da por cumplido.")
        print("=" * 70)
        print("No es un fallo: es la respuesta correcta mientras nadie se haya sentado")
        print("delante. Un criterio que habla de personas solo lo cumplen personas.")
        return 2

    # --------------------------------------------------------------- el vaciado
    notas = []
    for hoja in rellenadas:
        for t in hoja["tareas"]:
            if t["tipo"] in TIPOS:
                notas.append((hoja, t))

    if notas:
        print("| Nº | Papel | Tarea | Qué pasó | Tipo |")
        print("| :-: | :--- | :-: | :--- | :--- |")
        for i, (hoja, t) in enumerate(notas, 1):
            que = t["dudo"] or t["dijo"] or "(sin describir)"
            print(f"| {i} | {hoja['papel']} | {t['numero']} | {que} | {t['tipo']} |")
        print()

    atascos = [(h, t) for h, t in notas if t["tipo"] == "atasco"]
    confunden = [(h, t) for h, t in notas if t["tipo"] == "duda"]
    ideas = [(h, t) for h, t in notas if t["tipo"] == "falta"]
    papeles = {h["papel"] for h in rellenadas}
    faltan = set(PAPELES) - papeles

    print(f"Atascos: {len(atascos)}  ·  Dudas: {len(confunden)}  ·  Ideas: {len(ideas)}")
    print(f"Papeles observados: {', '.join(sorted(papeles)) or 'ninguno'}")
    if faltan:
        print(f"Papeles sin observar: {', '.join(sorted(faltan))}")
    print()

    # --------------------------------------------------------------- el veredicto
    print("=" * 70)
    if atascos:
        print(f"NO cumplido: {len(atascos)} atasco(s). Se corrigen y se repite la sesión.")
        print("=" * 70)
        for hoja, t in atascos:
            print(f"  · {hoja['papel']}, tarea {t['numero']}: {t['dudo'] or t['dijo']}")
        return 1
    if faltan:
        print("Sin veredicto: faltan papeles por observar.")
        print("=" * 70)
        print("Los cuatro papeles se recorren entre todos; el atasco de uno para a los que")
        print("vienen detrás, así que tres de cuatro no contestan la pregunta.")
        return 2
    print("CUMPLIDO: nadie se atascó en ninguna tarea, con los cuatro papeles observados.")
    print("=" * 70)
    if confunden:
        print(f"Quedan {len(confunden)} duda(s) por corregir: no bloquean, pero confunden.")
    if ideas:
        print(f"Y {len(ideas)} idea(s) para después, que no se implementan en esta fase.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="orden", required=True)
    p_crear = sub.add_parser("crear", help="Deja una hoja en blanco por papel.")
    p_crear.add_argument(
        "--forzar", action="store_true",
        help="Rehace las hojas que ya existan, perdiendo lo que tengan escrito.",
    )
    sub.add_parser("leer", help="Lee las hojas rellenadas y dicta el veredicto.")
    args = parser.parse_args()

    if args.orden == "crear":
        return crear(args.forzar)
    return leer()


if __name__ == "__main__":
    sys.exit(main())
