"""Pruebas de contratos de entrada (D4) para CommunicationQuerySchema.

La validación estricta en la frontera es parte del rigor de pruebas (P1):
los límites del esquema se verifican con aserciones, no por inspección.
"""

import pytest
from pydantic import ValidationError

from src.schemas import CommunicationQuerySchema


def test_esquema_acepta_valores_por_defecto():
    schema = CommunicationQuerySchema()
    assert schema.query is None
    assert schema.limit == 10


@pytest.mark.parametrize("limite", [1, 10, 100])
def test_esquema_acepta_limites_validos(limite):
    assert CommunicationQuerySchema(limit=limite).limit == limite


@pytest.mark.parametrize("limite", [0, -1, 101, 1000])
def test_esquema_rechaza_limites_fuera_de_rango(limite):
    with pytest.raises(ValidationError):
        CommunicationQuerySchema(limit=limite)


def test_esquema_rechaza_limite_no_entero():
    with pytest.raises(ValidationError):
        CommunicationQuerySchema(limit="diez")
