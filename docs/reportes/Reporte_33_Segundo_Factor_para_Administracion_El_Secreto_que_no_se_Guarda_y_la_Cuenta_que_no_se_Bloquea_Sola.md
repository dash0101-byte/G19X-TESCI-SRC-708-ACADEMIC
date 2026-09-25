# Capítulo 35: Segundo Factor para Administración — El Secreto que no se Guarda y la Cuenta que no se Bloquea Sola

> **Sobre la numeración.** Este es el **Reporte 33** y el **capítulo 35**. El desfase de dos
> viene de los capítulos 29 y 31, que no escribieron reporte propio; está explicado al
> principio del Reporte 30. Los apartados se numeran **35.x**, por el capítulo.

> **Sobre la congelación.** Cierra §3.6, que llevaba abierto desde el capítulo 19. No es una
> excepción a la congelación por la misma razón que el capítulo 34 no lo era: §3.6 no decía
> «queda pendiente», decía **qué hacía falta para que hacerlo no fuera peor que no hacerlo**,
> y eso es un encargo escrito esperando a ejecutarse.

## 35.1. Por qué estuvo abierto dieciséis capítulos

El documento de congelación no decía que faltara tiempo. Decía esto:

> «Un TOTP para `System_Admin` exige alta con código de verificación, códigos de
> recuperación, un paso más en el login del cliente y una respuesta para quien pierde el
> teléfono siendo el único administrador —que es justo la cuenta que no puede quedarse
> fuera—. **Añadir la verificación sin eso produce una cuenta de administración que se
> bloquea sola.**»

Es un diagnóstico exacto y conviene leerlo despacio, porque describe el fallo característico
de esta funcionalidad: un segundo factor a medias no es «menos seguridad», es **un sistema
que se cierra por dentro**. La parte que protege se escribe en una tarde; la que evita
quedarse fuera es el resto del trabajo.

Este capítulo hace las cuatro cosas. La cuarta manda sobre las otras tres.

## 35.2. Tres decisiones antes de escribir nada

El proyecto no tenía **ninguna** biblioteca de criptografía: ni `pyotp`, ni codificador de
QR, ni `cryptography`. Así que había que decidir qué entra al lock de un proyecto congelado,
y las tres piezas se resolvieron distinto a propósito.

### El TOTP se escribe: la norma publica con qué demostrarlo

TOTP no es un diseño criptográfico. Es un contador de treinta segundos metido en un HMAC y
truncado, y el HMAC lo pone la biblioteca estándar. Son cuarenta líneas.

Lo que hace defendible escribirlo no es que sea corto, es que **RFC 6238 publica vectores de
prueba oficiales**. La implementación no se afirma correcta: se comprueba contra los
dieciocho valores que publica la norma, para SHA-1, SHA-256 y SHA-512, desde 1970 hasta el
año 2603. Si eso pasa, cualquier aplicación del teléfono calculará lo mismo.

### El QR se trae: es la única pieza que saldría peor a mano

Un codificador de QR son los polinomios de Reed-Solomon, ocho patrones de enmascaramiento
con sus penalizaciones y la tabla de versiones. `segno` es Python puro, **sin dependencias
propias**, 76 KB. Es la única dependencia que añade este capítulo, y regenerar el lock con
el comando documentado movió **exactamente un paquete y ninguna versión más**.

### El secreto no se cifra: no se guarda

Aquí está la decisión de fondo. «Guardar el secreto cifrado» habría exigido `cryptography`,
la dependencia más pesada que el proyecto podría tomar —extensión compilada, y justo la que
§6.4 punto 21 registra que ya dio problemas en esta máquina—.

La alternativa no es guardar el secreto en claro. Es **no guardarlo**:

```python
secreto = HMAC-SHA256(SECRET_KEY, "totp:v1:" + sal)[:20]
```

La base guarda una **sal** aleatoria por alta. El secreto se calcula con ella y con
`SECRET_KEY`, que vive en el entorno y nunca en la base. Quien se lleve un volcado de
`users` se lleva sales: sin la clave del servidor no genera ni un código.

Es la **misma** protección que cifrar el secreto con una clave derivada de `SECRET_KEY` —en
los dos casos, base sin clave no vale nada—, con una dependencia menos y sin cifrador que
implantar. No es criptografía propia: es HMAC usado como función de derivación, que es para
lo que está.

**El precio, dicho entero.** Rotar `SECRET_KEY` invalida **todas** las altas, y no se pueden
recuperar porque no hay nada cifrado que releer. Con Fernet se habría podido re-cifrar bajo
la clave nueva. No es una situación nueva —rotar esa clave ya invalida todas las sesiones y
todos los tokens— pero sí es peor: las sesiones se recuperan volviendo a entrar y esto exige
volver a escanear el QR. Está en el módulo, en la migración y en §5 de la guía.

La sal, además, hace que dos altas de la misma cuenta den secretos distintos: volver a darse
de alta invalida el teléfono anterior sin tocar la clave del servidor.

## 35.3. Las cuatro cosas que §3.6 exigía

### Alta con código de verificación

`/segundo-factor/alta` genera sal, secreto y códigos, y **no activa nada**. Entre esa
llamada y `/segundo-factor/activar`, la cuenta sigue entrando con la contraseña.

Es la diferencia entre un alta y un acto de fe: sin ese paso, quien escanee mal el QR se
queda fuera de su propia cuenta sin haber visto nunca un código bueno. Volver a pedir el
alta descarta la anterior, así que un alta a medias se rehace sin pasar por nadie.

En la pantalla, el botón de activar está **deshabilitado hasta marcar que los códigos de
recuperación se han guardado**. Es la única forma de que ese paso no se lea como decorado:
en cuanto esto se active, esos diez códigos son lo único que queda si el teléfono se pierde.

### Códigos de recuperación

Diez, de un solo uso, de un alfabeto sin caracteres que se confundan al copiar de una hoja
(`0/O`, `1/I/L`). Se guardan como **resumen SHA-256** y se borra el resumen al gastarlo.

Lo de SHA-256 y no bcrypt merece explicación porque el resto del sistema sí usa bcrypt:
bcrypt es lento a propósito para que una contraseña **elegida por una persona** no se pueda
probar por diccionario. Un código de recuperación no lo elige nadie —son sesenta bits de
`secrets`— y probarlo por fuerza bruta no es viable con ningún resumen. Lo que sí sería un
problema es el coste: comprobar contra diez bcrypt son diez operaciones lentas por intento,
y eso convierte el endpoint en un amplificador de carga para quien lo llame en bucle.

Al comprobarlos se recorre la lista **entera** y se compara en tiempo constante. Salir en
cuanto casa filtraría por tiempo cuántos quedan y en qué posición está el bueno.

### Un paso más en el login

`POST /auth/login` devuelve ahora una de dos cosas, con un discriminador `tipo` explícito:
una **sesión**, o un **desafío**.

Es **200 y no un error**, y esa decisión se tomó a conciencia. La contraseña se comprobó y
era buena; lo que pasa es que la autenticación tiene dos pasos y va por el primero. Devolver
401 obligaría al cliente a tratar el camino normal dentro de su rama de fallos, que es donde
se acaban tragando los errores de verdad.

El desafío es un token de **tipo propio** (`segundo_factor`), no un access token de vida
corta. Esa es la línea que cierra el fallo obvio: si sirviera como `Authorization`, el
segundo factor se saltaría sencillamente no pidiéndolo. Hay una prueba que lo presenta como
`Bearer` y comprueba que devuelve 401.

Mientras el desafío vale, el formulario **deja de pedir correo y contraseña**. No es estética:
dejarlos en pantalla invita a volver a enviarlos.

### Y la respuesta para quien se queda fuera

Tres salidas, en orden, y ninguna deja el sistema sin administración utilizable:

| Situación | Salida |
| :--- | :--- |
| Perdió el teléfono, tiene códigos | Entra con uno; se gasta |
| Sin códigos, hay otra administración | Esa otra le quita el factor |
| Sin códigos y sin otra administración | Acceso al servidor: una sentencia SQL, en §3c de la guía |

Y la salvaguarda que impide llegar al tercer caso por descuido: **la última cuenta de
administración con segundo factor activo no se lo puede quitar**. Una cuenta de
administración sin segundo factor no puede operar, así que quitárselo siendo el único que lo
tiene dejaría el sistema sin administración utilizable hasta que esa misma persona volviera
a darse de alta. El panel lo dice con todas las letras al intentarlo.

Que el tercer caso exija acceso al servidor es la respuesta correcta y no una carencia:
cualquier rescate usable desde fuera —un enlace por correo, una pregunta de seguridad— sería
una segunda puerta a la cuenta más poderosa del sistema.

## 35.4. Dónde se comprueba la exigencia, y por qué ahí

En **la resolución de identidad**, junto a la comprobación de la contraseña prestada del
capítulo 19, y por el mismo motivo escrito entonces: así un endpoint nuevo **nace cerrado**
para una cuenta de administración sin segundo factor, sin que nadie tenga que acordarse de
añadirlo a ninguna lista. La excepción se pide por su nombre
(`get_current_user_sin_segundo_factor`) y solo la usan las rutas que sirven para dejar de no
tenerlo.

El **orden** entre las dos comprobaciones es una decisión: primero la contraseña prestada.
Una cuenta con las dos cosas pendientes tiene que cambiar primero la credencial que conoce
otra persona; al revés, ataría un teléfono a una cuenta que todavía no es suya. El cliente
aplica el mismo orden, y hay una prueba de que lo hace.

Quién está obligado vive en **una sola tupla** (`ROLES_OBLIGADOS_A_SEGUNDO_FACTOR`), que
leen el servidor, el servicio y la guarda del CI. Y el cliente **no lo deduce del rol**: lo
recibe calculado (`segundo_factor_obligatorio`). Deducirlo allí crearía una segunda
definición que se quedaría atrás el día que alguien cambiara la primera, sin que nada
fallara: el panel enseñaría la aplicación a una cuenta a la que el servidor le va a rechazar
todo.

## 35.5. Intentos, reloj y repetición

**Los intentos se cuentan por desafío, no por cuenta.** Es la decisión que evita regalar una
forma de dejar al sistema sin administrador: contando por cuenta, cualquiera podría bloquear
la de administración fallando cinco veces contra su correo. Contando por desafío, agotarlos
solo obliga a volver a escribir la contraseña; la cuenta nunca queda inaccesible y no hay
nada que desbloquear a mano, porque el contador vive lo que vive el desafío y se limpia solo.

**La tolerancia de reloj es un periodo**, ±30 s, que es lo que recomienda RFC 6238 §5.2. Lo
que se compra es que funcione el teléfono un poco desfasado; lo que se paga es que cada
código pasa de valer 30 segundos a valer 90. Con dos periodos serían 150 por un caso que casi
no ocurre, porque los teléfonos sincronizan la hora por red.

**Y por eso mismo, un código no vale dos veces.** Se guarda el último periodo aceptado y se
rechaza cualquier código de ese periodo o anterior. Sin esa memoria, la tolerancia regala una
ventana de noventa segundos para reutilizar un código leído por encima del hombro o sacado de
un registro.

Tiene una consecuencia visible que la guía explica: entrar en dos equipos en la misma media
vuelta de reloj falla el segundo. Es correcto, y es lo que obligó a que la propia suite
—que entra varias veces por segundo— diga explícitamente «han pasado treinta segundos».

## 35.6. La bitácora

Cinco acciones y no una con un campo «qué pasó», porque son hechos de gravedad distinta y hay
que poder filtrarlos por separado: alta, activación, uso, fallo y baja.

El uso anota **la forma**: `totp` o `recuperacion`. Gastar un código significa que alguien
perdió el teléfono, y dos en una semana significa otra cosa; tiene que verse sin cruzar
tablas. Anota también cuántos quedan.

Lo que **no** anota, con prueba propia: el secreto, la sal, la URI y los códigos. Copiar
cualquiera de ellos convertiría la tabla de auditoría —que se consulta con otro criterio de
acceso que la de cuentas (R-11)— en el sitio donde sí está guardado lo que esta
implementación se cuida de no guardar.

## 35.7. Que nada de esto sea decorativo

**Las pruebas.** `test_segundo_factor.py`, **56 casos**: los dieciocho vectores del RFC, la
tolerancia y su límite, la no repetición, que la base no guarde ningún secreto, el alta que
no activa, los códigos de un solo uso, el login de dos pasos, el desafío que no sirve como
autorización, la exigencia por rol, las tres salidas de quien se queda fuera, los intentos
por desafío y los cinco asientos. Y once en el cliente, entre la entrada y la pantalla de
alta.

Toda la suite pasó además a entrar **por los dos pasos** para las pruebas de administración.
Se podía haber apagado la exigencia en las pruebas y habría sido un error: el camino que
recorre la suite dejaría de ser el que recorre un administrador de verdad, y el día que el
segundo paso se rompiera lo diría una sola prueba en lugar de todas.

**La guarda del CI.** Un paso nuevo; `configuracion-peligrosa` pasa de 39 a **40 controles**.
No vigila que el TOTP funcione —eso lo hacen los vectores— sino las ocho decisiones que al
revertirse dejan el sistema **aparentemente sano**: un secreto guardado, una sal que
sobrevive a la baja, un desafío que sirve como sesión, un código que vale dos veces, una
comparación que filtra por tiempo, la tolerancia subida, la salvaguarda de la última
administración, y la exigencia sacada de la resolución de identidad.

**La reintroducción de defectos.** Diez, de uno en uno: **10 de 10 detectados**. Seis los
caza la guarda y ocho la suite; ninguno se escapa por los dos.

**Y un defecto que encontró la propia suite, del mismo tipo que corrigió el capítulo 33.**
`test_borrar_la_cuenta_invalida_el_token` borraba la cuenta de administración y la
restauraba a partir de una **lista de columnas escrita a mano**. Esa lista acertaba el día
que se escribió y se quedó corta al añadir las cinco columnas de este capítulo: la cuenta
volvía sin segundo factor y, a partir de ahí, toda petición de administración respondía 403.

Lo que lo hace digno de contarse es **dónde aparecía el fallo**. Esa prueba seguía en verde.
Las que se ponían rojas eran otras nueve, de tres archivos distintos, a media suite de
distancia, y ninguna hablaba de borrar cuentas. La copia se toma ahora de
`User.__table__.columns`: si la lista la dicta la tabla, no se puede quedar corta.

## 35.8. Comprobación final

| Qué | Resultado |
| :--- | :--- |
| Suite del backend | **1485 pruebas**, 2 omitidas, cobertura **93 %** |
| Suite del cliente | **385 pruebas** en 28 archivos |
| Vectores oficiales del RFC 6238 | 18 de 18, en SHA-1, SHA-256 y SHA-512 |
| `ruff check .` / `npm run lint` | Sin avisos |
| Guardas del CI | `configuracion-peligrosa` con 40 controles |
| Reintroducción de defectos | 10 de 10 detectados |
| Dependencias nuevas | **Una**: `segno`. El lock no movió ninguna otra versión |

## 35.9. Lo que esta fase no hizo, y por qué

**No hay SMS, ni llaves físicas, ni proveedores externos.** Estaba fuera del encargo y sigue
fuera. Del SMS conviene decir además que no es una carencia: se intercepta cambiando la
tarjeta del teléfono en la operadora, que es un ataque conocido y barato.

**No hay «recordar este dispositivo».** Un segundo factor que se salta a veces es un segundo
factor que no está el día que hace falta.

**No se exige a los líderes comerciales.** Pueden activarlo y se les ofrece; no se les
obliga. El criterio es el alcance de lo que puede hacer la cuenta, y cambiarlo es añadir un
rol a una tupla.

**Un administrador no puede quitarle el segundo factor a otro desde el panel.** La salida (b)
de §3 de la guía existe en el diseño pero no tiene botón: la gestión de cuentas no ganó esa
operación en este capítulo. Hoy se resuelve por la vía (c), que es la misma sentencia SQL.
Queda anotado en §6.4.

**El teléfono desfasado más de medio minuto no entra.** Es la tolerancia de la norma y
subirla tiene un precio medido. La guía dice qué hacer: activar la hora automática.
