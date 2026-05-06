import re
import csv
from collections import Counter
from typing import Dict, List, Optional
from pathlib import Path


def load_alert_dataset(csv_path: str) -> List[Dict]:
    if not Path(csv_path).exists():
        return []
    
    alertas = []
    with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            for key in ['estaciones_afectadas', 'servicios_afectados', 'desvios']:
                raw_value = row.get(key, '')
                if raw_value:
                    items = [s.strip() for s in re.split(r'\s*\|\s*|\s*;\s*', raw_value) if s.strip()]
                    row[key] = items
                else:
                    row[key] = []
            
            usuarios = row.get('usuarios_afectados')
            if usuarios is not None:
                usuarios_str = str(usuarios).replace('.', '').replace(',', '')
                try:
                    row['usuarios_afectados'] = int(usuarios_str)
                except:
                    row['usuarios_afectados'] = 0
            else:
                row['usuarios_afectados'] = 0
            
            alertas.append(row)
    
    return alertas


def is_valid_pattern_value(value: Optional[str]) -> bool:
    invalid = {
        'No especificada', 'No especificado', 'No reportadas', 'No reportados',
        'No disponible', ''
    }
    return bool(value and str(value).strip() not in invalid)


def _calcular_puntaje_dia(dia_semana: str, csv_path: str) -> tuple:
    """
    Calcula puntos adicionales basados en la frecuencia histórica del día de la semana.
    Retorna: (puntos, explicacion)
    """
    if not dia_semana:
        return (0, "")
    
    alertas = load_alert_dataset(csv_path)
    
    if not alertas:
        return (0, "")
    
    dias_counter = Counter(
        a.get('dia_semana', '').lower().strip()
        for a in alertas
        if is_valid_pattern_value(a.get('dia_semana'))
    )
    
    if not dias_counter:
        return (0, "")
    
    dia_normalizado = dia_semana.lower().strip()
    total_alertas = sum(dias_counter.values())
    promedio = total_alertas / len(dias_counter) if dias_counter else 0
    
    if promedio == 0:
        return (0, "")
    
    alertas_dia = dias_counter.get(dia_normalizado, 0)
    ratio = alertas_dia / promedio if promedio > 0 else 0
    
    if ratio >= 1.5:
        puntos = 15
        explicacion = f"{dia_semana.capitalize()} históricamente tiene {int((ratio-1)*100)}% más alertas que el promedio"
    elif ratio >= 1.25:
        puntos = 10
        explicacion = f"{dia_semana.capitalize()} históricamente tiene {int((ratio-1)*100)}% más alertas que el promedio"
    elif ratio > 1.0:
        puntos = 5
        explicacion = f"{dia_semana.capitalize()} tiene más alertas que el promedio histórico"
    else:
        puntos = 0
        explicacion = ""
    
    return (puntos, explicacion)


def _calcular_descuento_dia_no_historico(
    dia_consulta: str, 
    csv_path: str, 
    ubicacion: Optional[str] = None,
    dia_usuario_especifico: bool = False
) -> tuple:
    """
    Calcula descuento si el día de consulta no coincide con el día histórico más frecuente.
    Solo aplica si el usuario NO especificó un día manualmente.
    Si hay ubicacion, filtra las alertas por esa zona específica.
    
    Retorna: (descuento, explicacion)
    """
    if dia_usuario_especifico:
        return (0, "")
    
    if not dia_consulta:
        return (0, "")
    
    alertas = load_alert_dataset(csv_path)
    
    if not alertas:
        return (0, "")
    
    if ubicacion:
        alertas = [a for a in alertas if ubicacion.lower() in a.get('ubicacion', '').lower()]
    
    if not alertas:
        return (0, "")
    
    dias_counter = Counter(
        a.get('dia_semana', '').lower().strip()
        for a in alertas
        if is_valid_pattern_value(a.get('dia_semana'))
    )
    
    if not dias_counter:
        return (0, "")
    
    dia_mas_historico = dias_counter.most_common(1)[0][0]
    alertas_dia_historico = dias_counter.get(dia_mas_historico, 0)
    
    if alertas_dia_historico == 0:
        return (0, "")
    
    dia_consulta_normalizado = dia_consulta.lower().strip()
    alertas_dia_consulta = dias_counter.get(dia_consulta_normalizado, 0)
    
    ratio = alertas_dia_consulta / alertas_dia_historico if alertas_dia_historico > 0 else 0
    
    descuento = 0
    explicacion = ""
    
    if ratio < 0.10:
        descuento = 30
        explicacion = f"Descuento: hoy ({dia_consulta.capitalize()}) tiene casi 0 alertas vs {dia_mas_historico.capitalize()} que tiene {alertas_dia_historico}"
    elif ratio < 0.25:
        descuento = 25
        explicacion = f"Descuento: hoy ({dia_consulta.capitalize()}) tiene {int(ratio*100)}% de alertas vs {dia_mas_historico.capitalize()}"
    elif ratio < 0.50:
        descuento = 20
        explicacion = f"Descuento: hoy ({dia_consulta.capitalize()}) tiene {int(ratio*100)}% de alertas vs {dia_mas_historico.capitalize()}"
    elif ratio < 0.75:
        descuento = 10
        explicacion = f"Descuento: hoy ({dia_consulta.capitalize()}) tiene menos alertas que {dia_mas_historico.capitalize()}"
    
    return (descuento, explicacion)


def analyze_patterns(csv_path: str) -> Dict:
    alertas = load_alert_dataset(csv_path)
    
    if not alertas:
        return {
            "total_alertas": 0,
            "dias_con_mas_alertas": [],
            "ubicaciones_mas_frecuentes": [],
            "causas_mas_frecuentes": [],
            "estaciones_mas_afectadas": [],
            "servicios_mas_afectados": [],
            "franjas_horarias_mas_frecuentes": [],
            "usuarios_afectados_total": 0,
            "promedio_usuarios_afectados": 0,
            "conclusiones": ["No hay datos para analizar"]
        }
    
    dias_counter = Counter(a.get('dia_semana') for a in alertas if is_valid_pattern_value(a.get('dia_semana')))
    ubicaciones_counter = Counter(
        a.get('ubicacion_normalizada') or a.get('ubicacion')
        for a in alertas
        if is_valid_pattern_value(a.get('ubicacion_normalizada') or a.get('ubicacion'))
    )
    causas_counter = Counter(a.get('causa') for a in alertas if is_valid_pattern_value(a.get('causa')))
    franjas_counter = Counter(a.get('franja_horaria') for a in alertas if is_valid_pattern_value(a.get('franja_horaria')))
    
    estaciones = []
    servicios = []
    for a in alertas:
        estaciones.extend([e for e in a.get('estaciones_afectadas', []) if is_valid_pattern_value(e)])
        servicios.extend([s for s in a.get('servicios_afectados', []) if is_valid_pattern_value(s)])
    
    estaciones_counter = Counter(estaciones)
    servicios_counter = Counter(servicios)
    
    usuarios_total = sum(int(a.get('usuarios_afectados', 0) or 0) for a in alertas)
    promedio_usuarios = usuarios_total / len(alertas) if alertas else 0
    
    conclusiones = []
    if dias_counter:
        dia_mas = dias_counter.most_common(1)[0][0]
        conclusiones.append(f"El día con más alertas es {dia_mas}")
    
    if ubicaciones_counter:
        ubicacion_mas = ubicaciones_counter.most_common(1)[0][0]
        conclusiones.append(f"La ubicación más afectada es {ubicacion_mas}")
    
    if causas_counter:
        causa_mas = causas_counter.most_common(1)[0][0]
        conclusiones.append(f"La causa más frecuente es {causa_mas}")
    
    if promedio_usuarios > 10000:
        conclusiones.append("Las alertas afectan a muchos usuarios en promedio")
    
    return {
        "total_alertas": len(alertas),
        "dias_con_mas_alertas": [d[0] for d in dias_counter.most_common(5)],
        "ubicaciones_mas_frecuentes": [u[0] for u in ubicaciones_counter.most_common(5)],
        "causas_mas_frecuentes": [c[0] for c in causas_counter.most_common(5)],
        "estaciones_mas_afectadas": [e[0] for e in estaciones_counter.most_common(5)],
        "servicios_mas_afectados": [s[0] for s in servicios_counter.most_common(5)],
        "franjas_horarias_mas_frecuentes": [f[0] for f in franjas_counter.most_common(4)],
        "usuarios_afectados_total": usuarios_total,
        "promedio_usuarios_afectados": round(promedio_usuarios, 2),
        "conclusiones": conclusiones
    }


def predict_risk_from_patterns(
    csv_path: str,
    ubicacion: Optional[str] = None,
    dia_semana: Optional[str] = None,
    tipo_evento: Optional[str] = None
) -> Dict:
    from datetime import datetime
    
    alertas = load_alert_dataset(csv_path)

    dia_actual = None
    dia_usuario_especifico = False
    if not dia_semana:
        dias_map = {
            0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
            4: "viernes", 5: "sabado", 6: "domingo"
        }
        dia_actual = dias_map.get(datetime.now().weekday())
        dia_semana = dia_actual
    else:
        dia_usuario_especifico = True

    if not alertas:
        return {
            "ubicacion": ubicacion or "general",
            "probabilidad": 10,
            "nivel_riesgo": "bajo",
            "patrones_detectados": [],
            "explicacion": ["No hay datos históricos para analizar."]
        }

    if ubicacion:
        filtered_alertas = [a for a in alertas if ubicacion.lower() in a.get('ubicacion', '').lower()]
    else:
        filtered_alertas = alertas

    if dia_semana:
        filtered_alertas = [
            a for a in filtered_alertas
            if str(a.get("dia_semana", "")).lower() == dia_semana.lower()
        ]

    if tipo_evento:
        filtered_alertas = [
            a for a in filtered_alertas
            if tipo_evento.lower() in str(a.get("tipo_evento", "")).lower()
        ]

    if not filtered_alertas:
        return {
            "ubicacion": ubicacion or "general",
            "probabilidad": 10,
            "nivel_riesgo": "bajo",
            "patrones_detectados": [],
            "explicacion": ["No hay suficientes registros históricos."]
        }

    alertas_ubicacion = len(filtered_alertas)
    puntaje_total = 0
    patrones_detectados = []

    if alertas_ubicacion == 1:
        puntaje_total += 15
    elif alertas_ubicacion == 2:
        puntaje_total += 25
    elif alertas_ubicacion <= 5:
        puntaje_total += 35
    elif alertas_ubicacion <= 10:
        puntaje_total += 45
    else:
        puntaje_total += 55

    patrones_detectados.append(f"Se encontraron {alertas_ubicacion} alertas.")

    tipo_evento_map = {
        'manifestación': 25,
        'manifestacion': 25,
        'protesta': 25,
        'bloqueo': 25,
        'cierre': 20,
        'sin operar': 20,
        'desvío': 18,
        'desvio': 18,
        'siniestro vial': 15,
        'tormenta': 12,
        'congestión': 10,
        'retrasos': 10,
        'novedad operacional': 8,
        'normalización': 3,
    }

    max_evento_puntaje = 0
    tipo_evento_detectado = None

    for alerta in filtered_alertas:
        causa = str(alerta.get('causa', '')).lower().strip()
        for evento_key, puntaje in tipo_evento_map.items():
            if evento_key in causa:
                if puntaje > max_evento_puntaje:
                    max_evento_puntaje = puntaje
                    tipo_evento_detectado = evento_key

    puntaje_total += max_evento_puntaje
    if tipo_evento_detectado:
        patrones_detectados.append(f"Evento: {tipo_evento_detectado}.")

    usuarios_con_dato = [int(a.get('usuarios_afectados', 0) or 0) for a in filtered_alertas if int(a.get('usuarios_afectados', 0) or 0) > 0]
    usuarios_promedio = sum(usuarios_con_dato) / len(usuarios_con_dato) if usuarios_con_dato else 0

    puntaje_usuarios = 0
    if usuarios_promedio > 50000:
        puntaje_usuarios = 20
    elif usuarios_promedio > 20000:
        puntaje_usuarios = 15
    elif usuarios_promedio > 5000:
        puntaje_usuarios = 10

    puntaje_total += puntaje_usuarios
    if usuarios_promedio > 0:
        patrones_detectados.append(f"Usuarios afectados promedio: {int(usuarios_promedio)}.")

    franjas = Counter(a.get('franja_horaria') for a in filtered_alertas if is_valid_pattern_value(a.get('franja_horaria')))
    if franjas:
        franja_mas_comun = franjas.most_common(1)[0][0]
        patrones_detectados.append(f"Franja: {franja_mas_comun}.")

    servicios = [s for a in filtered_alertas for s in a.get('servicios_afectados', []) if is_valid_pattern_value(s)]
    estaciones = [e for a in filtered_alertas for e in a.get('estaciones_afectadas', []) if is_valid_pattern_value(e)]

    puntos_dia, explicacion_dia = _calcular_puntaje_dia(dia_semana, csv_path)
    if puntos_dia > 0:
        puntaje_total += puntos_dia
        patrones_detectados.append(explicacion_dia)

    descuento, explicacion_descuento = _calcular_descuento_dia_no_historico(
        dia_semana, csv_path, ubicacion, dia_usuario_especifico
    )
    if descuento > 0:
        puntaje_total -= descuento
        patrones_detectados.append(explicacion_descuento)

    probabilidad = min(95, max(0, puntaje_total))

    if probabilidad >= 66:
        nivel_riesgo = "alto"
    elif probabilidad >= 31:
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "bajo"

    return {
        "ubicacion": ubicacion or "general",
        "probabilidad": probabilidad,
        "nivel_riesgo": nivel_riesgo,
        "patrones_detectados": patrones_detectados,
        "explicacion": [f"Predicción basada en {alertas_ubicacion} alertas. Riesgo: {nivel_riesgo} ({probabilidad}%)"]
    }