import requests

print('=== CHECK API ENDPOINTS ===')

endpoints = [
    '/buses/ultimas_posiciones',
    '/buses',
    '/buses/posiciones'
]

for ep in endpoints:
    try:
        resp = requests.get('http://localhost:8000' + ep + '?limite=5', timeout=5)
        print(ep + ': status=' + str(resp.status_code))
        if resp.status_code == 200:
            data = resp.json()
            print('   Keys: ' + str(list(data.keys())))
            if 'buses' in data:
                print('   Buses: ' + str(len(data.get('buses', []))))
            if 'data' in data:
                print('   Data: ' + str(len(data.get('data', []))))
    except Exception as e:
        print(ep + ': error - ' + str(e))