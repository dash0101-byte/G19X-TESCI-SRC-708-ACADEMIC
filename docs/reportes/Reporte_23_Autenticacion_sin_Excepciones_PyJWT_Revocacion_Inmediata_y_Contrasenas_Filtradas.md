# Capítulo 23: Autenticación sin Excepciones — PyJWT, Revocación Inmediata y Contraseñas Filtradas

## 23.1. Por qué existe esta fase

Tres entradas de «lo que esta fase no hizo» tenían en común que eran **excepciones
aceptadas en la autenticación**:

* **§20.8.** `python-jose` arrastraba `ecdsa`, con un aviso sin arreglo (PYSEC-2026-1325), y
  `pip-audit` tenía que ignorarlo. La excepción estaba acotada y comprobada, pero seguía
  siendo un aviso que nadie volvería a mirar.
* **§14.7 y §19.9.** Un access token robado valía sus quince minutos aunque su víctima cerrara
  sesión o cambiara la contraseña. La revocación cortaba la renovación, no el token.
* **La política de contraseñas** rechazaba una lista corta del contexto, y el propio módulo
  decía que una lista de filtradas «pide un servicio externo o un fichero grande».

La fase las cierra sin cuentas externas. El segundo factor para `System_Admin`, que figuraba
como opcional, no se hizo; §23.7 dice por qué.

---

## 23.2. PyJWT en lugar de python-jose

### El cambio

| | Antes | Ahora |
| :--- | :--- | :--- |
| Biblioteca | `python-jose[cryptography]` 3.5.0 | `PyJWT` 2.14.0 |
| Arrastraba | `ecdsa`, `rsa`, `pyasn1`, `cryptography`, `cffi`, `pycparser` | nada |
| `pip-audit` | `--ignore-vuln PYSEC-2026-1325` en tres pasos | sin excepciones |
| Imagen del backend | 895 MB | 869 MB |

Solo se firma con HMAC, así que `cryptography` no hacía falta. Los locks se regeneraron
tomando el lock anterior como preferencia: **no cambió la versión de ningún otro paquete**.
Lo comprobó `scripts/comprobar_instalado.py`, que contra el entorno anterior solo señaló
PyJWT como nuevo y los seis paquetes de python-jose como sobrantes.

### Una diferencia de comportamiento que había que cubrir

python-jose y PyJWT validan los claims de forma distinta. **PyJWT solo comprueba un claim si
viene en el token**: sin más, un token firmado con la clave correcta pero sin `exp` no
caducaría nunca. Por eso `decode_token` exige ahora `exp`, `iat`, `nbf`, `iss`, `aud`, `sub` y
`jti`, que son los que la aplicación pone en todos sus tokens, y una prueba falla si falta
cualquiera.

### Auditar sin excepciones

La guarda del pipeline pasó de exigir **exactamente** la excepción de `ecdsa` a exigir que no
haya **ninguna**, en todo el workflow y no solo en los pasos de auditoría. Si mañana aparece
un aviso sin arreglo, la puerta se pone en rojo y se decide a la vista, cambiando la prueba,
en lugar de añadir otro `--ignore-vuln` que pase desapercibido.

---

## 23.3. Revocación inmediata del access token

### La premisa de §14.7 ya no era cierta

§14.7 lo descartó porque revocar un access token «exigiría consultar la base en cada
petición autenticada». Desde el capítulo 15 esa consulta **ya se hacía**: la resolución de
identidad relee la cuenta en cada petición para tomar el rol de la base y no del token. El
coste que justificaba la excepción se estaba pagando, y la protección no se cobraba.

### El cambio

* `create_access_token` añade `ver`, la `token_version` de la cuenta al emitirlo.
* `_resolver_identidad` compara `ver` con la cuenta que ya ha leído. Si no coincide, 401.

`token_version` ya subía en cinco sitios, así que las cinco operaciones invalidan al instante
los access tokens emitidos:

| Operación | Antes | Ahora |
| :--- | :--- | :--- |
| Cerrar sesión | El token robado seguía operando hasta 15 min | 401 en la siguiente petición |
| Cambiar la propia contraseña | Igual | 401 |
| Restablecimiento por el administrador | 403 «cambie la contraseña» (§19.2) | 401 |
| Cambio de rol | Operaba con el rol nuevo hasta 15 min | 401 |
| Desactivación | 401, por `is_active` | 401 |

**Un token sin `ver` no vale como «versión 0».** Los emitidos antes del cambio caducan solos
en minutos, y aceptarlos reabriría el hueco para cualquier token fabricado sin el claim.

### Lo que cambió en el cliente y en la suite

* **El cliente no necesitó cambios.** Ante un 401 ya intentaba renovar una vez y, si la
  renovación también fallaba —y falla, porque el refresh token lleva la misma versión—,
  cerraba la sesión.
* **La suite sí.** `conftest.py` cachea las cabeceras de autenticación para toda la sesión, y
  una prueba que cerraba sesión dejaba inservible el token de la siguiente. Al restaurar
  las cuentas de prueba tras cada prueba, `token_version` vuelve a 0.
* **Una prueba de §19.2 cambió de expectativa**: tras el restablecimiento, el token anterior
  ya no recibe el 403 que lleva a la pantalla de cambio, sino 401. Es más estricto, y es lo
  correcto: ese token es justo el que se quería dejar sin uso.

---

## 23.4. Contraseñas filtradas, con una lista local

### Qué lista y por qué así

`scripts/generar_lista_de_contrasenas.py` construye la lista a partir de dos listas públicas de
SecLists (licencia MIT): la de las 100 000 más usadas del NCSC británico y el primer millón
de la de Mark Burnett (xato-net).

* **Solo lo que la longitud no rechaza ya.** Una filtrada de 8 caracteres ya la rechaza el
  mínimo de 12. De 1,1 millones de líneas quedan **46 825 entradas**, en 332 KB comprimidos.
  Si algún día baja el mínimo, una prueba falla hasta que se regenere.
* **Normalizada con la misma función que la política**, minúsculas y sin acentos, importada
  del módulo y no copiada.
* **Local.** Viaja dentro de `backend/app`, que es lo que copia la imagen. Comprobar una
  contraseña no manda nada a ningún servicio, ni siquiera un prefijo de su huella.
* **Íntegra.** Es determinista (ordenada, sin duplicados, gzip con fecha cero) y su huella
  y su número de entradas están en un manifiesto. La aplicación los comprueba al cargarla:
  **una lista vaciada o sustituida lanza un error** en lugar de aceptarlo todo en silencio.

Ejemplos de lo que la política anterior aceptaba y ahora rechaza, porque cumplían longitud y
variedad: `Password1234`, `1q2w3e4r5t6y`, `qwertyuiop12`, `iloveyou1234`.

### Un defecto que apareció al probarla

`_normalizar` pasaba a minúsculas **antes** de descomponer con NFKD. Así no es idempotente:
NFKD convierte algunos signos en letras mayúsculas (`ℌ` → `H`). La lista, ya normalizada, no
coincidía con la misma contraseña normalizada otra vez, y la prueba que exige idempotencia
sobre las 46 825 entradas lo encontró. Ahora se descompone primero.

### Las tres puertas

Alta, cambio propio y restablecimiento pasan por `exigir`, y `exigir` consulta la lista. Hay
una prueba por puerta con una contraseña filtrada real, y otra que comprueba que ninguna de
las contraseñas que usa la suite está en la lista.

---

## 23.5. Que nada de esto sea decorativo

### Las pruebas

23 pruebas nuevas en `test_autenticacion_sin_excepciones.py`, cinco de ellas añadidas tras
la primera ejecución del arnés (abajo). En `test_dependencias_fijadas.py` la prueba que
justificaba la excepción de `ecdsa` se sustituyó por dos: una exige que ninguna auditoría
ignore avisos y otra que la biblioteca de JWT no arrastre criptografía asimétrica. Se adaptaron
además `test_security_rbac.py` y `test_contrasena_prestada.py`. En total, 24 más que en el
capítulo 22.

### Las guardas del pipeline

| Guarda | Qué detecta |
| :--- | :--- |
| El access token se revoca al instante y no hay python-jose | el token sin `ver`, la identidad sin comparar, `decode` sin claims obligatorios, `jose` o `ecdsa` de vuelta en el código o en el lock |
| Las contraseñas filtradas se rechazan con la lista local | la política sin consulta, la lista usada sin comprobar su huella, archivos ausentes o manipulados, una puerta sin `exigir` |
| Las dependencias y las imágenes se auditan (modificada) | cualquier `--ignore-vuln` en cualquier paso del workflow |

### Reintroducciones

Se reintrodujeron **13 defectos** con el mismo arnés del capítulo 22. El arnés copia y
restaura cada archivo, y exige que la prueba falle, que la guarda falle con `FALLO` y que ambas
pasen sobre el árbol correcto.

| Pieza | Defectos reintroducidos |
| :--- | :--- |
| Revocación | el access token sin `ver`; la identidad sin comparar; un token sin `ver` aceptado como versión 0; `decode` sin claims obligatorios; el logout sin subir la versión |
| Filtradas | la política sin consultar la lista; una lista manipulada usada en silencio; normalizar en el orden que no es idempotente; el restablecimiento sin pasar por la política; un manifiesto que no corresponde al archivo |
| Auditoría | la excepción de vuelta en producción; otra excepción en la imagen; python-jose de vuelta en el lock |

**Primera ejecución: pruebas 11 de 13 y guardas 6 de 8.** Tres huecos, los tres del tipo que
este arnés existe para encontrar:

* **La guarda de `ver` no veía que el access token lo hubiera perdido.** Buscaba la línea
  `"ver": user.token_version,` en todo `security.py`, y el refresh token lleva la misma.
  Ahora mira solo dentro de `create_access_token`.
* **Una lista sustituida por otra del mismo tamaño no la detectaba nadie.** La prueba usaba
  una lista vaciada, y a esa ya la rechaza el recuento de entradas: quitar la comprobación
  de la huella no cambiaba nada. La guarda, por su parte, aceptaba cualquier `raise`. La
  prueba añade una lista con una sola entrada cambiada y la guarda exige la comparación de
  la huella seguida de su `raise`.
* **El orden de la normalización no lo comprobaba ninguna prueba.** Sobre entradas ya
  normalizadas los dos órdenes dan lo mismo. Se añadieron casos con `ℌ` y letras de ancho
  completo, que NFKD convierte en mayúsculas, y el de una filtrada escrita en ancho completo
  (`ＰＡＳＳＷＯＲＤ１２３４`), que con el orden equivocado esquivaba la lista.

Repetidos los tres contra la prueba y las guardas corregidas: **3 de 3 y 2 de 2. Resultado
final: 13 de 13 pruebas y 8 de 8 guardas.**

---

## 23.6. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend | **815 pruebas**, 92 % de cobertura |
| Reintroducciones | 13 defectos: pruebas 13/13 y guardas 8/8 (11/13 y 6/8 en la primera ejecución, §23.5) |
| `ruff` | Sin avisos |
| Locks | Entra `pyjwt 2.14.0`; salen `python-jose`, `ecdsa`, `rsa`, `pyasn1`, `cryptography`, `cffi` y `pycparser`; ninguna otra versión cambia |
| `pip-audit` sobre lo fijado para producción, sin excepciones | «No known vulnerabilities found» |
| Imagen del backend | Se construye; `jwt` importable y `jose`, `ecdsa` y `cryptography` ausentes; la lista carga 46 825 entradas y rechaza `Password1234`; Trivy (ALTAS/CRÍTICAS con arreglo): **0**; 869 MB |
| Guardas nuevas y modificada, ejecutadas con Git Bash | Pasan sobre el árbol correcto |
| Integración continua | 10 trabajos, 34 guardas en `configuracion-peligrosa` |

---

## 23.7. Lo que esta fase no hizo

* **No hay segundo factor.** Era opcional, y no se hizo a medias. Un TOTP para
  `System_Admin` exige alta con código de verificación, códigos de recuperación, un paso más en
  el login del cliente y una respuesta para quien pierde el teléfono siendo el único
  administrador, que es justo la cuenta que no puede quedarse fuera (§15). Añadir la
  verificación sin eso produciría una cuenta de administración que se bloquea sola.
* **La lista no se actualiza sola.** Es una foto de dos listas públicas. Regenerarla es
  ejecutar el guion con fuentes nuevas, y el manifiesto dice de cuáles salió.
* **La lista no es exhaustiva.** Cubre las filtradas más frecuentes que miden 12 caracteres o
  más, no todas las filtraciones. Comprobar contra cientos de millones de huellas sin
  servicio externo pediría un archivo de decenas de gigabytes dentro de la imagen.
* **Un cambio de rol ahora obliga a volver a entrar.** Antes el rol nuevo se aplicaba a la
  sesión abierta en la siguiente petición. Es la consecuencia de revocar al instante, y
  para una degradación es lo buscado; para un ascenso es una molestia.
* **En el entorno de desarrollo de esta máquina quedan `cffi`, `cryptography` y
  `pycparser`.** Un servidor de desarrollo lanzado desde otra sesión tenía abierto
  `_cffi_backend.pyd` y Windows no permitió borrarlo; no se detuvo un proceso ajeno. El
  código no los importa, el CI instala desde cero y la imagen ya no los lleva.
