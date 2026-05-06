"""
Firestore client for handling reports.
Based on ParoTrash logic.
"""

import math
from datetime import datetime
from typing import List, Dict, Any, Optional
from firebase_admin import firestore

from src.firebase import init_firebase, get_collection

# Distance in meters for consensus
RADIO_CONSENSUS = 100  # meters

def haversine(p1: List[float], p2: List[float]) -> float:
    """Calculate distance between two points [lat, lon] in meters."""
    if not p1 or not p2 or len(p1) < 2 or len(p2) < 2:
        return float('inf')
    
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(p1[0]), math.radians(p2[0])
    dphi = math.radians(p2[0] - p1[0])
    dlambda = math.radians(p2[1] - p1[1])
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def get_all_reportes() -> List[Dict]:
    """Get all reports from Firestore."""
    init_firebase()
    reportes_ref = get_collection("reportes").stream()
    
    reportes = []
    for doc in reportes_ref:
        data = doc.to_dict()
        data["id"] = doc.id
        reportes.append(data)
    
    return reportes

def get_reporte_by_id(reporte_id: str) -> Optional[Dict]:
    """Get a specific report by ID."""
    init_firebase()
    doc = get_collection("reportes").document(reporte_id).get()
    
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None

def create_reporte(reporte_id: str, id_usuario: str, ubicacion: List[float], 
                tipo: str = "trancón", descripcion: str = "") -> Dict:
    """Create a new report."""
    init_firebase()
    
    reporte_data = {
        "id_usuario": id_usuario,
        "ubicacion": ubicacion,
        "tipo": tipo,
        "descripcion": descripcion,
        "verificado": False,
        "descartes": 0,
        "votos_positivos": 0,
        "votos_negativos": 0,
        "timestamp": datetime.now().isoformat()
    }
    
    get_collection("reportes").document(reporte_id).set(reporte_data)
    
    # Also create/update user
    user_ref = get_collection("usuarios").document(id_usuario)
    user_doc = user_ref.get()
    if not user_doc.exists:
        user_ref.set({
            "nombre": f"Usuario_{id_usuario[:8]}",
            "reputacion": 0,
            "fecha_registro": datetime.now().isoformat()
        })
    
    return reporte_data

def votacion(reporte_id: str, tipo_voto: str = "positivo") -> Dict:
    """
    Vote on a report.
    tipo_voto: "positivo" (es válido) or "negativo" (descartar)
    """
    init_firebase()
    
    reporte_ref = get_collection("reportes").document(reporte_id)
    reporte_doc = reporte_ref.get()
    
    if not reporte_doc.exists:
        return {"status": "error", "message": "Reporte no encontrado"}
    
    reporte_data = reporte_doc.to_dict()
    
    # Update vote count
    if tipo_voto == "positivo":
        new_votos = reporte_data.get("votos_positivos", 0) + 1
        reporte_ref.update({"votos_positivos": new_votos})
        
        # Check verification (3+ positive votes or high reputation)
        if new_votos >= 3:
            reporte_ref.update({"verificado": True})
        
        return {"status": "voto_positivo", "votos": new_votos}
    
    else:
        new_descartes = reporte_data.get("descartes", 0) + 1
        reporte_ref.update({"descartes": new_descartes})
        
        # Penalize author if 5+ disrecks
        if new_descartes >= 5:
            id_autor = reporte_data.get("id_usuario")
            if id_autor:
                autor_ref = get_collection("usuarios").document(id_autor)
                autor_doc = autor_ref.get()
                if autor_doc.exists:
                    autor_data = autor_doc.to_dict()
                    reputacion_actual = autor_data.get("reputacion", 0)
                    autor_ref.update({"reputacion": max(0, reputacion_actual - 10)})
        
        return {"status": "descartado", "descartes": new_descartes}

def get_reportes_cercanos(ubicacion: List[float], radio: int = None) -> List[Dict]:
    """Get reports within radio of a location."""
    radio = radio or RADIO_CONSENSUS
    reportes = get_all_reportes()
    
    cercanos = []
    for r in reportes:
        if r.get("ubicacion") and isinstance(r["ubicacion"], list) and len(r["ubicacion"]) >= 2:
            dist = haversine(ubicacion, r["ubicacion"])
            if dist <= radio:
                r["distancia"] = round(dist, 1)
                cercanos.append(r)
    
    return cercanos

def verificar_reporte_por_consenso(reporte_id: str) -> Dict:
    """Verify report using consensus logic (from ParoTrash)."""
    reporte = get_reporte_by_id(reporte_id)
    if not reporte:
        return {"status": "error", "message": "Reporte no encontrado"}
    
    ubicacion = reporte.get("ubicacion")
    if not ubicacion:
        return {"status": "error", "message": "Sin ubicación"}
    
    # Find nearby reports
    reportes_cercanos = get_reportes_cercanos(ubicacion)
    
    # Count other reports in area (excluding self)
    otros = [r for r in reportes_cercanos if r["id"] != reporte_id]
    
    # Check author reputation
    id_usuario = reporte.get("id_usuario")
    reputacion = 0
    if id_usuario:
        user_doc = get_collection("usuarios").document(id_usuario).get()
        if user_doc.exists:
            reputacion = user_doc.to_dict().get("reputacion", 0)
    
    # Consensus logic
    es_verificado = len(otros) >= 3 or reputacion > 50
    
    # Update status
    if es_verificado:
        get_collection("reportes").document(reporte_id).update({"verificado": True})
    
    return {
        "status": "verificado" if es_verificado else "pendiente",
        "coincidencias": len(otros),
        "reputacion": reputacion,
        "reportes_cercanos": reportes_cercanos
    }