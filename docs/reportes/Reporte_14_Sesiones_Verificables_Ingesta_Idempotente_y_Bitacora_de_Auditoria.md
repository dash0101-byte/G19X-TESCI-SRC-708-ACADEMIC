# Capítulo 14: Sesiones Verificables, Ingesta Idempotente y Bitácora de Auditoría

## 14.1. Por qué existe esta fase

Los capítulos 11 a 13 cerraron los treinta y seis hallazgos de la auditoría interna. Esta
fase no viene de allí: viene de una segunda pasada sobre el código **ya corregido**, que
es donde aparecen los defectos de una clase distinta —los que no están en lo que falta,
sino en lo que se dio por hecho—.

| Hallazgo | Enunciado | Naturaleza |
| :--- | :--- | :--- |
| **N-1** | La rotación de tokens de refresco es nominal: se emite uno nuevo y el anterior sigue valiendo | Una promesa del código que el código no cumple |
| **N-2** | La firma HMAC autentica el cuerpo pero no acredita que la petición sea nueva | Una garantía confundida con otra |
| **N-6** | `TRUST_PROXY_HEADERS` viene activada por defecto, y el contador de tasa vive en memoria | Un valor por defecto cómodo |
| **N-8** | No hay traza de lo que hacen las personas, solo de lo que les pasa a los datos | Una ausencia, no un error |

Los cuatro comparten algo con los de la fase anterior: ninguno produce un síntoma. Pero
N-1 va más lejos, y por eso encabeza el capítulo. Su docstring decía:

> *"Rota también el refresh token en cada uso, de modo que la ventana de validez de una
> cookie robada se limita al tiempo que tarde el usuario legítimo en refrescar."*

Eso era falso. El endpoint entregaba un token nuevo, sí, pero no invalidaba el anterior:
lo único que se comprobaba era `token_version`, que solo cambia al cerrar sesión. **Un
comentario que describe una protección inexistente es peor que no tener el comentario**,
porque cierra la pregunta. Quien lea ese archivo buscando si la rotación está resuelta
encuentra que sí, y pasa a otra cosa.

---

## 14.2. N-1 — La rotación de sesión era nominal

### El defecto

```python
def refresh_session(...):
    ...
    if payload.get("ver") != user.token_version:      # única comprobación de revocación
        raise expired
    return _issue_session(response, user)             # emite uno nuevo; el viejo sigue vivo
```

`token_version` sube al cerrar sesión. Entre un login y un logout puede pasar una semana,
y durante toda esa semana **cualquier copia del refresh token vale**, tantas veces como se
quiera. La consecuencia práctica:

* una cookie robada —copia de un respaldo, acceso al equipo, un intermediario mal
  configurado— daba **siete días de acceso renovable**;
* el robo era **invisible**: víctima y atacante refrescaban en paralelo, cada uno con su
  propia cadena de tokens, sin estorbarse. No había ninguna señal que generar, porque
  nada resultaba anómalo.

### La corrección

Cada emisión pasa a tener identidad y pertenencia:

| Claim | Significado |
| :--- | :--- |
| `jti` | Esta emisión concreta. Se marca como consumida al refrescar. |
| `fid` | La **familia**: constante en toda la cadena nacida de un mismo login. |
| `ver` | `token_version`. Se conserva, no se sustituye. |

Sobre la tabla `refresh_tokens` se sostiene un invariante simple: **una familia tiene como
mucho un token vigente**. Emitir uno revoca cualquier otro vivo de esa familia. De ahí sale
la detección, que no necesita heurística ninguna:

> Presentar un token ya consumido solo puede significar que dos partes tienen la misma
> cookie. Como no hay forma de saber cuál es la legítima, se revoca la familia entera y
> las dos vuelven a autenticarse.

El robo pasa de costar siete días de acceso silencioso a costar una sesión, y deja un
asiento en la bitácora (`auth.refresh_reutilizado`) con la familia afectada y cuántos
tokens cayeron.

Cada login abre su **propia** familia. Es lo que permite que revocar la sesión de un
portátil comprometido no cierre la del teléfono: son cadenas independientes.

### La decisión incómoda: la ventana de gracia

Aquí hay un conflicto real, y prefiero exponerlo antes que presentar la medida como
gratuita.

El cliente deduplica los refrescos concurrentes **dentro de una pestaña** —hay una promesa
compartida en `frontend/src/services/api.js`— pero no entre pestañas: cada una tiene su
propio módulo. Dos pestañas abiertas pueden refrescar a la vez, y la segunda llegaría con
un token que la primera acaba de consumir. Con detección estricta, eso expulsa de su sesión
a un usuario que no hizo absolutamente nada.

La solución es una ventana de gracia de diez segundos (`REFRESH_ROTATION_GRACE_SECONDS`):
un token consumido hace menos de ese margen —y consumido por rotación normal, no por
revocación— se trata como esa carrera y se rota sin incidente.

**Coste de esta decisión:** reabre la ventana de uso de una cookie robada durante esos
segundos. Es la parte que no me gusta y que hay que decir en voz alta. Lo que la justifica
es la comparación honesta: diez segundos frente a los siete días de antes, a cambio de que
la medida sea sostenible. Una protección que expulsa a la gente de su sesión se acaba
desactivando, y una protección desactivada vale exactamente cero.

### Al desplegar

Los refresh tokens ya emitidos no tienen fila en la tabla nueva, así que su primer refresco
se rechaza y esos usuarios inician sesión una vez más. Es el comportamiento correcto —un
token sin registro no se puede consumir— y conviene anunciarlo antes de desplegar, no
descubrirlo como una incidencia.

---

## 14.3. N-2 — La firma autentica el cuerpo, no la novedad de la petición

### El defecto

El webhook estaba bien protegido contra falsificación: HMAC-SHA256 sobre
`<timestamp>.<cuerpo>`, comparación en tiempo constante, ventana anti-replay de cinco
minutos. Lo que faltaba es que **nada de eso impide reenviar una petición legítima**.

Quien capture una entrega —un intermediario, un log de acceso que registre cuerpos,
cualquier tramo sin TLS— puede reenviarla tal cual. Dentro de la ventana de tolerancia
vuelve a pasar todas las comprobaciones, porque es literalmente la misma petición que ya
pasó. Cada repetición añadía otra actividad al prospecto, movía su score y sumaba una fila
de auditoría de integración.

Es una confusión de garantías fácil de cometer: la ventana anti-replay **acota el daño en
el tiempo**; no lo impide dentro de ella, que es exactamente donde ocurre.

### Dos huellas, dos intenciones

La corrección distingue dos cosas que se parecen mucho y no son lo mismo:

| Qué llega | Qué es | Respuesta |
| :--- | :--- | :--- |
| Mismos bytes, misma firma | Un replay. Ningún emisor honesto reenvía con la misma marca de tiempo | **409** |
| Mismo evento, firma nueva | Un reintento: al CRM se le perdió la respuesta | **200 con la respuesta original** |

La segunda fila importa tanto como la primera. Un reintento que recibe un error distinto
del original no puede distinguir «ya estaba hecho» de «volvió a fallar», y acaba
reintentando indefinidamente. Se le devuelve lo que pedía, con una cabecera
`X-PluriOne-Idempotent-Replay: true` para que quien depure la integración pueda
distinguirlo de un segundo procesamiento.

### Una desviación deliberada del enunciado

El hallazgo pedía «idempotencia por `external_lead_id` + evento». La clave implementada
lleva además **la huella SHA-256 del cuerpo**, y conviene explicar por qué me aparté.

Con la clave a secas, dos `lead.updated` distintos del mismo prospecto dentro de la ventana
se colapsarían en uno, y la segunda actualización —la buena— se descartaría **en silencio**.
Eso sería un fallo peor que el que se está corrigiendo, porque no da error: simplemente
pierde el dato. Con la huella del cuerpo, un reintento (cuerpo idéntico) se detecta y dos
cambios reales (cuerpos distintos) se procesan los dos. Hay una prueba dedicada a este
caso, `test_dos_cambios_reales_seguidos_se_procesan_los_dos`.

### Dónde se confirma la reserva

La fila de `webhook_deliveries` se añade a la sesión **antes** de procesar y se confirma con
la misma transacción que el alta del prospecto. No es un detalle de implementación:

> Si la reserva se confirmara por su cuenta, un evento cuyo pipeline de scoring falla
> dejaría un candado sobre sí mismo. El CRM reintentaría, recibiría «duplicado», y el
> prospecto no existiría en ninguna parte.

Reserva e ingesta viven o caen juntas. Y si dos entregas idénticas confirman a la vez, el
índice único decide: la segunda falla y el endpoint la traduce a 409, que es la respuesta
correcta, porque la primera ya hizo el trabajo.

La limpieza de entradas caducadas va colgada del propio flujo de ingesta —esta pila no
despliega ningún planificador— y se autolimita a una ejecución cada cinco minutos por
proceso. Sin ese freno, un CRM con picos de sincronización pagaría un `DELETE` por evento.

---

## 14.4. N-6 — Quién es el cliente

### El defecto

```python
TRUST_PROXY_HEADERS: bool = True     # ← valor por defecto
```

`X-Forwarded-For` la escribe el cliente. Con la confianza activada por defecto, un backend
alcanzable directamente —el `ports: 127.0.0.1:8000` de esta misma pila, un despliegue sin
proxy, un puerto abierto por descuido— acepta como identidad lo que le manden. Y como el
tope de tasa cuenta *por identidad*, basta con rotar un valor inventado en cada intento
para que el límite de login no llegue a aplicarse nunca.

El valor por defecto correcto es el restrictivo. Quien tiene un proxy de confianza delante
lo declara —`devops/docker-compose.yml` lo hace— y esa declaración es un acto consciente de
quien sabe que nginx reescribe la cabecera. Quien no lo declara pierde precisión al agrupar
clientes, que es un fallo hacia el lado seguro.

La resolución de la IP se unificó en `app/core/proxy.py`, con dos consumidores: el
limitador y la bitácora. Si cada uno la resolviera a su manera, un bloqueo por fuerza bruta
quedaría atribuido a una dirección y el intento que lo provocó a otra —justo el cruce que
se querría hacer al investigar—.

### El contador en memoria

El segundo tramo del hallazgo es que `RATE_LIMIT_STORAGE_URI` valía `memory://`. La imagen
arranca uvicorn con varios workers, y cada uno lleva su propia cuenta: el tope real que ve
un cliente es el declarado **multiplicado por el número de workers**. Medido en la fase de
rendimiento: con 2 workers y `"10/minute"` pasaban entre 11 y 20 intentos antes del corte.

La pila de compose levanta ahora un `redis:7-alpine` propio y el backend apunta a él. Sin
persistencia a disco (`--save "" --appendonly no`): son contadores derivados y efímeros, y
escribir en un fichero algo que caduca en un minuto solo cuesta. Sin publicar el puerto,
por la misma razón que PostgreSQL: solo lo necesita el backend, y un Redis sin contraseña
en la red del anfitrión es acceso directo.

---

## 14.5. N-8 — La bitácora de auditoría

### Lo que faltaba

El sistema trazaba bien lo que les pasaba a los **datos**: `crm_integration_logs` para la
sincronización, `score_histories` para cada puntuación. Lo que no trazaba es lo que hacían
las **personas**.

* Un prospecto borrado desaparecía sin dejar constancia de quién lo borró.
* Un recálculo masivo, que reescribe la cartera entera, solo constaba en el `logger` del
  contenedor, que rota y se pierde.
* Un intento denegado por rol no dejaba nada persistente. Una sola denegación es ruido;
  una tanda seguida de la misma cuenta es alguien tanteando los límites de su rol, y eso
  solo se ve si queda escrito.

### Cómo se escribe

Desde una dependencia con `yield`, no desde cada endpoint:

```python
auditoria: AsientoDeAuditoria = Depends(auditar(ACCION_LEAD_ELIMINAR, ENTIDAD_LEAD))
...
auditoria.anotar(entidad_id=lead_id, email=condenado.email)
```

Un `db.add(AuditLog(...))` repetido a mano en veinte sitios se olvida en el veintiuno, y el
que se olvida es siempre el que hace falta. El endpoint solo añade lo que él sabe; el
resultado lo pone la dependencia, de modo que un 404 o un 409 quedan registrados como lo
que fueron y no como una operación correcta.

**Las denegaciones se escriben desde `require_roles`, no desde esa dependencia.** El 403
nace ahí, antes de que el endpoint —y por tanto su asiento— llegue a ejecutarse. Si se
esperara al desmontaje de la dependencia, la única operación que nunca quedaría registrada
sería precisamente la que alguien intentó hacer sin permiso.

### Dos decisiones que conviene justificar

**El actor va desnormalizado** —id, correo y rol— en lugar de por clave foránea. Una
bitácora que resolviera el nombre a través de la fila del usuario perdería la autoría en
cuanto la cuenta se eliminara, justo en el caso en que más falta hace saber quién actuó. Y
el rol guardado es el que tenía *en ese momento*, no el que tenga hoy.

**Se escribe sobre la sesión de la petición**, no sobre una independiente. La tentación es
abrirla aparte para que la bitácora sobreviva a un `rollback` del negocio, pero el
desmontaje ocurre *después* de que el endpoint haya terminado: a esas alturas la
transacción ya se confirmó o ya se deshizo. A cambio se evita un problema real: con SQLite
en memoria y `StaticPool` —la configuración de la suite— dos sesiones comparten conexión, y
un `commit` desde la «independiente» confirmaría de paso lo que hubiera pendiente en la
otra.

### Quién puede leerla, y qué no se puede hacer con ella

`GET /api/v1/audit` es **solo `System_Admin`**, y no por formalidad. La bitácora concentra,
en un sitio y ya correlacionado, quién trabaja con qué cartera, desde qué direcciones se
conecta cada persona y a qué horas. Es el resumen más útil que existe del comportamiento
interno de la empresa. Dársela a un `Sales_Lead` «porque es responsable del equipo»
convertiría una medida de control en vigilancia entre compañeros.

Es **de solo lectura**: no hay endpoint que borre ni edite asientos. Una bitácora que la
aplicación puede reescribir no prueba nada, porque lo primero que borraría quien abusa de
sus permisos es el registro de que lo hizo. La retención se aplica desde fuera, con las
herramientas de la base de datos.

> **Nota del capítulo 20.** Sigue sin haber endpoint que borre o edite asientos, pero desde
> la Fase 14 hay una operación que sí cambia su **contenido**: suprimir a un prospecto
> sustituye por `[suprimido]` los datos personales de esa persona dentro de los asientos que
> la mencionan. El asiento, su autor, su rol y su fecha se quedan. Y el asiento del propio
> borrado ya no guarda el correo, como hacía desde esta fase para no quedarse en «solo un
> número»: guarda cuántas filas salieron de cada tabla y una huella con clave del correo.
> Guardar el correo de quien pidió ser borrado era no borrarlo (§20.4).

Y consultar la bitácora queda **registrado en la bitácora**. El administrador es el único
rol que puede leer aquí y, por tanto, el único cuyo acceso nadie más vería si no quedara
escrito.

### Un fallo que encontró la prueba

Al escribir `test_la_auditoria_no_tumba_la_operacion` apareció un defecto en mi propia
implementación. `registrar_evento` se protegía por dentro, pero la dependencia llamaba a
`asiento.persistir()` dentro de un `finally` **sin protección**. Como ese bloque se ejecuta
después de que el endpoint haya producido su respuesta, una excepción allí la sustituye:
un alta ya confirmada en la base se le devolvía al usuario como un 500.

La prueba lo destapó y está corregido. Lo cuento porque la promesa que hace el módulo —«la
bitácora nunca convierte una operación correcta en un error»— era exactamente la que el
código incumplía en el último tramo.

---

## 14.6. Verificación

### Pruebas

| Archivo | Pruebas | Qué demuestra |
| :--- | ---: | :--- |
| `test_sesiones_rotativas.py` | 13 | Rotación real, detección de reutilización, aislamiento entre sesiones, carrera de dos pestañas, purga con margen |
| `test_ingesta_idempotente.py` | 11 | 409 al reenvío exacto, respuesta repetida al reintento, dos cambios reales sí pasan, la reserva cae con la ingesta |
| `test_proxy_y_auditoria.py` | 19 | La cabecera rotada no esquiva el tope, asientos con actor/IP/resultado, denegaciones registradas, bitácora solo lectura y solo admin |

### Ninguna de las tres es una prueba complaciente

Se comprobó reintroduciendo los defectos y confirmando que fallan las pruebas correctas:

| Defecto reintroducido | Pruebas que fallaron |
| :--- | ---: |
| El refresco no consume el token anterior (N-1) | 5 |
| El endpoint no comprueba la entrega contra las anteriores (N-2) | 3 |
| `TRUST_PROXY_HEADERS` vuelve a `True` (N-6) | 1 |

Nueve fallos, repartidos exactamente entre los tres defectos, y ninguno en el resto de la
suite. Una prueba de rotación que se limitara a comparar «la cookie nueva es distinta de la
vieja» habría pasado en verde sobre el código defectuoso; la que separa una implementación
de la otra es `test_reutilizar_un_token_consumido_cierra_la_sesion`.

### Guardas en el pipeline

El trabajo `configuracion-peligrosa` sube de tres a **siete** comprobaciones. Las cuatro
nuevas se verificaron una a una reintroduciendo su defecto: las cuatro lo detectaron.

| Guarda | Qué impide |
| :--- | :--- |
| No se confía en las cabeceras de proxy por defecto | Que `TRUST_PROXY_HEADERS` vuelva a venir en `True` |
| La rotación de sesión consume el token anterior | Que desaparezca la detección de reutilización |
| La ingesta comprueba que la entrega sea nueva | Que el webhook deje de deduplicar |
| La bitácora de auditoría es de solo lectura | Que se añada un endpoint de borrado o edición |

### Esquema

Una migración aditiva, `130b990d78d7`: tres tablas nuevas, ninguna alteración de las
existentes. Se puede aplicar sobre una base en producción sin ventana de mantenimiento.
Verificada de ida y vuelta (`upgrade head` → `downgrade base` → `upgrade head`) y con
`alembic check` sin diferencias pendientes.

### La verificación sobre la pila real, y los dos defectos que encontró

Esta sección decía, al cerrar la fase, que el demonio de Docker no había llegado a
arrancar y que quedaba pendiente un `docker compose up --build` de verdad. Terminaba
diciendo que no había motivo para esperar un fallo, pero que «no hay motivo para
esperarlo» no es «comprobado». La pila se levantó después, y esa distinción resultó no ser
retórica: **encontró dos defectos, y uno de ellos dejaba N-6 a medio cerrar**.

**Primero: la pila no arrancaba sobre una base nueva.** Con el volumen vacío,
`docker compose up` deja el backend en un bucle de arranque fallido. El motivo es una
guarda correcta: el backend comprueba al iniciar que el esquema esté sellado por Alembic y
se niega a servir si no lo está. Lo que faltaba es que alguien aplicara las migraciones —
ningún servicio de la pila lo hacía—. Se había probado siempre sobre una base ya migrada a
mano, de modo que el despliegue documentado nunca se había ejecutado tal como está escrito.

Se resolvió con un servicio `migrate` de un solo disparo, del que el backend depende con
`service_completed_successfully`. No con un `alembic upgrade` dentro del arranque del
backend: sirve con dos workers y puede escalarse, y varios procesos migrando la misma base
a la vez es una carrera con un final que nadie quiere depurar.

**Segundo, y más serio: `X-Forwarded-For` seguía siendo falsificable detrás de nginx.** La
pila activa `TRUST_PROXY_HEADERS`, y el comentario que lo justificaba decía que nginx
«reescribe X-Forwarded-For con la IP real del cliente». No lo hacía. Usaba
`$proxy_add_x_forwarded_for`, que **añade** la IP real al final de lo que mandara el
cliente: `X-Forwarded-For: <inventada>, <real>`. El backend lee el primer elemento de la
cadena —lo correcto cuando quien escribe el primero es el salto más externo—, así que
seguía leyendo el valor inventado.

Es el mismo defecto que abre este capítulo, cometido en el arreglo del capítulo: un
comentario que describe una protección que no existe. El comentario de nginx razonaba
sobre el extremo equivocado de la cadena, y era cierto y a la vez irrelevante.

Se midió antes y después, contra la pila levantada:

| Petición | Antes (`$proxy_add_x_forwarded_for`) | Después (`$remote_addr`) |
| :--- | :--- | :--- |
| 6 intentos de login con `X-Forwarded-For` distinto en cada uno | 6 contadores en Redis, ningún 429 | 1 contador; el sexto intento recibe **429** |

**Lo que sí se confirmó de extremo a extremo**, ya con la pila corregida:

* `docker compose up` sobre un volumen vacío levanta la pila completa: `migrate` sale con
  código 0 y el backend queda sano;
* la cadena entera de migraciones se aplica sobre **PostgreSQL**, no solo sobre el SQLite
  de las pruebas —incluida la de esta fase—;
* el tope de login es exacto con dos workers: con `5/minute` pasan exactamente cinco
  intentos y el sexto recibe 429. Con `memory://` habrían pasado hasta diez;
* el contador vive en Redis (`LIMITS:LIMITER/<ip>//api/v1/auth/login/5/1/minute`), sin
  persistencia a disco y con `allkeys-lru`, como declara el compose;
* la rotación de sesión: refrescar consume el token anterior; reutilizarlo pasada la
  ventana de gracia devuelve 401 **y tumba también el token legítimo** —cae la familia
  entera, que es lo previsto—, y ambos intentos quedan en `audit_log` como
  `auth.refresh_reutilizado` con el identificador de familia;
* la idempotencia de ingesta: bytes idénticos → **409**; reintento con firma nueva → **200**
  con la respuesta original byte a byte y la cabecera `X-PluriOne-Idempotent-Replay: true`;
  un segundo cambio real del mismo prospecto → se procesa (el score pasó de 32,3 a 32,5),
  que es justo el caso que protege la desviación de §14.3;
* la bitácora: un asesor recibe 403 y el intento queda registrado como `acceso.denegado`
  con su correo; `POST`, `PUT`, `PATCH` y `DELETE` sobre `/api/v1/audit` devuelven 405;
* la guarda de siembra de la fase anterior disparó sola al intentar sembrar contra
  `ENVIRONMENT=production`, y ofreció la salida correcta (`--solo-usuarios`).

Los dos defectos tienen ahora prueba de regresión —`test_pila_de_despliegue.py` y dos
pruebas nuevas en `test_proxy_y_auditoria.py`— y guarda en el pipeline. Se comprobó que
ninguna de las cuatro es vacía reintroduciendo el defecto correspondiente.

---

## 14.7. Lo que esta fase **no** resuelve

Cuatro cosas, dichas explícitamente para que no se lean como resueltas:

1. **La ventana de gracia de diez segundos** es una concesión real, no una formalidad.
   Durante esos segundos una cookie robada sigue sirviendo. Es el precio de que la medida
   no expulse de su sesión a los usuarios con varias pestañas.

2. **Un access token robado sigue valiendo hasta expirar** (quince minutos). La revocación
   actúa sobre la capacidad de *renovar* la sesión, no sobre los tokens ya emitidos.
   Revocarlos exigiría consultar la base en cada petición autenticada, y ese es un coste
   por petición para cubrir una ventana de quince minutos.

   > **Nota del capítulo 23.** Cerrado. La premisa ya no era cierta: desde el capítulo 15 la
   > identidad se relee de la base en cada petición para tomar el rol, así que la consulta
   > ya se pagaba. El access token lleva ahora `ver` y esa misma lectura lo compara con
   > `token_version`: el logout, el cambio o restablecimiento de contraseña, el cambio de
   > rol y la desactivación lo invalidan al instante, sin ninguna consulta más.

3. **La deduplicación de webhooks protege dentro de su ventana**, no indefinidamente.
   Pasada la ventana la marca de tiempo ya no supera la comprobación anti-replay, así que
   guardar la huella para siempre solo serviría para bloquear un evento legítimo repetido
   meses después.

4. **La bitácora no se purga sola, y no hay ajuste que lo cambie.** Llegué a declarar un
   `AUDIT_LOG_RETENTION_DAYS` y lo retiré antes de cerrar la fase: nada lo leía, así que
   anunciaba una política de retención que no existe. Es exactamente el defecto que abre
   este capítulo —un valor que cierra una pregunta que sigue abierta—, y no tenía sentido
   denunciarlo en N-1 y cometerlo dos secciones más abajo. El borrado se aplica desde
   fuera, con las herramientas de la base de datos.

   > **Nota del capítulo 20.** La bitácora sigue igual. El que sí tiene ahora plazo, con
   > ajuste y con algo que lo lee, es el historial de puntuación:
   > `SCORE_HISTORY_RETENTION_MONTHS`, aplicado por el servicio `retencion-historial`
   > (§20.3). La tabla de conservación completa, bitácora incluida, está en §20.5.

---

## 14.8. Estado de los hallazgos de esta ronda

| Hallazgo | Estado | Dónde |
| :--- | :--- | :--- |
| **N-1** | Corregido | `refresh_tokens`, `session_service.py`, `auth.py` |
| **N-2** | Corregido, con desviación documentada (§14.3) | `webhook_deliveries`, `webhook_dedup.py`, `crm.py` |
| **N-6** | Corregido en dos tiempos (§14.6): el defecto del proxy solo se vio al levantar la pila | `config.py`, `proxy.py`, `frontend/nginx.conf`, `devops/docker-compose.yml` |
| **N-8** | Corregido | `audit_log`, `audit.py`, `endpoints/audit.py` |

Los cuatro tienen prueba de regresión que falla si se revierten, y tres tienen además una
guarda en el pipeline que los detecta sin ejecutar la suite.
