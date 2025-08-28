"""CLI entry point for migration utilities.

Allows running migrations via: python -m app.utils.migrate
"""

from .migrate import main

if __name__ == "__main__":
    raise SystemExit(main())
