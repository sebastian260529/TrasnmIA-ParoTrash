"""
API de Detección de Anomalías para el sistema de buses Transmilenio.
Detecta anomalías solo de buses actualmente en operación.
"""

import math
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.database import BusDatabase
from src.config import (
    CLUSTER_RADIUS,
    MIN_DISTANCE_ALERT,
    MIN_POS_CHANGE,
    VELOCIDAD_LENTA,
    RADIO_EXCLUSION_PORTAL,
    MINUTAS_INACTIVIDAD,
    UMBRAL_MANIFESTACION,
    UMBRAL_TRANCON,
    RADIO_ANOMALIA,
    PORTALES
)

logger = logging.getLogger(__name__)

# Cache para no recalcular constantemente
_cache = {}
_cache_time = 0
CACHE_DURATION = 60  # segundos


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en metros entre dos puntos."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def obtener_direccion(bus: Dict[str, Any]) -> str:
    """Determina la dirección del bus."""
    angulo = bus.get("angulo")
    if angulo is None:
        return "GRIS"
    angulo = float(angulo) % 360
    if angulo < 45 or angulo >= 315:
        return "ARRIBA"
    elif 45 <= angulo < 135:
        return "ARRIBA"
    elif 135 <= angulo < 225:
        return "ABAJO"
    else:
        return "ABAJO"


def esta_en_zona_portal(bus: Dict[str, Any]) -> bool:
    """Verifica si un bus está en zona de portal."""
    lat = bus.get("latitud")
    lon = bus.get("longitud")
    if lat is None or lon is None:
        return False
    for nombre, (portal_lat, portal_lon) in PORTALES.items():
        if haversine(lat, lon, portal_lat, portal_lon) <= RADIO_EXCLUSION_PORTAL:
            return True
    return False


def es_destino_portal(bus: Dict[str, Any]) -> bool:
    """Verifica si el destino es un portal."""
    destino = bus.get("destino_limpio", "")
    if not destino:
        return False
    for nombre in PORTALES.keys():
        if nombre.lower() in destino.lower():
            return True
    return False


def filtrar_buses_no_portal(buses: List[Dict]) -> List[Dict]:
    """Filtra buses que están en zonas de portales."""
    return [b for b in buses if not esta_en_zona_portal(b) and not es_destino_portal(b)]


def clustering_buses(buses: List[Dict], radio: int = None) -> List[Dict]:
    """Agrupa buses en clusters."""
    radio = radio or RADIO_ANOMALIA
    clusters = []
    asignaciones = {}
    
    for i, bus in enumerate(buses):
        lat = bus.get("latitud")
        lon = bus.get("longitud")
        if lat is None or lon is None:
            continue
        asignacion = -1
        for idx, cluster in enumerate(clusters):
            centro_lat, centro_lon, _ = cluster
            if haversine(lat, lon, centro_lat, centro_lon) <= radio:
                asignacion = idx
                break
        if asignacion == -1:
            clusters.append((lat, lon, 1))
            asignacion = len(clusters) - 1
        else:
            centro_lat, centro_lon, count = clusters[asignacion]
            nuevo_count = count + 1
            nuevo_lat = (centro_lat * count + lat) / nuevo_count
            nuevo_lon = (centro_lon * count + lon) / nuevo_count
            clusters[asignacion] = (nuevo_lat, nuevo_lon, nuevo_count)
        asignaciones[i] = asignacion
    
    return [
        {
            "latitud": lat,
            "longitud": lon,
            "cantidad": count,
            "buses": [b for b, a in zip(buses, asignaciones.items()) if a == idx]
        }
        for idx, (lat, lon, count) in enumerate(clusters)
    ]


def calcular_porcentaje_confianza(tipo: str, buses_count: int, umbral: int, **kwargs) -> float:
    """Calcula el porcentaje de confianza."""
    if tipo == "MANIFESTACION":
        return min((buses_count / UMBRAL_MANIFESTACION) * 100, 100.0)
    elif tipo == "TRANCON":
        porcentaje = (buses_count / UMBRAL_TRANCON) * 100
        vel_prom = kwargs.get("velocidad_promedio", 0)
        if vel_prom and vel_prom < 10:
            porcentaje += 15
        return min(porcentaje, 100.0)
    elif tipo == "BUS_VARADO":
        porcentaje = 50.0
        vecinos = kwargs.get("buses_vecinos", 0)
        return min(porcentaje + min(vecinos * 10, 40), 90.0)
    return 0.0


def calcular_velocidad_bus(db: BusDatabase, bus_id: str, posicion_actual: int) -> tuple:
    """
    Calcula velocidad de un bus usando sus datos históricos.
    Si tiene 2 datos: usa esos 2.
    Si tiene 3+ datos: usa promedio de los últimos N.
    Returns: (velocidad_kmh, datos_usados)
    """
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT posicion, timestamp
        FROM posiciones_buses
        WHERE bus_id = ?
        ORDER BY timestamp DESC
        LIMIT 10
    """, (bus_id,))
    
    resultados = cursor.fetchall()
    conn.close()
    
    if len(resultados) < 2:
        return (0, len(resultados))
    
    # Usar todos los datos disponibles (2 o más)
    velocidades = []
    for i in range(len(resultados) - 1):
        pos_ant = resultados[i + 1][0]
        pos_act = resultados[i][0]
        tiempo_diff = (datetime.strptime(resultados[i][1], "%Y-%m-%d %H:%M:%S") -
                    datetime.strptime(resultados[i + 1][1], "%Y-%m-%d %H:%M:%S")).total_seconds()
        if tiempo_diff > 0:
            cambio_pos = abs(pos_act - pos_ant)
            velocidad = (cambio_pos / tiempo_diff) * 3.6  # m/s a km/h
            velocidades.append(velocidad)
    
    if velocidades:
        return (sum(velocidades) / len(velocidades), len(velocidades))
    return (0, 0)


def analizar_buses_activos(db: BusDatabase) -> Dict[str, Any]:
    """
    Analiza Solo buses activos (los que están en captura actual).
    """
    captura_actual = db.obtener_captura_actual()
    
    # Solo buses con posición válida
    buses_activos = [b for b in captura_actual if b.get("posicion") is not None]
    
    velocidades = []
    buses_detenidos = []
    buses_lentos = []
    buses_normales = []
    
    for bus in buses_activos:
        bus_id = bus.get("bus_id")
        posicion = bus.get("posicion")
        
        if bus_id is None or posicion is None:
            continue
        
        vel, datos_usados = calcular_velocidad_bus(db, bus_id, posicion)
        
        # Excluir buses en portales
        if esta_en_zona_portal(bus) or es_destino_portal(bus):
            continue
        
        bus_con_vel = {
            "bus_id": bus_id,
            "label": bus.get("label"),
            "ruta": bus.get("ruta"),
            "latitud": bus.get("latitud"),
            "longitud": bus.get("longitud"),
            "posicion": posicion,
            "destino_limpio": bus.get("destino_limpio"),
            "angulo": bus.get("angulo"),
            "velocidad_kmh": round(vel, 1),
            "datos_velocidad": datos_usados,
            "direccion": obtener_direccion(bus)
        }
        
        if datos_usados == 0:
            buses_normales.append(bus_con_vel)
        elif vel < 1:  # Casi detenido
            buses_detenidos.append(bus_con_vel)
        elif vel < VELOCIDAD_LENTA:
            buses_lentos.append(bus_con_vel)
        else:
            buses_normales.append(bus_con_vel)
        
        velocidades.append(vel)
    
    return {
        "detenidos": buses_detenidos,
        "lentos": buses_lentos,
        "normales": buses_normales,
        "total_detenidos": len(buses_detenidos),
        "total_lentos": len(buses_lentos),
        "total_normales": len(buses_normales),
        "total_activos": len(buses_activos),
        "velocidad_promedio": round(sum(velocidades) / len(velocidades), 1) if velocidades else 0
    }


def detectar_manifestaciones(buses_detenidos: List[Dict]) -> List[Dict]:
    """Detecta posibles manifestaciones."""
    if len(buses_detenidos) < 5:
        return []
    
    clusters = clustering_buses(buses_detenidos, RADIO_ANOMALIA)
    resultados = []
    
    for cluster in clusters:
        if cluster["cantidad"] >= UMBRAL_MANIFESTACION:
            buses_zona = cluster["buses"]
            direcciones = [obtener_direccion(b) for b in buses_zona]
            direccion_mas = max(set(direcciones), key=direcciones.count) if direcciones else "mixto"
            
            porcentaje = calcular_porcentaje_confianza("MANIFESTACION", cluster["cantidad"], UMBRAL_MANIFESTACION)
            
            resultados.append({
                "tipo": "MANIFESTACION",
                "coordenadas": {"latitud": round(cluster["latitud"], 6), "longitud": round(cluster["longitud"], 6)},
                "porcentaje_confianza": round(porcentaje, 1),
                "buses_involucrados": cluster["cantidad"],
                "radio_m": RADIO_ANOMALIA,
                "duracion_estimada_min": MINUTAS_INACTIVIDAD,
                "detalles": {"buses_sin_movimiento": cluster["cantidad"], "direccion": direccion_mas},
                "buses_ids": [b.get("bus_id", b.get("label", "")) for b in buses_zona[:20]]
            })
    return resultados


def detectar_trancones(buses_lentos: List[Dict]) -> List[Dict]:
    """Detecta trancones."""
    if len(buses_lentos) < 3:
        return []
    
    clusters = clustering_buses(buses_lentos, RADIO_ANOMALIA)
    resultados = []
    
    for cluster in clusters:
        if cluster["cantidad"] >= UMBRAL_TRANCON:
            buses_zona = cluster["buses"]
            velocidades = [b.get("velocidad_kmh", 0) for b in buses_zona]
            vel_prom = sum(velocidades) / len(velocidades) if velocidades else 0
            
            porcentaje = calcular_porcentaje_confianza("TRANCON", cluster["cantidad"], UMBRAL_TRANCON, velocidad_promedio=vel_prom)
            
            resultados.append({
                "tipo": "TRANCON",
                "coordenadas": {"latitud": round(cluster["latitud"], 6), "longitud": round(cluster["longitud"], 6)},
                "porcentaje_confianza": round(porcentaje, 1),
                "buses_involucrados": cluster["cantidad"],
                "radio_m": RADIO_ANOMALIA,
                "detalles": {"velocidad_promedio_kmh": round(vel_prom, 1), "buses_lentos": cluster["cantidad"]},
                "buses_ids": [b.get("bus_id", b.get("label", "")) for b in buses_zona[:20]]
            })
    return resultados


def detectar_buses_varados(buses_detenidos: List[Dict], buses_lentos: List[Dict]) -> List[Dict]:
    """Detecta buses varados."""
    resultados = []
    
    for bus_det in buses_detenidos:
        lat, lon = bus_det.get("latitud"), bus_det.get("longitud")
        if lat is None or lon is None:
            continue
        
        vecinos = sum(1 for b in buses_lentos if haversine(lat, lon, b.get("latitud", 0), b.get("longitud", 0)) <= MIN_DISTANCE_ALERT * 2)
        
        if vecinos >= 3:
            porcentaje = calcular_porcentaje_confianza("BUS_VARADO", 1, 1, buses_vecinos=vecinos)
            resultados.append({
                "tipo": "BUS_VARADO",
                "coordenadas": {"latitud": round(lat, 6), "longitud": round(lon, 6)},
                "porcentaje_confianza": round(porcentaje, 1),
                "buses_involucrados": 1,
                "bus_id": bus_det.get("bus_id", bus_det.get("label", "")),
                "detalles": {"buses_vecinos_lentos": vecinos}
            })
    return resultados


def detectar_anomalias(db: BusDatabase, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Detecta anomalías solo de buses actualmente activos.
    Usa cache para no recalcular constantemente.
    """
    global _cache, _cache_time
    
    ahora = datetime.now()
    tiempo_actual = ahora.timestamp()
    
    # Usar cache si no ha expirado
    if not force_refresh and _cache and (tiempo_actual - _cache_time) < CACHE_DURATION:
        _cache["from_cache"] = True
        return _cache
    
    analisis = analizar_buses_activos(db)
    
    buses_detenidos = analisis["detenidos"]
    buses_lentos = analisis["lentos"]
    
    manifestaciones = detectar_manifestaciones(buses_detenidos)
    trancones = detectar_trancones(buses_lentos)
    varados = detectar_buses_varados(buses_detenidos, buses_lentos)
    
    # Contar buses excluidos por portales
    captura = db.obtener_captura_actual()
    buses_no_portal = filtrar_buses_no_portal(captura)
    excluidos = len(captura) - len(buses_no_portal)
    
    resultado = {
        "timestamp": ahora.isoformat(),
        "actualizacion_en_segundos": CACHE_DURATION,
        "buses_activos": analisis["total_activos"],
        "anomalias": manifestaciones + trancones + varados,
        "resumen": {
            "total_anomalias": len(manifestaciones) + len(trancones) + len(varados),
            "manifestaciones": len(manifestaciones),
            "trancones": len(trancones),
            "buses_varados": len(varados),
            "buses_sin_movimiento": analisis["total_detenidos"],
            "buses_lentos": analisis["total_lentos"],
            "buses_normales": analisis["total_normales"],
            "velocidad_promedio_kmh": analisis["velocidad_promedio"]
        },
        "excluidos_portal": excluidos,
        "from_cache": False
    }
    
    _cache = resultado
    _cache_time = tiempo_actual
    
    return resultado


def formatear_salida(analisis: Dict) -> str:
    """Formatea para mostrar en consola."""
    lines = []
    lines.append("\n" + "=" * 50)
    lines.append("       DETECCION DE ANOMALIAS")
    lines.append("=" * 50)
    lines.append(f"Fecha: {analisis['timestamp']}")
    lines.append(f"Buses activos: {analisis['buses_activos']}")
    lines.append(f"Actualizacion: cada {analisis['actualizacion_en_segundos']}s")
    lines.append("")
    
    resumen = analisis.get("resumen", {})
    lines.append(f"Buses sin movimiento: {resumen.get('buses_sin_movimiento', 0)}")
    lines.append(f"Buses lentos: {resumen.get('buses_lentos', 0)}")
    lines.append(f"Buses normales: {resumen.get('buses_normales', 0)}")
    lines.append(f"Velocidad promedio: {resumen.get('velocidad_promedio_kmh', 0)} km/h")
    lines.append("")
    
    if analisis.get("anomalias"):
        for a in analisis["anomalias"]:
            lines.append(f"[{a['tipo']}] {a['porcentaje_confianza']}% - {a['buses_involucrados']} buses")
            if "coordenadas" in a:
                lines.append(f"  Coordenadas: {a['coordenadas']['latitud']}, {a['coordenadas']['longitud']}")
            if "bus_id" in a:
                lines.append(f"  Bus: {a['bus_id']}")
            lines.append("")
    else:
        lines.append("  No se detectaron anomalías.")
    
    return "\n".join(lines)