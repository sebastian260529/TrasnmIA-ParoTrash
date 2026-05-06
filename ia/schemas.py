from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ReporteAppInput(BaseModel):
    tipo: str
    descripcion: str
    confirmaciones: int = 0
    descartes: int = 0


class PrediccionRequest(BaseModel):
    zona: str
    publicaciones: List[str] = []
    reportes_app: List[ReporteAppInput] = []


class FuentesAnalizadas(BaseModel):
    publicaciones: int = 0
    reportes_app: int = 0


class PrediccionResponse(BaseModel):
    zona: str
    probabilidad: int
    nivel_riesgo: str
    palabras_clave_detectadas: List[str] = []
    explicacion: List[str] = []
    recomendaciones: List[str] = []
    fuentes_analizadas: FuentesAnalizadas


class ChatbotRequest(BaseModel):
    pregunta: str
    zona: str = "Bogotá"
    publicaciones: List[str] = []
    reportes_app: List[ReporteAppInput] = []


class ChatbotResponse(BaseModel):
    respuesta: str
    probabilidad: int
    nivel_riesgo: str


class TransMilenioAlertRequest(BaseModel):
    texto: str
    fecha: Optional[str] = None
    fuente: str = "WhatsApp TransMilenio"


class TransMilenioAlertResponse(BaseModel):
    fecha: Optional[str] = None
    hora_publicacion: Optional[str] = None
    hora_inicio: Optional[str] = None
    ubicacion: Optional[str] = None
    causa: str = "Novedad operacional"
    estaciones_afectadas: List[str] = []
    servicios_afectados: List[str] = []
    desvios: List[str] = []
    usuarios_afectados: Optional[int] = None
    fuente: str = "WhatsApp TransMilenio"
    texto_original: str = ""


class WhapiPredictionResponse(BaseModel):
    modo: str
    alertas: List[TransMilenioAlertResponse]
    prediccion: Dict[str, Any]
    error: Optional[str] = None