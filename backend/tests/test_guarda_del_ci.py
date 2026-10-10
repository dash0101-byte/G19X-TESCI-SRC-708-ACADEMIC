"""
§6.4 punto 68: el CI llevaba rojo desde antes de aquel trabajo y nada en el árbol lo decía.

La guarda es `scripts/guarda_del_ci.py`. Aquí se comprueban las dos cosas que una guarda
necesita para existir: que **mide bien** —su lector propio ve lo mismo que PyYAML, y el
repositorio tal como está sale limpio— y que **se puede poner en rojo**, volviendo a escribir
cada defecto uno a uno. Los casos de ejecución no se inventan: son la forma exacta que
contestó GitHub en ejecuciones reales, con su número al lado para poder volver a medirlas.

Lo que no se prueba aquí y es a propósito: la mitad que pregunta a GitHub necesita red y
sesión, así que `preguntar` se inyecta —como `consultar` en `renovar_imagenes.py`—. Que la
guarda **no se calle en verde** cuando no puede mirar es lo que más importa de esta tanda, y
eso sí se prueba: tres formas de no poder mirar y las tres salen con 2.
"""
import importlib.util
import pathlib

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("guarda_del_ci", RAIZ / "scripts" / "guarda_del_ci.py")
guarda = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guarda)

FLUJO = (RAIZ / guarda.FLUJO).read_text(encoding="utf-8")
TRABAJOS = guarda.trabajos_declarados(FLUJO)
CIFRAS = guarda.cifras_documentadas()


def _necesita(trabajo: dict) -> list:
    valor = trabajo.get("needs") or []
    return [valor] if isinstance(valor, str) else list(valor)


def _ejecucion(trabajos, conclusion="success", status="completed", numero=1):
    """La forma con la que contesta `gh run view --json ...`, con lo que esta guarda mira."""
    return {
        "databaseId": numero,
        "headSha": "0" * 40,
        "status": status,
        "conclusion": conclusion,
        "url": "https://example.invalid/runs/1",
        "workflowName": "CI - Sistema Inteligente de Lead Scoring",
        "jobs": [
            {
                "name": nombre,
                "status": "completed",
                "conclusion": veredicto,
                "steps": [{"name": paso, "conclusion": suyo} for paso, suyo in pasos],
            }
            for nombre, veredicto, pasos in trabajos
        ],
    }


def _los_diez_en_verde():
    return [(str(trabajo["nombre"]), "success", [("Set up job", "success")]) for trabajo in TRABAJOS.values()]


# --------------------------------------------------------------- mide lo que dice medir
def test_el_lector_del_flujo_ve_los_mismos_trabajos_que_yaml():
    """El lector propio existe para no depender de PyYAML; no puede ver otro pipeline."""
    esperado = {
        clave: (trabajo.get("name", clave), _necesita(trabajo))
        for clave, trabajo in yaml.safe_load(FLUJO)["jobs"].items()
    }
    assert {clave: (t["nombre"], t["necesita"]) for clave, t in TRABAJOS.items()} == esperado


def test_el_lector_ve_los_mismos_pasos_y_las_mismas_condiciones_que_yaml():
    esperado = [
        (clave, str(paso.get("name") or paso.get("uses") or ""), str(paso.get("if") or ""))
        for clave, trabajo in yaml.safe_load(FLUJO)["jobs"].items()
        for paso in trabajo.get("steps") or []
    ]
    assert guarda.pasos_declarados(FLUJO) == esperado


def test_un_paso_sin_nombre_se_cuenta_igual_por_su_accion():
    """La primera versión del lector solo abría paso con `- name:`, y hay pasos sin nombre."""
    sin_nombre = [
        paso for trabajo in yaml.safe_load(FLUJO)["jobs"].values()
        for paso in trabajo.get("steps") or [] if "name" not in paso
    ]
    assert sin_nombre, "si todos los pasos llevaran nombre, esta prueba no mediría nada"
    assert len(guarda.pasos_declarados(FLUJO)) == sum(
        len(trabajo.get("steps") or []) for trabajo in yaml.safe_load(FLUJO)["jobs"].values()
    )


def test_el_comentario_de_al_lado_no_entra_en_el_valor():
    """`- uses: actions/checkout@abc # v4.4.0`: la versión va en un comentario, no en el nombre."""
    assert guarda._escalar("actions/checkout@abc # v4.4.0") == "actions/checkout@abc"
    assert guarda._escalar(" 'con # dentro' ") == "con # dentro"
    assert not any("#" in nombre for _, nombre, _ in guarda.pasos_declarados(FLUJO))


# --------------------------------------------------------------- el árbol tal como está
def test_el_repositorio_pasa_la_mitad_que_no_necesita_red():
    assert guarda.problemas_del_flujo(FLUJO, CIFRAS) == []
    assert guarda.main(["--sin-red"]) == 0


def test_los_documentos_vivos_repiten_la_cifra_que_declara_el_flujo():
    assert CIFRAS, "la cifra dejó de estar escrita y no hay nada que cotejar"
    assert {cifra for _, _, cifra in CIFRAS} == {len(TRABAJOS)}


def test_las_filas_de_observacion_no_cuentan_como_cifra():
    """§6.4 guarda veredictos con fecha —«diez de diez trabajos»— y el pasado no se reescribe."""
    documento = RAIZ / "docs" / "Congelacion_y_Trabajo_Futuro.md"
    filas = [
        numero
        for numero, linea in enumerate(documento.read_text(encoding="utf-8").splitlines(), start=1)
        if guarda.FILA_DE_OBSERVACION.match(linea) and guarda.CIFRA_DE_TRABAJOS.search(linea)
    ]
    assert filas, "ninguna fila de §6.4 da una cifra de trabajos: la prueba no mediría nada"
    vistas = {(ruta, numero) for ruta, numero, _ in CIFRAS}
    assert not [n for n in filas if (documento.relative_to(RAIZ).as_posix(), n) in vistas]


def test_el_registro_compilado_queda_fuera_de_los_documentos_vivos():
    rutas = {ruta.relative_to(RAIZ).as_posix() for ruta in guarda.documentos_vivos()}
    assert "AGENTS.md" in rutas and "docs/compile_reports.py" in rutas
    assert not [ruta for ruta in rutas if "reportes/" in ruta or "docs_residencias" in ruta]
    assert f"docs/{guarda.COMPILADA}" not in rutas


# --------------------------------------------------------------- arnés: el flujo
def test_un_flujo_sin_trabajos_se_ve():
    """Cero trabajos es el síntoma de un flujo roto, y GitHub lo presenta como una ejecución."""
    problemas = guarda.problemas_del_flujo("name: CI\non:\n  push:\n", CIFRAS)
    assert len(problemas) == 1 and "no declara ningún trabajo" in problemas[0]


def test_una_dependencia_a_un_trabajo_que_no_existe_se_ve():
    # Con la sangría, y no «needs: modelo» a secas: un comentario del flujo lo menciona, y
    # sustituir ahí no cambia nada —la guarda ignora los comentarios, como debe—.
    declaracion = "\n    needs: modelo\n"
    assert FLUJO.count(declaracion) == 1
    roto = FLUJO.replace(declaracion, "\n    needs: modelo_que_ya_no_existe\n", 1)
    problemas = guarda.problemas_del_flujo(roto, CIFRAS)
    assert any("modelo_que_ya_no_existe" in uno and "no correría nunca" in uno for uno in problemas)


def test_dos_trabajos_con_el_mismo_nombre_se_ven():
    roto = FLUJO.replace("name: Lint (ruff)", "name: Migraciones (Alembic)", 1)
    problemas = guarda.problemas_del_flujo(roto, CIFRAS)
    assert any("comparten nombre" in uno for uno in problemas)


def test_un_paso_que_puede_saltarse_por_su_cuenta_se_ve():
    """Con una condición que no es `always()`, un paso saltado deja de significar «tapado»."""
    roto = FLUJO.replace("        if: always()", "        if: github.event_name == 'push'", 1)
    problemas = guarda.problemas_del_flujo(roto, CIFRAS)
    assert any("github.event_name == 'push'" in uno for uno in problemas)


def test_un_always_no_se_confunde_con_una_condicion():
    assert [uno for _, _, uno in guarda.pasos_declarados(FLUJO) if uno] == ["always()"] * 8
    assert guarda.problemas_del_flujo(FLUJO, CIFRAS) == []


def test_un_documento_que_da_otra_cifra_se_ve():
    problemas = guarda.problemas_del_flujo(FLUJO, [("AGENTS.md", 94, len(TRABAJOS) + 1)])
    assert len(problemas) == 1 and f"declara {len(TRABAJOS)}" in problemas[0]


def test_que_ningun_documento_diga_la_cifra_tambien_se_ve():
    problemas = guarda.problemas_del_flujo(FLUJO, [])
    assert any("ningún documento vivo" in uno for uno in problemas)


# --------------------------------------------------------------- arnés: la ejecución
def test_una_ejecucion_verde_y_completa_no_tiene_problemas():
    assert guarda.problemas_de_la_ejecucion(TRABAJOS, _ejecucion(_los_diez_en_verde())) == []


def test_un_trabajo_en_rojo_se_ve():
    trabajos = _los_diez_en_verde()
    trabajos[0] = (trabajos[0][0], "failure", [("Pruebas del cliente con cobertura", "failure")])
    problemas = guarda.problemas_de_la_ejecucion(TRABAJOS, _ejecucion(trabajos, conclusion="failure"))
    assert any(trabajos[0][0] in uno and "failure" in uno for uno in problemas)


def test_un_trabajo_saltado_se_ve_como_sin_veredicto():
    """Ejecución 37819881196: `Cliente` en rojo dejó «Build de imágenes Docker» en `skipped`."""
    trabajos = [
        (nombre, "failure" if nombre.startswith("Cliente") else "success", [])
        for nombre, _, _ in _los_diez_en_verde()
        if not nombre.startswith("Build de")
    ] + [("Build de imágenes Docker", "skipped", [])]
    problemas = guarda.problemas_de_la_ejecucion(TRABAJOS, _ejecucion(trabajos, conclusion="failure"))
    assert any("Build de imágenes Docker" in uno and "sin veredicto" in uno for uno in problemas)


def test_un_trabajo_declarado_que_no_aparece_se_ve():
    """Ejecución 37722329695: el flujo no disparó y la respuesta vino sin un solo trabajo."""
    problemas = guarda.problemas_de_la_ejecucion(TRABAJOS, _ejecucion([], conclusion="failure"))
    assert len(problemas) == 1 + len(TRABAJOS)
    assert all(
        any(str(trabajo["nombre"]) in uno and "no corrió" in uno for uno in problemas)
        for trabajo in TRABAJOS.values()
    )


def test_un_paso_saltado_dentro_de_un_trabajo_verde_se_ve():
    """Ejecución 37819881196: `Cliente` dejó cinco pasos suyos sin correr, «Publicar el bundle» entre ellos."""
    trabajos = _los_diez_en_verde()
    trabajos[0] = (trabajos[0][0], "success", [("Publicar el bundle", "skipped")])
    problemas = guarda.problemas_de_la_ejecucion(TRABAJOS, _ejecucion(trabajos))
    assert any("Publicar el bundle" in uno for uno in problemas)


def test_un_trabajo_que_el_flujo_no_declara_se_ve():
    """`Dependabot Updates` también deja trabajos: el flujo que corrió no sería el del árbol."""
    problemas = guarda.problemas_de_la_ejecucion(
        TRABAJOS, _ejecucion(_los_diez_en_verde() + [("Dependabot", "success", [])])
    )
    assert any("no declara" in uno for uno in problemas)


def test_el_veredicto_global_rojo_se_ve_aunque_los_diez_salgan_verdes():
    problemas = guarda.problemas_de_la_ejecucion(
        TRABAJOS, _ejecucion(_los_diez_en_verde(), conclusion="failure")
    )
    assert len(problemas) == 1 and "no en verde" in problemas[0]


# --------------------------------------------------------------- lo que no se da por bueno
def test_sin_gh_la_guarda_no_se_calla_en_verde():
    def no_hay_gh(_argumentos):
        raise guarda.SinVeredicto("no está instalado `gh`")

    assert guarda.main(["--ejecucion", "1"], preguntar=no_hay_gh) == 2


def test_una_ejecucion_en_vuelo_no_es_verde():
    def en_vuelo(_argumentos):
        respuesta = _ejecucion(_los_diez_en_verde(), conclusion=None, status="in_progress")
        respuesta["jobs"][-1]["status"] = "in_progress"
        return respuesta

    assert guarda.main(["--ejecucion", "1"], preguntar=en_vuelo) == 2


def test_una_ejecucion_cancelada_no_es_verde():
    assert guarda.main(
        ["--ejecucion", "1"], preguntar=lambda _: _ejecucion(_los_diez_en_verde(), conclusion="cancelled")
    ) == 2


def test_una_ejecucion_verde_y_completa_sale_con_cero():
    assert guarda.main(
        ["--ejecucion", "1"], preguntar=lambda _: _ejecucion(_los_diez_en_verde())
    ) == 0


def test_una_ejecucion_roja_sale_con_uno():
    assert guarda.main(
        ["--ejecucion", "1"], preguntar=lambda _: _ejecucion([], conclusion="failure")
    ) == 1


def test_se_pregunta_filtrando_por_el_archivo_del_flujo():
    """Sin filtrar, «la última ejecución» es cada pocos días una de `Dependabot Updates`:
    un trabajo, verde, y daría por bueno lo que nadie ha comprobado."""
    preguntas = []

    def anotar(argumentos):
        preguntas.append(argumentos)
        return [{"databaseId": 7, "headSha": "a" * 40, "status": "completed", "conclusion": "success"}]

    assert guarda.elegir_ejecucion(anotar, de_la_rama=True)["databaseId"] == 7
    assert "--workflow" in preguntas[0] and guarda.FLUJO in preguntas[0]


def test_sin_ninguna_ejecucion_del_flujo_no_hay_veredicto():
    with pytest.raises(guarda.SinVeredicto):
        guarda.elegir_ejecucion(lambda _: [], de_la_rama=True)
