# JUG LCA Buildings

`jug_lca_buildings` is a Sabu microservice that estimates building-level life-cycle carbon emissions from GeoJSON building data.

At a high level, the service accepts a GeoJSON `FeatureCollection` of buildings, runs a building life-cycle assessment workflow, and returns emissions results for the embodied and end-of-life stages. It can return either JSON results for API-to-API use or a CSV report for download and review.

All emission values returned by this service are expressed as `kgCO2e` per building unless stated otherwise.

This service is part of the broader Sabu project, where each "jug" is a focused microservice for a specific urban carbon or geospatial workflow. In that architecture, `jug_lca_buildings` covers the building LCA calculation step.

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

`FeatureCollection.type` and `FeatureCollection.features`, feature `type`,
`id`, `geometry`, and `properties`, geometry `type` and `coordinates`, and all
five building properties above are required and cannot be null. Marshmallow
validates their declared types and normalizes numeric values (including numeric
strings). Geometry types are `Polygon` and `MultiPolygon`, including both types
in one collection. Polygon coordinates use `[ring][point][number]` (three nested
lists); MultiPolygon coordinates use `[polygon][ring][point][number]` (four).
Unsupported types and incorrect coordinate nesting produce field validation
errors. Validation adds no ring-length, ring-closure, topology, or domain-value
checks and does not repair invalid geometry.

Polygon parts and interior holes are retained without flattening or splitting
features. The service adapts the pinned `cerc-hub` reader's MultiPolygon hole
handling by combining its Polygon parsing results into a single building.
Schema acceptance alone does not guarantee that geometry can be processed by
the calculation engine. Existing reader behavior, including filtering footprints
smaller than 25 square metres, remains in effect.

Input coordinates must be WGS84 longitude/latitude. Accepting and excluding
`crs` metadata does not reproject coordinates; perform any necessary CRS
conversion upstream.

Additional fields at the FeatureCollection, Feature, Geometry, and Properties
levels are accepted and excluded from computation input. The original object
or file is preserved. One invalid feature rejects the entire batch; neither
endpoint silently removes invalid features. API schema failures return `422`
with nested field details in `errors` (JSON request-parser errors are nested
under `errors.json`). Invalid JSON uploads continue to return `400`.

Direct calls to `EmissionsApplicationService.compute_emissions(request_city)`
apply the same Marshmallow rules and raise `marshmallow.ValidationError` with
field details in `.messages`. Supported inputs remain a GeoJSON object, JSON
text, or a string file path. Relative file paths retain the fallback to bundled
service data. Validation happens before cache lookup. Computation, cached request
artifacts, and application CSV reports use normalized input, so ignored metadata
and equivalent numeric strings do not change the computation cache identity.

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
- MultiPolygon and mixed Polygon/MultiPolygon request examples
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

<https://github.com/demianAdli/sabu-test-data-and-examples/tree/main/services/jug_lca_buildings>

Use that repository together with the local contract artifacts in this project when preparing manual tests or integration examples.

## Usage Examples

Instructions on how to run `jug_lca_buildings` in different settings can be found in these example directories:

- API usage: <https://github.com/demianAdli/sabu-test-data-and-examples/tree/main/services/jug_lca_buildings/examples/api>
- Direct Python run: <https://github.com/demianAdli/sabu-test-data-and-examples/tree/main/services/jug_lca_buildings/examples/direct-python>
- Docker Compose run: <https://github.com/demianAdli/sabu-test-data-and-examples/tree/main/services/jug_lca_buildings/examples/docker>

## Docker Image

The container image is intended to run the published PyPI package, not the local checkout.

- Runtime port inside the container: `5000`
- Recommended host mapping: `-p 8080:5000` or any other host port you prefer
- Image tag should match the package version, for example `0.1.1`
- Do not publish `latest`; only publish versioned tags
- Build args `JUG_LCA_BUILDINGS_VERSION` and `SABU_CHASSIS_VERSION` are optional and default to `latest`
- If a package version build arg is omitted or set to `latest`, Docker installs the latest available release from PyPI
- If a package version build arg is provided, Docker pins that package to the exact version

Example build and run commands using the latest PyPI releases:

```bash
docker build \
  --no-cache \
  -f services/jug_lca_buildings/docker/Dockerfile \
  -t demianadli/jug_lca_buildings:0.1.1 \
  .

docker run --rm \
  -p 8080:5000 \
  -e JUG_LCA_ARTIFACTS_DIR=/app/data/jug_lca_buildings \
  demianadli/jug_lca_buildings:0.1.1
```

Example pinned build:

```bash
docker build \
  -f services/jug_lca_buildings/docker/Dockerfile \
  --build-arg JUG_LCA_BUILDINGS_VERSION=0.1.1 \
  --build-arg SABU_CHASSIS_VERSION=0.1.0 \
  -t demianadli/jug_lca_buildings:0.1.1 \
  .
```

Compose example:

```bash
docker compose -f services/jug_lca_buildings/docker-compose.yml build --no-cache
docker compose -f services/jug_lca_buildings/docker-compose.yml up -d
```

The compose file can build the image locally from the Dockerfile. By default it installs the latest available PyPI releases for `jug_lca_buildings` and `sabu-chassis`, so you can rebuild locally after publishing either package to PyPI without publishing a new Docker Hub image. Use `--no-cache` when you want Docker to check PyPI again instead of reusing the previous pip-install layer.

To pin versions in Compose, set environment variables before building:

```bash
JUG_LCA_BUILDINGS_VERSION=0.1.1 SABU_CHASSIS_VERSION=0.1.0 \
  docker compose -f services/jug_lca_buildings/docker-compose.yml up -d --build
```

## Versioned Publishing

The GitHub Actions workflow publishes the image from a version tag only.

- Tag format: `jug_lca_buildings-v0.1.1`
- Docker Hub image tag: `0.1.1`
- Workflow file: [`.github/workflows/publish-jug-lca-buildings-docker.yml`](../../.github/workflows/publish-jug-lca-buildings-docker.yml)

Release flow:

1. Publish `jug_lca_buildings==0.1.1` to PyPI.
2. Create and push the git tag `jug_lca_buildings-v0.1.1`.
3. GitHub Actions builds the Docker image with `JUG_LCA_BUILDINGS_VERSION=0.1.1`.
4. The image is pushed to Docker Hub as `demianadli/jug_lca_buildings:0.1.1`.
