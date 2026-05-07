import requests

resp = requests.post('http://localhost:8000/chatbot', json={
    'pregunta': 'como esta la universidad pedagogica',
    'zona': ''
}, timeout=60)

data = resp.json()

with open('respuesta_chatbot.txt', 'w', encoding='utf-8') as f:
    f.write("Probabilidad: " + str(data.get('probabilidad')) + "%\n")
    f.write("Zona: " + data.get('zona') + "\n\n")
    f.write(data.get('respuesta', ''))

print("Done")