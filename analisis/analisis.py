"""
Módulo de análisis de trancones para buses Transmilenio.
Analiza densidad, proximidad y velocidad de los buses.
"""

import math
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from database.database import BusDatabase
from config.config import (
    CLUSTER_RADIUS,
    MIN_DISTANCE_ALERT,
    MIN_POS_CHANGE,
    VELOCIDAD_LENTA,
    VELOCIDAD_DETENIDO,
    ALERT_THRESHOLD,
    RADIO_EXCLUSION_PORTAL,
    MINUTAS_INACTIVIDAD,
    TIEMPO_HISTORIAL_ANALISIS,
    UMBRAL_MANIFESTACION,
    UMBRAL_TRANCON,
    RADIO_ANOMALIA,
    PORTALES
)

logger = logging.getLogger(__name__)

DESTINOS_SUR_A_NORTE = [
    "Portal Norte", "Portal 80", "Portal Suba", "Calle 161", "Toberin"
]

DESTINOS_NORTE_A_SUR = [
    "Portal 20", "Portal Sur", "Portal Tunal", "Portal Usme", "Portal Américas",
    "Portal El Dorado", "7 de Agosto", "Banderas"
]

LATITUD_CENTRO_BOGOTA = 4.65


DIR_ARRIBA = {
    "ARRIBA": ("^", 0),
    "ABAJO": ("v", 180),
    "GRIS": ("?", 0)
}


def obtener_direccion(bus: Dict[str, Any]) -> str:
    """
    Determina la dirección del bus: ARRIBA, ABAJO o GRIS (si no hay ángulo).
    """
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


def obtener_simbolo_direccion(direccion: str) -> str:
    """Retorna el símbolo Unicode para la dirección."""
    return DIR_ARRIBA.get(direccion, ("?", 0))[0]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en metros entre dos puntos usando fórmula de Haversine.
    """
    R = 6371000  # Radio de la Tierra en metros

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def analisis_densidad(buses: List[Dict], radio_m: int = None) -> Dict[str, Any]:
    """
    Analiza la densidad de buses por zonas usando clustering simple.
    """
    radio_m = radio_m or CLUSTER_RADIUS

    if not buses:
        return {"zonas": [], "total_buses": 0}

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
            dist = haversine(lat, lon, centro_lat, centro_lon)
            if dist <= radio_m:
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

    zonas = []
    for idx, (lat, lon, count) in enumerate(clusters):
        if count >= 2:
            buses_en_zona = [b for b, a in zip(buses, asignaciones.items()) if a == idx]
            direccion_contada = defaultdict(int)
            for b in buses_en_zona:
                direccion = obtener_direccion(b)
                direccion_contada[direccion] += 1

            zonas.append({
                "id": idx,
                "latitud": lat,
                "longitud": lon,
                "cantidad": count,
                "buses": buses_en_zona,
                "direccion": dict(direccion_contada)
            })

    zonas.sort(key=lambda x: x["cantidad"], reverse=True)

    return {
        "zonas": zonas[:10],
        "total_zonas": len(zonas),
        "total_buses": len(buses)
    }


def analisis_proximidad(buses: List[Dict], distancia_m: int = None) -> Dict[str, Any]:
    """
    Encuentra buses que están muy cercanos entre sí.
    """
    distancia_m = distancia_m or MIN_DISTANCE_ALERT

    if not buses:
        return {"pares": [], "total": 0}

    pares = []

    for i in range(len(buses)):
        for j in range(i + 1, len(buses)):
            bus1 = buses[i]
            bus2 = buses[j]

            lat1, lon1 = bus1.get("latitud"), bus1.get("longitud")
            lat2, lon2 = bus2.get("latitud"), bus2.get("longitud")

            if lat1 is None or lat2 is None:
                continue

            dist = haversine(lat1, lon1, lat2, lon2)

            if dist <= distancia_m:
                dir1 = obtener_direccion(bus1)
                dir2 = obtener_direccion(bus2)

                if dir1 == "GRIS" or dir2 == "GRIS":
                    continue
                if dir1 != dir2:
                    continue

                pares.append({
                    "bus1": bus1.get("label", bus1.get("bus_id")),
                    "bus2": bus2.get("label", bus2.get("bus_id")),
                    "ruta1": bus1.get("ruta"),
                    "ruta2": bus2.get("ruta"),
                    "direccion1": dir1,
                    "direccion2": dir2,
                    "misma_direccion": True,
                    "distancia": round(dist, 1),
                    "latitud": (lat1 + lat2) / 2,
                    "longitud": (lon1 + lon2) / 2
                })

    return {
        "pares": pares,
        "total": len(pares),
        "misma_ruta": len([p for p in pares if p["ruta1"] == p["ruta2"]]),
        "diferente_ruta": len([p for p in pares if p["ruta1"] != p["ruta2"]])
    }


def analisis_velocidad(db: BusDatabase, minutos_atras: int = 5) -> Dict[str, Any]:
    """
    Analiza buses que no han avanzado (detenidos o tráfico lento).
    Compara posiciones entre capturas.
    """
    ahora = datetime.now()
    hace_minutos = ahora - timedelta(minutes=minutos_atras)

    conn = db.db_path
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT bus_id, MAX(timestamp) as ultimo
        FROM posiciones_buses
        GROUP BY bus_id
        HAVING ultimo >= ?
    """, (hace_minutos.strftime("%Y-%m-%d %H:%M:%S"),))

    buses_recientes = [row[0] for row in cursor.fetchall()]

    buses_detenidos = []
    buses_lentos = []

    for bus_id in buses_recientes:
        cursor.execute("""
            SELECT posicion, timestamp
            FROM posiciones_buses
            WHERE bus_id = ?
            ORDER BY timestamp DESC
            LIMIT 2
        """, (bus_id,))

        resultados = cursor.fetchall()

        if len(resultados) >= 2:
            pos_actual = resultados[0][0]
            pos_anterior = resultados[1][0]
            tiempo_diff = (datetime.strptime(resultados[0][1], "%Y-%m-%d %H:%M:%S") -
                          datetime.strptime(resultados[1][1], "%Y-%m-%d %H:%M:%S")).total_seconds()

            if tiempo_diff > 0:
                cambio_pos = abs(pos_actual - pos_anterior)
                velocidad = (cambio_pos / tiempo_diff) * 3.6  # m/s a km/h

                cursor.execute("""
                    SELECT label, ruta, latitud, longitud, destino_limpio
                    FROM posiciones_buses
                    WHERE bus_id = ? AND timestamp = ?
                """, (bus_id, resultados[0][1]))

                info = cursor.fetchone()

                if info:
                    bus_data = {
                        "bus_id": bus_id,
                        "label": info[0],
                        "ruta": info[1],
                        "latitud": info[2],
                        "longitud": info[3],
                        "destino_limpio": info[4]
                    }
                else:
                    bus_data = {"bus_id": bus_id, "ruta": None, "latitud": None, "destino_limpio": None}

                direccion = obtener_direccion(bus_data)
                bus_data["direccion"] = direccion

                if cambio_pos < MIN_POS_CHANGE:
                    buses_detenidos.append({
                        "bus_id": bus_id,
                        "label": info[0] if info else bus_id,
                        "ruta": info[1] if info else None,
                        "direccion": direccion,
                        "posicion": pos_actual,
                        "ultimo_cambio": cambio_pos
                    })
                elif velocidad < VELOCIDAD_LENTA:
                    buses_lentos.append({
                        "bus_id": bus_id,
                        "label": info[0] if info else bus_id,
                        "ruta": info[1] if info else None,
                        "direccion": direccion,
                        "velocidad_kmh": round(velocidad, 1)
                    })

    conn.close()

    detained_arriba = len([b for b in buses_detenidos if b.get("direccion") == "ARRIBA"])
    detained_abajo = len([b for b in buses_detenidos if b.get("direccion") == "ABAJO"])
    detained_gris = len([b for b in buses_detenidos if b.get("direccion") == "GRIS"])
    lentos_arriba = len([b for b in buses_lentos if b.get("direccion") == "ARRIBA"])
    lentos_abajo = len([b for b in buses_lentos if b.get("direccion") == "ABAJO"])
    lentos_gris = len([b for b in buses_lentos if b.get("direccion") == "GRIS"])

    return {
        "detenidos": buses_detenidos,
        "lentos": buses_lentos,
        "total_detenidos": len(buses_detenidos),
        "total_lentos": len(buses_lentos),
        "detenidos_arriba": detained_arriba,
        "detenidos_abajo": detained_abajo,
        "detenidos_gris": detained_gris,
        "lentos_arriba": lentos_arriba,
        "lentos_abajo": lentos_abajo,
        "lentos_gris": lentos_gris
    }


def esta_en_zona_portal(bus: Dict[str, Any]) -> bool:
    """
    Verifica si un bus está en la zona de un portal.
    Usa las coordenadas del portal en config.py.
    """
    lat = bus.get("latitud")
    lon = bus.get("longitud")
    
    if lat is None or lon is None:
        return False
    
    for nombre, (portal_lat, portal_lon) in PORTALES.items():
        distancia = haversine(lat, lon, portal_lat, portal_lon)
        if distancia <= RADIO_EXCLUSION_PORTAL:
            return True
    
    return False


def es_destino_portal(bus: Dict[str, Any]) -> bool:
    """
    Verifica si el destino del bus es un portal.
    Usa el campo destino_limpio.
    """
    destino = bus.get("destino_limpio", "")
    if not destino:
        return False
    
    for nombre in PORTALES.keys():
        if nombre.lower() in destino.lower():
            return True
    
    return False


def filtrar_buses_no_portal(buses: List[Dict]) -> List[Dict]:
    """
    Filtra los buses que están en zonas de portales.
    Excluye buses que están físicamente en zonas de portales
    o cuyo destino es un portal.
    """
    buses_filtrados = []
    for bus in buses:
        if not esta_en_zona_portal(bus) and not es_destino_portal(bus):
            buses_filtrados.append(bus)
    return buses_filtrados


def analizar_buses_detenidos_historico(db: BusDatabase, minutos_atras: int = None) -> Dict[str, Any]:
    """
    Analiza buses que han estado sin movimiento por un período de tiempo.
    Consulta el historial para detectar buses detenidos por mucho tiempo.
    """
    minutos = minutos_atras or MINUTAS_INACTIVIDAD
    ahora = datetime.now()
    hace_minutos = ahora - timedelta(minutes=minutos)
    
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT bus_id, MAX(timestamp) as ultimo
        FROM posiciones_buses
        GROUP BY bus_id
        HAVING ultimo >= ?
    """, (hace_minutos.strftime("%Y-%m-%d %H:%M:%S"),))
    
    buses_recientes = [row[0] for row in cursor.fetchall()]
    
    buses_detenidos = []
    buses_lentos = []
    
    for bus_id in buses_recientes:
        cursor.execute("""
            SELECT posicion, timestamp
            FROM posiciones_buses
            WHERE bus_id = ?
            ORDER BY timestamp DESC
            LIMIT 2
        """, (bus_id,))
        
        resultados = cursor.fetchall()
        
        if len(resultados) >= 2:
            pos_actual = resultados[0][0]
            pos_anterior = resultados[1][0]
            tiempo_diff = (datetime.strptime(resultados[0][1], "%Y-%m-%d %H:%M:%S") -
                        datetime.strptime(resultados[1][1], "%Y-%m-%d %H:%M:%S")).total_seconds()
            
            if tiempo_diff > 0:
                cambio_pos = abs(pos_actual - pos_anterior)
                velocidad = (cambio_pos / tiempo_diff) * 3.6
                
                cursor.execute("""
                    SELECT label, ruta, latitud, longitud, destino_limpio
                    FROM posiciones_buses
                    WHERE bus_id = ? AND timestamp = ?
                """, (bus_id, resultados[0][1]))
                
                info = cursor.fetchone()
                
                if info and info[2] is not None and info[3] is not None:
                    bus_data = {
                        "bus_id": bus_id,
                        "label": info[0],
                        "ruta": info[1],
                        "latitud": info[2],
                        "longitud": info[3],
                        "destino_limpio": info[4]
                    }
                else:
                    bus_data = {"bus_id": bus_id, "ruta": None, "latitud": None, "destino_limpio": None}
                
                direccion = obtener_direccion(bus_data)
                bus_data["direccion"] = direccion
                
                if cambio_pos < MIN_POS_CHANGE:
                    buses_detenidos.append({
                        "bus_id": bus_id,
                        "label": info[0] if info else bus_id,
                        "ruta": info[1] if info else None,
                        "direccion": direccion,
                        "posicion": pos_actual,
                        "ultimo_cambio": cambio_pos,
                        "tiempo_sin_mover": minutos
                    })
                elif velocidad < VELOCIDAD_LENTA:
                    buses_lentos.append({
                        "bus_id": bus_id,
                        "label": info[0] if info else bus_id,
                        "ruta": info[1] if info else None,
                        "direccion": direccion,
                        "velocidad_kmh": round(velocidad, 1)
                    })
    
    conn.close()
    
    return {
        "detenidos": buses_detenidos,
        "lentos": buses_lentos,
        "total_detenidos": len(buses_detenidos),
        "total_lentos": len(buses_lentos)
    }


def detectar_anomalias(db: BusDatabase) -> Dict[str, Any]:
    """
    Detecta anomalías en el sistema de transporte usando el historial de 1 hora.
    
    Tipos de anomalías:
    - Manifestación: ≥20 buses sin movimiento >10 min en radio de 500m
    - Trancón: ≥10 buses moviéndose lento en zona
    - Bus varado: bus quieto + buses alrededor lentos
    """
    maintenant = datetime.now()
    
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    hace_una_hora = maintenant - timedelta(minutes=TIEMPO_HISTORIAL_ANALISIS)
    
    cursor.execute("""
        SELECT bus_id, label, ruta, latitud, longitud, posicion, timestamp, destino_limpio
        FROM posiciones_buses
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
    """, (hace_una_hora.strftime("%Y-%m-%d %H:%M:%S"),))
    
    resultados = cursor.fetchall()
    conn.close()
    
    if not resultados:
        return {
            "timestamp": maintenant.isoformat(),
            "anomalias": [],
            "manifestaciones": [],
            "trancones": [],
            "buses_varados": [],
            "total_anomalias": 0
        }
    
    buses_por_id = {}
    for row in resultados:
        bus_id = row[0]
        if bus_id not in buses_por_id:
            buses_por_id[bus_id] = {
                "bus_id": bus_id,
                "label": row[1],
                "ruta": row[2],
                "latitud": row[3],
                "longitud": row[4],
                "posicion": row[5],
                "timestamp": row[6],
                "destino_limpio": row[7]
            }
    
    todas_capturas = db.obtener_captura_actual()
    todas_capturas = [b for b in todas_capturas if b.get("latitud") and b.get("longitud")]
    
    buses_no_portal = filtrar_buses_no_portal(todas_capturas)
    
    analisis_vel = analizar_buses_detenidos_historico(db, MINUTAS_INACTIVIDAD)
    
    buses_detenidos = [b for b in analisis_vel["detenidos"] 
                      if not esta_en_zona_portal(b) and not es_destino_portal(b)]
    buses_lentos = [b for b in analisis_vel["lentos"]
                   if not esta_en_zona_portal(b) and not es_destino_portal(b)]
    
    manifestaciones = detectar_manifestaciones(buses_detenidos)
    trancones = detectar_trancones(buses_lentos)
    varados = detectar_buses_varados(buses_detenidos, buses_lentos)
    
    anomalias = []
    for m in manifestaciones:
        anomalias.append({
            "tipo": "MANIFESTACION",
            "severidad": "ALTA",
            "mensaje": m["mensaje"],
            "cantidad": m["cantidad"],
            "latitud": m.get("latitud"),
            "longitud": m.get("longitud"),
            "buses": m.get("buses", [])
        })
    
    for t in trancones:
        anomalias.append({
            "tipo": "TRANCON",
            "severidad": "MEDIA",
            "mensaje": t["mensaje"],
            "cantidad": t["cantidad"],
            "latitud": t.get("latitud"),
            "longitud": t.get("longitud"),
            "buses": t.get("buses", [])
        })
    
    for v in varados:
        anomalias.append({
            "tipo": "BUS_VARADO",
            "severidad": "ALTA",
            "mensaje": v["mensaje"],
            "bus": v["bus"],
            "latitud": v.get("latitud"),
            "longitud": v.get("longitud"),
            "buses_vecinos": v.get("buses_vecinos", 0)
        })
    
    return {
        "timestamp": maintenant.isoformat(),
        "anomalias": anomalias,
        "manifestaciones": manifestaciones,
        "trancones": trancones,
        "buses_varados": varados,
        "total_anomalias": len(anomalias),
        "resumen": {
            "manifestaciones": len(manifestaciones),
            "trancones": len(trancones),
            "buses_varados": len(varados),
            "buses_detenidos": len(buses_detenidos),
            "buses_lentos": len(buses_lentos)
        }
    }


def detectar_manifestaciones(buses_detenidos: List[Dict]) -> List[Dict]:
    """
    Detecta posibles manifestaciones: ≥20 buses sin movimiento en radio de 500m.
    """
    if len(buses_detenidos) < UMBRAL_MANIFESTACION:
        return []
    
    clusters = []
    asignaciones = {}
    
    for i, bus in enumerate(buses_detenidos):
        lat = bus.get("latitud")
        lon = bus.get("longitud")
        if lat is None or lon is None:
            continue
        
        asignacion = -1
        for idx, cluster in enumerate(clusters):
            centro_lat, centro_lon, _ = cluster
            dist = haversine(lat, lon, centro_lat, centro_lon)
            if dist <= RADIO_ANOMALIA:
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
    
    resultados = []
    for idx, (lat, lon, count) in enumerate(clusters):
        if count >= UMBRAL_MANIFESTACION:
            buses_en_zona = [b for b, a in zip(buses_detenidos, asignaciones.items()) if a == idx]
            resultados.append({
                "latitud": lat,
                "longitud": lon,
                "cantidad": count,
                "mensaje": f"Posible manifestación con {count} buses detenidos",
                "buses": [b["bus_id"] for b in buses_en_zona[:10]]
            })
    
    return resultados


def detectar_trancones(buses_lentos: List[Dict]) -> List[Dict]:
    """
    Detecta trancones: ≥10 buses moviéndose lento en zona.
    """
    if len(buses_lentos) < UMBRAL_TRANCON:
        return []
    
    clusters = []
    asignaciones = {}
    
    for i, bus in enumerate(buses_lentos):
        lat = bus.get("latitud")
        lon = bus.get("longitud")
        if lat is None or lon is None:
            continue
        
        asignacion = -1
        for idx, cluster in enumerate(clusters):
            centro_lat, centro_lon, _ = cluster
            dist = haversine(lat, lon, centro_lat, centro_lon)
            if dist <= RADIO_ANOMALIA:
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
    
    resultados = []
    for idx, (lat, lon, count) in enumerate(clusters):
        if count >= UMBRAL_TRANCON:
            buses_en_zona = [b for b, a in zip(buses_lentos, asignaciones.items()) if a == idx]
            resultados.append({
                "latitud": lat,
                "longitud": lon,
                "cantidad": count,
                "mensaje": f"Trancón detectado con {count} buses lentos",
                "buses": [b["bus_id"] for b in buses_en_zona[:10]]
            })
    
    return resultados


def detectar_buses_varados(buses_detenidos: List[Dict], buses_lentos: List[Dict]) -> List[Dict]:
    """
    Detecta buses varados: bus sin movimiento + buses alrededor moviéndose lento.
    """
    resultados = []
    
    for bus_det in buses_detenidos:
        lat = bus_det.get("latitud")
        lon = bus_det.get("longitud")
        if lat is None or lon is None:
            continue
        
        buses_vecinos_lentos = 0
        for bus_len in buses_lentos:
            lat2 = bus_len.get("latitud")
            lon2 = bus_len.get("longitud")
            if lat2 is None or lon2 is None:
                continue
            
            dist = haversine(lat, lon, lat2, lon2)
            if dist <= MIN_DISTANCE_ALERT * 2:
                buses_vecinos_lentos += 1
        
        if buses_vecinos_lentos >= 3:
            resultados.append({
                "bus": bus_det["bus_id"],
                "label": bus_det.get("label"),
                "latitud": lat,
                "longitud": lon,
                "mensaje": f"Bus {bus_det.get('label', bus_det['bus_id'])} varado con {buses_vecinos_lentos} buses lentos alrededor",
                "buses_vecinos": buses_vecinos_lentos
            })
    
    return resultados


def formatear_anomalias(analisis: Dict) -> str:
    """
    Formatea el análisis de anomalías para mostrar en consola.
    """
    lines = []
    lines.append("\n" + "=" * 50)
    lines.append("       DETECCION DE ANOMALIAS")
    lines.append("=" * 50)
    lines.append(f"Fecha: {analisis['timestamp']}")
    lines.append("")
    
    resumen = analisis.get("resumen", {})
    lines.append(f"Buses sin movimiento: {resumen.get('buses_detenidos', 0)}")
    lines.append(f"Buses lentos: {resumen.get('buses_lentos', 0)}")
    lines.append("")
    
    if analisis.get("manifestaciones"):
        lines.append("!" * 20)
        lines.append(" MANIFESTACIONES DETECTADAS")
        lines.append("!" * 20)
        for m in analisis["manifestaciones"]:
            lines.append(f"  [{m['cantidad']} buses] {m['mensaje']}")
        lines.append("")
    
    if analisis.get("trancones"):
        lines.append("=" * 20)
        lines.append(" TRANCONES DETECTADOS")
        lines.append("=" * 20)
        for t in analisis["trancones"]:
            lines.append(f"  [{t['cantidad']} buses] {t['mensaje']}")
        lines.append("")
    
    if analisis.get("buses_varados"):
        lines.append("=" * 20)
        lines.append(" BUSES VARADOS")
        lines.append("=" * 20)
        for v in analisis["buses_varados"]:
            lines.append(f"  {v['mensaje']}")
        lines.append("")
    
    if not analisis.get("anomalias"):
        lines.append("  No se detectaron anomalías.")
    
    return "\n".join(lines)


def analisis_por_ruta(buses: List[Dict], db: BusDatabase, ruta: str = None) -> Dict[str, Any]:
    """
    Análisis específico de una o todas las rutas.
    """
    if ruta:
        buses_filtrados = [b for b in buses if b.get("ruta") == ruta]
    else:
        buses_filtrados = buses

    densidad = analisis_densidad(buses_filtrados)
    proximidad = analisis_proximidad(buses_filtrados)

    rutas_contadas = defaultdict(int)
    for b in buses_filtrados:
        rutas_contadas[b.get("ruta", "unknown")] += 1

    velocidad_promedio = {}
    for r, count in rutas_contadas.items():
        velocidad_promedio[r] = round(count * 1.5, 1)  # Estimación

    return {
        "ruta": ruta,
        "total_buses": len(buses_filtrados),
        "densidad": densidad,
        "proximidad": proximidad,
        "buses_por_ruta": dict(rutas_contadas),
        "velocidad_estimada": velocidad_promedio
    }


def generar_resumen(db: BusDatabase) -> Dict[str, Any]:
    """
    Genera un resumen completo de análisis.
    """
    buses = db.obtener_ultimas_posiciones(1000)

    densidad = analisis_densidad(buses)
    proximidad = analisis_proximidad(buses)
    velocidad = analisis_velocidad(db)

    alertas = []
    for zona in densidad["zonas"]:
        if zona["cantidad"] >= ALERT_THRESHOLD:
            alertas.append({
                "tipo": "ALTA_DENSIDAD",
                "zona": f"({zona['latitud']:.4f}, {zona['longitud']:.4f})",
                "cantidad": zona["cantidad"],
                "mensaje": f"Zona con {zona['cantidad']} buses (umbral: {ALERT_THRESHOLD})"
            })

    if proximidad["total"] > 20:
        alertas.append({
            "tipo": "MUCHOS_CERCANOS",
            "cantidad": proximidad["total"],
            "mensaje": f"{proximidad['total']} pares de buses muy cercanos"
        })

    if velocidad["total_detenidos"] > 5:
        alertas.append({
            "tipo": "BUSES_DETENIDOS",
            "cantidad": velocidad["total_detenidos"],
            "mensaje": f"{velocidad['total_detenidos']} buses detectados como detenidos"
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "buses_analizados": len(buses),
        "densidad": densidad,
        "proximidad": proximidad,
        "velocidad": velocidad,
        "alertas": alertas,
        "alertas_count": len(alertas)
    }


def analizar_captura_actual(db: BusDatabase) -> Dict[str, Any]:
    """
    Analiza solo la última captura (tabla captura_actual).
    No consulta el histórico.
    """
    buses = db.obtener_captura_actual()

    if not buses:
        return {
            "timestamp": datetime.now().isoformat(),
            "buses_analizados": 0,
            "densidad": {"zonas": []},
            "proximidad": {"pares": [], "total": 0},
            "velocidad": {"detenidos": [], "lentos": [], "total_detenidos": 0, "total_lentos": 0},
            "alertas": [],
            "alertas_count": 0
        }

    densidad = analisis_densidad(buses)
    proximidad = analisis_proximidad(buses)

    alertas = []
    for zona in densidad.get("zonas", []):
        if zona["cantidad"] >= ALERT_THRESHOLD:
            alertas.append({
                "tipo": "ALTA_DENSIDAD",
                "zona": f"({zona['latitud']:.4f}, {zona['longitud']:.4f})",
                "cantidad": zona["cantidad"],
                "mensaje": f"Zona con {zona['cantidad']} buses (umbral: {ALERT_THRESHOLD})"
            })

    if proximidad["total"] > 20:
        alertas.append({
            "tipo": "MUCHOS_CERCANOS",
            "cantidad": proximidad["total"],
            "mensaje": f"{proximidad['total']} pares de buses muy cercanos"
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "buses_analizados": len(buses),
        "densidad": densidad,
        "proximidad": proximidad,
        "velocidad": {"detenidos": [], "lentos": [], "total_detenidos": 0, "total_lentos": 0},
        "alertas": alertas,
        "alertas_count": len(alertas)
    }


def analizar_buses_directo(buses: List[Dict], db: BusDatabase = None) -> Dict[str, Any]:
    """
    Analiza una lista de buses directamente (sin usar base de datos).
    Para análisis en tiempo real durante el monitoreo.
    Si se pasa db, también calcula velocidad comparando con captura anterior.
    """
    if not buses:
        return {
            "timestamp": datetime.now().isoformat(),
            "buses_analizados": 0,
            "densidad": {"zonas": []},
            "proximidad": {"pares": [], "total": 0},
            "velocidad": {"detenidos": [], "lentos": [], "total_detenidos": 0, "total_lentos": 0},
            "alertas": [],
            "alertas_count": 0
        }

    densidad = analisis_densidad(buses)
    proximidad = analisis_proximidad(buses)

    if db:
        velocidad = db.comparar_velocidad()
    else:
        velocidad = {"detenidos": [], "lentos": [], "total_detenidos": 0, "total_lentos": 0}

    alertas = []
    for zona in densidad.get("zonas", []):
        if zona["cantidad"] >= ALERT_THRESHOLD:
            alertas.append({
                "tipo": "ALTA_DENSIDAD",
                "zona": f"({zona['latitud']:.4f}, {zona['longitud']:.4f})",
                "cantidad": zona["cantidad"],
                "mensaje": f"Zona con {zona['cantidad']} buses (umbral: {ALERT_THRESHOLD})"
            })

    if proximidad["total"] > 20:
        alertas.append({
            "tipo": "MUCHOS_CERCANOS",
            "cantidad": proximidad["total"],
            "mensaje": f"{proximidad['total']} pares de buses muy cercanos"
        })

    if velocidad["total_detenidos"] > 5:
        alertas.append({
            "tipo": "BUSES_DETENIDOS",
            "cantidad": velocidad["total_detenidos"],
            "mensaje": f"{velocidad['total_detenidos']} buses detectados como detenidos"
        })

    if velocidad["total_lentos"] > 20:
        alertas.append({
            "tipo": "BUSES_LENTOS",
            "cantidad": velocidad["total_lentos"],
            "mensaje": f"{velocidad['total_lentos']} buses en tráfico lento"
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "buses_analizados": len(buses),
        "densidad": densidad,
        "proximidad": proximidad,
        "velocidad": velocidad,
        "alertas": alertas,
        "alertas_count": len(alertas)
    }


def formatear_salida(analisis: Dict) -> str:
    """
    Formatea el análisis para mostrar en consola.
    """
    lines = []
    lines.append("\n" + "=" * 50)
    lines.append("       ANALISIS DE TRANCONES")
    lines.append("=" * 50)
    lines.append(f"Fecha: {analisis['timestamp']}")
    lines.append(f"Buses analizados: {analisis['buses_analizados']}")
    lines.append("")

    densidad = analisis["densidad"]
    if densidad["zonas"]:
        lines.append("[ZONAS CONGESTIONADAS]")
        for i, zona in enumerate(densidad["zonas"][:5], 1):
            dir_info = zona.get("direccion", {})
            dir_norte = dir_info.get('NORTE', 0)
            dir_sur = dir_info.get('SUR', 0)
            dir_oriente = dir_info.get('ORIENTE', 0)
            dir_occidente = dir_info.get('OCCIDENTE', 0)
            dir_str = f" (N:{dir_norte}, S:{dir_sur}, E:{dir_oriente}, O:{dir_occidente})"
            lines.append(f"  {i}. ({zona['latitud']:.4f}, {zona['longitud']:.4f}): "
                        f"{zona['cantidad']} buses{dir_str}")
        lines.append("")

    proximidad = analisis["proximidad"]
    if proximidad["total"] > 0:
        lines.append(f"[BUSES CERCANOS ({MIN_DISTANCE_ALERT}m)]")
        lines.append(f"  Total: {proximidad['total']} pares")
        lines.append(f"  Misma ruta: {proximidad['misma_ruta']}")
        lines.append(f"  Diferente ruta: {proximidad['diferente_ruta']}")
        lines.append("")

    velocidad = analisis["velocidad"]
    if velocidad["total_detenidos"] > 0 or velocidad["total_lentos"] > 0:
        lines.append("[BUSES SIN MOVIMIENTO]")
        lines.append(f"  Detenidos: {velocidad['total_detenidos']} (↑:{velocidad.get('detenidos_arriba', 0)}, ↓:{velocidad.get('detenidos_abajo', 0)}, ?:{velocidad.get('detenidos_gris', 0)})")
        lines.append(f"  Lentos: {velocidad['total_lentos']} (↑:{velocidad.get('lentos_arriba', 0)}, ↓:{velocidad.get('lentos_abajo', 0)}, ?:{velocidad.get('lentos_gris', 0)})")
        lines.append("")

    if analisis["alertas"]:
        lines.append("!" * 20)
        lines.append(" ALERTAS DETECTADAS")
        lines.append("!" * 20)
        for alerta in analisis["alertas"]:
            lines.append(f"  [{alerta['tipo']}] {alerta['mensaje']}")
        lines.append("")

    return "\n".join(lines)


def obtener_configuracion() -> Dict[str, Any]:
    """Retorna la configuración actual del análisis."""
    return {
        "CLUSTER_RADIUS": CLUSTER_RADIUS,
        "MIN_DISTANCE_ALERT": MIN_DISTANCE_ALERT,
        "MIN_POS_CHANGE": MIN_POS_CHANGE,
        "VELOCIDAD_LENTA": VELOCIDAD_LENTA,
        "VELOCIDAD_DETENIDO": VELOCIDAD_DETENIDO,
        "ALERT_THRESHOLD": ALERT_THRESHOLD
    }


def generar_grafica(buses: List[Dict], densidad: Dict = None, velocidad: Dict = None,
                    titolo: str = "Mapa de Buses Transmilenio") -> Optional[Any]:
    """
    Genera una gráfica de los buses usando matplotlib.
    Retorna la figura si éxito, None si matplotlib no está disponible.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.warning("matplotlib no está instalado. No se puede mostrar la gráfica.")
        return None

    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_title(titolo, fontsize=16, fontweight='bold')
    ax.set_xlabel("Longitud", fontsize=12)
    ax.set_ylabel("Latitud", fontsize=12)

    lats = []
    lons = []
    labels = []
    rutas_set = set()

    for bus in buses:
        lat = bus.get("latitud")
        lon = bus.get("longitud")
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)
            label = bus.get("label", bus.get("bus_id", "?"))
            labels.append(label)
            rutas_set.add(bus.get("ruta", "unknown"))

    if not lats:
        ax.text(0.5, 0.5, "No hay datos de buses", ha='center', va='center', transform=ax.transAxes)
        return fig

    COLOR_ARRIBA = "#2196F3"
    COLOR_ABAJO = "#F44336"
    COLOR_GRIS = "gray"

    COLOR_DIRECCION = {
        "ARRIBA": COLOR_ARRIBA,
        "ABAJO": COLOR_ABAJO,
        "GRIS": COLOR_GRIS
    }

    MARKER_ROTATION = {
        "ARRIBA": 0,
        "ABAJO": 180,
        "GRIS": 0
    }

    colores_direccion = {}
    for bus in buses:
        if bus.get("latitud"):
            direccion = obtener_direccion(bus)
            colores_direccion[bus.get("label", bus.get("bus_id", ""))] = COLOR_DIRECCION.get(direccion, "gray")

    colores_buses = [colores_direccion.get(b.get("label", b.get("bus_id", "")), "gray") for b in buses if b.get("latitud")]

    ax.scatter(lons, lats, c=colores_buses, s=100, alpha=0.7, edgecolors='black', linewidth=0.5, marker='>')

    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    lon_padding = (lon_max - lon_min) * 0.1 if lon_max != lon_min else 0.01
    lat_padding = (lat_max - lat_min) * 0.1 if lat_max != lat_min else 0.01
    ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
    ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)

    patches = [
        mpatches.Patch(color=COLOR_ARRIBA, label='^ Arriba'),
        mpatches.Patch(color=COLOR_ABAJO, label='v Abajo'),
        mpatches.Patch(color=COLOR_GRIS, label='? Sin angulo')
    ]
    ax.legend(handles=patches, loc='upper left', fontsize=10)

    if densidad and densidad.get("zonas"):
        for zona in densidad["zonas"][:5]:
            circle = plt.Circle(
                (zona["longitud"], zona["latitud"]),
                CLUSTER_RADIUS / 111000,
                fill=False,
                color='red',
                linewidth=2,
                linestyle='--',
                alpha=0.8
            )
            ax.add_patch(circle)
            ax.annotate(
                f"{zona['cantidad']}",
                (zona["longitud"], zona["latitud"]),
                color='red',
                fontsize=10,
                fontweight='bold'
            )

    if velocidad and velocidad.get("detenidos"):
        for bus in velocidad["detenidos"]:
            lat = bus.get("latitud")
            lon = bus.get("longitud")
            if lat and lon:
                ax.scatter([lon], [lat], c='red', s=200, marker='X', edgecolors='black', linewidth=2, zorder=5)

    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    return fig


def mostrar_grafica(buses: List[Dict], densidad: Dict = None, velocidad: Dict = None,
                    archivo: str = "mapa_buses.png"):
    """
    Guarda la gráfica como imagen (en lugar de abrir ventana).
    """
    fig = generar_grafica(buses, densidad, velocidad)
    if fig:
        fig.savefig(archivo, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"\n[Grafica guardada en {archivo}]")
    else:
        print("No se pudo generar la grafica.")


def guardar_grafica(buses: List[Dict], densidad: Dict = None, velocidad: Dict = None,
                    archivo: str = "mapa_buses.png"):
    """
    Guarda la gráfica como imagen.
    """
    fig = generar_grafica(buses, densidad, velocidad)
    if fig:
        fig.savefig(archivo, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"Gráfica guardada en {archivo}")
        return True
    return False