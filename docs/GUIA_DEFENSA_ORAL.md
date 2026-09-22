# Guía de Defensa Oral y Banco de Preguntas Técnicas de Estadía Profesional

**Proyecto:** Sistema Inteligente de Lead Scoring basado en Inteligencia Artificial y Machine Learning  
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)  
**Autor:** Alumno de Estadía Profesional - Ingeniería en Sistemas Computacionales  
**Fecha de Sustentación:** Septiembre 2026  

---

## 1. Guion Cronometrado de Exposición Ejecutiva (10 Minutos)

| Tiempo | Diapositiva / Sección | Puntos Clave a Defender | Recomendación de Comunicación |
| :---: | :--- | :--- | :--- |
| **0:00 - 1:00**<br>*(1 min)* | **1. Portada y Contexto Institucional** | • Presentación personal y agradecimiento a PluriOne S.A. de C.V. (Develop Talent & Technology).<br>• Mención de asesores (Lic. Xochicuahuitl Gleason, Juan Méndez, Edgar Loheffelmman).<br>• Declaración de confidencialidad y datos 100% sintéticos. | Tono formal, seguro y enfocado en el impacto de ingeniería de software. |
| **1:00 - 2:30**<br>*(1.5 min)* | **2. Diagnóstico del Problema y Objetivos** | • El cuello de botella: Latencia de primer contacto de 36 horas por atención FIFO manual.<br>• Tasa de conversión de partida baja (12%).<br>• La restricción de ingeniería: Solución local robusta a **$0 USD** escalable a **Microsoft Azure**. | Enfatizar la justificación económica y técnica de la estadía. |
| **2:30 - 4:30**<br>*(2 min)* | **3. Arquitectura del Sistema y Formulación Matemática** | • *Clean Architecture* con Puertos y Adaptadores (Hexagonal).<br>• Ecuación del algoritmo híbrido: $60\%$ ML + $40\%$ Heurístico $\times \gamma(\Delta t)$.<br>• Justificación matemática de la vida media de 14 días ($\gamma(\Delta t) = (0.5)^{\Delta t / 14}$). | Mostrar claridad metodológica y solidez en ciencias de la computación. |
| **4:30 - 6:30**<br>*(2 min)* | **4. Demostración Técnica y Explicabilidad (XAI)** | • Ejecución del flujo: Ingesta de Webhook $\rightarrow$ Scoring reactivo $\rightarrow$ Asignación comercial de leads `HOT`.<br>• Presentación de la Ficha 360 y diagnóstico en lenguaje natural de IA (XAI).<br>• Visualización analítica tipo Power BI en React.js. | Demostrar dominio del código y de la experiencia de usuario. |
| **6:30 - 8:00**<br>*(1.5 min)* | **5. Aseguramiento de Calidad, DevOps y Seguridad** | • Pirámide de QA: **428 pruebas** automatizadas en Pytest (100% aprobadas, 91% de cobertura).<br>• Autenticación real con JWT firmado, sesiones con rotación verificable y **autorización sobre el dato**: un asesor solo ve su cartera.<br>• Contenerización Docker multi-etapa con usuario sin privilegios y **diez trabajos** de CI en GitHub Actions. | Transmitir rigor en buenas prácticas de ingeniería de software. |
| **8:00 - 10:00**<br>*(2 min)* | **6. Impacto Cuantitativo, ROI y Conclusiones** | • Reducción del tiempo de contacto de 36 horas a $<15$ min.<br>• Incremento proyectado de conversión al $32.5\%$ (+170%).<br>• Ahorro de $100\%$ en licencias de desarrollo.<br>• Conclusiones y agradecimiento al sínodo. | Cierre firme, vinculando los logros de ingeniería con el éxito empresarial. |

---

## 2. Banco de 16 Preguntas Técnicas Rigurosas de Sínodo y Respuestas Modelo

### Pregunta 1: ¿Por qué elegiste Clean Architecture (Puertos y Adaptadores) en lugar de una arquitectura MVC convencional?
**Respuesta Modelo:**  
> *"Elegí Clean Architecture porque uno de los requerimientos críticos de PluriOne era operar en desarrollo local a costo cero ($0 USD) pero mantener la capacidad de conectarse a servicios administrados de Azure (Azure ML, Azure OpenAI y Azure AI Search) en producción sin reescribir la lógica del negocio.  
> Mediante el patrón Puertos y Adaptadores, definí interfaces abstractas en `app/adapters/base.py` y creé dos implementaciones concretas: una local mock (con Scikit-Learn y sintetizador de reglas en memoria) y una en la nube (con SDKs de Azure). FastAPI y los servicios de dominio interactúan únicamente con las interfaces abstractas, logrando un acoplamiento nulo con la infraestructura subyacente y permitiendo alternar entornos con solo cambiar una variable en el archivo `.env`."*

---

### Pregunta 2: ¿Cómo justificas matemáticamente ponderar el Score en 60% Machine Learning y 40% Heurística en lugar de usar 100% Machine Learning?
**Respuesta Modelo:**  
> *"En la prospección comercial B2B de talento TI, confiar exclusivamente en un modelo de Machine Learning introduce dos riesgos graves: el problema de **arranque en frío (Cold Start)** para nuevos segmentos o cargos emergentes y la **falta de determinismo en reglas de negocio estrictas** (como un Ideal Customer Profile o ICP).  
> Al diseñar la ecuación $S_{\text{final}} = 0.60 \times S_{\text{ML}} + 0.40 \times S_{\text{Heurístico}}$, permití que el 60% capture las correlaciones sutiles y no lineales del comportamiento histórico mediante Gradient Boosting, mientras que el 40% garantiza que prospectos con alto encaje de cargo (ej. CTO) y presupuesto verificado reciban una base sólida de puntuación incluso si sus interacciones digitales son escasas. Esta combinación híbrida maximiza tanto la adaptabilidad estadística como el alineamiento estratégico de la empresa."*

---

### Pregunta 3: ¿Cuál es el fundamento científico de la fórmula de decaimiento temporal $\gamma(\Delta t) = (0.5)^{\Delta t / 14}$ y por qué una vida media de 14 días?
**Respuesta Modelo:**  
> *"En los sistemas de ventas B2B, el interés y la propensión de compra de un prospecto no caen de forma lineal ni mediante escalones discretos arbitrarios, sino siguiendo una ley de desintegración exponencial análoga a la vida media física: $\gamma(\Delta t) = e^{-\lambda \Delta t}$.  
> Tras analizar los ciclos de venta de consultoría y contratación de talento en PluriOne, determiné que el ciclo promedio de evaluación de proveedores es de dos semanas (14 días). Fijando $T_{1/2} = 14 \text{ días}$, la tasa de decaimiento es $\lambda = \frac{\ln(2)}{14} \approx 0.04951$. Esto asegura que en el día 0 el factor sea 1.0 (sin penalización), en el día 7 conserve el $70.7\%$, en el día 14 caiga exactamente al $50\%$ y en el día 28 al $25\%$. Esto refleja fielmente la urgencia de recontactar al cliente antes de que busque otra alternativa."*

---

### Pregunta 4: ¿Por qué utilizaste `CalibratedClassifierCV` con calibración isotónica en lugar de tomar directamente la salida de `predict_proba`?
**Respuesta Modelo:**  
> *"Los algoritmos basados en árboles de decisión potenciados, como Gradient Boosting o XGBoost, son excelentes clasificadores ordinales (generan curvas ROC óptimas), pero sus probabilidades predichas brutas suelen estar distorsionadas hacia los extremos debido al mecanismo de partición de hojas y la función de pérdida logarítmica.  
> Dado que en nuestro sistema la salida del modelo de ML se multiplica directamente por 60 para integrarse a la ecuación de scoring, una probabilidad mal calibrada distorsionaría el umbral entre prospectos `WARM` y `HOT`. Al aplicar `CalibratedClassifierCV(method='isotonic', cv=3)`, ajusté una regresión no paramétrica monótona que mapeó las probabilidades del modelo a frecuencias relativas reales, reduciendo el Brier Score a $0.0875$ y garantizando que un 80% predicho equivalga exactamente a 8 conversiones de cada 10 casos reales."*

---

### Pregunta 5: ¿Cómo garantizaste que no existiera fuga de datos (Data Leakage) durante el preprocesamiento y entrenamiento del pipeline?
**Respuesta Modelo:**
> *"En tres niveles, y conviene distinguirlos porque el tercero es el que de verdad importa.
>
> **En el preprocesamiento:** la partición (80/20, estratificada sobre `converted`) se hace
> antes de cualquier transformación, y todos los transformadores —`StandardScaler`,
> `SimpleImputer`, `OneHotEncoder`— viven dentro de un `Pipeline` de Scikit-Learn, de modo
> que se ajustan solo con el conjunto de entrenamiento.
>
> **En los datos publicados:** el generador sintético calcula una variable latente
> `latent_prob` de la que se deriva la etiqueta, y esa columna se estaba publicando en el
> CSV. Era una columna de fuga en el sentido literal: la respuesta del examen junto a las
> preguntas. La detecté en la auditoría interna y la retiré (Capítulo 12).
>
> **En el bucle de realimentación:** este es el más sutil. Un prospecto ganado lleva, por
> definición, propuesta enviada y reunión agendada. Si construyera el dataset de
> reentrenamiento leyendo los prospectos tal como están hoy, el modelo aprendería que
> enviar propuestas causa cierres: la relación invertida, y además inútil, porque en el
> momento de decidir a quién llamar todavía no se ha enviado ninguna. Por eso cada
> puntuación guarda una instantánea del vector de variables tal como estaba al puntuar, y
> el dataset se etiqueta sobre esa instantánea. Los prospectos aún en el embudo se excluyen
> en lugar de contarse como perdidos: tratar la censura por la derecha como negativo sesga
> el modelo hacia el pesimismo justo en los prospectos más activos."*

---

### Pregunta 6: ¿Cómo resolvió el sistema la deduplicación y la idempotencia ante múltiples webhooks entrantes de plataformas CRM?
**Respuesta Modelo:**  
> *"En `app/services/crm_service.py`, diseñé un flujo de ingesta transaccional atómica en base de datos. Cada webhook entrante normaliza el correo electrónico del prospecto como identificador único natural (`Lead.email`).  
> Si el prospecto ya existe en la base de datos, el servicio actualiza sus atributos firmográficos (empresa, cargo) y añade el nuevo evento digital en la tabla relacional `lead_activities` sin crear registros duplicados. Posteriormente, ejecuta de forma automática el recálculo dinámico del score y registra una traza inmutable en `crm_integration_logs` con el ID externo de la plataforma (ej. HubSpot o Zoho), garantizando auditoría total e idempotencia en la ingesta."*

---

### Pregunta 7: ¿Cómo funciona el desacoplamiento a costo cero ($0 USD) de la capa de IA generativa (Azure OpenAI)?
**Respuesta Modelo:**  
> *"Diseñé la clase `NativeXAIExplanationAdapter` —`LocalMockOpenAIAdapter` se conserva como alias— que implementa la interfaz `BaseAIExplanationAdapter`.  
> En entorno de desarrollo local ($0 USD), este adaptador analiza determinísticamente el desglose del score (cargo, industria, actividades registradas) y genera un diagnóstico en lenguaje natural con resumen ejecutivo, viñetas de fortalezas y una recomendación táctica para el asesor comercial (ej. 'Ofrecer propuesta de células de desarrollo').  
> Cuando el parámetro `AI_MODE` en `.env` se conmuta a `azure`, el adaptador `AzureOpenAIAdapter` se activa para invocar la API REST de Azure OpenAI (GPT-4o) utilizando el mismo formato estructurado JSON Pydantic (`AIExplanation`), manteniendo la interfaz del frontend 100% inalterada."*

---

### Pregunta 8: ¿De qué manera previene el algoritmo el sesgo o la discriminación hacia prospectos de empresas pequeñas o canales emergentes?
**Respuesta Modelo:**  
> *"El algoritmo compensa la escala de la empresa mediante el componente conductual y de cargo. Si un prospecto proviene de una empresa de 11 a 50 empleados pero su contacto es el Director General (CEO) y ha descargado tres whitepapers, asistido a un webinar y solicitado una demostración, la suma de las puntuaciones de alta intención digital y cargo directivo elevará su score por encima de los 75 puntos (`HOT`), asegurando que las oportunidades comerciales viables de alto interés nunca sean descartadas por el tamaño de su organización."*

---

### Pregunta 9: ¿Cómo se estructuró la seguridad y el control de acceso basado en roles (RBAC)?
**Respuesta Modelo:**
> *"Conviene que empiece por lo que **no** hace, porque la primera versión lo hacía mal y
> la corrección es parte del trabajo.
>
> El sistema leía el rol de las cabeceras `X-User-Role` / `X-Entra-User-Role`. Una cabecera
> la escribe el cliente, así que cualquiera podía declararse administrador con un `curl` de
> una línea. Además la mayoría de los endpoints de datos no tenían ninguna dependencia de
> autorización. Lo detecté en una auditoría interna del propio código y lo reescribí por
> completo.
>
> Hoy hay autenticación real: `POST /auth/login` verifica la contraseña contra un hash
> `bcrypt` y emite un JWT firmado con HS256. `get_current_user` **verifica la firma**, y las
> cabeceras de identidad ya no se leen en ningún punto. Los tres roles —
> `Commercial_Executive`, `Sales_Lead`, `System_Admin`— se aplican con la fábrica de
> dependencias `require_roles([...])`, que responde 403 cuando la operación queda fuera del
> perfil.
>
> El *access token* vive solo en memoria del navegador, nunca en `localStorage`; el de
> refresco viaja en una cookie `HttpOnly`, `SameSite=Strict`, acotada a `/api/v1/auth`, y
> **se rota en cada uso**: cada emisión queda registrada y refrescar consume la anterior.
> Al cerrar sesión se revocan todas las sesiones vivas y se incrementa `token_version`,
> que las cierra en todos los dispositivos a la vez. La Pregunta 13 desarrolla la parte de
> la rotación, que también empezó siendo aparente y no real.
>
> Y las pruebas comprueban la **denegación**, no el permiso: un token forjado y una cabecera
> manipulada deben recibir 401 y 403. Una prueba que solo verifica que el usuario correcto
> entra pasa igual de verde con la autorización desactivada."*

---

### Pregunta 10: ¿Cuál es el plan de mantenimiento para evitar la degradación del modelo de Machine Learning en producción (MLOps)?
**Respuesta Modelo:**
> *"Parte está implementada y parte depende del tiempo, y prefiero separarlo con claridad.
>
> **Lo que ya funciona.** El monitoreo de deriva de variables está implementado con el
> índice PSI: compara la distribución de los prospectos que se están puntuando contra el
> perfil de referencia del entrenamiento, con los umbrales convencionales de 0.10 y 0.25.
> Viaja dentro de la imagen del backend, porque en la pila de despliegue PostgreSQL no
> publica puerto y solo un contenedor de esa red alcanza la base. Existe además un registro
> versionado de modelos: cada entrenamiento anota fecha, huella SHA-256 del artefacto,
> ROC-AUC y aporte sobre el heurístico, de modo que un `.joblib` desplegado puede
> rastrearse hasta el entrenamiento que lo produjo. El reentrenamiento tiene dos puertas:
> el ROC-AUC no puede caer de 0.82 y el modelo tiene que aportar al menos +0.01 sobre el
> heurístico; si no las pasa, el proceso sale con código 1 y **no sobrescribe el artefacto
> anterior**.
>
> **Lo que todavía no puede estar hecho.** El *concept drift* —que cambie la relación entre
> las variables y la conversión— solo se mide con conversiones reales, y el bucle de
> realimentación necesita un ciclo comercial completo para producir su primer dataset: entre
> puntuar un prospecto y conocer su desenlace pasan semanas o meses. La infraestructura está
> lista y probada, con mínimos de 200 ejemplos y 50 por clase; los datos, por definición,
> aún no. Prometer un reentrenamiento trimestral automático hoy sería prometer algo que el
> calendario no permite."*

---

### Pregunta 11: El ROC-AUC de 0.9524 parece muy alto. ¿Es creíble?
**Respuesta Modelo:**
> *"No como métrica de negocio, y es importante que lo diga yo antes de que lo pregunte el
> sínodo.
>
> El modelo se entrena con datos **sintéticos** cuya etiqueta `converted` se genera con una
> fórmula conocida a partir de las mismas variables, más ruido gaussiano. El 0.9524 mide,
> por tanto, la capacidad del modelo de reaprender la regla del generador. Eso verifica que
> el pipeline está íntegro —que las variables llegan, que el preprocesado no las corrompe,
> que la calibración funciona—, no el rendimiento esperable en producción.
>
> Para poder decir esto con números y no con adjetivos, añadí líneas base sobre el mismo
> conjunto de prueba:
>
> | | ROC-AUC |
> | :--- | ---: |
> | Azar | 0.5000 |
> | Ordenar por una sola columna (`days_since_last_activity`) | 0.9136 |
> | Heurístico ICP, sin modelo | 0.9110 |
> | Modelo entrenado | 0.9524 |
>
> El número que importa no es el 0.95: es que **ordenar la lista por una columna ya da
> 0.91**. El aporte real de todo el pipeline de Machine Learning es de **+0.041** sobre lo
> que el sistema haría sin modelo. Esa es la cifra que defiendo, y por eso el gate de
> calidad mide también el aporte y no solo el ROC-AUC: el umbral de 0.82 no distinguía
> nada, porque la regla trivial ya lo superaba.
>
> Sostener el 0.94 como logro comercial habría sido más lucido y no habría resistido esta
> misma pregunta. El Capítulo 12 lo desarrolla."*

---

### Pregunta 12: El sistema pasa datos escritos por el prospecto a un modelo generativo. ¿Qué impide que alguien manipule la recomendación que ve el asesor?
**Respuesta Modelo:**
> *"Es una inyección de prompt, y la trato como lo que es: un riesgo que se acota, no un
> problema que se resuelve del todo.
>
> El adaptador componía la petición interpolando el diccionario del prospecto en una frase.
> `first_name`, `company` y el `custom_metadata` los escribe quien rellena el formulario, así
> que un prospecto podía introducir saltos de línea y un delimitador falso y redactar parte
> del prompt. El daño no es técnico —no ejecuta nada— sino de confianza: la salida se
> persiste y se le muestra al asesor **como la recomendación del sistema**, de modo que el
> atacante consigue que la herramienta de la empresa transmita su mensaje con credibilidad
> interna.
>
> Tres medidas, porque ninguna basta sola. Primera: los datos viajan como datos, serializados
> en JSON bajo una clave explícita, y `json.dumps` escapa los saltos de línea, que son el
> vehículo de la inyección. Segunda: se sanean y se acotan, con lista blanca de campos y
> truncado, lo que además pone techo al coste —`raw_metadata` llega por webhook y nada
> impedía mandar un megabyte—. Tercera: la salida se valida contra un esquema estricto antes
> de creerla; si no cumple, se cae al motor determinista.
>
> Lo que **no** puedo afirmar es que el modelo vaya a ignorar siempre un intento de
> manipulación: eso no lo garantiza ningún prompt. Lo que sí queda garantizado es que nada
> fuera del esquema llega a la base ni a la interfaz. Prefiero decirlo así antes que declarar
> el riesgo cerrado."*

---

### Pregunta 13: Si alguien roba la cookie de sesión de un usuario, ¿qué pasa?
**Respuesta Modelo:**
> *"Hasta hace poco, siete días de acceso renovable sin que nadie se enterara. Ahora, como
> mucho una sesión — y queda constancia.
>
> El código decía que rotaba el token de refresco, y en su comentario incluso explicaba por
> qué eso limitaba la ventana de una cookie robada. Era falso: entregaba una cookie nueva,
> sí, pero la anterior seguía valiendo hasta expirar, porque lo único que se comprobaba era
> un contador que solo cambia al cerrar sesión. Lo digo así de claro porque **un comentario
> que describe una protección inexistente es peor que no tenerlo**: cierra la pregunta.
> Quien leyera ese archivo buscando si la rotación estaba resuelta encontraba que sí.
>
> Lo que hay ahora: cada emisión tiene un identificador propio y pertenece a una *familia*,
> que es la cadena de refrescos nacida de un mismo inicio de sesión. Refrescar consume el
> token presentado y emite el siguiente de la familia, y por construcción una familia tiene
> como mucho un token vigente. De ahí sale la detección, sin ninguna heurística: presentar
> un token ya consumido solo puede significar que dos partes tienen la misma cookie. Como
> no hay forma de saber cuál es la legítima, se revoca la familia entera, ambas vuelven a
> autenticarse y el incidente queda escrito en la bitácora.
>
> Y aquí hay una concesión que prefiero decir yo. Dos pestañas del mismo navegador pueden
> refrescar a la vez, y la segunda llegaría con un token que la primera acaba de consumir:
> con detección estricta, expulsaría de su sesión a alguien que no hizo nada. Por eso hay
> una ventana de gracia de diez segundos. Eso reabre la ventana de una cookie robada
> durante esos segundos, y no me gusta; lo que la justifica es la comparación honesta —diez
> segundos frente a siete días— y que una protección que expulsa a la gente de su sesión se
> acaba desactivando, y desactivada vale cero.
>
> Lo que sigue abierto: un *access token* robado vale hasta expirar, quince minutos. Lo que
> se corta de raíz es la capacidad de **renovar** la sesión, no los tokens ya emitidos."*

---

### Pregunta 14: ¿Cómo demuestra el sistema quién hizo qué?
**Respuesta Modelo:**
> *"Con una bitácora de auditoría, y con tres decisiones sobre ella que importan más que la
> tabla en sí.
>
> El sistema ya trazaba bien lo que les pasaba a los **datos**: cada sincronización con el
> CRM, cada puntuación con su desglose. Lo que no trazaba es lo que hacían las **personas**.
> Un prospecto borrado desaparecía sin dejar constancia de quién lo borró.
>
> Primera decisión: **se registran también los intentos denegados**. Una sola denegación por
> rol es ruido; una tanda seguida de la misma cuenta es alguien tanteando los límites de sus
> permisos, y eso solo se ve si queda escrito. Se escribe desde la propia comprobación de
> rol y no desde el endpoint, porque el 403 ocurre antes de que el endpoint llegue a
> ejecutarse: si esperáramos, la única operación que nunca quedaría registrada sería
> justamente la que alguien intentó hacer sin permiso.
>
> Segunda: **es de solo lectura**. No hay endpoint que borre ni edite asientos. Una bitácora
> que la aplicación puede reescribir no prueba nada, porque lo primero que borraría quien
> abusa de sus permisos es el registro de que lo hizo. La retención se aplica desde fuera.
>
> Tercera, y es la que suele sorprender: **solo la lee el administrador de sistemas, y
> consultarla queda registrado**. La bitácora concentra, ya correlacionado, quién trabaja
> con qué cartera y desde qué direcciones se conecta cada persona; es el mejor resumen que
> existe del comportamiento interno de la empresa. Dársela a un líder comercial «porque es
> responsable del equipo» convertiría una medida de control en vigilancia entre compañeros.
> Y el administrador es el único cuyo acceso nadie más vería si no quedara escrito."*

---

### Pregunta 15: Un asesor comercial inicia sesión. ¿Qué ve?
**Respuesta Modelo:**
> *"Ahora, solo sus prospectos. Antes veía la cartera completa de la empresa, y eso no era
> un fallo de implementación: era una capa que faltaba entera.
>
> El sistema tenía control de acceso por **endpoint** —quién puede llamar a `PUT
> /leads/{id}`— y ninguno por **objeto**, es decir, sobre cuál de todos los prospectos. El
> rol decidía qué verbos podía usar, nunca sobre qué datos. Un asesor autenticado podía
> listar la cartera entera, abrir la ficha de cualquier prospecto con su historial y sus
> explicaciones, y leer los KPIs consolidados de todo el pipeline.
>
> Lo interesante es **dónde** se arregla. Ponerlo en cada endpoint parece lo natural y es
> exactamente lo que no hay que hacer, porque los fallos de autorización son silenciosos:
> nadie recibe un error porque una consulta devolvió prospectos ajenos, la respuesta es un
> 200 perfectamente formado. Un filtro que dependa de que cada endpoint se acuerde de
> aplicarlo dejará de aplicarse el día que alguien añada el siguiente con prisa, y nadie se
> enterará. Así que vive en el repositorio, que es el único sitio por el que hay que pasar
> para llegar a los datos, y el alcance es un **argumento obligatorio del constructor**: sin
> valor por defecto, porque un `alcance=None` que significara «toda la cartera» convertiría
> el olvido en acceso total. Quien lo olvide recibe un error en la primera línea, en la
> suite, no en producción.
>
> Un detalle que suele preguntarse: un prospecto ajeno responde **404**, no 403. Un 403
> confirmaría que ese identificador corresponde a algo real, y recorrer identificadores es
> barato: distinguir «no existe» de «no es tuyo» permite dibujar el tamaño y la forma de la
> cartera ajena sin ver un solo dato. La distinción sí se conserva, pero en la bitácora, que
> es donde sirve.
>
> Y hay una contrapartida que no era obvia: ahora un asesor **sí puede editar** los
> prospectos que atiende. Antes no podía editar ninguno, ni los suyos, y eso empuja a pedirle
> cada cambio de teléfono al líder comercial, o —lo que pasa de verdad— a repartir el rol de
> líder para que la aplicación sea usable. Una restricción demasiado gruesa acaba produciendo
> permisos de más."*

---

### Pregunta 16: ¿Por qué hubo que fusionar dos tablas antes de poder hacer eso?
**Respuesta Modelo:**
> *"Porque sin fusionarlas, la pregunta «¿es este prospecto suyo?» no se podía escribir.
>
> El sistema tenía dos tablas de personas que no se conocían entre sí: `users`, con quien
> puede iniciar sesión, y `sales_reps`, con quien atiende prospectos. Ninguna clave las unía.
> El script de sembrado lo dejaba a la vista sin querer: creaba tres cuentas con unos correos
> y cuatro asesores con otros distintos. Siete personas, cero coincidencias. Cada prospecto
> de la demostración tenía un dueño nominal y ningún dueño real, porque quien figuraba como
> asesor no podía entrar al sistema.
>
> `Lead.assigned_rep_id` apuntaba a la tabla de asesores, así que «de quién es este
> prospecto» y «quién está pidiendo verlo» eran preguntas sobre universos distintos,
> imposibles de comparar. La unificación no fue una limpieza previa: era el requisito.
>
> Se fusionó dentro de `users` y no al revés porque la identidad autenticable es la que
> manda: ser asesor es un atributo de alguien que entra al sistema, no una persona aparte.
> Ahora es una columna, `is_sales_rep`, y conviene decir que **no es un rol**: `Sales_Lead`
> describe qué puede hacer en el sistema; esto, si además se le asignan prospectos. Un
> administrador de TI puede todo y no atiende a nadie.
>
> La parte delicada fue la migración, porque mueve personas, no columnas. Empareja por
> correo: quien ya tenía cuenta la conserva y gana la marca de asesor; quien no la tenía
> recibe una **sin contraseña utilizable** —un marcador que bcrypt nunca puede validar—, así
> que la cuenta existe y sigue recibiendo cartera, pero no entra hasta que un administrador
> le asigne contraseña. Inventar una contraseña conocida para completar la migración habría
> creado exactamente la clase de puerta trasera que este trabajo persigue.
>
> Y un detalle que solo aparece si se ensaya con datos dentro: los identificadores de las dos
> tablas son espacios distintos y **pueden coincidir**. El asesor 1 puede corresponder al
> usuario 3, y el usuario 1 ser otra persona. Si se traduce fila a fila leyendo el valor
> actual, se acaba traduciendo dos veces lo ya traducido y las asignaciones se corrompen en
> silencio. El mapa se lee entero antes de escribir nada, y el ensayo se montó justamente
> sobre ese choque, porque una base de prueba sin colisiones habría dado el mismo resultado
> con el código roto."*
