# JUG SIM Buildings Contract Artifacts

- `scenario_001.json`: CLI configuration example; this is not an HTTP request body.
- `health.response.200.json`: Example response from `GET /health`.
- `scenario_001_evaluation.json`: Illustrative evidence report, not measured results.

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

For complete execution, enable both `preparation_enabled` and `lca_enabled`, set
`lca_url`, and run all three upstream APIs. LCA has separate connect/read timeouts.
The orchestrator sends the exact final artifact to `POST /emissions`; HTTP 201
results must identify their actual reader building using `feature_id`. Equal
counts and response order are not identity guarantees. Missing IDs or unexplained
omissions fail reconciliation. The pinned reader excludes footprints below 25 m2;
its policy is unchanged, and such omissions cause explicit batch failure.

`evaluation_provenance_path` optionally supplies operator-declared provenance JSON;
relative paths resolve against the configuration file. Preserve remote service
logs and the LCA evaluation manifest separately: JSON results do not expose full
cache/version/data provenance. Evaluation evidence uses
`contracts/jsonschema/jug_sim_buildings/scenario_001_evaluation.schema.json`.
Carbon units are kgCO2e. Component fields are opening/envelope subtotals, not extra
emissions to add to their constituent fields. `--prepare-from-run` never submits.
