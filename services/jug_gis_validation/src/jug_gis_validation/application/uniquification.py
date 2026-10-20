"""Standalone feature uniquification, independent of census validation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import geopandas as gpd
import pandas as pd

from ..domain_validation.buildings_input import load_buildings_set
from ..domain_validation.uniquify_features import (
    FeatureUniquificationStats,
    uniquify_features_with_trace,
)
from ..errors import GISValidationInputError


def _json_safe(value):
    """Normalize pandas scalars and non-finite values without changing policy."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'item'):
        return _json_safe(value.item())
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class GISUniquificationResult:
    """Retained features, existing counts, and positional record provenance."""

    retained_features: gpd.GeoDataFrame
    uniquification_stats: FeatureUniquificationStats
    records: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        # Index labels can repeat and are not record identities. The trace joins
        # to GeoJSON by feature position, so do not synthesize GeoJSON IDs.
        geojson = json.loads(self.retained_features.to_json(
            drop_id=True, default=_json_safe))
        return _json_safe({
            'uniquification': self.uniquification_stats.as_dict(),
            'retained_geojson': geojson,
            'records': self.records,
        })


class GISUniquificationApplicationService:
    """Apply the existing selector without constructing a validation workflow."""

    @staticmethod
    def run_uniquification(
            buildings_set,
            *,
            unique_attribute_key: str,
            area_key: str = 'area',
    ) -> GISUniquificationResult:
        for name, value in (
                ('unique_attribute_key', unique_attribute_key),
                ('area_key', area_key)):
            if not isinstance(value, str) or not value.strip():
                raise GISValidationInputError(f'{name} must be a nonblank string.')
        buildings, _ = load_buildings_set(
            buildings_set, preserve_geojson_values=True)
        retained, stats, records = uniquify_features_with_trace(
            buildings,
            unique_attribute_key=unique_attribute_key,
            area_key=area_key)
        return GISUniquificationResult(retained, stats, records)
