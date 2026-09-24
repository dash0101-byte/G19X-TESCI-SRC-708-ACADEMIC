"""
Recorre la demostración entera sobre la base de demostración y la cronometra.

    python scripts/ensayo_de_la_demo.py --base <ruta al .db de demostración>
    python scripts/ensayo_de_la_demo.py            # usa DATABASE_URL si es SQLite

Los nueve pasos son los ocho de la historia del README más el del asesor, que el README
mete dentro del quinto. Cada uno se ejecuta contra la **API de verdad** —el mismo
`app.main:app` que sirve la pila— y se comprueba su resultado. Si uno falla, el ensayo para
ahí y dice cuál: un guion que se ensaya y no se comprueba es un guion que se cae delante
del sínodo.

**Nunca escribe en la base que se le pasa.** La copia a un temporal y trabaja sobre la
copia. La demostración se enseña sobre la original, y un ensayo que deje un prospecto de
prueba dentro obliga a volver a sembrarla justo antes de la defensa.

**No inicia sesión con ninguna contraseña.** Las dos cuentas que necesita —líder y asesor—
se autentican firmando su token con `create_access_token`, que es lo que hacen las guardas
del CI desde el capítulo 28. Lo que se ensaya es el camino, no el formulario de entrada.

### Sobre los tiempos que imprime

Son **tiempos de servidor**: lo que tarda la API en contestar, medido en el proceso. No son
los minutos de la exposición, que dependen de quien habla y están repartidos en
`docs/Guion_Cronometrado_de_la_Demo.md`. Sirven para una pregunta concreta y solo para esa:
**¿hay algún paso que tarde lo bastante como para que se note en la sala?** El umbral está
en `LENTO_MS`; pasarlo no es un fallo, es un aviso para no hacer ese clic en silencio.
"""
import argparse
import datetime
import os
import shutil
import sys
import tempfile
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# La consola de Windows sigue en cp1252 salvo que se le pida otra cosa, y este guion imprime
# acentos y comillas españolas en cada línea. Sin esto, el ensayo se cae al imprimir el
# resultado de un paso que había salido bien, que es la peor forma posible de fallar.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - depende de la consola del sistema
        print(f"Aviso: no se pudo forzar UTF-8 en la salida ({exc}); los acentos pueden verse mal.")

# Un paso que tarde más que esto se nota en una sala. No falla: avisa.
LENTO_MS = 400


def _origen(argumentos) -> str:
    """La base que se va a copiar. Explícita, o la de `DATABASE_URL` si es SQLite."""
    if argumentos.base:
        if not os.path.isfile(argumentos.base):
            _salir(f"no existe la base indicada: {argumentos.base}")
        return os.path.abspath(argumentos.base)

    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("sqlite"):
        _salir(
            "no se sabe qué base ensayar.\n"
            "   Pase --base <ruta al .db de demostración>, o exporte DATABASE_URL\n"
            "   apuntando a ella (es lo que hace devops/pila.py).\n"
            "   Contra PostgreSQL no se ensaya desde aquí: copiar la base no es cosa\n"
            "   de este guion."
        )
    ruta = url.split("///", 1)[-1]
    if not os.path.isfile(ruta):
        _salir(f"DATABASE_URL apunta a una base que no existe: {ruta}")
    return os.path.abspath(ruta)


def _salir(mensaje: str):
    print(f"\n[ERROR] {mensaje}")
    raise SystemExit(2)


# ==============================================================================
# Cronómetro
# ==============================================================================

class Ensayo:
    """Lleva la cuenta de los pasos, sus comprobaciones y lo que tardó el servidor."""

    def __init__(self):
        self.pasos = []
        # Lo que tarda cada pasada del motor de reglas. Se mide aparte porque no es un clic
        # de nadie: en producción es un trabajo programado que corre de madrugada.
        self.pasadas_del_motor = []
        self._abierto = None
        self._desde = 0.0

    def paso(self, numero: str, titulo: str):
        self._abierto = (numero, titulo)
        self._desde = time.perf_counter()
        print(f"\n{numero}. {titulo}")
        return self

    def cerrar(self, detalle: str):
        ms = (time.perf_counter() - self._desde) * 1000
        numero, titulo = self._abierto
        self.pasos.append({"numero": numero, "titulo": titulo, "ms": ms, "detalle": detalle})
        marca = "  <-- se nota en la sala" if ms >= LENTO_MS else ""
        print(f"   OK  {detalle}   [{ms:.0f} ms]{marca}")

    def descontar(self, segundos: float):
        """
        Quita del paso en curso algo que no es un clic de nadie.

        La pasada del motor de reglas se lanza aquí a mano porque el ensayo no espera a la
        tarea programada. En producción corre de madrugada y nadie la ve, así que meterla
        en el tiempo del paso diría que pulsar «Hoy» tarda medio segundo, y no es verdad.
        """
        self._desde += segundos
        self.pasadas_del_motor.append(segundos * 1000)

    def comprobar(self, condicion, mensaje: str):
        if not condicion:
            numero, titulo = self._abierto
            print(f"\n[FALLO] Paso {numero} ({titulo}): {mensaje}")
            print("\nEl guion no se puede enseñar tal como está. Corrija esto antes de ensayarlo")
            print("con nadie delante.")
            raise SystemExit(1)

    def resumen(self):
        print("\n" + "=" * 78)
        print("ENSAYO COMPLETO: los nueve pasos del guion se recorren de principio a fin")
        print("=" * 78)
        print(f"{'Paso':<6}{'Tiempo':>9}   Qué hace")
        print("-" * 78)
        for p in self.pasos:
            print(f"{p['numero']:<6}{p['ms']:>7.0f} ms   {p['titulo']}")
        print("-" * 78)
        total = sum(p["ms"] for p in self.pasos)
        lentos = [p for p in self.pasos if p["ms"] >= LENTO_MS]
        print(f"{'':<6}{total:>7.0f} ms   de servidor en todo el recorrido")
        if self.pasadas_del_motor:
            media = sum(self.pasadas_del_motor) / len(self.pasadas_del_motor)
            print(
                f"{'':<6}{media:>7.0f} ms   media de la pasada del motor de reglas "
                f"({len(self.pasadas_del_motor)} pasadas), descontada de los pasos:\n"
                f"{'':<16}en producción es un trabajo programado, no un clic."
            )
        if lentos:
            print(
                f"\nPasos que pasan de {LENTO_MS} ms: "
                + ", ".join(p["numero"] for p in lentos)
                + ".\nNo es un fallo. Es donde hay que seguir hablando mientras carga."
            )
        print(
            "\nLos minutos de la exposición no salen de aquí: están repartidos en\n"
            "docs/Guion_Cronometrado_de_la_Demo.md."
        )


# ==============================================================================
# El recorrido
# ==============================================================================

def ensayar(cliente, db, lider, asesor, modulos) -> Ensayo:
    e = Ensayo()
    marca = datetime.datetime.now().strftime("%H%M%S")
    correo = f"lucia.prado.ensayo.{marca}@ejemplo-demo.mx"

    cab_lider = {"Authorization": f"Bearer {modulos['token'](lider)}"}
    cab_asesor = {"Authorization": f"Bearer {modulos['token'](asesor)}"}

    # ---------------------------------------------------------------- Paso 0
    # No es un paso del guion: es la razón de que el guion tenga un paso 0 en el papel.
    #
    # El artefacto de ML se deserializa la primera vez que alguien puntúa y se queda en el
    # proceso. En una pila recién levantada, ese «primera vez» cae justo en el envío del
    # interesado, que es el momento de la demostración en el que todo el mundo está mirando
    # la pantalla. Aquí se provoca a propósito y se mide aparte, para que el tiempo del paso
    # 3 sea el de verdad y no el del arranque.
    desde = time.perf_counter()
    modulos["cargar_modelo"]()
    arranque_ms = (time.perf_counter() - desde) * 1000
    print("\n0. Calentamiento (no es un paso del guion): el artefacto de ML entra en memoria")
    print(f"   OK  cargado   [{arranque_ms:.0f} ms]")
    print("       Este tiempo se paga una vez por proceso. Si la pila se levanta delante del")
    print("       sínodo, lo paga el envío del interesado: hay que hacer un envío de prueba")
    print("       antes de empezar (paso 0 del guion cronometrado).")

    # ---------------------------------------------------------------- Paso 1
    e.paso("1", "Marketing crea la publicación y el servidor le da su enlace")
    respuesta = cliente.post(
        "/api/v1/campaigns",
        json={
            "name": f"Post · Equipos de TI en 30 días (ensayo {marca})",
            "channel": modulos["CANAL_LINKEDIN"],
            "description": (
                "Montar un equipo de TI completo tarda meses. Nosotros lo hacemos en 30 "
                "días, con perfiles probados y acompañamiento hasta que el equipo produce."
            ),
            "target_audience": "Directores y gerentes de TI de empresas medianas",
            "budget": 3500.0,
            "redes": ["linkedin", "whatsapp"],
        },
        headers=cab_lider,
    )
    e.comprobar(respuesta.status_code == 201, f"crear la publicación dio HTTP {respuesta.status_code}: {respuesta.text[:300]}")
    publicacion = respuesta.json()
    slug = publicacion["public_slug"]
    e.comprobar(len(slug) >= 22, f"el enlace público es corto ({len(slug)} caracteres): debería ser impredecible")
    e.cerrar(f"publicación {publicacion['id']}, enlace .../{slug[:12]}…")

    # ---------------------------------------------------------------- Paso 2
    e.paso("2", "Copia el texto para LinkedIn y para WhatsApp: dos enlaces distintos")
    respuesta = cliente.get(f"/api/v1/campaigns/{publicacion['id']}", headers=cab_lider)
    e.comprobar(respuesta.status_code == 200, f"leer la publicación dio HTTP {respuesta.status_code}")
    redes = {r["clave"]: r for r in respuesta.json()["difusion"] if r["activa"]}
    e.comprobar("linkedin" in redes and "whatsapp" in redes, f"faltan redes activas: {sorted(redes)}")
    for clave, red in redes.items():
        e.comprobar(red["enlace"] in red["texto"], f"el texto de {clave} no lleva su enlace dentro")
        e.comprobar(f"r={clave}" in red["enlace"], f"el enlace de {clave} no va etiquetado con su red")
    e.comprobar(
        redes["linkedin"]["enlace"] != redes["whatsapp"]["enlace"],
        "los dos enlaces son el mismo: sin etiqueta de red no hay atribución que contar",
    )
    e.cerrar(f"{len(redes)} redes, cada una con su enlace etiquetado")

    # El contador del líder, antes de que llegue nadie. El paso 5 comprueba que sube
    # exactamente uno y que vuelve a bajar al repartir la ficha.
    antes_del_envio = cliente.get(
        "/api/v1/publicaciones/nuevos-sin-asesor", headers=cab_lider
    ).json()["total"]

    # ---------------------------------------------------------------- Paso 3
    e.paso("3", "El interesado abre el enlace de WhatsApp y deja sus datos")
    # El límite por IP está puesto para el mundo, no para un ensayo que manda un envío
    # desde la misma máquina. Se restaura al salir de la función que llama a esta.
    pagina = cliente.get(f"/api/v1/interes/{slug}", params={"r": "whatsapp"})
    e.comprobar(pagina.status_code == 200, f"la página pública dio HTTP {pagina.status_code}")
    opciones = pagina.json()["opciones"]
    e.comprobar(opciones.get("necesidades"), "la página no ofrece opciones de «¿Qué necesitas?»")
    # Las listas vienen del servidor: son las mismas que conoce el modelo que puntúa.
    for lista in ("cargos", "sectores", "tamanos"):
        e.comprobar(opciones.get(lista), f"la página no trae la lista de {lista}")

    envio = cliente.post(
        f"/api/v1/interes/{slug}",
        params={"r": "whatsapp"},
        json={
            "nombre": "Lucía Prado",
            "correo": correo,
            "empresa": "Fábrica de Software Norte",
            "cargo": "Head of Engineering",
            "sector": "Software/TI",
            "tamano_de_empresa": "51-200",
            "linkedin": "https://www.linkedin.com/in/lucia-prado-demo",
            "necesidad": "equipo",
            "aviso_de_privacidad": True,
            "sitio_web": "",
        },
    )
    e.comprobar(envio.status_code == 202, f"el envío dio HTTP {envio.status_code}: {envio.text[:300]}")
    e.cerrar("envío aceptado (202), con la red de llegada en la consulta")

    # ---------------------------------------------------------------- Paso 4
    e.paso("4", "El sistema crea la ficha puntuada, atribuida y sin asesor")
    Lead = modulos["Lead"]
    lead = db.query(Lead).filter(Lead.email == correo).first()
    e.comprobar(lead is not None, "no se creó ninguna ficha con ese correo")
    e.comprobar(lead.current_score is not None and lead.current_score > 0, f"la ficha quedó sin puntuar (score={lead.current_score})")
    e.comprobar(lead.campaign_id == publicacion["id"], f"la ficha no quedó atribuida a la publicación (campaign_id={lead.campaign_id})")
    e.comprobar(lead.assigned_rep_id is None, "la ficha llegó ya con asesor: el líder no tendría nada que repartir")
    e.cerrar(f"ficha {lead.id}, score {lead.current_score:.1f} ({lead.score_category.value})")

    # ---------------------------------------------------------------- Paso 5
    e.paso("5", "El líder la ve en el contador «sin asesor» y se la asigna")
    contador = cliente.get("/api/v1/publicaciones/nuevos-sin-asesor", headers=cab_lider)
    e.comprobar(contador.status_code == 200, f"el contador dio HTTP {contador.status_code}")
    ahora = contador.json()["total"]
    # No basta con que el contador diga «uno o más»: tiene que haber subido **exactamente
    # uno** desde antes del envío. Durante dos capítulos el contador sumaba los seis canales
    # mientras el listado solo marcaba los de LinkedIn, así que el líder veía un número y
    # encontraba menos fichas. Un «>= 1» habría pasado igual de verde con ese defecto dentro.
    e.comprobar(
        ahora == antes_del_envio + 1,
        f"el contador de prospectos sin asesor pasó de {antes_del_envio} a {ahora} con una sola ficha nueva",
    )

    asignacion = cliente.put(
        f"/api/v1/leads/{lead.id}", json={"assigned_rep_id": asesor.id}, headers=cab_lider
    )
    e.comprobar(asignacion.status_code == 200, f"asignar dio HTTP {asignacion.status_code}: {asignacion.text[:300]}")

    despues = cliente.get("/api/v1/publicaciones/nuevos-sin-asesor", headers=cab_lider).json()["total"]
    e.comprobar(
        despues == antes_del_envio,
        f"el contador sigue en {despues} después de repartir la ficha: debería haber vuelto a {antes_del_envio}",
    )
    e.cerrar(
        f"contador {antes_del_envio} -> {ahora} -> {despues}, "
        f"ficha asignada a {asesor.full_name}"
    )

    # ---------------------------------------------------------------- Paso 6
    e.paso("6", "El asesor la encuentra en «Hoy», la abre y cierra su tarea")
    pasada = time.perf_counter()
    modulos["ejecutar"](db)          # la pasada diaria del motor de reglas
    e.descontar(time.perf_counter() - pasada)
    bandeja = cliente.get("/api/v1/agenda/hoy", headers=cab_asesor)
    e.comprobar(bandeja.status_code == 200, f"la bandeja dio HTTP {bandeja.status_code}")
    tareas = bandeja.json()["tareas"]
    mia = [t for t in tareas if t["prospecto"]["id"] == lead.id]
    e.comprobar(mia, "la ficha recién asignada no aparece en «Hoy»: el asesor tendría que buscarla")
    tarea = mia[0]
    e.comprobar(tarea["motivo"], "la tarea no dice por qué está ahí")

    ficha = cliente.get(f"/api/v1/leads/{lead.id}", headers=cab_asesor)
    e.comprobar(ficha.status_code == 200, f"la ficha 360 dio HTTP {ficha.status_code}")
    llego_por = ficha.json().get("llego_por") or {}
    solicitudes = llego_por.get("solicitudes") or []
    e.comprobar(solicitudes, "la tarjeta «Llegó por» viene vacía: el asesor no sabe de dónde salió")
    e.comprobar(
        solicitudes[0].get("red", "").lower().startswith("whatsapp"),
        f"la red de llegada se perdió por el camino: dice «{solicitudes[0].get('red')}» y se repartió por WhatsApp",
    )
    e.comprobar(solicitudes[0].get("necesidad"), "la ficha no dice qué pidió")
    e.comprobar(solicitudes[0].get("aviso_aceptado_en"), "la ficha no dice cuándo aceptó el aviso de privacidad")

    cerrada = cliente.post(f"/api/v1/agenda/tareas/{tarea['id']}/hecha", headers=cab_asesor)
    e.comprobar(cerrada.status_code == 200, f"cerrar la tarea dio HTTP {cerrada.status_code}")
    e.cerrar(f"tarea «{tarea['regla_etiqueta']}» vista, ficha leída y tarea cerrada")

    # ---------------------------------------------------------------- Paso 7
    e.paso("7", "El líder compara publicaciones y abre el informe por red")
    comparativa = cliente.get("/api/v1/publicaciones/comparativa", headers=cab_lider)
    e.comprobar(comparativa.status_code == 200, f"la comparativa dio HTTP {comparativa.status_code}")
    filas = comparativa.json()["items"]
    e.comprobar(len(filas) >= 2, f"solo hay {len(filas)} publicación(es): una comparativa de una fila no compara nada")
    nuestra = [f for f in filas if f["publicacion_id"] == publicacion["id"]]
    e.comprobar(nuestra, "la publicación recién creada no sale en la comparativa")
    e.comprobar(nuestra[0]["perfiles_recibidos"] >= 1, "la comparativa no cuenta el perfil que acaba de llegar")

    informe = cliente.get(f"/api/v1/publicaciones/{publicacion['id']}/informe", headers=cab_lider)
    e.comprobar(informe.status_code == 200, f"el informe dio HTTP {informe.status_code}")
    datos = informe.json()
    por_red = {f["red"]: f for f in datos.get("por_red", [])}
    e.comprobar("whatsapp" in por_red, f"el informe no atribuye nada a WhatsApp: {sorted(por_red)}")
    e.comprobar(por_red["whatsapp"]["perfiles"] >= 1, "la fila de WhatsApp dice cero perfiles")
    e.cerrar(f"{len(filas)} publicaciones comparadas, {len(por_red)} red(es) en el informe")

    # ---------------------------------------------------------------- Paso 8
    e.paso("8", "El trato se cierra diciendo por qué, y sale de «Hoy»")
    por_el_selector = cliente.put(f"/api/v1/leads/{lead.id}", json={"status": "WON"}, headers=cab_lider)
    e.comprobar(
        por_el_selector.status_code == 422,
        f"la edición de la ficha aceptó «Ganado» (HTTP {por_el_selector.status_code}): se puede cerrar sin decir por qué",
    )

    antes = lead.current_score
    cierre = cliente.post(
        f"/api/v1/leads/{lead.id}/desenlace",
        json={
            "resultado": "ganado",
            "motivo": "acompanamiento",
            "cerrado_el": datetime.date.today().isoformat(),
            "tramo": "de_100k_a_500k",
        },
        headers=cab_lider,
    )
    e.comprobar(cierre.status_code == 200, f"el cierre dio HTTP {cierre.status_code}: {cierre.text[:300]}")
    registrado = cierre.json()
    e.comprobar(registrado["motivo_etiqueta"], "el desenlace no trae la etiqueta de su motivo")

    db.refresh(lead)
    e.comprobar(
        abs(lead.current_score - antes) < 1e-9,
        f"cerrar movió el score ({antes} -> {lead.current_score}): «¿el score acertaba?» deja de tener respuesta",
    )

    pasada = time.perf_counter()
    modulos["ejecutar"](db)
    e.descontar(time.perf_counter() - pasada)
    bandeja = cliente.get("/api/v1/agenda/hoy", headers=cab_asesor).json()
    e.comprobar(
        not [t for t in bandeja["tareas"] if t["prospecto"]["id"] == lead.id],
        "el prospecto cerrado sigue en la bandeja «Hoy»",
    )
    e.cerrar(f"cerrado como «{registrado['resultado_etiqueta']}» por «{registrado['motivo_etiqueta']}», score intacto")

    # ---------------------------------------------------------------- Paso 9
    e.paso("9", "El líder mira los desenlaces y cuánto falta para reentrenar")
    panel = cliente.get("/api/v1/desenlaces/panel", headers=cab_lider)
    e.comprobar(panel.status_code == 200, f"el panel dio HTTP {panel.status_code}")
    datos = panel.json()
    resumen = datos["resumen"]
    e.comprobar(resumen["cerrados"] >= 1, "el panel no cuenta el cierre que acaba de hacerse")
    e.comprobar(resumen["ganados"] >= 1, "el cierre no cuenta como ganado")
    e.comprobar(datos["por_motivo"], "el panel no desglosa por motivo")
    e.comprobar(datos["acierto_del_score"], "el panel no dice qué score tenían al cerrarse")

    progreso = datos["reentrenamiento"]
    e.comprobar(progreso["minimo_de_casos"] > 0, "el contador del reentrenamiento no dice cuál es el mínimo")
    e.comprobar(
        not progreso["alcanzado"],
        "el contador dice que ya se puede reentrenar con un puñado de cierres",
    )

    # El panel son totales: ni una fila lleva a una persona.
    texto = panel.text
    e.comprobar(correo not in texto, "el correo del prospecto viaja en el panel de desenlaces")
    e.comprobar("Lucía Prado" not in texto and "Lucia Prado" not in texto, "el nombre del prospecto viaja en el panel")

    e.comprobar(
        cliente.get("/api/v1/desenlaces/panel", headers=cab_asesor).status_code == 403,
        "un asesor puede abrir el panel de desenlaces: son totales de toda la casa",
    )
    e.cerrar(
        f"{resumen['cerrados']} cierre(s) en el panel, faltan "
        f"{progreso['minimo_de_casos'] - progreso['utilizables']} casos utilizables para reentrenar"
    )

    return e


# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", help="Ruta al .db de demostración. Se copia; no se toca.")
    argumentos = parser.parse_args()

    origen = _origen(argumentos)
    copia = os.path.join(tempfile.mkdtemp(prefix="ensayo-demo-"), "ensayo.db")
    shutil.copy2(origen, copia)

    print("=" * 78)
    print("ENSAYO DE LA DEMOSTRACIÓN, DE PRINCIPIO A FIN")
    print("=" * 78)
    print(f"Base original : {origen}")
    print(f"Copia         : {copia}")
    print("La original no se toca: el ensayo escribe en la copia.")

    # Antes de importar la aplicación: la configuración lee la base al cargarse.
    os.environ["DATABASE_URL"] = "sqlite:///" + copia.replace("\\", "/")
    os.environ.setdefault("ENVIRONMENT", "development")
    sys.path.insert(0, os.path.join(RAIZ, "backend"))

    from app.adapters.azure_ml_adapter import get_ml_scoring_adapter
    from app.core.database import SessionLocal
    from app.core.publicaciones import CANAL_LINKEDIN
    from app.core.rate_limit import limiter
    from app.core.security import create_access_token
    from app.main import app
    from app.models.entities import Lead, User
    from app.services.motor_de_reglas import ejecutar
    from fastapi.testclient import TestClient

    db = SessionLocal()
    lider = db.query(User).filter(User.email == "lider.ventas@plurione.com").first()
    asesor = db.query(User).filter(User.email == "asesor.comercial@plurione.com").first()
    if lider is None or asesor is None:
        _salir(
            "la base no tiene las cuentas sembradas (lider.ventas@ / asesor.comercial@).\n"
            "   Prepárela antes:  python scripts/preparar_prueba_con_personas.py --force"
        )

    # El límite por IP está puesto para el mundo, no para un guion que manda un envío desde
    # la misma máquina. Se restaura pase lo que pase.
    estaba_activo = limiter.enabled
    limiter.enabled = False
    try:
        cliente = TestClient(app)
        ensayo = ensayar(
            cliente, db, lider, asesor,
            {
                "token": create_access_token,
                "ejecutar": ejecutar,
                "cargar_modelo": get_ml_scoring_adapter,
                "Lead": Lead,
                "CANAL_LINKEDIN": CANAL_LINKEDIN,
            },
        )
    finally:
        limiter.enabled = estaba_activo
        db.close()

    ensayo.resumen()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
