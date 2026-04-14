# JUG LCA Buildings

`jug_lca_buildings` is a JUGS microservice that estimates building-level life-cycle carbon emissions from GeoJSON building data.

At a high level, the service accepts a GeoJSON `FeatureCollection` of buildings, runs a building life-cycle assessment workflow, and returns emissions results for the embodied and end-of-life stages. It can return either JSON results for API-to-API use or a CSV report for download and review.

All emission values returned by this service are expressed as `kgCO2e` per building unless stated otherwise.

This service is part of the broader JUGS project, where each "jug" is a focused microservice for a specific urban carbon or geospatial workflow. In that architecture, `jug_lca_buildings` covers the building LCA calculation step.

## What The Service Does

- Accepts building data through `POST /emissions` as JSON or `POST /emissions/upload` as a GeoJSON file upload.
- Validates the request structure before running the workflow.
- Calculates embodied and end-of-life emissions for each building.
- Can export results as JSON or as a CSV report with per-building rows and totals.
- Stores generated artifacts under `.runtime/jug_lca_buildings` unless `JUG_LCA_ARTIFACTS_DIR` is set.

## Units

- `opening_embodied_emissions`, `envelope_embodied_emissions`, and `component_embodied_emissions` are reported in `kgCO2e`.
- `opening_end_of_life_emissions`, `envelope_end_of_life_emissions`, and `component_end_of_life_emissions` are reported in `kgCO2e`.
- CSV totals such as `total_embodied_emissions`, `total_end_of_life_emissions`, and `total_lca_emissions` are also reported in `kgCO2e`.
- These values are absolute totals for each building, not per-square-metre intensities and not tonnes.

## Inputs Needed For Testing

For a basic test request, you need a GeoJSON `FeatureCollection` where each feature represents one building and includes:

- `type`
- `id`
- `geometry`
- `properties.name`
- `properties.address`
- `properties.function`
- `properties.height`
- `properties.year_of_construction`

The service also depends on bundled reference data used by the workflow:

- [`src/jug_lca_buildings/data/nrcan_archetypes.json`](src/jug_lca_buildings/data/nrcan_archetypes.json)
- [`src/jug_lca_buildings/data/nrcan_constructions_cap_3.json`](src/jug_lca_buildings/data/nrcan_constructions_cap_3.json)
- [`src/jug_lca_buildings/data/nrcan_materials_dictionaries.json`](src/jug_lca_buildings/data/nrcan_materials_dictionaries.json)
- [`src/jug_lca_buildings/data/nrcan_transparent_surfaces_dictionaries.json`](src/jug_lca_buildings/data/nrcan_transparent_surfaces_dictionaries.json)

## Example Test Data

Contract examples already exist in the repository and are the safest starting point for manual or integration testing:

- [`contracts/examples/jug_lca_buildings/README.md`](../../contracts/examples/jug_lca_buildings/README.md)
- [`contracts/openapi/jug_lca_buildings.yaml`](../../contracts/openapi/jug_lca_buildings.yaml)
- External examples repository: <https://github.com/demianAdli/sabu-test-data-and-examples/tree/main/services/jug_lca_buildings>

The contract examples include:

- an example JSON body for `POST /emissions`
- an example JSON success response
- an example CSV export response
- example error payloads for invalid upload and validation failures

The test suite also shows the minimum valid request shape used in automated tests:

- [`tests/test_emissions_api.py`](tests/test_emissions_api.py)

That minimum test payload is a single polygon building with basic metadata such as name, address, function, height, and year of construction.

## Running A Simple Test

Once the service is running locally, you can test it by:

1. Sending a JSON GeoJSON payload to `POST /emissions`.
2. Sending the same payload with `?export=csv` to download a CSV report.
3. Uploading a `.geojson` file to `POST /emissions/upload`.

## External Test Data Reference

Additional example inputs and supporting test data are also available in the external repository:

<https://github.com/demianAdli/jugs-test-data-and-examples/tree/main/services/jug_lca_buildings>

Use that repository together with the local contract artifacts in this project when preparing manual tests or integration examples.
