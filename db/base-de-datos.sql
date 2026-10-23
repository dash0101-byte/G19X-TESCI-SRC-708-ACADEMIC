--
-- Sistema Inteligente de Lead Scoring (PluriOne) - volcado de la base de datos
--
-- Alumno: Rosales Castillo Sebastian - No. de control: 223107211
-- Codigo del proyecto academico: G19X-TESCI-SRC-708
-- Institucion: Tecnologico de Estudios Superiores de Cuautitlan Izcalli (TESCI)
--
-- QUE TRAE: el esquema completo -en la revision de Alembic que lleva `alembic_version`- y
-- los datos de demostracion. Todos los prospectos, empresas, correos y actividades son
-- SINTETICOS, generados por `backend/scripts/seed_data.py`. No hay ningun dato real de
-- personas ni de clientes de PluriOne.
--
-- COMO SE IMPORTA en una base vacia:
--
--   psql -U postgres -d lead_scoring_db -f db/base-de-datos.sql
--
-- O contra la pila ya levantada, sin publicar ningun puerto:
--
--   python devops/pila.py exec -T postgres psql -U plurione -d lead_scoring_db \
--     < db/base-de-datos.sql
--
-- CUENTAS QUE TRAE, todas con la contrasena de demostracion `PluriOne2026!`:
--
--   admin.ti@plurione.com          System_Admin          todo
--   lider.ventas@plurione.com      Sales_Lead            la cartera completa
--   asesor.comercial@plurione.com  Commercial_Executive  solo sus propios prospectos
--
--   Y cuatro asesores mas de la demostracion: carlos.morales@, ana.ruiz@,
--   valeria.mendoza@ y diego.herrera@, todos @plurione.com.
--
-- `PluriOne2026!` es la contrasena de desarrollo de `seed_data.py`, esta en el repositorio
-- desde el principio y es la unica excepcion documentada a «ningun secreto en el arbol»:
-- contra un entorno endurecido el sembrado genera una aleatoria. Aqui viaja su resumen
-- bcrypt, no la contrasena.
--
-- Las columnas del segundo factor van VACIAS a proposito: ninguna cuenta lo tiene activo y
-- el secreto se deriva de SECRET_KEY, que no vive en el repositorio.
--
--
-- PostgreSQL database dump
--

\restrict 6dROPHzveH8gbRfl9FJxJLmgmSBdYIzjygeNlGc3oEuIR7T1d5blub2l4i8vMI8

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.webhook_deliveries DROP CONSTRAINT IF EXISTS webhook_deliveries_lead_id_fkey;
ALTER TABLE IF EXISTS ONLY public.score_history_monthly DROP CONSTRAINT IF EXISTS score_history_monthly_lead_id_fkey;
ALTER TABLE IF EXISTS ONLY public.score_histories DROP CONSTRAINT IF EXISTS score_histories_lead_id_fkey;
ALTER TABLE IF EXISTS ONLY public.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.leads DROP CONSTRAINT IF EXISTS leads_campaign_id_fkey;
ALTER TABLE IF EXISTS ONLY public.lead_activities DROP CONSTRAINT IF EXISTS lead_activities_lead_id_fkey;
ALTER TABLE IF EXISTS ONLY public.visitas_de_publicacion DROP CONSTRAINT IF EXISTS fk_visitas_de_publicacion_campaign_id_campaigns;
ALTER TABLE IF EXISTS ONLY public.tareas DROP CONSTRAINT IF EXISTS fk_tareas_lead_id_leads;
ALTER TABLE IF EXISTS ONLY public.tareas DROP CONSTRAINT IF EXISTS fk_tareas_cerrada_por_id_users;
ALTER TABLE IF EXISTS ONLY public.tareas DROP CONSTRAINT IF EXISTS fk_tareas_asesor_id_users;
ALTER TABLE IF EXISTS ONLY public.leads DROP CONSTRAINT IF EXISTS fk_leads_assigned_rep_id_users;
ALTER TABLE IF EXISTS ONLY public.desenlaces DROP CONSTRAINT IF EXISTS fk_desenlaces_score_history_id_score_histories;
ALTER TABLE IF EXISTS ONLY public.desenlaces DROP CONSTRAINT IF EXISTS fk_desenlaces_registrado_por_id_users;
ALTER TABLE IF EXISTS ONLY public.desenlaces DROP CONSTRAINT IF EXISTS fk_desenlaces_lead_id_leads;
ALTER TABLE IF EXISTS ONLY public.campaigns DROP CONSTRAINT IF EXISTS fk_campaigns_responsable_id_users;
ALTER TABLE IF EXISTS ONLY public.avisos DROP CONSTRAINT IF EXISTS fk_avisos_usuario_id_users;
ALTER TABLE IF EXISTS ONLY public.avisos DROP CONSTRAINT IF EXISTS fk_avisos_lead_id_leads;
ALTER TABLE IF EXISTS ONLY public.crm_integration_logs DROP CONSTRAINT IF EXISTS crm_integration_logs_lead_id_fkey;
DROP INDEX IF EXISTS public.uq_unmatched_events_source_external_event;
DROP INDEX IF EXISTS public.uq_tareas_regla_lead_clave;
DROP INDEX IF EXISTS public.uq_scoring_jobs_lease_key;
DROP INDEX IF EXISTS public.uq_score_history_monthly_lead_month;
DROP INDEX IF EXISTS public.uq_lead_activities_source_external_event;
DROP INDEX IF EXISTS public.uq_desenlaces_lead;
DROP INDEX IF EXISTS public.uq_campaigns_public_slug;
DROP INDEX IF EXISTS public.uq_avisos_usuario_regla_lead_clave;
DROP INDEX IF EXISTS public.ix_webhook_deliveries_signature;
DROP INDEX IF EXISTS public.ix_webhook_deliveries_idempotency_key;
DROP INDEX IF EXISTS public.ix_webhook_deliveries_id;
DROP INDEX IF EXISTS public.ix_webhook_deliveries_external_lead_id;
DROP INDEX IF EXISTS public.ix_webhook_deliveries_expires_at;
DROP INDEX IF EXISTS public.ix_users_is_sales_rep;
DROP INDEX IF EXISTS public.ix_users_id;
DROP INDEX IF EXISTS public.ix_users_email;
DROP INDEX IF EXISTS public.ix_unmatched_events_received_at;
DROP INDEX IF EXISTS public.ix_unmatched_events_id;
DROP INDEX IF EXISTS public.ix_unmatched_events_contact_phone;
DROP INDEX IF EXISTS public.ix_unmatched_events_contact_email;
DROP INDEX IF EXISTS public.ix_tareas_vence_el;
DROP INDEX IF EXISTS public.ix_tareas_regla;
DROP INDEX IF EXISTS public.ix_tareas_lead_id;
DROP INDEX IF EXISTS public.ix_tareas_id;
DROP INDEX IF EXISTS public.ix_tareas_estado;
DROP INDEX IF EXISTS public.ix_tareas_asesor_id;
DROP INDEX IF EXISTS public.ix_scoring_jobs_status;
DROP INDEX IF EXISTS public.ix_scoring_jobs_id;
DROP INDEX IF EXISTS public.ix_scoring_jobs_created_at;
DROP INDEX IF EXISTS public.ix_score_history_monthly_id;
DROP INDEX IF EXISTS public.ix_score_histories_lead_id;
DROP INDEX IF EXISTS public.ix_score_histories_id;
DROP INDEX IF EXISTS public.ix_score_histories_calculated_at;
DROP INDEX IF EXISTS public.ix_refresh_tokens_user_id;
DROP INDEX IF EXISTS public.ix_refresh_tokens_revoked_at;
DROP INDEX IF EXISTS public.ix_refresh_tokens_jti;
DROP INDEX IF EXISTS public.ix_refresh_tokens_id;
DROP INDEX IF EXISTS public.ix_refresh_tokens_family_id;
DROP INDEX IF EXISTS public.ix_refresh_tokens_expires_at;
DROP INDEX IF EXISTS public.ix_leads_status;
DROP INDEX IF EXISTS public.ix_leads_score_category;
DROP INDEX IF EXISTS public.ix_leads_qualification_status;
DROP INDEX IF EXISTS public.ix_leads_industry;
DROP INDEX IF EXISTS public.ix_leads_id;
DROP INDEX IF EXISTS public.ix_leads_email;
DROP INDEX IF EXISTS public.ix_leads_dormido_desde;
DROP INDEX IF EXISTS public.ix_leads_current_score;
DROP INDEX IF EXISTS public.ix_leads_company;
DROP INDEX IF EXISTS public.ix_leads_campaign_id;
DROP INDEX IF EXISTS public.ix_leads_assigned_rep_id;
DROP INDEX IF EXISTS public.ix_lead_activities_occurred_at;
DROP INDEX IF EXISTS public.ix_lead_activities_lead_id;
DROP INDEX IF EXISTS public.ix_lead_activities_id;
DROP INDEX IF EXISTS public.ix_lead_activities_activity_type;
DROP INDEX IF EXISTS public.ix_desenlaces_resultado;
DROP INDEX IF EXISTS public.ix_desenlaces_motivo;
DROP INDEX IF EXISTS public.ix_desenlaces_id;
DROP INDEX IF EXISTS public.ix_desenlaces_cerrado_el;
DROP INDEX IF EXISTS public.ix_desenlaces_categoria_al_cierre;
DROP INDEX IF EXISTS public.ix_crm_integration_logs_synced_at;
DROP INDEX IF EXISTS public.ix_crm_integration_logs_lead_id;
DROP INDEX IF EXISTS public.ix_crm_integration_logs_id;
DROP INDEX IF EXISTS public.ix_crm_integration_logs_external_crm_id;
DROP INDEX IF EXISTS public.ix_campaigns_name;
DROP INDEX IF EXISTS public.ix_campaigns_id;
DROP INDEX IF EXISTS public.ix_avisos_usuario_id;
DROP INDEX IF EXISTS public.ix_avisos_regla;
DROP INDEX IF EXISTS public.ix_avisos_lead_id;
DROP INDEX IF EXISTS public.ix_avisos_id;
DROP INDEX IF EXISTS public.ix_avisos_creado_en;
DROP INDEX IF EXISTS public.ix_audit_log_outcome;
DROP INDEX IF EXISTS public.ix_audit_log_occurred_at;
DROP INDEX IF EXISTS public.ix_audit_log_id;
DROP INDEX IF EXISTS public.ix_audit_log_entity_id;
DROP INDEX IF EXISTS public.ix_audit_log_entity;
DROP INDEX IF EXISTS public.ix_audit_log_actor_id;
DROP INDEX IF EXISTS public.ix_audit_log_actor_email;
DROP INDEX IF EXISTS public.ix_audit_log_action;
DROP INDEX IF EXISTS public.idx_tareas_asesor_estado_vence;
DROP INDEX IF EXISTS public.idx_score_history_lead_time;
DROP INDEX IF EXISTS public.idx_refresh_family_user;
DROP INDEX IF EXISTS public.idx_leads_score_status;
DROP INDEX IF EXISTS public.idx_leads_rep_score;
DROP INDEX IF EXISTS public.idx_leads_created_score;
DROP INDEX IF EXISTS public.idx_desenlaces_cerrado_resultado;
DROP INDEX IF EXISTS public.idx_avisos_usuario_leido_creado;
DROP INDEX IF EXISTS public.idx_audit_entity_time;
DROP INDEX IF EXISTS public.idx_audit_actor_time;
DROP INDEX IF EXISTS public.idx_activity_lead_time;
ALTER TABLE IF EXISTS ONLY public.webhook_deliveries DROP CONSTRAINT IF EXISTS webhook_deliveries_pkey;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.unmatched_events DROP CONSTRAINT IF EXISTS unmatched_events_pkey;
ALTER TABLE IF EXISTS ONLY public.scoring_jobs DROP CONSTRAINT IF EXISTS scoring_jobs_pkey;
ALTER TABLE IF EXISTS ONLY public.score_history_monthly DROP CONSTRAINT IF EXISTS score_history_monthly_pkey;
ALTER TABLE IF EXISTS ONLY public.score_histories DROP CONSTRAINT IF EXISTS score_histories_pkey;
ALTER TABLE IF EXISTS ONLY public.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_pkey;
ALTER TABLE IF EXISTS ONLY public.visitas_de_publicacion DROP CONSTRAINT IF EXISTS pk_visitas_de_publicacion;
ALTER TABLE IF EXISTS ONLY public.tareas DROP CONSTRAINT IF EXISTS pk_tareas;
ALTER TABLE IF EXISTS ONLY public.desenlaces DROP CONSTRAINT IF EXISTS pk_desenlaces;
ALTER TABLE IF EXISTS ONLY public.avisos DROP CONSTRAINT IF EXISTS pk_avisos;
ALTER TABLE IF EXISTS ONLY public.leads DROP CONSTRAINT IF EXISTS leads_pkey;
ALTER TABLE IF EXISTS ONLY public.lead_activities DROP CONSTRAINT IF EXISTS lead_activities_pkey;
ALTER TABLE IF EXISTS ONLY public.crm_integration_logs DROP CONSTRAINT IF EXISTS crm_integration_logs_pkey;
ALTER TABLE IF EXISTS ONLY public.campaigns DROP CONSTRAINT IF EXISTS campaigns_pkey;
ALTER TABLE IF EXISTS ONLY public.audit_log DROP CONSTRAINT IF EXISTS audit_log_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS public.webhook_deliveries ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.users ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.unmatched_events ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.tareas ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.score_history_monthly ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.score_histories ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.refresh_tokens ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.leads ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.lead_activities ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.desenlaces ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.crm_integration_logs ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.campaigns ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.avisos ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.audit_log ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.webhook_deliveries_id_seq;
DROP TABLE IF EXISTS public.webhook_deliveries;
DROP TABLE IF EXISTS public.visitas_de_publicacion;
DROP SEQUENCE IF EXISTS public.users_id_seq;
DROP TABLE IF EXISTS public.users;
DROP SEQUENCE IF EXISTS public.unmatched_events_id_seq;
DROP TABLE IF EXISTS public.unmatched_events;
DROP SEQUENCE IF EXISTS public.tareas_id_seq;
DROP TABLE IF EXISTS public.tareas;
DROP TABLE IF EXISTS public.scoring_jobs;
DROP SEQUENCE IF EXISTS public.score_history_monthly_id_seq;
DROP TABLE IF EXISTS public.score_history_monthly;
DROP SEQUENCE IF EXISTS public.score_histories_id_seq;
DROP TABLE IF EXISTS public.score_histories;
DROP SEQUENCE IF EXISTS public.refresh_tokens_id_seq;
DROP TABLE IF EXISTS public.refresh_tokens;
DROP SEQUENCE IF EXISTS public.leads_id_seq;
DROP TABLE IF EXISTS public.leads;
DROP SEQUENCE IF EXISTS public.lead_activities_id_seq;
DROP TABLE IF EXISTS public.lead_activities;
DROP SEQUENCE IF EXISTS public.desenlaces_id_seq;
DROP TABLE IF EXISTS public.desenlaces;
DROP SEQUENCE IF EXISTS public.crm_integration_logs_id_seq;
DROP TABLE IF EXISTS public.crm_integration_logs;
DROP SEQUENCE IF EXISTS public.campaigns_id_seq;
DROP TABLE IF EXISTS public.campaigns;
DROP SEQUENCE IF EXISTS public.avisos_id_seq;
DROP TABLE IF EXISTS public.avisos;
DROP SEQUENCE IF EXISTS public.audit_log_id_seq;
DROP TABLE IF EXISTS public.audit_log;
DROP TABLE IF EXISTS public.alembic_version;
DROP TYPE IF EXISTS public.scorecategory;
DROP TYPE IF EXISTS public.qualificationstatus;
DROP TYPE IF EXISTS public.leadstatus;
DROP TYPE IF EXISTS public.activitytype;
DROP EXTENSION IF EXISTS "uuid-ossp";
DROP EXTENSION IF EXISTS pg_trgm;
DROP SCHEMA IF EXISTS lead_scoring;
--
-- Name: lead_scoring; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA lead_scoring;


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: activitytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.activitytype AS ENUM (
    'PAGE_VIEW',
    'FORM_SUBMIT',
    'EMAIL_OPEN',
    'EMAIL_CLICK',
    'DEMO_REQUEST',
    'WEBINAR_ATTEND',
    'CONTENT_DOWNLOAD',
    'CHAT_INTERACTION',
    'PHONE_CALL',
    'MEETING_SCHEDULED',
    'WHATSAPP_MESSAGE',
    'LINKEDIN_MESSAGE',
    'PROPOSAL_SENT',
    'CUSTOM'
);


--
-- Name: leadstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.leadstatus AS ENUM (
    'NEW',
    'CONTACTED',
    'ENGAGED',
    'QUALIFIED',
    'MEETING_SCHEDULED',
    'PROPOSAL_SENT',
    'NEGOTIATION',
    'UNQUALIFIED',
    'WON',
    'LOST'
);


--
-- Name: qualificationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.qualificationstatus AS ENUM (
    'INCOMING',
    'MQL',
    'SAL',
    'SQL',
    'DISQUALIFIED'
);


--
-- Name: scorecategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.scorecategory AS ENUM (
    'HOT',
    'WARM',
    'COLD'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    actor_id integer,
    actor_email character varying(150),
    actor_role character varying(50),
    action character varying(60) NOT NULL,
    entity character varying(60) NOT NULL,
    entity_id character varying(64),
    outcome character varying(20) NOT NULL,
    ip_address character varying(64),
    user_agent character varying(255),
    event_metadata json,
    occurred_at timestamp with time zone NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: avisos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.avisos (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    lead_id integer NOT NULL,
    regla character varying(40) NOT NULL,
    clave character varying(80) NOT NULL,
    texto character varying(300) NOT NULL,
    datos json,
    creado_en timestamp with time zone NOT NULL,
    leido_en timestamp with time zone
);


--
-- Name: avisos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.avisos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: avisos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.avisos_id_seq OWNED BY public.avisos.id;


--
-- Name: campaigns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.campaigns (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    channel character varying(100) NOT NULL,
    budget double precision NOT NULL,
    utm_source character varying(100),
    utm_medium character varying(100),
    utm_campaign character varying(100),
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    description text,
    target_audience character varying(300),
    public_slug character varying(32) NOT NULL,
    estado character varying(20) DEFAULT 'activa'::character varying NOT NULL,
    necesidades json,
    responsable_id integer,
    url_del_post character varying(300),
    redes json,
    url_base_publicada character varying(300)
);


--
-- Name: campaigns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.campaigns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: campaigns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.campaigns_id_seq OWNED BY public.campaigns.id;


--
-- Name: crm_integration_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crm_integration_logs (
    id integer NOT NULL,
    lead_id integer,
    external_crm_id character varying(100),
    crm_platform character varying(50) NOT NULL,
    event_type character varying(50) NOT NULL,
    sync_status character varying(20) NOT NULL,
    payload json,
    response_data json,
    error_message text,
    synced_at timestamp with time zone NOT NULL
);


--
-- Name: crm_integration_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crm_integration_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crm_integration_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crm_integration_logs_id_seq OWNED BY public.crm_integration_logs.id;


--
-- Name: desenlaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.desenlaces (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    resultado character varying(20) NOT NULL,
    motivo character varying(40) NOT NULL,
    cerrado_el date NOT NULL,
    tramo character varying(30),
    score_al_cierre double precision NOT NULL,
    categoria_al_cierre public.scorecategory NOT NULL,
    score_history_id integer,
    version_del_vector integer,
    registrado_en timestamp with time zone NOT NULL,
    registrado_por_id integer
);


--
-- Name: desenlaces_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.desenlaces_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: desenlaces_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.desenlaces_id_seq OWNED BY public.desenlaces.id;


--
-- Name: lead_activities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lead_activities (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    activity_type public.activitytype NOT NULL,
    channel character varying(50) NOT NULL,
    activity_data json,
    occurred_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL,
    source character varying(40) DEFAULT 'manual'::character varying NOT NULL,
    external_event_id character varying(200),
    verificada boolean DEFAULT false NOT NULL,
    direction character varying(10),
    call_outcome character varying(20)
);


--
-- Name: lead_activities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lead_activities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lead_activities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lead_activities_id_seq OWNED BY public.lead_activities.id;


--
-- Name: leads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leads (
    id integer NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    phone character varying(50),
    company character varying(150),
    job_title character varying(100),
    industry character varying(100),
    company_size character varying(50),
    annual_revenue double precision,
    country character varying(100),
    city character varying(100),
    source character varying(100) NOT NULL,
    status public.leadstatus NOT NULL,
    qualification_status public.qualificationstatus NOT NULL,
    current_score double precision NOT NULL,
    score_category public.scorecategory NOT NULL,
    conversion_probability double precision NOT NULL,
    last_score_update timestamp with time zone NOT NULL,
    last_activity_at timestamp with time zone NOT NULL,
    assigned_rep_id integer,
    campaign_id integer,
    raw_metadata json,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    privacy_notice_accepted_at timestamp with time zone,
    privacy_notice_source character varying(40),
    dormido_desde timestamp with time zone
);


--
-- Name: leads_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leads_id_seq OWNED BY public.leads.id;


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    id integer NOT NULL,
    jti character varying(32) NOT NULL,
    family_id character varying(32) NOT NULL,
    user_id integer NOT NULL,
    issued_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revoked_reason character varying(30),
    replaced_by_jti character varying(32),
    issued_ip character varying(64)
);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- Name: score_histories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_histories (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    score double precision NOT NULL,
    score_category public.scorecategory NOT NULL,
    model_version character varying(50) NOT NULL,
    ml_probability double precision NOT NULL,
    heuristic_score double precision NOT NULL,
    decay_factor double precision NOT NULL,
    rule_breakdown json,
    ai_explanation json,
    calculated_at timestamp with time zone NOT NULL,
    feature_snapshot json
);


--
-- Name: score_histories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.score_histories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: score_histories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.score_histories_id_seq OWNED BY public.score_histories.id;


--
-- Name: score_history_monthly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.score_history_monthly (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    month date NOT NULL,
    scores_count integer NOT NULL,
    score_sum double precision NOT NULL,
    score_min double precision NOT NULL,
    score_max double precision NOT NULL,
    first_score double precision NOT NULL,
    first_calculated_at timestamp with time zone NOT NULL,
    last_score double precision NOT NULL,
    last_category public.scorecategory NOT NULL,
    last_calculated_at timestamp with time zone NOT NULL,
    category_counts json NOT NULL,
    model_versions json NOT NULL,
    aggregated_at timestamp with time zone NOT NULL
);


--
-- Name: score_history_monthly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.score_history_monthly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: score_history_monthly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.score_history_monthly_id_seq OWNED BY public.score_history_monthly.id;


--
-- Name: scoring_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scoring_jobs (
    id character varying(36) NOT NULL,
    job_type character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    total_leads integer NOT NULL,
    processed_leads integer NOT NULL,
    failed_leads integer NOT NULL,
    batch_size integer NOT NULL,
    requested_by character varying(255),
    error_message text,
    created_at timestamp with time zone NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    lease_until timestamp with time zone,
    heartbeat_at timestamp with time zone,
    worker_id character varying(120),
    lease_key character varying(40)
);


--
-- Name: tareas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tareas (
    id integer NOT NULL,
    lead_id integer NOT NULL,
    asesor_id integer NOT NULL,
    regla character varying(40) NOT NULL,
    clave character varying(80) NOT NULL,
    estado character varying(20) DEFAULT 'abierta'::character varying NOT NULL,
    vence_el timestamp with time zone NOT NULL,
    motivo character varying(200) NOT NULL,
    datos json,
    creada_en timestamp with time zone NOT NULL,
    cerrada_en timestamp with time zone,
    cerrada_por_id integer
);


--
-- Name: tareas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tareas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tareas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tareas_id_seq OWNED BY public.tareas.id;


--
-- Name: unmatched_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unmatched_events (
    id integer NOT NULL,
    source character varying(40) NOT NULL,
    external_event_id character varying(200) NOT NULL,
    activity_type public.activitytype NOT NULL,
    channel character varying(50) NOT NULL,
    direction character varying(10),
    call_outcome character varying(20),
    contact_email character varying(150),
    contact_phone character varying(50),
    contact_name character varying(150),
    occurred_at timestamp with time zone NOT NULL,
    received_at timestamp with time zone NOT NULL
);


--
-- Name: unmatched_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unmatched_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unmatched_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unmatched_events_id_seq OWNED BY public.unmatched_events.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(150) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(150) NOT NULL,
    role character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    token_version integer NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_sales_rep boolean NOT NULL,
    phone character varying(50),
    capacity integer,
    password_changed_at timestamp with time zone NOT NULL,
    must_change_password boolean NOT NULL,
    totp_sal character varying(64),
    totp_activo boolean NOT NULL,
    totp_activado_en timestamp with time zone,
    totp_codigos_de_recuperacion json,
    totp_ultimo_contador integer
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: visitas_de_publicacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visitas_de_publicacion (
    campaign_id integer NOT NULL,
    dia date NOT NULL,
    red character varying(20) DEFAULT 'sin_red'::character varying NOT NULL,
    visitas integer NOT NULL
);


--
-- Name: webhook_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_deliveries (
    id integer NOT NULL,
    signature character varying(64) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    crm_platform character varying(50) NOT NULL,
    event character varying(50) NOT NULL,
    external_lead_id character varying(100),
    lead_id integer,
    response_data json,
    received_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: webhook_deliveries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.webhook_deliveries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: webhook_deliveries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_deliveries_id_seq OWNED BY public.webhook_deliveries.id;


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: avisos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos ALTER COLUMN id SET DEFAULT nextval('public.avisos_id_seq'::regclass);


--
-- Name: campaigns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns ALTER COLUMN id SET DEFAULT nextval('public.campaigns_id_seq'::regclass);


--
-- Name: crm_integration_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_integration_logs ALTER COLUMN id SET DEFAULT nextval('public.crm_integration_logs_id_seq'::regclass);


--
-- Name: desenlaces id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.desenlaces ALTER COLUMN id SET DEFAULT nextval('public.desenlaces_id_seq'::regclass);


--
-- Name: lead_activities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lead_activities ALTER COLUMN id SET DEFAULT nextval('public.lead_activities_id_seq'::regclass);


--
-- Name: leads id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads ALTER COLUMN id SET DEFAULT nextval('public.leads_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- Name: score_histories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_histories ALTER COLUMN id SET DEFAULT nextval('public.score_histories_id_seq'::regclass);


--
-- Name: score_history_monthly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_history_monthly ALTER COLUMN id SET DEFAULT nextval('public.score_history_monthly_id_seq'::regclass);


--
-- Name: tareas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tareas ALTER COLUMN id SET DEFAULT nextval('public.tareas_id_seq'::regclass);


--
-- Name: unmatched_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unmatched_events ALTER COLUMN id SET DEFAULT nextval('public.unmatched_events_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: webhook_deliveries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_deliveries ALTER COLUMN id SET DEFAULT nextval('public.webhook_deliveries_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
d8b3e5f09a71
\.


--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_log (id, actor_id, actor_email, actor_role, action, entity, entity_id, outcome, ip_address, user_agent, event_metadata, occurred_at) FROM stdin;
1	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-24 21:02:08.139697+00
2	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-24 21:02:08.182438+00
3	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-24 21:02:08.27137+00
4	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-24 21:02:08.317733+00
5	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-24 21:02:08.330702+00
6	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-24 21:02:08.348814+00
7	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-24 21:02:08.356029+00
8	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-24 21:02:08.423609+00
9	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-24 21:02:08.432107+00
10	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-25T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.473818+00
11	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-06-26T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.503681+00
12	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-06-26T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.529223+00
13	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-06-26T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.548974+00
14	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-03-28T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.566656+00
15	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-06-26T21:02:08.438570+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 21:02:08.627686+00
16	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-24 22:40:00.344156+00
17	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-24 22:40:00.496034+00
18	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-24 22:40:00.631154+00
19	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-24 22:40:00.660156+00
20	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-24 22:40:00.709395+00
21	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-24 22:40:00.754609+00
22	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-24 22:40:00.802443+00
23	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-24 22:40:00.842149+00
24	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-24 22:40:00.862466+00
25	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-25T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:00.905391+00
26	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-06-26T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:00.929851+00
27	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-06-26T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:00.949774+00
28	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-06-26T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:01.03276+00
29	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-03-28T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:01.057442+00
30	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-06-26T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:01.151989+00
31	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-24T22:40:00.881283+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-24 22:40:01.171048+00
32	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-25T22:40:00.881283+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-24 22:40:01.189178+00
33	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-25 02:00:21.30861+00
34	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-25 02:00:21.509187+00
35	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-25 02:00:21.80893+00
36	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-25 02:00:21.914975+00
37	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-25 02:00:22.013999+00
38	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-25 02:00:22.124745+00
39	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-25 02:00:22.213816+00
40	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-25 02:00:22.315972+00
41	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-25 02:00:22.406577+00
42	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-26T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:22.506504+00
43	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-06-27T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:22.606424+00
44	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-06-27T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:22.622323+00
45	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-06-27T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:22.81804+00
46	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-03-29T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:22.913482+00
47	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-06-27T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:23.108181+00
48	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-25T02:00:22.413431+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 02:00:23.128138+00
49	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-26T02:00:22.413431+00:00", "simulado": false, "archivos_borrados": 2, "error": null}	2026-09-25 02:00:23.307812+00
50	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-25 05:12:52.475919+00
51	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-25 05:12:52.555637+00
52	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-25 05:12:52.609369+00
53	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-25 05:12:52.661398+00
54	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-25 05:12:52.677335+00
55	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-25 05:12:52.696984+00
56	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-25 05:12:52.763568+00
57	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-25 05:12:52.777079+00
58	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-25 05:12:52.786498+00
59	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-26T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.853634+00
60	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-06-27T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.869413+00
61	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-06-27T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.884458+00
62	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-06-27T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.899187+00
63	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-03-29T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.95374+00
64	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-06-27T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.976742+00
65	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-25T05:12:52.791068+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 05:12:52.990074+00
66	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-26T05:12:52.791068+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-25 05:12:53.000654+00
67	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-25 15:42:48.077763+00
68	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-25 15:42:48.165212+00
69	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-25 15:42:48.345384+00
70	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-25 15:42:48.375686+00
71	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-25 15:42:48.395479+00
72	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-25 15:42:48.478066+00
73	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-25 15:42:48.485441+00
74	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-25 15:42:48.501485+00
75	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-25 15:42:48.56801+00
76	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-26T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.59923+00
77	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-06-27T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.672683+00
78	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-06-27T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.696216+00
79	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-06-27T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.741682+00
80	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-03-29T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.762769+00
81	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-06-27T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.803314+00
82	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-25T15:42:48.575093+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-25 15:42:48.818427+00
83	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-26T15:42:48.575093+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-25 15:42:48.860546+00
84	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-29 21:30:21.828751+00
85	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-29 21:30:21.886693+00
86	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-29 21:30:21.961436+00
87	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-29 21:30:21.978834+00
88	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-29 21:30:22.020031+00
89	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-29 21:30:22.037988+00
90	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-29 21:30:22.045178+00
91	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-29 21:30:22.059496+00
92	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-29 21:30:22.114493+00
93	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-30T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.136612+00
94	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-01T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.153084+00
95	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-01T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.169466+00
96	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-01T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.187103+00
97	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-02T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.216546+00
98	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-01T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.23543+00
99	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-29T21:30:22.120948+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:30:22.247124+00
100	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-30T21:30:22.120948+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-29 21:30:22.254902+00
101	\N	\N	\N	auth.login_fallido	sesion	\N	HTTP_401	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"email_intentado": "lider.ventas@plurione.com", "motivo": "email_no_registrado"}	2026-09-29 21:36:55.043246+00
102	\N	\N	\N	auth.login_fallido	sesion	\N	HTTP_401	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"email_intentado": "lider.ventas@plurione.com", "motivo": "email_no_registrado"}	2026-09-29 21:37:23.250351+00
103	\N	\N	\N	auth.login_fallido	sesion	\N	HTTP_401	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"email_intentado": "lider.ventas@plurione.com", "motivo": "email_no_registrado"}	2026-09-29 21:37:48.083106+00
104	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-29 21:45:13.346399+00
105	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-29 21:45:13.420993+00
106	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-29 21:45:13.573014+00
107	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-29 21:45:13.630915+00
108	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-29 21:45:13.647244+00
109	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-29 21:45:13.740728+00
110	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-29 21:45:13.759045+00
111	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-29 21:45:13.823112+00
112	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-29 21:45:13.835137+00
113	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-30T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:13.859491+00
114	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-01T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:13.927137+00
115	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-01T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:13.943989+00
116	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-01T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:13.96125+00
117	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-02T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:14.01857+00
118	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-01T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:14.039609+00
119	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-29T21:45:13.842254+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 21:45:14.055769+00
120	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-30T21:45:13.842254+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-29 21:45:14.116934+00
121	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.9939.4 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-09-29 21:58:39.859226+00
122	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.9939.4 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-09-29 22:18:27.762825+00
123	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-09-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-09-29 22:20:05.923101+00
124	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-09-29 22:20:06.00317+00
125	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 12, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-09-29 22:20:06.216547+00
126	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-09-29 22:20:06.236047+00
127	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-09-29 22:20:06.249039+00
128	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 4, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-09-29 22:20:06.332411+00
129	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 4, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-09-29 22:20:06.427274+00
130	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-09-29 22:20:06.441816+00
131	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-09-29 22:20:06.516138+00
132	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-08-30T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.532727+00
133	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-01T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.549729+00
134	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-01T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.562404+00
135	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-01T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.616591+00
136	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-02T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.628219+00
137	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-01T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.64128+00
138	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-09-29T22:20:06.522730+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-09-29 22:20:06.651936+00
139	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-08-30T22:20:06.522730+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-09-29 22:20:06.700561+00
140	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-09-29 22:22:09.838284+00
141	2	lider.ventas@plurione.com	Sales_Lead	desenlace.panel	desenlace	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"desde": null, "hasta": null, "cerrados": 0}	2026-09-29 22:22:57.300104+00
142	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"publicaciones": 1}	2026-09-29 22:23:45.011359+00
156	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-01 15:17:53.452365+00
157	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-01 15:17:54.264201+00
158	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-01 15:17:54.544659+00
159	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-01 15:17:54.569196+00
160	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-01 15:17:54.588071+00
161	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-01 15:17:54.748707+00
162	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-01 15:17:54.865966+00
163	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-01 15:17:54.945616+00
164	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-01 15:17:54.967648+00
165	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-01T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.055472+00
166	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-03T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.103507+00
167	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-03T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.134258+00
168	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-03T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.163396+00
169	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-04T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.197186+00
170	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-03T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.242239+00
171	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-01T15:17:54.981414+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 15:17:55.258267+00
172	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-01T15:17:54.981414+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-01 15:17:55.270092+00
173	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-01 16:25:21.727117+00
174	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-01 16:25:22.32721+00
175	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-01 16:25:22.611666+00
176	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-01 16:25:22.630825+00
177	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-01 16:25:22.645961+00
178	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-01 16:25:22.797434+00
179	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-01 16:25:22.920564+00
180	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-01 16:25:22.933522+00
181	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-01 16:25:23.015226+00
182	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-01T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.038875+00
183	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-03T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.104569+00
184	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-03T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.11981+00
185	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-03T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.136421+00
186	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-04T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.152487+00
187	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-03T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.201336+00
188	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-01T16:25:23.021626+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-01 16:25:23.214695+00
189	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-01T16:25:23.021626+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-01 16:25:23.230782+00
190	2	lider.ventas@plurione.com	Sales_Lead	desenlace.panel	desenlace	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"desde": null, "hasta": null, "cerrados": 0}	2026-10-01 20:03:36.896321+00
191	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"publicaciones": 1}	2026-10-01 20:03:47.804399+00
192	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-10-01 20:06:41.35772+00
193	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-10-01 20:06:52.621614+00
194	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-10-01 20:06:53.407565+00
195	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-10-01 20:06:54.925306+00
196	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{}	2026-10-01 20:06:55.257654+00
197	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	7	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"nombre": "Ingeniero en ciberseguridad", "canal": "LinkedIn", "presupuesto": 0.0, "estado": "activa", "responsable_id": 3}	2026-10-01 20:07:23.44518+00
198	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"publicaciones": 2}	2026-10-01 20:07:23.712054+00
199	2	lider.ventas@plurione.com	Sales_Lead	publicacion.informe	campana	7	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 OPR/136.0.0.0	{"filtros": {"etapa": null, "desde": null, "hasta": null}, "devueltos": 0, "total": 0, "alcance_completo": true}	2026-10-01 20:07:50.881894+00
200	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-05 15:36:44.044452+00
201	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-05 15:36:45.841157+00
202	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-05 15:36:46.165795+00
203	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-05 15:36:46.228196+00
204	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-05 15:36:46.251872+00
205	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-05 15:36:46.442229+00
206	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-05 15:36:46.686745+00
207	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-05 15:36:46.771601+00
208	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-05 15:36:46.843224+00
209	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-05T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:46.911906+00
210	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-07T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:46.940348+00
211	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-07T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:47.037563+00
212	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-07T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:47.118006+00
213	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-08T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:47.134144+00
214	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-07T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:47.222229+00
215	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-05T15:36:46.889399+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 15:36:47.235294+00
216	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-05T15:36:46.889399+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-05 15:36:47.245667+00
217	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-05 15:53:59.203323+00
218	3	asesor.comercial@plurione.com	Commercial_Executive	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-05 15:53:59.790401+00
219	1	admin.ti@plurione.com	System_Admin	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-05 15:54:00.431727+00
220	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 15:59:51.288236+00
221	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 2}	2026-10-05 16:02:28.548863+00
222	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	8	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"nombre": "Post \\u00b7 Talento TI octubre (demo)", "canal": "LinkedIn", "presupuesto": 0.0, "estado": "activa", "responsable_id": null}	2026-10-05 16:03:47.988143+00
223	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-05 16:03:48.274815+00
224	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-05 16:08:21.389417+00
225	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-05 16:08:21.898543+00
226	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-05 16:08:22.317179+00
227	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-05 16:08:22.38967+00
228	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-05 16:08:22.405745+00
229	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-05 16:08:22.683445+00
230	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-05 16:08:22.89318+00
231	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-05 16:08:22.976046+00
232	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-05 16:08:22.994469+00
233	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-05T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.009762+00
234	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-07T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.084888+00
235	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-07T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.101103+00
236	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-07T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.119682+00
237	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-08T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.179387+00
238	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-07T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.19249+00
239	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-05T16:08:22.999672+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 16:08:23.207015+00
240	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-05T16:08:22.999672+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-05 16:08:23.273611+00
241	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-05 16:08:54.222316+00
242	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-05 16:11:30.05433+00
243	2	lider.ventas@plurione.com	Sales_Lead	lead.actualizar	lead	30	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"campos": ["assigned_rep_id"], "campos_vaciados": []}	2026-10-05 16:14:55.154429+00
244	2	lider.ventas@plurione.com	Sales_Lead	auth.logout	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"tokens_revocados": 5}	2026-10-05 16:15:26.932455+00
245	5	ana.ruiz@plurione.com	Commercial_Executive	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 16:15:37.515894+00
246	5	ana.ruiz@plurione.com	Commercial_Executive	acceso.denegado	endpoint	/api/v1/analytics/campaigns	HTTP_403	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"metodo": "GET", "roles_requeridos": ["Sales_Lead", "System_Admin"]}	2026-10-05 16:15:37.629528+00
247	5	ana.ruiz@plurione.com	Commercial_Executive	lead.actividad	lead	30	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"tipo_de_actividad": "PHONE_CALL", "actividad_id": 55}	2026-10-05 16:20:18.585281+00
248	5	ana.ruiz@plurione.com	Commercial_Executive	acceso.denegado	endpoint	/api/v1/analytics/campaigns	HTTP_403	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"metodo": "GET", "roles_requeridos": ["Sales_Lead", "System_Admin"]}	2026-10-05 16:20:18.700297+00
249	5	ana.ruiz@plurione.com	Commercial_Executive	desenlace.registrar	desenlace	30	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"prospecto_id": 30, "resultado_del_cierre": "ganado", "motivo": "perfil", "cerrado_el": "2026-10-05", "tramo": "de_100k_a_500k", "version_del_vector": 2, "utilizable_para_reentrenar": true, "tareas_descartadas": 0}	2026-10-05 16:21:40.759635+00
250	5	ana.ruiz@plurione.com	Commercial_Executive	acceso.denegado	endpoint	/api/v1/analytics/campaigns	HTTP_403	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"metodo": "GET", "roles_requeridos": ["Sales_Lead", "System_Admin"]}	2026-10-05 16:21:40.879498+00
251	5	ana.ruiz@plurione.com	Commercial_Executive	auth.logout	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"tokens_revocados": 1}	2026-10-05 16:22:18.316787+00
252	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 16:22:29.28473+00
254	2	lider.ventas@plurione.com	Sales_Lead	lead.actualizar	lead	\N	ERROR	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 16:24:35.807669+00
253	2	lider.ventas@plurione.com	Sales_Lead	desenlace.panel	desenlace	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"desde": null, "hasta": null, "cerrados": 1}	2026-10-05 16:22:32.887142+00
258	1	admin.ti@plurione.com	System_Admin	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 16:26:32.607306+00
255	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-05 16:25:41.054969+00
256	2	lider.ventas@plurione.com	Sales_Lead	publicacion.informe	campana	8	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"filtros": {"etapa": null, "desde": null, "hasta": null}, "devueltos": 1, "total": 1, "alcance_completo": true}	2026-10-05 16:25:44.93694+00
257	2	lider.ventas@plurione.com	Sales_Lead	auth.logout	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"tokens_revocados": 1}	2026-10-05 16:26:15.31582+00
259	1	admin.ti@plurione.com	System_Admin	usuario.segundo_factor_alta	usuario	1	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"codigos_emitidos": 10}	2026-10-05 16:26:32.688555+00
260	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-05 17:13:13.533063+00
261	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-05 17:13:14.623281+00
262	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-05 17:13:15.25302+00
263	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-05 17:13:15.33144+00
264	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-05 17:13:15.366678+00
265	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-05 17:13:15.659382+00
266	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-05 17:13:15.869621+00
267	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-05 17:13:15.921241+00
268	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-05 17:13:15.960434+00
269	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-05T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.017008+00
270	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-07T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.044523+00
271	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-07T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.081238+00
272	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-07T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.116985+00
273	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-08T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.147741+00
274	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-07T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.173925+00
275	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-05T17:13:15.985235+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-05 17:13:16.229585+00
276	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-05T17:13:15.985235+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-05 17:13:16.273176+00
277	1	admin.ti@plurione.com	System_Admin	usuario.segundo_factor_alta	usuario	1	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"codigos_emitidos": 10}	2026-10-05 17:16:09.37793+00
278	1	admin.ti@plurione.com	System_Admin	auth.logout	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"tokens_revocados": 2}	2026-10-05 17:16:51.670281+00
279	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-05 17:17:04.337233+00
280	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-05 17:17:23.772346+00
281	2	lider.ventas@plurione.com	Sales_Lead	lead.exportar	lead	30	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.0 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"secciones": {"actividades": 2, "historial_de_puntuacion": 3, "resumen_mensual_de_puntuacion": 0, "integraciones_crm": 0, "entregas_de_webhook": 0, "tareas": 0, "avisos": 0, "desenlace": 1, "integraciones_crm_sin_vincular": 0, "eventos_sin_asociar": 0, "tratamientos_registrados": 2, "fuera_de_la_base": 3}}	2026-10-05 17:39:51.036521+00
282	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 02:54:41.914363+00
283	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 02:54:43.086497+00
284	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 02:54:43.605623+00
285	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 02:54:43.678288+00
286	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 02:54:43.692686+00
287	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 02:54:43.896754+00
288	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 02:54:44.081756+00
289	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 02:54:44.100385+00
290	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 02:54:44.173877+00
291	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.208264+00
292	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.226542+00
293	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.272197+00
294	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.29547+00
295	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.312708+00
296	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.326463+00
297	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T02:54:44.179817+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:54:44.378781+00
298	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T02:54:44.179817+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 02:54:44.388728+00
299	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 02:55:46.122867+00
300	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 02:55:46.821468+00
301	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 02:55:47.416113+00
302	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 02:55:47.445876+00
303	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 02:55:47.515599+00
304	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 02:55:47.724394+00
305	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 02:55:47.943542+00
306	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 02:55:48.01747+00
307	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 02:55:48.045435+00
308	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.132286+00
309	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.1642+00
310	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.21383+00
311	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.232616+00
312	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.251844+00
313	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.324623+00
314	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T02:55:48.060350+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 02:55:48.341065+00
315	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T02:55:48.060350+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 02:55:48.354423+00
316	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; es-MX) WindowsPowerShell/5.1.26100.9549	{}	2026-10-07 02:58:00.723052+00
317	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 03:08:28.732515+00
318	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 03:08:29.52912+00
319	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 03:08:30.411717+00
320	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 03:08:30.451132+00
321	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 03:08:30.514596+00
322	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 03:08:31.015412+00
323	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 03:08:31.617509+00
324	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 03:08:31.712756+00
325	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 03:08:31.899989+00
326	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.10941+00
327	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.203682+00
328	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.301284+00
329	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.36484+00
330	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.415667+00
331	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.437242+00
332	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T03:08:31.921778+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 03:08:32.52741+00
333	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T03:08:31.921778+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 03:08:32.601882+00
334	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{}	2026-10-07 03:44:58.994462+00
335	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 3}	2026-10-07 03:45:30.774472+00
336	2	lider.ventas@plurione.com	Sales_Lead	campana.crear	campana	9	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"nombre": "post qr prueba", "canal": "LinkedIn", "presupuesto": 0.0, "estado": "activa", "responsable_id": null}	2026-10-07 03:49:10.824215+00
337	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 4}	2026-10-07 03:49:10.98834+00
338	2	lider.ventas@plurione.com	Sales_Lead	publicacion.informe	campana	9	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"filtros": {"etapa": null, "desde": null, "hasta": null}, "devueltos": 0, "total": 0, "alcance_completo": true}	2026-10-07 03:50:08.120412+00
339	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 4}	2026-10-07 03:52:08.087428+00
340	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 4}	2026-10-07 03:52:14.293083+00
341	2	lider.ventas@plurione.com	Sales_Lead	campana.actualizar	campana	7	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"nombre": "Ingeniero en ciberseguridad", "estado_anterior": "activa", "estado_nuevo": "cerrada", "campos": ["estado"]}	2026-10-07 03:52:24.271481+00
342	2	lider.ventas@plurione.com	Sales_Lead	publicacion.comparativa	campana	\N	OK	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.19675.1 Chrome/152.0.7977.130 Safari/537.36 MSIX	{"publicaciones": 4}	2026-10-07 03:52:24.421948+00
343	\N	\N	\N	lead.reparto_automatico	lead	31	OK	\N	\N	{"asesor_id": 6, "regla": "mas_tiempo_sin_recibir", "candidatos": 6, "cartera_abierta_del_elegido": 2}	2026-10-07 04:12:57.587948+00
344	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 04:16:56.804474+00
345	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 1, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 04:16:57.11533+00
346	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 04:16:57.162793+00
347	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 04:16:57.209507+00
348	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 04:16:57.345073+00
349	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 04:16:57.551895+00
350	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 04:16:57.583402+00
351	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 04:16:57.616793+00
352	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-07 04:21:04.165543+00
353	2	lider.ventas@plurione.com	Sales_Lead	lead.eliminar	lead	31	OK	172.18.0.1	curl/8.22.0	{"huella_del_titular": "9098ddacdcf0be0d43f351c7e09a1125", "score": 14.3, "supresion": {"lead_activities": 1, "score_histories": 1, "score_history_monthly": 0, "crm_integration_logs": 0, "webhook_deliveries": 0, "tareas": 1, "avisos": 0, "desenlaces": 0, "crm_integration_logs_sin_vincular": 0, "unmatched_events": 0, "asientos_con_datos_retirados": 0, "leads": 1}}	2026-10-07 04:21:04.545592+00
354	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 06:15:38.653137+00
355	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 06:15:39.263403+00
356	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 06:15:39.765854+00
357	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 06:15:39.852554+00
358	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 06:15:39.871311+00
359	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 06:15:40.073157+00
360	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 06:15:40.267914+00
361	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 06:15:40.343232+00
362	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 06:15:40.37038+00
363	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.39446+00
364	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.454383+00
365	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.471898+00
366	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.491149+00
367	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.538486+00
368	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.549342+00
369	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T06:15:40.375059+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 06:15:40.561578+00
370	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T06:15:40.375059+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 06:15:40.56819+00
371	2	lider.ventas@plurione.com	Sales_Lead	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-07 06:16:14.363928+00
372	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 07:21:31.671078+00
373	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 07:21:32.161302+00
374	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 07:21:32.468646+00
375	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 07:21:32.487105+00
376	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 07:21:32.500569+00
377	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 07:21:32.667381+00
378	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 07:21:32.783239+00
379	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 07:21:32.853911+00
380	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 07:21:32.872284+00
381	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.88888+00
382	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.90411+00
383	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.953829+00
384	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.969257+00
385	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.981184+00
386	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:32.992113+00
387	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T07:21:32.878100+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:21:33.00281+00
388	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T07:21:32.878100+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 07:21:33.053791+00
389	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-07 07:26:48.975663+00
390	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-07 07:26:49.387549+00
391	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-07 07:26:49.693713+00
392	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-07 07:26:49.766373+00
393	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-07 07:26:49.780302+00
394	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-07 07:26:49.890986+00
395	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-07 07:26:50.076963+00
396	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-07 07:26:50.091302+00
397	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-07 07:26:50.108446+00
398	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-07T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.124071+00
399	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-09T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.175201+00
400	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-09T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.187918+00
401	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-09T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.20143+00
402	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-10T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.212506+00
403	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-09T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.262889+00
404	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-07T07:26:50.114096+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-07 07:26:50.274711+00
405	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-07T07:26:50.114096+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-07 07:26:50.282917+00
406	\N	\N	\N	historial.retencion	historial_de_puntuacion	\N	OK	\N	\N	{"limite": "2025-10-01T00:00:00+00:00", "meses": 12, "simulado": false, "prospectos": 0, "filas_resumidas": 0, "filas_protegidas": 0, "resumenes_nuevos": 0, "resumenes_fusionados": 0, "lotes_descartados": 0}	2026-10-10 02:54:59.15453+00
407	\N	\N	\N	regla.ejecucion	regla	cerrar_lo_cumplido	OK	\N	\N	{"regla": "cerrar_lo_cumplido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "cerrar_lo_cumplido"}	2026-10-10 02:54:59.942035+00
408	\N	\N	\N	regla.ejecucion	regla	primer_contacto	OK	\N	\N	{"regla": "primer_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Primer contacto"}	2026-10-10 02:55:00.376092+00
409	\N	\N	\N	regla.ejecucion	regla	volver_a_llamar	OK	\N	\N	{"regla": "volver_a_llamar", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Volver a llamar"}	2026-10-10 02:55:00.455024+00
410	\N	\N	\N	regla.ejecucion	regla	recordatorio_de_reunion	OK	\N	\N	{"regla": "recordatorio_de_reunion", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Reuni\\u00f3n ma\\u00f1ana"}	2026-10-10 02:55:00.540546+00
411	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto	OK	\N	\N	{"regla": "hot_sin_contacto", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar"}	2026-10-10 02:55:00.767216+00
412	\N	\N	\N	regla.ejecucion	regla	hot_sin_contacto_lider	OK	\N	\N	{"regla": "hot_sin_contacto_lider", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "HOT sin contactar (aviso al l\\u00edder)"}	2026-10-10 02:55:00.975244+00
413	\N	\N	\N	regla.ejecucion	regla	prospecto_dormido	OK	\N	\N	{"regla": "prospecto_dormido", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Prospecto dormido"}	2026-10-10 02:55:01.057852+00
414	\N	\N	\N	regla.ejecucion	regla	desenlaces_suficientes	OK	\N	\N	{"regla": "desenlaces_suficientes", "tareas_creadas": 0, "avisos_creados": 0, "tareas_cerradas": 0, "prospectos_marcados": 0, "error": null, "etiqueta": "Ya hay desenlaces para reentrenar"}	2026-10-10 02:55:01.1807+00
415	\N	\N	\N	conservacion.purga	sesion	\N	OK	\N	\N	{"plazo": "sesiones", "tabla": "refresh_tokens", "dias": 30, "corte": "2026-09-10T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.266736+00
416	\N	\N	\N	conservacion.purga	trabajo_de_scoring	\N	OK	\N	\N	{"plazo": "trabajos_de_recalculo", "tabla": "scoring_jobs", "dias": 90, "corte": "2026-07-12T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.340564+00
417	\N	\N	\N	conservacion.purga	registro_crm	\N	OK	\N	\N	{"plazo": "registros_crm", "tabla": "crm_integration_logs", "dias": 90, "corte": "2026-07-12T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.394033+00
418	\N	\N	\N	conservacion.purga	evento_sin_asociar	\N	OK	\N	\N	{"plazo": "bandeja_sin_asociar", "tabla": "unmatched_events", "dias": 90, "corte": "2026-07-12T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.477365+00
419	\N	\N	\N	conservacion.purga	tarea	\N	OK	\N	\N	{"plazo": "tareas", "tabla": "tareas", "dias": 180, "corte": "2026-04-13T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.517053+00
420	\N	\N	\N	conservacion.purga	aviso	\N	OK	\N	\N	{"plazo": "avisos", "tabla": "avisos", "dias": 90, "corte": "2026-07-12T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.541927+00
421	\N	\N	\N	conservacion.purga	bitacora	\N	OK	\N	\N	{"plazo": "bitacora", "tabla": "audit_log", "dias": 730, "corte": "2024-10-10T02:55:01.188440+00:00", "simulado": false, "filas_borradas": 0, "error": null}	2026-10-10 02:55:01.562198+00
422	\N	\N	\N	conservacion.purga	conjunto_de_realimentacion	\N	OK	\N	\N	{"plazo": "conjunto_de_realimentacion", "tabla": "/var/lib/plurione/realimentacion", "dias": 30, "corte": "2026-09-10T02:55:01.188440+00:00", "simulado": false, "archivos_borrados": 0, "error": null}	2026-10-10 02:55:01.574756+00
423	1	admin.ti@plurione.com	System_Admin	auth.login	sesion	\N	OK	172.18.0.1	curl/8.22.0	{}	2026-10-10 03:49:49.360918+00
\.


--
-- Data for Name: avisos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.avisos (id, usuario_id, lead_id, regla, clave, texto, datos, creado_en, leido_en) FROM stdin;
1	2	15	hot_sin_contacto	2026-09-24	Prospecto HOT sin contactar desde hace 24 h.	{"score": 87.3, "horas": 24}	2026-09-29 22:20:05.938932+00	\N
2	5	18	hot_sin_contacto	2026-09-28	Prospecto HOT sin contactar desde hace 24 h.	{"score": 91.2, "horas": 24}	2026-09-29 22:20:05.938932+00	\N
3	3	22	hot_sin_contacto	2026-09-29	Prospecto HOT sin contactar desde hace 24 h.	{"score": 87.9, "horas": 24}	2026-09-29 22:20:05.938932+00	\N
4	6	25	hot_sin_contacto	2026-09-26	Prospecto HOT sin contactar desde hace 24 h.	{"score": 90.6, "horas": 24}	2026-09-29 22:20:05.938932+00	\N
5	2	15	hot_sin_contacto_lider	2026-09-24	Prospecto HOT sin contactar desde hace 48 h; el aviso a su asesor no lo resolvió.	{"score": 87.3, "asesor_id": 2}	2026-09-29 22:20:05.938932+00	\N
6	2	18	hot_sin_contacto_lider	2026-09-28	Prospecto HOT sin contactar desde hace 48 h; el aviso a su asesor no lo resolvió.	{"score": 91.2, "asesor_id": 5}	2026-09-29 22:20:05.938932+00	\N
7	2	22	hot_sin_contacto_lider	2026-09-29	Prospecto HOT sin contactar desde hace 48 h; el aviso a su asesor no lo resolvió.	{"score": 87.9, "asesor_id": 3}	2026-09-29 22:20:05.938932+00	\N
8	2	25	hot_sin_contacto_lider	2026-09-26	Prospecto HOT sin contactar desde hace 48 h; el aviso a su asesor no lo resolvió.	{"score": 90.6, "asesor_id": 6}	2026-09-29 22:20:05.938932+00	\N
\.


--
-- Data for Name: campaigns; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.campaigns (id, name, channel, budget, utm_source, utm_medium, utm_campaign, start_date, end_date, is_active, created_at, description, target_audience, public_slug, estado, necesidades, responsable_id, url_del_post, redes, url_base_publicada) FROM stdin;
2	Q3 Tech Talent Summit 2026	LinkedIn Ads	12000	linkedin	cpc	talent_summit_26	\N	\N	t	2026-09-29 22:17:41.597662+00	\N	\N	jfkSY1-RfwkkcFaC_mQAIQ	activa	\N	\N	\N	\N	\N
3	Webinar: IA en Procesos de Selección B2B	Webinar	4500	email	newsletter	webinar_ia_b2b	\N	\N	t	2026-09-29 22:17:41.597677+00	\N	\N	thUGxlDY5eTy37fmK9Ja1w	activa	\N	\N	\N	\N	\N
4	Inbound SEO - Soluciones TI Corporativas	Organic Search	8000	google	organic	ti_solutions_seo	\N	\N	t	2026-09-29 22:17:41.597683+00	\N	\N	MuHiI2LzD1H2edDCGcqyug	activa	\N	\N	\N	\N	\N
5	Outbound Email - C-Level Executives	Outbound Cold Email	3000	outbound	email	c_level_q3	\N	\N	t	2026-09-29 22:17:41.597687+00	\N	\N	wawun1XOhfaEeHKiVYjzRQ	activa	\N	\N	\N	\N	\N
6	Post · Equipos de TI en 30 días (agosto)	LinkedIn	3500	\N	\N	\N	\N	\N	t	2026-09-29 22:17:41.869218+00	Montar un equipo de TI completo tarda meses. Nosotros lo hacemos en 30 días, con perfiles probados y acompañamiento hasta que el equipo produce.\n\nSi te interesa, cuéntanos qué necesitas y te escribimos.	Directores y gerentes de TI de empresas medianas	Ay3iCoyK1xoQsdY69xdDVA	activa	\N	\N	\N	\N	\N
8	Post · Talento TI octubre (demo)	LinkedIn	0	\N	\N	\N	\N	\N	t	2026-10-05 16:03:47.948464+00	¿Te falta gente de TI y el proyecto no espera? Te armamos el equipo en 30 días, con perfiles probados y acompañamiento hasta que produce.\n\nCuéntanos qué necesitas y te escribimos.	Directores y gerentes de TI de empresas medianas	ZrV9BZf2DKdbuv5cQuLpIQ	activa	null	\N	\N	["linkedin", "whatsapp", "facebook", "correo"]	https://beam-tasks-resolve-graduated.trycloudflare.com/interes
7	Ingeniero en ciberseguridad	LinkedIn	0	\N	\N	\N	\N	\N	f	2026-10-01 20:07:23.398756+00	ingeniero en ciberseguridad para empresa de ventas	admins	NarG5GoYY0TGweQJ-o4xQQ	cerrada	null	3	\N	["linkedin", "whatsapp", "facebook", "correo"]	https://beam-tasks-resolve-graduated.trycloudflare.com/interes
\.


--
-- Data for Name: crm_integration_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.crm_integration_logs (id, lead_id, external_crm_id, crm_platform, event_type, sync_status, payload, response_data, error_message, synced_at) FROM stdin;
1	15	CRM-PLURI-1015	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 15, "email": "mariana.c@fintechavanzada.com", "score": 87.3}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1015"}	\N	2026-09-29 22:17:41.732269+00
2	16	CRM-PLURI-1016	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 16, "email": "rgarza@logisticaglobal.mx", "score": 51.6}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1016"}	\N	2026-09-29 22:17:41.734908+00
3	17	CRM-PLURI-1017	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 17, "email": "lfernandez@cloudmex.com", "score": 66.0}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1017"}	\N	2026-09-29 22:17:41.737286+00
4	18	CRM-PLURI-1018	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 18, "email": "fsalinas@gruporetailnorte.com", "score": 91.2}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1018"}	\N	2026-09-29 22:17:41.740193+00
5	19	CRM-PLURI-1019	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 19, "email": "etorres@saluddigital.com", "score": 68.6}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1019"}	\N	2026-09-29 22:17:41.742869+00
6	20	CRM-PLURI-1020	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 20, "email": "jlopez@ecomexpress.mx", "score": 28.0}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1020"}	\N	2026-09-29 22:17:41.74499+00
7	21	CRM-PLURI-1021	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 21, "email": "gpaz@consultoriamex.com", "score": 36.7}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1021"}	\N	2026-09-29 22:17:41.746931+00
8	22	CRM-PLURI-1022	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 22, "email": "avargas@bancocentro.com.mx", "score": 87.9}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1022"}	\N	2026-09-29 22:17:41.74893+00
9	23	CRM-PLURI-1023	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 23, "email": "cmarquez@techconsultores.mx", "score": 18.1}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1023"}	\N	2026-09-29 22:17:41.750927+00
10	24	CRM-PLURI-1024	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 24, "email": "mortiz@inretailmex.com", "score": 17.8}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1024"}	\N	2026-09-29 22:17:41.752998+00
11	25	CRM-PLURI-1025	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 25, "email": "pnavarro@fintechavanzada.com", "score": 90.6}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1025"}	\N	2026-09-29 22:17:41.756003+00
12	26	CRM-PLURI-1026	PluriOne_CRM	INGEST_AND_SCORE	SUCCESS	{"lead_id": 26, "email": "edominguez@saluddigital.com", "score": 56.6}	{"status": "synchronized", "crm_lead_id": "CRM-PLURI-1026"}	\N	2026-09-29 22:17:41.758632+00
\.


--
-- Data for Name: desenlaces; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.desenlaces (id, lead_id, resultado, motivo, cerrado_el, tramo, score_al_cierre, categoria_al_cierre, score_history_id, version_del_vector, registrado_en, registrado_por_id) FROM stdin;
1	30	ganado	perfil	2026-10-05	de_100k_a_500k	34.3	COLD	30	2	2026-10-05 16:21:40.670585+00	5
\.


--
-- Data for Name: lead_activities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.lead_activities (id, lead_id, activity_type, channel, activity_data, occurred_at, created_at, source, external_event_id, verificada, direction, call_outcome) FROM stdin;
15	15	DEMO_REQUEST	Web	{"requested_topic": "Plataforma de Headhunting TI"}	2026-09-27 02:17:41.619025+00	2026-09-27 02:17:41.619025+00	crm	demo:15:0	t	\N	\N
16	15	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-28 00:17:41.619025+00	2026-09-28 00:17:41.619025+00	crm	demo:15:1	t	\N	\N
17	15	WEBINAR_ATTEND	Zoom	{"attendance_rate_percent": 95}	2026-09-29 00:17:41.619025+00	2026-09-29 00:17:41.619025+00	crm	demo:15:2	t	\N	\N
18	15	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-29 23:17:41.619025+00	2026-09-29 23:17:41.619025+00	crm	demo:15:3	t	\N	\N
19	15	CONTENT_DOWNLOAD	Web	{"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}	2026-10-01 05:17:41.619025+00	2026-10-01 05:17:41.619025+00	crm	demo:15:4	t	\N	\N
20	16	CONTENT_DOWNLOAD	Web	{"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}	2026-09-12 05:17:41.619025+00	2026-09-12 05:17:41.619025+00	crm	demo:16:0	t	\N	\N
21	16	PAGE_VIEW	Web	{"url": "/servicios/staffing-ti", "duration_sec": 140}	2026-09-13 00:17:41.619025+00	2026-09-13 00:17:41.619025+00	crm	demo:16:1	t	\N	\N
22	16	WEBINAR_ATTEND	Zoom	{"attendance_rate_percent": 95}	2026-09-13 23:17:41.619025+00	2026-09-13 23:17:41.619025+00	crm	demo:16:2	t	\N	\N
23	17	CONTENT_DOWNLOAD	Web	{"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}	2026-09-28 04:17:41.619025+00	2026-09-28 04:17:41.619025+00	crm	demo:17:0	t	\N	\N
24	17	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-29 04:17:41.619025+00	2026-09-29 04:17:41.619025+00	crm	demo:17:1	t	\N	\N
25	17	CONTENT_DOWNLOAD	Web	{"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}	2026-09-30 03:17:41.619025+00	2026-09-30 03:17:41.619025+00	crm	demo:17:2	t	\N	\N
26	18	PAGE_VIEW	Web	{"url": "/servicios/staffing-ti", "duration_sec": 140}	2026-09-23 00:17:41.619025+00	2026-09-23 00:17:41.619025+00	crm	demo:18:0	t	\N	\N
27	18	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-24 01:17:41.619025+00	2026-09-24 01:17:41.619025+00	crm	demo:18:1	t	\N	\N
28	18	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-25 01:17:41.619025+00	2026-09-25 01:17:41.619025+00	crm	demo:18:2	t	\N	\N
29	18	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-26 05:17:41.619025+00	2026-09-26 05:17:41.619025+00	crm	demo:18:3	t	\N	\N
30	18	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-27 00:17:41.619025+00	2026-09-27 00:17:41.619025+00	crm	demo:18:4	t	\N	\N
31	19	WEBINAR_ATTEND	Zoom	{"attendance_rate_percent": 95}	2026-09-14 06:17:41.619025+00	2026-09-14 06:17:41.619025+00	crm	demo:19:0	t	\N	\N
32	19	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-15 02:17:41.619025+00	2026-09-15 02:17:41.619025+00	crm	demo:19:1	t	\N	\N
33	19	PAGE_VIEW	Web	{"url": "/servicios/staffing-ti", "duration_sec": 140}	2026-09-16 03:17:41.619025+00	2026-09-16 03:17:41.619025+00	crm	demo:19:2	t	\N	\N
34	20	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-27 00:17:41.619025+00	2026-09-27 00:17:41.619025+00	crm	demo:20:0	t	\N	\N
35	21	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-24 01:17:41.619025+00	2026-09-24 01:17:41.619025+00	crm	demo:21:0	t	\N	\N
36	22	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-25 03:17:41.619025+00	2026-09-25 03:17:41.619025+00	crm	demo:22:0	t	\N	\N
37	22	FORM_SUBMIT	Web	{"form_id": "contact_lead_scoring", "fields": 6}	2026-09-26 04:17:41.619025+00	2026-09-26 04:17:41.619025+00	crm	demo:22:1	t	\N	\N
38	22	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-27 05:17:41.619025+00	2026-09-27 05:17:41.619025+00	crm	demo:22:2	t	\N	\N
39	22	PAGE_VIEW	Web	{"url": "/servicios/staffing-ti", "duration_sec": 140}	2026-09-28 04:17:41.619025+00	2026-09-28 04:17:41.619025+00	crm	demo:22:3	t	\N	\N
40	22	WEBINAR_ATTEND	Zoom	{"attendance_rate_percent": 95}	2026-09-29 05:17:41.619025+00	2026-09-29 05:17:41.619025+00	crm	demo:22:4	t	\N	\N
41	23	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-28 03:17:41.619025+00	2026-09-28 03:17:41.619025+00	crm	demo:23:0	t	\N	\N
42	24	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-23 06:17:41.619025+00	2026-09-23 06:17:41.619025+00	crm	demo:24:0	t	\N	\N
43	25	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-24 04:17:41.619025+00	2026-09-24 04:17:41.619025+00	crm	demo:25:0	t	\N	\N
44	25	DEMO_REQUEST	Web	{"requested_topic": "Plataforma de Headhunting TI"}	2026-09-25 03:17:41.619025+00	2026-09-25 03:17:41.619025+00	crm	demo:25:1	t	\N	\N
45	25	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-26 01:17:41.619025+00	2026-09-26 01:17:41.619025+00	crm	demo:25:2	t	\N	\N
46	25	EMAIL_CLICK	Email	{"link": "https://plurione.com/agenda-demo"}	2026-09-27 01:17:41.619025+00	2026-09-27 01:17:41.619025+00	crm	demo:25:3	t	\N	\N
47	25	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-28 00:17:41.619025+00	2026-09-28 00:17:41.619025+00	crm	demo:25:4	t	\N	\N
48	26	WEBINAR_ATTEND	Zoom	{"attendance_rate_percent": 95}	2026-09-14 23:17:41.619025+00	2026-09-14 23:17:41.619025+00	crm	demo:26:0	t	\N	\N
49	26	EMAIL_OPEN	Email	{"campaign": "talent_summit_26", "client": "Outlook"}	2026-09-16 01:17:41.619025+00	2026-09-16 01:17:41.619025+00	crm	demo:26:1	t	\N	\N
50	26	CONTENT_DOWNLOAD	Web	{"whitepaper": "Guia_Reclutamiento_TI_2026.pdf"}	2026-09-17 04:17:41.619025+00	2026-09-17 04:17:41.619025+00	crm	demo:26:2	t	\N	\N
51	27	FORM_SUBMIT	Publicación	{"publicacion": "Ay3iCoyK1xoQsdY69xdDVA", "necesidad": "equipo", "necesidad_etiqueta": "Formar un equipo completo", "red": "sin_red", "red_etiqueta": "Sin red", "aviso_aceptado_en": "2026-09-29T22:17:44.380165+00:00"}	2026-09-29 22:17:44.380165+00	2026-09-29 22:17:44.427255+00	pagina_de_interes	Ay3iCoyK1xoQsdY69xdDVA:cf9cfd8319d74990871ce0dad7ea66ca	t	\N	\N
52	28	FORM_SUBMIT	Publicación	{"publicacion": "Ay3iCoyK1xoQsdY69xdDVA", "necesidad": "demo", "necesidad_etiqueta": "Ver una demostraci\\u00f3n", "red": "sin_red", "red_etiqueta": "Sin red", "aviso_aceptado_en": "2026-09-29T22:17:46.720535+00:00"}	2026-09-29 22:17:46.720535+00	2026-09-29 22:17:46.734319+00	pagina_de_interes	Ay3iCoyK1xoQsdY69xdDVA:ff51b86193ff439899e85231545624f7	t	\N	\N
53	29	FORM_SUBMIT	Publicación	{"publicacion": "Ay3iCoyK1xoQsdY69xdDVA", "necesidad": "explorando", "necesidad_etiqueta": "Solo estoy explorando", "red": "sin_red", "red_etiqueta": "Sin red", "aviso_aceptado_en": "2026-09-29T22:17:46.839669+00:00"}	2026-09-29 22:17:46.839669+00	2026-09-29 22:17:46.848162+00	pagina_de_interes	Ay3iCoyK1xoQsdY69xdDVA:2ee2b98f9b844ada8ba2b828c999fc87	t	\N	\N
54	30	FORM_SUBMIT	WhatsApp	{"publicacion": "ZrV9BZf2DKdbuv5cQuLpIQ", "necesidad": "vacantes", "necesidad_etiqueta": "Cubrir vacantes de TI", "red": "whatsapp", "red_etiqueta": "WhatsApp", "aviso_aceptado_en": "2026-10-05T16:10:53.033237+00:00"}	2026-10-05 16:10:53.033237+00	2026-10-05 16:10:53.086875+00	pagina_de_interes	ZrV9BZf2DKdbuv5cQuLpIQ:78bbd86ca1f44af9897ec76bde59c9b9	t	\N	\N
55	30	PHONE_CALL	Teléfono	{"notes": "Primera llamada: quiere cubrir tres vacantes antes de diciembre."}	2026-10-05 16:20:18.450204+00	2026-10-05 16:20:18.450394+00	manual	\N	f	\N	CONECTO
\.


--
-- Data for Name: leads; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.leads (id, first_name, last_name, email, phone, company, job_title, industry, company_size, annual_revenue, country, city, source, status, qualification_status, current_score, score_category, conversion_probability, last_score_update, last_activity_at, assigned_rep_id, campaign_id, raw_metadata, created_at, updated_at, privacy_notice_accepted_at, privacy_notice_source, dormido_desde) FROM stdin;
15	Mariana	Castillo	mariana.c@fintechavanzada.com	+525525835625	FinTech Avanzada S.A.P.I.	CTO	FinTech	201-1000	5000000	México	CDMX	LinkedIn Ads	QUALIFIED	SQL	87.3	HOT	0.87	2026-09-29 10:17:41.619025+00	2026-09-24 22:17:41.619025+00	2	2	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": true, "estimated_hires": 14}	2026-09-26 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
16	Roberto	Garza	rgarza@logisticaglobal.mx	+525550389136	Logística y Transporte Global	Director de Operaciones	Logistics	51-200	2500000	México	Monterrey	Webinar	ENGAGED	MQL	51.6	WARM	0.52	2026-09-29 12:17:41.619025+00	2026-09-24 22:17:41.619025+00	3	3	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 28}	2026-09-11 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
17	Lucía	Fernández	lfernandez@cloudmex.com	+525583259177	Soluciones Cloud México	Head of Engineering	Software/TI	11-50	1200000	México	Guadalajara	Organic Search	ENGAGED	MQL	66	WARM	0.66	2026-09-29 11:17:41.619025+00	2026-09-28 22:17:41.619025+00	4	4	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 42}	2026-09-27 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
18	Fernando	Salinas	fsalinas@gruporetailnorte.com	+525542715205	Grupo Retail del Norte	VP de Recursos Humanos	Retail	1000+	15000000	México	Monterrey	Outbound Cold Email	QUALIFIED	SQL	91.2	HOT	0.91	2026-09-29 15:17:41.619025+00	2026-09-28 22:17:41.619025+00	5	5	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": true, "estimated_hires": 40}	2026-09-22 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
19	Elena	Torres	etorres@saluddigital.com	+525511593762	Salud Digital Innovación	Gerente de Talento TI	Healthcare	51-200	3000000	México	Querétaro	LinkedIn Ads	ENGAGED	MQL	68.6	WARM	0.69	2026-09-29 12:17:41.619025+00	2026-09-26 22:17:41.619025+00	6	2	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 11}	2026-09-13 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
20	Javier	López	jlopez@ecomexpress.mx	+525519518539	E-Commerce Logistics Express	Director General (CEO)	E-Commerce	11-50	900000	México	CDMX	Webinar	NEW	INCOMING	28	COLD	0.28	2026-09-29 21:17:41.619025+00	2026-09-29 22:17:41.619025+00	7	3	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 21}	2026-09-26 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
21	Gabriela	Paz	gpaz@consultoriamex.com	+525530716297	Consultoría Estratégica MX	Socia Directora	Consulting	1-10	400000	México	Puebla	Organic Search	NEW	INCOMING	36.7	COLD	0.37	2026-09-29 17:17:41.619025+00	2026-09-29 22:17:41.619025+00	2	4	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 13}	2026-09-23 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
22	Alejandro	Vargas	avargas@bancocentro.com.mx	+525539653877	Banco Regional del Centro	Chief Information Officer (CIO)	Banking	1000+	25000000	México	CDMX	Outbound Cold Email	QUALIFIED	SQL	87.9	HOT	0.88	2026-09-29 15:17:41.619025+00	2026-09-29 22:17:41.619025+00	3	5	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": true, "estimated_hires": 17}	2026-09-24 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
23	Claudia	Márquez	cmarquez@techconsultores.mx	+525510337533	Soluciones Cloud México	Gerente de Proyectos	Software/TI	11-50	1200000	México	Guadalajara	LinkedIn Ads	NEW	INCOMING	18.1	COLD	0.18	2026-09-29 12:17:41.619025+00	2026-09-27 22:17:41.619025+00	4	2	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 35}	2026-09-27 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
24	Mauricio	Ortiz	mortiz@inretailmex.com	+525526402839	Grupo Retail del Norte	Líder de Reclutamiento	Retail	1000+	15000000	México	Monterrey	Webinar	NEW	INCOMING	17.8	COLD	0.18	2026-09-29 19:17:41.619025+00	2026-09-24 22:17:41.619025+00	5	3	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 45}	2026-09-22 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
25	Patricia	Navarro	pnavarro@fintechavanzada.com	+525557852387	FinTech Avanzada S.A.P.I.	Engineering Manager	FinTech	201-1000	5000000	México	CDMX	Organic Search	QUALIFIED	SQL	90.6	HOT	0.91	2026-09-29 20:17:41.619025+00	2026-09-26 22:17:41.619025+00	6	4	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": true, "estimated_hires": 35}	2026-09-23 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
26	Esteban	Domínguez	edominguez@saluddigital.com	+525579792646	Salud Digital Innovación	Director de Tecnología	Healthcare	51-200	3000000	México	Querétaro	Outbound Cold Email	ENGAGED	MQL	56.6	WARM	0.57	2026-09-29 11:17:41.619025+00	2026-09-28 22:17:41.619025+00	7	5	{"source_device": "Desktop Mac/Windows", "preferred_contact_time": "Ma\\u00f1ana (9:00 - 13:00)", "budget_allocated": false, "estimated_hires": 50}	2026-09-14 22:17:41.619025+00	2026-09-29 22:17:41.619025+00	\N	\N	\N
27	Renata Quintero		renata.quintero@ejemplo-demo.mx	+525511223344	Servicios Digitales del Bajío	Director de Tecnología	Software/TI	51-200	\N	\N	\N	Publicación	NEW	INCOMING	30	COLD	0.2	2026-09-29 22:17:46.62843+00	2026-09-29 22:17:44.42322+00	\N	6	{"perfil_de_linkedin": "https://www.linkedin.com/in/renata-quintero-demo"}	2026-09-29 22:17:44.420174+00	2026-09-29 22:17:46.628441+00	2026-09-29 22:17:44.380165+00	pagina_de_interes	\N
28	Tomás Iriarte		tomas.iriarte@ejemplo-demo.mx	+525522334455	Banca Digital Peninsular	CIO	Banking	1000+	\N	\N	\N	Publicación	NEW	INCOMING	35.1	COLD	0.2516	2026-09-29 22:17:46.777453+00	2026-09-29 22:17:46.731837+00	\N	6	{"perfil_de_linkedin": "https://www.linkedin.com/in/tomas-iriarte-demo"}	2026-09-29 22:17:46.730765+00	2026-09-29 22:17:46.777462+00	2026-09-29 22:17:46.720535+00	pagina_de_interes	\N
29	Ceci Ayala		ceci.ayala@ejemplo-demo.mx	\N	Taller de Software Ayala	Consultor Independiente	Consulting	1-10	\N	\N	\N	Publicación	NEW	INCOMING	18.6	COLD	0.1503	2026-09-29 22:17:46.884656+00	2026-09-29 22:17:46.846378+00	\N	6	{}	2026-09-29 22:17:46.845619+00	2026-09-29 22:17:46.884666+00	2026-09-29 22:17:46.839669+00	pagina_de_interes	\N
30	Lucía Prado		lucia.prado@ejemplo-demo.mx	\N	Fábrica de Software Norte	Head of Engineering	Software/TI	51-200	\N	\N	\N	WhatsApp	WON	INCOMING	34.3	COLD	0.2516	2026-10-05 16:20:18.55242+00	2026-10-05 16:20:18.450204+00	5	8	{"perfil_de_linkedin": "https://linkedin.com/in/lucia-prado-demo"}	2026-10-05 16:10:53.072178+00	2026-10-05 16:21:40.698435+00	2026-10-05 16:10:53.033237+00	pagina_de_interes	\N
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.refresh_tokens (id, jti, family_id, user_id, issued_at, expires_at, revoked_at, revoked_reason, replaced_by_jti, issued_ip) FROM stdin;
3	476548bbfae34adcbac12065abd70a35	cafaa14bd25d463996d5cc54312d375f	2	2026-09-29 22:22:09.826616+00	2026-10-06 22:22:09.826616+00	2026-10-01 15:19:03.71299+00	ROTATED	786a2553e76a49f0914be518c61c2f6f	172.18.0.1
36	786a2553e76a49f0914be518c61c2f6f	cafaa14bd25d463996d5cc54312d375f	2	2026-10-01 15:19:03.71306+00	2026-10-08 15:19:03.71306+00	2026-10-01 20:03:14.556591+00	ROTATED	60dc75bae58e4c89bebfa7ab43cf2257	172.18.0.1
39	10a9fa64e6ac43b192f3796122b81066	46e0404f27f94e70879d847db2923084	3	2026-10-05 15:53:59.76403+00	2026-10-12 15:53:59.76403+00	\N	\N	\N	172.18.0.1
41	d32ad08722654f429a9040c7dfa8eb05	eecc29c9898c4b5e9df5be6a1edc26cd	2	2026-10-05 15:59:51.274383+00	2026-10-12 15:59:51.274383+00	2026-10-05 16:08:41.303504+00	ROTATED	35687e00744b464db6ad98aa2f1ab5b7	172.18.0.1
42	35687e00744b464db6ad98aa2f1ab5b7	eecc29c9898c4b5e9df5be6a1edc26cd	2	2026-10-05 16:08:41.303658+00	2026-10-12 16:08:41.303658+00	2026-10-05 16:11:26.497955+00	ROTATED	843f3b872cb84f6ab62f17b777bc1ee9	172.18.0.1
1	2ffad622cd3f4de8a3250f6b0888c75a	4d1261bd4b70448faf3715ae1632cb43	2	2026-09-29 21:58:39.831952+00	2026-10-06 21:58:39.831952+00	2026-10-05 16:15:26.886451+00	LOGOUT	\N	172.18.0.1
2	cd92f177c6aa488d8b05910646ed7ccf	6404204930994847a782ed75380bd15b	2	2026-09-29 22:18:27.74205+00	2026-10-06 22:18:27.74205+00	2026-10-05 16:15:26.886451+00	LOGOUT	\N	172.18.0.1
37	60dc75bae58e4c89bebfa7ab43cf2257	cafaa14bd25d463996d5cc54312d375f	2	2026-10-01 20:03:14.565845+00	2026-10-08 20:03:14.565845+00	2026-10-05 16:15:26.886451+00	LOGOUT	\N	172.18.0.1
38	9e7865bae5824e08b232def02478bd09	6f604290d47a4fd3b96f18d395f1d4bd	2	2026-10-05 15:53:59.174647+00	2026-10-12 15:53:59.174647+00	2026-10-05 16:15:26.886451+00	LOGOUT	\N	172.18.0.1
43	843f3b872cb84f6ab62f17b777bc1ee9	eecc29c9898c4b5e9df5be6a1edc26cd	2	2026-10-05 16:11:26.498019+00	2026-10-12 16:11:26.498019+00	2026-10-05 16:15:26.886451+00	LOGOUT	\N	172.18.0.1
44	aae0bc6bb75142629ee0b17194efea8a	47cfbd761980438fac74f3673590977e	5	2026-10-05 16:15:37.497146+00	2026-10-12 16:15:37.497146+00	2026-10-05 16:22:18.287245+00	LOGOUT	\N	172.18.0.1
45	bedfa6516e81499499b0a06161e7aaa2	6716ec0ddf7545e2ad8822d052755c07	2	2026-10-05 16:22:29.260352+00	2026-10-12 16:22:29.260352+00	2026-10-05 16:26:15.274586+00	LOGOUT	\N	172.18.0.1
46	b8c4b1ad154f45398f84ba435c4add3a	2580d29cc9f34851ba67b4e32f7bdfa3	1	2026-10-05 16:26:32.587363+00	2026-10-12 16:26:32.587363+00	2026-10-05 17:16:09.106108+00	ROTATED	165c83e21a9b4183bd3f5319f66b0ea1	172.18.0.1
40	03f82e6d73924d10a000779812249ee1	4d7332ec6fb841a292fc0d100ac9c64d	1	2026-10-05 15:54:00.412786+00	2026-10-12 15:54:00.412786+00	2026-10-05 17:16:51.54136+00	LOGOUT	\N	172.18.0.1
47	165c83e21a9b4183bd3f5319f66b0ea1	2580d29cc9f34851ba67b4e32f7bdfa3	1	2026-10-05 17:16:09.10628+00	2026-10-12 17:16:09.10628+00	2026-10-05 17:16:51.54136+00	LOGOUT	\N	172.18.0.1
48	5fabbf871ed04964bbb6844332792db1	ff5e0cc3d5fe4218b5219b715f7c8a1f	2	2026-10-05 17:17:04.266207+00	2026-10-12 17:17:04.266207+00	2026-10-05 17:39:25.892749+00	ROTATED	19f03dfdad674304ae60191772045998	172.18.0.1
49	19f03dfdad674304ae60191772045998	ff5e0cc3d5fe4218b5219b715f7c8a1f	2	2026-10-05 17:39:25.892943+00	2026-10-12 17:39:25.892943+00	\N	\N	\N	172.18.0.1
50	aa9da931734f44f4ad131fd6fb36f042	a3e235da445143999ebe3d8ec9db59ec	2	2026-10-07 02:58:00.681986+00	2026-10-14 02:58:00.681986+00	\N	\N	\N	172.18.0.1
51	65c6906c16044301966f7e695d41ad80	be9bf7739f5f48f08d81ee0714d691a5	2	2026-10-07 03:44:58.860757+00	2026-10-14 03:44:58.860757+00	2026-10-07 03:52:10.024478+00	ROTATED	97f7ae4728e64ded94c5819f5a57f863	172.18.0.1
52	97f7ae4728e64ded94c5819f5a57f863	be9bf7739f5f48f08d81ee0714d691a5	2	2026-10-07 03:52:10.024555+00	2026-10-14 03:52:10.024555+00	\N	\N	\N	172.18.0.1
53	641792b088d3449caf9d06f7da87e2e0	59aac300276c49d7a8c91cdee71cfc0e	2	2026-10-07 04:21:04.139973+00	2026-10-14 04:21:04.139973+00	\N	\N	\N	172.18.0.1
54	2fda483243b94f2bb86c49922fefca72	b0bdaee678c74a8ab5a65702a4facc48	2	2026-10-07 06:16:14.334492+00	2026-10-14 06:16:14.334492+00	\N	\N	\N	172.18.0.1
55	ca9b3d38f1a34a6ebf12b90873ef707c	4205ebd0bc664bec8a493c9fe4d393c0	1	2026-10-10 03:49:49.315204+00	2026-10-17 03:49:49.315204+00	\N	\N	\N	172.18.0.1
\.


--
-- Data for Name: score_histories; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.score_histories (id, lead_id, score, score_category, model_version, ml_probability, heuristic_score, decay_factor, rule_breakdown, ai_explanation, calculated_at, feature_snapshot) FROM stdin;
21	21	36.7	COLD	v1.0.0-hybrid	0.37	14.68	0.95	{"industry_fit": 15, "seniority_fit": 25, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como COLD debido a alta correspondencia de perfil (Cargo: Socia Directora) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Consulting", "Rol con poder de decisi\\u00f3n: Socia Directora"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 17:17:41.619025+00	{}
22	22	87.9	HOT	v1.0.0-hybrid	0.88	35.16	0.95	{"industry_fit": 25, "seniority_fit": 25, "company_size_fit": 20, "engagement_velocity": 15}	{"summary": "Prospecto calificado como HOT debido a alta correspondencia de perfil (Cargo: Chief Information Officer (CIO)) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Banking", "Rol con poder de decisi\\u00f3n: Chief Information Officer (CIO)"], "recommended_action": "Asignar de inmediato a llamada exploratoria de 15 minutos con ejecutivo senior."}	2026-09-29 15:17:41.619025+00	{}
15	15	87.3	HOT	v1.0.0-hybrid	0.87	34.92	0.95	{"industry_fit": 25, "seniority_fit": 25, "company_size_fit": 20, "engagement_velocity": 15}	{"summary": "Prospecto calificado como HOT debido a alta correspondencia de perfil (Cargo: CTO) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: FinTech", "Rol con poder de decisi\\u00f3n: CTO"], "recommended_action": "Asignar de inmediato a llamada exploratoria de 15 minutos con ejecutivo senior."}	2026-09-29 10:17:41.619025+00	{}
16	16	51.6	WARM	v1.0.0-hybrid	0.52	20.64	0.95	{"industry_fit": 15, "seniority_fit": 25, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como WARM debido a alta correspondencia de perfil (Cargo: Director de Operaciones) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Logistics", "Rol con poder de decisi\\u00f3n: Director de Operaciones"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 12:17:41.619025+00	{}
17	17	66	WARM	v1.0.0-hybrid	0.66	26.4	0.95	{"industry_fit": 25, "seniority_fit": 12, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como WARM debido a alta correspondencia de perfil (Cargo: Head of Engineering) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Software/TI", "Rol con poder de decisi\\u00f3n: Head of Engineering"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 11:17:41.619025+00	{}
18	18	91.2	HOT	v1.0.0-hybrid	0.91	36.48	0.95	{"industry_fit": 15, "seniority_fit": 25, "company_size_fit": 20, "engagement_velocity": 15}	{"summary": "Prospecto calificado como HOT debido a alta correspondencia de perfil (Cargo: VP de Recursos Humanos) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Retail", "Rol con poder de decisi\\u00f3n: VP de Recursos Humanos"], "recommended_action": "Asignar de inmediato a llamada exploratoria de 15 minutos con ejecutivo senior."}	2026-09-29 15:17:41.619025+00	{}
19	19	68.6	WARM	v1.0.0-hybrid	0.69	27.44	0.95	{"industry_fit": 15, "seniority_fit": 12, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como WARM debido a alta correspondencia de perfil (Cargo: Gerente de Talento TI) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Healthcare", "Rol con poder de decisi\\u00f3n: Gerente de Talento TI"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 12:17:41.619025+00	{}
20	20	28	COLD	v1.0.0-hybrid	0.28	11.2	0.95	{"industry_fit": 15, "seniority_fit": 25, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como COLD debido a alta correspondencia de perfil (Cargo: Director General (CEO)) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: E-Commerce", "Rol con poder de decisi\\u00f3n: Director General (CEO)"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 21:17:41.619025+00	{}
23	23	18.1	COLD	v1.0.0-hybrid	0.18	7.24	0.95	{"industry_fit": 25, "seniority_fit": 12, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como COLD debido a alta correspondencia de perfil (Cargo: Gerente de Proyectos) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Software/TI", "Rol con poder de decisi\\u00f3n: Gerente de Proyectos"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 12:17:41.619025+00	{}
24	24	17.8	COLD	v1.0.0-hybrid	0.18	7.12	0.95	{"industry_fit": 15, "seniority_fit": 12, "company_size_fit": 20, "engagement_velocity": 15}	{"summary": "Prospecto calificado como COLD debido a alta correspondencia de perfil (Cargo: L\\u00edder de Reclutamiento) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Retail", "Rol con poder de decisi\\u00f3n: L\\u00edder de Reclutamiento"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 19:17:41.619025+00	{}
25	25	90.6	HOT	v1.0.0-hybrid	0.91	36.24	0.95	{"industry_fit": 25, "seniority_fit": 12, "company_size_fit": 20, "engagement_velocity": 15}	{"summary": "Prospecto calificado como HOT debido a alta correspondencia de perfil (Cargo: Engineering Manager) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: FinTech", "Rol con poder de decisi\\u00f3n: Engineering Manager"], "recommended_action": "Asignar de inmediato a llamada exploratoria de 15 minutos con ejecutivo senior."}	2026-09-29 20:17:41.619025+00	{}
26	26	56.6	WARM	v1.0.0-hybrid	0.57	22.64	0.95	{"industry_fit": 15, "seniority_fit": 25, "company_size_fit": 10, "engagement_velocity": 15}	{"summary": "Prospecto calificado como WARM debido a alta correspondencia de perfil (Cargo: Director de Tecnolog\\u00eda) y recurrencia de interacciones digitales.", "strengths": ["Sector de alto valor: Healthcare", "Rol con poder de decisi\\u00f3n: Director de Tecnolog\\u00eda"], "recommended_action": "Nutrir con secuencia de emails de casos de \\u00e9xito."}	2026-09-29 11:17:41.619025+00	{}
27	27	30	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.2	45	1	{"title_fit_score": 25.0, "industry_fit_score": 15.0, "company_size_fit_score": 5.0, "firmographic_total": 45.0, "behavior_raw_total": 0.0, "decay_factor": 1.0, "behavior_decayed_total": 0.0, "heuristic_total": 45.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 30.0/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Cargo con alto poder de decisi\\u00f3n t\\u00e9cnica en el \\u00e1rea (Director de Tecnolog\\u00eda).", "Industria prioritaria de alta demanda para PluriOne (Software/TI)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-09-29 22:17:46.628463+00	{"job_title": "Director de Tecnolog\\u00eda", "industry": "Software/TI", "company_size": "51-200", "annual_revenue": null, "source_channel": "Publicaci\\u00f3n", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 0, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 2.472524305555556e-05, "custom_metadata": {"perfil_de_linkedin": "https://www.linkedin.com/in/renata-quintero-demo"}, "version_del_vector": 2}
28	28	35.1	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.2516	50	1	{"title_fit_score": 25.0, "industry_fit_score": 15.0, "company_size_fit_score": 10.0, "firmographic_total": 50.0, "behavior_raw_total": 0.0, "decay_factor": 1.0, "behavior_decayed_total": 0.0, "heuristic_total": 50.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 35.1/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Cargo con alto poder de decisi\\u00f3n t\\u00e9cnica en el \\u00e1rea (CIO).", "Industria prioritaria de alta demanda para PluriOne (Banking)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-09-29 22:17:46.777477+00	{"job_title": "CIO", "industry": "Banking", "company_size": "1000+", "annual_revenue": null, "source_channel": "Publicaci\\u00f3n", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 0, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 1.2605324074074074e-07, "custom_metadata": {"perfil_de_linkedin": "https://www.linkedin.com/in/tomas-iriarte-demo"}, "version_del_vector": 2}
29	29	18.6	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.1503	24	1	{"title_fit_score": 7.0, "industry_fit_score": 15.0, "company_size_fit_score": 2.0, "firmographic_total": 24.0, "behavior_raw_total": 0.0, "decay_factor": 1.0, "behavior_decayed_total": 0.0, "heuristic_total": 24.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 18.6/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Industria prioritaria de alta demanda para PluriOne (Consulting)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-09-29 22:17:46.88468+00	{"job_title": "Consultor Independiente", "industry": "Consulting", "company_size": "1-10", "annual_revenue": null, "source_channel": "Publicaci\\u00f3n", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 0, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 9.324074074074075e-08, "custom_metadata": {}, "version_del_vector": 2}
30	30	27.8	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.1969	40	1	{"title_fit_score": 20.0, "industry_fit_score": 15.0, "company_size_fit_score": 5.0, "firmographic_total": 40.0, "behavior_raw_total": 0.0, "decay_factor": 1.0, "behavior_decayed_total": 0.0, "heuristic_total": 40.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 27.8/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Cargo con alto poder de decisi\\u00f3n t\\u00e9cnica en el \\u00e1rea (Head of Engineering).", "Industria prioritaria de alta demanda para PluriOne (Software/TI)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-10-05 16:10:53.220369+00	{"job_title": "Head of Engineering", "industry": "Software/TI", "company_size": "51-200", "annual_revenue": null, "source_channel": "WhatsApp", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 0, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 3.861226851851852e-07, "custom_metadata": {"perfil_de_linkedin": "https://linkedin.com/in/lucia-prado-demo"}, "version_del_vector": 2}
31	30	27.8	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.1969	40	0.9999	{"title_fit_score": 20.0, "industry_fit_score": 15.0, "company_size_fit_score": 5.0, "firmographic_total": 40.0, "behavior_raw_total": 0.0, "decay_factor": 0.9999, "behavior_decayed_total": 0.0, "heuristic_total": 40.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 27.8/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Cargo con alto poder de decisi\\u00f3n t\\u00e9cnica en el \\u00e1rea (Head of Engineering).", "Industria prioritaria de alta demanda para PluriOne (Software/TI)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-10-05 16:14:55.106976+00	{"job_title": "Head of Engineering", "industry": "Software/TI", "company_size": "51-200", "annual_revenue": null, "source_channel": "WhatsApp", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 0, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 0.002800813726851852, "custom_metadata": {"perfil_de_linkedin": "https://linkedin.com/in/lucia-prado-demo"}, "version_del_vector": 2}
32	30	34.3	COLD	v1.0.0-hybrid+ml:98ed8bd1	0.2516	48	1	{"title_fit_score": 20.0, "industry_fit_score": 15.0, "company_size_fit_score": 5.0, "firmographic_total": 40.0, "behavior_raw_total": 8.0, "decay_factor": 1.0, "behavior_decayed_total": 8.0, "heuristic_total": 48.0}	{"summary": "Prospecto de baja prioridad o en etapa exploratoria temprana (Score: 34.3/100). Actualmente no cumple los criterios clave de decisi\\u00f3n inmediata.", "strengths": ["Cargo con alto poder de decisi\\u00f3n t\\u00e9cnica en el \\u00e1rea (Head of Engineering).", "Industria prioritaria de alta demanda para PluriOne (Software/TI)."], "recommended_action": "Mantener en campa\\u00f1as generales de branding y newsletters mensuales. Revaluar autom\\u00e1ticamente si se detectan nuevas visitas a p\\u00e1ginas de cotizaci\\u00f3n.", "engine": "PluriOne_XAI_Engine", "model_deployment": "XAI_Deterministic_Synthesizer_v1"}	2026-10-05 16:20:18.552444+00	{"job_title": "Head of Engineering", "industry": "Software/TI", "company_size": "51-200", "annual_revenue": null, "source_channel": "WhatsApp", "page_views": 0, "email_opens": 0, "email_clicks": 0, "content_downloads": 0, "attended_webinar": 0, "requested_demo": 0, "proposal_sent": 0, "meeting_scheduled": 0, "phone_calls_connected": 1, "phone_calls_unanswered": 0, "whatsapp_messages": 0, "linkedin_messages": 0, "custom_events": 0, "days_since_last_activity": 2.4519675925925926e-07, "custom_metadata": {"perfil_de_linkedin": "https://linkedin.com/in/lucia-prado-demo"}, "version_del_vector": 2}
\.


--
-- Data for Name: score_history_monthly; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.score_history_monthly (id, lead_id, month, scores_count, score_sum, score_min, score_max, first_score, first_calculated_at, last_score, last_category, last_calculated_at, category_counts, model_versions, aggregated_at) FROM stdin;
\.


--
-- Data for Name: scoring_jobs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scoring_jobs (id, job_type, status, total_leads, processed_leads, failed_leads, batch_size, requested_by, error_message, created_at, started_at, finished_at, lease_until, heartbeat_at, worker_id, lease_key) FROM stdin;
\.


--
-- Data for Name: tareas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tareas (id, lead_id, asesor_id, regla, clave, estado, vence_el, motivo, datos, creada_en, cerrada_en, cerrada_por_id) FROM stdin;
1	15	2	primer_contacto	2	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 87.3}	2026-09-29 22:20:05.938932+00	\N	\N
2	16	3	primer_contacto	3	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 51.6}	2026-09-29 22:20:05.938932+00	\N	\N
3	17	4	primer_contacto	4	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 66.0}	2026-09-29 22:20:05.938932+00	\N	\N
4	18	5	primer_contacto	5	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 91.2}	2026-09-29 22:20:05.938932+00	\N	\N
5	19	6	primer_contacto	6	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 68.6}	2026-09-29 22:20:05.938932+00	\N	\N
6	20	7	primer_contacto	7	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 28.0}	2026-09-29 22:20:05.938932+00	\N	\N
7	21	2	primer_contacto	2	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 36.7}	2026-09-29 22:20:05.938932+00	\N	\N
8	22	3	primer_contacto	3	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 87.9}	2026-09-29 22:20:05.938932+00	\N	\N
9	23	4	primer_contacto	4	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 18.1}	2026-09-29 22:20:05.938932+00	\N	\N
10	24	5	primer_contacto	5	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 17.8}	2026-09-29 22:20:05.938932+00	\N	\N
11	25	6	primer_contacto	6	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 90.6}	2026-09-29 22:20:05.938932+00	\N	\N
12	26	7	primer_contacto	7	abierta	2026-09-30 22:20:05.938932+00	Asignado y todavía sin contactar.	{"score": 56.6}	2026-09-29 22:20:05.938932+00	\N	\N
\.


--
-- Data for Name: unmatched_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.unmatched_events (id, source, external_event_id, activity_type, channel, direction, call_outcome, contact_email, contact_phone, contact_name, occurred_at, received_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, email, hashed_password, full_name, role, is_active, token_version, last_login_at, created_at, updated_at, is_sales_rep, phone, capacity, password_changed_at, must_change_password, totp_sal, totp_activo, totp_activado_en, totp_codigos_de_recuperacion, totp_ultimo_contador) FROM stdin;
6	valeria.mendoza@plurione.com	$2b$12$xdXaqAIwBYNgBmD6UaBteOsUwC/Af7oJrfK8y05tkHpdYsNdexh.C	Valeria Mendoza	Commercial_Executive	t	3	\N	2026-09-29 21:58:07.069473+00	2026-10-07 02:57:50.101451+00	t	+52 55 3456 7890	50	2026-09-29 21:58:07.069471+00	f	\N	f	\N	\N	\N
7	diego.herrera@plurione.com	$2b$12$RbhF9i.rcd5txXGfFKa7ROqcARkQv8fe7XHmoehw34Xk6WhHa.BSC	Diego Herrera	Commercial_Executive	t	3	\N	2026-09-29 21:58:07.069476+00	2026-10-07 02:57:50.101453+00	t	+52 55 4567 8901	80	2026-09-29 21:58:07.069475+00	f	\N	f	\N	\N	\N
2	lider.ventas@plurione.com	$2b$12$cv7zIhy0pRFY/ZNZzcCqMeJJGuvjtsg/2GBYAhi5/lBZ2q3B6Ig7G	Ricardo Peñaloza Gómez	Sales_Lead	t	5	2026-10-07 06:16:14.312083+00	2026-09-29 21:58:07.069457+00	2026-10-07 06:16:14.314542+00	t	\N	40	2026-09-29 21:58:07.069455+00	f	\N	f	\N	\N	\N
3	asesor.comercial@plurione.com	$2b$12$a8DNp83Euu5cw8IywgbYa.LL8VU7gd76ncSXK/ftnnJHiQh2vj3/i	Alejandro Morales	Commercial_Executive	t	3	2026-10-05 15:53:59.746953+00	2026-09-29 21:58:07.069462+00	2026-10-07 02:57:50.101446+00	t	\N	50	2026-09-29 21:58:07.06946+00	f	\N	f	\N	\N	\N
1	admin.ti@plurione.com	$2b$12$hi/1XHT/Sc8tjLRskkzZceyUoPam3uy348F7Cpd/UsKzJJGOzSnE.	Mónica Arredondo Vela	System_Admin	t	4	2026-10-10 03:49:49.275319+00	2026-09-29 21:58:07.06945+00	2026-10-10 03:49:49.293558+00	f	\N	\N	2026-09-29 21:58:07.069436+00	f	\N	f	\N	\N	\N
4	carlos.morales@plurione.com	$2b$12$ujSKIUDLYjRQjRMYn5OQKuIDOUeOOJmrfNKT0/JfDYqY9lMiSI1u2	Carlos Morales	Commercial_Executive	t	3	\N	2026-09-29 21:58:07.069465+00	2026-10-07 02:57:50.101448+00	t	+52 55 1234 5678	60	2026-09-29 21:58:07.069464+00	f	\N	f	\N	\N	\N
5	ana.ruiz@plurione.com	$2b$12$ypY./sPG/OC25nbWoJzhruDdyCg8IAJGc7VIFUuaaLV/gwU11Zj1S	Ana Sofía Ruiz	Commercial_Executive	t	4	2026-10-05 16:15:37.477294+00	2026-09-29 21:58:07.069469+00	2026-10-07 02:57:50.10145+00	t	+52 55 2345 6789	40	2026-09-29 21:58:07.069468+00	f	\N	f	\N	\N	\N
\.


--
-- Data for Name: visitas_de_publicacion; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.visitas_de_publicacion (campaign_id, dia, red, visitas) FROM stdin;
6	2026-09-29	sin_red	12
8	2026-10-05	whatsapp	1
8	2026-10-05	sin_red	2
8	2026-10-05	linkedin	2
\.


--
-- Data for Name: webhook_deliveries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.webhook_deliveries (id, signature, idempotency_key, crm_platform, event, external_lead_id, lead_id, response_data, received_at, expires_at) FROM stdin;
\.


--
-- Name: audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.audit_log_id_seq', 423, true);


--
-- Name: avisos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.avisos_id_seq', 137, true);


--
-- Name: campaigns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.campaigns_id_seq', 9, true);


--
-- Name: crm_integration_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.crm_integration_logs_id_seq', 12, true);


--
-- Name: desenlaces_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.desenlaces_id_seq', 1, true);


--
-- Name: lead_activities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.lead_activities_id_seq', 56, true);


--
-- Name: leads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.leads_id_seq', 31, true);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.refresh_tokens_id_seq', 55, true);


--
-- Name: score_histories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.score_histories_id_seq', 33, true);


--
-- Name: score_history_monthly_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.score_history_monthly_id_seq', 1, false);


--
-- Name: tareas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tareas_id_seq', 190, true);


--
-- Name: unmatched_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.unmatched_events_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 7, true);


--
-- Name: webhook_deliveries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.webhook_deliveries_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: campaigns campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT campaigns_pkey PRIMARY KEY (id);


--
-- Name: crm_integration_logs crm_integration_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_integration_logs
    ADD CONSTRAINT crm_integration_logs_pkey PRIMARY KEY (id);


--
-- Name: lead_activities lead_activities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lead_activities
    ADD CONSTRAINT lead_activities_pkey PRIMARY KEY (id);


--
-- Name: leads leads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_pkey PRIMARY KEY (id);


--
-- Name: avisos pk_avisos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos
    ADD CONSTRAINT pk_avisos PRIMARY KEY (id);


--
-- Name: desenlaces pk_desenlaces; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.desenlaces
    ADD CONSTRAINT pk_desenlaces PRIMARY KEY (id);


--
-- Name: tareas pk_tareas; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tareas
    ADD CONSTRAINT pk_tareas PRIMARY KEY (id);


--
-- Name: visitas_de_publicacion pk_visitas_de_publicacion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitas_de_publicacion
    ADD CONSTRAINT pk_visitas_de_publicacion PRIMARY KEY (campaign_id, dia, red);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: score_histories score_histories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_histories
    ADD CONSTRAINT score_histories_pkey PRIMARY KEY (id);


--
-- Name: score_history_monthly score_history_monthly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_history_monthly
    ADD CONSTRAINT score_history_monthly_pkey PRIMARY KEY (id);


--
-- Name: scoring_jobs scoring_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scoring_jobs
    ADD CONSTRAINT scoring_jobs_pkey PRIMARY KEY (id);


--
-- Name: unmatched_events unmatched_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unmatched_events
    ADD CONSTRAINT unmatched_events_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: webhook_deliveries webhook_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_deliveries
    ADD CONSTRAINT webhook_deliveries_pkey PRIMARY KEY (id);


--
-- Name: idx_activity_lead_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_lead_time ON public.lead_activities USING btree (lead_id, occurred_at);


--
-- Name: idx_audit_actor_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_actor_time ON public.audit_log USING btree (actor_email, occurred_at);


--
-- Name: idx_audit_entity_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_entity_time ON public.audit_log USING btree (entity, entity_id, occurred_at);


--
-- Name: idx_avisos_usuario_leido_creado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_avisos_usuario_leido_creado ON public.avisos USING btree (usuario_id, leido_en, creado_en);


--
-- Name: idx_desenlaces_cerrado_resultado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_desenlaces_cerrado_resultado ON public.desenlaces USING btree (cerrado_el, resultado);


--
-- Name: idx_leads_created_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leads_created_score ON public.leads USING btree (created_at, current_score);


--
-- Name: idx_leads_rep_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leads_rep_score ON public.leads USING btree (assigned_rep_id, current_score);


--
-- Name: idx_leads_score_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leads_score_status ON public.leads USING btree (score_category, status);


--
-- Name: idx_refresh_family_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_family_user ON public.refresh_tokens USING btree (family_id, user_id);


--
-- Name: idx_score_history_lead_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_score_history_lead_time ON public.score_histories USING btree (lead_id, calculated_at);


--
-- Name: idx_tareas_asesor_estado_vence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tareas_asesor_estado_vence ON public.tareas USING btree (asesor_id, estado, vence_el);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_action ON public.audit_log USING btree (action);


--
-- Name: ix_audit_log_actor_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_actor_email ON public.audit_log USING btree (actor_email);


--
-- Name: ix_audit_log_actor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_actor_id ON public.audit_log USING btree (actor_id);


--
-- Name: ix_audit_log_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_entity ON public.audit_log USING btree (entity);


--
-- Name: ix_audit_log_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_entity_id ON public.audit_log USING btree (entity_id);


--
-- Name: ix_audit_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_id ON public.audit_log USING btree (id);


--
-- Name: ix_audit_log_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_occurred_at ON public.audit_log USING btree (occurred_at);


--
-- Name: ix_audit_log_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_outcome ON public.audit_log USING btree (outcome);


--
-- Name: ix_avisos_creado_en; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_avisos_creado_en ON public.avisos USING btree (creado_en);


--
-- Name: ix_avisos_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_avisos_id ON public.avisos USING btree (id);


--
-- Name: ix_avisos_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_avisos_lead_id ON public.avisos USING btree (lead_id);


--
-- Name: ix_avisos_regla; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_avisos_regla ON public.avisos USING btree (regla);


--
-- Name: ix_avisos_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_avisos_usuario_id ON public.avisos USING btree (usuario_id);


--
-- Name: ix_campaigns_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campaigns_id ON public.campaigns USING btree (id);


--
-- Name: ix_campaigns_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_campaigns_name ON public.campaigns USING btree (name);


--
-- Name: ix_crm_integration_logs_external_crm_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crm_integration_logs_external_crm_id ON public.crm_integration_logs USING btree (external_crm_id);


--
-- Name: ix_crm_integration_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crm_integration_logs_id ON public.crm_integration_logs USING btree (id);


--
-- Name: ix_crm_integration_logs_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crm_integration_logs_lead_id ON public.crm_integration_logs USING btree (lead_id);


--
-- Name: ix_crm_integration_logs_synced_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crm_integration_logs_synced_at ON public.crm_integration_logs USING btree (synced_at);


--
-- Name: ix_desenlaces_categoria_al_cierre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_desenlaces_categoria_al_cierre ON public.desenlaces USING btree (categoria_al_cierre);


--
-- Name: ix_desenlaces_cerrado_el; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_desenlaces_cerrado_el ON public.desenlaces USING btree (cerrado_el);


--
-- Name: ix_desenlaces_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_desenlaces_id ON public.desenlaces USING btree (id);


--
-- Name: ix_desenlaces_motivo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_desenlaces_motivo ON public.desenlaces USING btree (motivo);


--
-- Name: ix_desenlaces_resultado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_desenlaces_resultado ON public.desenlaces USING btree (resultado);


--
-- Name: ix_lead_activities_activity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lead_activities_activity_type ON public.lead_activities USING btree (activity_type);


--
-- Name: ix_lead_activities_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lead_activities_id ON public.lead_activities USING btree (id);


--
-- Name: ix_lead_activities_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lead_activities_lead_id ON public.lead_activities USING btree (lead_id);


--
-- Name: ix_lead_activities_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_lead_activities_occurred_at ON public.lead_activities USING btree (occurred_at);


--
-- Name: ix_leads_assigned_rep_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_assigned_rep_id ON public.leads USING btree (assigned_rep_id);


--
-- Name: ix_leads_campaign_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_campaign_id ON public.leads USING btree (campaign_id);


--
-- Name: ix_leads_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_company ON public.leads USING btree (company);


--
-- Name: ix_leads_current_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_current_score ON public.leads USING btree (current_score);


--
-- Name: ix_leads_dormido_desde; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_dormido_desde ON public.leads USING btree (dormido_desde);


--
-- Name: ix_leads_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_leads_email ON public.leads USING btree (email);


--
-- Name: ix_leads_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_id ON public.leads USING btree (id);


--
-- Name: ix_leads_industry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_industry ON public.leads USING btree (industry);


--
-- Name: ix_leads_qualification_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_qualification_status ON public.leads USING btree (qualification_status);


--
-- Name: ix_leads_score_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_score_category ON public.leads USING btree (score_category);


--
-- Name: ix_leads_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_leads_status ON public.leads USING btree (status);


--
-- Name: ix_refresh_tokens_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens USING btree (expires_at);


--
-- Name: ix_refresh_tokens_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_family_id ON public.refresh_tokens USING btree (family_id);


--
-- Name: ix_refresh_tokens_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_id ON public.refresh_tokens USING btree (id);


--
-- Name: ix_refresh_tokens_jti; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_refresh_tokens_jti ON public.refresh_tokens USING btree (jti);


--
-- Name: ix_refresh_tokens_revoked_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_revoked_at ON public.refresh_tokens USING btree (revoked_at);


--
-- Name: ix_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: ix_score_histories_calculated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_histories_calculated_at ON public.score_histories USING btree (calculated_at);


--
-- Name: ix_score_histories_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_histories_id ON public.score_histories USING btree (id);


--
-- Name: ix_score_histories_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_histories_lead_id ON public.score_histories USING btree (lead_id);


--
-- Name: ix_score_history_monthly_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_score_history_monthly_id ON public.score_history_monthly USING btree (id);


--
-- Name: ix_scoring_jobs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_scoring_jobs_created_at ON public.scoring_jobs USING btree (created_at);


--
-- Name: ix_scoring_jobs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_scoring_jobs_id ON public.scoring_jobs USING btree (id);


--
-- Name: ix_scoring_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_scoring_jobs_status ON public.scoring_jobs USING btree (status);


--
-- Name: ix_tareas_asesor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_asesor_id ON public.tareas USING btree (asesor_id);


--
-- Name: ix_tareas_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_estado ON public.tareas USING btree (estado);


--
-- Name: ix_tareas_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_id ON public.tareas USING btree (id);


--
-- Name: ix_tareas_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_lead_id ON public.tareas USING btree (lead_id);


--
-- Name: ix_tareas_regla; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_regla ON public.tareas USING btree (regla);


--
-- Name: ix_tareas_vence_el; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tareas_vence_el ON public.tareas USING btree (vence_el);


--
-- Name: ix_unmatched_events_contact_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unmatched_events_contact_email ON public.unmatched_events USING btree (contact_email);


--
-- Name: ix_unmatched_events_contact_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unmatched_events_contact_phone ON public.unmatched_events USING btree (contact_phone);


--
-- Name: ix_unmatched_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unmatched_events_id ON public.unmatched_events USING btree (id);


--
-- Name: ix_unmatched_events_received_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_unmatched_events_received_at ON public.unmatched_events USING btree (received_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_is_sales_rep; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_is_sales_rep ON public.users USING btree (is_sales_rep);


--
-- Name: ix_webhook_deliveries_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_deliveries_expires_at ON public.webhook_deliveries USING btree (expires_at);


--
-- Name: ix_webhook_deliveries_external_lead_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_deliveries_external_lead_id ON public.webhook_deliveries USING btree (external_lead_id);


--
-- Name: ix_webhook_deliveries_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_deliveries_id ON public.webhook_deliveries USING btree (id);


--
-- Name: ix_webhook_deliveries_idempotency_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_webhook_deliveries_idempotency_key ON public.webhook_deliveries USING btree (idempotency_key);


--
-- Name: ix_webhook_deliveries_signature; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_webhook_deliveries_signature ON public.webhook_deliveries USING btree (signature);


--
-- Name: uq_avisos_usuario_regla_lead_clave; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_avisos_usuario_regla_lead_clave ON public.avisos USING btree (usuario_id, regla, lead_id, clave);


--
-- Name: uq_campaigns_public_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_campaigns_public_slug ON public.campaigns USING btree (public_slug);


--
-- Name: uq_desenlaces_lead; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_desenlaces_lead ON public.desenlaces USING btree (lead_id);


--
-- Name: uq_lead_activities_source_external_event; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_lead_activities_source_external_event ON public.lead_activities USING btree (source, external_event_id);


--
-- Name: uq_score_history_monthly_lead_month; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_score_history_monthly_lead_month ON public.score_history_monthly USING btree (lead_id, month);


--
-- Name: uq_scoring_jobs_lease_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_scoring_jobs_lease_key ON public.scoring_jobs USING btree (lease_key);


--
-- Name: uq_tareas_regla_lead_clave; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tareas_regla_lead_clave ON public.tareas USING btree (regla, lead_id, clave);


--
-- Name: uq_unmatched_events_source_external_event; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_unmatched_events_source_external_event ON public.unmatched_events USING btree (source, external_event_id);


--
-- Name: crm_integration_logs crm_integration_logs_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_integration_logs
    ADD CONSTRAINT crm_integration_logs_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: avisos fk_avisos_lead_id_leads; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos
    ADD CONSTRAINT fk_avisos_lead_id_leads FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: avisos fk_avisos_usuario_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos
    ADD CONSTRAINT fk_avisos_usuario_id_users FOREIGN KEY (usuario_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: campaigns fk_campaigns_responsable_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.campaigns
    ADD CONSTRAINT fk_campaigns_responsable_id_users FOREIGN KEY (responsable_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: desenlaces fk_desenlaces_lead_id_leads; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.desenlaces
    ADD CONSTRAINT fk_desenlaces_lead_id_leads FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: desenlaces fk_desenlaces_registrado_por_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.desenlaces
    ADD CONSTRAINT fk_desenlaces_registrado_por_id_users FOREIGN KEY (registrado_por_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: desenlaces fk_desenlaces_score_history_id_score_histories; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.desenlaces
    ADD CONSTRAINT fk_desenlaces_score_history_id_score_histories FOREIGN KEY (score_history_id) REFERENCES public.score_histories(id) ON DELETE SET NULL;


--
-- Name: leads fk_leads_assigned_rep_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT fk_leads_assigned_rep_id_users FOREIGN KEY (assigned_rep_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: tareas fk_tareas_asesor_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tareas
    ADD CONSTRAINT fk_tareas_asesor_id_users FOREIGN KEY (asesor_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tareas fk_tareas_cerrada_por_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tareas
    ADD CONSTRAINT fk_tareas_cerrada_por_id_users FOREIGN KEY (cerrada_por_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: tareas fk_tareas_lead_id_leads; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tareas
    ADD CONSTRAINT fk_tareas_lead_id_leads FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: visitas_de_publicacion fk_visitas_de_publicacion_campaign_id_campaigns; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visitas_de_publicacion
    ADD CONSTRAINT fk_visitas_de_publicacion_campaign_id_campaigns FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE CASCADE;


--
-- Name: lead_activities lead_activities_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lead_activities
    ADD CONSTRAINT lead_activities_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: leads leads_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leads
    ADD CONSTRAINT leads_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.campaigns(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: score_histories score_histories_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_histories
    ADD CONSTRAINT score_histories_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: score_history_monthly score_history_monthly_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.score_history_monthly
    ADD CONSTRAINT score_history_monthly_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;


--
-- Name: webhook_deliveries webhook_deliveries_lead_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_deliveries
    ADD CONSTRAINT webhook_deliveries_lead_id_fkey FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 6dROPHzveH8gbRfl9FJxJLmgmSBdYIzjygeNlGc3oEuIR7T1d5blub2l4i8vMI8

