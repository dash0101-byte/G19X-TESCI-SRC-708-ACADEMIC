# Guía del túnel público — encender y apagar la página de interés

**Para quién es esto.** Para quien tenga que poner la página de interés a disposición de
gente de fuera y apagarla después, sin programar nada. Todo son órdenes que se copian y se
pegan, y hay una comprobación automática que dice si quedó bien.

**Qué hace y qué no hace.** Enciende **una sola página**: la que rellena un interesado
cuando pulsa el enlace de un post. El panel, la base de datos y todo lo demás siguen sin
salir de esta máquina. Está comprobado ruta por ruta y se puede volver a comprobar en un
minuto (§4).

> ## ⚠ Lo primero, porque cambia cómo se usa
>
> **La dirección pública cambia cada vez que se arranca el túnel.** Es una dirección
> prestada y gratuita, del estilo `https://energy-compare-clearing-excerpt.trycloudflare.com`,
> y al apagar y volver a encender sale otra distinta.
>
> **Consecuencia práctica:** un post publicado en LinkedIn con una de estas direcciones
> **deja de funcionar en cuanto se reinicia el túnel**. El post sigue ahí, el enlace ya no
> lleva a ninguna parte, y quien lo pulse no ve nada.
>
> Por eso: esto sirve para **enseñar la página, probarla con personas y ver la tarjeta de
> vista previa en una red de verdad**. La difusión en serio —publicar el post y dejarlo
> semanas— espera a un dominio propio (§6). El sistema avisa cuando esto pasa: la pantalla
> de Publicaciones marca los enlaces que ya no llevan aquí, y dice si la dirección
> configurada dejó de responder.

---

## 1. Una sola vez: dejar el programa del túnel en la máquina

1. Descargue `cloudflared` para Windows desde la página oficial de Cloudflare:
   <https://github.com/cloudflare/cloudflared/releases/latest> → el archivo
   **`cloudflared-windows-amd64.exe`**.
2. Guárdelo donde lo vaya a encontrar, por ejemplo `C:\Users\<usted>\cloudflared.exe`.
3. Compruebe que funciona. Abra una ventana de órdenes y escriba:

```bash
C:\Users\<usted>\cloudflared.exe --version
```

Tiene que responder algo como `cloudflared version 2026.9.3`. Si responde eso, ya está.

**No hace falta cuenta, ni tarjeta, ni configurar el router.** El túnel sale **desde** esta
máquina hacia fuera; nadie entra por el router.

---

## 2. Encender (cinco pasos, siempre los mismos)

Hacen falta **dos ventanas de órdenes**: una para el túnel, que se queda abierta, y otra
para lo demás.

### Paso 1 — Levantar el sistema

En la ventana 1:

```bash
python devops/pila.py up -d
```

Espere a que termine. Si alguna vez falla, `python devops/pila.py ps` dice qué pasó.

### Paso 2 — Abrir el túnel

En la ventana 2, **y esta ventana se queda abierta todo el rato**:

```bash
C:\Users\<usted>\cloudflared.exe tunnel --url http://127.0.0.1:8080
```

A los pocos segundos escribe un recuadro con la dirección pública. Busque la línea que
contiene `trycloudflare.com`:

```
+------------------------------------------------------------+
|  https://energy-compare-clearing-excerpt.trycloudflare.com  |
+------------------------------------------------------------+
```

**Copie esa dirección.** Es la de hoy; mañana será otra.

> **Si se queda atascado repitiendo «Retrying connection»**, su red está bloqueando el
> protocolo que usa por defecto. Párelo con `Ctrl+C` y arránquelo así:
>
> ```bash
> C:\Users\<usted>\cloudflared.exe tunnel --url http://127.0.0.1:8080 --protocol http2
> ```

### Paso 3 — Decirle al sistema cuál es su dirección

Abra con el Bloc de notas el archivo `C:\Users\<usted>\.plurione\pila.env` y deje una línea
así, **con `/interes` al final** y pegando la dirección del paso 2:

```
PUBLICACIONES_URL_BASE=https://energy-compare-clearing-excerpt.trycloudflare.com/interes
```

Si la línea ya existe de otra vez, sustitúyala. Guarde el archivo.

> **El `/interes` del final no es opcional.** Sin él, el enlace que se copia para LinkedIn
> lleva a la pantalla de acceso en lugar de al formulario, y eso no se nota escribiendo la
> dirección a mano: solo siguiendo el enlace ya pegado en el post.

### Paso 4 — Reiniciar el servidor para que la lea

En la ventana 1:

```bash
python devops/pila.py up -d backend
```

**Y espere a que diga `healthy`** antes de seguir. Se mira así:

```bash
docker ps --filter name=plurione_leadscoring_backend --format "{{.Status}}"
```

Tiene que poner `Up ... (healthy)`. Mientras ponga `(health: starting)`, el servidor todavía
está arrancando y la comprobación del paso 5 dará **502** en tres rutas: no es un fallo, es
que preguntó demasiado pronto. Son unos veinte segundos.

### Paso 5 — Comprobar que quedó bien

En la ventana 1, pegando **su** dirección:

```bash
python scripts/comprobar_puerta_publica.py https://energy-compare-clearing-excerpt.trycloudflare.com
```

Tiene que terminar con:

```
La puerta publica 5 rutas y niega las 25 comprobadas.
Desde fuera, el panel y la API de gestion no existen.
```

**Si sale cualquier otra cosa, apague el túnel (§3) y avise.** No lo deje encendido «a ver
si se arregla»: mientras esté encendido, lo que publique está publicado.

---

## 3. Apagar

1. En la ventana del túnel (la 2): **`Ctrl+C`**. Con eso ya no se llega desde internet.
2. Si además quiere parar el sistema, en la ventana 1: `python devops/pila.py down`.

Apagar el túnel es instantáneo y no rompe nada: los datos que entraron siguen en el panel.

---

## 4. Qué revisar la primera semana

Una vez al día, y no lleva más de dos minutos:

| Qué mirar | Dónde | Qué quiere decir si está mal |
| :--- | :--- | :--- |
| **La página abre desde un teléfono con datos móviles**, no desde el wifi de la oficina | El enlace, en el móvil | Desde el wifi se puede llegar por otro camino y parecer que funciona cuando no |
| **La comprobación sigue en verde** | `python scripts/comprobar_puerta_publica.py <su dirección>` | Algo quedó publicado que no debía. Apague el túnel y avise |
| **La pantalla de Publicaciones no tiene avisos rojos** | El panel → Publicaciones | O la dirección dejó de responder, o hay enlaces repartidos que ya no llevan aquí |
| **Cuántos envíos entraron** | El panel → Prospectos, fuente «LinkedIn» | Si entran muchos y ninguno tiene sentido, mire §5 |
| **La tarjeta de vista previa sale bien** | Pegue el enlace en un chat de WhatsApp consigo mismo | Si sale sin imagen o sin título, el post en LinkedIn saldrá igual de soso |

Y una vez, el primer día: **pegue el enlace en LinkedIn sin publicar** y mire la tarjeta que
compone. Es lo único que no se puede comprobar de ninguna otra forma, y es media razón de
que exista este túnel.

---

## 5. Si llega una oleada

Señales: muchos envíos seguidos, nombres sin sentido, o el mismo texto repetido.

**Primero, lo que ya está puesto y no hay que hacer:**

* Cada visitante puede enviar **5 formularios por hora** y cada publicación acepta **60 por
  hora** en total; pasado eso, se responde «inténtalo más tarde».
* La propia puerta corta a **60 peticiones por minuto** por visitante antes de que el
  servidor trabaje.
* Hay un **campo trampa**: un robot que rellena todo el formulario recibe el mismo «gracias»
  que una persona y **no se registra nada**. No se le dice que fue descartado.
* El formulario no tiene ni un campo de texto libre: todo son listas cerradas. No se puede
  meter un enlace ni un mensaje.

**Lo que hay que hacer, en este orden:**

1. **Apagar el túnel** (`Ctrl+C` en la ventana 2). Es instantáneo, no hay que reconstruir
   nada y corta el problema entero. Todo lo demás se puede hacer con calma después.
2. Mirar en el panel qué entró y borrar lo que sea basura.
3. Si hace falta volver a encender, apretar los límites antes. En `pila.env`:

   ```
   INTERES_LIMITE_POR_IP=2/hour
   INTERES_LIMITE_POR_PUBLICACION=20/hour
   ```

   y reiniciar con `python devops/pila.py up -d backend`.
4. Al volver a encender, la dirección será otra. Eso, aquí, juega a favor: la anterior deja
   de existir para quien la tuviera.

---

## 6. Cuando haya dominio propio

Lo que hay hoy es la versión de prueba del mismo mecanismo. Con un dominio, **cambian tres
cosas y ninguna es código**:

1. El túnel pasa a ser «con nombre»: se crea una vez, se le asigna el dominio, y **la
   dirección deja de cambiar**.
2. `PUBLICACIONES_URL_BASE` se escribe **una vez** y ya no se vuelve a tocar. Los pasos 2, 3
   y 4 de §2 desaparecen: el túnel arranca solo como servicio de Windows.
3. Los enlaces de los posts dejan de caducar, y con eso la difusión en redes deja de tener
   fecha de caducidad.

Qué archivo se toca para eso —y cuáles no— está en [**Poner la dirección de la empresa**](Poner_la_Direccion_de_la_Empresa.md), escrito para quien lo vaya a hacer sin leer el código.

Qué haría falta y qué cuesta está en el Reporte 32 (§34.7). En resumen: un dominio (unos
**10-15 USD al año**), la cuenta gratuita de Cloudflare, y una tarde de configuración. El
certificado y el plan que hace falta son gratuitos.

---

## 7. Preguntas que van a surgir

**¿Esto abre mi router o mi wifi?** No. El túnel sale desde esta máquina hacia Cloudflare,
como cuando el navegador abre una página. No hay ningún puerto abierto hacia dentro.

**¿Pueden llegar al panel?** No. Desde fuera solo existen cinco direcciones, todas de la
página del formulario. El panel, la API de gestión, su documentación y las métricas
responden «no existe». Está comprobado una por una y se puede repetir (§2, paso 5).

**¿Y si alguien adivina el enlace de una publicación?** Los enlaces llevan 22 caracteres al
azar. Aun acertando uno, lo que se ve es el formulario público: nada de la cartera.

**¿Se queda encendido si cierro la ventana?** No. Cerrar la ventana 2 apaga el túnel. Eso es
a propósito: no hay forma de dejárselo encendido sin darse cuenta.

**¿Qué pasa si se va la luz?** Al volver hay que repetir §2 entero, y la dirección será
otra. Los datos que ya entraron no se pierden.
