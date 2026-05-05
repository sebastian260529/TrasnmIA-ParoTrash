"""
Script de prueba para debuggear la API de Transmilenio.
Muestra exactamente qué se envía y qué se recibe.
"""

import requests
import json
from src.config import API_CONFIG, RUTAS_CSV

# Cargar una ruta de prueba
import csv
with open(RUTAS_CSV, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rutas = list(reader)

# Tomar primera ruta con datos
ruta_test = None
for r in rutas:
    if r.get('Route_ID') and r.get('Final_Destination'):
        ruta_test = r
        break

if not ruta_test:
    print("No hay rutas en el CSV")
    exit(1)

print("=" * 60)
print("DATOS DE PRUEBA:")
print("=" * 60)
print(f"Ruta: {ruta_test.get('Route_ID')}")
print(f"Destino: {ruta_test.get('Final_Destination')}")
print()

# Construir petición
url = f"{API_CONFIG['base_url']}/buses"
headers = {
    "appid": API_CONFIG["appid"],
    "uuid": API_CONFIG["uuid"],
    "version": API_CONFIG["version"],
    "user-agent": API_CONFIG["user_agent"],
    "Content-Type": "application/json"
}
payload = {
    "ruta": ruta_test.get('Route_ID'),
    "nombre": ruta_test.get('Final_Destination')
}

print("=" * 60)
print("PETICIÓN:")
print("=" * 60)
print(f"URL: {url}")
print()
print("HEADERS:")
for k, v in headers.items():
    print(f"  {k}: {v}")
print()
print("PAYLOAD (JSON):")
print(json.dumps(payload, indent=2, ensure_ascii=False))
print()

print("=" * 60)
print("RESPUESTA:")
print("=" * 60)

try:
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    print(f"Reason: {response.reason}")
    print()
    print("Response Headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    print()
    
    if response.status_code == 200:
        datos = response.json()
        print("Body (JSON):")
        print(json.dumps(datos, indent=2, ensure_ascii=False)[:2000])
    else:
        print("Response Text:")
        print(response.text[:1000])
        
except Exception as e:
    print(f"ERROR: {e}")