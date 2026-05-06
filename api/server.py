"""
Servidor unificado FastAPI.
Combina detección automática + reportes de usuarios.

Ejecutar: python -m src.api.server
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os as os_module

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

# === WEB STATIC FILES ===
WEB_DIR = os_module.path.join(os_module.path.dirname(__file__), '..', 'web')
if os_module.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

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
    get_reportes_activos,
    calcular_score_prediccion_ia
)
from src.firebase.client import (
    create_reporte,
    votacion,
    get_all_reportes,
    get_reporte_by_id
)
from src.analisis.graficos import generar_mapa_buses, generar_mapa_anomalias, generar_todas_graficas
from src.api.bus_tracker import BusTracker
from src.ia.prediction_service import PredictionService
from src.ia.schemas import PrediccionRequest, ReporteAppInput
from src.ia.risk_integrator import calcular_prediccion_integrada, get_fuentes_estado
from src.ia.whatsapp_tm_service import get_tm_whatsapp_messages, find_recent_alerts_for_zone, now_colombia, is_whapi_configured
from src.api.demo_service import (
    crear_escenario_demo, limpiar_demo,
    get_demo_state, get_demo_reportes, get_demo_alertas, get_demo_buses
)
from threading import Thread
import time
import re

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
    peso_prediccion_ia: float = 0.2

class PrediccionRequestIA(BaseModel):
    zona: str = "Bogotá"
    publicaciones: List[str] = []
    reportes_app: List[ReporteAppInput] = []

class EscenarioRequest(BaseModel):
    zona: str
    intensidad: str = "alto"

class ChatbotRequest(BaseModel):
    pregunta: str
    zona: str = ""

# Mapa de alias a nombre canonico de zona
ZONE_ALIASES = {
    # Universidad Pedagogica
    "universidad pedagogica": "Universidad Pedagogica",
    "universidad pedagógica": "Universidad Pedagogica",
    "la pedagogica": "Universidad Pedagogica",
    "u pedagogica": "Universidad Pedagogica",
    "pedagogica": "Universidad Pedagogica",
    # Universidad Distrital
    "universidad distrital": "Universidad Distrital",
    "u distrital": "Universidad Distrital",
    "distrital": "Universidad Distrital",
    # Portal Eldorado
    "portal eldorado": "Portal Eldorado",
    "portal el dorado": "Portal Eldorado",
    "eldorado": "Portal Eldorado",
    "el dorado": "Portal Eldorado",
    # Avenida Caracas
    "avenida caracas": "Avenida Caracas",
    "av caracas": "Avenida Caracas",
    "caracas": "Avenida Caracas",
    "troncal caracas": "Avenida Caracas",
    # Portal Norte
    "portal norte": "Portal Norte",
    # Portal Sur
    "portal sur": "Portal Sur",
    # Portal Americas
    "portal americas": "Portal Americas",
    "portal américas": "Portal Americas",
    "americas": "Portal Americas",
    # Portal 20 de Julio
    "portal 20 de julio": "Portal 20 de Julio",
    "20 de julio": "Portal 20 de Julio",
    # Avenida Circunvalar
    "avenida circunvalar con calle 26": "Avenida Circunvalar con Calle 26",
    "avenida circunvalar": "Avenida Circunvalar con Calle 26",
    "circunvalar": "Avenida Circunvalar con Calle 26",
    # Carrera 5 con Calle 28
    "carrera 5 con calle 28": "Carrera 5 con Calle 28",
    "cra 5 con calle 28": "Carrera 5 con Calle 28",
    "cra 5 cll 28": "Carrera 5 con Calle 28",
    "cra 5 calle 28": "Carrera 5 con Calle 28",
    "carrera 5 con cll 28": "Carrera 5 con Calle 28",
    "carrera 5 cll 28": "Carrera 5 con Calle 28",
    # Carrera 7 con Calle 28
    "carrera 7 con calle 28": "Carrera 7 con Calle 28",
    "cra 7 con calle 28": "Carrera 7 con Calle 28",
    "cra 7 cll 28": "Carrera 7 con Calle 28",
    "carrera septima con calle 28": "Carrera 7 con Calle 28",
    "carrera séptima con calle 28": "Carrera 7 con Calle 28",
    # Calle 72 con Carrera 11
    "calle 72 con carrera 11": "Calle 72 con Carrera 11",
    "cll 72 con cra 11": "Calle 72 con Carrera 11",
    # Calle 12B con Carrera 10
    "calle 12b con carrera 10": "Calle 12B con Carrera 10",
    # Carrera 10 con Calle 24
    "carrera 10 con calle 24": "Carrera 10 con Calle 24",
    # Carrera 30 con Avenida Chile
    "carrera 30 con avenida chile": "Carrera 30 con Avenida Chile",
}

def _normalize_question(texto: str) -> str:
    if not texto:
        return ""
    import unicodedata
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^\w\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def extraer_zona_desde_pregunta(pregunta: str):
    if not pregunta:
        return None
    pregunta_norm = _normalize_question(pregunta)

    best = None
    best_len = 0
    for alias, canonico in ZONE_ALIASES.items():
        alias_norm = _normalize_question(alias)
        if alias_norm in pregunta_norm:
            if len(alias_norm) > best_len:
                best = canonico
                best_len = len(alias_norm)

    return best

# === NUEVOS ENDPOINTS ===

# Web principal
@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os_module.path.join(WEB_DIR, "index.html")
    if os_module.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Web no encontrada</h1>", status_code=404)

# Prediccion integrada (SOLO datos reales)
@app.get("/prediccion/integrada")
def prediccion_integrada(zona: str = "Portal Eldorado"):
    try:
        resultado = calcular_prediccion_integrada(
            zona=zona,
            db=db
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chatbot
@app.post("/chatbot")
def chatbot_endpoint(request: ChatbotRequest):
    try:
        zona_desde_pregunta = extraer_zona_desde_pregunta(request.pregunta)
        zona_body = request.zona.strip() if request.zona.strip() else None

        if zona_desde_pregunta:
            zona = zona_desde_pregunta
        elif zona_body:
            zona = zona_body
        else:
            return {
                "respuesta": "No detecto una zona en tu pregunta. Por favor escribe el nombre de una zona o lugar de Bogota (ej: Portal Eldorado, Universidad Pedagogica, Avenida Caracas).",
                "zona": None,
                "probabilidad": 0,
                "nivel_riesgo": "sin_zona",
                "fuentes": {},
                "fuentes_usadas": [],
                "fuentes_no_disponibles": [],
                "explicacion": ["No se pudo determinar la zona de consulta."],
                "recomendaciones": ["Escribe el nombre de una zona para analizar el riesgo."],
                "alerta_oficial_hoy": False
            }
        resultado = calcular_prediccion_integrada(
            zona=zona,
            db=db
        )
        prob = resultado["probabilidad"]
        nivel = resultado["nivel_riesgo"]
        fuentes = resultado.get("fuentes", {})
        fuentes_usadas = resultado.get("fuentes_usadas", [])
        fuentes_no_disp = resultado.get("fuentes_no_disponibles", [])
        alerta_oficial = resultado.get("alerta_oficial_hoy", False)
        estado_evento = resultado.get("estado_evento") or "sin_alerta_hoy"
        whatsapp_tm = fuentes.get("whatsapp_transmilenio", {})
        respuesta = f"Para {zona} el sistema estima riesgo {nivel} del {prob}%. "

        if alerta_oficial and whatsapp_tm.get("tipo_dato") == "real_hoy":
            if estado_evento == "restablecido":
                respuesta += "El ultimo aviso oficial de TransMilenio indica restablecimiento del servicio, "
                respuesta += "cancelacion de desvios o retorno a recorridos habituales. "
                respuesta += "No necesariamente confirma un paro si la alerta no lo dice literalmente."
            elif estado_evento == "activo":
                respuesta += "El ultimo aviso oficial de TransMilenio indica una afectacion activa."
                ultimo = whatsapp_tm.get("ultimo_mensaje_oficial", {})
                if ultimo and ultimo.get("texto"):
                    txt = ultimo["texto"].lower()
                    if "cierre" in txt or "cierran" in txt:
                        respuesta += " Reporta cierre de estaciones."
                    if "desvio" in txt:
                        respuesta += " Reporta desvios."
                    if "manifestacion" in txt or "protesta" in txt:
                        respuesta += " Reporta manifestacion."
                respuesta += " Esto indica una afectacion importante; no necesariamente confirma un paro si la alerta no lo dice literalmente."
            elif estado_evento == "parcial":
                respuesta += "El ultimo aviso oficial indica operacion parcial o retrasos. "
                respuesta += "No necesariamente confirma un paro si la alerta no lo dice literalmente."
            else:
                respuesta += "Se detecto una alerta oficial reciente de TransMilenio."
        else:
            if fuentes_usadas:
                if prob > 0:
                    respuesta += "La prediccion combina: " + ", ".join(fuentes_usadas) + ". "
                else:
                    respuesta += "No se detectaron senales de riesgo en las fuentes disponibles. "
            if fuentes_no_disp:
                respuesta += "Fuentes sin datos: " + ", ".join(fuentes_no_disp) + ". "
            recs = resultado.get("recomendaciones", [])
            if recs:
                respuesta += recs[0]
        return {
            "respuesta": respuesta,
            "zona": resultado["zona"],
            "probabilidad": prob,
            "nivel_riesgo": nivel,
            "fuentes": fuentes,
            "fuentes_usadas": fuentes_usadas,
            "fuentes_no_disponibles": fuentes_no_disp,
            "explicacion": resultado.get("explicacion", []),
            "recomendaciones": resultado.get("recomendaciones", []),
            "alerta_oficial_hoy": alerta_oficial,
            "estado_evento": estado_evento
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Demo: Crear escenario
@app.post("/demo/crear-escenario")
def crear_escenario(request: EscenarioRequest):
    try:
        resultado = crear_escenario_demo(request.zona, request.intensidad)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Demo: Limpiar
@app.post("/demo/limpiar")
def demo_limpiar():
    try:
        return limpiar_demo()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Demo: Estado
@app.get("/demo/estado")
def demo_estado():
    try:
        estado = get_demo_state()
        return estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Estado de fuentes
@app.get("/fuentes/estado")
def fuentes_estado():
    try:
        return get_fuentes_estado()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WhatsApp/TM mensajes recientes
@app.get("/whatsapp/tm/recientes")
def whatsapp_tm_recientes(count: int = 20):
    try:
        result = get_tm_whatsapp_messages(count=count)
        return {
            "status": result.get("status", "ok"),
            "modo": result.get("modo", "sin_configuracion"),
            "fecha_colombia": result.get("fecha_colombia", now_colombia().strftime("%Y-%m-%d")),
            "mensajes": result.get("mensajes", []),
            "advertencia": result.get("advertencia")
        }
    except Exception as e:
        return {
            "status": "error",
            "modo": "error",
            "fecha_colombia": now_colombia().strftime("%Y-%m-%d"),
            "mensajes": [],
            "advertencia": f"Error al consultar WhatsApp/TM: {str(e)}"
        }

# === FIN NUEVOS ENDPOINTS ===

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
        return set_pesos(pesos.peso_deteccion, pesos.peso_reporte, pesos.peso_prediccion_ia)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Endpoints - Predicción IA
@app.post("/ia/prediccion")
def prediccion_ia(request: PrediccionRequestIA):
    """Predicción de riesgo usando NLP + reglas expertas."""
    try:
        prediction_service = PredictionService()
        pred_request = PrediccionRequest(
            zona=request.zona,
            publicaciones=request.publicaciones,
            reportes_app=request.reportes_app
        )
        return prediction_service.predecir_riesgo(pred_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ia/prediccion/demo")
def prediccion_demo(zona: str = "Portal Norte"):
    """Predicción de demostración."""
    try:
        publicaciones = [
            f"Se reporta bloqueo en {zona} por manifestación",
            "Hay paro de transportadores y congestión fuerte"
        ]
        prediction_service = PredictionService()
        request = PrediccionRequest(zona=zona, publicaciones=publicaciones, reportes_app=[])
        return prediction_service.predecir_riesgo(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ia/prediccion/score")
def prediccion_score(textos: Optional[List[str]] = None):
    """Get prediction score only."""
    try:
        score = calcular_score_prediccion_ia(textos)
        nivel = "alto" if score > 60 else "medio" if score > 30 else "bajo"
        return {"score": score, "nivel": nivel}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
print("  + DETECCIÓN + REPORTES + PREDICCIÓN IA")
print("=" * 60)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Iniciar monitoreo en background
    monitoreo_thread = Thread(target=iniciar_monitoreo_background, daemon=True)
    monitoreo_thread.start()
    print(f"Monitoreo iniciado (cada {MONITOR_INTERVAL}s)")
    
    print(f"\nEndpoints disponibles:")
    print(f"  GET /                       - Web principal")
    print(f"  GET /health                 - Estado")
    print(f"  GET /fuentes/estado         - Estado de fuentes reales")
    print(f"  GET /anomalias/deteccion    - Solo deteccion")
    print(f"  GET /anomalias/reportes     - Solo reportes")
    print(f"  GET /anomalias/ponderado    - Combinacion ponderada")
    print(f"  POST /reportes/crear        - Crear reporte")
    print(f"  POST /reportes/votar        - Votar reporte")
    print(f"  GET /config/ponderado       - Ver pesos")
    print(f"  PUT /config/ponderado       - Actualizar pesos")
    print(f"  GET /buses/grafica          - Mapa de buses")
    print(f"  GET /anomalias/grafica      - Mapa de anomalias")
    print(f"  POST /ia/prediccion         - Prediccion IA")
    print(f"  GET /ia/prediccion/demo     - Prediccion demo")
    print(f"  GET /ia/prediccion/score    - Score prediccion")
    print(f"  GET /prediccion/integrada   - Prediccion integrada SOLO REAL")
    print(f"  POST /chatbot               - Chatbot conversacional")
    print("=" * 60)
    print(f"Servidor: http://localhost:{port}")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)