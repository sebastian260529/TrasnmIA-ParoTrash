"""
Configuración del sistema de monitoreo de buses Transmilenio.
EDITAR ESTE ARCHIVO PARA PERSONALIZAR EL SISTEMA.
"""

import os

# Ruta base del proyecto (2 niveles arriba desde config/)
# config/config.py -> ChatBot
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Credenciales para la API (obtener de la app TransMiApp o inspectores)
API_CONFIG = {
    "appid": "9a2c3b48f0c24ae9bfba38e94f27c3ea",
    "uuid": "32095e89-bf3c-4382-8d21-c1fab88221ad",
    "version": "27",
    "user_agent": "okhttp/4.12.0",
    "base_url": "https://tmsa-transmiapp-shvpc.uc.r.appspot.com"
}

# Intervalo de monitoreo en segundos (default: 60 segundos)
MONITOR_INTERVAL = 60

# Archivo CSV con las rutas a monitorear
# El CSV debe tener columnas: Route_ID, Final_Destination
RUTAS_CSV = os.path.join(BASE_DIR, "data", "rutas.csv")

# Configuración de la base de datos
DATABASE_PATH = os.path.join(BASE_DIR, "data", "buses.db")

# Configuración de análisis de trancones
CLUSTER_RADIUS = 100          # Radio de clustering en metros
MIN_DISTANCE_ALERT = 50        # Distancia mínima para alertar trancón (m)
MIN_POS_CHANGE = 10           # Cambio mínimo en metros para considerar movimiento
VELOCIDAD_LENTA = 20           # km/h considerado como tráfico lento (aumentado de 15)
VELOCIDAD_DETENIDO = 5        # km/h considerado como detenido
ALERT_THRESHOLD = 10          # Cantidad de buses para activar alerta de zona
MOSTRAR_GRAFICA = True        # Mostrar ventana con gráfica de clusters

# Configuración de análisis de anomalías
RADIO_EXCLUSION_PORTAL = 300        # Radio de exclusión alrededor de portales (metros)
MINUTAS_INACTIVIDAD = 5            # Minutos sin movimiento para considerarse detenido (reducido de 10)
TIEMPO_HISTORIAL_ANALISIS = 60       # Minutos de historial para análisis (1 hora)
NUM_CAPTURAS_HISTORIAL = 60          # Número de capturas a guardar para análisis

# Configuración de detección de anomalías
UMBRAL_MANIFESTACION = 20           # Buses sin movimiento para manifestar
UMBRAL_TRANCON = 8                  # Buses lentos para trancón (reducido de 10)
RADIO_ANOMALIA = 500               # Radio para clustering de anomalías (metros)
DISTANCIA_MAX_CLUSTER = 300        # Distancia máxima entre buses consecutivos para clustering lineal (metros)

# Portales con coordenadas (latitud, longitud)
PORTALES = {
    "Portal Norte": (4.7700, -74.0300),
    "Portal 80": (4.7100, -74.0500),
    "Portal Suba": (4.6900, -74.0800),
    "Portal 20": (4.4200, -74.1500),
    "Portal Sur": (4.4000, -74.1700),
    "Portal Tunal": (4.5700, -74.1200),
    "Portal Usme": (4.6000, -74.1300),
    "Portal Américas": (4.6800, -74.1100),
    "Portal El Dorado": (4.6900, -74.1000),
    "Portal 20 de Julio": (4.4200, -74.1500),
}

# Configuración de logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR