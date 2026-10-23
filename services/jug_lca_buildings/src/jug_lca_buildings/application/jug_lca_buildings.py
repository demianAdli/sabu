"""
Sabu project
jug_sim_buildings package
jug_lca_buildings module
Coordinate strict or exclusion-aware LCA computation and caching.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from dataclasses import dataclass, field
import logging
from math import isfinite

from ..lca_carbon_workflow import LCACarbonWorkflow
from ..reporting import EmissionsReportExporter
from ..storage import EmissionsArtifactStore
from .input_validation import normalize_city_input


logger = logging.getLogger(__name__)


def _log_cache_outcome(store, request_hash, cache_hit, artifact_kind):
    logger.info(
        'emissions_cache_outcome',
        extra={
            'request_hash': request_hash,
            'cache_hit': cache_hit,
            'artifact_kind': artifact_kind,
            'cache_directory': str(store.base_dir.resolve()),
        },
    )


@dataclass(frozen=True)
class EmissionsComputationResult:
    """Result envelope for emissions compute/cache operations."""

    request_hash: str
    emissions_data: list
    cache_hit: bool
    exclusions: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)


class EmissionsApplicationService:
    """Run the LCA workflow and return emissions data."""

    @classmethod
    def compute_emissions(cls, request_city, *, include_exclusions=False):
        """Validate all features before cache access or workflow execution.

        Accept a GeoJSON object, JSON text, or string file path. Invalid fields
        raise marshmallow.ValidationError with details in ``messages``.
        """
        request_city = normalize_city_input(request_city)
        if type(include_exclusions) is not bool:
            raise ValueError('include_exclusions must be a boolean.')
        if include_exclusions:
            return cls._compute_reader_outcome(request_city)
        store = EmissionsArtifactStore()
        request_hash = store.build_request_hash(request_city)
        cached_data = store.load_emissions_data(request_hash)
        if cached_data is not None:
            _log_cache_outcome(store, request_hash, True, 'emissions')
            return EmissionsComputationResult(
                request_hash=request_hash,
                emissions_data=cached_data,
                cache_hit=True,
            )

        emissions_data = LCACarbonWorkflow(
            request_city,
            'nrcan_archetypes.json',
            'nrcan_constructions_cap_3.json',
        ).export_emissions()
        store.save_emissions_data(request_hash, request_city, emissions_data)
        _log_cache_outcome(store, request_hash, False, 'emissions')
        return EmissionsComputationResult(
            request_hash=request_hash,
            emissions_data=emissions_data,
            cache_hit=False,
        )

    @staticmethod
    def _validate_reader_outcome(outcome, submitted_ids):
        """Reject corrupt cache partitions and unexplained reader omissions."""
        if not isinstance(outcome, dict) or type(outcome.get('schema_version')) is not int or outcome['schema_version'] != 1:
            raise ValueError('Invalid reader outcome contract.')
        results, exclusions = outcome.get('results'), outcome.get('exclusions')
        if not isinstance(results, list) or not isinstance(exclusions, list):
            raise ValueError('Reader outcome requires results and exclusions arrays.')
        seen = set()
        for row in results + exclusions:
            if not isinstance(row, dict) or type(row.get('feature_id')) is not int:
                raise ValueError('Reader outcome requires integer feature IDs.')
            identifier = row['feature_id']
            if identifier not in submitted_ids or identifier in seen:
                raise ValueError('Duplicate, overlapping or unexpected reader outcome ID.')
            seen.add(identifier)
        if seen != submitted_ids:
            raise ValueError('Unexplained missing reader outcome IDs.')
        for row in exclusions:
            area = row.get('reader_floor_area_m2')
            if (row.get('reason_code') != 'reader_floor_area_below_minimum'
                or row.get('field') != 'geometry' or not isinstance(row.get('reason'), str) or not row['reason'].strip()
                or type(area) not in (int, float) or not isfinite(area) or not 0 <= area < 25
                or type(row.get('minimum_floor_area_m2')) not in (int, float) or row['minimum_floor_area_m2'] != 25):
                raise ValueError('Invalid reader exclusion evidence.')
        for row in results:
            for key in EmissionsReportExporter.METRIC_FIELDS:
                value = row.get(key)
                if type(value) not in (int, float) or not isfinite(value):
                    raise ValueError('Invalid reader carbon result.')
        counts = outcome.get('counts')
        expected = {'submitted': len(submitted_ids), 'calculated': len(results), 'excluded': len(exclusions)}
        if not isinstance(counts, dict) or set(counts) != set(expected) or any(type(counts[k]) is not int or counts[k] != v for k, v in expected.items()):
            raise ValueError('Reader outcome count reconciliation failed.')

    @classmethod
    def _compute_reader_outcome(cls, request_city):
        ids = [feature['id'] for feature in request_city['features']]
        if any(type(identifier) is not int for identifier in ids) or len(set(ids)) != len(ids):
            raise ValueError('Reader outcomes require unique integer feature IDs.')
        store = EmissionsArtifactStore()
        request_hash = store.build_request_hash(request_city, include_exclusions=True)
        outcome = store.load_reader_outcome(request_hash)
        cache_hit = outcome is not None
        if not cache_hit:
            workflow = LCACarbonWorkflow(request_city, 'nrcan_archetypes.json',
                                         'nrcan_constructions_cap_3.json', include_exclusions=True)
            results = workflow.export_emissions()
            outcome = {'schema_version': 1, 'results': results, 'exclusions': workflow.exclusions,
                       'counts': {'submitted': len(ids), 'calculated': len(results), 'excluded': len(workflow.exclusions)}}
        cls._validate_reader_outcome(outcome, set(ids))
        if not cache_hit:
            store.save_reader_outcome(request_hash, request_city, outcome)
        _log_cache_outcome(store, request_hash, cache_hit, 'reader_outcome')
        return EmissionsComputationResult(request_hash=request_hash, emissions_data=outcome['results'],
                                          cache_hit=cache_hit, exclusions=outcome['exclusions'], counts=outcome['counts'])

    @classmethod
    def build_csv_report(cls, request_city, computation_result):
        if computation_result.counts or computation_result.exclusions:
            raise ValueError('CSV reporting is not supported for exclusion-aware outcomes.')
        request_city = normalize_city_input(request_city)
        store = EmissionsArtifactStore()
        csv_text = store.load_csv_report(computation_result.request_hash)
        csv_cache_hit = csv_text is not None
        if not csv_cache_hit:
            csv_text = EmissionsReportExporter.build_csv_text(
                request_city,
                computation_result.emissions_data,
            )
            store.save_csv_report(computation_result.request_hash, csv_text)

        _log_cache_outcome(
            store, computation_result.request_hash, csv_cache_hit, 'csv_report',
        )
        return {
            'csv_text': csv_text,
            'filename': store.build_csv_filename(
                computation_result.request_hash
            ),
            'cache_hit': csv_cache_hit,
        }
