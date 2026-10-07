# Reporte 44 — El reparto que ordenaba por un campo: H-6 cerrado, la tanda que ninguna prueba de un caso veía y el bloqueo que SQLite ignora

**Capítulo 46** · Reparto automático equitativo de prospectos · ≈ 1 día · coste cero, sin cuentas nuevas
**Fecha:** 6 de octubre de 2026
**Alcance:** el punto 10 de §6.2 (H-6), que era el primero de los cuatro que el capítulo 38 dejó abiertos por exigir comportamiento nuevo del servidor; el `if` que repartía solo las fichas `HOT` y lo hacía ordenando por la capacidad **declarada** de cada cuenta; la regla nueva —menos cartera abierta, con el tiempo sin recibir como desempate— y los tres casos que no se tocan nunca; el criterio de «es un alta» derivado de lo que ya existía, que es lo que hace que una reasignación a mano no se deshaga sin añadir ninguna columna; el bloqueo de fila que la suite no puede ejercitar y se comprueba sobre la sentencia compilada; el asiento de bitácora sin actor y sin confirmar, con el parámetro `commit` que eso exigió en `registrar_evento`; la guarda del CI con diez propiedades y sus propias dos pruebas; y los tres puntos que entran en §6.4 por lo que este capítulo decide no hacer.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 44 es el capítulo 46. Los capítulos 29 y 31 no escribieron reporte propio.

> **Sobre la congelación.** Este capítulo la abre para el punto 10 de §6.2 y para nada más, y es el primero en el que lo que entra **es funcionalidad** y no una corrección. Se escribe así de claro porque los otros tres puntos que quedaban abiertos en §6.2 lo están por este mismo motivo, y cerrar uno porque se encargó no convierte a los demás en correcciones.

---

## 46.1. El punto 10 decía la mitad

El punto, literalmente:

> **La asignación automática es solo para las fichas `HOT`.** H-6, a medias: hay dónde repartir, pero nada reparte solo. Una ficha `WARM` o `COLD` espera a que el líder la asigne.

Todo lo que afirma es cierto. Lo que no dice es que **lo que sí repartía tampoco repartía**.

Esto era el paso 6 del scoring, escrito en la Fase 15 y sin tocar desde entonces:

```python
if category == ScoreCategory.HOT and not lead.assigned_rep_id:
    available_rep = (
        self.db.query(User)
        .filter(User.is_sales_rep.is_(True), User.is_active.is_(True))
        .order_by(User.capacity.desc().nullslast(), User.id.asc())
        .first()
    )
```

Dos condiciones y un orden. Las dos condiciones son correctas —no tocar lo que ya tiene dueño, y que el destino sea una cuenta que puede iniciar sesión, que es lo que arregló la unificación de identidades del capítulo 15—. El orden es el defecto.

---

## 46.2. `ORDER BY capacity DESC` no reparte: ordena

`users.capacity` es la cartera **máxima** que alguien declaró en su ficha de cuenta. Lo dice el propio modelo:

```python
# Cartera máxima. NULL cuando la persona no es asesora: un número ahí significaría
# una capacidad que nadie va a usar.
capacity = Column(Integer, nullable=True)
```

Ordenar por ella de mayor a menor y tomar la primera fila devuelve **siempre la misma persona**: la del número más alto, hasta que alguien le cambie el número. Con el equipo sembrado para la demostración —seis cuentas que atienden cartera, con capacidades 40, 50, 60, 80, 50 y 40— todas las fichas `HOT` eran de la de 80. No las primeras: todas.

Y aquí está lo que convierte esto en un capítulo y no en una línea:

**el defecto no se parece a un defecto.** Cada ficha sale con dueño. El dueño puede abrirla, porque es una cuenta de verdad. La ficha 360 enseña su nombre. El contador de «sin asesor» baja. Ninguna pantalla se queja, ningún registro dice nada, ninguna excepción se lanza. Y **cualquier prueba que mire una sola ficha pasa en verde**: `assert lead.assigned_rep_id is not None` es cierto, y lo seguiría siendo con el reparto más injusto que se pueda escribir.

Es la misma familia que el capítulo anterior —el recorrido del 5 de octubre— pasó un día entero recogiendo: nada falla, hay una pantalla que dice algo que no es. La diferencia es que aquí lo que dice algo que no es es el **reparto del trabajo de un equipo**, y la única forma de verlo es contar una tanda.

De ahí sale la primera decisión de este capítulo sobre cómo se prueba: **la prueba mide un conjunto y su desvío, nunca un elemento.** Doce altas entre cuatro asesoras tienen que acabar en tres cada una, y lo que la guarda comprueba es `max − min ≤ 1`.

---

## 46.3. Sin asesor el motor no tiene de quién hablar

La mitad que el punto sí contaba era peor de lo que su redacción sugiere. «Una ficha `WARM` espera a que el líder la asigne» parece una espera. No lo es: es un **silencio**.

El motor de reglas del capítulo 28 no pregunta «¿hay fichas nuevas?». Pregunta, en todas sus reglas:

```python
Lead.assigned_rep_id.isnot(None),
```

Es una decisión deliberada y está escrita con su motivo: el motor barre el **estado** en vez de engancharse a cada suceso, porque asignar ocurre en cinco sitios y el día que aparezca el sexto nadie recibiría un error. El precio, también escrito, es la granularidad. El que nadie había contado es este: **una ficha sin asesor no produce ni tarea, ni aviso, ni línea en la bandeja de nadie.** Y la mayoría de las fichas que llegan de una publicación salen `WARM`.

Así que la cadena entera del capítulo 28 —la tarea de primer contacto, el aviso del HOT desatendido, el escalado al líder— empezaba a funcionar **el día que al líder se le ocurría abrir la matriz**. El sistema no se callaba por un fallo: es que no tenía de quién hablar.

---

## 46.4. La regla, y por qué estos dos criterios

Dos, en este orden.

**1. Menos cartera abierta.** Prospectos asignados de los que todavía queda algo que hacer. «Queda algo que hacer» no se vuelve a definir aquí: se importa.

```python
from app.services.motor_de_reglas import aware, en_seguimiento
```

`en_seguimiento()` es la condición que usan las seis reglas del motor, y excluye `WON`, `LOST` y `UNQUALIFIED`. Contar la cartera **entera** habría premiado a quien menos cierra, que es exactamente lo contrario de lo que un reparto equitativo quiere decir: una asesora con doce tratos cerrados y ninguno abierto no tiene doce de carga, tiene cero.

Y no se copia la lista. Dos copias de esa regla **no fallarían**: las dos pantallas seguirían funcionando, y discreparían el día que una etapa cambie de lado. Es el defecto que el recorrido del 5 de octubre encontró siete veces, y la guarda lo vigila con una comparación de identidad —`reparto_automatico.en_seguimiento is motor_de_reglas.en_seguimiento`— y con un barrido del módulo buscando las etapas escritas a mano.

**2. Más tiempo sin recibir uno**, cuando hay empate en lo anterior. Sin este segundo criterio el empate lo rompería el identificador, y la cuenta más antigua se llevaría el primero de cada tanda para siempre.

Y cuando tampoco hay nada que desempatar —dos cuentas con la misma cartera abierta y ninguna que haya recibido nunca nada— decide el identificador, que es estable. Eso **no es un criterio**: es la ausencia de uno, y por eso el asiento lo escribe con su propio nombre, `orden_estable`, para que en la bitácora no se confunda con una decisión. Los cuatro valores posibles son `unico_candidato`, `menos_cartera_abierta`, `mas_tiempo_sin_recibir` y `orden_estable`.

Lo que la regla **no** mira, por escrito: el score, el sector, la zona y `capacity`.

---

## 46.5. Lo que no se toca nunca, y el responsable que se dio de baja

Tres casos, y el tercero es el que hace que el encargo se cumpla.

**Un prospecto con asesor.** El reparto no reasigna; reparte lo que no tiene dueño.

**Un prospecto de una publicación con responsable.** Y cuenta que la publicación **tenga** responsable, no que ese responsable siga siendo un asesor activo. La diferencia importa, porque el capítulo 26 ya había decidido qué pasa cuando no lo es:

```python
def asesor_para(db: Session, campana: Campaign) -> Optional[int]:
    """
    Se vuelve a comprobar al llegar cada prospecto: si el responsable se dio de baja o dejó de
    ser asesor, el prospecto llega sin asesor al líder, como si la publicación no tuviera
    responsable, en lugar de caer en una cartera que nadie abre.
    """
```

Esa ficha llega **sin asesor**, así que un reparto que solo mirara `assigned_rep_id` se la daría a otra persona, deshaciendo en silencio una decisión del capítulo 26 y quitándole al líder la única cartera que se le había dejado a él a propósito. La regla pregunta por `campaign.responsable_id`, no por el resultado de `asesor_para`.

Cuesta nombrarlo porque es el caso que nunca se demuestra, y es el que una prueba de la suite ya tenía escrita desde el capítulo 26 —`test_si_el_responsable_deja_de_ser_asesor_llega_sin_asesor`— y que siguió en verde sin tocarla.

**Un prospecto que no es un alta.** Eso es la sección siguiente.

---

## 46.6. «Es un alta» sin una columna nueva

El punto 4 del encargo pide que el líder pueda «reasignar a mano sin que el sistema lo deshaga». La forma obvia de conseguirlo es una columna `asignado_en` o una marca `repartido`, escrita en los cinco sitios que asignan. Y esa es exactamente la forma de regla que este proyecto lleva dos capítulos quitando: una lista escrita a mano que el sexto sitio no actualiza.

La alternativa está en la propia función:

```python
    if lead.id is not None:
        ya_puntuado = (
            db.query(ScoreHistory.id).filter(ScoreHistory.lead_id == lead.id).first() is not None
        )
        if ya_puntuado:
            return NO_ES_UN_ALTA
```

`calculate_and_persist_score` escribe una instantánea en `score_histories` **en cada pasada**, y lo hace desde la Fase 14, porque esa instantánea es lo que permite construir un dataset de reentrenamiento sin fuga de información. Así que «esta ficha no tiene ninguna» significa, sin inventar nada y sin columna nueva, «es la primera vez que esto se puntúa», es decir el alta. La comprobación va en el paso 6 y la escritura en el paso 8, de modo que el alta se ve a sí misma vacía.

De ahí salen las dos mitades del punto 4 sin una línea más:

* una ficha que el líder reasigna a mano ya tiene instantánea, así que ningún recálculo la mueve;
* una ficha que el líder deja **sin asesor a propósito** también la tiene, así que el reparto no se la devuelve a nadie. Quitarle el asesor es una decisión igual que ponérselo.

---

## 46.7. Dónde corre, y por qué el punto 3 no añade un gancho

El reparto vive dentro de `ScoringService.calculate_and_persist_score`, en el sitio del `if` que sustituye. Dar de alta una ficha ocurre en cuatro caminos —el alta del panel, la página de interés, las integraciones y el webhook del CRM— y los cuatro acaban puntuándola ahí. Es el argumento del capítulo 28 aplicado al alta en vez de a la asignación: el único sitio seguro para una regla es aquel por el que hay que pasar obligatoriamente. El día que aparezca el quinto camino, repartirá sin que nadie se acuerde de enchufarlo.

El punto 3 del encargo pide que la asignación automática «genere la tarea de primer contacto y el aviso del capítulo 28 como una asignación manual». Leído de frente, eso pide un gancho. Pero el motor ya barre el estado, no el suceso: `regla_primer_contacto` pregunta por prospectos **asignados y sin contacto nuestro**, y le da igual por dónde se asignaron.

Así que lo que había que escribir no era código. Era la comparación:

```python
    repartida = await _alta(db_session)
    a_mano = _ficha(db_session, asesor=equipo["ana"])

    ejecutar(db_session, ahora=AHORA, reglas=[PRIMER_CONTACTO])

    comparables = [
        (t.asesor_id, t.regla, t.clave, t.estado, t.vence_el, t.motivo)
        for t in (tareas[repartida.id], tareas[a_mano.id])
    ]
    assert comparables[0] == comparables[1]
```

Dos fichas iguales, una repartida y otra asignada a mano, producen la misma tarea campo por campo. Y una ficha `HOT` repartida y desatendida recibe el aviso de `hot_sin_contacto` a nombre de su asesora, que es lo que antes no podía ocurrir porque no había asesora.

Aquí el capítulo gana una línea del documento de la prueba con personas, no del servidor: la tarea aparece en la **pasada siguiente**, no en el mismo segundo, y eso ya estaba escrito como «cosa que parece un fallo y no lo es».

---

## 46.8. Dos altas a la vez, y lo que la suite no puede ejercitar

La decisión lee un recuento que otra transacción está a punto de cambiar. Sin nada más, dos altas simultáneas leen «Ana tiene cero», y las dos se la dan a Ana: el mismo hueco repartido dos veces.

La defensa son dos líneas, y las dos cuentan:

```python
    return (
        db.query(User.id)
        .filter(User.is_sales_rep.is_(True), User.is_active.is_(True))
        .order_by(User.id.asc())
        .with_for_update()
    )
```

`with_for_update()` serializa las dos decisiones: la segunda cuenta después de que la primera haya confirmado. `order_by(User.id.asc())` impide que dos pasadas que toman las mismas filas se bloqueen una a la otra. Son pocas filas —las cuentas que atienden cartera— y el bloqueo dura lo que dura un alta.

Y aquí este capítulo tropieza con algo que el 42 ya había dejado escrito: **el motor de las pruebas no es el de producción.** La suite corre sobre SQLite en memoria, que ignora `FOR UPDATE` **en silencio**: el dialecto de SQLAlchemy simplemente no lo emite. Encima, con `StaticPool`, dos sesiones de la suite comparten la misma conexión, así que no hay concurrencia que simular. El bloqueo no se puede ejercitar aquí, y una prueba que fingiera ejercitarlo sería la tautología que el capítulo 42 documentó.

Lo que sí se puede comprobar es que la sentencia **lo pide**:

```python
    sentencia = str(
        reparto_automatico.consulta_de_candidatos(db_session).statement.compile(
            dialect=postgresql.dialect()
        )
    )

    assert "FOR UPDATE" in sentencia
    assert "ORDER BY users.id ASC" in sentencia
```

Contra el dialecto de PostgreSQL, que es el que corre en la pila. Y sobre **la consulta que usa el reparto**: `consulta_de_candidatos` existe separada precisamente para que la prueba compile lo que se ejecuta y no una copia parecida, que es el otro modo de que una guarda quede satisfecha por sí misma.

Queda además el caso hermano, que sí se ejercita y es el que ocurre de verdad varias veces al día: dos altas en la **misma** transacción —una entrega del CRM con dos eventos— no pueden ir a la misma cuenta. Eso exige que el recuento vea lo que la transacción ya escribió, y no solo lo confirmado.

---

## 46.9. El asiento: la regla, los candidatos, sin actor y sin confirmar

El punto 3 pide que cada asignación automática quede en la bitácora «con la regla aplicada y entre cuántos candidatos se eligió». Las dos cosas son lo que convierte el asiento en algo discutible: «se le dio a Ana» no se puede comprobar al día siguiente; «se le dio a Ana entre tres porque tenía la cartera abierta más pequeña» sí.

```python
    anotar_en_bitacora(
        db,
        accion=ACCION_LEAD_REPARTO_AUTOMATICO,
        entidad=ENTIDAD_LEAD,
        entidad_id=str(lead.id),
        metadatos={
            "asesor_id": reparto.asesor_id,
            "regla": reparto.regla,
            "candidatos": reparto.candidatos,
            "cartera_abierta_del_elegido": reparto.cartera_abierta,
        },
        commit=False,
    )
```

**Sin actor**, como la purga del historial y como el motor de reglas. El alta la pudo pedir una persona, pero a quién le tocaba no lo decidió ella: un asiento con su correo dentro se leería como que eligió, y eso es justo lo que no hay que poder confundir el día que alguien discuta un reparto.

**Sin confirmar**, y eso obligó a tocar `registrar_evento`, que hasta hoy siempre hacía `db.commit()`. El motivo es la ingesta del CRM: confirma la ficha, su actividad, su score y su auditoría **juntas o ninguna**, y un asiento que confirmara por su cuenta dejaría escrito en la bitácora el reparto de un prospecto que el `rollback` siguiente se llevó. La bitácora afirmaría algo que no pasó, que es peor que no tener asiento.

El parámetro arrastra un segundo cuidado, pequeño y fácil de olvidar: con `commit=False`, el manejador de errores **no** puede hacer `rollback`. Ese `rollback` le quitaría de debajo a quien llama lo que estaba escribiendo, que es exactamente el daño que el docstring de esa función lleva evitando desde la Fase 14 en el otro camino.

---

## 46.10. El interruptor, y el precio de que no tenga pantalla

`REPARTO_AUTOMATICO_ACTIVO`, con valor por omisión `true`, en `app/core/config.py`, en el servicio `backend` del compose y en `devops/.env.example`. Apagado, la ficha nace sin asesor y la reparte quien dirige la cartera, como antes de este capítulo; apagarlo **no mueve nada** de lo ya repartido, porque el reparto corre una sola vez y no vuelve a mirar una ficha que ya se puntuó.

Va solo en el servicio `backend` y no en el de retención: el reparto corre en el alta, y la pasada diaria no crea fichas. Una variable ahí no decidiría nada y sugeriría que sí.

El precio está escrito y es real: es configuración de la instalación, no una pantalla, así que apagarlo exige tocar `pila.env` y reiniciar el backend. El líder lo **pide** a quien opera la pila en lugar de hacerlo él. La pantalla queda fuera del encargo por escrito y anotada como punto 58 de §6.4, con una observación que la hace barata: es la misma forma que el punto 15 —una pantalla de configuración— pero sin ningún secreto que guardar ni rotar, solo un booleano.

---

## 46.11. Lo que cambia en lo que ya se enseñaba

Esta es la parte del capítulo que no se ve en un diff del servidor, y la que costó más páginas.

El contador «Nuevos de publicaciones, sin asesor» sigue calculando exactamente lo que calculaba. Lo que cambió es **lo que significa**: antes contaba las fichas que esperaban una decisión; ahora cuenta las que el reparto **no pudo colocar** —una instalación sin asesoras activas, una publicación cuyo responsable se dio de baja—. Con la pila sembrada, eso es **cero**. No está roto: cuenta otra cosa.

Y había siete sitios en el repositorio afirmando lo contrario:

| Dónde | Qué decía | Qué dice |
| :--- | :--- | :--- |
| `scripts/ensayo_de_la_demo.py`, paso 4 | «la ficha llegó ya con asesor: el líder no tendría nada que repartir» | comprueba que quedó repartida a una cuenta activa que atiende cartera |
| `scripts/ensayo_de_la_demo.py`, paso 5 | el contador sube **exactamente uno** | el contador **no** sube, y el líder **reasigna** |
| `docs/Prueba_Con_Personas.md`, tarea 5 del líder | «asígnasela al asesor comercial» | «averigua a quién se le asignó y **pásasela**» |
| `docs/Prueba_Con_Personas.md`, «cosas que parecen fallos» | cuatro | **cinco**: el contador dirá cero y la persona sí ha llegado |
| `docs/Guion_Cronometrado_de_la_Demo.md`, pasos 4 y 5 | «quedó sin dueño a propósito» | quedó repartida, y lo que el líder reasigna se queda |
| `docs/GUIA_DEFENSA_ORAL.md`, paso 4 | «la ficha nace puntuada, atribuida y sin asesor» | «…y ya repartida» |
| `backend/tests/test_pagina_de_interes.py` y `test_publicaciones_completas.py` | `assigned_rep_id is None` | la página no elige **con el reparto apagado**; con él encendido, reparte |

Las dos pruebas merecen una frase, porque son el caso que el capítulo 43 ya había señalado en otra forma: **una prueba puede tener escrito como resultado correcto lo que acaba de dejar de serlo.** No se borraron. Cada una se partió en dos: una comprueba, con el interruptor apagado, lo que de verdad decidía —que la publicación sin responsable no elige asesor por nadie— y la otra comprueba lo nuevo. Y `test_una_ficha_que_ya_existia_no_se_reasigna` pasó a ser **más fuerte** que antes: afirmaba que la ficha seguía sin asesor, y ahora afirma que sigue en la cartera donde estaba y que no se la llevó el responsable de la segunda publicación.

---

## 46.12. La guarda, y sus propias dos pruebas

`scripts/guarda_del_reparto_automatico.py`, en el CI junto a las otras tres, después de descargar el artefacto y antes de la suite. Diez propiedades, no casos:

| | Qué falla si se pierde |
| :---: | :--- |
| 1 | la tanda de doce entre cuatro se desvía en más de una ficha, o alguna cuenta no recibe nada; y la cartera que decide deja de ser la abierta |
| 2 | el reparto no es el mismo para `HOT`, `WARM` y `COLD` —se comparan las tres secuencias completas, no que cada una tenga dueño— |
| 3 | un recálculo deshace una reasignación a mano, o devuelve a alguien lo que el líder dejó sin asesor; o se toca una ficha con dueño o de una publicación con responsable |
| 4 | la consulta de candidatos deja de pedir `FOR UPDATE` o de ordenar por identificador; o el recuento deja de ver lo que la propia transacción escribió |
| 5 | la definición de cartera abierta deja de ser **la función** del motor, o aparece una etapa cerrada escrita a mano en el módulo |
| 6 | falta algún asiento, o no dice la regla y los candidatos, o lleva actor, o lleva algo de la persona, o sobrevive al `rollback` del alta |
| 7 | el interruptor apagado sigue repartiendo o escribiendo, o apagarlo mueve lo ya repartido |
| 8 | los prospectos repartidos no reciben su tarea en la pasada siguiente, a nombre de su propia asesora; o el reparto crea tareas por su cuenta |
| 9 | el alta del panel, la página pública o una integración acaban con una ficha sin asesor habiendo asesoras activas |
| 10 | sin asesoras activas se asigna a alguien, se escribe un asiento, o revienta |

La 9 es la que vigila el acoplamiento que da miedo: no comprueba el código del reparto, **recorre los tres caminos del alta de verdad** —dos por HTTP con `TestClient` y uno por el servicio de integraciones— y mira quién acabó siendo el dueño.

Y la guarda lleva **sus propias dos pruebas** en la suite, que es algo que hasta hoy solo tenía la de la página pública: una comprueba que el CI la ejecuta y en qué orden, leyendo `ci.yml`; la otra la ejecuta como subproceso y exige que pase. El motivo está escrito en la primera: un paso del CI se borra sin que nada falle. El flujo sigue en verde, solo que ya no comprueba lo que comprobaba.

---

## 46.13. Veinte defectos reintroducidos, y por qué hacen falta dos mitades

El arnés vuelve a escribir, uno a uno, cada defecto que este capítulo corrige o que la guarda dice vigilar, y corre la suite del reparto y la guarda contra cada uno. **20 de 20 detectados.**

Lo que vale es el reparto de quién vio qué:

| | Detectado por |
| :--- | :--- |
| 18 de los 20 | la suite **y** la guarda |
| «se pierde el desempate por tiempo sin recibir» | solo la **suite** |
| «la regla de queda algo que hacer se copia en el módulo» | solo la **guarda** |

Cada mitad vio 19. Y los dos que solo vio una son la razón de que haya dos:

* el **desempate perdido** no lo nota ninguna propiedad sobre una tanda, porque la tanda sigue saliendo equilibrada: lo único que cambia es a quién le toca dentro del empate, y eso solo se ve con un caso construido;
* la **regla copiada a mano** no la nota ninguna prueba de comportamiento, porque el comportamiento es **idéntico** hasta el día que una etapa cambie de lado. Lo único que la ve es una comprobación sobre la forma del código: que la condición sea la misma función y que el módulo no nombre ninguna etapa cerrada.

Es la respuesta, medida, a por qué este proyecto escribe guardas de propiedades además de pruebas: no porque las pruebas sean pocas, sino porque hay clases de defecto que ninguna de las dos formas alcanza sola.

---

## 46.14. Lo que apareció y no se hizo

Tres puntos nuevos en §6.4, los tres por decisión y no por falta de tiempo:

**57. El desempate mide la fecha de alta, no la de asignación.** «Quien lleva más tiempo sin recibir uno» se calcula con la fecha en que se creó el prospecto más reciente de su cartera. Para lo que el reparto reparte las dos fechas son la misma, porque reparte en el alta. Para una ficha **reasignada a mano** no lo son: a quien el líder acaba de traspasar un prospecto de hace tres meses le sigue constando que no recibe nada desde hace tres meses, y en un empate recibiría antes de lo que le toca. Se acepta a sabiendas —la carga de ese traspaso ya la cuenta el primer criterio, que es el que decide casi siempre— y la alternativa es la columna escrita en cinco sitios de §46.6.

**58. El interruptor no tiene pantalla.** Lo de §46.10.

**59. El reparto no mira `capacity`, así que la cartera máxima declarada no limita nada.** La columna sigue sirviendo donde ya servía —el traspaso de la cartera de una baja avisa cuando el destino la supera—, pero el reparto no se detiene al llegar al tope de nadie: con todas las asesoras llenas, la siguiente ficha va a la menos llena igualmente. Era eso o no repartirla, y no repartirla la devuelve al punto 10. Que `capacity` sea un tope de verdad exige decidir qué pasa cuando se alcanza, y eso es funcionalidad.

Y por escrito, lo que este capítulo **no** añadió: ninguna tabla, ninguna columna, ninguna migración, ningún endpoint, ninguna pantalla, ningún color. Un módulo de servicio, un ajuste de configuración, una acción de bitácora y un parámetro `commit`. No se tocó §3, §4, §5, §6.1, y de §6.2 solo el punto 10.

---

## 46.15. Estado al cierre

| | |
| :--- | :--- |
| Pruebas del servidor | **1734 pasan**, 2 omitidas (desde 1700) |
| Cobertura del servidor | **94,42 %** sobre un suelo de 85; el módulo nuevo, **100 %** |
| Pruebas del cliente | **748** en 45 archivos, sin cambios: este capítulo no toca el cliente |
| Cobertura del cliente | 96,65 % sentencias · 91,75 % ramas · 98,52 % funciones · 98,68 % líneas (suelos: 96 / 90 / 98 / 98) |
| Criterios del reparto | **2**, con **4** resultados posibles escritos en el asiento |
| Caminos del alta cubiertos | **3** recorridos de verdad por la guarda, de los **4** que pasan por el scoring |
| `ruff` / `eslint` / `npm run build` | sin avisos |
| Controles del CI | **59** en `configuracion-peligrosa`; guardas de propiedades, **7** (desde 6) |
| Arnés de reintroducción | **20 de 20** detectados; **19** por cada mitad |
| §6.2 | el **10** cerrado: **5 de 9** cerrados; siguen abiertos el 9, el 12, el 15 y el 35 |
| §6.4 | entran el **57**, el **58** y el **59** |

Lo que queda dicho de este capítulo: **una regla que reparte trabajo ordenando por un campo declarado no reparte, ordena**, y es invisible a cualquier prueba que mire un solo caso, porque en cada caso el resultado es correcto. Lo que hay que medir es el conjunto. Y cuando el mecanismo que de verdad protege no se puede ejercitar con el motor de las pruebas, la salida no es darlo por bueno ni dejarlo sin mirar: es comprobar que la sentencia **lo pide**, contra el motor que corre en producción y sobre la consulta que se ejecuta.
