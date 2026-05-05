"""
Configuración del sistema de monitoreo de buses Transmilenio.
EDITAR ESTE ARCHIVO PARA PERSONALIZAR EL SISTEMA.
"""

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
RUTAS_CSV = "rutas.csv"

# Configuración de la base de datos
DATABASE_PATH = "buses.db"

# Configuración de análisis de trancones
CLUSTER_RADIUS = 100          # Radio de clustering en metros
MIN_DISTANCE_ALERT = 50        # Distancia mínima para alertar trancón (m)
MIN_POS_CHANGE = 10           # Cambio mínimo en metros para considerar movimiento
VELOCIDAD_LENTA = 15          # km/h considerado como tráfico lento
VELOCIDAD_DETENIDO = 5        # km/h considerado como detenido
ALERT_THRESHOLD = 10          # Cantidad de buses para activar alerta de zona
MOSTRAR_GRAFICA = True        # Mostrar ventana con gráfica de clusters

# Configuración de logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR