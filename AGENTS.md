# AGENTS.md — reglas de este repositorio

Esto no es documentación del producto: es lo que hay que saber **antes de tocar nada**. Vale
igual para una persona que entra nueva y para un agente de código.

---

## 1. El proyecto está congelado, y desde el 6 de octubre de 2026 lo está del todo

| Fecha | Qué significa |
| :--- | :--- |
| 24-09-2026 | Congelación de funcionalidades: entran **correcciones de fallos**, una por capítulo, abriendo la congelación para puntos **nombrados** del documento de trabajo futuro |
| 06-10-2026 | **Congelación definitiva.** Entra solo lo que impida **levantar la pila** o **enseñar la demostración**. Nada más |

**No se abre ningún capítulo ni ninguna auditoría nuevos.** Ni de código, ni de
accesibilidad, ni de seguridad, ni de rendimiento, ni de calidad.

Ante la duda, una sola pregunta: **¿se puede enseñar el sistema hoy sin esto?** Si la
respuesta es sí, se **anota** en §6.4 de
[`docs/Congelacion_y_Trabajo_Futuro.md`](docs/Congelacion_y_Trabajo_Futuro.md) y no se toca.
Ese documento es la autoridad sobre qué está abierto y qué está cerrado: por encima de
cualquier reporte, de la memoria técnica y de este archivo.

Lo que **no** entra, por escrito: funcionalidad nueva, pantallas nuevas, endpoints nuevos,
columnas, migraciones, colores, reentrenar el modelo, y cualquier cosa que cambie lo que la
API ya contesta a un cliente que existe.

---

## 2. Cómo se levanta, y el único modo que hay

La pila se arranca **siempre** con el lanzador, nunca con `docker compose` a secas:

```bash
python devops/pila.py iniciar          # una sola vez: crea ~/.plurione/pila.env con los secretos
python devops/pila.py up -d --build    # cualquier orden de docker compose se pasa tal cual
python devops/pila.py ps
python devops/pila.py down             # SIN -v: `-v` borra la base
```

El entorno vive **fuera del repositorio**, en `~/.plurione/pila.env`. El lanzador se niega a
arrancar si ese archivo está dentro del árbol, si hay un `.env` suelto que Compose o la
aplicación leerían por su cuenta, o si faltan `SECRET_KEY` o `POSTGRES_PASSWORD`. Esto no es
una preferencia: en la Fase 0 hubo que rotar una clave que había viajado dentro de la
carpeta.

**`--build` importa.** `up -d` sin `--build` reutiliza la imagen que haya, y una imagen vieja
arranca igual de bien: los seis contenedores se ponen verdes y el panel funciona. El 5 de
octubre de 2026 se perdió media mañana juzgando la interfaz sobre una imagen de cuatro días
antes. Antes de dar por bueno algo visual, **reconstruir**; está anotado como punto 56 de
§6.4 porque nada lo comprueba todavía.

Puertas: panel en **3000**, puerta pública en **127.0.0.1:8080**, API en **127.0.0.1:8000**.
PostgreSQL no se publica salvo con el overlay `--dev`.

Para operar sin programar: [**Si algo falla**](docs/Si_Algo_Falla.md). Para publicarlo bajo
un dominio de la empresa: [**Poner la dirección de la empresa**](docs/Poner_la_Direccion_de_la_Empresa.md)
—una sola variable, y no vive en el repositorio—.

---

## 3. Qué guardas hay en el CI, y cómo se prueban

El CI (`.github/workflows/ci.yml`) tiene **10 trabajos**. Dentro hay tres clases de
comprobación y conviene no confundirlas:

| Clase | Cuántas | Qué es |
| :--- | :---: | :--- |
| Pruebas | 1734 servidor · 748 cliente | Comprueban **casos** |
| Controles de configuración peligrosa | 59 | Pasos del trabajo `configuracion-peligrosa`: leen archivos y fallan si reaparece una configuración que ya causó un fallo |
| Guardas de propiedades | 7 | Programas que levantan la aplicación y comprueban **propiedades**, no casos |

Las guardas de propiedades, con su orden propio y nombre propio en el CI:

```bash
python scripts/guarda_de_la_pagina_publica.py       # capítulo 25: la única ruta sin sesión que escribe
python scripts/guarda_del_motor_de_reglas.py        # capítulo 28: lo que decide de madrugada
python scripts/guarda_de_los_desenlaces.py          # capítulo 30: lo que produce etiquetas de entrenamiento
python scripts/guarda_del_reparto_automatico.py     # capítulo 46: lo que decide en el alta
python -m pytest scripts/test_hojas_de_observacion.py -q   # el veredicto de la prueba con personas
python scripts/renovar_imagenes.py --solo-fijacion  # que ninguna imagen quede sin huella
# y la del segundo factor, escrita en línea dentro del trabajo `configuracion-peligrosa`
```

Las suites:

```bash
python -m pytest backend/tests -q                   # ~9 min
python -m pytest backend/tests -q --cov=backend/app --cov-fail-under=85
cd frontend && npx vitest run && npx eslint src && npm run build
ruff check backend/ scripts/
```

**Dos reglas sobre las pruebas, aprendidas a base de perder tiempo:**

1. **Nunca dos `pytest` a la vez.** Comparten la base de pruebas y producen cientos de
   fallos falsos. Una vez dieron 227 rojas sobre un árbol correcto.
2. **El motor de las pruebas no es el de producción.** La suite corre sobre SQLite en
   memoria. Lo que solo existe en PostgreSQL —`FOR UPDATE`, algunos comportamientos de
   restricción— no se puede ejercitar ahí: se comprueba sobre la **sentencia compilada**
   contra el dialecto real, nunca dando por bueno lo que no se ha podido ejecutar.

### Cómo se prueba una guarda

Una guarda que nadie ha puesto en rojo no es una guarda. Cada capítulo que corrige algo pasa
un **arnés de reintroducción**: se vuelve a escribir el defecto, uno a uno, se corre la suite
y la guarda, y se exige que algo falle. Si un defecto pasa sin que nada se ponga rojo, la
defensa no existe y hay que arreglar la guarda, no el informe. Los arneses no viven en el
repositorio —son temporales— pero la cuenta sí queda escrita en cada reporte: el último fue
**20 de 20**.

Y el otro cuidado, que ha aparecido tres capítulos seguidos: **una guarda tiene dos mitades,
cómo mide y sobre qué.** Una lista de pantallas, de clases, de pares de colores o de etapas
escrita a mano hace que la medición sea correcta sobre el inventario equivocado. Las listas
se **derivan del código**.

---

## 4. Dónde vive cada cosa

```
backend/app/core/        reglas y vocabulario compartido; NO importa de app.models
backend/app/models/      el esquema (entities.py); importa de app.core, nunca al revés
backend/app/services/    la lógica; un servicio puede importar otro
backend/app/api/v1/      los endpoints; no deciden alcance de cartera (lo hace el repositorio)
backend/app/repositories/ el alcance sobre el dato vive aquí, no en cada endpoint
backend/tests/           la suite; conftest.py declara los datos por fixtures
backend/alembic/         migraciones; nada crea tablas al vuelo
frontend/src/            el cliente; services/ para reglas compartidas, pruebas/ para las derivadas
ml_pipeline/             entrenamiento, monitor de deriva, registro y bucle de realimentación
devops/                  pila.py (único arranque), compose, init_db.sql, respaldos
scripts/                 guardas del CI, ensayo de la demo, preparación de la prueba con personas
docs/                    la congelación, los guiones, las guías, los reportes y la memoria
docs/reportes/           un reporte por capítulo; el número va DOS por detrás del capítulo
docs/docs_residencias/   papeles institucionales — NO SE TOCAN NUNCA
```

**Numeración:** el reporte va dos por detrás del capítulo. El Reporte 44 es el capítulo 46.
Los capítulos 29 y 31 no escribieron reporte propio, y eso se explica en el compilador en
lugar de renumerar.

**La memoria técnica se compila, no se edita a mano:**

```bash
python docs/compile_reports.py
```

Toma los 44 reportes y genera `docs/Memoria_Tecnica_Final_Lead_Scoring.md` con portada,
índice y anclas. Las cifras del resumen ejecutivo van escritas a mano **dentro del
compilador**, para que la memoria salga igual dentro de un año sin depender de que haya un
entorno capaz de correr la suite. Si una cifra cambia, se cambia ahí.

---

## 5. Cómo se escribe en este repositorio

* **Todo en castellano**: comentarios, docstrings, nombres de prueba, documentos y mensajes
  de confirmación. Sin acentos solo en `ci.yml` y en los comentarios del compose, por
  consistencia con lo que ya hay ahí.
* **Un comentario dice por qué, no qué.** Si explica lo que la línea ya dice, sobra. Si
  explica qué pasaba antes y por qué se cambió, se queda para siempre.
* **Las reglas se escriben una vez.** Una regla aplicada en uno solo de los sitios que la
  necesitaban **no falla**: hay una pantalla que dice algo distinto, y eso solo lo ve quien
  mira la pantalla. El 5 de octubre de 2026 aparecieron siete de esa forma en un día. Al
  corregir algo, la pregunta obligatoria es **en cuántos sitios más vive esa regla**.
* **Los archivos del árbol tienen finales de línea mixtos** (la mayoría CRLF). Editar con
  herramientas que los respeten; `git` normaliza a LF en el índice con `core.autocrlf=true`,
  pero mezclarlos dentro de un archivo se nota.
* **Nunca secretos en el árbol.** Ni en un `.env`, ni en un comentario, ni en una prueba. La
  contraseña de demostración `PluriOne2026!` es la excepción documentada: es la de desarrollo
  de `seed_data.py`, está en el README desde el principio y en un entorno endurecido el
  sembrado genera una aleatoria.

---

## 6. Subir el trabajo

**Cada avance terminado se confirma y se sube a GitHub, sin preguntar.** Un trabajo que pasa
sus pruebas y se queda en el árbol de trabajo es un trabajo que no existe.

```bash
git add -A
git commit -F <mensaje>
git push
```

El mensaje de confirmación es en castellano, cuenta **qué estaba mal y por qué**, no solo qué
se cambió, y termina con la línea de coautoría. Al final lleva las cifras del cierre
—pruebas, cobertura, arnés—.

**`docs/docs_residencias/` no se toca nunca.** Son los papeles institucionales de la
residencia —acuerdos, cartas, el informe en `.docx`— y no los mantiene este repositorio. Si
hace falta contenido para ellos, se escribe en `docs/` como Markdown y lo traslada una
persona.

---

## 7. Lo que se aprendió por las malas, en siete líneas

1. Una imagen vieja arranca igual de bien que la nueva. Reconstruir antes de juzgar.
2. Dos `pytest` a la vez dan cientos de rojas falsas.
3. Una guarda que mide bien sobre una lista escrita a mano mide la lista.
4. Un doble puesto por encima del defecto convierte la prueba en una tautología.
5. Si encender una restricción del esquema no cambia ningún resultado, esa clase entera
   estaba sin probar.
6. Comprobar que un símbolo **aparece** no comprueba que se **use**: el `import` lo mantiene
   vivo.
7. Una regla que reparte ordenando por un campo declarado no reparte, ordena —y cada ficha
   sale con dueño, así que ninguna prueba de un caso lo ve—.
