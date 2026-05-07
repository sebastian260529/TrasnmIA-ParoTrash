import requests
import math

resp = requests.get('http://localhost:8000/anomalias/deteccion', timeout=10)
data = resp.json()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

target_lat = 4.5856403
target_lon = -74.09441

anomalias = data.get('anomalias', [])
print('=== ANOMALIAS CERCA DE LA CARACAS CON 11 SUR ===')
print('Coord objetivo:', target_lat, ',', target_lon)
print()

# Encontrar anomalías en radio de 5km
cercanas = []
for a in anomalias:
    coords = a.get('coordenadas', {})
    lat = coords.get('latitud')
    lon = coords.get('longitud')
    if lat and lon:
        dist = haversine(target_lat, target_lon, lat, lon)
        if dist <= 5000:
            item = {
                'tipo': a.get('tipo'),
                'buses': a.get('buses_involucrados'),
                'dist_km': dist / 1000,
                'lat': lat,
                'lon': lon
            }
            cercanas.append(item)

if cercanas:
    print('Se encontraron anomalias en radio de 5km:')
    for c in sorted(cercanas, key=lambda x: x['dist_km']):
        print(' -', c['tipo'], '-', c['buses'], 'buses -', round(c['dist_km'], 1), 'km')
else:
    print('No hay anomalias en radio de 5km')

print()
print('=== TOTAL ANOMALIAS EN SISTEMA:', len(anomalias), '===')
tipos = {}
for a in anomalias:
    t = a.get('tipo')
    tipos[t] = tipos.get(t, 0) + 1
for t, c in tipos.items():
    print('  ', t, ':', c)