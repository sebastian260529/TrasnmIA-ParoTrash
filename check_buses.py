import requests

resp = requests.get('http://localhost:8000/buses/ultimas_posiciones?limite=5', timeout=10)
data = resp.json()

print('=== CAMPOS DE BUSES ===')
print()

buses = data.get('buses', [])
if buses:
    print('Campos disponibles:', list(buses[0].keys()))
    print()
    print('Primer bus:')
    for k, v in buses[0].items():
        print(f'  {k}: {v}')
else:
    print('No hay buses')