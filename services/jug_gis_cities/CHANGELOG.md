# Changelog

## [Unreleased]

### Added
- Preserve request correlation in disposable QGIS workers through shutdown,
  restoring the prior worker context after both successful and failed runs.
- Reference the observed GIS dependency baseline under deploy/constraints;
  align shared HTTP/schema dependency ranges and remove duplicate GeoPandas entry.
- Correct a stale workflow test to expect preservation of merged source fields;
  the workflow implementation and selection policy are unchanged.
- Persistent artifact registrations and immutable GeoJSON copies for standardized application runs and successful per-FSA batch results.
- Additive artifact IDs and HTTP download URLs, plus `GET /artifacts/{artifact_id}/download` without rerunning preprocessing or requiring clients to share filesystem access.
- Persistent Docker artifact storage independent of workflow cleanup, documented indefinite retention, and 404/410 artifact errors.
- Focused download, batch, rerun, restart, cleanup, and API contract tests.
