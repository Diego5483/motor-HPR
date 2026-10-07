import sys
import os

# This is what app.py does - __file__ is HPR/src/desktop/app.py
__file__ = r"C:\Users\USUARIO\Desktop\motor HPR\HPR\src\desktop\app.py"
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("_parent_dir:", _parent_dir)

if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

print("sys.path after insert:", sys.path[:10])

from src.models.contracts import IDENTIDAD_DETERMINISTA
print("IDENTIDAD_DETERMINISTA:", IDENTIDAD_DETERMINISTA)