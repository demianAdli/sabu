"""
Sabu project
jug_lca_buildings package
jug_lca_buildings module
Application-layer orchestration for emissions computation.
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from dataclasses import dataclass

from ..lca_carbon_workflow import LCACarbonWorkflow
from ..reporting import EmissionsReportExporter
from ..storage import EmissionsArtifactStore


@dataclass(frozen=True)
class EmissionsComputationResult:
    """Result envelope for emissions compute/cache operations."""

    request_hash: str
    emissions_data: list
    cache_hit: bool


class EmissionsApplicationService:
    """Run the LCA workflow and return emissions data."""

    @classmethod
    def compute_emissions(cls, request_city):
        store = EmissionsArtifactStore()
        request_hash = store.build_request_hash(request_city)
        cached_data = store.load_emissions_data(request_hash)
        if cached_data is not None:
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
        return EmissionsComputationResult(
            request_hash=request_hash,
            emissions_data=emissions_data,
            cache_hit=False,
        )

    @classmethod
    def build_csv_report(cls, request_city, computation_result):
        store = EmissionsArtifactStore()
        csv_text = store.load_csv_report(computation_result.request_hash)
        csv_cache_hit = csv_text is not None
        if not csv_cache_hit:
            csv_text = EmissionsReportExporter.build_csv_text(
                request_city,
                computation_result.emissions_data,
            )
            store.save_csv_report(computation_result.request_hash, csv_text)

        return {
            'csv_text': csv_text,
            'filename': store.build_csv_filename(
                computation_result.request_hash
            ),
            'cache_hit': csv_cache_hit,
        }
