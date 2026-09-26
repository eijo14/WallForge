#!/usr/bin/env python3
"""Launcher script for Personal Wallpaper Engine."""

import sys
from pathlib import Path

# Ensure package directory is on python path
root_dir = Path(__file__).parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from wallpaper_engine.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
