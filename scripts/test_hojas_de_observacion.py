"""
Pruebas del lector de hojas de observación.

Por qué las lleva: este programa es el que dicta si el criterio «nadie se atasca» se cumple,
y un lector equivocado diría «cumplido» sin que nadie lo notara. Un veredicto que nadie
comprueba vale lo mismo que no tenerlo.

Lo que se comprueba:

1. Las hojas salen del guion, con las tareas enteras.
2. Una plantilla vacía no cuenta como observación.
3. Un atasco tumba el veredicto; una duda, no.
4. Tres papeles de cuatro no dan veredicto.
5. Los cuatro papeles sin atascos sí lo dan.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hojas_de_observacion as hojas  # noqa: E402

PAPELES = ("marketing", "interesado", "lider", "asesor")


def _hoja(tmp_path: Path, papel: str, tareas, persona="Ana Ruiz") -> Path:
    """Escribe una hoja como la rellenaría quien conduce."""
    lineas = [f"# Hoja de observación — {papel}", "", f"Persona: {persona}",
              f"Papel: {papel}", "Fecha: 2026-09-24", "Aparato: portátil",
              "Navegador: Firefox", ""]
    for i, (sola, segundos, dudo, dijo, tipo) in enumerate(tareas, 1):
        lineas += [
            f"## Tarea {i}. Lo que fuera", "",
            f"Sola: {sola}", f"Segundos: {segundos}", f"Dónde dudó: {dudo}",
            f"Qué hubo que decirle: {dijo}", f"Tipo: {tipo}", "",
        ]
    destino = tmp_path / f"{papel}.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


BIEN = [("S", "12", "", "", "")]
CON_DUDA = [("N", "40", "no sabía si se había guardado", "le dije que mirara arriba", "duda")]
CON_ATASCO = [("N", "180", "no encontró la bandeja", "le señalé la pestaña", "atasco")]


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(hojas, "CARPETA", tmp_path)
    return tmp_path


# --------------------------------------------------------------------- 1. del guion
@pytest.mark.parametrize("papel", PAPELES)
def test_cada_papel_saca_sus_tareas_del_guion(papel):
    tareas = hojas.tareas_del_guion(papel)
    assert tareas, f"{papel} se quedó sin tareas"
    # Las notas para quien conduce empiezan por «>» y no son tareas de nadie.
    assert not any(t.startswith(">") for t in tareas)


def test_las_tareas_de_varias_lineas_llegan_enteras():
    """
    Una tarea cortada por la mitad es peor que no llevarla: quien conduce leería media
    instrucción y la persona haría media tarea.
    """
    asesor = hojas.tareas_del_guion("asesor")
    primera = asesor[0]
    assert "di en voz alta" in primera, primera
    assert primera.endswith("."), primera


def test_la_plantilla_lleva_un_hueco_por_campo_y_tarea():
    texto = hojas.plantilla("lider")
    cuantas = len(hojas.tareas_del_guion("lider"))
    for campo in hojas.CAMPOS:
        assert texto.count(f"{campo}: ") == cuantas


# --------------------------------------------------------- 2. la plantilla no cuenta
def test_una_plantilla_recien_creada_no_es_una_observacion(carpeta):
    hojas.crear(forzar=True)
    assert hojas.leer() == 2, "una plantilla vacía no puede dar veredicto"


def test_una_hoja_sin_nombre_no_cuenta(carpeta):
    _hoja(carpeta, "asesor", BIEN, persona="")
    assert hojas.leer() == 2


# ------------------------------------------------------------------- 3. el veredicto
def test_un_atasco_tumba_el_veredicto(carpeta):
    for papel in PAPELES:
        _hoja(carpeta, papel, BIEN)
    _hoja(carpeta, "asesor", CON_ATASCO)
    assert hojas.leer() == 1


def test_una_duda_no_tumba_el_veredicto(carpeta):
    """«Nadie se atasca» habla de atascos. Las dudas se corrigen, pero no bloquean."""
    for papel in PAPELES:
        _hoja(carpeta, papel, BIEN)
    _hoja(carpeta, "lider", CON_DUDA)
    assert hojas.leer() == 0


# ---------------------------------------------------------------- 4. los cuatro papeles
def test_tres_papeles_de_cuatro_no_dan_veredicto(carpeta):
    """
    Los cuatro papeles se recorren entre todos: el atasco de uno para a los que vienen
    detrás, así que tres de cuatro no contestan la pregunta.
    """
    for papel in PAPELES[:3]:
        _hoja(carpeta, papel, BIEN)
    assert hojas.leer() == 2


def test_los_cuatro_papeles_sin_atascos_lo_dan(carpeta):
    for papel in PAPELES:
        _hoja(carpeta, papel, BIEN)
    assert hojas.leer() == 0


# ------------------------------------------------------------------- 5. no pisar datos
def test_crear_no_pisa_una_hoja_rellenada(carpeta):
    rellenada = _hoja(carpeta, "asesor", CON_DUDA)
    antes = rellenada.read_text(encoding="utf-8")

    hojas.crear(forzar=False)

    assert rellenada.read_text(encoding="utf-8") == antes, "se perdió una observación"


def test_sin_carpeta_no_hay_veredicto(tmp_path, monkeypatch):
    monkeypatch.setattr(hojas, "CARPETA", tmp_path / "no-existe")
    assert hojas.leer() == 2
