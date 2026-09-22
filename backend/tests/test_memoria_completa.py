"""
Cada reporte está en la memoria, y entró por el compilador.

Los capítulos 22 a 24 se pegaron a mano en `Memoria_Tecnica_Final_Lead_Scoring.md` sin pasar
por `docs/compile_reports.py`: salieron sin su ancla, así que sus entradas del índice no
llevaban a ninguna parte, y la siguiente regeneración los habría borrado sin avisar. Esta
prueba falla si un reporte existe y el compilador no lo lista, o si la memoria no tiene el
capítulo con su ancla.
"""
import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"


def _compilador():
    spec = importlib.util.spec_from_file_location("compile_reports_bajo_prueba", DOCS / "compile_reports.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_compilador_lista_todos_los_reportes_en_orden():
    compilador = _compilador()
    en_disco = sorted(p.name for p in (DOCS / "reportes").glob("Reporte_[0-9][0-9]_*.md"))
    listados = [nombre for nombre, _ in compilador.REPORT_FILES]

    assert listados == en_disco


def test_la_memoria_tiene_cada_capitulo_con_su_ancla():
    compilador = _compilador()
    memoria = (DOCS / "Memoria_Tecnica_Final_Lead_Scoring.md").read_text(encoding="utf-8")

    for numero, (_, titulo) in enumerate(compilador.REPORT_FILES, 1):
        assert re.search(rf'<a id="capitulo-{numero}-[^"]+"></a>\s+# {re.escape(titulo.upper())}', memoria), (
            f"Falta el capítulo {numero} con su ancla. Regenere con: python docs/compile_reports.py"
        )
