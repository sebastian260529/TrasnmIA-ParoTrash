"""
DeepSeek AI Service para generar respuestas naturales.
"""
import os
import requests
from typing import Dict, Any, Optional

DEEPSEEK_API_KEY = None
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def get_deepseek_api_key() -> str:
    global DEEPSEEK_API_KEY
    if DEEPSEEK_API_KEY is None:
        DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    return DEEPSEEK_API_KEY

def generar_respuesta(pregunta: str, datos_fuentes: Dict[str, Any]) -> str:
    """
    Genera una respuesta natural basada en los datos de las fuentes.
    """
    api_key = get_deepseek_api_key()
    if not api_key:
        return generar_respuesta_fallback(pregunta, datos_fuentes)

    buses = datos_fuentes.get("buses", {})
    firebase = datos_fuentes.get("firebase", {})
    whatsapp = datos_fuentes.get("whatsapp", {})
    historico = datos_fuentes.get("historico", {})
    prediccion = datos_fuentes.get("prediccion", {})

    scores = prediccion.get("scores", {})
    prob = prediccion.get("probabilidad", 0)
    nivel = prediccion.get("nivel", "desconocido")

    # Construir detalle de scores
    scores_detail = ""
    if scores:
        for fuente, score in scores.items():
            if score > 0:
                scores_detail += f"- {fuente}: {score}%\n"

    prompt = f"""Eres un asistente de TransMilenio Bogotá. El usuario pregunta: "{pregunta}"

DATOS DEL ANÁLISIS:
- Buses GPS: {buses.get('mensaje', 'Sin datos')}
- Firebase (reportes usuarios): {firebase.get('mensaje', 'Sin datos')}
- WhatsApp TM: {whatsapp.get('mensaje', 'Sin datos')}
- Datos históricos: {historico.get('mensaje', 'Sin datos')}

ANÁLISIS DE RIESGO:
{f'Puntuaciones por fuente:\n{scores_detail}' if scores_detail else ''}
PREDICCIÓN FINAL: {prob}% (nivel: {nivel})

Responde en español, de manera clara y amigable. USA LOS PORCENTAJES EXACTOS QUE APARECEN EN "PREDICCIÓN FINAL" ({prob}%). No inventes otros números."""

    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Eres un asistente útil de TransMilenio Bogotá."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return generar_respuesta_fallback(pregunta, datos_fuentes)
    except Exception:
        return generar_respuesta_fallback(pregunta, datos_fuentes)

def generar_respuesta_fallback(pregunta: str, datos_fuentes: Dict[str, Any]) -> str:
    """
    Genera respuesta sin usar DeepSeek (fallback).
    """
    buses = datos_fuentes.get("buses", {})
    firebase = datos_fuentes.get("firebase", {})
    whatsapp = datos_fuentes.get("whatsapp", {})
    historico = datos_fuentes.get("historico", {})
    prediccion = datos_fuentes.get("prediccion", {})

    probabilidad = prediccion.get("probabilidad", 0)
    nivel = prediccion.get("nivel", "desconocido")

    respuesta = f"Para la zona solicitada:\n\n"

    if buses.get("datos"):
        respuesta += f"🚌 Buses: {buses['datos']}\n"
    else:
        respuesta += "🚌 Buses: No hay anomalías de buses en esta zona\n"

    if firebase.get("datos"):
        respuesta += f"📱 Firebase: {firebase['datos']}\n"
    else:
        respuesta += "📱 Firebase: No hay reportes de usuarios en esta zona\n"

    if whatsapp.get("datos"):
        respuesta += f"💬 WhatsApp: {whatsapp['datos']}\n"
    else:
        respuesta += "💬 WhatsApp: No hay datos de WhatsApp para esta zona\n"

    if historico.get("datos"):
        respuesta += f"📊 Histórico: {historico['datos']}\n"
    else:
        respuesta += "📊 Histórico: No hay datos históricos para esta zona\n"

    respuesta += f"\n⚠️ Predicción de riesgo de paro: {probabilidad}% ({nivel.upper()})"

    return respuesta