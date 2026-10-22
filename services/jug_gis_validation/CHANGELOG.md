# Changelog

## [Unreleased]

### Added
- Align the Marshmallow dependency range with the GIS/simulation baseline;
  observed deployment constraints are recorded under deploy/constraints.
- Standalone `uniquify` CLI command and `POST /uniquifications` endpoint, backed by a shared application operation that reuses the existing largest-area selection policy without census loading, comparisons, or plotting.
- Retained GeoJSON, input/retained/removed counts, and positional record traces with removed-to-retained mappings and selection reasons.
- Focused policy, trace reconciliation, CLI/API equivalence, input preservation, and validation compatibility tests.
