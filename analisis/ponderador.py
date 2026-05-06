"""
Ponderador que combina detección automática + reportes de usuarios.
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime

from src.database import BusDatabase
from src.analisis.anomaly_detector import detectar_anomalias
from src.firebase.client import get_all_reportes, get_reporte_by_id
from src.ia.prediction_service import PredictionService
from src.ia.schemas import PrediccionRequest

# Get base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PONDERADO_CONFIG = os.path.join(BASE_DIR, "src", "config", "ponderado.json")

# Default weights
PESOS_DEFAULT = {
    "peso_deteccion": 0.5,
    "peso_reporte": 0.3,
    "peso_prediccion_ia": 0.2
}

def cargar_pesos() -> Dict[str, float]:
    """Load weights from config file."""
    if os.path.exists(PONDERADO_CONFIG):
        with open(PONDERADO_CONFIG, 'r') as f:
            return json.load(f)
    return PESOS_DEFAULT.copy()

def guardar_pesos(pesos: Dict[str, float]) -> None:
    """Save weights to config file."""
    with open(PONDERADO_CONFIG, 'w') as f:
        json.dump(pesos, f, indent=2)

def get_pesos() -> Dict[str, float]:
    """Get current weights."""
    return cargar_pesos()

def set_pesos(peso_deteccion: float, peso_reporte: float, peso_prediccion_ia: float = 0.2) -> Dict[str, float]:
    """Set new weights."""
    if peso_deteccion + peso_reporte + peso_prediccion_ia != 1.0:
        raise ValueError("Los pesos deben sumar 1.0")
    
    pesos = {
        "peso_deteccion": peso_deteccion,
        "peso_reporte": peso_reporte,
        "peso_prediccion_ia": peso_prediccion_ia
    }
    guardar_pesos(pesos)
    return pesos

def get_reportes_activos() -> List[Dict]:
    """Get active reports from Firebase."""
    try:
        reportes = get_all_reportes()
        # Filter only recent or verified reports
        activos = [r for r in reportes if r.get("verificado") or r.get("descartes", 0) < 5]
        return activos
    except Exception as e:
        print(f"Error getting reports: {e}")
        return []

def calcular_score_reporte(reporte: Dict) -> float:
    """Calculate score for a report (0-100)."""
    score = 0
    
    if reporte.get("verificado"):
        score += 50
    
    votos_pos = reporte.get("votos_positivos", 0)
    score += min(votos_pos * 15, 30)  # Up to 30 points for votes
    
    # Subtract negative votes
    votos_neg = reporte.get("votos_negativos", 0)
    score -= min(votos_neg * 10, 20)
    
    return max(0, min(score, 100))

def get_reportes_as_anomalias() -> List[Dict]:
    """Convert reports to anomaly format."""
    reportes = get_reportes_activos()
    anomalias = []
    
    for r in reportes:
        ubi = r.get("ubicacion", [])
        score = calcular_score_reporte(r)
        
        if ubi and len(ubi) >= 2:
            anomalias.append({
                "tipo": r.get("tipo", "REPORTE"),
                "coordenadas": {
                    "latitud": ubi[0],
                    "longitud": ubi[1]
                },
                "porcentaje_confianza": score,
                "buses_involucrados": 1,
                "fuente": "reporte_usuario",
                "reporte_id": r.get("id"),
                "verificado": r.get("verificado", False),
                "descripciones": r.get("descripcion", "")
            })
    
    return anomalias


def calcular_score_prediccion_ia(textos: List[str] = None) -> float:
    """Calculate prediction score using IA (NLP + expert rules)."""
    try:
        prediction_service = PredictionService()
        
        if textos is None or len(textos) == 0:
            default_textos = [
                "TransMilenio operando normalmente",
                "Sin reporte de anomalías",
                "Movilidad fluida en la ciudad"
            ]
            request = PrediccionRequest(
                zona="Bogotá",
                publicaciones=default_textos,
                reportes_app=[]
            )
        else:
            request = PrediccionRequest(
                zona="Bogotá",
                publicaciones=textos,
                reportes_app=[]
            )
        
        response = prediction_service.predecir_riesgo(request)
        return float(response.probabilidad)
    except Exception as e:
        print(f"Error in prediction IA: {e}")
        return 0.0


def detectar_anomalias_ponderadas(db: BusDatabase = None, textos_ia: List[str] = None) -> Dict[str, Any]:
    """
    Main function - combines automatic detection + user reports.
    Returns weighted anomaly analysis.
    """
    pesos = get_pesos()
    peso_det = pesos["peso_deteccion"]
    peso_rep = pesos["peso_reporte"]
    peso_pred = pesos.get("peso_prediccion_ia", 0.2)
    
    ahora = datetime.now()
    
    # Get automatic detection
    deteccion_score = 0
    deteccion_anomalias = []
    
    if db:
        try:
            analisis = detectar_anomalias(db)
            deteccion_anomalias = analisis.get("anomalias", [])
            
            # Calculate detection score based on anomalies
            if deteccion_anomalias:
                scores = [a.get("porcentaje_confianza", 0) for a in deteccion_anomalias]
                deteccion_score = sum(scores) / len(scores)
            else:
                res = analisis.get("resumen", {})
                total_anomalias = res.get("total_anomalias", 0)
                deteccion_score = min(total_anomalias * 20, 100)
        except Exception as e:
            print(f"Error in detection: {e}")
    
    # Get user reports
    reportes_anomalias = []
    reporte_score = 0
    
    try:
        reportes_anomalias = get_reportes_as_anomalias()
        if reportes_anomalias:
            scores = [r.get("porcentaje_confianza", 0) for r in reportes_anomalias]
            reporte_score = sum(scores) / len(scores)
    except Exception as e:
        print(f"Error in reports: {e}")
    
    # Get IA prediction score
    prediccion_ia_score = calcular_score_prediccion_ia(textos_ia)
    
    # Calculate combined score with 3 weights
    score_ponderado = (deteccion_score * peso_det) + (reporte_score * peso_rep) + (prediccion_ia_score * peso_pred)
    
    # Determine overall status
    if score_ponderado >= 70:
        estado = "ALTO"
    elif score_ponderado >= 40:
        estado = "MEDIO"
    else:
        estado = "BAJO"
    
    return {
        "timestamp": ahora.isoformat(),
        "estado": estado,
        "score_ponderado": round(score_ponderado, 1),
        "deteccion": {
            "score": round(deteccion_score, 1),
            "peso": peso_det,
            "anomalias": deteccion_anomalias
        },
        "reportes": {
            "score": round(reporte_score, 1),
            "peso": peso_rep,
            "cantidad": len(reportes_anomalias),
            "anomalias": reportes_anomalias
        },
        "prediccion_ia": {
            "score": round(prediccion_ia_score, 1),
            "peso": peso_pred
        },
        "pesos": pesos,
        "resumen": {
            "total_detecciones": len(deteccion_anomalias),
            "total_reportes": len(reportes_anomalias),
            "estado": estado
        }
    }

def get_resumen_ponderado() -> Dict:
    """Get summary of weighted analysis."""
    analisis = detectar_anomalias_ponderadas()
    return analisis.get("resumen", {})

def formatear_salida(analisis: Dict) -> str:
    """Format output for console."""
    lines = []
    lines.append("=" * 60)
    lines.append("    ANÁLISIS PONDERADO - 3 FUENTES")
    lines.append("=" * 60)
    lines.append(f"Fecha: {analisis['timestamp']}")
    lines.append(f"Estado: {analisis['estado']}")
    lines.append(f"Score Ponderado: {analisis['score_ponderado']}%")
    lines.append("")
    
    det = analisis.get("deteccion", {})
    lines.append(f"[DETECCIÓN AUTOMÁTICA] {det.get('score', 0)}% (peso: {det.get('peso', 0)*100}%)")
    lines.append(f"  Anomalías detectadas: {len(det.get('anomalias', []))}")
    lines.append("")
    
    rep = analisis.get("reportes", {})
    lines.append(f"[REPORTES USUARIOS] {rep.get('score', 0)}% (peso: {rep.get('peso', 0)*100}%)")
    lines.append(f"  Reportes activos: {rep.get('cantidad', 0)}")
    lines.append("")
    
    pred = analisis.get("prediccion_ia", {})
    lines.append(f"[PREDICCIÓN IA] {pred.get('score', 0)}% (peso: {pred.get('peso', 0)*100}%)")
    lines.append("")
    
    res = analisis.get("resumen", {})
    lines.append("-" * 60)
    lines.append(f"Total anomalías combinadas: {res.get('total_detecciones', 0) + res.get('total_reportes', 0)}")
    lines.append(f"Estado general: {res.get('estado', 'N/A')}")
    
    return "\n".join(lines)