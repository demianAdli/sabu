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
service resources. The consumed HTTP contracts remain owned by
[`jug_gis_cities`](../jug_gis_cities/README.md) and
[`jug_gis_validation`](../jug_gis_validation/README.md).
