from app.api.v1.endpoints import (
    agenda,
    analytics,
    audit,
    auth,
    campaigns,
    crm,
    desenlaces,
    integraciones,
    interes,
    leads,
    publicaciones,
    scoring,
    sin_asociar,
    users,
)
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
api_router.include_router(leads.router, prefix="/leads", tags=["Leads"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["Scoring"])
api_router.include_router(crm.router, prefix="/crm", tags=["CRM Webhooks"])
# Entregas firmadas de Calendly, WhatsApp, LinkedIn Lead Gen y el formulario web. Cada una
# con su secreto, su interruptor y su límite (Fase 15).
api_router.include_router(integraciones.router, prefix="/integraciones", tags=["Integraciones"])
api_router.include_router(sin_asociar.router, prefix="/eventos-sin-asociar", tags=["Bandeja «Sin asociar»"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & KPIs"])
api_router.include_router(audit.router, prefix="/audit", tags=["Auditoría"])
api_router.include_router(users.router, prefix="/users", tags=["Usuarios"])
# `/sales-reps` es una vista sobre `users`: un asesor es un usuario con `is_sales_rep`.
# Se mantiene como ruta propia porque es la pregunta que hace el frontend —"¿quién
# atiende cartera y cuánta lleva?"— y responderla desde `/users` obligaría a filtrar y
# a contar prospectos en el cliente, que es de donde venía el N+1.
api_router.include_router(users.asesores_router, prefix="/sales-reps", tags=["Asesores"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campañas"])
# Los informes de las publicaciones. El alta y la edición siguen en `/campaigns`: una
# publicación es una campaña con canal LinkedIn, no una entidad nueva.
api_router.include_router(publicaciones.router, prefix="/publicaciones", tags=["Publicaciones"])
# Sin sesión: es la página pública a la que llevan los enlaces de las publicaciones.
api_router.include_router(interes.router, prefix="/interes", tags=["Página de interés"])
# Lo que hay que hacer hoy (capítulo 28). Solo lee y cierra: quien decide qué hay que hacer
# es el motor de reglas, en la pasada diaria, sin nadie delante.
api_router.include_router(agenda.router, prefix="/agenda", tags=["Agenda del día"])
# Lo que dicen los cierres (capítulo 30). Solo lee: las opciones del formulario y el panel
# del líder. Cerrar un prospecto vive en `/leads/{id}/desenlace`, con el resto de lo que se
# le hace a un prospecto, porque necesita el alcance de cartera.
api_router.include_router(desenlaces.router, prefix="/desenlaces", tags=["Desenlaces"])
