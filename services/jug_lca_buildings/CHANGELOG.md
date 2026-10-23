# Changelog

## [Unreleased]

### Identified LCA results
- Return original integer `feature_id` from each actual reader-created building.
  Reject duplicate input IDs and unresolved reader omissions/identity mismatches
  before enrichment; preserve the pinned reader's existing footprint policy.
- Isolate identifier-less historical cache entries with a new cache namespace;
  retain their files without deletion. Package version is unchanged.

### Added
- Add opt-in evaluation cache preparation through `JUG_LCA_ARTIFACTS_DIR`, recording declared source/reference-data provenance and installed software versions, with explicit verification for reuse and no deletion of existing artifacts.
- Log calculation and CSV cache outcomes with full request hashes and resolved cache directories for evaluation provenance without changing API responses or cache keys.
- Support Polygon and MultiPolygon coordinate layouts, including mixed collections, through shared direct/API validation with structured errors for unsupported geometry types or incorrect coordinate nesting.

### Changed
- Exclude unknown GeoJSON fields at FeatureCollection, Feature, Geometry, and Properties levels without modifying the original input.
- Apply shared Marshmallow validation and normalization to direct application calls and both emissions API endpoints before cache lookup; reject invalid batches with field details and use normalized input for computation, caching, and reporting.
- Refresh the computation/report cache namespace after ring-winding corrections so potentially incorrect older results are recomputed while existing artifacts are retained.

### Fixed
- Preserve multipart footprint areas and interior holes by adapting the pinned geometry reader to combine its Polygon parsing results into one building per MultiPolygon feature, without rewriting source geometry.
- Prevent clockwise exterior rings from crashing the geometry reader and incorrectly oriented holes from inflating footprint areas. Normalize ring direction in a working copy for Polygon and MultiPolygon without changing coordinate values or original inputs.

## [0.1.1] - 2026-04-28

### Added
- Added the Docker image on Docker Hub to use the package

## [0.1.0] - 2026-04-28

### Added
- Initial PyPI-ready packaging for `jug_lca_buildings`
- Apache 2.0 license metadata and package manifest
- Bundled service data files for source distribution and wheel builds
- Project metadata for building and uploading to TestPyPI first, then PyPI
