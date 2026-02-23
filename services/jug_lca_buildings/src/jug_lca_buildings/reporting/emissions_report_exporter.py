"""CSV report export helpers for jug_lca_buildings emissions results."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from flask import Response


class EmissionsReportExporter:
    """Build downloadable reports for the LCA emissions API."""

    METRIC_FIELDS = [
        'opening_embodied_emissions',
        'envelope_embodied_emissions',
        'component_embodied_emissions',
        'opening_end_of_life_emissions',
        'envelope_end_of_life_emissions',
        'component_end_of_life_emissions',
    ]

    CSV_COLUMNS = [
        'building_index',
        'feature_id',
        'name',
        'address',
        'function',
        'height',
        'year_of_construction',
        *METRIC_FIELDS,
        'total_embodied_emissions',
        'total_end_of_life_emissions',
        'total_lca_emissions',
    ]

    @classmethod
    def _safe_number(cls, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _row_from_feature_and_result(cls, index, feature, result):
        props = (feature or {}).get('properties') or {}

        opening_embodied = cls._safe_number(
            result.get('opening_embodied_emissions')
        )
        envelope_embodied = cls._safe_number(
            result.get('envelope_embodied_emissions')
        )
        component_embodied = cls._safe_number(
            result.get('component_embodied_emissions')
        )
        opening_eol = cls._safe_number(
            result.get('opening_end_of_life_emissions')
        )
        envelope_eol = cls._safe_number(
            result.get('envelope_end_of_life_emissions')
        )
        component_eol = cls._safe_number(
            result.get('component_end_of_life_emissions')
        )

        total_embodied = (
            opening_embodied + envelope_embodied + component_embodied
        )
        total_eol = opening_eol + envelope_eol + component_eol

        return {
            'building_index': index + 1,
            'feature_id': (feature or {}).get('id', ''),
            'name': props.get('name', ''),
            'address': props.get('address', ''),
            'function': props.get('function', ''),
            'height': props.get('height', ''),
            'year_of_construction': props.get('year_of_construction', ''),
            'opening_embodied_emissions': opening_embodied,
            'envelope_embodied_emissions': envelope_embodied,
            'component_embodied_emissions': component_embodied,
            'opening_end_of_life_emissions': opening_eol,
            'envelope_end_of_life_emissions': envelope_eol,
            'component_end_of_life_emissions': component_eol,
            'total_embodied_emissions': total_embodied,
            'total_end_of_life_emissions': total_eol,
            'total_lca_emissions': total_embodied + total_eol,
        }

    @classmethod
    def build_csv_text(cls, request_city, emissions_data):
        features = (request_city or {}).get('features') or []

        out = io.StringIO(newline='')
        writer = csv.DictWriter(out, fieldnames=cls.CSV_COLUMNS)
        writer.writeheader()

        totals = {field: 0.0 for field in cls.METRIC_FIELDS}
        totals.update(
            {
                'total_embodied_emissions': 0.0,
                'total_end_of_life_emissions': 0.0,
                'total_lca_emissions': 0.0,
            }
        )

        for idx, result in enumerate(emissions_data or []):
            row = cls._row_from_feature_and_result(
                idx,
                features[idx] if idx < len(features) else {},
                result or {},
            )
            writer.writerow(row)
            for key in totals:
                totals[key] += cls._safe_number(row.get(key))

        if emissions_data:
            writer.writerow(
                {
                    'building_index': '',
                    'feature_id': 'TOTAL',
                    'name': '',
                    'address': '',
                    'function': '',
                    'height': '',
                    'year_of_construction': '',
                    **totals,
                }
            )

        return out.getvalue()

    @classmethod
    def to_csv_download_response(cls, request_city, emissions_data):
        csv_text = cls.build_csv_text(request_city, emissions_data)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        filename = f'jug_lca_buildings_emissions_report_{stamp}.csv'
        return cls.to_csv_download_response_with_filename(csv_text, filename)

    @classmethod
    def to_csv_download_response_with_filename(cls, csv_text, filename):
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={
                'Content-Disposition': (
                    f'attachment; filename={filename}'
                )
            },
        )
