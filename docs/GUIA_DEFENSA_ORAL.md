# Guía de Defensa Oral y Banco de Preguntas Técnicas de Estadía Profesional

**Proyecto:** Sistema Inteligente de Lead Scoring basado en Inteligencia Artificial y Machine Learning
**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Autor:** Alumno de Estadía Profesional - Ingeniería en Sistemas Computacionales
**Fecha de Sustentación:** Septiembre 2026
**Estado del proyecto:** congelado el 24-09-2026 · 35 capítulos · 33 reportes

> **Cómo usar esta guía.** La sección 1 es el reloj de los diez minutos y **sigue el guion
> de la demostración**: lo que se enseña es la columna vertebral de la exposición, no un
> apartado más. El detalle segundo a segundo de la parte demostrada, con la frase que hay
> que decir mientras carga cada pantalla, está en
> [Guion_Cronometrado_de_la_Demo.md](Guion_Cronometrado_de_la_Demo.md); aquí solo aparece el
> bloque que ocupa.
>
> La sección 2 es el banco de preguntas técnicas. La sección 3 es distinta: son **las
> preguntas incómodas**, las que apuntan a lo que el sistema deliberadamente **no** hace.
> Están respondidas sin adornos, porque son las únicas que no se pueden improvisar.

---

## 1. Guion Cronometrado de Exposición Ejecutiva (10 Minutos)

| Tiempo | Bloque | Qué se defiende | Recomendación |
| :---: | :--- | :--- | :--- |
| **0:00 – 1:00**<br>*(1 min)* | **Portada y contexto** | • Presentación personal y agradecimiento a PluriOne S.A. de C.V.<br>• Asesores: Lic. Xochicuahuitl Gleason, Juan Méndez, Edgar Loheffelmman.<br>• Confidencialidad, y que **todo lo que se va a ver son datos sintéticos**. | Decir lo de los datos sintéticos **aquí**, no cuando lo pregunten. Cambia cómo se lee todo lo demás. |
| **1:00 – 2:00**<br>*(1 min)* | **El problema** | • Atención FIFO sin calificar: **36 horas** de latencia de primer contacto, conversión del **12 %**.<br>• La restricción de ingeniería: local, **$0 USD**, con salida a Microsoft Azure sin reescribir la lógica. | Dos cifras y una restricción. No entrar en arquitectura todavía. |
| **2:00 – 3:00**<br>*(1 min)* | **La arquitectura, en una diapositiva** | • Puertos y Adaptadores: la lógica no sabe si detrás hay Scikit-Learn o Azure ML.<br>• $S_{\text{final}} = 0.60 \times S_{\text{ML}} + 0.40 \times S_{\text{Heurístico}} \times \gamma(\Delta t)$, con $\gamma(\Delta t) = (0.5)^{\Delta t/14}$.<br>• Por qué 60/40 y no 100 % ML: arranque en frío y reglas de negocio deterministas. | Una sola diapositiva. Si el sínodo quiere profundizar, preguntará: están las Preguntas 1, 2 y 3. |
| **3:00 – 7:30**<br>*(4.5 min)* | **LA DEMOSTRACIÓN**<br>*Del post a la red social hasta el dato de entrenamiento* | **1.** Marketing crea la publicación → enlace de 128 bits que da el servidor.<br>**2.** Un post, varias redes: **los dos enlaces son distintos**, y por eso después hay atribución.<br>**3.** El interesado envía sus datos desde el teléfono: **ni un campo de texto libre**.<br>**4.** La ficha nace puntuada, atribuida y **ya repartida**: a quien tiene menos cartera abierta, sin mirar el score.<br>**5.** El líder ve a quién le tocó y se la pasa a su asesor; lo que reasigna a mano se queda.<br>**6.** El asesor **no tiene que buscarla**: está en «Hoy», con el motivo escrito, y la ficha 360 responde de dónde salió, qué pidió y cuándo aceptó el aviso.<br>**7.** El líder compara publicaciones y ve **por qué red** llegó cada persona.<br>**8.** El trato **se cierra diciendo por qué**: lista cerrada, fecha y tramo. El score **no** se recalcula.<br>**9.** El panel de desenlaces: por motivo, por red, y **qué score tenían al cerrarse**. Más el contador del reentrenamiento. | **Nunca pulsar en silencio.** Cada paso tiene su frase en el guion cronometrado.<br>**El paso 0 es obligatorio:** hacer un envío de prueba antes de empezar, o la primera puntuación tarda **más de 3 s** en lugar de 286 ms mientras todos miran. |
| **7:30 – 8:45**<br>*(1.25 min)* | **Calidad, seguridad y operación** | • **1743 pruebas** de backend (94 % de cobertura) y **748** de cliente, todas en verde.<br>• **10 trabajos** de integración continua, **59 controles** de configuración peligrosa y **siete guardas de propiedades** que fallan cuando el sistema pierde una defensa aunque ninguna prueba se rompa.<br>• Y cada corrección pasó su **arnés de reintroducción**: se vuelve a escribir el defecto y se exige que algo se ponga rojo. Una guarda que nadie ha podido poner en rojo no es una guarda.<br>• Autenticación real con JWT y revocación inmediata; **autorización sobre el dato**: un asesor solo ve su cartera, y un prospecto ajeno responde 404.<br>• Imágenes fijadas por huella, copias con **prueba de restauración**, derechos del titular comprobados tabla por tabla. | Si hay que recortar la exposición, se recorta **aquí**, no en la demostración: esto se puede contestar en preguntas y la demostración, no. |
| **8:45 – 10:00**<br>*(1.25 min)* | **Lo que se negó a hacer, y cierre** | • **No se reentrenó el modelo** con los canales nuevos: no hay desenlaces reales, y el capítulo 30 construyó justamente el mecanismo para tenerlos.<br>• **No se inventó el peso de los motivos** ni se proyectaron ingresos.<br>• **No se publica un modelo** cuyo intervalo de confianza no alcance el umbral, aunque su estimación puntual lo supere.<br>• El trabajo futuro está en un solo documento, con **de qué depende cada punto**.<br>• Agradecimiento al sínodo. | Este bloque es el que distingue un proyecto terminado de uno abandonado. Decirlo con seguridad, no como disculpa. |

**Dónde está cada cosa si el sínodo la pide:**

| Pregunta previsible | Documento |
| :--- | :--- |
| «Enséñeme el detalle de la demostración» | `docs/Guion_Cronometrado_de_la_Demo.md` |
| «¿Qué queda por hacer?» | `docs/Congelacion_y_Trabajo_Futuro.md` |
| «¿Dónde está todo esto documentado?» | `docs/Memoria_Tecnica_Final_Lead_Scoring.md` (44 reportes compilados, 46 capítulos) |
| «¿Se ha probado con usuarios?» | `docs/Prueba_Con_Personas.md` — y la respuesta honesta es **todavía no**: Pregunta 20 |
| «¿Y si falla el día de la demostración?» | `docs/Si_Algo_Falla.md` — tabla de síntoma → qué mirar → qué hacer |
| «¿Quién puede seguir esto después?» | `AGENTS.md` en la raíz, y `docs/Informe_Tecnico_de_Residencia.md` para las cifras |

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

### Pregunta 11: El ROC-AUC de 0.9469 parece muy alto. ¿Es creíble?
**Respuesta Modelo:**
> *"No como métrica de negocio, y es importante que lo diga yo antes de que lo pregunte el
> sínodo.
>
> El modelo se entrena con datos **sintéticos** cuya etiqueta `converted` se genera con una
> fórmula conocida a partir de las mismas variables, más ruido gaussiano. El 0.9469 mide,
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
> | Ordenar por una sola columna (`days_since_last_activity`) | 0.9053 |
> | Heurístico ICP, sin modelo | 0.8950 |
> | **Modelo entrenado** | **0.9469**  *(IC 95 % [0.9275, 0.9635])* |
>
> El número que importa no es el 0.95: es que **ordenar la lista por una columna ya da
> 0.91**. El aporte real de todo el pipeline de Machine Learning es de **+0.0519** sobre lo
> que el sistema haría sin modelo, **con un intervalo de confianza del 95 % de [0.0296,
> 0.0761]** calculado con bootstrap pareado —las mismas filas para el modelo y para la
> regla en cada réplica—. Esa es la cifra que defiendo, y por eso el gate de calidad mide
> también el aporte y no solo el ROC-AUC: el umbral de 0.82 no distinguía nada, porque la
> regla trivial ya lo superaba.
>
> Y desde el Capítulo 24 publicar exige que el **límite inferior** de los dos intervalos
> alcance su umbral, no la estimación puntual. Con ese criterio, una cohorte sintética de
> 1000 prospectos con un aporte de +0.028 e intervalo [-0.002, +0.059] **no se publica**,
> aunque su ROC-AUC tenga el límite inferior en 0.91.
>
> Sostener el 0.94 como logro comercial habría sido más lucido y no habría resistido esta
> misma pregunta. Los Capítulos 12 y 24 lo desarrollan."*

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

---

## 3. Las Diez Preguntas Incómodas (17 – 26)

Las de la sección 2 preguntan **cómo está hecho** algo. Estas preguntan **por qué falta**
algo, y son las que de verdad se pueden contestar mal.

La regla para las diez es la misma: **decir primero que sí falta**, después por qué, y
después qué hay construido alrededor del hueco. Una respuesta que empieza justificándose
suena a excusa aunque sea verdad; una que empieza reconociendo el hueco tiene permiso para
explicarlo.

Y una advertencia general: **ninguna de las diez se arregla el día antes**. Si el sínodo
encuentra una que no está en esta lista, la respuesta honrada es «no lo había pensado, y
tiene razón», no una improvisación.

---

### Pregunta 17: El proyecto se llama «del post de LinkedIn al prospecto puntuado». ¿Por qué el sistema no lee LinkedIn?
**Respuesta Modelo:**
> *"Porque leer LinkedIn exige una cuenta que el proyecto no tiene, y fingir que la tiene
> habría sido peor que no tenerla.
>
> Concretamente hacen falta dos productos de LinkedIn, **Lead Sync** y **Sign In with
> LinkedIn**, y los dos pasan por una aplicación aprobada en LinkedIn Developer. Una
> estadía sin presupuesto y sin la empresa en el proceso de aprobación no los consigue.
>
> **Lo que sí hay** es el conector `linkedin-lead-gen`, con su firma HMAC y su ingesta
> idempotente, aceptando una forma **simplificada** de la carga. Y digo simplificada
> deliberadamente: no es el esquema `leadFormResponses` real. Está anotado como hueco
> abierto desde el capítulo 21 y sigue abierto. Conectar LinkedIn de verdad es contrastar
> su esquema completo y su firma contra lo que el conector acepta, o poner delante un
> traductor.
>
> **Y aquí está lo importante:** que no se lea LinkedIn no deja la historia coja, porque el
> camino que la demostración enseña no pasa por LinkedIn. Pasa por una **página de interés
> propia**, con su enlace de 128 bits, que es real, es completa y es la que de verdad
> atribuye la ficha a su publicación. LinkedIn es por donde se reparte el enlace, no por
> donde entran los datos.
>
> Dicho de otro modo: el sistema no depende de LinkedIn para funcionar. Depende de él para
> **una integración más**, que está diseñada y no conectada."*

---

### Pregunta 18: Añadió seis canales de difusión y un canal LinkedIn orgánico. ¿Por qué el modelo no los conoce?
**Respuesta Modelo:**
> *"Porque darles peso hoy sería inventármelo, y esa es exactamente la clase de decisión que
> este proyecto se ha pasado treinta capítulos evitando.
>
> El artefacto en producción conoce **«LinkedIn Ads»**, que es publicidad pagada. Un post
> orgánico no es publicidad pagada: se comporta distinto, llega a otra gente y no tiene por
> qué convertir igual. Los seis canales del capítulo 27 —WhatsApp, Facebook, X, Instagram,
> correo, enlace directo— tampoco existían cuando se entrenó.
>
> **Qué hace el sistema con ellos:** los trata como **canal desconocido**, es decir,
> **neutro**. No los penaliza ni los premia. Y quiero subrayar que neutro **no es cero**: un
> cero sería afirmar que ese canal no aporta nada, que es una afirmación sobre el mundo que
> nadie ha medido. Desconocido es la respuesta honrada.
>
> **Por qué no los añadí de todas formas.** Podría haber asignado un peso a ojo, y el
> sistema habría seguido funcionando y nadie lo habría notado. El problema es que seis meses
> después, cuando alguien leyera que WhatsApp vale 12 puntos, no habría forma de distinguir
> un número medido de un número inventado. Una constante escrita a ojo es indistinguible de
> una medición para quien lee el resultado.
>
> **Qué haría falta para cerrarlo.** Desenlaces reales de cada canal. Y el capítulo 30 se
> dedicó precisamente a construir el mecanismo que los recoge: cerrar un trato ahora exige
> decir cómo acabó y por qué, el panel cuenta cuántos casos hay y el sistema **avisa cuando
> se alcanza el mínimo**. No reentrena: avisa. Quien decide es una persona.
>
> Es lo que queda para la fase siguiente, y está escrito como tal en
> `docs/Congelacion_y_Trabajo_Futuro.md`, §4.1."*

---

### Pregunta 19: Usted genera datos sintéticos para entrenar el modelo. ¿Por qué no generó también desenlaces sintéticos y reentrenó?
**Respuesta Modelo:**
> *"Ésta es la pregunta que más me alegra que me hagan, porque la respuesta es la línea que
> separa un proyecto de ingeniería de una demostración bonita.
>
> **Sí generé datos sintéticos, y digo exactamente para qué sirven.** El conjunto de
> entrenamiento son 3000 filas con semilla 42, y su etiqueta `converted` se calcula con una
> fórmula conocida a partir de las propias variables más ruido gaussiano. Por eso el
> ROC-AUC de 0.9469 **no mide el negocio**: mide que el modelo es capaz de reaprender la
> regla del generador. Verifica que el pipeline está íntegro, y para eso es legítimo.
>
> **Reentrenar con desenlaces sintéticos sería otra cosa completamente distinta.** El
> entrenamiento sintético responde «¿funciona la maquinaria?». Un reentrenamiento con
> desenlaces inventados respondería «¿qué prospectos convierten en PluriOne?», y la
> respuesta saldría de una fórmula que escribí yo. Sería un modelo que aprende mis
> suposiciones sobre el negocio y me las devuelve con cuatro decimales y aspecto de
> evidencia. El asesor que lo usara estaría siguiendo mi opinión creyendo que sigue un dato.
>
> **Y ahora sí existe el camino para llenarlo de verdad.** El capítulo 30 hizo que cerrar un
> trato exija decir cómo acabó, por qué motivo —de una lista cerrada, sin texto libre— y qué
> día. El panel cuenta cuántos casos utilizables hay contra los mínimos: **200 ejemplos, 50
> de cada clase**.
>
> **Lo que sí hice para que el camino no se pudra mientras tanto**, que creo que es la parte
> defendible: el pipeline recorre el bucle entero en **cada ejecución del CI**, sobre una
> base desechable, con desenlaces sembrados —`ensayo_del_bucle.py`—. Comprueba que el
> extractor funciona, que la etiqueta se lee del desenlace y no del estado, que el motivo
> viaja como contexto y **no** como variable del modelo, y que ningún prospecto aún en el
> embudo se cuenta como perdido. Todo eso está probado. Lo único que falta son las filas, y
> las filas no se inventan.
>
> Añado una cosa más, porque demuestra que la línea se ha respetado hasta el final: los
> cierres anteriores al capítulo 30 **no tienen motivo**, y la migración no se lo inventó.
> El manifiesto del dataset los cuenta aparte. Es la merma que cuesta no inventar, y está
> medida."*

---

### Pregunta 20: ¿Se ha probado el sistema con usuarios reales?
**Respuesta Modelo:**
> *"No. Y es la entrada que más tiempo lleva abierta en este proyecto, así que prefiero
> decirla yo.
>
> **Lo que sí está hecho:** el guion por papel con las tareas de los cuatro roles escritas
> **sin decir dónde pulsar** —si la tarea dice dónde pulsar, la prueba ya no mide nada—, las
> cuatro hojas de observación, el preparador que deja la base sembrada y un ensayo
> automático que recorre los nueve pasos y los cronometra. Está todo en
> `docs/Prueba_Con_Personas.md`.
>
> **Lo que ninguna prueba automática puede decir**, y por lo que la sesión sigue pendiente:
> si marketing, al pedirle el texto de WhatsApp, contesta que los dos enlaces son el mismo
> —si lo dice, el informe por red es inexplicable por muy exactos que sean sus números—; o
> si el asesor, al entrar, **lee** su bandeja o se va a «Prospectos» por costumbre.
>
> **Ocho atascos salieron de ensayos propios y siete están corregidos**, así que el guion no
> está sin probar; está probado sin nadie delante, que es distinto y hay que decirlo así.
>
> **Y hay una cosa más, que es lo más cerca que se ha estado de la respuesta.** El 5 de
> octubre recorrí la historia entera en el navegador con los tres papeles y con un teléfono,
> como quien la usa por primera vez. Aparecieron **siete defectos** que la suite entera no
> veía, y los siete de la misma forma: una regla escrita una vez, con su motivo al lado,
> aplicada en uno solo de los sitios que la necesitaban. Ninguno **falla**: el embudo del
> tablero enseñaba `NEW` y `QUALIFIED` teniendo la traducción escrita desde el capítulo 29; el
> botón «Cerrar sesión» de la pantalla de alta del segundo factor era blanco sobre blanco,
> 1,03:1, y es la única salida de la única pantalla que ve una cuenta de administración; y la
> puerta pública servía su JavaScript como `immutable` **un año**, de modo que un visitante no
> podía recibir una corrección ni recargando. Los siete están corregidos con su guarda.
>
> Eso no sustituye a la sesión con personas —sigo siendo yo, y conozco el sistema—, pero sí
> dice una cosa con números: **mirar la pantalla encuentra una clase de defecto que ninguna
> suite alcanza**, y son 1743 pruebas las que no los vieron."*
>
> Y hay un error del que aprendí algo: el capítulo 28 dio por cerradas dos notas de
> usabilidad y solo una lo estaba. Al líder le di ver los prospectos calientes que se
> enfrían, que es **otra pregunta distinta** de cuántos esperan a que los repartan. Lo dejé
> escrito en el reporte, porque el error no fue de código: fue dar por resuelto un síntoma
> parecido al anotado, que es la forma más fácil de cerrar una observación de usabilidad sin
> haberla mirado."*

---

### Pregunta 21: ¿Tiene segundo factor de autenticación? Durante meses no lo tuvo.
**Respuesta Modelo:**
> *"Lo tiene desde el **capítulo 35**, y durante quince capítulos no lo tuvo a propósito. Las
> dos mitades de esa frase importan.
>
> **Por qué tardó.** Un TOTP para administración exige cinco cosas, y la quinta es la que
> nadie recuerda: alta con código de verificación, códigos de recuperación, un paso más en el
> login del cliente, auditoría de cada uso… y **una respuesta para quien pierde el teléfono
> siendo el único administrador**, que es justamente la cuenta que no puede quedarse fuera.
> Añadir la verificación sin eso produce un sistema al que nadie puede entrar, y eso no es
> más seguro: es una pérdida total con aspecto de mejora.
>
> **Cómo está hecho, y la decisión de la que estoy más conforme:** el secreto **no se
> guarda**. En la base hay una **sal** aleatoria por cuenta, y el secreto se deriva de ella y
> de `SECRET_KEY`, que vive en el entorno. Quien se lleve un volcado de la tabla se lleva
> sales, y con una sal sola no se genera ni un código: no hay nada que cifrar porque no hay
> nada guardado. El precio está escrito —rotar `SECRET_KEY` invalida todas las altas— y es un
> precio que se paga a sabiendas.
>
> El alta **no activa** hasta que se comprueba un código, así que quien se equivoque al
> escanear el QR no se queda fuera; el desafío del login es de un tipo propio y **no sirve
> como sesión**; un código no vale dos veces dentro de su ventana; los diez códigos de
> recuperación se guardan como **resumen** y son de un solo uso; y **la última cuenta de
> administración con el factor activo no puede quitárselo**, que es la salvaguarda que cierra
> el caso del teléfono perdido. El TOTP está escrito sobre la biblioteca estándar y comprobado
> contra los **18 vectores oficiales del RFC 6238**.
>
> Y lo que ya había antes sigue estando, porque cubre otra superficie: un segundo factor
> protege del robo de contraseña; la revocación inmediata por `token_version` protege del robo
> de **sesión**, que es un caso distinto."*

---

### Pregunta 22: El sistema dice al asesor qué hacer hoy, pero no le avisa por ningún sitio. ¿No es eso inútil?
**Respuesta Modelo:**
> *"Es una limitación real, y la razón de que quede fuera no es solo que falte una cuenta de
> correo.
>
> Son tres cosas. Una, sí: hace falta una cuenta y una dirección verificada. Dos: hace falta
> una política de qué ocurre cuando un aviso rebota, porque un canal de salida que falla en
> silencio es peor que no tenerlo. Y tres, la que de verdad pesa: **un aviso que sale del
> sistema saca de la aplicación el nombre de una persona que aceptó un aviso de privacidad
> para otra cosa**. Eso no es un problema de infraestructura, es una decisión de quien
> responde del tratamiento de datos, y no me corresponde tomarla.
>
> **Lo que hay mientras tanto** no es nada: son seis reglas que producen tareas con su
> motivo escrito y su plazo, una bandeja «Hoy» que las ordena, y una campana de avisos para
> el líder. Todo dentro del panel, que es donde el asesor ya entra cada mañana.
>
> Y añado la limitación de verdad, que no es el canal: **nadie ha vivido una semana con la
> bandeja**. Si las seis reglas producen la cantidad adecuada de trabajo —ni tan poco que
> sobre, ni tanto que se ignore— solo se sabe usándola varios días seguidos. Por eso los
> plazos se dejaron configurables y no fijos en el código."*

---

### Pregunta 23: Si el modelo no está validado con datos reales y nada está en producción, ¿qué ha demostrado exactamente esta estadía?
**Respuesta Modelo:**
> *"Que el camino completo existe, funciona de punta a punta y **se niega a inventar** en
> cada punto donde habría sido más cómodo hacerlo. Lo diría con tres pruebas concretas.
>
> **Primera: el camino es completo y verificable.** De un post en una red social a un dato
> de entrenamiento, pasando por la página de captación, la puntuación, la atribución por
> red, la bandeja del asesor y el cierre con su motivo. No es un diagrama: se recorre entero
> en menos de dos segundos de servidor y el ensayo lo comprueba paso por paso.
>
> **Segunda: está defendido contra sí mismo.** 1743 pruebas de backend con 94 % de
> cobertura, 748 de cliente, diez trabajos de integración continua. Y algo que considero más
> valioso que la cobertura: **siete guardas que comprueban propiedades, no casos**. Un
> campo de texto libre nuevo en el formulario de cierre no rompería ninguna prueba
> existente, porque nadie lo enviaría; la guarda falla en cuanto ese campo existe. Y las
> guardas no se dan por buenas porque pasen: se validan **reintroduciendo defectos a
> propósito** y comprobando que los cazan. La del motor de reglas se midió con 31 defectos
> inyectados; la del desenlace, con 18, detectados los 18, y con la huella de cada archivo
> verificada al restaurarlo.
>
> **Tercera, y es la que defiendo de verdad: el sistema sabe lo que no sabe.** Un canal que
> no conoce lo trata como desconocido, no como cero. Unos ingresos que faltan viajan como
> ausentes, no como 100 000. Un prospecto todavía en el embudo se excluye del entrenamiento
> en lugar de contarse como perdido. Un modelo cuyo intervalo de confianza no alcanza el
> umbral no se publica, aunque su estimación puntual lo supere. Y un cierre sin motivo no se
> puede registrar.
>
> Un sistema que hubiera rellenado todos esos huecos habría dado una demostración más
> vistosa y habría empezado a mentir el primer día que alguien se fiara de él. Lo que he
> demostrado es que sé dónde está esa línea y que la respeté incluso cuando cruzarla no lo
> habría notado nadie."*

---

### Pregunta 24: ¿Qué pasa con este sistema cuando usted se vaya?
**Respuesta Modelo:**
> *"Está pensado para eso, y lo puedo enseñar en cuatro puntos.
>
> **El proyecto está congelado, con criterio escrito.** Desde el 24 de septiembre solo entran
> correcciones de fallos, y `docs/Congelacion_y_Trabajo_Futuro.md` define qué cuenta como
> fallo y qué cuenta como funcionalidad, con tres casos frontera ya resueltos de antemano
> para que nadie tenga que discutirlos.
>
> **El trabajo futuro está en un solo documento y agrupado por de qué depende**, que es lo
> único que decide si algo se puede hacer: cuentas externas, datos reales, decisiones que no
> son técnicas, o deuda de ingeniería que se puede atacar hoy. Y lleva una sección de **lo
> que no se va a hacer, con el motivo**, para que nadie vuelva a plantear cada año las
> mismas discusiones ya zanjadas.
>
> **Y la parte de ese documento que sí dependía de nosotros ya está hecha.** La sección de
> deuda que se podía atacar hoy tenía ocho puntos; quedan dos, y los dos esperan a que un
> sistema externo mande un identificador o a que haya una cuenta de WhatsApp conectada. Lo
> demás se cerró en el capítulo 32, que es el Reporte 30: ninguna fila de la política de
> conservación se quedó sin plazo, la ficha dejó de suponer el país, y lo que el CI ejecuta
> va fijado por huella igual que lo que descarga.
>
> Ese capítulo abrió un punto nuevo, y merece contarse porque es la clase de hallazgo que no
> sale de una prueba: al quitar el país supuesto se comprobó si un asesor podía corregir a
> mano las fichas que la migración no podía tocar, y resultó que **ningún campo de la ficha
> se podía vaciar** una vez escrito. No es que respondiera que no: respondía 200 y el dato
> seguía ahí. Se cerró en el capítulo 33, el Reporte 31, y con él §6.1 vuelve a no tener
> nada que dependa de nosotros.
>
> **Todo lo que se decidió está explicado, no solo hecho.** **Cuarenta y cuatro reportes** para
> 46 capítulos, y cada uno dice por qué se tomó cada decisión y qué se descartó. La memoria
> técnica los compila con índice y anclas, y hay una prueba que falla si un reporte existe y no
> entró en la memoria: los capítulos 22 a 24 se pegaron a mano una vez, salieron sin ancla y la
> siguiente regeneración los habría borrado sin avisar.
>
> **Y hay dos documentos escritos para quien venga, no para el sínodo.** `AGENTS.md`, en la
> raíz, dice en una página que el proyecto está congelado, cómo se levanta —un solo modo—, qué
> guardas hay y cómo se prueban, dónde vive cada cosa y las siete cosas que se aprendieron por
> las malas. Y `docs/Si_Algo_Falla.md` está escrito para quien **no programa**: encender,
> apagar, reiniciar el túnel, qué hacer cuando se pierde la dirección pública, restaurar un
> respaldo paso a paso, y una tabla de «síntoma → qué mirar → qué hacer» con diecisiete
> entradas. Todas sus órdenes se ejecutaron contra la pila antes de escribirlas, y una de ellas
> estaba **mal** la primera vez: sin cuatro variables de entorno, restablecer las cuentas en la
> pila de Docker genera contraseñas aleatorias y deja a todo el mundo fuera. Se descubrió
> probándola, que es exactamente para lo que se prueba un documento de operación.
>
> **Desde el 6 de octubre la congelación es definitiva**: solo entra lo que impida levantar la
> pila o enseñar la demostración. No queda ningún capítulo abierto, y eso también es una
> decisión y está escrita con fecha.
>
> **Y el sistema se defiende solo mientras nadie lo mire.** Las guardas del CI no comprueban
> que las funciones sigan dando el resultado correcto: comprueban que el sistema no ha
> perdido una defensa. Si alguien dentro de un año añade un campo de texto libre al cierre,
> o hace que cerrar un prospecto recalcule su puntuación, el pipeline se pone en rojo y el
> mensaje dice exactamente qué se perdió y por qué importaba. Eso es lo que queda cuando yo
> ya no estoy para explicarlo."*

---

### Pregunta 25: La página pública funciona con una dirección que caduca. ¿Eso no invalida la demostración?
**Respuesta Modelo:**
> *"Caduca, y hay que decirlo antes de que lo pregunten. Lo que invalidaría la demostración
> sería no saberlo.
>
> **Qué es.** La página de interés sale a internet por un **túnel gratuito** de Cloudflare. No
> hace falta cuenta, ni tarjeta, ni abrir ningún puerto del router: el túnel sale **desde** la
> máquina hacia fuera, así que nadie entra por el router. A cambio, la dirección es prestada
> —`https://algo-algo-algo.trycloudflare.com`— y **cambia en cada arranque**.
>
> **La consecuencia honesta, que es la que importa:** un post publicado en LinkedIn con una de
> esas direcciones tiene un enlace **muerto** en cuanto se reinicia el túnel. El post sigue
> ahí; el enlace no lleva a nada. Por eso esto sirve para **enseñar** la página, probarla con
> personas y ver la tarjeta de vista previa en una red de verdad; la difusión en serio —publicar
> y dejarlo semanas— espera a un dominio propio.
>
> **Y el sistema no finge que no pasa.** La pantalla de Publicaciones **marca** los enlaces ya
> repartidos que no llevan aquí, y avisa cuando la dirección configurada dejó de responder. Eso
> es lo que separa una limitación documentada de un fallo: el software sabe en qué estado está
> y lo dice.
>
> **Lo que costaría cerrarlo del todo** son dos cosas que no son de programación: un dominio y
> un certificado. La dirección pública es **un solo ajuste** del entorno desde el capítulo 34
> —`PUBLICACIONES_URL_BASE`—, así que pasar a un dominio propio es cambiar un valor y
> reiniciar un servicio. Está escrito así a propósito, para que esa migración no sea un
> capítulo.
>
> Y se comprobó **desde fuera de la red**, no desde esta máquina: por esa puerta se publican 5
> rutas y se niegan las 25 comprobadas. El panel y la API de gestión no existen ahí."*

---

### Pregunta 26: El sistema atiende el derecho de supresión, pero suprimir aquí no suprime en el CRM. ¿No es eso un derecho a medias?
**Respuesta Modelo:**
> *"Lo es, y la parte que falta **no la puede hacer el software**. Prefiero explicar por qué, y
> qué se hizo para que nadie se lleve una sorpresa.
>
> **Qué sí hace.** La supresión recorre el mapa completo del esquema tabla por tabla —no una
> lista escrita a mano— y borra a la persona de todas. Queda constancia de que se hizo y de
> quién la pidió, **sin volver a guardar los datos de la persona borrada**: un asiento que
> dijera «suprimida Ana Pérez el día tal» sería conservar precisamente lo que se pidió borrar.
> Y la exportación previa dice, campo por campo, qué consta y de dónde llegó.
>
> **Qué no hace, y es la mitad incómoda.** El CRM es otro sistema, con su propio responsable.
> Aquí no hay credenciales para borrar allí, y no las habría aunque se quisiera: un sistema que
> puede borrar en otro es una superficie de ataque nueva. Peor que eso: una entrega posterior
> del CRM **vuelve a crear** a la persona, porque el webhook crea fichas que no existen. No es
> solo que los datos sigan allí; es que **volverán**.
>
> **Lo que se podría hacer y no se ha hecho, con el motivo.** La huella con clave del correo
> permitiría reconocer a una persona suprimida y **rechazar** su ingesta. Técnicamente está al
> alcance. Bloquear una entrada de negocio para siempre es una decisión que nadie ha tomado, y
> tomarla yo solo, en un capítulo técnico, sería la clase de decisión que no me corresponde.
> Está escrita como §5.3 de la congelación, en la sección de **decisiones que no son técnicas**.
>
> **Y lo que sí se hizo cuando se vio el hueco**: la advertencia dejó de vivir solo en un
> documento y en un campo del JSON de exportación, que no los lee quien atiende una petición de
> borrado. Desde el capítulo 38 la pantalla de derechos lo dice **dos veces** —al confirmar y al
> terminar— y dice la mitad que cambia lo que hay que hacer: que volverán. Las copias de
> seguridad conservan a la persona hasta 14 días, y eso también está dicho: no se editan
> volcados.
>
> Un derecho a medias documentado y visible en la pantalla es peor que uno completo y mejor que
> uno a medias que nadie sabe que lo está."*

---

## 4. Tres cosas que no hay que hacer en la defensa

1. **No prometer un reentrenamiento trimestral.** Entre puntuar un prospecto y conocer su
   desenlace pasan semanas o meses; el calendario no lo permite, y decirlo es peor que la
   limitación misma.
2. **No presentar el ROC-AUC de 0.9469 como logro comercial.** Es la trampa más fácil de
   esta defensa: la cifra es cierta y la conclusión que sugiere, no. Decir siempre qué mide
   **antes** de decir cuánto vale.
3. **No dar por probado con usuarios lo que está probado con pruebas.** «Tiene pruebas» y
   «se ha probado con alguien» son cosas distintas, y el proyecto lleva cinco capítulos
   distinguiéndolas por escrito. Confundirlas en voz alta delante del sínodo desharía ese
   trabajo en una frase.
