#!/usr/bin/env python
"""Launch script for Motor HPR Desktop Application."""

import sys
import os
import traceback

def main():
    # Add HPR source to Python path - calculate based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)  # This should be HPR
    src_dir = os.path.join(project_dir, "src")
    
    print(f"Script dir: {script_dir}")
    print(f"Project dir: {project_dir}")
    print(f"SRC dir: {src_dir}")
    print(f"Current sys.path[0]: {sys.path[0] if sys.path else 'empty'}")
    
    # Add src directory to the beginning of sys.path
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    
    print(f"sys.path after insertion: {sys.path[:3]}...")
    
    # Import and run the application
    try:
        from src.desktop.app import main
        main()
    except ImportError as e:
        print(f"Error de importaciůn: {e}")
        print(f"Python path verification:")
        for p in sys.path:
            print(f"  - {p}")
        print("\nPor favor, verifique que la estructura de directorios es correcta.")
        sys.exit(1)
    except Exception as e:
        print(f"Error inesperado al iniciar la aplicaciůn HPR: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()