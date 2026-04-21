"""
transform.py — Space Hazard Tracker
Limpia y enriquece los datos de NASA antes de cargarlos a PostgreSQL.
"""

import logging

logger = logging.getLogger(__name__)

# ── Umbrales de riesgo ────────────────────────────────────────────────────────
HIGH_RISK_DISTANCE_KM   = 1_000_000     # < 1 M km   → HIGH
MEDIUM_RISK_DISTANCE_KM = 10_000_000    # < 10 M km  → MEDIUM


def classify_asteroid_risk(asteroid: dict) -> str:
    """
    Asigna nivel de riesgo basado en distancia y flag de NASA.
    HIGH   — < 1M km  O  potencialmente peligroso + < 10M km
    MEDIUM — < 10M km
    LOW    — todo lo demás
    """
    dist      = asteroid.get("miss_distance_km") or 0
    hazardous = asteroid.get("is_potentially_hazardous", False)

    if dist < HIGH_RISK_DISTANCE_KM or (hazardous and dist < MEDIUM_RISK_DISTANCE_KM):
        return "HIGH"
    if dist < MEDIUM_RISK_DISTANCE_KM:
        return "MEDIUM"
    return "LOW"


def transform_asteroids(raw: list[dict]) -> list[dict]:
    """
    Castea tipos y agrega risk_level a cada asteroide.
    Si un registro tiene datos corruptos lo descarta con un warning.
    """
    cleaned = []
    for item in raw:
        try:
            item["miss_distance_km"]      = float(item.get("miss_distance_km") or 0)
            item["miss_distance_lunar"]   = float(item.get("miss_distance_lunar") or 0)
            item["relative_velocity_kmh"] = float(item.get("relative_velocity_kmh") or 0)
            item["estimated_diam_min_km"] = float(item.get("estimated_diam_min_km") or 0)
            item["estimated_diam_max_km"] = float(item.get("estimated_diam_max_km") or 0)
            item["absolute_magnitude"]    = float(item.get("absolute_magnitude") or 0)
            item["risk_level"]            = classify_asteroid_risk(item)
            cleaned.append(item)
        except (TypeError, ValueError) as e:
            logger.warning(f"Asteroide descartado {item.get('nasa_id')}: {e}")

    high   = sum(1 for a in cleaned if a["risk_level"] == "HIGH")
    medium = sum(1 for a in cleaned if a["risk_level"] == "MEDIUM")
    logger.info(
        f"Asteroides transformados: {len(cleaned)} total | {high} HIGH | {medium} MEDIUM"
    )
    return cleaned


def transform_events(raw: list[dict]) -> list[dict]:
    """
    Limpia eventos EONET — descarta los que no tienen coordenadas
    porque no se pueden mostrar en el mapa.
    """
    cleaned = []
    for ev in raw:
        if ev.get("longitude") is None or ev.get("latitude") is None:
            logger.debug(f"Evento sin coordenadas descartado: {ev.get('event_id')}")
            continue
        try:
            ev["longitude"] = float(ev["longitude"])
            ev["latitude"]  = float(ev["latitude"])
            if ev.get("magnitude_value") is not None:
                ev["magnitude_value"] = float(ev["magnitude_value"])
            cleaned.append(ev)
        except (TypeError, ValueError) as e:
            logger.warning(f"Evento descartado {ev.get('event_id')}: {e}")

    logger.info(
        f"Eventos transformados: {len(cleaned)}/{len(raw)} tienen coordenadas"
    )
    return cleaned


def transform_apod(raw: dict) -> dict:
    """
    Validación mínima del APOD — solo verifica que los campos
    esenciales existan antes de intentar guardar.
    """
    required = {"title", "date", "url"}
    missing  = required - raw.keys()
    if missing:
        raise ValueError(f"APOD response incompleto, faltan campos: {missing}")
    return raw