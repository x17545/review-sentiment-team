# main.py
import sys
from src.cli import main, run_interactive

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] in ("--interactive", "-i"):
        sys.exit(run_interactive())
    sys.exit(main())
