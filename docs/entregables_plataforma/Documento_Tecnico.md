# Informe técnico de la residencia — Sistema Inteligente de Lead Scoring

**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Periodo:** Estadía Profesional, 2026
**Cierre técnico:** 6 de octubre de 2026 — congelación definitiva
**Capítulos:** 46 · **Reportes:** 44 · **Memoria técnica:** compilada con índice y anclas

> **Qué es este documento y qué no.** Es el resumen técnico con las **cifras reales del
> cierre** y las preguntas difíciles con su respuesta honesta. No sustituye a la memoria
> técnica —que son los 44 reportes compilados— ni al documento de congelación, que es el que
> dice qué falta y por qué. Los papeles institucionales de la residencia viven en
> `docs/docs_residencias/` y no los mantiene este repositorio: si hace falta este contenido
> ahí, se traslada a mano.

---

## 1. El problema, en dos frases

PluriOne atendía sus solicitudes de prospección en orden de llegada y sin calificar: **36
horas** de latencia hasta el primer contacto y una conversión de MQL a SQL del **12 %**. El
ejecutivo comercial no tenía forma de saber a quién llamar primero, ni de dónde había salido
la persona que tenía delante.

La restricción de ingeniería fue igual de concreta: **coste recurrente de 0 USD**, sin cuentas
externas nuevas, y todo tiene que funcionar en una máquina.

---

## 2. Las cifras del cierre

Todas medidas el 6 y 7 de octubre de 2026 sobre el árbol congelado, no estimadas.

### Calidad

| | |
| :--- | :--- |
| Pruebas del servidor | **2093 pasan**, 2 omitidas |
| Cobertura del servidor | **99,11 %** contando ramas —99,37 % de sentencias · 97,88 % de ramas—, sobre suelos de 99,1 y 97,8 que el CI hace fallar |
| Pruebas del cliente | **748** en 45 archivos |
| Cobertura del cliente | 96,65 % sentencias · 91,75 % ramas · 98,52 % funciones · 98,68 % líneas, sobre suelos de 96,6 / 91,7 / 98,5 / 98,6 |
| Trabajos de integración continua | **10** |
| Controles de configuración peligrosa | **61** |
| Guardas de propiedades | **7**, cada una con su arnés de reintroducción |
| Análisis estático | `ruff`, `eslint` (con las 34 reglas de accesibilidad) y `npm run build`, sin avisos |

Las dos cifras de cobertura no significan lo mismo y conviene decirlo: la del servidor es una
sola, la del cliente son cuatro con suelo independiente, porque una cobertura de sentencias
alta con ramas bajas describe una suite que ejecuta el código y no lo decide.

### El modelo publicado

| | |
| :--- | :--- |
| Algoritmo | `GradientBoostingClassifier` con calibración isotónica (`CalibratedClassifierCV`) |
| ROC-AUC | **0,9469** · IC 95 % **[0,9275, 0,9635]**, por bootstrap de 2000 remuestreos |
| Aporte sobre el heurístico ICP | **+0,0519** · IC 95 % **[0,0296, 0,0761]**, bootstrap **pareado** |
| F1 · exactitud · Brier | 0,8405 · 0,8767 · 0,0872 |
| Umbrales para publicar | ROC-AUC ≥ 0,82 **y** aporte ≥ 0,01 **por el límite inferior del intervalo** |
| Líneas base sobre el mismo conjunto | azar 0,5 · ordenar por una sola columna 0,9053 · heurístico ICP 0,8950 |
| Datos | **3000 filas sintéticas** (2400 entrenamiento / 600 prueba), semilla 42, vector de variables v2 |
| Huella del conjunto | `a4a84ad4…50dff3` · huella del artefacto `98ed8bd1…9d2a63` |

> **La cifra que se defiende no es 0,9469; es +0,052.** El 0,9469 se mide sobre datos
> sintéticos cuya etiqueta se genera con una fórmula conocida a partir de las propias
> variables más ruido: verifica que el **pipeline está íntegro** —que las variables llegan,
> que el preprocesado no las corrompe, que la calibración funciona—, no el rendimiento
> comercial. Sobre ese mismo conjunto, **ordenar por una sola columna** da 0,9053. Lo único
> que dice algo del modelo es cuánto aporta **sobre el heurístico**, y eso es +0,0519 con un
> intervalo que no toca el cero.

La fórmula del score, con el decaimiento:

$$S_{\text{final}} = 0.60 \times S_{\text{ML}} + 0.40 \times S_{\text{Heurístico}} \times \gamma(\Delta t), \qquad \gamma(\Delta t) = (0.5)^{\Delta t / 14}$$

### Lo construido, por bloques

| Bloque | Qué quedó |
| :--- | :--- |
| Pipeline de ML | Entrenamiento reproducible por semilla, con umbrales que **impiden publicar** un artefacto peor; registro de modelos con procedencia; perfil de referencia atado por huella a su artefacto |
| Scoring | Híbrido ML + heurístico ICP con decaimiento continuo; una sola definición de las reglas, compartida con el pipeline; instantánea del vector en cada puntuación |
| Captación | Publicaciones con enlace propio de 128 bits, un enlace y un texto por red, código QR local, página de interés pública defendida (límite por IP y por publicación, campo trampa, misma respuesta exista o no el correo) |
| Ingesta | Cinco caminos de alta, todos por una sola pieza que escribe actividades; webhooks firmados con HMAC e idempotencia que distingue un reenvío hostil de un reintento |
| Agenda | Motor de seis reglas en una pasada diaria, tareas y avisos que **no salen del panel**, bandeja «Hoy», campana, escalado al líder |
| Reparto | Asignación automática y equitativa por carga abierta, con el tiempo sin recibir como desempate, asiento de bitácora con la regla y los candidatos (capítulo 46) |
| Cierre del bucle | Desenlace con motivo de lista cerrada, sin texto libre; dataset de realimentación etiquetado sobre la instantánea, sin fuga; contador del reentrenamiento |
| Seguridad | JWT con revocación inmediata por `token_version`, rotación verificable del refresco, contraseñas contra lista local **y** servicio público por rango, segundo factor TOTP con el secreto **derivado y no guardado**, autorización sobre el dato en el repositorio |
| Gobierno del dato | Migraciones versionadas con reversión probada, ninguna fila sin plazo de conservación, bitácora de solo lectura sin datos personales, exportación y supresión del titular tabla por tabla |
| Operación | Un solo modo de arranque con el entorno fuera del repositorio, imágenes fijadas por huella, copias con **prueba de restauración**, métricas y registro estructurado |
| Accesibilidad | Las nueve pantallas en nivel **AA de WCAG 2.1**, medido por `axe-core` desde la suite; contraste calculado leyendo la hoja de estilos; listas derivadas del código |

---

## 3. Cómo se trabajó, que es la parte transferible

Tres prácticas que no estaban en el plan y acabaron siendo el método:

**1. Cada capítulo abre la congelación para puntos nombrados y para ninguno más.** Desde el
24 de septiembre, un capítulo no es «mejorar esto»: es un punto del documento de trabajo
futuro, con su número, y lo que no esté en él no se toca. Eso es lo que impidió que el
proyecto creciera sin fin.

**2. Guardas de propiedades además de pruebas.** Una prueba comprueba un caso; una guarda
comprueba que el sistema no ha **perdido una defensa**. Son siete, corren en el CI con nombre
propio, y existen porque hay clases de defecto que ninguna prueba de caso alcanza: un reparto
que le da todo a una persona deja cada ficha con dueño; un umbral bajado a cero deja la guarda
existiendo y sin mirar nada.

**3. El arnés de reintroducción.** Después de corregir, se vuelve a escribir el defecto —uno a
uno, todas sus variantes— y se exige que algo se ponga rojo. **Una guarda que nadie ha podido
poner en rojo no es una guarda.** Las cuentas quedaron escritas capítulo a capítulo: 25 de 25,
23 de 23, 20 de 20. Y encontró cosas que nadie buscaba: tres capítulos seguidos descubrieron
guardas que medían bien **sobre un inventario escrito a mano**, y el defecto estaba siempre en
lo que la lista no incluía.

Lo que esas tres prácticas tienen en común es que no miden si el código funciona hoy: miden si
seguirá teniendo las mismas defensas cuando ya nadie recuerde por qué se pusieron.

---

## 4. Las preguntas difíciles, con la respuesta honesta

Están completas, con su argumento largo, en la [guía de defensa](../GUIA_DEFENSA_ORAL.md)
—veintiséis preguntas, de las cuales diez son de esta clase—. Aquí están las cinco que más se
van a preguntar, en corto.

### ¿Por qué el sistema no lee LinkedIn, si el proyecto se llama «del post de LinkedIn al prospecto puntuado»?

Porque leer LinkedIn exige una cuenta de empresa con la API de Lead Gen aprobada, y el
proyecto no la tiene. **Fingirla habría sido peor que no tenerla**: un conector contra un API
que nadie ha visto responder produce un sistema que funciona en la demostración y falla el
primer día real.

Lo que sí se hizo es la parte que **sí** depende de nosotros, y es la que de verdad cierra el
camino: el enlace propio por red, la página de interés que recoge los datos, la atribución de
por dónde llegó cada persona y el informe por red. El sistema no lee LinkedIn; **lee lo que
llega desde LinkedIn**, y eso es lo que el negocio necesitaba. El conector queda escrito como
un adaptador con su interfaz definida: el día que haya cuenta, es un archivo.

### ¿Por qué la dirección pública caduca?

Porque el túnel es **gratuito**: sale desde la máquina hacia fuera —sin cuenta, sin tarjeta y
sin abrir puertos del router— y a cambio la dirección es prestada y **cambia en cada
arranque**.

La consecuencia hay que decirla entera: **un post ya publicado con una dirección vieja tiene
un enlace muerto.** Por eso esto sirve para enseñar la página y probarla con personas, no para
difusión sostenida. Y el sistema no finge que no pasa: marca los enlaces repartidos que ya no
llevan aquí y avisa cuando la dirección configurada deja de responder. Cerrarlo del todo son
un dominio y un certificado, no código: la dirección pública es **un solo ajuste** del
entorno, así que la migración es cambiar un valor.

### ¿Por qué el modelo no conoce los canales nuevos?

Porque conocerlos significa **reentrenar**, y reentrenar exige desenlaces reales de prospectos
que llegaron por esos canales. No existen todavía: el primero llegó hace semanas.

Mientras no existan, un canal desconocido se trata como **desconocido, es decir neutro** —no
como un cero—, que es la única opción que no inventa nada. Y el sistema está preparado para el
día que existan: cada puntuación guarda la instantánea del vector, el panel de desenlaces
cuenta cuántos cierres utilizables hay y cuántos faltan para el mínimo (200 casos, 50 por
clase), y el monitor de deriva ya vigila el perfil de referencia. Lo que falta no es código:
es tiempo y conversiones.

### ¿Por qué no generó desenlaces sintéticos y reentrenó?

Porque habría sido **circular, y habría parecido un resultado**. La etiqueta sintética se
genera con una fórmula conocida a partir de las propias variables; entrenar sobre desenlaces
inventados con esa misma fórmula produce un modelo que acierta porque la respuesta estaba en
la pregunta, y un ROC-AUC que no significa nada presentado como si significara algo.

El capítulo 30 construyó precisamente lo contrario: la forma de recoger el desenlace **real**,
con motivo de lista cerrada, para que cuando haya datos se pueda entrenar sobre lo que pasó y
no sobre lo que se supuso. Decir «no reentrené» es más corto y más honesto que un número
fabricado.

### ¿Por qué suprimir aquí no suprime en el CRM?

Porque el CRM es otro sistema con su propio responsable, y aquí no hay —ni debería haber—
credenciales para borrar allí. Y hay una mitad peor: una entrega posterior del CRM **vuelve a
crear** a la persona.

Lo que sí hace la supresión: recorre el mapa completo del esquema tabla por tabla, no una
lista escrita a mano, y deja constancia de que se hizo **sin volver a guardar los datos de
quien se borró**. Lo que podría hacerse y no se ha hecho: reconocer por huella con clave a una
persona suprimida y **rechazar** su reingesta. Técnicamente está al alcance; bloquear una
entrada de negocio para siempre es una decisión que no corresponde a un capítulo técnico, y
está escrita como tal en la sección de **decisiones que no son técnicas**. Lo que sí se hizo al
ver el hueco: la advertencia salió del documento y entró en la pantalla, dos veces, diciendo la
mitad que cambia lo que hay que hacer —que volverán—.

---

## 5. Lo que no se hizo, y dónde está escrito

No es una lista de pendientes: es el inventario, clasificado **por de qué depende cada cosa**,
en [`Congelacion_y_Trabajo_Futuro.md`](../Congelacion_y_Trabajo_Futuro.md).

| Depende de | Ejemplos |
| :--- | :--- |
| **Cuentas externas** (§3) | LinkedIn, Calendly y WhatsApp no se leen; no se publica solo en ninguna red; la tarjeta de vista previa no se ha mirado en una red de verdad; las copias no salen de la máquina |
| **Datos reales** (§4) | El modelo no se reentrena; no hay deriva medible; los cierres anteriores al capítulo 30 no tienen motivo; **la sesión con personas sigue sin celebrarse** |
| **Decisiones que no son técnicas** (§5) | Los plazos de conservación no tienen valoración jurídica; suprimir aquí no suprime en el CRM; los motivos de pérdida no tienen peso; no hay previsión de ingresos |
| **Deuda de ingeniería** (§6) | Cinco de nueve huecos de la historia cerrados; **61 restos menores** anotados, numerados hasta el 81, de los que **16 se cerraron** en los capítulos siguientes y el resto queda con su medición y su motivo |

Y una sección de **lo que no se va a hacer, con el motivo**, para que las mismas discusiones
no se reabran cada año.

**Fuera del alcance técnico de este informe, y dicho con claridad:** la instalación en la PC
servidora **no está hecha ni ensayada**. Lo que está probado es esta instalación, en este
equipo, con Docker. Levantarla en otra máquina es un trabajo de operación que no se ha hecho.

---

## 6. Qué queda para quien siga

Tres documentos, en este orden:

1. **[`AGENTS.md`](../../AGENTS.md)** — las reglas: que está congelado y hasta dónde, cómo se
   levanta (un solo modo), qué guardas hay y cómo se prueban, dónde vive cada cosa, y las
   siete cosas que se aprendieron por las malas.
2. **[Si algo falla](../Si_Algo_Falla.md)** — para quien **no programa**: encender, apagar,
   reiniciar el túnel, qué hacer cuando se pierde la dirección pública, restaurar un respaldo
   paso a paso, las cuentas, y una tabla de «síntoma → qué mirar → qué hacer» con diecisiete
   entradas. Todas sus órdenes se ejecutaron contra la pila antes de escribirlas.
3. **[Congelación y trabajo futuro](../Congelacion_y_Trabajo_Futuro.md)** — qué falta y por qué.

Y lo que queda funcionando sin que nadie lo vigile: **las guardas del CI**. No comprueban que
las funciones den el resultado correcto; comprueban que el sistema no ha perdido una defensa.
Si alguien, dentro de un año, añade un campo de texto libre al formulario de cierre, hace que
cerrar un prospecto recalcule su puntuación, o escribe un color fuera de la paleta, el
pipeline se pone rojo y el mensaje dice **qué se perdió y por qué importaba**.

Eso es lo que queda cuando ya no hay nadie para explicarlo.
