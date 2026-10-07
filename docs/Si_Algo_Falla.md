# Si algo falla

**Para quién es esto.** Para quien tenga que encender, apagar o rescatar el sistema **sin
programar**. Todo son órdenes que se copian y se pegan. No hay que entender el código ni
abrir ningún archivo de programa.

**Cómo se usa.** Si ya sabe qué quiere hacer, vaya a su apartado. Si lo que tiene es un
síntoma —«no carga», «no entra», «el enlace no lleva a ninguna parte»—, vaya directo a la
**tabla del §8**.

> ## ⚠ Las tres cosas que no hay que hacer nunca
>
> 1. **No escriba `-v` detrás de `down`.** `python devops/pila.py down -v` **borra la base de
>    datos entera**, y no hay botón de deshacer. Sin `-v` solo apaga.
> 2. **No arranque con `docker compose` a secas.** Siempre `python devops/pila.py`. El
>    lanzador es lo que encuentra los secretos y comprueba que están donde deben.
> 3. **No cree archivos `.env` dentro de la carpeta del proyecto.** El sistema se niega a
>    arrancar si encuentra uno, y hace bien: un archivo con contraseñas dentro de la carpeta
>    viaja en cada copia y en cada correo.

---

## 1. Dónde está cada cosa

| Qué | Dónde |
| :--- | :--- |
| El proyecto | `C:\Users\<usted>\Desktop\Resi\Sistema_Inteligente_Lead_Scoring` |
| Las contraseñas del sistema | `C:\Users\<usted>\.plurione\pila.env` — **fuera** del proyecto, a propósito |
| El panel, en esta máquina | <http://localhost:3000> |
| La página pública, en esta máquina | `http://127.0.0.1:8080/interes/<enlace-de-la-publicación>` |
| Las copias de seguridad | dentro de Docker, en un volumen aparte llamado `devops_pgrespaldos` |

> **La dirección pública a secas da «404»**, y eso es correcto: cada publicación tiene su
> propio enlace de 128 bits, y la dirección sin enlace no es de nadie. El enlace completo se
> copia desde el panel, en la pestaña «Publicaciones».

Todas las órdenes de este documento se escriben **desde la carpeta del proyecto**. Para
llegar ahí, abra una ventana de órdenes (PowerShell) y escriba:

```bash
cd C:\Users\<usted>\Desktop\Resi\Sistema_Inteligente_Lead_Scoring
```

---

## 2. Encender el sistema

**Hace falta que Docker Desktop esté abierto.** Si no lo está, ábralo desde el menú de inicio
y espere a que el icono de la ballena deje de moverse. Esto tarda uno o dos minutos la primera
vez del día.

```bash
python devops/pila.py up -d
```

Cuando termine, compruebe que los seis están en pie:

```bash
python devops/pila.py ps
```

Tienen que aparecer **seis** líneas, y las de `backend`, `db` y `redis` tienen que decir
`(healthy)`. Mientras alguna diga `(health: starting)`, todavía está arrancando: espere
veinte segundos y vuelva a preguntar.

Después abra <http://localhost:3000> en el navegador. Si carga el panel, está encendido.

> **La primera vez en una máquina nueva**, antes de lo anterior, hay un paso más que se hace
> **una sola vez** y que crea las contraseñas del sistema:
>
> ```bash
> python devops/pila.py iniciar
> ```

---

## 3. Apagar el sistema

```bash
python devops/pila.py down
```

**Sin `-v`.** Así se apaga y los datos se quedan. La próxima vez que lo encienda, todo estará
como lo dejó.

Si solo quiere apagarlo un momento y volver:

```bash
python devops/pila.py stop
python devops/pila.py start
```

---

## 4. Las cuentas para entrar

Son tres, una por papel. Están en <http://localhost:3000>.

| Correo | Qué es | Qué ve |
| :--- | :--- | :--- |
| `admin.ti@plurione.com` | Administrador de TI | Todo: cuentas, bitácora, derechos del titular |
| `lider.ventas@plurione.com` | Líder comercial | La cartera completa, las publicaciones, los informes |
| `asesor.comercial@plurione.com` | Asesor comercial | **Solo sus propios prospectos** |

Y cuatro asesores más de la demostración: `carlos.morales@`, `ana.ruiz@`,
`valeria.mendoza@` y `diego.herrera@`, todos `@plurione.com`.

**La contraseña de todas, en esta instalación de demostración, es:**

```
PluriOne2026!
```

> **Esto es una contraseña de desarrollo y está escrita a la vista a propósito**, porque esta
> instalación es para enseñar el sistema, no para datos de nadie. Si alguna vez este sistema
> pasa a usarse con datos reales, lo primero es cambiar las siete.

### Si una cuenta no entra

Lo más probable es que alguien la cambió o la desactivó. Se restablecen **todas** sin tocar
ningún prospecto, y la orden va en **una sola línea**:

```bash
python devops/pila.py exec -e SEED_ADMIN_PASSWORD=PluriOne2026! -e SEED_SALES_LEAD_PASSWORD=PluriOne2026! -e SEED_EXECUTIVE_PASSWORD=PluriOne2026! -e SEED_ASESOR_PASSWORD=PluriOne2026! backend python /app/scripts/seed_data.py --solo-usuarios
```

Al terminar tiene que decir, en las siete líneas, **`contraseña: variable de entorno`**, y
abajo «No se tocó ningún otro dato».

> ### ⚠ Los cuatro `-e` no son adorno
>
> La pila arranca en modo `production`, y ahí el programa **se niega a sembrar una contraseña
> predecible**: si no se le dice cuál quiere, genera una **al azar por cuenta** y la enseña una
> sola vez. Eso está bien hecho —es lo que protege una instalación de verdad—, pero si se
> ejecuta la orden **sin** los cuatro `-e`, el resultado es siete cuentas con contraseñas
> aleatorias que pasan por la pantalla y se pierden, y nadie entra con `PluriOne2026!`.
>
> **Si ya le pasó:** no es grave. Vuelva a ejecutar la orden de arriba, **esta vez completa**.
> Las contraseñas se restablecen y no se pierde ningún dato.

---

## 5. La dirección pública (el túnel)

La página que rellena un interesado se puede abrir a internet por un rato. Mientras no esté
encendido el túnel, esa página **solo funciona en esta máquina**, y eso es lo normal.

> ### Lo que hay que saber antes de nada
>
> **La dirección pública cambia cada vez que se enciende el túnel.** Es prestada y gratuita,
> del estilo `https://algo-algo-algo.trycloudflare.com`. Al apagarla y volver a encenderla
> sale **otra distinta**, y la anterior deja de llevar a ninguna parte.
>
> **Consecuencia:** un post ya publicado en LinkedIn con una dirección vieja tiene un enlace
> muerto. El post sigue ahí; el enlace no lleva a nada.

### Encenderlo

Hacen falta **dos ventanas de órdenes**. La primera para todo; la segunda se queda abierta
con el túnel dentro.

**Ventana 2** (y no la cierre):

```bash
C:\Users\<usted>\cloudflared.exe tunnel --url http://127.0.0.1:8080
```

Al rato escribe una dirección en un recuadro. **Cópiela.**

**Luego**, abra con el Bloc de notas `C:\Users\<usted>\.plurione\pila.env` y deje una línea
así, pegando su dirección y **con `/interes` al final**:

```
PUBLICACIONES_URL_BASE=https://algo-algo-algo.trycloudflare.com/interes
```

Si la línea ya existe de otra vez, sustitúyala. Guarde.

**Ventana 1**, para que el sistema lea la dirección nueva:

```bash
python devops/pila.py up -d backend
```

Espere a que diga `(healthy)` —unos veinte segundos— y compruebe que quedó bien, pegando su
dirección:

```bash
python scripts/comprobar_puerta_publica.py https://algo-algo-algo.trycloudflare.com
```

Tiene que terminar diciendo que publica 5 rutas y niega las 25 comprobadas. **Si dice
cualquier otra cosa, apague el túnel y avise**: no lo deje encendido «a ver si se arregla».

### Reiniciarlo

Es lo mismo que encenderlo, con un paso previo: en la ventana 2, **`Ctrl+C`**. Y después los
pasos de arriba otra vez, **incluido el de pegar la dirección nueva en `pila.env`**, que es el
que se olvida.

### Apagarlo

En la ventana 2: **`Ctrl+C`**. Desde ese momento ya no se llega desde internet. Los datos que
entraron se quedan en el panel.

### Si se perdió la dirección pública

Pasa, y no es grave. Puede ser por tres motivos, y los tres se arreglan igual:

* se cerró la ventana del túnel;
* se reinició la máquina;
* lleva horas abierta y Cloudflare la soltó.

**Qué hacer:** reiniciar el túnel con los pasos de arriba. **Qué NO hacer:** buscar la
dirección vieja; no vuelve.

**Y una cosa más, importante si había un post publicado:** el panel lo detecta y lo dice. En
la pestaña «Publicaciones» aparecen marcados los enlaces que ya no llevan aquí, con un aviso
de que la dirección configurada dejó de responder. Hay que volver a publicar el post con la
dirección nueva, o aceptar que ese post ya no trae a nadie.

El detalle completo, con lo que conviene revisar la primera semana y qué hacer si llega una
oleada de visitas, está en [la guía del túnel público](Guia_del_Tunel_Publico.md).

---

## 6. Dejar la demostración limpia otra vez

Después de un ensayo quedan dentro los prospectos de prueba. Para volver al punto de partida
—cuentas, publicaciones de ejemplo y perfiles ya recibidos—:

```bash
python scripts/preparar_prueba_con_personas.py --force
```

Hace copia de la base antes de vaciarla e imprime al final los enlaces y las cuentas. **Borra
los prospectos de demostración**, así que no se usa sobre datos que interesen.

> Esto funciona sobre la instalación de desarrollo. La pila de Docker arranca en modo
> `production`, y ahí el sembrado de demostración **está prohibido a propósito**: lo único
> que se puede hacer es restablecer las cuentas (§4).

---

## 7. Restaurar una copia de seguridad

### Hacer una copia ahora

```bash
python devops/pila.py --profile respaldo run --rm respaldo
```

Deja un archivo con la fecha en el volumen de copias, comprueba que **se puede leer** y
guarda su huella al lado. Una copia que no se puede leer no es una copia.

### Comprobar que las copias sirven

```bash
python devops/pila.py --profile respaldo run --rm prueba-de-restauracion
```

Restaura la copia más reciente en una base **desechable** y compara los recuentos tabla por
tabla contra la base real. Esto es lo que convierte «tenemos copias» en «tenemos copias que
sirven», y conviene correrlo de vez en cuando aunque no haya pasado nada.

### Restaurar de verdad

Esto **sobrescribe la base actual**. Antes de empezar, asegúrese de que es lo que quiere.

**Paso 1 — Ver qué copias hay y elegir una.**

```bash
python devops/pila.py --profile respaldo run --rm --entrypoint sh respaldo -c "ls -lh /respaldos"
```

Los nombres llevan la fecha y la hora en UTC, así:
`lead_scoring_db_20260909T031500Z.dump`. **Elija a mano.** No hay «la más reciente»
automática, y es deliberado: la más reciente puede ser justo la que ya contiene el borrado
del que quiere volver.

**Paso 2 — Apagar lo que escribe.**

```bash
python devops/pila.py stop backend frontend
```

**Paso 3 — Restaurar**, poniendo el nombre exacto de su archivo:

```bash
python devops/pila.py --profile respaldo run --rm -e VOLCADO=/respaldos/lead_scoring_db_20260909T031500Z.dump -e CONFIRMO_SOBRESCRIBIR=si restaurar
```

Pide el nombre exacto y la confirmación escrita a propósito. Si falla a mitad, la base se
queda **como estaba** en lugar de convertirse en una mezcla de dos versiones.

**Paso 4 — Comprobar que el esquema es el que el programa espera.**

```bash
python devops/pila.py run --rm migrate alembic current
```

**Paso 5 — Volver a encender.**

```bash
python devops/pila.py start backend frontend
```

> **Dos límites, escritos para que nadie se lleve una sorpresa.** Las copias viven en un
> volumen del **mismo disco**: protegen de un borrado o de una migración que salió mal, **no**
> de que el disco se muera. Y la prueba demuestra que el archivo sirve, no que se podría
> reconstruir el servicio entero en otra máquina.

---

## 8. Síntoma → qué mirar → qué hacer

| Síntoma | Qué mirar | Qué hacer |
| :--- | :--- | :--- |
| **Nada carga.** <http://localhost:3000> no responde | ¿Está abierto Docker Desktop? El icono de la ballena | Abrir Docker Desktop, esperar a que pare de moverse y `python devops/pila.py up -d` |
| **El panel carga pero dice que no hay conexión** al entrar | `python devops/pila.py ps` — ¿dice `backend` `(healthy)`? | Si dice `(health: starting)`, esperar 20 s. Si no aparece o dice `Exited`, ver `python devops/pila.py logs --tail 50 backend` |
| **Un contenedor dice `Exited`** | `python devops/pila.py logs --tail 50 <nombre>` | Casi siempre es la base aún arrancando: `python devops/pila.py up -d` otra vez. Si insiste, guardar esas líneas y avisar |
| **Dice que falta `SECRET_KEY` o `POSTGRES_PASSWORD`** | ¿Existe `C:\Users\<usted>\.plurione\pila.env`? | `python devops/pila.py iniciar`. Si el archivo ya existía, abrirlo y comprobar que esas dos líneas están y tienen valor |
| **Dice que hay un `.env` en el repositorio** | Un archivo `.env` dentro de la carpeta del proyecto o de `devops/` | Moverlo fuera o borrarlo. El sistema se niega por seguridad, no por capricho |
| **No entra ninguna cuenta** | ¿La contraseña es `PluriOne2026!`? | §4, la orden larga **con los cuatro `-e`**. Sin ellos las deja aleatorias |
| **Entra el líder pero no ve prospectos** | ¿Se sembró la base? | `python scripts/preparar_prueba_con_personas.py --force` (§6) |
| **El asesor ve menos prospectos de los que debería** | Que no haya un nombre escrito en el buscador ni un cuadrante marcado | Vaciar el buscador. Si estaba vacío y sigue pasando, avisar: eso sí es un fallo |
| **El enlace del post no lleva a ninguna parte** | ¿Está encendido el túnel? ¿Es la dirección de ahora? | §5: reiniciar el túnel, pegar la dirección **nueva** en `pila.env` y volver a publicar el post |
| **La página pública da «no disponible»** | ¿La publicación está activa y dentro de fecha? | Activarla desde el panel, pestaña «Publicaciones» |
| **La página pública dice «demasiadas solicitudes»** | Son diez envíos por hora y por IP | Esperar, o levantar el límite para una sesión larga con `INTERES_LIMITE_POR_IP=60/hour` en `pila.env` y reiniciar el backend |
| **El código QR no lo lee el teléfono** | Que la pantalla no esté muy oscura y el código no esté muy pequeño | Acercar la cámara. Si es un QR impreso con una dirección vieja, está muerto: §5 |
| **El asesor no ve la tarea del prospecto nuevo en «Hoy»** | Nada: **es lo normal** | Las tareas las crea una pasada que corre **una vez al día**. No es un fallo; está explicado en el guion de la prueba con personas |
| **El contador «sin asesor» dice 0 y sí llegó alguien** | Nada: **es lo normal** desde el capítulo 46 | El prospecto ya se repartió solo. Ese contador cuenta lo que el reparto **no pudo** colocar |
| **La demostración va lentísima la primera vez** | Es el modelo cargándose en memoria | Hacer un envío de prueba **antes** de empezar. Está en el paso 0 del guion cronometrado |
| **Después de cambiar algo, la pantalla sigue igual** | La imagen vieja arranca igual de bien que la nueva | `python devops/pila.py up -d --build` — con `--build` |
| **Se borró algo que no se debía** | Qué copias hay | §7, restaurar de verdad. **No** siga usando el sistema mientras decide: cada minuto es una copia más reciente con el borrado dentro |

---

## 9. Si nada de esto sirve

Antes de pedir ayuda, recoja estas cuatro cosas. Con ellas, quien lo mire sabrá en un minuto
lo que sin ellas tarda una hora:

```bash
python devops/pila.py ps > estado.txt
python devops/pila.py logs --tail 200 backend > registro_backend.txt
python devops/pila.py logs --tail 100 frontend > registro_frontend.txt
python devops/pila.py --comprobar > comprobaciones.txt
```

Y apunte **qué estaba haciendo exactamente** cuando falló, y si antes funcionaba.

> **Lo que este documento no cubre, por escrito.** La instalación en otra máquina —la PC
> servidora— no está hecha ni ensayada. Lo que hay descrito aquí es esta instalación, en este
> equipo. Y el sistema está **congelado desde el 6 de octubre de 2026**: solo se corrigen
> fallos que impidan levantarlo o enseñarlo. Lo que falta, y por qué falta, está en
> [Congelación y trabajo futuro](Congelacion_y_Trabajo_Futuro.md).
