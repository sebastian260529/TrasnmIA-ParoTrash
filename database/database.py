"""
Módulo de base de datos SQLite para guardar ubicaciones de buses.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class BusDatabase:
    def __init__(self, db_path: str = "data/buses.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Inicializa la base de datos y crea las tablas si no existen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla principal de ubicaciones de buses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posiciones_buses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id TEXT NOT NULL,
                route_id INTEGER,
                label TEXT,
                ruta TEXT NOT NULL,
                nombre_bus TEXT,
                latitud REAL,
                longitud REAL,
                velocidad REAL,
                angulo INTEGER,
                destino_limpio TEXT,
                posicion INTEGER,
                lasttime TEXT,
                nombre_sistema TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                respuesta_json TEXT,
                UNIQUE(bus_id, timestamp)
            )
        """)

        # Tabla de rutas disponibles (para referencia)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rutas_disponibles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ruta TEXT UNIQUE,
                nombre TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Índice para búsquedas rápidas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bus_timestamp
            ON posiciones_buses(bus_id, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ruta_timestamp
            ON posiciones_buses(ruta, timestamp)
        """)

        # Tabla de última captura (se sobrescribe en cada escaneo)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captura_actual (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id TEXT UNIQUE NOT NULL,
                route_id INTEGER,
                label TEXT,
                ruta TEXT NOT NULL,
                nombre_bus TEXT,
                latitud REAL,
                longitud REAL,
                velocidad REAL,
                angulo INTEGER,
                destino_limpio TEXT,
                posicion INTEGER,
                lasttime TEXT,
                nombre_sistema TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                respuesta_json TEXT
            )
        """)

        # Tabla de captura anterior (para comparación de velocidad)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS captura_anterior (
                bus_id TEXT PRIMARY KEY,
                ruta TEXT,
                label TEXT,
                posicion INTEGER,
                latitud REAL,
                longitud REAL,
                timestamp DATETIME
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Base de datos inicializada: {self.db_path}")

    def guardar_posicion(self, datos: Dict[str, Any]) -> bool:
        """Guarda una posición de bus en la base de datos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO posiciones_buses (
                    bus_id, route_id, label, ruta, nombre_bus,
                    latitud, longitud, velocidad, angulo,
                    destino_limpio, posicion, lasttime,
                    nombre_sistema, respuesta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datos.get("id"),
                datos.get("route_id"),
                datos.get("label"),
                datos.get("ruta_extraida"),
                datos.get("destino_limpio"),
                datos.get("latitude"),
                datos.get("longitude"),
                datos.get("velocidad"),  # Puede ser None
                datos.get("angulo"),
                datos.get("destino_limpio"),
                datos.get("posicion"),
                datos.get("lasttime"),
                datos.get("nombre_sistema"),
                json.dumps(datos)  # Guardar respuesta completa para debug
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Duplicado
        except Exception as e:
            logger.error(f"Error guardando posición: {e}")
            return False
        finally:
            conn.close()

    def guardar_ruta(self, ruta: str, nombre: str):
        """Guarda una ruta en la tabla de referencia."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO rutas_disponibles (ruta, nombre, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (ruta, nombre))

        conn.commit()
        conn.close()

    def obtener_ultimas_posiciones(self, limite: int = 100) -> List[Dict]:
        """Obtiene las últimas posiciones registradas."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY bus_id ORDER BY timestamp DESC) as rn
                FROM posiciones_buses
            ) WHERE rn = 1
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limite,))

        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def obtener_trayectoria(self, bus_id: str, horas: int = 24) -> List[Dict]:
        """Obtiene la trayectoria de un bus en las últimas N horas."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM posiciones_buses
            WHERE bus_id = ?
                AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        """, (bus_id, horas))

        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def obtener_por_ruta(self, ruta: str, limite: int = 100) -> List[Dict]:
        """Obtiene las últimas posiciones de una ruta específica."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY bus_id ORDER BY timestamp DESC) as rn
                FROM posiciones_buses
                WHERE ruta = ?
            ) WHERE rn = 1
            ORDER BY timestamp DESC
            LIMIT ?
        """, (ruta, limite))

        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def resumen_por_ruta(self) -> List[Dict]:
        """Obtiene resumen de buses por ruta."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ruta,
                   COUNT(DISTINCT bus_id) as total_buses,
                   COUNT(*) as total_registros,
                   MAX(timestamp) as ultima_actualizacion
            FROM posiciones_buses
            GROUP BY ruta
            ORDER BY total_buses DESC
        """)

        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def exportar_json(self, archivo: str = "buses_export.json") -> int:
        """Exporta todos los datos a JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM posiciones_buses
            ORDER BY timestamp DESC
        """)

        datos = [dict(row) for row in cursor.fetchall()]
        conn.close()

        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        return len(datos)

    def estadisticas(self) -> Dict:
        """Obtiene estadísticas generales de la base de datos."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM posiciones_buses")
        total_registros = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT bus_id) FROM posiciones_buses")
        total_buses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT ruta) FROM posiciones_buses")
        total_rutas = cursor.fetchone()[0]

        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM posiciones_buses
        """)
        rango = cursor.fetchone()

        conn.close()

        return {
            "total_registros": total_registros,
            "total_buses": total_buses,
            "total_rutas": total_rutas,
            "inicio_datos": rango[0],
            "fin_datos": rango[1]
        }

    def limpiar_captura_actual(self):
        """Limpia la tabla de captura actual."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM captura_actual")
        conn.commit()
        conn.close()

    def guardar_captura_actual(self, buses: List[Dict[str, Any]]) -> int:
        """Guarda los buses de la captura actual (sobrescribe)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        guardados = 0
        for bus in buses:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO captura_actual (
                        bus_id, route_id, label, ruta, nombre_bus,
                        latitud, longitud, velocidad, angulo,
                        destino_limpio, posicion, lasttime,
                        nombre_sistema, timestamp, respuesta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bus.get("id") or bus.get("bus_id"),
                    bus.get("route_id"),
                    bus.get("label"),
                    bus.get("ruta_extraida") or bus.get("ruta"),
                    bus.get("destino_limpio"),
                    bus.get("latitude"),
                    bus.get("longitude"),
                    bus.get("velocidad"),
                    bus.get("angulo"),
                    bus.get("destino_limpio"),
                    bus.get("posicion"),
                    bus.get("lasttime"),
                    bus.get("nombre_sistema"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    json.dumps(bus)
                ))
                guardados += 1
            except Exception as e:
                logger.debug(f"Error guardando bus en captura actual: {e}")

        conn.commit()
        conn.close()
        return guardados

    def obtener_captura_actual(self) -> List[Dict]:
        """Obtiene los buses de la última captura."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM captura_actual ORDER BY timestamp DESC")
        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def captura_actual_estadisticas(self) -> Dict:
        """Obtiene estadísticas de la captura actual."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM captura_actual")
        total_buses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT ruta) FROM captura_actual")
        total_rutas = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(timestamp) FROM captura_actual")
        ultima_actualizacion = cursor.fetchone()[0]

        conn.close()

        return {
            "total_buses": total_buses,
            "total_rutas": total_rutas,
            "ultima_actualizacion": ultima_actualizacion
        }

    def guardar_captura_anterior(self, buses: List[Dict[str, Any]]) -> int:
        """Guarda los buses actuales como captura anterior para comparación futura."""
        if not buses:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for bus in buses:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO captura_anterior (
                        bus_id, ruta, label, posicion, latitud, longitud, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    bus.get("id") or bus.get("bus_id"),
                    bus.get("ruta_extraida") or bus.get("ruta"),
                    bus.get("label"),
                    bus.get("posicion"),
                    bus.get("latitude"),
                    bus.get("longitude"),
                    timestamp
                ))
            except Exception as e:
                logger.debug(f"Error guardando bus en captura anterior: {e}")

        conn.commit()
        conn.close()
        return len(buses)

    def obtener_captura_anterior(self) -> List[Dict]:
        """Obtiene los buses de la captura anterior."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM captura_anterior")
        resultados = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return resultados

    def comparar_velocidad(self) -> Dict[str, Any]:
        """
        Compara la captura actual con la anterior para calcular velocidad.
        Returns: análisis de buses detenidos, lentos y normales.
        """
        actual = self.obtener_captura_actual()
        anterior = self.obtener_captura_anterior()

        if not anterior:
            return {
                "detenidos": [],
                "lentos": [],
                "normales": [],
                "total_detenidos": 0,
                "total_lentos": 0,
                "total_normales": len(actual)
            }

        anterior_dict = {b["bus_id"]: b for b in anterior}
        timestamp_anterior = anterior[0].get("timestamp") if anterior else None

        try:
            if timestamp_anterior:
                tiempo_diff = (datetime.now() - datetime.strptime(timestamp_anterior, "%Y-%m-%d %H:%M:%S")).total_seconds()
            else:
                tiempo_diff = 60
        except:
            tiempo_diff = 60

        if tiempo_diff < 1:
            tiempo_diff = 60

        velocidades = {
            "detenidos": [],
            "lentos": [],
            "normales": []
        }

        for bus in actual:
            bus_id = bus.get("bus_id")
            posicion_actual = bus.get("posicion", 0)

            if bus_id in anterior_dict:
                posicion_anterior = anterior_dict[bus_id].get("posicion", 0)
                cambio_pos = abs(posicion_actual - posicion_anterior)

                velocidad_ms = cambio_pos / tiempo_diff
                velocidad_kmh = velocidad_ms * 3.6

                bus_info = {
                    "bus_id": bus_id,
                    "label": bus.get("label"),
                    "ruta": bus.get("ruta"),
                    "cambio_posicion": cambio_pos,
                    "velocidad_kmh": round(velocidad_kmh, 1)
                }

                if velocidad_kmh < 5:
                    velocidades["detenidos"].append(bus_info)
                elif velocidad_kmh < 15:
                    velocidades["lentos"].append(bus_info)
                else:
                    velocidades["normales"].append(bus_info)
            else:
                velocidades["normales"].append({
                    "bus_id": bus_id,
                    "label": bus.get("label"),
                    "ruta": bus.get("ruta"),
                    "cambio_posicion": 0,
                    "velocidad_kmh": 0,
                    "nuevo": True
                })

        return {
            "detenidos": velocidades["detenidos"],
            "lentos": velocidades["lentos"],
            "normales": velocidades["normales"],
            "total_detenidos": len(velocidades["detenidos"]),
            "total_lentos": len(velocidades["lentos"]),
            "total_normales": len(velocidades["normales"])
        }