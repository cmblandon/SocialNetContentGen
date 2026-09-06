"""
Regenerate docs/api-spec.yml from the running FastAPI app.

The file used to be hand-maintained under a rule that it "must always match
what app.py actually serves". It did not: it documented one endpoint while
the service exposed twenty-eight. Generating it removes that failure mode —
the spec cannot describe an endpoint the app does not have, or miss one it
does.

Run after changing any route or response model:

    python -m scripts.export_openapi
"""
from pathlib import Path

import yaml

from src.editorial.presentation.app import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "api-spec.yml"

_HEADER = """\
# GENERATED FILE — do not edit by hand.
# Regenerate with: python -m scripts.export_openapi
# Source of truth is src/editorial/presentation/app.py; endpoint descriptions
# come from each route function's docstring.
"""


def main() -> None:
    schema = app.openapi()
    schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development server"}
    ]
    OUTPUT_PATH.write_text(
        _HEADER + yaml.safe_dump(schema, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
