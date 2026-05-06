import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

from src.database import BusDatabase
from src.geo.location_service import get_zone_coords

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_demo_state: Dict[str, Any] = {
    "buses_demo": [],
    "reportes_demo": [],
    "alertas_simuladas": [],
    "ultima_zona": None,
    "ultima_intensidad": None
}

ZONA_COORDS_MAP = {
    "portal eldorado": (4.6900, -74.1000),
    "portal norte": (4.7700, -74.0300),
    "portal sur": (4.4000, -74.1700),
    "portal americas": (4.6800, -74.1100),
    "avenida caracas": (4.6100, -74.0800),
    "carrera 5 con calle 28": (4.6050, -74.0650),
    "universidad distrital": (4.6070, -74.0700),
    "avenida circunvalar con calle 26": (4.6200, -74.0550),
    "calle 72 con carrera 11": (4.6550, -74.0500),
}


def _get_coords(zona: str):
    zone = get_zone_coords(zona)
    if zone:
        return zone["lat"], zone["lon"]
    normalized = zona.lower().strip()
    for key, coords in ZONA_COORDS_MAP.items():
        if key in normalized or normalized in key:
            return coords
    return 4.6500, -74.0800


def crear_escenario_demo(zona: str, intensidad: str = "alto") -> Dict[str, Any]:
    global _demo_state
    base_lat, base_lon = _get_coords(zona)
    now = datetime.now().isoformat()
    buses_creados = []
    if intensidad == "alto":
        n_buses = 6
        velocidad = 3
        variacion = 0.002
    elif intensidad == "medio":
        n_buses = 3
        velocidad = 8
        variacion = 0.005
    else:
        n_buses = 1
        velocidad = 20
        variacion = 0.01
    for i in range(n_buses):
        bus = {
            "bus_id": f"DEMO_{int(time.time() * 1000)}_{i}",
            "id": f"DEMO_{int(time.time() * 1000)}_{i}",
            "label": f"Bus Demo #{i+1}",
            "ruta": f"R{90+i}",
            "ruta_extraida": f"R{90+i}",
            "latitud": base_lat + (i - n_buses/2) * variacion * 0.3,
            "latitude": base_lat + (i - n_buses/2) * variacion * 0.3,
            "longitud": base_lon + (i - n_buses/2) * variacion * 0.3,
            "longitude": base_lon + (i - n_buses/2) * variacion * 0.3,
            "velocidad": velocidad,
            "destino_limpio": zona,
            "timestamp": now,
            "lasttime": now,
            "posicion": 1000 + i * 100,
            "angulo": 90,
            "nombre_sistema": "demo",
            "route_id": 999,
            "nombre_bus": zona
        }
        buses_creados.append(bus)
    reportes_creados = []
    if intensidad == "alto":
        tipos_reporte = [
            {"tipo": "paro", "descripcion": f"Se reporta paro en {zona}. Flota sin paso.", "zona": zona},
            {"tipo": "bloqueo", "descripcion": f"Bloqueo total en {zona} por manifestacion.", "zona": zona},
            {"tipo": "manifestacion", "descripcion": f"Manifestacion masiva en {zona} afecta la movilidad.", "zona": zona},
            {"tipo": "congestion", "descripcion": f"Alta congestion en {zona} por cierre de vias.", "zona": zona},
        ]
    elif intensidad == "medio":
        tipos_reporte = [
            {"tipo": "congestion", "descripcion": f"Se reporta congestion moderada en {zona}.", "zona": zona},
            {"tipo": "desvio", "descripcion": f"Desvios reportados en {zona} por obras.", "zona": zona},
        ]
    else:
        tipos_reporte = [
            {"tipo": "normal", "descripcion": f"Movilidad normal en {zona} sin novedades.", "zona": zona},
        ]
    for tr in tipos_reporte:
        reporte = {
            "id": f"DEMO_{int(time.time() * 1000)}_{len(reportes_creados)}",
            "reporte_id": f"DEMO_{int(time.time() * 1000)}_{len(reportes_creados)}",
            "id_usuario": "demo_user",
            "tipo": tr["tipo"],
            "descripcion": tr["descripcion"],
            "zona": tr["zona"],
            "ubicacion": [base_lat, base_lon],
            "timestamp": now,
            "verificado": True if intensidad == "alto" else False,
            "votos_positivos": 10 if intensidad == "alto" else 3,
            "votos_negativos": 0,
            "descartes": 0
        }
        reportes_creados.append(reporte)
    alertas_simuladas = []
    if intensidad == "alto":
        alertas_simuladas = [
            f"Se reporta manifestacion en {zona}",
            f"Usuarios reportan bloqueo y alta congestion en {zona}",
            f"Flota con desvios por manifestacion en {zona}",
            f"Posible paro afecta la movilidad en {zona}",
        ]
    elif intensidad == "medio":
        alertas_simuladas = [
            f"Reporte de congestion en {zona}",
            f"Desvios reportados en {zona}",
        ]
    else:
        alertas_simuladas = [
            f"Movilidad normal en {zona}",
        ]
    _demo_state["buses_demo"] = buses_creados
    _demo_state["reportes_demo"] = reportes_creados
    _demo_state["alertas_simuladas"] = alertas_simuladas
    _demo_state["ultima_zona"] = zona
    _demo_state["ultima_intensidad"] = intensidad
    return {
        "status": "ok",
        "zona": zona,
        "intensidad": intensidad,
        "buses_creados": len(buses_creados),
        "reportes_creados": len(reportes_creados),
        "alertas_simuladas": alertas_simuladas,
        "mensaje": f"Escenario {intensidad} creado correctamente en {zona}"
    }


def limpiar_demo() -> Dict[str, Any]:
    global _demo_state
    _demo_state = {
        "buses_demo": [],
        "reportes_demo": [],
        "alertas_simuladas": [],
        "ultima_zona": None,
        "ultima_intensidad": None
    }
    return {"status": "ok", "mensaje": "Datos demo limpiados correctamente"}


def get_demo_state() -> Dict[str, Any]:
    return {
        "buses_demo_activos": len(_demo_state.get("buses_demo", [])),
        "reportes_demo_activos": len(_demo_state.get("reportes_demo", [])),
        "alertas_demo_activas": len(_demo_state.get("alertas_simuladas", [])),
        "ultima_zona": _demo_state.get("ultima_zona"),
        "ultima_intensidad": _demo_state.get("ultima_intensidad")
    }


def get_demo_reportes() -> List[Dict]:
    return _demo_state.get("reportes_demo", [])


def get_demo_alertas() -> List[str]:
    return _demo_state.get("alertas_simuladas", [])


def get_demo_buses() -> List[Dict]:
    return _demo_state.get("buses_demo", [])
