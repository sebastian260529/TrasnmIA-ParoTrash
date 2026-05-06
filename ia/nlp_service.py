import re
from typing import Dict, List


class NLPService:
    PALABRAS_CLAVE = {
        'paro': ['paro', 'huelga', 'paro nacional', 'paro indefinido'],
        'bloqueo': ['bloqueo', 'bloqueada', 'bloqueado', 'vía cerrada', 'cierre'],
        'manifestacion': ['manifestación', 'protesta', 'marcha', 'disturbio'],
        'accidente': ['accidente', 'choque', 'colisión'],
        'transporte_publico': ['transmilenio', 'sitp', 'estación', 'portal', 'bus', 'transporte'],
        'trafico_normal': ['trancón', 'congestión', 'retrasos', 'tráfico', 'movilidad afectada']
    }

    @staticmethod
    def procesar_texto(texto: str) -> str:
        texto = texto.lower()
        texto = re.sub(r'[^\w\s]', '', texto)
        return texto.strip()

    @staticmethod
    def detectar_palabras_clave(textos: List[str]) -> List[str]:
        palabras_detectadas = []
        for texto in textos:
            texto_procesado = NLPService.procesar_texto(texto)
            for categoria, palabras in NLPService.PALABRAS_CLAVE.items():
                for palabra in palabras:
                    if palabra in texto_procesado:
                        palabras_detectadas.append(palabra)
        return list(set(palabras_detectadas))

    @staticmethod
    def clasificar_por_categorias(textos: List[str]) -> Dict[str, int]:
        categorias = {}
        for texto in textos:
            texto_procesado = NLPService.procesar_texto(texto)
            for categoria, palabras in NLPService.PALABRAS_CLAVE.items():
                for palabra in palabras:
                    if palabra in texto_procesado:
                        categorias[categoria] = categorias.get(categoria, 0) + 1
        return categorias