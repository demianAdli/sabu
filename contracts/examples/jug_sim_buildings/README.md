# JUG SIM Buildings Contract Artifacts

- `scenario_001.json`: CLI configuration example; this is not an HTTP request body.
- `health.response.200.json`: Example response from `GET /health`.

The configuration schema is
[`scenario_001_config.schema.json`](../../jsonschema/jug_sim_buildings/scenario_001_config.schema.json).
The health API specification is
[`jug_sim_buildings.yaml`](../../openapi/jug_sim_buildings.yaml).
Runtime Python schemas and response checks remain inside the service.

Run the CLI from the repository root after configuring the upstream services:

```powershell
python -m jug_sim_buildings.scenario_001 --config contracts/examples/jug_sim_buildings/scenario_001.json
```

This executes real preprocessing. Relative output paths resolve against the
configuration file; the example points to `output_files/scenario_001` at the
repository root. These examples are repository-level artifacts, not packaged
service resources. Runs are grouped as `<output_root>/<FSA>/<run_id>/`, with
`retained.geojson` inside each run; existing run directories are never migrated.
The consumed HTTP contracts remain owned by
[`jug_gis_cities`](../jug_gis_cities/README.md) and
[`jug_gis_validation`](../jug_gis_validation/README.md).

The sample FSA is H3B. Preparation is disabled by default; enable
`preparation_enabled` to produce a separate eligible EPSG:4326 LCA input after
uniquification. `--prepare-from-run <run-directory>` prepares existing artifacts
without upstream calls. It requires a compatible CityGISOO/QGIS environment.
New attempts live in `<run>/preparation/<attempt_id>/`; existing artifacts remain
unchanged. Source CRS overrides require independent evidence and may not conflict
with existing declarations. The target CRS is fixed; this stage never submits LCA.
