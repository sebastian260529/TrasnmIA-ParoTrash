import sqlite3

conn = sqlite3.connect('data/buses.db')
cursor = conn.cursor()

# Ver estructura y valores de posicion
cursor.execute("SELECT bus_id, posicion, latitud, longitud, timestamp FROM posiciones_buses LIMIT 20")
results = cursor.fetchall()

print('=== MUESTRA DE POSICIONES ===')
for r in results:
    print(f'Bus: {r[0]}, Posicion: {r[1]}, Lat: {r[2]}, Lon: {r[3]}, Time: {r[4]}')

print()

# Ver diferencias de posicion para un mismo bus
cursor.execute("""
    SELECT posicion, timestamp
    FROM posiciones_buses
    WHERE bus_id = (SELECT bus_id FROM posiciones_buses LIMIT 1)
    ORDER BY timestamp DESC
    LIMIT 10
""")
posiciones = cursor.fetchall()

print('=== ULTIMAS POSICIONES DE UN BUS ===')
for p in posiciones:
    print(f'Posicion: {p[0]}, Time: {p[1]}')

conn.close()