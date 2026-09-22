# Capítulo 22: Nada sin Plazo ni sin Aviso — Caducidad de los Datos, Alertas del Monitor, Imágenes Fijadas y Arranque

## 22.1. Por qué existe esta fase

Los capítulos 17, 19, 20 y 21 terminan con una sección que dice lo que la fase no hizo. Leídas
juntas, cinco de esas entradas eran del mismo tipo: **algo que el sistema hacía sin plazo, o que
dejaba de hacer sin avisar**.

* **Datos sin plazo (§20.5, §20.8, §21.12).** Sesiones, trabajos de recálculo, registros del CRM
  y la bandeja «Sin asociar» crecían para siempre. La purga de sesiones existía desde la Fase 9
  y **nada la llamaba**.
* **Un monitor que calla (§19.9).** Cuando se negaba a evaluar, solo lo decía en su propia salida.
* **Imágenes sin fijar (§20.8, §17.9).** `python:3.13-slim`, `postgres:16-alpine` o
  `anchore/syft:latest` se resolvían por etiqueta, y `apk --no-cache upgrade` hacía que dos
  construcciones del mismo Dockerfile dieran imágenes distintas.
* **Secretos dentro del árbol.** Había tres maneras de arrancar la pila, y en las tres los
  secretos acababan en un `.env` dentro del repositorio.

Ninguna necesitaba cuentas externas. La fase se ocupó de las cinco.

---

## 22.2. Plazo para lo que no lo tenía

### El estado de partida

| Tabla | Qué guarda de personas | Qué había |
| :--- | :--- | :--- |
| `refresh_tokens` | IP del empleado | `purgar_tokens_caducados`, sin nadie que la llamara |
| `scoring_jobs` | Correo de quien lanzó el recálculo | Nada |
| `crm_integration_logs` | Correo, nombre y empresa de lo que llegó del CRM | Nada |
| `unmatched_events` | Correo, teléfono y nombre de quien aún no es prospecto | Nada |

### La regla

Cada tabla tiene un plazo en días, con un mínimo que se valida al arrancar: un `0` escrito por
error no puede convertir la purga diaria en un vaciado.

| Tabla | Ajuste | Por defecto | Mínimo | Cuenta desde |
| :--- | :--- | ---: | ---: | :--- |
| `refresh_tokens` | `CONSERVACION_SESIONES_DIAS` | 30 | 7 | que la sesión **caducó** |
| `scoring_jobs` | `CONSERVACION_TRABAJOS_DIAS` | 90 | 7 | que el trabajo **terminó** |
| `crm_integration_logs` | `CONSERVACION_REGISTROS_CRM_DIAS` | 90 | 30 | la sincronización |
| `unmatched_events` | `CONSERVACION_SIN_ASOCIAR_DIAS` | 90 | 30 | que el aviso **llegó** |

Los mínimos no son arbitrarios. Un token revocado por reutilización es la prueba de un
incidente, y los incidentes se investigan días después. Un recálculo fallido se mira la semana
en que falló. Una sincronización con el CRM se reclama al cerrar el mes. Un aviso sin asociar
necesita que alguien tenga tiempo de vincularlo.

### Lo vivo no caduca

La consulta de cada plazo lleva una decisión que no se ve a simple vista:

* **Una sesión vigente no se borra por antigua**: el plazo corre desde que caducó.
* **Un recálculo en curso no se borra nunca.** Solo caducan los terminados (`COMPLETED`,
  `FAILED`), sin turno ocupado y desde que terminaron.
* **Un aviso de la bandeja cuenta desde que llegó**, no desde que ocurrió. Un evento antiguo
  entregado ayer tiene que dar tiempo a vincularlo.

La purga de sesiones es la función que ya existía, no una segunda. El defecto era que nadie la
llamaba, y reescribirla al lado habría dejado dos criterios de qué es una sesión caducada.

### Dónde corre

En la misma pasada diaria que resume el historial de puntuación
(`scripts/retencion_historial.py`, servicio `retencion-historial`), y no en un servicio nuevo.
Un proceso más que supervisar es un proceso más que puede quedarse parado sin que nadie lo vea.

Tres propiedades de esa pasada:

1. **Cada plazo va en su transacción.** Si uno falla, los demás se aplican igual, y la pasada
   sale con código 1.
2. **Cada plazo deja un asiento en la bitácora** (`conservacion.purga`): tabla, días, corte y
   filas borradas. También cuando no hubo nada que borrar, porque «corrió y no encontró nada» es
   distinto de «no corrió». Y también cuando falló, con resultado `ERROR`.
3. **Simular cuenta y no escribe ni anota.** Es el mismo criterio que la retención del historial:
   la bitácora dice lo que pasó, no lo que se consultó que pasaría.

---

## 22.3. El monitor avisa también cuando no evalúa

### El estado de partida

Desde la Fase 13 el monitor de deriva se niega a evaluar si el perfil de referencia salió de otro
artefacto. Es lo correcto. Pero la negativa solo quedaba en la salida del contenedor, y el
servicio de la pila la repetía en cada reinicio sin que llegara a nadie. Tampoco avisaba de otros
tres casos:

* el perfil no existe;
* el perfil no se puede leer: un JSON truncado terminaba en una traza de Python;
* una evaluación falla dentro del bucle, por ejemplo con la base caída.

### Lo que hace

Con `--alertar`, que es como corre el servicio, la negativa sale por `ML_DRIFT_WEBHOOK` como
`[DERIVA-SIN-EVALUAR]`, con su motivo y desde cuándo el sistema no está vigilado.

* **Misma regla de silencio que la deriva.** El mismo motivo no se repite hasta pasado
  `ML_DRIFT_SILENCIO_S`. Sin eso, cada reinicio del contenedor sería un aviso, y un aviso que se
  repite solo se aprende a ignorar.
* **Un motivo nuevo sí avisa**, y «sin evaluar desde» sigue contando desde la primera negativa.
* **Aviso de vuelta.** Cuando el monitor evalúa otra vez, envía `[DERIVA-EVALUA-DE-NUEVO]` una
  sola vez.
* **Al webhook no llega el mensaje de la excepción, solo su clase.** El mensaje de un fallo de
  conexión nombra host, puerto y usuario de la base, y el receptor de avisos suele ser un
  servicio de fuera. El mensaje completo queda en la salida del contenedor.

Sin `--alertar`, una consulta manual informa y no avisa, igual que con la deriva.

---

## 22.4. Imágenes fijadas por huella

### Referencias

Toda imagen de terceros se escribe como `nombre:etiqueta@sha256:<huella>`. La huella decide lo
que se descarga. La etiqueta dice qué seguir al renovar, y cuando la etiqueta era `latest` y la
herramienta tiene versión, se sustituyó por la versión que había detrás (`anchore/syft:v1.51.1`,
`gitleaks:v8.30.1`), comprobando que la huella era la misma.

| Dónde | Imágenes |
| :--- | :--- |
| Dockerfiles | `python:3.13-slim` (dos etapas), `node:20-alpine`, `nginx:alpine` |
| Pila | `postgres:16-alpine` (base y tres servicios de respaldo), `redis:7-alpine` |
| Overlay de desarrollo | `alpine/socat`, `dpage/pgadmin4` |
| Integración continua | `postgres:16-alpine`, Trivy, syft, gitleaks |

Se usa la huella del **índice multiplataforma**, no la de una arquitectura: la misma referencia
sirve en el ejecutor x86 del CI y en un portátil ARM.

### Sin `apk upgrade`: un hallazgo

Quitar `apk --no-cache upgrade` y confiar en la base fijada no bastaba. Se comprobó en la propia
imagen fijada antes de escribir nada:

```
libuuid-2.42.1-r0      < 2.42.3-r1
xz-libs-5.8.3-r0       < 5.8.4-r0
apk-tools-3.0.6-r0     < 3.0.8-r0
```

La imagen oficial `nginx:alpine` más reciente **seguía trayendo el `libuuid` vulnerable** que
motivó el `apk upgrade` del capítulo 17. Sin sustituto, fijar la base habría reintroducido esas
siete ALTAS.

El sustituto nombra los paquetes con su versión exacta:

```dockerfile
RUN apk add --no-cache 'libuuid=2.42.3-r1' 'xz-libs=5.8.4-r0'
```

`apk-tools` aparece como pendiente y no se sube, porque la imagen no instala nada después de
construirse.

El precio es conocido: Alpine solo publica la última revisión de cada paquete en una rama, y el
día que salga otra esta línea dejará de construir. **Es lo buscado.** El aviso llega como un
fallo de construcción y no como una imagen distinta en silencio, y se resuelve renovando la base
y mirando qué sigue haciendo falta.

### El backend tampoco quedaba limpio: segundo hallazgo

Tras construir las dos imágenes con las bases fijadas, se pasó la misma puerta de Trivy que usa
el pipeline: altas y críticas **con arreglo publicado**.

* **Frontend: 0.**
* **Backend: 12.** `python:3.13-slim` —la huella que esa etiqueta publica hoy— trae cuatro
  paquetes de Debian para los que Debian 13 ya publicó corrección:

| Paquete | Instalado | Con arreglo | Avisos |
| :--- | :--- | :--- | ---: |
| `perl-base` | 5.40.1-6 | 5.40.1-6+deb13u1 | 7 |
| `libsqlite3-0` | 3.46.1-7+deb13u1 | 3.46.1-7+deb13u2 | 2 |
| `libpcre2-8-0` | 10.46-1~deb13u1 | 10.46-1~deb13u2 | 2 |
| `gzip` | 1.13-1 | 1.13-1+deb13u1 | 1 |

**No lo causó fijar la huella**: sin fijar, hoy se habría descargado la misma imagen, y la puerta
habría fallado igual. Es la entrada de §17.9 sobre la base de datos de Trivy del día. Pero con la
base fijada, esperar a que Docker Hub la reconstruya ya no la arregla sola, así que se aplicó la
misma regla que en Alpine: los cuatro paquetes, con su versión exacta, en la etapa de ejecución.

### Renovación explícita

`scripts/renovar_imagenes.py` tiene tres modos:

```bash
python scripts/renovar_imagenes.py --solo-fijacion   # sin red: la guarda
python scripts/renovar_imagenes.py                   # pregunta al registro qué quedó atrás
python scripts/renovar_imagenes.py --aplicar         # reescribe las huellas atrasadas
```

`--solo-fijacion` falla si:

* una imagen va sin huella;
* la misma `nombre:etiqueta` aparece con dos huellas distintas (una renovación a medias: el CI
  escanearía una imagen y la pila desplegaría otra, con el mismo nombre);
* un Dockerfile vuelve a `apk upgrade`;
* un Dockerfile instala un paquete de `apk` sin versión.

Solo usa la biblioteca estándar. Por eso lee los archivos de Compose con un lector propio de dos
niveles de sangría, y la suite comprueba que ese lector y `yaml.safe_load` ven los mismos
servicios y las mismas imágenes.

`--aplicar` no decide nada por su cuenta: deja un diff para revisar, y después hay que construir,
pasar Trivy y revisar los paquetes de `apk` con versión.

---

## 22.5. Un solo modo de arrancar, con el entorno fuera del repositorio

### El estado de partida

* El README mandaba escribir `SECRET_KEY` y `POSTGRES_PASSWORD` con `>> .env` dentro de `devops/`.
* La cabecera del compose decía `cd devops && docker compose up`.
* La aplicación, fuera de Docker, lee además `.env` y `../.env` desde donde se lance.

Que `.gitignore` excluya esos archivos evita que se versionen, no que existan. Un `.env` dentro
del repositorio viaja en cada copia de la carpeta, en cada comprimido y en cada respaldo del
portátil. En la Fase 0 de seguridad hubo que sacar uno con la clave ya expuesta.

### El lanzador

`devops/pila.py` envuelve `docker compose` y le pasa siempre el mismo archivo de entorno:
`~/.plurione/pila.env`, o el que indique `PLURIONE_ENTORNO`. Antes de ejecutar nada comprueba
cuatro cosas y se niega si falla cualquiera:

1. el archivo existe;
2. no está dentro del repositorio (con `normcase`: en Windows `C:\Users` y `c:\users` son la
   misma carpeta);
3. no hay un `.env` en `devops/`, en la raíz ni en `backend/` que Compose o la aplicación leerían
   por su cuenta;
4. trae `SECRET_KEY` y `POSTGRES_PASSWORD`.

```bash
python devops/pila.py iniciar            # crea el archivo con secretos nuevos; nunca sobrescribe
python devops/pila.py up -d --build
python devops/pila.py --dev up -d
python devops/pila.py --comprobar        # solo las comprobaciones
```

`iniciar` escribe el archivo con permisos solo para su usuario y **no sobrescribe nunca**.
`POSTGRES_PASSWORD` solo se aplica al crear el volumen, y cambiarla sobre una base ya creada deja
al backend sin poder conectar.

**El proyecto de Compose sigue llamándose `devops`**, como cuando se arrancaba desde esa carpeta.
Con otro nombre, la pila crearía volúmenes nuevos y vacíos al lado de los existentes, y la base
«desaparecería».

Todas las órdenes de la documentación que vigila la guarda pasan por el lanzador: README,
cabeceras de los dos compose y `.env.example`. También se cambiaron las de los comentarios del
Dockerfile del backend.

---

## 22.6. Una reparación en el capítulo 21

Al preparar esta fase se encontró **dañado el final del capítulo 21**, en el reporte y en la
memoria. Una edición posterior al cierre había mezclado tres cosas:

* la última fila de la tabla de evidencia (§21.11), cortada a mitad de palabra;
* el encabezado de §21.12, perdido;
* un fragmento de la versión anterior de la primera entrada de §21.12, que decía que PostgreSQL
  «queda pendiente» justo debajo de la entrada que dice que ya se verificó.

Se restauró la estructura: la fila se cierra, el encabezado vuelve y el fragmento obsoleto se
retira. **La palabra que completa la fila («en ninguna columna») es una reconstrucción**, tomada
de cómo §21.8 describe esa prueba, y no el texto original, que no se conserva en ningún sitio. Si
la tabla tenía más filas después de esa, se perdieron con el daño.

---

## 22.7. Que nada de esto sea decorativo

### Las pruebas

63 pruebas nuevas en cuatro archivos:

| Archivo | Qué comprueba |
| :--- | :--- |
| `test_caducidad_de_los_datos.py` | Lo vencido se va y lo vivo se queda, en cada tabla. La purga de sesiones es la función de siempre. Hay asiento por plazo, también sin filas. Simular no escribe. Un fallo no detiene a los demás. El guion diario aplica los plazos y la pila se los pasa. |
| `test_monitor_avisa_cuando_no_evalua.py` | Las cuatro negativas llegan al webhook. No se avisa sin `--alertar`. Hay silencio entre avisos y se avisa ante un motivo nuevo. El mensaje de la excepción no sale. El aviso de vuelta llega una vez. |
| `test_imagenes_fijadas.py` | El repositorio está fijado. Cada forma de volver atrás se detecta, y lo que no es una imagen ajena no dispara. El lector de Compose coincide con YAML. Se renueva solo lo atrasado. |
| `test_arranque_de_la_pila.py` | El lanzador se niega en cada caso sin ejecutar Docker. La orden conserva el proyecto. `iniciar` no sobrescribe ni escribe dentro. La documentación no enseña otro modo. |

### Las guardas del pipeline

Tres guardas nuevas en `configuracion-peligrosa` y una en `compose`:

| Guarda | Qué detecta |
| :--- | :--- |
| Nada sin plazo | La pasada diaria sin caducidad, una tabla fuera de la lista, la purga de sesiones por otra función, recálculos vivos que caducan, un plazo que no llega a la pila |
| El monitor avisa también cuando no evalúa | Una negativa en silencio, el mensaje de la excepción en el aviso, la negativa sin webhook |
| Imágenes fijadas por huella | `scripts/renovar_imagenes.py --solo-fijacion` |
| La pila solo arranca con el entorno fuera | Ejercita el lanzador de verdad —`iniciar`, `--comprobar`, `config`— y exige que se niegue con un `.env` dentro y con un entorno dentro |

### Reintroducciones

Se reintrodujeron **35 defectos**, uno a uno, con un arnés que copia cada archivo antes de
tocarlo y lo restaura siempre. A cada defecto se le pasó la prueba que lo cubre y, cuando la
hay, la guarda del pipeline, ejecutando el mismo guion del YAML. Se exige que la prueba falle,
que la guarda falle con la palabra `FALLO`, y que las dos pasen sobre el árbol correcto.

| Pieza | Defectos reintroducidos |
| :--- | :--- |
| Caducidad | recálculos vivos que caducan; sesiones por otra función; la bandeja fuera de la lista; la bandeja por fecha del evento; sin asiento cuando no hay filas; simular borra; un fallo detiene a los demás; sesiones desde la emisión; plazo mínimo ignorado; el guion no aplica los plazos; un plazo que no llega a la pila |
| Monitor | perfil ajeno en silencio; perfil ausente en silencio; el mensaje de la excepción en el aviso; la negativa sin webhook; sin silencio entre negativas; sin aviso de vuelta; avisa sin `--alertar` |
| Imágenes | vuelve `apk upgrade`; paquete de `apk` sin versión; base del backend por etiqueta; una etiqueta con dos huellas; Redis por etiqueta; syft vuelve a `latest`; la guarda no ve `apk upgrade`; confunde etapas con imágenes; no ve registros con dominio; no ve dos huellas; renovar reescribe todas |
| Arranque | acepta un entorno dentro; ignora los `.env` sueltos; otro proyecto de Compose; `iniciar` sobrescribe; no exige los secretos; el README vuelve a `docker compose` |

**Resultado de la primera ejecución: 34 de 35 pruebas detectaban, y las 18 guardas
disparaban.** Se escapaba un defecto: quitar el filtro «solo recálculos terminados» dejaba la
prueba en verde. En sus datos, cada trabajo vivo ya quedaba protegido por uno de los otros dos
filtros, sin turno o sin fecha de fin, así que la condición de estado no tenía ningún caso
propio. Solo la guarda la echaba en falta.

Se añadió el caso que faltaba: un trabajo que dice `RUNNING`, no ocupa el turno y tiene fecha
de fin. Es un estado que no debería existir, y ante la duda se conserva. Con él, el defecto se
detecta y la prueba sigue pasando sobre el árbol correcto. **Resultado final: 35 de 35 y 18 de
18.**

---

## 22.8. Evidencia

| Comprobación | Resultado |
| :--- | :--- |
| Suite del backend, en el entorno instalado desde el lock | **791 pruebas**, 92 % de cobertura |
| `ruff` | Sin avisos |
| Guarda de imágenes sobre el repositorio | 10 referencias fijadas, ninguna sin huella, sin `apk upgrade` |
| Lanzador contra Docker real | `iniciar` crea el entorno fuera; `--comprobar` y `config --quiet` pasan; proyecto `devops`; rechaza un entorno dentro del repositorio |
| Integración continua | 10 trabajos, 114 pasos, 32 guardas en `configuracion-peligrosa` |
| Imagen del frontend, con base fijada y `apk add` con versión | Se construye; `libuuid 2.42.3-r1` y `xz-libs 5.8.4-r0` instalados; Trivy (ALTAS/CRÍTICAS con arreglo): **0** |
| Imagen del backend, con base fijada | Se construye e importa la aplicación. Trivy: **12** con la base tal cual, **0** tras fijar los cuatro paquetes de Debian |
| Paquetes de Debian con versión | Se instalan sobre la base fijada con exactamente esas versiones |
| Reintroducciones | 35 defectos: pruebas 35/35 (34/35 en la primera ejecución, §22.7); guardas 18/18 con `FALLO` |

---

## 22.9. Lo que esta fase no hizo

* **El CSV de realimentación sigue sin mecanismo de caducidad.** Vive fuera de la base y fuera
  del control de versiones; es la última fila de §20.5 sin plazo.
* **La bitácora sigue sin plazo en la aplicación.** Es una decisión de operación desde el
  capítulo 14, y esta fase no la cambia.
* **Un aviso purgado puede volver a entrar.** Si el sistema de origen lo reentrega después del
  plazo, su `(fuente, identificador externo)` ya está libre. Conservar la huella de lo purgado
  sería guardar sin plazo un rastro de lo que se decidió no guardar.
* **Nadie avisa de que una huella se quedó atrás.** La renovación es explícita, y eso incluye que
  alguien tenga que correr el guion. Automatizarla con un servicio que abra solicitudes de cambio
  exige una cuenta externa, que esta fase excluía.
* **La guarda no mira `apt-get`.** Los cuatro paquetes de seguridad del backend van con versión,
  pero `libpq5` y las herramientas de compilación de la primera etapa no, y la guarda solo
  exige versión a `apk`. Es la misma clase de indeterminación que se quitó en Alpine, a medias.
* **Las acciones de GitHub van por etiqueta** (`actions/checkout@v4`), no por el SHA de un commit.
* **`socat` y `pgAdmin` siguen `latest`** al renovar. Van fijadas por huella, pero la etiqueta no
  dice versión.
* **El monitor no avisa cuando no hay instantáneas.** En una instalación nueva es el estado
  normal durante días, y avisar de él sería ruido.
* **Fuera de Docker, la aplicación sigue leyendo `.env` y `../.env`** desde donde se lance. El
  lanzador cubre la pila; la ejecución directa con `uvicorn` depende de que quien la lanza
  exporte las variables, como indica el README.
* **Los plazos son técnicos y provisionales.** No hay valoración jurídica; fijarlos corresponde a
  quien responda del tratamiento de datos.
