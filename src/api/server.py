"""
Servidor unificado FastAPI.
Combina detección automática + reportes de usuarios.

Ejecutar: python -m src.api.server
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

app = FastAPI(
    title="API de Anomalías Transmilenio",
    description="Sistema integrado de detección + reportes de usuarios",
    version="2.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Imports
from src.config import MONITOR_INTERVAL
from src.database import BusDatabase
from src.analisis.anomaly_detector import detectar_anomalias
from src.analisis.ponderador import (
    detectar_anomalias_ponderadas,
    get_resumen_ponderado,
    get_pesos,
    set_pesos,
    formatear_salida,
    get_reportes_activos
)
from src.firebase.client import (
    create_reporte,
    votacion,
    get_all_reportes,
    get_reporte_by_id
)
from src.analisis.graficos import generar_mapa_buses, generar_mapa_anomalias, generar_todas_graficas
from src.api.bus_tracker import BusTracker
from threading import Thread
import time

db = BusDatabase()
tracker = None
monitoreo_activo = False
monitoreo_thread = None

# Models
class ReporteCreate(BaseModel):
    reporte_id: str
    id_usuario: str
    ubicacion: List[float]
    tipo: str = "trancón"
    descripcion: str = ""

class ReporteVoto(BaseModel):
    reporte_id: str
    tipo_voto: str  # "positivo" or "negativo"

class PesosUpdate(BaseModel):
    peso_deteccion: float
    peso_reporte: float

# Endpoints - Health
@app.get("/health")
def health():
    return {
        "status": "ok",
        "servicio": "API Anomalías Transmilenio v2.0",
        "componentes": ["detección", "reportes", "ponderado"]
    }

# Endpoints - Detección automática
@app.get("/anomalias/deteccion")
def anomalias_deteccion():
    """Solo detección automática."""
    try:
        return detectar_anomalias(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints - Reportes usuarios
@app.get("/anomalias/reportes")
def anomalias_reportes():
    """Solo reportes de usuarios."""
    try:
        return {
            "timestamp": datetime.now().isoformat(),
            "reportes": get_reportes_activos(),
            "total": len(get_reportes_activos())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints - Ponderado (combinación)
@app.get("/anomalias/ponderado")
def anomalias_ponderado():
    """Combinación ponderada de detección + reportes."""
    try:
        return detectar_anomalias_ponderadas(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resumen")
def resumen():
    """Resumen rápido."""
    try:
        return get_resumen_ponderado()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints - Crear reporte
@app.post("/reportes/crear")
def crear_reporte_endpoint(reporte: ReporteCreate):
    """Crear nuevo reporte de usuario."""
    try:
        resultado = create_reporte(
            reporte_id=reporte.reporte_id,
            id_usuario=reporte.id_usuario,
            ubicacion=reporte.ubicacion,
            tipo=reporte.tipo,
            descripcion=reporte.descripcion
        )
        return {"status": "ok", "reporte": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints - Votar reporte
@app.post("/reportes/votar")
def votacion_endpoint(voto: ReporteVoto):
    """Votar un reporte."""
    try:
        return votacion(voto.reporte_id, voto.tipo_voto)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints - Ver/editar pesos
@app.get("/config/ponderado")
def ver_pesos():
    """Ver pesos actuales."""
    return get_pesos()

@app.put("/config/ponderado")
def actualizar_pesos(pesos: PesosUpdate):
    """Actualizar pesos."""
    try:
        return set_pesos(pesos.peso_deteccion, pesos.peso_reporte)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoints - Gráficos
@app.get("/buses/grafica")
def grafica_buses():
    """Mapa de buses activos."""
    try:
        archivo = generar_mapa_buses(db)
        if archivo and os.path.exists(archivo):
            from fastapi.responses import FileResponse
            return FileResponse(archivo, media_type="image/png")
        raise HTTPException(status_code=500, detail="No se pudo generar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anomalias/grafica")
def grafica_anomalias():
    """Mapa de anomalías."""
    try:
        archivo = generar_mapa_anomalias(db)
        if archivo and os.path.exists(archivo):
            from fastapi.responses import FileResponse
            return FileResponse(archivo, media_type="image/png")
        raise HTTPException(status_code=500, detail="No se pudo generar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Monitoreo background
def iniciar_monitoreo_background():
    """Inicia el monitoreo en background."""
    global monitoreo_activo, tracker
    try:
        tracker = BusTracker()
        monitoreo_activo = True
        print(f"[MONITOREO] Iniciando cada {MONITOR_INTERVAL}s...")
        
        while monitoreo_activo:
            try:
                resultado = tracker.escanear_rutas()
                print(f"[MONITOREO] {resultado['total_buses_encontrados']} buses, {resultado['guardados']} guardados")
            except Exception as e:
                print(f"[MONITOREO] Error: {e}")
            
            time.sleep(MONITOR_INTERVAL)
    except Exception as e:
        print(f"[MONITOREO] Error fatal: {e}")
        monitoreo_activo = False

@app.get("/monitoreo")
def estado_monitoreo():
    """Estado del monitoreo."""
    return {
        "monitoreo_activo": monitoreo_activo,
        "intervalo": MONITOR_INTERVAL
    }

# Inicialización
print("=" * 60)
print("  API DE ANOMALÍAS TRANSMILENIO v2.0")
print("  + DETECCIÓN + REPORTES + PONDERADO")
print("=" * 60)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Iniciar monitoreo en background
    monitoreo_thread = Thread(target=iniciar_monitoreo_background, daemon=True)
    monitoreo_thread.start()
    print(f"Monitoreo iniciado (cada {MONITOR_INTERVAL}s)")
    
    print(f"\nEndpoints disponibles:")
    print(f"  GET /health              - Estado")
    print(f"  GET /anomalias/deteccion - Solo detección")
    print(f"  GET /anomalias/reportes  - Solo reportes")
    print(f"  GET /anomalias/ponderado - Combinación ponderada")
    print(f"  POST /reportes/crear     - Crear reporte")
    print(f"  POST /reportes/votar     - Votar reporte")
    print(f"  GET /config/ponderado   - Ver pesos")
    print(f"  PUT /config/ponderado  - Actualizar pesos")
    print(f"  GET /buses/grafica     - Mapa de buses")
    print(f"  GET /anomalias/grafica  - Mapa de anomalías")
    print("=" * 60)
    print(f"Servidor: http://localhost:{port}")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)