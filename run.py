"""Convenience entry point.  Run from the project root:

    python run.py
"""

import subprocess
import sys

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "src.main"]))
