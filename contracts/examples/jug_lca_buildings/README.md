# JUG LCA Buildings Contract Artifacts

This folder contains example payloads for the `jug_lca_buildings` HTTP API.

Files
- `emissions.request.json`: Example JSON body for `POST /emissions`
- `emissions.multipolygon.request.json`: One multipart building with an interior hole
- `emissions.mixed.request.json`: Polygon and MultiPolygon buildings in one collection
- `emissions.response.201.json`: Example success response (201)
- `emissions.response.200.csv`: Example CSV download response for `POST /emissions?export=csv`
- `emissions_upload.response.400.invalid_json.json`: Example error when uploaded file is not valid JSON
- `emissions_upload.response.422.validation.json`: Example schema validation error for a missing required property in the second feature

Notes
- For `POST /emissions/upload`, upload a GeoJSON file whose JSON content matches any of the request examples.
- `POST /emissions` and `POST /emissions/upload` support `?export=csv` to return a downloadable CSV report (`200 text/csv`) instead of the JSON response (`201 application/json`).
- Unknown fields on FeatureCollection, Feature, Geometry, and Properties objects are accepted and excluded from computation, caching, and reporting. The original object/file is preserved.
- All declared required fields remain required and non-null; numeric strings are normalized by Marshmallow. Geometry types are Polygon (three coordinate list levels) and MultiPolygon (four levels), and a collection may contain both. Unsupported types or incorrect nesting produce field errors. Validation adds no ring-length, closure, or topology rules.
- Parts and holes are retained; a MultiPolygon is passed to the workflow as one building feature. The calculation reader's existing restrictions, including its filtering of footprints smaller than 25 square metres, still apply.
- Either ring winding direction is accepted. The reader orients an internal copy with counterclockwise exterior rings and clockwise holes, using ring position to identify their roles. Coordinate values, parts, holes, and original inputs are preserved. Request examples use standard winding order.
- Coordinates must be WGS84 longitude/latitude; CRS conversion is an upstream responsibility. Accepting `crs` metadata does not reproject data.
- One invalid feature rejects the entire batch before cache lookup. Both endpoints return `422` with nested field errors; JSON request-parser errors are wrapped in `errors.json`, while upload and application validation errors are directly under `errors`.
- Direct `EmissionsApplicationService.compute_emissions()` calls apply the same rules to objects, JSON text, and string file paths, raising `marshmallow.ValidationError` with details in `.messages`.
