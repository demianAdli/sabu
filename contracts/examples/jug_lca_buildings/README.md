# JUG LCA Buildings Contract Artifacts

This folder contains example payloads for the `jug_lca_buildings` HTTP API.

Files
- `emissions.request.json`: Example JSON body for `POST /emissions`
- `emissions.response.201.json`: Example success response (201)
- `emissions.response.200.csv`: Example CSV download response for `POST /emissions?export=csv`
- `emissions_upload.response.400.invalid_json.json`: Example error when uploaded file is not valid JSON
- `emissions_upload.response.422.validation.json`: Example schema validation error for a missing required property in the second feature

Notes
- For `POST /emissions/upload`, upload a GeoJSON file whose JSON content matches `emissions.request.json`.
- `POST /emissions` and `POST /emissions/upload` support `?export=csv` to return a downloadable CSV report (`200 text/csv`) instead of the JSON response (`201 application/json`).
- Unknown fields on FeatureCollection, Feature, Geometry, and Properties objects are accepted and excluded from computation, caching, and reporting. The original object/file is preserved.
- All declared required fields remain required and non-null; numeric strings are normalized by Marshmallow. Schema validation adds no geometry type or coordinate length restrictions.
- One invalid feature rejects the entire batch before cache lookup. Both endpoints return `422` with nested field errors; JSON request-parser errors are wrapped in `errors.json`, while upload and application validation errors are directly under `errors`.
- Direct `EmissionsApplicationService.compute_emissions()` calls apply the same rules to objects, JSON text, and string file paths, raising `marshmallow.ValidationError` with details in `.messages`.
