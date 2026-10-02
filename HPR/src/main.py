from fastapi import Depends, FastAPI
from .schemas import CommunicationQuerySchema
from .core.security_agent import verify_security_guard

# Inicialización de la API del motor HPR
app = FastAPI(title="Motor HPR - Arquitectura Híbrida", version="1.0.0")

@app.get("/")
def read_root():
    return {
        "estado": "en línea",
        "modulo": "main",
        "mensaje": "El servidor del motor HPR está transmitiendo correctamente.",
    }

@app.get("/api/v1/communications/query")
async def communications_query(
    params: CommunicationQuerySchema = Depends(),
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint para procesar consultas de comunicación en el motor HPR utilizando Pydantic
    y el agente de seguridad antiphishing.
    """
    return {
        "query": params.query,
        "limit": params.limit,
        "status": "procesado seguro",
        "resultados": [],
    }