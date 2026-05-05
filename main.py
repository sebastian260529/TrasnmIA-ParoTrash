"""
Interfaz CLI para el sistema de monitoreo de buses Transmilenio.
Ejecutar: python main.py [comando]
"""

import sys
import argparse
import json
from datetime import datetime

from bus_tracker import BusTracker
from database import BusDatabase
from config import RUTAS_CSV, MONITOR_INTERVAL, DATABASE_PATH
from analisis import generar_resumen, formatear_salida, obtener_configuracion, mostrar_grafica, guardar_grafica


def cmd_prueba(tracker: BusTracker, args):
    """Prueba la conexión con la API."""
    tracker.prueba_conexion()


def cmd_rutas(tracker: BusTracker, args):
    """Muestra las rutas cargadas desde el CSV."""
    print(f"\nRutas cargadas desde {RUTAS_CSV}:")
    print("-" * 60)
    print(f"{'Ruta':<10} | {'Destino':<40}")
    print("-" * 60)
    for r in tracker.rutas:
        print(f"{r['ruta']:<10} | {r['nombre'][:40]}")
    print("-" * 60)
    print(f"Total: {len(tracker.rutas)} rutas")


def cmd_analizar(db: BusDatabase, tracker: BusTracker, args):
    """Ejecuta análisis de trancones."""
    try:
        if args.config:
            config = obtener_configuracion()
            print("\nConfiguracion de Analisis:")
            print("-" * 40)
            for key, value in config.items():
                print(f"  {key}: {value}")
            return

        if args.ruta:
            buses = db.obtener_ultimas_posiciones(1000)
            buses_filtrados = [b for b in buses if b.get("ruta") == args.ruta]
            from analisis import analisis_por_ruta
            resultado = analisis_por_ruta(buses_filtrados, db, args.ruta)
            print(f"\nAnalisis de ruta {args.ruta}:")
            print(f"  Total buses: {resultado['total_buses']}")
            print(f"  Zonas congestionadas: {len(resultado['densidad']['zonas'])}")
            print(f"  Buses cercanos: {resultado['proximidad']['total']}")
        else:
            analisis = generar_resumen(db)
            print(formatear_salida(analisis))

        if args.grafica:
            buses = db.obtener_ultimas_posiciones(500)
            densidad = analisis.get("densidad", {}) if args.ruta is None else None
            velocidad = analisis.get("velocidad", {}) if args.ruta is None else None
            mostrar_grafica(buses, densidad, velocidad)

    except Exception as e:
        print(f"\nError en analisis: {e}")
        import traceback
        traceback.print_exc()

    if args.csv:
        archivo = args.csv if args.csv != True else "analisis_trasmilenio.csv"
        buses = db.obtener_ultimas_posiciones(1000)
        densidad = analisis.get("densidad", {}) if args.ruta is None else None
        try:
            import csv
            with open(archivo, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["bus_id", "label", "ruta", "latitud", "longitud", "destino"])
                for b in buses:
                    writer.writerow([
                        b.get("bus_id", ""),
                        b.get("label", ""),
                        b.get("ruta", ""),
                        b.get("latitud", ""),
                        b.get("longitud", ""),
                        b.get("destino_limpio", "")
                    ])
            print(f"\nDatos exportados a {archivo}")
        except Exception as e:
            print(f"Error exportando: {e}")


def cmd_consultar(db: BusDatabase, args):
    """Muestra las últimas ubicaciones."""
    if args.bus_id:
        trayectoria = db.obtener_trayectoria(args.bus_id, args.horas)
        print(f"\n📍 Trayectoria de bus {args.bus_id} (últimas {args.horas}h):")
        print(f"   {len(trayectoria)} registros encontrados\n")

        if args.json:
            print(json.dumps(trayectoria, indent=2, ensure_ascii=False))
        else:
            for pos in trayectoria[:20]:  # Mostrar máximo 20
                print(f"   {pos['timestamp']} | Lat: {pos['latitud']:.6f} | Lon: {pos['longitud']:.6f} | "
                      f"Label: {pos.get('label', 'N/A')}")
                if len(trayectoria) > 20:
                    print(f"   ... y {len(trayectoria) - 20} más (usar --json para ver todos)")
    else:
        posiciones = db.obtener_ultimas_posiciones(args.limite)
        print(f"\n📍 Últimas {len(posiciones)} posiciones de buses:")
        print("-" * 80)

        for pos in posiciones:
            print(f"{pos['timestamp']} | {pos['bus_id']} | {pos['ruta']} | "
                  f"Label: {pos.get('label', 'N/A')} | "
                  f"Lat: {pos['latitud']:.5f}, Lon: {pos['longitud']:.5f}")

        if args.json:
            print("\n--- JSON ---")
            print(json.dumps(posiciones, indent=2, ensure_ascii=False))


def cmd_por_ruta(db: BusDatabase, args):
    """Muestra buses por ruta específica."""
    posiciones = db.obtener_por_ruta(args.ruta, args.limite)
    print(f"\n🚌 Buses en ruta {args.ruta}: {len(posiciones)}")
    print("-" * 70)

    for pos in posiciones:
        print(f"{pos['timestamp']} | Bus: {pos['bus_id']} | Label: {pos.get('label', 'N/A')} | "
              f"Lat: {pos['latitud']:.5f}, Lon: {pos['longitud']:.5f} | "
              f"Destino: {pos.get('destino_limpio', 'N/A')}")

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(posiciones, indent=2, ensure_ascii=False))


def cmd_resumen(db: BusDatabase, args):
    """Muestra resumen por ruta."""
    resumen = db.resumen_por_ruta()
    print("\n📊 Resumen por ruta:")
    print("-" * 60)

    for r in resumen:
        print(f"  {r['ruta']:10} | {r['total_buses']:3} buses | "
              f"{r['total_registros']:5} registros | "
              f"Última: {r['ultima_actualizacion']}")


def cmd_exportar(db: BusDatabase, args):
    """Exporta datos a JSON."""
    archivo = args.archivo or f"buses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    total = db.exportar_json(archivo)
    print(f"✓ Exportados {total} registros a {archivo}")


def cmd_estadisticas(db: BusDatabase, args):
    """Muestra estadísticas de la base de datos."""
    stats = db.estadisticas()
    print("\n📈 Estadísticas de la base de datos:")
    print(f"   Total de registros: {stats['total_registros']}")
    print(f"   Buses únicos: {stats['total_buses']}")
    print(f"   Rutas monitoreadas: {stats['total_rutas']}")
    print(f"   Rango de datos: {stats['inicio_datos']} a {stats['fin_datos']}")


def cmd_monitorear(tracker: BusTracker, args):
    """Inicia el monitoreo continuo."""
    print("=" * 50)
    print("  SISTEMA DE MONITOREO DE BUSES TRANSMILENIO")
    print("=" * 50)
    print(f"\n📡 Conectando a la API...")

    if not tracker.prueba_conexion():
        print("\n❌ No se puede conectar a la API. Verificar credenciales en config.py")
        return

    print(f"\n🚀 Iniciando monitoreo...")
    print(f"   Intervalo: {args.intervalo} segundos")
    print(f"   Rutas: {len(tracker.rutas)}")
    print("\nPresionar Ctrl+C para detener\n")

    tracker.iniciar_monitoreo(intervalo=args.intervalo)


def main():
    parser = argparse.ArgumentParser(
        description="Sistema de monitoreo de buses Transmilenio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py prueba                    Probar conexión
  python main.py monitorear                Iniciar monitoreo continuo
  python main.py consultar                  Ver últimas posiciones
  python main.py consultar --bus-id 24224 --horas 2  Ver trayectoria
  python main.py ruta --ruta 6-9           Ver buses de ruta específica
  python main.py resumen                    Resumen por ruta
  python main.py exportar                   Exportar a JSON
  python main.py stats                      Ver estadísticas
        """
    )

    subparsers = parser.add_subparsers(dest="comando", help="Comandos disponibles")

    # Comando prueba
    subparsers.add_parser("prueba", help="Probar conexión a la API")

    # Comando rutas
    subparsers.add_parser("rutas", help="Ver rutas cargadas desde CSV")

    # Comando analizar
    ap = subparsers.add_parser("analizar", help="Análisis de trancones")
    ap.add_argument("--ruta", type=str, help="Filtrar por ruta específica")
    ap.add_argument("--grafica", action="store_true", help="Mostrar gráfica de clusters")
    ap.add_argument("--csv", nargs="?", const=True, default=False, help="Exportar a CSV")
    ap.add_argument("--config", action="store_true", help="Ver configuración de análisis")

    # Comando monitorear
    mp = subparsers.add_parser("monitorear", help="Iniciar monitoreo continuo")
    mp.add_argument("--intervalo", type=int, default=MONITOR_INTERVAL,
                    help=f"Intervalo de captura en segundos (default: {MONITOR_INTERVAL})")

    # Comando consultar
    cp = subparsers.add_parser("consultar", help="Ver últimas ubicaciones")
    cp.add_argument("--bus-id", type=str, help="ID específico del bus")
    cp.add_argument("--horas", type=int, default=24, help="Horas de historia (default: 24)")
    cp.add_argument("--limite", type=int, default=50, help="Límite de resultados (default: 50)")
    cp.add_argument("--json", action="store_true", help="Salida en JSON")

    # Comando ruta
    rp = subparsers.add_parser("ruta", help="Ver buses de una ruta específica")
    rp.add_argument("--ruta", type=str, required=True, help="Código de ruta (ej: 6-9)")
    rp.add_argument("--limite", type=int, default=50, help="Límite de resultados")
    rp.add_argument("--json", action="store_true", help="Salida en JSON")

    # Comando resumen
    subparsers.add_parser("resumen", help="Resumen por ruta")

    # Comando exportar
    ep = subparsers.add_parser("exportar", help="Exportar datos a JSON")
    ep.add_argument("--archivo", type=str, help="Nombre del archivo de salida")

    # Comando stats
    subparsers.add_parser("stats", help="Ver estadísticas de la base de datos")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        return

    # Inicializar tracker y base de datos
    tracker = BusTracker()
    db = BusDatabase()

    # Ejecutar comando
    if args.comando == "prueba":
        cmd_prueba(tracker, args)
    elif args.comando == "rutas":
        cmd_rutas(tracker, args)
    elif args.comando == "analizar":
        cmd_analizar(db, tracker, args)
    elif args.comando == "monitorear":
        cmd_monitorear(tracker, args)
    elif args.comando == "consultar":
        cmd_consultar(db, args)
    elif args.comando == "ruta":
        cmd_por_ruta(db, args)
    elif args.comando == "resumen":
        cmd_resumen(db, args)
    elif args.comando == "exportar":
        cmd_exportar(db, args)
    elif args.comando == "stats":
        cmd_estadisticas(db, args)


if __name__ == "__main__":
    main()