"""
nasa_etl_dag.py — Space Hazard Tracker
Pipeline diario: NASA APIs → PostgreSQL
Corre todos los días a las 06:00 UTC
"""

import sys
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow")

from etl.extract   import fetch_apod, fetch_neo_feed, fetch_eonet_events
from etl.transform import transform_apod, transform_asteroids, transform_events
from etl.load      import load_apod, load_asteroids, load_events, log_etl_run

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner":            "space-hazard-tracker",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}

# ── Funciones de cada tarea ───────────────────────────────────────────────────

def run_apod_pipeline(**ctx):
    run_date = ctx["ds"]
    logger.info(f"[APOD] Iniciando para {run_date}")
    try:
        raw       = fetch_apod(date=run_date)
        clean     = transform_apod(raw)
        count_out = load_apod(clean)
        log_etl_run("apod", "SUCCESS", records_in=1, records_out=count_out)
    except Exception as e:
        log_etl_run("apod", "FAILED", error_msg=str(e))
        raise


def run_neo_pipeline(**ctx):
    run_date = ctx["ds"]
    end_date = (
        datetime.strptime(run_date, "%Y-%m-%d") + timedelta(days=6)
    ).strftime("%Y-%m-%d")
    logger.info(f"[NEO] Fetching {run_date} → {end_date}")
    try:
        raw       = fetch_neo_feed(start_date=run_date, end_date=end_date)
        clean     = transform_asteroids(raw)
        count_out = load_asteroids(clean)
        log_etl_run("neo_feed", "SUCCESS", records_in=len(raw), records_out=count_out)
    except Exception as e:
        log_etl_run("neo_feed", "FAILED", error_msg=str(e))
        raise


def run_eonet_pipeline(**ctx):
    logger.info("[EONET] Fetching eventos activos de la Tierra")
    try:
        raw       = fetch_eonet_events(status="open", limit=200)
        clean     = transform_events(raw)
        count_out = load_events(clean)
        log_etl_run("eonet", "SUCCESS", records_in=len(raw), records_out=count_out)
    except Exception as e:
        log_etl_run("eonet", "FAILED", error_msg=str(e))
        raise


# ── Definición del DAG ────────────────────────────────────────────────────────

with DAG(
    dag_id="space_hazard_daily_etl",
    description="Pipeline diario: NASA APOD + NeoWs + EONET → PostgreSQL",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["nasa", "etl", "space-hazard-tracker"],
) as dag:

    apod_task = PythonOperator(
        task_id="extract_transform_load_apod",
        python_callable=run_apod_pipeline,
    )

    neo_task = PythonOperator(
        task_id="extract_transform_load_neo",
        python_callable=run_neo_pipeline,
    )

    eonet_task = PythonOperator(
        task_id="extract_transform_load_eonet",
        python_callable=run_eonet_pipeline,
    )

    # Las 3 tareas corren en paralelo — son independientes entre sí
    [apod_task, neo_task, eonet_task]