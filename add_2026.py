#!/usr/bin/env python
with open(r'C:\Users\USUARIO\Desktop\motor HPR\HPR\src\core\engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the SEÑALES_EXTERNAS tuple to add 2026
old_tuple = """SEÑALES_EXTERNAS = (
    "actualidad", "noticias", "última", "hoy", "2024", "2025", "tecnología",
    "lanzamiento", "versión", "actualizar", "tendencia", "desarrollo", "investigación",
    "web", "internet", "internacional", "mercado", "stock", "precio",
)"""

new_tuple = """SEÑALES_EXTERNAS = (
    "actualidad", "noticias", "última", "hoy", "2024", "2025", "2026", "tecnología",
    "lanzamiento", "versión", "actualizar", "tendencia", "desarrollo", "investigación",
    "web", "internet", "internacional", "mercado", "stock", "precio",
)"""

if old_tuple in content:
    content = content.replace(old_tuple, new_tuple)
    with open(r'C:\Users\USUARIO\Desktop\motor HPR\HPR\src\core\engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully added 2026 to SEÑALES_EXTERNAS')
else:
    print('Pattern not found')