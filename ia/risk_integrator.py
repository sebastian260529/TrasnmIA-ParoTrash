import os
import csv
import re
import unicodedata
from typing import Dict, List, Optional, Any
from datetime import datetime

from database.database import BusDatabase
from analisis.anomaly_detector import detectar_anomalias
from ia.prediction_service import PredictionService
from ia.schemas import PrediccionRequest, ReporteAppInput
from ia.pattern_analysis import predict_risk_from_patterns, load_alert_dataset
from whatsapp.whatsapp_tm_service import (
    get_tm_whatsapp_messages, find_recent_alerts_for_zone,
    detect_strong_tm_alert, matches_zone, is_today_colombia,
    is_whapi_configured, normalize_text_simple,
    extract_text_from_whapi_message, extract_datetime_from_whapi_message,
    parse_tm_alert, now_colombia, get_whapi_config
)
from ubicacion_buses.location_service import (
    get_zone_coords, distance_between_points, enrich_bus_location,
    normalize_address, ZONAS_CONOCIDAS
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TM_CSV_PATH = os.path.join(BASE_DIR, "data", "tm_alerts_sample.csv")

TM_CSV_PATHS_TO_TRY = [
    TM_CSV_PATH,
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "ChatBot", "data", "tm_alerts_sample.csv"),
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "tm_alerts_sample.csv"),
    "C:\\Users\\sebas\\Documents\\Inteligencia Artificial\\ChatBot\\data\\tm_alerts_sample.csv",
    "data/tm_alerts_sample.csv",
]

def _get_tm_csv_path():
    for path in TM_CSV_PATHS_TO_TRY:
        if os.path.exists(path):
            return path
    return TM_CSV_PATH

PESOS = {
    "buses": 0.35,
    "whatsapp_transmilenio": 0.30,
    "firebase_reportes": 0.20,
    "ia_texto": 0.15
}

PALABRAS_CLAVE_RIESGO = [
    'paro', 'bloqueo', 'manifestacion', 'protesta', 'cierre',
    'sin operar', 'desvio', 'congestion', 'disturbio', 'flota sin paso',
    'estacion cerrada', 'portal cerrado', 'marcha', 'bloqueada', 'bloqueado'
]


def normalize_text(texto: str) -> str:
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^\w\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def _busca_en_dataset_historico(ubicacion: str) -> List[Dict]:
    csv_path = _get_tm_csv_path()
    alertas = load_alert_dataset(csv_path)
    if not alertas:
        return []
    normalized_query = normalize_address(ubicacion)
    palabras_query = set(normalized_query.split())
    coincidencias = []
    for alerta in alertas:
        ubi = normalize_address(alerta.get('ubicacion', '') or '')
        ubi_norm = normalize_address(alerta.get('ubicacion_normalizada', '') or '')
        texto = normalize_address(alerta.get('texto_original', '') or '')
        if normalized_query in ubi or normalized_query in ubi_norm or normalized_query in texto:
            coincidencias.append(alerta)
            continue
        if any(p in ubi or p in ubi_norm for p in palabras_query if len(p) > 3):
            coincidencias.append(alerta)
            continue
        for p in palabras_query:
            if len(p) > 3 and (p in ubi or p in ubi_norm or p in texto):
                coincidencias.append(alerta)
                break
    return coincidencias


def _score_buses(db: BusDatabase, zona: str) -> Dict[str, Any]:
    try:
        zone = get_zone_coords(zona)
        
        if not zone:
            return {
                "score": 0,
                "tipo_dato": "sin_zona",
                "detalle": f"Zona '{zona}' no reconocida.",
                "cantidad": 0,
                "datos_usados": [],
                "advertencia": f"La zona '{zona}' no está en la lista de zonas conocidas."
            }
        
        analisis = detectar_anomalias(db, force_refresh=True)
        anomalias = analisis.get("anomalias", [])
        
        captura = db.obtener_captura_actual()
        captura_real = [b for b in captura if not str(b.get("bus_id", "")).startswith("DEMO_") and not str(b.get("id", "")).startswith("DEMO_")]
        
        anomalias_en_zona = []
        buses_cercanos = 0
        datos_buses = []
        
        radio_zona = zone.get("radio_metros", 800)
        
        for anom in anomalias:
            coords = anom.get("coordenadas", {})
            lat = coords.get("latitud")
            lon = coords.get("longitud")
            
            if lat is not None and lon is not None:
                dist = distance_between_points(float(lat), float(lon), zone["lat"], zone["lon"])
                
                if dist <= radio_zona:
                    anomalias_en_zona.append(anom)
        
        if zone and captura_real:
            for bus in captura_real:
                lat = bus.get("latitud") or bus.get("latitude")
                lon = bus.get("longitud") or bus.get("longitude")
                if lat is not None and lon is not None:
                    try:
                        dist = distance_between_points(float(lat), float(lon), zone["lat"], zone["lon"])
                        if dist <= radio_zona:
                            buses_cercanos += 1
                            datos_buses.append({
                                "bus_id": bus.get("bus_id"),
                                "label": bus.get("label"),
                                "ruta": bus.get("ruta"),
                                "distancia_m": round(dist, 1),
                                "velocidad": bus.get("velocidad")
                            })
                    except (ValueError, TypeError):
                        pass
        
        if len(captura_real) == 0 and len(anomalias_en_zona) == 0 and buses_cercanos == 0:
            return {
                "score": 0,
                "tipo_dato": "sin_datos",
                "detalle": f"No hay buses reales recientes disponibles para {zona}.",
                "cantidad": 0,
                "datos_usados": [],
                "advertencia": "No hay buses reales recientes en la base de datos. El tracker debe estar activo para capturar posiciones."
            }
        
        score = 0
        detalle = ""
        tipo_principal = "ninguna"

        if anomalias_en_zona:
            scores_tipados = []
            for a in anomalias_en_zona:
                tipo = a.get("tipo", "desconocido")
                confianza = a.get("porcentaje_confianza", 0)

                if tipo == "MANIFESTACION":
                    score_ajustado = confianza * 0.85
                    scores_tipados.append(("MANIFESTACION", score_ajustado, 85))
                    tipo_principal = "MANIFESTACION"
                elif tipo == "TRANCON":
                    score_ajustado = min(confianza * 0.55, 55)
                    scores_tipados.append(("TRANCON", score_ajustado, 55))
                    if tipo_principal != "MANIFESTACION":
                        tipo_principal = "TRANCON"
                elif tipo == "BUS_VARADO":
                    score_ajustado = min(confianza * 0.25, 25)
                    scores_tipados.append(("BUS_VARADO", score_ajustado, 25))
                    if tipo_principal not in ["MANIFESTACION", "TRANCON"]:
                        tipo_principal = "BUS_VARADO"
                else:
                    scores_tipados.append((tipo, confianza, 100))

            score = sum(s[1] for s in scores_tipados) / len(scores_tipados)

            tipos = [a.get("tipo", "desconocido") for a in anomalias_en_zona]
            tipos_str = ", ".join(set(tipos))
            topes = f"(Manifestación:85%, Trancón:55%, Varado:25%)"

            detalle = f"Se detectaron {len(anomalias_en_zona)} anomalías en {zona}: {tipos_str}. Score ajustado: {score:.1f}%. {topes}"

            datos_usados = [{
                "tipo": a.get("tipo"),
                "coordenadas": a.get("coordenadas"),
                "porcentaje_confianza": a.get("porcentaje_confianza"),
                "buses_involucrados": a.get("buses_involucrados")
            } for a in anomalias_en_zona[:5]]
        elif buses_cercanos > 0:
            if buses_cercanos <= 3:
                score = 10
            elif buses_cercanos <= 7:
                score = 15
            else:
                score = 20
            tipo_principal = "buses_sin_anomalia"

            detalle = f"No hay anomalías formalizadas cerca de {zona}, pero se detectaron {buses_cercanos} buses en la zona. Score bajo: {score}%"
            datos_usados = datos_buses[:10]
        else:
            score = 0
            tipo_principal = "ninguna"
            detalle = f"No se detectaron anomalías ni buses afectados cerca de {zona}. Se revisaron {len(captura_real)} buses."
            datos_usados = []

        score_final = min(score, 85)

        return {
            "score": score_final,
            "tipo_dato": "real",
            "tipo_principal": tipo_principal,
            "detalle": detalle,
            "cantidad": len(anomalias_en_zona) + buses_cercanos,
            "datos_usados": datos_usados,
            "advertencia": None
        }
    except Exception as e:
        return {
            "score": 0,
            "tipo_dato": "error",
            "detalle": f"Error al consultar buses: {str(e)}",
            "cantidad": 0,
            "datos_usados": [],
            "advertencia": f"No fue posible consultar la fuente de buses: {str(e)}"
        }


def _score_whatsapp_transmilenio(zona: str) -> Dict[str, Any]:
    try:
        whapi_alerts = find_recent_alerts_for_zone(zona, count=50)
        hay_alerta_oficial_hoy = whapi_alerts.get("hay_alerta_oficial_hoy", False)
        estado_evento = whapi_alerts.get("estado_evento", "sin_alerta_hoy")
        ultimo_mensaje = whapi_alerts.get("ultimo_mensaje_oficial")
        alertas_hoy = whapi_alerts.get("alertas_hoy_para_zona", [])
        whapi_status = whapi_alerts.get("status", "")

        STATE_SCORES_MAP = {"activo": 100, "parcial": 40, "restablecido": 15, "sin_alerta_hoy": 0}
        STATE_NIVELES_MAP = {"activo": "alto", "parcial": "medio", "restablecido": "bajo", "sin_alerta_hoy": "bajo"}

        if hay_alerta_oficial_hoy and estado_evento in ("activo", "parcial", "restablecido"):
            alertas_resumen = []
            for a in alertas_hoy[:10]:
                alertas_resumen.append({
                    "message_id": a.get("message_id"),
                    "texto": a.get("texto", "")[:300],
                    "fecha_colombia": a.get("fecha_colombia"),
                    "hora_colombia": a.get("hora_colombia"),
                    "ubicacion_detectada": a.get("ubicacion_detectada"),
                    "severidad": a.get("severidad")
                })
            score_final = STATE_SCORES_MAP.get(estado_evento, 0)
            if estado_evento == "activo":
                detalle = (f"El ultimo aviso oficial de TransMilenio indica una afectacion activa en {zona}. "
                          f"Se detectaron {len(alertas_hoy)} mensajes de hoy coincidentes. "
                          f"Por eso el sistema asigna riesgo alto del 100% para la zona consultada.")
            elif estado_evento == "restablecido":
                detalle = (f"El ultimo aviso oficial de TransMilenio indica restablecimiento del servicio "
                          f"o cancelacion de desvios en {zona}. "
                          f"Aunque hubo {len(alertas_hoy)} mensajes de hoy, el mas reciente senala normalizacion.")
            elif estado_evento == "parcial":
                detalle = (f"El ultimo aviso oficial indica operacion parcial o retrasos en {zona}. "
                          f"Se detectaron {len(alertas_hoy)} mensajes de hoy coincidentes.")
            else:
                detalle = f"Se detectaron {len(alertas_hoy)} mensajes de WhatsApp/TM hoy para {zona}."
            return {
                "score": score_final,
                "tipo_dato": "real_hoy",
                "detalle": detalle,
                "coincidencias": len(alertas_hoy),
                "datos_usados": alertas_resumen,
                "alertas_recientes": alertas_resumen,
                "alerta_oficial_hoy": True,
                "estado_evento": estado_evento,
                "ultimo_mensaje_oficial": ultimo_mensaje,
                "advertencia": None
            }

        total_alertas_hoy = len(alertas_hoy)

        if not alertas_hoy:
            return {
                "score": 0,
                "tipo_dato": "sin_datos_hoy",
                "detalle": f"No se encontraron mensajes de WhatsApp/TM para {zona} en el dia de hoy.",
                "coincidencias": 0,
                "datos_usados": [],
                "alerta_oficial_hoy": False,
                "advertencia": "No hay alertas del dia de hoy. Use IA/Texto para datos historicos."
            }

        return {
            "score": 60,
            "tipo_dato": "real_hoy",
            "detalle": f"Se detectaron {total_alertas_hoy} mensajes de WhatsApp/TM para {zona} en el dia de hoy.",
            "coincidencias": total_alertas_hoy,
            "datos_usados": alertas_hoy[:5],
            "alerta_oficial_hoy": False,
            "advertencia": None
        }
    except Exception as e:
        return {
            "score": 0,
            "tipo_dato": "error",
            "detalle": f"Error al consultar WhatsApp/TM: {str(e)}",
            "coincidencias": 0,
            "datos_usados": [],
            "alerta_oficial_hoy": False,
            "advertencia": f"Error al consultar WhatsApp: {str(e)}"
        }


def _score_firebase_reportes(zona: str) -> Dict[str, Any]:
    try:
        from firebase.client import get_all_reportes
        reportes_raw = get_all_reportes()
    except Exception as e:
        return {
            "score": 0,
            "tipo_dato": "error",
            "detalle": "Firebase no esta configurado o no responde.",
            "cantidad": 0,
            "datos_usados": [],
            "advertencia": f"Firebase no esta disponible: {str(e)}"
        }
    reportes_reales = [r for r in reportes_raw if not str(r.get("id", "")).startswith("DEMO_") and not str(r.get("reporte_id", "")).startswith("DEMO_")]
    reportes_filtrados = []
    palabras_detectadas = set()
    zone = get_zone_coords(zona)
    zona_normalizada = normalize_address(zona)
    for r in reportes_reales:
        match = False
        desc = normalize_text(r.get("descripcion", ""))
        tipo = normalize_text(r.get("tipo", ""))
        ubi = r.get("ubicacion", [])
        r_zona = normalize_text(r.get("zona", ""))
        if zone and isinstance(ubi, list) and len(ubi) >= 2:
            try:
                dist = distance_between_points(float(ubi[0]), float(ubi[1]), zone["lat"], zone["lon"])
                if dist <= zone["radio_metros"]:
                    match = True
            except (ValueError, TypeError):
                pass
        if zona_normalizada in desc or zona_normalizada in r_zona:
            match = True
        if zona_normalizada in tipo:
            match = True
        if match:
            for palabra in PALABRAS_CLAVE_RIESGO:
                if palabra in desc or palabra in tipo:
                    palabras_detectadas.add(palabra)
            reportes_filtrados.append({
                "id": r.get("id") or r.get("reporte_id"),
                "tipo": r.get("tipo"),
                "descripcion": r.get("descripcion"),
                "zona": r.get("zona"),
                "timestamp": r.get("timestamp")
            })
    cantidad = len(reportes_filtrados)
    if cantidad == 0:
        return {
            "score": 0,
            "tipo_dato": "sin_datos" if reportes_reales or not reportes_raw else "sin_datos",
            "detalle": f"No se encontraron reportes reales de usuarios en {zona}." + (" Firebase esta configurado pero sin reportes en esta zona." if reportes_raw else ""),
            "cantidad": 0,
            "datos_usados": [],
            "advertencia": "No hay reportes reales disponibles para esta zona."
        }
    if cantidad == 1:
        score = 25
    elif cantidad <= 3:
        score = 50
    elif cantidad <= 5:
        score = 70
    else:
        score = 85
    if palabras_detectadas:
        score = min(90, score + 10)
    detalle = f"Se encontraron {cantidad} reportes reales de usuarios en {zona}."
    if palabras_detectadas:
        detalle += f" Palabras clave: {', '.join(list(palabras_detectadas)[:5])}."
    return {
        "score": min(score, 90),
        "tipo_dato": "real",
        "detalle": detalle,
        "cantidad": cantidad,
        "datos_usados": reportes_filtrados[:10],
        "advertencia": None
    }


def _score_ia_texto(zona: str) -> Dict[str, Any]:
    try:
        prediction_service = PredictionService()

        coincidencias_hist = _busca_en_dataset_historico(zona)

        if not coincidencias_hist:
            return {
                "score": 0,
                "tipo_dato": "sin_datos",
                "detalle": f"No se encontraron alertas historicas para {zona} en el dataset de TransMilenio.",
                "palabras_clave": [],
                "advertencia": "No hay datos historicos para esta zona."
            }

        textos = []
        for al in coincidencias_hist:
            txt = al.get("texto_original", "")
            if txt:
                textos.append(txt)

        request = PrediccionRequest(zona=zona, publicaciones=textos, reportes_app=[])
        result = prediction_service.predecir_riesgo(request)
        palabras = result.palabras_clave_detectadas
        prob = result.probabilidad

        n = len(coincidencias_hist)
        if n == 1:
            prob = max(prob, 25)
        elif n <= 3:
            prob = max(prob, 45)
        elif n <= 6:
            prob = max(prob, 65)
        else:
            prob = max(prob, 80)

        if prob <= 30:
            detalle = f"El analisis de datos historicos no detecta senales fuertes de riesgo en {zona}."
        elif prob <= 60:
            detalle = f"El analisis de datos historicos detecta senales moderadas de riesgo en {zona}: {n} alertas encontradas."
        else:
            detalle = f"El analisis de datos historicos detecta senales fuertes de riesgo en {zona}: {n} alertas encontradas."

        if palabras:
            detalle += f" Palabras clave: {', '.join(palabras)}."

        return {
            "score": min(prob, 90),
            "tipo_dato": "historico",
            "detalle": detalle,
            "palabras_clave": palabras,
            "coincidencias": n,
            "datos_usados": coincidencias_hist[:5],
            "advertencia": "Datos basados en dataset historico de TransMilenio."
        }
    except Exception as e:
        return {
            "score": 0,
            "tipo_dato": "error",
            "detalle": f"Error en analisis de texto: {str(e)}",
            "palabras_clave": [],
            "advertencia": f"No fue posible ejecutar analisis de texto: {str(e)}"
        }


def _score_geolocalizacion(zona: str, buses_data: Dict, firebase_data: Dict, whatsapp_data: Dict) -> Dict[str, Any]:
    try:
        zone = get_zone_coords(zona)
        if not zone:
            zona_norm = normalize_address(zona)
            encontrada = False
            for z in ZONAS_CONOCIDAS:
                if z["direccion_normalizada"] in zona_norm or any(
                    p in z["direccion_normalizada"] for p in zona_norm.split() if len(p) > 3
                ):
                    zone = z
                    encontrada = True
                    break
            if not encontrada:
                return {
                    "score": 0,
                    "tipo_dato": "sin_datos",
                    "detalle": f"No se pudo geolocalizar la zona: {zona}. La zona no esta en el diccionario local de Bogota.",
                    "zona_normalizada": zona_norm,
                    "coordenadas_estimadas": {"lat": None, "lon": None},
                    "buses_cercanos": 0,
                    "reportes_cercanos": 0,
                    "alertas_historicas_cercanas": 0,
                    "advertencia": "Zona no conocida en el catalogo local. Agreguela en ZONAS_CONOCIDAS."
                }
        buses_cercanos = len(buses_data.get("datos_usados", []))
        reportes_cercanos = firebase_data.get("cantidad", 0)
        alertas_cercanas = whatsapp_data.get("coincidencias", 0)
        total_cercanos = buses_cercanos + reportes_cercanos + alertas_cercanas
        if total_cercanos == 0:
            score = 0
            detalle = f"No se encontraron elementos geolocalizados cerca de {zona}."
        elif total_cercanos <= 3:
            score = 20
            detalle = f"Pocos elementos geolocalizados cerca de {zona}: {total_cercanos} en total."
        elif total_cercanos <= 8:
            score = 40
            detalle = f"Cantidad moderada de elementos geolocalizados cerca de {zona}: {total_cercanos} en total."
        else:
            score = 60
            detalle = f"Alta concentracion de elementos geolocalizados cerca de {zona}: {total_cercanos} en total."
        return {
            "score": min(score, 70),
            "tipo_dato": "real",
            "detalle": detalle,
            "zona_normalizada": zone["direccion_normalizada"],
            "coordenadas_estimadas": {"lat": zone["lat"], "lon": zone["lon"]},
            "buses_cercanos": buses_cercanos,
            "reportes_cercanos": reportes_cercanos,
            "alertas_historicas_cercanas": alertas_cercanas,
            "advertencia": None
        }
    except Exception as e:
        return {
            "score": 0,
            "tipo_dato": "error",
            "detalle": f"Error en geolocalizacion: {str(e)}",
            "zona_normalizada": normalize_address(zona),
            "coordenadas_estimadas": {"lat": None, "lon": None},
            "buses_cercanos": 0,
            "reportes_cercanos": 0,
            "alertas_historicas_cercanas": 0,
            "advertencia": f"Error en modulo de geolocalizacion: {str(e)}"
        }


def calcular_prediccion_integrada(zona: str, db: BusDatabase = None, reportes_demo: List[Dict] = None, alertas_simuladas: List[str] = None, buses_demo: List[Dict] = None) -> Dict[str, Any]:
    if db is None:
        db = BusDatabase()
    errores_fuentes = []
    fuentes_usadas = []
    fuentes_no_disponibles = []
    buses = _score_buses(db, zona)
    if buses["advertencia"]:
        errores_fuentes.append({"fuente": "buses", "error": buses["advertencia"]})
    if buses["score"] > 0:
        fuentes_usadas.append("buses")
    else:
        fuentes_no_disponibles.append("buses")
    whatsapp = _score_whatsapp_transmilenio(zona)
    if whatsapp["advertencia"]:
        errores_fuentes.append({"fuente": "whatsapp_transmilenio", "error": whatsapp["advertencia"]})
    if whatsapp["score"] > 0:
        fuentes_usadas.append("whatsapp_transmilenio")
    else:
        fuentes_no_disponibles.append("whatsapp_transmilenio")
    firebase = _score_firebase_reportes(zona)
    if firebase["advertencia"]:
        errores_fuentes.append({"fuente": "firebase_reportes", "error": firebase["advertencia"]})
    if firebase["score"] > 0:
        fuentes_usadas.append("firebase_reportes")
    else:
        fuentes_no_disponibles.append("firebase_reportes")
    ia_texto = _score_ia_texto(zona)
    if ia_texto["advertencia"]:
        errores_fuentes.append({"fuente": "ia_texto", "error": ia_texto["advertencia"]})
    if ia_texto["score"] > 0:
        fuentes_usadas.append("ia_texto")
    else:
        fuentes_no_disponibles.append("ia_texto")
    alerta_oficial_hoy = whatsapp.get("alerta_oficial_hoy", False)
    whatsapp_tipo = whatsapp.get("tipo_dato", "")
    estado_evento = whatsapp.get("estado_evento", "sin_alerta_hoy")

    if alerta_oficial_hoy and whatsapp_tipo == "real_hoy":
        STATE_SCORES_MAP = {"activo": 100, "parcial": 40, "restablecido": 15}
        STATE_NIVELES_MAP = {"activo": "alto", "parcial": "medio", "restablecido": "bajo"}
        prob = STATE_SCORES_MAP.get(estado_evento, 100)
        score_ponderado = prob
        nivel = STATE_NIVELES_MAP.get(estado_evento, "alto")
        datos_reales_usados = True
    else:
        prob = (
            (buses.get("score", 0) * PESOS["buses"]) +
            (whatsapp.get("score", 0) * PESOS["whatsapp_transmilenio"]) +
            (firebase.get("score", 0) * PESOS["firebase_reportes"]) +
            (ia_texto.get("score", 0) * PESOS["ia_texto"])
        )
        prob = min(95, max(0, round(prob)))
        score_ponderado = prob
        datos_reales_usados = True
        if prob <= 30:
            nivel = "bajo"
        elif prob <= 65:
            nivel = "medio"
        else:
            nivel = "alto"

    explicacion = []
    if alerta_oficial_hoy and whatsapp_tipo == "real_hoy":
        explicacion.append(whatsapp.get("detalle", ""))
        if whatsapp.get("alertas_recientes"):
            for alerta in whatsapp.get("alertas_recientes", [])[:3]:
                txt = alerta.get("texto", "").strip()
                if txt:
                    explicacion.append(f"Alerta original: {txt[:250]}")
    else:
        if buses["score"] > 0:
            explicacion.append(buses["detalle"])
        if whatsapp["score"] > 0:
            explicacion.append(whatsapp["detalle"])
        if firebase["score"] > 0:
            explicacion.append(firebase["detalle"])
        if ia_texto["score"] > 0:
            explicacion.append(ia_texto["detalle"])
    if not explicacion:
        explicacion.append(f"No se detectaron anomalias en {zona} con los datos reales disponibles. El riesgo es bajo.")

    recomendaciones = []
    if nivel == "alto":
        if alerta_oficial_hoy:
            recomendaciones = [
                "Evitar la zona si es posible.",
                "Consultar canales oficiales de TransMilenio.",
                "Buscar rutas alternas.",
                "No asumir que es paro confirmado si la alerta solo indica cierre o desvios."
            ]
        else:
            recomendaciones = [
                "Evitar la zona si es posible.",
                "Buscar transporte alternativo.",
                "Seguir reportes oficiales de TransMilenio.",
                "Consultar rutas alternas en la app TransMiApp."
            ]
    elif nivel == "medio":
        recomendaciones = [
            "Revisar rutas alternas antes de salir.",
            "Consultar actualizaciones en tiempo real.",
            "Mantenerse informado por canales oficiales."
        ]
    else:
        recomendaciones = [
            "La movilidad parece normal en la zona.",
            "Puede continuar con su ruta habitual.",
            "Siempre consulte fuentes oficiales de TransMilenio."
        ]

    zone_info = get_zone_coords(zona)
    ubicacion_inteligente = {
        "zona_consultada": zona,
        "direccion_normalizada": zone_info["direccion_normalizada"] if zone_info else normalize_address(zona),
        "coordenadas_estimadas": {"lat": zone_info["lat"], "lon": zone_info["lon"]} if zone_info else {"lat": None, "lon": None},
        "buses_cercanos": buses.get("cantidad", 0),
        "reportes_cercanos": firebase.get("cantidad", 0),
        "alertas_historicas_cercanas": whatsapp.get("coincidencias", 0)
    }

    whatsapp_out = {
        "score": whatsapp["score"],
        "tipo_dato": whatsapp["tipo_dato"],
        "detalle": whatsapp["detalle"],
        "coincidencias": whatsapp["coincidencias"],
        "datos_usados": whatsapp["datos_usados"],
        "advertencia": whatsapp.get("advertencia"),
        "estado_evento": estado_evento if whatsapp_tipo == "real_hoy" else None,
        "ultimo_mensaje_oficial": whatsapp.get("ultimo_mensaje_oficial") if whatsapp_tipo == "real_hoy" else None,
    }
    if alerta_oficial_hoy:
        whatsapp_out["alertas_recientes"] = whatsapp.get("alertas_recientes", [])
        whatsapp_out["alerta_oficial_hoy"] = True

    return {
        "zona": zona,
        "probabilidad": prob,
        "nivel_riesgo": nivel,
        "score_ponderado": score_ponderado,
        "modo_operacion": "real",
        "datos_reales_usados": datos_reales_usados,
        "alerta_oficial_hoy": alerta_oficial_hoy and whatsapp_tipo == "real_hoy",
        "estado_evento": estado_evento if whatsapp_tipo == "real_hoy" else None,
        "ultimo_mensaje_oficial": whatsapp.get("ultimo_mensaje_oficial") if whatsapp_tipo == "real_hoy" else None,
        "fuentes_usadas": fuentes_usadas,
        "fuentes_no_disponibles": fuentes_no_disponibles,
        "fuentes": {
            "buses": {
                "score": buses["score"],
                "tipo_dato": buses["tipo_dato"],
                "detalle": buses["detalle"],
                "cantidad": buses["cantidad"],
                "datos_usados": buses["datos_usados"],
                "advertencia": buses["advertencia"]
            },
            "whatsapp_transmilenio": whatsapp_out,
            "firebase_reportes": {
                "score": firebase["score"],
                "tipo_dato": firebase["tipo_dato"],
                "detalle": firebase["detalle"],
                "cantidad": firebase["cantidad"],
                "datos_usados": firebase["datos_usados"],
                "advertencia": firebase["advertencia"]
            },
            "ia_texto": {
                "score": ia_texto["score"],
                "tipo_dato": ia_texto["tipo_dato"],
                "detalle": ia_texto["detalle"],
                "palabras_clave": ia_texto["palabras_clave"],
                "advertencia": ia_texto["advertencia"]
            }
        },
        "ubicacion_inteligente": ubicacion_inteligente,
        "explicacion": explicacion,
        "recomendaciones": recomendaciones,
        "debug": {
            "timestamp": datetime.now().isoformat(),
            "errores_fuentes": errores_fuentes
        }
    }


def get_fuentes_estado() -> Dict[str, Any]:
    estado = {}
    try:
        db = BusDatabase()
        estadisticas = db.estadisticas()
        captura = db.obtener_captura_actual()
        captura_real = [b for b in captura if not str(b.get("bus_id", "")).startswith("DEMO_") and not str(b.get("id", "")).startswith("DEMO_")]
        estado["buses"] = {
            "disponible": True,
            "registros": len(captura_real),
            "total_db": estadisticas.get("posiciones_capturadas", 0) or estadisticas.get("total_posiciones", 0),
            "detalle": f"Base de datos activa. {len(captura_real)} buses en captura actual."
        }
    except Exception as e:
        estado["buses"] = {
            "disponible": False,
            "registros": 0,
            "detalle": f"Error al leer base de datos de buses: {str(e)}"
        }
    try:
        whapi_ok = is_whapi_configured()
        whapi_config = get_whapi_config()
        csv_path = _get_tm_csv_path()
        csv_existe = os.path.exists(csv_path)
        alertas = load_alert_dataset(csv_path)

        modo_parts = []
        if whapi_ok:
            modo_parts.append("whapi_real")
        if csv_existe and alertas:
            modo_parts.append("csv_historico")

        modo = "+".join(modo_parts) if modo_parts else "sin_datos"
        registros = len(alertas) if alertas else 0

        if whapi_ok:
            detalle = f"Whapi configurado (canal: {whapi_config.get('channel_id', 'N/A')[:20]}...). "
        else:
            detalle = "Whapi no configurado. "

        if csv_existe and alertas:
            detalle += f"Dataset historico de TransMilenio encontrado con {len(alertas)} alertas."
        elif csv_existe:
            detalle += "Dataset historico encontrado pero vacio o ilegible."
        else:
            detalle += "No se encontro dataset historico de TransMilenio."

        estado["whatsapp_transmilenio"] = {
            "disponible": whapi_ok or (csv_existe and alertas),
            "modo": modo,
            "configuracion_whapi": {
                "configurado": whapi_ok,
                "mode": whapi_config.get("mode"),
                "channel_id": whapi_config.get("channel_id", "")[:20] + "..." if whapi_config.get("channel_id") else None,
                "base_url": whapi_config.get("base_url")
            },
            "registros": registros,
            "detalle": detalle
        }
    except Exception as e:
        estado["whatsapp_transmilenio"] = {
            "disponible": False,
            "modo": "error",
            "registros": 0,
            "detalle": f"Error al leer fuentes WhatsApp/TM: {str(e)}"
        }
    try:
        from firebase.client import get_all_reportes
        reportes = get_all_reportes()
        reales = [r for r in reportes if not str(r.get("id", "")).startswith("DEMO_") and not str(r.get("reporte_id", "")).startswith("DEMO_")]
        estado["firebase"] = {
            "disponible": True,
            "registros": len(reales),
            "detalle": f"Firebase configurado. {len(reales)} reportes reales encontrados."
        }
    except Exception as e:
        estado["firebase"] = {
            "disponible": False,
            "registros": 0,
            "detalle": f"Firebase no configurado o no disponible: {str(e)}"
        }
    try:
        estado["ia_texto"] = {
            "disponible": True,
            "detalle": "Analisis de texto por reglas experto activo."
        }
    except Exception as e:
        estado["ia_texto"] = {
            "disponible": False,
            "detalle": f"Error en modulo IA/texto: {str(e)}"
        }
    return estado
