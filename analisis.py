"""
Módulo de análisis de trancones para buses Transmilenio.
Analiza densidad, proximidad y velocidad de los buses.
"""

import math
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from database import BusDatabase
from config import (
    CLUSTER_RADIUS,
    MIN_DISTANCE_ALERT,
    MIN_POS_CHANGE,
    VELOCIDAD_LENTA,
    VELOCIDAD_DETENIDO,
    ALERT_THRESHOLD
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


def obtener_direccion(bus: Dict[str, Any]) -> str:
    """
    Determina la dirección del bus (Sur->Norte o Norte->Sur).
    Retorna: "SUR_A_NORTE" o "NORTE_A_SUR"
    """
    destino = bus.get("destino_limpio", bus.get("Final_Destination", ""))

    for d in DESTINOS_SUR_A_NORTE:
        if destino and d.lower() in destino.lower():
            return "SUR_A_NORTE"

    for d in DESTINOS_NORTE_A_SUR:
        if destino and d.lower() in destino.lower():
            return "NORTE_A_SUR"

    lat = bus.get("latitud") or bus.get("latitude")
    if lat is not None:
        if lat > LATITUD_CENTRO_BOGOTA:
            return "SUR_A_NORTE"
        else:
            return "NORTE_A_SUR"

    return "NORTE_A_SUR"


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
                pares.append({
                    "bus1": bus1.get("label", bus1.get("bus_id")),
                    "bus2": bus2.get("label", bus2.get("bus_id")),
                    "ruta1": bus1.get("ruta"),
                    "ruta2": bus2.get("ruta"),
                    "direccion1": dir1,
                    "direccion2": dir2,
                    "misma_direccion": dir1 == dir2,
                    "distancia": round(dist, 1),
                    "latitud": (lat1 + lat2) / 2,
                    "longitud": (lon1 + lon2) / 2
                })

    return {
        "pares": pares,
        "total": len(pares),
        "misma_ruta": len([p for p in pares if p["ruta1"] == p["ruta2"]]),
        "diferente_ruta": len([p for p in pares if p["ruta1"] != p["ruta2"]]),
        "misma_direccion": len([p for p in pares if p["misma_direccion"]]),
        "diferente_direccion": len([p for p in pares if not p["misma_direccion"]])
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

    detained_sur_norte = len([b for b in buses_detenidos if b.get("direccion") == "SUR_A_NORTE"])
    detained_norte_sur = len([b for b in buses_detenidos if b.get("direccion") == "NORTE_A_SUR"])
    lentos_sur_norte = len([b for b in buses_lentos if b.get("direccion") == "SUR_A_NORTE"])
    lentos_norte_sur = len([b for b in buses_lentos if b.get("direccion") == "NORTE_A_SUR"])

    return {
        "detenidos": buses_detenidos,
        "lentos": buses_lentos,
        "total_detenidos": len(buses_detenidos),
        "total_lentos": len(buses_lentos),
        "detenidos_sur_a_norte": detained_sur_norte,
        "detenidos_norte_a_sur": detained_norte_sur,
        "lentos_sur_a_norte": lentos_sur_norte,
        "lentos_norte_a_sur": lentos_norte_sur
    }


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
            dir_str = f" (S→N:{dir_info.get('SUR_A_NORTE', 0)}, N→S:{dir_info.get('NORTE_A_SUR', 0)})"
            lines.append(f"  {i}. ({zona['latitud']:.4f}, {zona['longitud']:.4f}): "
                        f"{zona['cantidad']} buses{dir_str}")
        lines.append("")

    proximidad = analisis["proximidad"]
    if proximidad["total"] > 0:
        lines.append(f"[BUSES CERCANOS ({MIN_DISTANCE_ALERT}m)]")
        lines.append(f"  Total: {proximidad['total']} pares")
        lines.append(f"  Misma ruta: {proximidad['misma_ruta']}")
        lines.append(f"  Diferente ruta: {proximidad['diferente_ruta']}")
        if "misma_direccion" in proximidad:
            lines.append(f"  Misma dirección: {proximidad['misma_direccion']}")
            lines.append(f"  Diferente dirección: {proximidad['diferente_direccion']}")
        lines.append("")

    velocidad = analisis["velocidad"]
    if velocidad["total_detenidos"] > 0 or velocidad["total_lentos"] > 0:
        lines.append("[BUSES SIN MOVIMIENTO]")
        lines.append(f"  Detenidos: {velocidad['total_detenidos']} (S→N:{velocidad.get('detenidos_sur_a_norte', 0)}, N→S:{velocidad.get('detenidos_norte_a_sur', 0)})")
        lines.append(f"  Lentos: {velocidad['total_lentos']} (S→N:{velocidad.get('lentos_sur_a_norte', 0)}, N→S:{velocidad.get('lentos_norte_a_sur', 0)})")
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

    COLOR_SUR_A_NORTE = "blue"
    COLOR_NORTE_A_SUR = "red"

    colores_direccion = {}
    for bus in buses:
        if bus.get("latitud"):
            direccion = obtener_direccion(bus)
            colores_direccion[bus.get("label", bus.get("bus_id", ""))] = COLOR_SUR_A_NORTE if direccion == "SUR_A_NORTE" else COLOR_NORTE_A_SUR

    colores_buses = [colores_direccion.get(b.get("label", b.get("bus_id", "")), "gray") for b in buses if b.get("latitud")]

    ax.scatter(lons, lats, c=colores_buses, s=50, alpha=0.7, edgecolors='black', linewidth=0.5)

    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    lon_padding = (lon_max - lon_min) * 0.1 if lon_max != lon_min else 0.01
    lat_padding = (lat_max - lat_min) * 0.1 if lat_max != lat_min else 0.01
    ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
    ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)

    sur_norte_patch = mpatches.Patch(color=COLOR_SUR_A_NORTE, label='Sur → Norte')
    norte_sur_patch = mpatches.Patch(color=COLOR_NORTE_A_SUR, label='Norte → Sur')
    ax.legend(handles=[sur_norte_patch, norte_sur_patch], loc='upper left', fontsize=10)

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
        fig.savefig(archivo, dpi=150, bbox_inches='tight')
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
        fig.savefig(archivo, dpi=150, bbox_inches='tight')
        logger.info(f"Gráfica guardada en {archivo}")
        return True
    return False