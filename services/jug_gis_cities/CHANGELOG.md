# Changelog

## [Unreleased]

### Added
- Persistent artifact registrations and immutable GeoJSON copies for standardized application runs and successful per-FSA batch results.
- Additive artifact IDs and HTTP download URLs, plus `GET /artifacts/{artifact_id}/download` without rerunning preprocessing or requiring clients to share filesystem access.
- Persistent Docker artifact storage independent of workflow cleanup, documented indefinite retention, and 404/410 artifact errors.
- Focused download, batch, rerun, restart, cleanup, and API contract tests.
