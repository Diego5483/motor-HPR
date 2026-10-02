"""Pruebas de recursos de la interfaz de escritorio (src/desktop/app.py).

Reglas de la Constitución:
- P1: toda funcionalidad nueva llega con pruebas.
- P3: determinismo (las rutas se resuelven desde __file__).
- D3: rutas canónicas de recursos de la aplicación.
"""

from pathlib import Path

from PIL import Image

from src.desktop.app import RUTA_ICONO, RUTA_LOGO, _ruta_recurso


def test_ruta_recurso_se_resuelve_en_assets():
    ruta = _ruta_recurso("prueba.txt")
    esperado = Path(__file__).resolve().parent / "desktop" / "assets"
    assert ruta.parent == esperado
    assert ruta.name == "prueba.txt"


def test_icono_principal_es_ico_valido():
    assert RUTA_ICONO.exists()
    assert RUTA_ICONO.suffix == ".ico"
    with Image.open(RUTA_ICONO) as imagen:
        assert imagen.format == "ICO"
        tamanos = imagen.info.get("sizes", set())
        assert (16, 16) in tamanos
        assert (32, 32) in tamanos
        assert (256, 256) in tamanos


def test_logo_principal_es_png_valido():
    assert RUTA_LOGO.exists()
    assert RUTA_LOGO.suffix == ".png"
    with Image.open(RUTA_LOGO) as imagen:
        assert imagen.format == "PNG"
        assert imagen.mode == "RGBA"  # transparencia oficial preservada


def test_logo_conserva_proporcion_oficial():
    # El escudo oficial es 1536x1024 (ratio 1.5); la derivada
    # para cabecera debe conservar la misma proporción.
    with Image.open(RUTA_LOGO) as imagen:
        ancho, alto = imagen.size
        assert abs(ancho / alto - 1.5) < 0.01
