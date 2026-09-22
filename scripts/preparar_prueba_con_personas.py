"""
Deja la pila lista para sentar a cuatro personas delante (fase 4 del guion de la demo).

    python scripts/preparar_prueba_con_personas.py --force

Qué hace, en este orden:

1. **Copia la base** si es SQLite, antes de tocarla. Lo que se va a hacer es un borrado, y
   una copia con fecha cuesta un segundo.
2. **Siembra los datos de demostración** con `backend/scripts/seed_data.py`, que es el que
   ya existía: cuentas, campañas, prospectos e historial. No se duplica aquí su lógica —ni
   sus guardas: sigue negándose a correr contra un entorno endurecido.
3. **Crea una publicación de ejemplo con perfiles ya recibidos**. Sin ella, el líder no
   tiene nada que comparar: la publicación que cree marketing durante la prueba será la
   primera, y una comparativa de una sola fila no compara nada.

Los perfiles de ejemplo entran **por la página pública**, con una petición de verdad a
`/api/v1/interes/{slug}`. No se insertan a mano: así la ficha, su puntuación, su
atribución y su tarjeta «Llegó por» son exactamente las que verán los participantes.

Lo que NO hace: inventar contraseñas. Las cuentas quedan con la que decida `seed_data.py`
—la de desarrollo, o la de las variables `SEED_*_PASSWORD` si están definidas—, y el
resumen final dice cuál usar sin escribirla en ningún fichero del proyecto.
"""
import argparse
import datetime
import importlib.util
import os
import shutil
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RAIZ, "backend"))

from app.core.config import HARDENED_ENVIRONMENTS, settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.publicaciones import CANAL_LINKEDIN, enlace_publico  # noqa: E402
from app.models.entities import Campaign, Lead  # noqa: E402

# La publicación que ya trae perfiles cuando empieza la prueba. Marketing creará otra
# distinta delante de todos; esta existe para que haya **dos** que comparar.
PUBLICACION_DE_EJEMPLO = {
    "name": "Post · Equipos de TI en 30 días (agosto)",
    "channel": CANAL_LINKEDIN,
    "description": (
        "Montar un equipo de TI completo tarda meses. Nosotros lo hacemos en 30 días, con "
        "perfiles probados y acompañamiento hasta que el equipo produce.\n\n"
        "Si te interesa, cuéntanos qué necesitas y te escribimos."
    ),
    "target_audience": "Directores y gerentes de TI de empresas medianas",
    "budget": 3500.0,
}

# Tres respuestas al post anterior. Nombres y correos claramente ficticios: esto se enseña
# en una sala, y un correo que parezca real acaba recibiendo un mensaje de verdad.
PERFILES_DE_EJEMPLO = [
    {
        "nombre": "Renata Quintero",
        "correo": "renata.quintero@ejemplo-demo.mx", "telefono": "5511223344",
        "empresa": "Servicios Digitales del Bajío", "cargo": "Director de Tecnología",
        "sector": "Software/TI", "tamano_de_empresa": "51-200",
        "linkedin": "https://www.linkedin.com/in/renata-quintero-demo",
        "necesidad": "equipo", "aviso_de_privacidad": True, "sitio_web": "",
    },
    {
        "nombre": "Tomás Iriarte",
        "correo": "tomas.iriarte@ejemplo-demo.mx", "telefono": "5522334455",
        "empresa": "Banca Digital Peninsular", "cargo": "CIO",
        "sector": "Banking", "tamano_de_empresa": "1000+",
        "linkedin": "https://www.linkedin.com/in/tomas-iriarte-demo",
        "necesidad": "demo", "aviso_de_privacidad": True, "sitio_web": "",
    },
    {
        "nombre": "Ceci Ayala",
        # Solo lo obligatorio: ni teléfono ni perfil, como quien no despliega «Añadir más datos».
        "correo": "ceci.ayala@ejemplo-demo.mx",
        "empresa": "Taller de Software Ayala", "cargo": "Consultor Independiente",
        "sector": "Consulting", "tamano_de_empresa": "1-10",
        "necesidad": "explorando", "aviso_de_privacidad": True, "sitio_web": "",
    },
]


# Visitas que miraron la página y no dejaron sus datos.
VISITAS_SIN_ENVIO = 9


def _cargar_seed():
    """`backend/scripts/` no es un paquete; se carga por ruta, como hace su propia suite."""
    ruta = os.path.join(RAIZ, "backend", "scripts", "seed_data.py")
    spec = importlib.util.spec_from_file_location("seed_data_para_la_prueba", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _ruta_de_sqlite() -> str | None:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        return None
    ruta = url.split("///", 1)[-1]
    return ruta if os.path.isfile(ruta) else None


def copiar_la_base() -> str | None:
    """Copia la base antes de vaciarla. Solo SQLite: en PostgreSQL no es cosa del script."""
    origen = _ruta_de_sqlite()
    if origen is None:
        return None
    marca = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = f"{origen}.antes-de-la-prueba-{marca}"
    shutil.copy2(origen, destino)
    return destino


def crear_publicacion_de_ejemplo(db) -> Campaign:
    publicacion = Campaign(**PUBLICACION_DE_EJEMPLO)
    db.add(publicacion)
    db.commit()
    db.refresh(publicacion)
    return publicacion


def enviar_perfiles(publicacion: Campaign) -> int:
    """
    Manda los perfiles por la ruta pública de verdad.

    Se importa aquí y no arriba porque levantar el cliente carga el modelo de puntuación,
    y quien solo venga a leer `--help` no tiene por qué esperarlo.
    """
    from app.core.rate_limit import limiter
    from app.main import app
    from fastapi.testclient import TestClient

    # La preparación manda tres envíos seguidos desde la misma máquina; el límite por IP
    # está puesto para el mundo, no para el guion. Se restaura al terminar.
    estaba_activo = limiter.enabled
    limiter.enabled = False
    try:
        cliente = TestClient(app)
        enviados = 0
        # Cada perfil abre la página antes de enviar, como una persona: así la publicación de
        # ejemplo tiene visitas contadas y su tasa de envío (capítulo 26) sale de verdad.
        # Otras cuantas visitas no envían nada, que es lo normal.
        for _ in range(VISITAS_SIN_ENVIO):
            cliente.get(f"/api/v1/interes/{publicacion.public_slug}")
        for perfil in PERFILES_DE_EJEMPLO:
            cliente.get(f"/api/v1/interes/{publicacion.public_slug}")
            respuesta = cliente.post(f"/api/v1/interes/{publicacion.public_slug}", json=perfil)
            if respuesta.status_code != 202:
                print(f"   !! {perfil['correo']}: HTTP {respuesta.status_code} {respuesta.text[:200]}")
                continue
            enviados += 1
        return enviados
    finally:
        limiter.enabled = estaba_activo


CUENTAS_DE_LA_PRUEBA = [
    ("lider.ventas@plurione.com", "marketing y líder", "SEED_SALES_LEAD_PASSWORD"),
    ("asesor.comercial@plurione.com", "asesor", "SEED_EXECUTIVE_PASSWORD"),
    ("admin.ti@plurione.com", "administración", "SEED_ADMIN_PASSWORD"),
]


def direccion_en_la_red() -> str | None:
    """
    La dirección de esta máquina en su red, para que el teléfono llegue al panel.

    Se abre un socket UDP hacia una dirección exterior **sin enviar nada**: es la forma
    portable de preguntarle al sistema qué interfaz usaría, y no depende de que el nombre
    de la máquina resuelva (`gethostbyname` devuelve 127.0.0.1 en la mitad de los equipos).
    """
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1: no existe, no se manda un paquete
            return s.getsockname()[0]
    except OSError:
        return None


def avisar_del_telefono() -> None:
    """
    El paso «el interesado envía su perfil desde el móvil» no sale solo.

    El servidor de desarrollo escucha en `localhost`: desde un teléfono no se abre nada. Y
    aunque se abra, el enlace que copia marketing lleva dentro `PUBLICACIONES_URL_BASE`, así
    que si dice «localhost» el teléfono intentará abrirse a sí mismo. Las dos cosas hay que
    decidirlas antes de levantar la pila, no cuando hay cuatro personas esperando.
    """
    base = settings.PUBLICACIONES_URL_BASE
    if "localhost" not in base and "127.0.0.1" not in base:
        return
    ip = direccion_en_la_red()
    print("\nSi el «interesado» va a usar un teléfono de verdad (no el navegador en modo")
    print("teléfono), hacen falta dos cosas antes de levantar la pila:")
    print("   1) servir el panel en la red:  npm run dev:lan --prefix frontend")
    if ip:
        print("   2) que el enlace lleve esta dirección y no «localhost»:")
        print(f"      PUBLICACIONES_URL_BASE=http://{ip}:3000/interes")
        print("      (y vuelva a lanzar esta preparación, para que la publicación de")
        print("       ejemplo se cree con el enlace bueno)")
    else:
        print("   2) definir PUBLICACIONES_URL_BASE con la dirección de esta máquina en la red")
    print("   El panel queda accesible para quien esté en esa red: hágalo solo en una de")
    print("   confianza y apague el servidor al terminar.")


def resumen(publicacion: Campaign, db, seed) -> None:
    prospectos = db.query(Lead).count()
    sin_asesor = (
        db.query(Lead)
        .filter(Lead.source == CANAL_LINKEDIN, Lead.assigned_rep_id.is_(None))
        .count()
    )
    print("\n" + "=" * 78)
    print("PILA LISTA PARA LA PRUEBA CON PERSONAS")
    print("=" * 78)
    print("Panel:            http://localhost:3000")
    print("API:              http://localhost:8000/docs")
    print(f"Publicación de ejemplo: «{publicacion.name}»")
    print(f"   enlace:        {enlace_publico(publicacion.public_slug)}")
    print(f"Prospectos en la base: {prospectos} ({sin_asesor} de LinkedIn sin asesor)")
    print("\nCuentas para repartir entre los participantes:")
    for correo, papel, variable in CUENTAS_DE_LA_PRUEBA:
        # La contraseña la resuelve `seed_data.py`, que es quien la fijó: aquí no se
        # inventa ninguna ni se guarda en ningún fichero del proyecto. Se imprime porque
        # quien conduce la prueba tiene que dictarla, y esto es una base local de ejemplo.
        clave, origen = seed.resolve_seed_password(variable)
        print(f"   {correo:<30} {papel:<26} {clave}   [{origen}]")
    if not os.environ.get("SECRET_KEY"):
        print(
            "\nAviso: sin SECRET_KEY definida, el backend firma con una clave nueva en cada\n"
            "arranque. Si lo reinicia en mitad de la prueba, los cuatro tendrán que volver a\n"
            "entrar. Defina SECRET_KEY (32 caracteres o más) antes de levantar la pila si no\n"
            "quiere que eso pase."
        )

    avisar_del_telefono()
    print("\nGuion y hoja de observación: docs/Prueba_Con_Personas.md")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--force", action="store_true",
        help="Confirma que se puede vaciar y regenerar la base de destino.",
    )
    argumentos = parser.parse_args()

    if settings.ENVIRONMENT.strip().lower() in HARDENED_ENVIRONMENTS:
        print(f"ENVIRONMENT='{settings.ENVIRONMENT}': esta preparación borra datos y no corre aquí.")
        return 2

    seed = _cargar_seed()
    print(f"Destino: {seed.destino_de_la_base()}")
    if not argumentos.force:
        print(
            "Esto VACÍA las tablas de negocio y las regenera. Repita con --force cuando esté "
            "seguro de que el destino es la base de la demostración."
        )
        return 2

    copia = copiar_la_base()
    print(f"Copia previa: {copia}" if copia else "Sin copia previa (la base no es un fichero SQLite).")

    seed.seed_database(forzar=True)

    db = SessionLocal()
    try:
        publicacion = crear_publicacion_de_ejemplo(db)
        print(f"\n5. Publicación de ejemplo «{publicacion.name}» creada.")
        enviados = enviar_perfiles(publicacion)
        print(f"   -> {enviados} perfiles recibidos por su enlace público.")
        db.expire_all()
        resumen(publicacion, db, seed)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
