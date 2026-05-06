import math
import re
from typing import Dict, List, Optional, Tuple

ZONAS_CONOCIDAS = [
    {"nombre": "Portal Eldorado", "lat": 4.6900, "lon": -74.1000, "radio_metros": 800, "direccion_normalizada": "portal eldorado"},
    {"nombre": "Universidad Distrital sede La Macarena", "lat": 4.6070, "lon": -74.0700, "radio_metros": 500, "direccion_normalizada": "universidad distrital sede la macarena"},
    {"nombre": "Universidad Pedagógica", "lat": 4.6350, "lon": -74.0800, "radio_metros": 500, "direccion_normalizada": "universidad pedagogica"},
    {"nombre": "Avenida Caracas con Carrera 12B", "lat": 4.6100, "lon": -74.0800, "radio_metros": 500, "direccion_normalizada": "avenida caracas con carrera 12b"},
    {"nombre": "Avenida Caracas con Calle 6", "lat": 4.5800, "lon": -74.0850, "radio_metros": 500, "direccion_normalizada": "avenida caracas con calle 6"},
    {"nombre": "Avenida Circunvalar con Calle 26", "lat": 4.6200, "lon": -74.0550, "radio_metros": 500, "direccion_normalizada": "avenida circunvalar con calle 26"},
    {"nombre": "Carrera 5 con Calle 28", "lat": 4.6050, "lon": -74.0650, "radio_metros": 500, "direccion_normalizada": "carrera 5 con calle 28"},
    {"nombre": "Carrera 7 con Calle 28", "lat": 4.6070, "lon": -74.0680, "radio_metros": 500, "direccion_normalizada": "carrera 7 con calle 28"},
    {"nombre": "Calle 12B con Carrera 10", "lat": 4.5950, "lon": -74.0750, "radio_metros": 500, "direccion_normalizada": "calle 12b con carrera 10"},
    {"nombre": "Carrera 10 con Calle 24", "lat": 4.6000, "lon": -74.0730, "radio_metros": 500, "direccion_normalizada": "carrera 10 con calle 24"},
    {"nombre": "Portal Américas", "lat": 4.6800, "lon": -74.1100, "radio_metros": 800, "direccion_normalizada": "portal americas"},
    {"nombre": "Portal Norte", "lat": 4.7700, "lon": -74.0300, "radio_metros": 800, "direccion_normalizada": "portal norte"},
    {"nombre": "Portal Sur", "lat": 4.4000, "lon": -74.1700, "radio_metros": 800, "direccion_normalizada": "portal sur"},
    {"nombre": "Portal 20 de Julio", "lat": 4.4200, "lon": -74.1500, "radio_metros": 800, "direccion_normalizada": "portal 20 de julio"},
    {"nombre": "Calle 72 con Carrera 11", "lat": 4.6550, "lon": -74.0500, "radio_metros": 500, "direccion_normalizada": "calle 72 con carrera 11"},
    {"nombre": "Carrera 30 con Avenida Chile", "lat": 4.6600, "lon": -74.0750, "radio_metros": 500, "direccion_normalizada": "carrera 30 con avenida chile"},
]


def normalize_address(address: str) -> str:
    if not address:
        return ""
    address = address.lower().strip()
    address = re.sub(r'[áàäâ]', 'a', address)
    address = re.sub(r'[éèëê]', 'e', address)
    address = re.sub(r'[íìïî]', 'i', address)
    address = re.sub(r'[óòöô]', 'o', address)
    address = re.sub(r'[úùüû]', 'u', address)
    address = re.sub(r'[ñ]', 'n', address)
    address = re.sub(r'[^\w\s]', ' ', address)
    address = re.sub(r'\s+', ' ', address)
    return address.strip()


def distance_between_points(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_zone_coords(zona_nombre: str) -> Optional[Dict]:
    normalized = normalize_address(zona_nombre)
    for z in ZONAS_CONOCIDAS:
        if z["direccion_normalizada"] in normalized or normalized in z["direccion_normalizada"]:
            return z
    for z in ZONAS_CONOCIDAS:
        parts = normalized.split()
        for part in parts:
            if part in z["direccion_normalizada"]:
                return z
    return None


def find_nearest_zone(lat: float, lon: float) -> Optional[Dict]:
    best = None
    best_dist = float('inf')
    for z in ZONAS_CONOCIDAS:
        d = distance_between_points(lat, lon, z["lat"], z["lon"])
        if d < best_dist:
            best_dist = d
            best = z
    if best and best_dist <= best["radio_metros"] * 2:
        return best
    return None


def match_location_with_zone(address_or_coords, zona_consultada: str) -> bool:
    if isinstance(address_or_coords, dict):
        lat = address_or_coords.get("lat") or address_or_coords.get("latitud")
        lon = address_or_coords.get("lon") or address_or_coords.get("longitud")
        if lat is not None and lon is not None:
            zone = get_zone_coords(zona_consultada)
            if zone:
                return distance_between_points(float(lat), float(lon), zone["lat"], zone["lon"]) <= zone["radio_metros"]
            return False
        return False
    if isinstance(address_or_coords, str):
        addr = normalize_address(address_or_coords)
        zone = get_zone_coords(zona_consultada)
        if zone:
            return zone["direccion_normalizada"] in addr or any(
                part in addr for part in zone["direccion_normalizada"].split()
            )
        return False
    return False


def reverse_geocode_colombia(lat: float, lon: float) -> dict:
    zone = find_nearest_zone(lat, lon)
    if zone:
        return {
            "zona_detectada": zone["nombre"],
            "direccion_aproximada": zone["nombre"],
            "lat": zone["lat"],
            "lon": zone["lon"],
            "distancia_metros": round(distance_between_points(lat, lon, zone["lat"], zone["lon"]), 1),
            "fuente": "diccionario_local"
        }
    return {
        "zona_detectada": None,
        "direccion_aproximada": f"Coordenadas ({lat:.4f}, {lon:.4f})",
        "lat": lat,
        "lon": lon,
        "distancia_metros": 0,
        "fuente": "coordenadas_sin_zonificar"
    }


def enrich_bus_location(bus: dict) -> dict:
    bus = dict(bus)
    lat = bus.get("latitud") or bus.get("latitude")
    lon = bus.get("longitud") or bus.get("longitude")
    if lat is not None and lon is not None:
        geo = reverse_geocode_colombia(float(lat), float(lon))
        bus["direccion_aproximada"] = geo.get("direccion_aproximada")
        bus["zona_detectada"] = geo.get("zona_detectada")
        bus["distancia_a_zona_detectada"] = geo.get("distancia_metros")
    return bus


def enrich_alert_location(alerta: dict, zona_consultada: str = None) -> dict:
    alerta = dict(alerta)
    lat = alerta.get("latitud") or alerta.get("lat")
    lon = alerta.get("longitud") or alerta.get("lon")
    if lat is not None and lon is not None:
        geo = reverse_geocode_colombia(float(lat), float(lon))
        alerta["direccion_aproximada"] = geo.get("direccion_aproximada")
        alerta["zona_detectada"] = geo.get("zona_detectada")
        if zona_consultada:
            zone = get_zone_coords(zona_consultada)
            if zone:
                dist = distance_between_points(float(lat), float(lon), zone["lat"], zone["lon"])
                alerta["coincide_con_zona_consultada"] = dist <= zone["radio_metros"]
                alerta["distancia_a_zona_consultada"] = round(dist, 1)
    elif "direccion" in alerta and zona_consultada:
        alerta["coincide_con_zona_consultada"] = match_location_with_zone(alerta["direccion"], zona_consultada)
    return alerta
