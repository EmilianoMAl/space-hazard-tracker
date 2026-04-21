"""
load.py — Space Hazard Tracker
Guarda los datos transformados en PostgreSQL (upsert idempotente).
"""

import os
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def _get_conn():
    """Crea una conexión a PostgreSQL usando las variables del .env"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "nasa_tracker"),
        user=os.getenv("DB_USER", "nasa"),
        password=os.getenv("DB_PASSWORD", "nasa123"),
    )


@contextmanager
def _cursor():
    """
    Context manager — abre conexión, da el cursor,
    hace commit automático y cierra aunque haya error.
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_apod(apod: dict) -> int:
    sql = """
        INSERT INTO apod
            (apod_date, title, explanation, url, hdurl, media_type, copyright)
        VALUES
            (%(date)s, %(title)s, %(explanation)s, %(url)s,
             %(hdurl)s, %(media_type)s, %(copyright)s)
        ON CONFLICT (apod_date) DO UPDATE SET
            title       = EXCLUDED.title,
            explanation = EXCLUDED.explanation,
            url         = EXCLUDED.url,
            hdurl       = EXCLUDED.hdurl,
            fetched_at  = NOW()
    """
    apod.setdefault("hdurl", apod.get("url"))
    apod.setdefault("explanation", "")
    apod.setdefault("media_type", "image")
    apod.setdefault("copyright", None)

    with _cursor() as cur:
        cur.execute(sql, apod)
    logger.info(f"APOD guardado: {apod['title']} ({apod['date']})")
    return 1


def load_asteroids(asteroids: list[dict]) -> int:
    sql = """
        INSERT INTO neo_asteroids (
            nasa_id, name, close_approach_date, absolute_magnitude,
            estimated_diam_min_km, estimated_diam_max_km,
            is_potentially_hazardous, miss_distance_km, miss_distance_lunar,
            relative_velocity_kmh, orbiting_body, risk_level
        ) VALUES (
            %(nasa_id)s, %(name)s, %(close_approach_date)s, %(absolute_magnitude)s,
            %(estimated_diam_min_km)s, %(estimated_diam_max_km)s,
            %(is_potentially_hazardous)s, %(miss_distance_km)s, %(miss_distance_lunar)s,
            %(relative_velocity_kmh)s, %(orbiting_body)s, %(risk_level)s
        )
        ON CONFLICT (nasa_id, close_approach_date) DO UPDATE SET
            miss_distance_km      = EXCLUDED.miss_distance_km,
            relative_velocity_kmh = EXCLUDED.relative_velocity_kmh,
            risk_level            = EXCLUDED.risk_level,
            fetched_at            = NOW()
    """
    with _cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, asteroids, page_size=100)
    logger.info(f"Asteroides guardados: {len(asteroids)} registros")
    return len(asteroids)


def load_events(events: list[dict]) -> int:
    sql = """
        INSERT INTO earth_events (
            event_id, title, description, category, category_id,
            status, geometry_date, longitude, latitude,
            magnitude_value, magnitude_unit, sources
        ) VALUES (
            %(event_id)s, %(title)s, %(description)s, %(category)s, %(category_id)s,
            %(status)s, %(geometry_date)s, %(longitude)s, %(latitude)s,
            %(magnitude_value)s, %(magnitude_unit)s, %(sources)s
        )
        ON CONFLICT (event_id) DO UPDATE SET
            status     = EXCLUDED.status,
            latitude   = EXCLUDED.latitude,
            longitude  = EXCLUDED.longitude,
            fetched_at = NOW()
    """
    with _cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, events, page_size=100)
    logger.info(f"Eventos guardados: {len(events)} registros")
    return len(events)


def log_etl_run(pipeline: str, status: str, records_in: int = 0,
                records_out: int = 0, error_msg: str = None):
    """Guarda en la bitácora el resultado de cada ejecución del pipeline."""
    sql = """
        INSERT INTO etl_runs
            (run_date, pipeline, status, records_in, records_out, error_msg, finished_at)
        VALUES
            (CURRENT_DATE, %s, %s, %s, %s, %s, NOW())
    """
    with _cursor() as cur:
        cur.execute(sql, (pipeline, status, records_in, records_out, error_msg))