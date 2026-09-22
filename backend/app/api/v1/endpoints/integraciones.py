"""
Entrada de las integraciones: `POST /api/v1/integraciones/{nombre}/eventos`.

Una ruta para todas y un conector por integración (`app.services.integraciones`). El orden
de las comprobaciones es deliberado:

1. **¿Existe y está activa?** Si no, 404, igual en los dos casos: quien no tiene por qué
   saber qué integraciones hay conectadas no lo averigua probando nombres.
2. **Límite** de esa integración, antes de leer el cuerpo: una firma filtrada no permite
   inundar la base, y la cuenta de una no consume la de otra.
3. **Firma** con el secreto de esa integración (HMAC sobre `<marca de tiempo>.<cuerpo>`).
4. **Traducción y validación de todos los eventos** antes de escribir ninguno: una entrega
   con un evento inválido se rechaza entera con su motivo (422).
5. **Registro** de cada evento por `registrar_evento`. La deduplicación es la del registro,
   permanente por `(fuente, identificador externo)`: una entrega repetida no vuelve a entrar
   aunque llegue fuera de la ventana de la marca de tiempo.
"""
import json
import logging
from collections import Counter
from typing import Any, Dict

from app.core.audit import ACCION_INTEGRACION_ENTREGA, ENTIDAD_INTEGRACION
from app.core.audit import registrar_evento as anotar_en_bitacora
from app.core.database import get_db
from app.core.proxy import ip_del_cliente
from app.core.security import INTEGRACION_NO_DISPONIBLE, verificar_firma_de_entrega
from app.services.integraciones import INTEGRACIONES, aplicar_limite
from app.services.registro_de_actividad import (
    EventoInvalido,
    ResultadoDelRegistro,
    registrar_evento,
    validar_evento,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


def _resumen(resultado: ResultadoDelRegistro) -> Dict[str, Any]:
    """Qué pasó con el evento. Sin score ni datos de la persona: el emisor no los necesita."""
    return {
        "estado": resultado.estado,
        "prospecto_id": resultado.lead.id if resultado.lead is not None else None,
        "actividad_id": resultado.actividad.id if resultado.actividad is not None else None,
        "evento_sin_asociar_id": resultado.sin_asociar.id if resultado.sin_asociar is not None else None,
        "prospecto_creado": resultado.prospecto_creado,
    }


@router.post("/{nombre}/eventos", status_code=status.HTTP_200_OK)
async def recibir_eventos_de_integracion(
    nombre: str,
    request: Request,
    db: Session = Depends(get_db),
):
    integracion = INTEGRACIONES.get(nombre)
    if integracion is None or not integracion.activa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=INTEGRACION_NO_DISPONIBLE)

    aplicar_limite(integracion, request)
    cuerpo = await verificar_firma_de_entrega(request, integracion.secreto, integracion.nombre)

    try:
        carga = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El cuerpo no es JSON válido."
        ) from exc
    if not isinstance(carga, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El cuerpo tiene que ser un objeto JSON."
        )

    try:
        eventos = integracion.adaptar(carga)
        for evento in eventos:
            validar_evento(evento)
    except EventoInvalido as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.como_detalle()
        ) from exc

    resumenes = []
    for evento in eventos:
        try:
            resultado = await registrar_evento(db, evento)
        except EventoInvalido as exc:
            # Lo que solo se sabe mirando la base: por ejemplo, que no hay ficha y el evento
            # no trae el correo con el que crearla. Los eventos anteriores de la misma entrega
            # ya quedaron registrados; su reintento los encontrará como duplicados.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.como_detalle()
            ) from exc
        resumenes.append(_resumen(resultado))

    anotar_en_bitacora(
        db,
        accion=ACCION_INTEGRACION_ENTREGA,
        entidad=ENTIDAD_INTEGRACION,
        entidad_id=integracion.nombre,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
        metadatos={
            "eventos": len(resumenes),
            "estados": dict(Counter(resumen["estado"] for resumen in resumenes)),
        },
    )
    logger.info(
        "Entrega de '%s': %s evento(s), %s.",
        integracion.nombre, len(resumenes), dict(Counter(r["estado"] for r in resumenes)),
    )
    return {"integracion": integracion.nombre, "eventos": resumenes}
