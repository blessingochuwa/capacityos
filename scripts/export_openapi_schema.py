"""Regenerates docs/openapi.json from the live FastAPI app definition —
no server needs to be running; app.openapi() builds the schema from the
route/schema definitions already in the code. Run this after adding or
changing any route so the checked-in schema doesn't drift from reality.

Usage (from apps/api, so imports resolve the same way the API itself does):

    uv run python ../../scripts/export_openapi_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    route_count = len(schema.get("paths", {}))
    print(f"Wrote {OUTPUT_PATH} ({route_count} routes, schema version {schema.get('openapi')}).")


if __name__ == "__main__":
    main()
