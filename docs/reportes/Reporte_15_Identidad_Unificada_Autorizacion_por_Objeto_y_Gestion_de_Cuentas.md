# Capítulo 15: Identidad Unificada, Autorización por Objeto y Gestión de Cuentas

## 15.1. Por qué existe esta fase

Los capítulos 11 a 14 endurecieron cómo se entra al sistema: quién eres, cómo se prueba,
cuánto dura tu sesión y qué queda escrito. Esta fase se ocupa de lo siguiente, que hasta
ahora no existía: **una vez dentro, sobre qué datos puedes actuar**.

| Hallazgo | Enunciado | Naturaleza |
| :--- | :--- | :--- |
| **N-16** | Dos tablas de personas sin relación entre sí: `users` y `sales_reps` | Una duplicación que impide una comprobación |
| **N-3** | No hay autorización por objeto: el rol decide qué verbos, nunca sobre qué datos | Una capa que falta entera |
| **N-4** | No hay endpoints de gestión: las cuentas solo existen si alguien ejecuta un script en el servidor | Una operación que se hace fuera del sistema |
| — | No hay política de contraseñas ni forma de cambiar la propia | Una ausencia con consecuencia práctica |

N-16 y N-3 están en ese orden por una razón que no es de estilo. Mientras hubiera dos
tablas de personas, N-3 **no se podía escribir**: «¿es este prospecto suyo?» compara el
dueño del prospecto con quien pregunta, y esos dos datos vivían en universos distintos que
ninguna clave relacionaba. La unificación no es una limpieza previa; es el requisito.

---

## 15.2. N-16 — Dos poblaciones de personas

### El defecto

El sistema tenía `users`, con quien puede iniciar sesión, y `sales_reps`, con quien atiende
prospectos. Ni una clave ajena entre ellas, ni la garantía de que un mismo correo apareciera
en las dos. El sembrado lo dejaba a la vista sin querer:

```python
# users
"admin.ti@plurione.com", "lider.ventas@plurione.com", "asesor.comercial@plurione.com"

# sales_reps
"carlos.morales@plurione.com", "ana.ruiz@plurione.com",
"valeria.mendoza@plurione.com", "diego.herrera@plurione.com"
```

Siete personas, cero coincidencias. Los prospectos se asignaban a los cuatro de abajo, que
no podían iniciar sesión; las tres cuentas de arriba no aparecían como asesores de nada.
Cada prospecto de la demostración tenía un dueño nominal y ningún dueño real.

`sales_reps` llevaba además su propia columna `role`, con valores que no existían en
ninguna parte del sistema de permisos: `Senior_Account_Executive`, `Enterprise_Sales_Lead`,
`BDR_Lead`. Dos vocabularios de roles, uno de ellos decorativo.

### La corrección

`SalesRep` desaparece. Ser asesor pasa a ser un atributo de una cuenta:

```python
class User(Base):
    ...
    # Marca si esta persona atiende cartera. No es un rol: `Sales_Lead` describe qué
    # puede hacer en el sistema, esto describe si además se le asignan prospectos. Un
    # administrador de TI tiene permisos sobre todo y no atiende a nadie.
    is_sales_rep = Column(Boolean, default=False, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    capacity = Column(Integer, nullable=True)   # NULL cuando no atiende cartera
```

Y `Lead.assigned_rep_id` pasa a apuntar a `users.id`. Esa línea es la fase entera: es lo
que convierte «¿es suyo?» en una comparación que se puede escribir.

Se fusionó en `User` y no al revés porque la identidad autenticable es la que manda. Ser
asesor es un atributo de alguien que entra al sistema, no una persona aparte.

### La migración mueve personas, no columnas

`a23deac578cf` está escrita a mano, y el orden importa. Traslada cada fila de `sales_reps`
a `users` emparejando por correo, reescribe `leads.assigned_rep_id` con el identificador
del usuario correspondiente, cambia la clave ajena y solo entonces retira la tabla.

Dos decisiones dentro de ella:

**El mapa se lee entero antes de escribir nada.** Los identificadores de `sales_reps` y los
de `users` son espacios distintos y pueden solaparse: el asesor 1 puede corresponder al
usuario 3, y el usuario 1 ser otra persona. Actualizar fila a fila leyendo el valor actual
traduciría dos veces el que ya se hubiera traducido. El ensayo se montó justamente sobre ese
choque —`sales_reps.id = 1` correspondiendo a `users.id = 3`— porque una base de prueba sin
colisiones habría dado el mismo resultado con el código roto.

**Las cuentas que crea no pueden iniciar sesión.** Reciben un marcador de contraseña
inutilizable:

```python
HASH_INUTILIZABLE = "!sin-contrasena:migracion-a23deac578cf"
```

No es un hash bcrypt válido y no puede serlo: `verify_password` intenta comprobarlo, bcrypt
lanza `ValueError` ante un salt malformado y la función devuelve `False`. Ninguna contraseña
coincide nunca. La alternativa —generar una contraseña real y anotarla en algún sitio para
completar la migración— crea una credencial que alguien conoce y que probablemente
sobreviva al despliegue. Estas cuentas quedan **activas** (siguen recibiendo cartera) pero
mudas hasta que un administrador les asigne contraseña.

La bajada reconstruye `sales_reps` y devuelve las asignaciones, pero **no borra cuentas**.
Un `downgrade` está para revertir estructura, no para borrar personas: eliminar las cuentas
que la subida creó destruiría los asientos de auditoría que las referencian.

### Ensayo con datos dentro

| Antes | Después |
| :--- | :--- |
| `sales_reps.1` Ana Torres (mismo correo que `users.3`) | `users.3` conserva su cuenta, gana `is_sales_rep` y `capacity=60` |
| `sales_reps.2` Luis Prado (sin cuenta) | `users.4`, sin contraseña utilizable, `must_change_password` |
| `sales_reps.3` sin correo | No se traslada; sus prospectos quedan **sin asignar**, que es visible |
| `leads` apuntando a `sales_reps.1` | Apuntan a `users.3`, no a `users.1` |
| `leads` apuntando a un id inexistente | `NULL` |

Ida y vuelta comprobadas, y `alembic check` limpio contra el esquema resultante.

---

## 15.3. N-3 — El rol decidía qué verbos, nunca sobre qué

### El defecto

Un asesor comercial autenticado veía la cartera completa de la empresa. Podía listar todos
los prospectos, abrir la ficha de cualquiera con su historial de actividades y sus
explicaciones generadas, y leer los KPIs consolidados de todo el pipeline. El control de
acceso existía y funcionaba: decidía que no podía *editar* ni *borrar*. Sobre qué datos
podía *mirar*, no había nada.

### Dónde se aplica el filtro, que es la decisión de esta sección

El filtro podría haber ido en cada endpoint. No va ahí, y el motivo se puede decir en una
frase: **los fallos de autorización son silenciosos**. Nadie recibe un 500 porque una
consulta devolvió prospectos ajenos; la respuesta es un 200 perfectamente formado. Un
filtro que dependa de que cada endpoint se acuerde de aplicarlo dejará de aplicarse en
cuanto se añada el siguiente con prisa, y ese día nadie se enterará.

Así que vive en el repositorio, el único sitio por el que hay que pasar para llegar a los
datos. Y el alcance es un argumento **obligatorio**:

```python
class LeadRepository:
    def __init__(self, db: Session, alcance: AlcanceDeCartera):
```

Sin valor por defecto, y no puede haberlo. Un `alcance=None` que significara «toda la
cartera» convertiría el olvido en acceso total, que es exactamente el fallo que este
módulo existe para impedir. Quien olvida el alcance recibe un `TypeError` en la primera
línea, en la suite, no en producción.

Los procesos sin persona detrás —la ingesta del CRM, el recálculo masivo— usan
`AlcanceDeCartera.del_sistema("motivo")`, que sí ve todo y **exige un motivo por escrito**.
Que abrirlo cueste una frase es el punto: aparece en la revisión.

### 404, no 403

Un prospecto ajeno responde igual que uno inexistente:

```python
def _no_encontrado(lead_id: int) -> HTTPException:
    """
    La alternativa —403 cuando existe pero es ajeno, 404 cuando no existe— convierte el
    endpoint en un oráculo: recorrer identificadores devuelve el mapa de la cartera
    completa sin ver un solo dato.
    """
```

La distinción sí se conserva, pero hacia dentro: el intento sobre un prospecto real y ajeno
queda en la bitácora como `acceso.fuera_de_alcance`. Un 404 suelto es un enlace viejo; una
tanda seguida de la misma cuenta es alguien recorriendo identificadores, y eso solo se ve si
queda escrito. El 404 por identificador inexistente **no** se registra: no dice nada de nadie.

### La contrapartida: un asesor ahora sí edita lo suyo

`PUT /leads/{id}` estaba reservado a `Sales_Lead` y `System_Admin`. Un asesor no podía
corregir el teléfono de su propio prospecto. Eso empuja a pedirle cada cambio al líder
comercial —o, lo que ocurre de verdad, a repartir el rol de líder para que la aplicación sea
usable. Una restricción demasiado gruesa acaba produciendo permisos de más.

Ahora el permiso lo da la propiedad del objeto. Lo que sigue reservado a quien dirige la
cartera es **reasignar**: cambiar el dueño de un prospecto es repartir trabajo, no
atenderlo, y un asesor que pudiera hacerlo podría quitarse de encima lo que no le apetece o
apropiarse de lo ajeno.

El **borrado** también sigue reservado, y es una asimetría deliberada frente a la edición:
editar es reversible y queda en el historial de scores; borrar se lleva por delante
actividades e historial en cascada, y eso no vuelve.

### Tres casos que la acotación obliga a resolver aparte

**El prospecto que crea un asesor queda suyo.** Sin esta regla, un asesor que creara un
prospecto sin dueño lo perdería de vista en el mismo instante: quedaría fuera de su propio
alcance y no podría volver a abrirlo.

**La comprobación de duplicados NO se acota**, y va a contracorriente del resto de la clase:

> `leads.email` es único en toda la tabla. Si un asesor comprobara duplicados solo dentro
> de su cartera, un correo que ya pertenece a otra persona pasaría la comprobación y
> estallaría en el INSERT: el usuario recibiría un 500 en vez de un 400. Sí, esto permite
> averiguar si una dirección concreta está en el sistema. Es una fuga real y pequeña, y no
> hay forma de cerrarla mientras la columna sea única: ocultarla no elimina la señal, solo
> la convierte en un error del servidor, que revela lo mismo y encima rompe.

**Los agregados también revelan.** Filtrar el listado y dejar `/analytics/summary` contando
la empresa entera sería arreglar la puerta y dejar la ventana: sin abrir una sola ficha, un
total y una media dicen el tamaño y la salud del pipeline completo. El resumen se acota.

El informe por campaña, en cambio, **no se acota: se restringe** a quien dirige la cartera.
Acotarlo daría una rentabilidad falsa —los prospectos de una persona divididos por el
presupuesto entero de la campaña—, y publicar un número de negocio mal calculado hace más
daño que no publicarlo.

---

## 15.4. N-4 — Las cuentas se gestionaban fuera del sistema

### Lo que faltaba

Añadir a una persona, retirar a quien se marchó o cambiarle el rol exigía acceso al servidor
y a la línea de comandos. En la práctica eso significa que lo hacía quien tuviera ese
acceso, sin dejar rastro, y que el equipo compartía las tres cuentas de demostración. **Un
sistema de roles no protege nada si la forma normal de trabajar es que varias personas usen
la misma cuenta.**

`/api/v1/users` (solo `System_Admin`) y `/api/v1/campaigns` (`Sales_Lead` y `System_Admin`)
cierran ese hueco. Toda mutación escribe en `audit_log`, con acción propia.

### Tres decisiones

**No hay borrado, hay baja.** `DELETE /users/{id}` desactiva. Es un `DELETE` que no borra, y
esa incoherencia aparente es la decisión: eliminar la fila dejaría sin sujeto los asientos de
auditoría de esa persona —el registro de quién eliminó qué se convertiría en un identificador
que ya no resuelve— y pondría a `NULL` el asesor de todos sus prospectos sin dejar constancia.
La respuesta a «se fue de la empresa» es que deje de entrar, no que desaparezca de la historia.
Sus prospectos **se conservan asignados a ella**: reasignarlos automáticamente repartiría
cartera sin que nadie lo decidiera.

**Un administrador no puede quitarse a sí mismo.** No es cortesía. El caso no es hipotético:
es el administrador que se cambia el rol «para ver cómo lo ve un asesor». Sin la
comprobación, la operación funciona, y a partir de ese momento no queda nadie con permiso
para deshacerla — la única salida es editar la base a mano. La comprobación cuenta cuántos
administradores activos quedarían, así que no es un bloqueo permanente: con un segundo
administrador, la operación procede.

**Un cambio de permisos cierra las sesiones.** El rol viaja dentro del token ya emitido. Sin
revocar, quien acaba de perder permisos los conserva hasta que su token caduque: un usuario
degradado seguiría administrando durante los siguientes quince minutos, que es tiempo de
sobra para hacer justo aquello por lo que se le degradó.

### Campañas

Las campañas existían en el modelo desde el principio y solo podían crearse sembrando la
base: el informe de rendimiento por campaña estaba, pero no había forma de dar de alta la
campaña cuyo rendimiento se quería medir.

El reparto de permisos no es el de las cuentas, a propósito: una campaña es una decisión
comercial, no de sistemas. Tampoco hay borrado — desactivarla en lugar de borrarla evita
poner a `NULL` la campaña de cada prospecto que atrajo, que es la atribución de la inversión
y el número por el que existe la tabla.

Una diferencia menor con la bitácora de prospectos, que conviene explicar porque parece una
inconsistencia: el cambio de presupuesto **sí registra los valores** anterior y nuevo,
mientras que la edición de un prospecto solo anota los nombres de los campos tocados. Los
datos de un prospecto son personales y duplicarlos en una tabla con otro criterio de acceso
los expone dos veces; una cifra de presupuesto no es un dato personal, y su historial de
cambios es justo lo que alguien querrá reconstruir cuando el rendimiento no cuadre.

---

## 15.5. Contraseñas

### Dos huecos

El primero: no había política. El login exigía ocho caracteres y nada más, así que
`password` era una contraseña válida del sistema.

El segundo, más grave en la práctica: **no había forma de cambiar la contraseña**. Hacerlo
—lo primero que hay que hacer con una recibida de otra persona, y lo urgente cuando se
sospecha que se filtró— exigía que un administrador entrara al servidor a ejecutar el script
de sembrado, que además reescribía las tres cuentas a la vez. En la práctica eso significa
que las contraseñas no se cambiaban nunca.

### Longitud antes que ceremonia

El mínimo son 12 caracteres y **no** se exige mayúscula, número y símbolo. Esa exigencia
produce `Verano2026!` —que cumple las cuatro reglas y es de las primeras que prueba
cualquier diccionario— mientras rechaza `caballo grapa batería correcta`, que es
incomparablemente más fuerte. Lo que se pide es más modesto: variedad real (tres clases de
carácter) **o** longitud suficiente para no necesitarla (16+).

El máximo son **72 bytes**, no caracteres, porque bcrypt trunca ahí en silencio. Una
contraseña de 40 caracteres acentuados ocupa 80 bytes: aceptarla dejaría fuera un trozo sin
que nadie se enterara, y quien la eligió creería tener una protección que no tiene.

Se devuelven **todos** los motivos del rechazo, no el primero. Dar uno solo obliga a
descubrir la política a base de intentos, y cada rechazo empuja un poco más hacia poner lo
primero que se acepte.

Lo que la política **no** hace, dicho para que no se deduzca: no caduca contraseñas por
tiempo. Forzar cambios periódicos empuja a rotar un sufijo, y lo que se gana en rotación se
pierde en calidad. `password_changed_at` se registra para poder auditarlo, no para exigirlo.

### El cambio propio, y por qué pide la contraseña actual

`POST /api/v1/auth/change-password` exige la credencial actual aunque la sesión ya esté
autenticada. Un token robado, o un equipo que alguien dejó abierto, permite todo lo que la
aplicación permita sin volver a preguntar; pedir la contraseña actual es lo único que impide
convertir ese acceso prestado en uno permanente. **Si el token bastara, el robo de una
sesión de quince minutos se transformaría en la pérdida definitiva de la cuenta.**

Cierra **todas** las sesiones, incluida la que hizo el cambio. Es incómodo, y es la parte
que más importa: quien cambia su contraseña casi siempre lo hace porque cree que alguien más
la tiene, y dejar vivas las sesiones abiertas con la credencial anterior deja dentro
precisamente a quien se quería echar. Cerrar solo «las demás» tampoco vale: no hay forma de
saber cuál de dos sesiones es la legítima.

Un restablecimiento hecho por un administrador marca la cuenta con `must_change_password`:
quien fija la contraseña la conoce, y una credencial que conoce otra persona no identifica a
nadie. La contraseña no se devuelve en la respuesta ni se escribe en la bitácora; el asiento
registra que hubo un restablecimiento, no cuál fue el valor.

---

## 15.6. Frontend: la pantalla que enseñaba gente inventada

`AdminPanel.jsx` mostraba un array de tres personas escrito dentro del propio componente,
con roles que no existían en el backend (`Asesor Comercial Senior`, `Administrador TI`), y
para rellenar la columna de «leads activos» lanzaba **una petición al listado de prospectos
por cada persona**: tantas consultas como miembros del equipo, cada una trayendo una página
entera de prospectos para leer un único número, y todo contra identificadores fijos que no
tenían por qué corresponder con nadie real.

Peor: cuando la API fallaba, el componente caía en el array fijo. La pantalla seguía
enseñando un equipo plausible con el backend caído.

Ahora `/sales-reps` devuelve el equipo con su carga ya contada en **una sola consulta
agregada** —con `LEFT JOIN`, para que un asesor sin cartera salga con cero en lugar de
desaparecer, que es precisamente a quien hay que ver para repartirle trabajo—, y el fallo se
muestra como fallo. El administrador tiene además alta de cuentas, cambio de rol, baja,
reactivación y restablecimiento de contraseña; y cualquier usuario puede cambiar la suya
desde el menú de sesión.

---

## 15.7. Verificación

### Pruebas

| Fichero | Pruebas | Qué fija |
| :--- | ---: | :--- |
| `test_autorizacion_por_objeto.py` | 28 | El alcance, el filtro del repositorio, el 404 indistinguible, la reasignación |
| `test_gestion_de_identidades.py` | 24 | Alta, baja lógica, rol, reset, y las puertas que no se pueden cerrar por dentro |
| `test_politica_de_contrasenas.py` | 22 | La política y el cambio propio |
| `test_campanas.py` | 12 | Permisos, baja lógica, bitácora del presupuesto |

**Total: 428 pruebas, 91 % de cobertura** (2958 sentencias, 253 sin cubrir), `ruff` limpio.

### Ninguna comprueba sobre una cartera de un solo dueño

Casi todas las de autorización usan el fixture `cartera_repartida`, que reparte los
prospectos entre el asesor de pruebas y otra persona. Hace falta que en la misma base
existan a la vez prospectos propios y ajenos: **con una cartera de un solo dueño, una prueba
pasaría igual con el filtro completamente roto.**

### Ninguna de las cinco es una prueba complaciente

Una prueba que no ha fallado nunca no ha demostrado nada. Se reintrodujo cada defecto, uno
por uno, y se corrió la suite entera:

| Defecto reintroducido | Fallos | Dónde |
| :--- | ---: | :--- |
| El repositorio deja de filtrar por dueño | **11** | `test_autorizacion_por_objeto.py`, `test_security_rbac.py` |
| Un asesor puede reasignar cartera | **4** | `test_autorizacion_por_objeto.py` |
| La gestión de cuentas se abre a cualquier rol | **2** | `test_gestion_de_identidades.py` |
| El cambio de contraseña deja de pedir la actual | **2** | `test_politica_de_contrasenas.py` |
| El resumen analítico deja de acotarse | **1** | `test_autorizacion_por_objeto.py` |

Veinte fallos en total, **todos en el fichero que corresponde y ninguno fuera de él**. Esa
localización importa tanto como el número: una prueba que falla al reintroducir un defecto
que no le toca no está comprobando lo que dice comprobar. Restaurado el código, 428 en verde.

### Un fallo que las pruebas nuevas destaparon en la propia suite

Al integrar los ficheros nuevos, ocho pruebas anteriores empezaron a fallar —y pasaban
todas en aislamiento—. La causa estaba en el `conftest`: las tres cuentas de la suite
sobreviven al vaciado entre pruebas, porque crearlas cuesta un hash bcrypt deliberadamente
lento. Esa optimización era inocua mientras ninguna prueba tocara las cuentas. En cuanto
aparecieron pruebas que degradan roles y cambian contraseñas, dejó de serlo: una prueba que
degradaba a un usuario para comprobar que sus sesiones se cerraban lo dejaba degradado, y la
siguiente que esperaba un 403 recibía un 401 sin que nada apuntara a la causa.

Se resolvió restaurando las cuentas a un estado conocido en el desmontaje —con el hash
calculado una sola vez en toda la ejecución—, lo que convierte esa optimización en algo
seguro en vez de frágil. Vale la pena registrarlo porque es el mismo patrón que persigue
esta fase: algo que funcionaba por una condición que nadie había escrito.

### Guardas en el pipeline

El trabajo `configuración-peligrosa` pasa de 10 a **14 pasos** (10 trabajos, 69 pasos en
total). Las cuatro nuevas:

| Guarda | Qué impide |
| :--- | :--- |
| El repositorio de prospectos exige alcance | Que el alcance vuelva a tener valor por defecto, o que aparezca un `LeadRepository(db)` |
| La gestión de cuentas no borra ni publica hashes | Un `db.delete(usuario)`, o un `hashed_password` declarado en un esquema de respuesta |
| El cambio de contraseña propio exige la actual | Que baste el token para quedarse con la cuenta |
| El frontend no lleva equipo comercial escrito a mano | Que vuelva `DEFAULT_SALES_REPS` |

Las cuatro se comprobaron reintroduciendo su defecto: las cuatro dispararon, y con el
código restaurado ninguna detecta nada.

Una de ellas tropezó al principio con **el comentario que explica el propio arreglo** —el
docstring del módulo de esquemas menciona `hashed_password` para decir por qué no debe estar
ahí—. Se afinó para mirar declaraciones de campo (`^\s*hashed_password\s*:`) y no la palabra
suelta: una guarda que no distingue el código de la prosa que lo justifica obliga a no
explicar los arreglos, que es un precio absurdo.

---

## 15.8. Lo que esta fase **no** resuelve

1. **La lista de contraseñas prohibidas es corta y específica del contexto** (unas veinte
   entradas: las clásicas, el nombre del producto, el de la empresa). No sustituye a una
   lista de millones de contraseñas filtradas; eso pide un servicio externo o un fichero
   grande. Se dice aquí en lugar de fingir que está resuelto.

2. **No hay segundo factor.** Una contraseña fuerte sigue siendo un solo factor, y todo lo
   que esta fase protege —la cartera de cada asesor, la gestión de cuentas— cuelga de ella.

3. **La marca `must_change_password` se registra pero no se fuerza.** La cuenta queda
   señalada y la interfaz lo muestra, pero el backend no bloquea el resto de operaciones
   hasta que se cambie. Cerrar ese bucle exige interceptar toda petición autenticada de una
   cuenta marcada y dejar pasar solo el cambio de contraseña; es la continuación natural y no
   está hecha.

   *Cerrado en el Capítulo 19 (§19.2): el servidor rechaza con 403 toda petición de una
   cuenta marcada salvo consultar su perfil, cambiar la contraseña y cerrar la sesión.*

4. **La cartera de quien se va no se reparte sola.** La baja conserva sus prospectos
   asignados, deliberadamente, pero eso significa que quedan a nombre de una cuenta
   desactivada hasta que alguien los reparta. No hay aviso que lo recuerde: el asiento de
   auditoría anota cuántos eran, y ahí se queda.

   *Cerrado en el Capítulo 19 (§19.3): el equipo comercial avisa de los prospectos
   asignados a cuentas de baja aunque el listado las oculte, y el líder los reparte.*

5. **`is_sales_rep` sobre las cuentas migradas se dedujo del rol.** Las cuentas que ya
   existían con un rol comercial quedaron marcadas como asesoras. Es la interpretación
   razonable y puede no coincidir con la realidad de una organización concreta; se corrige
   desde la pantalla de administración, que para eso existe.

---

## 15.9. Estado de los hallazgos de esta ronda

| Hallazgo | Estado | Dónde |
| :--- | :--- | :--- |
| **N-16** | Corregido, con migración de datos ensayada | `entities.py`, `a23deac578cf`, `seed_data.py` |
| **N-3** | Corregido en el repositorio, no en los endpoints | `core/autorizacion.py`, `lead_repository.py`, `analytics_service.py` |
| **N-4** | Corregido | `endpoints/users.py`, `endpoints/campaigns.py`, `schemas/user.py` |
| Contraseñas | Corregido, con límites en §15.8 | `core/passwords.py`, `auth.py`, `SessionModal.jsx` |

Los cuatro tienen prueba de regresión que falla si se revierten, y todos menos la migración
tienen además una guarda en el pipeline que los detecta sin ejecutar la suite.
