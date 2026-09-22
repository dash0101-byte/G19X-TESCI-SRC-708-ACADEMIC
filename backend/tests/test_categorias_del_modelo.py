"""
Las listas del formulario público son las que el modelo conoce. Aquí se garantiza.

Esta es la prueba que la regla R-3 del guion pide: un sector escrito de otra forma no
produce ningún error visible, porque el preprocesador está construido con
`OneHotEncoder(handle_unknown="ignore")`. La categoría desconocida se descarta en silencio
y el prospecto se puntúa como si no hubiera dicho a qué se dedica. Sin esta comparación, la
divergencia solo se notaría meses después, mirando por qué el modelo no distingue nada.

Se compara `CATEGORIAS_DEL_MODELO` contra dos referencias distintas:

* el **artefacto servido**, que es lo que de verdad puntúa hoy;
* el **generador del dataset**, que es de donde salen esas categorías al entrenar.
"""
import ast
import os

import joblib
import pytest
from app.core.vector_del_modelo import CATEGORIAS_DEL_MODELO, CATEGORICAS
from app.schemas.interes import NECESIDADES

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTEFACTO = os.path.join(RAIZ, "ml_pipeline", "models", "lead_scorer_model.joblib")


@pytest.fixture(scope="module")
def categorias_del_artefacto():
    if not os.path.exists(ARTEFACTO):
        pytest.skip("No hay artefacto servido en ml_pipeline/models.")
    modelo = joblib.load(ARTEFACTO)
    preprocesador = modelo.named_steps["preprocessor"]
    codificador = preprocesador.named_transformers_["cat"]
    columnas = preprocesador.transformers_[0][2]
    return {
        columna: set(valores)
        for columna, valores in zip(columnas, codificador.categories_, strict=True)
    }


VARIABLE_POR_LISTA = {
    "job_titles": "job_title",
    "industries": "industry",
    "company_sizes": "company_size",
    "channels": "source_channel",
}


@pytest.fixture(scope="module")
def categorias_del_generador():
    """
    Las listas del generador, leídas del código sin ejecutarlo.

    Están dentro de `generate_synthetic_leads`, emparejadas con el peso de cada valor:
    `[("CTO", 0.90), ...]`. Se leen del árbol sintáctico en lugar de generar el dataset
    entero, que tarda y no hace falta para comparar nombres.
    """
    fuente = os.path.join(RAIZ, "ml_pipeline", "src", "synthetic_generator.py")
    arbol = ast.parse(open(fuente, encoding="utf-8").read())
    encontradas = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        destino = nodo.targets[0]
        if not isinstance(destino, ast.Name) or destino.id not in VARIABLE_POR_LISTA:
            continue
        pares = ast.literal_eval(nodo.value)
        encontradas[VARIABLE_POR_LISTA[destino.id]] = {nombre for nombre, _ in pares}
    assert sorted(encontradas) == sorted(VARIABLE_POR_LISTA.values()), (
        f"No se pudieron leer las listas del generador: {sorted(encontradas)}"
    )
    return encontradas


def test_estan_declaradas_todas_las_variables_categoricas():
    assert sorted(CATEGORIAS_DEL_MODELO) == sorted(CATEGORICAS)


@pytest.mark.parametrize("variable", ["job_title", "industry", "company_size", "source_channel"])
def test_las_listas_son_las_que_el_artefacto_conoce(variable, categorias_del_artefacto):
    """
    Lo que puntúa hoy es el artefacto. Si una lista se cambia sin reentrenar, esto falla, y
    ese es el aviso: el valor nuevo no lo vería el modelo.
    """
    assert set(CATEGORIAS_DEL_MODELO[variable]) == categorias_del_artefacto[variable]


@pytest.mark.parametrize("variable", ["job_title", "industry", "company_size", "source_channel"])
def test_las_listas_son_las_del_generador_del_dataset(variable, categorias_del_generador):
    assert set(CATEGORIAS_DEL_MODELO[variable]) == categorias_del_generador[variable]


def test_las_listas_propias_de_la_pagina_no_alimentan_al_modelo():
    """
    La necesidad no es una variable del modelo: es una lista cerrada de la página, y no
    puntúa. Si coincidiera con una variable categórica habría que alinearla también, y es
    mejor descubrirlo aquí que en la puntuación.
    """
    assert not set(NECESIDADES) & set(CATEGORIAS_DEL_MODELO)
