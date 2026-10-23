# jug_sim_buildings

Sabu's building carbon emissions simulation service, supporting Python 3.10–3.12.
The foundation API provides health and logging support. `scenario_001` runs the
initial Montreal FSA preprocessing/download/uniquification workflow through two
upstream HTTP APIs and preserves artifacts and positional provenance per run.

From the repository root after installation, run:

```powershell
python -m jug_sim_buildings.scenario_001 --config contracts/examples/jug_sim_buildings/scenario_001.json
```

This command executes real preprocessing; configure the upstream services first.
Normal scenario runs request upstream cleanup. No GIS execution happens during
imports, `--help`, foundation API startup, or health requests.

The example uses H3B. Set `preparation_enabled` to `true` to prepare eligible LCA
features after uniquification. Preparation requires the separately maintained
CityGISOO package exposing `ScrubLayer.reproject_layer` in a configured QGIS
environment. The optional `preparation` extra declares CityGISOO, but a version
number alone does not guarantee that method; the imported package is checked.
Keep the existing OSGeo4W environment and native dependencies intact.

To prepare an already successful run without repeating upstream calls:

```powershell
pyqgis344 -m jug_sim_buildings.scenario_001 --config contracts/examples/jug_sim_buildings/scenario_001.json --prepare-from-run <H3B-run-directory>
```

Each attempt writes separate artifacts under `<run>/preparation/<attempt_id>/`,
including accepted/rejected features, ID mappings, CRS/measurement reports, and
verified `lca_input.geojson` in EPSG:4326 longitude/latitude order. Existing run
artifacts are preserved. Missing/ambiguous CRS, no eligible features, and failed
transformation/export stop preparation. This stage does not submit to LCA.

Repository-level [examples](../../contracts/examples/jug_sim_buildings/README.md),
[configuration schema](../../contracts/jsonschema/jug_sim_buildings/scenario_001_config.schema.json),
and [OpenAPI specification](../../contracts/openapi/jug_sim_buildings.yaml) live
under `contracts/`. Runtime schemas and response checks stay inside this service.

## Install and run

From the repository root, using a virtual environment:

```powershell
python -m pip install -e services/jug_sim_buildings
cd services/jug_sim_buildings
python -m jug_sim_buildings --host 127.0.0.1 --port 5000
```

Alternatively, from the service directory:

```powershell
python -m flask --app app:app run --host 127.0.0.1 --port 5000
```

The installed factory is also available as
`jug_sim_buildings.api:create_app`. Both commands start a development server.

- `GET /health` returns `{"service":"jug_sim_buildings","status":"ok"}`.
  This reports process health without checking downstream services.
- `GET /openapi.json` serves the API description.
- `GET /swagger-ui` serves the Swagger UI (its assets require CDN access).
- `python -m jug_sim_buildings --help` lists startup options without creating logs.

## Logging

Logging uses the installed `sabu-chassis>=0.1.1` dependency. The default
service name is `sim_buildings-api`. Console output and rotating JSON file
output use the chassis configuration. In a checkout, the default file is
`services/jug_sim_buildings/logs/jug_sim_buildings.log`, independent of the
startup working directory. Installed wheels default to
`%LOCALAPPDATA%/Sabu/jug_sim_buildings/logs/jug_sim_buildings.log` on Windows,
or `~/.local/state/Sabu/jug_sim_buildings/logs/jug_sim_buildings.log` otherwise.
Deployments should explicitly set `LOG_DIR_BASE` to their persistent log location.

Set `LOG_DIR_BASE` and/or `LOG_FILE_NAME` to change the destination.
Existing `LOG_SERVICE`, `LOG_ENV`, `LOG_LEVEL`, `LOG_FILE_LEVEL`,
`LOG_FILE_MAX_BYTES`, `LOG_FILE_BACKUP_COUNT`, and `WERKZEUG_LEVEL`
settings are honored by chassis.

Requests use `X-Request-ID`, then `X-Correlation-ID`, then a generated ID.
Responses include `X-Request-ID`; access and exception logs carry the same
ID. Request teardown restores the prior correlation context.

Scenario results are saved under `<output_root>/<FSA>/<run_id>/`. Completion
output includes the FSA, run ID, run directory, and full `retained.geojson` path.
Existing UUID-only run directories are preserved. The shared GIS dependency
baseline and its LCA compatibility limits are described in
[`deploy/constraints`](../../deploy/constraints/README.md).

## Verify

From the service directory after installation:

```powershell
python -m pip check
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

For a packaging smoke check, install the resulting wheel in a fresh virtual
environment and run from outside the repository:

```powershell
python -m pip install C:/path/to/jug_sim_buildings-0.1.0-py3-none-any.whl
python -m pip check
python -m jug_sim_buildings --help
python -c "import importlib.metadata as m, sabu_chassis; print(m.version('sabu-chassis'), sabu_chassis.__file__)"
python -m flask --app jug_sim_buildings.api:create_app run
```

Confirm `GET /health` returns HTTP 200. Tests use installed packages without
adding service or chassis checkout paths to Python's import search path.
