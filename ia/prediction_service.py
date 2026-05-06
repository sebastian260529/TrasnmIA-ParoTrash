from typing import List
from ia.nlp_service import NLPService
from ia.expert_rules_service import ExpertRulesService
from ia.schemas import PrediccionRequest, PrediccionResponse, FuentesAnalizadas


class PredictionService:
    def __init__(self):
        self.nlp_service = NLPService()
        self.expert_rules = ExpertRulesService()

    def predecir_riesgo(self, request: PrediccionRequest) -> PrediccionResponse:
        textos_publicaciones = request.publicaciones
        textos_reportes = [reporte.descripcion for reporte in request.reportes_app]
        todos_los_textos = textos_publicaciones + textos_reportes

        palabras_clave = self.nlp_service.detectar_palabras_clave(todos_los_textos)

        probabilidad = self.expert_rules.calcular_probabilidad(
            palabras_clave,
            len(textos_publicaciones),
            len(textos_reportes),
            sum(r.confirmaciones for r in request.reportes_app),
            sum(r.descartes for r in request.reportes_app)
        )

        if probabilidad <= 30:
            nivel_riesgo = "bajo"
        elif probabilidad <= 60:
            nivel_riesgo = "medio"
        else:
            nivel_riesgo = "alto"

        explicacion = self._generar_explicacion(probabilidad, palabras_clave, len(textos_publicaciones), len(textos_reportes))
        recomendaciones = self._generar_recomendaciones(nivel_riesgo)

        fuentes = FuentesAnalizadas(
            publicaciones=len(textos_publicaciones),
            reportes_app=len(textos_reportes)
        )

        return PrediccionResponse(
            zona=request.zona,
            probabilidad=probabilidad,
            nivel_riesgo=nivel_riesgo,
            palabras_clave_detectadas=palabras_clave,
            explicacion=explicacion,
            recomendaciones=recomendaciones,
            fuentes_analizadas=fuentes
        )

    def _generar_explicacion(self, probabilidad: int, palabras_clave: list, num_publicaciones: int, num_reportes: int) -> List[str]:
        explicacion = []
        if probabilidad > 60:
            explicacion.append("Alto riesgo detectado debido a palabras clave relacionadas con paros y bloqueos.")
        elif probabilidad > 30:
            explicacion.append("Riesgo medio por posibles alteraciones en la movilidad.")
        else:
            explicacion.append("Riesgo bajo, movilidad aparentemente normal.")

        if palabras_clave:
            explicacion.append(f"Palabras clave detectadas: {', '.join(palabras_clave)}")

        explicacion.append(f"Fuentes analizadas: {num_publicaciones} publicaciones, {num_reportes} reportes de app.")
        return explicacion

    def _generar_recomendaciones(self, nivel_riesgo: str) -> List[str]:
        if nivel_riesgo == "bajo":
            return ["Monitorear la zona regularmente."]
        elif nivel_riesgo == "medio":
            return ["Revisar rutas alternas.", "Consultar actualizaciones en tiempo real."]
        else:
            return ["Evitar la zona si es posible.", "Buscar transporte alternativo.", "Seguir reportes oficiales."]

    def predecir_con_textos(self, zona: str, textos: List[str]) -> PrediccionResponse:
        request = PrediccionRequest(zona=zona, publicaciones=textos, reportes_app=[])
        return self.predecir_riesgo(request)