"""Write the OpenAPI document to stdout or a file: python -m app.scripts.export_openapi [path]."""

import json
import sys
from pathlib import Path

from app.main import app


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(render())
    else:
        sys.stdout.write(render())


if __name__ == "__main__":
    main()
