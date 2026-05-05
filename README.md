# Sistema de Monitoreo de Buses Transmilenio

Sistema en Python para monitorear buses de Transmilenio en tiempo real y guardar sus ubicaciones en SQLite.

## Estructura del Proyecto

```
├── config.py        # Configuración (credenciales, rutas, intervalo)
├── bus_tracker.py  # Módulo principal de monitoreo
├── database.py     # Base de datos SQLite
├── main.py         # Interfaz CLI
├── requirements.txt
└── README.md
```

## Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

Editar `config.py` para configurar:

1. **Credenciales de la API** (buscar en la app TransMiApp o inspectores):
```python
API_CONFIG = {
    "appid": "transmiapp_2",
    "uuid": "tu_uuid_aqui",
    "version": "27",
    "user_agent": "TransmiApp/27 ...",
}
```

2. **Rutas a monitorear** (agregar más buses):
```python
RUTAS = [
    {"ruta": "6-9", "nombre": "Arborizadora Alta"},
    {"ruta": "6-9", "nombre": "Portal Tunal"},
    {"ruta": "7-1", "nombre": "Portal Americas"},
    # Agregar más...
]
```

3. **Intervalo de monitoreo** (en segundos):
```python
MONITOR_INTERVAL = 60
```

## Comandos

### 1. Probar conexión
```bash
python main.py prueba
```
Expected: Muestra si la conexión es exitosa y cuántos buses hay activos.

### 2. Iniciar monitoreo continuo
```bash
python main.py monitorear
```
- Captura ubicaciones cada X segundos (configurable)
- Presionar `Ctrl+C` para detener limpiamente
- Guarda cada captura en la base de datos SQLite

### 3. Ver últimas ubicaciones
```bash
python main.py consultar
python main.py consultar --limite 20  # últimos 20 registros
```

### 4. Ver trayectoria de un bus específico
```bash
python main.py consultar --bus-id 24224 --horas 2
```
Muestra todas las posiciones del bus en las últimas 2 horas.

### 5. Ver buses de una ruta específica
```bash
python main.py ruta --ruta 6-9
```

### 6. Resumen por ruta
```bash
python main.py resumen
```
Muestra cuántos buses activos hay por cada ruta.

### 7. Exportar datos a JSON
```bash
python main.py exportar
python main.py exportar --archivo mis_buses.json
```

### 8. Estadísticas
```bash
python main.py stats
```

## Base de Datos

Los datos se guardan automáticamente en `buses.db` con esta estructura:

| Campo | Descripción |
|-------|--------------|
| bus_id | ID único del bus |
| ruta | Código de ruta (ej: 6-9) |
| nombre_bus | Nombre del destino |
| latitud | Latitud GPS |
| longitud | Longitud GPS |
| velocidad | Velocidad (si está disponible) |
| timestamp | Fecha/hora del registro |
| respuesta_json | Respuesta completa para debug |

## Agregar Nuevas Rutas

Para agregar más rutas, editar `config.py`:

```python
RUTAS = [
    {"ruta": "6-9", "nombre": "Arborizadora Alta"},
    {"ruta": "6-9", "nombre": "Portal Tunal"},
    {"ruta": "B1", "nombre": "Portal Norte"},
    {"ruta": "B2", "nombre": "Portal Sur"},
    {"ruta": "M82", "nombre": "Santa Bibiana"},
    # Agregar más buses/rutas...
]
```

## Notas Importantes

1. Las credenciales (`appid`, `uuid`) deben ser válidas. Si no funcionan, obtenerlas de la app TransMiApp (usar un inspector de red para ver las requests).

2. El código detecta automáticamente las coordenadas en múltiples formatos.

3. El monitoreo se ejecuta en un loop infinito que se detiene con `Ctrl+C` (guardando los datos antes de salir).

4. La base de datos crece con el tiempo. Para ver tamaño: `python main.py stats`

## Solución de Problemas

**Error de conexión:**
- Verificar que las credenciales en `config.py` sean correctas
- Verificar conexión a internet

**No hay buses:**
- Es normal en horas de poco tráfico
- Verificar que la ruta y nombre sean correctos

**SQLite error:**
- Verificar permisos de escritura en el directorio
- La base de datos se crea automáticamente

---

*Sistema creado para monitoreo de buses Transmilenio - Bogotá, Colombia*