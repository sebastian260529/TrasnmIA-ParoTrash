# TransmIA ParoTrash - Sistema de Monitoreo y Prediccion de Riesgo

Sistema en Python para monitorear buses de Transmilenio en tiempo real y predecir riesgo de paros, bloqueos o afectaciones usando datos reales.

## Ejecucion real del sistema

### Instalacion

```bash
pip install -r requirements.txt
```

### Ejecutar el servidor

```bash
uvicorn src.api.server:app --reload --host 127.0.0.1 --port 8000
```

### Abrir la web

```
http://127.0.0.1:8000
```

### Swagger/OpenAPI

```
http://127.0.0.1:8000/docs
```

### Pruebas

```bash
python test_integracion_web.py
```

## Fuentes reales que usa el sistema

El sistema integra **5 fuentes de datos** con pesos ponderados:

| Fuente | Peso | Datos usados |
|--------|------|-------------|
| Buses / Anomalias | 30% | `data/buses.db` (SQLite con posiciones reales de buses capturadas por el tracker) |
| WhatsApp / TransMilenio | 25% | Whapi.cloud (mensajes en tiempo real del canal WhatsApp de TransMilenio) + `data/tm_alerts_sample.csv` (dataset historico de alertas) |
| Firebase / Reportes | 20% | Reportes de usuarios en Firestore (si esta configurado) |
| IA / Texto | 15% | Analisis de palabras clave en textos reales + reglas expertas |
| Geolocalizacion | 10% | Diccionario local de zonas de Bogota con coordenadas |

### WhatsApp/TransMilenio en tiempo real

El sistema consulta el canal oficial de WhatsApp de TransMilenio mediante Whapi.cloud.

**Configuracion (.env):**

```
WHAPI_MODE=real
WHAPI_TOKEN=tu_token_whapi
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TRANSMILENIO_CHANNEL_ID=120363248438023604@newsletter
```

**Funcionamiento:**

- Si Whapi esta configurado (`WHAPI_MODE=real`), el sistema consulta mensajes recientes del canal de TransMilenio.
- Si hay una alerta oficial de HOY que coincide con la zona consultada y contiene palabras fuertes (cierre de estaciones, desvios, bloqueo, manifestacion, etc.), el riesgo se eleva al **100%** y el tipo de dato aparece como `real_hoy`.
- Si Whapi **no** esta configurado, el sistema usa el CSV historico (`data/tm_alerts_sample.csv`) como respaldo y funciona normalmente.
- El sistema estima riesgo operativo, **no confirma oficialmente un paro** si la alerta no lo dice literalmente.

### Que pasa si Firebase no esta configurado

El sistema no se rompe. La fuente `firebase_reportes` devuelve score=0 con tipo_dato="sin_datos" o "error" y una advertencia explicando que Firebase no esta disponible. La prediccion se calcula con las fuentes que si tengan datos.

### Que pasa si no hay buses reales recientes

La fuente `buses` devuelve score=0 con tipo_dato="sin_datos" y una advertencia indicando que no hay buses reales recientes. Esto es normal si el tracker de buses no se ha ejecutado o no se han capturado posiciones.

### Que significa que el score venga principalmente del historico

Si la mayor parte del score viene de `whatsapp_transmilenio` (patrones historicos), significa que hay coincidencias en el dataset de alertas pasadas de TransMilenio, pero NO confirma un evento actual. El sistema siempre lo aclara con la advertencia: "Este score es historico, no confirma un evento actual."

### El sistema estima riesgo, NO confirma paros oficiales

La probabilidad que muestra el sistema es una estimacion basada en los datos reales disponibles. Un riesgo alto NO significa que haya un paro confirmado. Siempre consulte fuentes oficiales de TransMilenio para informacion verificada.

## Zonas de Bogota reconocidas

El sistema reconoce 16 zonas con coordenadas y radios de busqueda:

- Portal Eldorado, Portal Norte, Portal Sur, Portal Americas, Portal 20 de Julio
- Universidad Distrital sede La Macarena, Universidad Pedagogica
- Avenida Caracas con Carrera 12B, Avenida Caracas con Calle 6
- Avenida Circunvalar con Calle 26
- Carrera 5 con Calle 28, Carrera 7 con Calle 28
- Calle 12B con Carrera 10, Carrera 10 con Calle 24
- Calle 72 con Carrera 11, Carrera 30 con Avenida Chile

## Estructura del Proyecto

```
├── data/
│   ├── buses.db                  # SQLite con posiciones de buses
│   ├── rutas.csv                 # Rutas de Transmilenio
│   ├── tm_alerts_sample.csv      # Dataset historico de alertas TM
│   └── serviceAccountKey.json    # Credenciales Firebase
├── src/
│   ├── api/
│   │   ├── server.py             # FastAPI con todos los endpoints
│   │   ├── bus_tracker.py        # Monitoreo de buses en tiempo real
│   │   └── demo_service.py       # Servicio de escenarios demo (no usado en flujo principal)
│   ├── analisis/
│   │   ├── anomaly_detector.py   # Deteccion de anomalias en buses
│   │   ├── ponderador.py         # Ponderador deteccion + reportes
│   │   ├── analisis.py           # Analisis de densidad/proximidad
│   │   ├── graficos.py           # Generacion de mapas
│   │   └── tendencias.py
│   ├── database/
│   │   └── database.py           # SQLite para posiciones de buses
│   ├── firebase/
│   │   ├── __init__.py           # Inicializacion de Firebase
│   │   └── client.py             # Operaciones CRUD de reportes
│   ├── geo/
│   │   └── location_service.py   # Geocodificacion y comparacion espacial
│   ├── ia/
│   │   ├── prediction_service.py
│   │   ├── pattern_analysis.py   # Analisis de patrones historicos
│   │   ├── risk_integrator.py    # Integrador de 5 fuentes de riesgo (SOLO REAL)
│   │   ├── nlp_service.py
│   │   ├── expert_rules_service.py
│   │   ├── schemas.py
│   │   └── tm_alert_parser.py
│   ├── config/
│   │   ├── config.py
│   │   └── ponderado.json
│   └── web/
│       ├── index.html            # Interfaz web
│       ├── styles.css            # Estilos
│       └── app.js                # Logica frontend
├── test_integracion_web.py       # Pruebas de integracion (modo real)
└── requirements.txt
```

## Endpoints principales

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/` | GET | Web principal |
| `/health` | GET | Health check |
| `/fuentes/estado` | GET | Estado de las 5 fuentes de datos |
| `/prediccion/integrada?zona=...` | GET | Prediccion integrada SOLO con datos reales |
| `/chatbot` | POST | Chatbot conversacional |
| `/whatsapp/tm/recientes?count=...` | GET | Mensajes recientes del canal WhatsApp/TransMilenio via Whapi |
| `/anomalias/deteccion` | GET | Deteccion automatica de anomalias |
| `/anomalias/reportes` | GET | Reportes de usuarios |
| `/anomalias/ponderado` | GET | Combinacion ponderada |
| `/reportes/crear` | POST | Crear reporte de usuario |
| `/reportes/votar` | POST | Votar reporte |
| `/config/ponderado` | GET/PUT | Ver/editar pesos |
| `/buses/grafica` | GET | Mapa de buses |
| `/anomalias/grafica` | GET | Mapa de anomalias |
| `/ia/prediccion` | POST | Prediccion IA |
| `/monitoreo` | GET | Estado del monitoreo |
| `/docs` | GET | Swagger/OpenAPI |

## Notas Importantes

1. Las credenciales de la API de Transmilenio (`appid`, `uuid`) deben ser validas en `src/config/config.py`.
2. El monitoreo de buses se ejecuta en background al iniciar el servidor.
3. La base de datos `data/buses.db` crece con el tiempo.
4. Firebase requiere `data/serviceAccountKey.json` valido. Si no existe, el sistema funciona sin el.
5. El sistema NO crea datos falsos. Si una fuente no tiene datos, lo indica claramente.
