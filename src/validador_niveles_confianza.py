class ValidadorNivelesConfianza:
    def __init__(self):
        pass

    def clasificar_fuente(self, origen: str, contenido: str, es_oficial: bool = False) -> dict:
        """
        Evalúa y clasifica la información según los tres niveles de confianza del sistema HPR:
        - Nivel 1: Alta Confianza / Verificado (Fuentes institucionales y repositorio CEO)
        - Nivel 2: Confianza Media / Validación Requerida (Datos generales validados por lógica)
        - Nivel 3: Baja Confianza / Precaución (Datos ambiguos o incompletos)
        """
        if es_oficial or "ceo_knowledge_base" in origen:
            return {
                "nivel": 1,
                "etiqueta": "Alta Confianza (Verificado)",
                "estado": "Aceptado directamente en el flujo del motor."
            }
        
        if not contenido or len(contenido.strip()) < 40:
            return {
                "nivel": 3,
                "etiqueta": "Baja Confianza (Precaución)",
                "estado": "Descartado o requiere re-consulta por insuficiencia de datos."
            }
            
        return {
            "nivel": 2,
            "etiqueta": "Confianza Media (Validación Requerida)",
            "estado": "Sujeto a validación cruzada con la lógica interna antes de la salida."
        }