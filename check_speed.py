import requests

resp = requests.get('http://localhost:8000/buses/ultimas_posiciones?limite=30', timeout=10)
data = resp.json()

print('=== VELOCIDADES DE BUSES (muestreo de 30) ===')
print()

buses = data.get('buses', [])
velocidades = []
for b in buses:
    vel = b.get('velocidad')
    if vel is not None:
        velocidades.append(vel)
        print(f"Bus {b.get('id')}: {vel} km/h - {b.get('ruta', 'sin ruta')}")

print()
print('Estadisticas:')
print('  Min:', min(velocidades) if velocidades else 0)
print('  Max:', max(velocidades) if velocidades else 0)
print('  Promedio:', round(sum(velocidades)/len(velocidades), 1) if velocidades else 0)