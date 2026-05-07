"""
Google Maps Geocoding Service with caching.
"""
import os
import requests
from typing import Optional, Dict, Any
from functools import lru_cache

GEOCODE_CACHE = {}

def get_google_maps_api_key() -> str:
    return os.getenv("GOOGLE_MAPS_API_KEY", "")

def geocode(direccion: str) -> Optional[Dict[str, Any]]:
    """
    Geocodifica una dirección usando Google Maps API.
    Retorna: {lat, lon, direccion_formateada} o None si falla.
    """
    if not direccion:
        return None

    direccion = direccion.strip()
    if direccion in GEOCODE_CACHE:
        return GEOCODE_CACHE[direccion]

    api_key = get_google_maps_api_key()
    if not api_key:
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": f"{direccion}, Bogotá, Colombia",
        "key": api_key,
        "language": "es"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]

            resultado = {
                "lat": location["lat"],
                "lon": location["lng"],
                "direccion_formateada": result["formatted_address"]
            }

            GEOCODE_CACHE[direccion] = resultado
            return resultado
        else:
            return None
    except Exception:
        return None

def geocode_reverse(lat: float, lon: float) -> Optional[str]:
    """
    Obtiene dirección a partir de coordenadas (reverse geocoding).
    """
    api_key = get_google_maps_api_key()
    if not api_key:
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lon}",
        "key": api_key,
        "language": "es"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0]["formatted_address"]
        return None
    except Exception:
        return None