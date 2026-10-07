#!/usr/bin/env python
"""
=== HPR Build Script ===
PyInstaller configuration for Motor HPR Desktop Application.

Este script configura la compilación para generar un ejecutable (.exe) 
autónomo y portable con interfaz gráfica (modo windowed).

Para ejecutar cuando el proyecto esté listo para empaquetado:
    python build_hpr.py

El ejecutable resultante se ubicará en: dist/Motor HPR.exe
"""

import os
import sys
import subprocess

# ============================================================================
# Configuration
# ============================================================================

# Base directory (project root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
HPR_DIR = BASE_DIR

# Ensure src directory is in path for imports
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# PyInstaller executable location
PYINSTALLER_EXE = os.path.join(
    os.environ.get(
        "PYTHON_APPLOCALAPPDATA",
        os.path.expanduser("~\\AppData\\Local\\Python\\pythoncore-3.14-64\\Scripts")
    ),
    "pyinstaller.exe"
)
if not os.path.isfile(PYINSTALLER_EXE):
    PYINSTALLER_EXE = os.path.join(sys.prefix, "Scripts", "pyinstaller.exe")
    if not os.path.isfile(PYINSTALLER_EXE):
        PYINSTALLER_EXE = "pyinstaller"  # Fallback: assume it's on PATH


# ============================================================================
# Data Files Configuration
# ============================================================================

# Critical resources that must be embedded in the executable
# Format: (source_path, destination_subdirectory_relative_to_exe)
DATAS = [
    # CEO Knowledge Base - essential for CEO knowledge integration
    ("src/data/ceo_knowledge_base.json", "."),
    
    # Visual assets - icon and logo
    ("src/desktop/assets/hpr.ico", "assets"),
    ("src/desktop/assets/hpr_logo.png", "assets"),
    
    # Core engine modules
    ("src/core/engine.py", "core"),
    ("src/core/triage.py", "core"),
    ("src/core/security_agent.py", "core"),
    
    # Desktop module
    ("src/desktop/agent.py", "desktop"),
    ("src/desktop/voice.py", "desktop"),
    
    # Models
    ("src/models/contracts.py", "models"),
]


# ============================================================================
# PyInstaller Options
# ============================================================================

PYINSTALLER_OPTS = [
    # Entry point script
    "src/desktop/app.py",
    
    # --windowed: crucial - prevents console window from appearing
    # This ensures the app opens directly with its GUI
    "--windowed",
    
    # Application icon (must be .ico format)
    f"--icon={os.path.join(SRC_DIR, 'desktop', 'assets', 'hpr.ico')}",
    
    # Optimization level 2 (strips assert statements, etc.)
    "--optimize=2",
    
    # Name the executable
    "--name=Motor HPR",
    
    # Add all critical data files
    *DATAS,
]


# ============================================================================
# Build Execution
# ============================================================================

def main():
    """
    Ejecuta la compilación PyInstaller para generar el ejecutable de HPR.
    
    Este script está diseñado para ser ejecutado cuando el proyecto 
    está en fase de congelado/estable y todos los recursos están 
    consolidados en las rutas esperadas.
    
    Output:
    - dist/Motor HPR.exe: Ejecutable standalone, windowed (sin consola)
    - build/: Directory used during build process
    - *.spec: PyInstaller spec file for future reference
    """
    
    print("=" * 60)
    print("=== HPR Build Script - PyInstaller Compilation ===")
    print("=" * 60)
    print()
    print(f"Directorio base: {os.path.abspath(BASE_DIR)}")
    print(f"Directorio src:  {os.path.abspath(SRC_DIR)}")
    print()
    print("Configuración de empaquetado:")
    print(f"  - Modo: --windowed (interfaz gráfica, sin consola)")
    print(f"  - Icono: {os.path.join(SRC_DIR, 'desktop', 'assets', 'hpr.ico')}")
    print(f"  - Base CEO:    {os.path.join(SRC_DIR, 'data', 'ceo_knowledge_base.json')}")
    print(f"  - Assets:    hpr.ico, hpr_logo.png")
    print(f"  - Módulos:   core/, desktop/, models/")
    print()
    print("Comando PyInstaller aproximado:")
    print("  pyinstaller --windowed --icon=SRC/desktop/assets/hpr.ico ")
    print("            --name 'Motor HPR' ")
    print("            --optimize=2 ")
    print("            --add-data 'SRC/data/ceo_knowledge_base.json;.' ")
    print("            --add-data 'SRC/desktop/assets/hpr.ico;SRC/desktop/assets' ")
    print("            --add-data 'SRC/desktop/assets/hpr_logo.png;SRC/desktop/assets' ")
    print("            src/desktop/app.py")
    print()
    print("=" * 60)
    print("Validando que los recursos existen antes de compilar...")
    print()
    
    # Validate that all critical resources exist
    all_exist = True
    for src, dst in DATAS:
        full_src = os.path.join(BASE_DIR, src) if not os.path.isabs(src) else src
        if not os.path.isfile(full_src):
            print(f"❌ FALTANTE: {src}")
            all_exist = False
    
    if not all_exist:
        print()
        print("⚠️ Algunos recursos críticos faltan. Complete la estructura de archivos")
        print("   antes de ejecutar el build para evitar errores.")
        print()
        print("Estructura esperada:")
        print("  HPR/src/data/ceo_knowledge_base.json")
        print("  HPR/src/desktop/assets/hpr.ico")
        print("  HPR/src/desktop/assets/hpr_logo.png")
        print("  HPR/src/core/engine.py")
        print("  HPR/src/desktop/agent.py")
        print("  HPR/src/models/contracts.py")
        sys.exit(1)
    
    print("✅ Todos los recursos críticos presentes.")
    print()
    print("Iniciando compilación PyInstaller...")
    print()
    
    # Execute PyInstaller
    try:
        result = subprocess.run(
            [PYINSTALLER_EXE] + PYINSTALLER_OPTS,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes timeout
        )
        
        if result.returncode == 0:
            print()
            print("=" * 60)
            print("✅ COMPILACIÓN EXITOSA")
            print("=" * 60)
            print()
            print("Ubicación del ejecutable:")
            print(f"  dist/Motor HPR.exe")
            print()
            print("Características del ejecutable:")
            print("  • Standalone (no requiere instalación)")
            print("  • Modo windowed (sin ventana de consola negra)")
            print("  • Icono personalizado (HPR escudo)")
            print("  • Base de conocimiento CEO integrada")
            print("  • Recursos visuales empaquetados")
            print()
            print("Para ejecutar el resultado:")
            print("  dist/Motor HPR.exe")
            print()
            print("NOTAS para futura distribución:")
            print("  • El ejecutable puede copiarse a otra máquina Windows")
            print("  • No requiere instalación previa de Python")
            print("  • Si se necesitan actualizaciones, ejecute nuevamente")
            print("    python build_hpr.py para regenerar el .exe")
            print()
        else:
            print()
            print("=" * 60)
            print("❌ ERROR DURANTE LA COMPILACIÓN")
            print("=" * 60)
            print(f"Código de retorno: {result.returncode}")
            if result.stderr:
                print()
                print("Detalles del error PyInstaller:")
                print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
            print()
            print("Posibles soluciones:")
            print("  1. Verifique que todos los archivos de origen existen")
            print("  2. Confirme que PyInstaller está instalado y actualizado")
            print("  3. Ejecute: python -m pip install --upgrade pyinstaller")
            print("  4. Consulte la consola para warnings o errores específicos")
            sys.exit(1)
            
    except FileNotFoundError:
        print()
        print("❌ Error: No se encontró el ejecutable PyInstaller.")
        print("Por favor, instálelo primero con:")
        print("  python -m pip install pyinstaller")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print()
        print("❌ Error: La compilación excedió el tiempo límite (600s).")
        print("Intente de nuevo o simplifique la configuración.")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()