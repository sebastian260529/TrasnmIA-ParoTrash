from typing import List


class ExpertRulesService:
    def calcular_probabilidad(self, palabras_clave: List[str], num_publicaciones: int,
                            num_reportes: int, confirmaciones_total: int, descartes_total: int) -> int:
        puntaje = 0

        palabras_alto_riesgo = ['paro', 'bloqueo', 'bloqueada', 'bloqueado', 'cierre']
        palabras_medio_riesgo = ['manifestación', 'protesta', 'marcha', 'disturbio']
        palabras_bajo_riesgo = ['trancón', 'congestión', 'retrasos']

        for palabra in palabras_clave:
            if palabra in palabras_alto_riesgo:
                puntaje += 30
            elif palabra in palabras_medio_riesgo:
                puntaje += 20
            elif palabra in palabras_bajo_riesgo:
                puntaje += 5

        if num_publicaciones > 5:
            puntaje += 15
        elif num_publicaciones > 2:
            puntaje += 10

        if num_reportes > 3:
            puntaje += 15
        elif num_reportes > 1:
            puntaje += 10

        if confirmaciones_total > descartes_total * 2:
            puntaje += 20
        elif descartes_total > confirmaciones_total:
            puntaje -= 10

        return max(0, min(100, puntaje))