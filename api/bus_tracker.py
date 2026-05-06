"""
Módulo principal de monitoreo de buses Transmilenio.
Maneja la conexión con la API y el monitoreo continuo.
"""

import requests
import logging
import time
import signal
import sys
import csv
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from database.database import BusDatabase
from config.config import API_CONFIG, RUTAS_CSV, MONITOR_INTERVAL, DATABASE_PATH, MOSTRAR_GRAFICA
from analisis import generar_resumen, formatear_salida, generar_grafica, analizar_captura_actual, analizar_buses_directo

logger = logging.getLogger(__name__)


class BusTracker:
    """Sistema de monitoreo de buses Transmilenio."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db = BusDatabase(db_path)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.running = False
        self.rutas = self.cargar_rutas_desde_csv()
        self._setup_logging()

    def cargar_rutas_desde_csv(self, csv_path: str = None) -> List[Dict[str, str]]:
        """
        Carga las rutas desde el archivo CSV.
        Returns: Lista de diccionarios con {'ruta': Route_ID, 'nombre': Final_Destination}
        """
        csv_path = csv_path or RUTAS_CSV

        if not os.path.exists(csv_path):
            logger.warning(f"Archivo CSV no encontrado: {csv_path}")
            return []

        rutas_unicas = {}
        try:
            with open(csv_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    route_id = row.get('Route_ID', '').strip()
                    destino = row.get('Final_Destination', '').strip()
                    if route_id and destino:
                        clave = (route_id, destino)
                        if clave not in rutas_unicas:
                            rutas_unicas[clave] = {"ruta": route_id, "nombre": destino}

            resultado = list(rutas_unicas.values())
            logger.info(f"Cargadas {len(resultado)} rutas desde {csv_path}")
            return resultado

        except Exception as e:
            logger.error(f"Error leyendo CSV: {e}")
            return []

    def _setup_logging(self):
        """Configura el logging."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def _get_headers(self) -> Dict[str, str]:
        """Genera los headers para la API."""
        return {
            "appid": API_CONFIG["appid"],
            "uuid": API_CONFIG["uuid"],
            "version": API_CONFIG["version"],
            "user-agent": API_CONFIG["user_agent"],
            "content-type": "application/json"
        }

    def _build_payload(self, ruta: str, nombre: str) -> Dict[str, str]:
        """Construye el payload para la solicitud POST."""
        return {
            "ruta": ruta,
            "Nombre": nombre
        }

    def _extraer_coordenadas(self, datos: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Extrae coordenadas de la respuesta de forma automática.
        Detecta múltiples formatos posibles de la API.
        """
        # Formato conocido
        if "latitude" in datos and "longitude" in datos:
            if datos["latitude"] is not None and datos["longitude"] is not None:
                return {
                    "latitud": float(datos["latitude"]),
                    "longitud": float(datos["longitude"])
                }

        # Buscar en otros campos posibles
        for key in ["lat", "lng", "coords", "location", "pos", "gps"]:
            if key in datos:
                val = datos[key]
                if isinstance(val, dict):
                    if "lat" in val and "lon" in val:
                        return {"latitud": val["lat"], "longitud": val["lon"]}

        return None

    def obtener_buses(self, ruta: str, nombre: str) -> List[Dict[str, Any]]:
        """
        Obtiene los buses activos para una ruta específica.
        Returns: Lista de diccionarios con datos de cada bus.
        """
        url = f"{API_CONFIG['base_url']}/buses"
        headers = self._get_headers()
        payload = self._build_payload(ruta, nombre)

        try:
            logger.debug(f"Consultando: {ruta} - {nombre}")
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()

            datos = response.json()

            # La API puede devolver:
            # - Un diccionario con un solo bus
            # - Una lista de buses
            # - Un diccionario con clave "0", "1", etc.

            buses = []

            if isinstance(datos, list):
                buses = datos
            elif isinstance(datos, dict):
                # Verificar si es un solo bus o varios
                if "id" in datos and "latitude" in datos:
                    # Un solo bus
                    buses = [datos]
                else:
                    # Múltiples buses en claves numéricas
                    for key, value in datos.items():
                        if isinstance(value, dict) and "latitude" in value:
                            buses.append(value)

            # Agregar información de la ruta a cada bus
            for bus in buses:
                bus["ruta_extraida"] = ruta
                bus["destino_limpio"] = nombre

            return buses

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout consultando {ruta} - {nombre}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error consultando {ruta} - {nombre}: {e}")
        except Exception as e:
            logger.error(f"Error inesperado: {e}")

        return []

    def guardar_buses(self, buses: List[Dict[str, Any]]) -> int:
        """Guarda los buses en la base de datos. Returns: número de guardados."""
        guardados = 0

        for bus in buses:
            coords = self._extraer_coordenadas(bus)
            if coords:
                bus["latitude"] = coords["latitud"]
                bus["longitude"] = coords["longitud"]

            if self.db.guardar_posicion(bus):
                guardados += 1

        return guardados

    def escanear_rutas(self, rutas: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Escanea todas las rutas configuradas.
        Returns: Estadísticas del escaneo y lista de buses capturados.
        """
        if rutas is None:
            rutas = self.rutas

        total_buses = 0
        guardados = 0
        errores = []
        todos_los_buses = []

        logger.info(f"========================================")
        logger.info(f"INICIANDO ESCANEO PARALELO de {len(rutas)} rutas")
        logger.info(f"========================================")

        def procesar_ruta(item):
            ruta = item["ruta"]
            nombre = item["nombre"]
            logger.debug(f"Consultando ruta {ruta} - {nombre}...")
            buses = self.obtener_buses(ruta, nombre)
            return {"ruta": ruta, "nombre": nombre, "buses": buses}

        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = {executor.submit(procesar_ruta, item): item for item in rutas}

            for i, future in enumerate(as_completed(futures)):
                try:
                    resultado = future.result()
                    buses = resultado["buses"]
                    total_buses_captura = len(buses)
                    total_buses += total_buses_captura
                    todos_los_buses.extend(buses)

                    if buses:
                        g = self.guardar_buses(buses)
                        guardados += g
                        logger.info(f"[{i+1}/{len(rutas)}] {resultado['ruta']} - {resultado['nombre']}: {total_buses_captura} buses, {g} guardados")
                    else:
                        logger.info(f"[{i+1}/{len(rutas)}] {resultado['ruta']} - {resultado['nombre']}: sin buses activos")
                        errores.append(f"{resultado['ruta']} - {resultado['nombre']}")
                except Exception as e:
                    item = futures[future]
                    logger.error(f"ERROR en {item['ruta']} - {item['nombre']}: {e}")

        logger.info(f"========================================")
        logger.info(f"ESCANEO COMPLETADO: {total_buses} buses encontrados, {guardados} guardados en DB")
        logger.info(f"Rutas sin buses: {len(errores)}")
        logger.info(f"========================================")

        captura_anterior = self.db.obtener_captura_actual()
        if captura_anterior:
            self.db.guardar_captura_anterior(captura_anterior)

        self.db.limpiar_captura_actual()
        self.db.guardar_captura_actual(todos_los_buses)
        logger.info(f"Captura actual actualizada: {len(todos_los_buses)} buses en memoria")

        return {
            "buses": todos_los_buses,
            "total_buses_encontrados": total_buses,
            "guardados": guardados,
            "rutas_sin_buses": errores,
            "timestamp": datetime.now().isoformat()
        }

    def iniciar_monitoreo(self, intervalo: int = None, callback: Callable = None):
        """
        Inicia el monitoreo continuo de buses.
        Se detiene con Ctrl+C limpiamente.
        """
        self.running = True
        intervalo = intervalo or MONITOR_INTERVAL

        # Configurar manejador de señal para Ctrl+C
        def signal_handler(sig, frame):
            print("\n\n🛑 Deteniendo monitoreo...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info(f"=== INICIANDO MONITOREO CONTINUO ===")
        logger.info(f"Intervalo: {intervalo} segundos")
        logger.info(f"Rutas configuradas: {len(self.rutas)}")
        logger.info("Presionar Ctrl+C para detener")
        logger.info("=" * 40)

        contador = 0

        while self.running:
            contador += 1
            logger.info(f"\n--- Captura #{contador} ---")

            resultado = self.escanear_rutas()

            logger.info(f"Resumen: {resultado['total_buses_encontrados']} buses, "
                       f"{resultado['guardados']} guardados")

            buses_captura = resultado.get("buses", [])
            analisis = analizar_buses_directo(buses_captura, self.db)
            salida_analisis = formatear_salida(analisis)
            print(salida_analisis)

            if analisis['alertas_count'] > 0:
                logger.warning(f"ALERTA: {analisis['alertas_count']} alertas detectadas")

            if MOSTRAR_GRAFICA:
                try:
                    buses_para_grafica = []
                    for bus in buses_captura:
                        lat = bus.get("latitude") or bus.get("latitud")
                        lon = bus.get("longitude") or bus.get("longitud")
                        if lat is not None and lon is not None:
                            bus_normalizado = dict(bus)
                            bus_normalizado["latitud"] = lat
                            bus_normalizado["longitud"] = lon
                            buses_para_grafica.append(bus_normalizado)

                    densidad = analisis.get("densidad", {})
                    velocidad = analisis.get("velocidad", {})
                    fig = generar_grafica(buses_para_grafica, densidad, velocidad,
                                         titulo=f"Transmilenio - Captura #{contador}")
                    if fig:
                        import matplotlib.pyplot as plt
                        # Guardar en carpeta data/graficos/
                        graficos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "graficos")
                        os.makedirs(graficos_dir, exist_ok=True)
                        ruta_grafica = os.path.join(graficos_dir, f"captura_{contador}.png")
                        fig.savefig(ruta_grafica, dpi=100)
                        plt.close(fig)
                        logger.info(f"Grafica guardada: {ruta_grafica}")
                except Exception as e:
                    logger.warning(f"No se pudo generar grafica: {e}")

            if callback:
                callback(resultado)

            # Verificar si debemos continuar (permite Ctrl+C limpio)
            if self.running:
                logger.info(f"Próxima captura en {intervalo} segundos...")
                for _ in range(intervalo):
                    if not self.running:
                        break
                    time.sleep(1)

        logger.info("Monitoreo detenido.")

    def prueba_conexion(self) -> bool:
        """Prueba la conexión con la API."""
        logger.info("Probando conexión con la API...")

        if not self.rutas:
            logger.error("No hay rutas cargadas desde el CSV")
            return False

        ruta = self.rutas[0]
        buses = self.obtener_buses(ruta["ruta"], ruta["nombre"])

        if buses:
            logger.info(f"✓ Conexión exitosa. {len(buses)} buses encontrados en {ruta['ruta']}")
            logger.info(f"  Ejemplo: {buses[0].get('label', 'N/A')} - "
                       f"Lat: {buses[0].get('latitude', 'N/A')}, "
                       f"Lon: {buses[0].get('longitude', 'N/A')}")
            return True
        else:
            logger.warning("✗ Conexión OK pero no hay buses activos")
            return True