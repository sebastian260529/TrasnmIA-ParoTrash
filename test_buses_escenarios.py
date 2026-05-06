"""
Test de escenarios para el sistema de score de buses.
Ejecutar: python test_buses_escenarios.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock, patch

# Importar la funcion a testear
from ia.risk_integrator import _score_buses


# === COORDENADAS DE PRUEBA ===
# Portal Eldorado: lat 4.69, lon -74.10, radio 800m
ZONA_TEST = "Portal Eldorado"


# === FUNCIONES AUXILIARES ===

def crear_mock_db(buses):
    """Crea un mock de BusDatabase con buses simulados."""
    mock_db = Mock()
    mock_db.obtener_captura_actual.return_value = buses
    return mock_db


def ejecutar_escenario(nombre, buses, anomalias_esperado, score_esperado, descripcion):
    """Ejecuta un escenario y devuelve el resultado."""
    print(f"\n--- {nombre} ---")
    print(f"  Descripcion: {descripcion}")
    print(f"  Buses simulados: {len(buses)}")
    print(f"  Anomalias simuladas: {len(anomalias_esperado)}")

    # Crear mocks
    mock_db = crear_mock_db(buses)

    # Patchear detectar_anomalias para devolver las anomalias que queremos
    with patch('ia.risk_integrator.detectar_anomalias') as mock_detectar:
        mock_detectar.return_value = {
            "anomalias": anomalias_esperado,
            "total_anomalias": len(anomalias_esperado)
        }

        # Ejecutar la funcion
        resultado = _score_buses(mock_db, ZONA_TEST)

    # Mostrar resultado
    print(f"  Score obtenido: {resultado['score']}")
    print(f"  Score esperado: {score_esperado}")
    print(f"  Tipo dato: {resultado['tipo_dato']}")

    # Verificar (con tolerancia para floats)
    diff = abs(resultado['score'] - score_esperado)
    ok = diff < 0.1  # Tolerancia de 0.1 para comparison de floats
    print(f"  RESULTADO: {'OK' if ok else 'FALLO'} (diff: {diff:.2f})")

    return {
        "nombre": nombre,
        "score_obtenido": resultado['score'],
        "score_esperado": score_esperado,
        "tipo_dato": resultado['tipo_dato'],
        "ok": ok,
        "detalle": resultado.get('detalle', '')
    }


# === DEFINICION DE ESCENARIOS ===

ESCENARIOS = [
    {
        "nombre": "ESCENARIO 1: Sin buses cercanos",
        "descripcion": "No hay buses en la zona - base de datos vacia",
        "buses": [],
        "anomalias": [],
        "score_esperado": 0
    },
    {
        "nombre": "ESCENARIO 2: Pocos buses (3)",
        "descripcion": "Solo 3 buses cerca de la zona (radio 800m)",
        "buses": [
            {"bus_id": "B001", "latitud": 4.695, "longitud": -74.095, "ruta": "1", "label": "E0001"},
            {"bus_id": "B002", "latitud": 4.692, "longitud": -74.098, "ruta": "1", "label": "E0002"},
            {"bus_id": "B003", "latitud": 4.688, "longitud": -74.102, "ruta": "2", "label": "D0003"},
        ],
        "anomalias": [],
        "score_esperado": 25
    },
    {
        "nombre": "ESCENARIO 3: Buses moderados (5)",
        "descripcion": "5 buses cerca de la zona - cantidad moderada",
        "buses": [
            {"bus_id": "B001", "latitud": 4.695, "longitud": -74.095, "ruta": "1", "label": "E0001"},
            {"bus_id": "B002", "latitud": 4.692, "longitud": -74.098, "ruta": "1", "label": "E0002"},
            {"bus_id": "B003", "latitud": 4.688, "longitud": -74.102, "ruta": "2", "label": "D0003"},
            {"bus_id": "B004", "latitud": 4.685, "longitud": -74.105, "ruta": "3", "label": "C0004"},
            {"bus_id": "B005", "latitud": 4.700, "longitud": -74.090, "ruta": "5", "label": "A0005"},
        ],
        "anomalias": [],
        "score_esperado": 55
    },
    {
        "nombre": "ESCENARIO 4: Muchos buses (10)",
        "descripcion": "10 buses cerca - alta concentracion (8+ para score 80)",
        "buses": [
            {"bus_id": f"B{i:03d}", "latitud": 4.689 + (i*0.001), "longitud": -74.099 + (i*0.001),
             "ruta": str(i%10 + 1), "label": f"E{i:04d}"}
            for i in range(10)
        ],
        "anomalias": [],
        "score_esperado": 55  # 10 buses pero solo 6 dentro de 800m (rango 4-7 = 55)
    },
    {
        "nombre": "ESCENARIO 5: Con anomalía detectada (1)",
        "descripcion": "3 buses + 1 anomalia con 85% de confianza",
        "buses": [
            {"bus_id": "B001", "latitud": 4.695, "longitud": -74.095, "ruta": "1", "label": "E0001"},
            {"bus_id": "B002", "latitud": 4.692, "longitud": -74.098, "ruta": "1", "label": "E0002"},
            {"bus_id": "B003", "latitud": 4.688, "longitud": -74.102, "ruta": "2", "label": "D0003"},
        ],
        "anomalias": [
            {
                "tipo": "tren_lento",
                "coordenadas": {"latitud": 4.690, "longitud": -74.100},
                "porcentaje_confianza": 85,
                "buses_involucrados": 2
            }
        ],
        "score_esperado": 85
    },
    {
        "nombre": "ESCENARIO 6: Con anomalía detectada (2)",
        "descripcion": "5 buses + 2 anomalias - riesgo moderado-alto",
        "buses": [
            {"bus_id": "B001", "latitud": 4.695, "longitud": -74.095, "ruta": "1", "label": "E0001"},
            {"bus_id": "B002", "latitud": 4.692, "longitud": -74.098, "ruta": "1", "label": "E0002"},
            {"bus_id": "B003", "latitud": 4.688, "longitud": -74.102, "ruta": "2", "label": "D0003"},
            {"bus_id": "B004", "latitud": 4.685, "longitud": -74.105, "ruta": "3", "label": "C0004"},
            {"bus_id": "B005", "latitud": 4.700, "longitud": -74.090, "ruta": "5", "label": "A0005"},
        ],
        "anomalias": [
            {
                "tipo": "tren_lento",
                "coordenadas": {"latitud": 4.690, "longitud": -74.100},
                "porcentaje_confianza": 75,
                "buses_involucrados": 3
            },
            {
                "tipo": "portal_cerrado",
                "coordenadas": {"latitud": 4.691, "longitud": -74.099},
                "porcentaje_confianza": 80,
                "buses_involucrados": 5
            }
        ],
        "score_esperado": 77.5  # Promedio: (75+80)/2 = 77.5 → min(95, 77.5) = 77.5
    },
    {
        "nombre": "ESCENARIO 7: Paro confirmado (muchas anomalías + buses)",
        "descripcion": "15 buses + 3 anomalias de manifestacion - riesgo muy alto",
        "buses": [
            {"bus_id": f"B{i:03d}", "latitud": 4.689 + (i*0.001), "longitud": -74.099 + (i*0.001),
             "ruta": str(i%10 + 1), "label": f"E{i:04d}"}
            for i in range(15)
        ],
        "anomalias": [
            {
                "tipo": "manifestacion",
                "coordenadas": {"latitud": 4.690, "longitud": -74.100},
                "porcentaje_confianza": 90,
                "buses_involucrados": 8
            },
            {
                "tipo": "tren_lento",
                "coordenadas": {"latitud": 4.688, "longitud": -74.098},
                "porcentaje_confianza": 80,
                "buses_involucrados": 10
            },
            {
                "tipo": "portal_cerrado",
                "coordenadas": {"latitud": 4.692, "longitud": -74.102},
                "porcentaje_confianza": 95,
                "buses_involucrados": 12
            }
        ],
        "score_esperado": 88.33  # Promedio: (90+80+95)/3 = 88.33 → min(95, 88.33) = 88.33
    },
    {
        "nombre": "ESCENARIO 8: Zona no reconocida",
        "descripcion": "Zona que no existe en el catalogo de zonas - buses lejanos",
        "buses": [
            {"bus_id": "B001", "latitud": 4.600, "longitud": -74.000, "ruta": "1", "label": "E0001"},  # Lejos
        ],
        "anomalias": [],
        "score_esperado": 0,
        "zona": "Zona Inventada XYZ"
    },
    {
        "nombre": "ESCENARIO 9: Anomalías lejos de la zona",
        "descripcion": "Anomalias existen pero a mas de 800m de distancia",
        "buses": [],
        "anomalias": [
            {
                "tipo": "manifestacion",
                "coordenadas": {"latitud": 4.600, "longitud": -74.000},  # Lejos de Portal Eldorado
                "porcentaje_confianza": 90,
                "buses_involucrados": 5
            }
        ],
        "score_esperado": 0
    },
]


# === EJECUTOR PRINCIPAL ===

def ejecutar_tests():
    print("=" * 70)
    print("TEST DE ESCENARIOS - SISTEMA DE SCORE DE BUSES")
    print("=" * 70)
    print(f"Zona de prueba: {ZONA_TEST}")
    print("Coordenadas: lat 4.69, lon -74.10, radio 800m")
    print("=" * 70)

    resultados = []

    for escenario in ESCENARIOS:
        zona = escenario.get("zona", ZONA_TEST)

        resultado = ejecutar_escenario(
            nombre=escenario["nombre"],
            buses=escenario["buses"],
            anomalias_esperado=escenario["anomalias"],
            score_esperado=escenario["score_esperado"],
            descripcion=escenario["descripcion"]
        )

        resultados.append(resultado)

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE RESULTADOS")
    print("=" * 70)

    ok_count = sum(1 for r in resultados if r["ok"])
    total = len(resultados)

    print(f"Total escenarios: {total}")
    print(f"OK: {ok_count}")
    print(f"FALLOS: {total - ok_count}")
    print("-" * 70)

    for r in resultados:
        status = "OK" if r["ok"] else "FALLO"
        print(f"{r['nombre']}: {status} (obtenido: {r['score_obtenido']}, esperado: {r['score_esperado']})")

    print("=" * 70)

    if ok_count == total:
        print("TODOS LOS TESTS PASARON OK!")
    else:
        print(f"ALGUNOS TESTS FALLARON - Revisar resultados acima")

    return resultados


if __name__ == "__main__":
    ejecutar_tests()