# Manual de usuario — Sistema Inteligente de Lead Scoring

**Para quién es:** asesores comerciales, líderes comerciales y administradores de PluriOne. No requiere conocimientos técnicos.
**Dirección del panel (instalación de demostración):** <http://localhost:3000>

> Todos los datos del sistema de demostración son **sintéticos**. Ningún nombre, correo ni empresa corresponde a un cliente real.

---

## 1. Qué hace el sistema

Cada vez que llega una persona interesada, el sistema:

1. crea su **ficha** y le calcula una **puntuación de 0 a 100**;
2. la clasifica en **HOT** (75 o más), **WARM** (de 45 a 74) o **COLD** (menos de 45);
3. la **reparte** al asesor con menos cartera abierta;
4. le crea al asesor una **tarea para hoy**, con el motivo escrito;
5. cuando el trato se gana o se pierde, guarda el **desenlace** con su motivo, para que el modelo aprenda con datos reales.

La puntuación **baja sola con el tiempo** si no hay actividad: el interés de una persona se enfría con una vida media de 14 días.

---

## 2. Entrar al sistema

1. Abra <http://localhost:3000>.
2. Escriba su **correo** y su **contraseña**.
3. Si su cuenta tiene segundo factor (administradores), escriba el código de 6 dígitos de su aplicación autenticadora.
4. Si el sistema le pide **cambiar la contraseña**, hágalo: mínimo 12 caracteres (a partir de 16 basta una frase larga). Se rechazan contraseñas conocidas y las que contienen su nombre o su correo.

La sesión se renueva sola; si no hace nada durante mucho tiempo, vuelve a pedirle los datos. **Cerrar sesión** la cierra en todos sus dispositivos.

### Roles

| Rol | Qué ve y qué puede hacer |
| :--- | :--- |
| **Asesor comercial** | Solo **sus** prospectos: consultar, dar de alta, editar, registrar actividades, cerrar |
| **Líder comercial** | Toda la cartera; reasignar; borrar; campañas; publicaciones e informes; desenlaces |
| **Administrador de TI** | Todo lo anterior, más cuentas de usuario, bitácora de auditoría, derechos del titular |

Si una ficha existe pero es de otra persona, el sistema contesta como si **no existiera** — es intencional.

---

## 3. Las pestañas

La barra superior muestra las pestañas según su rol.

### 3.1 Hoy

Es la pantalla de inicio del asesor: **qué hacer hoy y por qué**.

- Cada tarea muestra el **motivo** (por ejemplo, «ficha nueva sin primer contacto»).
- Un clic abre la **ficha 360°** del prospecto.
- **«Ya está»** cierra la tarea.
- La **campana** avisa de lo nuevo. Los avisos no salen del panel: no hay correos ni mensajes externos.

Las tareas las genera una pasada **diaria** del sistema: una ficha creada hoy puede no tener tarea hasta la pasada siguiente.

### 3.2 Dashboard

Resumen analítico: totales por categoría, distribución de puntuaciones, embudo de conversión (MQL → SAL → SQL), rendimiento por campaña y un **contador de fichas «sin asesor»**. Ese contador debe estar en **cero**: cuenta solo lo que el reparto automático no pudo colocar.

### 3.3 Prospectos

La matriz de toda su cartera.

| Acción | Cómo |
| :--- | :--- |
| Buscar y filtrar | Barra de búsqueda y filtros por categoría, etapa y asesor |
| Ordenar | Clic en el encabezado de la columna |
| Dar de alta | Botón de alta de prospecto («Registrar Nuevo Prospecto»); complete el formulario y guarde. El sistema lo puntúa y lo reparte al instante |
| Ver el detalle | Clic en la fila: abre la **ficha 360°** |
| Reasignar (líder) | En la ficha, el selector de asesor |
| Registrar una actividad | En la ficha 360°, sección de actividades (llamada, reunión, descarga, visita, solicitud de demo…) |

**Ficha 360°.** Reúne: datos de la persona, **puntuación y categoría**, la **explicación** del puntaje en lenguaje natural con tácticas sugeridas, el historial de actividades, y la tarjeta **«Llegó por»**: de qué publicación salió, por qué red llegó, qué pidió y cuándo aceptó el aviso de privacidad.

### 3.4 Simulador

Permite probar «¿qué puntuación tendría un prospecto con estas características?» sin crear ninguna ficha. Cambie cargo, sector, tamaño y actividad con los deslizadores y el resultado se recalcula.

### 3.5 Publicaciones

Para marketing y líderes.

1. **Nueva publicación:** nombre, canal (LinkedIn), texto del post y a quién va dirigido. Guardar.
2. El sistema genera solo el **enlace** de la publicación (identificador de 128 bits; no se elige ni se adivina).
3. **Compartir en redes:** abra la difusión y copie el texto de cada red. **Cada red tiene su propio enlace etiquetado** y el texto viene recortado a lo que cabe en ella (280 caracteres en X).
4. El **código QR** de la publicación se genera en el panel y se puede descargar.
5. **Informe de la publicación:** perfiles recibidos, avance de etapa, puntuación media, y **cuántos llegaron por cada red**.
6. **Comparativa:** enfrenta dos o más publicaciones.

> **Lectura honesta del informe por red.** Dice por dónde se repartió el enlace que se abrió, no dónde estaba la persona. Quien recibe por WhatsApp un enlace copiado de LinkedIn cuenta como WhatsApp.

### 3.6 Desenlaces

Solo líderes y administradores. Totales de **toda la casa**: ganados y perdidos por motivo, por publicación y por red; la categoría que tenía cada prospecto **al cerrarse** (la respuesta a «¿el score acertaba?») y el **contador del reentrenamiento**: cuántos cierres utilizables hay y cuántos faltan (mínimo 200 casos, 50 de cada clase). El sistema avisa cuando se alcanza; **no reentrena solo**.

### 3.7 Administración

Líder y administrador.

| Función | Quién |
| :--- | :--- |
| Alta, edición, cambio de rol, baja y reactivación de cuentas | Administrador |
| Restablecer la contraseña de una cuenta | Administrador |
| Consultar la **bitácora de auditoría** (quién hizo qué, sobre qué, desde dónde, con qué resultado) | Administrador |
| **Derechos del titular:** exportar o suprimir los datos de una persona | Administrador |
| Alta del **segundo factor** (código QR para la aplicación autenticadora) | Administrador |
| Campañas de captación | Líder y administrador |

Las cuentas y las campañas **no se borran: se desactivan**, para no dejar sin sujeto los asientos de auditoría. Un administrador no puede desactivarse ni degradarse a sí mismo, ni dejar al sistema sin administradores activos.

---

## 4. Tareas frecuentes

### Cerrar un trato (ganado o perdido)

1. Abra la ficha del prospecto.
2. El selector de etapa **no permite** poner «Ganado» ni «Perdido»: es a propósito.
3. Pulse el botón de **cierre** de la ficha.
4. Elija el **motivo** de la lista cerrada (no hay cuadro de texto), la **fecha** y, si se ganó, el **tramo**.
5. Confirme. La puntuación **no se recalcula**: se conserva la que había cuando se decidió, que es lo único con lo que después se puede saber si el score acertaba.

### Atender una ficha nueva que llegó por la página pública

1. Abra **Hoy** y busque la tarea de primer contacto.
2. Abra la ficha 360° y lea «Llegó por».
3. Contacte a la persona; registre la actividad.
4. Marque la tarea con **«Ya está»**.

### Qué ve la persona interesada

Abre el enlace de la publicación en su teléfono o navegador. El formulario es corto, **sin texto libre**: cargo, sector y tamaño de empresa vienen de listas cerradas; teléfono y perfil están plegados porque son opcionales. Debe aceptar el **aviso de privacidad**. Siempre recibe la misma confirmación, exista o no su correo en el sistema.

---

## 5. Preguntas frecuentes

| Pregunta | Respuesta |
| :--- | :--- |
| No veo a un prospecto que sé que existe | Si es de otro asesor, usted no lo ve. Pida al líder que lo reasigne |
| Una ficha nueva no tiene tarea en «Hoy» | Las tareas se generan en una pasada diaria; aparecerá en la siguiente |
| El score de un prospecto bajó solo | Es el decaimiento temporal: pierde la mitad de su peso heurístico cada 14 días sin actividad |
| No puedo poner «Ganado» en el selector | Es intencional; use el botón **Cerrar** con su motivo |
| El panel de Desenlaces me da «403» | Es correcto: son totales de toda la casa y solo los ve la dirección |
| El enlace de una publicación ya no abre | La dirección pública gratuita cambia en cada arranque; pida a TI que ponga la nueva en la configuración. El panel marca los enlaces desactualizados |
| La pantalla dice «la dirección pública no responde» y sí funciona | En redes con proxy corporativo la comprobación falla siempre; TI puede apagarla con `COMPROBAR_DIRECCION_PUBLICA=false` |
| Olvidé mi contraseña | Un administrador la restablece desde Administración; al entrar se le pedirá cambiarla |

---

## 6. Qué no hace el sistema

- **No lee LinkedIn, Calendly ni WhatsApp**: recibe lo que llega *desde* ellos mediante enlaces propios.
- **No publica solo** en ninguna red: usted copia el texto y lo publica.
- **No reentrena el modelo solo**: avisa cuando hay datos suficientes y decide una persona.
- **Suprimir un prospecto aquí no lo suprime en el CRM** ni en ningún otro sistema; si el CRM vuelve a enviarlo, se creará de nuevo.
