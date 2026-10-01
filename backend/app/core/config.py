import hashlib
import json
import logging
import math
import secrets
from typing import Annotated, List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

# Entornos donde una SECRET_KEY débil o ausente debe abortar el arranque
HARDENED_ENVIRONMENTS = {"production", "prod", "staging", "preproduction", "preprod"}

# Claves que alguna vez estuvieron escritas en el repositorio y no pueden volver a usarse.
#
# Se guardan **por su huella SHA-256**, no en claro. Hasta el capítulo 27 la lista llevaba
# el texto literal de la clave de firma que se filtró en el capítulo 11. Funcionaba —la
# prohibía—, pero dejaba la clave escrita en tres sitios del proyecto y en el historial de
# Git para siempre; está rotada y no abre nada, pero un secreto publicado no se despublica,
# y el repositorio no es el sitio donde se guarda lo que se quiere que nadie lea.
#
# Con la huella se consigue lo mismo sin el texto: comparar es una operación de un solo
# sentido, así que el arranque puede reconocer la clave prohibida y nadie puede leerla aquí.
# Añadir una clave nueva a la lista se hace calculando su huella fuera del proyecto:
#   python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" CLAVE
HUELLAS_DE_CLAVES_COMPROMETIDAS = frozenset({
    # La clave de firma de producción que se publicó en el repositorio (capítulo 11) y se
    # rotó el mismo día. Nunca vuelve a ser válida, ni en desarrollo.
    "d133504215cb4b76ec3a97b6aff2293865eadb61f27e873a47e14e474344abef",
})

# Marcadores de posición: lo que alguien escribe para salir del paso. No son secretos de
# nadie, así que se quedan en claro —son más útiles legibles— y además los tres son más
# cortos que `MIN_SECRET_KEY_LENGTH`, que ya los rechazaría por su cuenta.
CLAVES_DE_RELLENO = frozenset({"changeme", "secret", "CAMBIAR_ESTA_CLAVE"})


def es_clave_comprometida(clave: str) -> bool:
    """¿Es esta una clave que ya no puede volver a usarse?"""
    if clave in CLAVES_DE_RELLENO:
        return True
    return hashlib.sha256(clave.encode("utf-8")).hexdigest() in HUELLAS_DE_CLAVES_COMPROMETIDAS

MIN_SECRET_KEY_LENGTH = 32

# Los JWT los firma y los verifica este mismo servicio con SECRET_KEY: solo HMAC.
ALGORITMOS_JWT_ADMITIDOS = {"HS256", "HS384", "HS512"}

# Por debajo de esto la purga del historial destruye en lugar de resumir (véase el validador).
RETENCION_MINIMA_DEL_HISTORIAL_MESES = 3

# Mínimo de días de cada plazo de conservación (capítulo 22). Un `0` escrito por error no
# puede convertir la purga diaria en un vaciado: cada mínimo es lo que hace falta para que
# el dato siga sirviendo para lo único que justifica guardarlo.
CONSERVACION_MINIMA_DIAS = {
    # Un token revocado por reutilización es la prueba de un incidente, y los incidentes
    # se investigan días después, no el mismo día en que el token caduca.
    "CONSERVACION_SESIONES_DIAS": 7,
    # Un recálculo fallido se mira la semana en que falló.
    "CONSERVACION_TRABAJOS_DIAS": 7,
    # Una sincronización con el CRM se reclama al cerrar el mes, cuando las cifras no cuadran.
    "CONSERVACION_REGISTROS_CRM_DIAS": 30,
    # Un aviso sin asociar necesita que alguien tenga tiempo de vincularlo.
    "CONSERVACION_SIN_ASOCIAR_DIAS": 30,
    # Una tarea cerrada es la prueba de que el trabajo se hizo, y eso se revisa al cerrar
    # el trimestre.
    "CONSERVACION_TAREAS_DIAS": 30,
    # Un aviso leído ya cumplió; se conserva lo justo para poder reconstruir una semana.
    "CONSERVACION_AVISOS_DIAS": 14,
    # Capítulo 32. El conjunto de realimentación es un DERIVADO: se vuelve a extraer de la
    # base cuando haga falta, con la misma consulta y el mismo manifiesto. Lo único que
    # justifica conservarlo es poder repetir un entrenamiento y comparar el resultado con
    # el anterior, y eso no se hace un año después; se hace esa semana.
    "CONSERVACION_REALIMENTACION_DIAS": 7,
    # Capítulo 32, y el mínimo más alto de la tabla con diferencia. La bitácora es el único
    # sitio donde consta quién borró una ficha, quién lanzó un recálculo o quién tanteó los
    # límites de su rol; un plazo corto aquí no ahorra espacio, borra la prueba. Un año es
    # el ciclo de revisión más corto que tiene sentido: por debajo, la purga se llevaría los
    # asientos antes de que nadie haya mirado el ejercicio completo.
    "CONSERVACION_AUDITORIA_DIAS": 365,
}

# Mínimo de cada plazo del motor de reglas (capítulo 28). Mismo criterio que arriba: un `0`
# escrito por error no puede convertir el motor en una máquina de avisar. Aquí el daño no es
# borrar sino lo contrario —inundar—, y el resultado práctico es el mismo: una bandeja con
# cuarenta tareas de la misma mañana no se lee, y el sistema deja de decir qué hacer hoy.
PLAZOS_MINIMOS_DE_LAS_REGLAS = {
    # Menos de una hora para el primer contacto es pedir que nadie coma.
    "REGLA_PRIMER_CONTACTO_HORAS": 1,
    # Un HOT recién llegado a media tarde no lleva «demasiado tiempo» a las dos horas.
    "REGLA_HOT_SIN_CONTACTO_HORAS": 4,
    # El aviso al líder existe para escalar, y escalar exige que el primero tuviera margen.
    "REGLA_HOT_LIDER_HORAS": 8,
    # Volver a llamar el mismo día a quien no contestó es insistir, no hacer seguimiento.
    "REGLA_VOLVER_A_LLAMAR_DIAS": 1,
    # La víspera es la víspera: un recordatorio a diez minutos no da tiempo a prepararse.
    "REGLA_RECORDATORIO_DE_REUNION_HORAS": 1,
    # Una semana de silencio no es un prospecto dormido; es una semana.
    "REGLA_DORMIDO_DIAS": 7,
}


class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str = "Sistema Inteligente de Lead Scoring - PluriOne"
    # Por defecto 'development': producción debe declararse explícitamente por entorno,
    # de modo que un despliegue mal configurado nunca se ejecute con valores laxos por accidente.
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    # Sin valor por defecto: debe inyectarse por entorno. En producción su ausencia aborta el arranque.
    SECRET_KEY: str = ""
    # --- JWT ---
    JWT_ALGORITHM: str = "HS256"

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def _validar_algoritmo_jwt(cls, valor: str) -> str:
        """
        Solo HMAC, y la aplicación no arranca con otro.

        No hay un tercero que necesite verificar estos tokens con una clave pública. Admitir
        ES256 o RS256 por variable de entorno cambiaría el modelo de claves sin cambiar el
        código que las gestiona. Y exigiría volver a instalar criptografía asimétrica, que
        salió del lock en el capítulo 23 junto con python-jose y el aviso sin arreglo de
        `ecdsa` que el CI tenía que ignorar.
        """
        if valor not in ALGORITMOS_JWT_ADMITIDOS:
            raise ValueError(
                f"JWT_ALGORITHM={valor!r} no admitido; use uno de {sorted(ALGORITMOS_JWT_ADMITIDOS)}."
            )
        return valor
    JWT_ISSUER: str = "plurione-lead-scoring"
    JWT_AUDIENCE: str = "plurione-lead-scoring-api"
    # Access token corto: vive solo en memoria del navegador y se renueva vía refresh.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Refresh token largo: viaja en cookie HttpOnly restringida al endpoint de refresco.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "plurione_refresh"
    # Margen durante el que un refresh token recién consumido se sigue admitiendo.
    # Dos pestañas del mismo navegador refrescan a la vez —cada una con su propio módulo
    # de API, y la deduplicación del cliente no cruza pestañas—, así que la segunda llega
    # con un token que la primera acaba de consumir. Sin este margen, ese usuario, que no
    # hizo nada malo, se quedaría fuera de su sesión. Reabre la ventana de una cookie
    # robada durante estos segundos, frente a los siete días que duraba antes.
    REFRESH_ROTATION_GRACE_SECONDS: int = 10
    # En producción la cookie exige HTTPS; en desarrollo se permite HTTP local.
    REFRESH_COOKIE_SECURE: bool = True

    # --- Segundo factor (capítulo 35) ---
    # Cuánto vive el desafío entre los dos pasos del login: lo que se tarda en sacar el
    # teléfono y leer un código, no lo que dura una sesión. Cinco minutos es holgado para
    # eso y corto para quien se haya hecho con el desafío de otro.
    SEGUNDO_FACTOR_DESAFIO_MINUTOS: int = 5
    # Intentos de código por desafío antes de invalidarlo. Un TOTP son seis dígitos: sin un
    # tope, un millón de intentos lo rompen, y el límite por IP no basta porque cuenta
    # peticiones y no intentos contra una misma cuenta.
    SEGUNDO_FACTOR_INTENTOS: int = 5
    # El tope por IP de la ruta del segundo paso. Va aparte del login porque son dos cosas
    # distintas: fallar la contraseña muchas veces es un barrido de cuentas; fallar el
    # código muchas veces es un ataque contra una cuenta concreta cuya contraseña ya cayó.
    SEGUNDO_FACTOR_LIMITE_POR_IP: str = "20/minute"

    # --- Contraseñas filtradas, comprobadas fuera (capítulo 37) ---
    # La lista local del capítulo 23 es una foto de dos listas públicas: no se actualiza
    # sola y cubre lo frecuente, no lo exhaustivo (§3.7 de la congelación). Preguntar por
    # rango —k-anonymity— añade cientos de millones de huellas sin meter un gigabyte en la
    # imagen y sin mandar la contraseña a ningún sitio: salen cinco caracteres del resumen.
    #
    # ENCENDIDO por defecto, al revés que COMPROBAR_DIRECCION_PUBLICA, y la diferencia es
    # deliberada. Aquella comprobación sin red deja una alarma encendida en el panel; esta,
    # sin red, no cambia nada: la lista local sigue rechazando y el veredicto remoto queda
    # en «no se pudo preguntar». Una defensa que solo protege a quien se acordó de activarla
    # protege a muy poca gente.
    #
    # La suite nunca sale a internet aunque esto esté encendido: `filtradas_remotas.consultar`
    # se niega a abrir un socket con ENVIRONMENT=test si no se le inyecta una sonda.
    COMPROBAR_CONTRASENAS_FILTRADAS: bool = True
    # Dos segundos. El alta de usuario espera a esto, así que el tope no es «cuánto aguanto
    # que tarde» sino «cuánto puede un tercero retener a quien está dándose de alta». No hay
    # reintentos: un reintento con espera multiplica este número por el que nadie fijó.
    CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS: float = 2.0

    @field_validator("CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS")
    @classmethod
    def _validar_espera_de_filtradas(cls, valor: float) -> float:
        """
        Un tope largo es peor que no tener la comprobación: convierte un servicio ajeno
        caído en un formulario que parece colgado, y quien lo sufre no tiene forma de saber
        que la culpa es de un tercero. Diez segundos es ya un abuso; medio segundo no da
        tiempo ni al apretón de manos TLS.
        """
        if not 0.5 <= valor <= 10:
            raise ValueError(
                "CONTRASENAS_FILTRADAS_TIMEOUT_SEGUNDOS debe estar entre 0.5 y 10: por "
                "debajo no cabe el apretón de manos TLS y por encima el alta se queda "
                "colgada esperando a un tercero."
            )
        return valor

    # --- Webhook CRM (HMAC-SHA256) ---
    # Secreto compartido con el CRM emisor. Sin él, el webhook queda deshabilitado (503).
    CRM_WEBHOOK_SECRET: str = ""
    # Ventana anti-replay: firmas con timestamp fuera de este margen se rechazan.
    CRM_WEBHOOK_TOLERANCE_SECONDS: int = 300
    # Tope de tamaño del cuerpo del webhook (256 KiB) para evitar abuso de memoria.
    CRM_WEBHOOK_MAX_BODY_BYTES: int = 256 * 1024

    # Ventana durante la que un mismo evento se considera repetido. La firma HMAC ya
    # impide falsificar una petición, pero no impide reenviar una legítima capturada: el
    # rechazo por marca de tiempo solo actúa pasados CRM_WEBHOOK_TOLERANCE_SECONDS, y
    # dentro de ese margen la repetición es indistinguible del original.
    CRM_IDEMPOTENCY_WINDOW_SECONDS: int = 900
    # Cada cuánto, como mucho, se purgan las entregas ya caducadas del registro. La
    # limpieza va colgada del propio flujo de ingesta porque esta pila no despliega
    # ningún planificador; el intervalo evita pagar un DELETE en cada webhook.
    CRM_DEDUP_PURGE_INTERVAL_SECONDS: int = 300

    # --- Integraciones (Fase 15) ---
    # Cada integración tiene su secreto, su interruptor y su límite, y no comparte ninguno:
    # revocar Calendly —vaciar su secreto o apagarla— no toca a WhatsApp, y un secreto
    # filtrado no firma entregas de otra. Apagadas por defecto: una integración se enciende
    # cuando hay alguien al otro lado.
    #
    # El CRM conserva `CRM_WEBHOOK_SECRET` y `RATE_LIMIT_WEBHOOK` como secreto y límite, y
    # gana su interruptor. Encendido por defecto, porque ya lo estaba.
    INTEGRACION_CRM_ACTIVA: bool = True

    INTEGRACION_CALENDLY_ACTIVA: bool = False
    INTEGRACION_CALENDLY_SECRETO: str = ""
    INTEGRACION_CALENDLY_LIMITE: str = "60/minute"

    INTEGRACION_WHATSAPP_ACTIVA: bool = False
    INTEGRACION_WHATSAPP_SECRETO: str = ""
    INTEGRACION_WHATSAPP_LIMITE: str = "120/minute"

    INTEGRACION_LINKEDIN_LEAD_GEN_ACTIVA: bool = False
    INTEGRACION_LINKEDIN_LEAD_GEN_SECRETO: str = ""
    INTEGRACION_LINKEDIN_LEAD_GEN_LIMITE: str = "60/minute"

    INTEGRACION_FORMULARIO_WEB_ACTIVA: bool = False
    INTEGRACION_FORMULARIO_WEB_SECRETO: str = ""
    INTEGRACION_FORMULARIO_WEB_LIMITE: str = "30/minute"

    @field_validator(
        "INTEGRACION_CALENDLY_LIMITE",
        "INTEGRACION_WHATSAPP_LIMITE",
        "INTEGRACION_LINKEDIN_LEAD_GEN_LIMITE",
        "INTEGRACION_FORMULARIO_WEB_LIMITE",
        "INTERES_LIMITE_POR_IP",
        "INTERES_LIMITE_POR_PUBLICACION",
        "INTERES_LIMITE_DE_LECTURAS_POR_IP",
        "INTERES_LIMITE_DE_TARJETAS_POR_IP",
    )
    @classmethod
    def _validar_limite_de_integracion(cls, valor: str) -> str:
        """
        Un límite mal escrito se descubre al arrancar, no en la primera entrega: `limits`
        lo interpretaría al recibirla y respondería 500 a un emisor que no hizo nada mal.
        """
        from limits import parse

        try:
            parse(valor)
        except ValueError as exc:
            raise ValueError(f"Límite de integración inválido: '{valor}' (ejemplo: '60/minute').") from exc
        return valor

    # --- Página de interés (pública) ---
    # Límites de envío de `/api/v1/interes/{slug}`. Son bajos a propósito: es la única ruta
    # sin sesión que escribe en la base. El de IP frena a quien insiste desde un sitio; el de
    # publicación frena el mismo envío repartido entre muchas IP.
    INTERES_LIMITE_POR_IP: str = "10/hour"
    INTERES_LIMITE_POR_PUBLICACION: str = "120/hour"
    # Abrir la página no es enviar. Hasta el capítulo 25 las dos cosas gastaban la misma
    # cuenta de diez por hora, y desde una oficina detrás de una sola IP bastaban unas pocas
    # visitas de compañeros para que el siguiente no pudiera ni ver el formulario. La
    # lectura tiene su propio límite, más alto: no escribe nada, y lo que frena es recorrer
    # enlaces en bucle.
    INTERES_LIMITE_DE_LECTURAS_POR_IP: str = "120/hour"
    # El HTML de la página y su imagen de vista previa (capítulo 27) tienen su propia cuenta.
    # Quien los pide casi siempre es un rastreador de una red social, no una persona: si
    # gastaran el cupo de lectura, unas cuantas veces compartido el enlace dejarían sin poder
    # abrir la página a quien la quisiera ver. Y la imagen se dibuja al pedirla, así que sin
    # un tope sería una forma barata de hacer trabajar al servidor.
    INTERES_LIMITE_DE_TARJETAS_POR_IP: str = "240/hour"

    # Con qué arranca la aplicación en el HTML que sirve el servidor para `/interes/{slug}`.
    # Son nombres fijos a propósito (`vite.config.js`): el servidor tiene que poder
    # nombrarlos sin conocer la huella que el compilador le pone al resto de los archivos.
    PAGINA_PUBLICA_SCRIPT: str = "/assets/app.js"
    PAGINA_PUBLICA_HOJA: str = "/assets/app.css"

    # --- Publicaciones ---
    # Dirección bajo la que se sirve el enlace público de cada publicación:
    # `<PUBLICACIONES_URL_BASE>/<slug>`. Es lo que se pega en LinkedIn, así que en un
    # despliegue tiene que ser la dirección pública del sitio, no la de desarrollo.
    #
    # El último segmento **es** la ruta que atiende la página: el panel solo reconoce
    # `/interes/<slug>`. Con `/p` el texto copiado llevaba a la pantalla de acceso, y eso no
    # se nota escribiendo la dirección a mano: solo siguiendo el enlace ya pegado en el post.
    # `tests/test_publicaciones.py` compara este valor con la ruta del frontend.
    # Desde el capítulo 34 es, además, **la única** cosa que hay que cambiar para pasar de
    # la dirección efímera de un túnel de prueba a un dominio propio. No hay ninguna otra
    # copia de la dirección pública en el código: la tarjeta de vista previa, su imagen, el
    # texto que se copia para cada red y el enlace que enseña el panel salen todos de
    # `enlace_publico()`, que lee este valor. `tests/test_puerta_estrecha.py` lo comprueba
    # buscando direcciones escritas a mano en todo el árbol.
    PUBLICACIONES_URL_BASE: str = "http://localhost:3000/interes"

    # --- La dirección pública, comprobada (capítulo 34) ---
    # Un túnel gratuito da una dirección DISTINTA en cada arranque. Eso convierte un enlace
    # ya publicado en un enlace muerto sin que nada del sistema se entere: el post sigue en
    # LinkedIn, la publicación sigue activa, y quien pulsa no llega a ninguna parte.
    #
    # Apagado por defecto a propósito. La comprobación sale a internet, y una suite de
    # pruebas o un arranque en desarrollo no deben depender de que haya red ni ponerse a
    # pedir una dirección que no existe. Se enciende en el despliegue que está detrás del
    # túnel, que es el único donde la pregunta tiene sentido.
    COMPROBAR_DIRECCION_PUBLICA: bool = False
    # Cada cuánto se vuelve a preguntar. El panel consulta el estado cada vez que se abre
    # la pantalla de publicaciones, y sin caché eso serían varias salidas a internet por
    # minuto para responder algo que cambia una vez al día.
    DIRECCION_PUBLICA_CACHE_SEGUNDOS: int = 120
    # Un túnel caído no tarda en no contestar: tarda en no contestar *nada*. El tope corto
    # es lo que distingue «no responde» de «el panel se quedó colgado».
    DIRECCION_PUBLICA_TIMEOUT_SEGUNDOS: float = 4.0

    @field_validator("PUBLICACIONES_URL_BASE")
    @classmethod
    def _validar_url_base_de_publicaciones(cls, valor: str) -> str:
        """
        Un valor mal escrito se descubre al arrancar. Si no, cada texto copiado para LinkedIn
        llevaría un enlace roto, y nadie lo notaría hasta ver el post ya publicado.
        """
        from urllib.parse import urlsplit

        limpio = valor.strip().rstrip("/")
        partes = urlsplit(limpio)
        if partes.scheme not in ("http", "https") or not partes.netloc or partes.query or partes.fragment:
            raise ValueError(
                "PUBLICACIONES_URL_BASE tiene que ser una dirección http(s) sin parámetros "
                f"ni fragmento (ejemplo: 'https://plurione.com/interes'); se recibió '{valor}'."
            )
        return limpio

    # --- Bitácora de auditoría ---
    # Tope de asientos que devuelve una consulta, para que un `limit` desmedido no
    # convierta la bitácora en la forma más cómoda de tumbar la API.
    #
    # No hay ajuste de retención, y es deliberado: la aplicación no purga la bitácora.
    # Declarar `AUDIT_LOG_RETENTION_DAYS` sin que nada lo leyera habría anunciado una
    # política que no existe, que es justo el defecto que motivó esta fase. El borrado
    # es una decisión de quien opera y se aplica con las herramientas de la base.
    AUDIT_LOG_MAX_PAGE_SIZE: int = 200

    # --- Retención del historial de puntuación ---
    # Meses completos de detalle que conserva `score_histories`, además del mes en curso.
    # Lo anterior lo resume `retencion_service` por prospecto y mes y lo borra. A diferencia
    # de la bitácora, aquí SÍ hay ajuste, porque hay algo que lo lee: la purga programada
    # (servicio `retencion-historial` de la pila). La política completa está en el capítulo
    # 20 de la memoria técnica.
    SCORE_HISTORY_RETENTION_MONTHS: int = 12

    @field_validator("SCORE_HISTORY_RETENTION_MONTHS")
    @classmethod
    def _validar_retencion_del_historial(cls, valor: int) -> int:
        """
        Un plazo demasiado corto no degrada: destruye.

        Con un mes de retención, cada madrugada se resumiría la trayectoria de la semana
        anterior y la comparación entre meses —lo único que un resumen permite hacer—
        dejaría de tener detalle con el que contrastarse. Se falla al arrancar, que es
        cuando aún no se ha borrado nada.
        """
        if valor < RETENCION_MINIMA_DEL_HISTORIAL_MESES:
            raise ValueError(
                f"SCORE_HISTORY_RETENTION_MONTHS={valor} está por debajo del mínimo de "
                f"{RETENCION_MINIMA_DEL_HISTORIAL_MESES} meses."
            )
        return valor

    # --- Plazos de conservación (capítulo 22) ---
    # Lo que la tabla de §20.5 dejaba «sin caducidad automática». Los aplica la misma pasada
    # diaria que resume el historial (`scripts/retencion_historial.py`), cada uno con su
    # asiento en la bitácora. Son plazos técnicos y provisionales, como los de §20.5:
    # fijarlos corresponde a quien responda del tratamiento de datos.
    #
    # Días después de CADUCAR, no de emitirse: un token vigente no se toca nunca.
    CONSERVACION_SESIONES_DIAS: int = 30
    # Días desde que el trabajo TERMINÓ. Los vivos no se tocan, por antiguos que sean.
    CONSERVACION_TRABAJOS_DIAS: int = 90
    # Días desde la sincronización.
    CONSERVACION_REGISTROS_CRM_DIAS: int = 90
    # Días desde que el aviso llegó a la bandeja.
    CONSERVACION_SIN_ASOCIAR_DIAS: int = 90

    @field_validator(*CONSERVACION_MINIMA_DIAS)
    @classmethod
    def _validar_plazo_de_conservacion(cls, valor: int, info) -> int:
        """Como con el historial: un plazo demasiado corto se rechaza al arrancar, antes de borrar nada."""
        minimo = CONSERVACION_MINIMA_DIAS[info.field_name]
        if valor < minimo:
            raise ValueError(f"{info.field_name}={valor} está por debajo del mínimo de {minimo} días.")
        return valor

    # Días desde que la tarea se cerró. Una tarea abierta no caduca nunca: sigue siendo
    # trabajo pendiente por viejo que sea, y borrarla lo haría desaparecer sin hacerse.
    CONSERVACION_TAREAS_DIAS: int = 180
    # Días desde que el aviso se leyó. Uno sin leer no caduca: nadie se ha enterado todavía.
    CONSERVACION_AVISOS_DIAS: int = 90

    # --- Las dos últimas filas sin plazo (capítulo 32) ---
    #
    # Días desde que se escribió cada archivo del conjunto de realimentación. Es la última
    # fila de la tabla de §20.5 que seguía diciendo «sin mecanismo», y la única que vive
    # FUERA de la base: un CSV con una fila por persona cerrada, más su manifiesto. Treinta
    # días es lo que dura una tanda de entrenamiento de principio a fin —extraer, entrenar,
    # comparar contra el artefacto vigente, decidir—; pasado eso, el CSV ya no es material
    # de trabajo sino una copia de datos personales que nadie mira.
    CONSERVACION_REALIMENTACION_DIAS: int = 30
    # Dónde vive ese conjunto. Vacío significa «donde lo deja el extractor cuando se lanza
    # desde el árbol del repositorio» (`ml_pipeline/data`), que es su valor por defecto
    # documentado. En la pila es un volumen, montado tanto en el backend —que es quien
    # extrae— como en el servicio que purga: sin ese volumen compartido el plazo existiría
    # y no alcanzaría a ningún archivo, que es la forma más cara de no tener plazo.
    REALIMENTACION_DIR: str = ""
    # Días desde que ocurrió el asiento. Hasta el capítulo 32 la bitácora no tenía plazo EN
    # LA APLICACIÓN: se remitía a «una decisión de operación» (N-8) y crecía sin techo.
    # Sigue siendo una decisión de operación —este número es técnico y provisional, no una
    # valoración jurídica, igual que todos los de §20.5—, pero ahora tiene un mecanismo y un
    # valor por defecto conservador en lugar de ninguno de las dos cosas.
    #
    # Dos años, y no menos, por lo que la bitácora es: el único registro de quién hizo qué.
    # Borrar aquí es borrar la prueba de un abuso de permisos, no liberar espacio, así que
    # el defecto se equivoca del lado de conservar y quien opere decidirá si acortarlo.
    CONSERVACION_AUDITORIA_DIAS: int = 730

    # --- Plazos del motor de reglas (capítulo 28) ---
    # Cuánto se da para cada cosa. Son de la instalación, no del dominio: un equipo que
    # atiende cuentas grandes quizá dé 48 horas al primer contacto. El vocabulario de las
    # reglas está en `app/core/agenda.py`.
    #
    # Para cuándo vence la tarea de primer contacto desde que se asigna el prospecto.
    REGLA_PRIMER_CONTACTO_HORAS: int = 24
    # Cuánto puede estar un HOT sin que nadie lo contacte antes de avisar a su asesor.
    REGLA_HOT_SIN_CONTACTO_HORAS: int = 24
    # Y antes de que el aviso suba al líder. Tiene que ser mayor que el anterior.
    REGLA_HOT_LIDER_HORAS: int = 48
    # Cuántos días después de una llamada sin respuesta toca volver a intentarlo.
    REGLA_VOLVER_A_LLAMAR_DIAS: int = 2
    # Cuánto antes de una reunión agendada se recuerda. 24 h es «la víspera».
    REGLA_RECORDATORIO_DE_REUNION_HORAS: int = 24
    # Días sin ninguna actividad tras los cuales el prospecto se marca dormido.
    REGLA_DORMIDO_DIAS: int = 30

    @field_validator(*PLAZOS_MINIMOS_DE_LAS_REGLAS)
    @classmethod
    def _validar_plazo_de_regla(cls, valor: int, info) -> int:
        """Un plazo por debajo del mínimo se rechaza al arrancar, antes de crear nada."""
        minimo = PLAZOS_MINIMOS_DE_LAS_REGLAS[info.field_name]
        if valor < minimo:
            raise ValueError(
                f"{info.field_name}={valor} está por debajo del mínimo de {minimo}."
            )
        return valor

    @model_validator(mode="after")
    def _validar_escalado_al_lider(self) -> "Settings":
        """
        El aviso al líder llega DESPUÉS del aviso al asesor, o no es un escalado.

        Cada plazo por separado puede ser válido y la pareja no serlo: con 24 y 24, las dos
        reglas disparan en la misma pasada y el líder se entera a la vez que la persona que
        todavía podía resolverlo. Con 24 y 12, antes. Esto no lo puede ver un validador de
        un solo campo, y es justo el error que nadie notaría: no falla nada, simplemente el
        líder recibe avisos que no debería estar recibiendo.
        """
        if self.REGLA_HOT_LIDER_HORAS <= self.REGLA_HOT_SIN_CONTACTO_HORAS:
            raise ValueError(
                f"REGLA_HOT_LIDER_HORAS={self.REGLA_HOT_LIDER_HORAS} tiene que ser mayor que "
                f"REGLA_HOT_SIN_CONTACTO_HORAS={self.REGLA_HOT_SIN_CONTACTO_HORAS}: el aviso al "
                "líder escala el del asesor, y no puede llegar antes ni a la vez."
            )
        return self

    # Database (SQLite autocontenido por defecto, compatible con PostgreSQL en producción)
    DATABASE_URL: str = "sqlite:///./lead_scoring.db"
    POSTGRES_USER: str = "postgres"
    # Sin valor por defecto: el despliegue la inyecta. Un "postgres/postgres" por defecto
    # es exactamente la credencial que prueba primero cualquier escaneo automatizado.
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "lead_scoring_db"
    POSTGRES_PORT: int = 5432

    # AI Mode: 'native' para motor de inferencia y XAI de producción autocontenido, 'azure' para nube
    AI_MODE: str = "native"

    # Azure OpenAI (Opcional si se requiere nube externa)
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Azure Machine Learning (Opcional si se requiere nube externa)
    AZURE_ML_ENDPOINT: str = ""
    AZURE_ML_API_KEY: str = ""
    MODEL_VERSION: str = "v1.0.0-hybrid"

    # Ruta absoluta del artefacto .joblib. En el contenedor el modelo se copia a una
    # ubicación fija; vacía, el adaptador cae a su búsqueda relativa habitual dentro del
    # repositorio (A-5: la imagen se construía sin el modelo y arrancaba degradada).
    ML_MODEL_PATH: str = ""
    # Huella SHA-256 esperada del artefacto. `joblib.load` deserializa con pickle, que
    # ejecuta código al cargar: quien pueda sustituir el fichero al que apunta ML_MODEL_PATH
    # ejecuta lo que quiera dentro del backend (A-10). Con este valor fijado, una huella
    # distinta impide la carga en lugar de ejecutarla. Vacío = sin anclar (se registra la
    # huella encontrada para poder fijarla, y en producción se avisa).
    ML_MODEL_SHA256: str = ""

    # --- Limitación de tasa (slowapi) ---
    # Los límites se leen en cada petición, no al declarar el endpoint, para poder
    # ajustarlos por entorno sin reconstruir la imagen.
    RATE_LIMIT_ENABLED: bool = True
    # Si se hace caso a `X-Forwarded-For` para identificar al cliente. Por defecto NO.
    #
    # El valor por defecto era `True`, y esa es la clase de opción que no debe venir
    # abierta: la cabecera la escribe el cliente, así que un backend alcanzable
    # directamente —el `ports: 127.0.0.1:8000` de esta misma pila, un despliegue sin
    # proxy, un puerto abierto por error— acepta como identidad lo que le manden y el
    # tope por IP se esquiva rotando un valor inventado en cada intento. El despliegue
    # que sí tiene un proxy de confianza delante lo declara, y ese es un acto consciente
    # de quien sabe que nginx reescribe la cabecera; el que no lo declara pierde
    # precisión al agrupar clientes, que es un fallo hacia el lado seguro.
    TRUST_PROXY_HEADERS: bool = False
    # Login: el objetivo es la fuerza bruta de contraseñas. bcrypt ya hace cara cada
    # comprobación; esto acota además cuántas puede intentar una IP por minuto.
    RATE_LIMIT_LOGIN: str = "10/minute"
    # Scoring: cada llamada ejecuta el pipeline de inferencia y la generación de texto.
    RATE_LIMIT_PREDICT: str = "60/minute"
    # Webhook: holgado porque el emisor es un CRM legítimo con picos de sincronización,
    # pero acotado para que una firma filtrada no permita inundar la base de datos.
    RATE_LIMIT_WEBHOOK: str = "120/minute"
    # Dónde se lleva la cuenta. Con el valor por defecto vive en la memoria del proceso,
    # y la imagen arranca uvicorn con varios workers: cada uno cuenta por su lado, así que
    # el tope real que ve un cliente es el declarado MULTIPLICADO por el número de workers
    # (medido: con 2 workers y "10/minute" pasan 11-20 intentos antes del corte). Para un
    # límite exacto —o para más de una instancia— hay que apuntar a un almacén compartido:
    #   RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
    # Se deja `memory://` por defecto porque esta pila no despliega Redis; el tope sigue
    # acotando la fuerza bruta, pero no es exacto.
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    # Azure AI Search (Opcional si se requiere búsqueda semántica en la nube).
    # `AzureAISearchAdapter` las consume al construirse: sin declararlas aquí,
    # arrancar con AI_MODE=azure fallaba con AttributeError en vez de con un
    # error de configuración legible.
    AZURE_AI_SEARCH_ENDPOINT: str = ""
    AZURE_AI_SEARCH_KEY: str = ""
    AZURE_AI_SEARCH_INDEX: str = "plurione-leads-index"

    # Scoring Algorithm Constants
    SCORE_WEIGHT_ML: float = 0.60
    SCORE_WEIGHT_HEURISTIC: float = 0.40
    DECAY_HALF_LIFE_DAYS: float = 14.0
    HOT_THRESHOLD: float = 75.0
    WARM_THRESHOLD: float = 45.0

    # CORS
    # `NoDecode` desactiva el parseo JSON que pydantic-settings aplica a los campos de
    # tipo lista ANTES de cualquier validador. Con él activo, un `CORS_ORIGINS=` vacío en
    # el `.env` —la forma natural de escribir «ninguno»— moría en `json.loads` con un
    # `SettingsError` que no nombra ni la causa ni el remedio. El validador de abajo se
    # encarga ahora del formato y admite JSON, lista por comas y cadena vacía.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # --- Registro estructurado y métricas (N-14) ---
    # `json`, `text` o `auto`. Con `auto` manda el entorno: JSON en producción y staging,
    # donde los registros los lee una herramienta, y texto en desarrollo, donde los lee
    # una persona en una terminal. No se fija JSON en todas partes porque eso volvería
    # ilegible el bucle local, y un registro que nadie mira en desarrollo es un registro
    # que nadie corrige.
    LOG_FORMAT: str = "auto"

    # Ruta `/metrics` en formato de exposición de Prometheus.
    METRICS_ENABLED: bool = True
    # Credencial del recolector. Prometheus no sabe iniciar sesión, así que la protección
    # de esta ruta no puede ser el JWT del resto de la API: se compara un testigo fijo con
    # `compare_digest`.
    #
    # Vacío significa cosas distintas según dónde: en desarrollo, ruta abierta; en
    # producción y staging, ruta APAGADA —404, como si no existiera—. El volcado dice
    # cuántos prospectos hay, cómo se reparten por categoría y qué rutas se usan; es poco
    # para un atacante y mucho para un competidor, y sobre todo es información que nadie
    # eligió publicar. Que el valor por defecto sea «no publicar» obliga a decidirlo.
    METRICS_TOKEN: str = ""

    # Seguridad y RBAC
    DEFAULT_USER_ROLE: str = "Commercial_Executive"

    @field_validator("LOG_FORMAT")
    @classmethod
    def _validar_formato_de_registro(cls, valor: str) -> str:
        """
        Un valor mal escrito no debe caer en silencio al formato de texto.

        `LOG_FORMAT=jsonn` en un `.env` de producción dejaría los registros en texto plano
        sin que nada lo dijera, y el agregador que espera JSON los descartaría en bloque:
        el sistema seguiría "funcionando" y nadie tendría registros hasta que hiciera
        falta consultarlos.
        """
        normalizado = (valor or "auto").strip().lower()
        if normalizado not in ("json", "text", "auto"):
            raise ValueError(
                f"LOG_FORMAT='{valor}' no es válido. Use 'json', 'text' o 'auto'."
            )
        return normalizado

    @property
    def is_hardened_environment(self) -> bool:
        """True en producción, staging y equivalentes: donde se cierran las concesiones."""
        return self.ENVIRONMENT.strip().lower() in HARDENED_ENVIRONMENTS

    @model_validator(mode="after")
    def _validate_score_weights(self) -> "Settings":
        """
        Exige que los pesos del score híbrido sumen 1.0.

        La fórmula `peso_ml * ml + peso_heur * heur` solo produce una escala 0-100 si
        los pesos suman uno. Con 0.6 + 0.5, por ejemplo, todos los prospectos se
        desplazan hacia arriba y los umbrales HOT/WARM dejan de significar lo que dice
        la documentación, sin que nada falle de forma visible: los scores simplemente
        salen mal. Se aborta el arranque en cualquier entorno porque no es un problema
        de endurecimiento sino un error aritmético de configuración.
        """
        total = self.SCORE_WEIGHT_ML + self.SCORE_WEIGHT_HEURISTIC
        # Tolerancia de coma flotante: 0.60 + 0.40 no da exactamente 1.0 en binario.
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                f"SCORE_WEIGHT_ML ({self.SCORE_WEIGHT_ML}) + SCORE_WEIGHT_HEURISTIC "
                f"({self.SCORE_WEIGHT_HEURISTIC}) = {total}, y deben sumar exactamente 1.0. "
                "Ajuste ambas variables de entorno de forma complementaria."
            )
        return self

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """
        Exige una SECRET_KEY propia, aleatoria y no comprometida en entornos endurecidos.

        Fuera de ellos (desarrollo, tests) se genera una clave efímera en memoria para no
        bloquear el trabajo local: al reiniciar el proceso la clave cambia, de modo que
        nunca se convierte en un secreto de facto ni se persiste en disco.
        """
        key = (self.SECRET_KEY or "").strip()
        is_hardened = self.is_hardened_environment

        # Fuera de producción el frontend corre en http://localhost: una cookie `Secure`
        # nunca se enviaría y el refresco quedaría roto.
        if not is_hardened:
            self.REFRESH_COOKIE_SECURE = False

        if es_clave_comprometida(key):
            problem = "es una clave publicada en el repositorio y se considera comprometida"
        elif not key:
            problem = "no está definida"
        elif len(key) < MIN_SECRET_KEY_LENGTH:
            problem = f"tiene menos de {MIN_SECRET_KEY_LENGTH} caracteres"
        else:
            return self

        if is_hardened:
            raise ValueError(
                f"SECRET_KEY inválida para ENVIRONMENT='{self.ENVIRONMENT}': {problem}. "
                "Defina la variable de entorno SECRET_KEY con un valor único y aleatorio antes de arrancar. "
                'Puede generarla con: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )

        self.SECRET_KEY = secrets.token_urlsafe(64)
        logger.warning(
            "SECRET_KEY %s; se generó una clave efímera para ENVIRONMENT='%s'. "
            "Esto NO es válido en producción: defina SECRET_KEY por variable de entorno.",
            problem,
            self.ENVIRONMENT,
        )
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _admitir_formatos_de_cors(cls, valor):
        """
        Acepta la variable vacía y la lista separada por comas, además del JSON.

        Sin esto, un `CORS_ORIGINS=` en el `.env` —que es lo que hace cualquiera al
        querer decir «ninguno»— revienta antes de llegar a ningún validador, con un
        `SettingsError` de pydantic que no menciona ni la causa ni el remedio. El
        formato JSON sigue funcionando; simplemente deja de ser el único.
        """
        if valor is None:
            return []
        if isinstance(valor, str):
            texto = valor.strip()
            if not texto:
                return []
            if texto.startswith("["):
                try:
                    return json.loads(texto)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"CORS_ORIGINS parece una lista JSON pero no se pudo interpretar: {exc}. "
                        'Escríbala como ["https://app.plurione.com"], o como una lista '
                        "separada por comas, o déjela vacía."
                    ) from exc
            return [parte.strip() for parte in texto.split(",") if parte.strip()]
        return valor

    @model_validator(mode="after")
    def _validate_cors_origins(self) -> "Settings":
        """
        Normaliza la lista de orígenes permitidos y prohíbe el comodín (A-8).

        `allow_origins=["*"]` junto con `allow_credentials=True` no es una configuración
        permisiva: es una puerta abierta. Starlette, cuando ve el comodín y las credenciales
        activadas, deja de responder `Access-Control-Allow-Origin: *` y pasa a **devolver el
        origen que pidió**, sea cual sea, acompañado de `Access-Control-Allow-Credentials:
        true`. El navegador de la víctima entonces autoriza a cualquier página de internet a
        leer las respuestas de esta API con la sesión de esa víctima: basta con que visite el
        sitio del atacante estando autenticada. Y el token de refresco de este sistema viaja
        en cookie, así que el navegador la adjunta solo.

        Se normaliza además la barra final porque la comparación de orígenes es textual:
        `https://app.plurione.com/` nunca coincide con el `Origin` que envía el navegador,
        que jamás la lleva. Es un fallo silencioso —CORS simplemente deja de funcionar—
        que se diagnostica mal y suele "resolverse" volviendo al comodín.
        """
        normalizados: List[str] = []
        for origen in self.CORS_ORIGINS:
            limpio = (origen or "").strip().rstrip("/")
            if limpio and limpio not in normalizados:
                normalizados.append(limpio)

        if "*" in normalizados:
            raise ValueError(
                "CORS_ORIGINS contiene '*'. Con `allow_credentials=True` el comodín hace que "
                "la API devuelva el origen de quien pregunte junto a "
                "`Access-Control-Allow-Credentials: true`, autorizando a cualquier sitio a "
                "leer respuestas autenticadas desde el navegador del usuario. Enumere los "
                "orígenes exactos, por ejemplo: "
                'CORS_ORIGINS=["https://app.plurione.com"]'
            )

        # Una lista vacía NO es un error: es la configuración correcta cuando el frontend
        # se sirve desde el mismo origen que la API, que es justo lo que hace la pila de
        # Compose —nginx entrega la SPA y hace de proxy de `/api/`—. Ahí no interviene
        # CORS en absoluto. Exigir una lista obligaría a inventarse un origen para
        # satisfacer al validador, y esa clase de requisito termina en un comodín.
        #
        # Lo que sí se registra en entornos endurecidos es qué quedó permitido: si un día
        # el frontend se despliega en otro dominio y el navegador empieza a bloquear las
        # peticiones, este renglón del arranque es lo que evita que el diagnóstico acabe
        # en «pongamos asterisco y ya».
        if self.is_hardened_environment:
            if normalizados:
                logger.info(
                    "CORS: orígenes autorizados para ENVIRONMENT='%s': %s",
                    self.ENVIRONMENT,
                    ", ".join(normalizados),
                )
            else:
                logger.info(
                    "CORS: sin orígenes cruzados autorizados para ENVIRONMENT='%s'. Es lo "
                    "correcto si el frontend se sirve desde el mismo origen que la API; si "
                    "no lo hace, declare los orígenes en CORS_ORIGINS.",
                    self.ENVIRONMENT,
                )

        self.CORS_ORIGINS = normalizados
        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()
