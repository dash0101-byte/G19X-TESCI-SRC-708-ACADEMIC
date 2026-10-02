# Reporte 40 — El motor que no comprobaba nada: dieciocho claves sin probar, el `except` que adivinaba y el «duplicado» que perdía un prospecto

**Capítulo 42** · Integridad de datos y respuestas de error · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 2 de octubre de 2026
**Alcance:** las dieciocho claves ajenas y las dieciocho cláusulas `ondelete` del esquema, que el motor de la suite y del desarrollo no comprobaba; las cuatro columnas de clave ajena que pueden llegar en un cuerpo de petición y las dos que no se comprobaban (§6.4 punto 40); los `except IntegrityError` que traducían cualquier violación de integridad a la única que su autor tenía en mente (§6.4 punto 26); el «duplicado» con el que el webhook del CRM descartaba un evento que no era un duplicado; el 200 con el que la edición de una ficha decía que sí a un campo que ignoraba; un control de regresión con veintitrés defectos reintroducidos, y cuatro de ellos que escaparon en la primera pasada y cambiaron el arreglo.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 40 es el capítulo 42. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 42.1. Dos restos menores, y la mitad que no estaba en ninguna lista

`docs/Congelacion_y_Trabajo_Futuro.md` está congelado desde el 24 de septiembre de 2026: desde esa fecha solo entran correcciones de fallos. Este capítulo abre la congelación **para dos puntos de §6.4 y para ninguno más**, el **26** y el **40**, que el propio documento mandaba arreglar juntos —«las dos son sobre lo que el servidor dice cuando la base rechaza algo, y se arreglan mejor juntas»—.

Lo que decían:

> **26.** *«El `except IntegrityError` de la edición traduce **cualquier** violación de integridad a "el correo ya existe", que es lo único que podía producirla. Con el 422 del esquema delante, un nulo sobre una columna `NOT NULL` no llega a ese commit; si llegara, el mensaje sería equivocado. Distinguir qué restricción falló obliga a leer el error del motor, específico de PostgreSQL y de SQLite por separado.»*

> **40.** *«El alta de una ficha no tiene la red del `IntegrityError` que sí tiene la edición. `create_lead` comprueba que el correo no esté registrado y después inserta; entre las dos cosas cabe otra transacción que tome ese correo, y entonces el `INSERT` viola el índice único y sale como 500. Es una carrera, así que no se ve en uso normal y no la provoca ninguna prueba.»*

Las dos frases eran ciertas y las dos estaban cortas en lo mismo: daban por hecho que el único camino hasta ese `commit` es una carrera. No lo es, y lo que lo convierte en otra cosa no estaba en ninguna lista de §6.4.

| Lo que los puntos decían | Lo que había |
| :--- | :--- |
| El mensaje sería equivocado **si llegara** | Llega sin ninguna carrera: `leads` tiene dos claves ajenas, y un `assigned_rep_id` que no existe pasa el esquema —es un entero— y lo rechaza la base |
| La carrera «no se ve en uso normal y no la provoca ninguna prueba» | Cierto, y por eso el 500 del alta no era una carrera: era `POST /leads` con un identificador que no existe, que cualquier cliente de la API puede mandar |
| Distinguir obliga a leer el error del motor | A medias, y la mitad que falta cambia el arreglo: SQLite **no nombra la columna** en el caso más probable de los tres (§42.5) |
| — | El motor de la suite y del desarrollo **no comprobaba ninguna de las dieciocho claves ajenas del esquema**, así que esta clase entera de fallo no podía ponerse roja (§42.2) |
| — | Había además otros dos `except IntegrityError` suponiendo, y el del webhook del CRM contestaba «duplicado»: **descartaba el evento entero** dando por hecho que alguien ya lo había procesado (§42.8) |

### Lo que este capítulo decidió NO abrir

Por escrito: ninguna pantalla nueva, ningún endpoint nuevo, ninguna columna nueva, ninguna migración —§42.10 dice por qué no hace falta—, ninguna regla nueva sobre **quién** puede recibir cartera, y nada de §3, §4, §5, §6.1, §6.2 ni §6.3. Los puntos 37, 38 y 39 de §6.4 siguen abiertos y §42.14 dice por qué.

---

## 42.2. La línea que estaba escrita seis veces, todas en el sitio donde no hacía falta

SQLite no comprueba las claves ajenas si no se le pide. `PRAGMA foreign_keys` nace **apagado**, no se guarda en el archivo y no se hereda: hay que encenderlo en cada conexión. PostgreSQL las comprueba siempre.

En este repositorio la línea estaba escrita seis veces, y las seis dentro de tres pruebas de migración:

```
backend/tests/test_migracion_desenlaces.py              4
backend/tests/test_migracion_pais_telefonos_e_ingresos.py  1
backend/tests/test_migracion_un_blanco_no_es_un_dato.py    1
```

Cuatro en un solo archivo porque el pragma es por conexión y esa prueba abre cuatro transacciones. Quien escribió aquello sabía exactamente lo que hacía: la prueba del capítulo 30 comprueba, en SQL y a mano, que «el prospecto se va y el desenlace se va con él». Es la única cascada del sistema que estaba demostrada.

Donde no estaba era en `app/core/database.py`, el único sitio donde se crea el motor de la aplicación: el que usa la suite —SQLite en memoria, con `StaticPool`, es decir **una sola conexión para las 1589 pruebas**— y el que usa el desarrollo local sobre un archivo. Una línea en el `connect` del motor habría cubierto las dos cosas.

El arreglo es esa línea:

```python
if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _exigir_las_claves_ajenas(conexion_dbapi, _registro) -> None:
        cursor = conexion_dbapi.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()
```

**Lo que midió al encenderla es lo importante de este capítulo.** La suite entera, con el pragma:

```
1587 passed, 2 skipped
```

Exactamente lo mismo que sin él. Ni una prueba cambió de color.

Eso no es tranquilidad. Si ninguna de las 1589 pruebas nota la diferencia entre un motor que comprueba dieciocho claves ajenas y uno que no comprueba ninguna, es porque **ninguna había escrito nunca una clave que no apuntara a nada, ni había borrado un padre cuya cascada importara**. No era una laguna de una prueba: era una clase entera de fallo que no existía para nadie. Los 500 de §42.4 llevaban ahí desde que existen esas dos columnas.

Va en el motor y no en `conftest.py` a propósito. En `conftest.py` habría encendido las claves ajenas para la suite y las habría dejado apagadas para el desarrollo local, que usa el mismo motor sobre un archivo; y el síntoma de eso —una ficha de desarrollo apuntando a una publicación que no existe— es de los que no se ven hasta que alguien mira la base a mano.

---

## 42.3. Dieciocho claves, y cuatro que un cuerpo puede apuntar a cualquier parte

El esquema tiene **16 tablas, 18 restricciones únicas y 18 claves ajenas**: once en cascada y siete a nulo.

De las dieciocho, catorce se escriben desde una fila que el código ya tiene cargada —`lead.id`, `campana.id`, `destino.id`—, así que no pueden apuntar a nada que no exista. Las otras cuatro pueden venir de un cuerpo de petición, y la lista no está escrita a mano: sale de cruzar los campos de cada esquema de entrada con las columnas de clave ajena del esquema de la base, reutilizando la enumeración de rutas que el capítulo 41 dejó escrita.

El cruce dio **siete campos sobre cuatro columnas**, y tres no se esperaban:

| Esquema · campo | Columna | Cómo se trataba |
| :--- | :--- | :--- |
| `CampanaCreate.responsable_id` | `campaigns.responsable_id` | **422** por `ciclo.comprobar_responsable`, y además exige que sea un asesor **activo** |
| `CampanaUpdate.responsable_id` | `campaigns.responsable_id` | lo mismo |
| `VinculacionRequest.lead_id` | `lead_activities.lead_id` | **404**, porque el cuerpo nombra un prospecto que quien vincula puede no tener en su alcance |
| `LeadCreate.assigned_rep_id` | `leads.assigned_rep_id` | nada |
| `LeadCreate.campaign_id` | `leads.campaign_id` | nada |
| `LeadUpdate.assigned_rep_id` | `leads.assigned_rep_id` | nada |
| `LeadUpdate.campaign_id` | — | el campo no estaba declarado: **200 y no cambiaba nada** (§42.9) |

Es decir: la pregunta «¿y si ese identificador no existe?» tenía **tres respuestas escritas en este repositorio** —un 422 que pide más de lo que la base pide, un 404 que protege la cartera ajena, y nada— y la cuarta era no preguntar. El goal de este capítulo decía «dos de las dieciocho»; la lista derivada dijo cuatro columnas en siete campos, y que dos de ellas estaban cubiertas desde el capítulo 28. La comprobación que faltaba **ya estaba escrita al lado**, como en el capítulo 41 lo estaba la línea del recorte.

Las dos respuestas que ya existían se quedan como están. Unificarlas sería cambiar comportamiento que nadie ha pedido: el 404 de la bandeja es una decisión sobre qué se cuenta de la cartera de otro, y el 422 de la publicación exige que el responsable sea un asesor activo, que es más de lo que la integridad de la base pregunta.

---

## 42.4. Lo que contestaba cada puerta, medido

Con el pragma encendido —es decir, con el motor comportándose como el de producción— y antes de tocar nada:

| Petición | Respuesta |
| :--- | :--- |
| `POST /leads` con `campaign_id: 999999` | **500** · «Excepción no controlada en POST /api/v1/leads: FOREIGN KEY constraint failed» |
| `POST /leads` con `assigned_rep_id: 999999` | **500** · lo mismo |
| `PUT /leads/{id}` con `assigned_rep_id: 999999` | **409** · «El correo 'elena.ruiz@fintechmx.com' ya está registrado en otro prospecto» |
| `PUT /leads/{id}` con `campaign_id: 999999` | **200** con la ficha entera, sin cambiar nada |

El 409 es el que conviene mirar dos veces. El correo que nombra es **el de la propia ficha**, que quien editaba no había tocado; el conflicto del que habla no ha ocurrido; y el consejo que da —cambie el correo— no arregla nada. Un 500 al menos no afirma nada falso.

Después del capítulo, las mismas cuatro:

| Petición | Respuesta |
| :--- | :--- |
| `POST /leads` con `campaign_id: 999999` | **422** · `loc: ["body", "campaign_id"]` · «No existe ninguna publicación con ese identificador.» |
| `POST /leads` con `assigned_rep_id: 999999` | **422** · `loc: ["body", "assigned_rep_id"]` · «No existe ninguna cuenta con ese identificador.» |
| `PUT /leads/{id}` con `assigned_rep_id: 999999` | **422** · el mismo renglón, y sin hablar del correo |
| `PUT /leads/{id}` con `campaign_id: X` | **422** · «La publicación que atrajo esta ficha no se cambia desde aquí: es cómo llegó, no un dato de la ficha.» |

Y lo que funcionaba sigue igual: el alta con una publicación real responde 201, la reasignación a un asesor real responde 200, y el correo repetido sigue contestando lo que contestaba.

El 422 llega con el campo en `loc`, así que **el mecanismo del capítulo 40 lo pinta debajo del campo sin tocar una línea del cliente**. Es el mismo regalo que se cobró el capítulo 41 por recortar antes de medir: cuando el error sale con la forma que el contrato ya tenía, la pantalla no hay que cambiarla.

---

## 42.5. Por qué el `except` no lee el mensaje del motor

El punto 26 proponía leer el error del motor, dialecto por dialecto. Esto es lo que dice SQLite, literal, en los tres casos:

```
UNIQUE constraint failed: leads.email
NOT NULL constraint failed: leads.first_name
FOREIGN KEY constraint failed
```

La tercera no nombra la columna, ni la tabla, ni el valor. Y es el caso más probable de los tres: una clave ajena es lo único de una fila que puede apuntar a algo que no está. Un arreglo que leyera el texto habría quedado **a medias en el motor del desarrollo y distinto en producción**, donde `psycopg2` sí trae el nombre de la restricción en `diag.constraint_name`; es decir, habría dependido del dialecto para dar o no dar el dato que el capítulo 40 necesita para pintar el error en su sitio.

Así que no se lee el mensaje. Se pregunta a la base cuál de sus reglas no se cumple, con la lista de reglas sacada de `__table__`:

```python
def motivo_del_rechazo(db, modelo, valores, *, id_propio=None) -> Rechazo:
    for columna in columnas_obligatorias_escribibles(modelo):
        if columna in valores and valores[columna] is None:
            return Rechazo(OBLIGATORIO, columna, "Este campo no puede quedar vacío.")

    sin_destino = claves_que_no_apuntan_a_nada(db, modelo, valores)
    if sin_destino:
        return sin_destino[0]

    ...  # las restricciones únicas, descontando la propia fila

    return Rechazo(CARRERA, None, MOTIVO_DE_LA_CARRERA)
```

Es la misma idea que el capítulo 33 tuvo con las columnas obligatorias y que el 41 generalizó: **la lista de reglas tiene un dueño, la tabla**, y preguntar no caduca. Una clave ajena nueva entra en la comprobación el día que se declara.

Tres detalles que no se ven al leerlo:

**El orden de las tres comprobaciones es el de lo que quien envió el cuerpo puede arreglar.** Una columna obligatoria vacía y una clave que no apunta a nada son errores del cuerpo —422, con el campo—; un valor repetido es un conflicto con otra fila —409—. Si dos reglas estuvieran mal a la vez, nombrar la del cuerpo es más útil que nombrar el conflicto.

**La propia fila no es un duplicado de sí misma.** Sin descontar `id_propio`, cualquier edición que no toque el correo encontraría su propia fila y contestaría que ese correo ya está cogido.

**Los valores se copian antes del `commit`.** Un `rollback` caduca los objetos de la sesión, así que leer `lead.campaign_id` después devuelve lo que la base tiene y no lo que se intentó escribir, que es lo único que explica el rechazo. Esto habría funcionado en el alta —el objeto es nuevo y conserva sus valores— y habría leído los valores viejos en la edición **sin que nada se pusiera rojo**. Por eso estas funciones reciben un diccionario y no la fila.

Y cuando no queda ninguna regla incumplida, la respuesta es `CARRERA` y no «no sé»: la base rechazó la fila hace un instante, así que algo pasó, y lo que pasó es que otra transacción lo cambió entre el intento y la pregunta. Devolver `None` habría dejado a cada `except` inventándose qué decir en ese caso, que es de lo que viene este módulo.

---

## 42.6. Los ocho `except IntegrityError`

Eran siete. Dos preguntaban, cuatro suponían y uno no tenía que averiguar nada:

| Dónde | Qué contestaba | Cómo lo decidía |
| :--- | :--- | :---: |
| `registro_de_actividad` | la actividad ya registrada, o vuelve a lanzar | **pregunta** (`_ya_registrado`) |
| `recalculation_service` | «hay un recálculo en curso» | **pregunta** (`trabajo_en_curso`) |
| `lead_repository.update` | «el correo ya está registrado en otro prospecto» | supone |
| `users.crear_usuario` | «ya existe una cuenta con ese correo» | supone |
| `crm.py` (webhook) | «esta entrega ya fue recibida» | supone |
| `motor_de_reglas._crear` | `False`, es decir «ya existía» | supone |
| `ciclo_de_publicaciones` | nada: repite la suma | **ni una cosa ni otra** |

Los cuatro que suponían ahora preguntan, y los dos que ya preguntaban **no se han tocado**: el capítulo 41 dejó escrito lo que pasa cuando se le añade una capa a algo que ya la tiene.

El séptimo —el contador de visitas de una publicación— se queda igual y queda inventariado con su motivo. No traduce el rechazo a ningún mensaje ni decide si la fila existía: vuelve a ejecutar el `UPDATE` que incrementa. Si el rechazo fuera otro, lo que se pierde es el recuento de una visita, que es la única cosa del sistema que puede perderse sin que nadie tenga que enterarse.

El octavo es nuevo, y es el punto 40: la red del alta.

```python
self.db.add(lead)
try:
    self.db.commit()
except IntegrityError as exc:
    self.db.rollback()
    raise self._lo_que_la_base_rechazo(valores) from exc
```

La edición lleva esa red desde el capítulo 33 con el comentario «red de seguridad ante dos actualizaciones simultáneas». El alta comprobaba el correo y después insertaba, sin nada entre las dos cosas, **y el archivo lo sabía**: el comentario de `leads.py:167` explica que acotar esa comprobación a la cartera propia «dejaría pasar un duplicado ajeno hasta el `INSERT` y lo convertiría en un 500». Estaba escrito el diagnóstico de una puerta que no tenía la red.

Y el conflicto para el que se escribió sigue contestando lo mismo: cuando lo que la base rechazó **es** el correo, la frase es la del capítulo 33, que es la que la pantalla ya enseña. Lo que cambia es todo lo demás.

---

## 42.7. La comprobación y la red no son la misma cosa, y hubo que demostrarlo

Esto no estaba previsto y lo encontró el arnés (§42.12). Las dos puertas de la ficha comprueban las claves ajenas **antes** de escribir:

```python
sin_destino = integridad.claves_que_no_apuntan_a_nada(self.db, Lead, enviados)
if sin_destino:
    raise integridad.LaBaseRechaza(sin_destino[0])
```

Al reintroducir los defectos del capítulo apareció que **quitar esa comprobación no ponía nada rojo**: la red del `except` clasifica el mismo rechazo y contesta el mismo 422, con el mismo campo y el mismo texto. Dos capas con la misma respuesta son una de más, y el capítulo 41 dejó dicho qué hacer cuando eso pasa: o falta una prueba, o el arreglo sobra.

Aquí faltaba la prueba, y lo que faltaba medir era **el momento**. Las dos capas no contestan en el mismo instante: la comprobación responde sin llegar a intentar la escritura, y la red existe para el hueco que la comprobación no puede cubrir —entre preguntar y escribir cabe otra transacción—. Así que la prueba mide eso, escuchando las instrucciones que la base recibe:

```python
respuesta, escrituras = _escrituras_sobre_fichas(lambda: client.post(...))
assert respuesta.status_code == 422
assert escrituras == []
```

Con la comprobación, la base no recibe ninguna inserción sobre `leads`. Sin ella, recibe una que falla. La misma prueba está escrita para la edición, porque que las dos puertas contesten lo mismo **y en el mismo momento** es exactamente lo que este capítulo vino a arreglar.

La comprobación **no** está acotada por el alcance de cartera, y es deliberado: existir no es lo mismo que poder verse, y si aquí se mirara solo lo que quien pide alcanza, un identificador real pero ajeno se diría «no existe», que es una respuesta falsa y que además cuenta algo por el camino. Es el mismo razonamiento, palabra por palabra, que el comentario de la comprobación del correo en el alta.

Hay un límite que también está escrito en una prueba: **una cuenta desactivada existe**, así que la ficha se le puede asignar igual que antes. La comprobación nueva responde «¿hay una fila ahí?», que es lo que la base pregunta y lo que convertía el error en un 500. Si además tiene que ser un asesor **activo** es otra decisión, con su propia discusión, y tomarla de paso habría cambiado a quién se le puede dar cartera sin que nadie lo pidiera.

---

## 42.8. El «duplicado» que descartaba un prospecto

De las cuatro suposiciones, la del webhook del CRM era la más cara, y se ve en lo que cuesta cada una cuando acierta y cuando no:

| Si acierta | Si no acierta |
| :--- | :--- |
| «el correo ya existe» → quien edita cambia el correo | …cambia un correo que no era el problema |
| «ya existe una cuenta» → el administrador usa otro correo | …usa otro correo y el fallo sigue |
| «ya existía» (tarea) → la pasada sigue, no había nada que hacer | …el trabajo que esa regla decidió crear no se crea y no consta |
| **«esta entrega ya fue recibida»** → el CRM no reintenta, y hace bien | **…el CRM no reintenta, y el prospecto no existe en ninguna parte** |

El último es el único que convierte un error en una pérdida silenciosa de datos: «duplicado» es una respuesta que **cierra el caso**. El emisor da por procesado un evento que nadie procesó.

Y lo llamativo es que dos capas más abajo, en el registro de actividad, ese mismo problema estaba resuelto desde el capítulo 25: `_ya_registrado` pregunta si el evento consta y **vuelve a lanzar** si no era un duplicado. La capa de arriba lo suponía.

El arreglo es la misma pregunta, en una consulta:

```python
db.rollback()
if entrega_registrada(db, signature=firma, idempotency_key=clave):
    raise duplicado from None
logger.error("La base rechazó la ingesta del webhook y no era una entrega repetida ...")
raise HTTPException(500, "Error durante el procesamiento del Webhook CRM.") from exc
```

Un 500 ante un rechazo que no se entiende es una respuesta honesta: el CRM reintenta, que es lo que hay que hacer cuando no se sabe qué pasó. `entrega_registrada` no mira si la entrada ha caducado, al contrario que `verificar_entrega`: aquí la pregunta no es si vale como respuesta repetida, sino si la fila existe, porque una entrada vencida que siguiera ahí explica igual el rechazo del índice único.

---

## 42.9. El 200 que no cambiaba nada

`LeadUpdate` no declaraba `campaign_id`, y el esquema no prohíbe campos de más. Resultado: `PUT /leads/{id}` con `{"campaign_id": 3}` respondía **200 con la ficha entera** y no cambiaba nada.

Es exactamente la forma del defecto que el capítulo 33 vino a arreglar, y que entonces se describió así: *«no respondía que no: respondía 200 con la ficha entera, de modo que la pantalla decía "Prospecto actualizado" y el dato seguía ahí»*. Aquel capítulo lo cerró para los campos que se vaciaban; sobrevivía en un campo que no estaba declarado.

Lo que entra es **dejar de decir sí a lo que no se hace**:

```python
campaign_id: Optional[int] = None

@field_validator("campaign_id")
@classmethod
def _la_atribucion_no_se_edita(cls, valor):
    raise ValueError(
        "La publicación que atrajo esta ficha no se cambia desde aquí: es cómo llegó, "
        "no un dato de la ficha."
    )
```

El campo se declara **para poder rechazarlo**: sin declararlo, Pydantic lo descarta antes de que nadie pueda verlo. Y se rechaza así y no con `extra="forbid"` porque prohibirle de golpe los campos de más a un cliente que ya existe es un cambio de contrato: rompería a quien mande un campo que el servidor lleva capítulos ignorando, sin corregir ningún dato.

Que la atribución **se pueda** corregir es una frase nueva —ninguna pantalla la pide— y se queda en §6.4.

---

## 42.10. Las dieciocho cláusulas, y el borrado que la Fase 14 ya había corregido

Las dieciocho claves ajenas declaran además qué pasa al borrar la fila a la que apuntan: once `CASCADE` y siete `SET NULL`. Varias llevan la frase escrita en el modelo:

```python
# De quién es el trabajo. Si la cuenta desaparece, su lista de tareas se va con ella:
# una tarea sin dueño no la ve nadie y no la puede hacer nadie.
asesor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
```

Ninguna prueba de la aplicación lo había comprobado nunca, por el mismo motivo de §42.2. Ahora hay una por cláusula, y las filas se construyen desde la propia tabla —diecinueve claves en dieciséis tablas; una fila escrita a mano por cada una envejece en la primera columna obligatoria que alguien añada—. El inventario de las cláusulas sí está escrito a mano, y es el único sitio de este capítulo donde algo lo está: una lista derivada del esquema y comparada con el esquema no comprueba nada. Lo que fija es la decisión, para que cambiarla se vea en una revisión.

Escribirlas enseñó dos cosas que no estaban previstas:

**Una tabla puede apuntar dos veces a la misma tabla con cláusulas distintas.** `tareas` apunta a `users` con `asesor_id` en cascada y con `cerrada_por_id` a nulo, así que borrar la cuenta se lleva la tarea entera por la primera y no deja ver lo que hace la segunda. La prueba de una cláusula `SET NULL` necesita que las demás claves de esa fila apunten a **otra** familia de filas.

**El borrado de una ficha no usa ninguna de las dieciocho.** `DELETE /leads/{id}` recorre el mapa de `derechos_del_titular`, derivado de las claves ajenas, porque la Fase 14 descubrió que fiarse de las cascadas dejaba atrás las entregas de webhook —su cláusula es `SET NULL`, así que la fila sobrevive con el prospecto a nulo—, los registros de ingesta revertida y el correo de la persona dentro de la bitácora.

Lo que quedaba de aquello es que **`LeadRepository.delete` seguía siendo el borrado que esa decisión había retirado**. No lo llamaba nadie —solo una prueba, para comprobar su rama de «fuera de alcance»— y era, para quien leyera el repositorio, la forma de borrar un prospecto. El día que alguien lo llamara, la supresión volvería a ser incompleta. Ahora delega en `suprimir_prospecto`, y la prueba que lo vigila mira la entrega de webhook, que es lo único que distingue los dos borrados.

**Y por eso este capítulo no lleva migración.** PostgreSQL ha rechazado estas filas desde que las claves existen, así que no hay nada que igualar: no puede haber en producción una fila que apunte a algo que no está. Donde puede haberla es en una base de desarrollo que haya vivido con el pragma apagado, y para eso no hace falta una migración: `PRAGMA foreign_key_check` las nombra.

---

## 42.11. La guarda: tres listas que salen del código

El capítulo deja tres cosas que no se pueden olvidar sin que algo se ponga rojo, y las tres se derivan:

1. **Las claves ajenas y sus cláusulas**, de `Base.metadata`. Una tabla nueva, una clave nueva o una cláusula cambiada rompen el inventario de §42.10, y entonces alguien decide.
2. **Las claves ajenas que pueden llegar en un cuerpo de petición**, cruzando los esquemas de entrada —la enumeración del capítulo 41, que recorre las rutas y la validación a mano— con las columnas del esquema. Un campo nuevo que se llame como una de ellas aparece el día que se declara, y hay que decir cómo se trata.
3. **Los `except IntegrityError`**, leyendo las fuentes. Cada uno tiene que llamar a una de las funciones que preguntan, o estar inventariado con su motivo.

El tercero tuvo un detalle divertido: la primera versión contaba diez donde hay ocho, porque varios comentarios de este mismo capítulo hablan de `except IntegrityError` dentro de una frase. Explicar el arreglo cambiaba la cuenta de lo arreglado. La guarda busca la cláusula, no la palabra.

Hay además una prueba que vigila el sitio del pragma: que esté en el motor y **no** en `conftest.py`. Y la que sostiene todas las demás, que es una línea:

```python
assert db_session.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
```

Sin ella, quitar el oyente del motor dejaría estas pruebas pasando **sin comprobar nada**, que es la peor forma de guarda que hay. Es el caso del capítulo 41 al revés: allí una guarda que no se podía hacer fallar, aquí una comprobación que el motor no hacía.

---

## 42.12. Lo que el arnés encontró

Veintitrés defectos reintroducidos uno a uno, cada uno con una sustitución literal, las pruebas que deberían verlo, y el archivo restaurado byte a byte. **Primera pasada: 19 detectados, 4 escapados.** Los cuatro escapes son el resultado útil del ejercicio:

| Defecto que escapó | Qué significaba |
| :--- | :--- |
| El alta no comprueba la clave ajena | La comprobación y la red contestan lo mismo: una de las dos parecía de más (§42.7) |
| La edición no comprueba la clave ajena | Lo mismo, en la otra puerta |
| El `except` del alta vuelve a culpar al correo | La red nueva **no tenía ninguna prueba**: la comprobación previa impedía llegar a ella |
| El borrado del repositorio vuelve a fiarse de las cascadas | La prueba miraba las tareas, y con las claves encendidas la cascada del motor también se las lleva: estaba mirando la tabla que no distingue los dos borrados |

El segundo par es el de siempre —faltaban pruebas, se escribieron: la red del alta se ejercita dejando pasar la comprobación, que es lo que ocurre cuando la publicación existe al preguntar y ya no existe al insertar; y el borrado se comprueba con la entrega de webhook—. El primer par es el que cambió el arreglo: obligó a escribir qué distingue a las dos capas, descubrir que es **el momento** y medir el momento.

Es la misma lección del capítulo 41 llegando por el otro lado. Allí el arnés dijo «este arreglo no hace nada» y el arreglo se quitó. Aquí dijo lo mismo y la respuesta fue otra: las dos capas sí se distinguen, pero nadie lo había escrito, y un arreglo cuya razón de ser no está en ninguna prueba es indistinguible de uno que sobra.

**Segunda pasada: 23 de 23.**

---

## 42.13. El control 56 del CI

`configuracion-peligrosa` pasa a tener 57 pasos y 56 controles. El 56 vigila la forma de las dos mitades del defecto, no su síntoma:

| | |
| :--- | :--- |
| 1 | `app/core/database.py` enciende las claves ajenas, y el oyente se registra **para SQLite** |
| 2 | `conftest.py` **no** lleva el pragma: así lo tendría la suite y no el desarrollo |
| 3 | `integridad.py` existe y conserva las tres funciones que preguntan |
| 4 | El renglón del 422 conserva el prefijo que el cliente reconoce como mensaje propio |
| 5 | Cada `except IntegrityError` llama a una de las funciones que preguntan, o está inventariado; y son ocho |
| 6 | El alta y la edición comprueban las claves ajenas del cuerpo —dos llamadas, una por puerta— |
| 7 | El borrado del repositorio sigue pasando por el mapa de los derechos del titular |
| 8 | `LeadUpdate` sigue rechazando `campaign_id` en vez de ignorarlo |
| 9 | Hay tantas cláusulas `ondelete` como claves ajenas: una clave sin cláusula deja al motor decidiendo por omisión |
| 10 | Las dos pruebas nuevas siguen derivando sus listas del código |

---

## 42.14. Lo que este capítulo no pagó

**La suite entera contra PostgreSQL.** El pragma hace que SQLite exija lo mismo que PostgreSQL en las tres clases de restricción que importan aquí —única, obligatoria y ajena—, y eso cubre el defecto de este capítulo. No cubre todo lo demás en lo que los dos motores se distinguen, y la única forma de saberlo es correr la suite contra PostgreSQL. Es un trabajo de infraestructura con su propia discusión —un servicio más en el CI y varios minutos en cada ejecución—, no una corrección. Entra en §6.4.

**La atribución que no se puede corregir.** Una ficha dada de alta a mano con la publicación equivocada no se puede arreglar por la API. Que se pueda es una frase nueva: §6.4.

**El 400 y el 409 de la misma puerta.** El alta contesta **400** cuando su comprobación encuentra el correo repetido y **409** cuando lo encuentra la red; la edición contesta 409 en los dos casos. Es la misma situación con dos códigos, y cambiar el 400 es tocar lo que un cliente ya recibe sin corregir ningún dato. §6.4.

**El nombre de la columna, donde sigue saliendo.** El 422 nuevo llega a dos sitios del panel. En la edición de una ficha va al aviso de arriba con su frase entera, porque esos dos campos no están en ese formulario —«es la diferencia entre repartir y perder»—. En el recuadro de reasignar asesor sale por `parseApiError` como `assigned_rep_id: No existe ninguna cuenta…`, con el nombre de la columna delante. Es exactamente el punto **37** de §6.4, que sigue abierto; este capítulo no lo amplía ni lo arregla a medias.

**Las dos respuestas que ya existían.** El 404 de la bandeja y el 422 del responsable de una publicación se quedan como están (§42.3).

---

## 42.15. Estado al cerrar

| | |
| :--- | :--- |
| Pruebas del servidor | **1673** pasadas, 2 omitidas |
| Pruebas del cliente | **637** pasadas en 40 archivos |
| Cobertura del cliente | 96.35 / 90.67 / 98.63 / 98.59 sobre suelos de 96 / 90 / 98 / 98 |
| `ruff` y `eslint` | sin avisos |
| Controles del CI | **56** |
| Defectos reintroducidos / detectados | **23 / 23** |
| Claves ajenas con su cláusula probada | **18 / 18** |
| `except IntegrityError` que preguntan | **7 de 8**, y el octavo con su motivo escrito |
| Migración | ninguna, y §42.10 dice por qué |
| Puntos de §6.4 cerrados | **26** y **40** |
| Puntos de §6.4 que entran | la suite contra PostgreSQL, la atribución que no se puede corregir, el 400 y el 409 de la misma puerta |

La frase del capítulo, para la próxima vez: **una restricción que el motor de las pruebas no hace cumplir es una restricción que nadie ha probado nunca**, y se nota en que encenderla no cambia nada.
