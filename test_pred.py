import requests

# Get reportes desde Firebase
resp = requests.get('http://localhost:8000/anomalias/reportes', timeout=10)
data = resp.json()

print('=== REPORTES EN FIREBASE ===')
print('Total:', data.get('total', 0))
print()

reportes = data.get('reportes', [])
for r in reportes[:5]:
    print('- Tipo:', r.get('tipo'))
    print('  Ubicacion:', r.get('ubicacion'))
    print('  ID:', r.get('id'))
    print()