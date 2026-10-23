# Changelog

## [Unreleased]

### Added
- Optional synchronous LCA submission of exact prepared GeoJSON with correlated
  HTTP evidence, explicit timeouts, identified result reconciliation, and carbon
  summaries in kgCO2e without double-counting component subtotals.
- Consolidated source/uniquification/preparation/submission/result histories,
  stage outcomes, provenance, and four-criterion evaluation reports.
- Controlled H3B execution and injected-failure tests; separate real-run instructions.
- Optional scenario_001 LCA preparation and existing-run CLI mode with independent
  eligibility/normalization, generated names, stable numeric IDs, and full positional
  lineage for accepted/rejected features. No LCA service or cerc-hub imports/submission.
- Separate preparation attempts, count reconciliation, rejection reasons, CRS and
  measurement audit reports, scoped scratch cleanup, and verified WGS84 LCA exports.
- Runtime verification of the actually consumed CityGISOO reprojection capability,
  strict source-CRS evidence, and method-based EPSG:4617/2950/4326 transformation/copy.
- H3B sample configuration and focused preparation/export tests; package version unchanged.
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
- Resolve checkout logs from the service root, with a user-state fallback for
  installed wheels and preserved explicit LOG_* overrides.
- Group new run artifacts by FSA and expose the full retained-output path;
  include FSA in scenario stage/completion logs and preserve legacy directories.
- Moved the scenario configuration example to `contracts/examples/jug_sim_buildings/`,
  updated references, and removed it from service source-distribution packaging.
- Replaced the empty `contracts/openapi/jug_sim.yaml` placeholder with
  `contracts/openapi/jug_sim_buildings.yaml` for the implemented health API.
- Corrected the distribution name to `jug_sim_buildings`, configured src-layout
  packaging, aligned Python support to 3.10–3.12, and declared foundation-only
  dependencies. The package version remains `0.1.0`.
