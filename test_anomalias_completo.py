"""
Test completo del sistema de detección de anomalías.
Inserta datos de prueba en la DB y verifica la detección.

Ejecutar: python test_anomalias_completo.py
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(__file__))

from database.database import BusDatabase
from analisis.anomaly_detector import (
    detectar_anomalias,
    analizar_buses_activos,
    detectar_manifestaciones,
    detectar_trancones,
    detectar_buses_varados
)


# === CONFIGURACIÓN DE PRUEBA ===
ZONA_TEST = "Portal Eldorado"
# Coordenadas aproximadas de Portal Eldorado
LAT_TEST = 4.69
LON_TEST = -74.10
RADIO_ZONA = 0.01  # ~1km


# === FUNCIONES AUXILIARES ===

def limpiar_datos_prueba(db_path):
    """Limpia TODOS los datos de la tabla para test aislado."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Eliminar TODOS los buses de ambas tablas
    cursor.execute("DELETE FROM posiciones_buses")
    cursor.execute("DELETE FROM captura_actual")
    
    conn.commit()
    conn.close()
    print("[+] TODOS los datos eliminados (test aislado)")


def insertar_buses_prueba(db_path, buses_data):
    """Inserta buses de prueba con posiciones."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    ahora = datetime.now()
    
    for bus in buses_data:
        bus_id = bus["bus_id"]
        lat = bus["latitud"]
        lon = bus["longitud"]
        posicion = bus["posicion"]
        ruta = bus["ruta"]
        angulo = bus.get("angulo", 0)  # Ángulo para dirección
        
        timestamp_actual = ahora.strftime("%Y-%m-%d %H:%M:%S")
        
        # Insertar en tabla de posiciones (historial)
        cursor.execute("""
            INSERT OR REPLACE INTO posiciones_buses
            (bus_id, route_id, latitud, longitud, label, posicion, lasttime, timestamp, ruta, angulo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bus_id,
            10056,
            lat,
            lon,
            f"TEST_{bus_id}",
            posicion,
            ahora.strftime("%H:%M:%S"),
            timestamp_actual,
            ruta,
            angulo
        ))
        
        # Insertar en tabla captura_actual (para que el sistema lo detecte)
        cursor.execute("""
            INSERT OR REPLACE INTO captura_actual
            (bus_id, route_id, latitud, longitud, label, posicion, lasttime, timestamp, ruta, angulo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bus_id,
            10056,
            lat,
            lon,
            f"TEST_{bus_id}",
            posicion,
            ahora.strftime("%H:%M:%S"),
            timestamp_actual,
            ruta,
            angulo
        ))
        
        # Insertar historial para calcular velocidad
        angulo = bus.get("angulo", 0)
        for i in range(5):
            tiempo_atras = ahora - timedelta(minutes=i*5)
            
            if bus.get("movimiento") == "detenido":
                # Misma posición = velocidad 0 = detenido
                pos_hist = posicion
            elif bus.get("movimiento") == "lento":
                # Cambio pequeño = velocidad baja = lento
                pos_hist = posicion - (i * 2)
            else:
                # Cambio grande = velocidad alta = normal (más de 500 puntos)
                pos_hist = posicion - (i * 500)
            
            ts_hist = tiempo_atras.strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("""
                INSERT OR IGNORE INTO posiciones_buses
                (bus_id, route_id, latitud, longitud, label, posicion, lasttime, timestamp, ruta, angulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bus_id,
                10056,
                lat,
                lon,
                f"TEST_{bus_id}",
                pos_hist,
                tiempo_atras.strftime("%H:%M:%S"),
                ts_hist,
                ruta,
                angulo
            ))
    
    conn.commit()
    conn.close()
    print(f"[+] Insertados {len(buses_data)} buses de prueba")


def ejecutar_escenario(nombre, buses_data, esperado):
    """Ejecuta un escenario de prueba."""
    print(f"\n{'='*60}")
    print(f"ESCENARIO: {nombre}")
    print(f"{'='*60}")
    print(f"  Buses: {len(buses_data)}")
    print(f"  Esperado: {esperado}")
    
    # Conectar a DB real
    db = BusDatabase()
    db_path = db.db_path
    
    # Limpiar e insertar
    limpiar_datos_prueba(db_path)
    insertar_buses_prueba(db_path, buses_data)
    
    # Forzar detección sin cache
    resultado = detectar_anomalias(db, force_refresh=True)
    
    # Mostrar resultados
    resumen = resultado.get("resumen", {})
    anomalias = resultado.get("anomalias", [])
    
    print(f"\n  --- RESULTADOS ---")
    print(f"  Buses activos: {resumen.get('buses_activos', 0)}")
    print(f"  Buses sin movimiento: {resumen.get('buses_sin_movimiento', 0)}")
    print(f"  Buses lentos: {resumen.get('buses_lentos', 0)}")
    print(f"  Buses normales: {resumen.get('buses_normales', 0)}")
    print(f"  Velocidad promedio: {resumen.get('velocidad_promedio_kmh', 0):.1f} km/h")
    print(f"\n  Anomalías detectadas: {len(anomalias)}")
    
    for a in anomalias:
        print(f"    - {a['tipo']}: {a['porcentaje_confianza']}% ({a['buses_involucrados']} buses)")
    
    # Verificar
    tipos_encontrados = [a['tipo'] for a in anomalias]
    ok = any(t in tipos_encontrados for t in esperado['tipos'])
    
    print(f"\n  RESULTADO: {'OK' if ok else 'FALLO'}")
    print(f"  Esperado: {esperado['tipos']}")
    print(f"  Encontrado: {tipos_encontrados}")
    
    return {
        "nombre": nombre,
        "esperado": esperado['tipos'],
        "encontrado": tipos_encontrados,
        "ok": ok,
        "resumen": resumen,
        "anomalias": anomalias
    }


# === ESCENARIOS DE PRUEBA ===

def crear_buses_normales(cantidad):
    """Crea buses con movimiento normal (ángulos hacia arriba = 0-90, 270-360)."""
    buses = []
    for i in range(cantidad):
        buses.append({
            "bus_id": f"TEST_N{i:03d}",
            "latitud": LAT_TEST + random.uniform(-0.005, 0.005),
            "longitud": LON_TEST + random.uniform(-0.005, 0.005),
            "posicion": 1000 + i * 100,
            "ruta": "1",
            "movimiento": "normal",
            "angulo": random.randint(0, 45)  # Dirección ARRIBA
        })
    return buses


def crear_buses_lentos(cantidad):
    """Crea buses lentos (ángulos hacia abajo = 135-225)."""
    buses = []
    for i in range(cantidad):
        buses.append({
            "bus_id": f"TEST_L{i:03d}",
            "latitud": LAT_TEST + random.uniform(-0.003, 0.003),
            "longitud": LON_TEST + random.uniform(-0.003, 0.003),
            "posicion": 1000 + i * 50,
            "ruta": "2",
            "movimiento": "lento",
            "angulo": random.randint(135, 225)  # Dirección ABAJO
        })
    return buses


def crear_buses_detenidos(cantidad):
    """Crea buses sin movimiento (detenidos) - mismos ángulos."""
    buses = []
    for i in range(cantidad):
        buses.append({
            "bus_id": f"TEST_D{i:03d}",
            "latitud": LAT_TEST + random.uniform(-0.002, 0.002),
            "longitud": LON_TEST + random.uniform(-0.002, 0.002),
            "posicion": 1000 + i,
            "ruta": "3",
            "movimiento": "detenido",
            "angulo": random.randint(0, 45)  # Todos misma dirección
        })
    return buses


# === DEFINICIÓN DE ESCENARIOS ===

ESCENARIOS = [
    {
        "nombre": "ESCENARIO 1: Sin anomalías (solo buses normales)",
        "descripcion": "20 buses con movimiento normal - no debe detectar anomalías",
        "buses": lambda: crear_buses_normales(20),
        "esperado": {
            "tipos": [],  # No se esperan anomalías
            "min_lentos": 0,
            "min_detenidos": 0
        }
    },
    {
        "nombre": "ESCENARIO 2: Trancón (buses lentos)",
        "descripcion": "15 buses lentos - debe detectar TRANCON",
        "buses": lambda: crear_buses_lentos(15),
        "esperado": {
            "tipos": ["TRANCON"],
            "min_lentos": 10
        }
    },
    {
        "nombre": "ESCENARIO 3: MANIFESTACIÓN (buses detenidos)",
        "descripcion": "22 buses detenidos - debe detectar MANIFESTACION",
        "buses": lambda: crear_buses_detenidos(22),
        "esperado": {
            "tipos": ["MANIFESTACION"],
            "min_detenidos": 20
        }
    },
    {
        "nombre": "ESCENARIO 4: MANIFESTACIÓN + TRANCON mixtos",
        "descripcion": "25 detenidos + 12 lentos - debe detectar ambos",
        "buses": lambda: crear_buses_detenidos(25) + crear_buses_lentos(12),
        "esperado": {
            "tipos": ["MANIFESTACION", "TRANCON"],
            "min_detenidos": 20,
            "min_lentos": 10
        }
    },
    {
        "nombre": "ESCENARIO 5: Muchos buses normales + algunos lentos",
        "descripcion": "30 normales + 8 lentos - trancón borderline",
        "buses": lambda: crear_buses_normales(30) + crear_buses_lentos(8),
        "esperado": {
            "tipos": [],  # Puede no detectar (8 < 10 umbral)
            "min_lentos": 5
        }
    },
    {
        "nombre": "ESCENARIO 6: Paro parcial",
        "descripcion": "10 detenidos + 5 lentos + 15 normales - detectados parcial",
        "buses": lambda: crear_buses_detenidos(10) + crear_buses_lentos(5) + crear_buses_normales(15),
        "esperado": {
            "tipos": [],  # No llega a umbrales (10 < 20 manifest, 5 < 10 tracon)
            "min_detenidos": 8,
            "min_lentos": 3
        }
    },
    {
        "nombre": "ESCENARIO 7: Buses varados",
        "descripcion": "3 buses detenidos muy cerca - posible bus varado",
        "buses": lambda: crear_buses_detenidos(3),
        "esperado": {
            "tipos": [],  # Varados se detectan diferente
            "min_detenidos": 3
        }
    },
    {
        "nombre": "ESCENARIO 8: Paro masivo",
        "descripcion": "30 detenidos + 20 lentos - MANIFESTACION + TRANCON",
        "buses": lambda: crear_buses_detenidos(30) + crear_buses_lentos(20),
        "esperado": {
            "tipos": ["MANIFESTACION", "TRANCON"],
            "min_detenidos": 20,
            "min_lentos": 10
        }
    },
]


# === EJECUTOR PRINCIPAL ===

def ejecutar_tests():
    print("=" * 70)
    print("TEST COMPLETO - DETECCIÓN DE ANOMALÍAS")
    print("=" * 70)
    print(f"Zona: {ZONA_TEST}")
    print(f"Coordenadas: lat {LAT_TEST}, lon {LON_TEST}")
    print("=" * 70)
    
    resultados = []
    
    for escenario in ESCENARIOS:
        buses = escenario["buses"]()
        
        resultado = ejecutar_escenario(
            nombre=escenario["nombre"],
            buses_data=buses,
            esperado=escenario["esperado"]
        )
        
        resultados.append(resultado)
        
        # Limpiar para el siguiente
        db = BusDatabase()
        limpiar_datos_prueba(db.db_path)
    
    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    
    ok_count = sum(1 for r in resultados if r["ok"])
    total = len(resultados)
    
    print(f"Total escenarios: {total}")
    print(f"OK: {ok_count}")
    print(f"FALLOS: {total - ok_count}")
    print("-" * 70)
    
    for r in resultados:
        status = "OK" if r["ok"] else "FALLO"
        print(f"{r['nombre'][:50]:50s} | {status}")
        if not r["ok"]:
            print(f"  Esperado: {r['esperado']}")
            print(f"  Encontrado: {r['encontrado']}")
    
    print("=" * 70)
    
    if ok_count == total:
        print("TODOS LOS TESTS PASARON OK!")
    else:
        print(f"ALGUNOS TESTS FALLARON")
    
    return resultados


if __name__ == "__main__":
    resultados = ejecutar_tests()