#!/usr/bin/env python
"""Test script for HPR Desktop Application."""

import sys
import os
import importlib
import importlib.machinery

# Rutas absolutas - el script está en la raíz del proyecto motor HPR
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')

# Add src directory to path
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Try to import using importlib for robustness
try:
    # Load the module spec from file location
    spec = importlib.machinery.ModuleSpec(
        'src.desktop.app', 
        importlib.machinery.SourceFileLoader('src.desktop.app', os.path.join(SRC_DIR, 'desktop', 'app.py'))
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    print(">>> Iniciando Motor HPR - Interfaz Gráfica...")
    main = mod.main
    main()
    print("\n>>> Ejecución completada exitosamente.")
except Exception as e:
    import traceback
    print("\n>>> ERROR CRITICO AL INICIAR el agente HPR:")
    print(f"  Tipo: {type(e).__name__}")
    print(f"  Mensaje: {str(e)}")
    print()
    print("Traceback completo:")
    traceback.print_exc()
    sys.exit(1)