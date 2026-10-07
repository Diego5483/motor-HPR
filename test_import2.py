import sys
import os

# Simulate what app.py does
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

print("sys.path after insert:", sys.path[:5])

from src.models.contracts import IDENTIDAD_DETERMINISTA
print("IDENTIDAD_DETERMINISTA:", IDENTIDAD_DETERMINISTA)