# Changelog

## [Unreleased]

### Added
- Flask API factory, WSGI and module entrypoints, process health, and OpenAPI schemas.
- Flask-independent application boundary and reserved `scenario_001` package.
- Service logging defaults using sabu-chassis, correlated access/error logs,
  and request-context cleanup.
- Focused foundation tests and installation/startup instructions.

### Changed
- Corrected the distribution name to `jug_sim_buildings`, configured src-layout
  packaging, aligned Python support to 3.10–3.12, and declared foundation-only
  dependencies. The package version remains `0.1.0`.
