#!/usr/bin/env python
import sys

with open(r'C:\Users\USUARIO\Desktop\motor HPR\HPR\src\security_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The section we want to replace (the broken part after my earlier modification)
# We want to replace lines starting from intencion evaluation through the sovereign_gate check
old_section = """        intencion = self.evaluar_intencion_consulta(str(query))

        if not sovereign_gate_validation(str(query)):
            return MENSAJE_BLOQUEO_SOVEREIGN_GATE

        return f"Consulta procesada con éxito. Análisis de intención: {intencion}""""

new_section = """        intencion = self.evaluar_intencion_consulta(str(query))

        # Nexus Root: validación de identidad ligera (sin bloqueo para consultas web/externas).
        # El acceso a internet y la veracidad de la información quedan gobernados
        # exclusivamente por el sistema de tres niveles de confianza (Regla E5).
        # Si la identidad no coincide, simplemente continuamos para que el sistema
        # de confianza evalúe el contenido web entrante.
        _ = nexus_root_validation(intencion, self.nexus_identity)  # Auditoria ligera, sin bloqueo

        if not sovereign_gate_validation(str(query)):
            return MENSAJE_BLOQUEO_SOVEREIGN_GATE"""

if old_section in content:
    content = content.replace(old_section, new_section)
    with open(r'C:\Users\USUARIO\Desktop\motor HPR\HPR\src\security_agent.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fix applied successfully")
else:
    print("Old section not found - trying alternative approach")
    # Alternative: just remove the 'return MENSAJE_DENEGACION_NEXUS_ROOT' line and the nexus_root_validation check
    # Find 'if not nexus_root_validation' and remove it plus the return
    import re
    # Pattern to find and replace
    pattern = r"        if not nexus_root_validation\(intencion, self\.nexus_identity\):\n            return MENSAJE_DENEGACION_NEXUS_ROOT"
    match = re.search(pattern, content)
    if match:
        # Replace just the if block with a comment
        replacement = "        # Nexus Root: validación de identidad (sin bloqueo para consultas web/externas)\n        # El acceso a internet y la veracidad quedan gobernados por el sistema de tres niveles de confianza"
        content = content.replace(match.group(), replacement)
        with open(r'C:\Users\USUARIO\Desktop\motor HPR\HPR\src\security_agent.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Alternative fix applied")
    else:
        print("Could not apply fix")