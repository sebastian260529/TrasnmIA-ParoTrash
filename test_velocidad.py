import requests
import time

time.sleep(6)

print('=== TEST VELOCIDAD CORREGIDA ===')

# Ver estado anomalias
resp = requests.get('http://localhost:8000/anomalias/deteccion', timeout=10)
data = resp.json()
resumen = data.get('resumen', {})
print('Buses activos:', data.get('buses_activos'))
print('Velocidad promedio:', resumen.get('velocidad_promedio_kmh', 0), 'km/h')
print('Buses lentos:', resumen.get('buses_lentos'))
print('Buses sin movimiento:', resumen.get('buses_sin_movimiento'))

print()
anomalias = data.get('anomalias', [])
print('Anomalias:', len(anomalias))
for a in anomalias[:3]:
    print(' -', a['tipo'], ':', a['porcentaje_confianza'], '% (', a['buses_involucrados'], 'buses)')

print()
# Test predicción
zonas = ['Avenida Caracas', 'Portal Eldorado']
for zona in zonas:
    resp = requests.get('http://localhost:8000/prediccion/integrada?zona=' + zona.replace(' ', '%20'), timeout=10)
    data = resp.json()
    print(zona + ':', data.get('probabilidad'), '% - Score buses:', data.get('fuentes', {}).get('buses', {}).get('score'))