import sys
from pathlib import Path

# Tests live in tests/, modules live at repo root (flat layout).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
