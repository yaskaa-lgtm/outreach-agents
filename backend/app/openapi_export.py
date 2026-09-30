"""Write the OpenAPI schema used to generate the typed web client.

    uv run python -m app.openapi_export web/src/lib/api/openapi.json

CI regenerates it and fails if the committed file is out of date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.openapi_export <output.json>", file=sys.stderr)
        return 2
    # Fixed settings: the schema must not depend on the local .env file.
    schema = create_app(Settings(_env_file=None)).openapi()
    output = Path(argv[1])
    output.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OpenAPI schema written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
