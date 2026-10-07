#!/usr/bin/env python
"""Launch script for Motor HPR Desktop Application.

Uses runpy to ensure proper module resolution.
"""

import sys
import os
import runpy

# Add HPR source directory to Python path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Also add HPR directory
hpr_dir = os.path.dirname(src_dir)
if hpr_dir not in sys.path:
    sys.path.insert(0, hpr_dir)

# Try to run the desktop module
try:
    # Run the desktop module's main function
    runpy.run_module("src.desktop", run_name="__main__", alter_sys=True)
except ImportError as e:
    print(f"Error importing HPR application: {e}")
    print(f"Python path: {sys.path}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"Error running HPR application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)