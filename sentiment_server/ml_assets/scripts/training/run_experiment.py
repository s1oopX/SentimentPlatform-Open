"""Canonical maintained experiment launcher, including batch execution mode."""

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.training.launcher import main as run_launcher


def main(argv=None):
    return run_launcher(argv)


if __name__ == "__main__":
    main()

