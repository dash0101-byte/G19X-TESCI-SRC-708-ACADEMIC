# Poner la dirección de la empresa — qué archivo se toca y cuál no

**Para quién es esto.** Para quien vaya a publicar este sistema bajo una dirección de la
empresa: un dominio propio, un subdominio, o un túnel con nombre. No hace falta leer el
código ni entenderlo.

**La idea entera, en una línea:** se cambia **una variable** en **un archivo**, y ese archivo
**no está dentro del proyecto**.

> No es una simplificación para este documento. Está escrito así a propósito desde el
> capítulo 34: la dirección pública **no tiene ninguna otra copia** en el árbol. La tarjeta
> de vista previa, su imagen, el texto que se copia para cada red y el enlace que enseña el
> panel salen todos de la misma función, que lee ese valor. Hay una prueba,
> `backend/tests/test_puerta_estrecha.py`, que recorre todo el repositorio buscando
> direcciones escritas a mano y falla si aparece una. Si alguien le dice que hay que tocar
> algo más, está mirando una versión distinta de este sistema.

---

## 1. El archivo

```
C:\Users\<el usuario del servidor>\.plurione\pila.env
```

En Linux o macOS, `~/.plurione/pila.env`.

Se crea una sola vez, y lo crea el propio lanzador:

```bash
python devops/pila.py iniciar
```

Eso lo escribe con los dos secretos obligatorios ya generados y con permisos solo para ese
usuario. Después se edita con el Bloc de notas como cualquier archivo de texto.

**Por qué vive fuera de la carpeta del proyecto.** Porque dentro viajaría en cada copia de la
carpeta, en cada respaldo y en cada envío por correo, aunque Git lo ignore. En la Fase 0 hubo
que rotar una clave por eso. El lanzador **se niega a arrancar** si encuentra un `.env` dentro
del árbol: no es un aviso, es una parada.

---

## 2. La variable

Al final del archivo, escriba la línea con la dirección de la empresa:

```
PUBLICACIONES_URL_BASE=https://plurione.com/interes
```

**En un archivo recién creado esa línea no está, y es normal:** el valor de fábrica
—`http://localhost:3000/interes`— lo pone el compose, no el archivo de entorno, así que lo
que hay que hacer es **añadirla**. Si ya estuviera escrita, se cambia en su sitio y no se
duplica: con dos líneas iguales manda la última, y eso es muy difícil de ver leyendo.

Tres cosas, y las tres se han roto alguna vez:

| Regla | Si no se cumple |
| :--- | :--- |
| **Termina en `/interes`** | El enlace que se pega en LinkedIn lleva a la **pantalla de acceso**, no al formulario. No se nota escribiendo la dirección a mano: solo siguiendo el enlace ya pegado en el post |
| **Sin barra al final, sin `?` ni `#`** | El servidor **no arranca** y dice por qué. Es deliberado: un valor mal escrito se descubre al encender, no al ver el post publicado |
| **Es la dirección pública, no la de desarrollo** | El valor de fábrica es `http://localhost:3000/interes`, que solo funciona en la máquina donde corre |

---

## 3. A qué puerta tiene que apuntar el dominio

El sistema abre tres puertas en la máquina y **solo una** sale a internet:

| Puerta | Qué es | ¿Sale a internet? |
| :---: | :--- | :--- |
| **8080** | La página pública del formulario | **Sí. Es la única.** El dominio apunta aquí |
| 3000 | El panel de la empresa | No. Solo desde la red interna |
| 8000 | La API de gestión | No. Solo desde la máquina |

Quien configure el proxy inverso, el balanceador o el túnel con nombre tiene que mandar el
tráfico a **`127.0.0.1:8080`**. Apuntar al 3000 publicaría el panel entero en internet.

Esa puerta está comprobada ruta por ruta y se puede volver a comprobar en un minuto (§5).

---

## 4. Las otras variables, solo si cambia la forma del despliegue

En el mismo archivo, y ninguna es obligatoria para que la dirección funcione:

| Variable | Cuándo se cambia | A qué |
| :--- | :--- | :--- |
| `REFRESH_COOKIE_SECURE` | En cuanto el sitio se sirva por **HTTPS** | `true`. Mientras sea HTTP tiene que quedarse en `false`, o el navegador descarta la cookie y nadie mantiene la sesión |
| `COMPROBAR_DIRECCION_PUBLICA` | Cuando ya hay dirección pública de verdad | `true`. El sistema sale a internet a confirmar que su propia dirección responde —como mucho una vez cada dos minutos, cuando alguien abre la pantalla de Publicaciones— y avisa ahí si deja de responder |
| `CORS_ORIGINS` | **Solo** si el panel se sirve desde otro dominio que la API | La lista exacta, en formato JSON: `CORS_ORIGINS=["https://panel.plurione.com"]`. Si los sirve el mismo nginx de esta pila, se deja **vacío** |
| `TRUST_PROXY_HEADERS` | Si delante hay un proxy de confianza que reescribe `X-Forwarded-For` | `true`. Expuesto directamente tiene que ser `false`, o los topes por IP no se aplican nunca |

De las cuatro, `REFRESH_COOKIE_SECURE`, `CORS_ORIGINS` y `TRUST_PROXY_HEADERS` **sí vienen
escritas** en el archivo recién creado, con su valor de fábrica; `COMPROBAR_DIRECCION_PUBLICA`
**no**, igual que la variable del apartado 2, y se añade del mismo modo.

El comodín `*` en `CORS_ORIGINS` no se admite: el servidor aborta el arranque si lo encuentra.

---

## 5. Aplicar el cambio y comprobar que quedó bien

```bash
python devops/pila.py up -d backend
```

Espere a que diga `healthy` antes de comprobar nada:

```bash
docker ps --filter name=plurione_leadscoring_backend --format "{{.Status}}"
```

Mientras ponga `(health: starting)` el servidor sigue arrancando y la comprobación dará
errores que no son reales. Son unos veinte segundos.

Después, con la dirección de la empresa:

```bash
python scripts/comprobar_puerta_publica.py https://plurione.com
```

Tiene que terminar exactamente con:

```
La puerta publica 5 rutas y niega las 25 comprobadas.
Desde fuera, el panel y la API de gestion no existen.
```

**Si sale cualquier otra cosa, no lo deje publicado.** Quite el dominio y avise.

---

## 6. Lo que hay que hacer después, en el panel

Cambiar la dirección **no arregla los enlaces que ya se repartieron**. Un post publicado
antes del cambio lleva dentro la dirección vieja, y quien lo pulse no llega a ninguna parte.

El sistema lo sabe y lo dice solo: cada publicación guarda bajo qué dirección se activó, y la
pantalla de **Publicaciones** marca con un aviso las que repartieron un enlace que ya no lleva
aquí. En cada una:

1. Copie el enlace nuevo que enseña la ficha —ese ya es el bueno—.
2. Edite el post en la red donde esté, o publíquelo de nuevo.

Las publicaciones que se activen **a partir de ahora** quedan con la dirección nueva y no
vuelven a marcarse.

---

## 7. Lo que no se toca

Nada de esto hay que editar para cambiar la dirección, y editarlo rompe cosas:

| Archivo | Por qué no |
| :--- | :--- |
| `devops/.env.example` | Es la **plantilla** del archivo del §1, no el archivo. Cambiarlo no afecta a nada que esté corriendo |
| `devops/docker-compose.yml` | Las variables entran desde el archivo del §1; escribirlas aquí las mete en el repositorio |
| `frontend/nginx.conf`, `frontend/puerta-publica.conf` | Son la puerta estrecha: qué rutas existen desde fuera y cuáles no. Tocarlas es decidir qué se publica en internet, y hay un control del CI que las vigila |
| Cualquier archivo de `backend/`, `frontend/src/` o `ml_pipeline/` | No hay ninguna dirección escrita a mano en el código, y hay una prueba que lo comprueba |
| Un `.env` dentro de la carpeta del proyecto | El lanzador **se niega a arrancar** si lo encuentra |

---

## 8. Resumen

| Quiero… | Toco… |
| :--- | :--- |
| Que los enlaces lleven a mi dominio | `PUBLICACIONES_URL_BASE` en `~/.plurione/pila.env`, terminado en `/interes` |
| Que el dominio llegue al sitio | El proxy o el túnel, apuntando a `127.0.0.1:**8080**` |
| Servir por HTTPS | `REFRESH_COOKIE_SECURE=true` en el mismo archivo |
| Que el panel avise si la dirección se cae | `COMPROBAR_DIRECCION_PUBLICA=true` |
| Que el cambio surta efecto | `python devops/pila.py up -d backend` |
| Saber si quedó bien | `python scripts/comprobar_puerta_publica.py <mi dirección>` |

---

**Documentos relacionados.** El túnel de prueba gratuito —y qué cambia al pasar a uno con
nombre— está en [`Guia_del_Tunel_Publico.md`](Guia_del_Tunel_Publico.md). Arrancar, parar,
respaldos y qué hacer cuando algo falla, en [`Si_Algo_Falla.md`](Si_Algo_Falla.md).
