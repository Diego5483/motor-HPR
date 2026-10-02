from pydantic import BaseModel, Field


class CommunicationQuerySchema(BaseModel):
    """
    Modelo de validación para las consultas de comunicación en el motor HPR.
    """

    query: str | None = Field(
        default=None,
        description="Texto o término de búsqueda para la consulta de comunicación.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Límite de resultados a retornar, entre 1 y 100.",
    )