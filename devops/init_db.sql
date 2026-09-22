-- =============================================================================
-- SISTEMA INTELIGENTE DE LEAD SCORING - PLURIONE S.A. DE C.V.
-- SCRIPT DE INICIALIZACIÓN DE BASE DE DATOS POSTGRESQL
-- =============================================================================

-- Extensiones útiles para UUIDs y búsqueda de texto
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Esquema principal si se requiere aislamiento lógico
CREATE SCHEMA IF NOT EXISTS lead_scoring;

-- Comentario informativo
COMMENT ON DATABASE lead_scoring_db IS 'Base de datos del Sistema Inteligente de Lead Scoring para PluriOne S.A. de C.V.';
