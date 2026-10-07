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


# Prueba rápida del validador
if __name__ == "__main__":
    validador = ValidadorNivelesConfianza()
    
    # Test 1: Fuente CEO knowledge base (debe ser Nivel 1)
    print("Test 1 - Fuente CEO knowledge base:")
    resultado = validador.clasificar_fuente("ceo_knowledge_base", "Algun contenido", es_oficial=False)
    print(f"  Nivel: {resultado['nivel']}, Etiqueta: {resultado['etiqueta']}")
    
    # Test 2: Fuente oficial
    print("Test 2 - Fuente oficial:")
    resultado = validador.clasificar_fuente("fuente_oficial", "Contenido oficial aquí", es_oficial=True)
    print(f"  Nivel: {resultado['nivel']}, Etiqueta: {resultado['etiqueta']}")
    
    # Test 3: Contenido vacío (Nivel 3)
    print("Test 3 - Contenido vacío:")
    resultado = validador.clasificar_fuente("fuente_random", "")
    print(f"  Nivel: {resultado['nivel']}, Etiqueta: {resultado['etiqueta']}")
    
    # Test 4: Contenido normal (Nivel 2)
    print("Test 4 - Contenido normal:")
    resultado = validador.clasificar_fuente("fuente_random", "Este es un contenido de prueba con suficiente longitud para ser evaluado adecuadamente por el validador de niveles de confianza HPR.")
    print(f"  Nivel: {resultado['nivel']}, Etiqueta: {resultado['etiqueta']}")