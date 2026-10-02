import re
from fastapi import HTTPException, status

PHISHING_PATTERNS = [
    r"login.*verify",
    r"update.*account",
    r"secure.*bank",
    r"confirm.*identity",
    r"reset.*password.*urgently"
]

def inspect_for_phishing(query_text: str | None) -> bool:
    if not query_text:
        return False
    for pattern in PHISHING_PATTERNS:
        if re.search(pattern, query_text, re.IGNORECASE):
            return True
    return False

def verify_security_guard(query: str | None = None) -> bool:
    if inspect_for_phishing(query):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alerta de Seguridad HPR: Petición bloqueada por coincidencia con patrones de phishing."
        )
    return True