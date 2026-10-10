# Congelación de funcionalidades y trabajo futuro

**Fecha de congelación:** 24 de septiembre de 2026
**Congelación definitiva:** 6 de octubre de 2026 — a partir de aquí, **solo fallos que impidan la instalación o la demostración**
**Alcance:** todo el repositorio `Sistema_Inteligente_Lead_Scoring`
**Sustituye a:** las secciones «Lo que esta fase no hizo» dispersas en los reportes 19 a 29
**Último capítulo:** 46 (Reporte 44), 6 de octubre de 2026

> ## 🧊 Congelación definitiva — 6 de octubre de 2026
>
> **Aquí se cierra.** El 24 de septiembre de 2026 el proyecto se congeló para funcionalidad:
> desde entonces entraban correcciones, y entraron **quince capítulos** —del 32 al 46—, cada
> uno abriendo la congelación para puntos nombrados de este documento y para ninguno más.
> Catorce fueron correcciones; el último, el 46, es el único que entró como funcionalidad, y
> porque se encargó explícitamente.
> Desde hoy el criterio es **más estrecho que ese**, y es el último:
>
> > Solo entra un cambio si, sin él, **la pila no se levanta** o **la demostración no se
> > puede enseñar**. Nada más.
>
> **No se abre ningún capítulo ni ninguna auditoría nuevos.** Ni de código, ni de
> accesibilidad, ni de seguridad, ni de calidad. Los capítulos 42 a 45 fueron auditorías de
> lo que ya existía y el 46 cerró el último punto que se encargó; el trabajo que queda está
> **escrito y clasificado** en las secciones §3 a §6 de este documento, y seguirá escrito.
> Eso es el entregable: no una lista de deseos, sino el inventario de lo que falta con el
> motivo por el que falta.
>
> **Qué cuenta y qué no, con ejemplos, para que no haya que interpretar:**
>
> | Entra | No entra |
> | :--- | :--- |
> | La pila no arranca: un contenedor se cae, una migración falla, el lanzador no encuentra `pila.env` | Un punto de §6.4, aunque sea de una línea y esté medido |
> | La demostración se detiene: la página pública no carga, el QR no se lee, el panel no deja asignar, el túnel no publica | Una pantalla, un filtro, un campo o un mensaje que **se ve** mal pero deja seguir |
> | Una cuenta de demostración no entra, o el sembrado deja la base inservible | Reentrenar el modelo, o cualquier cosa que lo cambie |
> | Una dependencia fijada desaparece del registro y la imagen ya no se construye | Un capítulo de auditoría nuevo, de cualquier clase |
> | El CI se pone rojo por algo del entorno y no por el código | Una guarda nueva, aunque vigile algo real |
>
> Ante la duda, la pregunta es una sola: **¿se puede enseñar el sistema hoy sin esto?** Si la
> respuesta es sí, se anota en §6.4 y no se toca.
>
> **Dónde está escrito el relevo.** Quien reciba este repositorio tiene tres documentos y en
> ese orden: [`AGENTS.md`](../AGENTS.md) en la raíz, con las reglas del proyecto —que está
> congelado, cómo se levanta, qué guardas hay y cómo se prueban, dónde vive cada cosa—;
> [**Si algo falla**](Si_Algo_Falla.md), escrito para quien no programa, con la tabla de
> «síntoma → qué mirar → qué hacer»; y este documento, para saber qué **no** se hizo y por
> qué. El informe técnico de la residencia y la guía de defensa llevan las cifras finales.
>
> **Las cifras del cierre.** 46 capítulos, 44 reportes. Servidor: **2064 pruebas**, 2
> omitidas, **99,11 %** de cobertura **contando ramas** —99,37 % de sentencias y 97,88 % de
> ramas— sobre suelos de 99,1 y 97,8. Esa cifra se mide **apartando el cliente compilado**,
> que es la condición en la que corre el CI; con el bundle presente pasan 2064 y se omiten
> 2, y sin él pasan 2052 y se omiten 14 —las doce del comodín de la SPA—. Cliente: **748
> pruebas** en 45 archivos, con suelos de 96,6 / 91,7 / 98,5 / 98,6. **10 trabajos** de
> integración continua, **61 controles** de configuración peligrosa y **siete guardas de
> propiedades**, cada una con su arnés de reintroducción. Modelo publicado: ROC-AUC **0,9469** con IC 95 % [0,9275, 0,9635]
> sobre datos sintéticos, y un aporte sobre el heurístico de **+0,0519** con IC 95 %
> [0,0296, 0,0761], que es la cifra que se defiende. `ruff`, `eslint` y `npm run build` sin
> avisos.
>
> **Lo que sigue abierto, en una línea cada bloque.** §3, lo que depende de cuentas externas:
> LinkedIn no se lee, Calendly y WhatsApp tampoco, no se publica solo en ninguna red, la
> tarjeta de vista previa no se ha visto en una red de verdad, nada sale del panel, las copias
> no salen de la máquina y sin `event_id` el CRM se deduplica por contenido. §4, lo que
> depende de datos reales: el modelo no se reentrena y por eso no conoce los canales nuevos,
> no hay deriva medible todavía, el monitor dirá «muestra insuficiente» un tiempo, las
> instantáneas anteriores al capítulo 24 no sirven para entrenar, los cierres anteriores al 30
> no tienen motivo, y **la sesión con personas sigue sin celebrarse**. §5, lo que no es
> técnico: los plazos de conservación no tienen valoración jurídica, aceptar el aviso no es
> condición para crear la ficha, suprimir aquí no suprime en el CRM, «¿qué necesitas?» no
> pesa, reabrir un cerrado no es una operación del sistema, los motivos no tienen peso y no
> hay candidatos. §6.2, cinco de nueve cerrados: siguen abiertos el 9, el 12, el 15 y el 35.
> §6.3 y §6.4, las comprobaciones que nadie ha hecho a mano y los restos menores: **39
> anotados** y numerados hasta el 59, de los que **13 se cerraron** por el camino, con el 57,
> el 58 y el 59 recién anotados por el capítulo 46.

> **Revisión del capítulo 46.** La congelación se abre **para el punto 10 de §6.2 (H-6) y
> para nada más**, y esta vez lo que entra **es** funcionalidad: el punto exige que el
> servidor haga algo que no hacía, y eso es exactamente lo que §1 llama una frase nueva. Se
> escribe así de claro porque los cuatro puntos que quedaban abiertos en §6.2 lo estaban por
> este mismo motivo, y cerrar uno no cambia el criterio para los otros tres.
>
> **Lo que había, y por qué no era repartir.** El punto decía: «hay dónde repartir, pero nada
> reparte solo». Lo único que repartía era un `if` dentro del scoring: si la ficha salía
> `HOT` y no tenía dueño, se le daba a quien tuviera el número más alto en `capacity`. Las
> dos mitades estaban mal. Una ficha `WARM` —la mayoría de las que llegan de una
> publicación— esperaba al líder, y **sin asesor el motor de reglas no tiene de quién
> hablar**: el capítulo 28 no pregunta «¿hay fichas nuevas?», pregunta «¿hay algún prospecto
> **asignado** al que nadie haya contactado?», así que esa ficha no producía ni tarea, ni
> aviso, ni línea en la bandeja de nadie. Y `capacity` es la cartera **máxima declarada**, no
> la que alguien tiene: `ORDER BY capacity DESC` entrega todos los prospectos a la misma
> persona hasta que alguien le cambie el número. Con dos asesoras de 60 y 40, los mil
> siguientes son de la de 60, cada ficha tiene dueño y ninguna pantalla se queja.
>
> **La regla.** Menos cartera **abierta** —la definición de «queda algo que hacer» es la del
> motor de reglas, importada y no copiada— y, con empate, quien lleva más tiempo sin recibir
> uno. Nada más: ni el score, ni el sector, ni la zona, ni `capacity`, que queda sin decidir
> nada (punto 59). No se toca una ficha que ya tiene asesor, ni una de una **publicación con
> responsable** —incluso si ese responsable se dio de baja, porque `ciclo.asesor_para` la deja
> sin asesor a propósito y esa cartera la reparte el líder—, ni una que no sea un alta.
>
> **Lo que hace que el punto 4 del encargo se cumpla sin un campo nuevo.** «Es un alta» se
> comprueba por algo que ya existía: que la ficha no tenga todavía ninguna instantánea en
> `score_histories`, que es lo primero que escribe el propio scoring. De ahí sale que una
> reasignación hecha a mano —o un prospecto que el líder dejó sin asesor a propósito— no la
> deshaga ningún recálculo posterior, sin una columna `asignado_en` que habría que escribir
> en los cinco sitios que asignan.
>
> **Dos altas a la vez.** La decisión lee un recuento que la otra transacción está a punto de
> cambiar: sin nada más, las dos leen «Ana tiene 0» y las dos se la dan a Ana. Los candidatos
> se leen con la fila bloqueada y en orden de identificador. Eso **no se puede ejercitar en
> la suite**, porque SQLite ignora `FOR UPDATE` en silencio; lo que la prueba y la guarda
> comprueban es que la sentencia lo pide de verdad, compilándola contra el dialecto de
> PostgreSQL, que es el motor de la pila. Lo que sí se ejercita es el caso hermano: dos altas
> en la misma transacción —una entrega del CRM con dos eventos— no pueden ir a la misma
> cuenta, y eso exige que el recuento vea lo que la transacción ya escribió.
>
> **Lo que NO se añadió.** Ni una tabla, ni una columna, ni una migración, ni un endpoint, ni
> una pantalla. Un módulo (`services/reparto_automatico.py`), un ajuste
> (`REPARTO_AUTOMATICO_ACTIVO`), una acción de bitácora y un parámetro `commit` en
> `registrar_evento`, que es lo que permite que el asiento del reparto viva en la transacción
> del alta: la ingesta del CRM confirma la ficha, su actividad, su score y su auditoría
> juntas o no confirma nada, y un asiento que confirmara por su cuenta dejaría escrito el
> reparto de un prospecto que el `rollback` siguiente se llevó.
>
> **Lo que cambia en lo que ya se enseñaba, que es la parte que no se ve en un diff.** El
> contador de «nuevos sin asesor» del líder mide desde ahora **lo que el reparto no pudo
> colocar** —una instalación sin asesoras activas, una publicación cuyo responsable se dio de
> baja—, y con la pila sembrada eso es cero. No está roto: cuenta otra cosa. Por eso el
> ensayo del guion (`scripts/ensayo_de_la_demo.py`) comprueba en el paso 5 que **no** sube, y
> la tarea 5 del líder en la prueba con personas pasa de «asígnasela» a «pásasela», que es
> además la forma de ejercitar con personas que una reasignación a mano no se deshace. La
> memoria técnica sigue diciendo, en sus capítulos 25 y 38, que H-6 está a medias: era verdad
> en su fecha, y la tabla de §6.2 de este documento es la que dice el estado de hoy.
>
> **Guarda y arnés.** `scripts/guarda_del_reparto_automatico.py`, con diez propiedades y no
> casos: que una tanda quede equilibrada, que el score no cambie a quién le toca, que lo
> decidido a mano no se deshaga, que la consulta siga pidiendo el bloqueo, que la definición
> de cartera abierta siga siendo la del motor, que el asiento diga con qué regla y entre
> cuántos candidatos, que el interruptor apague, que lo repartido reciba su tarea en la
> pasada siguiente, que los tres caminos del alta repartan igual y que sin asesoras no se
> invente un destino. 20 defectos reintroducidos, 20 detectados.

> **Recorrido de la demostración, 5 de octubre de 2026.** No es un capítulo ni una
> auditoría: es la historia del README recorrida en el navegador con los tres roles y con
> una persona interesada desde la vista de teléfono, apuntando todo lo que falla, se ve
> mal, está en otro idioma o confunde. La congelación se mantiene; lo que entró son
> correcciones, cada una con su prueba.
>
> **Lo primero que apareció no estaba en el código.** La pila que llevaba levantada toda
> la mañana servía la imagen del **1 de octubre**: su `app.css` tenía 8 KB y no traía
> ninguna de las reglas de `CompartirEnRedes`, así que el panel de difusión salía con el
> estilo por omisión del navegador —lo que el capítulo 39 cerró— y los capítulos 42 a 45
> no estaban en lo que se iba a enseñar. Nada lo decía: la pila arranca igual, los seis
> contenedores se ponen verdes y la pantalla funciona. Está anotado como punto 56.
>
> **Lo que se corrigió, con su prueba y su arnés** (11 defectos reintroducidos, 11
> detectados): la media de un conjunto vacío salía como **0** al lado de una tasa que sí
> decía «—», en las tres tablas que la enseñan; el embudo del tablero y la columna
> «Estado» de la matriz enseñaban **`NEW`, `ENGAGED`, `QUALIFIED`** teniendo la tabla de
> traducción escrita desde el capítulo 29 y usada por la ficha; cerrar sesión no limpiaba
> el buscador ni el cuadrante, de modo que la asesora entraba y veía **uno** de sus tres
> prospectos, filtrados por un nombre que había escrito el líder; `.btn` sin variante
> seguía sin declarar **fondo** —el capítulo 39 le dio el color del texto y dio el caso por
> cerrado—, y eso dejaba cuatro botones de blanco sobre blanco, uno de ellos el «Cerrar
> sesión» de la pantalla de alta del segundo factor, que es la única salida de la única
> pantalla que ve una cuenta de administración; el selector de **Sector** de la página
> pública ofrecía siete opciones de diez en inglés; y vaciar un campo de la ficha
> contestaba «Tiene que tener al menos **1 caracteres**».

> **Revisión del capítulo 45.** La congelación se mantiene, y este capítulo la abrió **para
> el punto 46 de §6.4 y para nada más**. El punto decía, de los validadores de modelo que
> rechazan sin poder nombrar el campo: «**los dos** validan con `model_validator`». Todo lo
> que afirmaba es verdad, incluida su observación fina de que el docstring del cierre dice lo
> contrario de lo que hace. Lo que no era cierto es la cuenta: en los esquemas hay **cinco**,
> y los tres que el punto no contaba son los de las **ediciones parciales** —el capítulo 33
> escribió el primero y el 41 lo repartió a los otros dos, los dos después de que este punto
> se escribiera—.
>
> **Y los tres que faltaban eran los únicos que tenían un defecto.** `PUT /users/{id}` con
> `{"full_name": null}` contestaba «La cuenta no existe sin estos campos, así que no se pueden
> dejar vacíos: **full_name**»: el nombre de la columna de la base dentro de una frase en
> castellano. Es exactamente lo que el capítulo 43 le quitó a `parseApiError` —y lo quitó del
> **prefijo**, que es donde una expresión regular lo alcanza; dentro de la frase no lo alcanza
> nada—, y con `loc: ['body']` el cliente no puede repartir ese renglón por campos, así que
> cae entero en el aviso de arriba con la columna dentro. El 43 cerró el punto 37 y esta línea
> se quedó en pantalla.
>
> **Por qué estaba ahí, que es lo que vale.** Tres funciones más arriba, en el mismo archivo,
> el capítulo 41 había escrito la regla: «el mensaje no dice qué campo es: lo dice el `loc` del
> 422… repetir el nombre de la columna en el texto es lo que hacía que la pantalla dijera
> `source`». Lo que nadie escribió es **qué hacer cuando no hay `loc`**. Un validador de modelo
> ve el cuerpo entero y responde `loc: ['body']`, así que su autor hizo lo único que quedaba
> —decirlo en el texto—, y las dos mitades no son evitables por separado. Una regla que no dice
> qué hacer en el caso que no cumple su condición es una regla que ese caso incumple con razón.
>
> El arreglo separa las dos cosas que ese mensaje mezclaba: **la frase** dice qué pasa y se lee
> sola —ya no termina en dos puntos y una lista—, y **los campos viajan en el `ctx`** del
> renglón, que es dato estructurado y no prosa, como ya hacen el 409 del recálculo masivo y los
> `motivos` de la política de contraseñas. El cliente los reparte debajo de cada campo con **la
> etiqueta que esa pantalla tiene al lado de su `input`**, que es la decisión del 43: una tabla
> de columna a etiqueta sería una segunda verdad. Y van nombres **del esquema** y no de la
> tabla, aunque salgan de cruzar con `__table__`: `vacios_prohibidos` recorre
> `model_fields_set`, así que lo que vuelve es lo que el cliente envió.
>
> **El `loc` no cambia, y eso es la mitad del punto que sigue abierta.** Pasar los cinco a
> validadores de campo permitiría repartirlos por campos de verdad, y cambia lo que la API
> contesta a un cliente que ya existe. El punto 46 queda **reescrito y partido**, no cerrado.
>
> **Lo que apareció al medirlo fue otra cosa, y más grande.** Los dos formularios del panel
> que no reparten su 422 —el de actividad de la ficha 360 y el de cierre— tienen nueve
> rechazos alcanzables, y **seis de los nueve llegaban en inglés**: «Field required», «Input
> should be a valid datetime or date», la lista de las catorce claves del `enum`. Cinco de los
> seis eran de un tipo que el cliente **ya sabía traducir** desde el capítulo 40, en una tabla
> que usan las cuatro pantallas que reparten; la función que ve todas las demás entregaba el
> `msg` de Pydantic tal cual. No faltaba la traducción: faltaba que la viera quien la
> necesitaba. Y la razón de que se separaran es que esa tabla, junto con la expresión regular
> del prefijo, estaba escrita **dos veces**, una en cada archivo, y la copia sin tabla era la
> que lo veía todo. Las dos viven ya en `services/rechazos.js`.
>
> Derivado de las rutas: **diecisiete** esquemas son cuerpo de una petición y entre todos
> pueden contestar **diecinueve** clases de rechazo, de las que la tabla cubría **once**. Los
> ocho que faltaban no los provoca un formulario —son «lo que llegó no es de la clase del
> campo», y un `<input>` manda siempre una cadena—, pero sí cualquier cliente de la API: la
> tabla se escribió mirando lo que un formulario rompe. Más un noveno que es una errata con
> forma: Pydantic nombra la conversión de fecha en **las dos direcciones** y la tabla tenía dos
> de los tres nombres, así que la misma errata de teclado contestaba en castellano en la fecha
> de un cierre y en inglés en la de una reunión, en el mismo panel.
>
> **Dos guardas nuevas, las dos derivadas y las dos con su propia cifra.** Una pregunta **a
> Pydantic** por los validadores que va a ejecutar —no al texto del archivo: el de las
> publicaciones lo heredan cuatro clases, así que contar por clase daría ocho donde hay
> cinco— y comprueba que ninguno de los 152 nombres de columna aparece en la frase de ningún
> `raise` de los esquemas. La otra deriva las puertas de las rutas, provoca los diecinueve
> tipos, **lee la tabla del archivo del cliente** y exige que los cubra; vive en el servidor
> porque la lista de tipos la decide quien los manda. El control **59** del CI vigila las dos
> y, desde que el arnés lo demostró, también **sus umbrales**: bajar un `>= 5` a `>= 0` es la
> forma en que una guarda deja de mirar sin dejar de existir. **25 defectos reintroducidos, 25
> detectados.**
>
> Dos cosas que este capítulo encontró y no son suyas. **La red de los campos obligatorios no
> atrapa ningún blanco**: medido campo a campo, de los quince que la alcanzan, el `null` llega
> en catorce y el blanco en **cero** —a todos los atrapa antes su mínimo, su tipo o su
> validador, y mejor, porque esos nombran el campo en el `loc`—. El capítulo 41 escribió en un
> docstring que esa red «no depende de que cada campo se acuerde de declarar un mínimo», y en
> el docstring de su propia prueba había escrito lo contrario y exacto. Se corrige la frase, no
> el código: la red es para la columna obligatoria que alguien añada sin mínimo. Y **dos
> pruebas de `api.test.js` tenían el inglés escrito como valor esperado** —`'Field required'`—
> porque sus renglones del 422 no traían `type`, que es el único campo por el que se sabe de
> qué clase de error se trata. Pasaban documentando el defecto. Es la forma del 43 y del 44 en
> una capa más: un renglón del 422 escrito a mano no es la respuesta del servidor.
>
> Y una corrección del punto **45**, que el capítulo 43 escribió: decía que el simulador
> era «el único de los formularios que quedan donde un rechazo por campo es alcanzable», y
> el de actividad recibe tres tipos con el campo en su `loc`. El argumento del punto sigue
> siendo bueno —un 422 sobre una lista cerrada que el propio desplegable ofrece es un fallo
> de programación— y vale para los tres; lo que no era cierto es la exclusividad.
>
> Entran dos puntos nuevos, el **49** y el **50**: el reparto por campos de esos dos
> formularios, que ya no es un problema de idioma sino de dónde cae el renglón, y el hueco del
> tipo que la tabla no conozca, que sale como «No se admite este valor» —mejor que el inglés y
> peor que una frase—.
>
> §6.4 pasa de **quince entradas abiertas de veintiocho a diecisiete de treinta**: el 46 se
> reescribe y sigue abierto por su mitad de contrato, y entran la **49** y la **50**. Las
> abiertas son hoy la 19, 20, 21, 23, 27, 28, 29, 34, 41, 42, 43, 45, 46, 47, 48, 49 y 50,
> contadas leyendo la tabla.

> **Revisión del capítulo 44.** La congelación se mantiene, y este capítulo la abrió **para
> el punto 44 de §6.4 y para la mitad medible del punto 18 de §6.3**, y para nada más. El
> punto de partida no fue ninguno de los dos, sino una frase de la cabecera de la auditoría
> de accesibilidad del cliente, escrita en el capítulo 36: «las **ocho** pantallas». Era
> verdad. Lo que no decía es de cuántas: el cliente tiene **dieciocho** componentes con
> controles de formulario, 105 controles entre todos, y la auditoría montaba ocho —más la
> tabla y la campana, que caen dentro del tablero—. **Nueve pantallas con 39 de las 105
> cajas no las había mirado ningún motor nunca.**
>
> Es la misma forma que el capítulo 43 encontró en `PARES`: una comprobación real, que mide
> bien, sobre **un inventario escrito a mano**. Lo que la suite medía no era el cliente, era
> la lista. Y el defecto la seguía: `LoginScreen` lleva escrito desde el capítulo 36
> «`<main>` y no un `<div>`: es la pantalla entera y no estaba dentro de ninguna región»; el
> cambio obligatorio de contraseña y el alta del segundo factor son **también** la pantalla
> entera —`App.jsx` las devuelve en lugar del panel—, no se montaban aquí, y las dos seguían
> siendo un `<div>`. De las tres pantallas obligatorias y sin salida del sistema, dos estaban
> enteras fuera de cualquier región.
>
> Lo que había en las nueve, con `axe` pasado por encima: **tres deslizadores del simulador
> sin ningún nombre accesible** —ni `<label>`, ni `aria-label`, ni `title`, ni `placeholder`:
> un lector de pantalla decía «control de deslizamiento, 6, mínimo 0, máximo 25» y de qué, no;
> infracción **crítica**, §4.1.2 y §1.3.1—; **el selector del rol de cada cuenta tampoco**
> —otra crítica, y es el control que cambia los permisos de una persona: la cabecera de la
> columna nombra la celda, no el control que hay dentro—; y un **`aria-label` sobre un `div`
> sin rol** en el alta del segundo factor, que ARIA prohíbe, así que el nombre se ignoraba y
> el único dibujo de esa pantalla no tenía ninguno.
>
> **Ninguna de las tres guardas que debían verlo lo vio, y por tres motivos distintos.** La
> regla del `linter` —`label-has-associated-control`— empieza por la `<label>`: un control sin
> ninguna etiqueta en ningún sitio no aparece en su recorrido. La guarda de `.input-field` del
> capítulo 43 excluye los deslizadores a propósito y con su motivo escrito —no tienen contorno
> que medir—. Y `axe` sí lo caza, en la pantalla que la lista no incluía. No faltaba una
> herramienta: faltaba que la lista incluyera la pantalla.
>
> **Lo más instructivo es lo del QR.** La prueba de ese componente lo buscaba por su nombre
> accesible —`findByLabelText(/Código QR/)`— y pasaba desde el capítulo 35, porque
> `getByLabelText` lee el atributo tal cual sin preguntar si ARIA lo admite ahí. Verde sobre
> un marcado que ningún lector de pantalla usa, y documentando como comprobado justo lo que no
> lo estaba. Es la forma del capítulo 43 en otra capa: no un doble puesto por encima del
> fallo, sino **una consulta más permisiva que la norma que se quiere cumplir**. De ahí sale la
> regla que este capítulo deja escrita: una consulta de la biblioteca de pruebas no es una
> medición de accesibilidad, y por eso la auditoría tiene que pasar por **todas** las
> pantallas.
>
> Lo que impide que vuelva a pasar no es haber montado las nueve: es que la lista **sale del
> código**. `frontend/src/pruebas/pantallas.test.js` deriva el inventario de los componentes
> con controles y se pone roja cuando uno no aparece montado en la auditoría, igual que
> `tokens.test.js` con la paleta desde el capítulo 39. Y el control **58** del CI vigila
> además que el arreglo no sea apagar lo que mira: el nivel sigue siendo AA de WCAG 2.1, la
> única regla apagada sigue siendo el contraste —que necesita píxeles y se mide sobre la
> paleta— y ninguna prueba se apaga una regla para sí misma. **24 defectos reintroducidos, 24
> detectados**, y tres de ellos los encontró el arnés dentro del control recién escrito: la
> comprobación buscaba su respuesta en un comentario o en una cadena que no venía al caso, y
> pasaba con el defecto puesto. Ninguna la vio una lectura.
>
> Entran dos puntos nuevos, el **47** y el **48**, los dos con su cuenta: las otras dos suites
> de accesibilidad —el recorrido con teclado y los anuncios a un lector de pantalla— miran 2 y
> 5 de las 18 pantallas, y cuarenta y ocho etiquetas escriben a mano un estilo que la hoja ya
> define.
>
> §6.4 pasa de **catorce entradas abiertas de veintiséis a quince de veintiocho**: se cierra
> la 44 y entran la **47** y la **48**. Y una corrección de la cuenta anterior: el bloque del
> capítulo 43 escribió «once de veintiséis», y eran **catorce**, porque dio el número después
> de cerrar sus tres puntos y antes de sumar los tres que él mismo abría. Las abiertas son hoy
> la 19, 20, 21, 23, 27, 28, 29, 34, 41, 42, 43, 45, 46, 47 y 48, y están contadas leyendo la
> tabla y no de memoria.

> **Revisión del capítulo 43.** La congelación se mantiene, y este capítulo la abrió **para
> tres puntos de §6.4 y para ninguno más**: el **37**, el **38** y el **39**, que eran los
> tres que quedaban del lado del cliente. Los tres estaban mal medidos, y uno en la frase que
> decidía que podía esperar.
>
> El **38** contaba «siete errores» avisados con un `alert()` del navegador. Eran **seis y
> todos en `App.jsx`** —el del recálculo de una ficha lo había movido el capítulo 40 sin que
> nadie actualizara el punto—, uno no era de ningún recálculo y **dos no eran errores**: uno
> anunciaba un éxito, «✅ 312 prospectos recalculados», y otro decía que el trabajo seguía en
> curso. `alert()` no era solo cómo el panel avisaba de un fallo: era la única forma que tenía
> de decir cualquier cosa fuera de un formulario. Y el punto no mencionaba los otros dos
> cuadros del navegador que había, uno de ellos **el peor de los tres**: un `window.prompt`
> pedía la contraseña de otra cuenta, y un `prompt` **escribe en claro**, sin repetición que
> comprobara la errata y sin sitio donde enseñar los motivos de la política (R41 §43.2, §43.3).
>
> El **37** decía que diez avisos escribían su geometría en un `style` y que eso «no incumple
> ningún mínimo». Las dos frases eran falsas. Los diez que llevan `className="alert"` tienen
> **una** propiedad en su `style`, un margen; los que escribían la caja entera eran otros
> **diecinueve**, los que nunca recibieron la clase. **Lo importante no es el arreglo sino lo
> que apareció al hacerlo**: un par de colores escrito en un `style` es un par que la suite de
> contraste **no puede ver**, porque su lista de pares se declara a mano. Al derivarla del
> código aparecieron **siete combinaciones sin medir** y dos por debajo de los 4.5 de §1.4.3:
> `--text-muted` sobre el relleno de un chip daba **4.47** sobre el panel y **4.18** sobre el
> elevado, y sobre el de una insignia **4.64 en reposo y 4.36 con el ratón sobre la fila**,
> porque `tr:hover` añade el mismo relleno debajo. La guarda nueva deriva los pares de las dos
> partes —del marcado y de la hoja— y por eso el arreglo no se puede perder moviendo un color
> de sitio (R41 §43.5, §43.6).
>
> Y una planta más abajo, lo mismo: **once de las ochenta y ocho cajas de formulario del
> cliente no llevaban `.input-field`** —ocho en administración, tres en el menú de la sesión—,
> así que se quedaron fuera del contorno medido del capítulo 39 (su borde era el de 1.12:1 que
> §6.4 punto 32 cerró), del aro de foco y del borde rojo que el capítulo 40 pinta sobre
> `[aria-invalid='true']`. Las ocho del alta de una cuenta son **de las que ese capítulo marca
> con `aria-invalid`**: el atributo se anunciaba y no se veía, que son las dos verdades sobre
> el mismo campo que ese mismo capítulo decía estar evitando (R41 §43.7).
>
> El **37** contaba además mal dónde estaba el nombre de la columna: no lo escribían siete
> pantallas, lo escribía **una función en un sitio**, `parseApiError`. Y su ejemplo —`nueva: La
> contraseña está en la lista de filtradas`— no existe: el campo se llama `nueva_contrasena` y
> ese rechazo no llega como un renglón por campo, sino como un detalle estructurado con
> **todos** los motivos por los que la contraseña no vale… que el cliente **tiraba desde el
> primer commit**, quedándose con el titular. Las dos pruebas de cliente que decían
> comprobarlo fabricaban el mensaje con los motivos ya dentro, una capa por debajo de donde
> estaba el fallo (R41 §43.8, §43.9).
>
> El **39** era cierto y además corto: `--warm-*` hacía de temperatura WARM y de advertencia,
> y no solo en `.alert-warn`. Hay ya una familia `--warn-*` con los mismos valores, porque lo
> que había que separar no era el color —sigue sin haber otro ámbar— sino la decisión de
> moverlo (R41 §43.11).
>
> §6.4 pasa de **once entradas abiertas de veintitrés a once de veintiséis**: se cierran la
> 37, la 38 y la 39, y entran la **44**, la **45** y la **46**. El arnés reintrodujo
> veintinueve defectos y los detectó los veintinueve, con dos resultados que valen escritos:
> el defecto «los motivos vuelven a tirarse» lo detectan el control del CI y la prueba de
> `api.js`, y **no** las de los dos formularios —que es exactamente lo que había pasado—, y el
> de «el texto de un chip vuelve al apagado que daba 4.47» solo lo detecta la mitad de la
> guarda que deriva los pares **de la hoja**, sin la cual el mismo incumplimiento habría
> cambiado de sitio sin ponerse rojo (R41 §43.13).

> **Revisión del capítulo 42.** La congelación se mantiene, y este capítulo la abrió **para
> dos puntos de §6.4 y para ninguno más**: el **26** y el **40**, que este documento mandaba
> arreglar juntos porque «las dos son sobre lo que el servidor dice cuando la base rechaza
> algo».
>
> Los dos puntos eran ciertos y los dos estaban cortos en lo mismo: daban por hecho que el
> único camino hasta ese `commit` es una **carrera**, y por eso los dos decían que el fallo no
> se ve en uso normal. `leads` tiene dos claves ajenas, así que un `assigned_rep_id` que no
> existe pasa el esquema —es un entero— y lo rechaza la base, sin ninguna carrera y con
> cualquier cliente de la API. Medido antes de tocar nada: `POST /leads` con un identificador
> inexistente era un **500**, y `PUT /leads/{id}` con un asesor inexistente era un **409 que
> decía «el correo de esta ficha ya está registrado en otro prospecto»** — el correo de la
> propia ficha, que quien editaba no había tocado, dentro de una frase sobre un conflicto que
> no había ocurrido (R40 §42.4).
>
> **Lo importante no es el arreglo sino por qué no había forma de encontrarlo.** SQLite no
> comprueba las claves ajenas si no se le pide: `PRAGMA foreign_keys` nace apagado y hay que
> encenderlo **en cada conexión**. La línea estaba escrita seis veces en este repositorio, y
> las seis dentro de tres pruebas de migración; faltaba en `app/core/database.py`, el único
> sitio donde se crea el motor de la aplicación —el de la suite y el del desarrollo local—.
> Las **18 claves ajenas y las 18 cláusulas `ondelete`** del esquema eran inertes ahí. Al
> encender el pragma, la suite dio **1587 pasadas y 2 omitidas: exactamente lo mismo que sin
> él**, y eso no es tranquilidad: es la demostración de que ninguna de las 1589 pruebas había
> escrito nunca una clave que no apuntara a nada ni borrado un padre cuya cascada importara.
> **Una restricción que el motor de las pruebas no hace cumplir es una restricción que nadie
> ha probado nunca**, y se nota en que encenderla no cambia nada (R40 §42.2).
>
> **El punto 26 era verdad a medias, y la mitad que faltaba cambia el arreglo.** Proponía leer
> el error del motor, dialecto por dialecto. SQLite dice `UNIQUE constraint failed:
> leads.email` y `NOT NULL constraint failed: leads.first_name`, pero para una clave ajena
> dice exactamente `FOREIGN KEY constraint failed` **y nada más**: ni columna, ni tabla, ni
> valor, y es el caso más probable de los tres. Leer el mensaje no podía nombrar el campo
> justo donde hace falta. Así que el `except` no lee el mensaje: **pregunta a la base** cuál
> de sus reglas no se cumple, con la lista de reglas sacada de `__table__` como hizo el 33 y
> generalizó el 41, y contesta un 422 con el campo en `loc` — que el mecanismo del capítulo 40
> pinta debajo del campo sin tocar una línea del cliente (R40 §42.5).
>
> Lo demás, en una línea cada cosa. De las dieciocho claves ajenas, **catorce se escriben
> desde una fila ya cargada** y cuatro pueden venir de un cuerpo de petición; la lista sale de
> cruzar los esquemas de entrada con el esquema de la base, y al derivarla apareció que la
> pregunta «¿y si ese identificador no existe?» ya tenía **tres respuestas escritas** en el
> repositorio —un 422 que además exige un asesor activo, un 404 que protege la cartera ajena,
> y nada— (R40 §42.3). De los siete `except IntegrityError`, dos preguntaban y cuatro
> suponían, y el más caro era el del webhook: contestar «duplicado» a un rechazo que no lo era
> **descarta el evento entero**, el CRM no reintenta y el prospecto no existe en ninguna
> parte, cuando dos capas más abajo el registro de actividad ya preguntaba antes de decirlo
> (R40 §42.8). `PUT /leads/{id}` con `campaign_id` respondía **200 con la ficha entera** sin
> cambiar nada, que es la forma exacta del defecto que el 33 cerró, sobreviviendo en un campo
> que no estaba declarado (R40 §42.9). Y `LeadRepository.delete` seguía siendo el borrado que
> la Fase 14 había retirado por dejar atrás las entregas de webhook: no lo llamaba nadie y
> parecía la forma de borrar un prospecto (R40 §42.10). **Sin migración**: PostgreSQL ha
> rechazado estas filas desde que las claves existen, así que no hay nada que igualar.
>
> §6.4 pasa de **diez entradas abiertas de veinte a once de veintitrés**: se cierran la 26 y
> la 40, y entran la **41**, la **42** y la **43**. Y hay otra vuelta de tuerca del arnés,
> distinta de la del 41: de los veintitrés defectos reintroducidos, cuatro escaparon en la
> primera pasada, y **dos de ellos decían que una comprobación de este capítulo no hacía
> nada** —quitarla dejaba la suite verde, porque la red del `except` contesta lo mismo—. Esta
> vez la respuesta no fue quitarla: las dos capas sí se distinguen, pero en **el momento** y no
> en la respuesta, y nadie lo había escrito. Un arreglo cuya razón de ser no está en ninguna
> prueba es indistinguible de uno que sobra (R40 §42.7, §42.12).

> **Revisión del capítulo 41.** La congelación se mantiene, y este capítulo la abrió **para
> un punto de §6.4 y para ninguno más**: el **25**, que el 33 encontró, dejó escrito en su
> propio docstring y no pagó.
>
> El punto decía que el alta de una ficha guarda `''` donde la edición guarda `NULL`. Es
> cierto, en nueve campos, y está corto en tres sitios. **El alta y la edición no son dos
> puertas: son dos de cinco**, y cada una respondía algo distinto a «qué es un vacío». De los
> **61 campos de texto** de los dieciocho cuerpos de petición de la API, **34 guardaban el
> blanco tal cual**, 15 lo normalizaban y 12 lo rechazaban — y los doce eran el formulario
> público y tres listas cerradas. El formulario público lo rechazaba con **una línea de
> configuración** que llevaba ahí desde el capítulo 34 y que no tenía ninguna otra entrada:
> el arreglo estaba escrito desde hacía siete capítulos, en una puerta de cinco (R39 §41.3).
>
> **El defecto es de orden, y es lo que conviene recordar de este capítulo.**
> `UsuarioCreate.full_name` declaraba `min_length=2` y recortaba en un `field_validator`, y
> un validador de campo corre **después** de las restricciones declaradas: el mínimo medía lo
> que llegaba y la base recibía otra cadena. Dos espacios —dos caracteres, mínimo cumplido—
> se guardaban como `''` en una columna `NOT NULL`, y `' A '` como una sola letra. Las dos
> piezas eran correctas y no se veía nada raro en el archivo; lo que estaba mal era que una
> corriera antes que la otra. **Una comprobación y una normalización en el orden equivocado
> son una comprobación que no comprueba nada** (R39 §41.2).
>
> **Y la regla del capítulo 33 solo existía para una tabla.** Ese capítulo derivó de
> `Lead.__table__` la lista de campos sin los que una fila no existe —lo difícil, y lo que
> hace que el arreglo no caduque— y la escribió **dentro del esquema de esa tabla**. El
> sistema tiene tres ediciones parciales, y en las otras dos un `null` explícito sobre una
> columna obligatoria llegaba al `commit` y salía como **500**: `{"name": null}` sobre una
> publicación y `{"full_name": null}` sobre una cuenta. No es el mismo fallo que el del 33
> —aquel contestaba 200 a algo que no había hecho— pero es peor de lo que el número sugiere:
> un 500 se anota como fallo del servidor y no del cuerpo enviado, no dice qué campo fue, y
> en la pantalla sale como «algo ha ido mal» (R39 §41.4).
>
> Lo demás, en una línea cada cosa: `crm_platform` es el prefijo del identificador con el que
> un evento del CRM queda marcado para siempre, y nadie lo recortaba, así que **«HubSpot» y
> «HubSpot » eran dos eventos distintos y el mismo evento entraba dos veces** (R39 §41.7); la
> migración `d8b3e5f09a71` iguala los blancos que ya hay en catorce columnas y **cuenta y
> nombra** las seis obligatorias que no puede tocar, porque un nombre no se inventa y porque
> un nombre vacío puede ser el vacío deliberado del webhook (R39 §41.10); y el blanco del
> webhook **no se unifica a propósito**: donde hay alguien delante un campo indispensable en
> blanco es un 422, y donde no hay nadie rechazar el evento perdería el prospecto entero
> (R39 §41.6).
>
> §6.4 pasa de **diez entradas abiertas de diecinueve a diez de veinte**: se cierra la 25 y
> entra la **40**. Y hay una cosa más que no es del código sino de cómo se comprueba, y que
> es la vuelta de tuerca del capítulo 40 sobre otra superficie: de los treinta y tres
> defectos reintroducidos, seis escaparon en la primera pasada, y **dos de ellos eran
> arreglos de este mismo capítulo que no arreglaban nada**. Un normalizador que se le puso a
> `ActivityCreate` se quitó y ninguna prueba se puso roja, porque `registrar_evento` ya hacía
> eso desde el capítulo 24. El arnés dejó de medir guardas y empezó a medir arreglos: **una
> guarda que no se puede falsear es peor que ninguna, porque parece cubrir algo** (R39
> §41.12).

> **Revisión del capítulo 40.** La congelación se mantiene, y este capítulo la abrió **para
> un punto de §6.4 y para ninguno más**: el **36**, que el 39 encontró y no pagó.
>
> Lo que se fue a arreglar era que un campo con un valor inválido se viera igual que uno
> correcto. Al medirlo aparecieron tres cosas que no estaban en ningún punto, y las tres
> pasan el criterio del §1 con el mismo argumento incómodo del capítulo anterior: **el
> README promete el nivel AA de WCAG 2.1 para las nueve pantallas**.
>
> **La primera es un hueco entre dos comprobaciones que están bien escritas**, y es lo que
> conviene recordar de este capítulo. `accesibilidad.test.jsx` dice en su cabecera que no
> mide contraste porque jsdom no dibuja y manda a `contraste.test.js`; `contraste.test.js`
> dice que lee los colores del `:root`. Las dos frases son verdad, y entre las dos queda un
> sitio: **un color escrito en un `style` del JSX no está en ninguna de las dos**. Trece
> archivos tenían colores ahí, y el rojo de cuatro avisos daba 4.43:1 sobre el panel y
> 4.17:1 sobre el elevado, por debajo de los 4.5 de §1.4.3. Y el token que la paleta ya
> tenía para ese sitio daba 6.02: **el color no estaba mal elegido, estaba elegido donde no
> se mide** (R38 §40.2).
>
> **La segunda es que el servidor ya decía qué campo y la pantalla lo tiraba.** El 422 trae
> `loc`, y el capítulo 33 se tomó el trabajo de que nombrara el campo en vez de contestar un
> 200 mentiroso. Los cuatro formularios del panel volcaban ese 422 entero en un aviso de
> arriba —con el nombre de la columna, en inglés y en un solo renglón, porque el salto de
> línea que el cliente pone no es un salto en HTML—, y el de la ficha 360 lo hacía en un
> `alert()` del navegador, que no se puede poner junto a un campo, no lo anuncia ningún
> lector y tapa el formulario que hay que corregir. El trabajo del 33 llegaba hasta el
> servidor y se perdía en la última pulgada (R38 §40.7).
>
> **El hallazgo del capítulo es el del 39 un piso más abajo, y esta vez sin salida.** El
> borde rojo de un campo inválido no puede cambiar al recibir el foco —el error
> desaparecería justo mientras se escribe la corrección— y **ningún color llega a los 3.0
> por encima de ese rojo**: el aro de foco de la paleta da 1.96 y el rojo más claro que
> sigue siendo rojo, 2.60. Lo único que pasaría es el blanco puro, que no es un rojo. Cuando
> no hay salida cromática, la salida es geométrica: el foco es un aro **añadido** por fuera,
> y hay una prueba que recalcula esa imposibilidad para que la decisión no sobreviva a su
> motivo (R38 §40.6).
>
> §6.4 pasa de **once entradas abiertas de dieciséis a diez de diecinueve**: se cierra la 36
> y entran la **37**, la **38** y la **39**, que son lo que este capítulo encontró y no
> pagó. Y hay una cosa más que conviene dejar escrita, porque no es del código sino de cómo
> se comprueba: de los veintiocho defectos reintroducidos, **cuatro no se detectaron en la
> primera pasada**, y los cuatro porque la guarda buscaba un **nombre** y no un **uso** —un
> `import` sigue ahí aunque la llamada no—. Es la lección del capítulo 37 con una vuelta
> más, y la encontró el arnés sobre guardas recién escritas por quien acababa de escribir el
> código que vigilan (R38 §40.9).

> **Revisión del capítulo 39.** La congelación se mantiene, y este capítulo la abrió **para
> cuatro puntos de §6.4 y para ninguno más**: el 33, el 30, el 31 y el 32.
>
> Pasan el criterio del §1 de la forma más incómoda posible: **el README promete el nivel AA
> de WCAG 2.1 para las nueve pantallas**, y había un par de colores que no llegaba; la hoja
> declara un sistema de diseño, y el marcado le pedía clases y tokens que no existían. No hay
> pantalla nueva, ni endpoint, ni esquema, ni migración: **el servidor del capítulo 39 es,
> byte a byte, el del 38** (R37).
>
> **El punto 33 estaba mal medido, y conviene decirlo.** Decía «`var(--accent-primary)` no
> existe… cosmético, y en un elemento que dura lo que una petición». Eran **cinco** tokens en
> nueve sitios, y dos no eran cosméticos: un `var()` que no resuelve no deja la propiedad en
> su valor anterior, la deja en el **inicial**, así que la barra de distribución del tablero
> se dibujaba **vacía** y la opción elegida de la ficha 360 se quedaba **sin contorno**. Es el
> riesgo de anotar un defecto por el ejemplar que uno tiene delante en vez de por su forma: el
> defecto no era «falta un color», era «el marcado nombra cosas que nadie comprueba que
> existan», y eso tiene tantos ejemplares como nombres haya (R37 §39.2).
>
> **El hallazgo del capítulo no es el defecto: es lo que apareció al arreglarlo.** Subir el
> borde de un control a los 3.0 que pide §1.4.11 lo dejaba a **1.11:1** del aro de foco, que
> estaba una centésima por encima: §1.4.11 cumplido **incumpliendo §2.4.7**, con el contorno
> por fin visible y el foco invisible. Los dos tokens se mueven juntos, y el cambio de estado
> se mide ahora en los **dos** controles donde ocurre, porque el que manda es el botón
> secundario y medir solo el campo habría dejado pasar un valor que allí falla (R37 §39.5).
>
> §6.4 pasa de **catorce entradas abiertas de quince a once de dieciséis**: se cierran la 30,
> la 31, la 32 y la 33, y entra la **36**, que el propio capítulo encontró y no pagó. Además
> se corrigieron dos cosas que no estaban en ningún punto y que entraron **porque sin ellas la
> corrección habría introducido algo peor que lo que cierra** — por eso no abren entrada: se
> cierran el mismo día que se encuentran:
>
> * **La hoja no tenía ningún `:disabled`**, y quince componentes apagan botones. Mientras los
>   botones fueron blancos o grises no dolía; con un relleno rojo sólido, «Suprimir
>   definitivamente» apagado se habría visto igual que encendido (R37 §39.8).
> * **`.btn` no declaraba `color`.** En un `<button>` se hereda y no se nota; en el único
>   `<a class="btn">` del cliente gana la hoja del navegador, y «Compartir en LinkedIn» salía
>   en azul de enlace sobre un panel oscuro: **1.87:1**. Lo encontró mirar la pantalla ya
>   maquetada, que es lo único que lo encuentra (R37 §39.9).
>
> El inventario `SIN_DEFINIR` de `clases.test.js` queda **vacío** y el mecanismo **se
> conserva**: no existe para guardar nombres, existe para que aceptar una deuda cueste
> escribirla con su motivo. Hay una prueba que comprueba que sigue vacío, y volver a usarlo
> obliga a borrarla — que es justo el tamaño de decisión que corresponde.

> **Revisión del capítulo 38.** La congelación se mantiene, y este capítulo la abrió **para
> tres puntos de §6.2 y para ninguno más**: el 16, el 14 y el 11.
>
> Los tres eran el mismo fallo con tres caras —**una capacidad que existe, está probada y no
> se puede usar desde donde hay que usarla**— y los tres pasan el criterio del §1: la frase
> ya estaba escrita y el código no la cumplía. El README promete desde el capítulo 20
> «exportación y supresión del titular comprobadas tabla por tabla», y lo que no decía era
> **quién** podía usarlas: hasta este capítulo, un derecho de acceso y supresión que solo se
> ejerce construyendo una petición HTTP con un token de líder comercial no era un derecho de
> la persona, era un derecho de quien sabe usar `curl`.
>
> No se añadió ni un endpoint, ni una tabla, ni una migración, ni un campo de esquema: **el
> servidor del capítulo 38 es el del 37 más un archivo de pruebas**. Lo que entró fue el
> alrededor que faltaba, y es donde están todas las decisiones (R36).
>
> §6.2 pasa de **siete entradas abiertas de ocho a cinco de nueve**: se cierran la 11, la 14
> y la 16, y entra la **35**, que el propio capítulo encontró al enlazar el contador del
> tablero con la matriz. De las cinco que quedan, cuatro —9, 10, 12 y 15— piden que el
> servidor haga algo que hoy no hace, y eso es funcionalidad: es la misma distinción que
> dejó entrar a estos tres.
>
> **Lo que el capítulo encontró por ejecutar y no por leer, esta vez dentro de su propio
> trabajo**, y son dos:
>
> * Un **recuento que habría mentido**. El bloque de confirmación del borrado decía «se
>   borran la ficha y los N registros», sumando la tabla de secciones. Entre esas secciones
>   están los asientos de la bitácora, que **no se borran**: se les retiran los datos
>   personales y se quedan. El número se quitó, porque un total que no es el que ocurre acaba
>   en la constancia de la persona (R36 §38.5).
> * Una **fila que no era una sección**. `fuera_de_la_base` también es una lista del documento
>   de exportación, y lleva dentro tres párrafos de texto: salió en la pantalla como «fuera de
>   la base — 3», que no dice que haya tres registros de nadie. Arreglado por la forma del
>   contenido y no por una excepción con nombre.
>
> **Y lo que apareció con un teléfono en la mano, que es lo más grave de todo el capítulo.**
> §6.3 punto 17 decía «el código QR no se ha escaneado con un teléfono… es lo primero que
> habría que hacer antes de repartir material impreso». Se escaneó. **No lo detectaba
> ningún lector, y llevaba así desde el capítulo 27.** La información de formato —los quince
> bits que dicen con qué máscara está hecho el código, y sin los cuales no se puede leer un
> solo dato— iba escrita con la fila y la columna cambiadas de sitio. El dibujo, los datos,
> la corrección Reed-Solomon y el zigzag estaban bien.
>
> Lo que lo hace una lección y no un descuido: **las diecinueve pruebas del QR son todas
> simétricas respecto de la diagonal** —localizadores en esquinas simétricas, dos patrones
> de sincronismo que son uno el reflejo del otro, dos bandas de formato reservadas a la
> vez—, así que transponer no rompía ninguna. Y la única que podría haberlo visto —el módulo
> siempre oscuro, que el bucle pisaba— **pasaba por casualidad**. Una familia entera de
> pruebas puede estar ciega a un error concreto sin que nada lo señale; lo que faltaba era
> **leer el código**, y ahora la suite lo lee. §6.3 pasa de cuatro comprobaciones a mano a
> tres: el punto 17 queda cerrado (R36 §38.10a).
>
> Con el mismo teléfono salieron otras dos, menores y de la misma familia —lo que el sistema
> **no dice**—: el botón desactivado de la vista previa no explicaba por qué a quien llegaba
> hasta él, y el panel de compartir no avisaba de que la dirección pública estaba caída justo
> donde alguien copia e imprime ese enlace. Las dos corregidas (R36 §38.10b y §38.10c).
>
> Y una tercera, sobre el método: **la primera pasada del arnés de reintroducción dijo 13 de
> 13 y era mentira**. Lanzaba el control con una ruta relativa desde otro directorio, Python
> salía con código 1 por no encontrar el archivo, y el arnés leía ese 1 como «el control
> disparó». Un arnés que verifica guardas es código sin verificar; lo destapó mirar **qué
> mensaje** daba cada disparo en vez de contar los que disparaban (R36 §38.9).

> **Revisión del capítulo 37.** La congelación se mantiene, y esta revisión corrige el
> **documento** además del código, que es la primera vez que pasa.
>
> El capítulo 37 cerró **§3.7** y **§3.8**, y los cerró demostrando que su premisa era falsa:
> ninguno de los dos necesitaba una cuenta externa. El servicio de comprobación de
> contraseñas filtradas por rango —*k-anonymity*, el modelo que la propia entrada nombraba—
> es una petición anónima sin registro ni clave, y Dependabot es parte de GitHub, donde el
> repositorio vive desde el capítulo 11. §3 pasa de **nueve entradas abiertas a siete**: de
> las diez que tiene, tres están ya cerradas —§3.6 en el capítulo 35, y estas dos—.
>
> Las siete que quedan sí necesitan lo que dicen necesitar, y conviene decirlo para que esta
> revisión no se lea como una sospecha general sobre §3: LinkedIn, Calendly, WhatsApp y la
> publicación automática piden credenciales de una plataforma; la tarjeta de vista previa
> pide un dominio público; las copias fuera de la máquina piden almacenamiento; y el
> `event_id` lo tiene que mandar un CRM que todavía no existe. El error no estaba en el
> criterio de §3, estaba en dos entradas que nadie volvió a comprobar.
>
> **La diferencia entre los dos errores importa.** §3.8 fue correcto el día que se escribió:
> en el capítulo 22 no estaba decidido dónde viviría el repositorio, y dejó de ser cierto sin
> que nadie volviera a mirarlo. §3.7 **nunca** lo fue: el capítulo 23 escribió «haría falta
> una cuenta» por analogía con el resto de §3 y no fue a comprobarlo, y así estuvo catorce
> capítulos.
>
> Es la cuarta vez que algo aparece por **ejecutar y no por leer** —el volumen `deriva` del
> capítulo 32, el suelo de cobertura del 36, el `target` ausente del Compose— y la primera en
> que lo que falla no es el código sino **el inventario de lo que falta**. Una lista de
> trabajo futuro es también código que envejece, y nadie le corre pruebas. De aquí sale una
> costumbre nueva: **una entrada de §3 no se da por buena sin haber comprobado que la cuenta
> hace falta de verdad**, porque «depende de alguien» es la clasificación que nadie revisa.
>
> §6.3 pasa de dos comprobaciones a mano a **cuatro** y §6.4 de quince restos a **dieciséis**.
> Las dos nuevas de §6.3 son del mismo tipo y conviene leerlas: lo que el capítulo 37 añadió
> solo se puede ver funcionando **fuera** de la suite, a propósito, porque meter un tercero
> dentro de la suite la pondría roja los días que ese tercero tenga un mal día.

> **Revisión del capítulo 36.** La congelación se mantiene. El capítulo 36 fue calidad del
> cliente, no funcionalidad: ninguna pantalla nueva, ningún campo nuevo, ninguna frase nueva
> en el README. Lo que hizo fue **comprobar** lo que el sistema ya afirmaba —que se puede
> usar con teclado, que el texto se lee, que los errores llegan a quien no ve la pantalla— y
> corregir los seis sitios donde no era cierto (R36).
>
> Encontró además dos cosas que no estaban en ninguna lista, y las dos son de la clase que
> este documento no puede prever:
>
> * **El suelo de cobertura del cliente estaba roto en `main`.** El capítulo 35 añadió al
>   módulo de sesión las cinco funciones del segundo factor sin una sola prueba; la suite
>   pasaba y la cobertura no, y la cobertura es lo que el CI ejecuta. Corregido en el 36
>   (R36 §36.9), que es donde entra por §1: «una guarda del CI en rojo».
> * **La bandeja «Hoy» hacía una consulta por tarea.** No se veía con seis prospectos: con
>   seis filas, una consulta por fila y una para todas tardan lo mismo. Se vio al medir con
>   300 prospectos y 5 000 actividades (R36 §36.7).
>
> §6.4 pasa de cinco restos menores a nueve: los cuatro nuevos son deuda **visual** que el
> capítulo encontró y no pagó porque pagarla es diseñar, y eso estaba fuera de su alcance.
>
> **Añadido el 29-09-2026, y es la tercera de esa clase.** Al levantar la pila para mirar el
> trabajo del capítulo 36, el panel seguía enseñando el defecto que ese capítulo había
> corregido: servía un bundle de cinco días antes. El servicio del cliente no declaraba
> `target` en Compose, así que Docker construía la **última** etapa del Dockerfile —la del
> pipeline, que no compila y copia el `dist/` del contexto— mientras la cabecera de ese
> mismo Dockerfile afirmaba que la que se construía era la que compila. Ninguna prueba podía
> verlo: todas miden el código fuente, y lo que fallaba era el empaquetado. Corregido, con
> el control **43** del CI (R36 §36.13).
>
> Las tres —el volumen `deriva` del capítulo 32, el suelo de cobertura roto y esta— tienen
> la misma forma: **no estaban en ninguna lista, y ninguna apareció leyendo código**.
> Aparecieron al ejecutar el sistema de verdad. Es lo que este documento no puede prever y
> la razón de que «verificar levantando la pila» sea una costumbre escrita.

> **Revisión del capítulo 32.** La congelación se mantiene tal cual: solo entran
> correcciones de fallos, con el criterio de §1. Lo que cambia es el inventario. §6.1 —«lo
> que puede morder»— tenía ocho puntos y ahora tiene **dos**, y los dos esperan a un
> sistema externo, no a más trabajo de este equipo. Se cerraron además el 13 y el 22. El
> capítulo 32 fue deuda, no funcionalidad: cada punto reparaba algo que el sistema ya
> prometía por escrito —una política de conservación sin filas sin plazo, una ficha que no
> supone, una guarda que exige versión— y ninguno añadió una frase nueva al README.
>
> Ese capítulo encontró además, al levantar la pila para comprobar el trabajo, **un defecto
> que no estaba en ninguna lista**: el volumen `deriva` del capítulo 22 nunca fue escribible
> por el proceso que lo usa, así que el monitor de deriva no habría podido recordar que ya
> avisó. Corregido, con un control nuevo en el CI. Se anota aquí porque es la clase de cosa
> que este documento no puede prever: las listas recogen lo que se sabe que falta, no lo que
> se cree terminado y no lo está.

---

## 0. Por qué existe este documento

Desde el capítulo 19, cada reporte termina con una lista de lo que esa fase **no** hizo.
Son once listas, cada una en su contexto, y cada una es correcta el día que se escribió.

El problema es doble. Primero, **una docena larga de esas entradas ya no son ciertas**: se
cerraron en un capítulo posterior, y el reporte lo dice en cursiva debajo de la entrada
original —que es lo honrado, porque tachar la línea borraría que estuvo abierta—. Segundo,
quien hoy quiera saber «qué falta» tiene que abrir once archivos y llevar la cuenta a mano
de cuáles se tacharon.

Este documento hace dos cosas, y ninguna más:

1. **Declara la congelación.** A partir de la fecha de arriba, el criterio de qué entra al
   repositorio cambia. §1.
2. **Reúne en un solo sitio lo que queda abierto**, agrupado por **de qué depende**, que es
   lo único que decide si algo se puede hacer o no. §3 a §6.

No decide prioridades ni promete fechas. Ninguna de las dos cosas corresponde a quien
escribe el código: la primera es de PluriOne y la segunda depende de cuándo lleguen cuentas
y datos que hoy no existen.

---

## 1. Qué significa «congelado»

**A partir de aquí solo se corrigen fallos.** Un cambio entra si y solo si repara algo que
está roto respecto de lo ya documentado.

| Entra | No entra |
| :--- | :--- |
| Un comportamiento que contradice lo que dice su reporte, el README o una prueba | Una funcionalidad nueva, por pequeña que parezca |
| Un fallo de seguridad | Un campo más en un formulario existente |
| Una prueba que falla, o una guarda del CI en rojo | Una pantalla, un endpoint o una tabla nuevos |
| Una dependencia con aviso de seguridad publicado | Una biblioteca nueva |
| Documentación que describe algo que el código no hace | Reescribir algo que funciona porque se le ocurrió una forma mejor |

**El criterio para distinguirlos** es el que el proyecto ya venía usando y no cambia aquí:
si para explicarlo hay que añadir una frase nueva al README, es funcionalidad; si la frase
del README ya está escrita y el código no la cumple, es un fallo.

**Tres casos frontera**, decididos de antemano para no tener que discutirlos con el reloj en
contra:

* **Reentrenar el modelo con desenlaces reales no es una funcionalidad nueva**: el camino
  está construido, comprobado en cada ejecución del CI (`ensayo_del_bucle.py`) y lo único
  que falta son las filas. Ejecutarlo el día que existan es operación, no desarrollo. Lo que
  sí sería funcionalidad nueva es cambiar el pipeline para que acepte menos datos.
* **Rellenar una lista cerrada** —un motivo de pérdida más, un sector más— es cambiar una
  constante del vocabulario y sus etiquetas. Cuenta como corrección si el panel demuestra
  que «Otro motivo» está creciendo (§4.7); como funcionalidad si sale de una intuición.
* **Los plazos de conservación** son configurables por variable de entorno a propósito
  (capítulos 20 y 22). Cambiarlos es configuración, no código, y no toca la congelación.

---

## 2. Cómo está clasificado lo que sigue

Cada entrada dice **de qué depende**, porque es lo que separa «no se hizo» de «no se puede
hacer todavía»:

| Grupo | Significa | Qué haría falta |
| :---: | :--- | :--- |
| **§3. Cuentas externas** | El código no se puede escribir de forma honrada sin una cuenta, una clave o un dominio público que el proyecto no tiene | Que PluriOne abra la cuenta |
| **§4. Datos reales** | El código se podría escribir, pero cualquier número que produjera sería inventado | Que el bucle acumule desenlaces |
| **§5. Decisiones que no son técnicas** | Está construido lo necesario; falta que alguien decida qué debe pasar | Una decisión de negocio, de producto o de quien responde del tratamiento de datos |
| **§6. Deuda de ingeniería** | No depende de nadie. Se puede hacer hoy | Tiempo |

**§7** recoge aparte lo que **no se va a hacer**, con el motivo. Una lista de trabajo futuro
que no dice qué descartó obliga a volver a plantear cada año las mismas discusiones ya
zanjadas.

Cada entrada lleva su origen entre paréntesis: `R25 §25.10` remite al **capítulo** 25,
apartado 25.10.

**Ojo con la numeración, que se ha desfasado dos veces.** Hasta el capítulo 28, el número
del reporte y el del capítulo coincidían. El capítulo 29 no escribió reporte propio, así que
a partir de ahí el reporte va **uno** por detrás; el capítulo 31 tampoco, y desde el capítulo
32 va **dos**. Hoy: el capítulo 36 está en el `Reporte_34`, y sus apartados se numeran `36.x`.

Por eso las referencias de este documento van por **capítulo** y no por reporte: es lo único
que no vuelve a moverse. `R36 §36.8` es el capítulo 36, apartado 36.8, que vive en el
archivo `Reporte_34_...`.

---

## 3. Depende de cuentas externas

Nada de esto se puede terminar dentro del proyecto. Lo que sí está hecho en todos los casos
es el lado de acá: el conector, el esquema, la firma o el botón.

### 3.1. LinkedIn no se lee

**(R25 §25.10, R21 §21.12 — H-5)**

Ni **Lead Sync** (recoger los formularios de captación de LinkedIn) ni **Sign In with
LinkedIn**. Las dos exigen una aplicación aprobada en LinkedIn Developer con su producto
concedido. El conector `linkedin-lead-gen` existe y acepta una forma **simplificada** de la
carga, no la de `leadFormResponses`: hoy sirve para probar el camino, no para recibir a
LinkedIn de verdad.

**Consecuencia hoy:** los perfiles entran por la página de interés del proyecto, que es lo
que la demostración enseña. Es un camino completo y real; simplemente no es el de LinkedIn.

**Qué haría falta:** la cuenta, y después contrastar el esquema completo y la firma de
LinkedIn contra lo que el conector acepta —o poner delante un traductor.

### 3.2. Calendly y WhatsApp Business, lo mismo

**(R21 §21.12)**

Los tres conectores se firman con el **esquema HMAC propio** del proyecto, no con el de cada
proveedor. Aceptan una forma reducida de sus cargas.

### 3.3. No se publica en ninguna red automáticamente

**(R26 §26.11, R27 §27.13)**

Los botones de difusión abren la **dirección pública de compartir** de cada red y publica
quien pulsa. El texto se copia y se pega; la dirección del post se escribe a mano después.
Publicar desde el panel exige una API y una cuenta por red.

**Estaba fuera del alcance desde el principio y sigue fuera.**

### 3.4. La tarjeta de vista previa no se ha visto en una red de verdad

**(R27 §27.13 · desbloqueado a medias en el capítulo 34)**

El HTML se comprueba como lo lee un rastreador, y las etiquetas Open Graph y Twitter Card
son las que LinkedIn, WhatsApp, Facebook y X documentan. Pero pegar el enlace y **mirar** la
tarjeta exige una dirección pública, y la de la demostración era `localhost`.

**Ya no lo es.** El capítulo 34 dejó la página alcanzable desde internet por un túnel
gratuito, con HTTPS y sin abrir puertos (R32). Se comprobó desde fuera de la red que el HTML
llega con `og:title`, `og:description`, `og:url`, `og:image` y `twitter:card` correctos, y
que la imagen de 1 200 × 630 se sirve.

**Lo que sigue abierto es la última mitad, y es la que no puede hacer una máquina:** pegar el
enlace en LinkedIn y **mirar** la tarjeta que compone. Eso exige una cuenta y una persona.
La guía lo pone como tarea del primer día (`docs/Guia_del_Tunel_Publico.md` §4).

**Qué haría falta para cerrarlo del todo:** alguien con cuenta de LinkedIn, diez minutos, y
el túnel encendido.

### 3.5. Nada sale del panel

**(R28 §28.13)**

Ni correo, ni WhatsApp, ni notificación de navegador. Las tareas y los avisos del motor de
reglas viven dentro del panel y se ven al entrar.

**Esto no es solo una cuenta que falta.** Un aviso que sale del sistema necesita una
dirección verificada, una política de qué hacer cuando rebota y, sobre todo, saca de la
aplicación el nombre de una persona que aceptó un aviso de privacidad para otra cosa. La
cuenta es el requisito más barato de los tres.

### 3.6. ~~No hay segundo factor~~ — **cerrado en el capítulo 35**

**(R23 §23.7, R19 §19.9 · cerrado en R33)**

Decía esto, y era un diagnóstico exacto: «Un TOTP para `System_Admin` exige alta con código
de verificación, códigos de recuperación, un paso más en el login del cliente y una
respuesta para quien pierde el teléfono siendo el único administrador —que es justo la
cuenta que no puede quedarse fuera. Añadir la verificación sin eso produce una cuenta de
administración que se bloquea sola.»

**Las cuatro cosas están hechas** (R33 §35.3), y la cuarta mandó sobre las otras tres: hay
tres salidas para quien se queda fuera, y la última cuenta de administración con segundo
factor **no se lo puede quitar**, porque hacerlo dejaría el sistema sin administración
utilizable.

Resultó que **no dependía de ninguna cuenta externa**, que es lo que lo tenía clasificado
aquí. Los códigos de recuperación se entregan en pantalla al darse de alta —no hacía falta
un canal para mandarlos— y el rescate del último caso se resuelve con acceso al servidor,
que es la respuesta correcta y no una carencia: cualquier canal usable desde fuera sería una
segunda puerta a la cuenta más poderosa del sistema.

Tampoco hizo falta una biblioteca de criptografía. El secreto **no se guarda**: se deriva de
`SECRET_KEY` y de una sal por alta, así que la base no contiene nada que cifrar. El precio
está escrito: rotar esa clave invalida todas las altas
(`docs/Guia_del_Segundo_Factor.md` §5).

### 3.7. ~~La lista de contraseñas filtradas no se actualiza sola ni es exhaustiva~~ — **cerrado en el capítulo 37**

**(R23 §23.7 · cerrado en R37 §37.2)**

~~Es una foto de dos listas públicas, con manifiesto de cuáles salió. Cubre las filtradas
más frecuentes de 12 caracteres o más. Comprobar contra cientos de millones de huellas sin
un servicio externo pediría un archivo de decenas de gigabytes dentro de la imagen.~~

~~**Qué haría falta:** una cuenta en un servicio de comprobación de contraseñas
comprometidas —con el modelo de *k-anonymity*, que no envía la contraseña— o aceptar el
tamaño.~~

**Lo que hacía falta no era una cuenta, y por eso esta entrada estaba mal clasificada desde
el día que se escribió.** El servicio de rango que implementa *k-anonymity* —el modelo que
esta misma entrada nombraba— es una petición `GET` anónima: sin registro, sin clave de API,
sin identificarse. El capítulo 23 escribió «haría falta una cuenta» por analogía con el
resto de §3, donde sí hace falta, y nadie volvió a comprobarlo en catorce capítulos.

Desde el capítulo 37, al alta de usuario y al cambio de contraseña se les pregunta por
rango: **salen los cinco primeros caracteres del resumen SHA-1 y nada más**, nunca la
contraseña ni el resumen completo. Si el servicio no contesta, no se bloquea a nadie y el
resultado es idéntico al de antes del capítulo 37 —hay una prueba que compara las dos
listas de motivos carácter a carácter—, porque la lista local sigue decidiendo primero.

**Lo que sigue abierto, y es la mitad que no se cerró:** la lista **local** sigue sin
actualizarse sola. Se regenera a mano con `scripts/generar_lista_de_contrasenas.py`, y
sigue importando porque es exactamente lo que queda cuando no hay internet. No depende de
ninguna cuenta: depende de que alguien la corra, así que su sitio ya no es §3 sino §6. Está
anotada como resto **34** en §6.4.

### 3.8. ~~Nadie avisa de que una huella de imagen se quedó atrás~~ — **cerrado en el capítulo 37**

**(R22 §22.9 · cerrado en R37 §37.7)**

~~Todas las imágenes de terceros van fijadas por huella y se renuevan con
`scripts/renovar_imagenes.py`. Que alguien **tenga que correr el guion** es deliberado.
Automatizarlo con un servicio que abra solicitudes de cambio exige una cuenta.~~

**Tampoco exigía una cuenta.** Dependabot es parte de GitHub y el repositorio está en
GitHub desde el capítulo 11; lo único que faltaba era `.github/dependabot.yml`. Esta
entrada sí fue correcta el día que se escribió —en el capítulo 22 no estaba decidido dónde
viviría el repositorio— y dejó de serlo sin que nadie volviera a mirarla.

Desde el capítulo 37 hay seis ecosistemas vigilados: las acciones del CI, las dependencias
de Python y de npm, las dos imágenes base de los Dockerfile y las imágenes de la pila.

**Lo que NO cambia, y está escrito en la cabecera del propio archivo:** Dependabot
**avisa**; `scripts/renovar_imagenes.py` sigue siendo la fuente de verdad. El guion es quien
conoce las reglas de este proyecto —una etiqueta no puede llevar dos huellas, nada de
`apt-get upgrade`, paquetes con versión, acciones por huella de commit— y una solicitud
automática puede dejar el repositorio en un estado que su guarda `--solo-fijacion` rechaza.
Y al revés: que no haya solicitudes abiertas no significa que todo esté al día, significa
que Dependabot no ha visto nada.

El archivo documenta además qué se acepta con el CI verde y qué exige repetir la
comprobación de la imagen entera —construir, Trivy, syft y los paquetes con versión fijada
de los dos Dockerfile—, y el control **45** del CI comprueba que esa cobertura y ese
criterio sigan ahí.

### 3.9. Las copias de seguridad no salen de la máquina

**(R19 §19.9)**

Hay copias, con prueba de restauración comprobada (capítulo 16). Sacarlas de la máquina
exige almacenamiento externo.

---

### 3.10. Sin `event_id`, el CRM se deduplica por contenido

**(R21 §21.12 · reclasificado desde §6.1 en el capítulo 32)**

Estuvo en «deuda de ingeniería» hasta el capítulo 32, y estaba mal colocado: aquí no hay
nada que escribir. La clave de deduplicación es `(source, external_event_id)`, y cuando el
sistema de origen **no manda** identificador la única huella disponible es el contenido.

Lo que eso cuesta: dos eventos reales idénticos byte a byte —incluido el instante— entran
como uno. Lo que costaría la alternativa: aceptar los dos y dejar que el operador decida,
es decir, cambiar un caso raro y sin daño por uno frecuente y con daño, porque cada
reentrega del CRM duplicaría la actividad. La corrección de verdad es que el CRM mande
`event_id`, y eso lo decide quien opera ese CRM.

Lo mismo, en menor grado, vale para la entrega de WhatsApp con varios mensajes (§6.1,
punto 6): el arreglo es escribible, pero **no comprobable** hasta que haya una cuenta al
otro lado, porque depende de si el proveedor reentrega la tanda entera o solo lo que
faltaba, y de esa respuesta depende si la transacción única es la corrección o el problema.

---

## 4. Depende de datos reales

Este grupo es el corazón del trabajo futuro, y todo él cuelga del mismo hecho:

> **Hoy la base no tiene ni un solo prospecto en estado terminal.** El bucle de
> realimentación está construido, comprobado y vacío.

El capítulo 30 construyó lo que faltaba para llenarlo: cerrar un trato exige decir cómo
acabó, por qué motivo —de una lista cerrada— y qué día. El contador del panel de desenlaces
dice cuánto falta: **200 ejemplos utilizables, 50 de cada clase**.

### 4.1. El modelo no se reentrena, y por eso no conoce los canales nuevos

**(R25 §25.10, R26 §26.11, R27 §27.13, R28 §28.13, R29 §30.14)**

El artefacto en producción conoce **«LinkedIn Ads»**, que es publicidad pagada. Un post
orgánico no lo es. Los seis canales de difusión del capítulo 27 tampoco los conoce.

**Qué hace hoy con ellos:** los trata como **canal desconocido**, es decir, **neutro**. No
los penaliza ni los premia. Esa es la respuesta honrada: no hay ninguna evidencia sobre la
que asignarles un peso.

**Tampoco llegan al modelo** ni las opciones de «¿Qué necesitas?», ni la tasa de envío de la
página, ni las tareas, ni los avisos, ni el motivo del desenlace. En los tres últimos casos
**es una garantía comprobada por el CI**, no un olvido: el motivo se conoce al cerrar, y el
día que hay que decidir a quién llamar todavía no existe.

### 4.2. No hay deriva del rendimiento ni curva de aprendizaje de los mínimos

**(R24 §24.9)**

Las dos necesitan desenlaces reales. El monitor vigila deriva de **variables** (PSI), que sí
se puede medir sin etiquetas; el rendimiento del modelo, no.

### 4.3. El monitor dirá «muestra insuficiente» durante un tiempo

**(R24 §24.9)**

Solo compara instantáneas del **vector 2**, y hasta que se acumulen cien no dictamina. Es la
respuesta verdadera: comparar con las antiguas daría un PSI con aspecto de deriva que sería
en realidad un cambio de definición.

### 4.4. Las instantáneas anteriores al capítulo 24 no sirven para entrenar

**(R24 §24.9)**

Es el precio de no inventar: no dicen qué mensajes eran de LinkedIn ni cuántas llamadas
quedaron sin respuesta. El dataset real y el monitor las **descartan y las cuentan** en
lugar de traducirlas, y el manifiesto dice cuántas son.

### 4.5. Los cierres anteriores al capítulo 30 no tienen motivo

**(R29 §30.14)**

La migración no los rellenó. El panel no los cuenta y el manifiesto del dataset los cuenta
aparte, con la etiqueta deducida del estado. Es la merma que cuesta no inventar.

### 4.6. El criterio del límite inferior es juicio, no medida

**(R19 §19.9)**

Publicar un modelo exige que el **límite inferior** del IC 95 % del ROC-AUC alcance 0.82 y
el del aporte sobre el heurístico alcance +0.01. Con esos umbrales, 260 desenlaces reales no
publicarían. Puede resultar demasiado exigente, y no hay curva de aprendizaje que diga
cuánto hasta que haya datos.

### 4.7. Nadie ha rellenado el formulario de cierre varias veces seguidas

**(R29 §30.14)**

Si **nueve motivos de pérdida** son demasiados o se quedan cortos —y sobre todo cuánto crece
«Otro motivo»— solo se sabe usándolo. El panel cuenta «otro» aparte precisamente para poder
tener esa conversación con datos en vez de con opiniones.

### 4.8. Nadie ha vivido una semana con la bandeja «Hoy»

**(R28 §28.13)**

Si las seis reglas producen la cantidad adecuada de trabajo —ni tan poco que sobre, ni tanto
que se ignore— es justo lo que solo se puede saber usándola varios días seguidos. **Los
plazos se dejaron configurables por eso.**

### 4.9. Las suposiciones del generador sintético son suposiciones

**(R24 §24.9)**

Qué prospectos dejan los ingresos en blanco, y cuánto pesa un intento de llamada sin
respuesta, están **elegidos para que el pipeline tenga algo que aprender**, no medidos. El
ROC-AUC de 0.9469 mide la integridad del pipeline, no el negocio.

### 4.10. La sesión con personas sigue sin celebrarse

**(R25 §25.10, R26 §26.11, R27 §27.13, R28 §28.13, R29 §30.14)**

Es la entrada más arrastrada del proyecto y merece decirse con precisión, porque es fácil
confundir «tiene pruebas» con «se ha probado con alguien».

**Lo que sí está:** la pila, el guion por papel (`docs/Prueba_Con_Personas.md`), las cuatro
hojas de observación, el preparador de la base y el ensayo automático del guion —que desde
este capítulo recorre los nueve pasos contra la API de verdad y los cronometra
(`scripts/ensayo_de_la_demo.py`, y su reloj en `docs/Guion_Cronometrado_de_la_Demo.md`)—.

**Lo que no puede decir ninguna prueba automática:**

| Rol | Lo que hay que observar | De qué capítulo viene |
| :--- | :--- | :---: |
| Marketing | Si al pedirle el texto de WhatsApp contesta que los dos enlaces **son el mismo**. Si lo dice, el informe por red es inexplicable por muy exactos que sean sus números | 27 |
| Interesado | Si el formulario se rellena de verdad en **treinta segundos** desde un teléfono, y en qué campo se para si no | 25 |
| Líder | Si lo primero que mira para contar los prospectos sin asesor es el **tablero** —el contador vive en «Publicaciones»— | 25 · 28 |
| Asesor | Si al entrar **lee** la bandeja «Hoy» o se va a «Prospectos» por costumbre, y si encuentra «Ya está» sin que nadie se lo nombre | 28 |
| Todos | Cerrar un prospecto con su motivo: **nadie lo ha ensayado con una persona delante** | 30 |

**Nota sobre una nota:** el capítulo 28 dio por cerradas dos observaciones y solo una lo
estaba. Al líder se le dio ver los `HOT` que se enfrían, que es **otra pregunta distinta** de
cuántos esperan a que los repartan. Queda escrito porque el error no fue de código: fue dar
por resuelto un síntoma parecido al anotado.

---

## 5. Decisiones que no son técnicas

Aquí está construido lo necesario. Lo que falta es que alguien decida.

### 5.1. Los plazos de conservación no tienen valoración jurídica

**(R20 §20.8, R22 §22.9)**

Son **técnicos y provisionales**. Fijarlos corresponde a quien responda del tratamiento de
datos. La **oposición al tratamiento** no está modelada.

### 5.2. Aceptar el aviso de privacidad no es condición para crear la ficha

**(R21 §21.12)**

Se registra si llega. Qué hacer cuando no llega —rechazar la ficha, crearla marcada, crearla
y no contactar— es una decisión de quien responde del tratamiento, no del código.

**Sigue abierta tras el capítulo 38**, y conviene decirlo porque ese capítulo tocó justo al
lado. El punto 14 de §6.2 cerró que el alta del panel **ofreciera** la casilla; esta entrada
es si **exigirla**, y ahí no se tocó nada: la casilla no es obligatoria. La diferencia con la
página pública, donde sí lo es, es deliberada —allí la marca la persona, aquí la marcaría el
asesor por ella—, y obligarla garantizaría que se marque siempre, que es lo contrario de que
signifique algo (R36 §38.7).

### 5.3. Suprimir aquí no suprime en el CRM

**(R20 §20.8)**

Una entrega posterior del CRM vuelve a crear a la persona. La huella con clave permitiría
reconocerla y **rechazar la ingesta**, pero bloquear una entrada de negocio es una decisión
que nadie ha tomado. Las copias de seguridad conservan a la persona suprimida hasta 14 días;
no se editan volcados, y está dicho en la propia exportación.

**Tras el capítulo 38 la advertencia está donde se ve, que es todo lo que puede hacer el
software.** Hasta entonces vivía en este documento y en el campo `fuera_de_la_base` del JSON
de exportación, y ninguno de los dos lo lee quien atiende una petición de borrado. La
pantalla de derechos lo dice dos veces —en el bloque de confirmación y en el mensaje de
éxito— y dice además la mitad que no es obvia y que cambia lo que hay que hacer: no es solo
que los datos sigan allí, es que **volverán** con la siguiente entrega. Lo que falta es un
procedimiento para el otro lado, y eso sigue sin decidirse aquí.

### 5.4. «¿Qué necesitas?» no tiene peso

**(R25 §25.10)**

Informa y nada más. Darle peso —que una demostración pedida en la página cuente como
interés— es una decisión de negocio. Antes lo tenía y sumaba 25 puntos; el capítulo 25 se lo
quitó porque nadie había decidido que lo tuviera.

### 5.5. Reabrir un prospecto cerrado no es una operación del sistema

**(R29 §30.14)**

**Corregir** un cierre equivocado sí: se vuelve a cerrar y la fila se reescribe. Devolver un
trato a «En negociación» exigiría decidir qué pasa con su desenlace —si se borra, si se
conserva como histórico, si el dataset lo sigue usando—, y esa decisión no se ha tomado.

### 5.6. El peso de los motivos y la previsión de ingresos

**(R29 §30.14)**

Ningún motivo suma ni resta. El tramo del acuerdo agrupa lo ganado y **no se multiplica por
nada**. Si algún día se quiere saber si el motivo predice algo, eso es un análisis sobre los
datos ya recogidos, no una constante escrita a ojo.

### 5.7. El alta del panel no pregunta los ingresos

**(R24 §24.9)**

Deja el campo vacío y se rellena desde la ficha. Añadir el campo al alta es producto.

### 5.8. No hay A/B de textos

**(R26 §26.11)**

Una publicación tiene un texto. Duplicarla es la forma honrada de comparar dos hoy: dos
publicaciones, dos enlaces, la comparativa lado a lado.

### 5.9. No hay candidatos

**(R25 §25.10)**

La historia es de **prospectos comerciales**. Los perfiles que PluriOne coloca en sus
clientes son otra historia y otro sistema.

---

## 6. Deuda de ingeniería

No depende de nadie. Se puede hacer hoy. Ordenada por lo que cuesta si nadie la toca.

### 6.1. Lo que puede morder

> **Estado tras el capítulo 32 (cerrado el 24-09-2026).** De los ocho puntos, **seis
> cerrados**: 1, 2, 3, 4, 5 y 8. Quedan abiertos el **6** y el **7**, y los dos por el
> mismo motivo, que está escrito debajo de la tabla. La lista se conserva entera, tachada,
> porque un backlog del que se borran las filas resueltas deja de servir para saber qué se
> decidió y cuándo.
>
> Entra además un punto nuevo, el **24**, que el propio capítulo 32 encontró al comprobar si
> un país escrito por error se podía corregir desde el panel. No se cerró porque el arreglo
> afecta a **todos** los campos de la ficha a la vez y eso es una decisión de diseño con su
> propia discusión, no una corrección.

> **Estado tras el capítulo 33 (cerrado el 24-09-2026).** El punto **24** queda cerrado: la
> decisión que el capítulo 32 dejó por tomar se tomó, y la corrección completa está en el
> Reporte 31 (§33.2–§33.5). Vuelve a ser cierto lo que decía el capítulo 32: **§6.1 no tiene
> ningún punto que este equipo pueda cerrar por su cuenta**. Quedan el 6 y el 7, los dos
> esperando a un sistema externo.
>
> El 24 duró un capítulo, y conviene decir cómo se encontró porque no fue por donde se
> suelen encontrar estas cosas. No lo vio una prueba, ni el CI, ni una revisión: lo vio
> alguien preguntándose si el arreglo que acababa de escribir se podía usar. El capítulo 32
> quitó el país supuesto de cuatro sitios y escribió una migración que solo podía tocar
> parte de las fichas; las demás quedaban «a que un asesor las corrigiera», y nadie había
> comprobado que eso fuera posible. No lo era.

| # | Qué | Por qué importa | Origen | Estado |
| :---: | :--- | :--- | :---: | :---: |
| 1 | ~~**El CSV de realimentación no caduca**~~ | Vive fuera de la base y fuera del control de versiones. Es la última fila de la política de conservación sin plazo, y lleva datos de personas | R20 §20.8 · R22 §22.9 | **Cerrado** (R32 §32.2) |
| 2 | ~~**La bitácora de auditoría no tiene plazo en la aplicación**~~ | Es una decisión de operación desde el capítulo 14 y crece sin techo | R22 §22.9 | **Cerrado** (R32 §32.3) |
| 3 | ~~**`App.jsx` sigue sin pruebas**~~ | La redirección al cambio obligatorio de contraseña y el que no se lancen cargas de datos en ese estado están comprobados por lectura y por la prueba del componente, no por la aplicación montada. Arrastra desde el capítulo 17 y el 19 le añadió dos comportamientos más | R19 §19.9 | **Cerrado** (R32 §32.5) |
| 4 | ~~**La guarda no mira `apt-get`**~~ | Los cuatro paquetes de seguridad del backend van con versión; `libpq5` y las herramientas de compilación de la primera etapa, no. La guarda solo exige versión a `apk`: la misma indeterminación que se quitó en Alpine, a medias | R22 §22.9 | **Cerrado** (R32 §32.6) |
| 5 | ~~**Las acciones de GitHub van por etiqueta**~~ | `actions/checkout@v4`, no por el SHA del commit. Todo lo demás del CI va por huella | R22 §22.9 | **Cerrado** (R32 §32.6) |
| 6 | **Una entrega de WhatsApp con varios mensajes no es atómica** | Se validan todos antes de escribir, pero si el tercero falla al registrarse los dos primeros quedan. Un reintento los encuentra como duplicados, así que no corrompe; deja trabajo a medias | R21 §21.12 | **Abierto** |
| 7 | **Sin `event_id`, el CRM se deduplica por contenido** | Dos eventos reales idénticos byte a byte entran como uno | R21 §21.12 | **Abierto** → §3.10 |
| 24 | ~~**Ningún campo de la ficha se puede vaciar una vez escrito**~~ | La actualización parcial aplicaba `if value is not None`, así que un `null` explícito se ignoraba. Se podía cambiar un valor por otro; no borrarlo. Y no respondía que no: respondía **200 con la ficha entera**, de modo que la pantalla decía «Prospecto actualizado» y el dato seguía ahí | R32 §32.9 | **Cerrado** (R33 §33.2–§33.5) |
| 8 | ~~**El país sigue supuesto**~~ | La ficha escribe «México» cuando no llega. No puntúa en ninguna de las dos mitades del score, y quitarlo exige una migración de la columna | R25 §25.10 · H-7 | **Cerrado** (R32 §32.4) |

**Por qué 6 y 7 siguen abiertos, uno por uno.**

**6 — La entrega de WhatsApp con varios mensajes.** Arreglarlo es escribible: envolver el
registro de los mensajes de una entrega en una transacción y deshacerla entera si uno falla.
No se hizo porque **no se puede comprobar que esté arreglado**. Nadie ha conectado nunca una
cuenta de WhatsApp Business a este sistema (§3.2), así que la única forma de ejercitar el
caso es una prueba que simule el fallo del tercer mensaje, y eso comprueba el código que se
acaba de escribir, no el comportamiento con el proveedor real: no se sabe si WhatsApp
reentrega la tanda entera o solo lo que faltaba, y de esa respuesta depende si la
transacción única es la corrección o el problema. El daño mientras tanto está acotado y
medido: no corrompe nada —el reintento encuentra los dos primeros como duplicados por
`(source, external_event_id)`— y lo que deja es trabajo a medias, visible en la bandeja.
Pertenece a §3, «depende de cuentas externas», más que a la deuda de ingeniería.

**7 — La deduplicación por contenido del CRM.** Aquí no hay nada que escribir: la clave de
deduplicación es `(source, external_event_id)`, y cuando el sistema de origen **no manda**
identificador, la única huella disponible es el contenido. La alternativa —aceptar los dos
eventos y dejar que el operador decida— cambia un caso raro y sin daño (dos eventos reales
idénticos byte a byte, incluido el instante, entran como uno) por uno frecuente y con daño
(cada reentrega del CRM duplica la actividad). La corrección de verdad es que el CRM mande
`event_id`, y eso no se decide aquí. **Queda reclasificado a §3**, con lo demás que depende
de que alguien del otro lado haga algo.

Es decir: cerrado el punto 24 en el capítulo 33, **§6.1 no tiene ningún punto que este
equipo pueda cerrar por su cuenta**. Los dos que quedan esperan a un sistema externo, no a
más trabajo.

**24 — Vaciar un campo.** Cerrado en el capítulo 33. La decisión que el 32 dejó pendiente
—qué pasa cuando el vacío llega a un campo que la ficha no puede no tener— se resolvió con
un 422 que nombra el campo, y con la lista de campos obligatorios **derivada de la tabla**
en vez de escrita a mano, que es lo que evita que el arreglo caduque en la primera migración
que toque un `nullable`. La bitácora distingue desde entonces los campos vaciados de los
cambiados, sin copiar valores.

### 6.2. Huecos de la historia que se enseña

> **Estado tras el capítulo 46 (cerrado el 06-10-2026).** El punto **10** queda cerrado, y es
> el primero de los cuatro que el capítulo 38 dejó abiertos por exigir comportamiento nuevo
> del servidor. Lo exigía, y se escribió: el reparto automático reparte cada ficha nueva sin
> asesor entre las cuentas activas que atienden cartera, por cartera abierta y con el tiempo
> sin recibir como desempate. §6.2 queda en **cinco cerrados de nueve** —10, 11, 13, 14 y
> 16—, y los tres que siguen abiertos por el mismo motivo —el 9, el 12 y el 15— lo siguen
> estando: cerrar uno porque se encargó no convierte los otros en correcciones.
>
> **Estado tras el capítulo 38 (cerrado el 01-10-2026).** De los ocho puntos, **cuatro
> cerrados**: 11, 13, 14 y 16. Quedan abiertos el **9**, el **10**, el **12** y el **15**, y
> los cuatro por el mismo motivo, escrito debajo de la tabla: exigen decidir comportamiento
> **nuevo** del servidor, y eso es funcionalidad, no corrección.
>
> El capítulo 38 abrió la congelación para los tres que eran lo mismo con tres caras —una
> capacidad que existe, está probada y **no se puede usar desde donde hay que usarla**— y
> para ninguno más. No añadió ni un endpoint, ni una tabla, ni una migración: el servidor
> del capítulo 38 es el del 37 más un archivo de pruebas.
>
> Entra además un punto nuevo, el **35**, que el propio capítulo encontró al enlazar el
> contador del tablero con la matriz. No se cerró porque el arreglo honrado exige un
> parámetro nuevo en el listado, y hacerlo en el cliente sobre una página de cincuenta
> habría reproducido la discrepancia del capítulo 27.

| # | Qué | Estado | Origen |
| :---: | :--- | :--- | :---: |
| 9 | **Las integraciones no atribuyen la ficha a una campaña** | `formulario_web`, `linkedin_lead_gen`, Calendly y WhatsApp no leen el UTM. **Solo la página de interés atribuye.** H-4 está cerrado para ese camino y abierto para los demás | R25 §25.10 |
| 10 | ~~**La asignación automática es solo para las fichas `HOT`**~~ | H-6, a medias: hay dónde repartir, pero nada reparte solo. Una ficha `WARM` o `COLD` espera a que el líder la asigne. **Cerrado en el capítulo 46**, y el punto estaba corto por un lado: lo que repartía no solo se limitaba a los `HOT`, es que **tampoco repartía** —`ORDER BY capacity DESC` le da todas las fichas a quien tenga el número más alto en su cuenta hasta que alguien lo cambie—. Ahora se reparte por cartera **abierta**, con el tiempo sin recibir como desempate, entre cuentas activas que atienden cartera; no se toca lo que ya tiene asesor ni lo que viene de una publicación con responsable; corre una sola vez, en el alta, así que una reasignación a mano no se deshace; y se apaga con `REPARTO_AUTOMATICO_ACTIVO`. Sin tabla, sin columna, sin migración y sin pantalla | R25 §25.10 |
| 11 | ~~**El contador de «sin asesor» vive en «Publicaciones»**~~ | No en el tablero, que es donde el líder mira primero. Es la nota de usabilidad que el capítulo 28 dio por cerrada sin estarlo. **Cerrado** en el capítulo 38: el bloque se sacó a `ContadorSinAsesor` y se monta en los dos sitios —el mismo componente, no una copia del texto—, con enlace a la matriz, pedido solo a quien dirige la cartera y distinguiendo «no se preguntó» de cero (R36 §38.8) | R25 §25.10 · R28 §28.13 |
| 12 | **El reparto de la cartera de una baja es todo o nada** | A un solo destino. Repartir entre varias personas exige hacerlo prospecto a prospecto, y no hay aviso fuera del panel de administración | R19 §19.9 |
| 13 | ~~**El teléfono de los asesores no se normaliza**~~ | `users.phone`. El capítulo 21 se ocupó del de los prospectos. **Cerrado** en el capítulo 32: mismo E.164 y mismo módulo (`app.core.telefono`), con migración de los que ya estaban escritos de otra forma (R32 §32.4) | R21 §21.12 |
| 14 | ~~**El alta del panel no ofrece la casilla del aviso de privacidad**~~ | La API la admite (`privacy_notice_accepted`); la pantalla, no. **Cerrado** en el capítulo 38, y lo delicado no era que existiera: nace **sin marcar** —una aceptación por omisión es una suposición con fecha, indistinguible de las de verdad—, se envía siempre y **no** es obligatoria, que sigue siendo el §5.2 (R36 §38.7) | R21 §21.12 |
| 15 | **No hay pantalla para configurar integraciones** | Se encienden y se revocan por variables de entorno | R21 §21.12 |
| 16 | ~~**No hay interfaz para exportar ni para explicar la supresión**~~ | Los derechos del titular son API. Funcionan y están comprobados; no tienen pantalla. **Cerrado** en el capítulo 38: pantalla en administración que busca por correo, enseña qué consta y de dónde llegó, exporta el documento del servidor y suprime exigiendo que el correo se **escriba**, con su constancia. Sin lógica de supresión nueva (R36 §38.2–§38.6) | R20 §20.8 |
| 35 | **El listado no se puede filtrar por «sin asesor»** | El contador del tablero lleva a la matriz, donde las fichas que esperan llevan su marca, pero la lista no se acota a ellas. Filtrarla exige un parámetro nuevo en el servidor; hacerlo en el cliente sobre una página de cincuenta reproduciría la discrepancia del capítulo 27 —un número que dice siete y una lista con dos marcas— | R36 §38.10 |

**Por qué 9, 12 y 15 siguen abiertos.** Los tres piden que el servidor **haga algo que hoy no
hace**: leer el UTM en cuatro conectores y decidir qué gana cuando hay dos atribuciones
posibles; partir una cartera entre varias personas; y encender integraciones desde una
pantalla, lo que significa guardar y rotar sus secretos en la base en vez de en el entorno.
Ninguno es «la frase ya está escrita y el código no la cumple»; los tres son frases nuevas.
Es la distinción del §1, y es la que dejó entrar a los tres del capítulo 38 y detuvo a estos.

El **10** era el cuarto de esa lista y se cerró en el capítulo 46 porque se encargó
explícitamente, no porque hubiera dejado de ser funcionalidad. La distinción del §1 sigue
siendo la misma: lo que cambió no es el criterio, es que alguien decidió abrir la congelación
para ese punto. Queda escrito para que la siguiente vez no se lea como un precedente.

**16, 14 y 11 — qué se cerró exactamente.** Lo que faltaba no era la capacidad, era el
alrededor. En el 16: encontrar a la persona por su correo comparando la **igualdad** y no la
coincidencia parcial del buscador —quedarse con la primera fila del `LIKE` entrega o
destruye los datos de otra persona—; decir qué hace cada acción **antes** de ofrecerla;
contestar **lo mismo** para una dirección que nunca entró y para una cuya ficha ya no está,
para no ser el oráculo de pertenencia que la huella con clave de la bitácora evita; y avisar
de que suprimir aquí no suprime en el CRM (§5.3), dos veces y donde se ve. En el 14 y el 11,
lo que está en la tabla. Los tres quedan vigilados por los controles 46 y 47 del CI, con 22
defectos reintroducidos y 22 detectados.

### 6.3. Comprobaciones que nadie ha hecho a mano

| # | Qué | Por qué no se hizo | Origen |
| :---: | :--- | :--- | :---: |
| 17 | ~~**El código QR no se ha escaneado con un teléfono**~~ | Se comprueban las propiedades matemáticas y estructurales que exige la norma, que es lo verificable sin lector. **Es lo primero que habría que hacer antes de repartir material impreso**. **Hecho el 01-10-2026, y no lo leyó**: la información de formato iba transpuesta desde el capítulo 27, así que ningún lector podía empezar a decodificar. Las diecinueve pruebas del QR estaban verdes porque todas miden propiedades **simétricas respecto de la diagonal**. Corregido, con un lector escrito dentro de la suite y el control 48 del CI (R36 §38.10a) | R27 §27.13 · R36 §38.10 |
| 18 | **El panel no se ha recorrido con una persona dentro** | Entrar exige iniciar sesión. La suite del cliente y el ensayo automático cubren las pantallas; una persona, no. **El capítulo 36 acercó la mitad verificable** —las pantallas que ese capítulo listó pasan WCAG 2.1 AA medido por `axe`, se recorren con teclado y sus errores llegan a un lector de pantalla (R36)—, **el 39 la acercó más** —todo lo que el marcado nombra, clases y variables de la paleta, existe ahora en la hoja, y el contorno de los controles llega al mínimo de §1.4.11 sin que el foco deje de distinguirse (R37)—, **el 40 dio por cerrado el último hueco medible** —ningún color del cliente se escribe fuera de la paleta, que es el único sitio donde se mide, y cuando el servidor rechaza un campo la pantalla lo señala, lo explica en castellano y lleva el foco hasta él (R38)— **y el 44 enseñó que quedaba uno**, que era la propia lista: esa mitad verificable eran **ocho pantallas de las dieciocho** que llevan controles, y en las nueve que nadie montaba había tres deslizadores sin nombre accesible, un selector de rol sin nombre, un `aria-label` que ARIA no admite donde estaba y dos pantallas enteras fuera de toda región. Hoy la auditoría pasa por las dieciocho y **su lista sale del código** (R42 §44.1, §44.10). Del capítulo 36 queda abierto lo que el punto 47 cuenta: el recorrido con teclado mira 2 y los anuncios 5. Lo que sigue sin responder es si **lo que se ve y lo que ese lector dice se entienden**, y eso no lo contesta ninguna herramienta | R28 §28.13 · R36 §36.8 · R37 §39.14 · R42 §44.1 |
| 19 | **Nadie ha visto una solicitud de Dependabot en este repositorio** | `.github/dependabot.yml` está bien formado y el control 45 comprueba que cubre los seis ecosistemas y que la renovación a mano sigue mandando. Lo que ninguna prueba sustituye es el **primer lunes** que abra solicitudes de verdad: qué propone, si el CI las deja verdes y si alguna choca con la guarda `--solo-fijacion` | R37 §37.10 |
| 20 | **La comprobación de contraseñas filtradas no se ha ejecutado nunca contra el servicio real** | La suite usa una sonda simulada a propósito: una suite que depende de un tercero se pone roja los días que ese tercero tiene un mal día. Lo que falta por saber es si el contexto TLS del sistema basta desde la máquina del despliegue — y si no bastara, **el síntoma sería silencioso**: la política ante «no se pudo preguntar» es seguir adelante, así que la comprobación estaría apagada de hecho mientras el código afirma tenerla. **Es lo primero que hay que mirar en la bitácora el día del despliegue**, buscando el `WARNING` de `app.core.filtradas_remotas` | R37 §37.4 · §37.10 |

### 6.4. Restos menores

| # | Qué | Origen |
| :---: | :--- | :---: |
| 19 | `socat` y `pgAdmin` van fijados por huella, pero su etiqueta dice `latest` y no la versión | R22 §22.9 |
| 20 | Fuera de Docker la aplicación lee `.env` y `../.env` desde donde se lance; el lanzador cubre la pila, `uvicorn` directo depende de quien lo lanza | R22 §22.9 |
| 21 | En el entorno de desarrollo de **esta máquina** quedan `cffi`, `cryptography` y `pycparser`: un proceso ajeno tenía abierto `_cffi_backend.pyd` y no se detuvo. El código no los importa, el CI instala desde cero y la imagen no los lleva | R23 §23.7 |
| 22 | ~~Los ceros de ingresos que ya hay en la base no se migraron a nulos. El extractor los lee como ausentes, que es lo que importa al modelo; la ficha los muestra como cero hasta que alguien la edite~~ — **cerrado** en el capítulo 32: la migración `a4c8d1e70f39` los pasa a vacío y la base dice ya lo que el modelo leía (R32 §32.4) | R24 §24.9 |
| 23 | Un aviso purgado puede volver a entrar si el sistema de origen lo reentrega pasado el plazo; y **descartar no bloquea** | R21 §21.12 · R22 §22.9 |
| 25 | ~~El **alta** no normaliza los textos en blanco: `LeadCreate` guarda `''` donde la edición guarda `NULL` desde el capítulo 33. Es el mismo arreglo en otro camino, y afecta también a las integraciones que dan de alta fichas, así que tiene su propia discusión~~ — **cerrado en el capítulo 41**, y el punto estaba corto en tres sitios. El alta y la edición no son dos puertas sino dos de **cinco**, y de los 61 campos de texto de las entradas **34 guardaban el blanco**; la única que lo rechazaba era el formulario público, con una línea de configuración que nadie más tenía desde el capítulo 34. La frase sobre las integraciones era además falsa: las dos normalizaban ya, con una copia privada de la misma función —ahora comparten `app.core.texto.texto_o_nada`—; lo que no normalizaba nadie era el **sobre** del webhook. **Lo importante no es el arreglo sino lo que apareció al hacerlo**: el alta de una cuenta declaraba un mínimo de dos caracteres y recortaba **después** de comprobarlo, así que dos espacios lo cumplían y se guardaban como `''`; y la regla que el 33 derivó de la tabla estaba escrita dentro del esquema de **una** tabla, de modo que las otras dos ediciones parciales contestaban 500 a un `null` sobre una columna obligatoria (R39 §41.2, §41.4) | R33 §33.8 |
| 26 | ~~El `except IntegrityError` de la edición traduce **cualquier** violación de integridad a «el correo ya existe», que es lo único que podía producirla. Con el 422 del esquema delante, un nulo sobre una columna `NOT NULL` no llega a ese commit; si llegara, el mensaje sería equivocado. Distinguir qué restricción falló obliga a leer el error del motor, específico de PostgreSQL y de SQLite por separado~~ — **cerrado en el capítulo 42**, y el punto estaba corto en dos sitios. El primero: «si llegara» ya llegaba. `leads` tiene dos claves ajenas además de la restricción única, así que un `assigned_rep_id` que no existe pasa el esquema —es un entero— y lo rechaza la base **sin ninguna carrera**; el 409 que salía nombraba el correo de la propia ficha, que quien editaba no había tocado. El segundo: leer el error del motor no sirve para el caso más probable, porque SQLite nombra la columna en `UNIQUE constraint failed: leads.email` y para una clave ajena dice exactamente `FOREIGN KEY constraint failed` y nada más. Así que no se lee el mensaje: se **pregunta a la base** cuál de sus reglas no se cumple, con la lista sacada de `__table__`. Eran siete `except IntegrityError` —dos preguntaban, cuatro suponían, uno no tenía que averiguar nada— y el más caro era el del webhook del CRM, que contestando «duplicado» **descartaba el evento entero**. **Lo importante no es el arreglo sino por qué no se podía encontrar**: el motor de la suite no comprobaba ninguna de las 18 claves ajenas del esquema (R40 §42.2, §42.5, §42.8) | R33 §33.8 |
| 27 | El **bundle de la SPA es descargable** desde la puerta pública: la página de interés lo necesita para dibujarse y es un solo archivo. Es código de cliente sin secretos y no puede llamar a nada —las rutas de gestión no existen en esa puerta—; evitarlo exigiría compilar un segundo bundle solo para esa página | R34 §34.8 |
| 28 | El **túnel no arranca con la pila**: hay que abrir una ventana y dejarla abierta, y la dirección hay que copiarla a mano en `pila.env` en cada arranque. Es deliberado mientras la dirección sea efímera —cerrar la ventana apaga la exposición al instante—, y es lo primero que se automatiza cuando haya dominio | R34 §34.8 |
| 29 | Un administrador **no puede quitarle el segundo factor a otro** desde el panel: la salida (b) de la guía existe en el diseño pero no tiene botón, porque la gestión de cuentas no ganó esa operación. Hoy se resuelve por la vía (c), que es la misma sentencia SQL | R35 §35.9 |
| 30 | ~~**`CompartirEnRedes` se dibuja sin ningún estilo.** El componente no usa ni un estilo en línea: se apoyaba entero en **catorce clases que la hoja no definía**, así que el panel de difusión y el del QR salían con el estilo por omisión del navegador~~ — **cerrado en el capítulo 39**: las catorce están escritas, con los tokens que ya existían y sin añadir ni un color, porque lo que faltaba era la hoja y no la paleta. El aviso de «la dirección pública no contesta» pierde el estilo en línea que el capítulo 38 le puso, y **no** hereda la clase de las notas de cada red: tiene la suya, porque un aviso de que lo que se está haciendo no sirve para nada no puede verse como una nota al pie. El tamaño del código QR deja de ser el que trajera el SVG y pasa a tener un suelo medido —**5 píxeles CSS por módulo**, 5,99 con el enlace real—, que es la unidad en que una cámara de teléfono resuelve o no resuelve un código. Al mirar el panel ya maquetado apareció además que `.btn` no declaraba `color`: el único `<a class="btn">` del cliente salía en azul de enlace sobre el panel oscuro, 1.87:1 (R37 §39.9, §39.10) | R36 §36.6 |
| 31 | ~~**`btn-danger` no existe.** «Cerrar sesión» pide un aspecto de acción destructiva que la paleta no tiene, así que se dibuja como un `.btn` a secas —borde transparente, sin fondo— y no parece un botón~~ — **cerrado en el capítulo 39**: la paleta tiene una familia `--danger-*` propia, y **no** se reutilizó la de HOT, porque ese rojo es una temperatura de prospecto y pintar «Cerrar sesión» con él diría que ese botón es un prospecto caliente. Relleno sólido con 6.18:1 de texto y borde aparte, porque el relleno solo da 2.87:1 contra el panel y lo que delimita el botón es el borde. Lo usan «Cerrar sesión» y los dos de la pantalla de derechos; el de confirmar era `btn-primary`, el mismo blanco que «Buscar», y en esta paleta el blanco significa «la acción esperada de esta pantalla». Al darle relleno sólido apareció que **la hoja no tenía ningún `:disabled`** y quince componentes apagan botones: se escribió, con colores y no con `opacity`, sobre un par ya medido (R37 §39.7, §39.8) | R36 §36.6 |
| 32 | ~~**El borde de un campo sin foco tiene 1.12:1** contra lo que lo rodea: el contorno es prácticamente invisible hasta que se le pone el foco. WCAG §1.4.11 pide 3.0 para lo que identifica un control~~ — **cerrado en el capítulo 39**, y no subiendo `--border-subtle`: ese token dibuja a la vez el contorno de un campo y la raya entre dos filas de una tabla, y §1.4.11 habla de **controles**, no de líneas. Hay ahora dos familias: `--border-subtle` y `--border-medium` para separar, y **`--border-control`** (3.02:1 en el peor de los cinco fondos) para delimitar un control. **Lo importante no es el arreglo sino lo que apareció al hacerlo**: con el reposo en 0.34 y el aro de foco donde estaba, 0.35, los dos quedaban a 1.11:1 entre sí —§1.4.11 cumplido **incumpliendo §2.4.7**—, así que el foco sube a 0.71, la primera alfa en que el cambio de estado alcanza 3.0 **en los dos controles donde ocurre**. El que manda es el botón secundario: con 0.70 se queda en 2.99, y medir solo el campo lo habría dejado pasar (R37 §39.5, §39.6) | R36 §36.8 |
| 33 | ~~**`var(--accent-primary)` no existe** en la paleta —el token se llama `--color-primary`—, así que el borde superior del girador de carga de `App.jsx` se queda sin color. Cosmético, y en un elemento que dura lo que una petición~~ — **cerrado en el capítulo 39, y estaba mal medido**: eran **cinco** tokens en nueve sitios, y dos no eran cosméticos. Un `var()` que no resuelve no deja la propiedad en su valor anterior, la deja en el **inicial**: `background: var(--hot-gradient)` dejaba la barra de distribución del tablero en `transparent` —el gráfico que dice cómo se reparte la cartera no pintaba nada— y el `border` de la opción elegida de la ficha 360 se caía entero a `border-style: none`. Los cinco están definidos, y lo que impide que vuelva a pasar no es haberlos escrito sino `frontend/src/pruebas/tokens.test.js`, que **saca la lista del código** como `clases.test.js` hace con las clases: un token nuevo sin definir nace en rojo. `var(--x, respaldo)` no cuenta como defecto —alguien dijo qué pasa si no está— y por eso los que lo llevan están inventariados: si no, bastaría una coma para silenciar la comprobación (R37 §39.2, §39.3, §39.4) | R36 §36.8 |
| 34 | **La lista LOCAL de contraseñas filtradas no se actualiza sola.** Viene de §3.7, que el capítulo 37 cerró a medias: la comprobación contra el servicio público por rango añade cientos de millones de huellas, pero la lista de la imagen —la que decide cuando no hay internet— sigue siendo la foto del capítulo 23. Se regenera con `scripts/generar_lista_de_contrasenas.py`. No depende de ninguna cuenta; depende de que alguien lo corra, y por eso ya no vive en §3 | R23 §23.7 · R37 §37.10 |
| 36 | ~~**La hoja no tiene estado de error para los campos.** Un `.input-field` con un valor inválido se ve exactamente igual que uno correcto: lo que avisa es el `.form-error` de debajo~~ — **cerrado en el capítulo 40**, y dibujado sobre `[aria-invalid='true']` y no sobre una clase propia: así la hoja pinta **exactamente** lo que el lector de pantalla anuncia, y no hay dos verdades sobre el mismo campo. Las había: el atributo llevaba puesto en la página pública desde el capítulo 34 y la hoja no lo miraba. El mensaje de debajo se queda —§1.4.1 no admite que el color sea el único portador—; lo que el borde añade es **cuál** de los ocho campos es. **Lo importante no es el arreglo sino lo que apareció al hacerlo**: el borde rojo no puede cambiar con el foco, y ningún color alcanza los 3.0 por encima de él —1.96 el aro de la paleta, 2.60 el rojo más claro que sigue siendo rojo, y solo el blanco puro pasa, que no es un rojo—, así que el foco es un aro **añadido** por fuera. Cuando no hay salida cromática, la salida es geométrica (R38 §40.5, §40.6) | R37 §39.14 |
| 37 | ~~**Las otras siete formas del panel siguen enseñando el nombre de la columna, y diez avisos escriben su geometría en línea.** El capítulo 40 repartió el 422 por campos en las cuatro formas que pueden recibirlo con más de un campo y escribió `.alert` y sus tres variantes en la hoja; en las demás, un 422 sigue saliendo por `parseApiError` como `nueva: La contraseña está en la lista de filtradas`, con el nombre del campo del esquema delante, y diez avisos conservan sus siete propiedades en un `style`. **No incumple ningún mínimo**: es el mismo arreglo en los sitios donde el 422 es menos probable, y hacerlo toca diez componentes más sin corregir ningún número~~ — **cerrado en el capítulo 43, y el punto estaba mal en cuatro sitios**. (1) Los diez avisos con `className="alert"` llevan **una** propiedad en su `style`, un margen; los que escribían la caja entera eran otros **diecinueve**, los que nunca recibieron la clase, uno de ellos sin `role` y otro sin caja ninguna. (2) «No incumple ningún mínimo» era falso: **un par de colores escrito en un `style` es un par que la suite de contraste no puede ver**, y al derivar los pares del código aparecieron siete combinaciones sin medir, dos por debajo de los 4.5 de §1.4.3 —`--text-muted` sobre el relleno de un chip da 4.47 sobre el panel y 4.18 sobre el elevado; sobre el de una insignia, 4.36 con el ratón sobre la fila—. (3) El nombre de la columna no lo escribían siete pantallas sino **una función en un sitio**, `parseApiError`, y se quita en vez de traducirse: la etiqueta de cada campo es la que cada pantalla tiene al lado de su `input`, y una tabla global sería una segunda verdad. (4) El renglón del ejemplo no existe: el campo es `nueva_contrasena` y ese rechazo llega como un detalle estructurado cuyos **motivos el cliente tiraba desde el primer commit** (R41 §43.5, §43.6, §43.8, §43.9) | R38 §40.12 |
| 38 | ~~**Siete errores del panel se avisan con un `alert()` del navegador**: seis en el recálculo masivo de `App.jsx` y uno en el recálculo de una ficha. Un cuadro del navegador no forma parte de la página —ningún lector de pantalla lo anuncia como contenido—, no se puede señalar junto a nada y tapa lo que hay que corregir. Los demás no son errores de un campo y darles sitio en la pantalla es otra decisión~~ — **cerrado en el capítulo 43, y el punto estaba corto por los dos lados**. Eran **seis y todos en `App.jsx`** —el de la ficha lo había movido el capítulo 40 sin que nadie actualizara esta línea—, uno no era de ningún recálculo y **dos no eran errores**: uno anunciaba un éxito y otro que el trabajo seguía en curso, así que `alert()` era la única forma que el panel tenía de decir cualquier cosa fuera de un formulario. Y había **dos cuadros más** que este punto no contaba: un `confirm` que decidía el borrado de un aviso sin asociar y un `window.prompt` que pedía la contraseña de otra cuenta **en claro**, sin repetición que comprobara la errata y sin sitio donde enseñar los motivos de la política. Los ocho están ya en la página, con `role="alert"` para lo que falla y `role="status"` para lo que no, y el velo del recálculo —que tapa la pantalla durante minutos— dice ya que está trabajando (R41 §43.2, §43.3, §43.4) | R38 §40.12 |
| 39 | ~~**`--warm-*` hace dos oficios, y dos usos de `--hot-text` también.** El capítulo 40 partió el rojo —`--error-*` para lo que avisa de un fallo, `--hot-*` para la temperatura de una ficha— y dejó sin partir el ámbar: `.alert-warn` usa la familia WARM porque el ámbar de esta paleta es ese y no hay otro. Es el mismo trabajo que el rojo y no se hace a medias~~ — **cerrado en el capítulo 43**, con una familia `--warn-*` de los **mismos valores**: sigue sin haber otro ámbar, así que lo que se separa no es el color sino la decisión de moverlo. Con un solo token, el día que la temperatura WARM necesite otro ámbar habría que elegir entre tocar el gráfico del tablero o dejar el aviso mal, y esa elección no debería existir. Los oficios eran además más de los que el punto contaba: aparte de `.alert-warn`, advertían con la familia de la temperatura el cartel de las cuentas de baja, la columna de las contraseñas prestadas, el aviso de los códigos de recuperación agotados, el del enlace caducado y la confirmación de una supresión. Y `.alert-warn` **no la usaba ningún componente**: el ámbar era la variante del aviso que no tenía dónde salir (R41 §43.11) | R38 §40.3, §40.12 |
| 40 | ~~**El alta de una ficha no tiene la red del `IntegrityError` que sí tiene la edición.** `create_lead` comprueba que el correo no esté registrado y después inserta; entre las dos cosas cabe otra transacción que tome ese correo, y entonces el `INSERT` viola el índice único y sale como **500**. La edición lleva ese `except` desde el capítulo 33 por este mismo motivo, con el comentario «red de seguridad ante dos actualizaciones simultáneas». Es una carrera, así que no se ve en uso normal y no la provoca ninguna prueba; va junto al punto 26, porque las dos son sobre lo que el servidor dice cuando la base rechaza algo, y se arreglan mejor juntas~~ — **cerrada en el capítulo 42**. La red está escrita y cubre las dos cosas: la carrera del correo y la clave ajena que puede perder su destino en el mismo hueco. Y la carrera no era el camino que importaba: `POST /leads` con un `campaign_id` que no existe era un **500** sin carrera ninguna, que cualquier cliente de la API podía provocar. Delante de la red va la comprobación de existencia, que es la misma función en el alta y en la edición, y el arnés obligó a demostrar que las dos capas no son la misma: la comprobación contesta **sin intentar escribir**, y eso es lo que mide su prueba (R40 §42.6, §42.7) | R39 §41.14 |
| 41 | **La suite no se ejecuta nunca contra PostgreSQL.** El capítulo 42 encendió `PRAGMA foreign_keys` en el motor, así que SQLite exige ya lo mismo que PostgreSQL en las tres clases de restricción que importan —única, obligatoria y ajena—, y eso cubrió el defecto de ese capítulo. No cubre todo lo demás en lo que los dos motores se distinguen, y la única forma de saberlo es correr la suite contra PostgreSQL: hoy ese motor solo aparece en el trabajo de migraciones y en el arranque del contenedor. Es un servicio más en el CI y varios minutos en cada ejecución, con su propia discusión; no es una corrección | R40 §42.14 |
| 42 | **La atribución de una ficha no se puede corregir.** `LeadUpdate` no acepta `campaign_id`, y desde el capítulo 42 lo **rechaza** con su motivo en vez de responder 200 y no hacer nada. Una ficha dada de alta a mano con la publicación equivocada —o sin ninguna— se queda así, y el informe de rendimiento por campaña la cuenta donde está. Que se pueda cambiar es una frase nueva: ninguna pantalla la pide, y decidir si la atribución es un dato editable o es cómo llegó el prospecto es una decisión de producto, no una corrección | R40 §42.9 |
| 43 | **El alta de una ficha contesta 400 y 409 para el mismo conflicto.** Cuando el correo repetido lo encuentra su comprobación, responde **400**; cuando lo encuentra la red del `IntegrityError` —la carrera—, responde **409**, que es lo que contesta la edición en los dos casos. Es la misma situación con dos códigos, y el 400 lleva ahí desde el capítulo 10. Cambiarlo es tocar lo que un cliente ya recibe sin corregir ningún dato | R40 §42.14 |
| 44 | ~~**Los tres campos del cambio de contraseña se nombran con un `placeholder`.** No con una etiqueta: el marcador desaparece al escribir, así que quien vuelve al campo ya no sabe cuál es, y no es lo mismo que un `<label>` para quien navega con lector de pantalla. No es un incumplimiento claro de AA —el marcador da nombre accesible al campo— y ponerles etiqueta cambia la maquetación de un modal, así que no entró con el capítulo que sí les dio la clase de la hoja y el reparto de su error~~ — **cerrado en el capítulo 44**, y el punto era correcto en todo, incluido lo que parecía su parte débil. Al montar ese panel en la auditoría, `axe` da **cero infracciones**: un marcador sí da nombre accesible, así que ningún motor se queja de un nombre que se va en cuanto se usa el campo. Son tres cajas de contraseña seguidas, idénticas en cuanto hay algo escrito —una fila de puntos—, y con el marcador como único nombre quien vuelve a la segunda no puede saber si es la nueva o la repetición. Las tres llevan ya su `<label>` con la clase que la hoja define, no un `style` nuevo, y el marcador se queda solo donde dice algo que la etiqueta no dice: «Mínimo 12 caracteres». Sus pruebas dejan de buscar los campos por el marcador y los buscan por su etiqueta, con una nueva que comprueba lo que el punto describía: que el nombre **sigue ahí con el campo lleno** (R42 §44.8) | R41 §43.12 |
| 45 | **El simulador de scoring no reparte su 422 por campos.** Es el formulario con más campos en el cuerpo —veintisiete—, y todos sus valores salen de deslizadores y listas cerradas, así que un 422 ahí es un fallo de programación y no un dato mal escrito. Con el nombre de la columna ya fuera, lo que se ve es el mensaje del servidor; repartir veintisiete campos para eso es trabajo sin ningún número que corregir. **Este punto decía «el único de los formularios que quedan donde un rechazo por campo es alcanzable» y no es cierto**: el de actividad de la ficha 360 recibe `missing`, `enum` y `string_too_long` con el campo en su `loc`, y el de cierre también podría si sus validadores dejaran de ser de modelo. Son los del punto 49, y el argumento de este punto —que un 422 ahí no es un dato mal escrito— es el que vale para los tres (R43 §45.7) | R41 §43.12 |
| 46 | **Los cinco validadores de modelo rechazan sin poder nombrar el campo, y pasarlos a validadores de campo cambia el contrato.** El punto decía «los **dos**» —el cierre de un prospecto y el registro de una actividad— y en los esquemas hay **cinco**: los tres que faltaban son los de las ediciones parciales, que el capítulo 33 escribió para una tabla y el 41 repartió a las otras dos, los dos **después** de que este punto se escribiera. Un `model_validator(mode="after")` ve el cuerpo entero y responde `loc: ['body']`, así que su 422 no cabe debajo de ningún campo —y el docstring del cierre dice lo contrario, «la convierte en un 422 que señala el campo», que no es cierto para un validador de modelo—. **La mitad que era una corrección se cerró en el capítulo 45**: los tres de las ediciones parciales escribían el nombre de la columna de la base **dentro de la frase** —«no se pueden dejar vacíos: `full_name`»—, que es lo que el 43 le quitó a `parseApiError` del prefijo y dentro de la frase no alcanza ninguna expresión regular; ahora la frase se lee sola y los campos viajan en el `ctx`, donde el cliente los reparte con la etiqueta de cada pantalla (R43 §45.5, §45.6). **Lo que sigue abierto es el `loc`**: moverlo a `['body', 'campo']` permitiría repartir también los otros dos —que no tienen el defecto del nombre, porque nombran su campo en castellano y entre comillas— y es un cambio en lo que la API contesta a un cliente que ya existe, no una corrección | R41 §43.10, §43.12 · R43 §45.4 |
| 47 | **El recorrido con teclado mira 2 de las 18 pantallas, y los anuncios a un lector de pantalla 5.** La auditoría con `axe` pasa desde el capítulo 44 por las dieciocho que llevan controles, y su lista sale del código; las otras dos suites de accesibilidad siguen tomando la suya a mano, y son las que miden lo que `axe` no puede: el **orden real del foco** al tabular y si lo que falla **llega** a un lector de pantalla. No se derivan del código como la de `axe` porque cada pantalla tiene su propio orden esperado y hay que escribirlo —trece recorridos es más trabajo que el capítulo entero—. Lo que sí es cierto es que lo estructural ya lo mira un motor en todas | R42 §44.13 |
| 48 | **Cuarenta y ocho etiquetas escriben a mano un estilo que la hoja ya define.** En diez componentes, mientras `.form-label` existe en `index.css` y ocho la usan. Es la misma forma que el punto 37 que cerró el capítulo 43 —la hoja lo tiene y el marcado lo reescribe—, una planta más abajo, y **no** es un incumplimiento: ninguna de esas etiquetas forma un par de colores sin medir, porque ninguna escribe su propio fondo. Lo que hay es un tamaño y un color que dependen del archivo, con `--text-muted` en unas y `--text-secondary` en otras, y unificarlo toca diez componentes sin corregir ningún número | R42 §44.15 |
| 49 | **El formulario de actividad y el de cierre no reparten su 422 por campos.** Son los dos del panel que no lo hacen, y desde el capítulo 45 ya **no** es un problema de idioma —los seis de nueve rechazos que llegaban en inglés llegan en castellano— sino de **dónde cae el renglón**: en el aviso de arriba y no debajo de su campo. Repartiría poco: los dos tienen pocos campos y casi todos sus rechazos son de listas cerradas que el propio desplegable ofrece, así que un 422 ahí es un fallo de programación y no un dato mal escrito —el mismo argumento que el punto 45—. Y el del cierre depende de la mitad abierta del punto 46, porque todos sus rechazos salen de un validador de modelo | R43 §45.7, §45.14 |
| 50 | **Un tipo de rechazo que la tabla del cliente no conozca sale como «No se admite este valor».** Mejor que el inglés y peor que una frase. La tabla cubre hoy los diecinueve tipos que las diecisiete puertas con cuerpo pueden contestar, y `test_lo_que_el_cliente_sabe_decir_de_un_rechazo.py` los deriva de los esquemas y exige que los cubra, así que el hueco no se puede llenar en silencio: un tipo nuevo nace en rojo. Lo que no tiene arreglo sin una segunda fuente de verdad es que el cliente diga algo sensato de un tipo que nadie ha visto todavía | R43 §45.9, §45.14 |
| 51 | **«Ver y repartir» no reparte: lleva a la matriz entera.** El contador del tablero dice «4 nuevos de publicaciones, sin asesor» y su botón cambia a la pestaña de prospectos sin filtrar nada, así que el líder aterriza en las dieciséis filas y tiene que encontrar las cuatro a ojo —la fila las marca con «Nuevo, sin asesor», pero los únicos filtros de esa pantalla son los tres cuadrantes de score—. El componente lo dice en su propio comentario: «aquí además lleva a la matriz, que es donde se abre la ficha y se asigna», así que el comportamiento es el previsto y lo que promete de más es la etiqueta. Darle un filtro propio es funcionalidad nueva | Demo 05-10-2026 |
| 52 | **Siete formularios del panel dejan la queja de un campo vacío al navegador, que la escribe en SU idioma.** Llevan `required` sin `noValidate`, así que quien pulsa «Consultar qué consta» con el correo en blanco recibe el globo del navegador y no un mensaje de la página: en un Chrome en inglés, **«Please fill out this field.»** dentro del panel en castellano. La página pública hace lo contrario desde el capítulo 39 —`noValidate` y su propio mensaje bajo cada campo—, y la razón está escrita en `LeadDetailModal`: «un cuadro del navegador no se puede señalar junto a un campo, no lo anuncia la página y tapa el formulario que hay que corregir». Son los de derechos del titular, alta de cuenta, cambio de contraseña, cierre de prospecto, alta del segundo factor, acceso y edición de ficha: **siete**, y hacerlo bien es escribir la validación de los siete | Demo 05-10-2026 |
| 53 | **La lista de cargos de la página pública mezcla los dos idiomas dentro de sí misma.** «Director de Tecnología» y «Gerente de Talento TI» conviven con «Head of Engineering» y «Engineering Manager». Los sectores se corrigieron el 05-10-2026 —son palabras corrientes y nadie dice «me dedico al Banking»—; los cargos no, y la razón es que un cargo es como se llama alguien: traducir «Head of Engineering» a «Jefe de Ingeniería» puede hacer que quien lo es no reconozca el suyo. Decidir qué pesa más es una decisión de producto y no una corrección | Demo 05-10-2026 |
| 54 | **Las dos listas de sector del panel están escritas a mano, son distintas entre sí y ninguna es la del modelo.** El alta ofrece «Banking / Banca», «Educación / Universidades», «Salud / HealthTech»; la edición ofrece «Banca y Finanzas», «Logistics», «Manufactura», «Retail / E-Commerce». El campo es de texto libre a propósito —lo que no está en el vocabulario del modelo se trata como desconocido—, así que no hay ningún dato mal; lo que hay son dos sugerencias que no coinciden ni entre ellas ni con las diez categorías que el modelo conoce, de modo que escribir el sector desde el panel o desde la página pública produce fichas que no se agrupan igual. Unificarlas es decidir antes si ese campo sigue siendo libre | Demo 05-10-2026 |
| 55 | **La matriz de prospectos desborda en horizontal y su primera columna no es fija.** Con nueve columnas, por debajo de unos 1200 px la tabla se lleva «Cuadrante», «Estado» y «Acciones» fuera de la vista; hay barra de desplazamiento, pero al usarla se pierde el nombre del prospecto, que es la primera columna. No se ve en la suite —`jsdom` no dibuja— y no se vio antes porque la demostración se ensaya en una pantalla ancha | Demo 05-10-2026 |
| 56 | **Nada comprueba que la pila levantada sea de este código.** `pila.py up -d` sin `--build` reutiliza la imagen que haya, y una imagen vieja arranca igual de bien: los seis contenedores se ponen verdes y el panel funciona. El 05-10-2026 llevaba toda la mañana levantada una del **1 de octubre**, cuatro capítulos por detrás, y lo que la delató fue mirar un panel que salía sin estilos —no una comprobación—. El compose ya avisa de la mitad de abajo de este problema (el `target` explícito del Dockerfile del cliente, que servía un `dist/` viejo); lo que falta es que algo compare lo que sirve la pila con el commit que hay en el árbol. Un `/health` que devolviera la revisión construida lo resolvería, y es funcionalidad nueva | Demo 05-10-2026 |
| 57 | **El desempate del reparto mide la fecha de alta, no la de asignación.** «Quien lleva más tiempo sin recibir uno» se calcula con la fecha en que se creó el prospecto más reciente de su cartera, porque el reparto ocurre en el alta y para lo que él reparte las dos fechas son la misma. Para un prospecto **reasignado a mano** no lo son: a quien el líder acaba de traspasar una ficha de hace tres meses le sigue constando que no recibe nada desde hace tres meses, y en un empate recibiría antes de lo que le toca. Se acepta a sabiendas —la carga de ese traspaso ya la cuenta el primer criterio, que es el que decide casi siempre—, y la alternativa es una columna `asignado_en` escrita en los cinco sitios que asignan, que es la forma de regla que el recorrido del 05-10-2026 pasó un día entero quitando | C46 |
| 58 | **El interruptor del reparto no tiene pantalla.** Es `REPARTO_AUTOMATICO_ACTIVO` en `pila.env`, así que apagarlo exige tocar un archivo y reiniciar el backend: el líder lo pide a quien opera la pila en lugar de hacerlo él. Quedó fuera del encargo por escrito, y es la misma forma del punto 15 —una pantalla de configuración— con la diferencia de que aquí no hay ningún secreto que guardar, solo un booleano: cuando haya pantalla de configuración, este interruptor es el candidato más barato para estrenarla | C46 |
| 59 | **El reparto no mira `capacity`, así que la cartera máxima declarada no limita nada.** La columna sigue usándose donde ya se usaba —el traspaso de la cartera de una baja avisa cuando el destino la supera—, pero el reparto automático reparte por carga abierta y no se detiene al llegar al tope de nadie: con todas las asesoras llenas, la siguiente ficha va a la menos llena igualmente. Era eso o no repartirla, y no repartirla la devuelve al punto 10. Que `capacity` sea un tope de verdad exige decidir qué pasa cuando se alcanza, y eso es funcionalidad | C46 |
| 60 | **La galleta de refresco que se borra nunca llega al navegador.** `POST /api/v1/auth/refresh` llama a `_clear_refresh_cookie(response)` antes de `raise HTTPException(401)` en los cuatro caminos de rechazo —sin `jti`, `jti` ajeno, caducado, cuenta desactivada—, y **FastAPI descarta las cabeceras del `Response` inyectado cuando el manejador lanza**: medido, el 401 viaja sin ninguna cabecera `Set-Cookie`. La consecuencia es pequeña —el navegador se queda con una galleta que ya no sirve y que el siguiente intento vuelve a rechazar— y arreglarlo es devolver una `JSONResponse` construida a mano en vez de lanzar, que cambia la forma del cuerpo del 401 que el cliente ya lee. Queda medido y nombrado en el docstring de `test_el_refresco_de_una_cuenta_desactivada_no_renueva` | Cobertura 07-10-2026 |
| 61 | **El README dice que el camino remoto se retiró, y `AI_MODE=azure` todavía lo elige.** El código conserva `AzureMLScoringAdapter`: con ese modo se selecciona igual, y si el extremo no responde —que es lo que pasa hoy, porque no hay ninguno desplegado— **contesta 0,50 para todo el mundo** sin que nada falle. Un 0,50 uniforme no se distingue de un modelo que no discrimina: la pantalla se pinta, la auditoría anota su versión y nadie se entera. No se toca porque el modo por defecto no es ese y cambiar el selector es cambiar lo que la API contesta; los cuatro caminos de ese adaptador sí están probados, incluido el 0,50 de cuando el puerto rechaza. Falta decidir si se borra el modo o se corrige el README | Cobertura 07-10-2026 |
| 62 | **Una sola palabra más ancha que el lienzo se dibuja desbordada.** `core/tarjeta.py:_repartir` promete en su docstring que «una palabra más larga que la línea entera se corta por caracteres en lugar de desbordar el lienzo». No lo cumple: el `while` saca `actual[:-1]` como línea y se queda con `actual[-1]` —corta un carácter y guarda el último— en vez de sacar un trozo que quepa y seguir con el resto. Con 200 letras y el ancho útil real (1032 px) la primera línea mide **14 925 px**: catorce veces el lienzo. Y `_tamano_del_titulo` no lo salva, porque dos líneas son menos de tres y se detiene en el primer peldaño, dibujándolo al tamaño más grande. Lo ve quien pega el enlace en LinkedIn o WhatsApp, no el panel, y hace falta un título de una sola palabra larguísima —una dirección pegada— para provocarlo. Arreglarlo cambia píxeles de una imagen que hoy se sirve con su `ETag`; queda medido en `test_una_sola_palabra_mas_ancha_que_el_lienzo_se_parte_por_letras`, que comprueba lo medido y nombra el defecto | Cobertura 07-10-2026 |
| 63 | **Los cuatro suelos del cliente se cierran sobre seis archivos, no sobre `src/`.** Lo que el CI exige del cliente son cuatro umbrales sobre los **seis módulos elegidos** de `frontend/src/services/` y `frontend/src/pruebas/`, no sobre `src/` entero. Es deliberado —los componentes se prueban por lo que pintan, y un suelo global premiaría pruebas de montaje que no comprueban reglas—, pero significa que el número que el CI defiende no es «la cobertura del cliente». La alternativa, medir `src/` completo con un suelo más bajo, daría una cifra más honesta de leer y un trinquete más flojo: hay que decidir cuál de las dos cosas importa más | Cobertura 07-10-2026 |
| 64 | **La cobertura de local y la del CI no miden lo mismo.** `main.py` decide **en tiempo de importación** si registra el comodín de la SPA, según si existe `frontend/dist/assets`; el trabajo `pruebas` del CI declara `needs: modelo` y nada más, así que corre sin bundle. En local la cifra sale **más alta**, de modo que un suelo pegado a lo medido en una máquina de trabajo pone el CI en rojo sobre un árbol correcto —exactamente el fallo que un trinquete no puede tener—. Medido: **15 líneas y 2 ramas** de `main.py` que en el CI no se pueden cubrir de ninguna manera. El suelo se fijó contra la condición del CI, apartando `frontend/dist` para medirlo, y queda dicho al lado del número. Igualar los dos entornos pide o encadenar `pruebas` a `frontend` —hoy corren en paralelo, por una razón de medición y no de corrección— o que la aplicación no mire el disco para decidir sus rutas | Cobertura 07-10-2026 |
| 65 | **`pyjwt 2.14.0` tenía dos avisos con corrección disponible** —subida a 2.15.0 el 8 de octubre de 2026—. Caían **dos trabajos** por ello: `pip-audit` y, desde el 7 de octubre, también `imagenes`, que audita los paquetes fijados de la imagen ya construida; el segundo empezó a caer sin que cambiara una sola línea, cuando se publicó el segundo aviso. Eran **PYSEC-2026-4141** y **PYSEC-2026-4183**, las dos corregidas en 2.15.0. El lock fijaba 2.14.0, que era la versión sin avisos cuando se congeló: no lo rompió ningún cambio, lo rompió el calendario. Se sube **solo pyjwt** y no se recompila el lock: un `uv pip compile` de hoy movería todo lo que haya avanzado desde que se fijó —docenas de paquetes— y la congelación definitiva no admite eso. Lo que hace legítimo el cambio quirúrgico está medido: los metadatos de dependencias de 2.15.0 son **idénticos** a los de 2.14.0 —`typing_extensions` solo por debajo de Python 3.11 y `cryptography` solo con el extra `crypto`—, así que no hay ningún paquete nuevo que resolver y el lock no queda incompleto. Las huellas se tomaron de la API de PyPI, no escritas de memoria, y OSV responde **4 avisos para 2.14.0 y 0 para 2.15.0** —se elige 2.15.0 y no la 2.15.1 publicada después porque es la versión que los avisos nombran como corrección, y es el paso más pequeño—. Verificado: `pip install --require-hashes` sobre los dos locks acepta las huellas y cambia **un solo paquete**; la suite completa con PyJWT 2.15.0 da **2064 pasadas, 2 omitidas y ningun fallo** en 9 min 56 s, y el suelo de cobertura lo vuelve a medir el CI con el lock nuevo. Lo que **no** se pudo hacer en esta máquina: reconstruir las imágenes y volver a validar la pila, porque el servicio de Docker necesita privilegios que esta sesión no tiene; lo contestan los trabajos `imagenes` y `compose` del CI, que construyen la imagen desde el lock y la auditan. Contestaron: la auditoría de producción dice «No known vulnerabilities found» y la de los paquetes fijados **de la imagen ya construida**, también. Las dos puertas de este aviso quedan cerradas. El trabajo `imagenes` siguió en rojo, pero no por esto: al dejar de morir en la auditoría llegó a un paso que nunca se había ejecutado, y eso es el punto 70. Y en el mismo día apareció otro aviso, de `urllib3`, que es el punto 71: la lección no es sobre pyjwt, es que un lock congelado no se queda quieto | Cobertura 07-10-2026 |
| 66 | **El control del capítulo 33 llevaba roto y nadie lo vio** —corregido el 8 de octubre de 2026—. El trabajo `configuracion-peligrosa` fallaba con «los campos que no admiten vacío ya no salen de la tabla (capítulo 33)»: una copia escrita a mano se había quedado atrás. Medido al arreglarlo, era peor que lo anotado aquí: los **cuatro** `grep` de ese bloque se habían quedado atrás a la vez, no uno. El capítulo 41 mudó la derivación a `app/core/texto.py` para compartirla con `Campaign` y `User`, el bloque entero dejó de encontrar nada, y como el primero sale con `exit 1` los otros tres no se volvieron a mirar —uno de ellos fijaba siete nombres de columna de los que el 41 había quitado uno—. Y no estaba solo, por una razón de forma: **un paso en rojo deja sin correr todos los que vienen detrás**, así que desde que el punto 69 tumbó el paso 31 los pasos 32 a 62 no se ejecutaron ni una vez en el CI. Corriendo los 59 en local aparecieron **tres más** de la misma familia: el inventario de la paleta, que el capítulo 40 mudó a `pruebas/codigo.js`; la tabla del 422, que el 45 mudó a `services/rechazos.js`; y el oyente del pragma de SQLite, que rompió un `# pragma: no branch` escrito al final de la línea al apretar el suelo de ramas —un comentario se metió entre los dos renglones que la expresión exigía pegados, y la guarda se puso roja sin que el código cambiara de comportamiento—. Las cuatro medían una **ruta** y un fragmento literal; ahora miden la **propiedad** donde viva: buscando en todo `backend/app`, siguiendo los `import` locales de la prueba y del módulo, y quitando los comentarios antes de comparar una forma. De paso, el de la paleta pedía el **nombre** `readdirSync`, que la línea del `import` satisface sola —la lección del capítulo 37—, y al ensancharlo a los módulos importados habría entrado por esa puerta: ahora pide `readdirSync(`. Arnés de reintroducción 23 de 23, uno verde a propósito —reescribir ese comentario no puede poner roja la guarda—. Y hubo una **cuarta**, que no se podía ver desde aquí: con las tuberías del punto 69 arregladas el trabajo dejó de morir en el paso 31 y llegó al 61 de 62, donde el control «Ningún rechazo nombra una columna ni llega en inglés» cayó con `ModuleNotFoundError: No module named 'sqlalchemy'`. Importaba `app.models.entities` para preguntarle sus columnas —que es lo correcto, porque la alternativa es una lista escrita a mano— en un trabajo que hace *checkout* y nada más, y cuyos pasos **leen archivos** por diseño. En una máquina de trabajo pasa, porque el intérprete del `PATH` sí tiene SQLAlchemy; en el CI no podía pasar nunca, y nunca se vio porque es el paso 61 y algo anterior moría primero: desde que se escribió no se había ejecutado una sola vez. Ahora las columnas se **leen** de `entities.py` con `ast` —las asignaciones `nombre = Column(...)` de cada clase, y el primer argumento literal cuando la columna se llama distinto que el atributo—, lo que conserva la propiedad y cambia el medio. Probado por las dos mitades que hacen falta: los dos caminos devuelven el **mismo** conjunto de 162 columnas, sin una diferencia en ningún sentido, y el programa sacado del `run:` y corrido con un intérprete sin paquetes de terceros falla en la versión anterior y pasa en la de ahora, 2 de 2. Y la pregunta de en cuántos sitios más vive esa regla, medida: en ninguno —los 60 pasos corridos con ese intérprete dan 58 verdes, y los 2 restantes son controles que leen YAML y **dicen** que les falta PyYAML, que el runner de Ubuntu sí trae—. Con las cuatro arregladas el trabajo pasa **entero** en el CI por primera vez desde antes de la congelación definitiva: 61 controles en verde. | Cobertura 07-10-2026 |
| 67 | **`gitleaks` marcaba una contraseña de prueba** —corregido el 8 de octubre de 2026—. Un hallazgo, falso positivo: `"password": "Una-Frase-Larga-Y-Propia-2026"` en `backend/tests/test_nada_supuesto_en_la_ficha.py:216`, una frase inventada para crear una cuenta en una prueba, que la regla `generic-api-key` marca por entropía. Se perdona por **huella** en un `.gitleaksignore` —`8a352fb…:archivo:generic-api-key:216`—, que fija cuatro cosas a la vez y por tanto no cubre nada más que el hallazgo que nombra; no con un `# gitleaks:allow` suelto, que no dice por qué, ni con una exclusión por ruta, que apagaría el escáner para todo el archivo y dejaría pasar un secreto de verdad escrito mañana ahí al lado. Y como la pregunta «¿y quién vigila que esa excepción siga siendo estrecha?» no tenía respuesta, el trabajo `configuracion-peligrosa` gana su **control 61**, hermano del 60: exige que cada línea sea una huella completa, que lleve su motivo escrito encima, que no haya ninguna marca suelta en el código y que el total no pase de `EXCEPCIONES_GITLEAKS`. La cuarta cosa que comprueba es la que más costaba ver: que la orden del flujo pase `--gitleaks-ignore-path`, porque dentro del contenedor el directorio de trabajo no es el repositorio y sin ese flag el archivo **está puesto y no se lee**. Arnés 6 de 6 —cinco formas de volver al defecto y una verde: reescribir el motivo no puede poner roja la guarda—, y el arnés encontró dos agujeros en el control recién escrito, uno de ellos que buscaba el nombre del flag en **todo** el `ci.yml` y lo encontraba en su propio comentario: la cuarta vez que este repositorio tropieza con una guarda satisfecha por su explicación. Lo que **no** se pudo comprobar en esta máquina: correr gitleaks de verdad, porque su servicio de Docker necesita privilegios que esta sesión no tiene; la respuesta la da el propio trabajo `secretos` del CI | Cobertura 07-10-2026 |
| 68 | **El CI llevaba rojo desde antes de este trabajo, y nada lo decía.** Los cuatro puntos de arriba —más uno de las pruebas, ya corregido: el arnés de travesía de rutas daba por hecho que `frontend/dist` existe, y en el CI no existe— llevaban el CI en rojo desde al menos la confirmación de la congelación definitiva. Ninguna de las guardas del repositorio vigila el CI mismo: un trabajo que falla se ve en GitHub y en ningún otro sitio, y quien trabaja en local con la suite verde no tiene forma de enterarse. El 7 de octubre de 2026 se descubrió por casualidad, midiendo la cobertura con `frontend/dist` apartado. El 8 de octubre de 2026 se trabajaron los cuatro y **esta observación sigue abierta**, más alta de lo que estaba: lo que los dejó meses sin verse no fue ninguno de ellos, fue que nada mira. Y hubo una vuelta más que lo demuestra: tres de los controles que fallaban estaban tapados por un paso anterior —un paso en rojo deja sin correr los que vienen detrás—, así que ni mirando el CI se veían todos. Hasta que no quedó uno, no se supo cuántos eran. Y la cuenta de aquel día lo mide mejor que cualquier argumento: los cuatro rojos anotados resultaron ser **nueve** defectos, porque cada uno tapaba al siguiente. Arreglar el 69 descubrió el 66 y, detrás, tres controles más caducados; arreglar esos descubrió uno que importaba la aplicación en un trabajo sin dependencias; cerrar el 65 descubrió el 70 —un paso que nunca se había ejecutado— y detrás el 72 —un escáner que no escaneaba—, y detrás el 73. Cuatro gestores de dependencias dieron aviso el mismo día. Ninguno de los nueve lo trajo un cambio del árbol, y ninguno se habría visto desde una máquina de trabajo con la suite en verde | Cobertura 07-10-2026 |
| 69 | **El idioma con que los controles leen los archivos fallaba justo cuando encontraban lo que buscan** —corregido el 8 de octubre de 2026—. Los pasos de `configuracion-peligrosa` leían un archivo a una variable y la metían en un `grep` por una tubería: `printf '%s\n' "$modelo" \| grep -q '…'`. Con `set -o pipefail`, si `grep -q` encuentra la coincidencia **pronto** sale de inmediato y cierra la tubería; `printf`, que todavía estaba escribiendo, recibe `EPIPE`, y la tubería entera devuelve error. El control fallaba **precisamente porque la comprobación salía bien**. El 8 de octubre le pasó al control «El pais no se supone», que mete los 53 KB de `entities.py` en un `grep -q` cuya coincidencia está en las primeras líneas: `printf: write error: Broken pipe`, y detrás el mensaje de un defecto que no existe. No lo rompió ningún cambio del árbol —el archivo no se tocó— sino el tamaño del archivo frente al buffer de lectura de `grep`, así que era una carrera que se cruzó sola. Se aplazó una vez con un motivo que dejó de ser cierto: entonces el trabajo seguía rojo de todas formas por el punto 66, así que arreglar esto no ganaba nada; cerrado el 66, esta era la única cosa entre ese trabajo y el verde. Medido al arreglarlo: **102** tuberías de esa forma —de 105 líneas con `printf '%s\n'`; las otras tres solo imprimen y no tienen tubería— y, al buscar la **forma** del defecto en vez de la palabra `printf`, **23 más** que el recuento original no vio porque las produce otra cosa: `grep -vE '…' archivo \| grep -q`, `ordenes script.sh \| grep -q`, `sed -n '…' archivo \| grep -q` y un `sort -g \| head -1`. Son 125 sitios y hoy quedan **cero**: la última etapa sale del conducto y recibe la entrada por una cadena —`grep -q '…' <<< "$v"`, que no tiene dos procesos y por tanto no puede romperse por la mitad—, y donde la etapa que cerraba iba detrás de otra se anidan. Un transformador que sabe de comillas hizo 94 y **se negó** a tocar 11, que se hicieron a mano con su motivo escrito. La prueba: los 59 pasos del trabajo corridos antes y después dicen **exactamente lo mismo**, los 118 programas `run:` del archivo pasan `bash -n`, y las tres líneas que caen en el trabajo `imagenes` —que no se puede correr en local— se comprobaron por equivalencia contra las mismas entradas, 15 casos de 15. Hay **un** veredicto que cambia, a propósito y escrito al lado: `grep '\.css$' \| head -1` devolvía 1 cuando la página no enlazaba ninguna hoja de estilo, y `set -e` mataba el paso ahí sin una línea que dijera por qué; ahora el caso lo nombra un `aviso`. Y el descuido de al lado, también corregido: los mensajes de fallo llevaban el nombre de la columna **entre acentos graves dentro de un `echo` con comillas dobles**, así que bash lo ejecutaba como una orden y lo imprimía vacío —«la columna  vuelve a ser obligatoria»— | Cobertura 07-10-2026 |
| 70 | **El paso que comprueba que la imagen arranca contra una base real nunca se había ejecutado, y comprobaba lo contrario de lo que dice** —corregido el 8 de octubre de 2026—. Con el punto 65 cerrado, el trabajo `imagenes` pasó su auditoría de paquetes y llegó por primera vez al paso «Arrancar la imagen contra una base de datos real», que falló: `EsquemaDesactualizado: la base no tiene ninguna migración aplicada`. El paso levantaba Postgres vacío y arrancaba el contenedor del backend esperando un 200 en `/health`. La imagen lleva `ENVIRONMENT=production`, así que `init_db()` **no crea nada**: comprueba que el esquema esté sellado por Alembic y se niega a servir si no lo está. Esa guarda es correcta —es la del capítulo que descubrió que la pila no arrancaba sobre un volumen nuevo— y es exactamente el motivo de que el compose tenga un servicio `migrate` aparte, con la misma imagen y `alembic upgrade head`, del que el backend depende. Aquí nadie aplicaba las migraciones, así que el paso fallaba sobre una imagen **sana** y, si alguna vez hubiera pasado, habría sido sobre una base migrada por otra vía. Arreglado copiando lo que hace la pila real: un contenedor efímero con la misma imagen que migra y muere, antes de arrancar el backend; y las dos variables que los dos contenedores necesitan se escriben una sola vez. No se vio en meses por el mismo motivo que los cuatro controles del punto 66: **un paso en rojo deja sin correr todos los que vienen detrás**, y delante de este estaba la auditoría que el aviso de pyjwt tumbaba. De los 30 últimos registros del CI, en ninguno aparece este paso con un veredicto: la primera vez que se ejecutó fue el 8 de octubre de 2026 | Cobertura 07-10-2026 |
| 71 | **`urllib3 2.7.0` acumuló tres avisos entre una ejecución del CI y la siguiente** —subido a 2.8.0 el 8 de octubre de 2026—. Es la misma clase de rotura que el punto 65 y en el mismo día: el trabajo `pip-audit` pasó a verde en producción —«No known vulnerabilities found»— y siguió rojo en desarrollo por **PYSEC-2026-4175**, **4176** y **4177**, publicados mientras se cerraban los otros puntos. `urllib3` **solo** está en `requirements-dev.lock`, por `requests`, que lo trae `pip-audit`: de ahí que la auditoría de producción y la de desarrollo digan cosas distintas sobre el mismo árbol. Mismo criterio que con pyjwt: se cambia la entrada y no se recompila el lock, las huellas se toman de la API de PyPI, y lo que lo hace completo está medido —ninguna de las dos versiones declara una sola dependencia **obligatoria**; todas las suyas van con `extra`—. OSV: **6 avisos para 2.7.0 y 0 para 2.8.0**. Verificado con `pip install --require-hashes`, que acepta las huellas y cambia un solo paquete. Lo que este punto deja dicho, porque volverá a pasar: un lock congelado no se queda quieto, se queda **atrás**, y los dos avisos de hoy no los trajo ningún cambio del árbol. Y con las dos auditorías de Python en verde —«No known vulnerabilities found» las dos—, el mismo trabajo cayó en la del **cliente**: `npm audit` con dos avisos altos, `brace-expansion <=1.1.20` (tres avisos de denegación de servicio) y `source-map-js 1.0.0 - 1.2.1`, los dos transitivos y los dos **solo de desarrollo** —`dev: true` en el lock, así que no viajan en el bundle—. `npm audit fix` los sube a 1.1.21 y 1.2.2 tocando **dos entradas** de `package-lock.json` y ninguna de `package.json`: mismo cambio quirúrgico que en el lado de Python, y comprobado como lo comprueba el CI —`npm ci`, `npm audit --audit-level=high` con **0** avisos, 748 pruebas de cliente en 45 archivos, `eslint` sin una queja y el build en pie—. Tres gestores de dependencias, cuatro paquetes y un solo día: la lección de este punto no es de ninguna biblioteca | Cobertura 07-10-2026 |
| 72 | **El escáner de vulnerabilidades de las imágenes llevaba desde que se escribió sin escanear nada** —corregido el 8 de octubre de 2026—. Arreglado el punto 70, el trabajo `imagenes` pasó el arranque contra la base real, el *healthcheck*, la documentación cerrada y la CSP —cuatro pasos que tampoco se habían ejecutado nunca— y cayó en el de Trivy. No con una vulnerabilidad: con `docker: invalid reference format` y salida **125**. La referencia del escáner era `aquasec/trivy:0.74.0@sha256:…c1969image`: faltaba el espacio antes de `image`, que es el **subcomando** de Trivy, así que el nombre del subcomando se pegó al final de la huella. En las dos órdenes del paso, la del informe y la de la puerta. Lo peor no es el descuido, es que **la guarda que vigila las fijaciones lo daba por bueno**: comprobaba que la huella *estuviera* y no que *terminara* ahí, así que los 64 primeros caracteres encajaban y el resto no se miraba. Es la lección del capítulo 37 otra vez —que algo aparezca no es que esté bien— aplicada a la guarda misma. Corregido el espacio y, además, `renovar_imagenes.py` comprueba ahora que ninguna huella lleve nada pegado detrás, en los tres formatos que lee y no solo en el flujo, porque la forma del descuido no es de ningún formato. Medido: **17 huellas** en el repositorio, todas de 64 caracteres y sin nada detrás. Arnés 2 de 2 —el defecto real reintroducido en el flujo y otro inventado en el compose, los dos puestos en rojo con su mensaje— y las 33 pruebas de la guarda siguen pasando. Y el motivo de que nadie lo viera es el mismo de los puntos 66 y 70: **un paso en rojo deja sin correr todos los que vienen detrás**, y delante estaba la auditoría que el aviso de pyjwt tumbaba | Cobertura 07-10-2026 |
| 73 | ~~**La capa base de la imagen del backend tiene siete avisos ALTOS con arreglo publicado, y renovarla no se puede hacer sin Docker.** Corregido el punto 72, Trivy escaneó por primera vez y encontró lo que estaba ahí: `plurione-backend:ci` sobre **debian 13.6**, `Total: 7 (HIGH: 7, CRITICAL: 0)`, y **0** en los 100 y pico paquetes de Python de la imagen —el lock está limpio, lo que falta es el sistema operativo de la base—. Son `libpcre2-8-0` **CVE-2026-103111** (escritura fuera de límites con una expresión regular preparada; `10.46-1~deb13u2` → `10.46-1~deb13u3`), y `libssl3t64`, `openssl` y `openssl-provider-legacy` con **CVE-2026-75804** (denegación de servicio por QUIC) y **CVE-2026-84782** (revelación de información), `3.5.7-1~deb13u2` → `3.5.7-1~deb13u3`. De los cuatro, tres llegan con `python:3.13-slim@sha256:9d2e…0285` y no se nombran en ningún archivo del repositorio; `libpcre2-8-0`, en cambio, **sí** se instala con su versión exacta en `backend/Dockerfile`, y la primera redacción de esta fila lo metió en el mismo saco que los otros tres: era un error, corregido aquí. El arreglo pedía renovar la huella de la base y, detrás, lo que manda la propia herramienta —«construir, escanear con Trivy y mirar si los paquetes con versión de los dos Dockerfile siguen haciendo falta»—; las tres cosas necesitan Docker, y el servicio de Docker de la máquina donde se cerró esa tanda no arrancaba sin privilegios que la sesión no tenía~~ — **cerrado el 9 de octubre de 2026**, con Docker en pie y las tres cosas hechas. Base renovada a `bf44…d79c` (**Debian 13.6 → 13.7**) y el pin de `libpcre2-8-0` subido a `deb13u3`: **7 → 0**, y la puerta del CI sale con 0. Lo primero que pasó al cambiar la huella es que **la imagen dejó de construir**, que es exactamente lo que el comentario del Dockerfile prometía desde el capítulo 32: la base nueva ya trae `deb13u3`, así que pedir `deb13u2` dejó de ser subir para ser **bajar** —`E: Packages were downgraded and -y was used without --allow-downgrades`, salida 100—. Es la primera vez que ese aviso llega como estaba previsto, como un fallo con el motivo escrito y no como una imagen distinta en silencio. Los otros cuatro pines se quedan, y medido antes de dejarlos: en la base nueva el instalado y el candidato coinciden con lo que piden esas líneas, así que hoy no suben nada y valen solo como aviso de la próxima revisión. **Y cerrarlo destapó la mitad que nadie había medido nunca: la imagen del cliente.** La puerta de Trivy sale con 1 en la primera imagen, así que `plurione-frontend` quedaba detrás y nunca se llegaba a ella —el punto 68 otra vez, ahora dentro de un paso—. Escaneada aparte: **alpine 3.24.1, `Total: 3 (HIGH: 3)`** —`libexpat` **CVE-2026-93990** (inyección de XML con UTF-16 mal formado), `pcre2` **CVE-2026-103111**, el mismo que el `libpcre2` del backend, y `tiff` **CVE-2026-4775** (ejecución de código o denegación de servicio por un entero con signo)—. Arreglados con tres pines más y **no** renovando la huella de `nginx:alpine`, porque se midió que no sirve: la base al día —`72ba…f1d3` → `df22…eac2`, 3.24.1 → 3.24.2— trae **las mismas tres versiones**. La imagen va por detrás del **repositorio**, no del arreglo: v3.24/main ya publica 2.8.5-r0, 10.49-r0 y 4.7.2-r0. Derivado con el comparador del propio `apk` —el que usaría `apk version -l '<'`, que dentro del contenedor no puede actualizar el índice en esta máquina—: **16** paquetes de esa base van por detrás del repositorio, y los tres de Trivy están entre ellos. **Pruebas del cierre**, todas sobre los Dockerfile tal como quedan confirmados: las dos imágenes construyen y pasan la puerta con **0**; la del backend aplica `alembic upgrade head` contra un PostgreSQL de verdad y `/health` contesta **200** con `database: connected` y `ml_model_loaded: true`, y **503** con la base caída; la del cliente sirve **200** con `nginx -t` correcto, las tres bibliotecas en la versión corregida y sus cabeceras de seguridad; la guarda de fijación en verde —10 referencias con huella, 7 acciones por commit— y sus **33** pruebas pasando. Lo que **no** se tocó: las otras cinco imágenes que el renovador da por atrasadas (`postgres:16-alpine`, `redis:7-alpine`, `nginx:alpine`, `alpine/socat`, `dpage/pgadmin4`), porque renovarlas cambia la capa de datos o el utillaje de desarrollo sin cerrar ningún aviso, y eso es lo que la congelación prohíbe. Una nota sobre cómo se midió, para que se pueda repetir: en esta máquina el TLS está interceptado y ni `pip` ni `apk` pueden verificar desde dentro de un contenedor, así que se construyó pasando el certificado del anfitrión como **secreto de construcción** —BuildKit no lo deja en ninguna capa, y no cambia qué se instala: uno va por lock con hash y el otro verifica firmas con sus propias claves—. La línea base medida así dio exactamente el `Total: 7` del CI, y eso es lo que hace válida la comparación. **Y el CI lo confirma, que es lo que faltaba:** la ejecución `38003136533` sobre `619e997` sale verde entera —**diez de diez trabajos**, y el de imágenes con sus **27 pasos** en verde, puerta de Trivy sobre las dos imágenes incluida—. Es la primera ejecución verde de la que hay constancia: el trabajo de imágenes no había pasado **nunca** completo —se revisaron 30 ejecuciones y su paso de arranque contra una base real jamás había dado un veredicto (punto 70)—, así que mientras ese trabajo existió en rojo no hubo ninguna. De §6.4 quedaba abierto entonces el **74** —catorce carreras medidas en las pruebas del cliente—, cerrado ese mismo día; y queda abierto el **68**, que nada en el repositorio vigila el CI, por decisión y no por olvido. | Cobertura 07-10-2026 |
| 74 | ~~**Catorce pruebas del cliente dan por hecho que el dato ya llegó, y una de ellas puso el CI en rojo sin que nada del árbol hubiera cambiado** —la que lo puso, corregida el 8 de octubre de 2026; las otras catorce, medidas y abiertas—. La ejecución `37819881196`, sobre un commit que solo tocaba documentación, devolvió `Cliente` en rojo con **1 de 748**: `src/components/AsignarAsesor.test.jsx:64`, «Value "4" not found in options», y el `<select>` del volcado con una sola opción, la vacía. El mecanismo es el de siempre con otra cara: **la espera se ancla en el envase y la acción necesita el contenido**. El componente dibuja el selector en el primer render, antes de que `fetchSalesReps` conteste, así que `await screen.findByLabelText('Asignar a')` se cumple con la lista **vacía**; `selectOptions(…, '4')` no. Pasaba por los pelos porque el doble resolvía en el mismo tick, y dejó de pasar el día que la máquina del CI fue más despacio. Corregido anclando la espera en la **opción** —y sacando de la misma lista el identificador que se elige y el nombre que se espera, para que no vigilen a asesores distintos—; y de paso una segunda carrera en la misma prueba, la recarga de la ficha afirmada sin esperarla, que el componente pide **después** de que el PUT conteste mientras el `waitFor` de arriba se cumple en cuanto la llamada sale. **El inventario está medido, no estimado:** un arnés que hace llegar 60 ms tarde todo dato asíncrono de los dobles —muy por debajo del tope de `findBy`, 1000 ms, y del `testTimeout` de 10 s, así que una espera correcta no se entera— dio **17 fallos en 12 archivos** antes, y **14 en 11** después de corregir el rojo: `App.test.jsx:530` y `:551`, `EnsayoDelGuion.test.jsx:365`, `AltaDelSegundoFactor.test.jsx:81`, `BandejaDeHoy.test.jsx:108`, `Campana.test.jsx:83` y `:94` —y `:69`, que falló en una pasada y no en la otra—, `CerrarProspecto.test.jsx:119`, `DerechosDelTitular.test.jsx:420`, `LoginScreen.test.jsx:87`, `NewLeadModal.test.jsx:101`, `Publicaciones.test.jsx:250` y `:414`, y `services/api.test.js:318`. **Y catorce es un suelo, no un total**, por la razón del punto 68: corregir la línea 64 destapó la 83 de la misma prueba, que el primer fallo tapaba. No se arreglan ahora porque son catorce pruebas en once archivos, bastante más cambio del que la congelación definitiva admite, y ninguna está roja hoy; pero no es cosmético: cualquiera de ellas puede poner `Cliente` en rojo en una máquina cargada, y `Cliente` en rojo deja **`Build de imágenes Docker` saltado por completo** —el trabajo donde viven los puntos 70, 72 y 73—, que es el punto 68 un piso más arriba: un rojo esconde lo que viene detrás, ahora a nivel de trabajo. Dos pruebas que **no** cayeron dicen cuál es la forma buena: `AdminPanel.test.jsx:88` y `BandejaSinAsociar.test.jsx:89` esperan algo **derivado del dato** —una etiqueta que nombra a un asesor de la lista traída—, y un envase vacío no puede cumplirlas. Para volver a medirlo, el arnés no vive en el repositorio: es un archivo de preparación de vitest que envuelve `vi.fn` para que `mockResolvedValue` resuelva dentro de 60 ms y para que una implementación `async` espere 60 ms antes de contestar, añadido detrás de `src/pruebas/preparar.js` en una copia de la configuración~~ — **cerrado el 9 de octubre de 2026**: las catorce arregladas, cada una anclando la espera en lo que la línea siguiente necesita. Son **17 cambios en 11 archivos, todos de prueba y ninguno de componente**, y la cobertura sale idéntica antes y después —96.65 % de sentencias, 91.75 % de ramas—, que es la señal de que no cambió **qué** se ejercita sino **cuándo** se espera. Las tres formas, con su arreglo cada una: esperar la etiqueta y elegir una opción que llega después → esperar la **opción**; esperar la región de avisos y afirmar su texto → `waitFor` sobre el **texto**, porque desde el capítulo 43 esas regiones están siempre montadas y buscarlas no espera nada; y afirmar un efecto que ocurre **detrás** del que se esperó → su propia espera, porque un `waitFor` sobre «se llamó al PUT» se cumple en cuanto la llamada **sale**. Cuatro tenían además causa propia, y vale nombrarlas porque ninguna se parece a una carrera al leerla: en `Campana`, `/Avisos:/` casa también con «Avisos: ninguno sin leer», que es lo que dice el primer render, así que el clic abría el panel antes de que hubiera un solo aviso dentro; en `Publicaciones`, pausar recarga la lista y la recarga aterrizaba entre buscar la fila y pulsarla, de modo que se pulsaba un nodo ya **desprendido** del documento y el fallo salía tres líneas más lejos del motivo; en `DerechosDelTitular`, «el último blob» no se puede esperar —el último de antes ya existe—, así que hay que contar los que había y esperar a que crezca; y en `api.test.js`, dos `await Promise.resolve()` daban por hecho que el 401 ya había llegado al cliente, y se cambian por esperar la condición que de verdad hacía falta. **Y el suelo era suelo:** corregidas las trece que el arnés señalaba, la suite salía limpia a 60 ms, y subir el retardo a 250 ms destapó la decimocuarta —`EnsayoDelGuion.test.jsx`, `Value "3" not found in options`: exactamente el defecto del 8 de octubre, en otra prueba, que la medición a 60 ms no había visto nunca—. **El arnés también mejoró dos veces, por el mismo motivo que mide:** a 250 y a 500 ms empezaban a fallar esperas **correctas** por pasarse del tope por omisión —1000 ms en `findBy`, y otros 1000 en `vi.waitFor`, que `configure` no gobierna—, y el arnés lo habría llamado carrera; subidos los dos topes queda sano a cualquier retardo, porque entonces un fallo solo puede significar que no se esperó. Medido así: **748 de 748 en tres pasadas seguidas a 500 ms**, ocho veces el retardo con el que apareció el defecto original. Y en limpio, como lo corre el CI: 748 pruebas en 45 archivos, `npm run lint` sin una queja y el build en pie. | Cobertura 08-10-2026 |

---

## 7. Lo que no se va a hacer, y por qué

Distinto de todo lo anterior: esto no está pendiente, está **decidido**.

| Qué | Por qué |
| :--- | :--- |
| **Inventar un peso para los motivos del desenlace** | Una constante escrita a ojo que entra al modelo es indistinguible de una medición para quien lee el resultado seis meses después |
| **Cualquier previsión de ingresos** | El tramo del acuerdo agrupa lo ganado y no se multiplica por nada. Multiplicarlo por una tasa supuesta produce un número con dos decimales y ningún respaldo |
| **Contar personas en lugar de aperturas** | Las visitas de la página son aperturas. Contar personas exige cookies o dirección IP. Es a propósito |
| **Tratar la red de llegada como una medición** | La etiqueta dice por dónde se repartió el enlace que se abrió, no dónde estaba la persona. Quien recibe por WhatsApp un enlace copiado del post de LinkedIn cuenta como WhatsApp: correcto para decidir dónde volver a publicar, y nada más |
| **Un editor de reglas para el usuario** | Un editor de reglas es un lenguaje, y un lenguaje es otro proyecto. Las seis reglas están en el código con sus plazos configurables |
| **Bajar los mínimos del reentrenamiento para poder reentrenar antes** | El pipeline se negaría con razón. Los mínimos son 200 casos y 50 por clase, y publicar exige además que el límite inferior del intervalo alcance el umbral |
| **Automatizar el recálculo del score al cerrar** | El score guardado en el desenlace es el que había **cuando se decidió**. Recalcularlo destruiría la única respuesta posible a «¿el score acertaba?» |
| **TikTok** | Estaba fuera del alcance |
| **Granularidad menor de un día en el motor de reglas** | Una asignación de las diez de la mañana produce su tarea en la pasada siguiente. Los cierres sí son inmediatos. Bajar de un día convierte una pasada diaria en un servicio |
| **Regenerar el lock automáticamente** | Cuando se publique un aviso sobre una versión fijada, `pip-audit --strict` pondrá el pipeline en rojo y habrá que regenerar a mano. **Es el comportamiento buscado**: la alternativa es que el arreglo entre sin que nadie lo decida |
| **Avisar cuando no hay instantáneas** | En una instalación nueva es el estado normal durante días. Avisar de él sería ruido |
| **Conservar la huella de un aviso purgado para que no vuelva** | Sería guardar sin plazo un rastro de lo que se decidió no guardar |

---

## 8. Qué mirar el primer día que haya datos

Un orden sugerido, no un plan. Cada paso está construido y solo hay que ejecutarlo.

1. **Abrir el panel de «Desenlaces».** El contador dice cuántos casos utilizables hay y
   cuántos faltan para 200 con 50 de cada clase. Mientras no llegue, todo lo demás es
   prematuro.
2. **Mirar cuánto pesa «Otro motivo».** Si es el motivo más frecuente, la lista cerrada está
   mal y ampliarla es corrección, no funcionalidad (§1).
3. **Mirar la columna de categoría al cierre.** Es la respuesta a «¿el score acertaba?».
   Con los cierres del primer trimestre cualquier lectura es una anécdota, y el panel lo
   dice en vez de redondearlo.
4. **Extraer el dataset y medirlo sin publicar.** `feedback_dataset.py` y
   `train_model.py --datos realimentacion`. Medir y publicar están separados a propósito.
5. **Comprobar el manifiesto** antes de mirar ninguna métrica: cuántas filas se descartaron
   por vector antiguo, cuántas se etiquetaron solo por su estado y cuántas llevan motivo.
   Una cohorte con mitad de filas heredadas no dice lo mismo que una entera.
6. **Solo entonces, pedir la publicación.** Y aceptar que se niegue.

---

## 9. Dónde está cada cosa

| Qué | Dónde |
| :--- | :--- |
| El estado completo del sistema | `README.md` |
| Los capítulos con su detalle | `docs/reportes/` |
| Todo compilado, con portada e índice | `docs/Memoria_Tecnica_Final_Lead_Scoring.md` |
| La historia que se enseña, con sus reglas | `docs/Guion_Demo_Del_Post_de_LinkedIn_al_Prospecto_Puntuado.md` |
| El guion cronometrado y su ensayo | `docs/Guion_Cronometrado_de_la_Demo.md` |
| Cómo sentar a cuatro personas delante | `docs/Prueba_Con_Personas.md` |
| La defensa oral y las preguntas difíciles | `docs/GUIA_DEFENSA_ORAL.md` |
| Qué actualiza un tercero y qué sigue decidiendo una persona | `.github/dependabot.yml` |
| **Lo que queda por hacer** | **este documento** |
