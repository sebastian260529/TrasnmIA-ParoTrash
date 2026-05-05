import re
import unicodedata
from typing import List, Optional


class TMAlertParserService:
    @staticmethod
    def normalize_text(texto: str) -> str:
        if not texto:
            return ""
        texto = unicodedata.normalize("NFC", str(texto))
        texto = texto.replace("\u00a0", " ")
        texto = texto.replace("*", "")
        texto = re.sub(r"[\r\n\t]+", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()

    @staticmethod
    def _to_24h(match: re.Match) -> str:
        hora = int(match.group("h"))
        minuto = int(match.group("m"))
        ampm = match.group("ampm").lower()

        if "p" in ampm and hora != 12:
            hora += 12
        if "a" in ampm and hora == 12:
            hora = 0

        return f"{hora:02d}:{minuto:02d}"

    def extract_time(self, texto: str) -> Optional[str]:
        if not texto:
            return None

        normalized = self.normalize_text(texto).lower()
        normalized = normalized.replace("'", "'")
        normalized = re.sub(r"\s+", "", normalized)

        normalized = normalized.replace("a.m.", "am").replace("p.m.", "pm")
        normalized = normalized.replace("a.m", "am").replace("p.m", "pm")
        normalized = normalized.replace("am.", "am").replace("pm.", "pm")
        normalized = normalized.replace("a m", "am").replace("p m", "pm")

        match = re.search(
            r"(?P<h>\d{1,2})[:\.](?P<m>\d{2})(?P<ampm>am|pm)",
            normalized,
            re.I,
        )
        if match:
            return self._to_24h(match)

        match = re.search(r"(?P<h>[01]?\d|2[0-3]):(?P<m>[0-5]\d)", normalized)
        if match:
            return f"{int(match.group('h')):02d}:{match.group('m')}"

        return None

    def extract_affected_users(self, texto: str) -> Optional[int]:
        if not texto:
            return None

        texto = self.normalize_text(texto)

        match = re.search(
            r"(?:usuarios afectados|usuarios aproximados|personas afectadas|personas usuarias afectadas)\s*[:\-]?\s*([\d\.]+)",
            texto,
            re.I,
        )

        if not match:
            return None

        digits = re.sub(r"\D", "", match.group(1))
        if not digits:
            return None

        try:
            return int(digits)
        except ValueError:
            return None

    def extract_location(self, texto: str) -> Optional[str]:
        if not texto:
            return None

        texto = self.normalize_text(texto)
        texto = re.sub(r'[^\x00-\x7F]+', '', texto)

        texto = re.sub(r"(?i)actualización", " ", texto)
        texto = re.sub(r"(?i)#tmahora", " ", texto)
        texto = re.sub(r"(?i)usuarios afectados[:\s-\d\.,]*", " ", texto)
        texto = re.sub(r"(?i)usuarios aproximados[:\s-\d\.,]*", " ", texto)
        texto = re.sub(r"(?i)personas afectadas[:\s-\d\.,]*", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()

        patterns = [
            r"((?:Portal)\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+?)(?=[\.,;:]|$)",
            r"((?:Estación|Estacion)\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+?)(?=[\.,;:]|$)",
            r"((?:Universidad)\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+?)(?=[\.,;:]|$)",
            r"((?:Avenida|Av\.?|AV\.?|Avda\.?|Avd\.?)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?(?:\s+con\s+(?:Avenida|Av\.?|Carrera|Cra\.?|Kr\.?|Cll\.?|Cl\.?|Calle)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?)?)(?=[\.,;:]|A la hora|por manifestación|por siniestro|continúan|continua|siguen|flota|usuarios afectados|$)",
            r"((?:Calle|Cl\.?|Cll\.?)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?(?:\s+con\s+(?:Calle|Carrera|Av\.?|Avenida|Cra\.?|Kr\.?|Cll\.?|Cl\.?)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?)?)(?=[\.,;:]|A la hora|por manifestación|por siniestro|continúan|continua|siguen|flota|usuarios afectados|$)",
            r"((?:Carrera|Cra\.?|Kr\.?)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?(?:\s+con\s+(?:Calle|Av\.?|Avenida|Cra\.?|Kr\.?|Cll\.?|Cl\.?)\s+[A-Za-z0-9ºª°ÁÉÍÓÚáéíóúÑñ\-\s]+?)?)(?=[\.,;:]|A la hora|por manifestación|por siniestro|continúan|continua|siguen|flota|usuarios afectados|$)",
            r"((?:sector de|zona de)\s+[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s]+?)(?=[\.,;:]|$)",
        ]

        matches = []
        for pattern in patterns:
            for match in re.finditer(pattern, texto, re.I):
                candidate = match.group(1).strip() if match.groups() else match.group(0).strip()
                candidate = self.normalize_text(candidate).strip(" .,:;-")
                if not candidate:
                    continue

                if re.search(
                    r"(?i)tmahora|usuarios afectados|flota|servicios?|desv[ií]os?|operaci[oó]n|manifestaci[oó]n",
                    candidate,
                ):
                    continue

                matches.append(candidate)

        if not matches:
            return None

        return max(matches, key=len)

    def normalize_location(self, ubicacion: str, texto: Optional[str] = None) -> str:
        if not ubicacion:
            return "No especificada"

        original_text = self.normalize_text(texto or "")
        ubicacion = self.normalize_text(ubicacion)

        if not ubicacion or ubicacion.lower() in {"no especificada", "no disponible"}:
            return "No especificada"

        value = ubicacion.lower()

        value = re.sub(r"\bav\.?\b|\bavda\.?\b|\bavd\.?\b", "avenida", value)
        value = re.sub(r"\bcra\.?\b|\bkr\.?\b", "carrera", value)
        value = re.sub(r"\bcl\.?\b|\bcll\.?\b", "calle", value)

        value = re.sub(r"\b1(?:o|º|°|er|ro|a|ª)?\b", "1", value)
        value = re.sub(r"\bprimero\b", "1", value)
        value = re.sub(r"\bsext[oa]\b|\b6a\b|\b6ª\b", "6", value)
        value = re.sub(r"\bseptim[ea]\b|\bs[eé]ptim[ea]\b|\b7a\b|\b7ª\b", "7", value)

        text_lower = original_text.lower()

        if "circunvalar" in value:
            if "calle 26" in value or "calle 26" in text_lower:
                return "Avenida Circunvalar con Calle 26"
            return "Avenida Circunvalar"

        if "1 de mayo" in value or "1 mayo" in value:
            if "caracas" in value or "caracas" in text_lower:
                return "Avenida 1 de Mayo con Avenida Caracas"
            return "Avenida 1 de Mayo"

        if "avenida caracas" in value or value == "caracas":
            if "carrera 12b" in value or "carrera 12b" in text_lower:
                return "Avenida Caracas con Carrera 12B"
            if "calle sexta" in value or "calle 6" in value or "calle sexta" in text_lower or "calle 6" in text_lower:
                return "Avenida Caracas con Calle 6"
            return "Avenida Caracas"

        if "carrera 10 con calle 24" in value:
            return "Carrera 10 con Calle 24"

        if "calle 12b con carrera 10" in value:
            return "Calle 12B con Carrera 10"

        if "carrera 5 con calle 28" in value:
            return "Carrera 5 con Calle 28"

        if "portal eldorado" in value:
            return "Portal Eldorado"

        if "universidad distrital" in value and "macarena" in value:
            return "Universidad Distrital sede La Macarena"

        if "universidad pedag" in value:
            return "Universidad Pedagógica"

        if "carrera 7 con calle 34" in value or "carrera septima con calle 34" in value or "carrera séptima con calle 34" in value:
            return "Carrera Séptima con Calle 34"

        value = re.sub(r"(\d+)([a-zA-Z])\b", lambda m: f"{m.group(1)}{m.group(2).upper()}", value)

        words = []
        for word in value.split():
            if word in {"de", "la", "el", "los", "las", "y", "con", "en", "del", "sede", "al", "a", "por", "para"}:
                words.append(word)
            elif re.match(r"^\d+[A-Z]?$", word):
                words.append(word)
            elif word.lower() in {"portal", "estación", "estacion", "universidad", "avenida", "carrera", "calle", "circunvalar", "américa", "américa", "pedagógica", "pedagogica", "distrital", "nacional", "museo", "puente", "aranda", "lucía", "lucia", "san", "victorino", "diego", "nieves", "hortúa", "hortua", "nariño", "narino", "fucha", "mandalay", "banderas", "ricaurte"}:
                words.append(word.capitalize())
            else:
                words.append(word.capitalize())

        normalized = " ".join(words)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized or "No especificada"

    def classify_event_type(self, texto: str, causa: Optional[str] = None) -> str:
        contenido = self.normalize_text(" ".join([texto or "", causa or ""])).lower()

        if re.search(r"manifestaci[oó]n|manifestacion|manifestantes|protesta|movilizaci[oó]n|movilizacion|marcha", contenido):
            return "Manifestación o protesta"
        if re.search(r"siniestro|accidente|choque|colisi[oó]n|colision", contenido):
            return "Siniestro vial"
        if re.search(r"tormenta|el[eé]ctrica|electrica|lluvia fuerte", contenido):
            return "Tormenta eléctrica"
        if re.search(r"sin operar|sin paso|cierre|cerrado|cerrada|cerradas|estaciones sin operar", contenido):
            return "Cierre o estaciones sin operar"
        if re.search(r"desv[ií]o|desv[ií]os|desvio|desvios|desv[ií]a|desvia|activamos desv[ií]os|activamos desvios", contenido):
            return "Desvíos operacionales"
        if re.search(r"retoma|retoman|normaliza|normalizaci[oó]n|restablece|operaci[oó]n normal|se normaliza", contenido):
            return "Normalización de operación"
        if re.search(r"congesti[oó]n|congestion|retraso|retrasos|alta congesti[oó]n|alta congestion", contenido):
            return "Congestión o retrasos"

        return "Novedad operacional"

    def infer_cause(self, texto: str) -> str:
        return self.classify_event_type(texto)

    def extract_affected_stations(self, texto: str) -> List[str]:
        if not texto:
            return []

        texto = self.normalize_text(texto)

        patterns = [
            r"(?:siguen|contin[uú]an|continuan)?\s*sin operar(?:\s+las)?\s+estaciones?\s*([^\.;]+)",
            r"retoman(?: su)? operaci[oó]n(?: en)?\s+las?\s+estaciones?\s*([^\.;]+)",
            r"se normaliza operaci[oó]n(?: en)?\s+las?\s+estaciones?\s*([^\.;]+)",
            r"estaciones?\s+afectadas?\s*[:\-]?\s*([^\.;]+)",
            r"estaciones?\s+([A-ZÁÉÍÓÚÑ][^\.;]+)",
        ]

        candidates = []
        for pattern in patterns:
            for match in re.finditer(pattern, texto, re.I):
                raw = match.group(1)
                partes = re.split(r",| y | e |;|/|\n", raw, flags=re.I)

                for parte in partes:
                    item = self.normalize_text(parte).strip(" .,-:")
                    if not item:
                        continue

                    if len(item.split()) > 6:
                        continue

                    if re.search(
                        r"(?i)tmahora|usuarios afectados|operaci[oó]n|manifestaci[oó]n|manifestacion|flota|troncal|servicio|servicios|desv[ií]o|desvio|ruta|rutas|afectaci[oó]n|afectacion|avenida|carrera|calle|circunvalar|sector|zona|norte|sur|oriente|occidente|en la avenida|en el sector|por la carrera|con calle|con carrera",
                        item,
                    ):
                        continue

                    candidates.append(item.title())

        cleaned = []
        for estacion in candidates:
            if estacion not in cleaned:
                cleaned.append(estacion)

        return cleaned

    def extract_affected_services(self, texto: str) -> List[str]:
        if not texto:
            return []

        servicios = []
        for match in re.finditer(r"\b[A-Za-z]{1,3}\d{1,4}\b", texto):
            servicio = match.group(0).strip().upper()

            if servicio.lower() in {"am", "pm", "est", "av", "avd", "cra", "cll", "cl", "kr", "de", "y"}:
                continue

            servicios.append(servicio)

        unique = []
        for servicio in servicios:
            if servicio not in unique:
                unique.append(servicio)

        return unique

    def extract_detours(self, texto: str) -> List[str]:
        if not texto:
            return []

        frases = re.findall(
            r"([^.]*\b(?:desv[ií]o|desv[ií]os|desvio|desvios|continúa por|continua por|sigue por|sigue con|flota troncal sigue con|servicio\s+[^\.]+?\s+continúa\s+por)[^.]*\.)",
            texto,
            re.I,
        )

        return [self.normalize_text(frase.strip()) for frase in frases if frase.strip()]

    def parse_tm_alert(
        self,
        texto: str,
        fecha: Optional[str] = None,
        fuente: str = "WhatsApp TransMilenio",
    ) -> dict:
        texto_normalizado = self.normalize_text(texto)
        hora_publicacion = self.extract_time(texto_normalizado)
        ubicacion = self.extract_location(texto_normalizado)
        ubicacion_normalizada = self.normalize_location(ubicacion or "", texto_normalizado)
        tipo_evento = self.classify_event_type(texto_normalizado)
        causa = self.infer_cause(texto_normalizado)

        return {
            "fecha": fecha,
            "hora_publicacion": hora_publicacion,
            "hora_inicio": hora_publicacion,
            "franja_horaria": None,
            "ubicacion": ubicacion,
            "ubicacion_normalizada": ubicacion_normalizada,
            "causa": causa,
            "tipo_evento": tipo_evento,
            "estaciones_afectadas": self.extract_affected_stations(texto_normalizado),
            "servicios_afectados": self.extract_affected_services(texto_normalizado),
            "desvios": self.extract_detours(texto_normalizado),
            "usuarios_afectados": self.extract_affected_users(texto_normalizado),
            "fuente": fuente,
            "texto_original": texto,
            "texto_normalizado": texto_normalizado,
        }

    def parse_alerts(self, textos: List[str]) -> List[dict]:
        return [self.parse_tm_alert(texto) for texto in textos]