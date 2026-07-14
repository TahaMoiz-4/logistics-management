"""
src/utils/scripts/export_openapi.py

Export the FastAPI app's OpenAPI schema to documentation/openapi.json.

This is the frontend handoff artifact — re-run it after ANY change to a
router, schema, or response model so the frontend (and Claude Design) build
against the current contract.

It imports the app object directly (no running server needed) and dumps the
same schema FastAPI serves at /openapi.json.

Usage:
    python -m src.utils.scripts.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from src.main import app

# Repo root = three levels up from this file (src/utils/scripts/ -> repo).
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = REPO_ROOT / "documentation" / "openapi.json"


def main() -> None:
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    paths = len(schema.get("paths", {}))
    schemas = len(schema.get("components", {}).get("schemas", {}))
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {paths} paths, {schemas} schemas")


if __name__ == "__main__":
    main()
