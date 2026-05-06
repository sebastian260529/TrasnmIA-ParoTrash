"""
Módulo de Generación de Gráficas.
Genera mapas de anomalías y buses activos.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ruta absoluta para gráficos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRAFICOS_DIR = os.path.join(BASE_DIR, "data", "graficos")

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_DISPONIBLE = True
except ImportError:
    MATPLOTLIB_DISPONIBLE = False

from database.database import BusDatabase
from analisis.anomaly_detector import detectar_anomalias, obtener_direccion
from config.config import RADIO_ANOMALIA


def generar_nombre_archivo(tipo: str) -> str:
    """Genera nombre de archivo con timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(GRAFICOS_DIR, f"{tipo}_{timestamp}.png")


def generar_mapa_buses(db: BusDatabase, guardar: bool = True) -> Optional[str]:
    """
    Genera mapa de buses activos (igual al anterior).
    Returns: ruta del archivo guardado o None.
    """
    if not MATPLOTLIB_DISPONIBLE:
        print("matplotlib no está instalado")
        return None
    
    captura = db.obtener_captura_actual()
    buses = [b for b in captura if b.get("latitud") and b.get("longitud")]
    
    if not buses:
        print("No hay buses con datos")
        return None
    
    analisis = detectar_anomalias(db)
    
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_title(f"Mapa de Buses Transmilenio - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                 fontsize=16, fontweight='bold')
    ax.set_xlabel("Longitud", fontsize=12)
    ax.set_ylabel("Latitud", fontsize=12)
    
    lats = [b["latitud"] for b in buses]
    lons = [b["longitud"] for b in buses]
    
    COLOR_ARRIBA = "#2196F3"
    COLOR_ABAJO = "#F44336"
    COLOR_GRIS = "gray"
    
    colores = []
    for bus in buses:
        direccion = obtener_direccion(bus)
        colores.append(COLOR_ARRIBA if direccion == "ARRIBA" else 
                    COLOR_ABAJO if direccion == "ABAJO" else COLOR_GRIS)
    
    ax.scatter(lons, lats, c=colores, s=100, alpha=0.7, edgecolors='black', linewidth=0.5, marker='>')
    
    if lons and lats:
        ax.set_xlim(min(lons) - 0.01, max(lons) + 0.01)
        ax.set_ylim(min(lats) - 0.01, max(lats) + 0.01)
    
    patches = [
        mpatches.Patch(color=COLOR_ARRIBA, label='^ Arriba'),
        mpatches.Patch(color=COLOR_ABAJO, label='v Abajo'),
        mpatches.Patch(color=COLOR_GRIS, label='? Sin angulo')
    ]
    ax.legend(handles=patches, loc='upper left', fontsize=10)
    
    resumen = analisis.get("resumen", {})
    info_text = f"Buses activos: {resumen.get('buses_sin_movimiento', 0) + resumen.get('buses_lentos', 0) + resumen.get('buses_normales', 0)}"
    info_text += f" | Detenidos: {resumen.get('buses_sin_movimiento', 0)}"
    info_text += f" | Lentos: {resumen.get('buses_lentos', 0)}"
    info_text += f" | Normales: {resumen.get('buses_normales', 0)}"
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=10, 
           verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if guardar:
        archivo = generar_nombre_archivo("buses")
        fig.savefig(archivo, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return archivo
    
    return fig


def generar_mapa_anomalias(db: BusDatabase, guardar: bool = True) -> Optional[str]:
    """
    Genera mapa de anomalías detectadas.
    Returns: ruta del archivo guardado o None.
    """
    if not MATPLOTLIB_DISPONIBLE:
        print("matplotlib no está instalado")
        return None
    
    analisis = detectar_anomalias(db)
    anomalias = analisis.get("anomalias", [])
    
    captura = db.obtener_captura_actual()
    buses = [b for b in captura if b.get("latitud") and b.get("longitud")]
    
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_title(f"Mapa de Anomalías Transmilenio - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                 fontsize=16, fontweight='bold')
    ax.set_xlabel("Longitud", fontsize=12)
    ax.set_ylabel("Latitud", fontsize=12)
    
    colores_por_tipo = {
        "MANIFESTACION": "red",
        "TRANCON": "orange",
        "BUS_VARADO": "black"
    }
    
    if buses:
        lats = [b["latitud"] for b in buses]
        lons = [b["longitud"] for b in buses]
        ax.scatter(lons, lats, c='lightgray', s=20, alpha=0.3, label='Buses')
    
    if anomalias:
        for anom in anomalias:
            tipo = anom.get("tipo", "UNKNOWN")
            coords = anom.get("coordenadas", {})
            lat = coords.get("latitud")
            lon = coords.get("longitud")
            color = colores_por_tipo.get(tipo, "gray")
            
            if lat and lon:
                radio = RADIO_ANOMALIA / 111000
                circle = plt.Circle((lon, lat), radio, fill=False, color=color, linewidth=2, linestyle='--')
                ax.add_patch(circle)
                ax.scatter([lon], [lat], c=color, s=200, marker='X', edgecolors='black', linewidth=2, zorder=5)
                
                label = f"{tipo} {anom.get('porcentaje_confianza', 0)}%"
                ax.annotate(label, (lon, lat + 0.005), fontsize=8, ha='center')
        
        if lons and lats:
            ax.set_xlim(min(lons) - 0.02, max(lons) + 0.02)
            ax.set_ylim(min(lats) - 0.02, max(lats) + 0.02)
    else:
        if buses:
            ax.set_xlim(min(lons) - 0.02, max(lons) + 0.02)
            ax.set_ylim(min(lats) - 0.02, max(lats) + 0.02)
    
    patches = [
        mpatches.Patch(color='red', label='MANIFESTACION'),
        mpatches.Patch(color='orange', label='TRANCON'),
        mpatches.Patch(color='black', label='BUS_VARADO')
    ]
    ax.legend(handles=patches, loc='upper left', fontsize=10)
    
    resumen = analisis.get("resumen", {})
    info_text = f"Total anomalías: {resumen.get('total_anomalias', 0)}"
    info_text += f" | Manif: {resumen.get('manifestaciones', 0)}"
    info_text += f" | Trancon: {resumen.get('trancones', 0)}"
    info_text += f" | Varados: {resumen.get('buses_varados', 0)}"
    info_text += f" | Excluidos portal: {analisis.get('excluidos_portal', 0)}"
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=10,
           verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if guardar:
        archivo = generar_nombre_archivo("anomalias")
        fig.savefig(archivo, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return archivo
    
    return fig


def generar_todas_graficas(db: BusDatabase) -> Dict[str, str]:
    """
    Genera todas las gráficas.
    Returns: diccionario con rutas de archivos.
    """
    resultados = {}
    
    try:
        archivo_buses = generar_mapa_buses(db)
        if archivo_buses:
            resultados["buses"] = archivo_buses
            print(f"Grafica de buses guardada: {archivo_buses}")
    except Exception as e:
        print(f"Error generando grafica de buses: {e}")
    
    try:
        archivo_anomalias = generar_mapa_anomalias(db)
        if archivo_anomalias:
            resultados["anomalias"] = archivo_anomalias
            print(f"Grafica de anomalias guardada: {archivo_anomalias}")
    except Exception as e:
        print(f"Error generando grafica de anomalias: {e}")
    
    return resultados


def obtener_ultima_grafica(tipo: str = "buses") -> Optional[str]:
    """
    Obtiene la ruta de la última gráfica generada.
    tipo: 'buses' o 'anomalias'
    """
    if not os.path.exists(GRAFICOS_DIR):
        return None
    
    archivos = [f for f in os.listdir(GRAFICOS_DIR) if f.startswith(tipo)]
    if not archivos:
        return None
    
    archivos.sort(reverse=True)
    return os.path.join(GRAFICOS_DIR, archivos[0])