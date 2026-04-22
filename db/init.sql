-- ============================================================
-- Space Hazard Tracker — Database Schema
-- ============================================================

-- Base de datos para Airflow
CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;

-- Astronomy Picture of the Day
CREATE TABLE IF NOT EXISTS apod (
    id          SERIAL PRIMARY KEY,
    apod_date   DATE        NOT NULL UNIQUE,
    title       TEXT        NOT NULL,
    explanation TEXT,
    url         TEXT,
    hdurl       TEXT,
    media_type  VARCHAR(20),
    copyright   TEXT,
    fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Near Earth Objects (asteroids)
CREATE TABLE IF NOT EXISTS neo_asteroids (
    id                       SERIAL PRIMARY KEY,
    nasa_id                  VARCHAR(50)  NOT NULL,
    name                     TEXT         NOT NULL,
    close_approach_date      DATE         NOT NULL,
    absolute_magnitude       NUMERIC(6,2),
    estimated_diam_min_km    NUMERIC(10,4),
    estimated_diam_max_km    NUMERIC(10,4),
    is_potentially_hazardous BOOLEAN      DEFAULT FALSE,
    miss_distance_km         NUMERIC(18,2),
    miss_distance_lunar      NUMERIC(10,4),
    relative_velocity_kmh    NUMERIC(14,2),
    orbiting_body            VARCHAR(20),
    risk_level               VARCHAR(10),
    fetched_at               TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (nasa_id, close_approach_date)
);

-- Earth natural events (EONET)
CREATE TABLE IF NOT EXISTS earth_events (
    id              SERIAL PRIMARY KEY,
    event_id        VARCHAR(50)  NOT NULL UNIQUE,
    title           TEXT         NOT NULL,
    description     TEXT,
    category        VARCHAR(100),
    category_id     VARCHAR(50),
    status          VARCHAR(20),
    geometry_date   TIMESTAMPTZ,
    longitude       NUMERIC(10,6),
    latitude        NUMERIC(10,6),
    magnitude_value NUMERIC(10,2),
    magnitude_unit  VARCHAR(20),
    sources         TEXT,
    fetched_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- ETL run log
CREATE TABLE IF NOT EXISTS etl_runs (
    id          SERIAL PRIMARY KEY,
    run_date    DATE        NOT NULL,
    pipeline    VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL,
    records_in  INTEGER     DEFAULT 0,
    records_out INTEGER     DEFAULT 0,
    error_msg   TEXT,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Indexes para queries rápidas en el dashboard
CREATE INDEX IF NOT EXISTS idx_neo_date      ON neo_asteroids(close_approach_date);
CREATE INDEX IF NOT EXISTS idx_neo_hazardous ON neo_asteroids(is_potentially_hazardous);
CREATE INDEX IF NOT EXISTS idx_neo_risk      ON neo_asteroids(risk_level);
CREATE INDEX IF NOT EXISTS idx_events_cat    ON earth_events(category);
CREATE INDEX IF NOT EXISTS idx_events_status ON earth_events(status);
CREATE INDEX IF NOT EXISTS idx_events_coords ON earth_events(longitude, latitude);