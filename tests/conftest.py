"""Shared pytest fixtures + sys.path setup.

The toolkit-template repo is a flat layout (modules sit at the root, not
inside a package), so pytest needs the repo root on sys.path to import them.
This conftest lives one level above each test file and pytest auto-loads it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
