# TransmIA ParoTrash

Sistema integral en Python para monitorear buses de Transmilenio en tiempo real y predecir el riesgo de paros, bloqueos, manifestaciones o afectaciones operativas mediante el análisis ponderado de 5 fuentes de datos reales con inteligencia artificial.

---

## Tabla de Contenidos

1. [Instalación](#instalación)
2. [Configuración](#configuración)
3. [Ejecución](#ejecución)
4. [Arquitectura del Sistema](#arquitectura-del-sistema)
5. [Estructura del Proyecto](#estructura-del-proyecto)
6. [Módulos](#módulos)
   - [API (FastAPI Server)](#api-fastapi-server)
   - [Análisis](#análisis)
   - [IA / Inteligencia Artificial](#ia--inteligencia-artificial)
   - [Base de Datos](#base-de-datos)
   - [Firebase](#firebase)
   - [WhatsApp / TransMilenio](#whatsapp--transmilenio)
   - [Ubicación de Buses](#ubicación-de-buses)
   - [Configuración](#configuración-1)
   - [CLI](#cli)
   - [Web Frontend](#web-frontend)
7. [Sistema de Fuentes y Pesos](#sistema-de-fuentes-y-pesos)
8. [Pipeline de Predicción Integrada](#pipeline-de-predicción-integrada)
9. [Sistema de Scoring](#sistema-de-scoring)
10. [Endpoints de la API](#endpoints-de-la-api)
11. [Comandos CLI](#comandos-cli)
12. [Datos y Archivos](#datos-y-archivos)
13. [Scripts de Prueba y Verificación](#scripts-de-prueba-y-verificación)
14. [Variables de Entorno (.env)](#variables-de-entorno-env)
15. [Configuración del Análisis](#configuración-del-análisis)
16. [Zonas Reconocidas](#zonas-reconocidas)
17. [Escenarios Demo](#escenarios-demo)
18. [Manejo de Errores y Degradación](#manejo-de-errores-y-degradación)
19. [Notas Importantes](#notas-importantes)

---

## Instalación

```bash
pip install -r requirements.txt
```

**Dependencias:**

| Paquete | Uso |
|---------|-----|
| `requests>=2.28.0` | Cliente HTTP para APIs externas (Transmilenio, Whapi, DeepSeek, Google Maps) |
| `matplotlib>=3.5.0` | Generación de mapas y gráficas de buses/anomalías |
| `flask>=2.0.0` | Dependencia heredada (incluida en requirements) |
| `fastapi>=0.100.0` | Framework principal del servidor REST |
| `uvicorn[standard]>=0.23.0` | Servidor ASGI para FastAPI |
| `firebase-admin>=6.0.0` | SDK de Firebase para Firestore (reportes de usuarios) |
| `pydantic>=2.0.0` | Validación de schemas y modelos de datos |
| `python-multipart>=0.0.6` | Soporte para subida de archivos en FastAPI |

---

## Configuración

### Archivo `.env`

Crear en la raíz del proyecto:

```
WHAPI_MODE=real
WHAPI_TOKEN=tu_token_whapi
WHAPI_BASE_URL=https://gate.whapi.cloud
WHAPI_TRANSMILENIO_CHANNEL_ID=ID_DEL_CANAL

MODEL_MODE=rules
ENVIRONMENT=development

GOOGLE_MAPS_API_KEY=tu_api_key_de_google_maps
DEEPSEEK_API_KEY=tu_api_key_de_deepseek
```

### Archivo `config/config.py`

Contiene toda la parametrización del sistema (ver [Configuración del Análisis](#configuración-del-análisis) para detalle completo).

### Firebase

Colocar el archivo de credenciales en `data/serviceAccountKey.json` (ignorado por git).

---

## Ejecución

### Servidor web principal

```bash
python -m api.server
```

Esto inicia:
- El servidor FastAPI en `http://localhost:8000`
- La interfaz web en `http://localhost:8000`
- El monitoreo background de buses (cada 60s por defecto)
- Swagger/OpenAPI en `http://localhost:8000/docs`

También se puede ejecutar directamente con uvicorn:

```bash
uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

### CLI (Terminal)

```bash
python cli/main.py monitorear
python cli/main.py consultar
python cli/main.py anomalias
```

(Versión completa en [Comandos CLI](#comandos-cli))

### Pruebas

```bash
python test_integracion_web.py
python test_anomalias_completo.py
python test_chatbot.py
python test_buses_escenarios.py
```

---

## Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USUARIO FINAL                                 │
├──────────────────────────────┬───────────────────────────────────────┤
│          WEB (SPA)           │              CLI                      │
│   web/index.html + app.js    │          cli/main.py                  │
└──────────────┬───────────────┴───────────────┬───────────────────────┘
               │                               │
┌──────────────▼───────────────────────────────▼───────────────────────┐
│                     FASTAPI SERVER (api/server.py)                    │
│  ┌─────────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │ /prediccion/ │ │ /chatbot │ │ /anomalias/* │ │ /reportes/*      │ │
│  │  integrada   │ │          │ │              │ │                  │ │
│  └──────┬───────┘ └────┬─────┘ └──────┬───────┘ └───────┬──────────┘ │
└─────────┼──────────────┼──────────────┼─────────────────┼────────────┘
          │              │              │                 │
┌─────────▼──────────────▼──────────────▼─────────────────▼────────────┐
│                  INTEGRADOR DE RIESGO (ia/risk_integrator.py)        │
│  Pondera 4 fuentes con pesos: buses 35% + whatsapp 30% +             │
│  firebase 20% + ia_texto 15%                                         │
├───────┬──────────┬──────────────┬──────────────┬─────────────────────┤
│Buses  │WhatsApp  │Firebase      │IA/Texto      │Google Maps          │
│35%    │TM 30%    │Reportes 20%  │Historico 15% │Geocoding            │
├───────┼──────────┼──────────────┼──────────────┼─────────────────────┤
│DB     │Whapi     │Firestore     │NLP + Reglas  │Google Geocode API   │
│SQLite │.cloud    │              │Expertas      │                     │
├───────┼──────────┼──────────────┼──────────────┼─────────────────────┤
│Tracker│Parser TM │CRUD Reportes │Pattern       │DeepSeek Chatbot     │
│API TM │Alertas   │Votación      │Analysis +    │                     │
│       │          │Consenso      │Prediction    │                     │
└───────┴──────────┴──────────────┴──────────────┴─────────────────────┘
```

### Flujo de datos

1. **BusTracker** (`api/bus_tracker.py`) consulta la API de Transmilenio cada 60s mediante 40 workers en paralelo, capturando posiciones GPS de todos los buses por cada ruta del CSV `data/rutas.csv` (1265+ rutas).
2. Las posiciones se almacenan en **SQLite** (`data/buses.db`) en 3 tablas: `posiciones_buses` (historial), `captura_actual` (última captura), `captura_anterior` (para comparar velocidad).
3. **AnomalyDetector** (`analisis/anomaly_detector.py`) analiza las posiciones en tiempo real para detectar 3 tipos de anomalías: manifestaciones, trancones y buses varados, usando clustering lineal por dirección y cálculo de velocidad mediante Haversine.
4. **WhatsApp/TM** (`whatsapp/whatsapp_tm_service.py`) consulta via Whapi.cloud el canal oficial de TransMilenio, parsea alertas, clasifica severidad y estado del evento (activo/parcial/restablecido) y las cruza con zonas consultadas.
5. **Firebase** (`firebase/client.py`) gestiona reportes de usuarios con votación y consenso.
6. **RiskIntegrator** (`ia/risk_integrator.py`) combina los 4 scores individuales mediante pesos ponderados (35%/30%/20%/15%) y produce una predicción final con nivel de riesgo (bajo/medio/alto).
7. **DeepSeek** (`ia/deepseek_service.py`) genera respuestas conversacionales en español en el chatbot usando los datos de todas las fuentes como contexto.
8. **Google Maps** (`ia/geocode_service.py`) geocodifica direcciones ingresadas por el usuario a coordenadas, con caché para evitar consultas repetidas.

---

## Estructura del Proyecto

```
TrasnmIA-ParoTrash/
├── .env                              # Variables de entorno
├── .gitignore                        # Exclusiones de git
├── requirements.txt                  # Dependencias Python
├── rutas.csv                         # (duplicado en raíz, usar data/rutas.csv)
│
├── analisis/                         # Módulo de análisis y detección
│   ├── __init__.py                   # Exporta funciones públicas
│   ├── analisis.py                   # Densidad, proximidad, velocidad, Haversine, clustering
│   ├── anomaly_detector.py           # Detección de anomalías (manifestación, trancón, bus varado)
│   ├── graficos.py                   # Generación de mapas PNG con matplotlib
│   ├── ponderador.py                 # Combinación ponderada: detección + reportes + IA
│   └── tendencias.py                 # Tendencias por hora, resumen del día
│
├── api/                              # Servidor FastAPI y servicios asociados
│   ├── __init__.py                   # Exporta BusTracker
│   ├── server.py                     # FastAPI: 25+ endpoints, web frontend, monitoreo background
│   ├── bus_tracker.py                # Monitoreo de buses: API TM, 40 workers paralelos, captura GPS
│   └── demo_service.py               # Escenarios demo (alto/medio/bajo) con datos sintéticos
│
├── cli/                              # Interfaz de línea de comandos
│   └── main.py                       # 10 comandos: prueba, rutas, analizar, monitorear, consultar,
│                                     #   ruta, resumen, exportar, stats, anomalias
│
├── config/                           # Configuración centralizada
│   ├── __init__.py                   # Re-exporta config.py
│   ├── config.py                     # 67 líneas: API TM, DB, clustering, portales, umbrales, logging
│   └── ponderado.json                # Pesos para el sistema de 3 fuentes (detección/reporte/predicción)
│
├── data/                             # Archivos de datos
│   ├── buses.db                      # SQLite: posiciones_buses, captura_actual, captura_anterior
│   ├── rutas.csv                     # 1265+ rutas Transmilenio (Route_ID, Final_Destination)
│   ├── tm_alerts_sample.csv          # Dataset histórico de 15 alertas TM (para análisis de patrones)
│   ├── serviceAccountKey.json        # Credenciales Firebase (gitignored)
│   └── graficos/                     # 13+ mapas PNG generados (buses/anomalias en tiempo real)
│
├── database/                         # Persistencia SQLite
│   ├── __init__.py                   # Exporta BusDatabase
│   └── database.py                   # CRUD completo: guardar/consultar posiciones, capturas,
│                                     #   trayectorias, estadísticas, comparación de velocidad
│
├── firebase/                         # Integración con Firebase Firestore
│   ├── __init__.py                   # Inicialización de Firebase, Firestore client
│   └── client.py                     # CRUD reportes, votación, consenso por proximidad,
│                                     #   reputación de usuarios, verificación
│
├── ia/                               # Inteligencia Artificial y predicción
│   ├── __init__.py                   # Exporta PredictionService, NLPService, ExpertRulesService, schemas
│   ├── schemas.py                    # Modelos Pydantic: PrediccionRequest/Response, Reporte, Chatbot, etc.
│   ├── prediction_service.py         # Orquestador: NLP + ExpertRules → predicción de riesgo
│   ├── nlp_service.py                # Detección de palabras clave en 6 categorías
│   ├── expert_rules_service.py       # Reglas expertas: puntajes por palabra clave, publicaciones, reportes
│   ├── risk_integrator.py            # INTEGRADOR PRINCIPAL: 4 scores → predicción ponderada final
│   ├── deepseek_service.py           # DeepSeek AI: respuestas conversacionales del chatbot
│   ├── geocode_service.py            # Google Maps Geocoding con caché local
│   ├── pattern_analysis.py           # Análisis de patrones históricos + predicción diaria/semanal
│   └── tm_alert_parser.py            # Parser de alertas TM: hora, ubicación, causa, estaciones, desvíos
│
├── ubicacion_buses/                  # Geocodificación local (sin API externa)
│   ├── __init__.py                   # Exporta funciones de location_service
│   └── location_service.py           # Zonas conocidas (16), Haversine, reverse geocode local,
│                                     #   enriquecimiento de buses y alertas con ubicación
│
├── web/                              # Frontend Single Page Application
│   ├── index.html                    # Interfaz: zona, chatbot, scores, explicación, debug
│   ├── styles.css                    # Tema oscuro (213 líneas), responsive
│   └── app.js                        # Lógica: analizarRiesgo(), chatbot, renderResultado(),
│                                     #   cargarEstadoFuentes()
│
├── whatsapp/                         # Integración WhatsApp/TransMilenio via Whapi.cloud
│   └── whatsapp_tm_service.py        # Consulta Whapi, parsea mensajes, detecta severidad,
│                                     #   clasifica estado, cruza con zonas, zona horaria Colombia
│
├── chatbot_response.json             # Respuesta de ejemplo del chatbot
├── debug_chatbot.json                # Depuración del chatbot
├── debug_firebase.json               # Depuración de Firebase
├── debug_sim.py                      # Depuración de simulación
├── respuesta_chatbot.txt             # Respuesta de ejemplo (texto)
│
├── check_anomalias.py                # Script: consulta anomalías cerca de la Caracas con 11 Sur
├── check_api.py                      # Script: verifica 3 endpoints de la API
├── check_buses.py                    # Script: inspecciona campos de buses
├── check_hist.py                     # Script: verifica datos históricos
├── check_posicion.py                 # Script: verifica posiciones de buses
├── check_speed.py                    # Script: verifica velocidad de buses
│
├── test_anomalias_completo.py        # Pruebas completas de detección de anomalías
├── test_buses_escenarios.py          # Pruebas de escenarios de buses
├── test_chatbot.py                   # Pruebas del chatbot
├── test_integracion_web.py           # Pruebas de integración web (modo real)
├── test_pred.py                      # Pruebas de predicción
└── test_velocidad.py                 # Pruebas de velocidad de buses
```

---

## Módulos

### API (FastAPI Server)

**Archivo:** `api/server.py` (629 líneas)
**Descripción:** Servidor FastAPI unificado con CORS habilitado, sirve el frontend web estático, ejecuta monitoreo en background y expone 25+ endpoints REST.

**Modelos Pydantic:**
- `ReporteCreate`: reporte_id, id_usuario, ubicacion [lat, lon], tipo, descripcion
- `ReporteVoto`: reporte_id, tipo_voto ("positivo"/"negativo")
- `PesosUpdate`: peso_deteccion, peso_reporte, peso_prediccion_ia
- `PrediccionRequestIA`: zona, publicaciones[], reportes_app[]
- `EscenarioRequest`: zona, intensidad ("alto"/"medio"/"bajo")
- `ChatbotRequest`: pregunta, zona

**Sistema de Zonas (Zone Aliases):**
Mapa interno de ~30 alias de zonas de Bogotá con coordenadas (Universidad Pedagógica, Universidad Distrital, Portales, Avenida Caracas, Circunvalar, etc.) usado para:
- Normalizar preguntas del chatbot
- Extraer zona automáticamente del texto del usuario
- Calcular similaridad Jaccard entre la pregunta y los alias (umbral ≥ 0.7)

**ZONE_ALIASES:** Diccionario con ~50 entradas que mapean variantes de nombres de lugares a su forma canónica con lat/lon. Ej: "la pedagogica", "u pedagogica", "pedagogica" → Universidad Pedagogica (4.627, -74.065).

**Monitoreo Background:**
Al iniciar el servidor, se lanza un thread daemon que ejecuta `iniciar_monitoreo_background()`:
1. Crea un `BusTracker`
2. Carga rutas desde CSV
3. Cada `MONITOR_INTERVAL` segundos (60 por defecto) escanea todas las rutas
4. Los resultados se almacenan en `captura_actual` y `posiciones_buses`

**Funciones auxiliares:**
- `_normalize_question(texto)`: Normaliza texto (minúsculas, sin tildes, sin puntuación)
- `similarity_jaccard(s1, s2)`: Índice de Jaccard para comparar textos
- `extraer_zona_desde_pregunta(pregunta)`: Detecta la zona mencionada en una pregunta usando substring matching + Jaccard

---

**Archivo:** `api/bus_tracker.py` (356 líneas)
**Descripción:** Motor principal de monitoreo de buses. Se conecta a la API de Transmilenio para obtener posiciones GPS en tiempo real.

**Clase `BusTracker`:**
- `cargar_rutas_desde_csv()`: Lee `data/rutas.csv` y extrae combinaciones únicas Route_ID + Final_Destination
- `_get_headers()`: Headers con appid, uuid, version, user-agent para la API TM
- `_build_payload(ruta, nombre)`: Payload JSON para la solicitud POST
- `_extraer_coordenadas(datos)`: Detecta formato de coordenadas (latitude/longitude, lat/lng, coords, location, pos, gps)
- `obtener_buses(ruta, nombre)`: POST a la API TM, maneja respuesta como dict único, lista, o dict con claves numéricas
- `guardar_buses(buses)`: Inserta en `posiciones_buses` via `BusDatabase`
- `escanear_rutas(rutas)`: Escaneo paralelo con `ThreadPoolExecutor(max_workers=40)`, 40 rutas simultáneas
  1. Procesa todas las rutas en paralelo
  2. Guarda buses en DB
  3. Rota capturas: actual → anterior, nueva → actual
  4. Retorna estadísticas (total encontrados, guardados, rutas sin buses)
- `iniciar_monitoreo(intervalo, callback)`: Loop infinito con Ctrl+C, analiza cada captura, genera gráficas opcionales
- `prueba_conexion()`: Test de conexión con la primera ruta del CSV

---

**Archivo:** `api/demo_service.py` (180 líneas)
**Descripción:** Servicio para crear escenarios de demostración con datos sintéticos. Útil para pruebas y presentaciones sin depender del tracker real.

**Estado global `_demo_state`** con buses_demo, reportes_demo, alertas_simuladas.

**Intensidades:**
- `alto`: 6 buses a 3 km/h, 4 reportes (paro, bloqueo, manifestación, congestión), 4 alertas
- `medio`: 3 buses a 8 km/h, 2 reportes (congestión, desvío), 2 alertas
- `bajo`: 1 bus a 20 km/h, 1 reporte (normal), 1 alerta

**Funciones:**
- `crear_escenario_demo(zona, intensidad)`: Crea datos demo
- `limpiar_demo()`: Resetea estado demo
- `get_demo_state()`: Estado actual de la demo
- `get_demo_reportes()`, `get_demo_alertas()`, `get_demo_buses()`: Getters

---

### Análisis

**Archivo:** `analisis/analisis.py` (1161 líneas)
**Descripción:** Módulo central de análisis de trancones y congestión.

**Funciones principales:**
- `haversine(lat1, lon1, lat2, lon2)`: Distancia en metros entre dos puntos geográficos
- `obtener_direccion(bus)`: Determina dirección (ARRIBA/ABAJO/GRIS) según ángulo del bus
- `analisis_densidad(buses, radio)`: Clustering simple de buses por proximidad (radio=100m)
- `analisis_proximidad(buses, distancia)`: Pares de buses muy cercanos (<50m) en la misma dirección
- `analisis_velocidad(db, minutos)`: Detecta buses detenidos/lentos comparando últimas 2 posiciones en DB
- `esta_en_zona_portal(bus)`: Verifica si el bus está a ≤300m de un portal
- `es_destino_portal(bus)`: Verifica si el destino del bus contiene el nombre de un portal
- `filtrar_buses_no_portal(buses)`: Excluye buses en/rumbo a portales
- `analizar_buses_detenidos_historico(db, minutos)`: Detecta buses sin movimiento por ≥5 minutos
- `detectar_anomalias(db)`: Detecta manifestaciones (≥20 detenidos), trancones (≥8 lentos), buses varados en el historial de 1 hora
- `detectar_manifestaciones(detenidos)`: Clustering de ≥20 buses detenidos en radio 500m
- `detectar_trancones(lentos)`: Clustering de ≥8 buses lentos en radio 500m
- `detectar_buses_varados(detenidos, lentos)`: Bus detenido + ≥3 buses lentos alrededor
- `generar_resumen(db)`: Resumen completo: densidad + proximidad + velocidad + alertas
- `analizar_captura_actual(db)`: Análisis solo de la última captura
- `analizar_buses_directo(buses, db)`: Análisis en tiempo real durante el monitoreo
- `formatear_salida(analisis)`: Formato consola con símbolos unicode
- `generar_grafica(buses, densidad, velocidad)`: Mapa matplotlib con colores por dirección, círculos de clusters
- `obtener_configuracion()`: Retorna todos los parámetros de análisis
- `analisis_por_ruta(buses, db, ruta)`: Análisis filtrado por ruta específica

---

**Archivo:** `analisis/anomaly_detector.py` (523 líneas)
**Descripción:** Detección de anomalías optimizada con caché y clustering lineal.

**Características:**
- Caché de 60 segundos para no recalcular constantemente
- Clustering lineal por dirección: ordena buses por latitud dentro de cada dirección y agrupa consecutivos con distancia ≤ 300m
- Cálculo de velocidad real usando Haversine (distancia GPS ÷ tiempo)
- Ignora buses sin al menos 2 posiciones históricas para calcular velocidad
- Porcentaje de confianza escalonado por tipo de anomalía

**Tipos de anomalía y umbrales:**
| Tipo | Umbral | Método | Confianza máxima |
|------|--------|--------|-----------------|
| MANIFESTACION | ≥20 buses sin movimiento | Clustering lineal por dirección | 100% |
| TRANCON | ≥8 buses lentos (<20 km/h) | Clustering lineal por dirección | 100% (+15% si vel < 10 km/h) |
| BUS_VARADO | 1 bus detenido + ≥3 lentos alrededor | Radio 100m | 90% |

**Estructura de respuesta:**
```json
{
  "timestamp": "2026-05-06T...",
  "actualizacion_en_segundos": 60,
  "buses_activos": 150,
  "anomalias": [
    {
      "tipo": "MANIFESTACION",
      "coordenadas": {"latitud": 4.627, "longitud": -74.065},
      "porcentaje_confianza": 85.0,
      "buses_involucrados": 22,
      "radio_m": 300,
      "detalles": {"buses_sin_movimiento": 22, "direccion": "ARRIBA"},
      "buses_ids": ["24224", "24225", ...]
    }
  ],
  "resumen": {
    "total_anomalias": 3,
    "manifestaciones": 1,
    "trancones": 1,
    "buses_varados": 1,
    "buses_sin_movimiento": 25,
    "buses_lentos": 12,
    "buses_normales": 113,
    "buses_sin_datos_historicos": 0,
    "velocidad_promedio_kmh": 18.5
  },
  "excluidos_portal": 0,
  "from_cache": false
}
```

---

**Archivo:** `analisis/graficos.py` (226 líneas)
**Descripción:** Generación de mapas PNG con matplotlib.

**Funciones:**
- `generar_mapa_buses(db)`: Mapa de todos los buses activos con colores por dirección (azul=arriba, rojo=abajo, gris=sin ángulo), incluye leyenda e info de resumen
- `generar_mapa_anomalias(db)`: Mapa de anomalías con círculos por tipo (rojo=manifestación, naranja=trancón, negro=bus varado) y porcentaje de confianza
- `generar_todas_graficas(db)`: Genera ambos mapas a la vez
- `obtener_ultima_grafica(tipo)`: Recupera la última gráfica generada

Los archivos se guardan en `data/graficos/` con timestamp en el nombre (ej: `buses_20260506_180810.png`).

---

**Archivo:** `analisis/ponderador.py` (260 líneas)
**Descripción:** Combina 3 fuentes (detección automática, reportes de usuarios, predicción IA) usando pesos configurables desde `config/ponderado.json`.

**Sistema de 3 pesos** (ponderado.json):
```json
{"peso_deteccion": 0.5, "peso_reporte": 0.3, "peso_prediccion_ia": 0.2}
```

**Funciones:**
- `detectar_anomalias_ponderadas(db, textos_ia)`: Función principal de combinación
  - Score detección: promedio de confianza de anomalías detectadas
  - Score reportes: convierte reportes Firestore a formato anomalía con score por verificación + votos
  - Score IA: pasa textos por NLP + reglas expertas (PredictionService)
  - Resultado: `score_ponderado = detección*0.5 + reportes*0.3 + ia*0.2`
- `get_reportes_activos()`: Filtra reportes verificados o con <5 descartes
- `calcular_score_reporte(reporte)`: Verificado (+50) + votos positivos (max +30) - votos negativos (max -20)
- `calcular_score_prediccion_ia(textos)`: Wrapper para PredictionService con textos default si no hay

---

**Archivo:** `analisis/tendencias.py` (276 líneas)
**Descripción:** Análisis de tendencias horarias y del día.

**Funciones:**
- `obtener_tendencias_por_hora(db, horas)`: Conteo de buses por cada hora de las últimas 24h
- `obtener_resumen_dia(db)`: Total registros, buses únicos, rutas únicas del día actual
- `detectar_tendencias_anomalias(db)`: Actividad por hora con peak/hora menos activa
- `get_tendencias(db, force_refresh)`: Versión con caché (5 minutos)
- `formatear_tendencias(tendencias)`: Formato consola con barras ASCII

---

### IA / Inteligencia Artificial

**Archivo:** `ia/schemas.py` (70 líneas)
**Descripción:** Modelos Pydantic para toda la capa de IA.

**Modelos:**
- `ReporteAppInput`: tipo, descripcion, confirmaciones, descartes
- `PrediccionRequest`: zona, publicaciones[], reportes_app[]
- `FuentesAnalizadas`: publicaciones, reportes_app
- `PrediccionResponse`: zona, probabilidad, nivel_riesgo, palabras_clave_detectadas, explicacion, recomendaciones
- `ChatbotRequest/Response`: pregunta, respuesta, probabilidad, nivel_riesgo
- `TransMilenioAlertRequest/Response`: texto, fecha, hora, ubicación, causa, estaciones, servicios, desvíos, usuarios
- `WhapiPredictionResponse`: modo, alertas[], prediccion, error

---

**Archivo:** `ia/prediction_service.py` (77 líneas)
**Descripción:** Orquestador de predicción que combina NLP + reglas expertas.

**Clase `PredictionService`:**
- `predecir_riesgo(request)`: Pipeline completo:
  1. Extrae textos de publicaciones y reportes
  2. NLP → detecta palabras clave en todos los textos
  3. ExpertRules → calcula probabilidad (0-100) basada en palabras + volumen + confirmaciones
  4. Clasifica nivel: ≤30=bajo, ≤60=medio, >60=alto
  5. Genera explicación y recomendaciones
- `_generar_explicacion()`: Texto contextual según nivel de riesgo
- `_generar_recomendaciones()`: Acciones sugeridas por nivel
- `predecir_con_textos(zona, textos)`: Wrapper simplificado

---

**Archivo:** `ia/nlp_service.py` (41 líneas)
**Descripción:** Servicio de Procesamiento de Lenguaje Natural con detección de palabras clave.

**6 Categorías de palabras clave:**
| Categoría | Palabras |
|-----------|---------|
| paro | paro, huelga, paro nacional, paro indefinido |
| bloqueo | bloqueo, bloqueada, bloqueado, vía cerrada, cierre |
| manifestación | manifestación, protesta, marcha, disturbio |
| accidente | accidente, choque, colisión |
| transporte_publico | transmilenio, sitp, estación, portal, bus, transporte |
| trafico_normal | trancón, congestión, retrasos, tráfico, movilidad afectada |

**Funciones:**
- `procesar_texto(texto)`: Normaliza (minúsculas, sin puntuación)
- `detectar_palabras_clave(textos)`: Detecta palabras clave en múltiples textos
- `clasificar_por_categorias(textos)`: Agrupa por categoría con conteo

---

**Archivo:** `ia/expert_rules_service.py` (36 líneas)
**Descripción:** Motor de reglas expertas para calcular probabilidad de riesgo.

**Sistema de puntuación:**
| Condición | Puntos |
|-----------|--------|
| Palabra alto riesgo (paro, bloqueo, cierre) | +30 c/u |
| Palabra medio riesgo (manifestación, protesta, marcha) | +20 c/u |
| Palabra bajo riesgo (trancón, congestión, retrasos) | +5 c/u |
| >5 publicaciones | +15 |
| >2 publicaciones | +10 |
| >3 reportes | +15 |
| >1 reporte | +10 |
| Confirmaciones > 2× descartes | +20 |
| Descartados > confirmaciones | -10 |

Resultado final: `max(0, min(100, puntaje))`

---

**Archivo:** `ia/risk_integrator.py` (938 líneas)
**Descripción:** **INTEGRADOR PRINCIPAL.** Calcula la predicción de riesgo integrada combinando 4 fuentes de datos reales con pesos ponderados.

**Pesos:**
```python
PESOS = {
    "buses": 0.35,                # Anomalías detectadas en posiciones GPS
    "whatsapp_transmilenio": 0.30, # Alertas oficiales del canal WhatsApp TM
    "firebase_reportes": 0.20,     # Reportes de usuarios en Firestore
    "ia_texto": 0.15               # Análisis de datos históricos + NLP
}
```

**Funciones de scoring por fuente:**

1. **`_score_buses(db, zona)`**:
   - Obtiene coordenadas de la zona consultada
   - Ejecuta `detectar_anomalias(db)` con force_refresh
   - Filtra anomalías y buses dentro del radio de la zona (800m portales, 500m otras)
   - Scores escalonados por tipo:
     - MANIFESTACION: confianza × 0.85 (tope 85%)
     - TRANCON: confianza × 0.55 (tope 55%)
     - BUS_VARADO: confianza × 0.25 (tope 25%)
   - Si no hay anomalías pero hay buses: 10-20% según cantidad
   - Sin datos: 0% con advertencia

2. **`_score_whatsapp_transmilenio(zona)`**:
   - Consulta `find_recent_alerts_for_zone(zona)`
   - **Caso alerta oficial hoy:** scores predefinidos por estado:
     - activo: 100% (cierre, sin operar, bloqueo)
     - parcial: 40% (retrasos, operación parcial)
     - restablecido: 15% (normalización)
   - **Caso sin alerta oficial:** si hay coincidencias en dataset histórico → 60%
   - Sin datos: 0% con advertencia

3. **`_score_firebase_reportes(zona)`**:
   - Consulta Firestore, filtra reportes reales (no DEMO_)
   - Match por coordenadas (distancia) o texto (zona en descripción/tipo)
   - Score por cantidad: 1=25%, 2-3=50%, 4-5=70%, 6+=85% (tope 90%)
   - Bonus +10% si hay palabras clave de riesgo

4. **`_score_ia_texto(zona)`**:
   - Busca coincidencias en dataset histórico (`tm_alerts_sample.csv`)
   - Pasa textos por PredictionService (NLP + reglas)
   - Score mínimo por cantidad: 1=25%, 2-3=45%, 4-6=65%, 7+=80% (tope 90%)

5. **`_score_geolocalizacion(zona, ...)`**:
   - Score basado en cantidad total de elementos geolocalizados
   - 0 elementos: 0%, ≤3: 20%, ≤8: 40%, >8: 60% (tope 70%)

**Función principal:** `calcular_prediccion_integrada(zona, db)`
   - Ejecuta los 4 scorers (buses, whatsapp, firebase, ia_texto)
   - Si hay alerta oficial de WhatsApp hoy: el score = puntuación del estado (100%/40%/15%), ignora los demás
   - Si no: `prob = buses*0.35 + whatsapp*0.30 + firebase*0.20 + ia_texto*0.15`
   - Clasificación: ≤30=bajo, ≤65=medio, >65=alto
   - Genera explicación, recomendaciones, ubicación inteligente y debug info

**Otras funciones:**
- `get_fuentes_estado()`: Estado de disponibilidad de las 4 fuentes (conectado/no conectado, registros, modo)
- `haversine_distance(lat1, lon1, lat2, lon2)`: Fórmula Haversine
- `buscar_buses_por_coords(lat, lon, radio, db)`: Busca anomalías en radio de coordenadas
- `buscar_whatsapp_por_texto(texto, threshold)`: Busca mensajes WhatsApp con Jaccard ≥ 0.7
- `buscar_historico_por_texto(texto, threshold)`: Busca en CSV histórico con Jaccard ≥ 0.25

---

**Archivo:** `ia/deepseek_service.py` (120 líneas)
**Descripción:** Servicio de IA conversacional usando la API de DeepSeek.

**Función principal:** `generar_respuesta(pregunta, datos_fuentes)`
   - Construye un prompt con todos los datos de las 4 fuentes + predicción
   - Llama a `https://api.deepseek.com/chat/completions` con modelo `deepseek-chat`
   - Temperatura: 0.7, max_tokens: 500
   - Instruye a la IA a usar los porcentajes exactos de la predicción
   - Si DeepSeek no está disponible o falla, usa `generar_respuesta_fallback()` que construye una respuesta estructurada con los datos crudos

**Fallback:** Respuesta formateada con emojis mostrando cada fuente y la predicción final.

---

**Archivo:** `ia/geocode_service.py` (81 líneas)
**Descripción:** Servicio de geocodificación con Google Maps API + caché local.

**Funciones:**
- `geocode(direccion)`: Convierte dirección → coordenadas {lat, lon, direccion_formateada}
  - Usa caché en memoria (`GEOCODE_CACHE`)
  - Añade ", Bogotá, Colombia" al query
- `geocode_reverse(lat, lon)`: Convierte coordenadas → dirección

---

**Archivo:** `ia/pattern_analysis.py` (388 líneas)
**Descripción:** Análisis de patrones históricos de alertas TM para predicción contextual.

**Funciones:**
- `load_alert_dataset(csv_path)`: Carga el CSV de alertas (delimiter `;`, encoding `utf-8-sig`), parsea estaciones/servicios/desvíos como listas
- `analyze_patterns(csv_path)`: Análisis completo:
  - Días con más alertas
  - Ubicaciones más frecuentes
  - Causas más frecuentes
  - Estaciones y servicios más afectados
  - Franjas horarias más frecuentes
  - Total y promedio de usuarios afectados
  - Conclusiones automáticas
- `predict_risk_from_patterns(csv_path, ubicacion, dia_semana, tipo_evento)`:
  - Filtra alertas por ubicación, día de semana y tipo de evento
  - Score por cantidad de alertas históricas: 1=+15, 2=+25, ≤5=+35, ≤10=+45, >10=+55
  - Score por tipo de evento: manifestación=+25, bloqueo=+25, cierre=+20, desvío=+18, congestión=+10, normalización=+3
  - Score por usuarios afectados promedio: >50K=+20, >20K=+15, >5K=+10
  - **Bonus por día histórico:** si el día consultado tiene ≥1.5× más alertas que el promedio → +15
  - **Descuento por día no histórico:** si el día consultado tiene <10% de alertas vs el día más frecuente → -30
  - Probabilidad final: `min(95, max(0, puntaje))`
  - Niveles: ≥66=alto, ≥31=medio, <31=bajo

---

**Archivo:** `ia/tm_alert_parser.py` (335 líneas)
**Descripción:** Parser avanzado de alertas de TransMilenio desde texto de WhatsApp.

**Clase `TMAlertParserService`:**
- `normalize_text(texto)`: Normalización NFC, elimina asteriscos, colapsa espacios
- `extract_time(texto)`: Extrae hora en formato 24h desde variantes AM/PM (a.m., p.m., a m, am., etc.)
- `extract_location(texto)`: Extrae ubicación usando 6 patrones regex (Portal, Estación, Universidad, Avenida, Calle, Carrera, sector/zona de...)
- `normalize_location(ubicacion, texto)`: Normaliza abreviaturas (av→avenida, cra→carrera, cll→calle), números ordinales, nombres compuestos específicos (Circunvalar con Calle 26, Caracas con 12B, etc.)
- `extract_affected_stations(texto)`: Detecta estaciones sin operar o que retoman operación
- `extract_affected_services(texto)`: Extrae códigos de servicio (ej: B23, H15) ignorando falsos positivos (am, pm, av)
- `extract_detours(texto)`: Extrae frases sobre desvíos
- `classify_event_type(texto, causa)`: Clasifica en 7 tipos:
  - Manifestación o protesta
  - Siniestro vial
  - Tormenta eléctrica
  - Cierre o estaciones sin operar
  - Desvíos operacionales
  - Normalización de operación
  - Congestión o retrasos
  - (default) Novedad operacional
- `parse_tm_alert(texto, fecha, fuente)`: Pipeline completo → dict estructurado

---

### Base de Datos

**Archivo:** `database/database.py` (489 líneas)
**Descripción:** Capa de persistencia SQLite para posiciones de buses.

**Clase `BusDatabase`:**
- **3 Tablas:**
  - `posiciones_buses`: Historial completo (bus_id, route_id, label, ruta, latitud, longitud, velocidad, ángulo, destino_limpio, posicion, timestamp)
  - `captura_actual`: Última captura (se sobrescribe cada escaneo), clave única bus_id
  - `captura_anterior`: Penúltima captura (para calcular velocidad entre capturas)
  - `rutas_disponibles`: Catálogo de rutas monitoreadas

- **Índices:** `idx_bus_timestamp`, `idx_ruta_timestamp`

- **Métodos:**
  - `guardar_posicion(datos)`: Inserta en posiciones_buses con UNIQUE(bus_id, timestamp)
  - `obtener_ultimas_posiciones(limite)`: Última posición de cada bus (ROW_NUMBER PARTITION BY)
  - `obtener_trayectoria(bus_id, horas)`: Historial de posiciones de un bus
  - `obtener_por_ruta(ruta, limite)`: Buses de una ruta específica
  - `resumen_por_ruta()`: Agregación por ruta
  - `exportar_json(archivo)`: Export full a JSON
  - `estadisticas()`: total_registros, total_buses, total_rutas, rango de fechas
  - `limpiar_captura_actual()`: DELETE FROM captura_actual
  - `guardar_captura_actual(buses)`: INSERT OR REPLACE en captura_actual
  - `obtener_captura_actual()`: SELECT de captura_actual
  - `captura_actual_estadisticas()`: Conteo de la captura actual
  - `guardar_captura_anterior(buses)`: INSERT OR REPLACE en captura_anterior
  - `obtener_captura_anterior()`: SELECT de captura_anterior
  - `comparar_velocidad()`: Compara captura actual vs anterior para calcular velocidad en km/h

---

### Firebase

**Archivo:** `firebase/__init__.py` (38 líneas)
**Descripción:** Inicialización de Firebase Admin SDK.

**Funciones:**
- `init_firebase()`: Inicializa con `data/serviceAccountKey.json`, retorna Firestore client
- `get_collection(name)`: Obtiene referencia a una colección de Firestore

---

**Archivo:** `firebase/client.py` (177 líneas)
**Descripción:** Operaciones CRUD sobre reportes de usuarios en Firestore.

**Constante:** `RADIO_CONSENSUS = 100` metros

**Funciones:**
- `get_all_reportes()`: Retorna todos los reportes de la colección "reportes"
- `get_reporte_by_id(reporte_id)`: Busca un reporte específico
- `create_reporte(reporte_id, id_usuario, ubicacion, tipo, descripcion)`: Crea reporte + usuario si no existe
- `votacion(reporte_id, tipo_voto)`: Vota positivo → incrementa votos_positivos. Con ≥3 votos positivos → verificado=true. Voto negativo → incrementa descartes. Con ≥5 descartes → penaliza autor (-10 reputación)
- `get_reportes_cercanos(ubicacion, radio)`: Busca reportes en radio de 100m
- `verificar_reporte_por_consenso(reporte_id)`: Verifica si ≥3 reportes cercanos o reputación > 50

---

### WhatsApp / TransMilenio

**Archivo:** `whatsapp/whatsapp_tm_service.py` (483 líneas)
**Descripción:** Integración con Whapi.cloud para monitorear el canal oficial de WhatsApp de TransMilenio.

**Zona horaria:** Colombia (America/Bogota, UTC-5).

**Constantes de clasificación:**
- `FRASES_ACTIVO` (10 frases): cierre de estaciones, sin operar, desvíos activos, bloqueo, flota sin paso, manifestación, protesta, troncal cerrada
- `FRASES_RESTABLECIDO` (13 frases): restablecimiento, cancelan desvíos, retoman recorrido, operación habitual
- `FRASES_PARCIAL` (5 frases): operación parcial, retrasos, congestión residual

**Funciones principales:**
- `get_whapi_config()`: Lee configuración de variables de entorno
- `is_whapi_configured()`: Verifica WHAPI_MODE=real + token + channel_id
- `now_colombia()` / `is_today_colombia(ts)`: Manejo de zona horaria
- `extract_text_from_whapi_message(msg)`: Extrae texto de mensajes (text.body, image.caption, video.caption, document.caption)
- `extract_datetime_from_whapi_message(msg)`: Extrae timestamp con manejo de zona horaria
- `detect_strong_tm_alert(texto)`: Detecta severidad (baja/media_alta/alta/critica) + palabras detectadas
- `classify_event_state(texto)`: Clasifica estado del evento (activo/parcial/restablecido/sin_alerta_hoy)
- `matches_zone(texto, zona)`: Match avanzado:
  1. Substring directo
  2. Expansión de abreviaturas (av→avenida, cra→carrera, cll→calle)
  3. Match de palabras significativas (≥2 palabras en común, o 1 si zona tiene 1 sola palabra)
  4. Palabras fuertes de zona (Caracas, Pedagógica, Distrital, Eldorado, etc.)
  5. Patrón de ruta (regex para códigos tipo B23, H15)
- `get_tm_whatsapp_messages(count)`: Consulta Whapi API, parsea cada mensaje, extrae fecha/hora/ubicación/severidad
- `find_recent_alerts_for_zone(zona, count)`: Filtra mensajes de hoy que matchean con la zona, determina estado del evento

**Palabras ignoradas (genéricas):** universidad, avenida, portal, calle, carrera, con, de, la, el, etc.

**Palabras fuertes (específicas de zona):** caracas, pedagógica, distrital, eldorado, macarena, américas, circunvalar, chile, suba, tunal, usme, banderas, ricautte, etc.

---

### Ubicación de Buses

**Archivo:** `ubicacion_buses/location_service.py` (147 líneas)
**Descripción:** Sistema de geolocalización local con diccionario de 16 zonas conocidas de Bogotá.

**Zonas conocidas (ZONAS_CONOCIDAS):**
- 5 Portales: Eldorado (800m), Américas (800m), Norte (800m), Sur (800m), 20 de Julio (800m)
- 11 Intersecciones/zonas: Universidad Distrital, Pedagógica, Caracas con 12B, Caracas con Calle 6, Circunvalar con Calle 26, Carrera 5 con Calle 28, Carrera 7 con Calle 28, Calle 12B con Carrera 10, Carrera 10 con Calle 24, Calle 72 con Carrera 11, Carrera 30 con Avenida Chile (500m c/u)

**Funciones:**
- `normalize_address(address)`: Normaliza texto (minúsculas, sin tildes, sin puntuación)
- `distance_between_points(lat1, lon1, lat2, lon2)`: Haversine
- `get_zone_coords(zona_nombre)`: Busca zona por nombre (exacto, substring, palabras sueltas)
- `find_nearest_zone(lat, lon)`: Zona más cercana a coordenadas (dentro de 2× radio)
- `match_location_with_zone(address, zona)`: Verifica si una ubicación coincide con una zona
- `reverse_geocode_colombia(lat, lon)`: Geocodificación inversa local (sin API externa)
- `enrich_bus_location(bus)`: Añade dirección y zona detectada a datos de bus
- `enrich_alert_location(alerta, zona)`: Añade info geo + verifica coincidencia con zona consultada

---

### Configuración

**Archivo:** `config/config.py` (67 líneas)
**Descripción:** Configuración centralizada de todo el sistema.

Ver sección [Configuración del Análisis](#configuración-del-análisis) para todos los parámetros.

**Archivo:** `config/ponderado.json` (5 líneas)
```json
{"peso_deteccion": 0.5, "peso_reporte": 0.3, "peso_prediccion_ia": 0.2}
```
Usado por el ponderador de 3 fuentes (no confundir con los 4 pesos del risk_integrator).

---

### CLI

**Archivo:** `cli/main.py` (304 líneas)
**Descripción:** Interfaz de línea de comandos con argparse.

**10 Comandos:**

| Comando | Descripción | Opciones |
|---------|-------------|----------|
| `prueba` | Prueba conexión a la API de Transmilenio | - |
| `rutas` | Lista todas las rutas cargadas desde CSV | - |
| `analizar` | Análisis de trancones | `--ruta`, `--grafica`, `--csv`, `--config` |
| `monitorear` | Monitoreo continuo en tiempo real | `--intervalo` (default: 60s) |
| `consultar` | Últimas posiciones de buses | `--bus-id`, `--horas`, `--limite`, `--json` |
| `ruta` | Buses de una ruta específica | `--ruta` (requerido), `--limite`, `--json` |
| `resumen` | Resumen por ruta | - |
| `exportar` | Exportar datos a JSON | `--archivo` |
| `stats` | Estadísticas de la base de datos | - |
| `anomalias` | Detectar anomalías en transporte | `--json` |

---

### Web Frontend

**Archivos:** `web/index.html`, `web/styles.css`, `web/app.js`
**Descripción:** SPA (Single Page Application) vanilla JS con tema oscuro.

**Secciones de la interfaz:**
1. **Controls:** Input de zona + botón "Analizar riesgo"
2. **Estado de fuentes:** Indicadores verde/rojo para cada una de las 4 fuentes (Buses, WhatsApp, Firebase, IA/Texto) con detalle de disponibilidad, modo y registros
3. **Chatbot:** Área de conversación con historial de mensajes, input de texto y botón "Preguntar". Soporte para Enter key
4. **Resultados:**
   - Tarjetas de probabilidad y nivel de riesgo (con colores: verde=10%, amarillo=50%, rojo=90%)
   - 4 tarjetas de scores por fuente con tipo de dato (real/histórico/sin_datos)
   - Banner de alerta oficial de WhatsApp (si detectada hoy)
   - Explicación detallada
   - Recomendaciones
   - Fuentes utilizadas / no disponibles
   - Ubicación inteligente (zona, coordenadas, conteos)
   - Sección de alerta oficial (roja, si aplica)
   - JSON de depuración (plegable)
5. **Status bar:** Estado actual

**Funciones JS:**
- `analizarRiesgo()`: GET `/prediccion/integrada?zona=...`
- `enviarChatbot()`: POST `/chatbot` con {pregunta, zona}
- `cargarEstadoFuentes()`: GET `/fuentes/estado`
- `renderResultado(data)`: Renderiza toda la UI con los datos de la predicción
- `getNivelClass(nivel)`: Mapea nivel a clase CSS (nivel-alto/medio/bajo)
- `getTipoDatoClass(tipo)`: Mapea tipo de dato a clase CSS (tipo-real/historico/mixto/sin-datos)

---

## Sistema de Fuentes y Pesos

El sistema integra **2 sistemas de pesos** para diferentes propósitos:

### Sistema de 4 Pesos (Risk Integrator - predicción principal)

Usado por `ia/risk_integrator.py` en `calcular_prediccion_integrada()`:

| Fuente | Peso | Descripción |
|--------|------|-------------|
| **Buses / Anomalías** | 35% | Anomalías detectadas en posiciones GPS reales (manifestaciones, trancones, buses varados) desde `data/buses.db` |
| **WhatsApp / TransMilenio** | 30% | Alertas en tiempo real del canal oficial de TM via Whapi.cloud + dataset histórico `data/tm_alerts_sample.csv` |
| **Firebase / Reportes** | 20% | Reportes de usuarios en Firestore con verificación y votación |
| **IA / Texto** | 15% | Análisis de palabras clave por NLP + reglas expertas + patrones históricos |

**Regla de override:** Si WhatsApp detecta una alerta oficial del día de hoy en la zona consultada, el score final se asigna directamente desde el estado del evento (activo=100%, parcial=40%, restablecido=15%), ignorando los otros 3 scores.

### Sistema de 3 Pesos (Ponderador - análisis combinado)

Usado por `analisis/ponderador.py` en `detectar_anomalias_ponderadas()`:

| Fuente | Peso | Descripción |
|--------|------|-------------|
| Detección automática | 50% | Anomalías detectadas por el anomaly_detector |
| Reportes de usuarios | 30% | Reportes en Firestore convertidos a formato anomalía |
| Predicción IA | 20% | NLP + reglas expertas del PredictionService |

Configurable en `config/ponderado.json`. Los pesos deben sumar 1.0.

---

## Pipeline de Predicción Integrada

```
USUARIO pregunta: "¿Hay paro en Portal Eldorado?"
        │
        ▼
┌───────────────────────────────────────────┐
│ 1. GEOCODING                              │
│    Google Maps API → coordenadas          │
│    Fallback: ZONE_ALIASES + Jaccard       │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│ 2. SCORING POR FUENTE                     │
│                                            │
│  _score_buses(zona)                       │
│    → detectar_anomalias(db)               │
│    → filtrar por radio de zona            │
│    → score escalonado por tipo            │
│                                            │
│  _score_whatsapp_transmilenio(zona)       │
│    → Whapi.cloud API                      │
│    → filtrar mensajes de hoy              │
│    → classify_event_state()               │
│    → score por estado                     │
│                                            │
│  _score_firebase_reportes(zona)           │
│    → Firestore get_all_reportes()         │
│    → filtrar por coordenadas/texto        │
│    → score por cantidad + keywords        │
│                                            │
│  _score_ia_texto(zona)                    │
│    → load_alert_dataset(CSV)              │
│    → filtrar por zona                     │
│    → PredictionService(NLP+Rules)         │
│    → score mínimo por cantidad            │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│ 3. PONDERACIÓN                            │
│                                            │
│  ¿Alerta oficial WhatsApp hoy?            │
│    SÍ → prob = score del estado           │
│    NO → prob = buses*0.35 +               │
│                whatsapp*0.30 +            │
│                firebase*0.20 +            │
│                ia_texto*0.15              │
│                                            │
│  Nivel: ≤30=bajo, ≤65=medio, >65=alto     │
└───────────────┬───────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│ 4. CHATBOT (DeepSeek AI)                  │
│    Prompt con datos de las 4 fuentes      │
│    + predicción final + scores            │
│    → respuesta en español                 │
└───────────────┬───────────────────────────┘
                │
                ▼
         RESPUESTA FINAL
```

---

## Sistema de Scoring

### Scores de Buses

| Situación | Score |
|-----------|-------|
| MANIFESTACION detectada | confianza × 0.85 (tope 85%) |
| TRANCON detectado | confianza × 0.55 (tope 55%) |
| BUS_VARADO detectado | confianza × 0.25 (tope 25%) |
| Buses sin anomalía (≤3) | 10% |
| Buses sin anomalía (4-7) | 15% |
| Buses sin anomalía (≥8) | 20% |
| Sin datos | 0% |

### Scores de WhatsApp/TM

| Estado del evento | Score |
|-------------------|-------|
| activo (cierre, sin operar, bloqueo, protesta) | 100% |
| parcial (retrasos, operación parcial) | 40% |
| restablecido (normalización) | 15% |
| Sin alerta hoy pero con coincidencias | 60% |
| Sin datos | 0% |

### Scores de Firebase

| Reportes en zona | Score |
|-----------------|-------|
| 1 reporte | 25% |
| 2-3 reportes | 50% |
| 4-5 reportes | 70% |
| 6+ reportes | 85% |
| + palabras clave de riesgo | +10% (tope 90%) |
| Sin reportes | 0% |

### Scores de IA/Texto

| Alertas históricas | Score mínimo |
|-------------------|-------------|
| 1 alerta | 25% |
| 2-3 alertas | 45% |
| 4-6 alertas | 65% |
| 7+ alertas | 80% (tope 90%) |

### Niveles de Riesgo

| Probabilidad | Nivel | Color |
|-------------|-------|-------|
| 0-30% | bajo | Verde |
| 31-65% | medio | Amarillo |
| 66-100% | alto | Rojo |

---

## Endpoints de la API

Servidor en `http://localhost:8000`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Interfaz web principal (SPA) |
| `/health` | GET | Health check del servicio |
| `/docs` | GET | Swagger/OpenAPI |
| `/fuentes/estado` | GET | Estado de disponibilidad de las 4 fuentes |
| `/prediccion/integrada?zona=...` | GET | **Predicción integrada** con datos reales |
| `/chatbot` | POST | **Chatbot conversacional** con DeepSeek AI |
| `/whatsapp/tm/recientes?count=...` | GET | Mensajes recientes del canal WhatsApp/TM |
| `/anomalias/deteccion` | GET | Detección automática de anomalías (solo tracker) |
| `/anomalias/reportes` | GET | Reportes activos de usuarios (solo Firestore) |
| `/anomalias/ponderado` | GET | Combinación ponderada (detección + reportes + IA) |
| `/anomalias/grafica` | GET | Mapa PNG de anomalías |
| `/resumen` | GET | Resumen rápido del análisis ponderado |
| `/reportes/crear` | POST | Crear nuevo reporte de usuario |
| `/reportes/votar` | POST | Votar un reporte (positivo/negativo) |
| `/config/ponderado` | GET | Ver pesos actuales del ponderador |
| `/config/ponderado` | PUT | Actualizar pesos del ponderador |
| `/buses/grafica` | GET | Mapa PNG de buses activos |
| `/ia/prediccion` | POST | Predicción IA (NLP + reglas) |
| `/ia/prediccion/demo?zona=...` | GET | Predicción demo con textos de ejemplo |
| `/ia/prediccion/score?textos=...` | GET | Score de predicción IA |
| `/demo/crear-escenario` | POST | Crear escenario demo (alto/medio/bajo) |
| `/demo/limpiar` | POST | Limpiar datos demo |
| `/demo/estado` | GET | Estado actual del demo |
| `/monitoreo` | GET | Estado del monitoreo background |

---

## Comandos CLI

Ejecutar desde la raíz del proyecto:

```bash
python cli/main.py <comando> [opciones]
```

| Comando | Ejemplo | Descripción |
|---------|---------|-------------|
| `prueba` | `python cli/main.py prueba` | Probar conexión a la API de Transmilenio |
| `rutas` | `python cli/main.py rutas` | Listar todas las rutas cargadas del CSV |
| `analizar` | `python cli/main.py analizar --ruta 6-9 --grafica` | Análisis de trancones con gráfica |
| `monitorear` | `python cli/main.py monitorear --intervalo 30` | Monitoreo continuo cada 30s |
| `consultar` | `python cli/main.py consultar --limite 20 --json` | Últimas 20 posiciones en JSON |
| `ruta` | `python cli/main.py ruta --ruta B23` | Buses de la ruta B23 |
| `resumen` | `python cli/main.py resumen` | Resumen por ruta |
| `exportar` | `python cli/main.py exportar --archivo datos.json` | Exportar DB a JSON |
| `stats` | `python cli/main.py stats` | Estadísticas de la base de datos |
| `anomalias` | `python cli/main.py anomalias --json` | Detectar anomalías en JSON |

---

## Datos y Archivos

### `data/rutas.csv`
- **1265+ rutas** de Transmilenio
- Columnas: `Route_ID`, `Final_Destination`
- Cargado por `BusTracker.cargar_rutas_desde_csv()`
- Hay un duplicado en la raíz (`rutas.csv`) que puede eliminarse

### `data/buses.db` (SQLite)
- **Tabla `posiciones_buses`**: Historial de posiciones GPS con timestamp
- **Tabla `captura_actual`**: Última captura (sobrescrita cada escaneo)
- **Tabla `captura_anterior`**: Penúltima captura (para comparar velocidad)
- **Tabla `rutas_disponibles`**: Catálogo de rutas
- Crece con el tiempo de monitoreo

### `data/tm_alerts_sample.csv`
- **15 registros** de alertas históricas de TransMilenio
- Delimitador: `;`
- Encoding: `utf-8-sig`
- Columnas: fecha, hora, ubicacion, causa, estaciones_afectadas, servicios_afectados, desvios, usuarios_afectados, dia_semana, franja_horaria, etc.
- Usado por `ia/pattern_analysis.py` para análisis de patrones históricos
- Usado como fallback si Whapi.cloud no está configurado

### `data/graficos/`
- Carpeta con 13+ mapas PNG generados automáticamente
- Nomenclatura: `buses_YYYYMMDD_HHMMSS.png`, `anomalias_YYYYMMDD_HHMMSS.png`
- Generados al llamar `/buses/grafica` o `/anomalias/grafica`

### `config/ponderado.json`
- Pesos para el sistema de 3 fuentes (detección/reporte/predicción_ia)
- Deben sumar exactamente 1.0

### `data/serviceAccountKey.json`
- Credenciales de Firebase (gitignored)
- Requerido para la funcionalidad de reportes de usuarios
- Si no existe, el sistema funciona sin Firebase

---

## Scripts de Prueba y Verificación

### Scripts de prueba (`test_*.py`)

| Archivo | Descripción |
|---------|-------------|
| `test_anomalias_completo.py` | Pruebas completas del sistema de detección de anomalías |
| `test_buses_escenarios.py` | Pruebas de diferentes escenarios de buses |
| `test_chatbot.py` | Pruebas del chatbot y respuestas |
| `test_integracion_web.py` | Pruebas de integración del frontend web con la API |
| `test_pred.py` | Pruebas del sistema de predicción |
| `test_velocidad.py` | Pruebas del cálculo de velocidad de buses |

### Scripts de verificación (`check_*.py`)

| Archivo | Descripción |
|---------|-------------|
| `check_anomalias.py` | Verifica anomalías cerca de la Caracas con Calle 11 Sur (5km radio) |
| `check_api.py` | Verifica 3 endpoints: `/buses/ultimas_posiciones`, `/buses`, `/buses/posiciones` |
| `check_buses.py` | Inspecciona los campos disponibles en las posiciones de buses |
| `check_hist.py` | Verifica los datos históricos disponibles |
| `check_posicion.py` | Verifica las posiciones actuales de los buses |
| `check_speed.py` | Verifica el cálculo de velocidad de los buses |
| `debug_sim.py` | Depuración de simulación |

---

## Variables de Entorno (.env)

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `WHAPI_MODE` | No | `real` para activar Whapi.cloud |
| `WHAPI_TOKEN` | No* | Token de autenticación Whapi |
| `WHAPI_BASE_URL` | No* | URL base de Whapi (default: https://gate.whapi.cloud) |
| `WHAPI_TRANSMILENIO_CHANNEL_ID` | No* | ID del canal de WhatsApp de TM |
| `GOOGLE_MAPS_API_KEY` | Opcional | API Key de Google Maps para geocoding |
| `DEEPSEEK_API_KEY` | Opcional | API Key de DeepSeek para chatbot IA |
| `MODEL_MODE` | No | Modo del modelo (`rules`) |
| `ENVIRONMENT` | No | Entorno (`development`/`production`) |
| `PORT` | No | Puerto del servidor (default: 8000) |

\* Requerido solo si `WHAPI_MODE=real`

---

## Configuración del Análisis

Todos los parámetros de `config/config.py`:

### API Transmilenio
| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `API_CONFIG.appid` | `9a2c3b48...` | ID de aplicación para API TM |
| `API_CONFIG.uuid` | `32095e89...` | UUID del dispositivo |
| `API_CONFIG.version` | `27` | Versión de la app |
| `API_CONFIG.user_agent` | `okhttp/4.12.0` | User-Agent HTTP |
| `API_CONFIG.base_url` | `tmsa-transmiapp...` | URL de la API TM |

### Monitoreo
| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `MONITOR_INTERVAL` | 60 | Segundos entre escaneos |
| `DATABASE_PATH` | `data/buses.db` | Ruta de SQLite |
| `RUTAS_CSV` | `data/rutas.csv` | Ruta del CSV de rutas |

### Clustering y Densidad
| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `CLUSTER_RADIUS` | 100 | Radio de clustering en metros |
| `MIN_DISTANCE_ALERT` | 50 | Distancia mínima para alerta de proximidad (m) |
| `MIN_POS_CHANGE` | 10 | Cambio mínimo de posición para considerar movimiento (m) |
| `VELOCIDAD_LENTA` | 20 | Umbral de tráfico lento (km/h) |
| `VELOCIDAD_DETENIDO` | 5 | Umbral de bus detenido (km/h) |
| `ALERT_THRESHOLD` | 10 | Cantidad de buses para activar alerta de zona |
| `MOSTRAR_GRAFICA` | true | Generar gráficas durante monitoreo |

### Anomalías
| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `RADIO_EXCLUSION_PORTAL` | 300 | Radio de exclusión alrededor de portales (m) |
| `MINUTAS_INACTIVIDAD` | 5 | Minutos sin movimiento para considerar detenido |
| `TIEMPO_HISTORIAL_ANALISIS` | 60 | Minutos de historial a analizar |
| `NUM_CAPTURAS_HISTORIAL` | 60 | Capturas a guardar para análisis |
| `UMBRAL_MANIFESTACION` | 20 | Buses sin movimiento para manifestación |
| `UMBRAL_TRANCON` | 8 | Buses lentos para trancón |
| `RADIO_ANOMALIA` | 500 | Radio para clustering de anomalías (m) |
| `DISTANCIA_MAX_CLUSTER` | 300 | Distancia máxima entre buses consecutivos (m) |

### Portales (10)
Portal Norte, Portal 80, Portal Suba, Portal 20, Portal Sur, Portal Tunal, Portal Usme, Portal Américas, Portal El Dorado, Portal 20 de Julio.

### Logging
| Parámetro | Valor |
|-----------|-------|
| `LOG_LEVEL` | `INFO` |

---

## Zonas Reconocidas

El sistema reconoce las siguientes zonas con coordenadas, usadas por `ubicacion_buses/location_service.py`, `ia/risk_integrator.py` y `api/server.py`:

| Zona | Coordenadas | Radio (m) |
|------|-------------|-----------|
| Portal Eldorado | (4.6900, -74.1000) | 800 |
| Portal Norte | (4.7700, -74.0300) | 800 |
| Portal Sur | (4.4000, -74.1700) | 800 |
| Portal Américas | (4.6800, -74.1100) | 800 |
| Portal 20 de Julio | (4.4200, -74.1500) | 800 |
| Universidad Distrital sede La Macarena | (4.6070, -74.0700) | 500 |
| Universidad Pedagógica | (4.6350, -74.0800) | 500 |
| Avenida Caracas con Carrera 12B | (4.6100, -74.0800) | 500 |
| Avenida Caracas con Calle 6 | (4.5800, -74.0850) | 500 |
| Avenida Circunvalar con Calle 26 | (4.6200, -74.0550) | 500 |
| Carrera 5 con Calle 28 | (4.6050, -74.0650) | 500 |
| Carrera 7 con Calle 28 | (4.6070, -74.0680) | 500 |
| Calle 12B con Carrera 10 | (4.5950, -74.0750) | 500 |
| Carrera 10 con Calle 24 | (4.6000, -74.0730) | 500 |
| Calle 72 con Carrera 11 | (4.6550, -74.0500) | 500 |
| Carrera 30 con Avenida Chile | (4.6600, -74.0750) | 500 |

Además, `api/server.py` tiene ~50 alias adicionales en `ZONE_ALIASES` para reconocer variantes de nombres (ej: "la pedagogica", "u distrital", "caracas", "eldorado", "cra 5 cll 28", etc.)

---

## Escenarios Demo

El sistema incluye datos sintéticos para pruebas mediante `api/demo_service.py`:

| Intensidad | Buses | Velocidad | Reportes | Tipos |
|-----------|-------|-----------|----------|-------|
| **alto** | 6 | 3 km/h | 4 | paro, bloqueo, manifestación, congestión |
| **medio** | 3 | 8 km/h | 2 | congestión, desvío |
| **bajo** | 1 | 20 km/h | 1 | normal |

**Endpoints:**
- `POST /demo/crear-escenario` → `{"zona": "Portal Eldorado", "intensidad": "alto"}`
- `POST /demo/limpiar` → limpia todos los datos demo
- `GET /demo/estado` → estado actual de la demo

---

## Manejo de Errores y Degradación

El sistema está diseñado para funcionar con degradación elegante: si una fuente no está disponible, se indica claramente y la predicción se calcula solo con las fuentes disponibles.

| Escenario | Comportamiento |
|-----------|---------------|
| **Sin API TM** | `BusTracker` no captura buses → score buses = 0, tipo_dato = "sin_datos" |
| **Sin Whapi.cloud** | Usa `data/tm_alerts_sample.csv` como respaldo → score basado en histórico |
| **Sin Firebase** | Score firebase = 0, tipo_dato = "error" → no rompe la predicción |
| **Sin DeepSeek** | Usa `generar_respuesta_fallback()` → respuesta estructurada sin IA |
| **Sin Google Maps** | Usa `ZONE_ALIASES` para matching por texto → sin coordenadas precisas |
| **Sin serviceAccountKey.json** | Firebase no se inicializa → score firebase = 0 |
| **Sin buses en DB** | Score buses = 0, advertencia: "No hay buses reales recientes" |
| **Zona no reconocida** | Score general bajo, advertencia: "Zona no está en el catálogo" |
| **Error en fuente** | Score = 0, tipo_dato = "error", advertencia con mensaje del error |

---

## Notas Importantes

1. **Las credenciales de la API de Transmilenio** (`appid`, `uuid`) deben ser válidas en `config/config.py`. Sin ellas, el tracker no puede obtener posiciones de buses.
2. **El monitoreo se ejecuta en background** al iniciar el servidor con `python -m api.server`. Si no se inicia el tracker, no habrá datos de buses.
3. **`data/buses.db` crece con el tiempo.** Monitorear el tamaño si se ejecuta por períodos prolongados.
4. **Firebase requiere `data/serviceAccountKey.json`** válido. Este archivo está en `.gitignore` por seguridad.
5. **El sistema NUNCA crea datos falsos.** Si una fuente no tiene datos, lo indica explícitamente con `tipo_dato="sin_datos"` y una advertencia descriptiva.
6. **La predicción es una ESTIMACIÓN de riesgo, no una confirmación oficial.** Un score alto no garantiza que haya un paro o bloqueo real. Siempre consulte fuentes oficiales de TransMilenio.
7. **El chatbot usa DeepSeek AI** como opción principal. Si no hay API key configurada, usa un fallback que construye respuestas estructuradas con los datos disponibles.
8. **Zona horaria:** Todo el sistema de WhatsApp/TM usa `America/Bogota` (UTC-5).
9. **Caché:** El anomaly_detector tiene caché de 60s. El geocode_service tiene caché en memoria.
10. **Workers paralelos:** El BusTracker usa 40 workers simultáneos para escanear rutas. Ajustar según recursos del servidor.
11. **Los datos demo** (prefijo `DEMO_`) son filtrados y excluidos de todos los cálculos con datos reales.
12. **Las gráficas PNG** se acumulan en `data/graficos/`. Limpiar periódicamente si no se necesitan.
