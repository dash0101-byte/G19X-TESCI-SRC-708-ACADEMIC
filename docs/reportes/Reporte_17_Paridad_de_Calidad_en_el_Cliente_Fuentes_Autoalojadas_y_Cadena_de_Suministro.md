# Capítulo 17: Paridad de Calidad en el Cliente — Fuentes Autoalojadas y Cadena de Suministro

## 17.1. Por qué existe esta fase

Al terminar el capítulo 16 el backend tenía 536 pruebas, 92 % de cobertura, análisis
estático con `ruff`, auditoría de dependencias con `pip-audit` y diecinueve guardas de
regresión en el pipeline. El cliente —que es la mitad del sistema que la gente usa de
verdad— tenía **cero pruebas y cero análisis estático**.

Esa asimetría no es una cuestión de gusto. Significa que la mitad del código donde ocurren
la sesión, la autorización visible, el simulador y todos los formularios cambiaba sin que
nada la mirase.

| Hallazgo | Enunciado | Naturaleza |
| :--- | :--- | :--- |
| **N-9** | El cliente no tiene pruebas | Ausencia total, no un fallo concreto |
| **N-7** | La página pide fuentes a un tercero que su propia CSP prohíbe | Una contradicción que el navegador resuelve en silencio |
| **N-10** | Las dependencias del cliente y las imágenes no se auditan | Una superficie que nadie mide |
| **N-17** | El bundle que se despliega no es el que se prueba | Dos compilaciones que ambas terminan bien |

Los cuatro comparten la propiedad que ya define a este proyecto: **ninguno produce un
error**. La aplicación sin pruebas funciona. Las fuentes bloqueadas se sustituyen por las
del sistema y la página se ve, solo que distinta. Una dependencia vulnerable instala y
ejecuta igual. Y un bundle recompilado a última hora se sirve exactamente como el otro.

---

## 17.2. N-9 — Pruebas del cliente, empezando por donde no se ve

### La prioridad no fue la pantalla

Se empezó por `src/services/api.js`, el módulo de sesión, y no por los componentes. El
motivo: en un componente, un fallo se ve. En el módulo de sesión, no. Un refresco de más
solo multiplica peticiones contra el backend; una sesión que revive tras cerrarla tampoco
avisa de nada. Son defectos que llegan a producción y viven allí.

Las pruebas miran **las llamadas que se hacen**, no solo lo que devuelve la función. Cada
`it` reimporta el módulo con `vi.resetModules()`, porque el token vive en una variable de
módulo y sin eso la sesión de una prueba se filtraría a la siguiente.

La preparación común hace algo que conviene explicar:

```js
globalThis.fetch = vi.fn(async (url) => {
  throw new Error(`Petición no simulada en la prueba: ${url}`);
});
```

Dejar el `fetch` real disponible haría que una ruta sin simular saliera a la red de
verdad: la prueba pasaría en el portátil de quien tiene el backend levantado y fallaría en
el pipeline. Es la peor clase de prueba que existe.

### Primer defecto: cerrar sesión con el servidor caído dejaba la pantalla dentro

```js
export async function logout() {
  try {
    if (accessToken) { await fetch(`${API_BASE}/auth/logout`, ...); }
  } finally {
    clearSession();
  }
}
```

El `finally` limpiaba la sesión local, sí. Pero la excepción de red **seguía subiendo**, y
en `App.jsx`:

```js
const handleLogout = async () => {
  await logout();        // <- revienta aquí
  setUser(null);         // <- nunca se ejecuta
  ...
};
```

Resultado con el servidor caído: el token desaparecía por dentro y la pantalla se quedaba
dentro de la aplicación, con cada acción posterior fallando. Quien pulsa «salir» ha salido;
cerrar sesión no puede fallar hacia fuera. Se cambió el `finally` a secas por un `catch`
vacío con el motivo escrito.

### Segundo defecto: la sesión resucitaba después de cerrarla

La prueba se llamaba *«un refresco en vuelo no puede resucitar una sesión ya cerrada»* y
**pasaba**. Pero pasaba por casualidad, y verlo costó mirar dos veces.

La secuencia: una petición recibe 401 y arranca la renovación. Mientras esa renovación
sigue en el aire, la persona cierra sesión. La renovación termina después y escribe
`accessToken = data.access_token` sin mirar si esa sesión todavía existe.

En la primera versión de la prueba, el reintento posterior al refresco devolvía otro 401,
y `apiFetch` volvía a limpiarlo todo. El estado final era el correcto, así que la prueba
pasaba **sin haber comprobado nada**. Basta con que el reintento funcione —lo normal, si
el token nuevo es válido— para que la sesión vuelva a estar viva sin que nadie haya vuelto
a entrar.

Corregida la prueba para aislar el caso, el defecto apareció. La solución es un contador
de sesiones:

```js
let epocaDeSesion = 0;

function clearSession() {
  accessToken = null;
  currentUser = null;
  epocaDeSesion += 1;
  refreshPromise = null;
}
```

La renovación captura la época al empezar y descarta su resultado si cambió:

```js
if (epoca !== epocaDeSesion) return false;
accessToken = data.access_token;
```

### Tercer defecto: lo encontró la comprobación de que las pruebas no son vacías

Al reintroducir los defectos uno a uno para verificar que alguna prueba fallaba, quitar la
línea `refreshPromise = null` de `clearSession` **no hizo fallar nada**.

El detalle es fino. La promesa compartida se libera en un `setTimeout` que ahora solo
actúa si la sesión sigue siendo la misma. Si al cerrar sesión no se descarta a mano, ese
temporizador ya no la libera nunca —la época cambió—, y queda pegada una promesa ya
resuelta a `false`. A partir de ahí, **cada 401 la reutiliza y da por fallada la
renovación sin llegar a pedirla**: la sesión siguiente se cae a los cinco minutos, al
caducar su primer token, y no hay forma de seguir sin recargar la página.

La línea era correcta; lo que faltaba era la prueba que la sostuviera. Se escribió.

### El catálogo de rutas

Veintiún envoltorios de endpoint son veintiuna líneas que nadie vuelve a mirar, y en las
que un error —un plural de más, un `PUT` donde iba un `POST`— no se nota al escribirlas: la
llamada sale, el backend devuelve 404 o 405, y en pantalla aparece un mensaje genérico. Una
tabla `it.each` fija ese contrato en un solo sitio.

---

## 17.3. Los componentes con lógica

### El simulador: dos defectos, uno de ellos invisible por diseño

**Respuestas desordenadas.** El simulador espera 250 ms antes de pedir una inferencia, y
cancela el temporizador si algo cambia antes. Eso evita disparar una petición por cada
píxel del deslizador, pero **no ordena las respuestas**: cancela el temporizador, no la
petición que ya salió.

Dos inferencias en vuelo tardan cosas distintas —una genera la explicación por IA y la
otra no—, así que la vieja puede contestar después que la nueva. Cuando eso ocurría, en
pantalla quedaba la puntuación de una entrada que ya nadie tenía delante, sin ningún
síntoma. La prueba lo reprodujo: puntuación 99 en pantalla, llega la respuesta atrasada, y
la pantalla pasa a 11 con los controles diciendo otra cosa.

```js
const miTurno = ultimaPeticion.current + 1;
ultimaPeticion.current = miTurno;
...
if (ultimaPeticion.current !== miTurno) return;   // esta respuesta ya no manda
setResult(data);
```

**Fallos mudos.** El `catch` hacía `console.error(err)` y nada más. En pantalla seguía el
resultado de la entrada *anterior*, indistinguible de una evaluación recién hecha con los
controles actuales. Un simulador que miente en silencio es peor que uno roto: ahora hay un
aviso, y debajo dice de cuándo es la puntuación que se está viendo.

**Etiquetas sueltas.** Escribir la prueba de los desplegables reveló que sus `<label>` no
estaban asociados a ningún control: sin `htmlFor`, y el control fuera de la etiqueta. Un
lector de pantalla anunciaba «lista desplegable» sin decir de qué, y pulsar el texto no
llevaba el foco al campo. Las casillas de verificación sí funcionaban, porque su `input`
va dentro de la propia `label`.

Se arreglaron las cuatro del simulador. **Quedan unas 43 iguales** en `LeadDetailModal`,
`NewLeadModal`, `LoginScreen` y `AdminPanel`: están fuera del alcance que esta fase se
comprometió a cubrir y se dejan señaladas explícitamente, no arregladas en silencio ni
escondidas.

### La matriz de prospectos

Casi todo lo que hace es pintar. Sus pruebas fijan los tres estados excluyentes —cargando,
vacía, con filas—, el cuadrante que da color a cada fila, y algo que sí puede romperse sin
avisar: los botones de acción dentro de una fila que también es pulsable. Sin
`stopPropagation`, el clic sube a la fila y `onSelectLead` se llama dos veces, la segunda
con `false`, que reabre la ficha en lectura y pierde el modo edición.

Una prueba encontró que `Math.round(lead.conversion_probability * 100)` escribe `NaN%` si
el campo no llega. **El contrato del backend no lo permite** —`conversion_probability:
float`, no nulo, con defecto `0.0`—, así que no es un fallo alcanzable hoy. Se aplicó la
guarda igual, y se dice aquí lo que es: precaución, no corrección.

### El menú de la sesión

Aquí se cambia la contraseña propia, así que sus reglas importan más que su aspecto: que
la confirmación se compruebe **antes** de mandar nada —un dedazo al repetir no debe gastar
un intento contra el límite de tasa—, que los motivos de rechazo de la política lleguen
enteros y no solo el primero, y que el formulario no se pueda enviar dos veces mientras el
primer envío está en el aire. Las once pruebas pasaron a la primera: este componente ya
estaba bien.

---

## 17.4. N-9/17 — Análisis estático, y las veinte cosas que encontró de una vez

`eslint` con `eslint-plugin-react-hooks` señaló veinte problemas en la primera pasada. Dos
no eran estilo.

### Once hooks después de un `return`

```js
export default function LeadDetailModal({ lead: initialLead, ... }) {
  if (!initialLead) return null;      // <- antes de todos los hooks

  const [lead, setLead] = useState(initialLead);
  // ... diez `useState` más y un `useEffect`
```

Hoy no se dispara: `App.jsx` monta el modal con `{selectedLead && <LeadDetailModal .../>}`,
así que nunca llega nulo. Pero es un cartucho puesto. El día que algún camino renderizara
este componente con `lead={null}` estando ya montado, React contaría menos hooks que en el
render anterior, lanzaría **durante el render**, y sin ninguna frontera de error por encima
la aplicación entera se quedaría en blanco.

La comprobación bajó después de los hooks y el valor inicial se toma con `?.`.

### Dos listas de dependencias incompletas

`react-hooks/exhaustive-deps` señaló `App.jsx` y `ScoringSimulator.jsx`. Es exactamente la
familia del defecto de respuestas desordenadas que las pruebas acababan de encontrar: una
dependencia que falta no rompe la pantalla, deja el efecto leyendo un valor viejo. Se
cerró envolviendo los cargadores en `useCallback` con sus dependencias reales.

De paso apareció `totalLeads`: una variable de estado que se escribía en dos sitios y no se
leía en ninguno. Fuera.

### Una regla apagada, con el motivo escrito

`react-hooks/set-state-in-effect` señala cinco sitios: los tres cargadores de `App.jsx`, el
de `AdminPanel` y la sincronización de `lead` en `LeadDetailModal`. Ninguno es un error:
son la forma en que esta aplicación entera obtiene sus datos. Cumplirla de verdad significa
mover la carga fuera del render —una biblioteca de datos, o estado derivado en vez de
copiado—, que es un rediseño del flujo y no lo que esta fase se comprometió a hacer.

Se apagó **entera**, no se bajó a aviso, y el porqué está en `eslint.config.js`. Un aviso
permanente que nadie va a atender acaba enseñando a ignorar la salida del `linter`, y
entonces tampoco se ven los avisos que sí importan.

### El suelo de cobertura

Vive en `vite.config.js` y va justo por debajo de lo medido:

| Medida | Medido | Suelo |
| :--- | ---: | ---: |
| Sentencias | 95,06 % | 92 % |
| Ramas | 88,20 % | 86 % |
| Funciones | 97,50 % | 94 % |
| Líneas | 97,43 % | 94 % |

No en un número redondo y cómodo: un suelo del 80 % con la cobertura real en el 95 % deja
pasar una regresión de quince puntos sin decir nada, que es tanto como no tenerlo. Se mide
sobre los cuatro módulos con lógica; incluir las tarjetas de KPI o la barra de navegación
subiría el número y bajaría lo que significa.

---

## 17.5. N-7 — Una política de seguridad que la propia página contradecía

### El defecto

No era una CSP ausente. La CSP estaba, y era estricta:

```
style-src 'self' 'unsafe-inline'; font-src 'self' data:
```

Y `index.html` decía:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit...&family=Plus+Jakarta+Sans...&family=JetBrains+Mono..." rel="stylesheet">
```

`style-src 'self'` no admite `fonts.googleapis.com`. El navegador bloqueaba la hoja **sin
un error visible para nadie**, la aplicación caía a las fuentes del sistema, y el único
síntoma era que en producción se veía distinta que con `npm run dev` —donde no hay nginx,
ni CSP, y todo se ve bien—.

Al mirarlo de cerca había además un descuido de bulto: de las tres familias que se
descargaban, **dos no se usaban en ningún sitio**, y la que el CSS pedía de verdad para el
texto (`Inter`) no se descargaba nunca. La página informaba a un tercero de la IP, el
`User-Agent` y el momento exacto de cada visita, a cambio de nada.

### El arreglo

Los `.woff2` viajan en el bundle con huella en el nombre. Son fuentes **variables**: un
solo archivo cubre el rango 100–900, así que los seis pesos que usan los componentes no
cuestan seis descargas. Solo los subconjuntos `latin` y `latin-ext`; los acentos y la eñe
del castellano caen en `latin`, de modo que en la práctica se descargan 88 KB.

La política se apretó a `font-src 'self'`, sin `data:`. Con las fuentes autoalojadas ya no
hay ninguna incrustada: una política que permite más de lo que hace falta deja de servir
para detectar que algo cambió.

### La prueba que el enunciado pedía

«Verificar la CSP con una prueba que cargue la página servida por nginx». Se hizo en dos
mitades, y las dos hacen falta.

La **estática** (`src/pruebas/csp.test.js`) comprueba coherencia entre archivos: que
`index.html` no enlace ningún origen externo, que las familias que el CSS pide sean las
que `fuentes.css` declara, y —al revés— que no quede ninguna familia declarada que nadie
use. Esa última es la que habría cazado a Outfit y Plus Jakarta Sans.

La **viva** levanta la imagen del frontend, descarga la página y verifica que todo lo que
enlaza lo sirve ese mismo origen. Con un detalle que costó descubrir: el `try_files` de la
SPA devuelve `index.html` con **código 200** para cualquier ruta que no exista, así que
comprobar el código no basta. Se mira la firma `wOF2` de los primeros cuatro bytes.

```
=== 4. Las fuentes viajan en el bundle y las sirve nginx ===
  /assets/inter-latin-wght-normal-Dx4kXJAl.woff2 -> 200 font/woff2 48256
  /assets/jetbrains-mono-latin-wght-normal-B9CIFXIH.woff2 -> 200 font/woff2 40404
```

Y se comprobó que **detecta el defecto original**: reintroducidos los `<link>` a Google y
reconstruida la imagen, tanto el guion vivo como la prueba estática fallan.

Dos detalles de la implementación que evitan una guarda que falla sobre un árbol correcto:
se descartan los comentarios —que explican que antes había enlaces a Google y nombran el
dominio— y los `data:` —el favicon es un SVG en línea que lleva dentro
`xmlns='http://www.w3.org/2000/svg'`, un espacio de nombres XML que el navegador nunca
descarga—.

---

## 17.6. N-10 — Auditar antes de poner la puerta

### Las dependencias del cliente

Al instalar el utillaje de pruebas, `npm audit` señaló cinco avisos: dos críticos y uno
alto, en `vite`, `vitest`, `@vitest/mocker` y `esbuild`. Se cerraron subiendo a vite 8 y
vitest 5. La puerta queda en `--audit-level=high`: un aviso moderado en una herramienta
que solo corre en el portátil no justifica dejar el pipeline en rojo hasta que alguien
publique el arreglo, y un pipeline rojo por costumbre deja de informar de nada. El informe
completo, con los moderados y bajos, se publica como artefacto.

### Las imágenes: por qué `--ignore-unfixed` no es una concesión

Se escaneó **antes** de escribir la puerta, precisamente para no escribir una que no pueda
pasar. El resultado inicial:

| Imagen | ALTAS + CRÍTICAS | Con arreglo publicado |
| :--- | ---: | ---: |
| `plurione-backend` | 57 | 2 |
| `plurione-frontend` | 7 | 7 |

Cincuenta y cinco de los hallazgos del backend son paquetes del sistema base de Debian sin
parche disponible. Una puerta que está en rojo por causas que nadie de este proyecto puede
resolver **se acaba desactivando**, y entonces tampoco avisa de los dos que sí eran
accionables. Es la misma lección que la fase anterior aprendió con una guarda que fallaba
sobre un árbol correcto.

Los dos accionables del backend eran `msgpack 1.1.2` y `setuptools 70.3.0`. Ninguno estaba
en `pip list`: viven **vendorizados dentro de pip**, en `pip/_vendor`, para la caché HTTP
del propio instalador. La aplicación no los importa nunca. Actualizarlos habría sido
perseguir un síntoma; lo que sobra es el paquete entero:

```dockerfile
RUN rm -rf /opt/venv/lib/python3.13/site-packages/pip \
           /usr/local/lib/python3.13/site-packages/pip \
           ...
```

Sacar pip tiene además un valor propio: esta aplicación no instala nada en tiempo de
ejecución, y pip es una herramienta de descarga y ejecución de código arbitrario al
alcance de quien consiga ejecutar algo dentro del contenedor.

Los siete del frontend eran `libuuid 2.42.1-r0`, con Alpine ya en 2.42.3-r0: no había nada
que arreglar en este proyecto, solo recoger el parche con `apk --no-cache upgrade`. El
precio, dicho abiertamente: dos construcciones del mismo Dockerfile en fechas distintas ya
no dan la misma imagen. Se acepta a sabiendas, porque la alternativa —fijar cada paquete
del sistema— significa en la práctica no recoger el parche nunca.

Tras ambos cambios, y comprobado ejecutando:

| Imagen | ALTAS + CRÍTICAS con arreglo |
| :--- | ---: |
| `plurione-backend` | **0** |
| `plurione-frontend` | **0** |

Y el backend sin pip arranca, migra y responde: `/health` 200, `alembic upgrade head`
correcto, y `sklearn`, `xgboost`, `joblib`, `jose` y `bcrypt` importables.

> **Nota del capítulo 20.** `xgboost` ya no está en la imagen. Importable sí era; usado, no:
> ninguna línea del código lo importa y el modelo es un `GradientBoostingClassifier` de
> scikit-learn. En Linux arrastraba además `nvidia-nccl-cu13`, una biblioteca de
> comunicación entre GPU. Entre las dos, 310 MB de ruedas comprimidas en una imagen que no
> tiene GPU. Lo destapó el lock de la Fase 14, que por primera vez puso por escrito todo lo
> que se instalaba (§20.2).

### La lista de materiales

`syft` en formato CycloneDX, publicada como artefacto con 30 días de retención. Sirve para
lo que ningún escáner sirve: cuando mañana se publique un aviso sobre una biblioteca,
responder «está o no está, y en qué versión» sin reconstruir nada.

---

## 17.7. N-17 — Dos compilaciones que ambas terminan bien

El pipeline compilaba la SPA **dos veces**: una en el trabajo del cliente —la que pasa el
`linter`, las pruebas y el suelo de cobertura— y otra dentro del Dockerfile del frontend
—la que se publica—. Basta que `npm ci` resuelva algo distinto, o que el contexto de build
excluya un archivo que el otro sí veía, para que lo verificado y lo desplegado dejen de
coincidir. Y no habría ningún síntoma: las dos terminan con éxito.

El Dockerfile pasa a tener dos destinos:

```dockerfile
FROM servidor AS production-stage      # por defecto: compila (un portátil)
COPY --from=build-stage /app/dist /usr/share/nginx/html

FROM servidor AS desde-artefacto       # el pipeline: consume lo ya probado
COPY dist/ /usr/share/nginx/html/
RUN test -f /usr/share/nginx/html/index.html && test -d /usr/share/nginx/html/assets || ...
```

Esa comprobación final no sobra: `download-artifact` no se queja si el artefacto existe
pero viene vacío, y una imagen con un `dist/` vacío arranca sin protestar y devuelve 404
en cada ruta. Se probó construyendo con un `dist/` vacío: la construcción falla con el
mensaje puesto.

El paso posterior compara la huella SHA-256 del artefacto con la del archivo que sirve la
imagen. Medido:

```
  artefacto: 7b9c3d7ad5ef1a1cda5b7f6c2af47d80bdcb8509c75328d4fb4eba6c05604e07
  en imagen: 7b9c3d7ad5ef1a1cda5b7f6c2af47d80bdcb8509c75328d4fb4eba6c05604e07
```

El destino por defecto hace `rm -rf dist` antes de compilar, porque `dist/` ya no se
excluye del contexto de build y un `dist/` viejo del portátil no puede colarse.

---

## 17.8. Que nada de esto sea decorativo

### Que ninguna prueba es vacía

Se reintrodujo cada defecto de la fase, uno por uno, y se corrió **la suite entera** con
cada uno puesto:

| Defecto reintroducido | Fallos | Dónde |
| :--- | ---: | :--- |
| `logout` vuelve a propagar el fallo de red | 1 | `api.test.js` |
| Un refresco en vuelo resucita la sesión cerrada | 1 | `api.test.js` |
| Cerrar sesión no descarta la renovación en curso | 1 | `api.test.js` |
| Cada 401 abre su propio refresco | 1 | `api.test.js` |
| Un 401 ya no reintenta la petición | 4 | `api.test.js` |
| La probabilidad sin valor vuelve a escribir `NaN` | 1 | `LeadsTable.test.jsx` |
| Los botones de fila vuelven a disparar el clic de la fila | 1 | `LeadsTable.test.jsx` |
| La tabla enseña las filas viejas mientras carga | 1 | `LeadsTable.test.jsx` |
| Una respuesta vieja vuelve a pisar a la nueva | 1 | `ScoringSimulator.test.jsx` |
| El fallo de inferencia vuelve a la consola y no a la pantalla | 2 | `ScoringSimulator.test.jsx` |
| El simulador pide una inferencia por cada movimiento | 1 | `ScoringSimulator.test.jsx` |
| Las etiquetas del simulador se sueltan de sus campos | 1 | `ScoringSimulator.test.jsx` |
| La contraseña repetida deja de comprobarse | 1 | `SessionModal.test.jsx` |
| El botón de guardar deja de inhabilitarse | 1 | `SessionModal.test.jsx` |
| Las fuentes vuelven a pedirse a Google | 1 | `csp.test.js` |
| La política vuelve a admitir fuentes incrustadas | 1 | `csp.test.js` |

**20 fallos en total**, cada uno en el archivo que debe responder por él. Ninguna fuga
entre archivos.

Dos de las dieciséis mediciones no fallaron en la primera pasada. Una era un problema de
la propia medición —un ancla ambigua—. La otra, la renovación pegada tras cerrar sesión,
era un hueco real en la cobertura: el código estaba bien y no había prueba que lo
sostuviera. Se escribió.

### Las guardas del pipeline también se comprobaron, y ocho de dieciséis no servían

Se extrajeron las cuatro guardas nuevas del propio `ci.yml` —no copiadas a mano, que se
desincronizan— y se ejecutaron contra el árbol correcto y contra dieciséis defectos.

**Ocho no dispararon.** La causa principal es una variante nueva de un error que este
proyecto ya ha cometido tres veces:

> **La guarda se satisface a sí misma.** Cinco comprobaciones buscaban una cadena en
> `ci.yml`, y esa misma cadena está escrita en la línea `grep` de la propia guarda, que
> vive en ese archivo. Filtrar comentarios no ayuda: la orden no es un comentario.

Es la cuarta forma del mismo problema de fondo —la guarda encuentra su propio texto en vez
del hecho que vigila—, después del comentario que satisface la guarda (capítulos 14, 15 y
16), la línea del `import` (capítulo 16) y el «aparece alguna vez» (capítulo 16).

| Guarda | Por qué no servía |
| :--- | :--- |
| Trivy, `--exit-code`, `--ignore-unfixed`, syft, artefacto | Buscaban en `ci.yml` entero y encontraban su propia línea `grep` |
| El destino `desde-artefacto` y la huella del bundle | Lo mismo |
| Las fuentes locales en `fuentes.css` | «Alguna vez»: con dos familias, quitarle el archivo a una dejaba la otra |
| `dist/` fuera del repositorio | Miraba que la regla siguiera en `.gitignore`, y una negación posterior la anula sin borrarla |

El arreglo de las siete primeras es acotar la búsqueda al **bloque del trabajo** donde la
orden debe estar, lo cual además es más exigente: no basta con que la cadena exista en
alguna parte del pipeline.

Corregidas, quedaba una más. Sustituir la orden de `syft` por un `true` seguía sin
disparar, porque la guarda buscaba `syft` y ese texto está en el **nombre del paso**:
`- name: Lista de materiales de las imagenes (syft, CycloneDX)`. Pasa a exigir
`anchore/syft` y el formato `cyclonedx-json`.

Resultado final: **las dieciséis reintroducciones disparan, y el árbol correcto pasa las
cuatro guardas.**

### Evidencia

| Medida | Antes de la fase | Después |
| :--- | :--- | :--- |
| Pruebas del backend | 536 | 536 |
| Pruebas del cliente | **0** | **113** |
| Cobertura del cliente | — | 95 % sentencias / 88 % ramas / 97 % funciones |
| `ruff check .` | Limpio | Limpio |
| `eslint .` | *no existía* | Limpio |
| `npm audit --audit-level=high` | *no existía* | 0 vulnerabilidades |
| Trivy (con arreglo publicado) | 64 ALTAS/CRÍTICAS | **0** |
| Trabajos de CI / pasos | 10 / 75 | 10 / **94** |
| Guardas de «configuración peligrosa» | 19 | **22** |

---

## 17.9. Lo que esta fase no hizo

Se dice aquí y no en una nota al pie, porque un informe que solo cuenta lo que salió bien
no sirve para planificar lo siguiente.

- **Unas 43 etiquetas de formulario siguen sin asociar** en `LeadDetailModal`,
  `NewLeadModal`, `LoginScreen` y `AdminPanel`. Se arreglaron las cuatro del simulador
  porque era el componente bajo prueba; el resto queda señalado.
  *Corregido después del cierre de esta fase, en otra sesión de trabajo del mismo día; el
  texto no se actualizó y el Capítulo 19 (§19.6) lo encontró al planificar: las 43 están
  asociadas y `jsx-a11y/label-has-associated-control` lo exige como error.*
- **`react-hooks/set-state-in-effect` está apagada.** Encenderla exige rediseñar cómo la
  aplicación obtiene sus datos.
- **No hay pruebas de `App.jsx`, `AdminPanel`, `LeadDetailModal` ni `NewLeadModal`.** El
  suelo de cobertura se mide sobre cuatro módulos, no sobre el cliente entero, y decir lo
  contrario sería inflar el número.
- **No hay pruebas de extremo a extremo en un navegador real.** Lo que hay son pruebas de
  unidad en un DOM simulado más una verificación de la página servida por nginx; entre
  ambas queda un hueco que ninguna cubre.
- **La reproducibilidad de la imagen del frontend bajó** al añadir `apk upgrade`.
  *Cerrado en el capítulo 22: la base va fijada por huella y `apk upgrade` se sustituyó por
  los dos paquetes que hacían falta, con su versión exacta.*
- **El escaneo depende de la base de datos de Trivy del día**: el mismo Dockerfile puede
  pasar hoy y fallar mañana sin que nada haya cambiado en el repositorio. Es el
  comportamiento correcto, pero conviene saberlo antes de que ocurra.
