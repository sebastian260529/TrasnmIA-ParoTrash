import csv

with open('data/tm_alerts_sample.csv', 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f, delimiter=';')

    print('=== ALERTAS CON CARACAS O 1 DE MAYO ===')
    for i, row in enumerate(reader):
        texto = row.get('texto_original', '')
        if 'caracas' in texto.lower() or '1 de mayo' in texto.lower():
            print('Alert', i+1)
            print('  Tipo:', row.get('tipo_evento', 'N/A'))
            print('  Ubicacion:', row.get('ubicacion', 'N/A'))
            print('  Texto:', texto[:150])
            print()