"""Deprecated name. The planner is plan.py (same options); this file only keeps old commands and imports working."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan import *  # noqa: F401,F403,E402
from plan import main  # noqa: E402

if __name__ == "__main__":
    main()
