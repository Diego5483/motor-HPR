"""Script para reemplazar los archivos de logo por versiones placeholder.

Ejecuta desde la raíz del proyecto motor HPR.
"""
from pathlib import Path
from PIL import Image

# Directorios
assets_dir = Path(r"C:\Users\USUARIO\Desktop\motor HPR\HPR\src\desktop\assets")

# --- PNG para la cabecera (60x40) ---
png_path = assets_dir / "hpr_logo.png"
img_png = Image.new("RGBA", (60, 40), color=(0, 122, 255))  # azul HPR
img_png.save(png_path)
print(f"Logo PNG placeholder guardado en {png_path}")

# --- ICO con múltiples tamaños requeridos por la prueba ---
# La prueba espera los tamaños (16,16), (32,32), (256,256).
ico_path = assets_dir / "hpr.ico"
sizes = [(16, 16), (32, 32), (256, 256)]
imgs = [Image.new("RGBA", size, color=(0, 122, 255)) for size in sizes]
# Guardar como ICO combinado; el primer imagen es la principal.
imgs[0].save(ico_path, format="ICO", sizes=sizes)
print(f"Logo ICO placeholder guardado en {ico_path} con tamaños {sizes}")

# Verificar
assert png_path.exists(), "PNG no creado"
assert ico_path.exists(), "ICO no creado"
print("Reemplazo de logos completado exitosamente.")