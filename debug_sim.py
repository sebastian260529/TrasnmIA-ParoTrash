import csv
import os
import re
import unicodedata

def _normalize_text(text):
    text = text.lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def similarity_jaccard(s1, s2):
    s1 = _normalize_text(s1)
    s2 = _normalize_text(s2)
    if not s1 or not s2:
        return 0.0
    set1 = set(s1.split())
    set2 = set(s2.split())
    if not set1 or not set2:
        return 0.0
    interseccion = len(set1 & set2)
    union = len(set1 | set2)
    return interseccion / union if union > 0 else 0.0

texto_buscar = "Avenida 1 de Mayo con Avenida Caracas"

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, "data", "tm_alerts_sample.csv")

print('=== SIMILARITY DEBUG ===')
print('Texto buscar:', texto_buscar)
print()

with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f, delimiter=';')
    for i, row in enumerate(reader):
        texto = row.get('texto_original', '') or row.get('contenido', '')
        score = similarity_jaccard(texto_buscar, texto)
        print('Alert', i+1, '- Score:', round(score, 2))
        print(' Texto:', texto[:80])
        print(' Match >= 0.7?', 'SI' if score >= 0.7 else 'NO')
        print()