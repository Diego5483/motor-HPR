import sys
from pathlib import Path

# Añade la ruta raíz actual al PYTHONPATH para garantizar la resolución de 'src' y 'models'
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

# 'models' es un subpaquete de src/ (HPR/src/models), no una carpeta hermana.
# Los módulos del motor importan 'models' como paquete absoluto de primer
# nivel (from models.contracts import ...), por lo que src/ debe estar en
# sys.path para evitar ModuleNotFoundError.
src_dir = root_dir / "src"
sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
