# Sistema Inteligente de Lead Scoring (Release v1.0.0 - Versión Entregable)

**Empresa Titular:** PluriOne S.A. de C.V.  
**Representante Legal:** Lic. Xochicuahuitl Gleason Juárez  
**Asesor Empresarial:** Juan Méndez Herrera  
**Líder de Proyecto:** Edgar Loheffelmman  
**Alumno Residente:** Rosales Castillo Sebastián · **No. de control:** 223107211  
**Código del proyecto académico:** G19X-TESCI-SRC-708 —el nombre de este repositorio—  
**Institución:** Tecnológico de Estudios Superiores de Cuautitlán Izcalli (TESCI)  
**Carrera:** Ingeniería en Sistemas Computacionales  
**Periodo de Ejecución:** Estadía Profesional (2026)  

---

## Cómo ejecutarlo desde cero

Para quien llega a evaluarlo y quiere verlo funcionando antes de leer nada más. Si algo de
aquí no sale, está en [**Si algo falla**](docs/Si_Algo_Falla.md).

**Hace falta instalado:** Python 3.13, Node.js 20 y Docker Desktop. Nada más —PostgreSQL y
Redis vienen dentro de la pila—.

**Cuánto tarda, cronometrado el 9 de octubre de 2026 sobre un clon limpio.** Todo menos
construir las imágenes son **306 s**: clonar 20, instalar el lock 147, entrenar el modelo 38,
compilar el cliente 40, migrar 38 y sembrar 8. Lo que manda en el total es la construcción de
las imágenes, y no depende del repositorio sino de lo que la máquina ya tenga: **37 s con la
caché de Docker caliente y 464 s con ella fría** —y más aún si hay que descargar las imágenes
base—. Así que entre **seis y trece minutos**, y la diferencia es casi toda descarga. Los
pasos 1 a 3 se hacen una sola vez; a partir de ahí, levantar la pila son segundos.

> **Docker Desktop se apaga solo, y no lo dice.** Trae el *Resource Saver* encendido con un
> plazo de cinco minutos: si no hay ningún contenedor corriendo apaga su máquina Linux, el
> icono **no cambia** y la ventana sigue diciendo que está encendido. La siguiente orden
> falla. Si pasa, espere medio minuto a que vuelva, o apague ese ajuste en
> *Settings → Resources*.

```bash
# 1. EL MODELO PRIMERO. No viaja en el repositorio y sin él la pila arranca igual, puntuando
#    con el heurístico: no da ningún síntoma. Dos minutos, con los datos ya dentro.
pip install --require-hashes -r backend/requirements.lock
python ml_pipeline/src/train_model.py

# 2. El cliente compilado. `dist/` tampoco viaja, y la imagen del backend lo copia para
#    servir la SPA ella sola en el 8000. Sin él la construcción muere.
cd frontend && npm ci && npm run build && cd ..

# 3. El entorno, una sola vez. Genera los secretos FUERA del repositorio, en
#    ~/.plurione/pila.env. Nunca `docker compose` a secas: el lanzador es el único arranque.
python devops/pila.py iniciar

# 4. El esquema y la pila.
python devops/pila.py run --rm migrate
python devops/pila.py up -d --build

# 5. Las cuentas y los datos. UNA BASE RECIÉN MIGRADA NO TIENE NINGUNA CUENTA: sin este paso
#    el panel pide credenciales que no existen.
python devops/pila.py exec -e ENVIRONMENT=development backend python /app/scripts/seed_data.py
```

> En **Git Bash sobre Windows** el paso 5 falla: MSYS convierte `/app/scripts/…` en una ruta
> de Windows y Python no la encuentra. Use PowerShell, o ponga `MSYS_NO_PATHCONV=1` delante.

El panel queda en **<http://localhost:3000>**. Que está vivo lo dice
`curl -s http://127.0.0.1:8000/health`, y en `ml_model_loaded` si está puntuando el modelo o
el heurístico.

### Usuario de prueba

| Usuario | Contraseña | Qué ve |
| :--- | :--- | :--- |
| `admin.ti@plurione.com` | `PluriOne2026!` | Todo: cuentas, bitácora, derechos del titular |
| `lider.ventas@plurione.com` | `PluriOne2026!` | La cartera completa, las publicaciones, los informes |
| `asesor.comercial@plurione.com` | `PluriOne2026!` | **Solo sus propios prospectos** |

`PluriOne2026!` es la contraseña de desarrollo de `backend/scripts/seed_data.py` y la única
excepción documentada a «ningún secreto en el árbol»: contra un entorno endurecido el
sembrado genera una aleatoria y la enseña una sola vez. Las otras cuatro cuentas de la
demostración están en [Si algo falla](docs/Si_Algo_Falla.md#4-las-cuentas-para-entrar).

**Si prefiere no construir nada**, [`db/base-de-datos.sql`](db/base-de-datos.sql) trae el
esquema y los datos de prueba ya volcados —las siete cuentas incluidas—, para
importarlo en una base vacía:

```bash
psql -U postgres -d lead_scoring_db -f db/base-de-datos.sql
```

Y si la pila ya está levantada, lo mismo sin publicar ningún puerto:

```bash
python devops/pila.py exec -T postgres psql -U plurione -d lead_scoring_db \
  < db/base-de-datos.sql
```

El volcado lleva `--clean --if-exists`, así que **borra y recrea** lo que encuentre: se
importa sobre una base vacía o sobre una que se pueda perder, nunca sobre datos que
haga falta conservar.

### Dónde está cada cosa

| Qué | Dónde |
| :--- | :--- |
| **Script de la base de datos** | [`db/base-de-datos.sql`](db/base-de-datos.sql) —esquema, datos sintéticos y las siete cuentas— |
| **Dependencias congeladas** | [`backend/requirements.lock`](backend/requirements.lock) —55 paquetes con 1373 huellas— y [`frontend/package-lock.json`](frontend/package-lock.json) |
| **Variables de entorno** | [`.env.example`](.env.example) y [`devops/.env.example`](devops/.env.example). Los valores reales **no** viven en el repositorio |
| **PRD y definición del MVP** | [`PRD`](docs/entregables_plataforma/PRD.md) · [`MVP`](docs/entregables_plataforma/MVP.md) |
| **Arquitectura** | La sección de aquí abajo, y [la memoria técnica](docs/Memoria_Tecnica_Final_Lead_Scoring.md) |
| **Manual de operación** | [`docs/Si_Algo_Falla.md`](docs/Si_Algo_Falla.md), escrito para quien no programa |

---

## Lo que todavía no funciona

Sin adornos, porque lo que no se dice se encuentra igual. La lista entera, con el origen de
cada punto y dónde se decidió, está en
[**Congelación y trabajo futuro**](docs/Congelacion_y_Trabajo_Futuro.md), que es la autoridad
sobre esto.

| | |
| :--- | :--- |
| **Deuda menor anotada** | **59 puntos** en §6.4, de los que **16 están cerrados** y **43 siguen abiertos**: cifras escritas a mano que nada compara con lo que hay, controles que miden una ruta en vez de una propiedad, y un lanzador que no comprueba si el motor de Docker está vivo |
| **Lo que no se va a hacer** | **12 decisiones** en §7, cada una con su motivo. No están pendientes: están decididas |
| **Lo que el modelo no puede decir** | El ROC-AUC de 0.9469 se mide sobre datos **sintéticos**. Lo que se defiende es el aporte de **+0.052** sobre el heurístico en ese mismo conjunto. El rendimiento comercial solo podrá medirse con conversiones reales, que todavía no existen |
| **Lo que la suite no puede ejercitar** | Corre sobre SQLite en memoria, así que lo que solo existe en PostgreSQL —`FOR UPDATE`, algunas restricciones— se comprueba sobre la **sentencia compilada** contra el dialecto real, nunca dándolo por bueno sin ejecutarlo |
| **El modelo y el cliente compilado** | No viajan en el repositorio, a propósito: un *pickle* versionado es código de procedencia desconocida. Hay que generarlos, y el paso 1 de arriba lo hace |

---

## En treinta segundos

> ⚠️ **Antes de ejecutar nada: el modelo entrenado no viaja en el repositorio** y la pila
> arranca igual sin él, puntuando con el heurístico —que es la línea base contra la que el
> modelo se compara—. Sin síntoma ninguno. El primer paso de la guía de inicio es entrenarlo:
> dos minutos, con los datos ya incluidos. Por qué y cómo comprobarlo, en
> [**Para quien revisa este repositorio**](docs/Para_Quien_Revisa_Este_Repositorio.md).

| | |
| :--- | :--- |
| **Qué es** | Un sistema de *lead scoring* para un equipo comercial pequeño: puntúa cada prospecto combinando un modelo supervisado calibrado con un heurístico de perfil ideal y decaimiento temporal, explica la puntuación, reparte las fichas nuevas, y recoge prospectos de una página pública enlazada desde una publicación de LinkedIn. Nueve pantallas, 2093 pruebas de servidor y 748 de cliente, seis contenedores. |
| **Cómo se levanta** | Entrenar el modelo, `python devops/pila.py iniciar`, `python devops/pila.py up --build -d`, y el panel queda en [localhost:3000](http://localhost:3000). Las órdenes exactas, en la [guía de inicio rápido](#-guía-de-inicio-rápido-despliegue-de-la-versión-entregable). Nunca `docker compose` a secas: el lanzador es el único arranque, y los secretos viven **fuera** del árbol. |
| **Cómo se comprueba** | `curl -s http://127.0.0.1:8000/health` dice si puntúa el modelo o el heurístico (`ml_model_loaded`). `python -m pytest backend/tests -q` corre la suite; las **siete guardas de propiedades** y los **61 controles de configuración peligrosa** están en `.github/workflows/ci.yml`, que no usa ningún secreto y corre tal cual en un *fork*. El recorrido completo de la demostración, con tiempos, en el [guion cronometrado](docs/Guion_Cronometrado_de_la_Demo.md). |
| **Qué se defiende** | No el ROC-AUC de 0.9469, que se mide sobre datos **sintéticos**, sino el **aporte de +0.052 (IC 95 % [+0.030, +0.076])** sobre el heurístico en el mismo conjunto. Las cifras verifican que el pipeline está íntegro; el rendimiento comercial solo puede medirse con conversiones reales que todavía no existen. |
| **Qué está congelado** | Desde el **06-10-2026**, todo: entra un cambio solo si sin él la pila no se levanta o la demostración no se puede enseñar. Lo que queda abierto está escrito y clasificado en [Congelación y trabajo futuro](docs/Congelacion_y_Trabajo_Futuro.md), que es la autoridad sobre esto. |
| **Si algo parece un fallo** | Mire primero la tabla de [**lo que parece un fallo y está decidido así**](docs/Para_Quien_Revisa_Este_Repositorio.md#4-si-esto-parece-un-fallo) y las dos listas a las que apunta: los **59 restos menores** de §6.4 —43 abiertos— y las **doce decisiones** de §7 «lo que no se va a hacer, y por qué». |

---

## 🔒 Aviso de Confidencialidad y Propiedad Intelectual

> **CONVENIO DE CONFIDENCIALIDAD Y CESIÓN DE DERECHOS PATRIMONIALES**  
> La totalidad del código fuente, modelos matemáticos, algoritmos de scoring híbrido, diagramas de arquitectura, componentes de software, reportes técnicos y la memoria técnica consolidada son propiedad intelectual y patrimonial exclusiva de **PLURIONE S.A. DE C.V.**
>
> **Anonimización Estricta:** En cumplimiento riguroso con el Secreto Industrial y el Convenio de Confidencialidad, el 100% de los datos, prospectos, empresas y correos electrónicos utilizados en este repositorio corresponden a **datos sintéticos generados probabilísticamente**. No se expone ningún dato sensible, financiero ni de clientes reales de PluriOne.
>
> Las condiciones de uso están en [**LICENSE**](LICENSE): se permite clonarlo y ejecutarlo para
> **evaluar o revisar** el trabajo, y citarlo con atribución; cualquier otro uso necesita
> autorización escrita de PluriOne S.A. de C.V.

---

## Declaración de uso de inteligencia artificial

Este proyecto se escribió **en pareja con un asistente de inteligencia artificial**, y queda
dicho aquí en lugar de dejar que se deduzca del historial. (La «IA explicable» que aparece más
abajo es otra cosa: un motor del producto que explica por qué una ficha puntuó lo que puntuó.)

| Qué | Detalle |
| :--- | :--- |
| Herramienta | Claude Code, de Anthropic |
| Modelos | Claude Opus 5 —la mayoría— y Claude Sonnet 5.5 |
| Alcance | **Todas** las confirmaciones del historial llevan su línea de coautoría. No «casi todas»: las dos órdenes de abajo tienen que devolver el mismo número |
| En qué | Redactar código, pruebas, guardas y documentos, y ejecutar las comprobaciones |

Esa tabla no hay que creérsela, se comprueba. **La segunda orden cuenta commits, no líneas**, y las dos cifras tienen que coincidir:

```bash
git rev-list --count HEAD
git log --grep="co-authored-by: claude" -i --format=%H | wc -l
```

> **Tres avisos para quien lo compruebe**, porque las tres cosas hacen que la cuenta salga distinta y una de ellas ya nos pasó:
>
> 1. **`git log --grep` es sensible a mayúsculas por omisión.** El trailer está escrito `Co-Authored-By`, así que buscarlo en minúsculas **sin `-i` devuelve cero**.
> 2. **`git log --format=%B | grep -c` cuenta líneas, no commits.** Aquí coincide porque cada mensaje lleva una sola línea de coautoría, pero no es la misma medición y no hay que confundirlas. Esa orden estuvo publicada aquí por error hasta el 19 de octubre de 2026.
> 3. **GitHub no pinta a Claude como coautor** en la página de cada commit, porque `noreply@anthropic.com` no es una cuenta de GitHub. La línea está en el mensaje y `git` la lee como trailer, pero la interfaz no la atribuye: contar lo que **se ve** da otro número que contar lo que **está escrito**.

**Lo que decidí yo.** El alcance del sistema y lo que entra en él; las dos congelaciones —la de
funcionalidades del 24 de septiembre y la definitiva del 6 de octubre— y, con ellas, qué
defectos se corrigen y qué se **anota** en lugar de corregirse, que es la lista de
[§6.4](docs/Congelacion_y_Trabajo_Futuro.md); y qué sale del repositorio y qué no.

**Y cómo se comprobó, que es lo que hace defendible lo anterior.** Nada se dio por bueno porque
pareciera correcto. La disciplina de este repositorio existe justamente para no fiarse de lo
que no se ha ejecutado: cada corrección pasa un **arnés de reintroducción** que vuelve a
escribir el defecto y exige que algo se ponga rojo —si nada se pone rojo, la defensa no
existe—, las listas que miden las guardas se **derivan del código** en lugar de escribirse a
mano, y el veredicto de la integración continua se consulta con `scripts/guarda_del_ci.py`, que
sale con **2** —y no con 0— cuando no ha podido mirar. Las cifras de este README salen de esas
ejecuciones.

---

## Referencia completa

Las **1450 líneas** que seguían aquí están íntegras en [**docs/Referencia_Completa.md**](docs/Referencia_Completa.md), sin cambiar una palabra. Se movieron el 15 de octubre de 2026 porque este archivo había llegado a 1 645 líneas y nadie entra a un repositorio por un documento de ese tamaño.

| # | Sección |
| :---: | :--- |
| 1 | 🚀 Arquitectura y Tecnologías Clave (Stack Optimizado de Producción) |
| 2 | ⚡ Guía de Inicio Rápido (Despliegue de la Versión Entregable) |
| 3 | 🔐 Autenticación y Control de Acceso |
| 4 | 📥 Cómo llegan los prospectos |
| 5 | 🌐 Rutas y Puertos de Validación Funcional |
| 6 | 🛠️ Fiabilidad Operativa |
| 7 | 🧪 Ejecución de Pruebas Automatizadas (QA) |
| 8 | 🎯 Demostración Técnica Interactiva (CLI) |
| 9 | 📚 Compilación de la Memoria Técnica Institucional |
| 10 | 📑 Suite de 44 Reportes Técnicos de Estadía Profesional |

Y el resto de la documentación —la congelación, los manuales, los 44 reportes y la memoria compilada— está en [`docs/`](docs/), con el mapa en **«Dónde está cada cosa»** más arriba.
