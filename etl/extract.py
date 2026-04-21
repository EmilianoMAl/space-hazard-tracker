"""
extract.py — Space Hazard Tracker
Obtiene datos de tres APIs de NASA: APOD, NeoWs, EONET
"""

import os
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_BASE    = "https://api.nasa.gov"
EONET_BASE   = "https://eonet.gsfc.nasa.gov/api/v3"

TIMEOUT = 30


def _get(url: str, params: dict = None) -> dict:
    """GET genérico con manejo de errores."""
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        logger.error(f"Request fallido — {url}: {e}")
        raise


def fetch_apod(date: str = None) -> dict:
    """
    Trae la Astronomy Picture of the Day.
    date: 'YYYY-MM-DD' — si no se pasa, trae la de hoy.
    """
    params = {"api_key": NASA_API_KEY}
    if date:
        params["date"] = date
    data = _get(f"{NASA_BASE}/planetary/apod", params)
    logger.info(f"APOD obtenido: {data.get('title')}")
    return data


def fetch_neo_feed(start_date: str = None, end_date: str = None) -> list[dict]:
    """
    Trae los asteroides cercanos a la Tierra en una ventana de fechas.
    Máximo 7 días por request (límite de la API).
    Devuelve lista plana de diccionarios.
    """
    if not start_date:
        start_date = datetime.utcnow().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (
            datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=6)
        ).strftime("%Y-%m-%d")

    params = {
        "start_date": start_date,
        "end_date":   end_date,
        "api_key":    NASA_API_KEY,
    }
    data = _get(f"{NASA_BASE}/neo/rest/v1/feed", params)

    asteroids = []
    for date_str, objects in data.get("near_earth_objects", {}).items():
        for obj in objects:
            approach = (
                obj["close_approach_data"][0]
                if obj.get("close_approach_data")
                else {}
            )
            diam = obj.get("estimated_diameter", {}).get("kilometers", {})
            asteroids.append({
                "nasa_id":                  obj["id"],
                "name":                     obj["name"],
                "close_approach_date":      date_str,
                "absolute_magnitude":       obj.get("absolute_magnitude_h"),
                "estimated_diam_min_km":    diam.get("estimated_diameter_min"),
                "estimated_diam_max_km":    diam.get("estimated_diameter_max"),
                "is_potentially_hazardous": obj.get(
                    "is_potentially_hazardous_asteroid", False
                ),
                "miss_distance_km":   float(
                    approach.get("miss_distance", {}).get("kilometers", 0)
                ),
                "miss_distance_lunar": float(
                    approach.get("miss_distance", {}).get("lunar", 0)
                ),
                "relative_velocity_kmh": float(
                    approach.get("relative_velocity", {})
                    .get("kilometers_per_hour", 0)
                ),
                "orbiting_body": approach.get("orbiting_body", "Earth"),
            })

    logger.info(
        f"NeoWs: {len(asteroids)} asteroides ({start_date} → {end_date})"
    )
    return asteroids


def fetch_eonet_events(status: str = "open", limit: int = 100) -> list[dict]:
    """
    Trae eventos naturales activos de la Tierra.
    Categorías: incendios, tormentas, volcanes, inundaciones, etc.
    """
    params = {"status": status, "limit": limit}
    data   = _get(f"{EONET_BASE}/events", params)

    events = []
    for ev in data.get("events", []):
        category = ev.get("categories", [{}])[0]
        geometry = (
            ev.get("geometry", [{}])[-1]
            if ev.get("geometry")
            else {}
        )
        coords  = geometry.get("coordinates", [None, None])
        sources = ", ".join(
            s.get("url", "") for s in ev.get("sources", [])
        )

        events.append({
            "event_id":        ev["id"],
            "title":           ev["title"],
            "description":     ev.get("description"),
            "category":        category.get("title"),
            "category_id":     category.get("id"),
            "status":          "closed" if ev.get("closed") else "open",
            "geometry_date":   geometry.get("date"),
            "longitude":       coords[0] if coords and len(coords) > 1 else None,
            "latitude":        coords[1] if coords and len(coords) > 1 else None,
            "magnitude_value": geometry.get("magnitudeValue"),
            "magnitude_unit":  geometry.get("magnitudeUnit"),
            "sources":         sources,
        })

    logger.info(f"EONET: {len(events)} eventos (status={status})")
    return events