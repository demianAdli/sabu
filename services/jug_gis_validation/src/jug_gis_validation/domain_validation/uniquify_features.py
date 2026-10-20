"""Select one validation feature per configured attribute value."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import geopandas as gpd
import pandas as pd

from jug_gis_validation.errors import GISValidationDataContractError


@dataclass(frozen=True)
class FeatureUniquificationStats:
    """Counts describing validation-only feature uniquification."""

    applied: bool
    unique_attribute_key: str | None
    ranking_area_key: str | None
    input_features: int
    retained_features: int
    removed_features: int
    duplicate_groups: int

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            'applied': self.applied,
            'unique_attribute_key': self.unique_attribute_key,
            'ranking_area_key': self.ranking_area_key,
            'input_features': self.input_features,
            'retained_features': self.retained_features,
            'removed_features': self.removed_features,
            'duplicate_groups': self.duplicate_groups,
        }

    @classmethod
    def not_applied(cls, input_features: int):
        """Build statistics for an unfiltered validation input."""
        return cls(
            applied=False,
            unique_attribute_key=None,
            ranking_area_key=None,
            input_features=input_features,
            retained_features=input_features,
            removed_features=0,
            duplicate_groups=0,
        )


@dataclass
class _GroupSelection:
    count: int
    best_position: int
    best_area: float | None
    has_invalid_area: bool
    maximum_count: int = 1


def _is_missing_identifier(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _numeric_area(value) -> float | None:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value


def uniquify_features(
        buildings_set: gpd.GeoDataFrame,
        *,
        unique_attribute_key: str,
        area_key: str,
) -> tuple[gpd.GeoDataFrame, FeatureUniquificationStats]:
    """Keep the greatest-area feature for each non-missing attribute value.

    Features with null or blank unique attributes remain independent and are
    all retained. Equal greatest areas keep the earliest input feature. The
    input frame is never mutated and retained features preserve input order.
    """
    filtered, stats, _ = _select_features(
        buildings_set,
        unique_attribute_key=unique_attribute_key,
        area_key=area_key,
        include_trace=False)
    return filtered, stats


def uniquify_features_with_trace(
        buildings_set: gpd.GeoDataFrame,
        *,
        unique_attribute_key: str,
        area_key: str,
) -> tuple[gpd.GeoDataFrame, FeatureUniquificationStats, list[dict[str, Any]]]:
    """Apply the same selection policy and explain every input record."""
    return _select_features(
        buildings_set,
        unique_attribute_key=unique_attribute_key,
        area_key=area_key,
        include_trace=True)


def _select_features(
        buildings_set,
        *,
        unique_attribute_key,
        area_key,
        include_trace,
):
    missing_columns = [
        key for key in (unique_attribute_key, area_key)
        if key not in buildings_set.columns
    ]
    if missing_columns:
        raise GISValidationDataContractError(
            'buildings_set is missing required uniquification column(s): '
            f'{", ".join(missing_columns)}')

    groups: dict[Any, _GroupSelection] = {}
    missing_positions: list[int] = []

    unique_values = buildings_set[unique_attribute_key].tolist()
    area_values = buildings_set[area_key].tolist()
    for position, (unique_value, area_value) in enumerate(
            zip(unique_values, area_values)):
        if _is_missing_identifier(unique_value):
            missing_positions.append(position)
            continue

        try:
            hash(unique_value)
        except TypeError as exc:
            raise GISValidationDataContractError(
                f'buildings_set column {unique_attribute_key!r} contains an '
                f'unusable identifier at input position {position}.') from exc

        numeric_area = _numeric_area(area_value)
        selection = groups.get(unique_value)
        if selection is None:
            groups[unique_value] = _GroupSelection(
                count=1,
                best_position=position,
                best_area=numeric_area,
                has_invalid_area=numeric_area is None,
            )
            continue

        selection.count += 1
        if numeric_area is None:
            selection.has_invalid_area = True
        elif selection.best_area is None or numeric_area > selection.best_area:
            selection.best_area = numeric_area
            selection.best_position = position
            selection.maximum_count = 1
        elif numeric_area == selection.best_area:
            selection.maximum_count += 1

    invalid_duplicate_values = [
        unique_value
        for unique_value, selection in groups.items()
        if selection.count > 1 and selection.has_invalid_area
    ]
    if invalid_duplicate_values:
        sample = invalid_duplicate_values[:10]
        raise GISValidationDataContractError(
            f'Duplicate {unique_attribute_key!r} group(s) contain missing, '
            f'nonnumeric, or non-finite {area_key!r} values. Sample: {sample}')

    retained_mask = [False] * len(buildings_set)
    for position in missing_positions:
        retained_mask[position] = True
    for selection in groups.values():
        retained_mask[selection.best_position] = True

    retained_positions = [
        position
        for position, retain in enumerate(retained_mask)
        if retain
    ]
    filtered = buildings_set.iloc[retained_positions].copy()
    duplicate_groups = sum(
        1 for selection in groups.values() if selection.count > 1)
    input_features = len(buildings_set)
    retained_features = len(filtered)
    stats = FeatureUniquificationStats(
        applied=True,
        unique_attribute_key=unique_attribute_key,
        ranking_area_key=area_key,
        input_features=input_features,
        retained_features=retained_features,
        removed_features=input_features - retained_features,
        duplicate_groups=duplicate_groups,
    )
    records = []
    if include_trace:
        retained_indexes = {
            position: index for index, position in enumerate(retained_positions)
        }
        missing_position_set = set(missing_positions)
        for position, (identifier, area) in enumerate(
                zip(unique_values, area_values)):
            if position in missing_position_set:
                retained_position = position
                reason = 'missing_identifier'
            else:
                selection = groups[identifier]
                retained_position = selection.best_position
                if selection.count == 1:
                    reason = 'unique_identifier'
                elif position == retained_position:
                    reason = (
                        'earliest_maximum_area'
                        if selection.maximum_count > 1 else 'largest_area')
                elif _numeric_area(area) == selection.best_area:
                    reason = 'later_tied_maximum'
                else:
                    reason = 'smaller_area'
            records.append({
                'record_ref': f'record:{position}',
                'input_position': position,
                'identifier': identifier,
                'area': area,
                'status': 'retained' if retained_mask[position] else 'removed',
                'retained_record_ref': f'record:{retained_position}',
                'retained_feature_index': retained_indexes[retained_position],
                'reason': reason,
            })
    return filtered, stats, records
