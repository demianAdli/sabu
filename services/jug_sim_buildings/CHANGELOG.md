# Changelog

## [Unreleased]

### Added
- Shared scenario configuration JSON Schema and health API specification/examples
  under the repository's `contracts/` layout.
- Scenario_001 CLI and Flask-independent workflow for Montreal FSA preprocessing,
  artifact download, and provincial-ID uniquification through upstream APIs.
- Configurable service URLs, H2M FSA default, timeouts, run output root, and
  forwarded GIS Cities cleanup/keep-output settings (cleanup enabled by default).
- Correlated per-run response evidence, preserved input/retained GeoJSON, source
  IDs and CRS information, positional record mappings, reconciliation, whole-run
  counts, and bounded duplicate-group inspection using the existing selector policy.
- Scoped temporary-file cleanup and failure preservation, controlled HTTP tests,
  configuration example, and operational/real-run instructions with contract gaps.
- Flask API factory, WSGI and module entrypoints, process health, and OpenAPI schemas.
- Flask-independent application boundary and reserved `scenario_001` package.
- Service logging defaults using sabu-chassis, correlated access/error logs,
  and request-context cleanup.
- Focused foundation tests and installation/startup instructions.

### Changed
- Moved the scenario configuration example to `contracts/examples/jug_sim_buildings/`,
  updated references, and removed it from service source-distribution packaging.
- Replaced the empty `contracts/openapi/jug_sim.yaml` placeholder with
  `contracts/openapi/jug_sim_buildings.yaml` for the implemented health API.
- Corrected the distribution name to `jug_sim_buildings`, configured src-layout
  packaging, aligned Python support to 3.10–3.12, and declared foundation-only
  dependencies. The package version remains `0.1.0`.
