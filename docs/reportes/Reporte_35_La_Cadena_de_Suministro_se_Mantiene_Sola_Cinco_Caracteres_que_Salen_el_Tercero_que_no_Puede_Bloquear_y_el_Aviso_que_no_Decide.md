# Reporte 35 — La cadena de suministro se mantiene sola: cinco caracteres que salen, el tercero que no puede bloquear y el aviso que no decide

**Capítulo 37** · Seguridad y mantenimiento · ≈ 1½ días · coste cero, sin cuentas nuevas
**Fecha:** 1 de octubre de 2026
**Alcance:** comprobación de contraseñas filtradas contra el servicio público por rango (*k-anonymity*), política explícita ante su fallo, salida TLS por el almacén del sistema, actualizaciones automáticas de imágenes, acciones y dependencias, y los dos controles de regresión que vigilan lo uno y lo otro.

> **Sobre la numeración.** El número del reporte va dos por detrás del capítulo: este Reporte 35 es el capítulo 37. Los capítulos 29 y 31 no escribieron reporte propio.

---

## 37.1. Este capítulo cierra dos entradas diciendo que su premisa era falsa

Los §3.7 y §3.8 de `docs/Congelacion_y_Trabajo_Futuro.md` viven en el grupo **§3, «depende de cuentas externas»**. Ese grupo tiene un significado preciso, escrito en el §2 del mismo documento:

> *«El código no se puede escribir de forma honrada sin una cuenta, una clave o un dominio público que el proyecto no tiene. Qué haría falta: que PluriOne abra la cuenta.»*

Las dos entradas decían esto:

| | Lo que decía | Lo que hacía falta, según la entrada |
| :--- | :--- | :--- |
| **§3.7** | La lista de contraseñas filtradas no se actualiza sola ni es exhaustiva | «una cuenta en un servicio de comprobación de contraseñas comprometidas —con el modelo de *k-anonymity*, que no envía la contraseña— o aceptar el tamaño» |
| **§3.8** | Nadie avisa de que una huella de imagen se quedó atrás | «Automatizarlo con un servicio que abra solicitudes de cambio exige una cuenta» |

**Ninguna de las dos cosas exige una cuenta, y ese es todo el capítulo.**

* El servicio de rango de Have I Been Pwned es una petición `GET` anónima. No hay registro, no hay clave de API, no hay límite que obligue a identificarse. Lo que §3.7 describía bien era el **modelo** —*k-anonymity*, y hasta lo nombraba—; lo que dio por supuesto sin comprobarlo fue el **requisito administrativo**.
* Dependabot es parte de GitHub. El repositorio ya está en GitHub desde el capítulo 11. Lo único que hacía falta era un archivo de cuarenta líneas.

Conviene decir qué clase de error fue, porque no es el mismo en los dos casos. §3.8 se escribió en el capítulo 22, cuando el repositorio todavía no estaba decidido que viviera en GitHub: era correcto el día que se escribió y dejó de serlo sin que nadie volviera a mirarlo. §3.7 nunca fue correcto: el capítulo 23 escribió «haría falta una cuenta» sin ir a comprobarlo, probablemente por analogía con el resto de §3, donde sí la hace falta.

**Es la cuarta vez en este proyecto que algo aparece por ejecutar y no por leer** —el volumen `deriva` del capítulo 32, el suelo de cobertura del 36, el `target` ausente del Compose—, y la primera en que lo que falla no es el código sino el **inventario de lo que falta**. Una lista de trabajo futuro es también código que envejece, y nadie le corre pruebas.

### Y por qué entra en un repositorio congelado

Esta es la pregunta incómoda, y hay que contestarla antes que nada. El §1 dice: *«si para explicarlo hay que añadir una frase nueva al README, es funcionalidad; si la frase ya está escrita y el código no la cumple, es un fallo»*.

La frase ya estaba escrita. En `backend/app/core/passwords.py`, desde el capítulo 23:

> *«Se rechaza lo que ya se filtró. Una lista LOCAL de contraseñas reales aparecidas en filtraciones públicas.»*

Y el README dice que el sistema rechaza contraseñas filtradas. Lo que este capítulo cambia no es la promesa, es **cuántas** filtradas se reconocen: de las 12 000 de una foto a los cientos de millones del índice público. No hay pantalla nueva, ni campo nuevo, ni endpoint nuevo, ni tabla nueva. El formulario de alta es idéntico; lo único que cambia es que ahora rechaza más cosas que antes rechazaba por no conocerlas.

Con §3.8 es aún más claro: no se añade código al producto. Se añade un archivo de configuración que hace que **un tercero avise**, y la renovación sigue siendo la del capítulo 22.

Hay un matiz honesto que no conviene esconder: §3.7 y §3.8 estaban clasificados como «no se puede hacer todavía», y este capítulo demuestra que sí se podía. **Eso es una corrección del documento de congelación tanto como del código**, y el apéndice de ese documento lo dice con esas palabras.

---

## 37.2. Qué significa *k-anonymity* aquí, en números

La idea es vieja y la implementación es de tres líneas, pero el razonamiento merece escribirse entero porque es lo único que hace aceptable mandar algo —lo que sea— derivado de una contraseña a una máquina que no es nuestra.

De la contraseña se calcula su resumen SHA-1, que son 40 caracteres hexadecimales. **Salen los cinco primeros. Se quedan aquí los treinta y cinco restantes.**

```
contraseña        ->  "tramoya-vistosa-9271"
resumen SHA-1     ->  4F2A1 C8B3E5D9A07F6B2C4E8D1A3F5B7C9E0D2A48
                      ^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                      sale   se queda
```

Cinco caracteres hexadecimales son **20 bits**: 1 048 576 prefijos posibles. El servidor recibe uno de ese millón largo y devuelve **todos** los sufijos que empiezan por él —entre trescientos y mil en la práctica—, sin saber ni poder saber cuál de ellos nos interesaba. La comparación se hace aquí.

Y aquí está la propiedad que de verdad importa, la que no es obvia: **la respuesta es idéntica se haya acertado o no**. El servidor no puede distinguir entre «le mandé una contraseña filtrada» y «le mandé una contraseña que no lo está», porque en los dos casos nos manda exactamente la misma lista. No es que no sepa cuál era: es que no sabe siquiera si alguna lo era.

### El tamaño también habla, y por eso va `Add-Padding`

Falta una fuga que es fácil pasar por alto. El cuerpo viaja cifrado, pero su **longitud** no. Cada prefijo tiene un número distinto de sufijos, así que el tamaño de la respuesta identifica el prefijo para cualquiera que mire el cable, aunque no pueda leer nada.

El servicio ofrece una cabecera para eso, y la petición la lleva:

```python
headers={"Add-Padding": "true", ...}
```

Con ella, el servicio rellena la respuesta hasta un tamaño uniforme con entradas falsas de **recuento cero**, que este módulo descarta. Es la diferencia entre «no mando el secreto» y «no mando nada que lo distinga».

El descarte no es un detalle de implementación: **contar el relleno sería un fallo con síntoma**. Una entrada de relleno que coincidiera por azar con nuestro sufijo haría que el sistema rechazara una contraseña perfectamente buena, y la persona que lo sufriera no tendría forma de entender por qué, porque no hay por qué. `_buscar_sufijo` lo ignora y hay una prueba que lo fija.

### Por qué SHA-1, que está roto

Porque aquí **no se usa como función de seguridad**. Se usa como índice compartido con el servicio, y el servicio publica SHA-1.

Lo que protege la contraseña no es la resistencia de SHA-1 a colisiones: es que solo salen cinco de sus cuarenta caracteres. Y lo que protege la contraseña **guardada** sigue siendo bcrypt, que no cambia en este capítulo ni se acerca a él. Por eso se pide con la bandera que dice exactamente eso:

```python
hashlib.sha1(contrasena.encode("utf-8"), usedforsecurity=False)
```

Además de documentar la intención, esa bandera evita que una compilación de Python en modo FIPS —que deshabilita SHA-1 para usos criptográficos— niegue el algoritmo y tire abajo el alta de usuario por un motivo que nadie relacionaría.

---

## 37.3. La política ante el fallo, que es la mitad difícil

Preguntar a un tercero es fácil. Lo difícil es decidir qué hace el sistema cuando ese tercero no contesta, y es donde esta clase de mejora se estropea en silencio. Hay dos formas de equivocarse y las dos son peores que no tener la comprobación:

1. **Bloquear.** «Si no puedo comprobarlo, no te dejo.» Un corte de internet, o un mal día del servicio, y nadie puede darse de alta ni cambiar su contraseña por un motivo que no tiene nada que ver con quien lo sufre.
2. **Abrirse.** «Si no puedo comprobarlo, adelante.» Si además se hubiera dejado de consultar la lista local, un servicio caído convertiría la política entera en un «todo vale» que nadie vería desde fuera: el formulario seguiría teniendo el mismo aspecto.

La forma de no caer en ninguna de las dos es que el veredicto **no sea un booleano**:

```python
@dataclass(frozen=True)
class Veredicto:
    filtrada: Optional[bool]   # True, False y None. El tercero es "no se pudo preguntar".
```

`None` no es «no está filtrada». Quien llama tiene que distinguirlos, y al no ser un booleano no puede olvidarse de hacerlo.

La política, en `passwords.py`, cabe en cuatro líneas y en una regla: **el orden**.

```python
if normalizada in CONTRASENAS_PROHIBIDAS or ...:
    motivos.append("Esa contraseña está entre las primeras que prueba cualquier ataque.")
elif normalizada in contrasenas_filtradas() or ...:      # la lista LOCAL, capítulo 23
    motivos.append("Esa contraseña aparece en filtraciones públicas: ...")
elif preguntar_fuera:                                     # solo si las dos locales pasaron
    veredicto = filtradas_remotas.consultar(contrasena)
    if veredicto.filtrada:                                # None cae aquí, y no añade nada
        motivos.append(filtradas_remotas.MOTIVO_FILTRADA_FUERA)
```

Tres cosas de esas líneas, por orden de importancia:

**Primera: `if veredicto.filtrada:` y no `is not None`.** Con `None` la condición es falsa, igual que con `False`, y no se añade ningún motivo. No es un descuido aprovechado: es la política escrita de la única forma que no se puede revertir sin que se note.

**Segunda: es un `elif`.** Se pregunta fuera **solo si las listas locales dejaron pasar la contraseña**. No hay ningún motivo para mandar ni cinco caracteres del resumen de algo que ya está rechazado, y una salida a internet por cada `123456789012` es una salida a internet regalada.

**Tercera, y es la que cierra el punto 2 del encargo: sin servicio, el resultado es exactamente el de antes del capítulo 37.** No «parecido»: el mismo. Hay una prueba que lo fija comparando las dos listas de motivos carácter a carácter:

```python
def test_sin_servicio_el_resultado_es_el_de_antes_del_capitulo_37(monkeypatch):
    ...
    for contrasena in (ACEPTADA_EN_LOCAL, "corta", "password", "Plurione2026!!"):
        con_servicio_caido = passwords.evaluar(contrasena, preguntar_fuera=True)
        como_siempre       = passwords.evaluar(contrasena, preguntar_fuera=False)
        assert con_servicio_caido == como_siempre, contrasena
```

Sin red no se degrada a «todo vale». Se degrada a **lo que había**, que seguía siendo una longitud mínima de doce, tres clases de carácter, la lista del contexto, los fragmentos del nombre y del correo, y doce mil filtradas locales. Lo que se pierde es la mejora, no la defensa.

### Y por eso no hay reintentos

El tope son dos segundos y se pregunta **una vez**.

Un reintento con espera suena prudente y es justo lo contrario: multiplica el tope por un número que nadie fijó, y convierte un tercero caído en un formulario de alta que tarda ocho segundos en responder. El tope corto no existe para que la consulta sea rápida; existe para que **un servicio ajeno no pueda retener a quien está dándose de alta**. Un reintento le devuelve esa capacidad.

El ajuste está acotado por un validador, y el motivo es el mismo:

```python
if not 0.5 <= valor <= 10:
    raise ValueError("...por debajo no cabe el apretón de manos TLS y por encima el alta
                      se queda colgada esperando a un tercero.")
```

---

## 37.4. El TLS interceptado, que ya mordió una vez

El punto 3 del encargo pide algo muy concreto: que la conexión saliente use el contexto TLS del sistema y no el paquete de certificados de la biblioteca. No es una preferencia estética.

```python
def _contexto_tls() -> ssl.SSLContext:
    return ssl.create_default_context()
```

En esta máquina —y en cualquiera con un antivirus que inspeccione el tráfico, o detrás del proxy de una empresa— el certificado que llega no está firmado por la autoridad real del servicio: está firmado por una autoridad local que el sistema operativo conoce y que el paquete `certifi` que trae `httpx` **no**. El resultado es un error de verificación.

Lo grave no es el error: es **cómo se lee**. Este módulo convierte cualquier fallo en `filtrada=None`, es decir, en «el servicio no contestó». Con `certifi`, el sistema diría «el servicio de contraseñas filtradas no está disponible» todos los días, para siempre, sobre un servicio que funciona perfectamente — y como la política ante `None` es seguir adelante, **nadie lo notaría nunca**. La comprobación estaría apagada de hecho mientras el código afirmaba tenerla.

Es exactamente el falso negativo que mordió en el capítulo 34 con `scripts/comprobar_puerta_publica.py`, donde el guion decía «no se pudo conectar» sobre un túnel que estaba levantado. Allí se descubrió porque alguien miró el túnel con el navegador. Aquí no habría nada que mirar.

Por eso el control 44 del CI vigila esa línea, y vigila también lo contrario: que nadie la «arregle» con `verify=False`.

---

## 37.5. Qué queda en la bitácora, y qué no

El punto 1 del encargo dice «nunca la contraseña ni el resumen completo» y el punto 2 añade «cada caso queda en la bitácora sin la contraseña ni su resumen». Es fácil cumplirlo al escribir el módulo y fácil romperlo tres meses después depurando un incidente.

Se registran **el prefijo, el resultado y el motivo**:

```
WARNING  No se pudo comprobar la contraseña contra el servicio de filtradas
         (prefijo 4F2A1): ConnectionError. Se continúa con la lista local; no se
         bloquea a nadie.
INFO     Contraseña rechazada por aparecer en filtraciones públicas
         (prefijo 4F2A1, 38421 apariciones).
```

El prefijo sí, porque **ya salió por el cable**: registrarlo no añade ninguna exposición y sin él un incidente no se puede investigar. El sufijo no, nunca, y la contraseña menos. Una bitácora que guardara el resumen completo anularía de un plumazo todo lo del §37.2: el archivo de registro acabaría siendo el diccionario que no quisimos mandar, y encima guardado en disco donde lo lee más gente.

Hay una fuga de segundo orden que vale la pena contar porque no es evidente. Cuando la consulta lanza, se registra **la clase de la excepción y no su mensaje**:

```python
except Exception as exc:
    return _sin_respuesta(prefijo, exc.__class__.__name__)
```

El mensaje de una excepción de `httpx` lleva la URL dentro, y la URL lleva el prefijo. En este caso concreto el prefijo ya se registra aparte, así que no habría pasado nada — pero el hábito de dejar que un texto libre de un tercero entre en la bitácora es justo por donde se escapa lo que nadie decidió registrar. Hay una prueba que lo fija con una excepción cuyo mensaje lleva un secreto a propósito:

```python
def sonda(prefijo, timeout):
    raise ErrorConUrlDentro(f"fallo al pedir https://ejemplo/range/{prefijo}SECRETO")
...
assert "ErrorConUrlDentro" in caplog.text
assert "SECRETO" not in caplog.text
```

### Un detalle de la interfaz: el recuento no se enseña

El veredicto lleva cuántas veces apareció la contraseña en filtraciones. El mensaje que ve quien la escribió, no:

> *«Esa contraseña aparece en filtraciones públicas conocidas. No se ha enviado su contraseña a ningún sitio: solo cinco caracteres del resumen, que no permiten reconstruirla. Elija una que no haya usado en otro sitio.»*

Saber que apareció 38 421 veces en lugar de 12 no ayuda a nadie a elegir otra, y es exactamente la pista que un atacante querría para ordenar su diccionario. El número va a la bitácora, que es donde sirve.

La segunda frase del mensaje es deliberada y no es relleno. Quien acaba de teclear una contraseña y lee «aparece en filtraciones públicas» tiene todo el derecho a preguntarse si acabamos de mandarla a algún sitio. Contestarle antes de que lo pregunte cuesta una línea.

---

## 37.6. Las dos guardas que impiden que la suite salga a internet

Una comprobación que depende de un tercero no puede entrar en la suite sin más, y el motivo no es la lentitud: es que **una suite que depende de un tercero se pone roja los días que ese tercero tiene un mal día**, y a partir de ahí el rojo del CI deja de significar «el código está mal». Es la forma más barata de destruir el valor de todo lo demás que el CI comprueba.

Hay dos guardas, y son dos a propósito.

**La primera** es el interruptor, en `conftest.py`:

```python
os.environ["COMPROBAR_CONTRASENAS_FILTRADAS"] = "false"
```

**La segunda** está dentro del módulo, por si alguien enciende el interruptor en una prueba:

```python
if sonda is None:
    if settings.ENVIRONMENT == "test":
        raise RuntimeError("La suite no sale a internet: inyecte `sonda` o deje "
                           "COMPROBAR_CONTRASENAS_FILTRADAS apagada.")
```

La diferencia entre tener una guarda y tener dos es la diferencia entre «esta suite no sale a internet» y «esta suite no sale a internet **mientras nadie toque el fixture**». La segunda frase es la que se puede comprobar dentro de seis meses.

El servicio se simula con una **sonda inyectada**, que es la misma costumbre de `services/direccion_publica.py` del capítulo 34, y se simulan los cuatro casos que pide el encargo más cinco que no pedía:

| Caso | Qué devuelve | Qué hace el sistema |
| :--- | :--- | :--- |
| Filtrada | 200 con nuestro sufijo | Rechaza, sin decir el recuento |
| No filtrada | 200 sin nuestro sufijo | Acepta |
| Caída | excepción de red | **No bloquea.** Sigue con lo local |
| Lenta | agota el tope | **No bloquea.** Idéntico a la caída |
| 429, 503, 500, 301 | código distinto de 200 | **No bloquea.** «Ahora no» no es «no está» |
| Relleno con recuento 0 | 200 con nuestro sufijo y `:0` | Acepta: es relleno, no un hallazgo |
| Cuerpo vacío o HTML | 200 con basura | Acepta, sin romper el alta |
| Recuento no numérico | `SUFIJO:no-es-un-numero` | Acepta, sin romper el alta |
| Apagada | — | Ni calcula el resumen |

Los cuatro últimos son el mismo miedo escrito cuatro veces: **que un cambio en el formato del servicio ajeno convierta el alta de usuario en un error 500**. Nada de lo que haga un tercero puede impedir que alguien se dé de alta en este sistema.

### Lo que se mide es el argumento, no la URL

La prueba central del capítulo captura lo que recibe la sonda —la única función que abre un socket— y lo mide:

```python
assert len(enviado) == PREFIJO == 5
assert enviado == _resumen(ACEPTADA_EN_LOCAL)[:5]
assert all(c in "0123456789ABCDEF" for c in enviado)
```

Comprobarlo sobre la URL construida habría comprobado la misma línea de código dos veces. Comprobarlo sobre el argumento comprueba el **contrato**. Y hay una segunda prueba que mira lo que **no** sale, porque no es redundante: un cambio que añadiera la contraseña como parámetro de consulta «para depurar» dejaría intacta la longitud del prefijo y pasaría la primera prueba sin inmutarse.

---

## 37.7. §3.8: lo automático avisa, la renovación a mano decide

El capítulo 22 fijó todas las imágenes de terceros por huella: `nombre:etiqueta@sha256:…`. Esa decisión tiene una consecuencia que el propio capítulo 22 asumió y el §3.8 anotó como deuda: **la huella es precisamente lo que impide que la imagen cambie sola**, así que una base con un parche de seguridad publicado hace cuatro meses sigue ahí, idéntica, sin que nada del repositorio cambie ni nadie se entere.

`.github/dependabot.yml` pone a alguien a mirar. Seis entradas:

| Ecosistema | Dónde | Qué vigila |
| :--- | :--- | :--- |
| `github-actions` | `/` | Las siete acciones del CI, que corren con el token del trabajo |
| `pip` | `/backend` | Las dependencias de Python |
| `npm` | `/frontend` | Las del cliente |
| `docker` | `/backend` | `python:3.13-slim` |
| `docker` | `/frontend` | `node:20-alpine`, `nginx:alpine` |
| `docker-compose` | `/devops` | `postgres:16-alpine`, `redis:7-alpine` y las dos del overlay |

### El punto 5 del encargo, que es el que hay que escribir con cuidado

> *«La renovación a mano sigue existiendo y sigue siendo la fuente de verdad; lo automático solo avisa.»*

Esto no se cumple configurando nada: se cumple **diciéndolo donde se mira**, y la cabecera de `dependabot.yml` lo dice antes que cualquier otra cosa.

`scripts/renovar_imagenes.py` es quien conoce este proyecto. Sabe que la misma `nombre:etiqueta` no puede aparecer con dos huellas distintas en archivos distintos, que un Dockerfile no puede volver a `apt-get upgrade`, que un paquete del sistema va con versión fijada, que una acción de GitHub va por la huella de su commit. **Nada de eso lo sabe Dependabot**, y su solicitud puede perfectamente dejar el repositorio en un estado que la guarda `--solo-fijacion` rechaza. Cuando eso pase, manda el guion.

Y al revés, que es la confusión que este archivo podría crear y por eso está escrita en él:

> *«Que no haya solicitudes abiertas NO significa que todo esté al día. Significa que Dependabot no ha visto nada. Lo que significa “al día” sigue siendo `python scripts/renovar_imagenes.py` sin salida.»*

### Qué se acepta sin pensar y qué exige repetir la comprobación de la imagen

Es la otra mitad del punto 4, y es una decisión operativa que conviene tener tomada **antes** de tener la solicitud delante un martes por la mañana.

**Se acepta con el CI verde y nada más:**

* Un parche (`1.2.3` → `1.2.4`) de Python o de npm que no venga del grupo de seguridad. Si rompe algo, lo rompe en la suite, y la suite corre en la propia solicitud.
* Una acción de GitHub que sube de huella dentro de la misma versión mayor, con su comentario `# vX.Y` al lado intacto.

**Exige construir, escanear con Trivy, mirar el inventario de syft y comprobar los paquetes con versión de los dos Dockerfile:**

* **Cualquier** cambio de huella de una imagen base. Una huella nueva de la misma etiqueta es un sistema operativo distinto por dentro: puede traer ya el paquete que el Dockerfile instala con versión —y entonces esa línea sobra—, puede no tener esa versión —y entonces la construcción falla—, o puede traer una vulnerabilidad que el escaneo tiene que ver antes que producción.
* Cualquier subida de versión mayor, de lo que sea. Una mayor es una decisión, no una actualización.
* Cualquier cosa del grupo de seguridad, aunque sea un parche: el motivo de que exista la solicitud es que hay un aviso publicado.
* Cualquier solicitud que toque `backend/requirements.lock`. Ese archivo lleva hashes y `--require-hashes`: **se regenera, no se edita**. Una solicitud que lo edite se cierra y se vuelve a generar en local.

### Por qué los límites son tan bajos

`open-pull-requests-limit` va entre 3 y 5 en todas partes, y los parches se agrupan en una sola solicitud. Un repositorio congelado con veinte solicitudes abiertas no es un repositorio vigilado: es un repositorio con veinte avisos que nadie lee, y el día que llegue el que importa estará en la página dos. Pocas y leídas vale más que todas y acumuladas — es la misma razón por la que el §37.5 registra el fallo del servicio en `WARNING` y no en `ERROR`.

---

## 37.8. Los dos controles nuevos, y los diecisiete defectos que se les reintrodujeron

`configuracion-peligrosa` pasa de **43 a 45 controles**.

**El 44, «La contraseña no sale de esta máquina»**, vigila ocho propiedades estructurales: que `PREFIJO` siga siendo 5 y no sea configurable; que la petición se construya con el prefijo y nada más; que `hexdigest()` aparezca **una sola vez** en todo el módulo y dentro de `huella_partida`; que la URL sea `https`; que se use el contexto del sistema y no `certifi` ni `verify=False`; que no se sigan redirecciones; que no aparezca ningún reintento ni espera; que la bitácora no reciba el sufijo ni la contraseña; que la política ante `None` siga siendo `if veredicto.filtrada:`; que la consulta siga detrás de las listas locales; y que las dos guardas de la suite sigan en su sitio.

Hay una división deliberada de trabajo entre el control y la suite: **la suite comprueba el comportamiento** —captura el argumento que recibe la sonda y lo mide— y **el control comprueba la estructura**, es decir, las líneas que, borradas por descuido, dejarían la prueba pasando y la propiedad perdida.

**El 45, «Las actualizaciones automáticas cubren todo lo que está fijado»**, lee `dependabot.yml` como YAML y comprueba tres cosas. Que los seis ecosistemas exigidos estén. Que **ningún directorio con imágenes fijadas por huella se quede fuera** —esto se calcula recorriendo los `Dockerfile` y los compose en busca de `@sha256:`, no copiando una lista a mano, de modo que un Dockerfile nuevo mañana aparezca aquí sin que nadie se acuerde de añadirlo—. Y que la renovación a mano siga existiendo con su guarda `--solo-fijacion`, y que el criterio de §37.7 siga escrito en el archivo.

### La comprobación de que los controles sirven

Un control que no se ha visto en rojo es una conjetura. Se escribió un arnés que reintroduce cada defecto, corre su control y restaura el archivo:

```
  control 44  rojo  OK   el prefijo crece a seis caracteres
  control 44  rojo  OK   se deja de verificar el certificado
  control 44  rojo  OK   se vuelve al paquete certifi
  control 44  rojo  OK   se siguen redirecciones
  control 44  rojo  OK   aparece un reintento con espera
  control 44  rojo  OK   la bitacora recibe el sufijo
  control 44  rojo  OK   el resumen vuelve a calcularse entero fuera de huella_partida
  control 44  rojo  OK   el servicio caido pasa a bloquear al usuario
  control 44  rojo  OK   se pregunta fuera ANTES que a las listas locales
  control 44  rojo  OK   la comprobacion deja de venir encendida
  control 44  rojo  OK   la suite deja de apagar la salida a internet
  control 44  rojo  OK   desaparece la guarda de ENVIRONMENT=test
  control 45  rojo  OK   dependabot deja de vigilar la imagen base del backend
  control 45  rojo  OK   dependabot deja de vigilar las imagenes de la pila
  control 45  rojo  OK   dependabot deja de vigilar las acciones del CI
  control 45  rojo  OK   se borra el criterio de que se acepta sin pensar
  control 45  rojo  OK   se deja de nombrar la renovacion a mano como fuente de verdad

Los 17 defectos reintroducidos ponen su control en rojo.
```

### Y los tres disparos en falso, los tres por la misma razón

Las dos primeras versiones del control 44 estaban **rojas con el código correcto**, y las dos por el mismo motivo: buscaban una palabra en vez de una forma.

* `grep certifi` disparaba con los cinco párrafos de la cabecera del módulo que explican **por qué no se usa** `certifi`.
* `grep reintent` disparaba con las dos frases que explican **por qué no hay reintentos**.

Es una ironía con moraleja: cuanto mejor documentado está el motivo de no hacer algo, más fácil es que un control escrito a base de palabras sueltas crea que se está haciendo. Y el daño de un control que dispara en falso no es el minuto perdido: es que a la tercera vez alguien lo desactiva, y entonces deja de vigilar también lo que sí vigilaba. Los dos quedaron anclados a la forma que tendría el defecto —`verify=False`, `import certifi`, `time.sleep`, `for … in range(`— con un comentario que dice por qué, para que nadie los «simplifique» de vuelta.

**El tercero no lo destapó la reintroducción: lo destapó la suite**, y es el mismo error cometido por el capítulo 22 contra el 37. `test_imagenes_fijadas.py` se puso rojo con tres hallazgos:

```
.github/workflows/ci.yml: línea 3010: python:3.13-slim no va fijada por huella
.github/workflows/ci.yml: línea 3011: node:20-alpine no va fijada por huella
.github/workflows/ci.yml: línea 3011: nginx:alpine no va fijada por huella
```

Las tres «referencias sin fijar» eran **texto explicativo dentro del control 45**, diciendo qué vigila cada entrada de Dependabot. La guarda de fijación recorre el workflow buscando la forma `nombre:etiqueta` sin huella y no distingue una referencia que descarga algo de un nombre citado dentro de una cadena de Python.

Es el mismo fallo de fondo —buscar una forma textual sin mirar su contexto— y aquí se arregló por el otro lado, porque la guarda de fijación tiene quince capítulos de uso y el texto nuevo tenía diez minutos: las imágenes se nombran ahora sin los dos puntos (`python 3.13-slim`), con un comentario que dice por qué, para que nadie lo «corrija» de vuelta a la forma bonita.

Que la suite lo encontrara y no yo tiene su propia lectura: **la guarda del capítulo 22 estaba vigilando un archivo que el capítulo 37 editaba, y funcionó.** Es lo que se espera de ella.

---

## 37.9. Lo que este capítulo NO hizo

* **No se manda la contraseña ni su resumen completo a ningún servicio.** Era la primera línea de lo que quedaba fuera y no hubo ninguna tentación de acercarse.
* **No se tocaron las copias de seguridad** (§3.9). Sigue abierto y sigue necesitando almacenamiento externo, que es la única entrada de §3 que de verdad lo necesitaba de las tres.
* **No se tocó bcrypt**, ni el almacenamiento de contraseñas, ni la caducidad —que sigue sin existir, y sigue siendo deliberado—.
* **No se automatizó la renovación de huellas.** Dependabot avisa; `renovar_imagenes.py` decide. Automatizar la decisión habría sido la funcionalidad nueva que este capítulo no podía añadir, y además habría sido peor.
* **No se añadió ninguna biblioteca.** `httpx` ya estaba; `ssl` y `hashlib` son de la biblioteca estándar; Dependabot no es código.
* **No se regeneró la lista local.** Sigue siendo la foto del capítulo 23, y sigue siendo la que decide cuando no hay internet. Lo que cambia es que ya no es lo único.

---

## 37.10. Qué queda abierto después de esto

1. **La lista local sigue sin actualizarse sola.** Es la mitad de §3.7 que este capítulo **no** cierra, y hay que decirlo claro: el servicio externo la complementa, no la sustituye, porque es precisamente lo que queda cuando no hay servicio. Regenerarla sigue siendo correr `scripts/generar_lista_de_contrasenas.py` a mano. No es grave —una foto de las filtradas más frecuentes envejece despacio— pero no está cerrado.
2. **Nadie ha visto una solicitud de Dependabot en este repositorio todavía.** El archivo está bien formado y el control 45 comprueba que cubre lo que dice cubrir, pero el primer lunes que abra solicitudes de verdad es la comprobación que ninguna prueba sustituye. Entra en §6.3, «comprobaciones que nadie ha hecho a mano».
3. **La comprobación remota no se ha ejecutado nunca contra el servicio real desde esta máquina.** La suite usa una sonda simulada, por las razones del §37.6. La primera vez que corra de verdad es también la primera vez que se sabrá si el contexto TLS del sistema basta aquí — y si no bastara, el síntoma sería silencioso, que es exactamente el riesgo descrito en el §37.4. **Es lo primero que hay que mirar en la bitácora el día del despliegue**, buscando el `WARNING` del §37.5.
4. **El alta de usuario ahora puede tardar dos segundos más.** Es el precio, está acotado y no hay reintentos, pero nadie lo ha medido con una persona delante.
