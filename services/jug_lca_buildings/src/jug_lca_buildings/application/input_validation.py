"""Load supported application inputs and validate without changing the source."""

import json
from pathlib import Path

from marshmallow import ValidationError

from ..schemas.schemas import LCAInputDataSchema


def normalize_city_input(request_city):
    """Return schema-loaded data from an object, JSON text, or string path.

    Relative paths retain the workflow's fallback to bundled data files.
    Schema failures raise ValidationError with nested field messages; malformed
    JSON raises ValidationError with a document-level message.
    """
    if isinstance(request_city, str):
        content = request_city.strip()
        try:
            if content.startswith(('{', '[')):
                request_city = json.loads(content)
            else:
                path = Path(content)
                if not path.is_absolute() and not path.exists():
                    path = Path(__file__).parents[1] / 'data' / path
                with path.open(encoding='utf-8') as source:
                    request_city = json.load(source)
        except json.JSONDecodeError as err:
            raise ValidationError(
                {'_schema': ['Invalid JSON content in GeoJSON input.']}
            ) from err

    return LCAInputDataSchema().load(request_city)
