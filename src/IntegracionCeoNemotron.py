import json
import os


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


class IntegracionCeoNemotron:
    def __init__(self, ruta_repositorio="src/data/ceo_knowledge_base.json"):
        self.ruta_repositorio = ruta_repositorio
        self.validador = ValidadorNivelesConfianza()

    def obtener_contexto_ceo(self) -> str:
        """Carga el repositorio del CEO y lo formatea como directriz en español para Nemotron 3.5."""
        if not os.path.exists(self.ruta_repositorio):
            return "Repositorio de CEO no disponible."
        
        with open(self.ruta_repositorio, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
            
        texto_contexto = f"--- REPOSITORIO INSTITUCIONAL CEO (Versión {datos.get('version', '1.0')}) ---\n"
        for pilar in datos.get("core_pillars", []):
            texto_contexto += f"* [{pilar['title']}]: {pilar['description']}\n"
            
        return texto_contexto

    def construir_prompt_nemotron(self, consulta_usuario: str) -> list:
        """Construye el esquema de mensajes en español para la API/modelo Nemotron 3.5."""
        contexto_ceo = self.obtener_contexto_ceo()
        
        mensajes = [
            {
                "role": "system",
                "content": (
                    "Eres el Agente HPR con arquitectura de soluciones avanzada. "
                    "Tienes acceso prioritario a la siguiente base de conocimiento del estudio de CEO con IA. "
                    "Utiliza estos parámetros en español para alinear todas tus respuestas lógicas, técnicas y conversacionales:\n\n"
                    f"{contexto_ceo}"
                )
            },
            {
                "role": "user",
                "content": consulta_usuario
            }
        ]
        return mensajes

    def validar_informacion(self, origen: str, contenido: str, es_oficial: bool = False) -> dict:
        """Método público para validar información usando los niveles de confianza HPR."""
        return self.validador.clasificar_fuente(origen, contenido, es_oficial)


# Ejemplo de uso integrado
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
    
    integracion = IntegracionCeoNemotron()
    validador = integracion.validador
    
    print("=== Sistema HPR: Validador de Niveles de Confianza ===\n")
    
    # Test con contenido del CEO knowledge base
    print("Test A - Información del repositorio CEO:")
    resultado = integracion.validar_informacion("ceo_knowledge_base", "Directrices sobre cómo los líderes ejecutivos integran modelos predictivos")
    print(f"  Origen: ceo_knowledge_base")
    print(f"  Resultado: Nivel {resultado['nivel']} - {resultado['etiqueta']}")
    print(f"  Estado: {resultado['estado']}\n")
    
    # Test con contenido oficial
    print("Test B - Información oficial:")
    resultado = integracion.validar_informacion("fuente_oficial", "Directriz institucional verificada", es_oficial=True)
    print(f"  Origen: fuente_oficial (es_oficial=True)")
    print(f"  Resultado: Nivel {resultado['nivel']} - {resultado['etiqueta']}")
    print(f"  Estado: {resultado['estado']}\n")
    
    # Test con contenido insuficiente
    print("Test C - Información insuficiente:")
    resultado = integracion.validar_informacion("fuente_aleatoria", "Corto")
    print(f"  Origen: fuente_aleatoria")
    print(f"  Contenido: 'Corto' (menos de 40 caracteres)")
    print(f"  Resultado: Nivel {resultado['nivel']} - {resultado['etiqueta']}")
    print(f"  Estado: {resultado['estado']}\n")
    
    # Test con contenido normal
    print("Test D - Contenido normal:")
    contenido_largo = ("Este es un contenido de prueba con suficiente longitud para ser evaluado adecuadamente "
                       "por el validador de niveles de confianza HPR en el sistema motor HPR.")
    resultado = integracion.validar_informacion("fuente_aleatoria", contenido_largo)
    print(f"  Origen: fuente_aleatoria")
    print(f"  Contenido: {len(contenido_largo)} caracteres")
    print(f"  Resultado: Nivel {resultado['nivel']} - {resultado['etiqueta']}")
    print(f"  Estado: {resultado['estado']}")