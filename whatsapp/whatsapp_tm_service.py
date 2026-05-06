"""
Servicio WhatsApp/TransMilenio via Whapi.
Consulta mensajes recientes del canal oficial de TransMilenio y los cruza con zonas.
"""
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from zoneinfo import ZoneInfo
    COLOMBIA_TZ = ZoneInfo("America/Bogota")
except (ImportError, Exception):
    COLOMBIA_TZ = timezone(timedelta(hours=-5))


def normalize_text_simple(texto: str) -> str:
    if not texto:
        return ""
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^\w\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


ABREVIACIONES = {
    "av": "avenida",
    "cra": "carrera",
    "kr": "carrera",
    "cll": "calle",
    "cl": "calle",
    "u distrital": "universidad distrital",
    "u pedagogica": "universidad pedagogica",
}

PALABRAS_GENERICAS = {
    "universidad", "avenida", "portal", "calle", "carrera", "estacion",
    "con", "de", "la", "el", "del", "los", "las", "y", "en", "a", "para",
    "por", "sur", "norte", "oriente", "occidente", "paro", "hay", "que",
    "trash", "transmia", "riesgo", "alto", "medio", "bajo", "hoy", "movilidad"
}

PALABRAS_FUERTES_ZONA = {
    "caracas", "pedagogica", "pedagogico", "distrital", "eldorado",
    "macarena", "americas", "transmilenio", "transmizonal", "circunvalar",
    "chile", "julio", "nacional", "suba", "tunal", "usme", "banderas",
    "ricaurte", "nieves", "hortua", "aranda", "lucia", "victorino",
    "diego", "narino", "fucha", "mandalay",
}


def get_whapi_config() -> Dict[str, str]:
    return {
        "mode": os.environ.get("WHAPI_MODE", "").strip(),
        "token": os.environ.get("WHAPI_TOKEN", "").strip(),
        "base_url": os.environ.get("WHAPI_BASE_URL", "https://gate.whapi.cloud").strip(),
        "channel_id": os.environ.get("WHAPI_TRANSMILENIO_CHANNEL_ID", "").strip(),
    }


def is_whapi_configured() -> bool:
    c = get_whapi_config()
    return c["mode"] == "real" and bool(c["token"]) and bool(c["channel_id"])


def now_colombia() -> datetime:
    return datetime.now(COLOMBIA_TZ)


def is_today_colombia(timestamp_or_date) -> bool:
    try:
        if isinstance(timestamp_or_date, (int, float)):
            dt = datetime.fromtimestamp(timestamp_or_date, tz=COLOMBIA_TZ)
        elif isinstance(timestamp_or_date, datetime):
            if timestamp_or_date.tzinfo is None:
                dt = timestamp_or_date.replace(tzinfo=COLOMBIA_TZ)
            else:
                dt = timestamp_or_date.astimezone(COLOMBIA_TZ)
        elif isinstance(timestamp_or_date, str):
            s = timestamp_or_date.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(COLOMBIA_TZ)
        else:
            return False
        now = now_colombia()
        return dt.date() == now.date()
    except Exception:
        return False


def extract_text_from_whapi_message(message: Dict) -> str:
    if not message:
        return ""
    text_obj = message.get("text", {})
    if isinstance(text_obj, dict):
        body = text_obj.get("body", "")
        if body:
            return body
    if isinstance(text_obj, str) and text_obj:
        return text_obj
    image = message.get("image", {})
    if isinstance(image, dict):
        caption = image.get("caption", "")
        if caption:
            return caption
    video = message.get("video", {})
    if isinstance(video, dict):
        caption = video.get("caption", "")
        if caption:
            return caption
    document = message.get("document", {})
    if isinstance(document, dict):
        caption = document.get("caption", "")
        if caption:
            return caption
    return message.get("body", "") or message.get("content", "") or ""


def extract_datetime_from_whapi_message(message: Dict) -> Optional[datetime]:
    ts = message.get("timestamp")
    if ts:
        try:
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts, tz=COLOMBIA_TZ)
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace('Z', '+00:00').replace('z', '+00:00'))
                except Exception:
                    return datetime.fromtimestamp(float(ts), tz=COLOMBIA_TZ)
        except Exception:
            pass
    date_str = message.get("date") or message.get("datetime") or message.get("created_at")
    if isinstance(date_str, str):
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00').replace('z', '+00:00'))
        except Exception:
            pass
    return None


def detect_strong_tm_alert(texto: str) -> Dict[str, Any]:
    if not texto:
        return {"severidad": "baja", "palabras_detectadas": []}

    text = normalize_text_simple(texto)
    palabras_detectadas = []
    severidad = "baja"

    if any(phrase in text for phrase in ["se cierran estaciones", "cierran estaciones"]):
        palabras_detectadas.append("cierre_estaciones")
        severidad = "alta"
    if "sin operar" in text or "no opera" in text:
        palabras_detectadas.append("sin_operar")
        severidad = "alta"
    if any(phrase in text for phrase in ["cierre", "cerrada", "cerrado", "estacion cerrada", "portal cerrado"]):
        if "cierre" not in str(palabras_detectadas):
            palabras_detectadas.append("cierre")
        if severidad == "baja":
            severidad = "media_alta"
    if any(phrase in text for phrase in ["desvio", "desvios"]):
        palabras_detectadas.append("desvios")
        if severidad not in ("alta", "critica"):
            severidad = "media_alta"
    if any(phrase in text for phrase in ["bloqueo", "bloqueada", "bloqueado"]):
        palabras_detectadas.append("bloqueo")
        severidad = "alta"
    if any(phrase in text for phrase in ["manifestacion", "protesta", "manifestantes"]):
        palabras_detectadas.append("manifestacion")
        severidad = "alta"
    if "paro" in text:
        palabras_detectadas.append("paro")
        severidad = "alta"
    if "flota sin paso" in text:
        palabras_detectadas.append("flota_sin_paso")
        severidad = "alta"
    if "estaciones desde" in text:
        palabras_detectadas.append("cierre_parcial_troncal")
        severidad = "alta"
    if any(phrase in text for phrase in ["rutas de transmizonal", "transmizonal"]):
        palabras_detectadas.append("transmizonal")

    tiene_cierre = any(p in text for p in ["se cierran", "cierran", "cierre", "cerrada", "cerrado", "sin operar"])
    tiene_desvios = any(p in text for p in ["desvio", "desvios"])
    if tiene_cierre and tiene_desvios:
        severidad = "critica"

    return {"severidad": severidad, "palabras_detectadas": palabras_detectadas}


FRASES_ACTIVO = [
    "se cierran estaciones", "cierran estaciones", "cierre de estaciones",
    "estaciones sin operar", "sin operar", "no opera",
    "continuan los desvios", "continuan desvios", "desvios activos",
    "flota sin paso", "sin paso",
    "manifestacion", "protesta", "bloqueo",
    "afectacion al servicio", "troncal cerrada", "paso restringido",
]

FRASES_RESTABLECIDO = [
    "restablecimiento del servicio",
    "se cancelan los desvios", "cancelamos los desvios",
    "se levantan los desvios",
    "retoman su recorrido habitual", "retoman sus recorridos habituales",
    "comienzan a retomar sus recorridos habituales",
    "retoman operacion", "retoma operacion",
    "retoman su operacion habitual",
    "servicios duales y transmizonal retoman su recorrido habitual",
    "la flota retoma su recorrido",
    "la flota troncal retoma su operacion",
    "estaciones retoman operacion",
    "se normaliza la operacion", "normalizacion",
    "operacion habitual", "recorrido habitual",
    "cancelan los desvios para el componente",
]

FRASES_PARCIAL = [
    "operacion parcial",
    "algunos servicios retoman",
    "continuan retrasos", "congestion residual",
    "operacion intermitente",
    "servicios con retraso",
]


def classify_event_state(texto: str) -> str:
    if not texto:
        return "sin_alerta_hoy"
    text = normalize_text_simple(texto)
    for frase in FRASES_RESTABLECIDO:
        if normalize_text_simple(frase) in text:
            return "restablecido"
    for frase in FRASES_ACTIVO:
        if normalize_text_simple(frase) in text:
            return "activo"
    for frase in FRASES_PARCIAL:
        if normalize_text_simple(frase) in text:
            return "parcial"
    return "sin_alerta_hoy"


STATE_SCORES = {
    "activo": 100,
    "parcial": 40,
    "restablecido": 15,
    "sin_alerta_hoy": 0,
}

STATE_NIVELES = {
    "activo": "alto",
    "parcial": "medio",
    "restablecido": "bajo",
    "sin_alerta_hoy": "bajo",
}


def matches_zone(texto: str, zona: str) -> bool:
    if not texto or not zona:
        return False

    text_norm = normalize_text_simple(texto)
    zona_norm = normalize_text_simple(zona)

    if zona_norm in text_norm:
        return True
    if text_norm in zona_norm:
        return True

    text_words = set(text_norm.split())
    for abbr, full in ABREVIACIONES.items():
        if abbr and full:
            abbr_norm = normalize_text_simple(abbr)
            full_norm = normalize_text_simple(full)
            abbr_words = set(abbr_norm.split())
            if abbr_words.issubset(text_words):
                text_words = text_words.difference(abbr_words)
                text_words.update(full_norm.split())

    text_expanded = " ".join(sorted(text_words))
    if zona_norm in text_expanded:
        return True

    is_route = bool(re.match(r'^[A-Za-z]{1,3}\d{1,4}$', zona.strip()))
    if is_route:
        route_pattern = re.compile(r'\b' + re.escape(zona.strip().upper()) + r'\b', re.IGNORECASE)
        if route_pattern.search(texto):
            return True
        return False

    zona_words_full = set(zona_norm.split())
    meaningful_zona = {w for w in zona_words_full if len(w) > 3 and w not in PALABRAS_GENERICAS}
    meaningful_text = {w for w in text_words if len(w) > 3 and w not in PALABRAS_GENERICAS}

    overlap = meaningful_zona & meaningful_text
    if len(overlap) >= 2:
        return True
    if len(overlap) >= 1 and len(meaningful_zona) == 1:
        return True

    fuertes_zona = {w for w in zona_words_full if w in PALABRAS_FUERTES_ZONA}
    fuertes_text = {w for w in text_words if w in PALABRAS_FUERTES_ZONA}
    if fuertes_zona & fuertes_text:
        return True

    return False


def parse_tm_alert(texto: str) -> Dict:
    try:
        from src.ia.tm_alert_parser import TMAlertParserService
        parser = TMAlertParserService()
        return parser.parse_tm_alert(texto)
    except Exception:
        ubicacion = None
        return {
            "ubicacion": ubicacion,
            "ubicacion_normalizada": ubicacion,
            "tipo_evento": "Novedad operacional",
            "causa": "Novedad operacional",
            "texto_original": texto,
        }


def get_tm_whatsapp_messages(count: int = 50) -> Dict[str, Any]:
    config = get_whapi_config()
    fecha_hoy = now_colombia().strftime("%Y-%m-%d")

    if config["mode"] != "real" or not config["token"] or not config["channel_id"]:
        return {
            "status": "sin_configuracion",
            "modo": config["mode"] if config["mode"] else "no_definido",
            "advertencia": "Whapi no esta configurado. Variables .env requeridas: WHAPI_MODE=real, WHAPI_TOKEN, WHAPI_TRANSMILENIO_CHANNEL_ID.",
            "mensajes": [],
            "fecha_colombia": fecha_hoy
        }

    base_url = config["base_url"].rstrip('/')
    channel_id = config["channel_id"]
    token = config["token"]

    url = f"{base_url}/messages/list/{channel_id}"

    try:
        import requests
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            },
            params={"count": count},
            timeout=15
        )

        if resp.status_code != 200:
            return {
                "status": "error",
                "modo": "real",
                "advertencia": f"Whapi respondio HTTP {resp.status_code}: {resp.text[:200]}",
                "mensajes": [],
                "fecha_colombia": fecha_hoy
            }

        data = resp.json()
        messages_raw = data.get("messages") or data.get("data") or []

        mensajes = []
        for msg in messages_raw:
            texto = extract_text_from_whapi_message(msg)
            ts = extract_datetime_from_whapi_message(msg)
            fecha_col = None
            hora_col = None
            es_hoy = False

            if ts:
                if isinstance(ts, datetime):
                    fecha_col = ts.strftime("%Y-%m-%d")
                    hora_col = ts.strftime("%H:%M:%S")
                    es_hoy = is_today_colombia(ts)

            ubicacion_detectada = None
            if texto:
                alerta = parse_tm_alert(texto)
                ubicacion_detectada = alerta.get("ubicacion_normalizada") or alerta.get("ubicacion")

            severidad_info = detect_strong_tm_alert(texto)

            mensajes.append({
                "message_id": str(msg.get("id") or msg.get("message_id") or ts or ""),
                "texto": texto,
                "timestamp_original": msg.get("timestamp"),
                "fecha_colombia": fecha_col,
                "hora_colombia": hora_col,
                "es_hoy": es_hoy,
                "ubicacion_detectada": ubicacion_detectada,
                "severidad": severidad_info.get("severidad", "baja"),
                "palabras_fuertes": severidad_info.get("palabras_detectadas", []),
                "raw": None
            })

        return {
            "status": "ok",
            "modo": "real",
            "mensajes": mensajes,
            "fecha_colombia": fecha_hoy,
            "advertencia": None
        }
    except ImportError:
        return {
            "status": "error",
            "modo": "real",
            "advertencia": "Libreria 'requests' no disponible. Instalar: pip install requests",
            "mensajes": [],
            "fecha_colombia": fecha_hoy
        }
    except Exception as e:
        err_msg = str(e)
        if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            err_msg = "Timeout al consultar Whapi."
        return {
            "status": "error",
            "modo": "real",
            "advertencia": f"Error al consultar Whapi: {err_msg}",
            "mensajes": [],
            "fecha_colombia": fecha_hoy
        }


def find_recent_alerts_for_zone(zona: str, count: int = 50) -> Dict[str, Any]:
    result = get_tm_whatsapp_messages(count=count)
    mensajes = result.get("mensajes", [])

    alertas_hoy = []
    for msg in mensajes:
        if msg.get("es_hoy"):
            texto = msg.get("texto", "")
            ubicacion = msg.get("ubicacion_detectada", "")
            if matches_zone(texto, zona) or matches_zone(ubicacion, zona):
                alertas_hoy.append(msg)

    alertas_hoy.sort(key=lambda m: m.get("hora_colombia") or "00:00:00")

    estado_evento = "sin_alerta_hoy"
    ultimo_mensaje = None
    if alertas_hoy:
        ultimo = alertas_hoy[-1]
        estado_evento = classify_event_state(ultimo.get("texto", ""))
        ultimo_mensaje = {
            "message_id": ultimo.get("message_id"),
            "texto": ultimo.get("texto", "")[:300],
            "hora_colombia": ultimo.get("hora_colombia"),
            "estado_detectado": estado_evento,
        }

    severidad_orden = {"critica": 4, "alta": 3, "media_alta": 2, "media": 1, "baja": 0}
    max_sev = "baja"
    for a in alertas_hoy:
        s = a.get("severidad", "baja")
        if severidad_orden.get(s, 0) > severidad_orden.get(max_sev, 0):
            max_sev = s

    return {
        "status": result.get("status"),
        "modo": result.get("modo"),
        "advertencia": result.get("advertencia"),
        "total_mensajes": len(mensajes),
        "alertas_hoy_para_zona": alertas_hoy,
        "hay_alerta_oficial_hoy": len(alertas_hoy) > 0,
        "severidad_maxima": max_sev if alertas_hoy else None,
        "fecha_colombia": result.get("fecha_colombia"),
        "estado_evento": estado_evento,
        "ultimo_mensaje_oficial": ultimo_mensaje,
    }
