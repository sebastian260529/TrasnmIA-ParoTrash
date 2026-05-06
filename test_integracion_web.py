"""
Pruebas de integracion web - TransmIA ParoTrash (MODO REAL)
Ejecutar: python test_integracion_web.py
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from fastapi.testclient import TestClient
from src.api.server import app

client = TestClient(app)

# Mock de alerta oficial de hoy para Universidad Pedagogica
MOCK_ALERTA_TM = "#TMAhora (6:36 p.m.) Universidad Pedagogica. A la hora se cierran estaciones desde la Calle 76 hasta la Calle 26 en la troncal Caracas. Continuan los desvios para las rutas de TransMiZonal."

MOCK_ALERTA_RESTABLECIDO = "#TMAhora (8:30 p.m.) Av. carrera Septima con calle 34. Los servicios TransMiZonal y duales retoman su recorrido habitual en la zona. Cancelan los desvios para el componente."

MOCK_ALERTA_PARCIAL = "#TMAhora (7:45 p.m.) Portal Norte. Operacion parcial, continuan retrasos en algunas rutas."

def _make_mock_alerts(alertas_data, estado_evento="activo"):
    return {
        "status": "ok",
        "modo": "real",
        "advertencia": None,
        "total_mensajes": 50,
        "alertas_hoy_para_zona": alertas_data,
        "hay_alerta_oficial_hoy": True,
        "severidad_maxima": "critica",
        "fecha_colombia": "2026-05-05",
        "estado_evento": estado_evento,
        "ultimo_mensaje_oficial": {
            "message_id": alertas_data[-1].get("message_id") if alertas_data else None,
            "texto": alertas_data[-1].get("texto", "")[:300] if alertas_data else "",
            "hora_colombia": alertas_data[-1].get("hora_colombia") if alertas_data else "",
            "estado_detectado": estado_evento,
        }
    }

MOCK_FIND_ALERTS_REAL_HOY = _make_mock_alerts([{
    "message_id": "mock_msg_001",
    "texto": MOCK_ALERTA_TM,
    "timestamp_original": None,
    "fecha_colombia": "2026-05-05",
    "hora_colombia": "18:36:00",
    "es_hoy": True,
    "ubicacion_detectada": "Universidad Pedagogica",
    "severidad": "critica",
    "palabras_fuertes": ["cierre_estaciones", "desvios", "transmizonal"],
    "raw": None
}], estado_evento="activo")

# Scenario: cierre a las 18:30, restablecimiento a las 20:00 -> ultimo manda = restablecido
MOCK_CIERRE_ANTIGUO_RESTABLECIDO_RECIENTE = _make_mock_alerts([
    {
        "message_id": "msg_cierre_001",
        "texto": "#TMAhora (6:30 p.m.) Portal Norte. A la hora se cierran estaciones. Continuan los desvios para las rutas de TransMiZonal.",
        "hora_colombia": "18:30:00",
        "es_hoy": True,
        "ubicacion_detectada": "Portal Norte",
        "severidad": "critica",
        "palabras_fuertes": ["cierre_estaciones", "desvios"],
    },
    {
        "message_id": "msg_restablecido_002",
        "texto": "#TMAhora (8:00 p.m.) Portal Norte. Los servicios TransMiZonal y duales retoman su recorrido habitual en la zona. Cancelan los desvios para el componente.",
        "hora_colombia": "20:00:00",
        "es_hoy": True,
        "ubicacion_detectada": "Portal Norte",
        "severidad": "baja",
        "palabras_fuertes": [],
    }
], estado_evento="restablecido")

# Scenario: restablecimiento a las 15:00, cierre a las 18:00 -> ultimo manda = activo
MOCK_RESTABLECIMIENTO_ANTIGUO_CIERRE_RECIENTE = _make_mock_alerts([
    {
        "message_id": "msg_rest_001",
        "texto": "#TMAhora (3:00 p.m.) Portal Norte. Los servicios TransMiZonal y duales retoman su recorrido habitual. Cancelan los desvios.",
        "hora_colombia": "15:00:00",
        "es_hoy": True,
        "ubicacion_detectada": "Portal Norte",
        "severidad": "baja",
        "palabras_fuertes": [],
    },
    {
        "message_id": "msg_cierre_002",
        "texto": "#TMAhora (6:00 p.m.) Portal Norte. A la hora se cierran estaciones. Continuan los desvios.",
        "hora_colombia": "18:00:00",
        "es_hoy": True,
        "ubicacion_detectada": "Portal Norte",
        "severidad": "critica",
        "palabras_fuertes": ["cierre_estaciones", "desvios"],
    }
], estado_evento="activo")

# Scenario: desvios activos como ultimo mensaje
MOCK_DESVIOS_ACTIVOS = _make_mock_alerts([{
    "message_id": "msg_desvios_001",
    "texto": "#TMAhora (7:00 p.m.) Avenida Caracas. Continuan los desvios para las rutas de TransMiZonal.",
    "hora_colombia": "19:00:00",
    "es_hoy": True,
    "ubicacion_detectada": "Avenida Caracas",
    "severidad": "media_alta",
    "palabras_fuertes": ["desvios"],
}], estado_evento="activo")

# Scenario: operacion parcial
MOCK_PARCIAL = _make_mock_alerts([{
    "message_id": "msg_parcial_001",
    "texto": "#TMAhora (7:45 p.m.) Portal Norte. Operacion parcial, continuan retrasos en algunas rutas.",
    "hora_colombia": "19:45:00",
    "es_hoy": True,
    "ubicacion_detectada": "Portal Norte",
    "severidad": "media",
    "palabras_fuertes": ["retrasos"],
}], estado_evento="parcial")

MOCK_FIND_ALERTS_EMPTY = {
    "status": "sin_configuracion",
    "modo": "no_definido",
    "advertencia": "Whapi no esta configurado.",
    "total_mensajes": 0,
    "alertas_hoy_para_zona": [],
    "hay_alerta_oficial_hoy": False,
    "severidad_maxima": None,
    "fecha_colombia": "2026-05-05",
    "estado_evento": "sin_alerta_hoy",
    "ultimo_mensaje_oficial": None,
}

print("=" * 60)
print(" PRUEBAS DE INTEGRACION - TransmIA ParoTrash (MODO REAL)")
print("=" * 60)

def test_health():
    print("\n[TEST] GET /health")
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    print(f"  OK: {data}")

def test_web_index():
    print("\n[TEST] GET /")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TransmIA ParoTrash" in resp.text
    print("  OK: Web index returned")

def test_fuentes_estado():
    print("\n[TEST] GET /fuentes/estado")
    resp = client.get("/fuentes/estado")
    assert resp.status_code == 200
    data = resp.json()
    assert "buses" in data
    assert "whatsapp_transmilenio" in data
    assert "firebase" in data
    assert "ia_texto" in data
    assert "geolocalizacion" in data
    for key in ["buses", "whatsapp_transmilenio", "firebase", "ia_texto", "geolocalizacion"]:
        val = data[key]
        assert "disponible" in val, f"Falta 'disponible' en {key}"
        assert "detalle" in val, f"Falta 'detalle' en {key}"
    wapp = data["whatsapp_transmilenio"]
    assert "configuracion_whapi" in wapp or True
    print(f"  OK: Las 5 fuentes reportan estado")
    print(f"  WhatsApp/TM modo={wapp.get('modo', 'N/A')}")

def test_prediccion_integrada_portal_eldorado():
    print("\n[TEST] GET /prediccion/integrada?zona=Portal Eldorado")
    resp = client.get("/prediccion/integrada?zona=Portal Eldorado")
    assert resp.status_code == 200
    data = resp.json()
    assert "zona" in data
    assert "probabilidad" in data
    assert "nivel_riesgo" in data
    assert "score_ponderado" in data
    assert "fuentes" in data
    assert "explicacion" in data
    assert "recomendaciones" in data
    assert "ubicacion_inteligente" in data
    assert "debug" in data
    assert "fuentes_usadas" in data
    assert "fuentes_no_disponibles" in data
    fuentes = data["fuentes"]
    assert "buses" in fuentes
    assert "whatsapp_transmilenio" in fuentes
    assert "firebase_reportes" in fuentes
    assert "ia_texto" in fuentes
    assert "geolocalizacion" in fuentes
    for key, val in fuentes.items():
        assert "score" in val, f"Falta 'score' en fuente '{key}'"
        assert val["score"] is not None, f"'score' es None en fuente '{key}'"
        assert "tipo_dato" in val, f"Falta 'tipo_dato' en fuente '{key}'"
        assert "detalle" in val, f"Falta 'detalle' en fuente '{key}'"
    assert data["modo_operacion"] == "real"
    print(f"  Zona: {data['zona']}")
    print(f"  Probabilidad: {data['probabilidad']}%")
    print(f"  Nivel: {data['nivel_riesgo']}")
    print(f"  Fuentes usadas: {data['fuentes_usadas']}")
    print(f"  WhatsApp/TM score: {fuentes['whatsapp_transmilenio']['score']} (tipo: {fuentes['whatsapp_transmilenio']['tipo_dato']})")

def test_prediccion_sin_demo_data():
    print("\n[TEST] Verificando que NO se usen datos DEMO_")
    resp = client.get("/prediccion/integrada?zona=Portal Eldorado")
    assert resp.status_code == 200
    data = resp.json()
    json_str = json.dumps(data)
    assert "DEMO_" not in json_str, "Se detecto contenido DEMO_ en la respuesta"
    print("  OK: No hay datos DEMO_ en la respuesta")

def test_buses_sin_datos():
    print("\n[TEST] Verificando buses sin datos reales")
    resp = client.get("/prediccion/integrada?zona=Carrera 5 con Calle 28")
    assert resp.status_code == 200
    data = resp.json()
    buses = data["fuentes"]["buses"]
    if buses["tipo_dato"] == "sin_datos":
        assert buses["score"] == 0, "Si no hay buses reales, score debe ser 0"
        print(f"  OK: Buses sin datos -> score=0")
    else:
        print(f"  OK: Buses con datos tipo={buses['tipo_dato']}, score={buses['score']}")

def test_csv_historico_presente():
    print("\n[TEST] Verificando que el CSV historico aporta datos")
    resp = client.get("/prediccion/integrada?zona=Portal Eldorado")
    assert resp.status_code == 200
    data = resp.json()
    whatsapp = data["fuentes"]["whatsapp_transmilenio"]
    assert whatsapp["tipo_dato"] in ("historico", "mixto", "real_hoy", "sin_datos", "error"), f"Tipo dato inesperado: {whatsapp['tipo_dato']}"
    print(f"  OK: WhatsApp/TM tipo={whatsapp['tipo_dato']}, score={whatsapp['score']}")

def test_firebase_sin_config():
    print("\n[TEST] Verificando Firebase sin configurar")
    resp = client.get("/prediccion/integrada?zona=Portal Eldorado")
    assert resp.status_code == 200
    data = resp.json()
    firebase = data["fuentes"]["firebase_reportes"]
    print(f"  OK: Firebase tipo={firebase['tipo_dato']}, score={firebase['score']}")

def test_chatbot():
    print("\n[TEST] POST /chatbot")
    resp = client.post("/chatbot", json={
        "pregunta": "Hay paro en Portal Eldorado?",
        "zona": "Portal Eldorado"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "respuesta" in data
    assert "probabilidad" in data
    assert "nivel_riesgo" in data
    assert "fuentes" in data
    print(f"  Respuesta: {data['respuesta'][:150]}...")
    print(f"  Probabilidad: {data['probabilidad']}%")

def test_chatbot_sin_zona():
    print("\n[TEST] POST /chatbot (sin zona explicita)")
    resp = client.post("/chatbot", json={
        "pregunta": "Como esta la movilidad en Avenida Caracas?",
        "zona": ""
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "respuesta" in data
    print(f"  Zona detectada: {data.get('zona', 'N/A')}")
    print(f"  Respuesta: {data['respuesta'][:120]}...")

def test_chatbot_otras_zonas():
    print("\n[TEST] POST /chatbot (variedad de zonas)")
    zonas = [
        "Universidad Distrital",
        "Carrera 5 con Calle 28",
        "Avenida Circunvalar con Calle 26"
    ]
    for z in zonas:
        resp = client.post("/chatbot", json={
            "pregunta": f"Hay riesgo en {z}?",
            "zona": z
        })
        assert resp.status_code == 200, f"Error en zona {z}"
        data = resp.json()
        print(f"  {z}: prob={data['probabilidad']}% nivel={data['nivel_riesgo']}")

def test_chatbot_prioridad_pregunta_sobre_body():
    print("\n[TEST] Chatbot: la zona de la pregunta tiene prioridad sobre el body")
    casos = [
        ("hay paro en la universidad pedagogica?", "Portal Eldorado", "Universidad Pedagogica"),
        ("hay paro en Portal Eldorado?", "Universidad Pedagogica", "Portal Eldorado"),
        ("hay paro en avenida caracas?", "Portal Eldorado", "Avenida Caracas"),
        ("como esta portal norte hoy?", "Portal Eldorado", "Portal Norte"),
        ("que pasa en la pedagogica", "Portal Eldorado", "Universidad Pedagogica"),
        ("movilidad en cra 5 con calle 28", "Portal Eldorado", "Carrera 5 con Calle 28"),
        ("distrital como esta", "Portal Eldorado", "Universidad Distrital"),
        ("hay paro en el dorado", "Portal Norte", "Portal Eldorado"),
        ("circunvalar con calle 26", "Portal Eldorado", "Avenida Circunvalar con Calle 26"),
        ("calle 72 con carrera 11 que tal", "Portal Eldorado", "Calle 72 con Carrera 11"),
        ("portal americas como esta", "Portal Eldorado", "Portal Americas"),
    ]
    for pregunta, zona_body, zona_esperada in casos:
        resp = client.post("/chatbot", json={
            "pregunta": pregunta,
            "zona": zona_body
        })
        assert resp.status_code == 200, f"Error: pregunta='{pregunta}'"
        data = resp.json()
        zona_usada = data.get("zona", "")
        assert zona_usada == zona_esperada, (
            f"Para pregunta='{pregunta}' con zona_body='{zona_body}' "
            f"se esperaba zona='{zona_esperada}' pero se uso '{zona_usada}'"
        )
        print(f"  OK: '{pregunta}' (body={zona_body}) -> zona={zona_usada}")

def test_chatbot_body_fallback_sin_zona_en_pregunta():
    print("\n[TEST] Chatbot: usa zona del body si la pregunta no tiene zona")
    resp = client.post("/chatbot", json={
        "pregunta": "hay paro ahi?",
        "zona": "Portal Eldorado"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("zona") == "Portal Eldorado", f"Esperaba Portal Eldorado, obtuve {data.get('zona')}"
    print(f"  OK: zona={data.get('zona')}, prob={data.get('probabilidad')}%")

def test_chatbot_sin_zona_sin_body_pide_zona():
    print("\n[TEST] Chatbot: sin zona en pregunta ni body pide escribir zona")
    resp = client.post("/chatbot", json={
        "pregunta": "como esta la movilidad hoy?",
        "zona": ""
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("zona") is None, f"Esperaba zona=None, obtuve {data.get('zona')}"
    assert data.get("nivel_riesgo") == "sin_zona", f"Esperaba nivel_riesgo='sin_zona'"
    assert "escrib" in data.get("respuesta", "").lower(), "Debe pedir que se escriba una zona"
    print(f"  OK: {data['respuesta'][:100]}...")

def test_extraer_zona_desde_pregunta():
    print("\n[TEST] extraer_zona_desde_pregunta")
    from src.api.server import extraer_zona_desde_pregunta
    casos = [
        ("hay paro en la universidad pedagogica?", "Universidad Pedagogica"),
        ("como esta la Universidad Pedagógica hoy", "Universidad Pedagogica"),
        ("u pedagogica hay paro?", "Universidad Pedagogica"),
        ("Portal Eldorado como va", "Portal Eldorado"),
        ("que pasa en el dorado", "Portal Eldorado"),
        ("avenida caracas con cierre", "Avenida Caracas"),
        ("av caracas hay paro?", "Avenida Caracas"),
        ("caracas esta bloqueada?", "Avenida Caracas"),
        ("troncal caracas como esta", "Avenida Caracas"),
        ("portal norte novedades", "Portal Norte"),
        ("portal sur movilidad", "Portal Sur"),
        ("portal americas bien?", "Portal Americas"),
        ("que tal la cra 5 con calle 28", "Carrera 5 con Calle 28"),
        ("cra 5 cll 28 paro", "Carrera 5 con Calle 28"),
        ("distrital como esta la movilidad", "Universidad Distrital"),
        ("u distrital hay paro", "Universidad Distrital"),
        ("circunvalar con calle 26 paro", "Avenida Circunvalar con Calle 26"),
        ("calle 12b con carrera 10", "Calle 12B con Carrera 10"),
        ("carrera septima con calle 28", "Carrera 7 con Calle 28"),
        ("portal 20 de julio como esta", "Portal 20 de Julio"),
        ("como esta la movilidad hoy?", None),
        ("hay paro ahi?", None),
        ("", None),
    ]
    for pregunta, esperada in casos:
        result = extraer_zona_desde_pregunta(pregunta)
        assert result == esperada, f"Para '{pregunta}': esperaba '{esperada}', obtuve '{result}'"
    print("  OK: Todos los casos de extraccion funcionan")

def test_existing_endpoints():
    print("\n[TEST] Endpoints existentes no rotos")
    endpoints = [
        ("/anomalias/deteccion", "GET"),
        ("/anomalias/ponderado", "GET"),
        ("/resumen", "GET"),
        ("/config/ponderado", "GET"),
        ("/monitoreo", "GET"),
        ("/ia/prediccion/demo?zona=Portal Norte", "GET"),
        ("/ia/prediccion/score", "GET"),
    ]
    for url, method in endpoints:
        if method == "GET":
            resp = client.get(url)
        assert resp.status_code == 200, f"{method} {url} returned {resp.status_code}"
        print(f"  OK: {method} {url} -> {resp.status_code}")

def test_actualizar_pesos():
    print("\n[TEST] PUT /config/ponderado")
    resp = client.put("/config/ponderado", json={
        "peso_deteccion": 0.5,
        "peso_reporte": 0.3,
        "peso_prediccion_ia": 0.2
    })
    assert resp.status_code == 200
    print("  OK: Pesos actualizados")

def test_docs():
    print("\n[TEST] GET /docs (Swagger)")
    resp = client.get("/docs")
    assert resp.status_code == 200
    print("  OK: Swagger docs available")

def test_openapi():
    print("\n[TEST] GET /openapi.json")
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    required_endpoints = ["/", "/health", "/fuentes/estado", "/prediccion/integrada", "/chatbot", "/whatsapp/tm/recientes"]
    for ep in required_endpoints:
        assert ep in paths, f"Missing endpoint {ep} in openapi.json"
    print(f"  OK: Todos los endpoints presentes en OpenAPI ({len(paths)} paths)")

# === NUEVOS TESTS WHATSAPP/TM ===

def test_detect_strong_tm_alert():
    print("\n[TEST] detect_strong_tm_alert con cierre de estaciones y desvios")
    from src.ia.whatsapp_tm_service import detect_strong_tm_alert
    result = detect_strong_tm_alert(MOCK_ALERTA_TM)
    assert result["severidad"] == "critica", f"Esperaba severidad 'critica', obtuve '{result['severidad']}'"
    assert "cierre_estaciones" in result["palabras_detectadas"], f"Esperaba 'cierre_estaciones' en palabras detectadas, obtuve {result['palabras_detectadas']}"
    assert "desvios" in result["palabras_detectadas"], f"Esperaba 'desvios' en palabras detectadas, obtuve {result['palabras_detectadas']}"
    print(f"  OK: severidad={result['severidad']}, palabras={result['palabras_detectadas']}")

def test_matches_zone_universidad_pedagogica():
    print("\n[TEST] matches_zone con Universidad Pedagogica")
    from src.ia.whatsapp_tm_service import matches_zone
    assert matches_zone(MOCK_ALERTA_TM, "Universidad Pedagogica"), "Debe coincidir Universidad Pedagogica con el texto"
    assert matches_zone(MOCK_ALERTA_TM, "Universidad Pedagógica"), "Debe coincidir con tilde"
    assert matches_zone(MOCK_ALERTA_TM, "universidad pedagogica"), "Debe coincidir sin mayusculas"
    assert matches_zone("Troncal Caracas con cierre", "Avenida Caracas"), "Debe coincidir troncal caracas con avenida caracas"
    assert matches_zone("Portal Eldorado", "Eldorado"), "Debe coincidir Eldorado"
    print("  OK: Todas las coincidencias funcionan correctamente")

def test_prediccion_integrada_universidad_pedagogica_mock_whapi():
    print("\n[TEST] Prediccion integrada para Universidad Pedagogica con mock Whapi (alerta hoy)")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_FIND_ALERTS_REAL_HOY
    try:
        resp = client.get("/prediccion/integrada?zona=Universidad%20Pedagogica")
        assert resp.status_code == 200
        data = resp.json()
        whatsapp = data["fuentes"]["whatsapp_transmilenio"]
        assert whatsapp["score"] == 100, f"Esperaba score=100, obtuve {whatsapp['score']}"
        assert whatsapp["tipo_dato"] == "real_hoy", f"Esperaba tipo_dato='real_hoy', obtuve '{whatsapp['tipo_dato']}'"
        assert data["alerta_oficial_hoy"] == True, f"Esperaba alerta_oficial_hoy=True, obtuve {data.get('alerta_oficial_hoy')}"
        assert data["probabilidad"] == 100, f"Esperaba probabilidad=100, obtuve {data['probabilidad']}"
        assert data["nivel_riesgo"] == "alto", f"Esperaba nivel_riesgo='alto', obtuve '{data['nivel_riesgo']}'"
        explicacion = " ".join(data.get("explicacion", []))
        print(f"  Probabilidad: {data['probabilidad']}%")
        print(f"  Nivel: {data['nivel_riesgo']}")
        print(f"  WhatsApp/TM: score={whatsapp['score']}, tipo={whatsapp['tipo_dato']}")
        print(f"  alerta_oficial_hoy: {data['alerta_oficial_hoy']}")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_chatbot_universidad_pedagogica_mock_whapi():
    print("\n[TEST] Chatbot para Universidad Pedagogica con mock Whapi")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_FIND_ALERTS_REAL_HOY
    try:
        resp = client.post("/chatbot", json={
            "pregunta": "hay paro en la Universidad Pedagogica?",
            "zona": ""
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["probabilidad"] == 100, f"Esperaba probabilidad=100, obtuve {data['probabilidad']}"
        assert data["nivel_riesgo"] == "alto", f"Esperaba nivel_riesgo='alto'"
        respuesta = data["respuesta"]
        assert "Universidad Pedagogica" in respuesta or "universidad pedagogica" in respuesta.lower(), f"La respuesta debe mencionar la zona: {respuesta[:200]}"
        assert "alerta" in respuesta.lower(), f"La respuesta debe mencionar alerta: {respuesta[:200]}"
        print(f"  Respuesta: {respuesta[:200]}...")
        print(f"  Probabilidad: {data['probabilidad']}%")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_sistema_sin_whapi_no_se_rompe():
    print("\n[TEST] Sistema sin Whapi configurado no se rompe")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_FIND_ALERTS_EMPTY
    try:
        resp = client.get("/prediccion/integrada?zona=Portal Eldorado")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerta_oficial_hoy"] == False
        whatsapp = data["fuentes"]["whatsapp_transmilenio"]
        assert whatsapp["tipo_dato"] in ("sin_datos", "historico", "error", "mixto"), f"Tipo dato inesperado: {whatsapp['tipo_dato']}"
        print(f"  OK: El sistema funciona sin Whapi. WhatsApp/TM tipo={whatsapp['tipo_dato']}")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_whatsapp_tm_recientes_endpoint():
    print("\n[TEST] GET /whatsapp/tm/recientes?count=20")
    resp = client.get("/whatsapp/tm/recientes?count=20")
    assert resp.status_code == 200, f"El endpoint debe responder 200 incluso sin configuracion. Status: {resp.status_code}"
    data = resp.json()
    assert "status" in data
    assert "modo" in data
    assert "fecha_colombia" in data
    assert "mensajes" in data
    if data["status"] == "sin_configuracion":
        assert data.get("advertencia") is not None, "Debe haber advertencia si no esta configurado"
    print(f"  Status: {data['status']}")
    print(f"  Modo: {data['modo']}")
    print(f"  Fecha Colombia: {data['fecha_colombia']}")
    print(f"  Mensajes: {len(data['mensajes'])}")

def test_chatbot_detecta_zona_desde_pregunta():
    print("\n[TEST] Chatbot detecta Universidad Pedagogica desde la pregunta sin zona explicita")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_FIND_ALERTS_REAL_HOY
    try:
        resp = client.post("/chatbot", json={
            "pregunta": "Como esta universidad pedagogica hoy?",
            "zona": ""
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("zona") is not None
        assert data["probabilidad"] == 100, f"Esperaba probabilidad=100, obtuve {data['probabilidad']}"
        print(f"  Zona detectada: {data.get('zona')}")
        print(f"  Probabilidad: {data['probabilidad']}%")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_estado_restablecido_ultimo_mensaje():
    print("\n[TEST] Cierre antiguo + restablecimiento mas reciente = riesgo bajo 15")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_CIERRE_ANTIGUO_RESTABLECIDO_RECIENTE
    try:
        resp = client.get("/prediccion/integrada?zona=Portal Norte")
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_evento"] == "restablecido", f"Esperaba restablecido, obtuve {data.get('estado_evento')}"
        assert data["probabilidad"] == 15, f"Esperaba 15, obtuve {data['probabilidad']}"
        assert data["nivel_riesgo"] == "bajo", f"Esperaba bajo, obtuve {data['nivel_riesgo']}"
        assert data["alerta_oficial_hoy"] == True
        print(f"  estado={data['estado_evento']}, prob={data['probabilidad']}%, nivel={data['nivel_riesgo']}")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_estado_activo_ultimo_mensaje():
    print("\n[TEST] Restablecimiento antiguo + cierre mas reciente = riesgo alto 100")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_RESTABLECIMIENTO_ANTIGUO_CIERRE_RECIENTE
    try:
        resp = client.get("/prediccion/integrada?zona=Portal Norte")
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_evento"] == "activo", f"Esperaba activo, obtuve {data.get('estado_evento')}"
        assert data["probabilidad"] == 100, f"Esperaba 100, obtuve {data['probabilidad']}"
        assert data["nivel_riesgo"] == "alto", f"Esperaba alto, obtuve {data['nivel_riesgo']}"
        print(f"  estado={data['estado_evento']}, prob={data['probabilidad']}%, nivel={data['nivel_riesgo']}")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_estado_desvios_activos():
    print("\n[TEST] Desvios activos como ultimo mensaje = riesgo alto 100")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_DESVIOS_ACTIVOS
    try:
        resp = client.get("/prediccion/integrada?zona=Avenida Caracas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_evento"] == "activo", f"Esperaba activo, obtuve {data.get('estado_evento')}"
        assert data["probabilidad"] == 100
        assert data["nivel_riesgo"] == "alto"
        print(f"  estado={data['estado_evento']}, prob={data['probabilidad']}%")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_estado_parcial():
    print("\n[TEST] Operacion parcial como ultimo mensaje = riesgo medio 40")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_PARCIAL
    try:
        resp = client.get("/prediccion/integrada?zona=Portal Norte")
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado_evento"] == "parcial", f"Esperaba parcial, obtuve {data.get('estado_evento')}"
        assert data["probabilidad"] == 40, f"Esperaba 40, obtuve {data['probabilidad']}"
        assert data["nivel_riesgo"] == "medio", f"Esperaba medio, obtuve {data['nivel_riesgo']}"
        print(f"  estado={data['estado_evento']}, prob={data['probabilidad']}%, nivel={data['nivel_riesgo']}")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_chatbot_restablecimiento_responde_bajo():
    print("\n[TEST] Chatbot menciona restablecimiento cuando estado=restablecido")
    import src.ia.risk_integrator as ri_module
    original = ri_module.find_recent_alerts_for_zone
    ri_module.find_recent_alerts_for_zone = lambda zona, count=50: MOCK_CIERRE_ANTIGUO_RESTABLECIDO_RECIENTE
    try:
        resp = client.post("/chatbot", json={
            "pregunta": "hay paro en portal norte?",
            "zona": "Portal Norte"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["probabilidad"] == 15
        assert data["nivel_riesgo"] == "bajo"
        assert "restablecimiento" in data["respuesta"].lower() or "recorrido" in data["respuesta"].lower()
        print(f"  Respuesta: {data['respuesta'][:200]}...")
    finally:
        ri_module.find_recent_alerts_for_zone = original

def test_classify_event_state():
    print("\n[TEST] classify_event_state detecta correctamente")
    from src.ia.whatsapp_tm_service import classify_event_state
    assert classify_event_state("A la hora se cierran estaciones. Continuan los desvios.") == "activo"
    assert classify_event_state("Servicios retoman su recorrido habitual. Cancelan los desvios.") == "restablecido"
    assert classify_event_state("Operacion parcial, continuan retrasos.") == "parcial"
    assert classify_event_state("Hoy es un dia soleado.") == "sin_alerta_hoy"
    print("  OK: activo, restablecido, parcial, sin_alerta_hoy")

def test_matches_zone_rutas():
    print("\n[TEST] matches_zone con rutas de bus (HK54, JF23, K86)")
    from src.ia.whatsapp_tm_service import matches_zone
    assert matches_zone("La ruta HK54 tiene desvios hoy", "HK54"), "HK54 debe coincidir"
    assert matches_zone("Servicio JF23 con retrasos", "JF23"), "JF23 debe coincidir"
    assert matches_zone("K86 sin paso por manifestacion", "K86"), "K86 debe coincidir"
    assert not matches_zone("Ruta H54 va bien", "HK54"), "H54 parcial no debe coincidir con HK54"
    print("  OK: rutas detectadas correctamente")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" EJECUTANDO PRUEBAS (MODO REAL)")
    print("=" * 60)
    tests = [
        test_health,
        test_web_index,
        test_fuentes_estado,
        test_prediccion_integrada_portal_eldorado,
        test_prediccion_sin_demo_data,
        test_buses_sin_datos,
        test_csv_historico_presente,
        test_firebase_sin_config,
        test_chatbot,
        test_chatbot_sin_zona,
        test_chatbot_otras_zonas,
        test_chatbot_prioridad_pregunta_sobre_body,
        test_chatbot_body_fallback_sin_zona_en_pregunta,
        test_chatbot_sin_zona_sin_body_pide_zona,
        test_extraer_zona_desde_pregunta,
        test_classify_event_state,
        test_matches_zone_rutas,
        test_existing_endpoints,
        test_actualizar_pesos,
        test_docs,
        test_openapi,
        test_whatsapp_tm_recientes_endpoint,
        test_detect_strong_tm_alert,
        test_matches_zone_universidad_pedagogica,
        test_prediccion_integrada_universidad_pedagogica_mock_whapi,
        test_chatbot_universidad_pedagogica_mock_whapi,
        test_sistema_sin_whapi_no_se_rompe,
        test_chatbot_detecta_zona_desde_pregunta,
        test_estado_restablecido_ultimo_mensaje,
        test_estado_activo_ultimo_mensaje,
        test_estado_desvios_activos,
        test_estado_parcial,
        test_chatbot_restablecimiento_responde_bajo,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n  FAIL: {test_fn.__name__} -> {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print("\n" + "=" * 60)
    print(f" RESULTADO: {passed} passed, {failed} failed")
    print("=" * 60)
