"""
API de Detección de Anomalías para el sistema de buses Transmilenio.
Detecta anomalías solo de buses actualmente en operación.
"""

import math
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from database.database import BusDatabase
from config.config import (
    CLUSTER_RADIUS,
    MIN_DISTANCE_ALERT,
    MIN_POS_CHANGE,
    VELOCIDAD_LENTA,
    RADIO_EXCLUSION_PORTAL,
    MINUTAS_INACTIVIDAD,
    UMBRAL_MANIFESTACION,
    UMBRAL_TRANCON,
    RADIO_ANOMALIA,
    DISTANCIA_MAX_CLUSTER,
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


# === CLUSTERING ANTIGUO (RADIAL) - YA NO SE USA - REEMPLAZADO POR clustering_lineal_por_direccion ===
# def clustering_buses(buses: List[Dict], radio: int = None) -> List[Dict]:
#     """Agrupa buses en clusters (radial)."""
#     radio = radio or RADIO_ANOMALIA
#     # ... (eliminado)
#
# def clustering_por_direccion(buses: List[Dict], radio: int = None) -> Dict[str, List[Dict]]:
#     """Agrupa buses por dirección y luego por proximidad espacial (radial)."""
#     radio = radio or RADIO_ANOMALIA
#     buses_arriba = [b for b in buses if obtener_direccion(b) == "ARRIBA"]
#     # ... (eliminado)


# === CLUSTERING LINEAL (NUEVO) - Se usa actualmente ===
# La función clustering_lineal_por_direccion() está definida más adelante


def clustering_por_direccion(buses: List[Dict], radio: int = None) -> Dict[str, List[Dict]]:
    """
    [DEPRECATED] Ahora usa clustering_lineal_por_direccion()
    Mantenido por compatibilidad. Redirige al clustering lineal.
    """
    return clustering_lineal_por_direccion(buses, DISTANCIA_MAX_CLUSTER)
    buses_abajo = [b for b in buses if obtener_direccion(b) == "ABAJO"]
    buses_sin_direccion = [b for b in buses if obtener_direccion(b) == "GRIS"]
    
    resultado = {
        "ARRIBA": clustering_buses(buses_arriba, radio),
        "ABAJO": clustering_buses(buses_abajo, radio),
        "GRIS": clustering_buses(buses_sin_direccion, radio)
    }
    
    return resultado


def clustering_lineal_por_direccion(buses: List[Dict], distancia_max: int = None) -> Dict[str, List[Dict]]:
    """
    Clustering LINEAL - agrupa buses que están cerca uno del otro en la misma vía.
    En lugar de usar radio circular, usa distancia entre buses consecutivos.

    Parámetros:
    - buses: lista de buses
    - distancia_max: distancia máxima entre buses consecutivos para considerarse mismo cluster

    Retorna: {"ARRIBA": [clusters], "ABAJO": [clusters]}
    """
    distancia_max = distancia_max or DISTANCIA_MAX_CLUSTER

    # Separar por dirección
    buses_arriba = [b for b in buses if obtener_direccion(b) == "ARRIBA"]
    buses_abajo = [b for b in buses if obtener_direccion(b) == "ABAJO"]
    buses_sin_direccion = [b for b in buses if obtener_direccion(b) == "GRIS"]

    def cluster_lineal(buses_direccion):
        """Agrupa buses por distancia lineal entre consecutivos."""
        if len(buses_direccion) < 2:
            return []

        # Ordenar por latitud (para vía vertical en Bogotá)
        # Si es horizontal, ordenar por longitud
        # Aquí usamos latitud como proxy de posición en la vía
        buses_ordenados = sorted(buses_direccion, key=lambda b: b.get('latitud', 0))

        clusters = []
        cluster_actual = [buses_ordenados[0]]
        posiciones = [buses_ordenados[0].get('latitud', 0)]

        for i in range(1, len(buses_ordenados)):
            bus_actual = buses_ordenados[i]
            lat_actual = bus_actual.get('latitud', 0)
            lat_anterior = posiciones[-1]

            # Calcular distancia entre este y el anterior (no desde el centro del cluster)
            dist = haversine(lat_anterior, bus_actual.get('longitud', 0),
                           lat_actual, bus_actual.get('longitud', 0))

            if dist <= distancia_max:
                # Mismo cluster - está cerca del anterior
                cluster_actual.append(bus_actual)
                posiciones.append(lat_actual)
            else:
                # Distancia grande - empezar nuevo cluster
                if len(cluster_actual) >= 2:
                    clusters.append(_crear_cluster_lineal(cluster_actual))
                cluster_actual = [bus_actual]
                posiciones.append(lat_actual)

        # Añadir el último cluster
        if len(cluster_actual) >= 2:
            clusters.append(_crear_cluster_lineal(cluster_actual))

        return clusters

    def _crear_cluster_lineal(buses_cluster):
        """Crea estructura de cluster."""
        lats = [b.get('latitud', 0) for b in buses_cluster]
        lons = [b.get('longitud', 0) for b in buses_cluster]
        return {
            "latitud": sum(lats) / len(lats),
            "longitud": sum(lons) / len(lons),
            "cantidad": len(buses_cluster),
            "buses": buses_cluster
        }

    resultado = {
        "ARRIBA": cluster_lineal(buses_arriba),
        "ABAJO": cluster_lineal(buses_abajo),
        "GRIS": cluster_lineal(buses_sin_direccion)
    }

    return resultado


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
    Solo considera buses con al menos 2 posiciones históricas para calcular velocidad.
    """
    captura_actual = db.obtener_captura_actual()

    # Solo buses con posición válida
    buses_activos = [b for b in captura_actual if b.get("posicion") is not None]

    velocidades = []
    buses_detenidos = []
    buses_lentos = []
    buses_normales = []
    buses_sin_datos = 0  # Contador de buses sin suficientes datos

    for bus in buses_activos:
        bus_id = bus.get("bus_id")
        posicion = bus.get("posicion")

        if bus_id is None or posicion is None:
            continue

        vel, datos_usados = calcular_velocidad_bus(db, bus_id, posicion)

        # IGNORAR buses sin suficientes datos históricos (menos de 2 posiciones)
        # No tienen historial para calcular velocidad real
        if datos_usados < 2:
            buses_sin_datos += 1
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
        "buses_sin_datos_historicos": buses_sin_datos,
        "velocidad_promedio": round(sum(velocidades) / len(velocidades), 1) if velocidades else 0
    }


def detectar_manifestaciones(buses_detenidos: List[Dict]) -> List[Dict]:
    """Detecta posibles manifestaciones usando clustering LINEAL por dirección."""
    if len(buses_detenidos) < 5:
        return []

    # Usar clustering LINEAL en lugar de radial
    clusters_por_direccion = clustering_lineal_por_direccion(buses_detenidos, DISTANCIA_MAX_CLUSTER)
    resultados = []
    
    for direccion, clusters in clusters_por_direccion.items():
        if direccion == "GRIS":
            continue
            
        for cluster in clusters:
            if cluster["cantidad"] >= UMBRAL_MANIFESTACION:
                buses_zona = cluster["buses"]
                
                porcentaje = calcular_porcentaje_confianza(
                    "MANIFESTACION", 
                    cluster["cantidad"], 
                    UMBRAL_MANIFESTACION
                )
                
                resultados.append({
                    "tipo": "MANIFESTACION",
                    "coordenadas": {"latitud": round(cluster["latitud"], 6), "longitud": round(cluster["longitud"], 6)},
                    "porcentaje_confianza": round(porcentaje, 1),
                    "buses_involucrados": cluster["cantidad"],
                    "radio_m": DISTANCIA_MAX_CLUSTER,
                    "duracion_estimada_min": MINUTAS_INACTIVIDAD,
                    "detalles": {"buses_sin_movimiento": cluster["cantidad"], "direccion": direccion},
                    "buses_ids": [b.get("bus_id", b.get("label", "")) for b in buses_zona[:20]]
                })
    return resultados


def detectar_trancones(buses_lentos: List[Dict]) -> List[Dict]:
    """Detecta trancones usando clustering LINEAL por dirección."""
    if len(buses_lentos) < 3:
        return []

    # Usar clustering LINEAL en lugar de radial
    clusters_por_direccion = clustering_lineal_por_direccion(buses_lentos, DISTANCIA_MAX_CLUSTER)
    resultados = []

    for direccion, clusters in clusters_por_direccion.items():
        if direccion == "GRIS":
            continue

        for cluster in clusters:
            if cluster["cantidad"] >= UMBRAL_TRANCON:
                buses_zona = cluster["buses"]
                velocidades = [b.get("velocidad_kmh", 0) for b in buses_zona]
                vel_prom = sum(velocidades) / len(velocidades) if velocidades else 0

                porcentaje = calcular_porcentaje_confianza(
                    "TRANCON",
                    cluster["cantidad"],
                    UMBRAL_TRANCON,
                    velocidad_promedio=vel_prom
                )

                resultados.append({
                    "tipo": "TRANCON",
                    "coordenadas": {"latitud": round(cluster["latitud"], 6), "longitud": round(cluster["longitud"], 6)},
                    "porcentaje_confianza": round(porcentaje, 1),
                    "buses_involucrados": cluster["cantidad"],
                    "radio_m": DISTANCIA_MAX_CLUSTER,
                    "detalles": {"velocidad_promedio_kmh": round(vel_prom, 1), "buses_lentos": cluster["cantidad"], "direccion": direccion},
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
    
    # Ya no excluimos buses por portales - analizamos todos los buses
    captura = db.obtener_captura_actual()
    buses_no_portal = captura  # Sin filtrar portales
    excluidos = 0  # Ya no excluimos nadie por portal
    
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
            "buses_sin_datos_historicos": analisis.get("buses_sin_datos_historicos", 0),
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